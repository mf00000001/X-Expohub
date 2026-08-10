import http from './index'

export interface BoothItem {
  id: number
  exhibition_id: number
  exhibitor_id?: number
  booth_number: string
  name?: string
  description?: string
  area?: number
  price?: number
  floor?: number
  zone?: string
  status: string
  created_at: string
  updated_at: string
}

export interface CreateBoothParams {
  exhibition_id: number
  booth_number: string
  name?: string
  description?: string
  area?: number
  price?: number
  floor?: number
  zone?: string
}

export const boothApi = {
  getList(params?: { exhibition_id?: number; zone?: string; status?: string }): Promise<BoothItem[]> {
    return http.get('/booths', { params })
  },
  getMyBooths(): Promise<BoothItem[]> {
    return http.get('/booths/my')
  },
  getDetail(id: number): Promise<BoothItem> {
    return http.get(`/booths/${id}`)
  },
  book(boothId: number): Promise<BoothItem> {
    return http.post('/booths/book', { booth_id: boothId })
  },
  apply(boothId: number): Promise<any> {
    return http.post(`/booths/${boothId}/apply`)
  },
  // 主办方接口
  create(data: CreateBoothParams): Promise<BoothItem> {
    return http.post('/booths', data)
  },
  update(id: number, data: Partial<CreateBoothParams>): Promise<BoothItem> {
    return http.put(`/booths/${id}`, data)
  },
  assign(boothId: number, exhibitorId: number): Promise<BoothItem> {
    return http.post(`/booths/${boothId}/assign`, { exhibitor_id: exhibitorId })
  }
}
