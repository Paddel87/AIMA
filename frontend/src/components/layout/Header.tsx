import { Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'

export default function Header({ onBurger }: { onBurger?: () => void }) {
  const [q, setQ] = useState('')
  const nav = useNavigate()
  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    nav(`/search?q=${encodeURIComponent(q)}`)
  }
  return (
    <header className="header">
      <div className="flex items-center gap-2">
        <button className="md:hidden inline-flex items-center justify-center w-10 h-10 rounded-md border border-neutral-300" onClick={onBurger} aria-label="Menü">
          <span className="w-5 h-0.5 bg-neutral-800 block mb-1"></span>
          <span className="w-5 h-0.5 bg-neutral-800 block mb-1"></span>
          <span className="w-5 h-0.5 bg-neutral-800 block"></span>
        </button>
        <Link to="/" className="text-xl font-semibold">AIMA</Link>
      </div>
      <form onSubmit={onSubmit} className="flex-1 mx-4 flex gap-2">
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="Suche..." className="input flex-1" />
        <button className="btn">Suche</button>
      </form>
    </header>
  )
}