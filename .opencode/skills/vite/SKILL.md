---
name: vite
description: Use when building or configuring Vite 6/7 projects — dev server, production builds, plugins system, SSR, library mode, HMR, environment variables, build optimization, Vitest testing, and migration from CRA/Webpack. Covers all aspects of the Vite build tool.
---

# Skill: vite

## Vite Mastery — Dev Server, Build Optimization, Plugins, SSR, and Production Patterns

### Core Philosophy

Vite is a **build tool that leverages native ES modules** during development and **Rollup** for production bundling. Unlike Webpack which bundles everything upfront, Vite serves source files as native ESM, letting the browser handle module resolution and only transforming files on-demand. This enables **sub-second HMR** regardless of project size.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         VITE ARCHITECTURE                            │
│                                                                      │
│   DEV SERVER                        PRODUCTION BUILD                │
│   ───────────                        ───────────────                │
│                                                                      │
│   Request                          ┌─────────────────────┐          │
│     │                              │   Rollup Bundler     │          │
│     ▼                              │                     │          │
│   esbuild (pre-bundle deps) ──────►│  ┌───────────────┐  │          │
│     │                              │  │ Tree Shaking  │  │          │
│     ▼                              │  └───────────────┘  │          │
│   Transform (esbuild/SWC/Babel)    │  ┌───────────────┐  │          │
│     │                              │  │ Code Splitting│  │          │
│     ▼                              │  └───────────────┘  │          │
│   HMR (WebSocket) ◄───────────►    │  ┌───────────────┐  │          │
│     │                              │  │ Minification  │  │          │
│     ▼                              │  └───────────────┘  │          │
│   Browser (native ESM)             │  ┌───────────────┐  │          │
│                                    │  │ CSS inlining  │  │          │
│                                    │  └───────────────┘  │          │
│   ┌─ esbuild pre-bundling ───────┐ │  ┌───────────────┐  │          │
│   │  - Converts CJS to ESM       │ │  │ Chunk Splitting│  │         │
│   │  - Deduplicates deps         │ │  └───────────────┘  │          │
│   │  - Single file per dep       │ │          ▼          │          │
│   └──────────────────────────────┘ │    dist/            │          │
│                                    │    ├── assets/      │          │
│   ┌─ HMR over WebSocket ─────────┐│    ├── index.html   │          │
│   │  - File change detected      ││    └── ...           │          │
│   │  - Transform only changed    ││                      │          │
│   │  - Push update to browser    │└──────────────────────┘          │
│   │  - Hot replace without reload│                                   │
│   └──────────────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 1. Configuration — `vite.config.ts`

#### 1.1 Base Configuration

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  // Root directory of the project
  root: process.cwd(),

  // Base public path when served in production
  base: '/',                   // absolute path
  // base: '/my-app/',         // sub-path deployment
  // base: './',               // relative — for Electron or static deploys

  // Public directory (served as-is at root)
  publicDir: 'public',

  // Cache directory for pre-bundled deps
  cacheDir: 'node_modules/.vite',

  // Array of plugins
  plugins: [react()],

  resolve: {
    // Path aliases — maps @/ to src/
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@components': path.resolve(__dirname, 'src/components'),
      '@utils': path.resolve(__dirname, 'src/lib/utils'),
      '#types': path.resolve(__dirname, 'src/types'),
    },
    // Extensions to try in order (default)
    extensions: ['.mjs', '.js', '.mts', '.ts', '.jsx', '.tsx', '.json'],
    // Main fields in package.json to check
    mainFields: ['module', 'browser', 'jsnext:main', 'jsnext'],
  },

  css: {
    modules: {
      // CSS Modules naming convention
      localsConvention: 'camelCaseOnly',
      scopeBehaviour: 'local',
      generateScopedName: '[name]__[local]___[hash:base64:5]',
    },
    preprocessorOptions: {
      scss: {
        additionalData: `@import "@/styles/variables.scss";`,
        api: 'modern-compiler', // use sass modern compiler
      },
      less: {
        javascriptEnabled: true,
      },
    },
    // PostCSS config — auto-detected from postcss.config.js
    devSourcemap: true,
  },

  define: {
    // Global constants replaced at build time
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version),
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
    __DEV__: process.env.NODE_ENV !== 'production',
  },

  server: {
    port: 5173,
    strictPort: false,       // auto-increment if port is taken
    host: 'localhost',       // or '0.0.0.0' for network access
    open: true,              // auto-open browser
    cors: true,
    // HTTPS — provide cert and key
    // https: { cert, key },
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        // WebSocket support
        ws: true,
        // Timeout
        proxyTimeout: 30_000,
        // Custom headers
        headers: {
          'X-Custom-Header': 'value',
        },
      },
      '/ws': {
        target: 'ws://localhost:3000',
        ws: true,
      },
    },
  },
})
```

#### 1.2 Build Options

```typescript
export default defineConfig({
  build: {
    // Output directory
    outDir: 'dist',
    // Clean outDir before build
    emptyOutDir: true,
    // Assets directory inside outDir
    assetsDir: 'assets',
    // Sourcemap strategy
    sourcemap: false,               // no sourcemaps
    // sourcemap: 'hidden',         // sourcemaps but no reference in files
    // sourcemap: 'inline',         // inline sourcemaps (large bundles)

    // Target browsers
    target: 'es2020',               // modern browsers
    // target: ['es2020', 'edge88', 'firefox78', 'chrome87', 'safari14'],

    // Minification — esbuild is faster, terser shrinks more
    minify: 'esbuild',              // default, 20-40x faster than terser
    // minify: 'terser',            // smaller output, slower build

    // Terser options (only when minify: 'terser')
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
      format: {
        comments: false,
      },
    },

    // esbuild minification options
    esbuild: {
      drop: ['console', 'debugger'],
      legalComments: 'none',
      treeShaking: true,
    },

    // CSS code splitting — extract CSS per chunk
    cssCodeSplit: true,

    // CSS minification
    cssMinify: 'esbuild',           // 'esbuild' | 'lightningcss'

    // Rollup options
    rollupOptions: {
      // Manual chunk splitting
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          ui: ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu'],
          utils: ['date-fns', 'zod', 'clsx'],
          // Dynamic splitting with function
          // manualChunks(id) {
          //   if (id.includes('node_modules')) {
          //     const pkg = id.split('node_modules/')[1].split('/')[0]
          //     return `vendor-${pkg}`
          //   }
          // },
        },
        // Chunk file naming
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },

    // Chunk size warning limit
    chunkSizeWarningLimit: 500,      // kB

    // Report compressed sizes
    reportCompressedSize: true,

    // Rollup watch options
    watch: null,                     // disable watch during build

    // Enable/disable emitting CSS into separate files
    cssCodeSplit: true,

    // Copy publicDir to outDir
    copyPublicDir: true,

    // Enable/disable module preload polyfill
    modulePreload: {
      polyfill: true,
      resolveDependencies: (filename, deps, context) => {
        return deps // or filter
      },
    },
  },
})
```

#### 1.3 Preview Server

```typescript
export default defineConfig({
  preview: {
    port: 4173,
    strictPort: false,
    host: 'localhost',
    open: false,
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
    },
  },
})
```

#### 1.4 Dependency Optimization

```typescript
export default defineConfig({
  optimizeDeps: {
    // Force pre-bundle of certain deps
    include: ['react', 'react-dom', 'react-router-dom', 'lodash-es'],
    // Exclude deps from pre-bundling
    exclude: ['fsevents'],
    // Force re-bundle when these deps change
    force: true,
    // esbuild options for dep optimization
    esbuildOptions: {
      target: 'es2020',
      // Custom tsconfig for deps
      tsconfigRaw: {
        compilerOptions: {
          experimentalDecorators: true,
        },
      },
    },
    // Prevent bundling of specific dependencies
    needsInterop: ['some-dep'],
  },
})
```

---

### 2. Plugin System

#### 2.1 Plugin Architecture

Vite plugins extend Rollup's plugin interface with Vite-specific hooks. A plugin is an object with `name`, `hooks`, and optional `enforce` (pre | post).

```
┌───────────────────────────────────────────────────────────┐
│                   PLUGIN HOOK ORDER                         │
│                                                             │
│   ROLLUP HOOKS                        VITE HOOKS            │
│   ─────────────                        ──────────           │
│   options ◄────── buildStart                                │
│   buildStart ◄───── resolveId ◄────────── resolve           │
│   resolveId ◄────── load ◄────────────── load              │
│   load ◄────────────── transform ◄─────────── transform     │
│   transform ◄─────── moduleParsed                           │
│   moduleParsed                                            │
│   ...                    configResolved                     │
│   generateBundle                                            │
│   writeBundle                                               │
│   closeBundle                                               │
│                                                             │
│   VITE-SPECIFIC:                                            │
│   ┌─────────────────────────────────────────────────────┐  │
│   │  config        — modify config before resolve        │  │
│   │  configResolved — read resolved config               │  │
│   │  configureServer — configure dev server              │  │
│   │  transformIndexHtml — transform index.html           │  │
│   │  handleHotUpdate — custom HMR handling               │  │
│   │  resolve — resolve id (before rollup)                │  │
│   │  load — load module (before rollup)                  │  │
│   │  transform — transform module (before rollup)        │  │
│   └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

