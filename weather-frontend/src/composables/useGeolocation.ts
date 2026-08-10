import { ref, onMounted } from 'vue'
import type { GeoLocation } from '@/types/api'

export function useGeolocation() {
  const location = ref<GeoLocation | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const supported = ref(true)

  function getPosition(): Promise<GeoLocation> {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        supported.value = false
        reject(new Error('浏览器不支持定位'))
        return
      }

      loading.value = true
      error.value = null

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const loc: GeoLocation = {
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
          }
          location.value = loc
          loading.value = false
          resolve(loc)
        },
        (err) => {
          loading.value = false
          let msg = '定位失败'
          switch (err.code) {
            case err.PERMISSION_DENIED:
              msg = '用户拒绝了定位请求'
              break
            case err.POSITION_UNAVAILABLE:
              msg = '位置信息不可用'
              break
            case err.TIMEOUT:
              msg = '定位超时'
              break
          }
          error.value = msg
          reject(new Error(msg))
        },
        {
          enableHighAccuracy: false,
          timeout: 10000,
          maximumAge: 300000,
        }
      )
    })
  }

  return {
    location,
    loading,
    error,
    supported,
    getPosition,
  }
}
