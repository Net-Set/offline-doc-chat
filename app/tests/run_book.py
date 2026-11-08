"""Structure checks for a BOOK already uploaded to the app (e.g. the NCERT maths textbook M1.pdf). Does not upload or delete anything.

  venv\\Scripts\\python.exe tests\\run_book.py [part-of-document-name]      (default: M1)
"""
import json
import sys
import time

import httpx

NAME = (sys.argv[1] if len(sys.argv) > 1 else "M1").lower()
c = httpx.Client(base_url="http://127.0.0.1:8000", timeout=900)
docs = [d for d in c.get("/api/documents").json() if NAME in d["name"].lower() and d["state"] == "INDEXED"]
assert docs, f"no indexed document with '{NAME}' in its name"
doc = docs[0]

CASES = [  # (question, must contain all, must NOT contain)
    ("hi", ["Hello"], []),
    ("can you tell me math book how much chapater", ["6 chapters", "Matrices", "Determinants"], []),
    ("how many chapters", ["6 chapters"], []),
    ("list the chapters", ["Relations and Functions", "Application of Derivatives"], []),
    ("what is chapter 3 about", ["Matrices", "3.4 Operations on Matrices"], []),
    ("3rd chapter", ["Matrices"], []),
    ("which chapter is about determinants", ["chapter 4", "Determinants"], []),
    ("what is section 3.4.5", ["Multiplication of matrices", "page 86"], []),
    ("what is on page 86", ["Page 86"], ["<br>", "<!--"]),
    ("how many pages does the book have", ["300 pages"], []),
]
ok = 0
for q, must, mustnot in CASES:
    t, fin, ev = time.time(), None, None
    with c.stream("POST", "/api/chat", json={"question": q, "doc_ids": [doc["id"]]}) as r:
        for line in r.iter_lines():
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:") and ev == "final":
                fin = json.loads(line[5:])
    a = fin["answer"]
    good = all(m.lower() in a.lower() for m in must) and not any(m in a for m in mustnot)
    ok += good
    print(f"{'PASS' if good else 'FAIL'} {time.time() - t:5.1f}s  {q!r}\n      {a[:200]!r}")
print(f"\n{ok}/{len(CASES)} passed on {doc['name']}")
sys.exit(0 if ok == len(CASES) else 1)
