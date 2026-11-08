# Offline Document Intelligence

Chat with your documents **fully offline**. Upload a PDF, Word file, image or text file and ask questions. The chat model, embeddings, OCR, reranker, search and storage all run on your own PC and listen on `127.0.0.1` only. There are no API keys, no cloud and no internet at runtime.

The repository has two parts:

| Folder | What it is |
|---|---|
| [`app/`](app/) | The runnable local app: document upload, structure extraction, hybrid search, local LLM chat, answer checking. |
| [`docs/`](docs/) | An enterprise reference architecture for a scaled-up version of the platform (24 documents plus an OpenAPI spec). |

> The design set in `docs/` is an independent reference architecture. It is not an official requirement set from any organisation.

## Features

- **Fully local.** llama.cpp runs a small chat model and an embedding model on CPU. No GPU is needed.
- **Many formats.** Digital and scanned PDFs (OCR), DOCX, PNG/JPG, TXT, MD and CSV, up to 50 MB each.
- **Structure first.** Chapters, sections, pages, tables and numbered lists are read from the document's own structure. Questions like "how many chapters", "5th design pattern" or "what is on page 86" are answered by code, not guessed by the model.
- **Hybrid retrieval.** BM25 plus vector search, fused with RRF and reranked with a cross-encoder.
- **Answers are checked.** Each sentence is compared with the retrieved text. Supported sentences get `[S#]` citations with document and page. Unsupported ones are removed or marked. If the text cannot support an answer, the app says so, or quotes the best passage word for word.
- **Consistent answers.** The first attempt uses fixed settings. If the checker finds unsupported claims, the app asks again automatically.
- **Prompt-injection resistant.** Text inside documents is treated as data, never as instructions.

## Quick start (Windows)

1. Go to `app/` and double-click **`start.bat`**. You can also run `powershell -ExecutionPolicy Bypass -File start.ps1`.
2. When it says "ready", open **http://127.0.0.1:8000**.
3. Drag in a document and wait for **INDEXED**.
4. Ask questions. Click a `[S1]` tag to see the exact passage and page.
5. Stop with **`stop.bat`**.

Ports: 8000 (app), 8081 (chat model), 8082 (embeddings).

## How it works

```
Upload ─► extract text (PyMuPDF / OCR / python-docx)
       ─► clean headers and footers ─► detect outline, chapters, tables
       ─► chunk (pages never crossed, tables kept whole)
       ─► embed + BM25 index (SQLite)

Question ─► small talk? ─► structure / metadata / table / list tools (exact, no model)
         ─► otherwise hybrid search ─► rerank ─► local LLM (JSON-forced where needed)
         ─► code validates every sentence ─► citations ─► answer
```

The guiding rule is that the model extracts or chooses, and code counts and validates.

## Tech stack

Python, FastAPI, SQLite, llama.cpp (`llama-server`), Qwen2.5-1.5B-Instruct (Q4_K_M), nomic-embed-text-v1.5, FlashRank (MiniLM cross-encoder), PyMuPDF and pymupdf4llm, pdfplumber, RapidOCR (ONNX), python-docx, and a single-page HTML/JS front end.

## Tests

Run these from `app/` while the app is running:

```bash
venv\Scripts\python.exe tests\run_golden.py
venv\Scripts\python.exe tests\run_book.py M1
```

- `run_golden.py` is the golden-question regression suite. It builds fixtures, asks about 49 questions and reports accuracy by category.
- `run_book.py` runs structure checks on a book you have already uploaded. It never deletes anything.

## Honest limits

- A 1.5B model is good at looking up written facts. It is weak at long reasoning, maths and comparing many documents. Check the citation for anything important.
- Counting is exact for numbered lists and headings. It cannot count things the document never lists.
- OCR quality depends on the scan. Handwriting and complex merged-cell tables are poor.
- Content answers take roughly 10–25 s on a 4-core CPU. A 300-page book takes about 6–8 minutes to index.
- Models and the virtual environment need several GB of disk. Keep free space on the drive.
- There is no login. Anyone on the PC can open the app.

## Roadmap

1. Build a **document map** at upload: chapter and section summaries, definitions, and counts of examples and exercises.
2. Add a **model-chosen tool plan** (forced JSON) that picks a tool, with code executing it exactly.
3. Support a larger model (3–7B) or a GPU, with no redesign.

## Documentation

See [`docs/README.md`](docs/README.md) for the architecture set: executive summary, HLD, LLD, database, API, Kafka events, AI/RAG, security, infrastructure, DR, testing, capacity, observability, ADRs and roadmap. More detail on the app is in [`app/README.md`](app/README.md).

## Not included in the repository

Do not commit these. A `.gitignore` is provided.

- `app/models/`: model weights, over 1 GB
- `app/bin/`: llama.cpp binaries
- `app/venv/`: Python virtual environment
- `app/data/`: your uploaded documents, database and logs
