# CLAUDE.md

This file contains context and guidelines for AI code assistants (Claude Code, Cursor, etc.) working on this repo. Read this before writing code.

## Project Summary

An open-source, Docker-based tool that converts old, scanned Turkish (Latin alphabet) books from PDF to EPUB. Uses OCR + a local vision-language model (Ollama, `gemma4`) to correct OCR errors, extract book structure, detect cover/metadata, and produce a valid EPUB.

For detailed architecture, see `docs/architecture.md` or the vibe-coding prompt at the project root (if present).

## Environment and Running

- **Ollama runs on the host machine, NOT inside the container.** Access from the container via `http://host.docker.internal:11434`. Do NOT try to install Ollama in the container.
- Development host: macOS, Apple Silicon (M5, 24GB RAM). Docker Desktop installed, `host.docker.internal` works natively.
- Model name: `gemma4`. Do not hardcode it in code; read it from `.env` / `config.py`.
- Starting services: `docker compose up --build`
- Backend alone: `cd backend && uvicorn app.main:app --reload`
- Frontend alone: `cd frontend && npm run dev`

## Architectural Decisions (ask before changing)

- Job queue is **in-memory + asyncio**, NO Redis/Celery. A deliberate simplicity decision for a single-user local tool — don't try to switch this to Celery for "production-grade" reasons.
- OCR engine should be selectable (`OCR_ENGINE=paddle|tesseract` env); don't lock to a single engine.
- NO Auth / rate limiting, by design. Don't add it.
- Every request to Ollama validates JSON output with Pydantic; if validation fails, retry once, then fall back to raw OCR text. Don't break this error tolerance chain.

## Code Standards

**Backend (Python)**
- Python 3.12, type annotations mandatory (to a level mypy won't complain)
- Pydantic v2 models, based on `BaseModel`
- Pipeline modules (`pipeline/*.py`) must be independently testable — each should be pure functions/classes, not dependent on FastAPI request/response objects
- Abstractions like `OCREngine` and `CorrectionBackend` defined via abstract base class; when adding a new engine/backend, extend the existing interface, don't modify existing calling code

**Frontend (React/TypeScript)**
- React 19, functional components + hooks, NO class components
- Tailwind utility classes; don't open separate CSS files
- WebSocket connection logic isolated in `useJobProgress` hook; don't write WebSocket code inside components

## Test Rules

- At least 1 unit test expected for each module under `pipeline/`
- Tests requiring real Ollama calls should be marked with `@pytest.mark.integration`, skipped in default `pytest` run (assuming Ollama may not always be running)
- When adding a new pipeline step, include at least one happy-path + one "returned invalid JSON" test with mocked Ollama response

## Things That Should NOT Be Done

- Installing Ollama inside the container
- Adding "production hardening" like Auth, rate limiting, Redis/Celery — out of scope, don't add without asking
- Tightly coupling pipeline modules to FastAPI routes (breaks testability)
- Hardcoding the model name or Ollama host URL in code

## Commit / PR Habits

- Small, single-purpose commits: one pipeline module = one commit
- Commit messages can be in Turkish or English; be consistent (use the same language throughout the project)
- For each new pipeline step, the related unit test should go in the same commit, not in a separate "add test" commit later
