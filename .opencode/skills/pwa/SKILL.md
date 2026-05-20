---
name: pwa
description: Use when building or optimizing Progressive Web Apps — Web App Manifest, Service Worker lifecycle, Workbox integration, caching strategies, offline support, Background Sync, Web Push notifications, Vite/Next.js PWA configuration, Lighthouse PWA audit, and production deployment patterns.
license: MIT
compatibility: opencode
metadata:
  audience: frontend-developers
  domain: frontend
  paradigm: progressive-enhancement
  capabilities:
    - service-worker-lifecycle
    - workbox-integration
    - caching-strategies
    - offline-support
    - background-sync
    - web-push-notifications
    - manifest-generation
    - lighthouse-audit
    - vite-plugin-pwa
    - next-pwa
  integrates_with:
    - frontend-react
    - vite
    - typescript
    - backend-nodejs
---

# Skill: pwa

## PWA Mastery — Service Worker, Workbox, Caching, Offline, Push, and Production Patterns

### Core Philosophy

A Progressive Web App is not a technology. It is a **capability bridge** between native apps and the web. The goal: make the web app feel like a first-class citizen on the user's device — installable, reliable offline, push-notifiable, and fast on repeat visits. Every PWA feature is progressive: it enhances the experience on capable browsers and degrades gracefully on others.

PWA = **Web App Manifest** (installability) + **Service Worker** (offline/performance) + **HTTPS** (security) + **Responsive Design** (usability).

```
┌──────────────────────────────────────────────────────────────────┐
│                        PWA CAPABILITY STACK                        │
│                                                                    │
│  LAYER 4: Re-engagement                                           │
│  ┌──────────────────────────────────────────────┐                 │
│  │ Push Notifications  │  Badging  │  Share API  │                 │
│  └──────────┬───────────────────────────────────┘                 │
│             ▼                                                      │
│  LAYER 3: Offline & Reliability                                   │
│  ┌──────────────────────────────────────────────┐                 │
│  │ Service Worker  │  Cache API  │  IndexedDB    │                 │
│  │ Background Sync │  Periodic Sync              │                 │
│  └──────────┬───────────────────────────────────┘                 │
│             ▼                                                      │
│  LAYER 2: Installability                                         │
│  ┌──────────────────────────────────────────────┐                 │
│  │ Web App Manifest  │  beforeinstallprompt      │                 │
│  └──────────┬───────────────────────────────────┘                 │
│             ▼                                                      │
│  LAYER 1: Foundation                                             │
│  ┌──────────────────────────────────────────────┐                 │
│  │ HTTPS  │  Responsive Design  │  Cross-browser │                 │
│  └──────────────────────────────────────────────┘                 │
└──────────────────────────────────────────────────────────────────┘
```

---

### 1. PWA Fundamentals

#### 1.1 What Makes a PWA

A web app is a PWA when it meets these core criteria:

| Criteria | Requirement | Why |
|----------|-------------|-----|
| HTTPS | TLS-enabled origin | Service Worker requires secure context |
| Web App Manifest | `manifest.json` linked in `<head>` | Enables "Add to Home Screen" |
| Service Worker | Registered SW with at least offline fallback | Enables offline, caching, push |
| Responsive | Works on mobile + desktop | Installable on all form factors |
| Cross-browser | Works on all major browsers | Progressive enhancement |

#### 1.2 Browser Support Matrix

```
Feature                  Chrome  Edge  Firefox  Safari  Samsung Internet
─────────────────────────────────────────────────────────────────────
Service Worker            ✓       ✓     ✓        16.4+   ✓
Manifest                  ✓       ✓     ✓        16.4+   ✓
Cache API                 ✓       ✓     ✓        16.4+   ✓
Push Notifications        ✓       ✓     ✓(1)     ✗(2)    ✓
Background Sync           ✓       ✓     ✗        ✗       ✓
Periodic Sync             ✓(80+)  ✓     ✗        ✗       ✗
Navigation Preload        ✓       ✓     ✓         ✗      ✓
Badging API               ✓       ✓     ✗        ✗       ✗
File System Access        ✓(86+)  ✓     ✗        ✗       ✗

(1) Firefox uses its own push service (autopush).
(2) Safari supports push via APNs on macOS 13+ / iOS 16.4+, but requires
    service worker registration + user gesture.
```

#### 1.3 Detecting PWA Support

```typescript
// Feature detection
const supportsSW = 'serviceWorker' in navigator
const supportsManifest = 'manifest' in document.createElement('link')
const supportsPush = 'PushManager' in window
const supportsSync = 'SyncManager' in window
const supportsPeriodicSync = 'PeriodicSyncManager' in window
const supportsBadge = 'setAppBadge' in navigator

// Check if running as installed PWA
const isInstalled = window.matchMedia('(display-mode: standalone)').matches
  || window.navigator.standalone === true  // Safari iOS

// Check if running via service worker
const isControlled = navigator.serviceWorker?.controller !== null
```

---

### 2. Web App Manifest

#### 2.1 manifest.json — Full Schema

```json
{
  "$schema": "https://json.schemastore.org/web-manifest-combined.json",
  "name": "Kapuas Carbon Project",
  "short_name": "Kapuas Carbon",
  "description": "Project Dokumen Deskripsi Karbon Kapuas",
  "start_url": "/?source=pwa",
  "scope": "/",
  "display": "standalone",
  "display_override": ["window-controls-overlay", "standalone"],
  "orientation": "portrait-primary",
  "theme_color": "#1a6b3c",
  "background_color": "#ffffff",
  "categories": ["environment", "business", "finance"],
  "lang": "id",
  "dir": "ltr",
  "iarc_rating_id": "e8c15ad4-4d3c-4a5f-9b10-8f6d7a2b1c3e",

  "icons": [
    { "src": "/icons/icon-192x192.png", "sizes": "192x192", "type": "image/png", "purpose": "any" },
    { "src": "/icons/icon-512x512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" },
    { "src": "/icons/icon-192x192-maskable.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable" }
  ],

  "screenshots": [
    {
      "src": "/screenshots/desktop-1.jpg",
      "sizes": "1920x1080",
      "type": "image/jpeg",
      "form_factor": "wide",
      "label": "Dashboard utama Kapuas Carbon"
    },
    {
      "src": "/screenshots/mobile-1.jpg",
      "sizes": "750x1334",
      "type": "image/jpeg",
      "form_factor": "narrow",
      "label": "Halaman proyek di mobile"
    }
  ],

  "shortcuts": [
    {
      "name": "Dashboard",
      "short_name": "Dashboard",
      "description": "Lihat dashboard utama",
      "url": "/dashboard?source=pwa-shortcut",
      "icons": [{ "src": "/icons/shortcut-dashboard.png", "sizes": "96x96" }]
    },
    {
      "name": "Proyek Terbaru",
      "url": "/projects?source=pwa-shortcut"
    }
  ],

  "related_applications": [
    {
      "platform": "play",
      "url": "https://play.google.com/store/apps/details?id=com.kapuascarbon.app",
      "id": "com.kapuascarbon.app"
    }
  ],

  "prefer_related_applications": false,

  "handle_links": "preferred",
  "launch_handler": {
    "client_mode": "focus-existing"
  },

  "edge_side_panel": {}
}
```

#### 2.2 Field Reference

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `name` | ✓ | string | Full app name (max 45 chars recommended) |
| `short_name` | ✓ | string | Launcher label (max 12 chars recommended) |
| `start_url` | ✓ | string | Entry point, include query param for analytics |
| `display` | ✓ | enum | `fullscreen`, `standalone`, `minimal-ui`, `browser` |
| `icons` | ✓ | array | At least 192x192 + 512x512 with maskable |
| `description` | | string | Used in install dialog |
| `scope` | | string | Defaults to dir of manifest |
| `theme_color` | | string | Taskbar/address bar color |
| `background_color` | | string | Splash screen color |
| `categories` | | string[] | Store categorization |
| `screenshots` | | array | Store listing (at least 1 wide + 1 narrow for Google Play) |
| `shortcuts` | | array | Up to 4, shown on long-press/home context menu |
| `display_override` | | enum[] | `window-controls-overlay` for desktop PWA titlebar |

#### 2.3 Dynamic Manifest Generation

```typescript
// lib/manifest.ts
import { type Manifest } from 'vite-plugin-pwa'

interface ManifestConfig {
  name: string
  shortName: string
  description: string
  themeColor: string
  locale: string
}

export function generateManifest(config: ManifestConfig): Partial<Manifest> {
  const { name, shortName, description, themeColor, locale } = config

  return {
    name,
    short_name: shortName,
    description,
    start_url: `/?locale=${locale}&source=pwa`,
    scope: '/',
    display: 'standalone',
    display_override: ['window-controls-overlay', 'standalone'],
    orientation: 'portrait-primary',
    theme_color: themeColor,
    background_color: '#ffffff',
    lang: locale,
    dir: 'ltr',
    categories: ['environment', 'business'],
    icons: [
      {
        src: '/icons/icon-192x192.png',
        sizes: '192x192',
        type: 'image/png',
        purpose: 'any',
      },
      {
        src: '/icons/icon-512x512.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'any',
      },
      {
        src: '/icons/icon-512x512-maskable.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'maskable',
      },
    ],
    screenshots: [
      {
        src: `/screenshots/${locale}/desktop-1.jpg`,
        sizes: '1920x1080',
        type: 'image/jpeg',
        form_factor: 'wide',
        label: `${name} Dashboard`,
      },
      {
        src: `/screenshots/${locale}/mobile-1.jpg`,
        sizes: '750x1334',
        type: 'image/jpeg',
        form_factor: 'narrow',
        label: `${name} Mobile`,
      },
    ],
    shortcuts: [
      {
        name: 'Dashboard',
        short_name: 'Dashboard',
        url: `/dashboard?locale=${locale}&source=pwa-shortcut`,
      },
    ],
    prefer_related_applications: false,
  }
}
```

#### 2.4 Linking Manifest in HTML

```html
<!-- Required -->
<link rel="manifest" href="/manifest.json" />

<!-- iOS-specific meta tags (Safari ignores manifest icons) -->
<link rel="apple-touch-icon" href="/icons/icon-192x192.png" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<meta name="apple-mobile-web-app-title" content="Kapuas" />

<!-- Windows / IE -->
<meta name="application-name" content="Kapuas Carbon" />
<meta name="msapplication-TileColor" content="#1a6b3c" />
<meta name="msapplication-TileImage" content="/icons/icon-144x144.png" />

<!-- Theme color for browsers -->
<meta name="theme-color" content="#1a6b3c" media="(prefers-color-scheme: light)" />
<meta name="theme-color" content="#0a2e1a" media="(prefers-color-scheme: dark)" />
```

---

### 3. Service Worker Lifecycle

#### 3.1 Lifecycle Diagram