#### 2.2 Vite-Specific Hooks

```typescript
import type { Plugin, ResolvedConfig, ViteDevServer } from 'vite'
import type { AddressInfo } from 'node:net'

function myPlugin(): Plugin {
  let config: ResolvedConfig
  let server: ViteDevServer

  return {
    name: 'my-plugin',

    // enforce — 'pre' (run before built-in), 'post' (run after)
    enforce: 'post',

    // Modify config before it's resolved
    config(userConfig, { command, mode, ssrBuild }) {
      return {
        define: {
          __MY_PLUGIN_VERSION__: JSON.stringify('1.0.0'),
        },
      }
    },

    // Read the resolved config
    configResolved(resolvedConfig) {
      config = resolvedConfig
      // Store resolved paths
      const cacheDir = config.cacheDir
    },

    // Configure the dev server
    configureServer(devServer) {
      server = devServer

      // Access the underlying http server (Vite 6+)
      // server.httpServer is deprecated in Vite 7
      const listen = server.listen.bind(server)
      server.listen = async (port, isRestart) => {
        await listen(port, isRestart)
        const addr = server.resolvedUrls?.local[0]
        console.log(`  ➜  Custom: http://localhost:${port}/custom`)
      }

      // Middleware mode — add connect middleware
      return () => {
        // Return a middleware function
        server.middlewares.use('/custom', (req, res, next) => {
          res.writeHead(200, { 'Content-Type': 'text/plain' })
          res.end('Hello from Vite plugin!')
        })
      }
    },

    // Transform index.html
    transformIndexHtml(html, { filename, server, bundle, chunk }) {
      return {
        html,
        tags: [
          {
            tag: 'link',
            attrs: {
              rel: 'preload',
              href: '/assets/preloaded-asset.js',
              as: 'script',
            },
            injectTo: 'head',
          },
          {
            tag: 'script',
            attrs: { src: '/analytics.js', 'data-id': 'UA-XXXXX-Y' },
            injectTo: 'head-prepend',
          },
          // InjectTo positions:
          // 'head' | 'head-prepend' | 'body' | 'body-prepend'
        ],
      }
    },

    // Custom HMR handling
    handleHotUpdate(ctx) {
      // ctx: { file, server, modules, read, timestamp }
      // Filter which modules to update
      if (ctx.file.includes('node_modules')) {
        return [] // ignore node_modules changes
      }
      if (ctx.file.endsWith('.graphql')) {
        // Custom handling for .graphql files
        return ctx.modules
      }
      // Return nothing = default behavior
    },

    // Resolve module specifiers (runs before Rollup's resolveId)
    resolve(id, importer, options) {
      if (id.startsWith('virtual:')) {
        return { id: '\0' + id, external: false }
      }
    },

    // Load modules (runs before Rollup's load)
    load(id, options) {
      if (id === '\0virtual:my-module') {
        return {
          code: `export const msg = 'Hello from virtual module'`,
          map: null,
        }
      }
    },

    // Transform module code
    transform(code, id, options) {
      if (id.endsWith('.custom')) {
        // Transform custom file types
        return {
          code: `export default ${JSON.stringify(code)}`,
          map: null,
        }
      }
    },

    // Close server — cleanup
    closeBundle() {
      // Cleanup resources
    },
  }
}
```

#### 2.3 Writing a Virtual Module Plugin

```typescript
import type { Plugin } from 'vite'
import fs from 'node:fs'

const VIRTUAL_PREFIX = 'virtual:config'
const RESOLVED_PREFIX = '\0' + VIRTUAL_PREFIX

function virtualConfigPlugin(): Plugin {
  return {
    name: 'virtual-config',
    resolve(id) {
      if (id === VIRTUAL_PREFIX) {
        return RESOLVED_PREFIX
      }
    },
    load(id) {
      if (id === RESOLVED_PREFIX) {
        const env = {
          NODE_ENV: process.env.NODE_ENV || 'development',
          API_URL: process.env.VITE_API_URL || 'http://localhost:3000',
          BUILD_TIME: new Date().toISOString(),
        }
        return {
          code: `export const config = ${JSON.stringify(env)}`,
          map: null,
        }
      }
    },
  }
}
```

---

### 3. Environment Variables

#### 3.1 Built-in Variables

```typescript
// Available at build time via import.meta.env
import.meta.env.MODE          // 'development' | 'production'
import.meta.env.BASE_URL      // base path (default '/')
import.meta.env.PROD          // true in production
import.meta.env.DEV           // true in development
import.meta.env.SSR           // true when running on server
```

#### 3.2 Custom Env Variables (VITE_ prefix)

```typescript
// Only variables with VITE_ prefix are exposed to client code
// .env
VITE_API_URL=http://localhost:3000
VITE_APP_TITLE=My App
VITE_FEATURE_FLAG_NEW_DASHBOARD=true

// .env.development
VITE_API_URL=http://localhost:3000
VITE_DEBUG=true

// .env.production
VITE_API_URL=https://api.example.com

// .env.local — git-ignored, for local overrides
VITE_API_KEY=sk-local-dev-key

// Priority (highest to lowest):
// 1. .env.[mode].local      — mode-specific, local
// 2. .env.[mode]             — mode-specific
// 3. .env.local              — general local overrides
// 4. .env                    — general defaults

// In code:
const apiUrl = import.meta.env.VITE_API_URL
const isDev = import.meta.env.DEV
```

#### 3.3 Type Safety for Env Variables

```typescript
// src/vite-env.d.ts — augment ImportMeta
interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_APP_TITLE: string
  readonly VITE_FEATURE_FLAG_NEW_DASHBOARD: 'true' | 'false'
  readonly VITE_DEBUG: string
  // optional with ?
  readonly VITE_SENTRY_DSN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// src/env.d.ts — alternative approach with triple-slash
/// <reference types="vite/client" />
```

#### 3.4 Runtime Env Variables (docker/K8s)

```typescript
// For runtime env injection (not at build time):
// index.html — load env from window object
// <script>
//   window.__ENV__ = {
//     VITE_API_URL: '${VITE_API_URL}',
//     VITE_APP_TITLE: '${VITE_APP_TITLE}',
//   }
// </script>

// src/env.ts — runtime env resolver
function getEnv(key: string, fallback?: string): string {
  if (typeof window !== 'undefined' && (window as any).__ENV__?.[key]) {
    return (window as any).__ENV__[key]
  }
  if (import.meta.env[key]) {
    return import.meta.env[key]
  }
  if (fallback !== undefined) return fallback
  throw new Error(`Missing env: ${key}`)
}

