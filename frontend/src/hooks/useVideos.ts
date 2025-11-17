import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function useVideos() {
  return useQuery({ queryKey: ['videos'], queryFn: api.getVideos })
}