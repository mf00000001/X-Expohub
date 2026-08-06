import http from './index'

export interface FavoriteItem {
  id: number
  visitor_id: number
  exhibition_id: number
  is_favorite: boolean
  is_registered: boolean
  ticket_code?: string
  created_at?: string
  exhibition?: any
}

export const favoritesApi = {
  getList(): Promise<{ list: FavoriteItem[]; total: number }> {
    return http.get('/registrations/favorites')
  },
  toggleFavorite(exhibitionId: number): Promise<{ is_favorite: boolean }> {
    return http.post('/registrations/favorites/' + exhibitionId)
  },
  removeFavorite(exhibitionId: number): Promise<any> {
    return http.post('/registrations/favorites/' + exhibitionId)
  }
}
