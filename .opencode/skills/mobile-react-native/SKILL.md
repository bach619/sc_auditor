---
name: mobile-react-native
description: React Native (0.76+) + Expo SDK 52+: Fabric/TurboModules/JSI architecture, Expo Router v4, React Navigation, EAS Build, offline-first (WatermelonDB, CRDT sync), TanStack Query, FlashList, Hermes, push notifications, testing, and deployment
license: MIT
compatibility: opencode
metadata:
  audience: mobile-developers
  domain: mobile
  paradigm: cross-platform-native
  capabilities:
    - new-architecture
    - expo-router
    - offline-first
    - push-notifications
    - eas-build
    - flashlist-performance
    - hermes-engine
    - testing-rntl-detox
  integrates_with:
    - frontend-react
    - mobile-flutter
    - database-postgres
    - security-crypto
    - ai-rag
---

## Mobile React Native + Expo Skill

### 1. Architecture Overview — RN New Architecture

React Native 0.76+ ships **New Architecture** by default.

```
┌──────────────────────────────────────────────────────────────┐
│                     REACT NATIVE APP                          │
│  ┌──────────────────┐    ┌──────────────────────────────┐    │
│  │  JavaScript       │    │  Native (C++/ObjC/Java/Kt)   │    │
│  │  (Hermes Engine)  │    │  ┌──────────┐ ┌──────────┐  │    │
│  │  React Reconcil.  │◄───│►│ Fabric   │ │Turbo     │  │    │
│  │  State/Effects    │ JSI│  │ Renderer │ │Modules   │  │    │
│  └──────────────────┘    │  └──────────┘ └──────────┘  │    │
│         │                │  ┌──────────────────────┐  │    │
│         ▼                │  │ Codegen              │  │    │
│  ┌─────────────────┐    │  │ (native specs auto)  │  │    │
│  │ JSI (JS Interf) │    │  └──────────────────────┘  │    │
│  │ sync C++↔JS     │    └──────────────────────────────┘    │
│  │ shared memory   │                                         │
│  │ direct native   │                                         │
│  └─────────────────┘                                         │
└──────────────────────────────────────────────────────────────┘
```

#### Fabric Renderer
- **Synchronous layout**: C++ layout engine shared across platforms
- **State updates**: Direct commit to shadow tree via JSI
- **Events**: Priority-based dispatch (discrete vs continuous)
- **Mounting**: Atomic commits — no partial UI updates

#### TurboModules
- **Lazy loading**: Native modules loaded on first access
- **Type-safe specs**: Codegen generates typed interfaces
- **Sync/async**: Synchronous calls via JSI (no bridge serialization)
- **Memory**: Modules deallocated when unused

#### JSI (JavaScript Interface)
- **Zero-copy**: Pass `ArrayBuffer`/`TypedArray` directly to native
- **Thread-safe**: C++ objects accessible from any thread
- **No JSON serialization**: Native methods receive JS values directly

#### Old Bridge (Legacy)
```
JS Thread → Serialize JSON → Bridge Queue → Deserialize → Native
           ← Serialize JSON ← Bridge Queue ← Deserialize ←
```
- **Asynchronous only**: Every native call through message queue
- **Serialization overhead**: JSON parse/stringify on every call

#### Enable New Architecture
```json
{
  "expo": {
    "newArchEnabled": true
  }
}
```

### 2. Expo vs RN CLI — Decision Tree

```
                  START
                    │
                    ▼
       Need native module not in Expo?
         YES                NO
          │                  │
          ▼                  ▼
   Custom native code?   Expo SDK 52
    YES       NO         (managed)
     │         │         250+ modules
     ▼         ▼         OTA updates
   RN CLI    Expo        EAS Build
   (bare)    prebuild    Dev Client
```

#### Expo (Managed) — 90%+ of apps
- CRUD, social, marketplace, MVP/Prototype
- 250+ modules, OTA updates without store review
- EAS Build for CI/CD without native setup

#### Expo Prebuild
- Custom native modules with Expo wrapper
- `expo prebuild` generates ios/android, still eject-safe

#### RN CLI (Bare)
- Heavy native integration: Bluetooth, ARKit, CoreML
- Complex native codebases, custom Metal/OpenGL
- Full control over native build pipeline

```bash
# Expo (recommended)
npx create-expo-app@latest MyApp

# Expo with prebuild (escape hatch)
npx create-expo-app@latest MyApp; npx expo prebuild

# RN CLI (only when Expo can't handle it)
npx @react-native-community/cli init MyApp
```

### 3. Expo Router v4 — File-Based Routing

```
app/
├── _layout.tsx              # Root layout (Stack)
├── index.tsx                # Initial screen (/)
├── (auth)/
│   ├── _layout.tsx          # Auth group layout (no path prefix)
│   ├── login.tsx            # /login
│   └── register.tsx         # /register
├── (tabs)/
│   ├── _layout.tsx          # Tab navigator
│   ├── index.tsx            # / (home tab)
│   ├── explore.tsx          # /explore
│   └── profile/
│       ├── _layout.tsx      # Stack within tab
│       ├── index.tsx        # /profile
│       └── settings.tsx     # /profile/settings
├── product/
│   └── [id].tsx             # /product/123 (dynamic)
├── modal.tsx                # Modal presentation
└── +not-found.tsx           # 404 catch-all
```

