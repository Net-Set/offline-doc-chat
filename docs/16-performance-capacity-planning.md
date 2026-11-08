# Stage 2 — Document 13: Performance and Capacity Planning

| Field | Value |
|---|---|
| Document ID | DIP-CAP-01 |
| Version | 0.1 |
| Builds on | `01` §3 (assumptions A-01…A-09, derived sizing), `02` §4 (NFRs), `08` §3.1, `09` §3–4, `11` §3.3, §8, `13` §5, `14` §8.3 |
| Note | **Every number here is a calculation from stated assumptions, not a measurement.** Labels: **[S]** = stated assumption from the brief/SRS; **[A]** = engineering assumption to be replaced by a benchmark; **[D]** = derived. The deliverable of this document is the *model* and the *validation plan*; infrastructure counts become commitments only after benchmarks B1–B6 and load tests (M3/M6/M13) update the parameters. Independent reference architecture, not organizational data. |

---

## 1. Method
1. State workload drivers (documents, pages, users, query rates).
2. Convert to resource demand per component with explicit unit costs (seconds/page, tokens/s/GPU, bytes/chunk).
3. Add headroom (target utilization ≤ 60–70% at peak to keep P95 stable — queueing rule: waiting time grows sharply beyond ~70% utilization), failure headroom (N+1 per failure domain), growth margin (30%).
4. Run sensitivity analysis on the parameters that dominate cost.
5. Define benchmarks that *measure* each unit cost; recompute; accept the model only when predicted vs measured agree within ±25%.

---

## 2. Workload model

### 2.1 Corpus drivers
| ID | Parameter | Initial | Medium | Large | Label |
|---|---|---|---|---|---|
| W1 | Documents | 10,000 | 1,000,000 | 10,000,000 | [S] |
| W2 | Pages/document (mean; heavy-tailed, P99 ≈ 10,000) | 500 | 500 | 500 | [S] |
| W3 | Pages | 5 M | 500 M | 5 B | [D] |
| W4 | Tokens/page | 500 | 500 | 500 | [A] |
| W5 | Net tokens/chunk (512 target, ~12% overlap) | 450 | 450 | 450 | [A] — **caveat:** the LLD default child target is 384 tokens (≈ 345 net, 10% overlap), which raises chunk counts, vectors, index sizes and embedding *chunk* counts by ≈ 30% (tokens embedded stay the same); until the M5 chunk-size study decides, treat vector/OpenSearch/PG figures as lower bounds (+30% sensitivity in §7.1) |
| W6 | Chunks (child) = W3 × W4 ÷ W5 | 5.6 M | 556 M | 5.56 B | [D] (rounded ≈ 5.5 M / 550 M / 5.5 B elsewhere) |
| W7 | Parent chunks (≈ 1 per 5 children, not embedded) | 1.1 M | 110 M | 1.1 B | [A] |
| W8 | Avg file size | 20 MB | 20 MB | 20 MB | [A] |
| W9 | Versions retained | 2.5 | 2.5 | 2.5 | [A] |
| W10 | Scanned share of pages | 30% | 30% | 30% | [A] — highest-sensitivity |
| W11 | Ingestion mode | 24 h burst | 180 d backfill, then steady | 180 d backfill, then steady | [S/A] |
| W12 | Steady-state ingestion after backfill (new docs/day) | 100 | 1,000 | 10,000 | [A] |

