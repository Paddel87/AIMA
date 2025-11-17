import { usePersons } from '../hooks/usePersons'
import PersonGrid from '../components/persons/PersonGrid'

export default function PersonsView() {
  const { data, isLoading, error } = usePersons()
  if (isLoading) return <div className="text-neutral-600">Laden…</div>
  if (error) return <div className="text-red-600">Fehler beim Laden der Daten. Bitte später erneut versuchen.</div>
  return (
    <div className="page">
      <div className="page-title">Personen</div>
      <PersonGrid items={data ?? []} />
    </div>
  )
}