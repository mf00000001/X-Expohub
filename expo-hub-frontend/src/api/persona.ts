/**
 * 展会画像 API（后端 app/modules/persona/routes.py）
 *
 * 设计约定：**档位文案由后端下发**，前端不硬编码任何 label / hint。
 * 原因：`severe` 在页面上极易被渲染成"这个展不能去"，而它真实的语义是
 * "在本样本 N 个可比值里排后 25%"——纯相对位置。文案与档位同源于
 * bands.py 的标定常量，改档位只需改后端，前端自动跟着变。
 * 一旦前端自己写一套文案，四处渲染里一定有一处写成红牌劝退。
 */
import http from './index'

/** E1 客群可得性档位。unknown 与 severe 不是一回事，视觉上必须区分。 */
export type E1Band = 'ample' | 'normal' | 'thin' | 'severe' | 'unknown'

/** E4 展位可得性档位。ongoing（进行中）与 closed（已结束）对用户是两回事。 */
export type E4Band =
  | 'ample' | 'normal' | 'urgent' | 'critical' | 'impossible'
  | 'ongoing' | 'closed' | 'unknown'

/** 数据来源。qufair = 去展网第三方源，观众数实测偏低 20~25%。 */
export type ScaleSource = 'official' | 'qufair' | null

export interface E1Info {
  /** 观众/展商比。null 表示两个数没同时拿到，算不出来——不等于 0。 */
  ratio: number | null
  band: E1Band
  label: string
  hint: string
  /** 目标观众数区间估算（role_hit 假设推导），仅供量级参考 */
  target_lo: number | null
  target_mid: number | null
  target_hi: number | null
  confidence: 'low' | 'medium' | 'high'
}

export interface E4Info {
  band: E4Band
  label: string
  hint: string
  /** 距开展天数。负数 = 已开展（ongoing 时是已开展天数） */
  days_left: number | null
  deadline: string | null
}

export interface ExpoPersonaItem {
  slug: string
  name_cn: string
  name_en: string | null
  city: string | null
  venue_name: string | null
  start_date: string | null
  end_date: string | null
  edition_no: number | null
  primary_category: string | null
  biz_type: string | null
  audience_access: string | null
  visitor_count: number | null
  visitor_caliber: string | null
  exhibitor_count: number | null
  exhibitor_caliber: string | null
  exhibit_area_sqm: number | null
  area_caliber: string | null
  scale_source: ScaleSource
  scale_source_label: string
  e1: E1Info
  e4: E4Info
  data_status: 'full' | 'partial' | 'skeleton'
  confidence_overall: 'S' | 'M' | 'L' | null
  computed_at: string | null
}

export interface ExpoPersonaDetail extends ExpoPersonaItem {
  note: string | null
  params_version: string | null
  booth_price_standard: number | null
  booth_price_raw: string | null
  booth_deadline: string | null
  has_listing: boolean
  listing_completeness: number | null
  sample_group: string | null
  /** 观测溯源：某个来源贡献了几条字段 */
  observations: { source_type: string; count: number }[]
  /** 这份结论是在哪一份标定下算出来的 */
  calibration: {
    version: string
    basis: string
    n: number
    p25?: number
    p50?: number
    p75?: number
    superseded?: string
    /** 样本本身的已知偏差（如第三方源观众数偏低），必须随数一起展示 */
    caveat?: string
    note?: string
  }
}

export interface PersonaListParams {
  page?: number
  page_size?: number
  /** 关键词（展名/城市/展馆） */
  q?: string
  category?: string
  city?: string
  ratio_band?: E1Band
  e4_band?: E4Band
  scale_source?: 'official' | 'qufair'
  has_dates?: boolean
  /** 只要尚未闭幕的展。默认按开展日升序时，已闭幕的会排最前，与"下一个去哪"正好相反 */
  upcoming?: boolean
  sort?: 'start_date' | 'ratio' | 'name' | 'category'
  order?: 'asc' | 'desc'
}

export interface PersonaListResult {
  items: ExpoPersonaItem[]
  pagination: { page: number; page_size: number; total: number; pages: number }
}

export interface PersonaOverview {
  total_expos: number
  e1_distribution: Record<string, { count: number; label: string }>
  e4_distribution: Record<string, { count: number; label: string }>
  coverage: Record<string, { filled: number; total: number; rate: number }>
  categories: { category: string; count: number }[]
  calibration: {
    version: string
    basis: string
    p25: number
    p50: number
    p75: number
    n: number
    note?: string
  }
}

