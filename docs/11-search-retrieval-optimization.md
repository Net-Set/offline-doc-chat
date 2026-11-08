# Stage 2 — Document 8: Search and Retrieval Optimization

| Field | Value |
|---|---|
| Document ID | DIP-SRCH-01 |
| Version | 0.1 |
| Builds on | `04` §5, §6; `05` §5; `06` §9; `09` §3, §9.5 |
| Note | Independent reference architecture. ANN parameters, memory formulas and latencies are starting points; the vector-database decision (ADR-006) remains **PROVISIONAL** until benchmark B5. |

---

## 1. Search strategies compared

| # | Strategy | How it works | Strengths | Weaknesses | Role here |
|---|---|---|---|---|---|
| 1 | Exact keyword (term/phrase) | Boolean match on tokens/phrases | Deterministic, precise for identifiers, part numbers, quoted text | No synonyms; brittle to typos | Quoted phrases, IDs; always available |
| 2 | Inverted index | term → posting lists; foundation of 1, 3 | Sub-linear lookup, mature | Memory/disk for postings; shard management | OpenSearch storage structure |
| 3 | BM25 | Probabilistic TF-IDF with length normalization (k1≈1.2, b≈0.75) | Strong baseline; excellent on rare tokens (codes, units), explainable | Vocabulary mismatch | **Core retriever** |
| 4 | Semantic vector (dense ANN) | Bi-encoder embeddings, nearest neighbors | Synonyms, paraphrase, cross-language | Weak on exact identifiers/numbers, near-duplicate revisions; embedding drift; index cost | **Core retriever** |
| 5 | Metadata filtering | Predicates on structured fields | Cheap, exact, security-critical | Needs good metadata | **Mandatory pre-filter** |
| 6 | Hybrid | BM25 + vector fused (RRF/weighted) | Robust across query types; typically beats either alone | Two systems to run | **Default mode** |
| 7 | Multi-query | Several rewrites retrieved, fused | Higher recall for ambiguous queries | Cost ×N | Conditional (low-confidence queries) |
| 8 | Hierarchical | Section/document-level retrieval → drill down | Scales to huge scopes, cheaper ANN over fewer vectors | Needs summaries/section index | Large-scope queries, summaries |
| 9 | Parent-child | Search small chunks, return larger parents | Precise match + sufficient context | Extra fetch; index of relations | Default context assembly |
| 10 | Cross-document | Retrieval over a set, diversity/quotas, per-document grouping | Needed for comparison/synthesis | Dominant documents crowd out others | Diversity constraints in selection |
Also considered and not default: learned sparse (SPLADE-class — evaluate in M7), late-interaction (ColBERT-class — heavy storage, evaluate for the rerank tier), graph retrieval (see RAG doc, optional).

### 1.1 Why vector similarity alone cannot guarantee the best result
| Limitation | Technical example | Remedy in this design |
|---|---|---|
| Embeddings blur exact tokens | "28 V ±2 V" vs "28 V ±1 V" or "PS-100" vs "PS-101" have near-identical vectors | BM25 with phrase/identifier handling; numeric/identifier boosts; reranker; validator checks numbers |
| Bi-encoder encodes query and chunk independently | Cannot model fine query-chunk interactions (negation, qualifiers, "not exceed" vs "shall exceed") | Cross-encoder reranking sees both together |
| Similar ≠ relevant/authoritative | A superseded revision is *more* similar than the current one when text barely changed | Version filters/ordering, metadata, dedupe/collapse rules |
| ANN is approximate | HNSW may miss true neighbors, worse under restrictive filters | Recall monitoring vs exact, adaptive `ef`, exact fallback for tiny filtered sets |
| Domain shift | General embeddings poor on units/jargon/equations | Bake-off on our data, contextual prefix, hybrid, optional fine-tune |
| Chunk boundary artifacts | Answer spans two chunks | Parent-child, overlap, neighbor expansion |
| Score non-comparability | Cosine scores not calibrated across queries/models | Rank-based fusion (RRF); learned thresholds only on reranker scores per model version |
| Permission constraints | Top-K then filter would return too few | Filter *inside* the index query |

