from pydantic import BaseModel


class SourceInfo(BaseModel):
    path: str
    duration_s: float


class SceneInfo(BaseModel):
    id: int
    start_s: float
    end_s: float


class FrameInfo(BaseModel):
    path: str
    time_s: float


class AudioSegment(BaseModel):
    start_s: float
    end_s: float
    text: str


class DetectedObject(BaseModel):
    class_name: str
    confidence: float
    bbox: list[float]


class ModelStatus(BaseModel):
    name: str
    status: str
    error: str | None = None


class SceneAnalysis(BaseModel):
    source: SourceInfo
    scene: SceneInfo
    frames: list[FrameInfo]
    audio: list[AudioSegment]
    objects: list[DetectedObject]
    models: list[ModelStatus]
    tags: list[str] = []