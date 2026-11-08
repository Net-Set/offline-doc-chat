# Stage 2 — Document 12: Test Strategy

| Field | Value |
|---|---|
| Document ID | DIP-TST-01 |
| Version | 0.1 |
| Builds on | `02` (FR/NFR), `05`–`14` (designs, acceptance criteria already stated there), `09` §5–7 (evaluation harness) |
| Note | Independent reference architecture. Thresholds are proposed acceptance values; those marked "(baseline)" are ratcheted from a measured baseline rather than asserted. |

---

## 1. Objectives and principles
1. **Prove the requirements, not the code:** every FR/NFR has at least one test; the traceability matrix (§13) is generated, not hand-maintained.
2. **Test pyramid with AI-specific layers:** many fast deterministic tests at the bottom; a *separate, statistical* evaluation layer for retrieval/RAG (their correctness is a measured rate, not pass/fail).
3. **Failure is a feature:** retry, DLQ, degradation, failover and permission-denial paths are tested as thoroughly as the happy path.
4. **Security tests are release gates**, not an end-phase activity (permission bypass, injection, sandbox escape).
5. **Realistic data without real secrets:** synthetic and sanitized corpora; production data is never used in lower environments (`13` §3).
6. **Deterministic where possible, statistical where not:** LLM and ANN behavior is evaluated on sample sets with confidence intervals, never on single outputs.
7. **Shift left, gate right:** fast checks at PR time; heavy suites (load, DR, full evaluation) on schedule and before promotion.
8. **Tests are code:** reviewed, versioned, flaky tests quarantined within 24 h and fixed within a sprint.

---

## 2. Test levels and scope

| Level | Scope | Tools (proposed) | Runs | Gate |
|---|---|---|---|---|
| L0 Static analysis | Lint, SAST, secret scan, license/SCA, Dockerfile/Helm/Terraform linting (hadolint, kube-linter, tfsec/checkov), OpenAPI lint (Spectral), Avro compat | SpotBugs/Semgrep/CodeQL, gitleaks, Trivy, Spectral | every PR | zero new high findings |
| L1 Unit | Domain logic: state machine, retry policy, chunker, RRF, evidence assessor, ACL evaluation, SQL validator | JUnit 5, AssertJ, Mockito (Java); pytest, hypothesis (Python) | every PR | ≥ 80% line / ≥ 70% branch on core packages; mutation score ≥ 60% on `domain` packages (PIT/mutmut) — nightly |
| L2 Component/integration | Service + real dependencies in containers: PG, Kafka, OpenSearch, vector DB, MinIO, Redis, Keycloak | Testcontainers, Spring Boot Test, embedded Schema Registry | every PR (≤ 15 min) | all pass |
| L3 Contract | HTTP API (provider/consumer), event schemas, DB migrations | Spring Cloud Contract/Pact, OpenAPI diff (`oasdiff`), Schema Registry compat, Flyway test | every PR | no breaking change without version bump |
| L4 API/system (ephemeral env) | Real deployed services in an ephemeral namespace; API tests, authz matrix, e2e ingestion→search | REST Assured, Schemathesis (OpenAPI fuzz), Karate/Playwright (UI smoke) | every PR on merge candidates; nightly full | all pass |
| L5 Data/ML evaluation | OCR accuracy, retrieval quality, RAG faithfulness, router accuracy, NL-to-SQL accuracy | Evaluation harness (`09` §7), ranx/trec-eval-style metrics, custom RAG judge + human review | on change to model/chunker/retrieval/prompt; nightly smoke; weekly full | gates in `09` §7.3 |
| L6 Non-functional | Load, stress, soak, spike, scalability, capacity validation | k6/Gatling (HTTP), custom Kafka producers, Locust (AI sessions), pgbench, vector/opensearch benchmarks | staging, scheduled + pre-release | NFR targets |
| L7 Resilience/chaos & DR | Fault injection, failover, restore | Chaos Mesh/Litmus, Toxiproxy, Velero/pgBackRest drills (`14` §12) | weekly staging / quarterly / annual | `14` §14 |
| L8 Security | AuthZ bypass, injection, sandbox, DAST, pen-test, supply chain | OWASP ZAP, custom red-team harness, fuzzers (AFL++/Jazzer/Atheris), Falco tests | per release + continuous | zero critical/high |
| L9 Acceptance (UAT) | Business scenarios with SMEs; usability | Scripted scenarios, timed tasks (BO-1) | each major milestone | BO targets |

