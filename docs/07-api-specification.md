# Stage 2 — Document 4: API Specification (v1)

| Field | Value |
|---|---|
| Document ID | DIP-API-01 |
| Version | 0.1 |
| Builds on | `05-lld.md` §2.4, §5.3, §8.2 (DTOs, response schema), `06-database-design.md` (entities, states) |
| Machine-readable form | [openapi/dip-api-v1.yaml](openapi/dip-api-v1.yaml) (OpenAPI 3.1; this document is the narrative and the source of the rules) |
| Note | Independent reference architecture. Limits, quotas and latency figures are proposals to be ratified and load-tested. |

---

## 1. Global conventions (apply to every endpoint unless overridden)

### 1.1 Base URL, versioning, content types
- Base path `/api/v1`, served only over TLS via `api-gateway`. Breaking change → `/api/v2` (v1 supported ≥ 12 months after v2 GA). Additive fields are non-breaking; clients must ignore unknown fields.
- Requests/responses `application/json; charset=utf-8` except file bytes (sent straight to object storage with presigned URLs, never through the API).
- JSON naming `snake_case`. IDs are UUIDs (document, version, session) or opaque strings (`chunk_id`). Timestamps ISO-8601 UTC. Sizes in bytes.

### 1.2 Authentication
- `Authorization: Bearer <JWT>` issued by the IdP (OIDC authorization code + PKCE for browsers; client credentials for service/batch clients). The gateway validates signature (JWKS), `iss`, `aud=dip-api`, `exp`, and rejects tokens older than 15 minutes of lifetime.
- Claims used: `sub`, `department_id`, `clearance`, `roles`, `azp`. Authorization is **never decided from token claims alone**: the identity-access PDP resolves current permissions (cached ≤ 60 s, FR-IAM-08).
- No API keys in query strings. Webhook/callback features are out of scope for v1.

### 1.3 Authorization model in the API
Each endpoint lists a *required permission* (RBAC, e.g. `document:read`) and the *resource check* (ABAC/ACL on the specific document, department, clearance). Both must pass. Resources the caller may not know exist return **404 instead of 403**.

| Permission | Meaning |
|---|---|
| `document:upload` | create documents/versions in a department |
| `document:read` | read metadata/status of permitted documents |
| `document:reprocess` | trigger reprocessing |
| `document:delete` | request deletion |
| `search:execute` | hybrid/keyword/semantic search |
| `ai:query` | RAG, summarize, compare |
| `analytics:query` | NL-to-SQL/analytics |
| `audit:read` | read audit logs (Security Auditor only; reads are themselves audited) |
| `model:manage` | model/prompt registry actions |

### 1.4 Common request headers
| Header | Required | Purpose |
|---|---|---|
| `Authorization` | yes | Bearer JWT |
| `Idempotency-Key` | required on creating POSTs (`upload`, `bulk-upload`, `reprocess`, `ai/*`, `analytics/query`) | UUID; same key + same body within 24 h returns the original result (HTTP 200/202 with `Idempotent-Replayed: true`); same key + different body → 422 |
| `X-Request-Id` | optional | echoed back; if absent the gateway generates one |
| `traceparent` | optional | W3C trace context, propagated into Kafka |
| `If-Match` | on mutating PATCH/PUT | optimistic lock using `ETag` (`row_version`) → 412 on mismatch |

### 1.5 Common response headers
`X-Request-Id`, `ETag` (resources), `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` (IETF draft style), `Retry-After` (429/503).

### 1.6 Error response (RFC 9457, `application/problem+json`)
```json
{
  "type": "https://errors.dip.example/validation",
  "title": "Validation failed",
  "status": 400,
  "code": "DOC-4001",
  "detail": "size_bytes must be greater than 0",
  "instance": "/api/v1/documents/upload",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "errors": [ { "field": "size_bytes", "message": "must be greater than 0" } ]
}
```
No stack traces, SQL, hostnames or document text in errors.