---

## 2. Index design

### 2.1 OpenSearch (BM25) schema (chunk index)
```json
{
  "settings": { "number_of_shards": 24, "number_of_replicas": 1,
    "analysis": { "analyzer": {
      "tech_text": { "tokenizer": "standard", "filter": ["lowercase", "asciifolding", "unit_split", "synonym_graph_acronyms", "english_stop_light"] },
      "id_exact":  { "tokenizer": "keyword",  "filter": ["lowercase"] } } } },
  "mappings": { "dynamic": "strict", "properties": {
    "chunk_id": { "type": "keyword" }, "document_id": { "type": "keyword" }, "version_id": { "type": "keyword" },
    "text": { "type": "text", "analyzer": "tech_text", "similarity": "BM25" },
    "text_exact": { "type": "text", "analyzer": "id_exact" },
    "title": { "type": "text", "analyzer": "tech_text", "boost": 2.0 },
    "section_path": { "type": "text", "analyzer": "tech_text" },
    "identifiers": { "type": "keyword" },
    "acl_tags": { "type": "keyword" }, "class_level": { "type": "short" },
    "doc_type": { "type": "keyword" }, "department_id": { "type": "keyword" },
    "effective_date": { "type": "date" }, "version_no": { "type": "integer" },
    "searchable": { "type": "boolean" }, "version_state": { "type": "keyword" },
    "page_start": { "type": "integer" }, "page_end": { "type": "integer" },
    "chunk_type": { "type": "keyword" }, "quality_score": { "type": "float" },
    "language": { "type": "keyword" }, "text_hash": { "type": "keyword" }, "pipeline_version": { "type": "keyword" } } } }
```
Notes: `dynamic: strict` (no accidental fields); `identifiers` extracted (part numbers, document numbers) for exact matching with high boost; analyzer handles unit splitting ("28V"→"28","v"), acronym synonyms from a governed glossary; `_id = chunk_id` (idempotent writes); `refresh_interval` 30 s during ingestion (5 s interactive tier optional), bulk indexing with `refresh=false`; ILM/rollover by index group (§2.2); replicas ≥ 1.

### 2.2 Index sharding and layout
| Tier | Layout | Rationale |
|---|---|---|
| Initial | 1 index, 3–6 shards | Simplicity |
| Medium | Indices per *era/tier* (hot-current, archive) via alias; shards sized 30–50 GB | Smaller hot tier searched first; cheap archive |
| Large | + per-classification-tier index sets (top tier physically separate cluster, ADR-004); shard count capped to keep cluster state manageable (≲ 10k shards/cluster) | Isolation + operations |
Search spans index groups via aliases with the version/lifecycle filter; superseded versions live in archive indices unless `include_history`.

### 2.3 Vector index (logical design independent of product)
- **Collection per (embedding model version, dimension, quantization)**; alias `chunks_active`.
- Payload kept minimal: `chunk_id`, `document_id`, `version_id`, `acl_tags`, `class_level`, `searchable`, `version_state`, `doc_type`, `department_id`, `effective_date`, `chunk_type`, `quality_score` — **payload-indexed** for filterable ANN. No chunk text.
- Point ID = `chunk_id` (idempotent upsert).

---

## 3. Vector database evaluation

