# Enterprise AI Document Intelligence & Knowledge Analytics Platform
## Stage 1 — Part A: Executive Summary, Scope, Assumptions and Constraints

| Field | Value |
|---|---|
| Document ID | DIP-S1-A |
| Version | 0.1 (Draft for architecture approval) |
| Status | Awaiting approval (Gate G1) |
| Nature | Independent **reference architecture**. Not an official ISRO project, requirement set, or security policy. Every ISRO-related statement is an *inspiration*, not a fact about ISRO. |

Companion documents: `02-brd-srs-requirements.md`, `03-context-hld-decisions-risks.md`.

---

## 1. Executive Summary

**What we are building.** A secure, distributed platform that turns a very large, continuously growing corpus of technical documents (PDF, DOCX, XLSX, PPTX, scans, images, research papers) into governed, searchable, analyzable knowledge. It is *not* a PDF chatbot. It has four separate engines that are deliberately not conflated:

| Engine | Answers | Technique | Example question |
|---|---|---|---|
| **Retrieval** | "Where is it written?" | BM25 + vector + metadata filters + reranking | "Find all passages on thermal limits of the X battery pack." |
| **Grounded reasoning (RAG)** | "What do the documents say, and do they agree?" | Retrieval → LLM with citation validation | "Do Rev B and Rev C of the power spec disagree on bus voltage?" |
| **Structured analytics** | "How many / how much / what trend?" | SQL on PostgreSQL/ClickHouse/Iceberg | "How many reports per department per year were superseded?" |
| **Statistical / batch analysis** | "What pattern exists across millions of rows?" | Spark jobs over the lakehouse | "Topic drift of failure reports over 15 years." |

**Why.** Large technical organizations accumulate millions of versioned, interrelated documents. The cost is not storage; it is that engineers cannot find the authoritative, current, non-contradicted answer, and cannot prove where an answer came from. Value comes from (a) retrieval with verifiable page-level provenance, (b) detecting superseded and conflicting specifications, (c) analytics that an LLM must never guess, and (d) auditability.

**How, in one paragraph.** Uploads land in object storage and emit events on Kafka. Independent worker pools (extraction, OCR, table/layout, classification, chunking, embedding, indexing) process documents page-range by page-range, checkpointing to PostgreSQL. Searchable knowledge is split by purpose: metadata/state in PostgreSQL, full text in OpenSearch (BM25), vectors in a vector database, binaries and parsed artifacts in object storage, analytical facts in an Iceberg lakehouse served by ClickHouse. A query router decides *deterministically first* whether a question needs retrieval, SQL, Spark, or a combination. Authorization is enforced **inside the retrieval layer, before any text reaches an LLM**. Answers are structured, cite document/version/page, and every citation is mechanically validated against stored source text.

**Design stance (principal-architect summary).**
1. Deterministic pipelines first; agents only where a fixed pipeline cannot work.
2. Source of truth is object storage + PostgreSQL; every index is *rebuildable* and therefore disposable.
3. At-least-once delivery + idempotent consumers; we do not claim end-to-end exactly-once.
4. Start as a modular system that deploys small (10k docs on a few nodes) and scales out by changing deployment, not architecture.
5. Do not index everything at maximum fidelity: tiering and quantization are first-class because 5 B pages is a stress case, not a default.

**Expected outcome of Stage 1.** Agreement on scope, requirements, context, initial HLD, technology direction, and risks, so that Stage 2 (detailed HLD, LLD, DB, API, AI, roadmap, remaining documents) is built on stable ground.

---

## 2. Project Scope

