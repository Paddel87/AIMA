import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import { useState } from 'react'

export default function Layout() {
  const [open, setOpen] = useState(false)
  return (
    <div className="min-h-screen flex bg-neutral-50">
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <main className="flex-1 flex flex-col">
        <Header onBurger={() => setOpen(true)} />
        <div className="container p-6 page">
          <Outlet />
        </div>
      </main>
    </div>
  )
}