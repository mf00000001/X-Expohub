import http from './index'

export const pointsApi = {
  balance() { return http.get('/points/balance') },
  dailyStats() { return http.get('/points/daily-stats') },
  history(params?: any) { return http.get('/points/history', { params }) },
  catalog() { return http.get('/points/catalog') },
  redeem(catalogId: number) { return http.post('/points/redeem', { catalog_id: catalogId }) },
}
