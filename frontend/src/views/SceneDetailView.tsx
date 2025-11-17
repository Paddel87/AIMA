import { useParams } from 'react-router-dom'
import { useScene } from '../hooks/useScenes'
import SceneDetailComp from '../components/scenes/SceneDetail'

export default function SceneDetailView() {
  const { sceneId = '', videoId = '' } = useParams()
  const { data, isLoading, error } = useScene(sceneId)
  if (isLoading) return <div className="text-neutral-600">Laden…</div>
  if (error) return <div className="text-red-600">Fehler beim Laden der Daten. Bitte später erneut versuchen.</div>
  if (!data) return <div className="text-neutral-600">Keine Daten</div>
  return (
    <div className="page">
      <div className="subtext">Video {videoId} • Szene {sceneId}</div>
      <SceneDetailComp d={data} />
    </div>
  )
}