import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  // GeoJSON 数据集直接作为静态资源目录（demo 与数据共用同一份文件）
  publicDir: 'data',
  server: { port: 5173, open: false }
})
