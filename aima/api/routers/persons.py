from fastapi import APIRouter, HTTPException
from aima.api.models import PersonSummaryResponse, PersonDetailResponse, SceneSummaryResponse, VideoSummaryResponse
from aima.api.deps import load_persons, load_face_person_map, list_video_ids, load_scene_json, list_scenes


router = APIRouter(prefix="/api/v1/persons", tags=["persons"])


@router.get("", response_model=list[PersonSummaryResponse])
def list_persons():
    persons = load_persons()
    res: list[PersonSummaryResponse] = []
    for p in persons:
        res.append(
            PersonSummaryResponse(
                person_id=p.get("person_id"),
                display_name=None,
                num_faces=int(p.get("num_faces") or 0),
                num_scenes=int(p.get("num_scenes") or 0),
                num_videos=int(p.get("num_videos") or 0),
            )
        )
    return res


@router.get("/{person_id}", response_model=PersonDetailResponse)
def person_detail(person_id: str):
    persons = load_persons()
    target = next((p for p in persons if p.get("person_id") == person_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="person not found")
    fmap = load_face_person_map()
    scenes: list[SceneSummaryResponse] = []
    videos: dict[str, VideoSummaryResponse] = {}
    for vid in list_video_ids():
        for s in list_scenes(vid):
            sid = int(s["scene"]["id"])
            faces = s.get("faces") or []
            has_person = False
            for fi in faces:
                pid = fmap.get(fi.get("face_id"))
                if pid == person_id:
                    has_person = True
                    break
            if not has_person:
                continue
            asr_text = " ".join([a.get("text", "") for a in s.get("audio") or []]).strip()
            ocr_text = s.get("ocr_text") or ""
            excerpt_source = asr_text or ocr_text
            scenes.append(
                SceneSummaryResponse(
                    scene_id=str(sid),
                    video_id=vid,
                    index=sid,
                    start_time=float(s["scene"]["start_s"]),
                    end_time=float(s["scene"]["end_s"]),
                    has_faces=len(faces) > 0,
                    num_faces=len(faces),
                    persons=[person_id],
                    text_excerpt=(excerpt_source[:150] if excerpt_source else None),
                )
            )
            videos.setdefault(
                vid,
                VideoSummaryResponse(
                    video_id=vid,
                    title=vid,
                    duration=None,
                    num_scenes=0,
                    num_persons=None,
                    created_at=None,
                ),
            )
    person_summary = PersonSummaryResponse(
        person_id=person_id,
        display_name=None,
        num_faces=int(target.get("num_faces") or 0),
        num_scenes=int(target.get("num_scenes") or 0),
        num_videos=int(target.get("num_videos") or 0),
    )
    return PersonDetailResponse(person=person_summary, scenes=scenes, videos=list(videos.values()))