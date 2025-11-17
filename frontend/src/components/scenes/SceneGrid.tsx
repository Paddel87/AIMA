import { SceneSummary } from '../../api/types'
import SceneCard from './SceneCard'

export default function SceneGrid({ items }: { items: SceneSummary[] }) {
  if (!items || items.length === 0) return <div className="subtext">Keine Szenen für diesen Filter.</div>
  return (
    <div className="grid-auto">
      {items.map(s => <SceneCard key={`${s.video_id}:${s.scene_id}`} s={s} />)}
    </div>
  )
}