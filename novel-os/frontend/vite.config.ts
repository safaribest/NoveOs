import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { spawn, type ChildProcess } from 'child_process'
import { createConnection } from 'net'

function isPortOpen(port: number, host = '127.0.0.1'): Promise<boolean> {
  return new Promise((resolve) => {
    const conn = createConnection(port, host)
    conn.on('connect', () => {
      conn.destroy()
      resolve(true)
    })
    conn.on('error', () => resolve(false))
  })
}

function waitForBackend(url: string, timeout = 30000): Promise<void> {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const res = await fetch(url)
        if (res.ok) {
          resolve()
          return
        }
      } catch {
        // keep polling
      }
      if (Date.now() - start > timeout) {
        reject(new Error('后端启动超时'))
        return
      }
      setTimeout(check, 500)
    }
    check()
  })
}

// 模块级状态，保证 Vite server restart 时不会重复启动或误杀后端
let backendProcess: ChildProcess | null = null
let backendStartedByVite = false
let cleanupRegistered = false

function registerBackendCleanup() {
  if (cleanupRegistered) return
  cleanupRegistered = true

  const cleanup = () => {
    if (backendStartedByVite && backendProcess && !backendProcess.killed) {
      console.log('[start-backend] 正在关闭后端...')
      backendProcess.kill('SIGTERM')
      backendProcess = null
      backendStartedByVite = false
    }
  }

  process.on('SIGINT', cleanup)
  process.on('SIGTERM', cleanup)
  process.on('exit', cleanup)
}

function startBackendPlugin() {
  return {
    name: 'start-backend',
    async configureServer() {
      const port = 8001
      const host = '127.0.0.1'
      const backendUrl = `http://${host}:${port}`

      registerBackendCleanup()

      // 1) 如果本进程已经启动过后端且还活着，直接复用
      if (backendProcess && !backendProcess.killed) {
        try {
          const res = await fetch(`${backendUrl}/api/v1/projects`)
          if (res.ok) {
            console.log(`[start-backend] 后端已在 ${backendUrl} 运行，直接复用`)
            return
          }
        } catch {
          // 进程还在但可能没完全就绪，继续检查端口
        }
      }

      // 2) 端口被其他进程占用，也复用
      if (await isPortOpen(port, host)) {
        console.log(`[start-backend] 端口 ${port} 已被占用，直接复用`)
        return
      }

      // 3) 否则启动新后端
      const backendDir = path.resolve(import.meta.dirname, '../../novel-os')
      console.log(`[start-backend] 正在启动后端: ${backendDir}`)

      backendProcess = spawn(
        'python',
        ['-X', 'utf8', '-m', 'uvicorn', 'api.main:app', '--host', host, '--port', String(port)],
        {
          cwd: backendDir,
          stdio: 'inherit',
          shell: false,
        }
      )
      backendStartedByVite = true

      backendProcess.on('error', (err) => {
        console.error('[start-backend] 后端启动失败:', err)
      })

      backendProcess.on('exit', (code) => {
        if (code && code !== 0) {
          console.error(`[start-backend] 后端退出，code=${code}`)
        }
        if (backendProcess?.killed) {
          backendStartedByVite = false
          backendProcess = null
        }
      })

      await waitForBackend(`${backendUrl}/api/v1/projects`)
      console.log(`[start-backend] 后端已就绪: ${backendUrl}`)
    },
  }
}

function matchPackage(id: string, pkg: string) {
  return (
    id.includes(`node_modules/${pkg}/`) || id.endsWith(`node_modules/${pkg}`)
  )
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), startBackendPlugin()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'es2022',
    sourcemap: 'hidden',
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return

          if (matchPackage(id, 'react') || matchPackage(id, 'react-dom')) {
            return 'vendor'
          }

          if (
            matchPackage(id, 'react-router-dom') ||
            matchPackage(id, 'react-router') ||
            matchPackage(id, '@remix-run/router')
          ) {
            return 'router'
          }

          if (
            matchPackage(id, '@tanstack/react-query') ||
            matchPackage(id, '@tanstack/query-core')
          ) {
            return 'query'
          }

          if (
            [
              'lucide-react',
              '@radix-ui/react-dialog',
              '@radix-ui/react-select',
              '@radix-ui/react-tooltip',
            ].some((pkg) => matchPackage(id, pkg))
          ) {
            return 'ui'
          }

          if (
            ['react-hook-form', 'zod', '@hookform/resolvers'].some((pkg) =>
              matchPackage(id, pkg)
            )
          ) {
            return 'form'
          }

          if (matchPackage(id, 'sonner')) {
            return 'toast'
          }
        },
      },
    },
  },
})
