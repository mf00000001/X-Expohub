import http from './index'
import type { ListResp } from './paged'
import { normList } from './paged'

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
  size?: string
  location_area?: string
  company_name?: string
  exhibitor_name?: string
  status: string
  created_at: string
  updated_at: string
}

export interface CreateBoothParams {
  exhibition_id: number
  booth_number?: string
  name?: string
  description?: string
  area?: number
  price?: number
  floor?: number
  zone?: string
  size?: string
  location_area?: string
  company_name?: string
  status?: string
}

export interface BoothListParams {
  exhibition_id?: number
  zone?: string
  status?: string
  page?: number
  page_size?: number
}

export const boothApi = {
  async getList(params?: BoothListParams): Promise<ListResp<BoothItem>> {
    const res: any = await http.get('/booths', { params })
    return normList<BoothItem>(res)
  },
  async getMyBooths(params?: { page?: number; page_size?: number; status?: string }): Promise<ListResp<BoothItem>> {
    const res: any = await http.get('/booths/my', { params })
    return normList<BoothItem>(res)
  },
  getDetail(id: number): Promise<BoothItem> {
    return http.get(`/booths/${id}`) as Promise<BoothItem>
  },
  book(boothId: number): Promise<BoothItem> {
    return http.post('/booths/book', { booth_id: boothId }) as Promise<BoothItem>
  },
  apply(boothId: number): Promise<any> {
    return http.post(`/booths/${boothId}/apply`) as Promise<any>
  },
  // 主办方接口
  create(data: CreateBoothParams): Promise<BoothItem> {
    return http.post('/booths', data) as Promise<BoothItem>
  },
  update(id: number, data: Partial<CreateBoothParams>): Promise<BoothItem> {
    return http.put(`/booths/${id}`, data) as Promise<BoothItem>
  },
  assign(boothId: number, exhibitorId: number): Promise<BoothItem> {
    return http.post(`/booths/${boothId}/assign`, { exhibitor_id: exhibitorId }) as Promise<BoothItem>
  }
}

export type Booth = BoothItem
