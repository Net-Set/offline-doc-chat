# Local Document Chat (fully offline)

Upload documents, then chat with them. **No API, no cloud, no internet at runtime** — chat model, embedding model, OCR, reranker, search and storage all run on this PC and listen on `127.0.0.1` only. (Internet was used once, only to download the tools and models listed below.)

## Run
Double-click **`start.bat`** (or `powershell -ExecutionPolicy Bypass -File start.ps1`). When it says "ready", open **http://127.0.0.1:8000**. Stop with **`stop.bat`**.

1. Drag in PDF (digital **or scanned**), DOCX, images (PNG/JPG), TXT, MD, CSV — up to 50 MB each.
2. Wait for **INDEXED** (scanned pages take a few seconds each for OCR).
3. Ask. Tick documents on the left to limit questions to them. Click `[S1]` tags to see the exact passage, page and section.

## What is installed (all in `D:\DOC_AI\app`)
| Part | Purpose | Size |
|---|---|---|
| `bin\` llama.cpp b12187 (CPU) | runs both models, forces JSON output for extraction | 61 MB |
| `models\qwen2.5-1.5b-instruct-q4_k_m.gguf` | chat model | 1.1 GB |
| `models\nomic-embed-text-v1.5.Q4_K_M.gguf` | embeddings | 84 MB |
| `models\flashrank\` ms-marco-MiniLM-L-12-v2 (ONNX) | reranker for search results | 33 MB |
| venv: **PyMuPDF + pymupdf4llm** | reads PDFs as structured text (headings, lists, tables) | ~65 MB |
| venv: **pdfplumber** | extra table finder for ruled tables | small |
| venv: **RapidOCR (ONNX)** | OCR for scanned PDFs and images, models bundled | ~30 MB |
| venv: FastAPI, numpy, httpx, pypdf (fallback), python-docx | app plumbing | |

## How a question is answered (the router)
| Question type | What happens | Accuracy source |
|---|---|---|
| "how many pages / documents" | answered from stored metadata | exact |
| "how many X / list all X" where X is a **numbered list under a heading** (e.g. "2. Design Pattern → 10 items") | read from the document's structure | exact, no model |
| "how many X / list X" otherwise | the model **lists items passage by passage** (JSON-forced), **code** verifies each name occurs in the text, de-duplicates and counts | verified names; model may miss some (marked PARTIALLY SUPPORTED) |
| one small document | whole document is given to the model | model reads everything |
| everything else | hybrid search (BM25 + vectors) → **FlashRank rerank** → top 4 passages → model answers | citations aligned by code |
Every answer sentence is checked by code against the retrieved text: supported sentences get `[S#]` with document and page; unsupported ones get `[unverified]`; if nothing is supported you get an explicit "not enough information" or the closest passages instead of a guess. Text inside documents is treated as data, never as instructions.

## Books and long documents (added after testing with a 300-page maths textbook)
- **Structure questions are answered from the extracted headings, instantly, without the model:** "how many chapters", "list the chapters", "what is chapter 3 about", "which chapter is about determinants", "what is section 3.4.5", "what is on page 86". Chapters come from "Chapter N" openers and section numbering (N.1 …); running page headers and converter junk are removed.
- **Small talk** ("hi", "thanks", "help") gets a friendly reply listing your documents.
- **If the model cannot write an answer the text supports, but the right passage was found, the app quotes the best sentences word for word** (clearly labelled), instead of refusing. It still refuses when the question's words are not in the text.
- **Same question, same answer:** the first attempt uses fixed settings; if the code finds unsupported statements it asks again automatically (up to 2 more times), removes unsupported statements, and only remembers the previous exchange when it was fully supported.
- Page numbers are PDF-viewer page numbers (a book's printed numbers may be lower).
- A 300-page book takes ~6-8 minutes to index and the page may freeze for a few seconds while it reads; `POST /api/documents/{id}/restructure` rebuilds only chapters/outline (~2 min) after structure-detection improvements.

## Tests
- `tests\run_golden.py` — **golden-question regression**: creates known fixtures (digital PDF, scanned PDF, table PDF, Word list, your design-pattern PDF if present), asks ~25 questions and prints accuracy per category. Run it after every change: `venv\Scripts\python.exe tests\run_golden.py` (needs the app running). Latest results are in `tests\last_run.json`.
- `testsun_book.py [name]` — structure checks on a book you already uploaded (default `M1`); it never deletes anything.
- `tests\smoke_test.py` — quick 5-question check.
- `run_golden.py` only replaces its own fixture copies and never deletes your documents.

## Limits (be honest with yourself)
- A 1.5B model is good at looking up written facts; weak at long reasoning, maths, comparing many documents. Check the cited passage for anything important.
- Counting works best for numbered lists (exact) and clearly delimited items (model-listed). It cannot count things the document never lists.
- OCR quality depends on the scan; low-confidence pages are flagged. Handwriting and unusual layouts are poor.
- Tables are read as text rows; complex merged-cell tables can be garbled.
- **Disk: C: is almost full (tens of MB free) and D: has under 1 GB free.** Delete unused documents (✕) and free space on both drives; a nearly full C: can make Windows and tools misbehave.
- No logins: anyone using this PC can open the app.

## Settings (environment variables, optional)
`TOP_K_CONTEXT` (4), `MIN_COSINE` (0.38), `MAX_ANSWER_TOKENS` (350), `FULL_CONTEXT_CHARS` (6500), `USE_RERANK` (1), `RERANK_CANDIDATES` (12), `MAX_EXTRACT_CHUNKS` (40), `OCR_DPI` (170).

## Bigger model later
When you have ~3–10 GB free: put a 3–4B `.gguf` (e.g. Qwen2.5-3B/Qwen3-4B) in `models\`, change the `-m` path in `start.ps1`, run `tests\run_golden.py` and compare accuracy and speed with `tests\last_run.json`.

## Troubleshooting
Logs: `data\logs\*.log`. Ports: 8000 (app), 8081 (chat), 8082 (embeddings).
