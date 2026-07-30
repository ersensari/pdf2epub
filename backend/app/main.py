"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes import jobs, library, upload, ws

app = FastAPI(title="pdf2epub", description="Scanned Turkish PDF → EPUB converter")

# Local single-user tool: the Vite dev server is the only expected origin,
# but keep CORS permissive for simplicity.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(jobs.router)
app.include_router(library.router)
app.include_router(ws.router)


@app.on_event("startup")
async def ensure_data_dirs() -> None:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
