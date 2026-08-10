/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        weather: {
          cold: '#3b82f6',
          cool: '#60a5fa',
          mild: '#fbbf24',
          warm: '#f97316',
          hot: '#ef4444',
        },
        aqi: {
          good: '#00e400',
          moderate: '#ffff00',
          unhealthy1: '#ff7e00',
          unhealthy2: '#ff0000',
          veryUnhealthy: '#8f3f97',
          hazardous: '#7e0023',
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
      },
    },
  },
  plugins: [],
}
