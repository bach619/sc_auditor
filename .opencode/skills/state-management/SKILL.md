---
name: state-management
description: "React State Management dewa: Zustand v5, Jotai, TanStack Query, Context/useReducer, URL State (nuqs). Decision tree, performance, testing, anti-patterns, file convention. 12 sections, 600+ lines, real TypeScript code."
---

# State Management for React — Tingkat Dewa

> React 19 + TypeScript — Zustand v5.0, Jotai 2.x, TanStack Query v5, nuqs v2

---

## 1. State Management Decision Tree

```
┌─────────────────────────────────────────────────────────────────┐
│                    PERTANYAAN AWAL                              │
│          "Data ini datang dari mana dan untuk apa?"             │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
          ┌─────────────────┐    ┌─────────────────────┐
          │  Dari SERVER?   │    │  Dibuat di CLIENT?  │
          │  (API/DB/WS)    │    │  (UI state, form,   │
          │                 │    │   modal, filter)     │
          └────────┬────────┘    └──────────┬──────────┘
                   │                        │
                   ▼                        ▼
          ┌─────────────────┐    ┌─────────────────────┐
          │  TanStack Query │    │  Apakah state ini   │
          │  (server cache) │    │  perlu di URL?      │
          │                 │    │                     │
          │  ┌───────────┐  │    ├── YA ─────► nuqs   │
          │  │ Mutations │  │    │                     │
          │  │ Optimistic│  │    └── TIDAK ───────────►│
          │  │ Cache inv │  │            │            │
          │  └───────────┘  │            ▼            │
          └─────────────────┘    ┌─────────────────────┐
                                 │  Frekuensi?         │
                                 │                     │
                    ┌────────────┼─────┬───────────┐   │
                    ▼            ▼     ▼           ▼   │
               High-freq    Medium   Low-freq    ─────┘
               (animasi,    (complex  (theme,
                scroll,     form,     lang,
                cursor)     wizard)   auth)
                    │            │        │
                    ▼            ▼        ▼
               ┌────────┐ ┌──────────┐ ┌────────┐
               │ Jotai  │ │ Zustand  │ │Context │
               │ atoms  │ │ slices   │ │(sparse)│
               │ derived│ │ immer    │ │        │
               │ async  │ │ persist  │ └────────┘
               └────────┘ └──────────┘
```

### Ringkasan Decision Tree

| Jenis State | Tools | Alasan |
|---|---|---|
| **Server state** (data dari API) | TanStack Query | Deduplikasi request, caching, background refetch, optimistic update |
| **URL state** (filter, page, search) | nuqs | Shareable, back/button, bookmarkable |
| **Global client state** (auth, theme, cart) | Zustand | Sederhana, middleware built-in, slices pattern |
| **High-frequency** (animasi, form field) | Jotai | Atomic re-render, no selector needed |
| **Complex state transitions** (multi-step wizard) | Zustand + immer | Immer untuk immutable update nyaman |
| **Low-frequency global** (theme, locale) | Context | Built-in, zero dependency, sparse updates |
| **Local UI state** (modal open, toggle) | `useState` | Local, tidak perlu global |

---

## 2. Zustand v5

### 2.1 Basic Store

```typescript
import { create } from 'zustand'

interface BearStore {
  bears: number
  increase: () => void
  reset: () => void
}

export const useBearStore = create<BearStore>()((set) => ({
  bears: 0,
  increase: () => set((state) => ({ bears: state.bears + 1 })),
  reset: () => set({ bears: 0 }),
}))
```

### 2.2 Slices Pattern

```typescript
import { create, StateCreator } from 'zustand'

interface AuthSlice {
  user: { id: string; name: string } | null
  login: (user: AuthSlice['user']) => void
  logout: () => void
}

interface CartSlice {
  items: Array<{ id: string; qty: number }>
  addItem: (id: string) => void
  removeItem: (id: string) => void
}

const createAuthSlice: StateCreator<AuthSlice & CartSlice, [], [], AuthSlice> = (set) => ({
  user: null,
  login: (user) => set({ user }),
  logout: () => set({ user: null }),
})

const createCartSlice: StateCreator<AuthSlice & CartSlice, [], [], CartSlice> = (set, get) => ({
  items: [],
  addItem: (id) => set((state) => ({ items: [...state.items, { id, qty: 1 }] })),
  removeItem: (id) => set((state) => ({ items: state.items.filter((i) => i.id !== id) })),
})

export const useBoundStore = create<AuthSlice & CartSlice>()((...a) => ({
  ...createAuthSlice(...a),
  ...createCartSlice(...a),
}))
```

Cross-slice access via `get()`:

```typescript
const createCartSlice: StateCreator<AuthSlice & CartSlice> = (set, get) => ({
  items: [],
  addItem: (id) => {
    const { user } = get()
    if (!user) return
    set((state) => ({ items: [...state.items, { id, qty: 1 }] }))
  },
})
```

### 2.3 Middleware: persist

```typescript
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface ThemeStore {
  theme: 'light' | 'dark'
  setTheme: (theme: 'light' | 'dark') => void
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      theme: 'light',
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: 'theme-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ theme: state.theme }),
      version: 1,
      migrate: (persisted: unknown, version: number) => {
        if (version === 0) {
          return { ...persisted as ThemeStore, theme: 'light' }
        }
        return persisted as ThemeStore
      },
    }
  )
)
```

Custom storage (AsyncStorage for React Native):

```typescript
import { createJSONStorage } from 'zustand/middleware'
import AsyncStorage from '@react-native-async-storage/async-storage'

const storage = createJSONStorage(() => ({
  getItem: async (name: string) => AsyncStorage.getItem(name),
  setItem: async (name: string, value: string) => AsyncStorage.setItem(name, value),
  removeItem: async (name: string) => AsyncStorage.removeItem(name),
}))

export const useStore = create(persist(store, { name: 'app', storage }))
```

### 2.4 Middleware: devtools

```typescript
import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

export const useStore = create<AppStore>()(
  devtools(
    (set) => ({
      count: 0,
      increment: () => set((state) => ({ count: state.count + 1 }), false, 'count/increment'),
    }),
    {
      name: 'AppStore',
      enabled: process.env.NODE_ENV === 'development',
      anonymousActionType: 'unknown',
    }
  )
)
```

### 2.5 Middleware: immer