### 2.2 Usage drivers (hypothetical, U-08 default)
| ID | Parameter | Initial | Medium | Large | Label |
|---|---|---|---|---|---|
| U1 | Registered users | 500 | 10,000 | 50,000 | [A] |
| U2 | Peak concurrent active users | 50 | 1,000 | 5,000 (NFR-SCL-02 "thousands") | [A] |
| U3 | Peak search requests/s (all kinds incl. retrieval inside RAG) | 5 | 100 | 400 | [A] (U-08 default) |
| U4 | Peak AI (RAG/summarize/compare) queries/s | 1 | 20 | 80 | [A] = 20% of U3 |
| U5 | Peak analytics queries/s | 0.1 | 1 | 4 | [A] |
| U6 | Peak document metadata/status reads/s | 20 | 300 | 1,500 | [A] |
| U7 | Peak-equivalent hours/day for token/cost budgeting | 2 | 2 | 2 | [A] |
Little's-law cross-check (concurrency = rate × time): 100 search req/s × 0.8 s ≈ 80 in-flight searches at Medium (400 × 1.5 s ≈ 600 at Large); 20 AI req/s × ~12 s ≈ 240 in-flight AI requests (80 × 12 s ≈ 960 at Large). With a think time of ~10 s between searches, 1,000 active users generate ≈ 100 req/s and 5,000 generate ≈ 500 req/s (planning peak 400 → treat 400–500 as the Large range; the sensitivity cases cover 1.25×). This is how NFR-SCL-02 "concurrent active users" maps to request rates. Note: U3 includes the retrieval executed by AI queries. 100 and 400 q/s are planning stress values; real telemetry in the pilot (Initial) replaces them (reduces risk R13).

---

## 3. Unit costs (to be benchmarked)
| ID | Unit cost | Value | Label | Benchmark |
|---|---|---|---|---|
| C1 | Digital-page extraction CPU | 0.4 core-s/page | [A] | B7 (extraction) |
| C2 | OCR GPU time | 0.5 GPU-s/page | [A] | B2 |
| C3 | Embedding throughput | 20,000 tokens/s/GPU (FP16) | [A] | B1 |
| C4 | Reranker throughput | 60–100k tokens/s/GPU | [A] | B3 |
| C5 | Rerank candidates × window | 30 × (256 + 30) = 8.6k tokens/query | [A] | B3 |
| C6 | LLM prefill (8–14B-class) | 8–10k tokens/s/GPU | [A] | B4 |
| C7 | LLM decode (aggregate with batching) | 1–2k tokens/s/GPU | [A] | B4 |
| C8 | RAG prompt / output tokens | 6,300 in (6,000 evidence + 300 instr.) / 300 out | [A] | eval |
| C9 | NLI per claim batch | 3 claims × ~400 tokens → 1.2k tokens/answer | [A] | B6 |
| C10 | HNSW graph overhead (M=16) | 150 B/vector | [A] | B5 |
| C11 | Vector size (1024-d): f32 / int8 / binary | 4096 / 1024 / 128 B | [D] | – |
| C12 | OpenSearch indexed size per chunk (text+fields+postings) | ≈ 2 KB (incl. 1.3 KB text) | [A] | B8 |
| C13 | Chunk row in PG | ≈ 350 B + indexes ≈ 700 B | [A] | DB benchmark |
| C14 | Artifacts size relative to originals | 1.5× (page JSON, tables, figures, OCR, chunk Parquet, embedding archive) | [A] | sample |
| C15 | Object-store erasure overhead | ×1.4 (e.g., 10+4) | [D] | – |
| C16 | BM25 bulk-indexing rate | 20k chunks/s per cluster at 10 data nodes | [A] | B8 |
| C17 | Query embedding latency | 40 ms (P95) | [A] | B1 |

---

## 4. Demand calculations

### 4.1 Ingestion (backfill) — CPU, GPU, I/O
Pages/s (Medium) = 500 M ÷ (180 d × 86,400) = **32 pages/s** [D]; (Large) = 5 B ÷ 15.55 M s = **322 pages/s** [D]; (Initial burst) = 5 M ÷ 86,400 = **58 pages/s** [D].