#### Root Layout
```tsx
import { Stack } from 'expo-router'
import { StatusBar } from 'expo-status-bar'

export default function RootLayout() {
  return (
    <>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false, animation: 'slide_from_right' }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="modal" options={{ presentation: 'modal' }} />
        <Stack.Screen name="+not-found" />
      </Stack>
    </>
  )
}
```

#### Tab Layout
```tsx
import { Tabs } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'

export default function TabLayout() {
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: '#6366f1' }}>
      <Tabs.Screen name="index" options={{ title: 'Home', tabBarIcon: ({ color, size }) => <Ionicons name="home" size={size} color={color} /> }} />
      <Tabs.Screen name="explore" options={{ title: 'Explore', tabBarIcon: ({ color, size }) => <Ionicons name="search" size={size} color={color} /> }} />
      <Tabs.Screen name="profile" options={{ title: 'Profile', tabBarIcon: ({ color, size }) => <Ionicons name="person" size={size} color={color} /> }} />
    </Tabs>
  )
}
```

#### Dynamic Routes
```tsx
import { useLocalSearchParams, router } from 'expo-router'
import { View, Text, Button } from 'react-native'

export default function ProductDetail() {
  const { id } = useLocalSearchParams<{ id: string }>()
  return (
    <View>
      <Text>Product {id}</Text>
      <Button title="Back" onPress={() => router.back()} />
    </View>
  )
}
```

#### Group Routes — no path prefix
```tsx
// app/(auth)/login.tsx → accessible at /login (not /auth/login)
export default function AuthLayout() {
  return <Stack screenOptions={{ headerShown: false }} />
}
```

### 4. React Navigation — Stack, Tab, Drawer, Deep Linking

For apps that outgrow Expo Router or need custom navigation logic.

#### Stack Navigator
```tsx
import { createNativeStackNavigator } from '@react-navigation/native-stack'

type RootStackParamList = {
  Home: undefined
  ProductDetail: { id: string }
  ReviewForm: { productId: string }
}

const Stack = createNativeStackNavigator<RootStackParamList>()

export function RootNavigator() {
  return (
    <Stack.Navigator screenOptions={{ animation: 'slide_from_right' }}>
      <Stack.Screen name="Home" component={HomeScreen} />
      <Stack.Screen name="ProductDetail" component={ProductDetailScreen} />
      <Stack.Screen name="ReviewForm" component={ReviewFormScreen} />
    </Stack.Navigator>
  )
}
```

#### Deep Linking
```tsx
// linking.ts
import type { LinkingOptions } from '@react-navigation/native'

export const linking: LinkingOptions<RootStackParamList> = {
  prefixes: ['myapp://', 'https://myapp.com'],
  config: {
    screens: {
      Home: '',
      ProductDetail: 'product/:id',
      ReviewForm: 'product/:productId/review',
      Profile: { screens: { Index: 'profile', Settings: 'profile/settings' } },
    },
  },
}

// App.tsx
import { NavigationContainer } from '@react-navigation/native'
export default function App() {
  return (
    <NavigationContainer linking={linking} fallback={<SplashScreen />}>
      <RootNavigator />
    </NavigationContainer>
  )
}
```

#### Drawer Navigator
```tsx
import { createDrawerNavigator } from '@react-navigation/drawer'

const Drawer = createDrawerNavigator()

export function DrawerNavigator() {
  return (
    <Drawer.Navigator
      drawerContent={(props) => <CustomDrawerContent {...props} />}
      screenOptions={{ drawerType: 'front', drawerStyle: { width: 280 } }}
    >
      <Drawer.Screen name="Dashboard" component={DashboardScreen} />
      <Drawer.Screen name="Reports" component={ReportsScreen} />
    </Drawer.Navigator>
  )
}
```

### 5. UI Components — NativeWind

#### NativeWind (Tailwind for RN)
```bash
npx expo install nativewind tailwindcss
```

```ts
// tailwind.config.js
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#6366f1', 50: '#eef2ff' },
        surface: { DEFAULT: '#ffffff', dark: '#1c1c1e' },
      },
    },
  },
}
```

```ts
// global.css — Required for NativeWind v4
@tailwind base;
@tailwind components;
@tailwind utilities;
```

```tsx
import { View, Text, TouchableOpacity } from 'react-native'

export function ProductCard({ title, price }: { title: string; price: number }) {
  return (
    <View className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm">
      <Text className="text-lg font-semibold text-gray-900 dark:text-white">{title}</Text>
      <Text className="text-xl font-bold text-primary mt-1">${price.toFixed(2)}</Text>
      <TouchableOpacity className="bg-primary rounded-lg px-4 py-2 mt-3">
        <Text className="text-white font-medium text-center">Add to Cart</Text>
      </TouchableOpacity>
    </View>
  )
}
```

#### Button Component with class-variance-authority
```tsx
import { TouchableOpacity, Text, ActivityIndicator } from 'react-native'
import { cva, type VariantProps } from 'class-variance-authority'

const button = cva('flex-row items-center justify-center rounded-lg px-4 py-3', {
  variants: {
    variant: { primary: 'bg-primary', secondary: 'bg-gray-100', outline: 'border border-primary bg-transparent', destructive: 'bg-red-500' },
    size: { sm: 'px-3 py-2', md: 'px-4 py-3', lg: 'px-6 py-4' },
    fullWidth: { true: 'w-full' },
  },
  defaultVariants: { variant: 'primary', size: 'md' },
})

type Props = VariantProps<typeof button> & { title: string; loading?: boolean; onPress: () => void }

export function Button({ title, loading, variant, size, fullWidth, onPress }: Props) {
  return (
    <TouchableOpacity onPress={onPress} disabled={loading} className={button({ variant, size, fullWidth })}>
      {loading && <ActivityIndicator className="mr-2" />}
      <Text className={variant === 'primary' ? 'text-white font-medium' : 'text-primary font-medium'}>{title}</Text>
    </TouchableOpacity>
  )
}
```