export const env = {
  apiUrl: getEnv('VITE_API_URL', 'http://localhost:3000'),
  appTitle: getEnv('VITE_APP_TITLE', 'My App'),
}
```

#### 3.5 Mode-Specific Config

```typescript
// vite.config.ts — access mode
export default defineConfig(({ mode, command }) => {
  const isDev = mode === 'development'
  const isStaging = mode === 'staging'

  return {
    // mode flag: vite build --mode staging
    base: isDev ? '/' : '/app/',
    build: {
      sourcemap: isDev || isStaging,
      minify: isDev ? false : 'esbuild',
    },
    define: {
      __STAGING__: JSON.stringify(isStaging),
    },
  }
})
```

---

### 4. Essential Plugins

#### 4.1 @vitejs/plugin-react — SWC vs Babel

```typescript
// Babel-based (default, more customizable)
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    react({
      // Babel configuration
      babel: {
        plugins: ['@emotion/babel-plugin'],
        presets: ['@babel/preset-typescript'],
        babelrc: false,
        configFile: false,
      },
      // Fast Refresh
      fastRefresh: true,
      // JSX runtime — 'automatic' (React 18+) or 'classic'
      jsxRuntime: 'automatic',
      // Exclude specific files from transformation
      exclude: /\.stories\.(t|j)sx?$/,
      // Include specific files
      include: /\.(t|j)sx?$/,
    }),
  ],
})
```

```typescript
// SWC-based (faster, less configurable)
import react from '@vitejs/plugin-react-swc'

export default defineConfig({
  plugins: [
    react({
      // SWC configuration
      tsDecorators: true,
      parserConfig: {
        syntax: 'typescript',
        tsx: true,
        decorators: true,
      },
      // Exclude stories
      exclude: /\.stories\.(t|j)sx?$/,
    }),
  ],
})
```

#### 4.2 @vitejs/plugin-vue

```typescript
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue({
      // Template compilation options
      template: {
        compilerOptions: {
          // Treat specific tags as custom elements
          isCustomElement: (tag) => tag.startsWith('ion-'),
        },
      },
      // Reactive transform (Vue 3.3+)
      reactivityTransform: true,
      // Custom SFC blocks
      customBlocks: ['i18n'],
    }),
  ],
})
```

#### 4.3 unplugin-auto-import

```typescript
import AutoImport from 'unplugin-auto-import/vite'

export default defineConfig({
  plugins: [
    AutoImport({
      // Auto-import from known libraries
      imports: [
        'react',
        'react-router-dom',
        'react-i18next',
        { 'date-fns': ['format', 'parseISO', 'addDays'] },
        { 'clsx': [['default', 'cn']] },
      ],
      // Include type declarations
      dts: 'src/auto-imports.d.ts',
      // Directories to auto-import from
      dirs: [
        'src/hooks/**',
        'src/utils/**',
      ],
      // ESLint globals
      eslintrc: {
        enabled: true,
        filepath: './.eslintrc-auto-import.json',
      },
    }),
  ],
})
```

#### 4.4 unplugin-icons

```typescript
import Icons from 'unplugin-icons/vite'
import IconsResolver from 'unplugin-icons/resolver'

export default defineConfig({
  plugins: [
    Icons({
      // Icon collections — install as devDeps
      // npm i -D @iconify-json/mdi @iconify-json/logos
      compiler: 'jsx',          // 'jsx' | 'tsx' | 'vue' | 'svelte' | 'solid'
      jsx: 'react',             // framework
      scale: 1.2,               // scale 1.2x
      defaultStyle: 'display: inline-block',
      autoInstall: true,        // install missing collections on the fly
    }),
  ],
})

// Usage:
// import IconAccessPoint from '~icons/mdi/access-point'
// import IconLogoGithub from '~icons/logos/github-icon'
```

#### 4.5 vite-tsconfig-paths

```typescript
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  plugins: [
    tsconfigPaths({
      // Match paths from tsconfig.json
      projects: ['./tsconfig.json'],
      extensions: ['.ts', '.tsx', '.js', '.jsx'],
    }),
  ],
})

// Instead of manual resolve.alias
// tsconfig.json:
// {
//   "compilerOptions": {
//     "paths": {
//       "@/*": ["./src/*"],
//       "@components/*": ["./src/components/*"]
//     }
//   }
// }
```

#### 4.6 vite-plugin-pwa

```typescript
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'robots.txt', 'apple-touch-icon.png'],
      manifest: {
        name: 'My App',
        short_name: 'MyApp',
        description: 'My amazing app',
        theme_color: '#ffffff',
        background_color: '#ffffff',
        display: 'standalone',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: 'icons/icon-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'icons/icon-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/api\.example\.com\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: {
                maxEntries: 50,
                maxAgeSeconds: 60 * 60 * 24, // 24 hours
              },
              networkTimeoutSeconds: 10,
            },
          },
        ],
      },
      // For dev — test PWA in development
      devOptions: {
        enabled: true,
        type: 'module',
      },
    }),
  ],
})
```

#### 4.7 vite-plugin-svgr

```typescript
import svgr from 'vite-plugin-svgr'

export default defineConfig({
  plugins: [
    svgr({
      // SVGR options
      svgrOptions: {
        exportType: 'default',
        ref: true,
        svgo: true,
        titleProp: true,
        plugins: ['@svgr/plugin-svgo', '@svgr/plugin-jsx'],
      },
      // Include/exclude
      include: '**/*.svg?react',
      exclude: '',
    }),
  ],
})

// Usage:
// import Logo from './logo.svg?react'
// const App = () => <Logo width={100} height={100} />
```

#### 4.8 Other Essential Plugins

```typescript
// vite-plugin-compression — gzip/brotli
import compression from 'vite-plugin-compression'

export default defineConfig({
  plugins: [
    compression({
      algorithm: 'brotliCompress',
      ext: '.br',
      threshold: 10240,          // only files > 10KB
      deleteOriginFile: false,
    }),
  ],
})
```

```typescript
// vite-plugin-inspect — inspect plugin output
import Inspect from 'vite-plugin-inspect'

export default defineConfig({
  plugins: [Inspect()],
  // Visit http://localhost:5173/__inspect in dev
})
```

```typescript
// vite-plugin-checker — type check + lint in a separate worker
import checker from 'vite-plugin-checker'

export default defineConfig({
  plugins: [
    checker({
      typescript: {
        tsconfigPath: './tsconfig.json',
      },
      eslint: {
        lintCommand: 'eslint src --ext .ts,.tsx',
        dev: {
          logLevel: ['error'],
        },
      },
    }),
  ],
})
```

---

### 5. Build Optimization

#### 5.1 Code Splitting — manualChunks Strategies

```typescript
// Strategy 1: Framework chunk
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
  },
})

// Strategy 2: Granular by package group
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            // Group by top-level package
            const pkg = id.split('node_modules/')[1].split('/')[0]

            // Put React and its ecosystem together
            if (['react', 'react-dom', 'react-router-dom', 'scheduler'].includes(pkg)) {
              return 'vendor-react'
            }
            // Put UI libraries together
            if (['@radix-ui', '@emotion', 'framer-motion'].includes(pkg)) {
              return 'vendor-ui'
            }
            // Default: per-package chunk
            return `vendor-${pkg}`
          }
          // Source code — group by feature
          if (id.includes('/src/pages/dashboard/')) {
            return 'feature-dashboard'
          }
          if (id.includes('/src/pages/admin/')) {
            return 'feature-admin'
          }
        },
      },
    },
  },
})

// Strategy 3: Use rollup-plugin-visualizer to analyze
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig({
  plugins: [
    visualizer({
      filename: 'stats.html',
      open: true,
      gzipSize: true,
      brotliSize: true,
    }),
  ],
})
```

#### 5.2 Dynamic Imports — Lazy Loading

```typescript
// React.lazy + Suspense for route-level splitting
import { lazy, Suspense } from 'react'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const AdminPanel = lazy(() => import('./pages/AdminPanel'))
const Settings = lazy(() => import('./pages/Settings'))

function App() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/admin" element={<AdminPanel />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Suspense>
  )
}

// Named exports — use with /* @vite-ignore */ for dynamic
const Page = lazy(() => import(/* @vite-ignore */ `./pages/${pageName}`))

// Prefetch on hover
// const loadDashboard = () => import('./pages/Dashboard')
// <Link onMouseEnter={loadDashboard} to="/dashboard">Dashboard</Link>

// Magic comments for chunk naming:
// const Admin = lazy(() => import(/* webpackChunkName: "admin" */ './pages/Admin'))
// Vite converts webpackChunkName to chunk names automatically
```

#### 5.3 Tree Shaking

```typescript
// Vite tree-shakes by default using Rollup. Ensure:

