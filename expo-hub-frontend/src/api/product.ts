import http from './index'

/** Standard Canton Fair categories served by the backend */
export const EXHIBITION_CATEGORIES = [
  '电子及家电',
  '照明',
  '车辆及配件',
  '五金工具',
  '机械',
  '建材',
  '化工产品',
  '能源',
  '日用消费品',
  '礼品',
  '纺织服装',
  '鞋类',
  '家居装饰品',
  '办公箱包及休闲用品',
  '食品',
  '医药及医疗保健',
  'AI/科技',
  '综合服务',
] as const

export type ExhibitionCategory = (typeof EXHIBITION_CATEGORIES)[number]

/** Category parent group mapping for hierarchical filtering */
export const CATEGORY_PARENT_GROUPS: Record<string, string> = {
  '电子及家电': '电子电器',
  '照明': '电子电器',
  '车辆及配件': '机械装备',
  '五金工具': '机械装备',
  '机械': '机械装备',
  '建材': '建筑装饰',
  '化工产品': '工业原料',
  '能源': '工业原料',
  '日用消费品': '消费品',
  '礼品': '消费品',
  '纺织服装': '纺织鞋服',
  '鞋类': '纺织鞋服',
  '家居装饰品': '建筑装饰',
  '办公箱包及休闲用品': '消费品',
  '食品': '食品医药',
  '医药及医疗保健': '食品医药',
  'AI/科技': '新兴技术',
  '综合服务': '新兴技术',
} as const

export interface ProductItem {
  id: number
  exhibitor_id: number
  exhibitor_username?: string
  booth_id?: number
  exhibition_id?: number
  name: string
  description?: string
  category: string
  images?: string[]
  price?: number
  specs?: Record<string, any>
  status: string
  created_at: string
  updated_at: string
}

export interface CreateProductParams {
  booth_id?: number
  exhibition_id?: number
  name: string
  description?: string
  category: string
  images?: string[]
  price?: number
  specs?: Record<string, any>
  status?: string
}

export interface CategoryResponse {
  categories: string[]
  parent_groups: Record<string, string>
  grouped: Record<string, string[]>
}

import type { ListResp } from './paged'
import { normList } from './paged'

export type Product = ProductItem

export interface ProductListParams {
  category?: string
  exhibition_id?: number
  exhibitor_id?: number
  booth_id?: number
  status?: string
  search?: string
  keyword?: string
  page?: number
  page_size?: number
}

export const productApi = {
  /** Get the full standard category list from the backend */
  getCategories() {
    return http.get('/categories') as Promise<CategoryResponse>
  },

  /** Get parent groups with their subcategories */
  getCategoryGroups() {
    return http.get('/categories/groups') as Promise<{
      groups: Record<string, string[]>
    }>
  },

  async getList(params?: ProductListParams): Promise<ListResp<ProductItem>> {
    const res: any = await http.get('/products', { params })
    return normList<ProductItem>(res)
  },
  getDetail(id: number): Promise<ProductItem> {
    return http.get('/products/' + id) as Promise<ProductItem>
  },
  create(data: CreateProductParams): Promise<ProductItem> {
    return http.post('/products', data) as Promise<ProductItem>
  },
  update(id: number, data: Partial<CreateProductParams>): Promise<ProductItem> {
    return http.put('/products/' + id, data) as Promise<ProductItem>
  },
  delete(id: number): Promise<void> {
    return http.delete('/products/' + id) as Promise<void>
  },
  /** Current exhibitor's own products */
  async getMyProducts(params?: { status?: string; page?: number; page_size?: number }): Promise<ListResp<ProductItem>> {
    const res: any = await http.get('/products/my', { params })
    return normList<ProductItem>(res)
  }
}
