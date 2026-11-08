"""Golden-question regression test for the running local app.

  venv\\Scripts\\python.exe tests\\run_golden.py            # run everything
  venv\\Scripts\\python.exe tests\\run_golden.py scan table  # only cases whose id/category contains these words

Uploads the fixtures (tests/make_fixtures.py), asks every question in tests/golden.json (scoped to the matching
document, like ticking its checkbox, or to all documents for doc "*"), checks the answers and prints accuracy per
category plus timing. Results are saved to tests/last_run.json. Cases marked "known_weak" are reported but do not
count against the pass threshold.
"""
import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8000"
THRESHOLD = 0.85


def main():
    sys.path.insert(0, str(HERE))
    import make_fixtures

    make_fixtures.main()
    fixtures = sorted((HERE / "fixtures").iterdir())
    cases = json.loads((HERE / "golden.json").read_text(encoding="utf-8"))
    words = [a.lower() for a in sys.argv[1:]]
    c = httpx.Client(base_url=BASE, timeout=1800)
    assert c.get("/api/health").json()["llm"], "start the app first (start.bat)"

    # start from a clean slate so the test is reproducible
    names = {f.name for f in fixtures}
    for d in c.get("/api/documents").json():          # only replace the fixtures' own copies; never touch the user's documents
        if d["name"] in names:
            c.delete(f"/api/documents/{d['id']}")
    ids, ingest = {}, {}
    for f in fixtures:
        t0 = time.time()
        r = c.post("/api/documents", files=[("files", (f.name, f.read_bytes()))]).json()[0]
        if "error" in r:
            print("upload error", f.name, r["error"]); continue
        while True:
            d = next(x for x in c.get("/api/documents").json() if x["id"] == r["id"])
            if d["state"] in ("INDEXED", "FAILED"):
                break
            time.sleep(1)
        ids[f.name] = d["id"]
        ingest[f.name] = {"state": d["state"], "pages": d["pages"], "chunks": d["chunks"], "seconds": round(time.time() - t0, 1), "detail": d["detail"]}
        print(f"  ingest {f.name:28s} {d['state']:8s} {d['pages']} pages {d['chunks']} passages {time.time() - t0:5.1f}s  {d['detail'] or ''}")

    results, sessions = [], {}
    for case in cases:
        if words and not any(w in case["id"].lower() or w in case["category"].lower() for w in words):
            continue
        scope = None if case["doc"] == "*" else [ids.get(case["doc"])]
        if scope == [None]:
            print(f"SKIP {case['id']} (fixture missing)"); continue
        t0, final, ev = time.time(), None, None
        with c.stream("POST", "/api/chat", json={"question": case["q"], "doc_ids": scope, "session_id": sessions.get(case.get("session"))}) as r:
            for line in r.iter_lines():
                if line.startswith("event:"):
                    ev = line[6:].strip()
                elif line.startswith("data:"):
                    dd = json.loads(line[5:])
                    if ev == "session" and case.get("session"):
                        sessions[case["session"]] = dd["session_id"]
                    elif ev == "final":
                        final = dd
        secs = time.time() - t0
        ans = final["answer"]
        low = ans.lower()
        checks = []
        for s in case.get("contains_all", []):
            s = s.replace("{ndocs}", str(sum(1 for d in c.get("/api/documents").json() if d["state"] == "INDEXED")))
            checks.append(("has " + s, s.lower() in low))
        if case.get("contains_any"):
            checks.append(("has any of " + "/".join(case["contains_any"]), any(s.lower() in low for s in case["contains_any"])))
        for s in case.get("not_contains", []):
            checks.append(("lacks " + s, s.lower() not in low))
        if case.get("status"):
            checks.append(("status " + final["evidence_status"], final["evidence_status"] in case["status"]))
        if case.get("method"):
            m = final["validation"].get("method", "llm")
            checks.append(("method " + m, m == case["method"]))
        if case.get("page"):
            checks.append((f"cites page {case['page']}", any(s["page"] == case["page"] for s in final["sources"])))
        ok = all(v for _, v in checks)
        results.append({"id": case["id"], "category": case["category"], "ok": ok, "known_weak": bool(case.get("known_weak")),
                        "seconds": round(secs, 1), "answer": ans[:300], "failed": [k for k, v in checks if not v],
                        "method": final["validation"].get("method", "llm")})
        print(f"{'PASS' if ok else 'FAIL'} {case['id']:18s} {secs:6.1f}s  [{results[-1]['method']}]  {ans[:110].replace(chr(10), ' ')}"
              + ("" if ok else f"\n      failed: {results[-1]['failed']}"))

    print("\n=== accuracy by category (known_weak cases excluded) ===")
    cats = sorted({r["category"] for r in results})
    total_ok = total = 0
    for cat in cats:
        rs = [r for r in results if r["category"] == cat and not r["known_weak"]]
        if rs:
            n_ok = sum(r["ok"] for r in rs)
            total_ok += n_ok; total += len(rs)
            print(f"  {cat:10s} {n_ok}/{len(rs)}  ({100 * n_ok / len(rs):.0f}%)  avg {sum(r['seconds'] for r in rs) / len(rs):.1f}s")
    weak = [r for r in results if r["known_weak"]]
    for r in weak:
        print(f"  known-weak {r['id']}: {'PASS' if r['ok'] else 'fail'}")
    rate = total_ok / total if total else 0
    print(f"\nOVERALL {total_ok}/{total} = {100 * rate:.0f}%  (threshold {int(THRESHOLD * 100)}%)")
    (HERE / "last_run.json").write_text(json.dumps({"ingest": ingest, "results": results, "overall": rate}, indent=2), encoding="utf-8")
    sys.exit(0 if rate >= THRESHOLD else 1)


if __name__ == "__main__":
    main()