### 2.1 In scope (mandatory, "MUST")
| ID | Capability |
|---|---|
| S-01 | Identity, RBAC + ABAC, org/department hierarchy, document-level permissions, audit |
| S-02 | Single, bulk, large, resumable uploads; validation; MIME verification; duplicate detection; versioning; lifecycle; retention |
| S-03 | Async processing: text, OCR, tables, images, equations, layout, header/footer, language, classification, quality validation |
| S-04 | Structure-aware chunking with parent-child hierarchy and page provenance |
| S-05 | Embedding service with model registry, versioning, batch/GPU, re-embedding and migration |
| S-06 | Hybrid search (BM25 + vector + metadata filter), fusion, reranking |
| S-07 | Grounded multi-document Q&A with page-level citations and mechanical citation validation |
| S-08 | Document version comparison; conflict detection; superseded-information detection |
| S-09 | Summaries and reports (grounded, cited) |
| S-10 | Structured analytics: safe NL-to-SQL, aggregation, trends; query router (RAG vs SQL vs Spark vs combined) |
| S-11 | Security: encryption, secrets/key mgmt, tenant isolation, prompt-injection and malicious-document defenses, private model deployment |
| S-12 | Reliability: retries, DLQ, circuit breakers, reconciliation, backup/DR |
| S-13 | Model/prompt management, evaluation harness, regression gating |
| S-14 | Observability, CI/CD, IaC, Kubernetes deployment |

### 2.2 Optional / future ("SHOULD"/"MAY")
| ID | Capability | Reason deferred |
|---|---|---|
| F-01 | Graph RAG (entity/relationship graph) | High build cost; value unproven until evaluation data exists. Pilot on a subset after M9. |
| F-02 | Agentic multi-step RAG | Only for questions the router flags as multi-hop and where decomposition beats a fixed plan. |
| F-03 | Predictive analytics (forecasting) | Needs stable historical data; after analytics engine matures. |
| F-04 | Multilingual / Indic-language OCR and retrieval | Depends on language mix (unresolved decision U-05). |
| F-05 | Cross-organization federation | Out of initial scope; tenant model must not preclude it. |
| F-06 | Fine-tuned domain embedding / reranker models | Only after evaluation shows off-the-shelf models plateau. |
| F-07 | Image/diagram semantic search (multimodal embeddings) | Phase 2; v1 indexes extracted captions and OCR text of figures. |

### 2.3 Out of scope
- Replacing the organization's authoring tools or document management of record (we ingest from them).
- Any claim of compliance with a named government security standard (to be determined by the owning organization; see U-03).
- Real-time collaborative editing, workflow/approval engines, e-signature.
- Training foundation LLMs.

### 2.4 Users (hypothetical personas)
Engineer/researcher (search, Q&A), configuration/document controller (versions, supersession), analyst (analytics), department admin (permissions), security auditor (audit), platform operator (ops, models).

---

## 3. Assumptions and Constraints

All numbers are **hypothetical design assumptions**, not organizational data. Each is tagged with how it will be validated.

### 3.1 Scale assumptions (design envelope)
| ID | Assumption | Value | Validation |
|---|---|---|---|
| A-01 | Documents at full scale | 10,000,000 | Stakeholder inventory |
| A-02 | Average pages / document | 500 (heavily skewed; long tail to 10,000+ pages) | Sample 1,000 real docs, publish the distribution (P50/P95/P99) |
| A-03 | Total pages | 5,000,000,000 | Derived |
| A-04 | Average tokens / page | ~500 (tables/equations raise this) | Tokenize sample |
| A-05 | Average source file size | ~20 MB (scan-heavy docs far larger) | Sample |
| A-06 | Share of scanned (OCR-required) pages | 30% (unknown; dominates compute cost) | Sample; **highest-sensitivity assumption** |
| A-07 | Versions per document | avg 2.5 retained | Policy decision |
| A-08 | Concurrent users | up to several thousand; ~10% issuing queries at peak | Pilot telemetry |
| A-09 | Ingestion pattern | Initial backfill over ~6 months, then continuous | Business plan |

### 3.2 Derived indicative sizing (to be replaced by benchmarks in the Performance and Capacity document)
These show *why* design choices are forced; they are not infrastructure quotes.

