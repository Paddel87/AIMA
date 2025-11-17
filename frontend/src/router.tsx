import { createBrowserRouter } from 'react-router-dom'
import Layout from './components/layout/Layout'
import DashboardView from './views/DashboardView'
import VideosView from './views/VideosView'
import VideoDetailView from './views/VideoDetailView'
import ScenesView from './views/ScenesView'
import SceneDetailView from './views/SceneDetailView'
import PersonsView from './views/PersonsView'
import PersonDetailView from './views/PersonDetailView'
import JobsView from './views/JobsView'
import JobDetailView from './views/JobDetailView'
import UploadView from './views/UploadView'
import SearchView from './views/SearchView'

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <DashboardView /> },
      { path: 'videos', element: <VideosView /> },
      { path: 'videos/:videoId', element: <VideoDetailView /> },
      { path: 'scenes', element: <ScenesView /> },
      { path: 'scenes/:videoId/:sceneId', element: <SceneDetailView /> },
      { path: 'persons', element: <PersonsView /> },
      { path: 'persons/:personId', element: <PersonDetailView /> },
      { path: 'jobs', element: <JobsView /> },
      { path: 'jobs/:jobId', element: <JobDetailView /> },
      { path: 'upload', element: <UploadView /> },
      { path: 'search', element: <SearchView /> }
    ]
  }
])

export default router