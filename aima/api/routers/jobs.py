from fastapi import APIRouter, HTTPException
from aima.api.models import JobSummaryResponse
from aima.services.job_service import list_jobs, get_job


router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=list[JobSummaryResponse])
def jobs_list(limit: int = 50):
    jobs = list_jobs(limit)
    out: list[JobSummaryResponse] = []
    for j in jobs:
        out.append(
            JobSummaryResponse(
                job_id=j.get("job_id"),
                video_id=j.get("video_id"),
                video_path=j.get("video_path"),
                status=j.get("status"),
                created_at=j.get("created_at"),
                finished_at=j.get("updated_at") if j.get("status") == "completed" else None,
            )
        )
    return out


@router.get("/{job_id}", response_model=JobSummaryResponse)
def job_detail(job_id: str):
    j = get_job(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="job not found")
    return JobSummaryResponse(
        job_id=j.get("job_id"),
        video_id=j.get("video_id"),
        video_path=j.get("video_path"),
        status=j.get("status"),
        created_at=j.get("created_at"),
        finished_at=j.get("updated_at") if j.get("status") == "completed" else None,
    )