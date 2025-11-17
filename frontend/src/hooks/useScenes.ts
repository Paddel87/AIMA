import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function useScenes(params: { videoId?: string; personId?: string; limit?: number; offset?: number }) {
  return useQuery({ queryKey: ['scenes', params], queryFn: () => api.getScenes(params) })
}

export function useScene(sceneId: string) {
  return useQuery({ queryKey: ['scene', sceneId], queryFn: () => api.getScene(sceneId) })
}