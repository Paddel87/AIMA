from pydantic import BaseModel


class SourceInfo(BaseModel):
    path: str
    duration_s: float


class SceneInfo(BaseModel):
    id: int
    start_s: float
    end_s: float
    video_id: str


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


class OcrBlock(BaseModel):
    text: str
    confidence: float
    bbox: list[int]


class FaceInstance(BaseModel):
    face_id: str
    bbox: list[int]
    confidence: float | None = None
    embedding: list[float]


class SceneAnalysis(BaseModel):
    source: SourceInfo
    scene: SceneInfo
    frames: list[FrameInfo]
    audio: list[AudioSegment]
    objects: list[DetectedObject]
    models: list[ModelStatus]
    tags: list[str] = []
    video_id: str
    ocr_text: str | None = None
    ocr_blocks: list[OcrBlock] | None = None
    faces: list[FaceInstance] | None = None


class UploadResponse(BaseModel):
    message: str
    video_id: str
    stored_path: str
    original_filename: str
    mime_type: str
    size_bytes: int


class JobAnalyzeRequest(BaseModel):
    video_id: str | None = None
    video_path: str | None = None
    duration: float
    modules: list[str] = ["objects", "asr"]


class JobCreateResponse(BaseModel):
    message: str
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    video_id: str | None = None
    output_dir: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str