### 6. State Management — Zustand + MMKV

```bash
npx expo install zustand react-native-mmkv
```

#### Cart Store with MMKV Persistence
```ts
// stores/cart-store.ts
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { MMKV } from 'react-native-mmkv'

const storage = new MMKV({ id: 'cart-storage' })

interface CartItem { id: string; name: string; price: number; quantity: number }
interface CartStore {
  items: CartItem[]
  addItem: (item: Omit<CartItem, 'quantity'>) => void
  removeItem: (id: string) => void
  updateQuantity: (id: string, qty: number) => void
  clearCart: () => void
}

export const useCartStore = create<CartStore>()(
  persist(
    (set) => ({
      items: [],
      addItem: (item) =>
        set((s) => {
          const existing = s.items.find((i) => i.id === item.id)
          return existing
            ? { items: s.items.map((i) => (i.id === item.id ? { ...i, quantity: i.quantity + 1 } : i)) }
            : { items: [...s.items, { ...item, quantity: 1 }] }
        }),
      removeItem: (id) => set((s) => ({ items: s.items.filter((i) => i.id !== id) })),
      updateQuantity: (id, qty) => set((s) => ({ items: s.items.map((i) => (i.id === id ? { ...i, quantity: Math.max(0, qty) } : i)) })),
      clearCart: () => set({ items: [] }),
    }),
    {
      name: 'cart-storage',
      storage: createJSONStorage(() => ({
        getItem: (key) => storage.getString(key) ?? null,
        setItem: (key, value) => storage.set(key, value),
        removeItem: (key) => storage.delete(key),
      })),
      partialize: (s) => ({ items: s.items }),
    }
  )
)
```

#### Selector Optimization
```tsx
// ❌ Bad: entire store subscription — re-renders on ANY change
const { items, addItem } = useCartStore()

// ✅ Good: selector-based — re-renders only when `items` changes
const items = useCartStore((state) => state.items)
const addItem = useCartStore((state) => state.addItem)

// ✅ Best: shallow comparison for complex selectors
import { shallow } from 'zustand/shallow'
const [items, count] = useCartStore((s) => [s.items, s.items.length], shallow)
```

### 7. Offline-First — WatermelonDB, SQLite, Sync

#### Architecture
```
┌──────────────────────┐
│    Cloud Server       │
│  (PostgreSQL + API)   │
└──────────┬───────────┘
           │ sync (pull/push)
┌──────────▼───────────┐
│   Local Database      │
│  (WatermelonDB/SQLite)│
│  • Pulled records     │
│  • Pending mutations  │
│  • Cached responses   │
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│    React Native App   │
│  • Observe local DB   │
│  • Write locally      │
│  • Queue mutations    │
│  • Show optimistic UI │
└──────────────────────┘
```

#### Sync Protocol
```
CLIENT                          SERVER
  │                               │
  │── GET /api/sync?since=TS ────►│  PULL: Get changes since timestamp
  │◄── { records, deleted, TS } ──│
  │                               │
  │── POST /api/sync ────────────►│  PUSH: Send local mutations
  │  [{type:'created', table, id, │
  │    record, timestamp}]        │
  │◄── { applied, conflicts } ────│
  │                               │
  │  Resolve conflicts (LWW)      │
  │  Re-pull to reconcile         │
```

#### WatermelonDB Setup
```bash
npx expo install @nozbe/watermelondb @nozbe/with-observables react-native-sqlite-storage
```

```ts
// db/schema.ts
import { appSchema, tableSchema } from '@nozbe/watermelondb'

export const schema = appSchema({
  version: 1,
  tables: [
    tableSchema({
      name: 'products',
      columns: [
        { name: 'name', type: 'string' },
        { name: 'price', type: 'number' },
        { name: 'image_url', type: 'string' },
        { name: 'category_id', type: 'string', isIndexed: true },
        { name: 'is_synced', type: 'boolean' },
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ],
    }),
    tableSchema({
      name: 'categories',
      columns: [{ name: 'name', type: 'string' }, { name: 'sort_order', type: 'number' }],
    }),
  ],
})
```

```ts
// db/models/Product.ts
import { Model } from '@nozbe/watermelondb'
import { field, date, readonly, relation } from '@nozbe/watermelondb/decorators'

export default class Product extends Model {
  static table = 'products'
  static associations = { categories: { type: 'belongs_to' as const, key: 'category_id' } }

  @field('name') name!: string
  @field('price') price!: number
  @field('image_url') imageUrl!: string
  @field('category_id') categoryId!: string
  @field('is_synced') isSynced!: boolean
  @readonly @date('created_at') createdAt!: Date
  @readonly @date('updated_at') updatedAt!: Date
  @relation('categories', 'category_id') category: any
}
```