// 1. Use ESM imports (not CJS)
import { map, filter } from 'lodash-es'      // ✓ ESM — tree-shakable
// const _ = require('lodash')                // ❌ CJS — full bundle

// 2. Use barrel exports carefully
// utils/index.ts
export { formatDate } from './date'           // ✓ tree-shakable
export { validateEmail } from './validation'  // ✓ tree-shakable
// export * from './date'                     // exports ALL from date (fine if tree-shaken)

// 3. Side effect flags in package.json
// {
//   "sideEffects": false,                     // tell bundler this package is side-effect-free
//   "sideEffects": ["*.css"]                  // only CSS has side effects
// }

// 4. Mark modules as pure
const result = /*#__PURE__*/ createFactory()
```

#### 5.4 Chunk Size Warning Configuration

```typescript
export default defineConfig({
  build: {
    chunkSizeWarningLimit: 1000,        // increase warning threshold to 1MB
    rollupOptions: {
      output: {
        // Aggressively split large chunks
        experimentalMinChunkSize: 20000, // merge chunks smaller than 20KB (Rollup 4+)
      },
    },
    // Report compressed sizes (default: true)
    reportCompressedSize: true,
  },
})
```

#### 5.5 CSS Optimization

```typescript
export default defineConfig({
  build: {
    // Extract CSS into separate files per chunk
    cssCodeSplit: true,

    // CSS minification engine
    cssMinify: 'lightningcss',   // faster than esbuild for CSS

    // Inline small CSS (< 4KB)
    cssMinify: 'esbuild',

    // PostCSS config auto-detected
  },
  css: {
    // CSS modules
    modules: {
      localsConvention: 'camelCase',
    },
    // LightningCSS options
    lightningcss: {
      // targets: browserslist to query
      drafts: {
        customMedia: true,
      },
    },
    // PostCSS
    postcss: './postcss.config.js',
  },
})
```

---

### 6. HMR (Hot Module Replacement)

#### 6.1 How Vite HMR Works

```
┌─────────┐     File Change      ┌───────────┐
│  Editor  │ ──────────────────►  │  File     │
└─────────┘                       │  Watcher  │
                                  └─────┬─────┘
                                        │
                                   ┌────▼────┐
                                   │  Vite   │
                                   │  Dev    │
                                   │  Server │
                                   └────┬────┘
                                        │
                              ┌─────────▼──────────┐
                              │  Invalidate module  │
                              │  chain in module    │
                              │  graph              │
                              └─────────┬──────────┘
                                        │
                              ┌─────────▼──────────┐
                              │  Transform only     │
                              │  changed module     │
                              │  (esbuild/SWC)      │
                              └─────────┬──────────┘
                                        │
                              ┌─────────▼──────────┐
                              │  Send over          │
                              │  WebSocket          │
                              │  (full update /     │
                              │   partial update)   │
                              └─────────┬──────────┘
                                        │
                              ┌─────────▼──────────┐
                              │  Browser receives   │
                              │  hot update         │
                              │  → re-render        │
                              │  without full reload│
                              └────────────────────┘
```

#### 6.2 HMR API

```typescript
// Accept module self-updates
if (import.meta.hot) {
  import.meta.hot.accept()

  // Accept with callback
  import.meta.hot.accept((newModule) => {
    // newModule is the updated module
    console.log('Module updated:', newModule)
  })
}

// Accept dependencies
import { foo } from './foo'

if (import.meta.hot) {
  import.meta.hot.accept('./foo', (newFoo) => {
    // Called when ./foo is updated
    foo = newFoo.foo
  })
}

// Self-dispose — cleanup before module is re-executed
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    // Cleanup: remove event listeners, timers, etc.
    cleanup()
  })
}

// Decline — do not accept updates (force full reload)
if (import.meta.hot) {
  import.meta.hot.decline()
}

// Invalidate — force parent modules to re-execute
if (import.meta.hot) {
  import.meta.hot.invalidate()
}

// Custom events — send data to dev server
if (import.meta.hot) {
  import.meta.hot.send('custom:event', { data: 'hello' })
}

// Status checks
if (import.meta.hot) {
  console.log(import.meta.hot.status) // 'idle' | 'check' | 'apply' | 'fail'
}
```

#### 6.3 Custom HMR Boundaries

```typescript
// For stateful modules (e.g., stores, contexts)
// src/store.ts
let store = {
  user: null,
  theme: 'light',
}

export function getStore() {
  return store
}

export function setStore(newStore: Partial<typeof store>) {
  store = { ...store, ...newStore }
}

