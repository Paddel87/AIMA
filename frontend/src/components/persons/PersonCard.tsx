import { Link } from 'react-router-dom'
import { PersonSummary } from '../../api/types'

export default function PersonCard({ p }: { p: PersonSummary }) {
  return (
    <Link to={`/persons/${p.person_id}`} className="card card-pad" role="button">
      <div className="text-base font-semibold">{p.person_id}</div>
      <div className="mt-1 subtext">Szenen {p.num_scenes} • Videos {p.num_videos}</div>
    </Link>
  )
}