import { useQuery } from '@tanstack/react-query'

import { getJson } from './client'

export interface Health {
  status: string
}

export function useHealth() {
  return useQuery({ queryKey: ['health'], queryFn: () => getJson<Health>('/health') })
}