| Quantity | Calculation | Result |
|---|---|---|
| Child chunks (512-token target, ~12% overlap) | 5×10⁹ pages × 500 tokens ÷ ~450 net tokens/chunk | **≈ 5.5 × 10⁹** (sizing basis; note the LLD default structure-aware child target is 384 tokens ≈ 345 net, which would give ≈ 7.2 × 10⁹ — a +30% sensitivity covered in `16` §7.1 and to be settled by the M5 chunk-size study) |
| Raw vectors, 1024-dim float32 | 5.5×10⁹ × 4 KB | ≈ 22 TB |
| Vectors, int8 scalar-quantized | 5.5×10⁹ × 1 KB | ≈ 5.5 TB |
| Vectors, binary-quantized (first-pass) | 5.5×10⁹ × 128 B | ≈ 0.7 TB |
| HNSW graph overhead (M=16) | ~150–250 B/vector | ≈ 1 TB |
| Embedding workload | 5.5×10⁹ × 512 tokens | ≈ 2.8 × 10¹² tokens |
| Embedding GPU-time at assumed 20k tokens/s/GPU (**must benchmark**) | 2.8×10¹² ÷ 2×10⁴ | ≈ 39,000 GPU-hours (≈ 25 days on 64 GPUs) |
| Raw source storage | 10⁷ × 20 MB × 2.5 versions | ≈ 500 TB (before dedup/compression) |

| Tier | Docs | Pages | Chunks (est.) | float32 vectors |
|---|---|---|---|---|
| Initial | 10,000 | 5 M | ~5.5 M | ~22 GB |
| Medium | 1,000,000 | 500 M | ~550 M | ~2.2 TB |
| Large | 10,000,000 | 5 B | ~5.5 B | ~22 TB |

**Consequences that drive the architecture:**
- Initial tier fits one vector node; Large tier is impossible without quantization, disk-based ANN, sharding and tiered indexing (hot: current versions / recent; cold: superseded, archive, scanned pages with low OCR confidence).
- OCR and embedding are the cost centers; GPU pools and queue-based scheduling are mandatory, not optional.
- Page-count skew means *work must be split below the document level* (page-range tasks).

### 3.3 Constraints
| ID | Constraint | Implication |
|---|---|---|
| C-01 | Backend: Java Spring Boot (primary); Python for AI/ML | Two runtimes; contracts via Protobuf/JSON-Schema + Schema Registry |
| C-02 | Confidential content must never reach external AI providers | Self-hosted models; egress-blocked inference network; external APIs allowed only for non-sensitive/dev with explicit policy |
| C-03 | Permissions enforced before context reaches LLM | Authorization filters pushed into every index query; post-filter re-check before prompt assembly |
| C-04 | Likely restricted/air-gapped or sovereign infrastructure (assumed) | No hard dependency on proprietary SaaS; S3-compatible storage; self-managed Kafka/K8s; offline model artifacts and image registry |
| C-05 | Source documents are immutable once stored | Versioning by new version, never mutation; content-hash addressing |
| C-06 | LLM output is non-deterministic and uncalibrated | Citations are mechanically validated; confidence is derived from evidence signals, not LLM self-report |
| C-07 | Auditability | Append-only audit trail incl. which chunks were exposed to which user and prompt/model version |

### 3.4 Unresolved decisions (need stakeholder input before or during Stage 2)
| ID | Question | Why it matters | Needed by |
|---|---|---|---|
| U-01 | On-prem, sovereign cloud, or hybrid? | Determines managed services vs self-managed, GPU procurement | Before M12 / ADR-001 |
| U-02 | Which data classification levels exist, and may mixed levels share a cluster? | Drives tenant isolation (shared index with ACL vs separate clusters) | Before HLD finalization |
| U-03 | Compliance regime and audit retention periods | Retention, key mgmt, deletion semantics | Before M11 |
| U-04 | Authoritative identity provider (existing LDAP/AD/Keycloak/other)? | Federation design | Before M1 |
| U-05 | Languages and scripts in corpus | OCR/embedding model choice | Before M4 |
| U-06 | Is there a golden evaluation set / SMEs to label one? | Evaluation gating, model selection | Before M5 |
| U-07 | Source systems to integrate (file shares, DMS, email) | Ingestion connectors | Before M3 |
| U-08 | Expected query volume and latency SLO tolerance | Sizing of reranker/LLM GPUs | Before capacity doc |
| U-09 | Is an approved LLM available inside the boundary, and its license? | LLM choice and quality ceiling | Before M8 |
| U-10 | Does "delete" mean legal-hold-aware soft delete or cryptographic erasure? | Secure deletion design | Before M11 |
