"""POST /api/upload — accept a PDF, create a job, start processing."""

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, UploadFile

from ..config import get_settings
from ..job_manager import job_manager
from ..worker import process_job

router = APIRouter()


@router.post("/api/upload")
async def upload_pdf(file: UploadFile) -> dict[str, str]:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = settings.upload_dir / f"{uuid.uuid4().hex}.pdf"
    pdf_path.write_bytes(await file.read())

    job = job_manager.create(pdf_path)
    job.task = asyncio.create_task(process_job(job, job_manager, settings))
    return {"job_id": job.job_id}
