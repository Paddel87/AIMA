from pathlib import Path
import os
import json
from typing import Optional, Dict, Any, List

from aima.config import OUTPUTS_PATH, UPLOADS_PATH


def get_outputs_path() -> Path:
    return Path(OUTPUTS_PATH)


def get_uploads_path() -> Path:
    return Path(UPLOADS_PATH)


def list_video_ids() -> List[str]:
    base = get_outputs_path()
    if not base.exists():
        return []
    vids: List[str] = []
    for p in base.iterdir():
        if not p.is_dir():
            continue
        if p.name in {"vectorstore", "persons"}:
            continue
        if (p / "scenes").exists():
            vids.append(p.name)
    vids.sort()
    return vids


def load_scene_json(video_id: str, scene_id: int | str) -> Optional[Dict[str, Any]]:
    path = get_outputs_path() / video_id / "scenes" / f"scene_{scene_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_scenes(video_id: str) -> List[Dict[str, Any]]:
    scenes_dir = get_outputs_path() / video_id / "scenes"
    if not scenes_dir.exists():
        return []
    items: List[Dict[str, Any]] = []
    for fn in sorted(os.listdir(scenes_dir)):
        if fn.startswith("scene_") and fn.endswith(".json"):
            with open(scenes_dir / fn, "r", encoding="utf-8") as f:
                items.append(json.load(f))
    return items


def load_persons() -> List[Dict[str, Any]]:
    p = get_outputs_path() / "persons" / "persons.json"
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def load_face_person_map() -> Dict[str, str]:
    p = get_outputs_path() / "persons" / "face_person_map.json"
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)