```
┌───────────────────────────────────────────────────────────────────┐
│                    SERVICE WORKER LIFECYCLE                         │
│                                                                     │
│  Browser loads page                                                 │
│         │                                                           │
│         ▼                                                           │
│  navigator.serviceWorker.register('/sw.js')                        │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────┐                                                    │
│  │  INSTALLING  │────► install event fires                          │
│  │  (installing)│     Cache static assets                          │
│  └──────┬──────┘     Skip waiting? → self.skipWaiting()            │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────┐     ┌───────────────────────┐                     │
│  │   INSTALLED  │     │  New version detected? │                    │
│  │   (waiting)  │────►│  Yes → skipWaiting()   │                    │
│  └──────┬──────┘     │  No → idle               │                   │
│         │            └───────────────────────┘                     │
│         ▼                                                           │
│  ┌─────────────┐                                                    │
│  │  ACTIVATING  │────► activate event fires                         │
│  │  (activating)│     Clean old caches                             │
│  └──────┬──────┘     clients.claim() → take control                │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────┐                                                    │
│  │  ACTIVATED   │     ┌───────────────────────┐                     │
│  │  (activated) │────►│ fetch / push / sync    │                    │
│  └─────────────┘     │ events fire            │                    │
│                       └───────────────────────┘                     │
│                                                                     │
│  ┌──────────────────────────────────────────────┐                   │
│  │  UPDATE FLOW                                  │                   │
│  │                                                │                   │
│  │  New SW detected (byte-diff)                   │                   │
│  │       │                                        │                   │
│  │       ▼                                        │                   │
│  │  Install event (new version)                    │                   │
│  │       │                                        │                   │
│  │       ▼                                        │                   │
│  │  Waiting (until all tabs close)                 │                   │
│  │       │                                        │                   │
│  │       ▼                                        │                   │
│  │  skipWaiting() → Activate                      │                   │
│  │       │                                        │                   │
│  │       ▼                                        │                   │
│  │  clients.claim() → pages reloaded               │                   │
│  └──────────────────────────────────────────────┘                   │
└───────────────────────────────────────────────────────────────────┘
```

#### 3.2 Registration

```typescript
// lib/sw-register.ts
export async function registerServiceWorker(swPath = '/sw.js'): Promise<void> {
  if (!('serviceWorker' in navigator)) {
    console.warn('Service Worker tidak didukung browser ini')
    return
  }

  try {
    const registration = await navigator.serviceWorker.register(swPath, {
      scope: '/',
      updateViaCache: 'none',
    })

    console.log('SW registered:', registration.scope)

    // Detect update
    registration.addEventListener('updatefound', () => {
      const installingWorker = registration.installing
      if (!installingWorker) return

      installingWorker.addEventListener('statechange', () => {
        if (installingWorker.state === 'installed') {
          if (navigator.serviceWorker.controller) {
            // New version available
            dispatchEvent(new CustomEvent('sw-update-available', {
              detail: { registration },
            }))
          } else {
            // First time install
            console.log('SW installed for first time')
          }
        }
      })
    })
  } catch (error) {
    console.error('SW registration failed:', error)
  }
}

// Auto-register on page load
if (typeof window !== 'undefined' && document.readyState === 'complete') {
  registerServiceWorker()
} else {
  window.addEventListener('load', () => registerServiceWorker())
}
```

#### 3.3 Install Event — Precache Static Assets

```typescript
// sw/install.ts
const STATIC_CACHE = 'static-v1'
const PRECACHE_URLS = [
  '/',
  '/offline',
  '/index.html',
  '/styles/global.css',
  '/scripts/main.js',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
  '/fonts/inter-var.woff2',
]

self.addEventListener('install', (event: ExtendableEvent) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(STATIC_CACHE)
      await cache.addAll(PRECACHE_URLS)
      // Force activation
      await self.skipWaiting()
    })()
  )
})
```

#### 3.4 Activate Event — Clean Old Caches

```typescript
// sw/activate.ts
const CURRENT_CACHES = ['static-v1', 'dynamic-v1', 'font-v1', 'image-v1']

self.addEventListener('activate', (event: ExtendableEvent) => {
  event.waitUntil(
    (async () => {
      // Clean old caches
      const cacheNames = await caches.keys()
      const deletePromises = cacheNames
        .filter((name) => !CURRENT_CACHES.includes(name))
        .map((name) => caches.delete(name))

      await Promise.all(deletePromises)

      // Take control of all clients immediately
      await self.clients.claim()

      // Notify all clients
      const clients = await self.clients.matchAll()
      clients.forEach((client) => {
        client.postMessage({ type: 'SW_ACTIVATED', version: '1.0.0' })
      })
    })()
  )
})
```

#### 3.5 Update Detection — UI Pattern

```typescript
// hooks/useSwUpdate.ts
import { useEffect, useState } from 'react'

interface SwUpdateState {
  needsUpdate: boolean
  registration: ServiceWorkerRegistration | null
  update: () => Promise<void>
}

export function useSwUpdate(): SwUpdateState {
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null)

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail as { registration: ServiceWorkerRegistration }
      setRegistration(detail.registration)
    }

    window.addEventListener('sw-update-available', handler)
    return () => window.removeEventListener('sw-update-available', handler)
  }, [])

  const update = async () => {
    if (!registration?.waiting) return

    // Listen for state change
    registration.waiting.addEventListener('statechange', (event) => {
      if ((event.target as ServiceWorker).state === 'activated') {
        window.location.reload()
      }
    })

    // Send skip waiting message
    registration.waiting.postMessage({ type: 'SKIP_WAITING' })
  }

  return {
    needsUpdate: registration !== null,
    registration,
    update,
  }
}
```

```tsx
// components/UpdatePrompt.tsx
import { useSwUpdate } from '@/hooks/useSwUpdate'

export function UpdatePrompt() {
  const { needsUpdate, update } = useSwUpdate()

  if (!needsUpdate) return null

  return (
    <div className="update-banner" role="alert">
      <p>Versi baru tersedia. Perbarui untuk pengalaman terbaik.</p>
      <button onClick={update} className="update-button">
        Perbarui Sekarang
      </button>
    </div>
  )
}
```

```typescript
// In service worker — listen for SKIP_WAITING
self.addEventListener('message', (event: ExtendableMessageEvent) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})
```

---

### 4. Workbox

#### 4.1 Workbox Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      WORKBOX MODULES                               │
│                                                                    │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────┐   │
│  │ workbox-core  │  │ workbox-routing│  │ workbox-strategies   │   │
│  │  - logger     │  │  - registerRoute│ │  - CacheFirst        │   │
│  │  - cacheNames │  │  - NavigationRoute│ │  - NetworkFirst      │   │
│  │  - setCacheName│  └───────┬───────┘  │  - StaleWhileRevalidate│ │
│  └──────┬───────┘           │           │  - NetworkOnly        │   │
│         │                   │           │  - CacheOnly          │   │
│         │                   │           └──────────┬──────────┘   │
│         ▼                   ▼                      ▼              │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  workbox-precaching  │  workbox-expiration            │        │
│  │  - precacheAndRoute  │  - CacheExpiration            │        │
│  │  - cleanupOutdatedCaches│ - ExpirationPlugin          │        │
│  └────────────────────────┴────────────────────────────┘        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  workbox-background-sync  │  workbox-broadcast-update  │        │
│  │  - BackgroundSyncPlugin  │  - BroadcastUpdatePlugin   │        │
│  └──────────────────────────┴──────────────────────────┘        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  workbox-cacheable-response  │  workbox-range-requests│        │
│  │  - CacheableResponsePlugin  │  - RangeRequestsPlugin  │        │
│  └──────────────────────────────┴──────────────────────┘        │
│  ┌──────────────────────────────────────────────────────┐        │
│  │  workbox-navigation-preload                            │        │
│  │  - enable()  │  - disable()                           │        │
│  └──────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────┘
```

#### 4.2 Caching Strategy Decision Tree

```
┌─────────────────────────────────────────────────────────────┐
│              CACHING STRATEGY DECISION TREE                   │
│                                                              │
│  For a given request:                                        │
│                                                              │
│  Is the resource static, versioned, and rarely changed?      │
│       │                              │                        │
│       YES                             NO                      │
│       ▼                              ▼                        │
│  ┌──────────┐              Is freshness critical?             │
│  │ CacheFirst│              │                     │           │
│  │ (precache)│              YES                    NO          │
│  └──────────┘              │                      │           │
│                             ▼                      ▼           │
│                     Is network available?    Is content         │
│                      │              │        user-specific?     │
│                      YES             NO       │        │        │
│                      ▼               ▼        YES       NO      │
│                 ┌──────────┐   ┌──────────┐   │        │        │
│                 │ Network  │   │  Cache   │   ▼        ▼        │
│                 │  First   │   │  First   │ ┌────────┐ ┌────┐  │
│                 │          │   │          │ │Network │ │Stale│  │
│                 │ (network │   │(use cache │ │ Only   │ │While│  │
│                 │  then    │   │ regardless│ │        │ │Reval│  │
│                 │  cache)  │   │  of age)  │ └────────┘ └────┘  │
│                 └──────────┘   └──────────┘                     │
│                                                              │
│  Quick reference:                                            │
│  ┌──────────────────────┬──────────────────┬──────────────┐  │
│  │ CacheFirst           │ Versioned assets │ JS, CSS, img │  │
│  │ NetworkFirst         │ Dynamic content  │ API, pages   │  │
│  │ StaleWhileRevalidate│ Non-critical data │ Avatars, feed│  │
│  │ NetworkOnly          │ Always fresh     │ Auth, paymts │  │
│  │ CacheOnly            │ Offline fallback │ Emergency     │  │
│  └──────────────────────┴──────────────────┴──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

#### 4.3 Using workbox-build / injectManifest

```typescript
// workbox-config.js — for use with workbox CLI or injectManifest
module.exports = {
  globDirectory: 'dist/',
  globPatterns: [
    '**/*.{html,js,css,woff2,ico,png,jpg,svg}',
  ],
  globIgnores: [
    '**/workbox-*.js',
    '**/sw.js',
  ],
  swDest: 'dist/sw.js',
  swSrc: 'src/sw/index.ts',
  maximumFileSizeToCacheInBytes: 5 * 1024 * 1024, // 5 MB
}
```

#### 4.4 Service Worker Entry Point (injectManifest)

```typescript
/// <reference types="vite-plugin-pwa/client" />
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching'
import { registerRoute, NavigationRoute } from 'workbox-routing'
import {
  NetworkFirst,
  CacheFirst,
  StaleWhileRevalidate,
  NetworkOnly,
} from 'workbox-strategies'
import { ExpirationPlugin } from 'workbox-expiration'
import { CacheableResponsePlugin } from 'workbox-cacheable-response'
import { BroadcastUpdatePlugin } from 'workbox-broadcast-update'
import { BackgroundSyncPlugin } from 'workbox-background-sync'

// ── Precache (auto-generated by workbox-build / vite-plugin-pwa) ──
declare const self: ServiceWorkerGlobalScope
precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()

// ── Navigation (HTML pages) — NetworkFirst with offline fallback ──
registerRoute(
  new NavigationRoute(
    new NetworkFirst({
      cacheName: 'pages-v1',
      plugins: [
        new ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 7 * 24 * 60 * 60 }),
        new CacheableResponsePlugin({ statuses: [200] }),
      ],
    })
  )
)

// ── Static assets (JS/CSS) — CacheFirst, versioned via hash ──
registerRoute(
  /\.(?:js|css)$/,
  new CacheFirst({
    cacheName: 'static-v1',
    plugins: [
      new ExpirationPlugin({ maxEntries: 80, maxAgeSeconds: 30 * 24 * 60 * 60 }),
      new CacheableResponsePlugin({ statuses: [200] }),
    ],
  })
)

// ── Images — CacheFirst with size limit ──
registerRoute(
  /\.(?:png|jpg|jpeg|gif|webp|avif|svg)$/,
  new CacheFirst({
    cacheName: 'images-v1',
    plugins: [
      new ExpirationPlugin({ maxEntries: 100, maxAgeSeconds: 60 * 24 * 60 * 60 }),
      new CacheableResponsePlugin({ statuses: [200] }),
    ],
  })
)

// ── Fonts — CacheFirst, long TTL ──
registerRoute(
  /\.(?:woff2|woff|ttf|otf)$/,
  new CacheFirst({
    cacheName: 'fonts-v1',
    plugins: [
      new ExpirationPlugin({ maxEntries: 20, maxAgeSeconds: 365 * 24 * 60 * 60 }),
      new CacheableResponsePlugin({ statuses: [200] }),
    ],
  })
)

// ── API calls — StaleWhileRevalidate with broadcast update ──
registerRoute(
  /\/api\/public\//,
  new StaleWhileRevalidate({
    cacheName: 'api-public-v1',
    plugins: [
      new ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 5 * 60 }), // 5 min
      new CacheableResponsePlugin({ statuses: [200] }),
      new BroadcastUpdatePlugin(),
    ],
  })
)

// ── Critical API (freshness required) — NetworkFirst ──
registerRoute(
  /\/api\/data\/dashboard\//,
  new NetworkFirst({
    cacheName: 'api-critical-v1',
    plugins: [
      new ExpirationPlugin({ maxEntries: 20, maxAgeSeconds: 60 }),
      new CacheableResponsePlugin({ statuses: [200] }),
    ],
  })
)

// ── Auth endpoints — NetworkOnly (never cache) ──
registerRoute(
  /\/api\/(?:auth|login|logout|token)/,
  new NetworkOnly()
)

// ── Background Sync for offline mutations ──
const syncPlugin = new BackgroundSyncPlugin('dataQueue', {
  maxRetentionTime: 24 * 60, // 24 hours in minutes
})

registerRoute(
  /\/api\/mutation\//,
  new NetworkOnly({ plugins: [syncPlugin] }),
  'POST'
)

// ── Navigation preload ──
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    if (self.registration.navigationPreload) {
      await self.registration.navigationPreload.enable()
    }
  })())
})
```