// HMR — preserve store state across hot updates
if (import.meta.hot) {
  const prevStore = store // save state

  import.meta.hot.accept((newModule) => {
    // Restore state in new module
    store = prevStore
  })

  import.meta.hot.dispose(() => {
    // Save state before dispose
    sessionStorage.setItem('__hmr_store__', JSON.stringify(store))
  })
}
```

#### 6.4 HMR in Plugins

```typescript
function hmrPlugin(): Plugin {
  return {
    name: 'hmr-plugin',
    handleHotUpdate(ctx) {
      // Filter — only update specific modules
      if (ctx.file.endsWith('.css')) {
        // CSS updates are handled natively
        return ctx.modules
      }
      if (ctx.file.endsWith('.graphql')) {
        // Transform before HMR
        return ctx.server.transformRequest(ctx.file).then(() => {
          return ctx.modules
        })
      }
      // Return empty to suppress update
      if (ctx.file.includes('__tests__')) {
        return []
      }
    },
  }
}
```

---

### 7. SSR (Server-Side Rendering)

#### 7.1 SSR Build Configuration

```typescript
// vite.config.ts — dual build
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    // Client build
    outDir: 'dist/client',
    rollupOptions: {
      input: 'src/entry-client.tsx',
    },
  },
  // SSR-specific config
  ssr: {
    // Externalize these deps (not bundled for SSR)
    external: ['react', 'react-dom/server'],
    // Vite will bundle everything else
    noExternal: ['@my-company/*'],
    // Target
    target: 'node',
    // Resolve conditions
    resolve: {
      conditions: ['node', 'module', 'import'],
    },
  },
})
```

```typescript
// vite.config.ts — SSR build config
export default defineConfig({
  build: {
    outDir: 'dist/server',
    ssr: 'src/entry-server.tsx',
    rollupOptions: {
      output: {
        format: 'esm',
        entryFileNames: '[name].mjs',
      },
    },
    // Minify is usually off for SSR bundles
    minify: false,
  },
})
```

#### 7.2 SSR Entry Points

```typescript
// src/entry-client.tsx — client-side hydration
import { StrictMode } from 'react'
import { hydrateRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

hydrateRoot(
  document.getElementById('root')!,
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
```

```typescript
// src/entry-server.tsx — server-side render
import { StrictMode } from 'react'
import { renderToPipeableStream, renderToString } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server'
import App from './App'

// For streaming SSR (React 18+)
export function render(url: string, opts?: { onShellReady?: () => void }) {
  const stream = renderToPipeableStream(
    <StrictMode>
      <StaticRouter location={url}>
        <App />
      </StaticRouter>
    </StrictMode>,
    {
      bootstrapScripts: ['/client/assets/entry-client.js'],
      onShellReady() {
        opts?.onShellReady?.()
      },
      onError(err) {
        console.error(err)
      },
    },
  )
  return stream
}

// For synchronous SSR
export function renderToString(url: string) {
  return renderToString(
    <StrictMode>
      <StaticRouter location={url}>
        <App />
      </StaticRouter>
    </StrictMode>,
  )
}
```

#### 7.3 SSR Server

```typescript
// server.js — production SSR server
import express from 'express'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const app = express()

// Serve static files from client build
app.use(
  '/client/assets',
  express.static(path.resolve(__dirname, 'dist/client/assets'), {
    maxAge: 31536000,
    immutable: true,
  }),
)
app.use('/client', express.static(path.resolve(__dirname, 'dist/client')))

// Import SSR renderer
const { render } = await import('./dist/server/entry-server.mjs')

app.get('*', async (req, res) => {
  const url = req.originalUrl
  const template = fs.readFileSync(
    path.resolve(__dirname, 'dist/client/index.html'),
    'utf-8',
  )

  try {
    // React streaming SSR
    const stream = render(url)
    const htmlStart = template.indexOf('<div id="root">')
    const head = template.slice(0, htmlStart)
    const tail = template.slice(htmlStart)

    res.setHeader('Content-Type', 'text/html')
    res.write(head)
    stream.pipe(res, { end: false })
    stream.on('end', () => {
      res.write(tail)
      res.end()
    })
  } catch (err) {
    console.error(err)
    res.status(500).send('Internal Server Error')
  }
})

app.listen(3000, () => {
  console.log('SSR server listening on http://localhost:3000')
})
```

#### 7.4 SSR with Data Fetching

```typescript
// src/entry-server.tsx — with data preloading
import { StaticRouter } from 'react-router-dom/server'
import { renderToString } from 'react-dom/server'
import App from './App'

// Data fetching context
interface SSRContext {
  url: string
  state: Record<string, unknown>
}

export async function render(url: string): Promise<{ html: string; state: Record<string, unknown> }> {
  const ctx: SSRContext = { url, state: {} }

  const html = renderToString(
    <StaticRouter location={url}>
      <App ssrContext={ctx} />
    </StaticRouter>,
  )

  return { html, state: ctx.state }
}

// In components:
// function Dashboard({ ssrContext }: { ssrContext?: SSRContext }) {
//   useEffect(() => {
//     if (!ssrContext) fetchData()
//   }, [])
//   if (ssrContext) {
//     ssrContext.state.dashboard = fetchDataSync()
//   }
//   // ...
// }
```

---

### 8. Library Mode

#### 8.1 Configuration

```typescript
// vite.config.ts — build a library
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import dts from 'vite-plugin-dts'
import path from 'node:path'

export default defineConfig({
  plugins: [
    react(),
    // Generate .d.ts files
    dts({
      insertTypesEntry: true,
      include: ['src'],
      exclude: ['src/**/*.test.*', 'src/**/*.stories.*'],
      rollupTypes: true, // rollup types into single file (TS 5+)
    }),
  ],
  build: {
    // Library mode
    lib: {
      // Entry point
      entry: path.resolve(__dirname, 'src/index.ts'),
      // Name for UMD/IIFE globals
      name: 'MyLibrary',
      // Output formats
      formats: ['es', 'cjs', 'umd'],
      // File names for each format
      fileName: (format) => {
        switch (format) {
          case 'es':
            return 'my-library.mjs'
          case 'cjs':
            return 'my-library.cjs'
          case 'umd':
            return 'my-library.umd.js'
          default:
            return 'my-library.[format].js'
        }
      },
    },
    // Externalize peer deps (don't bundle React)
    rollupOptions: {
      external: [
        'react',
        'react-dom',
        'react/jsx-runtime',
      ],
      output: {
        // Globals for UMD/IIFE builds
        globals: {
          react: 'React',
          'react-dom': 'ReactDOM',
          'react/jsx-runtime': 'jsxRuntime',
        },
        // Preserve modules structure
        preserveModules: false,
        // Sourcemaps for library
        sourcemap: true,
      },
    },
    // Don't empty outDir for lib builds
    emptyOutDir: true,
    // Sourcemap
    sourcemap: true,
    // Minify for distribution
    minify: 'esbuild',
  },
})
```

#### 8.2 Library Entry Point

```typescript
// src/index.ts — library public API
export { Button } from './components/Button'
export { Input } from './components/Input'
export { Card, CardHeader, CardContent } from './components/Card'
export { ThemeProvider, useTheme } from './context/ThemeContext'
export { cn } from './lib/utils'

// Types
export type { ButtonProps } from './components/Button'
export type { InputProps } from './components/Input'
export type { Theme } from './types'

// Internal types — not exported
```

#### 8.3 Package.json for Libraries

```jsonc
{
  "name": "@my-company/my-library",
  "version": "1.0.0",
  "type": "module",
  "files": ["dist"],
  "main": "./dist/my-library.cjs",
  "module": "./dist/my-library.mjs",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "import": {
        "types": "./dist/index.d.mts",
        "default": "./dist/my-library.mjs"
      },
      "require": {
        "types": "./dist/index.d.ts",
        "default": "./dist/my-library.cjs"
      }
    },
    "./styles.css": "./dist/styles.css"
  },
  "sideEffects": ["**/*.css"],
  "scripts": {
    "build": "vite build",
    "prepublishOnly": "npm run build"
  },
  "peerDependencies": {
    "react": "^18.0.0 || ^19.0.0",
    "react-dom": "^18.0.0 || ^19.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.0",
    "vite": "^6.0.0",
    "vite-plugin-dts": "^4.0.0"
  }
}
```

#### 8.4 Multiple Entry Points (Subpath Exports)

```typescript
// vite.config.ts — multi-entry library
import { defineConfig } from 'vite'
import dts from 'vite-plugin-dts'
import path from 'node:path'

export default defineConfig({
  plugins: [dts({ rollupTypes: true })],
  build: {
    lib: {
      entry: {
        index: path.resolve(__dirname, 'src/index.ts'),
        components: path.resolve(__dirname, 'src/components/index.ts'),
        hooks: path.resolve(__dirname, 'src/hooks/index.ts'),
        utils: path.resolve(__dirname, 'src/utils/index.ts'),
      },
      formats: ['es', 'cjs'],
      fileName: (format, entryName) => {
        const ext = format === 'es' ? 'mjs' : 'cjs'
        return `${entryName}.${ext}`
      },
    },
    rollupOptions: {
      external: ['react', 'react-dom'],
    },
  },
})
```

```jsonc
// package.json — subpath exports
{
  "exports": {
    ".": {
      "import": "./dist/index.mjs",
      "require": "./dist/index.cjs"
    },
    "./components": {
      "import": "./dist/components.mjs",
      "require": "./dist/components.cjs"
    },
    "./hooks": {
      "import": "./dist/hooks.mjs",
      "require": "./dist/hooks.cjs"
    },
    "./utils": {
      "import": "./dist/utils.mjs",
      "require": "./dist/utils.cjs"
    },
    "./styles.css": "./dist/styles.css"
  }
}
```

---

### 9. Testing with Vitest

#### 9.1 Configuration

```typescript
// vitest.config.ts — or merge with vite.config.ts
import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      // Test environment
      environment: 'jsdom',
      // Globals like describe, it, expect
      globals: true,
      // Setup files
      setupFiles: ['./src/test/setup.ts'],
      // File patterns
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      exclude: ['node_modules', 'dist'],
      // Coverage
      coverage: {
        provider: 'v8',       // 'v8' (built-in) or 'istanbul'
        reporter: ['text', 'json', 'html', 'lcov'],
        include: ['src'],
        exclude: [
          'src/**/*.test.*',
          'src/**/*.spec.*',
          'src/test/**',
          'src/**/*.d.ts',
          'src/**/index.ts',
        ],
        thresholds: {
          branches: 80,
          functions: 80,
          lines: 80,
          statements: 80,
        },
        // Report per-file
        reportsDirectory: './coverage',
      },
      // Test timeout
      testTimeout: 10_000,
      // Hooks timeout
      hookTimeout: 10_000,
      // Retry flaky tests
      retry: 2,
      // Parallel
      pool: 'forks',          // 'forks' | 'threads'
      poolOptions: {
        threads: {
          singleThread: false,
        },
        forks: {
          singleFork: false,
        },
      },
      // Sequence
      sequence: {
        shuffle: true,        // randomize test order
        seed: Date.now(),
      },
      // Update snapshots
      update: false,
      // API mocking
      mocks: {
        clearMocks: true,
        restoreMocks: true,
      },
      // Environment options
      environmentOptions: {
        jsdom: {
          url: 'http://localhost:3000',
        },
      },
      // CSS handling
      css: {
        modules: {
          classNameStrategy: 'non-scoped', // for testing CSS modules
        },
      },
      // Alias (inherits from vite.config.ts)
      alias: {
        '@': '/src',
      },
    },
  }),
)
```

#### 9.2 Basic Test Examples

```typescript
// src/utils/format.test.ts
import { describe, it, expect } from 'vitest'
import { formatDate, parseISO } from './format'