### 3.1 Comparison (qualitative; B5 decides)
| Criterion | Qdrant | Milvus | Weaviate | pgvector (PostgreSQL) |
|---|---|---|---|---|
| Architecture | Single binary; distributed mode with shards/replicas (Raft for cluster metadata) | Cloud-native disaggregated (proxy, query, data, index nodes; etcd/object storage/message queue dependencies) | Single binary + modules; sharding/replication built in | Extension inside PG; scale by PG scaling |
| ANN algorithms | HNSW (filterable), quantization (scalar/product/binary), on-disk vectors (mmap) | HNSW, IVF-family, DiskANN, GPU indexes; many index types | HNSW, flat; PQ/BQ compression | HNSW, IVFFlat (+ halfvec/binary quantization support in recent versions) |
| Filtered search | Strong: payload indexes with filter-aware HNSW traversal | Supported (scalar filtering, partitions/partition keys) | Pre-filtering support | Planner-based; filtered ANN can lose recall without iterative scan features |
| Billion-scale story | Possible with sharding + quantization + disk; operational maturity at multi-billion needs proof | **Designed for** very large deployments, mature disaggregated scaling | Less commonly chosen at this scale | Not intended beyond ~tens of millions per node |
| Ops complexity | Low–medium | **High** (many components) | Medium | Lowest (reuse PG skills) but heavy vector load contends with OLTP |
| Hybrid features | Sparse+dense, fusion in query API | Sparse+dense, hybrid search APIs | Native hybrid (BM25F) | Combine with PG FTS (not distributed BM25-grade) |
| Self-host/air-gap | Yes | Yes | Yes | Yes |
| License | Apache-2.0 | Apache-2.0 | BSD-3 | PostgreSQL-style |
| Fit — Initial (5.5 M vectors) | **Good** (single node) | Overkill | Good | **Good, simplest** (separate PG instance, not the OLTP one) |
| Fit — Medium (550 M) | **Good** (3–6 nodes, quantized) | Good | Uncertain | Poor |
| Fit — Large (5.5 B) | Needs proof (B5) | **Strong candidate** | Unlikely | No |
Decision (ADR-006, provisional): **start on Qdrant** (or pgvector on a *dedicated* PostgreSQL for the 10k-doc pilot if minimal ops matter), hide it behind a `VectorStore` port (upsert, delete-by-filter, search(filter, k, params), snapshot, stats) so a migration (e.g., to Milvus at Large) is a re-index, not a rewrite. **Benchmark gate before Medium→Large:** B5 results at 10M/100M/1B vectors with production-like filters decide whether to stay or migrate. Weaviate is not shortlisted (no differentiating advantage for our constraints); it can be re-evaluated.

### 3.2 ANN algorithms
| Algorithm | Principle | Build/memory | Query | Tuning knobs | When |
|---|---|---|---|---|---|
| **HNSW** | Multi-layer proximity graph; greedy descent + beam search | Graph ≈ M×2×4 B per vector at layer 0 (≈ 128–256 B with M=16) + vectors; build is CPU-heavy and sequential-ish | High recall at low latency | `M` (16–32), `ef_construction` (100–400), `ef_search` (64–512) | Default for RAM-resident or mmap'd indexes |
| **IVF (IVF-Flat / IVF-PQ)** | k-means partitions; search `nprobe` nearest cells | Small overhead; PQ compresses to 16–128 B/vec; train step required | Good for huge sets with compression; recall depends on `nprobe` | `nlist` ≈ √N…4√N, `nprobe`, PQ `m/nbits` | Billions of vectors when RAM-limited; GPU-friendly |
| **DiskANN/Vamana** | Graph on SSD with in-RAM compressed codes, beam search with few disk reads | RAM: PQ codes (~32–64 B/vec); disk: graph + full vectors | Low-ms with NVMe; more QPS-limited by IOPS | `R`, `L`, search list size | Billion-scale on disk |
| Flat/brute force | Exact scan | none | O(N·d); SIMD/GPU | – | Tiny filtered sets (< ~50k), ground truth for recall tests |
| Quantization (SQ8, PQ, binary) | Compress vectors | 4×–32× smaller | Faster distance; recall loss mitigated by **rescoring** with full-precision from disk | oversampling factor (e.g., 3–10×) | Always at Medium/Large |

**Recall vs latency:** raising `ef_search`/`nprobe` raises recall and latency roughly log/linear; target operating point = lowest latency achieving **recall@100 ≥ 0.97 versus exact search on our filtered workload**. Quantization with oversampling+rescore commonly recovers most recall for ~1% extra latency, but this must be measured per embedding model (some models degrade more under binary quantization).

