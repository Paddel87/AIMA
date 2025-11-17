from typing import List
from aima import config
from .detector import detect_faces, FaceBox
from .encoder import encode_faces, FaceEmbedding


def analyze_scene_frame(image) -> List[FaceEmbedding]:
    boxes: List[FaceBox] = detect_faces(image)
    if not boxes:
        return []
    max_n = int(config.FACES_MAX_PER_SCENE)
    boxes = boxes[:max_n]
    embeddings: List[FaceEmbedding] = encode_faces(image, boxes)
    return embeddings