| Status | Used for |
|---|---|
| 200 | Success (sync) |
| 201 | Resource created (synchronously committed) |
| 202 | Accepted for async processing |
| 204 | Success, no body |
| 400 | Malformed or invalid input |
| 401 | Missing/invalid/expired token |
| 403 | Authenticated but not permitted *and* existence already known to caller (e.g., listing own role limits) |
| 404 | Not found **or not visible to caller** |
| 409 | State conflict (illegal transition, duplicate) |
| 410 | Resource deleted |
| 412 | `If-Match` failed |
| 413 | Payload/size limit exceeded |
| 415 | Unsupported media type |
| 422 | Semantically invalid (idempotency key reuse with different body, unsupported combination) |
| 429 | Rate limit / quota exceeded |
| 500 | Unexpected server error |
| 502/503/504 | Dependency unavailable / timeout (retryable; `Retry-After`) |

### 1.7 Error code catalogue (excerpt)
`AUTH-4010` token invalid · `AUTH-4030` insufficient permission · `DOC-4001` validation · `DOC-4041` document not found · `DOC-4091` illegal state transition · `DOC-4092` duplicate (policy REJECT) · `DOC-4131` file too large · `DOC-4151` unsupported type · `SRCH-4001` bad query · `SRCH-5031` search degraded-unavailable · `AI-4221` insufficient scope/unsupported route · `AI-5041` LLM timeout (partial result returned if available) · `AN-4001` SQL rejected by validator · `AN-4291` analytics budget exceeded · `AUD-4030` auditor role required · `SYS-5000` internal.

### 1.8 Pagination
Keyset (cursor) pagination for all lists; offset pagination is not offered (unstable and slow at scale).
- Request: `?limit=50&cursor=<opaque>` (`limit` 1–200, default 50).
- Response envelope:
```json
{ "items": [ ], "page": { "limit": 50, "next_cursor": "eyJ0IjoiMjAyNi0xMS0wNyIsImlkIjoiLi4uIn0", "has_more": true } }
```
Cursors are signed, expire after 15 min, and encode sort key + last id. Sorting fields are whitelisted per endpoint. `total_count` is **not** returned by default (expensive); `?include_total=true` returns an approximate count for admin endpoints only.

### 1.9 Rate limits
Token bucket at gateway, keyed by `sub` (user) and by client (`azp`); limits are per minute unless stated. Values are proposals.

| Tier | Endpoints | Per user | Burst | Per org (aggregate) |
|---|---|---|---|---|
| T1 Light read | GET documents, status, sessions | 600/min | 100 | 30,000/min |
| T2 Search | POST /search | 120/min | 30 | 6,000/min |
| T3 AI | POST /ai/query, /ai/summarize | 30/min and 10 concurrent | 10 | 1,500/min |
| T4 Upload | POST /documents/upload, /bulk-upload | 60/min; bulk ≤ 1,000 files/call, ≤ 10 calls/hour | 20 | 3,000/min |
| T5 Analytics | POST /analytics/query | 20/min and 3 concurrent | 5 | 600/min |
| T6 Admin/Audit | audit, models | 60/min | 10 | – |
Exceeded → 429 + `Retry-After`. Quotas on LLM tokens per user/day are enforced by ai-orchestration (`AI-4291`).

### 1.10 Validation rules (global)
- Strings trimmed; control characters rejected; `query` ≤ 2,000 chars; metadata ≤ 50 key/value pairs, key ≤ 64 chars, value ≤ 1,024 chars.
- File names: ≤ 255 chars, no path separators, no `..`; extension allow-list: `pdf, docx, xlsx, pptx, png, jpg, jpeg, tif, tiff, txt, md` (extensible by policy). Declared MIME must match the extension; the real type is verified by magic bytes at ingestion (a mismatch yields `QUARANTINED`/`FAILED`, not a client error at upload time).
- Max single-file size: 5 GiB default (config).
- UUID path params validated before any DB access.
- Unknown JSON fields: rejected on write endpoints (`additionalProperties: false`) to prevent silent mistakes; ignored in responses by clients.

---

## 2. Document APIs

### 2.1 `POST /api/v1/documents/upload` — initiate resumable upload
| | |
|---|---|
| Auth | Bearer JWT |
| Permission | `document:upload` + upload right on `department_id` (resource check) |
| Rate limit | T4 |
| Idempotency | `Idempotency-Key` required |
| Success | `201 Created` |

