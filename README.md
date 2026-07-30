# pdf2epub

Convert scanned, old Turkish (Latin alphabet) books from PDF to EPUB.

The pipeline runs OCR on each page, then uses a **local** vision-language model
(via [Ollama](https://ollama.com), `gemma4`) to fix OCR errors,
detect the page structure (headings / paragraphs / footnotes), infer the book's
title and author when the PDF metadata is missing, and finally assembles a
valid EPUB with cover and table of contents.

```
React 19 + Vite  ──▶  FastAPI backend  ──▶  Ollama (on the HOST)
   (frontend)          (container)           llama3.2-vision:11b
                          │
                          ▼
              PyMuPDF + PaddleOCR/Tesseract + ebooklib
```

## Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- **Ollama running on the host machine** with the vision model pulled:

  ```sh
  ollama pull gemma4
  ollama serve   # usually already running as a service
  ```

  Ollama is deliberately **not** part of the Compose stack — the backend
  container reaches the host instance via `http://host.docker.internal:11434`.

  > **⚠️ Important (macOS):** two things must hold, or every LLM call silently
  > falls back to raw OCR text (symptom: conversion "succeeds" but the book is
  > untitled and all pages are flagged for review):
  >
  > 1. The Ollama app must listen on all interfaces, not just `127.0.0.1`:
  >    enable **"Expose Ollama to the network"** in the Ollama app settings
  >    (or `launchctl setenv OLLAMA_HOST 0.0.0.0` and reopen Ollama).
  > 2. Do **not** map `host.docker.internal` via `extra_hosts: host-gateway`
  >    in `docker-compose.yml` — on Docker Desktop for Mac that overrides the
  >    built-in resolution with `172.17.0.1`, which is not the host. (Linux
  >    users need that mapping; macOS users must leave it commented out.)
  >
  > Verify from inside the container:
  > `docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags').status)"`

## Quick start

```sh
docker compose up --build
```

| Service  | URL                     |
| -------- | ----------------------- |
| Frontend | http://localhost:5174   |
| Backend  | http://localhost:8001   |
| API docs | http://localhost:8001/docs |

Then open the frontend, drop a scanned PDF, watch the page-by-page progress,
review/edit the detected cover and metadata, and download the EPUB.

Uploaded PDFs and generated EPUBs are stored in `./data`.

## Configuration (`.env`)

| Variable            | Default                                | Notes                                        |
| ------------------- | -------------------------------------- | -------------------------------------------- |
| `OLLAMA_HOST`       | `http://host.docker.internal:11434`    | Use `http://localhost:11434` outside Docker  |
| `OLLAMA_MODEL`      | `gemma4`                               |                                              |
| `OCR_ENGINE`        | `paddle`                               | `paddle` or `tesseract`                      |
| `RENDER_DPI`        | `300`                                  | Page render resolution for OCR               |
| `VITE_API_BASE_URL` | `http://localhost:8000`                | Backend URL used by the frontend             |

## Development without Docker

Backend:

```sh
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
OLLAMA_HOST=http://localhost:11434 .venv/bin/uvicorn app.main:app --reload
```

Frontend:

```sh
cd frontend
npm install
npm run dev
```

## Tests

```sh
cd backend
.venv/bin/python -m pytest            # unit tests (no Ollama needed)
.venv/bin/python -m pytest -m integration   # needs Ollama running on the host
```

Tests that talk to a real Ollama instance are marked `@pytest.mark.integration`
and are skipped in the default run.

## Pipeline overview

1. **`pdf_extract.py`** — PDF metadata, cover candidates (large book-shaped
   embedded images from the first pages + first-page render), page rendering.
   Detects digital vs. scanned PDFs; digital text is extracted directly and
   only image-only pages go through OCR (mixed PDFs supported).
2. **`cover_analysis.py`** — the vision model inspects each cover candidate,
   picks the real cover and reads the title/author printed on it.
3. **`ocr.py`** — `OCREngine` strategy: PaddleOCR (primary) or Tesseract
   (`tur`) selected via `OCR_ENGINE`.
4. **`cleanup.py`** — strips page numbers and repeated running headers/footers
   from page edges, drops front-matter pages (copyright, ISBN, publisher).
5. **`correction.py`** — per page, raw OCR text + page image go to Ollama;
   the JSON answer is validated with Pydantic, retried once on invalid output,
   and falls back to the raw OCR text if it still fails. Pages with confidence
   below 0.6 are flagged for manual review.
6. **`metadata_llm.py`** — title/author/year inference from the first pages.
   Merge priority: user edits > cover analysis > content inference > PDF metadata.
7. **`epub_builder.py`** — chapters split at heading pages, TOC (NCX + Nav),
   cover embedding via ebooklib.
