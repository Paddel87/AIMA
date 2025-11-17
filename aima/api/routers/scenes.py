from fastapi import APIRouter, HTTPException, Query
from aima.api.models import SceneSummaryResponse, SceneDetailResponse, FaceResponse
from aima.api.deps import list_video_ids, list_scenes, load_scene_json, load_face_person_map


router = APIRouter(prefix="/api/v1/scenes", tags=["scenes"])


@router.get("", response_model=list[SceneSummaryResponse])
def list_scenes_api(
    video_id: str | None = Query(None),
    person_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    vids = [video_id] if video_id else list_video_ids()
    fmap = load_face_person_map()
    out: list[SceneSummaryResponse] = []
    for vid in vids:
        scenes = list_scenes(vid)
        for s in scenes:
            sid = int(s["scene"]["id"])
            faces = s.get("faces") or []
            persons = []
            for fi in faces:
                pid = fmap.get(fi.get("face_id"))
                if pid and pid not in persons:
                    persons.append(pid)
            if person_id and (person_id not in persons):
                continue
            asr_text = " ".join([a.get("text", "") for a in s.get("audio") or []]).strip()
            ocr_text = s.get("ocr_text") or ""
            excerpt_source = asr_text or ocr_text
            out.append(
                SceneSummaryResponse(
                    scene_id=str(sid),
                    video_id=vid,
                    index=sid,
                    start_time=float(s["scene"]["start_s"]),
                    end_time=float(s["scene"]["end_s"]),
                    has_faces=len(faces) > 0,
                    num_faces=len(faces),
                    persons=(persons or None),
                    text_excerpt=(excerpt_source[:150] if excerpt_source else None),
                )
            )
    out = out[offset : offset + limit]
    return out


@router.get("/{scene_id}", response_model=SceneDetailResponse)
def scene_detail(scene_id: str):
    # find scene across videos by first match
    fmap = load_face_person_map()
    for vid in list_video_ids():
        data = load_scene_json(vid, scene_id)
        if not data:
            continue
        faces_list = []
        for fi in data.get("faces") or []:
            pid = fmap.get(fi.get("face_id"))
            faces_list.append(
                FaceResponse(
                    face_id=fi.get("face_id"),
                    bbox=fi.get("bbox") or [],
                    confidence=fi.get("confidence"),
                    person_id=pid,
                )
            )
        asr_text = " ".join([a.get("text", "") for a in data.get("audio") or []]).strip() or None
        ocr_text = data.get("ocr_text")
        objs = [o.get("class_name") for o in data.get("objects") or []] or None
        summary = SceneSummaryResponse(
            scene_id=str(data["scene"]["id"]),
            video_id=vid,
            index=int(data["scene"]["id"]),
            start_time=float(data["scene"]["start_s"]),
            end_time=float(data["scene"]["end_s"]),
            has_faces=len(faces_list) > 0,
            num_faces=len(faces_list),
            persons=list({f.person_id for f in faces_list if f.person_id}) or None,
            text_excerpt=(asr_text or ocr_text or "")[:150] or None,
        )
        return SceneDetailResponse(
            scene=summary,
            asr_text=asr_text,
            ocr_text=ocr_text,
            objects=objs,
            faces=(faces_list or None),
        )
    raise HTTPException(status_code=404, detail="scene not found")