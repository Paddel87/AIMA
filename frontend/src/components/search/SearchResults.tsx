import { Link } from 'react-router-dom'
import { SearchResultScene } from '../../api/types'

export default function SearchResults({ items }: { items: SearchResultScene[] }) {
  const filtered = items.filter(i => i.video_id && i.video_id.length > 0)
  if (filtered.length === 0) return <div className="subtext">Keine gültigen Treffer (ohne Video-ID werden Treffer verworfen).</div>
  return (
    <div className="space-y-3">
      {filtered.map(r => (
        <Link key={`${r.video_id}:${r.scene_id}:${r.score}`} to={`/scenes/${r.video_id}/${r.scene_id}`} className="card card-pad" role="button">
          <div className="text-base font-semibold">{r.video_id} • Szene {r.scene_id} • Score {r.score.toFixed(3)}</div>
          {r.text_excerpt && <div className="text-sm mt-1 text-neutral-700">{r.text_excerpt}</div>}
        </Link>
      ))}
    </div>
  )
}