```ts
// db/sync.ts
import { synchronize } from '@nozbe/watermelondb/sync'
import { database } from './index'
import { api } from '@/lib/api'

export async function syncDatabase() {
  await synchronize({
    database,
    pullChanges: async ({ lastPulledAt }) => {
      const response = await api.syncPull({ since: lastPulledAt ?? 0 })
      return { changes: response.changes, timestamp: response.timestamp }
    },
    pushChanges: async ({ changes, lastPulledAt }) => {
      const mutations = extractMutations(changes)
      await api.syncPush({ mutations, lastPulledAt })
    },
    migrationsEnabledAtVersion: 1,
  })
}
```

#### Expo SQLite (Simpler Alternative)
```bash
npx expo install expo-sqlite
```

```ts
import * as SQLite from 'expo-sqlite'

const db = await SQLite.openDatabaseAsync('app.db')

await db.execAsync(`
  CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, price REAL NOT NULL,
    category_id TEXT, image_url TEXT, synced_at INTEGER
  )
`)

export async function getProducts() {
  return await db.getAllAsync<Product>('SELECT * FROM products ORDER BY name')
}

export async function upsertProduct(p: Product) {
  await db.runAsync(
    'INSERT OR REPLACE INTO products (id, name, price, category_id, image_url, synced_at) VALUES (?, ?, ?, ?, ?, ?)',
    [p.id, p.name, p.price, p.categoryId, p.imageUrl, Date.now()]
  )
}
```

#### Offline Queue
```ts
// lib/offline-queue.ts
import * as SQLite from 'expo-sqlite'

interface Mutation {
  id: string; type: 'create' | 'update' | 'delete'; table: string
  recordId: string; payload: string | null; retries: number
}

export class OfflineQueue {
  constructor(private db: SQLite.SQLiteDatabase) { this.init() }

  private async init() {
    await this.db.execAsync(`CREATE TABLE IF NOT EXISTS offline_queue (
      id TEXT PRIMARY KEY, type TEXT NOT NULL, table_name TEXT NOT NULL,
      record_id TEXT NOT NULL, payload TEXT, created_at INTEGER NOT NULL, retries INTEGER DEFAULT 0
    )`)
  }

  async enqueue(type: Mutation['type'], table: string, recordId: string, payload?: any) {
    await this.db.runAsync(
      'INSERT INTO offline_queue (id, type, table_name, record_id, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)',
      [`${Date.now()}-${Math.random().toString(36).slice(2)}`, type, table, recordId, payload ? JSON.stringify(payload) : null, Date.now()]
    )
  }

  async dequeue(): Promise<Mutation | null> {
    const row = await this.db.getFirstAsync<Mutation>('SELECT * FROM offline_queue ORDER BY created_at ASC LIMIT 1')
    if (row) await this.db.runAsync('DELETE FROM offline_queue WHERE id = ?', [row.id])
    return row
  }

  async processAll(handler: (m: Mutation) => Promise<void>) {
    let m = await this.dequeue()
    while (m) {
      try { await handler(m) } catch (e) {
        console.error('Mutation failed:', m.id, e)
        if (m.retries < 5) await this.db.runAsync('UPDATE offline_queue SET retries = retries + 1 WHERE id = ?', [m.id])
      }
      m = await this.dequeue()
    }
  }
}
```

### 8. Data Fetching — TanStack Query

```bash
npx expo install @tanstack/react-query
```

#### Query Client + Offline Support
```ts
// lib/query-client.ts
import { QueryClient, onlineManager } from '@tanstack/react-query'
import { createAsyncStoragePersister } from '@tanstack/query-async-storage-persister'
import AsyncStorage from '@react-native-async-storage/async-storage'
import NetInfo from '@react-native-community/netinfo'

onlineManager.setEventListener((setOnline) =>
  NetInfo.addEventListener((s) => setOnline(!!s.isConnected))
)

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5 * 60 * 1000, gcTime: 24 * 60 * 60 * 1000, retry: 2, retryDelay: (a) => Math.min(1000 * 2 ** a, 10000), networkMode: 'offlineFirst' },
    mutations: { networkMode: 'offlineFirst' },
  },
})

export const asyncPersister = createAsyncStoragePersister({
  storage: AsyncStorage,
  key: 'REACT_QUERY_OFFLINE_CACHE',
})
```

#### Custom Hooks
```ts
// hooks/useProducts.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { offlineQueue } from '@/lib/offline-init'
import { useOfflineStore } from '@/stores/offline-store'

export function useProducts(categoryId?: string) {
  return useQuery({
    queryKey: ['products', { categoryId }],
    queryFn: () => api.getProducts(categoryId),
  })
}

export function useCreateProduct() {
  const qc = useQueryClient()
  const isOnline = useOfflineStore((s) => s.isOnline)

  return useMutation({
    mutationFn: async (data: CreateProductInput) =>
      isOnline ? api.createProduct(data) : (await offlineQueue.enqueue('create', 'products', `temp-${Date.now()}`, data), { id: `temp-${Date.now()}`, ...data }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['products'] }),
  })
}

export function useDeleteProduct() {
  const qc = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => api.deleteProduct(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['products'] })
      const prev = qc.getQueryData(['products'])
      qc.setQueryData(['products'], (old: any[]) => old.filter((p) => p.id !== id))
      return { prev }
    },
    onError: (_, __, ctx) => { qc.setQueryData(['products'], ctx?.prev) },
    onSettled: () => qc.invalidateQueries({ queryKey: ['products'] }),
  })
}
```