---

## 3. Test data strategy

| Data set | Content | Source | Use | Controls |
|---|---|---|---|---|
| **Synthetic corpus** | Generated documents (reports, specs with revisions, tables, equations, scanned variants via degradation) with known ground truth | Generator scripts + public technical docs (arXiv, public standards, NASA/ESA public reports — check licenses) | L2–L6 | Contains no real data |
| **Public technical corpus** | Openly licensed research papers/specs, mixed layouts, scans | Public sources | Retrieval/RAG/OCR evaluation, load | License tracking per file |
| **Golden evaluation set** | Queries, labels, QA, conflicts, SQL, security probes (`09` §5.1) | SMEs + synthetic bootstrap (labeled) | L5 | Frozen test split, versioned |
| **Adversarial corpus** | Malformed/corrupt PDFs/OOXML, zip/PDF bombs, polyglots, macro documents, prompt-injection documents, homoglyph/zero-width attacks, EICAR test file | Crafted + public fuzz corpora | L8, L2 (validation) | Stored in isolated bucket; never processed outside sandbox |
| **Load corpus** | Distribution-matched page counts (P50/P95/P99 incl. 5,000+ page outliers) replicated with perturbations (unique hashes) | Derived from public + synthetic | L6 | Size to scenario (Initial 10k docs, Medium sample 100k, Large synthetic by amplification of chunks/vectors) |
| **Permission fixtures** | Org/department tree, users with every role/clearance combination, ACL permutations (grant/deny/inherit/expiry) | Generated from a model | authz matrix, bypass suite | Deterministic seed |
| **Migration fixtures** | Anonymized/synthetic dumps at multiple schema versions and sizes | Generated | migration tests | – |
Data rules: no production data in non-production; seeded random generators log seeds; test-data builders (not shared mutable fixtures); synthetic scale generation for Large uses **amplification** (replicate vectors/chunks with new IDs and perturbation) for index-scale benchmarks, flagged as approximate for recall conclusions (recall must be measured on real-distribution embeddings at ≥ 10M).

---

## 4. Test types in detail

### 4.1 Unit testing
- Domain invariants with property-based tests: state machine (only allowed transitions, idempotent replays), RRF properties (order independence of lists, monotonicity), chunk ID determinism and uniqueness, tag-expansion guard, backoff/jitter bounds, SQL validator (generated statement fuzz), evidence-band monotonicity (more unsupported claims never raises the band).
- Chunker: golden-file tests across document types (table splitting repeats header, equation retained with text, page references correct).
- Authorization: exhaustive table-driven matrix (role × classification × ACL effect × action) — ≥ 2,000 cases generated from the policy model, expected results from an independent reference implementation (differential testing).
- Python workers: handler purity tests (same input ⇒ same output bytes), poison-input handling.

### 4.2 Integration testing (component level)
| Area | Cases |
|---|---|
| Upload | Multipart resume after abort, hash mismatch, MIME mismatch, duplicate by SHA, new-version linkage, presigned URL expiry, outbox atomicity (kill after DB commit before publish → event still published) |
| Orchestrator | Duplicate completion events (advance once), out-of-order events, lease expiry re-issue, per-document concurrency cap, stale `pipeline_version` rejection, stuck-state sweeper |
| Workers | Idempotent re-execution (artifact bytes identical), checkpoint resume, timeout handling, sandbox limits (memory/time/pages), poison page → partial processing flags |
| Search | Filter compilation (ACL tags, version state), exact-search switch for narrow filters, RRF fusion with one engine empty/failed, degraded flags, parent expansion, cache keying with fingerprint |
| AI orchestration | Route rules, citation validator branches (every failure code), repair loop bound = 1, INSUFFICIENT_EVIDENCE conditions, LLM timeout fallback, session re-authorization after ACL change |
| Analytics | Validator accepts/rejects (corpus of 500 statements), row-level predicate injection, timeout/row-limit enforcement against ClickHouse |
| Persistence | Flyway up/down compatibility (N and N+1 images against schema N+1), partition creation/drop jobs, constraint behaviors, outbox cleanup, audit append-only trigger, hash-chain verifier |
| Security components | PDP decisions with caches/expiry, token validation (alg=none, wrong aud, expired, wrong signature, clock skew) |

