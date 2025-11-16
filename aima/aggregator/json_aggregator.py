import json
import os

from aima.schemas.models import SceneAnalysis


def write_scene_analysis(output_path: str, analysis: SceneAnalysis) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis.model_dump(), f, ensure_ascii=False, indent=2)