| Resource | Formula | Initial (24 h) | Medium | Large |
|---|---|---|---|---|
| Extraction cores (70% digital) | pages/s × 0.7 × C1 | 16 | 9 avg / ~40 peak-provisioned (4×) | 90 avg / ~400 peak (4×) |
| + sandbox overhead (~20%) [A] | × 1.2 | 19 | 11 / 48 | 108 / 480 |
| OCR GPUs (30% scanned) | pages/s × 0.3 × C2 | 8.7 (use 10–12) | 4.8 avg → 8–10 | 48 avg → 60–70 |
| Embedding GPUs | chunks/day × 450 tokens ÷ (C3 × 86,400) | 5.6M×450÷(2e4×86400)=1.5 | 556M/180d=3.09M chunks/d ×450 = 1.39e9 tok/d ÷ 1.73e9 = 0.8 avg → 4–8 for low lag | 30.9M chunks/d ×450 = 1.39e10 ÷ 1.73e9 = 8 avg → 16–24 |
| Embedding total GPU-hours | tokens ÷ C3 ÷ 3600 | 35 h | 3,900 h* | 39,000 h* |
(*uses 512 tokens/chunk in `01` §3.2; the 450-token net figure gives ≈ 12% less.)
| Object-store reads (originals, once) | docs/day × 20 MB | – | 5.6k docs/d → 112 GB/d | 55k docs/d → 1.1 TB/d ≈ 13 MB/s avg |
| Artifact writes | × 1.5 | – | 170 GB/d | 1.65 TB/d ≈ 19 MB/s |
Steady state after backfill (Large): 10,000 docs/day × 500 pages = 5 M pages/day ÷ 86,400 = 58 pages/s → OCR ≈ 9 GPUs, extraction ≈ 20 cores, embedding ≈ 1.5 GPUs ⇒ the backfill GPU pools can be released/repurposed (a **temporary capacity** decision: lease/burst GPUs for backfill rather than buy for peak).

### 4.2 Online path — search
Per search request: BM25 + vector (×1–3 variants), fusion, rerank (adaptive), post-check.
| Resource | Formula | Medium (100 q/s) | Large (400 q/s) |
|---|---|---|---|
| Query embeddings | U3 × variants(1.3) | 130/s (batch-able; 1–2 small replicas) | 520/s (≈ 4–6 replicas CPU/small-GPU slices) |
| BM25 requests to OpenSearch | U3 × 1.3 | 130 req/s | 520 req/s (spread across shard groups; each request touches all shards of target indices) |
| Vector requests (fan-out) | U3 × 1.3 × shards | 130 × 5 = 650 shard-queries/s | 520 × ~15 (hot-tier shards) ≈ 7,800 shard-queries/s → per shard ≈ 520/s (needs replicas, measured QPS/shard in B5) |
| Reranker tokens | U3 × C5 | 100 × 8.6k = 860k tok/s → 9–14 GPUs (no mitigations) | 400 × 8.6k = 3.44M tok/s → **35–57 GPUs** (no mitigations) |
| After mitigations [A: adaptive skip 40%, cache hit 25%, candidates 30→20 for identifier queries] | × (1−0.4)×(1−0.25) = 0.45 | **≈ 4–6 GPUs** | **≈ 16–26 GPUs** |
| PG post-check | U3 × 1 batched lookup | 100 q/s × ~5 ms | 400 q/s × ~5 ms |
| Network (search-service ↔ OpenSearch) | BM25 k=200 × ~300 B (IDs+fields, no text) = 60 KB/request; text fetched only for fused top-50 via multi-get ≈ 50 × 1.5 KB = 75 KB | 130×135 KB ≈ 18 MB/s | 520×135 KB ≈ **70 MB/s ≈ 0.56 Gbps** |
Design consequence: returning full text for 200 hits per variant would make the same flow ≈ 3× heavier (≈ 1.6 Gbps at Large) — the retrieval LLD must fetch **IDs first, text only for the rerank window** (recorded as a requirement on search-service).