#### Infinite Scroll
```tsx
import { useInfiniteQuery } from '@tanstack/react-query'
import { FlatList, ActivityIndicator } from 'react-native'

export function ProductListScreen() {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ['products-infinite'],
    queryFn: ({ pageParam = 0 }) => api.getProductsPaginated({ offset: pageParam, limit: 20 }),
    getNextPageParam: (last) => last.nextOffset ?? undefined,
    initialPageParam: 0,
  })

  const products = data?.pages.flatMap((p) => p.items) ?? []

  return (
    <FlatList
      data={products}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => <ProductCard product={item} />}
      onEndReached={() => !isFetchingNextPage && hasNextPage && fetchNextPage()}
      onEndReachedThreshold={0.5}
      ListFooterComponent={isFetchingNextPage ? <ActivityIndicator /> : null}
    />
  )
}
```

### 9. Push Notifications

```bash
npx expo install expo-notifications expo-device expo-constants
```

#### Registration
```ts
// lib/notifications.ts
import * as Notifications from 'expo-notifications'
import * as Device from 'expo-device'
import Constants from 'expo-constants'
import { Platform } from 'react-native'

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowAlert: true, shouldPlaySound: true, shouldSetBadge: true }),
})

export async function registerPushNotifications() {
  if (!Device.isDevice) { return null }

  const { status: existing } = await Notifications.getPermissionsAsync()
  const { status } = existing === 'granted' ? { status: existing } : await Notifications.requestPermissionsAsync()

  if (status !== 'granted') return null

  const projectId = Constants.expoConfig?.extra?.eas?.projectId
  if (!projectId) return null

  const token = await Notifications.getExpoPushTokenAsync({ projectId })
  await api.registerPushToken(token.data)

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'default',
      importance: Notifications.AndroidImportance.MAX,
    })
  }

  return token.data
}
```

#### Handling Notifications
```ts
// hooks/useNotifications.ts
import { useEffect } from 'react'
import * as Notifications from 'expo-notifications'
import { router } from 'expo-router'

export function useNotificationHandler() {
  useEffect(() => {
    const received = Notifications.addNotificationReceivedListener((n) =>
      console.log('Notif:', n.request.content.data)
    )
    const tapped = Notifications.addNotificationResponseReceivedListener((r) => {
      const data = r.notification.request.content.data
      if (data?.screen) router.push({ pathname: data.screen, params: data.params })
    })
    return () => { received.remove(); tapped.remove() }
  }, [])
}
```

#### Backend Push (Node.js)
```ts
import { Expo } from 'expo-server-sdk'
const expo = new Expo()

export async function sendPush(token: string, title: string, body: string, data?: any) {
  if (!Expo.isExpoPushToken(token)) return

  const chunks = expo.chunkPushNotifications([{ to: token, sound: 'default', title, body, data, priority: 'high' }])
  for (const chunk of chunks) await expo.sendPushNotificationsAsync(chunk)
}
```

### 10. EAS Build & Submit

#### Configuration
```json
{
  "expo": {
    "name": "MyApp",
    "slug": "my-app",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "splash": { "image": "./assets/splash.png", "resizeMode": "contain", "backgroundColor": "#ffffff" },
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.mycompany.myapp",
      "infoPlist": {
        "NSCameraUsageDescription": "Camera access for product photos",
        "NSPhotoLibraryUsageDescription": "Photo library access for profile pictures"
      }
    },
    "android": {
      "package": "com.mycompany.myapp",
      "adaptiveIcon": { "foregroundImage": "./assets/adaptive-icon.png", "backgroundColor": "#ffffff" }
    },
    "plugins": ["expo-router", "expo-secure-store", "expo-notifications"],
    "extra": { "eas": { "projectId": "your-project-id" } }
  }
}
```

#### eas.json
```json
{
  "cli": { "version": ">= 10.0.0" },
  "build": {
    "development": { "developmentClient": true, "distribution": "internal", "ios": { "simulator": true }, "android": { "buildType": "apk" } },
    "preview": { "distribution": "internal", "android": { "buildType": "apk" }, "env": { "APP_ENV": "staging" } },
    "production": { "autoIncrement": true, "env": { "APP_ENV": "production" } }
  },
  "submit": {
    "production": {
      "ios": { "appleId": "apple@developer.com", "ascAppId": "123456789", "appleTeamId": "ABCDEF1234" },
      "android": { "serviceAccountKeyPath": "./path/to/service-account.json", "track": "production" }
    }
  }
}
```

#### CI/CD
```yaml
name: EAS Build
on:
  push: { branches: [main] }
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: 'npm' }
      - uses: expo/expo-github-action@v8
        with: { eas-version: latest, token: '${{ secrets.EXPO_TOKEN }}' }
      - run: npm ci
      - run: npx expo lint && npx tsc --noEmit
      - run: eas build --platform all --profile preview --non-interactive
```

#### EAS Update (OTA)
```bash
eas update --branch production --message "Hotfix: checkout crash"
eas update --branch production --message "Rollback v1" --republish
```

```ts
// app/_layout.tsx — Update listener
import * as Updates from 'expo-updates'
import { Alert } from 'react-native'

useEffect(() => {
  (async () => {
    const update = await Updates.checkForUpdateAsync()
    if (update.isAvailable) {
      await Updates.fetchUpdateAsync()
      Alert.alert('Update Available', 'Restart to apply?', [
        { text: 'Later', style: 'cancel' },
        { text: 'Restart', onPress: () => Updates.reloadAsync() },
      ])
    }
  })()
}, [])
```

### 11. Performance

