const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`)
  if (!r.ok) throw new Error(`GET ${path} ${r.status}`)
  return r.json()
}

async function post<T>(path: string, body: any): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!r.ok) throw new Error(`POST ${path} ${r.status}`)
  return r.json()
}

export const api = {
  getVideos: () => get<any>('/videos'),
  getVideo: (videoId: string) => get<any>(`/videos/${videoId}`),
  getScenes: (params: { videoId?: string; personId?: string; limit?: number; offset?: number }) => {
    const p = new URLSearchParams()
    if (params.videoId) p.set('video_id', params.videoId)
    if (params.personId) p.set('person_id', params.personId)
    p.set('limit', String(params.limit ?? 50))
    p.set('offset', String(params.offset ?? 0))
    return get<any>(`/scenes?${p.toString()}`)
  },
  getScene: (sceneId: string) => get<any>(`/scenes/${sceneId}`),
  getPersons: () => get<any>('/persons'),
  getPerson: (personId: string) => get<any>(`/persons/${personId}`),
  searchScenes: (query: string, topK = 10) => post<any>('/search/scenes', { query, top_k: topK }),
  getJobs: () => get<any>('/jobs'),
  getJob: (jobId: string) => get<any>(`/jobs/${jobId}`),
  uploadVideo: async (formData: FormData) => {
    const r = await fetch(`${API}/upload/video`, { method: 'POST', body: formData })
    if (!r.ok) throw new Error(`upload ${r.status}`)
    return r.json()
  }
}