Request:
```json
{
  "file_name": "Power_Spec_RevC.pdf",
  "size_bytes": 83886080,
  "declared_mime_type": "application/pdf",
  "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "department_id": "0191d3a4-0000-7000-8000-000000000010",
  "classification": "RESTRICTED",
  "existing_document_id": null,
  "title": "Power System Specification Rev C",
  "metadata": { "project": "PROJ-X", "doc_number": "PS-100", "revision": "C" }
}
```
Response `201`:
```json
{
  "document_id": "0191d3a4-7c1e-7b8a-9f10-5d2f0c5b9a11",
  "version_id": "0191d3a4-7c1f-7000-8000-0000000000a2",
  "version_no": 3,
  "state": "UPLOADED",
  "upload": {
    "upload_id": "2~xyz",
    "part_size_bytes": 67108864,
    "parts": [ { "part_number": 1, "url": "https://objects.internal/raw/…?X-Amz-Signature=…" },
               { "part_number": 2, "url": "https://objects.internal/raw/…" } ],
    "expires_at": "2026-11-07T11:00:00Z"
  },
  "duplicate_of": null,
  "links": { "complete": "/api/v1/documents/0191…/versions/0191…/complete",
             "refresh_parts": "/api/v1/documents/0191…/versions/0191…/parts" }
}
```
Validation: `file_name`, `size_bytes` (1…limit), `declared_mime_type` matches allow-list, `sha256` optional 64-hex (if supplied, server verifies after upload and rejects mismatch), `classification` ∈ allowed levels ≤ caller clearance, `department_id` exists, `existing_document_id` (if present) visible to caller and not `DELETED`.
Status codes: `201`, `400`, `401`, `403`, `404` (department/document not visible), `409` (duplicate with policy REJECT; body has `duplicate_of`), `413`, `415`, `422`, `429`, `503`.

### 2.2 `POST /api/v1/documents/{documentId}/versions/{versionId}/complete`
Permission `document:upload` (uploader or document manager). Idempotent by path.
Request:
```json
{ "parts": [ { "part_number": 1, "etag": "\"a54357aff0632cce46d942af68356b38\"" },
             { "part_number": 2, "etag": "\"0c78aef83f66abc1fa1e8477f296d394\"" } ] }
```
Response `202 Accepted` (validation and processing are asynchronous):
```json
{ "document_id": "…", "version_id": "…", "state": "VALIDATING",
  "status_url": "/api/v1/documents/0191…/status?version_id=0191…" }
```
Errors: `400` (missing/mismatched parts), `404`, `409` (already completed/aborted/expired → `DOC-4091`), `410` (upload session expired and cleaned), `422` (hash mismatch → state `FAILED` with reason). `GET …/parts` refreshes presigned URLs and lists already uploaded parts (resume).

### 2.3 `POST /api/v1/documents/bulk-upload`
Permission `document:upload`. Rate T4 (≤ 1,000 items per call).
Request:
```json
{
  "batch_name": "Q4 backlog import",
  "defaults": { "department_id": "…", "classification": "INTERNAL" },
  "items": [
    { "client_ref": "row-1", "file_name": "a.pdf", "size_bytes": 1048576, "declared_mime_type": "application/pdf", "sha256": "…" },
    { "client_ref": "row-2", "file_name": "b.docx", "size_bytes": 524288, "declared_mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }
  ]
}
```
Response `207 Multi-Status`-style envelope with HTTP `201` (batch accepted; per-item outcome):
```json
{
  "batch_id": "0191d3a5-1111-7000-8000-000000000001",
  "accepted": 1, "rejected": 1,
  "items": [
    { "client_ref": "row-1", "status": "ACCEPTED", "document_id": "…", "version_id": "…", "upload": { "…": "as in 2.1" } },
    { "client_ref": "row-2", "status": "REJECTED", "error": { "code": "DOC-4151", "detail": "Unsupported media type" } }
  ]
}
```
`GET /api/v1/batches/{batchId}` returns aggregate progress (`state counts`). Validation: ≤ 1,000 items, unique `client_ref`, total declared size ≤ configured batch cap. Whole-request failures: `400`, `401`, `403`, `413`, `429`.

