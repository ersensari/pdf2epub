"""In-memory job store and progress broadcasting.

Deliberately simple: a dict of jobs plus asyncio primitives. This is a
single-user local tool, so no Redis/Celery — do not "upgrade" this.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import BookMetadata, JobInfo, JobStatus, PageResult, Progress, Stage


@dataclass
class Job:
    job_id: str
    pdf_path: Path
    status: JobStatus = JobStatus.QUEUED
    progress: Progress = field(default_factory=Progress)
    metadata: BookMetadata | None = None
    pages: list[PageResult] = field(default_factory=list)
    cover_png: bytes | None = None
    epub_path: Path | None = None
    error: str | None = None
    task: asyncio.Task[None] | None = None
    # One queue per connected WebSocket client.
    subscribers: list[asyncio.Queue[dict[str, Any]]] = field(default_factory=list)

    def to_info(self) -> JobInfo:
        return JobInfo(
            job_id=self.job_id,
            status=self.status,
            progress=self.progress,
            metadata=self.metadata,
            pages_needing_review=[p.page_number for p in self.pages if p.needs_review],
            error=self.error,
        )


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self, pdf_path: Path) -> Job:
        job = Job(job_id=uuid.uuid4().hex, pdf_path=pdf_path)
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    # --- progress events -------------------------------------------------

    def subscribe(self, job: Job) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        job.subscribers.append(queue)
        return queue

    def unsubscribe(self, job: Job, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in job.subscribers:
            job.subscribers.remove(queue)

    def publish(self, job: Job, event: dict[str, Any]) -> None:
        """Push an event to every WebSocket subscriber of this job."""
        for queue in job.subscribers:
            queue.put_nowait(event)

    def update_progress(
        self,
        job: Job,
        *,
        stage: Stage,
        current_page: int | None = None,
        total_pages: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        job.progress.stage = stage
        if current_page is not None:
            job.progress.current_page = current_page
        if total_pages is not None:
            job.progress.total_pages = total_pages
        event: dict[str, Any] = {
            "type": "progress",
            "status": job.status,
            "stage": stage,
            "current_page": job.progress.current_page,
            "total_pages": job.progress.total_pages,
        }
        if extra:
            event.update(extra)
        self.publish(job, event)

    def finish(self, job: Job, *, error: str | None = None, cancelled: bool = False) -> None:
        if cancelled:
            job.status = JobStatus.CANCELLED
        else:
            job.status = JobStatus.ERROR if error else JobStatus.DONE
        job.error = error
        self.publish(
            job,
            {"type": "finished", "status": job.status, "error": error},
        )


# Module-level singleton shared by the routes.
job_manager = JobManager()