---

### 5. Caching Strategies — Deep Dive

#### 5.1 CacheFirst

Best for: **Versioned, rarely-changing static assets** (JS bundles with content hash, CSS with hash, fonts, icon files).

```typescript
// CacheFirst — manual implementation
self.addEventListener('fetch', (event: FetchEvent) => {
  if (!event.request.url.match(/\.(js|css|woff2)$/)) return

  event.respondWith(
    (async () => {
      const cached = await caches.match(event.request)
      if (cached) return cached

      const response = await fetch(event.request)
      if (response.ok) {
        const cache = await caches.open('static-v1')
        cache.put(event.request, response.clone())
      }

      return response
    })()
  )
})
```

#### 5.2 NetworkFirst

Best for: **Dynamic content requiring freshness but with offline fallback** (HTML pages, API responses, blog posts).

```typescript
// NetworkFirst — manual implementation
async function networkFirst(request: Request, cacheName: string, timeout = 3000): Promise<Response> {
  try {
    const fetchPromise = fetch(request)

    // Timeout: serve from cache if network is slow
    const timeoutPromise = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('Network timeout')), timeout)
    )

    const response = await Promise.race([fetchPromise, timeoutPromise]) as Response

    if (response.ok) {
      const cache = await caches.open(cacheName)
      cache.put(request, response.clone())
    }

    return response
  } catch {
    const cached = await caches.match(request)
    if (cached) return cached

    // Offline fallback
    const cache = await caches.open('static-v1')
    const fallback = await cache.match('/offline')
    if (fallback) return fallback

    return new Response('Offline', { status: 503 })
  }
}
```

#### 5.3 StaleWhileRevalidate

Best for: **Non-critical content where instant display matters more than freshness** (user avatars, feed data, settings).

```typescript
// StaleWhileRevalidate — manual implementation
async function staleWhileRevalidate(request: Request, cacheName: string): Promise<Response> {
  const cache = await caches.open(cacheName)
  const cached = await cache.match(request)

  // Fire-and-forget network update
  const fetchPromise = fetch(request).then((response) => {
    if (response.ok) {
      cache.put(request, response.clone())
    }
    return response
  }).catch(() => cached)

  // Return cached immediately if available
  return cached || fetchPromise
}
```

#### 5.4 Strategy Comparison

```
┌─────────────────────┬──────────┬────────────┬───────────┬────────────┐
│                     │ Speed    │ Freshness  │ Offline   │ Use Case    │
├─────────────────────┼──────────┼────────────┼───────────┼────────────┤
│ CacheFirst          │ ⚡ Fast   │ ❌ Stale   │ ✓ Yes     │ JS, CSS,   │
│                     │          │            │           │ fonts, imgs│
├─────────────────────┼──────────┼────────────┼───────────┼────────────┤
│ NetworkFirst        │ 🐢 Slow  │ ✓ Fresh     │ ✓ Yes     │ Pages, API │
├─────────────────────┼──────────┼────────────┼───────────┼────────────┤
│ StaleWhileRevalidate│ ⚡ Fast   │ ⚠️ Stale    │ ✓ Yes     │ Avatars,   │
│                     │          │ (updates   │           │ public feed│
│                     │          │  in bg)    │           │            │
├─────────────────────┼──────────┼────────────┼───────────┼────────────┤
│ NetworkOnly          │ 🐢 Slow  │ ✓ Fresh     │ ❌ No     │ Auth,      │
│                     │          │            │           │ payments   │
├─────────────────────┼──────────┼────────────┼───────────┼────────────┤
│ CacheOnly           │ ⚡ Fast   │ ❌ Stale    │ ✓ Yes     │ Emergency  │
│                     │          │ (only if   │           │ offline UI │
│                     │          │  cached)   │           │            │
└─────────────────────┴──────────┴────────────┴───────────┴────────────┘
```

#### 5.5 Cache Expiration & Size Management

```typescript
import { ExpirationPlugin } from 'workbox-expiration'

// Example: cache max 50 images, delete after 30 days
registerRoute(
  /\.(?:png|jpg|jpeg|webp)$/,
  new CacheFirst({
    cacheName: 'images-v1',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 50,
        maxAgeSeconds: 30 * 24 * 60 * 60, // 30 hari
        purgeOnQuotaError: true,           // Auto-clean when storage full
      }),
    ],
  })
)
```

#### 5.6 Broadcast Update

Notify the page when cached content changes (for StaleWhileRevalidate).

```typescript
// Service Worker side
import { BroadcastUpdatePlugin } from 'workbox-broadcast-update'

registerRoute(
  /\/api\/public\/items/,
  new StaleWhileRevalidate({
    cacheName: 'api-items',
    plugins: [
      new BroadcastUpdatePlugin({
        channelName: 'api-updates',
        headersToCheck: ['content-type', 'etag'],
        generatePayload: ({ request, response }) => ({
          url: request.url,
          updatedAt: new Date().toISOString(),
          etag: response.headers.get('etag'),
        }),
      }),
    ],
  })
)
```

```typescript
// App side — listen for updates
const channel = new BroadcastChannel('api-updates')
channel.addEventListener('message', (event) => {
  console.log('Data updated in background:', event.data)
  // Optionally re-render UI with fresh data
  invalidateQuery(event.data.payload.url)
})
```

#### 5.7 Range Requests (Video/Audio Streaming)

```typescript
import { RangeRequestsPlugin } from 'workbox-range-requests'

registerRoute(
  /\.(?:mp4|webm|ogg|mp3|m3u8)$/,
  new CacheFirst({
    cacheName: 'media-v1',
    plugins: [
      new RangeRequestsPlugin(),
      new ExpirationPlugin({ maxEntries: 10, maxAgeSeconds: 7 * 24 * 60 * 60 }),
    ],
  })
)
```

#### 5.8 Cacheable Response Validation

```typescript
import { CacheableResponsePlugin } from 'workbox-cacheable-response'

// Only cache successful responses (200) + opaque responses (0 for CORS)
registerRoute(
  /\/api\/public\//,
  new StaleWhileRevalidate({
    cacheName: 'api-public',
    plugins: [
      new CacheableResponsePlugin({
        statuses: [0, 200],       // 0 = opaque response
        headers: {
          'X-Is-Cacheable': 'true',
        },
      }),
    ],
  })
)
```

---

### 6. Offline Support

#### 6.1 Offline Fallback Page

```typescript
// sw/offline-fallback.ts
const OFFLINE_URL = '/offline'
const STATIC_CACHE = 'static-v1'

// Precache offline page during install
self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(STATIC_CACHE)
      await cache.add(new Request(OFFLINE_URL, { cache: 'no-cache' }))
    })()
  )
})

// Intercept navigation failures → show offline page
self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const networkResponse = await fetch(event.request)
          return networkResponse
        } catch {
          const cache = await caches.open(STATIC_CACHE)
          const cachedResponse = await cache.match(OFFLINE_URL)
          return cachedResponse || new Response('Offline', {
            status: 503,
            headers: { 'Content-Type': 'text/html' },
          })
        }
      })()
    )
  }
})
```

#### 6.2 Offline Analytics Queue

```typescript
// lib/offline-analytics.ts
interface AnalyticsEvent {
  name: string
  data: Record<string, unknown>
  timestamp: number
  id: string
}

const DB_NAME = 'offline-analytics'
const STORE_NAME = 'events'

function openDB(): Promise<IDBPDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => {
      const db = request.result
      db.createObjectStore(STORE_NAME, { keyPath: 'id' })
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export async function queueAnalyticsEvent(name: string, data: Record<string, unknown> = {}): Promise<void> {
  const event: AnalyticsEvent = {
    id: crypto.randomUUID(),
    name,
    data,
    timestamp: Date.now(),
  }

  // Try sending online first
  if (navigator.onLine) {
    try {
      await fetch('/api/analytics', {
        method: 'POST',
        body: JSON.stringify(event),
        headers: { 'Content-Type': 'application/json' },
        keepalive: true,
      })
      return
    } catch {
      // Fall through to queue
    }
  }

  // Queue offline
  const db = await openDB()
  const tx = db.transaction(STORE_NAME, 'readwrite')
  tx.objectStore(STORE_NAME).add(event)
  await tx.done
}

export async function flushAnalyticsQueue(): Promise<void> {
  const db = await openDB()
  const events = await db.getAll(STORE_NAME)

  for (const event of events) {
    try {
      const response = await fetch('/api/analytics', {
        method: 'POST',
        body: JSON.stringify(event),
        headers: { 'Content-Type': 'application/json' },
      })
      if (response.ok) {
        const tx = db.transaction(STORE_NAME, 'readwrite')
        tx.objectStore(STORE_NAME).delete(event.id)
        await tx.done
      }
    } catch {
      // Leave in queue for next attempt
      break
    }
  }
}

// Flush on online event
window.addEventListener('online', flushAnalyticsQueue)
```

#### 6.3 IndexedDB for Offline Data

```typescript
// lib/offline-db.ts
import { openDB, type IDBPDatabase } from 'idb' // or use raw IDB

const DB_NAME = 'app-offline'
const DB_VERSION = 1

export interface OfflineStore {
  key: string
  value: unknown
  timestamp: number
  ttl: number // TTL in ms
}

export async function getOfflineDB(): Promise<IDBPDatabase> {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains('cache')) {
        const store = db.createObjectStore('cache', { keyPath: 'key' })
        store.createIndex('timestamp', 'timestamp')
        store.createIndex('ttl', 'ttl')
      }
      if (!db.objectStoreNames.contains('mutations')) {
        db.createObjectStore('mutations', {
          keyPath: 'id',
          autoIncrement: true,
        })
      }
    },
  })
}

export async function setOfflineData(key: string, value: unknown, ttlMs = 5 * 60 * 1000): Promise<void> {
  const db = await getOfflineDB()
  await db.put('cache', {
    key,
    value,
    timestamp: Date.now(),
    ttl: ttlMs,
  } satisfies OfflineStore)
}

export async function getOfflineData<T>(key: string): Promise<T | null> {
  const db = await getOfflineDB()
  const entry = await db.get('cache', key) as OfflineStore | undefined

  if (!entry) return null

  // Check TTL
  if (Date.now() - entry.timestamp > entry.ttl) {
    await db.delete('cache', key)
    return null
  }

  return entry.value as T
}

export async function queueOfflineMutation(endpoint: string, method: string, body: unknown): Promise<void> {
  const db = await getOfflineDB()
  await db.add('mutations', {
    endpoint,
    method,
    body,
    createdAt: Date.now(),
    retries: 0,
  })
}

// Remove expired entries periodically
export async function cleanExpiredCache(): Promise<void> {
  const db = await getOfflineDB()
  const now = Date.now()
  const tx = db.transaction('cache', 'readwrite')
  let cursor = await tx.store.openCursor()

  while (cursor) {
    const entry = cursor.value as OfflineStore
    if (now - entry.timestamp > entry.ttl) {
      cursor.delete()
    }
    cursor = await cursor.continue()
  }

  await tx.done
}
```