### 4.3 Online path — AI queries and LLM token consumption
| Quantity | Formula | Initial | Medium | Large |
|---|---|---|---|---|
| Prefill tokens/s at peak | U4 × 6,300 | 6.3k | 126k | 504k |
| Decode tokens/s at peak | U4 × 300 | 0.3k | 6k | 24k |
| LLM GPUs — prefill-bound | ÷ (C6 × 0.65 util) | 6.3k ÷ 5.8k = 1.1 → **2 (HA)** | 126k ÷ 5.8k = 22 → **≈ 20–25** | 504k ÷ 5.8k = 87 → **≈ 80–90** |
| Same, after mitigations [A: prefix caching saves 25% of prefill (shared system+schema), compression cuts evidence 6,000→4,000 tokens] | prefill/query ≈ 4,300×0.75 ≈ 3,200 | – | 64k → **≈ 11–13 GPUs** | 256k → **≈ 44–50 GPUs** |
| LLM GPUs — decode-bound | ÷ (C7 × 0.65) | ≈ 0.3 | 6k ÷ 0.98k = 6 | 24k ÷ 0.98k = 25 |
| Tokens/day (budget) | U4 × 3,600 × U7 × (in+out) | 1×3600×2×6.6k ≈ 48 M | 20×7,200 = 144k queries × 6.6k ≈ **0.95 B tokens/day** | 80×7,200 = 576k queries × 6.6k ≈ **3.8 B tokens/day** |
| NLI | U4 × 1.2k tokens | – | 24k tok/s → 1 small GPU slice | 96k tok/s → 2–3 GPU slices |
Note: the values in `13` §5.2 (12–15 and 50–60 GPUs) used 100% utilization of quoted per-GPU throughput **(A)**; this document applies a 65% utilization ceiling, which raises the unmitigated numbers (22 and 87) and then shows the effect of mitigations (≈ 12 and ≈ 47). The two documents are consistent in conclusion (prefill dominates; mitigations are mandatory); **this document supersedes the figures**, and the `13` §5.2 LLM row now points here. Larger (70B-class) models multiply these several-fold; the bake-off (B4) decides the model/size.

### 4.4 Storage
| Store | Formula | Initial | Medium | Large |
|---|---|---|---|---|
| Original documents | W1 × W8 × W9 | 0.5 TB | 50 TB | **500 TB** |
| Artifacts | × C14 (1.5) | 0.75 TB | 75 TB | 750 TB |
| Object logical total | | 1.25 TB | 125 TB | **1.25 PB** |
| Object raw (EC ×1.4), primary site | | 1.75 TB | 175 TB | 1.75 PB |
| + DR replica (full) | ×2 | 3.5 TB | 350 TB | **3.5 PB raw** |
| + WORM backups (audit anchors, PG base/WAL, snapshots, ~10% of logical, retained 35 d + monthly) | | small | ≈ 15–25 TB | ≈ 150–250 TB |
| Chunk text/embedding archive (included in artifacts): text Parquet ≈ 1.3 KB×W6 ÷ 3 (compression); embedding archive int8 1 KB × W6 | | ≈ 8 GB | ≈ 0.8 TB (text) + 0.56 TB (vectors) | ≈ 2.4 TB + 5.6 TB |
| OpenSearch | W6 × C12 | 11 GB | 1.1 TB (×2 with replica = 2.2 TB) | 11 TB (×2 = 22 TB) |
| Vector DB resident (int8 + graph) | W6 × (1,024 + 150) | 6.5 GB | **652 GB** | **6.5 TB** (tiered: hot ≈ 20% ≈ 1.3 TB RAM; rest on-disk/binary) |
| Vector DB on-disk (f32 rescoring copy + int8 + graph + WAL ×1.5) | W6 × (4,096+1,024+150) × 1.5 | 44 GB | 4.4 TB | 44 TB |
| PostgreSQL | chunk metadata W6 × 700 B (Initial/Medium only) + other schemas | ≈ 10 GB | ≈ 0.4 TB + 0.3 TB (jobs/events/audit window) | ≈ 1–2 TB (chunks offloaded) + audit/event archive in lakehouse |
| ClickHouse/Iceberg (events, chunk table at Large, curated) | | – | ≈ 5–10 TB | ≈ 80–150 TB (incl. chunk table Parquet ≈ 7 TB raw-compressed ≈ 2.4 TB, event history, audit archive) |
| Kafka (7 d, RF 3) | `08` §3.1 | ≈ 5 GB | ≈ 50 GB | ≈ 107 GB ingestion + audit/AI topics (up to ≈ 1 TB at sustained peak audit/AI) |
| Observability (30 d) | `17` | ≈ 0.2 TB | ≈ 2 TB | ≈ 20–40 TB |
Growth: steady-state after backfill adds W12 × W8 × (1+C14) ≈ Large 10,000 docs/day × 50 MB ≈ 500 GB/day ≈ 180 TB/year logical (×1.4 EC ×2 sites ≈ 500 TB raw/year) — object storage is a **continuous capex item**; capacity forecast dashboards must alert at 70% utilization with ≥ 6 months lead time (procurement).

