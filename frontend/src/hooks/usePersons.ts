import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function usePersons() {
  return useQuery({ queryKey: ['persons'], queryFn: api.getPersons })
}

export function usePerson(personId: string) {
  return useQuery({ queryKey: ['person', personId], queryFn: () => api.getPerson(personId) })
}