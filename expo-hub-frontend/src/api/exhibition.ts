import apiClient from './client'

export interface Exhibition {
  id: number; title: string; name?: string; description: string
  cover_image?: string; cover_url?: string; cover_image_url?: string
  start_date: string; end_date: string; location: string; venue?: string
  status: string; total_booths: number; organizer_id: number; organizer_name?: string
  created_at: string; updated_at: string
}
export interface ExhibitionCreatePayload { title: string; description: string; cover_image?: string; start_date: string; end_date: string; location: string; total_booths: number }
export type ExhibitionUpdatePayload = Partial<ExhibitionCreatePayload> & { status?: string }
const safe = <T>(p: Promise<T>, fb: T): Promise<T> => p.catch(() => fb)
export const exhibitionApi = {
  getList(params?: any) { return safe(apiClient.get('/exhibitions',{params}),{list:[],total:0}) as Promise<{list:Exhibition[];total:number}> },
  getMyExhibitions(oid:number,params?:any) { return safe(apiClient.get('/exhibitions',{params:{organizer_id:oid,...params}}),{list:[],total:0}) as Promise<{list:Exhibition[];total:number}> },
  getDetail(id:number) { return safe(apiClient.get('/exhibitions/'+id),null) as Promise<Exhibition|null> },
  create(p:ExhibitionCreatePayload) { return apiClient.post('/exhibitions',p) as Promise<Exhibition> },
  update(id:number,p:ExhibitionUpdatePayload) { return apiClient.put('/exhibitions/'+id,p) as Promise<Exhibition> },
  delete(id:number) { return apiClient.delete('/exhibitions/'+id).catch(()=>{}) as Promise<void> },
  // V2.0: 首页精选 & 热门
  getFeatured(limit?:number) { return safe(apiClient.get('/exhibitions/featured',{params:{limit:limit||5}}),[]) as Promise<Exhibition[]> },
  getHot(limit?:number) { return safe(apiClient.get('/exhibitions/hot',{params:{limit:limit||10}}),[]) as Promise<Exhibition[]> },
  getUpcoming(limit?:number) { return safe(apiClient.get('/exhibitions/upcoming',{params:{limit:limit||6}}),[]) as Promise<Exhibition[]> },
  smartSearch(q:string) { return apiClient.get('/exhibitions/search/smart',{params:{q}}) as Promise<any> },
}
