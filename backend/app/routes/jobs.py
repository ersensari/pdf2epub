"""Job status, metadata editing, cover preview and EPUB download."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from ..config import get_settings
from ..job_manager import Job, job_manager
from ..models import BookMetadata, JobInfo, JobStatus, MetadataPatch
from ..worker import build_epub_for_job

router = APIRouter()


def _get_job_or_404(job_id: str) -> Job:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> JobInfo:
    return _get_job_or_404(job_id).to_info()


@router.get("/api/jobs/{job_id}/cover")
async def get_cover(job_id: str) -> Response:
    job = _get_job_or_404(job_id)
    if job.cover_png is None:
        raise HTTPException(status_code=404, detail="No cover extracted yet")
    return Response(content=job.cover_png, media_type="image/png")


@router.patch("/api/jobs/{job_id}/metadata")
async def patch_metadata(job_id: str, patch: MetadataPatch) -> JobInfo:
    """Apply user corrections to title/author/year and rebuild the EPUB."""
    job = _get_job_or_404(job_id)
    current = job.metadata or BookMetadata()
    job.metadata = current.model_copy(
        update={
            key: value
            for key, value in patch.model_dump(exclude_none=True).items()
        }
        | {"source": "user"}
    )
    # If processing already finished, regenerate the EPUB with the new metadata.
    if job.status == JobStatus.DONE:
        await build_epub_for_job(job, get_settings())
    return job.to_info()


@router.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> JobInfo:
    """Stop a running conversion. Cancellation lands at the next page boundary."""
    job = _get_job_or_404(job_id)
    if job.status in (JobStatus.QUEUED, JobStatus.PROCESSING) and job.task is not None:
        job.task.cancel()
    return job.to_info()


@router.get("/api/jobs/{job_id}/download")
async def download_epub(job_id: str) -> FileResponse:
    job = _get_job_or_404(job_id)
    if job.status != JobStatus.DONE or job.epub_path is None:
        raise HTTPException(status_code=409, detail="EPUB is not ready yet")

    # The EPUB is already stored under its human-readable metadata name.
    return FileResponse(
        path=job.epub_path,
        media_type="application/epub+zip",
        filename=job.epub_path.name,
    )


