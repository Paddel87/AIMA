import os
import subprocess
import shutil
from typing import Optional

from aima.schemas.models import SceneInfo, FrameInfo


def _ffmpeg_bin() -> Optional[str]:
    p = shutil.which("ffmpeg")
    if p:
        return p
    workspace_bin = os.path.join(os.getcwd(), "tools", "ffmpeg", "ffmpeg-8.0-essentials_build", "bin", "ffmpeg.exe")
    if os.path.exists(workspace_bin):
        return workspace_bin
    return None


def extract_scene_frame(video_path: str, scene: SceneInfo, output_dir: str) -> FrameInfo | None:
    t = (scene.start_s + scene.end_s) / 2
    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    out_path = os.path.join(frames_dir, f"scene_{scene.id}.jpg")
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        return None
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{t:.3f}",
        "-i",
        video_path,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        out_path,
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return FrameInfo(path=out_path, time_s=t)
    except Exception:
        return None