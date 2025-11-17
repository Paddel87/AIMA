import { Link } from 'react-router-dom'
import { VideoSummary } from '../../api/types'

export default function VideoCard({ v }: { v: VideoSummary }) {
  return (
    <Link to={`/videos/${v.video_id}`} className="card card-pad" role="button">
      <div className="text-base font-semibold">{v.title}</div>
      <div className="subtext">Szenen: {v.num_scenes}{v.num_persons != null ? ` • Personen: ${v.num_persons}` : ''}</div>
    </Link>
  )
}