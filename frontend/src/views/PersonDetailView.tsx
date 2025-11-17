import { useParams } from 'react-router-dom'
import { usePerson } from '../hooks/usePersons'
import VideoGrid from '../components/videos/VideoGrid'
import SceneGrid from '../components/scenes/SceneGrid'

export default function PersonDetailView() {
  const { personId = '' } = useParams()
  const { data, isLoading, error } = usePerson(personId)
  if (isLoading) return <div className="text-neutral-600">Laden…</div>
  if (error) return <div className="text-red-600">Fehler beim Laden der Daten. Bitte später erneut versuchen.</div>
  if (!data) return <div className="text-neutral-600">Keine Daten</div>
  return (
    <div className="page">
      <div>
        <div className="page-title">Person {data.person.person_id}</div>
        <div className="subtext">Szenen {data.person.num_scenes} • Videos {data.person.num_videos}</div>
      </div>
      <div>
        <div className="text-base font-semibold mb-2">Szenen</div>
        <SceneGrid items={data.scenes} />
      </div>
      <div>
        <div className="text-base font-semibold mb-2">Videos</div>
        <VideoGrid items={data.videos} />
      </div>
    </div>
  )
}