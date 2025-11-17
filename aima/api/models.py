from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class VideoSummaryResponse(BaseModel):
    video_id: str
    title: str
    duration: float | None = None
    num_scenes: int
    num_persons: int | None = None
    created_at: datetime | None = None


class SceneSummaryResponse(BaseModel):
    scene_id: str
    video_id: str
    index: int
    start_time: float
    end_time: float
    has_faces: bool
    num_faces: int
    persons: List[str] | None = None
    text_excerpt: str | None = None


class FaceResponse(BaseModel):
    face_id: str
    bbox: List[int]
    confidence: float | None = None
    person_id: str | None = None


class SceneDetailResponse(BaseModel):
    scene: SceneSummaryResponse
    asr_text: str | None
    ocr_text: str | None
    objects: List[str] | None
    faces: List[FaceResponse] | None


class VideoDetailResponse(BaseModel):
    video: VideoSummaryResponse
    scenes: List[SceneSummaryResponse]


class PersonSummaryResponse(BaseModel):
    person_id: str
    display_name: str | None = None
    num_faces: int
    num_scenes: int
    num_videos: int


class PersonDetailResponse(BaseModel):
    person: PersonSummaryResponse
    scenes: List[SceneSummaryResponse]
    videos: List[VideoSummaryResponse]


class SearchResultSceneResponse(BaseModel):
    scene_id: str
    video_id: str
    score: float
    start_time: float
    end_time: float
    text_excerpt: str | None


class JobSummaryResponse(BaseModel):
    job_id: str
    video_id: str | None
    video_path: str | None = None
    status: str
    created_at: datetime
    finished_at: datetime | None


class UploadResponse(BaseModel):
    job_id: str
    video_id: str | None
    message: str