#### 6.4 Background Sync API

```typescript
// App: Register a sync
export async function registerBackgroundSync(tag: string): Promise<void> {
  if (!('sync' in self.registration)) {
    console.warn('Background Sync tidak didukung')
    return
  }

  try {
    await self.registration.sync.register(tag)
    console.log(`Background sync registered: ${tag}`)
  } catch (error) {
    console.error('Background sync registration failed:', error)
  }
}

// Call when user submits a form offline
export async function submitFormOffline(formData: Record<string, unknown>): Promise<void> {
  await queueOfflineMutation('/api/submissions', 'POST', formData)
  await registerBackgroundSync('sync-submissions')
}
```

```typescript
// Service Worker: Handle sync event
self.addEventListener('sync', (event: SyncEvent) => {
  if (event.tag === 'sync-submissions') {
    event.waitUntil(processSubmissionQueue())
  }
})

async function processSubmissionQueue(): Promise<void> {
  try {
    // Use workbox BackgroundSyncPlugin or custom IDB logic
    const db = await getOfflineDB()
    const mutations = await db.getAll('mutations')

    for (const mutation of mutations) {
      try {
        const response = await fetch(mutation.endpoint, {
          method: mutation.method,
          body: JSON.stringify(mutation.body),
          headers: { 'Content-Type': 'application/json' },
        })

        if (response.ok) {
          await db.delete('mutations', mutation.id)
        } else {
          // Increment retry count
          mutation.retries++
          if (mutation.retries < 5) {
            await db.put('mutations', mutation)
          } else {
            // Max retries exceeded, discard or notify
            await db.delete('mutations', mutation.id)
            await notifyAdminOfFailure(mutation)
          }
        }
      } catch {
        // Network still unavailable, stop processing
        break
      }
    }
  } catch (error) {
    console.error('Failed to process submission queue:', error)
  }
}

async function notifyAdminOfFailure(mutation: unknown): Promise<void> {
  // Store in a separate "failed" store for admin review
  const db = await getOfflineDB()
  if (!db.objectStoreNames.contains('failed-mutations')) {
    // Handle migration...
  }
  await db.add('failed-mutations', {
    ...mutation,
    failedAt: Date.now(),
  })
}
```

#### 6.5 Periodic Background Sync

```typescript
// Request periodic sync (requires user permission)
export async function requestPeriodicSync(tag: string, minInterval: number): Promise<void> {
  if (!('periodicSync' in self.registration)) {
    console.warn('Periodic Sync tidak didukung browser ini')
    return
  }

  // Check if already registered
  const tags = await self.registration.periodicSync.getTags()
  if (tags.includes(tag)) return

  try {
    await self.registration.periodicSync.register(tag, {
      minInterval, // Minimum time in ms between syncs
    })
  } catch (error) {
    if ((error as DOMException).name === 'AbortError') {
      console.warn('Periodic Sync ditolak user (permission required)')
    } else {
      console.error('Periodic Sync registration failed:', error)
    }
  }
}

// Service Worker: Handle periodic sync
self.addEventListener('periodicsync', (event: PeriodicSyncEvent) => {
  if (event.tag === 'update-content') {
    event.waitUntil(refreshCachedContent())
  } else if (event.tag === 'cleanup-storage') {
    event.waitUntil(storageCleanup())
  }
})

async function refreshCachedContent(): Promise<void> {
  const urlsToRefresh = ['/api/public/news', '/api/public/announcements']

  const cache = await caches.open('api-public-v1')
  const refreshPromises = urlsToRefresh.map(async (url) => {
    try {
      const response = await fetch(url)
      if (response.ok) {
        await cache.put(url, response)
      }
    } catch {
      // Network unavailable, skip this cycle
    }
  })

  await Promise.all(refreshPromises)
}
```

#### 6.6 Network Status Detection

```typescript
// hooks/useOnlineStatus.ts
import { useEffect, useState } from 'react'

export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(navigator.onLine)

  useEffect(() => {
    const handleOnline = () => setOnline(true)
    const handleOffline = () => setOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    // Also detect via SW connectivity check
    const checkConnection = setInterval(async () => {
      try {
        await fetch('/api/health', { method: 'HEAD', cache: 'no-store' })
        setOnline(true)
      } catch {
        setOnline(false)
      }
    }, 30000)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      clearInterval(checkConnection)
    }
  }, [])

  return online
}
```

---

### 7. Push Notifications

#### 7.1 Web Push API Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PUSH NOTIFICATION FLOW                          │
│                                                                      │
│  ┌───────┐     ┌──────────────┐     ┌───────────┐     ┌────────┐   │
│  │  App   │────►│ ServiceWorker │────►│ Push Service│────►│ Browser│  │
│  │ (page) │     │ (subscribe)  │     │ (server)   │     │  (SW)  │   │
│  └───┬───┘     └──────┬───────┘     └─────┬─────┘     └────┬───┘   │
│      │                │                    │                │        │
│      │  1. Register   │                    │                │        │
│      │  SW + Get      │                    │                │        │
│      │  PushSubscription                   │                │        │
│      │◄───────────────┤                    │                │        │
│      │                │                    │                │        │
│      │  2. Send sub   │                    │                │        │
│      │  to server     │                    │                │        │
│      │────────────────►│                    │                │        │
│      │                │                    │                │        │
│      │                │  3. Server sends   │                │        │
│      │                │  push via Web Push │                │        │
│      │                │  Protocol          │                │        │
│      │                │───────────────────►│                │        │
│      │                │                    │  4. Push event │        │
│      │                │                    │  delivered to  │        │
│      │                │                    │  browser SW    │        │
│      │                │◄───────────────────┼────────────────┤        │
│      │                │                    │                │        │
│      │                │  5. Show           │                │        │
│      │                │  notification      │                │        │
│      │                │────────────────────┼────────────────►        │
│      │                │                    │                │        │
│      │                │  6. User clicks    │                │        │
│      │                │  notification      │                │        │
│      │◄───────────────┼────────────────────┼────────────────┤        │
│      │                │                    │                │        │
└─────────────────────────────────────────────────────────────────────┘
```

#### 7.2 VAPID Key Generation

```typescript
// tools/generate-vapid-keys.ts
// Run: npx tsx tools/generate-vapid-keys.ts
import webPush from 'web-push'

const vapidKeys = webPush.generateVAPIDKeys()

console.log('VAPID Public Key:', vapidKeys.publicKey)
console.log('VAPID Private Key:', vapidKeys.privateKey)
console.log('\nAdd to .env:')
console.log(`VITE_VAPID_PUBLIC_KEY=${vapidKeys.publicKey}`)
console.log(`VAPID_PRIVATE_KEY=${vapidKeys.privateKey}`)
```

```bash
# Alternative: Generate via CLI
npx web-push generate-vapid-keys --json
```

#### 7.3 Subscription Management

```typescript
// lib/push-subscription.ts
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/')

  const rawData = atob(base64)
  const outputArray = new Uint8Array(rawData.length)

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i)
  }

  return outputArray
}

export async function subscribeToPush(
  registration: ServiceWorkerRegistration,
  vapidPublicKey: string
): Promise<PushSubscription | null> {
  try {
    // Check existing subscription
    let subscription = await registration.pushManager.getSubscription()

    if (subscription) {
      // Check if still valid
      const isValid = await verifySubscription(subscription)
      if (!isValid) {
        await subscription.unsubscribe()
        subscription = null
      } else {
        return subscription
      }
    }

    // Subscribe
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
    })

    // Send to server
    await fetch('/api/push/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subscription: subscription.toJSON(),
        userAgent: navigator.userAgent,
        locale: document.documentElement.lang,
      }),
    })

    return subscription
  } catch (error) {
    if ((error as DOMException).name === 'NotAllowedError') {
      console.warn('Push notification permission denied')
    } else {
      console.error('Push subscription failed:', error)
    }
    return null
  }
}

async function verifySubscription(subscription: PushSubscription): Promise<boolean> {
  try {
    const response = await fetch('/api/push/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ endpoint: subscription.endpoint }),
    })
    return response.ok
  } catch {
    return false
  }
}

export async function unsubscribeFromPush(
  registration: ServiceWorkerRegistration
): Promise<boolean> {
  const subscription = await registration.pushManager.getSubscription()

  if (!subscription) return true

  // Notify server
  try {
    await fetch('/api/push/unsubscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ endpoint: subscription.endpoint }),
    })
  } catch {
    // Continue even if server fails
  }

  return subscription.unsubscribe()
}

// React hook for push subscription
export function usePushSubscription() {
  const [permission, setPermission] = useState<NotificationPermission>(
    Notification.permission
  )

  const requestPermission = async () => {
    const result = await Notification.requestPermission()
    setPermission(result)
    return result === 'granted'
  }

  return { permission, requestPermission }
}
```

#### 7.4 Notification Payload

```typescript
// Server-side notification payload (Node.js example)
// server/push/send.ts
import webPush from 'web-push'

webPush.setVapidDetails(
  'mailto:admin@kapuascarbon.id',
  process.env.VITE_VAPID_PUBLIC_KEY!,
  process.env.VAPID_PRIVATE_KEY!
)

interface NotificationPayload {
  title: string
  body: string
  icon?: string
  badge?: string
  image?: string
  tag?: string
  data?: Record<string, unknown>
  actions?: NotificationAction[]
  requireInteraction?: boolean
  silent?: boolean
  vibrate?: number[]
  renotify?: boolean
  timestamp?: number
  dir?: 'auto' | 'ltr' | 'rtl'
  lang?: string
}

export async function sendPushNotification(
  subscription: PushSubscription,
  payload: NotificationPayload
): Promise<void> {
  try {
    await webPush.sendNotification(
      subscription,
      JSON.stringify(payload),
      {
        TTL: 86400,           // 24 hours
        urgency: 'normal',    // 'very-low' | 'low' | 'normal' | 'high'
        topic: 'general',
      }
    )
  } catch (error) {
    if ((error as { statusCode: number }).statusCode === 410) {
      // Subscription expired or unsubscribed
      // Remove from database
      await removeSubscription(subscription.endpoint)
    }
    throw error
  }
}

// Example: Send to multiple subscribers
export async function broadcastNotification(
  subscriptions: PushSubscription[],
  payload: NotificationPayload
): Promise<{ success: number; failed: number }> {
  let success = 0
  let failed = 0

  const results = await Promise.allSettled(
    subscriptions.map((sub) => sendPushNotification(sub, payload))
  )

  for (const result of results) {
    if (result.status === 'fulfilled') success++
    else failed++
  }

  return { success, failed }
}
```

#### 7.5 Notification Handling in Service Worker

```typescript
// sw/notifications.ts