### 2.4 `GET /api/v1/documents/{documentId}`
Permission `document:read` + ACL on the document. Rate T1. Supports `ETag`/`If-None-Match` (304).
Response `200`:
```json
{
  "document_id": "0191d3a4-7c1e-7b8a-9f10-5d2f0c5b9a11",
  "title": "Power System Specification Rev C",
  "doc_type": "SPECIFICATION",
  "department": { "id": "…", "name": "Power Systems" },
  "classification": "RESTRICTED",
  "lifecycle": "ACTIVE",
  "legal_hold": false,
  "current_version": { "version_id": "…", "version_no": 3, "state": "INDEXED", "searchable": true,
                       "page_count": 412, "language": "en", "size_bytes": 83886080, "sha256": "9f86…", "effective_date": "2026-09-01" },
  "versions_url": "/api/v1/documents/0191…/versions",
  "metadata": { "project": "PROJ-X", "doc_number": "PS-100", "revision": "C" },
  "created_at": "2026-11-07T09:15:30Z", "updated_at": "2026-11-07T09:40:12Z"
}
```
Errors: `401`, `404` (absent or not visible), `410` (deleted, only when caller had access).
Related: `GET /api/v1/documents` (list; filters `department_id`, `lifecycle`, `doc_type`, `state`, `created_from/to`, `q` title trigram; sort `created_at|title`; cursor pagination, returns only permitted documents), `GET /documents/{id}/versions`, `GET /documents/{id}/versions/{versionId}/download` (returns a short-lived presigned URL, audited, permission `document:read`; `403` if download is disabled for classification).

### 2.5 `GET /api/v1/documents/{documentId}/status`
Permission `document:read`. Optional `?version_id=` (default current/latest). Rate T1.
Response `200`:
```json
{
  "document_id": "…", "version_id": "…",
  "state": "PROCESSING",
  "progress_percent": 42,
  "stages": [
    { "stage": "VALIDATE", "state": "DONE",       "done_tasks": 1,  "total_tasks": 1 },
    { "stage": "EXTRACT",  "state": "RUNNING",    "done_tasks": 7,  "total_tasks": 17 },
    { "stage": "OCR",      "state": "RUNNING",    "done_tasks": 2,  "total_tasks": 4 },
    { "stage": "CHUNK",    "state": "PENDING",    "done_tasks": 0,  "total_tasks": 0 },
    { "stage": "EMBED",    "state": "PENDING",    "done_tasks": 0,  "total_tasks": 0 },
    { "stage": "INDEX",    "state": "PENDING",    "done_tasks": 0,  "total_tasks": 0 }
  ],
  "attempt": 0,
  "failure_reason": null,
  "estimated_completion": "2026-11-07T09:52:00Z",
  "updated_at": "2026-11-07T09:44:03Z"
}
```
`state` ∈ the 13 states in `02` §2.3. `estimated_completion` is best-effort (nullable). Clients poll no faster than every 5 s (guidance via `Retry-After`/`RateLimit`); push notification via the Notification service is the preferred channel.

### 2.6 `POST /api/v1/documents/{documentId}/reprocess`
Permission `document:reprocess` + `MANAGE` on the document. Rate T4. `Idempotency-Key` required. Success `202`.
Request:
```json
{
  "version_id": "0191d3a4-7c1f-7000-8000-0000000000a2",
  "from_stage": "EMBED",
  "reason": "Re-embed with bgem3@v2",
  "options": { "embedding_model": "bgem3@v2", "chunker_version": null, "priority": "P2" }
}
```
`from_stage` ∈ `EXTRACT|CHUNK|EMBED|INDEX|AUTO` (AUTO = failed stage, else full). Response `202`:
```json
{ "job_group_id": "0191d3a6-…", "version_id": "…", "state": "QUEUED", "from_stage": "EMBED",
  "status_url": "/api/v1/documents/0191…/status?version_id=0191…" }
```
Errors: `404`, `409` (version currently `PROCESSING`/`QUARANTINED`, or `DELETED` → `DOC-4091`), `422` (unknown model/chunker version or model not `ACTIVE`/`CANDIDATE`).

### 2.7 `DELETE /api/v1/documents/{documentId}`
Permission `document:delete` + `MANAGE`. Optional `?version_id=` (delete one version). Success `202` (deletion saga is asynchronous, `06` §7).
Response `202`: `{ "deletion_id": "…", "state": "DELETION_REQUESTED", "searchable": false }`. Errors: `409` `DOC-4093` (legal hold or retention not elapsed), `404`.

