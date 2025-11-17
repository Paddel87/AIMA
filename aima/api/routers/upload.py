from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from aima.api.models import UploadResponse
from aima.services.storage_service import save_upload
from aima.services.job_service import create_job, run_job


router = APIRouter(prefix="/api/v1/upload", tags=["upload"])


@router.post("/video", response_model=UploadResponse)
def upload_video(
    tasks: BackgroundTasks,
    file: UploadFile = File(...),
    duration: float = Form(...),
    modules: str = Form("objects,asr"),
    title: str | None = Form(None),
):
    if not file:
        raise HTTPException(status_code=400, detail="file required")
    info = save_upload(file, title=title)
    job = create_job({
        "video_id": info["video_id"],
        "video_path": None,
        "duration": float(duration),
        "modules": [m.strip() for m in modules.split(",") if m.strip()],
    })
    tasks.add_task(run_job, job["job_id"])
    return UploadResponse(job_id=job["job_id"], video_id=info["video_id"], message="upload scheduled")