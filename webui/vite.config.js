import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// Emit build directly into the Python static dir
export default defineConfig({
    plugins: [react()],
    build: {
        outDir: resolve(__dirname, '../msmacro/web/static'),
        emptyOutDir: true
    },
    server: {
        port: 5173,
        proxy: {
            '/api': 'http://localhost:8787'
        }
    }
})
