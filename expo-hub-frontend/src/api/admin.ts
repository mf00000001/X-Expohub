import http from './index'

export interface AdminStats {
  total_users: number
  total_exhibitions: number
  total_booths: number
  total_registrations: number
  user_role_distribution: Record<string, number>
}

export interface StatsOverview {
  total_users: number
  total_exhibitions: number
  total_booths: number
  total_registrations: number
  total_procurements: number
  total_products: number
  total_messages: number
  user_role_distribution: Record<string, number>
  exhibition_status_distribution: Record<string, number>
  procurement_status_distribution: Record<string, number>
  exhibitor_active_count: number
  exhibitor_with_booth_count: number
  exhibitor_with_product_count: number
  procurement_total: number
  procurement_matched: number
  procurement_match_rate: number
}

export interface TrendDataPoint {
  date: string
  value: number
}

export interface UserGrowthResponse {
  visitor_growth: TrendDataPoint[]
  exhibitor_growth: TrendDataPoint[]
  organizer_growth: TrendDataPoint[]
  boss_growth: TrendDataPoint[]
  total_growth: TrendDataPoint[]
}

export interface ExhibitionTrendResponse {
  exhibition_created: TrendDataPoint[]
  exhibition_published: TrendDataPoint[]
  registrations: TrendDataPoint[]
}

export interface TeamItem {
  id: number
  name: string
  description?: string
  member_count: number
  created_at: string
}

export interface TeamMember {
  id: number
  user_id: number
  username: string
  email: string
  role: string
  team_id: number
  joined_at: string
}

export interface ApprovalItem {
  id: number
  type: string
  title: string
  applicant_name: string
  status: string
  created_at: string
}

export const adminApi = {
  // 统计数据
  getStats(): Promise<AdminStats> {
    return http.get('/admin/stats')
  },
  getStatsOverview(): Promise<StatsOverview> {
    return http.get('/admin/stats/overview')
  },
  getUserGrowth(params?: { period?: string }): Promise<UserGrowthResponse> {
    return http.get('/admin/stats/users/growth', { params })
  },
  getExhibitionTrend(params?: { period?: string }): Promise<ExhibitionTrendResponse> {
    return http.get('/admin/stats/exhibitions/trend', { params })
  },

  // 审批
  getApprovalList(params?: { status?: string; type?: string; page?: number }): Promise<ApprovalItem[]> {
    return http.get('/admin/approvals', { params })
  },
  getApprovalDetail(id: number): Promise<ApprovalItem> {
    return http.get(`/admin/approvals/${id}`)
  },
  approveExhibition(exhibitionId: number): Promise<any> {
    return http.post(`/admin/exhibitions/${exhibitionId}/approve`)
  },
  rejectExhibition(exhibitionId: number, reason: string): Promise<any> {
    return http.post(`/admin/exhibitions/${exhibitionId}/reject`, { reject_reason: reason })
  },

  // 团队管理
  getTeamList(): Promise<TeamItem[]> {
    return http.get('/admin/teams')
  },
  createTeam(data: { name: string; description?: string }): Promise<TeamItem> {
    return http.post('/admin/teams', data)
  },
  getTeamMembers(teamId: number): Promise<TeamMember[]> {
    return http.get(`/admin/teams/${teamId}/members`)
  },
  addTeamMember(teamId: number, data: { user_id: number; role: string }): Promise<TeamMember> {
    return http.post(`/admin/teams/${teamId}/members`, data)
  },
  removeTeamMember(teamId: number, userId: number): Promise<void> {
    return http.delete(`/admin/teams/${teamId}/members/${userId}`)
  },

  // 主办方报名管理
  getRegistrationList(exhibitionId: number): Promise<any[]> {
    return http.get(`/admin/exhibitions/${exhibitionId}/registrations`)
  },

  // 用户管理
  getUserList(params?: { role?: string; status?: string; page?: number }): Promise<any[]> {
    return http.get('/admin/users', { params })
  }
}
