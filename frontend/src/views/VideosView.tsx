import { useVideos } from '../hooks/useVideos'
import VideoGrid from '../components/videos/VideoGrid'

export default function VideosView() {
  const { data, isLoading, error } = useVideos()
  if (isLoading) return <div className="text-neutral-600">Laden…</div>
  if (error) return <div className="text-red-600">Fehler beim Laden der Daten. Bitte später erneut versuchen.</div>
  return <VideoGrid items={data ?? []} />
}