### 4.5 Memory and CPU for services
| Service group | Basis | Medium | Large |
|---|---|---|---|
| Java services | requests/s per pod ≈ 150–300 RPS/pod at ~100 ms CPU-light work; search/ai/orchestrator heavier (I/O fan-out) | ≈ 50 pods × 2 vCPU/2–4 GB | ≈ 120 pods × 2–4 vCPU/2–6 GB (≈ 400 vCPU) |
| Redis | permission scope cache 50k users × 2 KB = 100 MB; result cache 5 min × 100 q/s × 40 KB ≈ 1.2 GB | 8 GB HA pair | 32–64 GB cluster |
| OpenSearch heap | ≤ 31 GB per data node (compressed oops), shards ≤ 20 per GB heap | – | 22–44 nodes |
| Embedding/rerank/LLM model memory | weights + KV cache: LLM 8–14B FP16 ≈ 16–28 GB weights + KV cache for batch (prefill-heavy, 6.3k context × batch 16 ≈ 12–20 GB with GQA) → fits 48–80 GB GPUs; 70B needs multi-GPU | – | – |

### 4.6 Database connections
| Item | Calculation | Result |
|---|---|---|
| Client pools (Java) | pods × pool size (default 10) | Medium 50 × 10 = 500; Large 120 × 10 = 1,200 client-side |
| Server connections needed | peak concurrent *active* queries ≈ QPS × latency | PG peak QPS (all schemas) Large ≈ 400 (post-check) + 1,500 (reads) + 600 (writes) + jobs ≈ 3,000 QPS × 5 ms avg = **15 active** → with 4× burst and slow-query margin ≈ **60–100** |
| PgBouncer (transaction pooling) | `default_pool_size` per DB/user ≈ 20–40, `max_client_conn` 5,000 | Server `max_connections` 300 (≈ 100 pooled + replication + admin + Debezium + batch) |
| Python workers | do not hold DB connections; job leasing via a small number of pooled connections per pod group or orchestrator RPC | ≤ 5 per worker deployment |
| Replicas | read-only queries (status/read APIs) to replicas; staleness ≤ 1–2 s accepted for GET status, not for authorization post-check (primary or sync replica) | – |
Risk: per-pod pools × many replicas can exceed server limits during autoscale; mitigations: PgBouncer, smaller pools (5), connection-budget check in CI (pods × pool ≤ budget), alert at 70% of `max_connections`.

### 4.7 Kafka (reference `08` §3.1, §9.4)
Throughput ≈ 40 msg/s avg, ≈ 400 peak (Large ingestion) + audit/AI events ≈ 1,200 msg/s at 400 q/s ⇒ **well below a 5-broker cluster's capacity**; partitions are sized by consumer parallelism (OCR ≈ 100 concurrent tasks [A]); broker count driven by partition-replica budget (≈ 14,000 replicas ÷ 5–9 brokers) and disk/retention, not bandwidth.

