import { JobSummary } from '../../api/types'

export default function JobList({ items }: { items: JobSummary[] }) {
  if (!items || items.length === 0) return <div className="subtext">Keine Jobs vorhanden.</div>
  return (
    <table className="w-full border border-neutral-200 rounded-xl overflow-hidden bg-white">
      <thead>
        <tr className="bg-neutral-100">
          <th className="p-4 text-left">Job</th>
          <th className="p-4 text-left">Status</th>
          <th className="p-4 text-left">Video</th>
          <th className="p-4 text-left">Erstellt</th>
        </tr>
      </thead>
      <tbody>
        {items.map(j => (
          <tr key={j.job_id} className="border-t border-neutral-200">
            <td className="p-4">{j.job_id}</td>
            <td className="p-4">{j.status}</td>
            <td className="p-4">{j.video_id ?? '-'}</td>
            <td className="p-4">{j.created_at}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}