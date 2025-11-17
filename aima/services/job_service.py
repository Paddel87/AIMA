import os
import json
import uuid
from datetime import datetime
from typing import Optional, List

from aima.config import JOBS_PATH, OUTPUTS_PATH
from aima.services.storage_service import get_stored_path
from aima.pipelines.analyzer import analyze_video


def _now() -> str:
    return datetime.utcnow().isoformat()


def _job_path(job_id: str) -> str:
    os.makedirs(JOBS_PATH, exist_ok=True)
    return os.path.join(JOBS_PATH, f"{job_id}.json")


def create_job(params: dict) -> dict:
    os.makedirs(JOBS_PATH, exist_ok=True)
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
        "video_id": params.get("video_id"),
        "video_path": params.get("video_path"),
        "duration": float(params.get("duration")),
        "modules": list(params.get("modules", [])),
        "output_dir": None,
        "error_message": None,
    }
    with open(_job_path(job_id), "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)
    return job


def get_job(job_id: str) -> Optional[dict]:
    path = _job_path(job_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_job(job: dict) -> None:
    job["updated_at"] = _now()
    with open(_job_path(job["job_id"]), "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)


def update_job_status(job_id: str, status: str, video_id: Optional[str] = None, output_dir: Optional[str] = None, error_message: Optional[str] = None) -> Optional[dict]:
    job = get_job(job_id)
    if not job:
        return None
    job["status"] = status
    if video_id is not None:
        job["video_id"] = video_id
    if output_dir is not None:
        job["output_dir"] = output_dir
    if error_message is not None:
        job["error_message"] = error_message
    _write_job(job)
    return job


def list_jobs(limit: int = 50) -> List[dict]:
    os.makedirs(JOBS_PATH, exist_ok=True)
    jobs = []
    for name in os.listdir(JOBS_PATH):
        if name.endswith(".json"):
            with open(os.path.join(JOBS_PATH, name), "r", encoding="utf-8") as f:
                jobs.append(json.load(f))
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    return jobs[:limit]


def run_job(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    try:
        update_job_status(job_id, "running")
        vid = job.get("video_id")
        vpath = job.get("video_path")
        if vid and not vpath:
            vpath = get_stored_path(vid)
            if not vpath:
                update_job_status(job_id, "failed", error_message="video_id not found")
                return
        out_base = OUTPUTS_PATH
        result_vid = analyze_video(vpath, float(job.get("duration")), list(job.get("modules", [])), out_base, video_id=vid)
        out_dir = os.path.join(out_base, result_vid)
        update_job_status(job_id, "completed", video_id=result_vid, output_dir=out_dir)
    except Exception as e:
        update_job_status(job_id, "failed", error_message=str(e))