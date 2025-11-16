import math
import os
import re
from typing import List

from aima.schemas.models import (
    SourceInfo,
    SceneInfo,
    FrameInfo,
    AudioSegment,
    DetectedObject,
    ModelStatus,
    SceneAnalysis,
)
from aima.services.frame_extractor import extract_scene_frame
from aima.modules.asr.whisper_asr import transcribe_audio
from aima.modules.objects.yolo import detect_objects
from aima.aggregator.json_aggregator import write_scene_analysis
from aima.services.embedding_service import embed_texts
from aima.services.vector_store import init_vector_store, add_scene, delete_by_video
from aima.config import GLOBAL_VECTORSTORE_PATH
import uuid
DEFAULT_YOLO_THRESHOLD = 0.6


def _split_scenes(duration_s: float) -> List[SceneInfo]:
    scenes: List[SceneInfo] = []
    i = 0
    start = 0.0
    while start < duration_s:
        end = min(start + 5.0, duration_s)
        scenes.append(SceneInfo(id=i, start_s=start, end_s=end, video_id=""))
        i += 1
        start += 5.0
    return scenes


def analyze_video(video_path: str, duration_s: float, modules: list[str], output_dir: str, video_id: str | None = None) -> str:
    os.makedirs(output_dir, exist_ok=True)
    vid = video_id or str(uuid.uuid4())
    source = SourceInfo(path=video_path, duration_s=duration_s)
    scenes = _split_scenes(duration_s)
    for s in scenes:
        s.video_id = vid
    base_dir = os.path.join(output_dir, vid)
    frames_dir = os.path.join(base_dir, "frames")
    scenes_dir = os.path.join(base_dir, "scenes")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(scenes_dir, exist_ok=True)
    client = init_vector_store(GLOBAL_VECTORSTORE_PATH)
    collection = client.get_or_create_collection(name="aima_scenes")
    delete_by_video(collection, vid)

    audio_segments: List[AudioSegment] = []
    whisper_ok = False
    whisper_err: str | None = None
    if "asr" in modules:
        try:
            audio_segments = transcribe_audio(video_path)
            whisper_ok = True
        except Exception as e:
            whisper_err = str(e)

    for scene in scenes:
        frames: List[FrameInfo] = []
        objects: List[DetectedObject] = []
        audio_in_scene: List[AudioSegment] = []

        need_frame = ("objects" in modules) or ("asr" in modules)
        ffmpeg_status = "skipped"
        ffmpeg_error: str | None = None
        frame: FrameInfo | None = None
        if need_frame:
            frame = extract_scene_frame(video_path, scene, base_dir)
            if frame is None:
                ffmpeg_status = "error"
                ffmpeg_error = "frame extraction failed"
            else:
                ffmpeg_status = "ok"
                frames.append(frame)

        if whisper_ok:
            filtered: List[AudioSegment] = []
            for s in audio_segments:
                inter_start = max(s.start_s, scene.start_s)
                inter_end = min(s.end_s, scene.end_s)
                overlap = inter_end - inter_start
                if overlap >= 0.5:
                    filtered.append(AudioSegment(start_s=inter_start, end_s=inter_end, text=s.text))
            audio_in_scene = filtered

        yolo_status = "skipped"
        yolo_error: str | None = None
        if ("objects" in modules) and frame is not None:
            try:
                objects = detect_objects(frame.path, threshold=DEFAULT_YOLO_THRESHOLD)
                yolo_status = "ok"
            except Exception as e:
                yolo_status = "error"
                yolo_error = str(e)

        models: List[ModelStatus] = []
        models.append(ModelStatus(name="ffmpeg_frame", status=ffmpeg_status, error=ffmpeg_error))
        if "asr" in modules:
            models.append(ModelStatus(name="whisper", status=("ok" if whisper_ok else "error"), error=whisper_err))
        else:
            models.append(ModelStatus(name="whisper", status="skipped", error=None))
        if "objects" in modules:
            models.append(ModelStatus(name="yolov8n", status=yolo_status, error=yolo_error))
        else:
            models.append(ModelStatus(name="yolov8n", status="skipped", error=None))

        yolo_tags = [o.class_name for o in objects]
        text_tokens: List[str] = []
        for seg in audio_in_scene:
            words = re.findall(r"\b\w+\b", seg.text.lower())
            for w in words:
                if len(w) > 3:
                    text_tokens.append(w)
        tags = list(dict.fromkeys(yolo_tags + text_tokens))

        analysis = SceneAnalysis(
            source=source,
            scene=scene,
            frames=frames,
            audio=audio_in_scene,
            objects=objects,
            models=models,
            tags=tags,
            video_id=vid,
        )
        out_json = os.path.join(scenes_dir, f"scene_{scene.id}.json")
        write_scene_analysis(out_json, analysis)

        scene_text_parts: List[str] = []
        if tags:
            scene_text_parts.append(" ".join(tags))
        if audio_in_scene:
            scene_text_parts.append(" ".join([a.text for a in audio_in_scene]))
        scene_text = " ".join(scene_text_parts).strip()
        if scene_text:
            emb = embed_texts([scene_text])[0]
            tags_str = ",".join(tags)
            add_scene(
                collection,
                scene_id=f"{vid}:{scene.id}",
                embedding=emb,
                metadata={
                    "video_id": vid,
                    "scene_id": scene.id,
                    "tags": tags_str,
                    "asr": " ".join([a.text for a in audio_in_scene]) if audio_in_scene else "",
                    "path": out_json,
                    "start": scene.start_s,
                },
            )
    return vid