#### FlashList vs FlatList
```tsx
// ✅ FlashList — recycled views, 10-100x faster
import { FlashList } from '@shopify/flash-list'

export function ProductList({ products }: { products: Product[] }) {
  return (
    <FlashList
      data={products}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => <ProductCard product={item} />}
      estimatedItemSize={120}          // CRITICAL: measure or estimate
      getItemType={(item) => item.category}
    />
  )
}
```

#### Image Optimization
```tsx
// ✅ expo-image — caching, blurhash, transition
import { Image } from 'expo-image'

export function OptimizedImage({ uri }: { uri: string }) {
  return (
    <Image
      source={{ uri }}
      placeholder={{ blurhash: 'LKO2?U%2Tw=w]~RjRjt7%Mj[WBay' }}
      contentFit="cover"
      transition={300}
      cachePolicy="memory-disk"
      style={{ width: '100%', height: 200, borderRadius: 12 }}
    />
  )
}
```

#### Hermes Engine
```json
{
  "expo": {
    "jsEngine": "hermes",
    "ios": { "jsEngine": "hermes" },
    "android": { "jsEngine": "hermes" }
  }
}
```

#### Bundle Optimization
```ts
// metro.config.js
const { getDefaultConfig } = require('expo/metro-config')
const config = getDefaultConfig(__dirname)
config.transformer.minifierConfig = {
  compress: { drop_console: true, drop_debugger: true, pure_funcs: ['console.log'] },
}
config.transformer.getTransformOptions = async () => ({
  transform: { experimentalImportSupport: true, inlineRequires: true },
})
module.exports = config
```

```bash
npx expo export --platform web
npx expo-analyzer bundle
```

#### Performance Checklist
```tsx
// 1. InteractionManager for non-critical work
import { InteractionManager } from 'react-native'
useEffect(() => { InteractionManager.runAfterInteractions(() => loadHeavyData()) }, [])

// 2. useMemo for expensive computations
const sorted = useMemo(() => [...products].sort((a, b) => a.price - b.price), [products])

// 3. useCallback for stable refs
const handlePress = useCallback((id: string) => router.push(`/product/${id}`), [])

// 4. React.memo for pure components
const ProductCard = React.memo(function ProductCard({ product, onPress }: Props) {
  return <TouchableOpacity onPress={() => onPress(product.id)}><Text>{product.name}</Text></TouchableOpacity>
})

// 5. Avoid anonymous functions in renderItem
const renderItem = useCallback(({ item }: { item: Product }) => <ProductCard product={item} />, [])
```

### 12. Testing

```bash
npx expo install jest-expo @testing-library/react-native
```

#### Jest Config
```ts
import type { Config } from 'jest'
const config: Config = {
  preset: 'jest-expo',
  transformIgnorePatterns: ['node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|react-navigation|@react-navigation/.*)'],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
  clearMocks: true,
}
export default config
```

```ts
// jest.setup.ts
import '@testing-library/jest-native/extend-expect'
jest.mock('expo-router', () => ({
  Stack: { Screen: jest.fn(), Navigator: jest.fn() },
  Tabs: { Screen: jest.fn(), Navigator: jest.fn() },
  useRouter: () => ({ push: jest.fn(), back: jest.fn() }),
  useLocalSearchParams: () => ({}),
  router: { push: jest.fn(), back: jest.fn() },
}))
jest.mock('expo-secure-store', () => ({ getItemAsync: jest.fn(), setItemAsync: jest.fn(), deleteItemAsync: jest.fn() }))
```

#### Component Tests (RNTL)
```tsx
import { render, fireEvent, screen } from '@testing-library/react-native'
import { ProductCard } from '@/components/ProductCard'

const product = { id: '1', name: 'Test', price: 29.99, image: 'https://img.com/p.jpg' }

describe('ProductCard', () => {
  it('renders product info', () => {
    render(<ProductCard product={product} onPress={jest.fn()} />)
    expect(screen.getByText('Test')).toBeTruthy()
    expect(screen.getByText('$29.99')).toBeTruthy()
  })

  it('calls onPress', () => {
    const onPress = jest.fn()
    render(<ProductCard product={product} onPress={onPress} />)
    fireEvent.press(screen.getByRole('button'))
    expect(onPress).toHaveBeenCalledWith('1')
  })
})
```

#### Hook Tests
```tsx
import { renderHook, waitFor } from '@testing-library/react-native'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useProducts } from '@/hooks/useProducts'

const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>

describe('useProducts', () => {
  it('returns products on success', async () => {
    const { result } = renderHook(() => useProducts(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(10)
  })

  it('handles error', async () => {
    jest.spyOn(api, 'getProducts').mockRejectedValueOnce(new Error('Network error'))
    const { result } = renderHook(() => useProducts(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
```

#### Detox E2E
```bash
npx detox init -r jest
```

```ts
describe('Product Flow', () => {
  beforeAll(async () => { await device.launchApp() })

  it('shows product list', async () => {
    await expect(element(by.id('product-list'))).toBeVisible()
  })

  it('navigates to detail on tap', async () => {
    await element(by.id('product-card-1')).tap()
    await expect(element(by.id('product-name'))).toHaveText('Test Product')
  })

  it('handles offline state', async () => {
    await device.setStatusBar({ mode: 'airplane' })
    await element(by.id('product-card-2')).tap()
    await expect(element(by.id('offline-banner'))).toBeVisible()
  })
})
```

### 13. Security

