import os
import json
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from aima.pipelines.analyzer import analyze_video
from aima.services.search_service import search_scenes
from aima.config import OUTPUTS_PATH

app = FastAPI(title="AIMA API", version="0.1.0")

class AnalyzeRequest(BaseModel):
    video_path: str
    duration: float
    modules: list[str] = ["objects", "asr"]
    out: str | None = None

class AnalyzeResponse(BaseModel):
    message: str
    output_dir: str

class SearchResponseItem(BaseModel):
    scene_id: str
    score: float
    metadata: dict

class SearchResponse(BaseModel):
    results: list[SearchResponseItem]

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    try:
        output_dir = req.out if req.out else OUTPUTS_PATH
        analyze_video(req.video_path, req.duration, req.modules, output_dir)
        return AnalyzeResponse(message="analysis completed", output_dir=output_dir)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/scene/{scene_id}")
def get_scene(scene_id: str):
    path = os.path.join(OUTPUTS_PATH, f"scene_{scene_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Scene not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/search", response_model=SearchResponse)
def search(query: str, top_k: int = Query(3, ge=1, le=50)):
    try:
        results = search_scenes(query, top_k)
        items = [SearchResponseItem(scene_id=r["scene_id"], score=r["score"], metadata=r["metadata"]) for r in results]
        return SearchResponse(results=items)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