describe('formatDate', () => {
  it('formats ISO date correctly', () => {
    expect(formatDate('2026-05-17')).toBe('May 17, 2026')
  })

  it('handles invalid dates', () => {
    expect(formatDate('invalid')).toBe('Invalid Date')
  })
})
```

#### 9.3 React Component Testing

```typescript
// src/test/setup.ts
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
})
```

```typescript
// src/components/Button.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Button } from './Button'

describe('Button', () => {
  it('renders children', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByText('Click me')).toBeInTheDocument()
  })

  it('calls onClick when clicked', () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Click</Button>)
    fireEvent.click(screen.getByText('Click'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled</Button>)
    expect(screen.getByText('Disabled')).toBeDisabled()
  })

  it('applies variant classes', () => {
    const { rerender } = render(<Button variant="primary">Primary</Button>)
    expect(screen.getByText('Primary')).toHaveClass('bg-blue-500')

    rerender(<Button variant="secondary">Secondary</Button>)
    expect(screen.getByText('Secondary')).toHaveClass('bg-gray-500')
  })
})
```

#### 9.4 Async Testing

```typescript
// src/hooks/useData.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useData } from './useData'

describe('useData', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches and returns data', async () => {
    const mockData = { id: 1, name: 'Test' }
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(mockData),
      ok: true,
    })

    const { result } = renderHook(() => useData('/api/test'))

    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.data).toEqual(mockData)
    })

    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('handles fetch error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useData('/api/test'))

    await waitFor(() => {
      expect(result.current.error).toBe('Network error')
    })
  })
})
```

#### 9.5 Vitest Workspace

```typescript
// vitest.workspace.ts
import { defineWorkspace } from 'vitest/config'

export default defineWorkspace([
  // Unit tests (jsdom)
  {
    test: {
      name: 'unit',
      root: './src',
      environment: 'jsdom',
      include: ['**/*.test.ts', '**/*.test.tsx'],
    },
  },
  // Integration tests (node)
  {
    test: {
      name: 'integration',
      root: './tests',
      environment: 'node',
      include: ['**/*.test.ts'],
      globalSetup: './tests/setup.ts',
    },
  },
  // Browser tests (experimental)
  {
    test: {
      name: 'browser',
      browser: {
        enabled: true,
        provider: 'playwright',
        instances: [
          { browser: 'chromium' },
        ],
      },
    },
  },
])
```

#### 9.6 Benchmark Mode

```typescript
// src/utils/sort.bench.ts
import { bench, describe } from 'vitest'

describe('sorting algorithms', () => {
  const data = Array.from({ length: 10000 }, () =>
    Math.floor(Math.random() * 10000)
  )

  bench('Array.sort', () => {
    data.slice().sort((a, b) => a - b)
  })

  bench('quick sort', () => {
    quickSort(data.slice())
  })
})

// Run: npx vitest bench
```

---

### 10. Performance Optimization

#### 10.1 Dev Server Cold Start

```typescript
export default defineConfig({
  // Reduce the number of files scanned
  server: {
    // Exclude directories from file watching
    watch: {
      ignored: [
        '**/node_modules/**',
        '**/dist/**',
        '**/.git/**',
        '**/coverage/**',
        '**/*.test.*',
        '**/*.spec.*',
      ],
      // Use polling if filesystem events are unreliable (Docker/WSL)
      usePolling: false,
      interval: 100,
    },
    // Warmup frequently used modules
    warmup: {
      clientFiles: [
        './src/main.tsx',
        './src/App.tsx',
        './src/routes.tsx',
      ],
    },
  },

  // Pre-bundle strategy
  optimizeDeps: {
    // Include common deps to pre-bundle them on startup
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      'lodash-es',
      'date-fns',
    ],
    // Disable dep discovery scan — use explicit include
    // (faster startup but must keep include list updated)
    // disabled: 'build' | 'dev'
    disabled: false,
  },
})
```

#### 10.2 Build Time Optimization

```typescript
export default defineConfig({
  build: {
    // Use esbuild for minification (20-40x faster than terser)
    minify: 'esbuild',

    // Disable sourcemaps for faster build
    sourcemap: false,

    // Don't compress during build (nginx/CDN does this)
    reportCompressedSize: false,

    // Disable CSS code splitting if not needed
    cssCodeSplit: true,

    // Larger chunk size limit reduces number of chunks
    rollupOptions: {
      output: {
        experimentalMinChunkSize: 100000,   // 100KB min chunk size
      },
    },
  },

  // Enable SWC instead of Babel for React (10x faster)
  // plugin-react-swc
})

// Build with --debug for timing info
// vite build --debug

// Profile build
// DEBUG="vite:build*" vite build
// cross-env VITE_PROFILE=vite-build-profile.json vite build
```

#### 10.3 Dependency Optimization Tuning

```typescript
export default defineConfig({
  optimizeDeps: {
    // Hold dependencies in cache longer
    // Forces re-optimization only if deps change

    // Force specific deps to use ESM
    needsInterop: [
      'some-cjs-lib',
      'another-lib-that-misidentifies-its-module-type',
    ],

    // Exclude if causing issues
    exclude: [
      '@firebase/app',
      'some-large-dep-that-shouldnt-be-pre-bundled',
    ],

    // esbuild target for optimized deps
    esbuildOptions: {
      target: 'es2020',
    },
  },
})
```

#### 10.4 Bundle Analysis

```bash
# Visualize bundle composition
npm i -D rollup-plugin-visualizer
```

```typescript
// vite.config.ts
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig({
  plugins: [
    visualizer({
      filename: 'dist/stats.html',
      open: true,                // auto-open in browser
      gzipSize: true,
      brotliSize: true,
      template: 'treemap',       // 'treemap' | 'sunburst' | 'network'
    }),
  ],
})
```

---

### 11. Migration Guides

#### 11.1 CRA → Vite

```typescript
// 1. Install Vite
// npm remove react-scripts
// npm i -D vite @vitejs/plugin-react

// 2. Create vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  server: { port: 3000 },
})

// 3. Move index.html to root (from public/)
// index.html — must have <script type="module" src="/src/index.tsx">

// 4. Update env variables
// REACT_APP_* → VITE_*
// process.env.REACT_APP_API_URL → import.meta.env.VITE_API_URL

// 5. Update tsconfig.json
// {
//   "compilerOptions": {
//     "types": ["vite/client"],
//     "module": "ESNext",
//     "moduleResolution": "bundler",
//     "target": "ES2020"
//   }
// }

// 6. Update scripts in package.json
// "dev": "vite",
// "build": "tsc && vite build",
// "preview": "vite preview"

// 7. Fix imports
// SVG: import { ReactComponent as Logo } from './logo.svg'
//    → import Logo from './logo.svg?react'
// Images: import logo from './logo.png'
//    → still works (Vite handles assets natively)

// 8. Proxy
// Setup proxy in vite.config.ts instead of package.json "proxy" field

// 9. Remove serviceWorker registration
// CRA's serviceWorker.js is not needed — use vite-plugin-pwa instead

// 10. CSS Modules
// .module.css filenames work identically
```

#### 11.2 Webpack → Vite

```typescript
// Key differences:
//    Webpack            → Vite
//    babel-loader        → esbuild (or SWC)
//    css-loader          → native CSS handling
//    file-loader         → native asset handling
//    html-webpack-plugin → index.html in root
//    DefinePlugin        → define in config
//    MiniCssExtractPlugin→ built-in CSS splitting
//    TerserPlugin        → esbuild minification

// Loader equivalents:
// ts-loader / babel-loader → esbuild (default) or SWC
// svg-inline-loader       → vite-plugin-svgr
// svgo-loader             → vite-plugin-svgr (includes SVGO)
// image-webpack-loader    → vite-plugin-imagemin
// webpack-manifest-plugin → built-in manifest

// webpack.config.js → vite.config.ts
// const webpackConfig = {
//   entry: './src/index.tsx',
//   output: { path: './dist' },
//   module: { rules: [...] },
//   plugins: [...],
//   resolve: { alias: {...} },
//   devServer: { ... },
// }

