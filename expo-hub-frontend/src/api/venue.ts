import apiClient from './client'

export interface Venue {
  id: number
  name: string
  city: string
  address: string
  area?: number | null
  important_info?: string
  honors?: string[]
  plan_image?: string
  image_url?: string
  cover_image?: string
  created_at?: string
}

const safe = <T>(p: Promise<T>, fb: T): Promise<T> => p.catch(() => fb)

export const venueApi = {
  getList(params?: { city?: string; q?: string; page?: number; page_size?: number }) {
    return safe(apiClient.get('/venues', { params }), { list: [], total: 0 }) as Promise<{ list: Venue[]; total: number }>
  },
  getDetail(id: number) {
    return safe(apiClient.get('/venues/' + id), null) as Promise<Venue | null>
  },
  create(data: Partial<Venue>) { return apiClient.post('/venues', data) as Promise<Venue> },
  update(id: number, data: Partial<Venue>) { return apiClient.put('/venues/' + id, data) as Promise<Venue> },
  remove(id: number) { return apiClient.delete('/venues/' + id).catch(() => {}) as Promise<void> },
}