### 2.8 `POST /api/v1/documents/compare`
Permission `ai:query` (+ `document:read` on both versions). Rate T3. Success `200` (≤ 60 s, else `202` with job).
Request: `{ "base_version_id": "…", "target_version_id": "…", "scope": "SEMANTIC", "sections": ["Power Management"] }`
Response `200`:
```json
{
  "comparison_id": "…",
  "summary": "3 requirements changed, 1 removed, 2 added in Power Management.",
  "changes": [
    { "type": "MODIFIED", "section": "Power Management > Bus Voltage",
      "base": { "page_number": 44, "quote": "28 V ±1 V" }, "target": { "page_number": 45, "quote": "28 V ±2 V" },
      "interpretation": "Tolerance relaxed", "citation_status": "VERIFIED" }
  ],
  "evidence_status": "SUPPORTED"
}
```

---

## 3. Search API

### 3.1 `POST /api/v1/search`
Permission `search:execute` + implicit document-level filter (results contain only permitted chunks, verified server-side). Rate T2. Success `200`.
Request:
```json
{
  "query": "thermal limits of the battery pack",
  "mode": "HYBRID",
  "filters": {
    "department_ids": ["0191d3a4-0000-7000-8000-000000000010"],
    "doc_types": ["SPECIFICATION", "REPORT"],
    "date_range": { "from": "2020-01-01", "to": "2026-11-07" },
    "document_ids": [],
    "tags": ["PROJ-X"]
  },
  "top_k": 10,
  "include_history": false,
  "expand_context": true,
  "cursor": null
}
```
Response `200`:
```json
{
  "search_id": "0191d3a7-…",
  "hits": [
    {
      "chunk_id": "7GQK3M2N8X4TR1B6Y0D9ZAHP5C",
      "document_id": "0191d3a4-7c1e-7b8a-9f10-5d2f0c5b9a11",
      "version_id": "0191d3a4-7c1f-7000-8000-0000000000a2",
      "document_name": "Power_Spec_RevC.pdf",
      "version_no": 3, "current_version": true,
      "page_start": 45, "page_end": 45,
      "section_path": ["Power Management", "Battery Thermal Limits"],
      "snippet": "The battery pack shall not exceed <em>45 °C</em> during charge …",
      "score": 0.842,
      "breakdown": { "bm25_rank": 3, "vector_rank": 1, "rrf": 0.0323, "rerank": 0.842 },
      "quality_flag": null
    }
  ],
  "rewrite": { "primary": "battery pack thermal limits temperature", "variants": [] },
  "page": { "limit": 10, "next_cursor": null, "has_more": false },
  "took_ms": 412, "degraded": false, "degraded_reasons": []
}
```
Validation: `query` 1–2,000 chars; `mode` ∈ `HYBRID|KEYWORD|SEMANTIC`; `top_k` 1–100; `date_range.from ≤ to`; at most 100 `document_ids`; filters referencing departments the caller cannot read are silently intersected with their scope (not an error, no existence leak).
Degraded: if reranker/vector/lexical is down the call still returns `200` with `degraded=true` and reasons; if **both** retrievers are down → `503 SRCH-5031`.
Errors: `400 SRCH-4001`, `401`, `403`, `429`, `503`, `504`.
Also: `POST /api/v1/search/feedback` `{ "search_id", "chunk_id", "signal": "CLICK|USEFUL|NOT_USEFUL" }` → `204` (feeds evaluation data, T1).

---

## 4. AI APIs

