# Project Charter — Enterprise AI Document Intelligence & Knowledge Analytics Platform

| Field | Value |
|---|---|
| Document ID | DIP-CHR-01 |
| Version | 0.1 (draft for sponsor approval) |
| Status | **Unsigned.** This is a template-complete draft; names, dates, budget figures and approvals are intentionally blank or marked "to be confirmed" because they are not known. |
| Note | The platform is an **independent reference architecture** inspired by the documentation needs of large aerospace research organizations. It is **not an official ISRO project, requirement set or policy**, and nothing here states or implies ISRO's actual requirements. All sizes (10 M documents, 5 B pages) are hypothetical design assumptions. |

---

## 1. Purpose and business case
Large technical organizations accumulate millions of versioned documents (reports, specifications, papers, scans). Engineers struggle to find the authoritative, current answer and cannot prove where an answer came from; superseded or conflicting specifications go unnoticed; aggregate questions are answered by hand; and confidential content cannot be sent to public AI services.

This project delivers a **secure, distributed platform** that ingests documents at scale, makes them searchable and analyzable, answers questions with **page-level, mechanically validated citations**, detects superseded and conflicting information, and keeps full audit traceability — while keeping retrieval, structured analytics, statistics and LLM reasoning as distinct engines.

**Expected benefits (to be baselined, not promised):** reduced time to find authoritative information (target ≥ 50% median reduction in a timed study), trustworthy answers (≥ 95% citation precision on the golden set), detection of stale/conflicting specifications (≥ 85% recall on a seeded set), self-service analytics, 100% audit coverage, and a scale path from a 10,000-document pilot to millions of documents.

**Cost and benefit quantification:** deliberately not invented here. The capacity model (`16`) provides the resource formulas; unit prices depend on the hosting decision (U-01). A financial business case requires sponsor-supplied cost-of-search/time-saved data and the Medium-tier BOM produced after benchmarks (gate G4).

## 2. Objectives and success criteria

| ID | Objective | Success criterion (measured) | Verified in |
|---|---|---|---|
| BO-1 | Reduce time to find authoritative information | Median task time ↓ ≥ 50% vs baseline (30 tasks, ≥ 12 users) | M14 UAT |
| BO-2 | Trustworthy, cited answers | Citation precision ≥ 0.95; faithfulness ≥ 0.95; post-validation hallucination ≤ 2%; 0 unauthorized exposures | M8, M11, M14 |
| BO-3 | Surface stale/conflicting specs | Conflict recall ≥ 0.85; supersession recall ≥ 0.90 | M9 |
| BO-4 | Safe self-service analytics | NL-to-SQL accuracy ≥ 0.80; 0 non-read-only executions | M10 |
| BO-5 | Full traceability | 100% auditable actions recorded ≤ 60 s; tamper-evident | M11 |
| BO-6 | Scale path | Same architecture at 10k and 1M documents with measured throughput; Large-tier evidence-gated | M13, G6 |

Project-level success: Medium-tier production launch (G5) with the readiness checklist complete, SLOs defined and monitored, DR verified with measured RTO/RPO, and business sign-off.

## 3. Scope

### 3.1 In scope (Must)
Identity/RBAC/ABAC and document-level permissions; resumable upload, versioning, lifecycle, retention and secure deletion; asynchronous processing (extraction, OCR, tables, layout, classification, normalization, quality validation); structure-aware chunking; embedding infrastructure and model registry; hybrid search with reranking; grounded multi-document Q&A with validated citations; version comparison, conflict and supersession detection; summaries; safe analytics (NL-to-SQL, aggregation); audit; security and governance; reliability and DR; evaluation and model management; observability; Kubernetes deployment, CI/CD, IaC. Detailed scope: `01` §2, requirements: `02`.

### 3.2 Optional / evidence-gated
Graph RAG, agentic RAG, learned sparse/late-interaction retrieval, learning-to-rank, tiered archive indexing (needed before Large), multilingual/Indic expansion, predictive analytics, multimodal image search, fine-tuned models, cross-organization federation.

### 3.3 Out of scope
Replacing authoring tools or the document system of record; workflow/approval/e-signature engines; real-time co-editing; training foundation LLMs; the front-end/UI design and build (to be planned as a separate workstream — dependency noted); any claim of compliance with a named standard (pending U-03).