// Display notification when push event arrives
self.addEventListener('push', (event: PushEvent) => {
  if (!event.data) return

  const payload: NotificationPayload = event.data.json()

  const options: NotificationOptions = {
    body: payload.body,
    icon: payload.icon || '/icons/icon-192x192.png',
    badge: payload.badge || '/icons/badge-96x96.png',
    tag: payload.tag || crypto.randomUUID(),
    data: payload.data || {},
    actions: payload.actions || [],
    requireInteraction: payload.requireInteraction ?? false,
    silent: payload.silent ?? false,
    vibrate: payload.vibrate || [200, 100, 200],
    renotify: payload.renotify ?? false,
    timestamp: payload.timestamp || Date.now(),
    dir: payload.dir || 'auto',
    lang: payload.lang || 'id',
  }

  event.waitUntil(
    self.registration.showNotification(payload.title, options)
  )
})

// Notification click handler
self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close()

  const clickAction = event.action
  const notificationData = event.notification.data || {}

  event.waitUntil(
    (async () => {
      const url = resolveNotificationUrl(clickAction, notificationData)
      if (!url) return

      const clients = await self.clients.matchAll({
        type: 'window',
        includeUncontrolled: true,
      })

      // Focus existing tab or open new one
      const existingClient = clients.find((c) => {
        const clientUrl = new URL(c.url)
        const targetUrl = new URL(url, self.location.origin)
        return clientUrl.pathname === targetUrl.pathname
      })

      if (existingClient) {
        await existingClient.focus()
        existingClient.postMessage({
          type: 'NOTIFICATION_CLICKED',
          data: notificationData,
        })
      } else {
        await self.clients.openWindow(url)
      }
    })()
  )
})

function resolveNotificationUrl(
  action: string | undefined,
  data: Record<string, unknown>
): string | null {
  // Map action to URL
  switch (action) {
    case 'view-dashboard':
      return '/dashboard'
    case 'view-project':
      return `/projects/${data.projectSlug}`
    case 'view-message':
      return `/messages/${data.messageId}`
    case 'approve':
      return `/approvals/${data.approvalId}`
    default:
      return (data.url as string) || '/'
  }
}

// Close all notifications with a tag
self.addEventListener('notificationclose', (event: NotificationEvent) => {
  // Optional: track that user dismissed notification
  if (event.notification.data?.analyticsId) {
    fetch('/api/analytics/notification-dismissed', {
      method: 'POST',
      body: JSON.stringify({
        id: event.notification.data.analyticsId,
        tag: event.notification.tag,
      }),
      headers: { 'Content-Type': 'application/json' },
    }).catch(() => {})
  }
})
```

#### 7.6 Notification Actions

```typescript
// Define actions for different notification types
const NOTIFICATION_ACTIONS = {
  projectUpdate: [
    {
      action: 'view-project',
      title: 'Lihat Proyek',
    },
    {
      action: 'dismiss',
      title: 'Tutup',
    },
  ],
  approval: [
    {
      action: 'approve',
      title: 'Setujui',
    },
    {
      action: 'reject',
      title: 'Tolak',
    },
    {
      action: 'view-detail',
      title: 'Detail',
    },
  ],
  message: [
    {
      action: 'reply',
      title: 'Balas',
    },
    {
      action: 'mark-read',
      title: 'Tandai Dibaca',
    },
  ],
} as const
```

---

### 8. PWA with Vite

#### 8.1 vite-plugin-pwa Configuration

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // ── Mode: generateSW (auto-generate SW) ──
      // strategi: 'generateSW',

      // ── Mode: injectManifest (full control) ──
      strategies: 'injectManifest',
      srcDir: 'src/sw',
      filename: 'index.ts',
      swSrc: 'src/sw/index.ts',   // deprecated alias, use filename
      swDest: 'sw.js',             // output in dist/

      // ── Manifest ──
      manifest: {
        name: 'Kapuas Carbon PDD',
        short_name: 'Kapuas Carbon',
        description: 'Project Design Document for Kapuas Carbon Project',
        start_url: '/?source=pwa',
        display: 'standalone',
        display_override: ['window-controls-overlay', 'standalone'],
        background_color: '#ffffff',
        theme_color: '#1a6b3c',
        orientation: 'portrait-primary',
        lang: 'id',
        icons: [
          {
            src: '/icons/icon-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'any maskable',
          },
          {
            src: '/icons/icon-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
        screenshots: [
          {
            src: '/screenshots/desktop.png',
            sizes: '1920x1080',
            type: 'image/png',
            form_factor: 'wide',
          },
          {
            src: '/screenshots/mobile.png',
            sizes: '750x1334',
            type: 'image/png',
            form_factor: 'narrow',
          },
        ],
      },

      // ── Workbox / injectManifest options ──
      workbox: {
        // Only used in generateSW mode
        globPatterns: ['**/*.{js,css,html,woff2,png,jpg,svg,ico}'],
        globIgnores: ['**/workbox-*.js'],
        cleanupOutdatedCaches: true,
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
        navigateFallback: '/',
        navigateFallbackDenylist: [/\/api\//],
        runtimeCaching: [
          {
            urlPattern: /\/api\/public\//,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'api-public',
              expiration: { maxEntries: 50, maxAgeSeconds: 300 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /\.(?:png|jpg|jpeg|webp|avif|svg)$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'images',
              expiration: { maxEntries: 100, maxAgeSeconds: 30 * 24 * 60 * 60 },
            },
          },
          {
            urlPattern: /\.(?:woff2|woff)$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'fonts',
              expiration: { maxEntries: 20, maxAgeSeconds: 365 * 24 * 60 * 60 },
            },
          },
        ],
      },

      // ── Inject Manifest SW entry ──
      // Used when strategies = 'injectManifest'
      // The file at srcDir/filename is injected with self.__WB_MANIFEST

      // ── Dev options ──
      devOptions: {
        enabled: true,           // Enable SW in dev mode
        type: 'module',           // Use ES module type for SW
        navigateFallback: '/',
        navigateFallbackDenylist: [/\/api\//],
      },

      // ── Register SW (auto inject) ──
      registerType: 'autoUpdate',  // 'autoUpdate' | 'prompt'
      // If 'prompt', exposes needRefresh/offlineReady via useRegisterSW

      // ── PWA assets generation ──
      includeAssets: [
        'icons/*.png',
        'screenshots/*.png',
        'fonts/*.woff2',
        'favicon.ico',
      ],

      // ── Self-destroying SW for development ──
      selfDestroying: false,
    }),
  ],
})
```

#### 8.2 generateSW vs injectManifest

```
┌───────────────────┬───────────────────────┬────────────────────────┐
│                   │     generateSW        │     injectManifest     │
├───────────────────┼───────────────────────┼────────────────────────┤
│ Control           │ Workbox config only   │ Full SW source control │
│ Precache list     │ Auto-generated from   │ Auto-injected via      │
│                   │ globPatterns          │ self.__WB_MANIFEST     │
│ Caching logic     │ Built-in Workbox      │ Custom logic with      │
│                   │ strategies            │ Workbox imports        │
│ Complexity        │ Low                   │ Medium-High            │
│ Use case          │ Simple PWA, static    │ Complex PWA, custom    │
│                   │ site, blog            │ caching, offline sync  │
│ Bundle size       │ Smaller (tree-shaken) │ Larger (full workbox)  │
└───────────────────┴───────────────────────┴────────────────────────┘
```

#### 8.3 Auto-Registration with vite-plugin-pwa

```typescript
// When registerType is 'autoUpdate', registration is automatic.
// For 'prompt', use the React hook:

// components/PwaPrompt.tsx
import { useRegisterSW } from 'virtual:pwa-register/react'

export function PwaPrompt() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegistered: (registration) => {
      console.log('SW registered:', registration)
      // Set up periodic SW update check
      setInterval(() => {
        registration?.update()
      }, 60 * 60 * 1000) // Check every hour
    },
    onRegisterError: (error) => {
      console.error('SW registration error:', error)
    },
  })

  if (!needRefresh) return null

  return (
    <div className="pwa-prompt" role="alert">
      <p>Pembaruan tersedia. Muat ulang untuk mendapatkan versi terbaru.</p>
      <div className="pwa-prompt-actions">
        <button onClick={() => setNeedRefresh(false)}>Nanti</button>
        <button onClick={() => updateServiceWorker(true)}>
          Muat Ulang
        </button>
      </div>
    </div>
  )
}
```

#### 8.4 Custom SW Entry for injectManifest

```typescript
// src/sw/index.ts — SW entry point
/// <reference types="vite-plugin-pwa/client" />
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching'
import { registerRoute, NavigationRoute, setDefaultHandler } from 'workbox-routing'
import { NetworkFirst, CacheFirst, StaleWhileRevalidate } from 'workbox-strategies'
import { ExpirationPlugin } from 'workbox-expiration'
import { CacheableResponsePlugin } from 'workbox-cacheable-response'
import { BackgroundSyncPlugin } from 'workbox-background-sync'

declare const self: ServiceWorkerGlobalScope
declare const clients: Clients

// ── Auto-precache (injected by build) ──
precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()

// ── Navigation route ──
registerRoute(
  new NavigationRoute(
    new NetworkFirst({
      cacheName: 'pages',
      plugins: [
        new ExpirationPlugin({ maxEntries: 20, maxAgeSeconds: 7 * 24 * 60 * 60 }),
        new CacheableResponsePlugin({ statuses: [200] }),
      ],
    })
  )
)

// ── Static assets ──
registerRoute(
  /\.(?:js|css)$/,
  new CacheFirst({
    cacheName: 'static',
    plugins: [
      new ExpirationPlugin({ maxEntries: 60, maxAgeSeconds: 30 * 24 * 60 * 60 }),
      new CacheableResponsePlugin({ statuses: [200] }),
    ],
  })
)

// ── Images ──
registerRoute(
  /\.(?:png|jpg|jpeg|webp|avif|svg|ico)$/,
  new CacheFirst({
    cacheName: 'images',
    plugins: [
      new ExpirationPlugin({ maxEntries: 80, maxAgeSeconds: 60 * 24 * 60 * 60 }),
      new CacheableResponsePlugin({ statuses: [200] }),
    ],
  })
)

// ── Fonts ──
registerRoute(
  /\.(?:woff2|woff|ttf|otf)$/,
  new CacheFirst({
    cacheName: 'fonts',
    plugins: [
      new ExpirationPlugin({ maxEntries: 10, maxAgeSeconds: 365 * 24 * 60 * 60 }),
      new CacheableResponsePlugin({ statuses: [200] }),
    ],
  })
)

// ── API ──
registerRoute(
  /\/api\/public\//,
  new StaleWhileRevalidate({
    cacheName: 'api-public',
    plugins: [
      new ExpirationPlugin({ maxEntries: 30, maxAgeSeconds: 5 * 60 }),
      new CacheableResponsePlugin({ statuses: [200] }),
    ],
  })
)

registerRoute(
  /\/api\/(?!auth|login|logout|token).*\/dashboard/,
  new NetworkFirst({
    cacheName: 'api-dashboard',
    plugins: [
      new ExpirationPlugin({ maxEntries: 10, maxAgeSeconds: 60 }),
      new CacheableResponsePlugin({ statuses: [200] }),
    ],
  })
)

// ── Default ──
setDefaultHandler(new NetworkOnly())

// ── Background sync ──
registerRoute(
  /\/api\/mutation\//,
  new NetworkOnly({ plugins: [
    new BackgroundSyncPlugin('mutation-queue', { maxRetentionTime: 24 * 60 }),
  ] }),
  'POST'
)

// ── Navigation preload ──
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    if (self.registration.navigationPreload) {
      await self.registration.navigationPreload.enable()
    }
  })())
})

// ── Message handling ──
self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})
```

