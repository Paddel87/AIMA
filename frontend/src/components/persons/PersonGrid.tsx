import { PersonSummary } from '../../api/types'
import PersonCard from './PersonCard'

export default function PersonGrid({ items }: { items: PersonSummary[] }) {
  if (!items || items.length === 0) return <div className="subtext">Keine Personen gefunden. Führe zuerst Personen-Clustering aus.</div>
  return (
    <div className="grid-auto">
      {items.map(p => <PersonCard key={p.person_id} p={p} />)}
    </div>
  )
}