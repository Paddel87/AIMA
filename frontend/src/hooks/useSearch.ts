import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'

export function useSearchScenes() {
  return useMutation({ mutationFn: ({ q, topK }: { q: string; topK?: number }) => api.searchScenes(q, topK) })
}