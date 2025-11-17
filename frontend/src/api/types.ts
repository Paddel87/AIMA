export type VideoSummary = {
  video_id: string
  title: string
  duration?: number | null
  num_scenes: number
  num_persons?: number | null
  created_at?: string | null
}

export type SceneSummary = {
  scene_id: string
  video_id: string
  index: number
  start_time: number
  end_time: number
  has_faces: boolean
  num_faces: number
  persons?: string[] | null
  text_excerpt?: string | null
}

export type Face = {
  face_id: string
  bbox: number[]
  confidence?: number | null
  person_id?: string | null
}

export type SceneDetail = {
  scene: SceneSummary
  asr_text?: string | null
  ocr_text?: string | null
  objects?: string[] | null
  faces?: Face[] | null
}

export type VideoDetail = {
  video: VideoSummary
  scenes: SceneSummary[]
}

export type PersonSummary = {
  person_id: string
  display_name?: string | null
  num_faces: number
  num_scenes: number
  num_videos: number
}

export type PersonDetail = {
  person: PersonSummary
  scenes: SceneSummary[]
  videos: VideoSummary[]
}

export type SearchResultScene = {
  scene_id: string
  video_id: string
  score: number
  start_time: number
  end_time: number
  text_excerpt?: string | null
}

export type JobSummary = {
  job_id: string
  video_id?: string | null
  video_path?: string | null
  status: string
  created_at: string
  finished_at?: string | null
}

export type UploadResponse = {
  job_id: string
  video_id?: string | null
  message: string
}