import os
import json
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from aima.pipelines.analyzer import analyze_video
from aima.services.search_service import search_scenes
from aima.config import OUTPUTS_PATH
from aima.services.storage_service import save_upload, get_stored_path
from aima.schemas.models import UploadResponse, JobAnalyzeRequest, JobCreateResponse, JobStatusResponse
from aima.services.job_service import create_job, get_job, run_job, list_jobs
from aima.config import OUTPUTS_PATH, UPLOADS_PATH


app = FastAPI(title="AIMA API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="aima/static"), name="static")
templates = Jinja2Templates(directory="aima/templates")
from aima.api.routers.videos import router as videos_router
from aima.api.routers.scenes import router as scenes_router
from aima.api.routers.persons import router as persons_router
from aima.api.routers.search import router as search_router
from aima.api.routers.jobs import router as jobs_router
from aima.api.routers.upload import router as upload_router
app.include_router(videos_router)
app.include_router(scenes_router)
app.include_router(persons_router)
app.include_router(search_router)
app.include_router(jobs_router)
app.include_router(upload_router)


class AnalyzeRequest(BaseModel):
    video_path: str | None = None
    video_id: str | None = None
    duration: float
    modules: list[str] = ["objects", "asr"]
    out: str | None = None


class AnalyzeResponse(BaseModel):
    message: str
    video_id: str
    output_dir: str


class SearchResponseItem(BaseModel):
    video_id: str
    scene_id: int
    score: float
    metadata: dict


class SearchResponse(BaseModel):
    results: list[SearchResponseItem]


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    try:
        output_dir = req.out if req.out else OUTPUTS_PATH
        if (req.video_path and req.video_id) or (not req.video_path and not req.video_id):
            raise HTTPException(status_code=400, detail="provide either video_path or video_id")
        path = req.video_path
        vid = req.video_id
        if vid and not path:
            path = get_stored_path(vid)
            if not path:
                raise HTTPException(status_code=404, detail="video_id not found")
        vid = analyze_video(path, req.duration, req.modules, output_dir, video_id=vid)
        return AnalyzeResponse(message="analysis completed", video_id=vid, output_dir=os.path.join(output_dir, vid))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/scene/{video_id}/{scene_id}")
def get_scene(video_id: str, scene_id: str):
    path = os.path.join(OUTPUTS_PATH, video_id, "scenes", f"scene_{scene_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Scene not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/search", response_model=SearchResponse)
def search(query: str, top_k: int = Query(3, ge=1, le=50)):
    try:
        results = search_scenes(query, top_k)
        items = [SearchResponseItem(video_id=r["video_id"], scene_id=r["scene_id"], score=r["score"], metadata=r["metadata"]) for r in results]
        return SearchResponse(results=items)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/upload", response_model=UploadResponse)
def upload(file: UploadFile = File(...), title: str | None = Form(None)):
    if not file:
        raise HTTPException(status_code=400, detail="file required")
    try:
        info = save_upload(file, title=title)
        return UploadResponse(
            message="upload successful",
            video_id=info["video_id"],
            stored_path=info["stored_path"],
            original_filename=info["original_filename"],
            mime_type=info["mime_type"],
            size_bytes=info["size_bytes"],
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.post("/jobs/analyze", response_model=JobCreateResponse)
def jobs_analyze(req: JobAnalyzeRequest, tasks: BackgroundTasks):
    if (req.video_path and req.video_id) or (not req.video_path and not req.video_id):
        raise HTTPException(status_code=400, detail="provide either video_path or video_id")
    if req.video_id and not get_stored_path(req.video_id):
        raise HTTPException(status_code=404, detail="video_id not found")
    job = create_job({
        "video_id": req.video_id,
        "video_path": req.video_path,
        "duration": req.duration,
        "modules": req.modules,
    })
    tasks.add_task(run_job, job["job_id"])
    return JobCreateResponse(message="job created", job_id=job["job_id"], status=job["status"])


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def jobs_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        video_id=job.get("video_id"),
        output_dir=job.get("output_dir"),
        error_message=job.get("error_message"),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
    )


@app.get("/jobs")
def jobs_list(limit: int = 50):
    return list_jobs(limit)


@app.get("/videos/{video_id}/scenes")
def videos_scenes(video_id: str):
    scenes_dir = os.path.join(OUTPUTS_PATH, video_id, "scenes")
    frames_dir = os.path.join(OUTPUTS_PATH, video_id, "frames")
    if not os.path.isdir(scenes_dir):
        raise HTTPException(status_code=404, detail="video_id not found")
    items = []
    for name in sorted(os.listdir(scenes_dir)):
        if name.startswith("scene_") and name.endswith(".json"):
            path = os.path.join(scenes_dir, name)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sid = int(data["scene"]["id"])
            frame_name = f"scene_{sid}.jpg"
            frame_path = os.path.join(frames_dir, frame_name)
            has_frame = os.path.exists(frame_path)
            ocr_text = data.get("ocr_text")
            ocr_excerpt = (ocr_text[:120] if ocr_text else None)
            items.append({
                "video_id": video_id,
                "scene_id": sid,
                "start_s": float(data["scene"]["start_s"]),
                "end_s": float(data["scene"]["end_s"]),
                "tags": data.get("tags", []),
                "has_frame": has_frame,
                "frame_path": f"/media/{video_id}/frames/{frame_name}" if has_frame else None,
                "ocr_excerpt": ocr_excerpt,
            })
    return items


@app.get("/media/{video_id}/frames/{filename}")
def media_frame(video_id: str, filename: str):
    fpath = os.path.join(OUTPUTS_PATH, video_id, "frames", filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(fpath, media_type="image/jpeg")

@app.get("/api/v1/status")
def api_status():
    return {"status": "ok"}


@app.get("/ui")
def ui_dashboard(request: Request):
    jobs = list_jobs(20)
    return templates.TemplateResponse("dashboard.html", {"request": request, "jobs": jobs})


@app.get("/ui/jobs/{job_id}")
def ui_job_detail(job_id: str, request: Request):
    job = get_job(job_id)
    return templates.TemplateResponse("job_detail.html", {"request": request, "job": job})


@app.get("/ui/videos/{video_id}/scenes")
def ui_scenes(video_id: str, request: Request):
    scenes = videos_scenes(video_id)
    return templates.TemplateResponse("scenes.html", {"request": request, "video_id": video_id, "scenes": scenes})


@app.get("/ui/search")
def ui_search(request: Request, query: str | None = None, top_k: int = 5):
    results = []
    if query:
        res = search_scenes(query, top_k)
        for r in res:
            md = r.get("metadata", {})
            asr = md.get("asr", "")
            ocrt = md.get("ocr_text", "")
            excerpt = (asr or ocrt)[:150]
            tags = md.get("tags", [])
            results.append({
                "score": r.get("score"),
                "video_id": r.get("video_id"),
                "scene_id": r.get("scene_id"),
                "excerpt": excerpt,
                "tags": ", ".join(tags) if isinstance(tags, list) else str(tags),
            })
    return templates.TemplateResponse("search.html", {"request": request, "query": query or "", "top_k": top_k, "results": results})


@app.post("/ui/upload")
def ui_upload(request: Request, file: UploadFile = File(...), title: str | None = Form(None)):
    if not file:
        raise HTTPException(status_code=400, detail="file required")
    info = save_upload(file, title=title)
    return RedirectResponse(url="/ui", status_code=303)


@app.post("/ui/jobs/analyze")
def ui_jobs_analyze(request: Request, tasks: BackgroundTasks, video_id: str = Form(...), duration: float = Form(11), modules: str = Form("objects,asr")):
    if not video_id:
        raise HTTPException(status_code=400, detail="video_id required")
    if not get_stored_path(video_id):
        raise HTTPException(status_code=404, detail="video_id not found")
    job = create_job({"video_id": video_id, "video_path": None, "duration": float(duration), "modules": [m.strip() for m in modules.split(",") if m.strip()]})
    tasks.add_task(run_job, job["job_id"])
    return RedirectResponse(url=f"/ui/jobs/{job['job_id']}", status_code=303)