### 3.3 Memory and storage model (formulas)
```
RAM_graph(HNSW)      ≈ N × (M × 2 × 4 B + ~20 B overhead)           # M=16 → ~150 B
RAM_vectors(in-RAM)  ≈ N × d × bytes_per_dim                        # float32=4, fp16=2, int8=1, binary=1/8
RAM_filter_indexes   ≈ N × ~10–40 B per payload-indexed field       # keyword indexes cost more
Disk_total           ≈ N × d × 4 B (originals for rescoring) + quantized copy + graph + WAL/snapshots (×1.5–2)
Shards               ≥ ceil( (RAM_graph+RAM_vectors_resident) / (RAM_per_node × 0.6) ) × replicas
```
Worked, 1024-d, **Medium (N = 550 M)** **(A: design estimates)**:
- float32 in RAM: 550 M × 4 KB = 2.2 TB (too costly) → **int8 in RAM**: 550 GB + graph 85 GB ≈ 635 GB (+ filter indexes ≈ 20 GB) → with 60% RAM utilization on 256 GB nodes ≈ 5 shards × 2 replicas = 10 nodes; or binary-in-RAM (70 GB) + graph on disk + float32 on NVMe for rescoring (2.2 TB) → 3–4 nodes with large NVMe, higher p95 (disk reads for rescoring).
**Large (N = 5.5 B)**: int8 = 5.5 TB (+ graph ≈ 0.85 TB) ≈ 6.4 TB RAM-resident ⇒ ~40 shards of 256 GB × 2 replicas = 80 nodes (very costly) → realistic options: (a) **tiering** — hot tier (current versions, recently accessed, ~15–25% of chunks) int8 in RAM; archive tier binary-quantized + disk (DiskANN/IVF-PQ style) or even excluded from semantic search (BM25 only) until requested; (b) smaller dimension (256–512 via Matryoshka-capable model) reduces all numbers 2–4×; (c) coarser chunking for archive documents (fewer vectors). These are *cost levers decided by measurement of recall impact*, which is why B5 and the tiering policy are Milestone 6/13 work items.

### 3.4 Sharding, replication, filtering
| Aspect | Design |
|---|---|
| Shard key | Hash of `document_id` (keeps all chunks of a document together → parent/child and per-document diversity operate within shard; even distribution) |
| Alternative | Partition by tier/classification (separate collections) for physical isolation and different quantization per tier |
| Query fan-out | Query broadcast to all shards, each returns top-k' (k' = k × oversample/shards-aware), coordinator merges; latency = slowest shard → hedged requests/replica selection to cut tails |
| Replication | ≥ 2 replicas at Medium/Large (availability + read throughput); writes quorum-acked; indexing is async to queries (read-your-writes not required, `searchable` flag handles visibility) |
| Filtering | Payload indexes on ACL tags, version_state, doc_type, department, date. Selectivity-aware: **wide filters** → ANN with filter; **narrow (< ~0.1% of corpus)** → exact scan over filtered IDs (pre-resolved from payload index) to avoid graph disconnection; **medium** → increase `ef_search`/over-fetch. ACL tag expansion guard per HLD §5.2 (threshold ≈ 1,000 tags; group tags preferred) |
| Index optimization | Build with `ef_construction` high once, optimize/merge segments off-peak, avoid frequent small updates (batch upserts), pause indexing under heavy query load, snapshot before migrations; monitor segment count, memory, rescoring disk reads |
| Disk-based search | mmap'd vectors on NVMe (≥ 100k random IOPS per node), keep graph or PQ codes in RAM, rescoring reads limited by oversample factor; avoid network-attached slow disks |

