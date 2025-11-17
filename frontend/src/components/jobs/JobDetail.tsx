import { JobSummary } from '../../api/types'

export default function JobDetailComp({ job }: { job: JobSummary }) {
  return (
    <div className="space-y-2">
      <div className="text-lg font-semibold">Job {job.job_id}</div>
      <div>Status: {job.status}</div>
      <div>Video: {job.video_id ?? '-'}</div>
      <div>Erstellt: {job.created_at}</div>
      <div>Fertig: {job.finished_at ?? '-'}</div>
    </div>
  )
}