from typing import List
from pydantic import BaseModel
import torch
from facenet_pytorch import InceptionResnetV1
from torchvision import transforms

from .detector import FaceBox


class FaceEmbedding(BaseModel):
    bbox: list[int]
    confidence: float
    embedding: list[float]


_resnet: InceptionResnetV1 | None = None


def _get_resnet() -> InceptionResnetV1:
    global _resnet
    if _resnet is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _resnet = InceptionResnetV1(pretrained="vggface2").eval().to(device)
    return _resnet


_preprocess = transforms.Compose(
    [
        transforms.Resize((160, 160)),
        transforms.ToTensor(),
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
    ]
)


def encode_faces(image, face_boxes: List[FaceBox]) -> List[FaceEmbedding]:
    model = _get_resnet()
    device = next(model.parameters()).device
    embeddings: List[FaceEmbedding] = []
    for fb in face_boxes:
        x1, y1, x2, y2 = fb.bbox
        crop = image.crop((x1, y1, x2, y2))
        tensor = _preprocess(crop).unsqueeze(0).to(device)
        with torch.no_grad():
            vec = model(tensor)
        emb = vec.detach().cpu().numpy().flatten().tolist()
        embeddings.append(
            FaceEmbedding(bbox=fb.bbox, confidence=fb.confidence, embedding=emb)
        )
    return embeddings