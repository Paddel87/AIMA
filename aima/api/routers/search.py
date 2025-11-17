from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from aima.api.models import SearchResultSceneResponse
from aima.services.search_service import search_scenes
from aima.api.deps import load_scene_json


router = APIRouter(prefix="/api/v1/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10


@router.post("/scenes", response_model=list[SearchResultSceneResponse])
def search_scenes_api(req: SearchRequest):
    try:
        results = search_scenes(req.query, req.top_k)
        out: list[SearchResultSceneResponse] = []
        for r in results:
            vid = r.get("video_id")
            sid = r.get("scene_id")
            data = load_scene_json(vid, sid)
            excerpt = None
            if data:
                asr = " ".join([a.get("text", "") for a in data.get("audio") or []]).strip()
                ocrt = data.get("ocr_text") or ""
                ex = asr or ocrt
                excerpt = ex[:150] if ex else None
            out.append(
                SearchResultSceneResponse(
                    scene_id=str(sid),
                    video_id=str(vid),
                    score=float(r.get("score") or 0.0),
                    start_time=float(data["scene"]["start_s"]) if data else 0.0,
                    end_time=float(data["scene"]["end_s"]) if data else 0.0,
                    text_excerpt=excerpt,
                )
            )
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))