### 4.1 `POST /api/v1/ai/query`
Permission `ai:query`. Rate T3. `Idempotency-Key` required. Success `200` (sync, up to 30 s) or `text/event-stream` when `Accept: text/event-stream` (events: `route`, `retrieval`, `token`, `final`; the `final` event carries the complete validated response — **streamed tokens are provisional until `final`**, see note).
Request:
```json
{
  "question": "Do Rev B and Rev C of the power spec disagree on main bus voltage tolerance?",
  "session_id": null,
  "scope": { "document_ids": [], "department_ids": [], "doc_types": [], "include_history": true },
  "options": { "max_sources": 8, "language": "en", "route_hint": null, "allow_sql": true }
}
```
Response `200`:
```json
{
  "response_id": "0191d3a8-…",
  "session_id": "0191d3a8-…",
  "route": "RAG",
  "answer": "Rev C specifies a 28 V ±2 V main bus [S1]; Rev B specified 28 V ±1 V [S2]. The tolerance was relaxed (interpretation).",
  "claims": [
    { "claim_id": "c1", "text": "Rev C specifies a 28 V ±2 V main bus.", "type": "FACT", "source_refs": ["S1"], "verified": true },
    { "claim_id": "c2", "text": "Rev B specified 28 V ±1 V.", "type": "FACT", "source_refs": ["S2"], "verified": true },
    { "claim_id": "c3", "text": "The tolerance was relaxed between revisions.", "type": "INTERPRETATION", "source_refs": ["S1", "S2"], "verified": true }
  ],
  "sources": [
    { "ref": "S1", "document_id": "DOC-1001", "document_name": "Power_Spec_RevC.pdf", "version_no": 3, "page_number": 45,
      "section": "Power Management > Bus Voltage", "chunk_id": "7GQK3M2N8X4TR1B6Y0D9ZAHP5C", "quote": "…28 V ±2 V…", "superseded": false },
    { "ref": "S2", "document_id": "DOC-1001", "document_name": "Power_Spec_RevB.pdf", "version_no": 2, "page_number": 44,
      "section": "Power Management > Bus Voltage", "chunk_id": "…", "quote": "…28 V ±1 V…", "superseded": true }
  ],
  "contradictions": [ { "topic": "Main bus tolerance", "source_refs": ["S1", "S2"], "note": "Different versions; S2 superseded by S1." } ],
  "limitations": [],
  "evidence_status": "SUPPORTED",
  "confidence_band": "HIGH",
  "validation": { "claims_total": 3, "claims_supported": 3, "citations_verified": 2 },
  "usage": { "input_tokens": 5120, "output_tokens": 210, "latency_ms": 4800 },
  "model": { "llm": "llm-x@2026-10", "prompt": "rag-answer@7" }
}
```
Insufficient evidence example (HTTP `200`, not an error):
```json
{ "response_id": "…", "route": "RAG", "answer": null,
  "evidence_status": "INSUFFICIENT_EVIDENCE", "confidence_band": null,
  "limitations": ["No permitted document contains a passage about this topic."],
  "sources": [], "claims": [], "contradictions": [] }
```
`confidence_band` is an evidence-derived band, **not a calibrated probability** (doc `05` §8.4). Validation: `question` 1–2,000 chars; `session_id` must belong to caller; `scope` intersected with permissions; `max_sources` 1–20.
Routing results: a SQL route returns `"route":"SQL"` with `"sql": { "statement": "...", "row_count": N, "columns": [...], "rows": [...] }` (rows capped); HYBRID returns both blocks.
Errors: `400`, `401`, `403`, `404` (session), `422 AI-4221`, `429` (also `AI-4291` token quota), `502/503`, `504 AI-5041` (LLM timeout: body contains `partial` retrieval-only sources when available).
Streaming note: if citation validation removes or changes a claim after tokens were streamed, the `final` event supersedes streamed text; clients must render `final`.

`GET /api/v1/ai/sessions/{sessionId}/messages` (T1, cursor pagination) lists a caller's own messages. `DELETE /api/v1/ai/sessions/{sessionId}` → `204`. A session never widens access; history is re-authorized on read (cited documents the user lost access to are redacted).

### 4.2 `POST /api/v1/ai/summarize`
Permission `ai:query` + `document:read` on targets. Rate T3. Success `200` for ≤ 200 pages (else `202` with job).
Request:
```json
{
  "document_ids": ["0191d3a4-7c1e-7b8a-9f10-5d2f0c5b9a11"],
  "version_id": null,
  "style": "EXECUTIVE",
  "focus": "risks and open issues",
  "max_words": 400,
  "page_range": { "from": 1, "to": 412 }
}
```
Response `200`: same shape as `ai/query` (`answer`, `claims`, `sources` with page numbers, `evidence_status`, `limitations`), plus `"coverage": { "pages_considered": 412, "pages_skipped": 12, "skipped_reason": "LOW_QUALITY_OCR" }` and `"method": "HIERARCHICAL_MAP_REDUCE"`. Validation: `document_ids` 1–20, `style` ∈ `EXECUTIVE|TECHNICAL|BULLETS`, `max_words` 50–2000. Errors as above; `202` returns `{ "job_id", "status_url": "/api/v1/ai/jobs/{jobId}" }`.