```typescript
import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'

interface Todo {
  id: string
  text: string
  done: boolean
}

interface TodoStore {
  todos: Todo[]
  toggleTodo: (id: string) => void
  addTodo: (text: string) => void
}

export const useTodoStore = create<TodoStore>()(
  immer((set) => ({
    todos: [],
    toggleTodo: (id) =>
      set((state) => {
        const todo = state.todos.find((t) => t.id === id)
        if (todo) todo.done = !todo.done
      }),
    addTodo: (text) =>
      set((state) => {
        state.todos.push({ id: crypto.randomUUID(), text, done: false })
      }),
  }))
)
```

### 2.6 Middleware: subscribeWithSelector

```typescript
import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'

export const useStore = create<Store>()(
  subscribeWithSelector((set) => ({
    count: 0,
    step: 1,
    inc: () => set((s) => ({ count: s.count + s.step })),
  }))
)

// Subscribe hanya saat count berubah
useStore.subscribe(
  (state) => state.count,
  (count, prevCount) => {
    console.log(`count changed: ${prevCount} → ${count}`)
  },
  { equalityFn: Object.is, fireImmediately: false }
)

// Subscribe dengan selector dan equality
useStore.subscribe(
  (state) => ({ count: state.count, step: state.step }),
  (snap) => {
    console.log('count or step changed', snap)
  },
  { equalityFn: shallow }
)
```

### 2.7 Computed Values

```typescript
import { create } from 'zustand'

interface CartStore {
  items: Array<{ price: number; qty: number }>
  addItem: (price: number) => void
}

// Computed via selector — rekomputasi hanya saat dependency berubah
export const useCartStore = create<CartStore>()((set) => ({
  items: [],
  addItem: (price) =>
    set((state) => ({ items: [...state.items, { price, qty: 1 }] })),
}))

// Selector computed
export const useTotalPrice = () =>
  useCartStore((state) => state.items.reduce((sum, i) => sum + i.price * i.qty, 0))

// Selector dengan shallow comparison untuk multi-value
export const useCartSummary = () =>
  useCartStore(
    (state) => ({
      count: state.items.length,
      total: state.items.reduce((sum, i) => sum + i.price * i.qty, 0),
    }),
    shallow
  )
```

### 2.8 Store Composition

```typescript
import { createStore, useStore } from 'zustand'

// Store tanpa React hook — pure store
const counterStore = createStore<{ count: number }>()(() => ({ count: 0 }))

// Hook wrapper
export const useCounterStore = <T>(selector: (state: { count: number }) => T) =>
  useStore(counterStore, selector)

// Multiple store composition
const authStore = createStore<AuthState>()((set) => ({...}))
const cartStore = createStore<CartState>()((set) => ({...}))

// Composed hook
function useCombined() {
  const user = useAuthStore((s) => s.user)
  const items = useCartStore((s) => s.items)
  return { user, items }
}
```

### 2.9 Selector Optimization (Re-render Prevention)

```typescript
import { shallow } from 'zustand/shallow'

// ❌ BAD — new object setiap render → selalu re-render
function B() {
  const { count, step } = useBearStore()
  return <div>{count}</div>
}

// ✅ GOOD — selector with shallow
function G() {
  const { count, step } = useBearStore(
    (state) => ({ count: state.count, step: state.step }),
    shallow
  )
  return <div>{count}</div>
}

// ✅ BETTER — atom selector per value
function GB() {
  const count = useBearStore((state) => state.count)
  const step = useBearStore((state) => state.step)
  return <div>{count}</div>
}

// ✅ BEST — selector returns primitive
function GB() {
  const count = useBearStore((state) => state.bears)
  return <div>{count}</div>
}
```

### 2.10 Store Outside React

```typescript
import { createStore } from 'zustand'

export const authStore = createStore<AuthState>()((set) => ({
  token: null,
  setToken: (token: string | null) => set({ token }),
}))

// Gunakan di axios interceptor
api.interceptors.request.use((config) => {
  const token = authStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      authStore.getState().setToken(null)
    }
    return Promise.reject(err)
  }
)
```

---

## 3. Jotai

### 3.1 Basic Atoms

```typescript
import { atom, useAtom } from 'jotai'

const countAtom = atom(0)
const textAtom = atom('hello')
const todoListAtom = atom<Array<{ id: string; text: string }>>([])

function Counter() {
  const [count, setCount] = useAtom(countAtom)
  return <button onClick={() => setCount((c) => c + 1)}>{count}</button>
}
```

### 3.2 Derived Atoms (Computed)

```typescript
import { atom, useAtom } from 'jotai'

const countAtom = atom(0)

// Read-only derived
const doubleCountAtom = atom((get) => get(countAtom) * 2)

// Read-write derived
const incrementByAtom = atom(
  (get) => get(countAtom),
  (_get, set, by: number) => set(countAtom, (c) => c + by)
)

// Write-only derived (action atom)
const resetAtom = atom(null, (_get, set) => set(countAtom, 0))

function DoubleCounter() {
  const [count] = useAtom(countAtom)
  const [double] = useAtom(doubleCountAtom)
  return <div>{count} × 2 = {double}</div>
}
```

### 3.3 Async Atoms

```typescript
import { atom, useAtom } from 'jotai'

const userIdAtom = atom(1)

const userAtom = atom(async (get) => {
  const id = get(userIdAtom)
  const res = await fetch(`/api/users/${id}`)
  if (!res.ok) throw new Error('Failed to fetch')
  return res.json() as Promise<{ id: number; name: string }>
})

function UserProfile() {
  const [user] = useAtom(userAtom)
  // user otomatis Suspense-friendly
  return <div>{user.name}</div>
}

// Async atom dengan Suspense boundary
function UserLoader() {
  return (
    <Suspense fallback={<Spinner />}>
      <UserProfile />
    </Suspense>
  )
}

// Loadable pattern (tanpa Suspense)
import { loadable } from 'jotai/utils'

const userLoadable = loadable(userAtom)

function UserSafe() {
  const [state] = useAtom(userLoadable)
  switch (state.state) {
    case 'loading': return <Spinner />
    case 'hasError': return <Error error={state.error} />
    case 'hasData': return <div>{state.data.name}</div>
  }
}
```

### 3.4 atomWithQuery (TanStack Query Integration)

```typescript
import { atomWithQuery } from 'jotai-tanstack-query'

const todosAtom = atomWithQuery(() => ({
  queryKey: ['todos'],
  queryFn: async () => {
    const res = await fetch('/api/todos')
    return res.json() as Promise<Todo[]>
  },
}))

function TodoList() {
  const [{ data, isLoading, error }] = useAtom(todosAtom)
  if (isLoading) return <Spinner />
  if (error) return <Error error={error} />
  return data.map((todo) => <TodoItem key={todo.id} todo={todo} />)
}
```