### 3.5 When distributed vs single-node
| Condition | Single node suffices | Move to distributed |
|---|---|---|
| Vectors (after quantization) fit ≲ 60% RAM of one large node (e.g., ≤ ~100–200 M int8 vectors at 1024-d on 256 GB) | Yes | – |
| Query throughput | ≤ ~200–500 QPS with p95 target met | Need more read capacity → replicas (still can be "distributed" by replication only) |
| Availability | Pilot tolerant of brief outage (99.5%) | 99.9% target → replicas across failure domains |
| Index build/maintenance windows | Acceptable downtime/rebuild | Rolling maintenance requires replicas |
| Growth | Predictable small | Hundreds of millions+ → sharding |
Applied: Initial = single node (+ snapshot backups); Medium = sharded + replicated; Large = sharded/tiered, possibly different engine per tier.

---

## 4. Reranking engine

### 4.1 Bi-encoder retrieval vs cross-encoder reranking
| Aspect | Bi-encoder (retrieval) | Cross-encoder (rerank) |
|---|---|---|
| Computation | Encode query once, chunks offline; ANN lookup | Joint (query, chunk) forward pass for each candidate |
| Cost | Query: O(1) encodes; scales to billions | O(candidates) transformer passes per query |
| Quality | Good recall, coarse relevance | Higher precision, models fine interaction |
| Use | Candidate generation (top 200) | Re-score top 30–50 |

### 4.2 Reranking service design
- Input: query, candidates (≤ 50) with `text` windows (≤ 256 tokens around best-matching sentence span; fetch via OpenSearch `_source` included in the hit to avoid extra calls).
- Output: scores; service is stateless, GPU-batched across concurrent requests (micro-batching 5–10 ms window).
- **Candidate selection:** top 30 from the fused list by default (hard maximum 50, set by the M7 knee curve); for narrow/precision queries (identifier lookups) 20; **adaptive skip**: if RRF top-1 appears in both lexical top-3 and vector top-3 *and* margin is large → skip rerank (saves GPU; validated by eval that quality is unchanged).
- **Top-K optimization:** K_final default 10 (search UI) / 12 (RAG pre-selection); K sensitivity curve (nDCG@K vs rerank candidates 10/20/30/50/100) measured in M7 to choose the knee — beyond the knee latency/cost rises without quality gain.
- **Score use:** rerank scores are **not** probabilities; thresholds (τ_min) are set per reranker version from the dev set and re-fit on version change; output band signals only.
- Timeout 400 ms → fallback to fused order (`degraded`).
- **Query-document similarity features** (optional learning-to-rank, later): lexical overlap, identifier exact match, recency, version status, document type prior, source quality; a LightGBM/linear LTR over (rerank score, BM25 rank, vector rank, features) trained on click/label data can replace hand-tuned boosts. Not in v1; evaluate after labels exist (U-06).

### 4.3 Context selection after rerank
See RAG doc stage 8: token budget, diversity, parent expansion, version grouping.

---

## 5. Search optimization techniques

### 5.1 Query processing
| Technique | Detail | Safety/measurement |
|---|---|---|
| Normalization | unit/identifier/Unicode normalization (same as indexing analyzer) | Test set of tricky tokens |
| Query rewriting | rules first; LLM rewrite only for conversational follow-ups | shown to user, logged |
| Query expansion | acronym/synonym glossary (governed list, reviewed by domain owners), pseudo-relevance feedback (RM3) optional for BM25 | PRF only when initial scores confident; ablation |
| Intent detection | identifier-like query (matches doc/part-number pattern) → exact-first: lexical `identifiers` field boosted ×10, vector weight reduced | Fixed rule + evaluated |
| Spell tolerance | fuzzy `AUTO` edit distance on non-identifier terms, off for identifier fields | typo set |
| Multi-language | language-specific analyzers per chunk `language` field; cross-lingual via multilingual embeddings (U-05) | language subset |

