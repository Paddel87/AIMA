from typing import List
from pydantic import BaseModel
import torch
from facenet_pytorch import MTCNN
from aima import config


class FaceBox(BaseModel):
    bbox: list[int]
    confidence: float


_mtcnn: MTCNN | None = None


def _get_mtcnn() -> MTCNN:
    global _mtcnn
    if _mtcnn is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _mtcnn = MTCNN(keep_all=True, device=device)
    return _mtcnn


def detect_faces(image) -> List[FaceBox]:
    mtcnn = _get_mtcnn()
    boxes, probs = mtcnn.detect(image)
    results: List[FaceBox] = []
    if boxes is None or probs is None:
        return results
    for i in range(len(probs)):
        conf = float(probs[i])
        if conf < float(config.FACES_MIN_CONFIDENCE):
            continue
        b = boxes[i]
        x1, y1, x2, y2 = int(b[0]), int(b[1]), int(b[2]), int(b[3])
        results.append(FaceBox(bbox=[x1, y1, x2, y2], confidence=conf))
    results.sort(key=lambda f: f.confidence, reverse=True)
    if len(results) > int(config.FACES_MAX_PER_SCENE):
        results = results[: int(config.FACES_MAX_PER_SCENE)]
    return results