### 4.3 Contract testing
- **HTTP:** provider tests generated from `dip-api-v1.yaml`; consumers (UI, internal clients) publish Pact/SCC contracts; CI blocks incompatible changes (`oasdiff`).
- **Events:** each producer has sample payloads per schema version; consumers' deserialization tests run against **all prior versions** (BACKWARD_TRANSITIVE) and default-handling (unknown enum symbols fall back to the safest default).
- **Model-server APIs:** embedding/reranker/NLI/LLM-gateway request/response schemas with golden fixtures; breaking change detection when model version changes dimension or tokenizer limits.
- **Database:** schema contract = migrations; tests assert views used by analytics (curated views) are stable.

### 4.4 API testing
Functional: every endpoint × (success, each documented 4xx/5xx, auth variants, idempotency replay, pagination edge cases). Fuzz: Schemathesis against OpenAPI (stateful links), boundary values (max sizes, unicode, null bytes), mass-assignment (extra fields rejected), IDOR checks (object IDs of other departments return 404 not 403), rate-limit behavior (429 + headers), error format (100% problem+json), response time smoke.
Authz matrix at API level: for each endpoint the same fixtures as unit matrix executed end-to-end (expected status including 404-instead-of-403).

### 4.5 Kafka testing
| Test | Method | Acceptance |
|---|---|---|
| Delivery/duplication | Redeliver each message ×3 (Testcontainers Kafka; also broker restarts) | Final state identical to single delivery |
| Ordering independence | Shuffle/delay completion events | Stage advances exactly once |
| Retry/DLQ topology | Inject TRANSIENT, RESOURCE, DETERMINISTIC, POISON failures | Correct tier path; partition not blocked; DLQ headers complete |
| Backpressure | Throttle downstream dependency | Consumers pause, lag bounded, no OOM; governor halts p2 release |
| Rebalance | Scale consumers up/down, kill members | No lost/duplicated side effects; rebalance time < 30 s with static membership |
| Priority fairness | Mixed p0/p1/p2 load | p0 P95 queue age ≤ 5 s while p2 saturates; p2 not starved when idle |
| Schema evolution | Add optional field, add enum symbol, attempt breaking change | Compat checks fail on breaking change; consumers survive additions |
| Outbox | Kafka outage 10 min during uploads | 0 lost events; drain order preserved per key |
| Broker failure | Kill 1 then 2 brokers (staging) | per `08` §10 |
| Replay | Offset reset on shadow consumer group | Derived tables converge (checksum equal) |
| Throughput | 10× planning peak for 1 h | produce P99 < 100 ms; lag returns to zero |

### 4.6 Database testing
Migrations (forward on fixtures of 3 sizes including a 100 M-row table for lock/timing check; online index creation; `NOT VALID` constraint validation), partition lifecycle (pre-create, detach, archive, drop), constraint/index tests (unique idempotency keys), isolation tests (concurrent stage advancement, optimistic locking), performance tests on hot paths (`processing_jobs` pull query, dispatcher, version status) with EXPLAIN plan assertions (no seq scans on large tables), vacuum/bloat soak, backup/restore + PITR verification (`14` §12), connection pool exhaustion tests (PgBouncer saturation), row-level security tests (if enabled), audit chain tamper tests.