### 5.2 Retrieval-time optimization
| Technique | Detail |
|---|---|
| Metadata pre-filtering | ACL/version mandatory; reduces candidate space; selectivity-based strategy switch |
| Parallel retrieval | BM25 ∥ vector with per-engine timeouts (600/500 ms); partial results fused if one times out (`degraded`) |
| Over-fetch factors | per-shard k' = k × 1.5–3 for vector fan-out to protect global recall |
| Result fusion — **RRF** | `score(d) = Σ_i w_i / (k + rank_i(d))`, k=60, weights default 1.0 (BM25 1.0, vector 1.0, boosted lists for identifiers); chosen over score normalization (min-max/z-score) because lexical/vector scores are incomparable and RRF is robust and parameter-light; weighted-score fusion is evaluated as an alternative with learned weights if labels permit |
| Duplicate removal | exact (`text_hash`), near-duplicate (MinHash Jaccard ≥ 0.9 on 5-gram shingles; computed at ingestion and stored as `dup_cluster_id`), cross-version collapse (same text across versions → show current, annotate "also in Rev B") |
| Adaptive retrieval | adjust `ef_search`, candidate counts, rerank on/off, multi-query on/off from query features (length, identifier presence, first-pass score distribution) and current load (load shedding: under pressure reduce candidates, skip multi-query, skip rerank) |
| Hierarchical retrieval | For scope > threshold (e.g., > 5,000 documents) first search section/document-summary index (≈ 20–50× fewer vectors) to select top documents/sections, then chunk search restricted to them |
| Result diversification | per-document cap, MMR (λ≈0.7) optional for exploratory queries |

### 5.3 Caching
| Cache | Key | TTL / invalidation | Notes |
|---|---|---|---|
| Query embedding cache | (normalized query text, model version) | 24 h | Safe across users (query text only; no document data) |
| Search result cache | (normalized query, filters, options, **permission fingerprint**, index epoch) | 5 min; invalidated on `iam.permission.changed` for affected fingerprints and on new INDEXED versions via epoch bump (coarse: per-tier epoch) | Never shared across different fingerprints |
| Semantic cache (query → prior result/answer) | embedding of query with similarity ≥ 0.97 **and** identical filters + fingerprint + same active model versions | 15 min; only for RETRIEVAL results and (optionally) RAG answers whose sources are unchanged | High risk of stale/incorrect reuse; answers re-validated against current ACL before serving; off by default for RAG answers |
| Chunk text cache | `chunk_id` → text | LRU in Redis (hot parents) | immutable by chunk_id |
| Permission scope cache | user → tags | ≤ 60 s | FR-IAM-08 |
Cache keys include the **model/prompt/config versions** so a promotion naturally invalidates results.

### 5.4 Search result evaluation (online + offline)
| Signal | Use |
|---|---|
| Offline: Recall@K, nDCG, MRR on golden set | gates (`09` §7) |
| Online implicit: CTR@position, dwell/ "used in answer", reformulation rate, zero-result rate, abandonment | monitoring, LTR labels (noisy; position-bias corrected by interleaving or propensity weighting) |
| Online explicit: useful / not useful, per-hit | label collection (`/search/feedback`) |
| Interleaving (team-draft) for A/B of rankers | detects ranking improvements faster than traffic splits |
| Per-slice dashboards | by doc type, department, language, query type (identifier vs natural) |

---