// Becomes:
// export default defineConfig({
//   plugins: [react()],
//   resolve: { alias: {...} },
//   server: { ... },
//   build: { outDir: 'dist' },
// })
```

#### 11.3 Migration Cookbook — Common Patterns

```typescript
// CRA: import { ReactComponent as Icon } from './icon.svg'
// Vite: import Icon from './icon.svg?react'
// (requires vite-plugin-svgr)

// CRA: process.env.PUBLIC_URL + '/static/image.png'
// Vite: import imageUrl from './image.png'
//    or: new URL('./image.png', import.meta.url).href

// CRA: require.context('./icons', false, /\.svg$/)
// Vite: const icons = import.meta.glob('./icons/*.svg')
//    for (const [path, loader] of Object.entries(icons)) {
//      const module = await loader()
//    }

// CRA: lazy(() => import('./Dashboard'))
// Vite: same — works identically

// CRA: CSS Modules: styles.someClass
// Vite: same — works identically

// CRA: Sass variables — @use 'styles/variables' as *;
// Vite: same, but configure via css.preprocessorOptions

// CRA: process.env.NODE_ENV
// Vite: import.meta.env.MODE (or import.meta.env.DEV / PROD)

// CRA: .env.development.local
// Vite: same — file priority is identical

// CRA: sourceMap in config
// Vite: build.sourcemap

// CRA: proxy in package.json
// Vite: server.proxy in vite.config.ts
```

---

### 12. File Convention

```
my-project/
├── index.html                  # Entry HTML with <script type="module" src="/src/main.tsx">
├── vite.config.ts              # Vite configuration
├── vitest.config.ts            # Vitest configuration (optional, can merge with above)
├── tsconfig.json               # TypeScript config
├── tsconfig.node.json          # TS config for vite.config.ts
├── postcss.config.js           # PostCSS config (auto-detected)
├── .env                        # Default env variables
├── .env.development            # Dev-specific env
├── .env.production             # Production-specific env
├── .env.local                  # Local overrides (git-ignored)
├── .env.staging                # Staging mode (vite build --mode staging)
├── public/                     # Served as-is at root
│   ├── favicon.ico
│   ├── robots.txt
│   └── manifest.json
├── src/
│   ├── main.tsx                # Entry point (client)
│   ├── entry-server.tsx        # Entry point (SSR) — optional
│   ├── App.tsx                 # Root component
│   ├── vite-env.d.ts           # Vite client types + ImportMetaEnv
│   ├── components/             # Shared components
│   │   ├── ui/                 # Primitive UI components
│   │   └── layout/             # Layout components
│   ├── pages/                  # Route pages
│   ├── hooks/                  # Custom React hooks
│   ├── lib/                    # Utility libraries
│   ├── stores/                 # State management
│   ├── services/               # API services
│   ├── types/                  # Shared TypeScript types
│   ├── assets/                 # Static assets (images, fonts)
│   ├── styles/                 # Global styles
│   │   ├── globals.css
│   │   └── variables.css
│   └── test/                   # Test setup
│       ├── setup.ts
│       └── mocks/
├── tests/                      # Integration/E2E tests
├── dist/                       # Build output (git-ignored)
│   ├── client/                 # SSR client build
│   └── server/                 # SSR server build
└── scripts/                    # Build/deploy scripts
```

---

### 13. Anti-Patterns

#### ❌ Disabling Dependency Optimization

```typescript
// ❌ BAD — disabling dep optimization cripples dev performance
export default defineConfig({
  optimizeDeps: {
    disabled: 'dev',        // causes: 1000s of requests instead of bundled deps
    exclude: ['react'],     // causes: React HMR will be slow, lots of requests
  },
})

// ✅ GOOD — let Vite handle dep optimization; only exclude if absolutely needed
export default defineConfig({
  optimizeDeps: {
    include: ['react', 'react-dom'],
    exclude: ['@firebase/app'], // only when it causes issues
  },
})
```

#### ❌ Misconfigured Proxy

```typescript
// ❌ BAD — missing changeOrigin, wrong target
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:3000',  // no changeOrigin → CORS issues
    },
  },
})

// ❌ BAD — accidental path rewrite
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        rewrite: (path) => path.replace(/^\/api/, ''),  // strips /api prefix!
        // Client expects /api/users but server receives /users
      },
    },
  },
})

// ✅ GOOD
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
        // No rewrite — /api/users → /api/users
      },
    },
  },
})
```

#### ❌ Large Entry Points

```typescript
// ❌ BAD — importing everything in entry point
import { Button } from '@mui/material'
import { Chart } from 'chart.js'
import { AllCommunityModule } from 'ag-grid-community'
// All imported even if not used on first page

// ✅ GOOD — lazy load heavy components
import { lazy } from 'react'

const HeavyChart = lazy(() => import('./charts/HeavyChart'))
const DataGrid = lazy(() => import('./components/DataGrid'))
```

#### ❌ Importing from Wrong Paths

```typescript
// ❌ BAD — full package imports instead of subpath
import { format } from 'date-fns'         // ← fine
import { z } from 'zod'                   // ← fine
import { isString } from 'lodash-es'       // ← fine (tree-shakable)

import _ from 'lodash'                     // ❌ BAD — full lodash, no tree-shaking
import { Button } from '@mui/material'     // ❌ BAD — full MUI import
// ✅ use: import Button from '@mui/material/Button'

// ❌ BAD — importing from barrel files that re-export everything
import { Button } from '@/components'      // barrel exports all components

// ✅ GOOD — import directly
import { Button } from '@/components/Button'
```

#### ❌ Overriding Vite Defaults

```typescript
// ❌ BAD — disabling useful defaults
export default defineConfig({
  css: {
    modules: {
      localsConvention: 'camelCaseOnly',  // fine, but:
      generateScopedName: '[name]__[local]___[hash:base64:5]',  // too short hash → collisions
    },
  },
})

// ❌ BAD — setting build.target too low
export default defineConfig({
  build: {
    target: 'es2015',      // causes: massive polyfill overhead
  },
})
// ✅ es2020 is the default for a reason
```

#### ❌ Forgetting to Externalize in Library Mode

```typescript
// ❌ BAD — library bundles React!
export default defineConfig({
  build: {
    lib: { entry: 'src/index.ts' },
    // missing rollupOptions.external
  },
})

// ✅ GOOD
export default defineConfig({
  build: {
    lib: { entry: 'src/index.ts' },
    rollupOptions: {
      external: ['react', 'react-dom', 'react/jsx-runtime'],
    },
  },
})
```

#### ❌ Not Using `@vitejs/plugin-react-swc` for Large Projects

```typescript
// ❌ BAD — using Babel for large project (slower transforms)
// vite.config.ts with default @vitejs/plugin-react (Babel)

// ✅ GOOD — SWC is 10-20x faster for React transforms
// npm i -D @vitejs/plugin-react-swc
import react from '@vitejs/plugin-react-swc'

