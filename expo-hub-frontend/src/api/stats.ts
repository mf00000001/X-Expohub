import apiClient from './client'

/** 单条公开动态（最新发布展会 / 最新采购需求） */
export interface PublicStatRecent {
  /** 动态类型：exhibition（展会） / procurement（采购需求） */
  type: string
  /** 标题（展会标题 / 采购需求标题） */
  title: string
  /** 发生时间（ISO 8601 字符串，可能为 null） */
  at: string | null
}

/**
 * 首页公开统计（GET /stats/public）
 *
 * 全部字段为后端数据库实时计数，前端不得做任何估算或回填兜底数字。
 */
export interface PublicStats {
  /** 已发布 + 进行中的展会数 */
  exhibitions: number
  /** 上述展会中开始日期 >= 今天的场次 */
  upcoming_exhibitions: number
  /** 状态正常的展商账号数 */
  exhibitors: number
  /** 已发布展品数 */
  products: number
  /** 待对接采购需求数 */
  procurements: number
  /** 在线微展位数 */
  micro_booths: number
  /** 最近 5 条动态，按时间倒序 */
  recent: PublicStatRecent[]
}

/**
 * 数字展示：无数据（null/undefined/非法值）返回「—」，其余按千分位展示。
 * 用于所有对外数字，避免出现编造的兜底值。
 */
export function formatStat(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return value.toLocaleString('zh-CN')
}

/** 把接口字段转成安全数字（缺失/非法一律按 0，不虚构） */
function toCount(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

/**
 * 获取首页公开统计（无需登录）。
 *
 * 失败时返回 null —— 调用方展示「—」或「暂无动态」，
 * 绝不回填任何编造数字（对外数字必须可验证）。
 */
export async function getPublicStats(): Promise<PublicStats | null> {
  try {
    const data: any = await apiClient.get('/stats/public')
    if (!data || typeof data !== 'object') return null
    return {
      exhibitions: toCount(data.exhibitions),
      upcoming_exhibitions: toCount(data.upcoming_exhibitions),
      exhibitors: toCount(data.exhibitors),
      products: toCount(data.products),
      procurements: toCount(data.procurements),
      micro_booths: toCount(data.micro_booths),
      recent: Array.isArray(data.recent)
        ? data.recent.filter((item: any) => item && typeof item === 'object')
        : [],
    }
  } catch (e) {
    console.warn('[stats] 公开统计获取失败，首页数字将显示为 —', e)
    return null
  }
}
