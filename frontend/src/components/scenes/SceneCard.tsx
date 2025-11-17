import { Link } from 'react-router-dom'
import { SceneSummary } from '../../api/types'

export default function SceneCard({ s }: { s: SceneSummary }) {
  return (
    <Link to={`/scenes/${s.video_id}/${s.scene_id}`} className="card card-pad" role="button">
      <div className="text-base font-semibold">Szene {s.index} • {s.start_time.toFixed(1)}–{s.end_time.toFixed(1)}s</div>
      <div className="mt-1">
        {s.has_faces ? (
          <span className="badge">Faces {s.num_faces}</span>
        ) : (
          <span className="badge">Keine Faces</span>
        )}
      </div>
      {s.text_excerpt && <div className="mt-2 text-sm text-neutral-700">{s.text_excerpt}</div>}
    </Link>
  )
}