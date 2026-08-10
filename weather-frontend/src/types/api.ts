export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface GeoLocation {
  latitude: number
  longitude: number
}

export interface UserInfo {
  id: number
  username: string
  email: string
  avatar?: string
  created_at: string
}

export interface AuthData {
  access_token: string
  token_type: string
  expires_in: number
  user: UserInfo
}
