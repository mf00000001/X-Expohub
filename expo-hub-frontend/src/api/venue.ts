import apiClient from './client'

export interface Venue {
  id: number
  name: string
  city: string
  address: string
  area?: number | null
  important_info?: string
  honors?: string[]
  created_at?: string
}

const safe = <T>(p: Promise<T>, fb: T): Promise<T> => p.catch(() => fb)

export const venueApi = {
  getList(params?: { city?: string; q?: string }) {
    return safe(apiClient.get('/venues', { params }), { list: [], total: 0 }) as Promise<{ list: Venue[]; total: number }>
  },
  getDetail(id: number) {
    return safe(apiClient.get('/venues/' + id), null) as Promise<Venue | null>
  },
}
