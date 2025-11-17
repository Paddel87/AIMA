import { useJobs } from '../hooks/useJobs'
import JobList from '../components/jobs/JobList'

export default function JobsView() {
  const { data, isLoading, error } = useJobs()
  if (isLoading) return <div className="text-neutral-600">Laden…</div>
  if (error) return <div className="text-red-600">Fehler beim Laden der Daten. Bitte später erneut versuchen.</div>
  return (
    <div className="page">
      <div className="page-title">Jobs</div>
      <JobList items={data ?? []} />
    </div>
  )
}