export default defineConfig({
  plugins: [react()],
})
```

---

### 14. Implementation Checklist

#### Project Setup
- [ ] `npm create vite@latest` or manual setup
- [ ] Install framework plugin (`@vitejs/plugin-react`, etc.)
- [ ] Configure `vite.config.ts` with resolve aliases, proxy, build options
- [ ] Set up `tsconfig.json` with `"types": ["vite/client"]`
- [ ] Verify `index.html` has `<script type="module" src="/src/main.tsx">`
- [ ] Add `vite-env.d.ts` with augmented `ImportMetaEnv`

#### Development
- [ ] Configure `server.proxy` for API requests
- [ ] Set up environment files (`.env`, `.env.development`, `.env.production`)
- [ ] Enable HMR — verify React Fast Refresh works
- [ ] Configure `optimizeDeps` for large projects
- [ ] Add `server.warmup` for faster cold start
- [ ] Enable TypeScript checker plugin (`vite-plugin-checker`)
- [ ] Set up `unplugin-auto-import` for hooks/utils
- [ ] Configure SVG handling (`vite-plugin-svgr` or `@svgr/rollup`)

#### Build Optimization
- [ ] Configure `manualChunks` for vendor splitting
- [ ] Set up lazy loading for route-level code splitting
- [ ] Enable `esbuild` minification (default)
- [ ] Analyze bundle with `rollup-plugin-visualizer`
- [ ] Configure `chunkSizeWarningLimit` appropriately
- [ ] Set `build.target` to modern browsers (`es2020`)
- [ ] Add `vite-plugin-compression` for brotli/gzip

#### CSS & Assets
- [ ] Configure PostCSS/SCSS/Less processors
- [ ] Set up CSS Modules naming convention
- [ ] Configure `css.preprocessorOptions` if using Sass/Less
- [ ] Enable LightningCSS for faster CSS processing
- [ ] Move static assets to `public/` or import directly

#### PWA
- [ ] Add `vite-plugin-pwa` with Workbox
- [ ] Configure manifest icons and metadata
- [ ] Set up runtime caching for API calls
- [ ] Test offline functionality

#### SSR (if applicable)
- [ ] Create `src/entry-client.tsx` for hydration
- [ ] Create `src/entry-server.tsx` for server render
- [ ] Configure `ssr.external` and `ssr.noExternal`
- [ ] Set up SSR server with Express/Fastify
- [ ] Implement data preloading for SSR
- [ ] Add streaming SSR support

#### Library Mode (if applicable)
- [ ] Configure `build.lib` with entry and formats
- [ ] Externalize peerDependencies
- [ ] Add `vite-plugin-dts` for type generation
- [ ] Set up `exports` in package.json
- [ ] Verify tree-shaking with `sideEffects` flag
- [ ] Add subpath exports for multi-entry libraries

#### Testing
- [ ] Install `vitest` and `@testing-library/react`
- [ ] Configure `vitest.config.ts` with environment
- [ ] Set up test setup file with cleanup
- [ ] Add coverage thresholds
- [ ] Create workspace config for multi-environment tests
- [ ] Write component tests with Testing Library
- [ ] Write hook tests with `renderHook`
- [ ] Add integration tests

#### Deployment
- [ ] Configure `build.outDir`
- [ ] Set `base` path for sub-path deployment
- [ ] Add `build.sourcemap` strategy
- [ ] Configure CDN headers for immutable assets
- [ ] Build preview (`vite preview`) before deploy
- [ ] Verify env variables at build time vs runtime

#### Migration (if migrating)
- [ ] CRA: Move `index.html` to root, update `REACT_APP_*` → `VITE_*`
- [ ] Webpack: Replace loaders with Vite equivalents
- [ ] Verify all dynamic imports work
- [ ] Test CSS Modules compatibility
- [ ] Update CI/CD scripts

#### Final Checks
- [ ] `npm run dev` — no errors, HMR works
- [ ] `npm run build` — no errors, bundle sizes reasonable
- [ ] `npm run preview` — production build works
- [ ] `npx vitest run` — all tests pass
- [ ] Lighthouse audit — good scores
- [ ] Bundle analysis — no unexpected large chunks

---

### 15. TypeScript Integration

```typescript
// src/vite-env.d.ts — required for all Vite + TS projects
/// <reference types="vite/client" />

// Augment for custom env variables
interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_SENTRY_DSN: string
  readonly MODE: string
  readonly DEV: boolean
  readonly PROD: boolean
  readonly SSR: boolean
  readonly BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// For Vite plugin types
declare module 'virtual:*' {
  const content: any
  export default content
}

// For ?raw imports
declare module '*?raw' {
  const content: string
  export default content
}

// For ?url imports
declare module '*?url' {
  const url: string
  export default url
}

// For ?worker imports
declare module '*?worker' {
  const worker: {
    new (): Worker
  }
  export default worker
}

// For ?import (explicit ESM)
declare module '*?import' {
  const content: any
  export default content
}
```

---

### 16. Common Troubleshooting

#### 16.1 HMR Not Working

```bash
# Check Vite HMR
# 1. Verify WebSocket connection in browser devtools (Network → WS)
# 2. Check for hmr: true in server config
# 3. Ensure Vite is not behind a proxy that strips WebSocket headers
# 4. Check browser console for HMR errors

# Solution — force WebSocket to use correct port
export default defineConfig({
  server: {
    hmr: {
      clientPort: 443,           # if behind HTTPS reverse proxy
      protocol: 'wss',           # force secure WebSocket
      host: 'example.com',
      port: 443,
    },
  },
})
```

#### 16.2 CORS Issues with Dev Server

```typescript
// Solution 1: Use proxy instead of CORS
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
    },
  },
})

// Solution 2: Enable CORS on dev server (for CDN assets)
export default defineConfig({
  server: {
    cors: {
      origin: ['http://localhost:3000', 'https://myapp.example.com'],
      methods: ['GET', 'POST'],
      credentials: true,
    },
  },
})
```

#### 16.3 Build Fails — Out of Memory

```bash
# Increase Node memory
# package.json
# "build": "NODE_OPTIONS=--max-old-space-size=4096 vite build"
# Windows:
# "build": "set NODE_OPTIONS=--max-old-space-size=4096 && vite build"

# Or reduce parallel work
export default defineConfig({
  build: {
    rollupOptions: {
      maxParallelFileOps: 20,  # default: 20
      maxParallelFileReads: 10, # default: read operations
    },
  },
})
```

#### 16.4 Dynamic Import Paths Not Working

```typescript
// ❌ BAD — dynamic import with variable path
// Vite must know import paths at build time for code splitting
const page = 'Dashboard'
const Module = await import(`./pages/${page}`)  // ❌ may not work

// ✅ GOOD — map known paths
const pages = {
  Dashboard: () => import('./pages/Dashboard'),
  Settings: () => import('./pages/Settings'),
}
const Module = await pages[page]()

// ✅ GOOD — use import.meta.glob
const pages = import.meta.glob('./pages/*.tsx')
const loader = pages[`./pages/${page}.tsx`]
if (loader) {
  const Module = await loader()
}
```

#### 16.5 CSS Modules Typings

```typescript
// For TypeScript CSS Modules support:
// 1. Add to tsconfig.json
// {
//   "compilerOptions": {
//     "types": ["vite/client"]
//   }
// }

// 2. Or create global type declaration
// src/types/css-modules.d.ts
declare module '*.module.css' {
  const classes: { readonly [key: string]: string }
  export default classes
}

declare module '*.module.scss' {
  const classes: { readonly [key: string]: string }
  export default classes
}

declare module '*.module.less' {
  const classes: { readonly [key: string]: string }
  export default classes
}
```

#### 16.6 Environment Variables Not Available

```bash
# Check:
# 1. Prefix is VITE_ (not VITE_APP_ or REACT_APP_)
# 2. Variables are in .env files at project root (not src/)
# 3. Dev server was restarted after creating .env
# 4. Use import.meta.env.VITE_XXX (not process.env in browser code)

# .env file location:
# ❌ src/.env          — wrong, Vite reads from project root
# ✅ .env              — right, at project root
```

---

### 17. Vite 6 vs Vite 7 Key Differences

| Feature | Vite 6 | Vite 7 |
|---------|--------|--------|
| Minimum Node | 18+ | 20+ |
| Rollup | 4.x | 4.x (upgraded) |
| esbuild | 0.21+ | 0.24+ |
| HMR | WebSocket | WebSocket + SSE fallback |
| SSR | Built-in | Built-in (improved) |
| Environment API | Basic | Enhanced (experimental) |
| Asset handling | Default | Improved SVG/Sourcemap |
| Build performance | Baseline | ~15% faster |
| CSS | PostCSS/LightningCSS | LightningCSS default |

```typescript
// Vite 7 features (when available)
export default defineConfig({
  // Environment API (experimental in Vite 7)
  environments: {
    client: {
      build: { outDir: 'dist/client' },
    },
    ssr: {
      build: { outDir: 'dist/server' },
    },
  },

  // Improved build defaults
  build: {
    cssMinify: 'lightningcss',      // default in Vite 7
    modulePreload: true,
  },
})
```

---

### References

- Vite Docs: https://vite.dev/guide/
- GitHub: https://github.com/vitejs/vite
- Plugins: https://github.com/vitejs/awesome-vite
- Vitest: https://vitest.dev/
- Migrate from CRA: https://vite.dev/guide/migration/
