import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../static',
    emptyOutDir: true,
    sourcemap: false,
    manifest: false,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Timeout lebih panjang — beberapa endpoint chain-proxy ke 10+ service
        timeout: 120_000,
        proxyTimeout: 120_000,
        // Jangan timeout saat besar body response
        selfHandleResponse: false,
        configure: (proxy) => {
          proxy.on('error', (err, _req, res) => {
            // Suppress ECONNRESET — terjadi saat downstream service lambat/down
            // Ini tidak kritikal, frontend sudah handle error di catch-blocks
            if ((err as any).code === 'ECONNRESET' || (err as any).code === 'ECONNREFUSED') {
              return;
            }
            console.error('[vite proxy error]', err);
          });
        },
      },
      '/events': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        timeout: 120_000,
        proxyTimeout: 120_000,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        timeout: 30_000,
        proxyTimeout: 30_000,
      },
    },
  },
})