### 3.5 atomFamily

```typescript
import { atomFamily } from 'jotai/utils'

const todoAtomFamily = atomFamily((id: string) =>
  atom(async (get) => {
    const res = await fetch(`/api/todos/${id}`)
    return res.json() as Promise<Todo>
  })
)

function TodoDetail({ id }: { id: string }) {
  const [todo] = useAtom(todoAtomFamily(id))
  return <div>{todo.title}</div>
}

// Cleanup — hapus dari cache
todoAtomFamily.remove('todo-123')

// Delete all
todoAtomFamily.setShouldRemove((createdAt) => Date.now() - createdAt > 300_000)
```

### 3.6 splitAtom

```typescript
import { atom, useAtom } from 'jotai'
import { splitAtom } from 'jotai/utils'

const todosAtom = atom<Todo[]>([])
const todoAtomsAtom = splitAtom(todosAtom)

function TodoList() {
  const [todoAtoms] = useAtom(todoAtomsAtom)
  return todoAtoms.map((todoAtom) => (
    <TodoItem key={`${todoAtom}`} todoAtom={todoAtom} />
  ))
}

function TodoItem({ todoAtom }: { todoAtom: Atom<Todo> }) {
  const [todo, setTodo] = useAtom(todoAtom)
  return (
    <div>
      <input
        value={todo.text}
        onChange={(e) => setTodo({ ...todo, text: e.target.value })}
      />
    </div>
  )
}
```

### 3.7 Immutable Atoms

```typescript
import { atom } from 'jotai'
import { freezeAtom } from 'jotai/utils'

const mutableTodoAtom = atom({ text: 'hello', done: false })

// Immutable version — Object.freeze output
const todoAtom = freezeAtom(mutableTodoAtom)

// Error saat mutasi langsung
function Bad() {
  const [todo, setTodo] = useAtom(todoAtom)
  todo.text = 'new' // ❌ TypeError in strict mode
}

function Good() {
  const [todo, setTodo] = useAtom(todoAtom)
  setTodo({ ...todo, text: 'new' }) // ✅
}
```

### 3.8 atomWithStorage

```typescript
import { atomWithStorage } from 'jotai/utils'
import AsyncStorage from '@react-native-async-storage/async-storage'

// localStorage by default
const themeAtom = atomWithStorage('theme', 'light')

// Custom storage (React Native)
const rnThemeAtom = atomWithStorage('theme', 'light', {
  getItem: async (key) => AsyncStorage.getItem(key),
  setItem: async (key, value) => AsyncStorage.setItem(key, value),
  removeItem: async (key) => AsyncStorage.removeItem(key),
})

function ThemeToggle() {
  const [theme, setTheme] = useAtom(themeAtom)
  return (
    <button onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>
      {theme}
    </button>
  )
}
```

---

## 4. Context + useReducer

### 4.1 When Context is Appropriate

Context cocok untuk **low-frequency state** (jarang berubah):

| Cocok | Tidak Cocok |
|---|---|
| Theme (light/dark) | Form input setiap keystroke |
| Locale / language | Real-time cursor position |
| Auth user (set on login/logout) | Animation frame data |
| Layout breakpoints | Websocket messages (high freq) |

### 4.2 Context Splitting Pattern

```typescript
import { createContext, useContext, useMemo } from 'react'

// State context — nilai yang berubah
interface ThemeState {
  theme: 'light' | 'dark'
}
const ThemeStateContext = createContext<ThemeState | null>(null)

// Dispatch context — fungsi (tidak berubah)
interface ThemeDispatch {
  setTheme: (t: 'light' | 'dark') => void
}
const ThemeDispatchContext = createContext<ThemeDispatch | null>(null)

function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  // State context — re-render hanya consumer state
  const stateValue = useMemo(() => ({ theme }), [theme])

  // Dispatch context — stabil, tidak pernah re-render
  const dispatchValue = useMemo(() => ({ setTheme }), [])

  return (
    <ThemeStateContext.Provider value={stateValue}>
      <ThemeDispatchContext.Provider value={dispatchValue}>
        {children}
      </ThemeDispatchContext.Provider>
    </ThemeStateContext.Provider>
  )
}

function useThemeState() {
  const ctx = useContext(ThemeStateContext)
  if (!ctx) throw new Error('useThemeState must be used within ThemeProvider')
  return ctx
}

function useThemeDispatch() {
  const ctx = useContext(ThemeDispatchContext)
  if (!ctx) throw new Error('useThemeDispatch must be used within ThemeProvider')
  return ctx
}
```

Consumer yang hanya butuh dispatch **tidak akan re-render** saat theme berubah:

```typescript
function ThemeButton() {
  const { setTheme } = useThemeDispatch() // ✅ never re-renders
  return <button onClick={() => setTheme('dark')}>Dark</button>
}

function ThemeDisplay() {
  const { theme } = useThemeState() // ✅ re-render only when theme changes
  return <div>{theme}</div>
}
```

### 4.3 useReducer untuk Complex State Transitions

```typescript
import { createContext, useContext, useReducer, useMemo } from 'react'

type Step = 'info' | 'address' | 'payment' | 'confirm'

interface WizardState {
  step: Step
  data: {
    name: string
    email: string
    address: string
    paymentMethod: string
  }
  errors: Partial<Record<keyof WizardState['data'], string>>
  isSubmitting: boolean
}

type WizardAction =
  | { type: 'GO_TO'; step: Step }
  | { type: 'UPDATE'; field: keyof WizardState['data']; value: string }
  | { type: 'SET_ERRORS'; errors: Partial<Record<keyof WizardState['data'], string>> }
  | { type: 'SUBMIT_START' }
  | { type: 'SUBMIT_SUCCESS' }
  | { type: 'SUBMIT_ERROR'; error: string }
  | { type: 'RESET' }

const initialState: WizardState = {
  step: 'info',
  data: { name: '', email: '', address: '', paymentMethod: '' },
  errors: {},
  isSubmitting: false,
}

function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case 'GO_TO':
      return { ...state, step: action.step, errors: {} }
    case 'UPDATE':
      return {
        ...state,
        data: { ...state.data, [action.field]: action.value },
        errors: { ...state.errors, [action.field]: undefined },
      }
    case 'SET_ERRORS':
      return { ...state, errors: action.errors }
    case 'SUBMIT_START':
      return { ...state, isSubmitting: true }
    case 'SUBMIT_SUCCESS':
      return { ...initialState }
    case 'SUBMIT_ERROR':
      return { ...state, isSubmitting: false, errors: { email: action.error } }
    case 'RESET':
      return { ...initialState }
    default:
      return state
  }
}

// Context setup
const WizardContext = createContext<WizardState | null>(null)
const WizardDispatchContext = createContext<React.Dispatch<WizardAction> | null>(null)

function WizardProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(wizardReducer, initialState)
  const stateValue = useMemo(() => state, [state])

  return (
    <WizardContext.Provider value={stateValue}>
      <WizardDispatchContext.Provider value={dispatch}>
        {children}
      </WizardDispatchContext.Provider>
    </WizardContext.Provider>
  )
}
```

