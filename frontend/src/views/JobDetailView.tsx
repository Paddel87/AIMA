import { useParams } from 'react-router-dom'
import { useJob } from '../hooks/useJobs'
import JobDetailComp from '../components/jobs/JobDetail'

export default function JobDetailView() {
  const { jobId = '' } = useParams()
  const { data, isLoading, error } = useJob(jobId)
  if (isLoading) return <div>Laden...</div>
  if (error) return <div>Fehler</div>
  if (!data) return <div>Keine Daten</div>
  return <JobDetailComp job={data} />
}