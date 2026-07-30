"""WebSocket /api/jobs/{job_id}/progress — live per-page progress stream."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..job_manager import job_manager
from ..models import JobStatus

router = APIRouter()


@router.websocket("/api/jobs/{job_id}/progress")
async def job_progress(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    job = job_manager.get(job_id)
    if job is None:
        await websocket.close(code=4404, reason="Job not found")
        return

    # Send a snapshot first so late subscribers see the current state.
    await websocket.send_json({"type": "snapshot", **job.to_info().model_dump()})
    if job.status in (JobStatus.DONE, JobStatus.ERROR):
        await websocket.close()
        return

    queue = job_manager.subscribe(job)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event.get("type") == "finished":
                break
    except (WebSocketDisconnect, RuntimeError, ConnectionError):
        # A dropped client (tab closed, laptop slept) surfaces as RuntimeError
        # ("transport closed") from send_json, not only WebSocketDisconnect.
        # Either way: stop streaming; the job itself keeps running.
        pass
    finally:
        job_manager.unsubscribe(job, queue)
