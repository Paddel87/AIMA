import { Link } from 'react-router-dom'

export default function DashboardView() {
  return (
    <div className="page">
      <div className="page-title">AIMA Dashboard</div>
      <div className="grid-auto">
        <Link to="/videos" className="card card-pad">Videos</Link>
        <Link to="/persons" className="card card-pad">Personen</Link>
        <Link to="/scenes" className="card card-pad">Szenen</Link>
        <Link to="/search" className="card card-pad">Suche</Link>
        <Link to="/upload" className="card card-pad">Upload</Link>
        <Link to="/jobs" className="card card-pad">Jobs</Link>
      </div>
    </div>
  )
}