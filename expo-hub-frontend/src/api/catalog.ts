import http from './index'

/**
 * 展商名录 / 展品库（第三方公开名录导入的目录数据）
 *
 * 与平台的「展商账号」是两套东西：
 * - 展商账号（users.role='exhibitor'）能登录、能发展品、能接需求；
 * - 名录（catalog_exhibitors / catalog_products）是公开信息快照，只读、可搜索、用于引流与撮合线索。
 *
 * 统一约定：失败一律返回空结构，页面据此显示空态，不抛错、不白屏。
 */

export interface CatalogProduct {
  id: number
  name: string
  category?: string | null
  application?: string | null
  price_spec?: string | null
  image?: string | null
  exhibitor_name?: string | null
  expo_name?: string | null
  exhibitor_id?: number | null
}

export interface FacetItem {
  value: string
  count: number
}

export interface CatalogFacets {
  industries?: FacetItem[]
  cities?: FacetItem[]
  expos?: FacetItem[]
  categories?: FacetItem[]
}

export interface PagedList<T> {
  list: T[]
  total: number
  page: number
  page_size: number
  facets?: CatalogFacets
}

export interface CatalogExhibitorMini {
  id?: number
  name?: string
  expo_name?: string | null
  industry?: string | null
  city?: string | null
}

export interface CatalogProductDetail extends CatalogProduct {
  detail_html?: string | null
  source?: string | null
  /** 所属展商（名录已并入微展位，这里只做展示，不再链到独立名录页） */
  exhibitor?: CatalogExhibitorMini | null
}

/**
 * 名录展商（第三方公开名录快照，不是平台展商账号）
 *
 * 所属展会口径：`exhibition_ids` 来自参展关系表 `exhibition_exhibitors`
 * （一个展商可参加多场），`exhibition_id` 是兼容旧字段 = 第一条。
 * 旧版后端可能只回 `exhibition_id`（遗留列），页面按「有则用、无则忽略」处理。
 */
export interface CatalogExhibitor {
  id: number
  name: string
  name_en?: string | null
  /** 名录原文展会名（字符串，可能为空） */
  expo_name?: string | null
  exhibition_id?: number | null
  exhibition_ids?: number[]
  industry?: string | null
  city?: string | null
  country?: string | null
  booth_no?: string | null
  product_count?: number
  website?: string | null
}

/** 展商详情 = 列表字段 + 企业档案 + 名录展品 Top 12 */
export interface CatalogExhibitorDetail extends CatalogExhibitor {
  company_type?: string | null
  scale?: string | null
  main_business?: string | null
  description?: string | null
  source?: string | null
  products?: Array<{
    id: number
    name: string
    category?: string | null
    image?: string | null
  }>
}

export interface CatalogStats {
  exhibitors: number
  products: number
  expos: number
  industries: number
  cities: number
}

export interface CatalogQuery {
  search?: string
  /** 展商页用 */
  industry?: string
  city?: string
  /** 展品页用（后端按 category 精确匹配） */
  category?: string
  expo?: string
  /**
   * 展商页用：按展会筛选（后端走参展关系表 `exhibition_exhibitors`，
   * 与展会详情页的「参展展商」同口径）。空值 / 非法值后端视为不筛选。
   */
  exhibition_id?: number | string
  page?: number
  page_size?: number
}

const EMPTY_PAGE = { list: [], total: 0, page: 1, page_size: 20 }

export const catalogApi = {


  /** 展品库（支持关键词/分类/展会筛选） */
  async getProducts(params: CatalogQuery = {}): Promise<PagedList<CatalogProduct>> {
    try {
      const data = await http.get('/catalog/products', { params })
      return { ...EMPTY_PAGE, ...(data as any) }
    } catch {
      return { ...EMPTY_PAGE }
    }
  },

  async getProduct(id: number): Promise<CatalogProductDetail | null> {
    try {
      const data = await http.get(`/catalog/products/${id}`)
      return (data as any) ?? null
    } catch {
      return null
    }
  },

  /**
   * 展商名录（支持关键词 / 行业 / 城市 / 展会 / 所属展会 id 筛选 + facets + 分页）
   *
   * 与 /catalog/products 同款容错：失败返回 EMPTY_PAGE，页面据此显示失败/空态。
   */
  async getExhibitors(params: CatalogQuery = {}): Promise<PagedList<CatalogExhibitor>> {
    try {
      const data = await http.get('/catalog/exhibitors', { params })
      return { ...EMPTY_PAGE, ...(data as any) }
    } catch {
      return { ...EMPTY_PAGE }
    }
  },

  /** 展商详情（含名录展品 Top 12）；不存在/失败返回 null */
  async getExhibitor(id: number): Promise<CatalogExhibitorDetail | null> {
    try {
      const data = await http.get(`/catalog/exhibitors/${id}`)
      return (data as any) ?? null
    } catch {
      return null
    }
  },

  /** 首页/名录页用的汇总数字 */
  async getStats(): Promise<CatalogStats> {
    try {
      const data = await http.get('/catalog/stats')
      return { exhibitors: 0, products: 0, expos: 0, industries: 0, cities: 0, ...(data as any) }
    } catch {
      return { exhibitors: 0, products: 0, expos: 0, industries: 0, cities: 0 }
    }
  },
}

export default catalogApi
