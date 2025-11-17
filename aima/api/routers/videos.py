from fastapi import APIRouter, HTTPException
from datetime import datetime
import os

from aima.api.models import VideoSummaryResponse, VideoDetailResponse, SceneSummaryResponse
from aima.api.deps import list_video_ids, list_scenes, load_persons, load_face_person_map, get_outputs_path


router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


def _build_video_summary(video_id: str) -> VideoSummaryResponse:
    scenes = list_scenes(video_id)
    num_scenes = len(scenes)
    persons = load_persons()
    num_persons = None
    if persons:
        vids_persons = 0
        for p in persons:
            faces = p.get("faces", [])
            if any(f.get("video_id") == video_id for f in faces):
                vids_persons += 1
        num_persons = vids_persons
    created_at = None
    try:
        ts = os.path.getmtime(get_outputs_path() / video_id)
        created_at = datetime.fromtimestamp(ts)
    except Exception:
        created_at = None
    return VideoSummaryResponse(
        video_id=video_id,
        title=video_id,
        duration=None,
        num_scenes=num_scenes,
        num_persons=num_persons,
        created_at=created_at,
    )


@router.get("", response_model=list[VideoSummaryResponse])
def list_videos():
    vids = list_video_ids()
    return [_build_video_summary(v) for v in vids]


@router.get("/{video_id}", response_model=VideoDetailResponse)
def video_detail(video_id: str):
    scenes = list_scenes(video_id)
    if not scenes:
        raise HTTPException(status_code=404, detail="video_id not found or no scenes")
    fmap = load_face_person_map()
    summaries: list[SceneSummaryResponse] = []
    for s in scenes:
        sid = int(s["scene"]["id"])
        faces = s.get("faces") or []
        persons = []
        for fi in faces:
            pid = fmap.get(fi.get("face_id"))
            if pid and pid not in persons:
                persons.append(pid)
        asr_text = " ".join([a.get("text", "") for a in s.get("audio") or []]).strip()
        ocr_text = s.get("ocr_text") or ""
        excerpt_source = asr_text or ocr_text
        summaries.append(
            SceneSummaryResponse(
                scene_id=str(sid),
                video_id=video_id,
                index=sid,
                start_time=float(s["scene"]["start_s"]),
                end_time=float(s["scene"]["end_s"]),
                has_faces=len(faces) > 0,
                num_faces=len(faces),
                persons=(persons or None),
                text_excerpt=(excerpt_source[:150] if excerpt_source else None),
            )
        )
    return VideoDetailResponse(video=_build_video_summary(video_id), scenes=summaries)