export interface E5Item {
  id: string
  name: string
  kind: string
  unit: string | null
  requirement_label: string | null
  capability_label: string | null
  /** 这一项的全部价值：该向主办方问什么 */
  ask: string
  why: string
  typical: string | null
  short_consequence: 'block' | 'cost'
  fallback: string | null
  /** 只有特装专属项允许标 na（标摊由主办方搭建，与他无关） */
  na_allowed: boolean
}

export interface E5Checklist {
  expo: {
    slug: string
    name_cn: string
    city: string | null
    venue_name: string | null
    start_date: string | null
    end_date: string | null
  } | null
  total: number
  items: E5Item[]
  valid_states: string[]
  note: string
}

export type E5State = 'ok' | 'short' | 'na' | 'unknown'

export interface E5Verdict {
  expo_slug: string | null
  verdict: 'blocked' | 'incomplete' | 'pass_with_cost' | 'pass'
  label: string
  hint: string
  blocked: Pick<E5Item, 'id' | 'name' | 'ask' | 'why' | 'fallback'>[]
  extra_cost: Pick<E5Item, 'id' | 'name' | 'ask' | 'why' | 'fallback'>[]
  unresolved: Pick<E5Item, 'id' | 'name' | 'ask' | 'why' | 'fallback'>[]
  states: Record<string, E5State>
  note: string
}

export const personaApi = {
  getExpos(params: PersonaListParams = {}) {
    return http.get('/persona/expos', { params }) as unknown as Promise<PersonaListResult>
  },

  getExpo(slug: string) {
    return http.get(`/persona/expos/${encodeURIComponent(slug)}`) as unknown as Promise<ExpoPersonaDetail>
  },

  getOverview() {
    return http.get('/persona/overview') as unknown as Promise<PersonaOverview>
  },

  getParams() {
    return http.get('/persona/params') as unknown as Promise<Record<string, unknown>>
  },

  getE5Checklist(slug?: string) {
    return http.get('/persona/e5/checklist', { params: { slug } }) as unknown as Promise<E5Checklist>
  },

  evaluateE5(states: Record<string, E5State>, expoSlug?: string) {
    return http.post('/persona/e5/evaluate', {
      expo_slug: expoSlug ?? null,
      states,
    }) as unknown as Promise<E5Verdict>
  },
}

// ============================================================
// 展示辅助：档位 → 视觉基调
// ============================================================
//
// 关键：`unknown` 用中性虚线灰，**绝不能**用红/橙色。
// 缺数据不是坏消息，把它染成警告色等于用一个数据缺口去劝退用户——
// 这正是 E1 只有 46% 覆盖率时最容易犯的错。

export type BandTone = 'good' | 'neutral' | 'warn' | 'bad' | 'muted' | 'live'

const E1_TONE: Record<E1Band, BandTone> = {
  ample: 'good',
  normal: 'neutral',
  thin: 'warn',
  severe: 'bad',
  unknown: 'muted',
}

const E4_TONE: Record<E4Band, BandTone> = {
  ample: 'good',
  normal: 'neutral',
  urgent: 'warn',
  critical: 'bad',
  impossible: 'bad',
  ongoing: 'live',
  closed: 'muted',
  unknown: 'muted',
}

export function e1Tone(band: E1Band): BandTone {
  return E1_TONE[band] ?? 'muted'
}

export function e4Tone(band: E4Band): BandTone {
  return E4_TONE[band] ?? 'muted'
}

/** 比值保留一位小数，null 返回 —（不能显示 0，0 会被读成"一个观众都没有") */
export function fmtRatio(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return v >= 100 ? v.toFixed(0) : v.toFixed(1)
}

/** 人数/平米数用"万"级缩写，避免一屏长串数字 */
export function fmtCount(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  if (v >= 10000) {
    const w = v / 10000
    return `${w >= 100 ? w.toFixed(0) : w.toFixed(1)} 万`
  }
  return v.toLocaleString('zh-CN')
}

export function fmtRate(r: number | null | undefined): string {
  if (r === null || r === undefined) return '—'
  return `${Math.round(r * 100)}%`
}

/** 日期缺年份或只有月份时也要能显示，不要装作知道 */
export function fmtDateRange(start: string | null, end: string | null): string {
  if (!start && !end) return '日期未知'
  if (start && !end) return start
  if (!start && end) return `至 ${end}`
  if (start === end) return start as string
  return `${start} — ${end}`
}

/** 口径的中文说法。页面上必须能看到，否则比值会被当成绝对可比。 */
export function caliberLabel(caliber: string | null): string {
  const map: Record<string, string> = {
    person: '人数',
    visit: '人次（已÷2 折算）',
    company: '企业数',
    booth: '展位数',
    gross: '建筑面积',
    net: '净面积',
  }
  if (!caliber) return '口径未标注'
  return map[caliber] ?? caliber
}
