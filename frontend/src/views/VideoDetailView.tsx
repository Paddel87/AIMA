import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import SceneGrid from '../components/scenes/SceneGrid'

export default function VideoDetailView() {
  const { videoId = '' } = useParams()
  const { data, isLoading, error } = useQuery({ queryKey: ['video', videoId], queryFn: () => api.getVideo(videoId) })
  if (isLoading) return <div className="text-neutral-600">Laden…</div>
  if (error) return <div className="text-red-600">Fehler beim Laden der Daten. Bitte später erneut versuchen.</div>
  const scenes = data?.scenes ?? []
  return (
    <div className="page">
      <div>
        <div className="page-title">Video {data?.video?.title}</div>
        <div className="subtext">Szenen: {scenes.length}</div>
      </div>
      <SceneGrid items={scenes} />
    </div>
  )
}