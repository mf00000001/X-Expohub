import http from './index'

export const getDashboardStats = () =>
  http.get('/dashboard/stats').then((r) => r.data)

export const getExhibitionStats = () =>
  http.get('/dashboard/stats/exhibitions').then((r) => r.data)

export const getExhibitorStats = () =>
  http.get('/dashboard/stats/exhibitors').then((r) => r.data)

export const getProcurementStats = () =>
  http.get('/dashboard/stats/procurements').then((r) => r.data)