### 4.4 Selective Context Consumer

```typescript
// HOC pattern untuk selective subscription
function withContextSelector<T, R>(
  useContextHook: () => T,
  selector: (state: T) => R,
  Component: React.ComponentType<{ value: R }>
) {
  return function Wrapped() {
    const ctx = useContextHook()
    const value = selector(ctx)
    return <Component value={value} />
  }
}

// Atau custom hook with equality
function useWizardField<K extends keyof WizardState['data']>(field: K) {
  const { data } = useWizardState()
  return data[field]
}

function NameField() {
  const name = useWizardField('name') // ✅ re-render only when name changes
  return <input value={name} readOnly />
}
```

---

## 5. TanStack Query (React Query v5)

### 5.1 Query Keys Structure

```typescript
// Best practice: flat, predictable, consistent
const queryKeys = {
  todos: {
    all: ['todos'] as const,
    detail: (id: string) => ['todos', 'detail', id] as const,
    list: (filters: { status?: string; page?: number }) =>
      ['todos', 'list', filters] as const,
    search: (query: string) => ['todos', 'search', query] as const,
  },
  users: {
    all: ['users'] as const,
    profile: (id: string) => ['users', 'profile', id] as const,
    me: ['users', 'me'] as const,
  },
  projects: {
    all: ['projects'] as const,
    detail: (slug: string) => ['projects', 'detail', slug] as const,
  },
}

// Penggunaan
const { data } = useQuery({
  queryKey: queryKeys.todos.list({ status: 'active', page: 1 }),
  queryFn: () => fetchTodos({ status: 'active', page: 1 }),
})
```

### 5.2 staleTime vs gcTime

```typescript
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,   // 5 menit — data dianggap fresh
      gcTime: 1000 * 60 * 30,      // 30 menit — data cache bertahan
      retry: 2,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
    },
  },
})

// Per query override
const { data: criticalData } = useQuery({
  queryKey: ['critical'],
  queryFn: fetchCritical,
  staleTime: 0,            // selalu refetch saat mount
  gcTime: 1000 * 60,       // garbage collect setelah 1 menit idle
})

const { data: staticData } = useQuery({
  queryKey: ['static-config'],
  queryFn: fetchConfig,
  staleTime: Infinity,     // data tidak pernah stale
  gcTime: Infinity,        // tidak pernah di-garbage collect
})
```

### 5.3 Optimistic Updates

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './query-keys'

