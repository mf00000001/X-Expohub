import http from './index'

export const analyticsApi = {
  trackEvent(data: { event_type: string; entity_type: string; entity_id: number; source_user_id?: number; metadata?: string }) {
    return http.post('/analytics/event', data).catch(() => {})
  },
}

export const exhibitorAnalyticsApi = {
  overview() { return http.get('/exhibitor/analytics/overview') },
  trend(days?: number) { return http.get('/exhibitor/analytics/trend', { params: { days: days || 7 } }) },
  topProducts(limit?: number) { return http.get('/exhibitor/analytics/top-products', { params: { limit: limit || 5 } }) },
}