---

### 9. PWA with Next.js

#### 9.1 next.config.js with next-pwa

```javascript
// next.config.js (Next.js 12-14)
const withPWA = require('@imbios/next-pwa')({
  dest: 'public',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
  runtimeCaching: [
    {
      urlPattern: /\.(?:js|css)$/,
      handler: 'CacheFirst',
      options: {
        cacheName: 'static',
        expiration: { maxEntries: 60, maxAgeSeconds: 30 * 24 * 60 * 60 },
      },
    },
    {
      urlPattern: /\.(?:png|jpg|jpeg|webp|svg)$/,
      handler: 'CacheFirst',
      options: {
        cacheName: 'images',
        expiration: { maxEntries: 50, maxAgeSeconds: 30 * 24 * 60 * 60 },
      },
    },
    {
      urlPattern: /^https?:\/\/.*\/_next\/data\/.+\/.+\.json$/,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'next-data',
        expiration: { maxEntries: 50, maxAgeSeconds: 7 * 24 * 60 * 60 },
      },
    },
    {
      urlPattern: /\/api\//,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'api',
        expiration: { maxEntries: 30, maxAgeSeconds: 5 * 60 },
      },
    },
  ],
})

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
}

module.exports = withPWA(nextConfig)
```

#### 9.2 Next.js App Router with PWA

For Next.js 15+ App Router, manage PWA directly without `next-pwa`:

```typescript
// app/manifest.ts — Dynamic manifest for App Router
import { type MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Kapuas Carbon PDD',
    short_name: 'Kapuas Carbon',
    description: 'Project Design Document for Kapuas Carbon Project',
    start_url: '/?source=pwa',
    display: 'standalone',
    display_override: ['window-controls-overlay', 'standalone'],
    background_color: '#ffffff',
    theme_color: '#1a6b3c',
    orientation: 'portrait-primary',
    lang: 'id',
    icons: [
      { src: '/icons/icon-192x192.png', sizes: '192x192', type: 'image/png' },
      { src: '/icons/icon-512x512.png', sizes: '512x512', type: 'image/png' },
    ],
    categories: ['environment', 'business'],
    shortcuts: [
      {
        name: 'Dashboard',
        url: '/dashboard?source=pwa-shortcut',
      },
    ],
  }
}
```

```xml
<!-- app/layout.tsx — Add manifest link -->
<!-- The manifest is auto-linked by Next.js when app/manifest.ts exists -->
```

```typescript
// Register service worker manually in App Router
// components/SwRegistrant.tsx
'use client'

import { useEffect } from 'react'

export function SwRegistrant() {
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js', {
        scope: '/',
        updateViaCache: 'none',
      }).catch(console.error)
    }
  }, [])

  return null
}
```

```typescript
// app/layout.tsx
import { SwRegistrant } from '@/components/SwRegistrant'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <head>
        <link rel="manifest" href="/manifest.webmanifest" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="theme-color" content="#1a6b3c" />
      </head>
      <body>
        <SwRegistrant />
        {children}
      </body>
    </html>
  )
}
```

#### 9.3 Static Export with PWA

```javascript
// next.config.js for static export + PWA
const withPWA = require('@imbios/next-pwa')({
  dest: 'public',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
})

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
}

module.exports = withPWA(nextConfig)
```

---

### 10. Performance

#### 10.1 Lighthouse PWA Audit Criteria

```
┌─────────────────────────────────────────────────────────────────────┐
│               LIGHTHOUSE PWA AUDIT CHECKLIST (v10+)                  │
│                                                                      │
│  INSTALLABLE (required for badge)                                    │
│  ☐ Registers a service worker                                        │
│  ☐ Responds with 200 on offline                                      │
│  ☐ Has a web app manifest with:                                      │
│     - name or short_name                                             │
│     - icons (192px + 512px)                                          │
│     - start_url                                                      │
│     - display (standalone/fullscreen/minimal-ui)                      │
│                                                                      │
│  PWA OPTIMIZED (pass/fail)                                           │
│  ☐ Loads fast on repeat visits (uses SW caching)                     │
│  ☐ HTTPS redirects to HTTPS                                          │
│  ☐ Page is responsive                                                │
│  ☐ Content is sized for viewport                                     │
│  ☐ Has a `<meta name="viewport">`                                    │
│  ☐ All text remains visible on font load                             │
│  ☐ Site works cross-browser                                          │
│  ☐ Page has `<title>`                                                │
│  ☐ Transitions are smooth (< 200ms response)                         │
│                                                                      │
│  ADDITIONAL (bonus)                                                  │
│  ☐ Splash screen (background_color + icons)                          │
│  ☐ address bar matches theme_color                                   │
│  ☐ maskable icon for Android                                         │
│  ☐ Shortcuts for quick actions                                       │
│  ☐ Screenshots for store listing                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### 10.2 Offline Speed Optimization

```typescript
// Minimize SW footprint:
// 1. Keep precache list small — only critical assets
const CRITICAL_ASSETS = [
  '/',
  '/offline',
  '/index.html',
  '/assets/main-*.js',     // Will be expanded by build tool
  '/assets/main-*.css',
  '/icons/icon-192x192.png',
]

// 2. Use stale-while-revalidate for large assets
// 3. Implement cache-first for all static assets
// 4. Use navigation preload
```

#### 10.3 First Load vs Repeat Load

```
┌─────────────────────┬───────────────────┬─────────────────────┐
│                     │   FIRST LOAD      │    REPEAT LOAD      │
├─────────────────────┼───────────────────┼─────────────────────┤
│ HTML                │ Network (server)  │ NetworkFirst (cache)│
│ JS/CSS (hashed)     │ Network (server)  │ CacheFirst (instant)│
│ Images              │ Network (server)  │ CacheFirst (instant)│
│ Fonts               │ Network (server)  │ CacheFirst (instant)│
│ API data            │ Network (server)  │ StaleWhileRevalidate│
│ SW install          │ Yes (async)       │ No (check for       │
│                     │                   │  update)            │
│ Time to interactive │ Normal            │ ~ 0ms (instant)     │
│ Data usage          │ Full download     │ Minimal (API only)  │
└─────────────────────┴───────────────────┴─────────────────────┘
```

#### 10.4 Minimizing SW Footprint

```typescript
// ❌ Bad: Cache everything
import { precacheAndRoute } from 'workbox-precaching'
precacheAndRoute(self.__WB_MANIFEST)  // Could be huge

// ✓ Good: Selective caching with limits
// In workbox config:
{
  globPatterns: ['**/*.{js,css,html,woff2}'],
  maximumFileSizeToCacheInBytes: 2 * 1024 * 1024, // 2 MB max per file
  globIgnores: [
    '**/*.map',           // Skip source maps
    '**/large-video.mp4', // Don't cache large media
    '**/admin/**',        // Skip admin section
  ],
}

// Use ExpirationPlugin for all runtime caches
new ExpirationPlugin({
  maxEntries: 50,
  maxAgeSeconds: 7 * 24 * 60 * 60,
  purgeOnQuotaError: true,
})
```

---

### 11. Testing PWA

#### 11.1 Lighthouse CI

```yaml
# .lighthouse/lighthouserc.json
{
  "ci": {
    "collect": {
      "method": "node",
      "numberOfRuns": 3,
      "settings": {
        "onlyCategories": ["performance", "pwa", "best-practices"],
        "preset": "desktop"
      }
    },
    "assert": {
      "assertions": {
        "service-worker": "error",
        "installable-manifest": "error",
        "works-offline": "error",
        "viewport": "error",
        "without-javascript": "error",
        "render-blocking-resources": "warn",
        "offscreen-images": "warn",
        "maskable-icon": "warn",
        "splash-screen": "warn",
        "themed-omnibox": "warn"
      }
    },
    "upload": {
      "target": "filesystem",
      "outputDir": ".lighthouse/reports"
    }
  }
}
```

```yaml
# GitHub Actions workflow
# .github/workflows/lighthouse.yml
name: Lighthouse CI
on: [push]
jobs:
  lighthouse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: npm ci
      - run: npm run build
      - run: npx serve -s dist -l 3000 &
      - run: npx @lhci/cli@0.14.x autorun --config=.lighthouse/lighthouserc.json
      - uses: actions/upload-artifact@v4
        with:
          name: lighthouse-reports
          path: .lighthouse/reports
```

#### 11.2 Manual Testing Checklist

```typescript
// DevTools > Application > Service Workers
// Test these scenarios:

export const PWATestScenarios = [
  {
    name: 'SW Registration',
    steps: [
      'Open DevTools > Application > Service Workers',
      'Verify SW status is "activated and is running"',
      'Verify scope is "/"',
    ],
  },
  {
    name: 'Offline Mode',
    steps: [
      'Open DevTools > Network tab',
      'Check "Offline" checkbox',
      'Reload page',
      'Verify offline fallback page appears',
      'Navigate to cached pages — should work',
      'Navigate to uncached pages — should show offline page',
    ],
  },
  {
    name: 'Cache Storage',
    steps: [
      'Open DevTools > Application > Cache Storage',
      'Verify caches exist (pages, static, images, api, etc.)',
      'Check cache content matches expected URLs',
      'Verify cache expiration works (check timestamps)',
    ],
  },
  {
    name: 'Manifest Validation',
    steps: [
      'Open DevTools > Application > Manifest',
      'Verify all fields display correctly',
      'Verify icons load (192px, 512px)',
      'Click "Add to home screen" — verify prompt',
    ],
  },
  {
    name: 'Push Notifications',
    steps: [
      'Open DevTools > Application > Service Workers',
      'Click "Push" to simulate push event',
      'Verify notification appears',
      'Click notification — verify navigation',
    ],
  },
  {
    name: 'Background Sync',
    steps: [
      'Go offline',
      'Submit form data',
      'Go online',
      'Verify data was synced',
      'Check DevTools > Application > Background Services',
    ],
  },
  {
    name: 'Update Flow',
    steps: [
      'Deploy new SW version',
      'Navigate site',
      'Verify update prompt appears',
      'Click "Update"',
      'Verify page reloads with new version',
    ],
  },
]
```

#### 11.3 Automated PWA Tests with Playwright

```typescript
// tests/pwa.spec.ts
import { test, expect } from '@playwright/test'

test.describe('PWA Tests', () => {
  test('service worker is registered', async ({ page }) => {
    await page.goto('/')

    const hasSW = await page.evaluate(() => {
      return 'serviceWorker' in navigator
    })
    expect(hasSW).toBe(true)

    const registration = await page.evaluate(async () => {
      const reg = await navigator.serviceWorker.getRegistration()
      return {
        scope: reg?.scope,
        state: reg?.active?.state,
      }
    })

    expect(registration.scope).toBe('http://localhost:3000/')
    expect(registration.state).toBe('activated')
  })

  test('manifest is valid', async ({ page }) => {
    await page.goto('/')

    const manifest = await page.evaluate(async () => {
      const response = await fetch('/manifest.json')
      return response.json()
    })

    expect(manifest.name).toBeTruthy()
    expect(manifest.short_name).toBeTruthy()
    expect(manifest.icons).toHaveLength(2)
    expect(manifest.display).toBe('standalone')
    expect(manifest.start_url).toBeTruthy()
  })

  test('works offline', async ({ page, context }) => {
    await page.goto('/')
    // Wait for SW to be active
    await page.waitForTimeout(2000)

    // Go offline
    await context.setOffline(true)
    await page.reload()

    // Should show offline fallback or cached page
    await expect(page.locator('body')).not.toBeEmpty()
    const title = await page.title()
    expect(title).toBeTruthy()

    await context.setOffline(false)
  })

  test('precached assets are available offline', async ({ page, context }) => {
    await page.goto('/')
    await page.waitForTimeout(2000)

    const cachedURLs = await page.evaluate(async () => {
      const cache = await caches.open('static-v1')
      const keys = await cache.keys()
      return keys.map((r) => r.url)
    })

    expect(cachedURLs.length).toBeGreaterThan(0)
  })
})
```

---

### 12. Deployment

#### 12.1 HTTPS Requirement

```
Service Worker hanya bekerja di secure context (HTTPS), kecuali:
- localhost (dev)
- 127.0.0.1
- *.localhost (some browsers)