### 4.8 Network bandwidth
| Flow | Large | Notes |
|---|---|---|
| Upload ingress (client → object store) | ≈ 13 MB/s avg, ≈ 130 MB/s peak [D] | presigned direct upload |
| Workers ↔ object store | reads ≈ 13 MB/s + artifact writes ≈ 19 MB/s avg; peaks 4× ≈ 130 MB/s | dominated by originals; OCR images adds (page rasters transient in worker memory) |
| Cross-site replication (object) | ≈ 32 MB/s avg, ≈ 130–250 MB/s peak [D] | must sustain backfill peaks or the governor throttles (`14` §4.3) |
| PG WAL to DR | ≈ 5–20 MB/s [A] | – |
| Snapshot shipping (OpenSearch, vector) | daily deltas ≈ 1–3% of 17.5 TB ≈ 0.2–0.5 TB/day ≈ 2.5–6 MB/s avg; full restore bursts ≈ 2–5 GB/s | restore speed limits RTO (`14` §8.3) |
| Query path search-service ↔ OpenSearch | ≈ 0.56 Gbps (§4.2) | design requires ID-first retrieval |
| Vector DB fan-out responses | 7,800 shard-queries/s × 200 results × 16 B (ID+score) ≈ 25 MB/s | small |
| Intra-cluster east-west with mTLS | include 10–20% TLS CPU overhead [A] | mesh decision (`13` §2) |
| GPU node fabric | LLM tensor parallelism needs NVLink/100 GbE; embedding/rerank nodes ≥ 25 GbE | – |
Conclusion: bandwidth is **not** a primary constraint if the design rules (direct upload, ID-first retrieval, small Kafka payloads) hold; it becomes a constraint if they are violated, hence they are testable requirements.

---

## 5. Scenario summary (supersedes `13` §5.2 where numbers differ)

| Component | Initial | Medium | Large (backfill peak → steady) |
|---|---|---|---|
| Extraction cores | ~20 (burst) | ~50 | ~480 → ~25 |
| OCR GPUs | 10–12 (burst, or 2 over 5 days) | 8–10 | 60–70 → 9–12 |
| Embedding GPUs | 1–2 | 4–8 | 16–24 → 2–3 |
| Reranker GPUs (mitigated) | 1 | 4–6 | 16–26 |
| LLM GPUs (8–14B, mitigated) | 2 (HA) | 11–13 | 44–50 (unmitigated 87) |
| NLI GPU slices | 0.2 | 1 | 2–3 |
| Vector DB nodes (256 GB class) | 1 (64 GB) | 10 (5 shards × 2) | ≈ 18 hot + 6–12 archive (tier) |
| OpenSearch data nodes | 3 | 3–6 (ratio-driven) | 22–44 |
| PG | 1+1 | 1+2 | 1+2 (+ separate audit/jobs clusters) |
| Kafka brokers | 3 | 5 | 5–9 |
| Object storage (raw, primary / with DR) | 1.75 / 3.5 TB | 175 / 350 TB | 1.75 / 3.5 PB |
| Java pods / vCPU | ~12 / 24 | ~50 / 100–150 | ~120 / 400 |
| GPUs total (peak) | ~16 | ~28–40 | ~140–180 (backfill) → ~75–95 (steady) |
Reading: Initial is modest; Medium is a typical production cluster; Large's steady-state GPU need is dominated by online AI (reranker + LLM), with ~65–85 additional GPUs only during the 6-month backfill window — a candidate for leased/burst capacity.

---

## 6. Latency budgets and throughput targets (consolidated)

| Path | Budget (P95) | Decomposition | Source |
|---|---|---|---|
| Hybrid search | ≤ 800 ms (≤ 1.5 s Large) | scope 15 + embed 40 + (BM25 ∥ vector) ≤ 250 + fuse/dedupe 20 + rerank ≤ 250 + post-check/parents 60 ≈ 635 | NFR-PRF-01 |
| RAG TTFT / total | ≤ 3 s / ≤ 15 s | retrieval 0.65 + select/compress 0.08 + LLM TTFT ≤ 1.5 + validation tail | NFR-PRF-04 |
| Upload initiate | ≤ 300 ms | auth + DB + presign | NFR-PRF-07 |
| Doc read/status | ≤ 150 ms | – | `15` §10 |
| Upload → INDEXED (100-page digital PDF) | ≤ 5 min; scanned ≤ 30 min | 4 range tasks parallel; queue wait < 60 s; embed/index batches | NFR-PRF-06 |
| Ingestion throughput | ≥ 55k docs/day at Large | §4.1 | NFR-PRF-05 |
| Analytics (ClickHouse) | ≤ 5 s | – | NFR-PRF-09 |
Utilization ceilings at planning peak: CPU pools ≤ 65%, GPU interactive pools ≤ 60% average / ≤ 80% at peak, vector/OpenSearch nodes ≤ 60% CPU and page cache hit ≥ 90%, PG ≤ 50% CPU and ≤ 70% connections, Kafka disk ≤ 70%.

