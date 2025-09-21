import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
    plugins: [tailwindcss(), react()],
    server: {
        port: 3000,
        host: '0.0.0.0', // Listen on all interfaces including 127.0.0.1
        proxy: {
            // Proxy all /api requests to the mock backend during development
            '/api': {
                target: 'http://127.0.0.1:8787',
                changeOrigin: true,
                secure: false,
                // Optional: log proxy requests for debugging
                configure: (proxy, options) => {
                    proxy.on('proxyReq', (proxyReq, req, res) => {
                        console.log(`[PROXY] ${req.method} ${req.url} -> ${options.target}${req.url}`)
                    })
                }
            }
        }
    },
    build: {
        // Output to the same directory structure as your real backend expects
        outDir: '../msmacro/web/static',
        emptyOutDir: true,
        rollupOptions: {
            output: {
                // Keep the same asset naming convention
                entryFileNames: 'assets/index-[hash].js',
                chunkFileNames: 'assets/[name]-[hash].js',
                assetFileNames: 'assets/[name]-[hash].[ext]'
            }
        }
    }
})