#### SecureStore
```ts
import * as SecureStore from 'expo-secure-store'

export async function saveSecure(key: string, value: string) {
  await SecureStore.setItemAsync(key, value, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  })
}

export async function getSecure(key: string) { return await SecureStore.getItemAsync(key) }
export async function deleteSecure(key: string) { await SecureStore.deleteItemAsync(key) }
```

#### Biometric Auth
```tsx
import * as LocalAuthentication from 'expo-local-authentication'

export async function authenticate() {
  const hasHardware = await LocalAuthentication.hasHardwareAsync()
  if (!hasHardware) throw new Error('No biometric hardware')

  const enrolled = await LocalAuthentication.isEnrolledAsync()
  if (!enrolled) throw new Error('No biometrics enrolled')

  const result = await LocalAuthentication.authenticateAsync({
    promptMessage: 'Authenticate to access account',
    fallbackLabel: 'Use passcode',
  })

  return result.success
}

// Protect sensitive routes
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState(false)
  useEffect(() => { (async () => setAuthed(await authenticate()))() }, [])
  if (!authed) return <UnauthorizedScreen />
  return <>{children}</>
}
```

#### SSL Pinning & App Attestation
```ts
// react-native-ssl-pinning
import { fetch } from 'react-native-ssl-pinning'

export async function secureApiCall(endpoint: string) {
  return await fetch(`https://api.myapp.com${endpoint}`, {
    sslPinning: { cert: 'sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=' },
    timeoutInterval: 10000,
  })
}
```

```ts
// Jailbreak/root detection
import * as Application from 'expo-application'

