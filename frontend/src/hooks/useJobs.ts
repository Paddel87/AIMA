import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function useJobs() {
  return useQuery({ queryKey: ['jobs'], queryFn: api.getJobs })
}

export function useJob(jobId: string) {
  return useQuery({ queryKey: ['job', jobId], queryFn: () => api.getJob(jobId) })
}