export function useToggleTodo() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, done }: { id: string; done: boolean }) => {
      const res = await fetch(`/api/todos/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ done }),
      })
      if (!res.ok) throw new Error('Failed to update')
      return res.json()
    },

    // Optimistic update — langsung ubah cache
    onMutate: async ({ id, done }) => {
      // Cancel ongoing refetch
      await queryClient.cancelQueries({ queryKey: queryKeys.todos.all })

      // Snapshot previous
      const previousTodos = queryClient.getQueryData(queryKeys.todos.all)

      // Optimistically update
      queryClient.setQueryData(queryKeys.todos.all, (old: Todo[]) =>
        old?.map((todo) => (todo.id === id ? { ...todo, done } : todo))
      )

      return { previousTodos }
    },

    // Rollback on error
    onError: (_err, _vars, context) => {
      if (context?.previousTodos) {
        queryClient.setQueryData(queryKeys.todos.all, context.previousTodos)
      }
    },

    // Refetch to sync with server
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.todos.all })
    },
  })
}
```

### 5.4 Infinite Queries

```typescript
import { useInfiniteQuery } from '@tanstack/react-query'

interface Page {
  data: Todo[]
  nextCursor: string | null
}

function useTodosInfinite() {
  return useInfiniteQuery<Page>({
    queryKey: queryKeys.todos.all,
    queryFn: async ({ pageParam }) => {
      const res = await fetch(`/api/todos?cursor=${pageParam}&limit=20`)
      return res.json()
    },
    initialPageParam: '',
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    getPreviousPageParam: (firstPage) => firstPage.nextCursor ?? undefined,
  })
}

function TodoList() {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useTodosInfinite()

  const todos = data?.pages.flatMap((page) => page.data) ?? []

  return (
    <div>
      {todos.map((todo) => <div key={todo.id}>{todo.text}</div>)}
      <button
        onClick={() => fetchNextPage()}
        disabled={!hasNextPage || isFetchingNextPage}
      >
        {isFetchingNextPage ? 'Loading...' : hasNextPage ? 'Load More' : 'All Loaded'}
      </button>
    </div>
  )
}
```

### 5.5 Mutations with Rollback

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'

interface DeleteTodoContext {
  previousTodos: Todo[] | undefined
}

export function useDeleteTodo() {
  const queryClient = useQueryClient()

  return useMutation<Todo, Error, string, DeleteTodoContext>({
    mutationFn: async (id) => {
      const res = await fetch(`/api/todos/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Delete failed')
      return res.json()
    },

    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.todos.all })
      const previousTodos = queryClient.getQueryData<Todo[]>(queryKeys.todos.all)

      queryClient.setQueryData<Todo[]>(queryKeys.todos.all, (old) =>
        old?.filter((todo) => todo.id !== id)
      )

      return { previousTodos }
    },

    onError: (_err, _id, context) => {
      if (context?.previousTodos) {
        queryClient.setQueryData(queryKeys.todos.all, context.previousTodos)
      }
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.todos.all })
    },
  })
}
```

### 5.6 Prefetching

```typescript
import { QueryClient, dehydrate, HydrationBoundary } from '@tanstack/react-query'

// RSC / SSR Prefetch
export default async function Page() {
  const queryClient = new QueryClient()

  await queryClient.prefetchQuery({
    queryKey: queryKeys.todos.all,
    queryFn: () => fetch('/api/todos').then((r) => r.json()),
    staleTime: 1000 * 60,
  })

  await queryClient.prefetchQuery({
    queryKey: queryKeys.users.me,
    queryFn: () => fetch('/api/users/me').then((r) => r.json()),
  })

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <TodoPage />
    </HydrationBoundary>
  )
}

// Client-side prefetch (hover-based)
function TodoLink({ id }: { id: string }) {
  const queryClient = useQueryClient()

  return (
    <Link
      to={`/todos/${id}`}
      onMouseEnter={() => {
        queryClient.prefetchQuery({
          queryKey: queryKeys.todos.detail(id),
          queryFn: () => fetch(`/api/todos/${id}`).then((r) => r.json()),
          staleTime: 1000 * 60,
        })
      }}
    >
      View Todo
    </Link>
  )
}

// Prefetch via queryClient.prefetchInfiniteQuery
queryClient.prefetchInfiniteQuery({
  queryKey: queryKeys.todos.all,
  queryFn: ({ pageParam }) => fetch(`/api/todos?cursor=${pageParam}`),
  initialPageParam: '',
})
```

### 5.7 Query Factories (Type-safe)

```typescript
import { createQueryKeyStore } from '@lukemorales/query-key-factory'

// Atau manual dengan type safety
export const todoApi = {
  baseKey: ['todos'] as const,

  list: (filters?: { status?: string }) =>
    ({ queryKey: [...todoApi.baseKey, 'list', filters] } as const),

  detail: (id: string) =>
    ({
      queryKey: [...todoApi.baseKey, 'detail', id],
      queryFn: () => fetch(`/api/todos/${id}`).then((r) => r.json()),
    } as const),
}

// Generic factory pattern
function createQueryFactory<T extends Record<string, unknown>>(config: {
  baseKey: string[]
  queries: {
    [K in keyof T]: (params: T[K]) => {
      queryKey: readonly unknown[]
      queryFn?: () => Promise<unknown>
    }
  }
}) {
  return config
}
```

---

## 6. URL State (nuqs)

### 6.1 useQueryState

```typescript
import { useQueryState } from 'nuqs'

function SearchBar() {
  const [search, setSearch] = useQueryState('q', {
    defaultValue: '',
    history: 'push',    // push to history (default)
    shallow: false,     // trigger server-side (Next.js) or client-only
  })

  return (
    <input
      value={search}
      onChange={(e) => setSearch(e.target.value || null)} // null = remove param
      placeholder="Search..."
    />
  )
}
```

### 6.2 useQueryStates

```typescript
import { useQueryStates, parseAsString, parseAsInteger, parseAsIsoDateTime } from 'nuqs'

const filters = {
  search: parseAsString.withDefault(''),
  page: parseAsInteger.withDefault(1),
  status: parseAsString.withDefault('all'),
  startDate: parseAsIsoDateTime,
}

function FilterPanel() {
  const [params, setParams] = useQueryStates(filters)

  return (
    <div>
      <input
        value={params.search}
        onChange={(e) => setParams({ search: e.target.value, page: 1 })}
      />
      <select
        value={params.status}
        onChange={(e) => setParams({ status: e.target.value, page: 1 })}
      >
        <option value="all">All</option>
        <option value="active">Active</option>
        <option value="done">Done</option>
      </select>
      <div>Page {params.page}</div>
    </div>
  )
}
```

### 6.3 Custom Parser/Serializer

```typescript
import { createParser, useQueryState } from 'nuqs'

// Enum parser
type SortOrder = 'asc' | 'desc'

const sortOrderParser = createParser({
  parse: (value: string) => {
    if (value === 'asc' || value === 'desc') return value as SortOrder
    return null
  },
  serialize: (value: SortOrder) => value,
}).withDefault('asc')

// Array parser
const tagsParser = createParser({
  parse: (value: string) => value.split(',').filter(Boolean),
  serialize: (value: string[]) => value.join(','),
}).withDefault([] as string[])

// Range parser
const rangeParser = createParser({
  parse: (value: string) => {
    const [min, max] = value.split('-').map(Number)
    if (isNaN(min) || isNaN(max)) return null
    return { min, max }
  },
  serialize: (value: { min: number; max: number }) => `${value.min}-${value.max}`,
})

function ProductFilters() {
  const [sort, setSort] = useQueryState('sort', sortOrderParser)
  const [tags, setTags] = useQueryState('tags', tagsParser)
  const [price, setPrice] = useQueryState('price', rangeParser)

  return (
    <div>
      <button onClick={() => setSort('asc')}>Price ↑</button>
      <button onClick={() => setTags([...tags, 'react'])}>Add Tag</button>
    </div>
  )
}
```

### 6.4 Sync with Zustand

```typescript
import { useQueryState, parseAsInteger, parseAsString } from 'nuqs'
import { useCallback } from 'react'
import { useBearStore } from './store'

function SyncedPage() {
  const bears = useBearStore((s) => s.bears)
  const increase = useBearStore((s) => s.increase)

  const [pageState, setPageState] = useQueryState('page', parseAsInteger.withDefault(1))
  const [searchState, setSearchState] = useQueryState('q', parseAsString)

  // Sync URL → Store (on mount)
  useEffect(() => {
    if (pageState > 0) {
      useBearStore.setState({ page: pageState })
    }
  }, [])

  // Sync Store → URL (on change)
  const handlePageChange = useCallback((newPage: number) => {
    useBearStore.setState({ page: newPage })
    setPageState(newPage)
  }, [setPageState])

  return <PageComponent onPageChange={handlePageChange} />
}
```

### 6.5 Shallow Routing

```typescript
import { useQueryStates, parseAsString } from 'nuqs'

const searchParams = {
  q: parseAsString,
  sort: parseAsString.withDefault('relevance'),
}

function ProductGrid() {
  const [params, setParams] = useQueryStates(searchParams, {
    history: 'replace',        // replace instead of push
    shallow: true,              // client-side only, no server roundtrip
    clearOnDefault: true,       // remove param if equals default
  })

  // URL berubah tapi tidak ada server request
  // Cocok untuk search-as-you-type
  return (
    <input
      defaultValue={params.q}
      onChange={(e) => {
        setParams({ q: e.target.value || null }, { shallow: true, history: 'replace' })
      }}
    />
  )
}
```

---

## 7. State Colocation

### 7.1 Decision Tree: Lift Up vs Push Down

```
                    ┌───────────────────┐
                    │  State baru       │
                    │  diperlukan       │
                    └────────┬──────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
          ┌─────────────────┐  ┌─────────────────┐
          │ Dipakai >1      │  │ Dipakai hanya   │
          │ komponen?       │  │ 1 komponen?     │
          └────────┬────────┘  └────────┬────────┘
                   │                    │
                   ▼                    ▼
          ┌─────────────────┐  ┌─────────────────┐
          │  Naik ke parent │  │  Tetap di lokal │
          │  bersama atau   │  │  useState       │
          │  ke Context     │  └─────────────────┘
          └────────┬────────┘
                   │
          ┌────────┴────────┐
          ▼                 ▼
    ┌────────────┐   ┌────────────┐
    │ Kedalaman  │   │ Kedalaman  │
    │ >2 level?  │   │ ≤2 level?  │
    └───────┬────┘   └───────┬────┘
            │                │
            ▼                ▼
    ┌────────────┐   ┌────────────┐
    │  Context   │   │  Prop      │
    │  atau      │   │  drilling │
    │  Zustand   │   │  sederhana│
    └────────────┘   └────────────┘
```

### 7.2 Contoh Prop Drilling → Context

```typescript
// ❌ Prop drilling yang tidak perlu
function App() {
  const [user, setUser] = useState(null)
  return (
    <Dashboard user={user} setUser={setUser}>
      <Sidebar user={user}>
        <Avatar user={user} />
        <Nav user={user} />
      </Sidebar>
      <Main user={user} setUser={setUser}>
        <ProfileForm user={user} setUser={setUser} />
      </Main>
    </Dashboard>
  )
}

// ✅ Colocation — state di tempat yang tepat
function App() {
  return (
    <AuthProvider>
      <Dashboard>
        <Sidebar>
          <Avatar />
          <Nav />
        </Sidebar>
        <Main>
          <ProfileForm />
        </Main>
      </Dashboard>
    </AuthProvider>
  )
}

// Avatar hanya butuh user — ambil dari Context terdekat
function Avatar() {
  const user = useAuth()
  return <img src={user?.avatar} />
}
```

### 7.3 Pushing State Down

```typescript
// ❌ State terlalu tinggi
function Page() {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [tooltipId, setTooltipId] = useState<string | null>(null)
  const [accordionOpen, setAccordionOpen] = useState<string | null>(null)

  return (
    <div>
      <Header />
      <Sidebar>
        <Accordion open={accordionOpen} onToggle={setAccordionOpen} />
      </Sidebar>
      <Main>
        <TooltipContent id={tooltipId} />
        <DataTable onTooltip={setTooltipId} />
      </Main>
      <Footer />
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </div>
  )
}

// ✅ State didorong ke komponen yang membutuhkan
function Page() {
  return (
    <div>
      <Header />
      <Sidebar>
        <Accordion />       {/* Accordion punya state sendiri */}
      </Sidebar>
      <Main>
        <DataTable />       {/* Tooltip state local di DataTable */}
      </Main>
      <Footer />
      <ModalWrapper />      {/* Modal state local */}
    </div>
  )
}
```

---

## 8. Performance

### 8.1 Selector Optimization

```typescript
// ❌ Selector membuat object baru setiap render
const { count, text } = useStore((s) => ({ count: s.count, text: s.text }))

// ✅ Selector dengan shallow equality
import { shallow } from 'zustand/shallow'
const { count, text } = useStore(
  (s) => ({ count: s.count, text: s.text }),
  shallow
)

// ✅ Selector dengan equality function custom
const { items } = useStore(
  (s) => ({ items: s.items, total: s.total }),
  (a, b) => a.total === b.total && a.items.length === b.items.length
)

// ✅ Multiple hooks (best untuk primitives)
const count = useStore((s) => s.count)
const text = useStore((s) => s.text)
```

### 8.2 Atom Splitting (Jotai)

```typescript
// ❌ Satu atom besar — re-render komponen yang tidak perlu
const bigAtom = atom({
  user: { name: '', email: '' },
  theme: 'light',
  filters: { search: '', page: 1 },
})

// ✅ Split ke atom-atom kecil — granular re-render
const userAtom = atom({ name: '', email: '' })
const themeAtom = atom('light')
const searchAtom = atom('')
const pageAtom = atom(1)

// Composed atom untuk yang perlu data dari multiple atoms
const displayAtom = atom((get) => ({
  user: get(userAtom),
  search: get(searchAtom),
}))

// Komponen hanya re-render saat atom yang dipakai berubah
function UserName() {
  const [user] = useAtom(userAtom)   // ✅ hanya re-render saat user berubah
  return <div>{user.name}</div>
}

function ThemeToggle() {
  const [theme] = useAtom(themeAtom) // ✅ tidak re-render saat user berubah
  return <div>{theme}</div>
}
```

### 8.3 Preventing Cascading Re-renders

```typescript
// ❌ Cascade — parent re-render → semua children re-render
function Parent() {
  const count = useStore((s) => s.count)
  return (
    <div>
      <ExpensiveChild />
      <AnotherChild />
    </div>
  )
}

// ✅ Memoize children yang tidak perlu parent's state
function Parent() {
  const count = useStore((s) => s.count)
  return (
    <div>
      <ExpensiveChild />           {/* ❌ tetap re-render karena Parent re-render */}
    </div>
  )
}

// ✅ Lebih baik — bungkus dengan React.memo
const ExpensiveChild = React.memo(function ExpensiveChild() {
  return <div>...</div>
})

// ✅ Atau — select state di child
function Parent() {
  return (
    <div>
      <CountDisplay />
      <ExpensiveChild />
    </div>
  )
}

function CountDisplay() {
  const count = useStore((s) => s.count) // ✅ hanya CountDisplay yang re-render
  return <div>{count}</div>
}

// ✅ Zustand dengan selector di komponen dalam
function GrandChild() {
  const deepValue = useDeepStore((s) => s.a.b.c.d)
  return <div>{deepValue}</div>
}
```

### 8.4 TanStack Query: Selector Performance

```typescript
// ❌ Selector creates new reference setiap render
const { data: names } = useQuery({
  queryKey: ['todos'],
  queryFn: fetchTodos,
  select: (data) => data.map((t) => t.name), // new array setiap render
})

// ✅ Structured selector dengan stable reference
const namesSelector = (data: Todo[]) => data.map((t) => t.name)

function useTodoNames() {
  return useQuery({
    queryKey: ['todos'],
    queryFn: fetchTodos,
    select: namesSelector,
    structuralSharing: true, // default — deep comparison
  })
}

// Selector untuk data terbatas
function useTodoCount() {
  return useQuery({
    queryKey: ['todos'],
    queryFn: fetchTodos,
    select: (data) => data.length, // primitive — aman
  })
}
```

---

## 9. Testing Stores

### 9.1 Testing Zustand Stores

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { useBearStore } from './bear-store'

// Reset store sebelum setiap test
beforeEach(() => {
  useBearStore.setState({ bears: 0 })
})

describe('BearStore', () => {
  it('should start with 0 bears', () => {
    const { bears } = useBearStore.getState()
    expect(bears).toBe(0)
  })

  it('should increase bears', () => {
    const { increase } = useBearStore.getState()
    increase()
    expect(useBearStore.getState().bears).toBe(1)
  })

  it('should reset bears', () => {
    useBearStore.setState({ bears: 10 })
    const { reset } = useBearStore.getState()
    reset()
    expect(useBearStore.getState().bears).toBe(0)
  })

  it('should handle multiple increases', () => {
    const { increase } = useBearStore.getState()
    increase()
    increase()
    increase()
    expect(useBearStore.getState().bears).toBe(3)
  })
})

// Test dengan custom selector
describe('BearStore selectors', () => {
  it('should compute double count correctly', () => {
    useBearStore.setState({ bears: 5 })
    const doubleCount = useBearStore.getState().bears * 2
    expect(doubleCount).toBe(10)
  })
})
```

### 9.2 Testing Zustand with React Components

```typescript
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, beforeEach } from 'vitest'

function TestComponent() {
  const bears = useBearStore((s) => s.bears)
  const increase = useBearStore((s) => s.increase)
  return (
    <div>
      <span>{bears}</span>
      <button onClick={increase}>Add</button>
    </div>
  )
}

describe('BearCounter Component', () => {
  beforeEach(() => {
    useBearStore.setState({ bears: 0 })
  })

  it('renders initial count', () => {
    render(<TestComponent />)
    expect(screen.getByText('0')).toBeDefined()
  })

  it('increments on button click', () => {
    render(<TestComponent />)
    fireEvent.click(screen.getByText('Add'))
    expect(screen.getByText('1')).toBeDefined()
  })
})
```

### 9.3 Mocking TanStack Query

```typescript
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi } from 'vitest'

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,        // disable retry untuk test
        gcTime: 0,           // no garbage collection delay
      },
      mutations: {
        retry: false,
      },
    },
  })
}

