import os
import json
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel

from aima.pipelines.analyzer import analyze_video
from aima.services.search_service import search_scenes
from aima.config import OUTPUTS_PATH
from aima.services.storage_service import save_upload, get_stored_path
from aima.schemas.models import UploadResponse


app = FastAPI(title="AIMA API", version="0.1.0")


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