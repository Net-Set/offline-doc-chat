# AI Document Intelligence & Knowledge Analytics Platform — Documentation Index

Independent reference architecture (not an ISRO project or specification). All capacity and performance figures are calculated from labeled assumptions; nothing has been benchmarked or run.

## Mapping to the 24 required deliverables

| # | Required deliverable | Status | Where |
|---|---|---|---|
| 1 | Project Charter | Written (unsigned draft) | [21-project-charter.md](21-project-charter.md) |
| 2 | Business Requirements Document | Written (Part 1) | [02-brd-srs-requirements.md](02-brd-srs-requirements.md) |
| 3 | Software Requirements Specification | Written (Parts 2) | [02-brd-srs-requirements.md](02-brd-srs-requirements.md) |
| 4 | Functional Requirements Specification | Written (Part 3) | [02-brd-srs-requirements.md](02-brd-srs-requirements.md) |
| 5 | Non-Functional Requirements Specification | Written (Part 4) | [02-brd-srs-requirements.md](02-brd-srs-requirements.md) |
| 6 | System Architecture Document | Written (consolidated; governs component list) | [22-system-architecture.md](22-system-architecture.md) (see also [03](03-context-hld-decisions-risks.md), [04](04-hld-detailed.md)) |
| 7 | High-Level Design | Written | [04-hld-detailed.md](04-hld-detailed.md) |
| 8 | Low-Level Design | Written | [05-lld.md](05-lld.md) |
| 9 | Data Architecture Document | Written (consolidated) | [23-data-architecture.md](23-data-architecture.md) (see also [06](06-database-design.md)) |
| 10 | Database Design Document | Written | [06-database-design.md](06-database-design.md) |
| 11 | API Specification | Written (+ OpenAPI) | [07-api-specification.md](07-api-specification.md), [openapi/dip-api-v1.yaml](openapi/dip-api-v1.yaml) |
| 12 | Kafka Event Architecture | Written | [08-kafka-event-architecture.md](08-kafka-event-architecture.md) |
| 13 | AI/ML Architecture | Written | [09-ai-ml-architecture.md](09-ai-ml-architecture.md) |
| 14 | RAG Pipeline Design | Written | [10-rag-pipeline-design.md](10-rag-pipeline-design.md) |
| 15 | Search and Retrieval Optimization | Written | [11-search-retrieval-optimization.md](11-search-retrieval-optimization.md) |
| 16 | Security Architecture | Written | [12-security-architecture.md](12-security-architecture.md) |
| 17 | Infrastructure and Deployment | Written | [13-infrastructure-deployment.md](13-infrastructure-deployment.md) |
| 18 | Disaster Recovery Plan | Written | [14-disaster-recovery-plan.md](14-disaster-recovery-plan.md) |
| 19 | Test Strategy | Written | [15-test-strategy.md](15-test-strategy.md) |
| 20 | Performance and Capacity Planning | Written | [16-performance-capacity-planning.md](16-performance-capacity-planning.md) |
| 21 | Monitoring and Observability | Written | [17-monitoring-observability.md](17-monitoring-observability.md) |
| 22 | Architecture Decision Records | Written | [18-architecture-decision-records.md](18-architecture-decision-records.md) |
| 23 | Implementation Roadmap | Written | [19-implementation-roadmap.md](19-implementation-roadmap.md) |
| 24 | Production Readiness Checklist | Written (template, all unchecked) | [20-production-readiness-checklist.md](20-production-readiness-checklist.md) |

## Stage 1 (approved) files
[01 Executive summary, scope, assumptions](01-executive-summary-scope-assumptions.md) · [02 BRD/SRS/requirements](02-brd-srs-requirements.md) · [03 Context, initial HLD, decision matrix, risks](03-context-hld-decisions-risks.md)

## Known inconsistencies to be aware of
- File numbering differs from the 24-item numbering above (files are numbered in writing order).
- Where figures differ between documents, the later/more specific one governs: capacity figures in `16` supersede `13` §5.2 (the LLM row there points to `16`); the Kafka partition-replica figure in `08` §9.4 was corrected after re-checking.
- The Stage 1 text in `03` refers to "13 deployables"; ADR-026, HLD §3 and the System Architecture (`22` §3.1, which governs the component list) use the same count and composition (12 services plus the separately deployed OCR pool).
- All 24 deliverables now exist as documents, but several are first drafts: nothing has been implemented, benchmarked, linted beyond the OpenAPI parse check, or reviewed by stakeholders. The Charter is unsigned and the Readiness Checklist is an unchecked template.
