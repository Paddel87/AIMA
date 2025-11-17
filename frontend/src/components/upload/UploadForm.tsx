import { useState } from 'react'
import { api } from '../../api/client'

export default function UploadForm() {
  const [file, setFile] = useState<File | null>(null)
  const [duration, setDuration] = useState(11)
  const [modules, setModules] = useState('objects,asr')
  const [msg, setMsg] = useState<string>('')
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    fd.append('duration', String(duration))
    fd.append('modules', modules)
    try {
      const res = await api.uploadVideo(fd)
      setMsg(`Upload ok, job_id=${res.job_id} video_id=${res.video_id ?? ''}`)
    } catch (err: any) {
      setMsg(`Fehler: ${err.message}`)
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      <input type="file" onChange={e => setFile(e.target.files?.[0] ?? null)} className="block" />
      <div className="flex items-center gap-3">
        <label className="w-48">Dauer (Sekunden)</label>
        <input type="number" value={duration} onChange={e => setDuration(Number(e.target.value))} className="input w-48" />
      </div>
      <div className="flex items-center gap-3">
        <label className="w-48">Module</label>
        <input type="text" value={modules} onChange={e => setModules(e.target.value)} className="input flex-1" />
      </div>
      <button className="btn">Upload</button>
      {msg && <div className="subtext">{msg}</div>}
    </form>
  )
}