Deployment checklist:
☐ SSL certificate valid (Let's Encrypt / Cloudflare / paid CA)
☐ HSTS header: Strict-Transport-Security: max-age=31536000
☐ Redirect HTTP → HTTPS (301)
☐ No mixed content (all resources loaded via HTTPS)
```

```nginx
# nginx.conf — HTTPS + HSTS
server {
    listen 443 ssl http2;
    server_name kapuascarbon.id;

    ssl_certificate /etc/letsencrypt/live/kapuascarbon.id/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kapuascarbon.id/privkey.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    root /var/www/kapuas-pdd/dist;
    index index.html;

    # SW scope must match the manifest scope
    location /sw.js {
        add_header Cache-Control "no-cache";
        add_header Service-Worker-Allowed "/";
    }

    location / {
        try_files $uri /index.html;
    }
}

server {
    listen 80;
    server_name kapuascarbon.id;
    return 301 https://$host$request_uri;
}
```

#### 12.2 Manifest Validation

```bash
# Validate manifest using pwabuilder
npx pwabuilder-validator https://kapuascarbon.id/manifest.json

# Or use the Chrome DevTools protocol
# Lighthouse audit covers manifest validation

# Validate icons are correct size
npx sharp-cli --input ./public/icons/icon-512x512.png --resize 192 --output ./public/icons/icon-192x192.png
```

#### 12.3 Service Worker Scope

```
SW scope = the directory where sw.js is located, by default.
To expand scope, use Service-Worker-Allowed header or set scope in registration.

┌──────────────────────────────┬──────────────────────────┐
│ SW location                  │ Scope                    │
├──────────────────────────────┼──────────────────────────┤
│ /sw.js                       │ /                        │
│ /dashboard/sw.js             │ /dashboard/              │
│ /subdir/sw.js                │ /subdir/                 │
│ /sw.js + header: "/"         │ / (expanded with header) │
└──────────────────────────────┴──────────────────────────┘

Scope expansion requires:
1. Service-Worker-Allowed: / header on sw.js response
2. Or scope param: navigator.serviceWorker.register('/sw.js', { scope: '/' })
```

#### 12.4 Update Prompt UI Pattern

```typescript
// components/UpdatePrompt.tsx — Complete pattern
'use client'

import { useEffect, useState } from 'react'

interface UpdateState {
  type: 'checking' | 'available' | 'downloading' | 'ready' | 'none'
  registration?: ServiceWorkerRegistration
}

export function UpdateManager() {
  const [state, setState] = useState<UpdateState>({ type: 'checking' })

  useEffect(() => {
    if (!('serviceWorker' in navigator)) {
      setState({ type: 'none' })
      return
    }

    // Navigate to trigger SW update check with the new Service Worker
    const handleControllerChange = () => {
      window.location.reload()
    }
    navigator.serviceWorker.addEventListener('controllerchange', handleControllerChange)

    // Set up periodic check
    const checkInterval = setInterval(async () => {
      const registration = await navigator.serviceWorker.getRegistration()
      if (registration) {
        await registration.update()
      }
    }, 60 * 60 * 1000) // Every hour

    return () => {
      navigator.serviceWorker.removeEventListener('controllerchange', handleControllerChange)
      clearInterval(checkInterval)
    }
  }, [])

  // Listen for update events
  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail
      setState({
        type: (detail.registration as any)?.installing ? 'downloading' : 'available',
        registration: detail.registration,
      })
    }

    window.addEventListener('sw-update-available', handler)
    return () => window.removeEventListener('sw-update-available', handler)
  }, [])

  const handleUpdate = () => {
    if (state.registration?.waiting) {
      state.registration.waiting.postMessage({ type: 'SKIP_WAITING' })
    }
  }

  if (state.type === 'checking' || state.type === 'none') return null

  return (
    <div className="update-banner" role="alert">
      <div className="update-banner-content">
        <span className="update-icon" aria-hidden="true">📥</span>
        <p>
          {state.type === 'downloading'
            ? 'Mengunduh pembaruan...'
            : 'Versi baru tersedia.'}
        </p>
        {state.type === 'available' && (
          <button onClick={handleUpdate} className="update-button">
            Perbarui
          </button>
        )}
      </div>
    </div>
  )
}
```

#### 12.5 Versioning

```typescript
// sw/version.ts — Track version across SW updates
const SW_VERSION = '1.2.0'
const CACHE_PREFIX = 'kapuas'

function getCacheName(name: string): string {
  return `${CACHE_PREFIX}-${name}-${SW_VERSION}`
}

// On activate, delete any cache that doesn't match current version
self.addEventListener('activate', (event) => {
  const expectedCaches = [
    getCacheName('pages'),
    getCacheName('static'),
    getCacheName('images'),
    getCacheName('fonts'),
    getCacheName('api'),
  ]

  event.waitUntil(
    (async () => {
      const cacheNames = await caches.keys()

      await Promise.all(
        cacheNames
          .filter((name) => !expectedCaches.includes(name))
          .map((name) => caches.delete(name))
      )

      await self.clients.claim()

      // Broadcast version to clients
      const clients = await self.clients.matchAll()
      clients.forEach((client) => {
        client.postMessage({
          type: 'SW_VERSION',
          version: SW_VERSION,
        })
      })
    })()
  )
})
```

---

### 13. Security

#### 13.1 HTTPS Mandatory

```
All PWA features require secure context:
- Service Worker registration
- Cache API
- Push Notifications
- Background Sync
- Geolocation
- MediaDevices

Exception: localhost, 127.0.0.1, and file:// (limited) for development.
```

#### 13.2 Service Worker Scope Restriction

```typescript
// SW scope cannot be expanded beyond the SW file's directory
// unless Service-Worker-Allowed header permits it.

// ❌ Bad: SW in /subdir/ trying to intercept /
// This will fail unless Service-Worker-Allowed: / header is sent

// ✓ Good: SW at root level or scope set correctly
navigator.serviceWorker.register('/sw.js', { scope: '/' })

// Security: SW can only intercept requests within its scope
// A SW in /dashboard/ cannot intercept /admin/ or /api/auth/
```

#### 13.3 Message Validation

```typescript
// SW message handler — always validate origin + payload
self.addEventListener('message', (event: ExtendableMessageEvent) => {
  // Validate source
  if (!event.source) return

  // For client messages, validate URL
  if (event.source instanceof Client) {
    const url = new URL(event.source.url)

    // Only accept messages from our own origin
    if (url.origin !== self.location.origin) return

    // Only accept from specific pages
    const allowedPaths = ['/', '/dashboard', '/settings']
    if (!allowedPaths.includes(url.pathname)) return
  }

  // Validate payload structure
  if (!event.data || typeof event.data !== 'object') return
  if (!event.data.type || typeof event.data.type !== 'string') return

  // Whitelist allowed message types
  const allowedTypes = ['SKIP_WAITING', 'CLEAR_CACHE', 'CHECK_UPDATE']
  if (!allowedTypes.includes(event.data.type)) return

  // Execute
  switch (event.data.type) {
    case 'SKIP_WAITING':
      self.skipWaiting()
      break
    case 'CLEAR_CACHE':
      clearAllCaches()
      break
    case 'CHECK_UPDATE':
      self.registration.update()
      break
  }
})

async function clearAllCaches(): Promise<void> {
  const cacheNames = await caches.keys()
  await Promise.all(cacheNames.map((name) => caches.delete(name)))
}
```

#### 13.4 XSS in Service Worker

```typescript
// ❌ Bad: Dynamic import/eval in SW
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  // eval is blocked in SW (Content Security Policy)
  // eval(url.searchParams.get('code')) — will throw

  // Dynamic import may fail
  // import(url.searchParams.get('module')) — CSP may block
})

// ❌ Bad: Using user input in cache keys
self.addEventListener('fetch', (event) => {
  const userInput = event.request.url.split('?')[1]
  // Could lead to cache poisoning
  caches.open(userInput)
})

// ✓ Good: Validate all inputs
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  // Only process our origin
  if (url.origin !== self.location.origin) return

  // Use fixed cache names
  caches.open('static-v1')
})
```

#### 13.5 Content Security Policy for SW

```http
# HTTP Headers for SW
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; worker-src 'self' blob:
Service-Worker-Allowed: /
```

#### 13.6 No eval in SW

```
The `eval()` function and `new Function()` are not available in Service Workers.
This is enforced by CSP (Content Security Policy) in Chromium browsers.

Workbox and all Workbox-using SW code MUST use strict CSP-compatible patterns.
No code generation, no dynamic function creation.

✓ Allowed:
  - Static imports
  - Template literals
  - Arrow functions
  - Regular expressions

❌ Blocked:
  - eval()
  - new Function()
  - setTimeout(string)
  - setInterval(string)
```

---

### 14. File Convention

#### 14.1 Folder Structure for SW Files

```
project-root/
├── public/
│   ├── icons/
│   │   ├── icon-72x72.png        # Chrome (optional)
│   │   ├── icon-96x96.png        # Chrome (optional)
│   │   ├── icon-128x128.png      # Chrome (optional)
│   │   ├── icon-144x144.png      # IE / MS app tiles
│   │   ├── icon-152x152.png      # iOS Safari
│   │   ├── icon-192x192.png      # PWA required (any maskable)
│   │   ├── icon-384x384.png      # Chrome (optional)
│   │   ├── icon-512x512.png      # PWA required (any maskable)
│   │   ├── icon-512x512-maskable.png  # PWA maskable variant
│   │   └── badge-96x96.png       # Notification badge
│   ├── screenshots/
│   │   ├── desktop-1.png         # Wide form factor (1920x1080)
│   │   ├── mobile-1.png          # Narrow form factor (750x1334)
│   │   └── mobile-2.png          # Additional mobile screenshot
│   ├── manifest.json             # Or manifest.webmanifest
│   ├── sw.js                     # Generated (or hand-written)
│   ├── offline.html              # Offline fallback page
│   └── favicon.ico
├── src/
│   ├── sw/                       # Service worker source (injectManifest)
│   │   ├── index.ts              # Entry point
│   │   ├── install.ts            # Install handler
│   │   ├── activate.ts           # Activate handler
│   │   ├── fetch.ts              # Fetch handler + routing
│   │   ├── notifications.ts      # Push notification handlers
│   │   ├── sync.ts               # Background sync handler
│   │   ├── messaging.ts          # Message handler
│   │   └── version.ts            # Version constants
│   ├── hooks/
│   │   ├── useSwUpdate.ts        # SW update detection hook
│   │   ├── useOnlineStatus.ts    # Online/offline hook
│   │   └── usePushSubscription.ts # Push subscription hook
│   ├── lib/
│   │   ├── pwa.ts                # PWA utility functions
│   │   ├── offline-db.ts         # IndexedDB offline helpers
│   │   ├── offline-analytics.ts   # Offline analytics queue
│   │   └── sw-register.ts        # SW registration logic
│   └── components/
│       ├── UpdatePrompt.tsx       # SW update UI
│       ├── PwaInstallPrompt.tsx   # Install prompt UI
│       ├── OfflineIndicator.tsx   # Network status indicator
│       └── PushPermissionPrompt.tsx # Push permission UI
├── vite.config.ts                 # Vite + vite-plugin-pwa config
├── workbox-config.js              # Standalone workbox config (optional)
└── tests/
    └── pwa.spec.ts                # PWA Playwright tests