---

## 5. Analytics API

### 5.1 `POST /api/v1/analytics/query`
Permission `analytics:query` + table/view-level grants (resource check). Rate T5. `Idempotency-Key` required.
Request (natural language):
```json
{
  "question": "How many documents were uploaded per department in 2025, by month?",
  "mode": "NATURAL_LANGUAGE",
  "execution": { "max_rows": 10000, "timeout_seconds": 20, "async": false }
}
```
or validated SQL passthrough (power users, same validator): `{ "mode": "SQL", "sql": "SELECT …" }`.
Response `200`:
```json
{
  "query_id": "0191d3a9-…",
  "engine": "CLICKHOUSE",
  "sql": "SELECT department_name, toStartOfMonth(created_at) AS month, count() AS documents FROM analytics.v_documents WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01' GROUP BY department_name, month ORDER BY month LIMIT 10000",
  "explanation": "Counts documents per department per month for 2025 from view v_documents.",
  "columns": [ { "name": "department_name", "type": "String" }, { "name": "month", "type": "Date" }, { "name": "documents", "type": "UInt64" } ],
  "rows": [ ["Power Systems", "2025-01-01", 412] ],
  "row_count": 1, "truncated": false,
  "cost": { "estimated_rows_scanned": 25000000, "estimated_bytes": 800000000, "within_budget": true },
  "took_ms": 840,
  "warnings": []
}
```
Safety guarantees (enforced server-side, independent of the model): single `SELECT`/`WITH … SELECT` only (AST-validated); allow-listed schemas/views; read-only DB role with `readonly=1`; `max_execution_time`, `max_rows_to_read`, result `LIMIT` injected; row-level predicates (department/classification) injected; no functions outside allow-list (no file/URL/system functions); every query, plan and cost audited. Natural-language mode always returns the SQL for transparency.
Large jobs: if the estimate exceeds the interactive budget the API returns `202 { "query_id", "engine": "SPARK", "status_url": "/api/v1/analytics/queries/{id}", "reason": "ESTIMATE_EXCEEDS_INTERACTIVE_BUDGET" }`; `GET …/queries/{id}` → `PENDING|RUNNING|SUCCEEDED|FAILED`, results as a signed Parquet/CSV download URL (permission-checked, expires in 15 min).
Errors: `400 AN-4001` (validator rejection, reason in `errors[]` e.g., `NON_SELECT_STATEMENT`, `DISALLOWED_TABLE`), `403`, `408/504` (timeout), `422`, `429 AN-4291`, `503`.

---

## 6. Audit API

### 6.1 `GET /api/v1/audit/logs`
Permission `audit:read` (Security Auditor role; ABAC: department-scoped auditors see only their scope). Rate T6. **Every call is itself audited** (`AUDIT_READ`).
Query params: `from`, `to` (required, ≤ 31 days per call), `actor_id`, `action`, `resource_type`, `resource_id`, `outcome`, `limit` (≤ 200), `cursor`.
Response `200`:
```json
{
  "items": [
    { "id": 99120345, "occurred_at": "2026-11-07T09:52:11.120Z", "actor_id": "u-1042", "actor_type": "USER",
      "action": "AI_QUERY", "resource_type": "CHAT_SESSION", "resource_id": "0191d3a8-…", "outcome": "SUCCESS",
      "context": { "route": "RAG", "chunk_ids": ["7GQK…"], "model": "llm-x@2026-10", "prompt_version": "rag-answer@7" },
      "source_ip": "10.1.2.3", "trace_id": "4bf9…", "row_hash": "b64:…" }
  ],
  "page": { "limit": 50, "next_cursor": "…", "has_more": true },
  "integrity": { "chain_verified": true, "partition": "audit_logs_2026_11" }
}
```
Errors: `400` (range > 31 days, missing `from/to`), `401`, `403 AUD-4030`, `429`. Export: `POST /api/v1/audit/exports` (async, `202`) → signed download of the filtered range; also audited. Audit data is never editable or deletable through the API.

---

## 7. Administration APIs (summary)