---

## 7. Sensitivity analysis (what moves the bill)

### 7.1 One-at-a-time (Large, relative to base)
| Parameter | Low | Base | High | OCR GPUs (backfill) | Embedding GPU-h | Vector resident | Object storage | Notes |
|---|---|---|---|---|---|---|---|---|
| Scanned share | 10% | 30% | 60% | 20 / 65 / **130** | – | – | – | Linear; largest ingestion uncertainty |
| Pages/doc (mean) | 250 | 500 | 1,000 | ×0.5 / 1 / ×2 | ×0.5 / 1 / ×2 | ×0.5/1/×2 | storage tracks bytes, not pages | Everything scales with pages |
| Avg file size | 10 MB | 20 MB | 40 MB | – | – | – | 0.63 / 1.25 / 2.5 PB logical | – |
| Tokens/chunk | 256 | 450 | 768 | – | tokens const; chunks ×1.76 / 1 / ×0.59 | ×1.76 / 1 / ×0.59 | OpenSearch ×1.76/1/0.59 | Chunk size trades recall granularity for index size |
| Embedding dimension | 384 | 1024 | 1024 | – | throughput changes | 0.38× | – | Quantization further ×0.25–0.125 |
| Quantization | binary | int8 | f32 | – | – | 0.125× / 1× / 4× | – | Recall impact must be measured (B5) |
| Hot-tier fraction | 10% | 20% | 40% | – | – | 0.5× / 1× / 2× of hot RAM | – | Policy decision (tiering) |
| AI query rate | 40 q/s | 80 | 160 | – | – | – | LLM GPUs ×0.5 / 1 / ×2 | Dominant online cost |
| Evidence budget | 3,000 | 6,000 | 9,000 | – | – | – | prefill ×0.55 / 1 / ×1.45 | Compression/selection quality lever |
| Rerank candidates | 20 | 30 | 50 | – | – | – | rerank GPUs ×0.67 / 1 / ×1.67 | Knee from M7 curve |
| Adaptive skip/cache efficacy | 20% | 55% combined | 80% | – | – | – | rerank GPUs ×1.25 / 1 / ×0.5 | Hypothesis until B3 |

### 7.2 Scenario stress cases
| Case | Change | Impact | Response |
|---|---|---|---|
| S-A "scan-heavy corpus" | 60% scanned | OCR GPUs ≈ 130 for 6-month backfill (or backfill stretches to 12 months with 65 GPUs) | Extend backfill window; prioritize by value (current versions first); leased GPUs |
| S-B "double the pages" | 1,000 pages/doc | everything ×2 (vectors 13 TB resident) | Stronger tiering/coarser chunking for archive tier |
| S-C "success disaster" | 3× planned AI usage | LLM GPUs ×3 | Quotas, queueing, smaller model route, semantic caching in permission scope |
| S-D "model migration during peak" | Re-embed 5.5 B chunks (39k GPU-h) | needs ≈ 2× vector storage and GPU burst for weeks | Tiered migration (§`09` §3.6), vector reuse across versions, scheduling in low-usage windows |
| S-E "DR site active" | failover at Large | DR has 30–50% GPU → AI concurrency 25–40% | Degraded-mode policy (`14` §11) |

---

## 8. Capacity validation plan