```

#### 14.2 Icon Generation Script

```typescript
// scripts/generate-pwa-icons.ts
// Run: npx tsx scripts/generate-pwa-icons.ts
import sharp from 'sharp'
import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const SOURCE = 'public/icon-source.svg' // Your master source (1024x1024 minimum)
const OUT_DIR = 'public/icons'

const ICONS = [
  { size: 72, name: 'icon-72x72.png' },
  { size: 96, name: 'icon-96x96.png' },
  { size: 128, name: 'icon-128x128.png' },
  { size: 144, name: 'icon-144x144.png' },
  { size: 152, name: 'icon-152x152.png' },
  { size: 192, name: 'icon-192x192.png' },
  { size: 384, name: 'icon-384x384.png' },
  { size: 512, name: 'icon-512x512.png' },
  { size: 512, name: 'icon-512x512-maskable.png' },
  { size: 96, name: 'badge-96x96.png' },
]

async function generateIcons(): Promise<void> {
  const sourceBuffer = readFileSync(SOURCE)

  for (const icon of ICONS) {
    const output = join(OUT_DIR, icon.name)

    // Default: resize with padding
    let pipeline = sharp(sourceBuffer).resize(icon.size, icon.size, {
      fit: 'contain',
      background: { r: 255, g: 255, b: 255, alpha: 0 },
    })

    // Maskable variant: ensure full bleed
    if (icon.name.includes('maskable')) {
      pipeline = sharp(sourceBuffer).resize(icon.size, icon.size, {
        fit: 'cover',
      })
    }

    await pipeline.png().toFile(output)
    console.log(`Generated: ${icon.name} (${icon.size}x${icon.size})`)
  }
}

generateIcons().catch(console.error)
```

---

### 15. Anti-Patterns

#### 15.1 Caching Everything

```typescript
// ❌ BAD: Cache ALL requests with same strategy
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  )
})

// Problems:
// - Caches API responses that should be fresh
// - Caches large files (videos, PDFs) until quota exceeded
// - Caches authenticated data that may leak between users
// - No cache expiration → stale data forever

// ✓ GOOD: Selective caching by URL pattern
registerRoute(
  /\.(?:js|css|woff2)$/,
  new CacheFirst({ cacheName: 'static', plugins: [expirationPlugin] })
)
registerRoute(
  /\/api\/auth\//,
  new NetworkOnly()
)
```

#### 15.2 No Cache Purge

```typescript
// ❌ BAD: No cache cleanup on activate
self.addEventListener('activate', (event) => {
  // Does nothing — old caches pile up forever
})

// ✓ GOOD: Clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const cacheNames = await caches.keys()
      const expected = ['static-v2', 'pages-v2', 'api-v2']
      await Promise.all(
        cacheNames
          .filter((name) => !expected.includes(name))
          .map((name) => caches.delete(name))
      )
    })()
  )
})
```

#### 15.3 Too Large Cache Storage

```typescript
// ❌ BAD: No size/entry limits
registerRoute(
  /\.(?:png|jpg)$/,
  new CacheFirst({ cacheName: 'images' }) // No expiration!
)

// ✓ GOOD: Set limits
registerRoute(
  /\.(?:png|jpg)$/,
  new CacheFirst({
    cacheName: 'images',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 80,
        maxAgeSeconds: 60 * 24 * 60 * 60, // 60 hari
        purgeOnQuotaError: true,
      }),
    ],
  })
)
```

#### 15.4 SW Blocking Update

```typescript
// ❌ BAD: SW never calls skipWaiting or clients.claim
self.addEventListener('install', () => {
  // No skipWaiting → new SW waits forever
})

// ✓ GOOD: Activate immediately
self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', () => {
  self.clients.claim()
})
```

#### 15.5 No Fallback for Offline

```typescript
// ❌ BAD: Network-only with no offline fallback
self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request)) // Fails offline
  }
})

// ✓ GOOD: NetworkFirst with offline fallback
self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          return await fetch(event.request)
        } catch {
          const cache = await caches.open('static-v1')
          const offline = await cache.match('/offline')
          return offline || new Response('Offline', { status: 503 })
        }
      })()
    )
  }
})
```

#### 15.6 Over-Caching Dynamic Content

```typescript
// ❌ BAD: Cache-first for user-specific API
registerRoute(
  /\/api\/user\/profile/,
  new CacheFirst() // Caches user A's data for user B!
)

// ✓ GOOD: NetworkFirst or NetworkOnly for user-specific endpoints
registerRoute(
  /\/api\/user\//,
  new NetworkFirst({
    cacheName: 'api-user',
    plugins: [
      new CacheableResponsePlugin({
        statuses: [200],
        headers: { 'X-Cache-User': 'true' }, // Custom header to signal cacheability
      }),
    ],
  })
)

// Even better: Don't cache user-specific data at all for sensitive apps
registerRoute(
  /\/api\/user\/profile|settings|preferences/,
  new NetworkOnly()
)
```

#### 15.7 Anti-Pattern Summary

```
┌──────────────────────────────┬─────────────────────────────┬─────────────────────┐
│          ANTI-PATTERN         │          PROBLEM            │      SOLUTION        │
├──────────────────────────────┼─────────────────────────────┼─────────────────────┤
│ Caching everything            │ Quota exceeded, stale data │ Selective caching    │
│ No cache purge                │ Disk filled with old caches │ Clean on activate    │
│ No size limits                │ Cache grows unbounded       │ ExpirationPlugin     │
│ SW never calls skipWaiting    │ Update never activates      │ skipWaiting()        │
│ No offline fallback           │ Broken offline experience   │ Offline page         │
│ Caching user-specific data    │ Data leak between users     │ NetworkOnly auth     │
│ Caching large media files     │ Quota exceeded quickly      │ Stream / skip cache  │
│ Using SW as CDN               │ SW becomes bottleneck       │ Minimize SW logic    │
│ No message validation         │ XSS via postMessage         │ Validate origin+type │
│ Over-relying on SW for SEO    │ SW can't index              │ SSR + SW for PWA     │
│ Not testing offline           │ Broken user experience      │ Playwright offline    │
└──────────────────────────────┴─────────────────────────────┴─────────────────────┘
```

---

### 16. Implementation Checklist

#### Phase 1: Foundation (Prerequisites)

```
☐ HTTPS configured with valid SSL certificate
☐ Responsive design implemented and tested
☐ Cross-browser tested (Chrome, Edge, Firefox, Safari)
☐ Build tool configured (Vite / Next.js)
```

#### Phase 2: Web App Manifest

```
☐ manifest.json created with all required fields
☐ Icons generated (192x192 + 512x512 + maskable variant)
☐ Icons optimized (PNG compression)
☐ Manifest linked in <head>
☐ iOS meta tags added (apple-touch-icon, apple-mobile-web-app-capable)
☐ theme-color meta tags (light + dark)
☐ Screenshots created (wide + narrow)
☐ Shortcuts defined for key pages
☐ Manifest validated with pwabuilder-validator
```

#### Phase 3: Service Worker

```
☐ SW registered with scope "/"
☐ Install handler: precache critical assets
☐ Activate handler: clean old caches + clients.claim()
☐ Fetch handler: caching strategies for different resource types
☐ Navigation route configured (NetworkFirst with offline fallback)
☐ Offline fallback page created
☐ Navigation preload enabled
☐ Message handler for SW update (SKIP_WAITING)
☐ Update prompt UI implemented
☐ Periodic SW update check (hourly)
```

#### Phase 4: Caching

```
☐ Static assets: CacheFirst with versioned cache names
☐ Images: CacheFirst with ExpirationPlugin
☐ Fonts: CacheFirst with long TTL (1 year)
☐ API (public): StaleWhileRevalidate
☐ API (critical): NetworkFirst
☐ API (auth): NetworkOnly
☐ HTML navigation: NetworkFirst
☐ Cache expiration set for all runtime caches
☐ purgeOnQuotaError enabled
☐ Opaque responses handled (status 0)
```

#### Phase 5: Offline & Sync

```
☐ Offline fallback page (/offline) designed and implemented
☐ IndexedDB setup for offline data storage
☐ Offline mutation queue implemented
☐ Background Sync registered and handled
☐ Periodic Sync implemented for content refresh
☐ Online/offline event listeners
☐ Offline analytics queue (non-blocking)
☐ Offline indicator UI component
```

#### Phase 6: Push Notifications

```
☐ VAPID keys generated
☐ Push subscription implemented
☐ Permission request flow designed (user gesture)
☐ Subscription stored on server
☐ Push event handler in SW
☐ Notification click handler implemented
☐ Notification actions defined
☐ Unsubscribe flow implemented
☐ Expired subscription cleanup
```

#### Phase 7: Testing

```
☐ Lighthouse PWA audit passes (installable + optimized)
☐ Offline testing: page load, navigation, cached assets
☐ Push notification testing (simulated via DevTools)
☐ Background sync testing
☐ SW update flow testing
☐ Cross-browser testing
☐ Playwright PWA tests written
☐ Lighthouse CI configured
☐ Storage quota testing (cache doesn't exceed limits)
```

#### Phase 8: Deployment

```
☐ HTTPS verified
☐ HSTS header configured
☐ SW cache headers (Cache-Control: no-cache for sw.js)
☐ Service-Worker-Allowed header (if scope expansion needed)
☐ manifest.json validates server-side
☐ Icons server and are accessible
☐ Build produces optimized SW bundle
☐ Deployment tested end-to-end
☐ Performance measured (first load vs repeat load)
```

---

### Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PWA QUICK REFERENCE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Manifest location: <link rel="manifest" href="/manifest.json">      │
│  SW registration:  navigator.serviceWorker.register('/sw.js')       │
│  SW scope:         Default = SW directory; expand with header        │
│  Cache API:        caches.open(name).then(c => c.match(req))         │
│  Precaching:       workbox-precaching.precacheAndRoute(manifest)     │
│  Background Sync:  self.registration.sync.register('tag')            │
│  Push subscribe:   registration.pushManager.subscribe({              │
│                      userVisibleOnly: true,                          │
│                      applicationServerKey: vapidKey,                 │
│                    })                                                │
│  Install detect:   beforeinstallprompt event + display-mode:standalone│
│  Update detect:    registration.onupdatefound + statechange          │
│  Offline detect:   navigator.onLine + online/offline events          │
│                                                                      │
│  Tools:                                                              │
│  - Workbox: https://developer.chrome.com/docs/workbox/               │
│  - PWABuilder: https://pwabuilder.com/                               │
│  - Lighthouse: https://developer.chrome.com/docs/lighthouse/         │
│  - web-push: https://www.npmjs.com/package/web-push                  │
│  - vite-plugin-pwa: https://vite-pwa-org.netlify.app/                │
│  - next-pwa: https://github.com/imbios/next-pwa                     │
│                                                                      │
│  Specs:                                                              │
│  - Web App Manifest: W3C Spec                                        │
│  - Service Worker: W3C Spec                                          │
│  - Web Push Protocol: RFC 8292 + RFC 8030                            │
│  - VAPID: RFC 8292                                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```
