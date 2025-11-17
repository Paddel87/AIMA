import { useSearchParams } from 'react-router-dom'
import SearchForm from '../components/search/SearchForm'
import SearchResults from '../components/search/SearchResults'
import { useSearchScenes } from '../hooks/useSearch'

export default function SearchView() {
  const [sp, setSp] = useSearchParams()
  const q = sp.get('q') || ''
  const { mutateAsync, data, isPending } = useSearchScenes()

  const doSearch = async (query: string) => {
    setSp({ q: query })
    await mutateAsync({ q: query, topK: 10 })
  }

  return (
    <div className="page">
      <div className="page-title">Suche</div>
      <SearchForm onSearch={doSearch} />
      {isPending && <div className="text-neutral-600">Laden…</div>}
      {Array.isArray(data) && <SearchResults items={data} />}
    </div>
  )
}