### 4.7 OCR and extraction accuracy testing
| Metric | Set | Target (baseline-then-ratchet) |
|---|---|---|
| Character error rate (CER) | 300 labeled pages across quality levels | clean scans ≤ 1.5%, medium ≤ 4%, poor ≤ 12% |
| Word error rate (WER) | same | clean ≤ 4%, medium ≤ 10% |
| Reading order accuracy (Kendall-τ/edit distance on blocks) | 200 multi-column pages | ≥ 0.95 |
| Header/footer removal precision/recall | 200 pages | ≥ 0.95 / ≥ 0.90 |
| Table structure (TEDS or cell F1) | 150 tables (ruled/unruled/merged cells) | ≥ 0.85 ruled, ≥ 0.70 unruled |
| Equation recovery (LaTeX match or flagged image fallback) | 100 equations | ≥ 0.6 exact; 100% either text or image fallback (never silently dropped) |
| Language detection accuracy | per U-05 set | ≥ 0.98 |
| Page-triage correctness (digital vs scanned routing) | 1,000 pages | ≥ 0.98; false "digital" for scans ≤ 1% |
| Classification macro-F1 | labeled docs | ≥ 0.90 (and UNCLASSIFIED rather than guess below confidence) |
| Quality-flag calibration | pages flagged LOW_QUALITY vs human judgement | recall ≥ 0.9 |
Regression: any OCR/extraction pipeline change reruns the set; downstream retrieval metrics on affected documents are checked (L5).

