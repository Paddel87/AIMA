import os
import uuid
from typing import Optional

from aima.config import UPLOADS_PATH


ALLOWED_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}


def ensure_uploads_dir() -> None:
    os.makedirs(UPLOADS_PATH, exist_ok=True)


def _ext_from_filename(name: str) -> str:
    return os.path.splitext(name)[1].lower()


def save_upload(file, title: Optional[str] = None, video_id: Optional[str] = None) -> dict:
    ensure_uploads_dir()
    vid = video_id or str(uuid.uuid4())
    ext = _ext_from_filename(getattr(file, "filename", ""))
    if ext not in ALLOWED_EXTS:
        raise ValueError("unsupported file extension")
    vdir = os.path.join(UPLOADS_PATH, vid)
    os.makedirs(vdir, exist_ok=True)
    dest = os.path.join(vdir, f"source{ext}")
    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                size += len(chunk)
    except Exception as e:
        raise RuntimeError(str(e))
    mime = getattr(file, "content_type", "application/octet-stream")
    return {
        "video_id": vid,
        "stored_path": dest,
        "original_filename": getattr(file, "filename", ""),
        "mime_type": mime,
        "size_bytes": size,
        "title": title or "",
    }


def get_stored_path(video_id: str) -> Optional[str]:
    vdir = os.path.join(UPLOADS_PATH, video_id)
    if not os.path.isdir(vdir):
        return None
    for name in os.listdir(vdir):
        if name.startswith("source"):
            return os.path.join(vdir, name)
    return None