## 6. Complete retrieval algorithm (pseudocode with adaptive and degradation behavior)
(The base algorithm is in `05` §5.2; this version adds the optimizations of this document.)
```
function retrieve(req, user, load):
    scope = scopeResolver.resolve(user)                                     # tags, clearance, fingerprint
    cacheKey = hash(normalize(req.query), req.filters, req.options, scope.fingerprint, config.version, indexEpoch(scope))
    if hit = resultCache.get(cacheKey): return hit

    intent   = classifyQuery(req.query)                                    # IDENTIFIER | KEYWORD | NATURAL | CONVERSATIONAL
    filters  = AND(aclFilter(scope), versionFilter(req.includeHistory), req.filters)
    sel      = estimateSelectivity(filters)                                # via payload index cardinality estimates

    variants = [rewrite(req.query, intent)]
    if intent == NATURAL and config.multiQuery and load.low and shouldExpand(req.query): variants += expand(req.query, max = 2)

    # hierarchical narrowing for very wide scopes
    if sel.documents > HIER_THRESHOLD and intent != IDENTIFIER:
        sections = sectionIndex.search(variants[0], filters, k = 100)
        filters  = AND(filters, inSections(sections))

    weights = intent == IDENTIFIER ? {lex: 2.0, vec: 0.5} : {lex: 1.0, vec: 1.0}
    parallel for q in variants:                                           # per-call timeouts; partial results allowed
        lex[q] = bm25.search(q, filters, k = 200, fields = [text, title^2, section_path, identifiers^10])
        vec[q] = (sel.chunks < EXACT_THRESHOLD) ? vector.exactSearch(embed(q), filters.ids, k = 200)
                                                : vector.ann(embed(q), filters, k = 200, ef = adaptiveEf(sel, load), rescore = true)
    if both lex and vec failed: raise Unavailable
    degraded = any engine failed or timed out

    fused = RRF(all lex, all vec, weights, k = 60)
    fused = collapseDuplicates(fused)                                      # text_hash, dup_cluster, cross-version
    cand  = top(fused, rerankCandidates(intent, load))                      # 30 default (max 50), 20 for identifier, 0 under heavy load

    if cand.size > 0 and not skipRerank(cand):                              # adaptive skip when lexical & vector agree with large margin
        ranked = reranker.rerank(variants[0], cand, windowTokens = 256, timeout = 400ms) or cand   # fallback = fused order, degraded = true
    else: ranked = cand

    safe   = aclPostChecker.verify(ranked, user)                            # authoritative; counts drops (alert if > 1% sustained)
    safe   = diversify(safe, perDocCap = req.focusDocument ? INF : 3)
    result = parentExpander.expand(top(safe, req.topK), budget = req.contextBudget)
    result.meta = {degraded, intent, selectivity: sel, tookMs, perHitProvenance}
    resultCache.put(cacheKey, result, ttl = 5m)
    return result
```
Complexity: BM25 and ANN are sub-linear; fusion O(Σk); rerank O(C × L_tokens) dominating GPU cost; post-check one batched indexed PG lookup (≤ 50 IDs, ~5 ms).

---

## 7. Tuning parameters and starting values

| Parameter | Start | Range explored | Selection metric |
|---|---|---|---|
| BM25 `k1`, `b` | 1.2, 0.75 | k1 0.8–2.0, b 0.3–0.9 | nDCG@10 |
| Field boosts (title, section_path, identifiers) | 2, 1.5, 10 | grid | nDCG@10 per query type |
| Lexical k / vector k per query variant | 200 / 200 | 50–500 | Recall@50 after fusion vs latency |
| RRF `k` | 60 | 10–100 | nDCG@10, stable ±0.5 pt |
| RRF weights | 1.0/1.0 | learned if labels | nDCG@10 |
| HNSW `M`, `ef_construction` | 16, 200 | M 12–32; efc 100–400 | recall@100 vs exact, build time, RAM |
| `ef_search` | 128 (adaptive 64–512) | – | recall@100 ≥ 0.97 at p95 latency target |
| Quantization oversample | 5× | 2–10× | recall recovery vs rescoring IO |
| Exact-search selectivity threshold | 0.1% of chunks (≈ 5.5 k at Initial; absolute cap 50 k) | 0.01–1% | latency vs recall under ACL filters |
| Rerank candidates | 30 (max 50) | 10–100 | nDCG@10 knee, GPU cost |
| Per-document cap | 3 | 1–5 | cross-document recall metrics |
| Cache TTLs | 5 min results | – | hit rate vs staleness incidents |
Process: tune on the **dev split**, confirm on the frozen **test split**, check per-slice regression, record in config version; every change runs the gates in `09` §7.