export async function verifyIntegrity() {
  if (Platform.OS === 'ios') {
    const canEditSystem = await canAccessPath('/private/var/lib/apt')
    if (canEditSystem) throw new Error('Jailbroken device')
  }
  if (Platform.OS === 'android') {
    const { response } = await api.getPlayIntegrityToken()
    if (!response.isVerified) throw new Error('Integrity check failed')
  }
}
```

### 14. Deployment

#### App Store
```bash
eas build --platform ios --profile production
eas submit --platform ios --profile production
```

#### Google Play
```bash
eas build --platform android --profile production
eas submit --platform android --profile production
```

#### OTA Updates
```bash
eas update --branch production --message "Hotfix v2.1.1"
eas branch:create staging
eas update --branch staging --message "RC v2.2.0"
```

```json
{
  "expo": {
    "updates": {
      "url": "https://u.expo.dev/your-project-id",
      "fallbackToCacheTimeout": 0,
      "checkAutomatically": "ON_LOAD",
      "enabled": true
    }
  }
}
```

### 15. File Convention — Folder Structure

```
my-app/
├── app/                          # Expo Router v4 routes
│   ├── _layout.tsx               # Root layout
│   ├── index.tsx                 # /
│   ├── (auth)/                   # Auth group (no prefix)
│   ├── (tabs)/                   # Tab navigator
│   ├── product/[id].tsx          # Dynamic route
│   └── modal.tsx                 # Modal sheet
├── assets/                       # Images, fonts, animations
├── components/
│   ├── ui/                       # Base UI (Button, Input, Card)
│   ├── layout/                   # Layout (Header, SafeArea)
│   └── product/                  # Domain (ProductCard)
├── constants/                    # Theme, layout, API endpoints
├── db/                           # Database
│   ├── index.ts                  # Init
│   ├── schema.ts                 # WatermelonDB schema
│   ├── models/                   # WatermelonDB models
│   └── sync.ts                   # Sync logic
├── hooks/                        # TanStack Query + custom hooks
├── lib/                          # API client, query-client, offline-queue
├── providers/                    # Auth, Query, Theme providers
├── stores/                       # Zustand stores
├── types/                        # Navigation, API, domain types
├── utils/                        # Formatters, validators
├── __tests__/                    # Unit & component tests
├── e2e/                          # Detox E2E tests
├── .env                          # Environment variables
├── app.json                      # Expo config
├── eas.json                      # EAS Build config
├── metro.config.js               # Metro bundler
├── tailwind.config.js            # NativeWind
├── tsconfig.json
├── jest.config.ts
└── package.json
```

### 16. Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Over-using React Context | Every context change re-renders ALL consumers | Use Zustand for global state; Context only for static values (theme) |
| Ignoring offline states | Blank screen on network drop; data loss | TanStack Query `networkMode: 'offlineFirst'`; WatermelonDB; offline mutation queue |
| FlatList without optimization | 60fps drops on lists >50 items | Use `FlashList` with `estimatedItemSize`; `React.memo` items |
| No Hermes | 2x slower JS; 30% larger bundle | Enable Hermes in `app.json` |
| Setting state in render | Infinite re-render loop | Move to `useEffect` or event handlers |
| Dimensions.get('window') once | Doesn't update on orientation change | Use `useWindowDimensions()` hook |
| Storing secrets in AsyncStorage | AsyncStorage is unencrypted | Use `expo-secure-store` for tokens; never store API keys client-side |
| Inline styles in renderItem | New StyleSheet every render; GC pressure | Use `StyleSheet.create` or NativeWind classes |
| Not debouncing search | API call on every keystroke | `useDebounce` hook with 300-500ms delay |
| Monolithic components | Hard to test; re-renders entire tree | Split into small components; extract logic to hooks/stores |
| Not handling keyboard | Input hidden behind keyboard | `KeyboardAvoidingView` with `behavior={Platform.OS === 'ios' ? 'padding' : 'height'}` |
| Blocking main thread with JSON/Images | UI freezes during parsing | `InteractionManager.runAfterInteractions`; `expo-image` for optimized decoding |
| Lazy loading all modules at startup | Slow cold start | Dynamic imports; code-split with Metro |
| Testing only on iOS | Android-specific bugs (back button, permissions) | Test on both platforms; use physical devices for camera/notifications |
| Ignoring accessibility | App unusable by screen readers | `accessibilityLabel`/`accessibilityRole` on all interactive elements; test with VoiceOver/TalkBack |

### 17. Implementation Checklist

#### Phase 1: Foundation
- [ ] `npx create-expo-app@latest` + TypeScript strict mode
- [ ] NativeWind + Tailwind config
- [ ] ESLint + Prettier
- [ ] Folder structure per convention
- [ ] `app.json` with name, slug, version
- [ ] EAS project (`eas init`); `eas.json` profiles (dev/preview/production)
- [ ] Hermes enabled
- [ ] Environment variables (`.env`, EAS secrets)

#### Phase 2: Navigation
- [ ] Expo Router v4 root layout
- [ ] Auth flow group (login/register)
- [ ] Tab navigator (3-5 tabs)
- [ ] Stack navigators within tabs
- [ ] Modal screen
- [ ] Deep linking with `expo-linking`
- [ ] Universal links / App Links

#### Phase 3: State & Data
- [ ] TanStack Query client
- [ ] MMKV storage for Zustand persistence
- [ ] Auth store with token persistence
- [ ] `onlineManager` connected to NetInfo
- [ ] Query persistence with `persistQueryClient`
- [ ] API client with retry + timeout
- [ ] Offline mutation queue

#### Phase 4: Local DB & Sync
- [ ] WatermelonDB or expo-sqlite
- [ ] Schema + models
- [ ] Pull-based sync protocol
- [ ] Push with conflict resolution (LWW)
- [ ] Sync status indicators in UI
- [ ] Background sync

#### Phase 5: UI Components
- [ ] Base components (Button, Input, Card, Badge, Avatar)
- [ ] Loading skeletons
- [ ] Error boundary
- [ ] Empty state components
- [ ] Pull-to-refresh
- [ ] FlashList for all large lists
- [ ] `expo-image` with blurhash

#### Phase 6: Push Notifications
- [ ] Register + permissions
- [ ] Foreground handler
- [ ] Notification tap → deep navigation
- [ ] Push tokens to backend
- [ ] Android notification channels

#### Phase 7: Security
- [ ] SecureStore for tokens
- [ ] Biometric auth for sensitive screens
- [ ] SSL pinning for API
- [ ] Jailbreak/root detection
- [ ] App attestation (DeviceCheck / Play Integrity)
- [ ] Input sanitization

#### Phase 8: Testing
- [ ] Jest + jest-expo preset
- [ ] Mock all native modules
- [ ] Unit tests for Zustand stores
- [ ] Component tests with RNTL
- [ ] Hook tests with renderHook
- [ ] Offline behavior tests
- [ ] Detox E2E with basic flows
- [ ] Cross-platform testing
- [ ] CI pipeline tests

#### Phase 9: Performance
- [ ] Profile with React DevTools on device
- [ ] FlashList optimization (`estimatedItemSize`, `getItemType`)
- [ ] React.memo on list items
- [ ] useCallback / useMemo
- [ ] Remove console.log in production
- [ ] Optimize images
- [ ] Hermes profiler
- [ ] Bundle size analysis
- [ ] Test on low-end Android device

#### Phase 10: Deployment
- [ ] EAS Build profiles configured
- [ ] Development build on device
- [ ] Preview distribution
- [ ] TestFlight / internal test track
- [ ] Fix submission warnings
- [ ] First EAS Update (OTA)
- [ ] Auto-increment versioning
- [ ] Production build + store submission
- [ ] Crash reporting (Sentry/Crashlytics)
- [ ] CI/CD pipeline (GitHub Actions)

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| `Invariant Violation: TurboModuleRegistry` | Library incompatible with New Architecture | Check library's Fabric support | Set `newArchEnabled: false` temporarily; find compatible version |
| `FlashList: estimatedItemSize not provided` | Missing essential perf prop | Console warning | Measure item height and pass `estimatedItemSize` |
| White screen on Android release | Hermes bytecode mismatch | Check Metro logs | `eas build --platform android --clear-cache` |
| Push not arriving iOS | Missing entitlements or wrong token | Check `app.json` entitlements | Add `expo-notifications` plugin; verify APNs key |
| Network request failed offline | TanStack Query not configured | Check `networkMode` | Set `networkMode: 'offlineFirst'` + NetInfo `onlineManager` |
| EAS Build: "No such module" | Cocoapods not synced | Check Podfile.lock | `eas build --platform ios --local --clear-cache` |
| Keyboard avoiding not working | Wrong `behavior` prop | Test both platforms | `Platform.OS === 'ios' ? 'padding' : 'height'` |
| Expo Router route not found | File path mismatch | Check file naming | Ensure files match route segments; groups `(g)` don't add path |
| Slow cold start | Too many sync modules | Hermes profiler | Lazy imports; `InteractionManager` for non-critical work |
| NativeWind styles not applying | Missing babel plugin | Check `babel.config.js` | Add `plugins: ['nativewind/babel']`; verify tailwind `content` paths |
| Detox can't find element | No `testID` prop | Check component | Add `testID` to all interactive elements |
| MMKV storage corrupted | App killed during write | Check MMKV logs | Add write transaction guard with try/finally |
