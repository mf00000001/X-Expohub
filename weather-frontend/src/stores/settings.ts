import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type TemperatureUnit = 'celsius' | 'fahrenheit'
export type Language = 'zh' | 'en'

export const useSettingsStore = defineStore('settings', () => {
  const temperatureUnit = ref<TemperatureUnit>(
    (localStorage.getItem('temp_unit') as TemperatureUnit) || 'celsius'
  )
  const language = ref<Language>(
    (localStorage.getItem('language') as Language) || 'zh'
  )

  const unitLabel = computed(() => (temperatureUnit.value === 'celsius' ? '℃' : '℉'))

  function toggleUnit() {
    temperatureUnit.value =
      temperatureUnit.value === 'celsius' ? 'fahrenheit' : 'celsius'
    localStorage.setItem('temp_unit', temperatureUnit.value)
  }

  function setUnit(unit: TemperatureUnit) {
    temperatureUnit.value = unit
    localStorage.setItem('temp_unit', unit)
  }

  function setLanguage(lang: Language) {
    language.value = lang
    localStorage.setItem('language', lang)
  }

  return {
    temperatureUnit,
    language,
    unitLabel,
    toggleUnit,
    setUnit,
    setLanguage,
  }
})
