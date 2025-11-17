import { VideoSummary } from '../../api/types'
import VideoCard from './VideoCard'

export default function VideoGrid({ items }: { items: VideoSummary[] }) {
  if (!items || items.length === 0) return <div className="subtext">Noch keine Videos analysiert.</div>
  return (
    <div className="grid-auto">
      {items.map(v => <VideoCard key={v.video_id} v={v} />)}
    </div>
  )
}