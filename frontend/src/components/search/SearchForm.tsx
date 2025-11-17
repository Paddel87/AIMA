import { useState } from 'react'

export default function SearchForm({ onSearch }: { onSearch: (q: string) => void }) {
  const [q, setQ] = useState('')
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSearch(q) }} className="flex gap-2">
      <input value={q} onChange={e => setQ(e.target.value)} placeholder="Query" className="border px-3 py-2 rounded flex-1" />
      <button className="px-4 py-2 bg-blue-600 text-white rounded">Suchen</button>
    </form>
  )
}