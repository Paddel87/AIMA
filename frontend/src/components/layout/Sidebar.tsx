import { Link, NavLink } from 'react-router-dom'

export default function Sidebar({ open, onClose }: { open?: boolean; onClose?: () => void }) {
  const item = (to: string, label: string) => (
    <NavLink to={to} className={({ isActive }) => `block px-4 py-2 rounded ${isActive ? 'bg-blue-600 text-white' : 'hover:bg-gray-200'}`}>
      {label}
    </NavLink>
  )
  return (
    <>
      <aside className="sidebar-panel hidden md:flex">
        <Link to="/" className="block text-xl font-semibold mb-4">AIMA</Link>
        <nav className="space-y-1">
          {item('/', 'Dashboard')}
          {item('/videos', 'Videos')}
          {item('/persons', 'Personen')}
          {item('/scenes', 'Szenen')}
          {item('/search', 'Suche')}
          {item('/upload', 'Upload')}
          {item('/jobs', 'Jobs')}
        </nav>
      </aside>
      {open && (
        <div className="overlay">
          <div className="overlay-bg" onClick={onClose}></div>
          <div className="overlay-menu">
            <nav className="space-y-1">
              {item('/', 'Dashboard')}
              {item('/videos', 'Videos')}
              {item('/persons', 'Personen')}
              {item('/scenes', 'Szenen')}
              {item('/search', 'Suche')}
              {item('/upload', 'Upload')}
              {item('/jobs', 'Jobs')}
            </nav>
          </div>
        </div>
      )}
    </>
  )
}