### 4.8 Retrieval quality and RAG evaluation
Executed by the evaluation harness (`09` §7); acceptance (initially "baseline + no regression", then absolute ratchets):
| Metric | Target |
|---|---|
| Recall@50 (pre-rerank) | ≥ 0.95 |
| Recall@20 / nDCG@10 / MRR | ≥ 0.90 / ≥ 0.75 / ≥ 0.70 |
| Hybrid advantage | nDCG@10 ≥ best single retriever + 5 pt (otherwise the hybrid complexity is unjustified) |
| ANN recall@100 vs exact (filtered) | ≥ 0.97 |
| Faithfulness / citation precision / citation recall | ≥ 0.95 / ≥ 0.95 / ≥ 0.90 |
| Post-validation hallucination rate | ≤ 2% |
| Unanswerable detection / false refusal | ≥ 90% / ≤ 10% |
| Conflict detection recall (seeded) | ≥ 0.85 |
| Route accuracy / NL-to-SQL execution accuracy | ≥ 95% / ≥ 80% |
| Confidence-band reliability | HIGH band observed faithfulness ≥ 0.97 |
Method: frozen test split; paired bootstrap CIs; ≥ 200 retrieval queries and ≥ 150 QA items per comparison; per-slice reporting (doc type, language, scanned vs digital, table-heavy); human adjudication on a 10% sample of QA outputs each release, inter-annotator agreement (Cohen's κ ≥ 0.7) tracked; LLM-as-judge used **only** as a screening aid, calibrated against human labels, never as the sole gate.
Ablation tests (M8/M9): each pipeline stage toggled (`10` §9) to prove its value.

### 4.9 Performance, load, stress, soak, spike, scalability
| Test | Scenario | Pass criteria |
|---|---|---|
| **Load** (steady) | Planning peak mix (search 70%, AI 15%, doc reads 10%, upload 5%) for 1 h at 100% planning peak (U-08) | P95 latencies within NFR-PRF-01..04; error rate < 0.5%; saturation < 70% on all pools |
| **Stress** | Ramp to 200%, 300% of peak until failure | Graceful degradation (429/shedding, degraded flags), no data loss, no unauthorized exposure; recovery within 5 min after load removed; breaking point recorded |
| **Soak** | 100% mix for 24–72 h | No memory/handle leaks, stable p99, GC/vacuum healthy, disk growth as predicted, no lag creep |
| **Spike** | 0→300% in 30 s, 3×; bulk upload spike 1,000 files | Autoscaling reacts ≤ 5 min; queues absorb; p0 unaffected |
| **Ingestion throughput** | Backfill at 1×, 2× of 55k docs/day (scaled to environment) with mixed page distribution | Meets NFR-PRF-05; no head-of-line blocking (NFR-SCL-04: small-doc P95 degrades ≤ 20% when a 10k-page document is ingested) |
| **Scalability** | Vary replicas/shards/partitions (½×, 1×, 2×) | Throughput scales ≥ 70% linear until named bottleneck |
| **Capacity validation** | Benchmarks B1–B6 (`09` §9.5) + DB connection, Kafka, network tests | Replace estimates in capacity doc; variance ≤ ±25% or model updated |
| **Index-scale** | 10M / 100M / 1B vectors with ACL filters | ADR-006 decision data |
| **Endurance of GPU pools** | 24 h continuous embedding/OCR | Thermal/OOM-free, throughput stable |
| **Tail-latency** | Replica/shard stragglers (inject 2 s delay on one shard) | Hedging keeps P99 within 2× P95 |
Method: open-model load generation (arrival-rate driven, not closed-loop) to avoid coordinated omission; production-like data distributions; warm-up excluded; results reported with percentiles and saturation metrics; benchmarks run on dedicated staging hardware, repeated ≥ 3 times, variance reported.

### 4.10 Security testing (details in `12` §15)
Permission-bypass suite (10k randomized + adversarial probes: search, AI, cache, chat, export, errors, timing); prompt-injection corpus (≥ 200); sandbox/parser exploit corpus and fuzzing (continuous fuzz of extraction workers); SQL safety corpus; DAST (ZAP) on staging; dependency/image scanning in pipeline; pen-test (external + internal) before production and annually; secrets scanning; policy/admission tests; audit tamper test; crypto-erasure test; network isolation matrix. Findings policy: critical/high block release; medium within 30 days; low backlog.

### 4.11 Disaster recovery and resilience testing
As in `14` §12: weekly restore verification, weekly chaos in staging, quarterly Kafka/PG failover drills, semi-annual cross-site exercise, annual game day and ransomware rebuild, deletion/erasure replay test. Resilience unit: for every dependency in the degradation matrix a **fault-injection test** asserts the documented degraded behavior (e.g., kill vector DB ⇒ search returns 200 with `degraded=true`, BM25-only).

### 4.12 Usability and acceptance (UAT)
Timed task study (30 tasks, ≥ 12 participants across personas) for BO-1; scripted scenarios per persona (document controller supersession workflow, analyst NL-to-SQL, auditor investigation); accessibility checks (WCAG 2.1 AA target for the UI — UI scope owned by the front-end plan, flagged here); error-message comprehension test; feedback loop into the golden set.

---

## 5. Test environments and tooling matrix
| Environment | Used for |
|---|---|
| Developer machine/dev cluster | L0–L2 (Testcontainers) |
| Ephemeral PR namespaces (test cluster) | L3–L4 |
| Staging (production-like, HA, sanitized/public corpus) | L5–L8, DR drills, perf |
| Production | Synthetic canaries (`17`), controlled game days, A/B and shadow evaluation |
Tooling is containerized and versioned; GPU-dependent tests run on staging GPUs or use tiny models in CI with recorded fixtures (and are explicitly labeled "functional only — not quality evidence").

---

## 6. Entry/exit criteria and gates per milestone

| Gate | Entry | Exit (must all hold) |
|---|---|---|
| PR merge | CI green | L0–L3 pass; coverage gates; no unreviewed schema/API/event breaking change |
| Promote to staging | Merged, signed image | L4 pass, security scans pass, eval smoke pass |
| Release candidate | Staging soak 24 h clean | Eval gates (`09` §7.3), perf gates, security suite 100%, DR quick-check, UAT sign-off for the milestone scope |
| Production promotion | RC approved | Two-person approval, rollback plan, canary analysis pass |
| Milestone M-n completion | Deliverables merged | Milestone-specific criteria (see roadmap) |
| Production readiness (M14) | All milestones | Checklist complete incl. verified DR (≤ 12 months), pen-test closure, capacity validated |

## 7. Defect management
Severity: S1 (data exposure, data loss, platform down) → fix immediately, release blocker; S2 (major function broken, SLO breach, workaround exists) → blocker for the affected milestone; S3 (minor) → scheduled; S4 (cosmetic). Triage SLAs (S1 4 h, S2 2 d). Every S1/S2 gets a regression test before closure and a root-cause note. Quality metrics tracked: escaped defects, change failure rate, MTTR, flaky-test rate (< 1%), test duration budget (PR pipeline ≤ 20 min).

## 8. Flaky-test and nondeterminism policy
LLM and ANN-dependent tests use fixed seeds/temperatures and **tolerance bands**, or run in the statistical layer (L5). Time-dependent tests use controllable clocks. No sleeps (await conditions with timeouts). Quarantine tag with auto-ticket; quarantined tests don't count toward gates but are reviewed weekly.

## 9. Test automation architecture
Shared libraries: fixtures/builders, Keycloak test realm, permission-model generator, Kafka test harness (`testkit` with delay/duplicate/reorder injectors), evaluation harness CLI (`dip-eval run --suite retrieval --config …` writing JSON reports to object store and registry), report aggregator publishing to dashboards. CI orchestration by path filters (e.g., changes under `chunking/**` trigger retrieval eval). All reports archived (≥ 1 year) for audit.

## 10. Measurable acceptance criteria summary (by requirement area)
| Area | Criterion | Target |
|---|---|---|
| Functional coverage | FR with ≥ 1 automated test | 100% of M-priority FRs |
| Code | Line/branch coverage (core) | ≥ 80% / ≥ 70% |
| API | Contract/OpenAPI conformance | 100% endpoints, 0 undocumented responses |
| Events | Schema compat + idempotency | 100% topics covered |
| OCR | CER/WER, tables | §4.7 |
| Retrieval | Recall/nDCG/MRR | §4.8 |
| RAG | Faithfulness, citation P/R, hallucination | §4.8 |
| Search latency | P95 | ≤ 800 ms (Initial/Medium) / ≤ 1.5 s (Large) |
| RAG latency | TTFT / complete P95 | ≤ 3 s / ≤ 15 s |
| Ingestion | Throughput | NFR-PRF-05; small-doc degradation ≤ 20% |
| Availability | Online path under single-component fault | SLO maintained |
| Security | Permission leaks, injection exfil | 0 |
| DR | Measured RTO/RPO | `14` §14 |
| Capacity | Model-vs-measured variance | ≤ ±25% |
| Usability | Task time reduction | ≥ 50% median (BO-1) |

## 11. Risks to testing
| Risk | Mitigation |
|---|---|
| No golden data (R11) | Start SME labeling M1; flag synthetic; block quality claims without it |
| Staging cannot reproduce Large scale | Scale-proportional tests + amplification + analytical models; report extrapolation uncertainty; first Large rollout phased with enhanced monitoring |
| GPU availability for tests | Reserve staging GPUs; off-peak scheduling; tiny-model CI |
| LLM non-determinism inflating variance | Larger samples, paired designs, fixed decoding |
| Test data licensing | License register for public corpora |
| Test duration growth | Parallelization, path-based triggers, nightly/weekly tiers |

## 12. Open items
| Item | Plan |
|---|---|
| UI test scope | Define with front-end design (not covered in this architecture set) |
| Human review capacity for RAG adjudication | Plan SME hours per release (e.g., 150 items × 3 min × 2 raters ≈ 15 h) |
| Chaos tooling choice (Chaos Mesh vs Litmus) | Spike in M3 |
| Large-scale synthetic amplification validity | Validate against a real 10M-vector set before trusting latency numbers |

## 13. Requirements traceability (generation rule)
Each test carries tags `@FR-XXX-nn` / `@NFR-XXX-nn`; the pipeline builds the matrix `requirement → tests → last result`; CI fails if an M-priority requirement has zero tests or its latest run failed. Excerpt:
| Requirement | Tests |
|---|---|
| FR-DOC-02 resumable upload | IT: multipart resume; API: upload flow; load: bulk upload |
| FR-PRC-12 page-range tasks | IT: cap per document; perf: big-doc isolation |
| FR-SRC-02 ACL filters | unit matrix; IT filter compile; security bypass suite |
| FR-AI-04 citation validation | unit (all failure codes); RAG eval citation precision |
| FR-AI-05 insufficient evidence | RAG eval unanswerable set |
| FR-ANL-02 safe NL-to-SQL | validator corpus; security SQL suite; execution accuracy |
| NFR-REL-04 at-least-once idempotent | Kafka duplicate/redelivery tests |
| NFR-SEC-03 zero unauthorized exposure | permission-bypass suite |
| NFR-PRF-05 ingestion throughput | ingestion load test |
| NFR-AVL-01 availability | chaos + soak + canary SLO reports |

## 14. Next
Performance and Capacity Planning (doc 16), Monitoring and Observability (doc 17).