## 8. Performance budgets and capacity checks (illustrative **(A)**)
| Component | Budget (P95, Medium) | Key capacity driver | Check |
|---|---|---|---|
| Permission scope | 15 ms | cache hit ≥ 95% | cache metrics |
| Query embedding | 40 ms | small model replicas | load test |
| BM25 | ≤ 150 ms | shard count, heap/page cache | OpenSearch profile API |
| Vector ANN (filtered) | ≤ 200 ms | RAM-resident quantized, `ef` | B5 |
| Fusion + dedupe | 20 ms | CPU | – |
| Rerank | ≤ 250 ms | GPU tokens/s | B3 |
| Post-check + parent fetch | ≤ 60 ms | PG indexes, Redis | – |
| **Total** | **≈ 650–800 ms** | | NFR-PRF-01 |
Throughput planning at 100 search QPS (U-08 default): BM25 100 QPS (trivial per shard group with replicas), vector 100–200 QPS (fan-out ×shards → per-shard QPS = 100 × queries per search ≈ 100–300), reranker ≈ 9–14 GPUs without adaptive skip **(A, B3)**. Adaptive skip, caching, and lower candidates are expected to reduce this substantially but that is a hypothesis until measured.

## 9. Operational concerns
| Topic | Design |
|---|---|
| Index consistency | `searchable` flip only after OpenSearch + vector confirmation; reconciliation compares counts and ID sets (`06` §7) |
| Zero-downtime re-index | Alias switch for both engines; dual-write window for changes during migration |
| Snapshots/DR | OpenSearch snapshots to object store (daily + after bulk loads); vector DB snapshots; DR RTO = max(restore snapshot, replay delta) vs rebuild-from-artifacts time — **a measured number** per tier recorded in the DR plan |
| Monitoring | per-engine latency/error, shard health, heap/RAM, segment counts, ANN recall audit (weekly vs exact on sampled queries), ACL post-check drop rate, cache hit rates, degraded rate, zero-result rate |
| Security | ACL filters compiled by search-service only (never client-supplied raw filters); engine access via service identities; OpenSearch security plugin roles; query logs without text where policy requires; field-level protection of `acl_tags` (not user-writable) |
| Failure behavior | OpenSearch down → vector-only (degraded); vector down → BM25-only; reranker down → fused; both retrievers down → 503 |

## 10. Acceptance criteria
| ID | Criterion | Target |
|---|---|---|
| S-AC1 | Recall@50 (pre-rerank, golden set) | ≥ 0.95 |
| S-AC2 | nDCG@10 final | ≥ 0.75 (and ≥ best single retriever + 5 pt, proving hybrid value) |
| S-AC3 | ANN recall@100 vs exact on filtered workload | ≥ 0.97 at the operating point |
| S-AC4 | P95 hybrid search latency | ≤ 800 ms (Initial/Medium), ≤ 1.5 s (Large) |
| S-AC5 | Permission tests | 0 unauthorized hits across 10k randomized probes |
| S-AC6 | Degraded-mode behavior | each single-component failure returns 200 with `degraded` (except both retrievers) in chaos tests |
| S-AC7 | Index parity | drift < 0.01% per day, auto-healed within 24 h |
| S-AC8 | Cache correctness | no cross-fingerprint cache hit in test suite (10k mixed-user queries) |

## 11. Open items
| Item | Plan |
|---|---|
| Vector DB final selection (ADR-006) | B5 at 10M/100M/1B; decision before Large |
| Learned sparse vs BM25 | Evaluate in M7 |
| ColBERT-class late interaction | Optional evaluation; storage heavy (token-level vectors) |
| Learning-to-rank | After labeled data exists |
| Archive-tier policy (BM25-only vs quantized semantic) | Decide with usage statistics at Medium |
| Glossary governance (acronyms/synonyms) | Domain owners; versioned artifact |

## 12. Next
Security Architecture, Infrastructure & Deployment, Disaster Recovery Plan, Test Strategy, Performance & Capacity Planning, Monitoring & Observability, ADRs, Implementation Roadmap, Production Readiness Checklist.