function createWrapper() {
  const queryClient = createTestQueryClient()
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )
  }
}

describe('useTodos', () => {
  it('should fetch todos successfully', async () => {
    const mockTodos = [{ id: '1', text: 'Learn testing' }]
    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockTodos),
    } as Response)

    const { result } = renderHook(() => useTodos(), {
      wrapper: createWrapper(),
    })

    expect(result.current.isLoading).toBe(true)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockTodos)
  })

  it('should handle error', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useTodos(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
```

### 9.4 Testing Context Consumers

```typescript
import { renderHook, act } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

function renderWithProviders(ui: React.ReactElement) {
  return render(ui, {
    wrapper: ({ children }) => (
      <ThemeProvider>
        <WizardProvider>
          {children}
        </WizardProvider>
      </ThemeProvider>
    ),
  })
}

describe('useWizardState', () => {
  it('should provide initial state', () => {
    const { result } = renderHook(() => useWizardState(), {
      wrapper: ({ children }) => (
        <WizardProvider>{children}</WizardProvider>
      ),
    })

    expect(result.current.step).toBe('info')
  })

  it('should navigate between steps', () => {
    const { result } = renderHook(
      () => ({ state: useWizardState(), dispatch: useWizardDispatch() }),
      {
        wrapper: ({ children }) => (
          <WizardProvider>{children}</WizardProvider>
        ),
      }
    )

    act(() => {
      result.current.dispatch({ type: 'GO_TO', step: 'payment' })
    })

    expect(result.current.state.step).toBe('payment')
  })
})
```

---

## 10. File Convention

### 10.1 Struktur Store Files

```
src/
├── stores/
│   ├── index.ts                    # barrel export
│   ├── auth-store.ts               # Zustand store tunggal
│   ├── use-auth.ts                 # Custom hooks untuk auth
│   ├── cart/
│   │   ├── index.ts                # barrel
│   │   ├── cart-store.ts           # Zustand store
│   │   ├── cart-selectors.ts       # Selector functions
│   │   ├── cart-computed.ts        # Computed values
│   │   └── cart-types.ts           # Types saja
│   └── ui/
│       ├── ui-store.ts             # UI state (sidebar, modal)
│       ├── ui-selectors.ts
│       └── ui-types.ts
│
├── queries/
│   ├── index.ts                    # barrel
│   ├── query-keys.ts               # Query key factory
│   ├── query-client.ts             # QueryClient config
│   ├── todos/
│   │   ├── index.ts                # useTodos, useTodo, useCreateTodo, etc.
│   │   ├── todos-key.ts
│   │   └── todos-types.ts
│   └── users/
│       ├── index.ts
│       ├── users-key.ts
│       └── users-types.ts
│
├── atoms/
│   ├── index.ts                    # barrel
│   ├── filter-atoms.ts             # Jotai atoms
│   ├── user-atoms.ts
│   └── ui-atoms.ts
│
├── url-state/
│   ├── parsers.ts                  # Custom nuqs parsers
│   └── hooks.ts                    # useSearchParams hooks
│
└── context/
    ├── ThemeContext.tsx             # Theme provider + hooks
    ├── AuthContext.tsx
    └── WizardContext.tsx
```

### 10.2 Zustand Store Template

```typescript
// stores/ui/ui-store.ts
import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import type { UIState, UIActions } from './ui-types'

type UIStore = UIState & UIActions

const initialState: UIState = {
  sidebarOpen: true,
  theme: 'light',
  activeModal: null,
}

export const useUIStore = create<UIStore>()(
  devtools(
    persist(
      (set) => ({
        ...initialState,
        toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
        setTheme: (theme) => set({ theme }),
        openModal: (modal) => set({ activeModal: modal }),
        closeModal: () => set({ activeModal: null }),
        reset: () => set(initialState),
      }),
      { name: 'ui-store', partialize: (s) => ({ theme: s.theme }) }
    ),
    { name: 'UIStore' }
  )
)
```

### 10.3 Query Keys Factory File

```typescript
// queries/query-keys.ts
export const queryKeys = {
  todos: {
    all: ['todos'] as const,
    lists: () => [...queryKeys.todos.all, 'list'] as const,
    list: (filters: Record<string, unknown>) =>
      [...queryKeys.todos.lists(), filters] as const,
    details: () => [...queryKeys.todos.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.todos.details(), id] as const,
  },
  users: {
    all: ['users'] as const,
    me: ['users', 'me'] as const,
    profile: (id: string) => ['users', 'profile', id] as const,
  },
  projects: {
    all: ['projects'] as const,
    detail: (id: string) => ['projects', 'detail', id] as const,
    milestones: (projectId: string) =>
      ['projects', 'milestones', projectId] as const,
  },
}
```

---

## 11. Anti-Patterns

### 11.1 Everything in One Store

```typescript
// ❌ BAD — satu store untuk semua
const monstroStore = create<{
  user: User
  theme: string
  todos: Todo[]
  filters: Filters
  notifications: Notification[]
  modal: string | null
  // ... 50+ properties
}>()

// ✅ GOOD — split by domain
const useAuthStore = create<AuthState>()
const useThemeStore = create<ThemeState>()
const useTodoStore = create<TodoState>()
const useUIStore = create<UIState>()
```

### 11.2 Over-using Context

```typescript
// ❌ BAD — Context untuk high-frequency updates
function MouseTrackerProvider({ children }: { children: React.ReactNode }) {
  const [pos, setPos] = useState({ x: 0, y: 0 })

  useEffect(() => {
    const handler = (e: MouseEvent) => setPos({ x: e.clientX, y: e.clientY })
    window.addEventListener('mousemove', handler)
    return () => window.removeEventListener('mousemove', handler)
  }, [])

  return <MouseContext.Provider value={pos}>{children}</MouseContext.Provider>
}
// Setiap mousemove → semua consumer re-render!

// ✅ GOOD — gunakan Jotai atau ref-based
const mouseAtom = atom({ x: 0, y: 0 })

// Atau Zustand dengan selector
const useMouseStore = create(() => ({ x: 0, y: 0 }))
// Consumer: useMouseStore((s) => s.x) — hanya re-render saat x berubah
```

### 11.3 Not Separating Server vs Client State

```typescript
// ❌ BAD — server state di Zustand
const useTodoStore = create<{
  todos: Todo[]
  isLoading: boolean
  fetchTodos: () => Promise<void>
}>()

// ✅ GOOD — TanStack Query untuk server state
function useTodos() {
  return useQuery({
    queryKey: ['todos'],
    queryFn: () => fetch('/api/todos').then((r) => r.json()),
  })
}

// Zustand hanya untuk client state
const useFilterStore = create(() => ({
  search: '',
  status: 'all' as string,
}))
```

### 11.4 Mutating Store Outside React Without Subscribe

```typescript
// ❌ BAD — mutasi tanpa subscribe → komponen tidak update
useBearStore.setState({ bears: 5 })

// ✅ GOOD — tetap melalui setState
useBearStore.setState({ bears: 5 })

// Atau subscribe untuk side effect
const unsub = useBearStore.subscribe(
  (state) => state.bears,
  (bears) => {
    console.log('bears changed:', bears)
  }
)
```

### 11.5 Over-using useAtomValue for Frequent Writes

```typescript
// ❌ BAD — useAtomValue + useSetAtom terpisah
const count = useAtomValue(countAtom)
const setCount = useSetAtom(countAtom)

// ✅ GOOD — useAtom untuk read+write
const [count, setCount] = useAtom(countAtom)
```

### 11.6 Infinite Query Keys Without Unique Identifier

```typescript
// ❌ BAD — infinite query dengan key sama dengan regular query
useInfiniteQuery({
  queryKey: ['todos'], // konflik dengan useQuery(['todos'])
})

// ✅ GOOD — prefix infinite query
useInfiniteQuery({
  queryKey: ['todos', 'infinite'],
})
```

---

## 12. Implementation Checklist

### Zustand
- [ ] Apakah state ini benar-benar global? (dipakai >2 komponen di level berbeda)
- [ ] Apakah slices pattern digunakan untuk store >5 properties?
- [ ] Apakah selector sudah optimal? (primitives > objects, shallow jika perlu multi-value)
- [ ] Apakah persist middleware digunakan untuk persistent state?
- [ ] Apakah devtools middleware aktif di development?
- [ ] Apakah immer digunakan untuk nested state mutation?
- [ ] Apakah store diakses dari luar React? (interceptor, utility)

### Jotai
- [ ] Apakah atom di-split per domain? (1 atom besar → multiple small atoms)
- [ ] Apakah derived atom dipakai untuk computed values?
- [ ] Apakah async atom punya Suspense boundary atau loadable wrapper?
- [ ] Apakah atomFamily punya cleanup strategy?
- [ ] Apakah splitAtom dipakai untuk array manipulation?

### TanStack Query
- [ ] Apakah query keys terstruktur dan type-safe?
- [ ] Apakah staleTime sesuai karakteristik data? (jarang berubah → staleTime besar)
- [ ] Apakah gcTime > staleTime? (cache bertahan lebih lama dari freshness)
- [ ] Apakah optimistic update punya rollback?
- [ ] Apakah infinite query pakai getNextPageParam yang benar?
- [ ] Apakah prefetching dipakai untuk navigasi yang diprediksi?
- [ ] Apakah query factory / structured query keys dipakai?

### Context
- [ ] Apakah low-frequency state only? (bukan untuk real-time/high-freq)
- [ ] Apakah state & dispatch di-split ke provider terpisah?
- [ ] Apakah memo/value stabilization diterapkan?
- [ ] Apakah ada guard untuk missing provider?

### URL State (nuqs)
- [ ] Apakah filter, page, search di URL state?
- [ ] Apakah parser custom untuk complex types?
- [ ] Apakah shallow routing untuk search-as-you-type?
- [ ] Apakah URL state disinkronisasi dengan store?

### Performance
- [ ] Apakah selector menggunakan equality function yang tepat?
- [ ] Apakah atom splitting sudah diterapkan?
- [ ] Apakah React.memo dipakai di komponen mahal?
- [ ] Apakah komponen yang select state ditempatkan serendah mungkin?
- [ ] Apakah TanStack Query selectors menggunakan stable references?

### Testing
- [ ] Apakah Zustand store di-test langsung (getState/setState)?
- [ ] Apakah TanStack Query hooks di-test dengan wrapper + mock fetch?
- [ ] Apakah Context consumers di-test dengan provider wrapper?
- [ ] Apakah store di-reset antar test?

### File Convention
- [ ] Apakah store files terorganisir per domain?
- [ ] Apakah selector dipisah dari store definition?
- [ ] Apakah query keys factory ada di file terpisah?
- [ ] Apakah type definitions terpisah?

---

> **Golden Rule**: Pilih tool berdasarkan _jenis state_, bukan _berapa banyak komponen_ yang pakai. Server state → TanStack Query. URL state → nuqs. Client global → Zustand. High-frequency atomic → Jotai. Low-frequency global → Context. Local → useState.