| ID | Benchmark | Method | Output replaced in model | Milestone |
|---|---|---|---|---|
| B1 | Embedding tokens/s/GPU (per candidate, FP16/INT8, batch sizes) | Representative chunk lengths, GPU type(s) | C3, C17 | M5 |
| B2 | OCR s/page/GPU + CPU baseline on our scans | 1,000-page sample, per engine | C2 | M4 |
| B3 | Reranker tokens/s/GPU; quality vs candidates; adaptive-skip efficacy | golden set + load replay | C4, C5, skip rate | M7 |
| B4 | LLM prefill/decode tokens/s at target context/batch; prefix-cache hit rate | vLLM-class load test with real prompts | C6, C7, C8 | M8 |
| B5 | ANN recall/latency/memory at 10M/100M/1B with ACL filters; per-shard QPS | production-like payload filters | C10, vector node counts, ADR-006 | M6 (10M, 100M), M13 (1B/amplified) |
| B6 | NLI throughput/accuracy | claim set | C9 | M8 |
| B7 | Extraction CPU s/page by document type, sandbox overhead | sample corpus under gVisor | C1 | M4 |
| B8 | OpenSearch size/chunk and indexing/search throughput | 100M-chunk dataset | C12, C16, node counts | M6 |
| B9 | PG hot-path load (job pulls, status reads, post-check) | pgbench-style custom | connections, PG sizing | M3/M13 |
| B10 | Object-store small/large object throughput; replication lag under backfill | synthetic uploads at 2× peak | storage platform choice, RPO | M2/M13 |
| B11 | Kafka at 10× peak with consumer lag/rebalance behavior | `15` §4.5 | partition/broker plan | M3 |
| B12 | End-to-end ingestion at scaled rate | `15` §4.9 | NFR-PRF-05 verification | M13 |
Acceptance of the model: after benchmarks, recompute §4–5; each component prediction must match a subsequent mixed-load test within ±25%; otherwise update parameters and repeat. Results are archived in the registry/Git with environment descriptions (hardware, driver, library versions).

## 9. Capacity management in operation
| Practice | Detail |
|---|---|
| Forecasting | Track growth of docs, pages, chunks, storage, query rates monthly; forecast time-to-70% for storage/RAM/GPU; alert ≥ 6 months before limit for hardware with long lead time |
| Headroom policy | Maintain ≥ 30% spare at peak for online pools; ≥ 25% storage free |
| Autoscaling limits | Max replicas bounded by GPU quota; cost alarms |
| Load shedding | Defined thresholds (`11` §6) and tested |
| Review cadence | Quarterly capacity review; mandatory before each tier step (Initial→Medium→Large) |
| Tier-step gates | Entry criteria to move to next tier: benchmarks updated, DR retested at new size, restore times measured, cost approved |

## 10. Cost model (structure; unit prices intentionally absent)
`Monthly cost = Σ(GPU-hours × rate) + Σ(node-hours × rate) + storage(TB-months × rate by class) + network egress/replication + licenses (if any) + staffing (SRE/ML-Ops FTE × cost)`. Costs per page ingested and per query are reported monthly (NFR-CST-01). Prices depend on U-01 (own hardware amortization vs cloud); we do not invent unit prices. Dominant lines at Large: GPUs (online reranker + LLM + backfill OCR/embedding), vector RAM, NVMe for OpenSearch/Kafka, ≈ 3.5 PB raw object storage (with DR), staffing.

## 11. Assumption register and risks
| Risk | Effect | Mitigation |
|---|---|---|
| Scanned share unknown | ±100% OCR GPUs | Sample corpus early (R1) |
| Query volume unknown | LLM/reranker sizing ±3× | Pilot telemetry; quotas; elastic burst |
| Throughput numbers are vendor/folklore | ±50% GPU counts | Benchmarks B1–B6 mandatory before procurement |
| Mitigation efficacy (skip/cache/compress) is hypothetical | Large GPU count 2× | Treat unmitigated numbers as upper bounds; stage investment |
| Object storage growth | Capex surprises | Forecast dashboards; archive tiering; dedup across versions |
| Vector DB at billions unproven for chosen engine | Replatform | B5 gate before Large; port abstraction (`VectorStore`) |

## 12. Acceptance criteria for this document
| ID | Criterion |
|---|---|
| CAP-1 | Every infrastructure count traces to a formula and labeled parameter |
| CAP-2 | Benchmarks B1–B12 executed and model updated before each tier commitment |
| CAP-3 | Predicted vs measured within ±25% in a mixed-load validation |
| CAP-4 | Capacity dashboards and 6-month forecast alerts live by M12 |
| CAP-5 | Sensitivity cases reviewed with stakeholders at G-gates (scanned share, query rate, model size) |

## 13. Next
Monitoring and Observability (doc 17).