## 4. Deliverables
| Category | Deliverables |
|---|---|
| Documentation (24 items) | Charter, BRD, SRS, FRS, NFRS, System Architecture, HLD, LLD, Data Architecture, Database Design, API Spec (+OpenAPI), Kafka Event Architecture, AI/ML Architecture, RAG Design, Search Optimization, Security Architecture, Infrastructure & Deployment, DR Plan, Test Strategy, Capacity Planning, Observability, ADRs, Roadmap, Readiness Checklist — index in `README.md` |
| Software | 13 deployables (Java Spring Boot control plane; Python data/AI plane), operator console API, evaluation harness, IaC/GitOps repositories, policy-as-code, runbooks |
| Data/AI assets | Golden evaluation set, model and prompt registry entries with evaluation reports, bake-off reports (OCR, embedding, reranker, LLM, NLI), glossary of acronyms/synonyms |
| Operations | Dashboards/alerts/SLOs as code, canaries, DR test reports, handover pack, training materials |

## 5. Approach and timeline (summary of `19`)
14 milestones in three tracks: Foundation (M1–M3), Processing and Retrieval (M4–M9), Platform tracks (M10 analytics, M11 security/audit, M12 deployment/observability), then optimization and production readiness (M13–M14).

| Gate | Event |
|---|---|
| G1 | Architecture approval and ratification of NFRs and working defaults |
| G2 | Pilot readiness: search released to pilot users (end of M7) |
| G3 | AI readiness: RAG enabled for pilot users (end of M8) |
| G4 | Medium-tier commitment (capacity model validated) |
| G5 | Production go-live (end of M14) |
| G6 | Large-tier program approval (after ≥ 3 months of Medium telemetry) |

Planning figures (±35%, to be re-baselined after M3): ≈ 645 person-weeks; about 17–21 months to Medium production with a team of ≈ 14 FTE. **Dates are not committed** in this charter; they are set at G1 once the team, hosting model and GPU lead times are known.

## 6. Stakeholders and governance

### 6.1 Stakeholders
| Group | Interest | Engagement |
|---|---|---|
| Executive sponsor | Funding, outcomes, risk acceptance | Steering committee at each gate |
| Department heads / data owners | Access policy, classification, retention, adoption | Data-owner council; onboarding plans |
| Document controllers | Versions, supersession workflow | Co-design M9; UAT |
| Engineers/researchers (end users) | Search and Q&A quality | Pilot users; feedback channels |
| Analysts | Analytics | M10 co-design |
| Information security / compliance / audit | Controls, evidence | Security review at each milestone; pen-test; audit access |
| Platform/infrastructure operations | Run the platform | Joint design of M12; on-call |
| AI/ML team | Models, evaluation | Core project team |
| Procurement / finance | GPU and storage spend | G4/G6 inputs |

### 6.2 Governance structure
- **Steering committee** (sponsor, business owner, security lead, platform lead, principal architect): approves gates, scope changes, risk acceptances, budget; meets monthly and at gates.
- **Architecture board** (principal architect, security lead, platform lead, AI lead): approves ADRs, reviews designs, resolves Open ADRs by their needed-by dates (`18` §3), applies defaults if undecided.
- **Data-owner council:** classification scheme, retention, access policies, golden-set SME allocation.
- **Change control board:** production changes (two-person approval for production promotion).
- **Security review authority:** threat-model reviews, exception approvals (time-boxed).

### 6.3 RACI (summary)
| Activity | Sponsor | Architect | Eng leads | Security | Platform/SRE | AI lead | Data owners | QA |
|---|---|---|---|---|---|---|---|---|
| Scope/budget | A | R | C | C | C | C | C | I |
| Architecture/ADRs | I | A/R | C | C | C | C | I | I |
| Security design and tests | I | C | R | A | C | C | C | R |
| Infrastructure/DR | I | C | C | C | A/R | I | I | C |
| Models and evaluation | I | C | C | C | C | A/R | C | R |
| Data classification/retention | C | C | I | R | I | I | A | I |
| UAT/go-live decision | A | C | C | C | C | C | R | R |
(R = responsible, A = accountable, C = consulted, I = informed.)

### 6.4 Roles and team (assumption PA-1)
Principal architect/tech lead (1), Java backend (5), Python/ML/data (4), platform/SRE (2), SDET (1), security engineer (1, shared), part-time PM, SME annotators (~0.5 FTE for ~9 months), front-end/UX as a separate workstream. Staffing is to be confirmed at G1; a smaller team extends duration (≈ 24–30 months at 8 FTE).

## 7. Assumptions, constraints, dependencies

### 7.1 Key assumptions
Scale and usage figures (`01` §3, `16` §2) are hypothetical and will be replaced by measurements; working defaults for U-01…U-10 (`04` §0) hold until the board decides otherwise; a sample corpus and SME labeling capacity are available by M2/M5; GPUs are procurable within the schedule.