| Method & path | Permission | Purpose | Success |
|---|---|---|---|
| `GET /api/v1/admin/models` | `model:manage` | list registry entries (kind, name, version, status) | 200 + cursor |
| `POST /api/v1/admin/models` | `model:manage` | register CANDIDATE model/prompt (artifact URI, checksum, params) | 201 |
| `POST /api/v1/admin/models/{id}/promote` | `model:manage` | promote to ACTIVE; **blocked unless the linked evaluation report meets gates** (`eval_report_uri` + gate pass) → else `409 MODEL-4091` | 200 |
| `POST /api/v1/admin/models/{id}/rollback` | `model:manage` | re-activate previous version | 200 |
| `GET /api/v1/admin/jobs?state=FAILED` | `ops:read` | list failed jobs/DLQ summaries | 200 |
| `POST /api/v1/admin/jobs/{id}/retry` | `ops:manage` | retry from DLQ | 202 |
| `GET /api/v1/admin/reconciliation/reports` | `ops:read` | index-parity results | 200 |
| `PUT /api/v1/admin/documents/{id}/acl` | `document:manage` / admin | replace ACL entries (requires `If-Match`) | 200 / 412 |
| `POST /api/v1/admin/quarantine/{versionId}/release` | `security:release` | release a quarantined version after review; audited with justification | 202 |
Admin APIs are exposed only on an internal gateway route / admin network; all calls audited with before/after values.

---

## 8. Health and operational endpoints (not under `/api/v1`)
`GET /actuator/health/liveness`, `/readiness` (internal only), `GET /actuator/prometheus` (metrics network only). Public `GET /api/v1/system/status` returns coarse state (`OK|DEGRADED`) without internals.

---

## 9. Cross-cutting API behaviors

| Topic | Behavior |
|---|---|
| Permission changes mid-session | Next request uses new decision (≤ 60 s propagation; revocation of document access is immediate through the PG post-check) |
| Concurrency control | `ETag`/`If-Match` on mutable resources; `409` for illegal state transitions |
| Long operations | `202` + `status_url`; never hold a request > 60 s (SSE excepted) |
| Idempotent replays | Stored result keyed by `(subject, Idempotency-Key)` in Redis/PG for 24 h |
| Time and ordering | Lists sorted by stable keys with tie-breaker `id` |
| Localization | `Accept-Language` influences error text only; data is not translated |
| Deprecation | `Deprecation` and `Sunset` headers on endpoints scheduled for removal |
| CORS | Allow-list of UI origins; no wildcard with credentials |
| Request size | JSON ≤ 1 MiB (bulk-upload ≤ 5 MiB); no file bytes via API |
| Security headers | HSTS, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store` on authenticated responses |
| Observability | Every response carries `X-Request-Id`/`trace_id`; latency, error rate, rate-limit hits exported per route |

## 10. Contract testing and acceptance criteria
| Criterion | Measure |
|---|---|
| OpenAPI is the contract | CI fails if an implemented endpoint differs from `dip-api-v1.yaml` (schema diff + Spring REST Docs/Spring Cloud Contract provider tests) |
| Backward compatibility | `oasdiff` breaking-change check on every PR |
| Error format | 100% of non-2xx responses validate against the problem+json schema in contract tests |
| Authorization | For each endpoint: a test with no token (401), insufficient permission (403/404), wrong department (404), correct (2xx) |
| Idempotency | Replaying each creating POST with the same key returns identical body, no duplicate side-effect |
| Rate limiting | Load test shows 429 at configured limits and correct `Retry-After` |
| Pagination | No duplicates/omissions when records are inserted during traversal (keyset test) |
| Latency (proposed) | `GET` document/status P95 ≤ 150 ms; search P95 ≤ 800 ms; upload initiate P95 ≤ 300 ms |

## 11. Open items
| Item | Plan |
|---|---|
| Final classification level names (`INTERNAL`, `RESTRICTED` used as placeholders) | Resolve with U-02 |
| Whether download of originals is allowed per classification | Policy decision; endpoint exists with 403 path |
| SSE vs WebSocket for streaming | SSE chosen (simple, proxy-friendly); revisit if bidirectional needs arise |
| Quota values (T1–T6) | Ratify after pilot telemetry |
| Webhook delivery for completion events | Out of v1; notifications via Notification service |
