import apiClient from './client'
import type { ListResp } from './paged'
import { normList } from './paged'

export interface Exhibition {
  id: number; title: string; name?: string; description: string
  cover_image?: string; cover_url?: string; cover_image_url?: string
  start_date: string; end_date: string; location: string; venue?: string
  status: string; total_booths: number; organizer_id: number; organizer_name?: string
  visitor_count?: number
  startDate?: string
  endDate?: string
  category?: string
  venue_id?: number | null
  created_at: string; updated_at: string
}

/**
 * 全球标杆展会条目（GET /exhibitions/hall-of-fame）
 *
 * 后端最多返回 10 条，返回顺序即首页展示顺序（前端不再排序、不再增删）。
 */
export interface HallOfFameItem {
  id: number
  /** 全称（用于 title 悬浮提示，卡片主标题优先用 short_name） */
  name: string
  /** 短名/展馆名（首页卡片主标题，避免全名过长折行） */
  short_name?: string
  /** 城市 */
  city?: string
  /** 国家/地区 */
  country?: string
  /** 一句话卖点（由后端维护，前端原样展示，不改写不补造） */
  tagline?: string
  /** 所属行业 */
  sector?: string
  /** 届次（原样展示，前端不推断「第几届」格式） */
  edition?: string
}

export type ExhibitionItem = Exhibition

/**
 * 展会真实聚合（GET /exhibitions/{id}/stats）
 *
 * 数字全部来自名录快照的真实计数：展商 = catalog_exhibitors 命中行数，
 * 展品 = 经展商反查 catalog_products 的命中行数，城市 / 行业 = distinct。
 * 接口失败时 getStats 返回 null，页面隐藏统计条而不是显示 0（不编造）。
 */
export interface ExhibitionStats {
  exhibitors: number
  products: number
  cities: number
  industries: number
}

/**
 * 展会参展展商（GET /exhibitions/{id}/exhibitors）
 *
 * 名录口径返回 name/industry/city/product_count；名录无数据时后端回落到
 * 展位口径（company/industry_domain/region/products_count），两种形状都兼容。
 */
export interface ExhibitionExhibitorItem {
  exhibitor_id?: number
  name?: string
  industry?: string
  city?: string
  product_count?: number
  /** 占用展位口径（回落数据才有） */
  company?: string
  industry_domain?: string
  region?: string
  products_count?: number
  source?: 'catalog' | 'booth'
}

/** 展会名录展品（GET /exhibitions/{id}/products） */
export interface ExhibitionProductItem {
  id: number
  name: string
  category?: string
  /** 名录图（多数为空串，页面用 ExpoCover 兜底） */
  image?: string
  exhibitor_name?: string
  source?: 'catalog' | 'products'
}

export interface ExhibitionCreatePayload {
  title: string
  description?: string
  cover_image?: string
  start_date: string
  end_date: string
  location: string
  total_booths?: number
  category?: string
  venue_id?: number | null
  status?: string
}
export type ExhibitionUpdatePayload = Partial<ExhibitionCreatePayload> & { status?: string }
const safe = <T>(p: Promise<T>, fb: T): Promise<T> => p.catch(() => fb)
export const exhibitionApi = {
  async getList(params?: any): Promise<ListResp<Exhibition>> { return normList<Exhibition>(await apiClient.get('/exhibitions',{params})) },
  async getMyExhibitions(oid:number,params?:any): Promise<ListResp<Exhibition>> { return normList<Exhibition>(await apiClient.get('/exhibitions',{params:{organizer_id:oid,...params}})) },
  getDetail(id:number) { return safe(apiClient.get('/exhibitions/'+id),null) as Promise<Exhibition|null> },
  create(p:ExhibitionCreatePayload) { return apiClient.post('/exhibitions',p) as Promise<Exhibition> },
  update(id:number,p:ExhibitionUpdatePayload) { return apiClient.put('/exhibitions/'+id,p) as Promise<Exhibition> },
  delete(id:number) { return apiClient.delete('/exhibitions/'+id).catch(()=>{}) as Promise<void> },
  remove(id:number) { return this.delete(id) },
  publish(id:number) { return apiClient.post('/exhibitions/'+id+'/publish') as Promise<Exhibition> },
  // V2.0: 首页精选 & 热门
  getFeatured(limit?:number) { return safe(apiClient.get('/exhibitions/featured',{params:{limit:limit||5}}),[]) as Promise<Exhibition[]> },
  getHot(limit?:number) { return safe(apiClient.get('/exhibitions/hot',{params:{limit:limit||10}}),[]) as Promise<Exhibition[]> },
  // 后端 /exhibitions/upcoming 只接受 limit（校验范围 1~100，不支持 page/page_size），
  // 所以首页「重磅发布」一次取满 100 条，再由前端切片做「查看更多」，不重复请求。
  getUpcoming(limit?:number) { return safe(apiClient.get('/exhibitions/upcoming',{params:{limit:limit||100}}),[]) as Promise<Exhibition[]> },
  /**
   * 全球标杆展会（首页长期展示位，≤10 条，顺序即展示顺序）。
   *
   * 契约：GET /exhibitions/hall-of-fame →
   *   { success, code, message, data: { list: [{id,name,short_name,city,country,tagline,sector,edition}], total } }
   * client 的响应拦截器已解包 { success, data } 信封，这里拿到的可能是
   * { list, total }，也可能（后端直接给数组时）是裸数组，两种都兼容。
   * 接口未上线 / 请求失败 / 空数据一律返回 []，由页面把整块隐藏（不留空白、不编造条目）。
   */
  async getHallOfFame(): Promise<HallOfFameItem[]> {
    const raw = await safe<any>(apiClient.get('/exhibitions/hall-of-fame'), null)
    const list = Array.isArray(raw) ? raw : (raw?.list ?? raw?.data?.list ?? [])
    if (!Array.isArray(list)) return []
    return (list as HallOfFameItem[])
      .filter((it) => !!it && typeof it === 'object')
      .slice(0, 10)
  },
  smartSearch(q:string) { return apiClient.get('/exhibitions/search/smart',{params:{q}}) as Promise<any> },
  /**
   * 展会真实聚合（详情页顶部统计条）。
   *
   * 契约：GET /exhibitions/{id}/stats → { exhibitors, products, cities, industries }
   * 失败返回 null（页面隐藏统计条，绝不显示编造的数字）。
   */
  getStats(id:number) { return safe<any>(apiClient.get('/exhibitions/'+id+'/stats'), null) as Promise<ExhibitionStats|null> },
  /**
   * 展会参展展商名单（名录优先，后端回落到展位口径）。
   *
   * 契约：GET /exhibitions/{id}/exhibitors?page&page_size →
   *   { list: [{ name, industry, city, product_count, ... }], total, page, pageSize, totalPages }
   */
  async getExhibitors(id:number, params?:any): Promise<ListResp<ExhibitionExhibitorItem>> {
    return normList<ExhibitionExhibitorItem>(await safe<any>(apiClient.get('/exhibitions/'+id+'/exhibitors',{params}), {}))
  },
  /**
   * 展会名录展品（详情页「展品」区块，分页）。
   *
   * 契约：GET /exhibitions/{id}/products?page&page_size →
   *   { list: [{ id, name, category, image, exhibitor_name }], total, page, pageSize, totalPages }
   */
  async getProducts(id:number, params?:any): Promise<ListResp<ExhibitionProductItem>> {
    return normList<ExhibitionProductItem>(await safe<any>(apiClient.get('/exhibitions/'+id+'/products',{params}), {}))
  },
}