### 7.2 Constraints
Java Spring Boot (primary backend) and Python (AI/ML); confidential content must not leave the trust boundary or reach external AI providers; permissions enforced before context reaches an LLM; immutable document versions; auditability; likely restricted/sovereign infrastructure with no mandatory proprietary SaaS; open-source components preferred; LLM output is non-deterministic and uncalibrated, so citation validation is mechanical.

### 7.3 External dependencies
Hosting/GPU procurement (U-01), IdP (U-04), approved LLM and licenses (U-09), source systems (U-07), sample corpus and SMEs (U-06), compliance requirements (U-03), front-end team.

## 8. Risks (top; full register in `03` §4 and `19` §9)
| # | Risk | Mitigation | Owner |
|---|---|---|---|
| R1 | OCR cost/quality dominate (scan share unknown) | Early sampling, bake-off, page triage | AI/processing lead |
| R2 | Vector index at billions exceeds budget | Quantization, tiering, benchmark B5, embedding archive | Search lead |
| R3 | Permission leakage via retrieval/AI/caches | Multi-layer authorization, permission suite as release gate, red team | Security lead |
| R6/R8 | Hallucination / prompt injection | Validation, no-tool generation, CI corpora | AI lead |
| R11 | No golden evaluation data | Start labeling in M1; no quality claims without it | AI lead/data owners |
| R12 | Operational complexity | Phased adoption, runbooks, platform staffing | Platform lead |
| R13 | Capacity assumptions wrong | Benchmarks B1–B12 and model validation; tier gates | Architect |
| R14 | Open-weight LLM quality below need | Early bake-off; retrieval-first value; routing | AI lead |
| R17 | Hosting/GPU lead time delays milestones | Procurement started in M1; leased burst capacity | Sponsor/platform |
| R18 | Staffing shortfall or turnover | Re-plan at M3; scope levers (`19` §7) | Sponsor/PM |

## 9. Budget and resourcing approach
No monetary figures are asserted. Cost structure: GPU capacity (online reranker/LLM dominant at scale; OCR/embedding for backfill — candidates for leased burst capacity), vector-database RAM, NVMe for search/Kafka, object storage (≈ 3.5 PB raw including DR at the Large tier), observability, staffing. Approval points: initial funding at G1 (team + Initial/staging infrastructure + GPU procurement start), Medium infrastructure at G4 (after validated capacity model), Large at G6. Cost per ingested page and per query are tracked from M5 (NFR-CST-01).

## 10. Quality, security and compliance approach
Quality gates and acceptance criteria per milestone (`19`), test strategy (`15`), evaluation regression gates (`09` §7), security gates (permission-bypass suite, injection corpus, pen-test, supply-chain controls; `12`), DR verification (`14`), production readiness checklist (`20`). Compliance mapping is deferred until the regime is known (U-03); no compliance claim is made in the interim.

## 11. Communication and reporting
Sprint reviews/demos (2-week), monthly steering reports (milestone status, acceptance-criteria dashboard, risks/ADRs, capacity-model variance, DORA metrics, spend vs plan), gate reviews G1–G6, security reviews per milestone, incident communication per `14` §11, release notes per production promotion. Single source of truth: Git repositories and the documentation index.

## 12. Change control
Scope changes follow: request → impact assessment (scope, schedule, cost, risk, security) → architecture board review for design impact → steering committee decision → update of charter/SRS/roadmap/ADRs with change log. Requirement IDs are stable; removed requirements are marked withdrawn, not renumbered. Emergency changes in production follow the hotfix path (`13` §6.4).

## 13. Approval authorities and decision log pointers
Decisions on U-01…U-10 and Open/Provisional ADRs are recorded in the decision log referenced from `18`. Escalation: engineering lead → architecture board → steering committee.

## 14. Sign-off (blank until approved)
| Role | Name | Signature | Date |
|---|---|---|---|
| Executive sponsor | | | |
| Business owner | | | |
| Principal architect | | | |
| Security lead | | | |
| Platform/SRE lead | | | |
| AI/ML lead | | | |
| Data owner representative | | | |
| Compliance/legal (as applicable) | | | |

## 15. Related documents
`README.md` (index) · `01`–`03` (Stage 1) · `04` HLD · `05` LLD · `06` Database · `07` API · `08` Kafka · `09` AI/ML · `10` RAG · `11` Search · `12` Security · `13` Infrastructure · `14` DR · `15` Test · `16` Capacity · `17` Observability · `18` ADRs · `19` Roadmap · `20` Readiness · `22` System Architecture · `23` Data Architecture.
