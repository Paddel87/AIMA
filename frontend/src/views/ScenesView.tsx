import { useSearchParams } from 'react-router-dom'
import { useScenes } from '../hooks/useScenes'
import SceneGrid from '../components/scenes/SceneGrid'

export default function ScenesView() {
  const [sp] = useSearchParams()
  const videoId = sp.get('videoId') ?? undefined
  const personId = sp.get('personId') ?? undefined
  const { data, isLoading, error } = useScenes({ videoId, personId, limit: 50, offset: 0 })
  if (isLoading) return <div className="text-neutral-600">Laden…</div>
  if (error) return <div className="text-red-600">Fehler beim Laden der Daten. Bitte später erneut versuchen.</div>
  return (
    <div className="page">
      <div className="page-title">Szenen</div>
      <SceneGrid items={data ?? []} />
    </div>
  )
}