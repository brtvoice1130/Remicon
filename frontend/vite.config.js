import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 최상위 .env 파일 로드
  const env = loadEnv(mode, '../', '')

  return {
    plugins: [react()],
    server: {
      port: 3000,
      open: true
    },
    // 환경변수 정의
    define: {
      'import.meta.env.VITE_API_URL': JSON.stringify(env.VITE_API_URL)
    },
    // 최상위 폴더에서 .env 파일 로드
    envDir: '../'
  }
})