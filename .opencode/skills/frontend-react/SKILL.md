---
name: frontend-react
description: React 18/19 with Server Components, Suspense, Concurrent Mode, hooks mastery, TanStack ecosystem, Next.js App Router, advanced patterns, testing, security, and troubleshooting
license: MIT
compatibility: opencode
metadata:
  audience: frontend-developers
  domain: frontend
  paradigm: declarative
  capabilities:
    - server-components
    - concurrent-rendering
    - hooks-patterns
    - state-management
    - performance-optimization
    - testing-strategy
    - error-boundaries
    - nextjs-app-router
  integrates_with:
    - frontend-animation
    - frontend-svelte
    - mobile-tauri
---

## Frontend React Skill

### Core Patterns

#### Server Components (React 18/19 + Next.js App Router)
Server Components are the **default** rendering strategy. They run on the server, never ship JS to the client, and can directly access backend resources.

```
┌──────────────────────────────────────────────┐
│              COMPONENT DECISION               │
│                                                │
│  Does it need interactivity?                   │
│       │                          │              │
│       NO                         YES            │
│       ▼                          ▼              │
│  Server Component          Does it need         │
│  (async, no hooks,         browser APIs?        │
│   direct DB access)            │                │
│                           ┌────┴────┐           │
│                           NO        YES         │
│                           │         │           │
│                      Add "use    Client         │
│                      client"    Component       │
│                      boundary                   │
└──────────────────────────────────────────────┘
```

```tsx
// Server Component — async, direct data access, zero client JS
// app/users/page.tsx
import { db } from '@/lib/db'

export default async function UsersPage() {
  const users = await db.user.findMany({ take: 20 })
  return (
    <ul>
      {users.map(u => (
        <li key={u.id}>{u.name}</li>
      ))}
    </ul>
  )
}
```

```tsx
// Client Component — "use client" at top, can use hooks/interactivity
// app/users/UserSearch.tsx
'use client'
import { useState } from 'react'

export function UserSearch({ onSearch }: { onSearch: (q: string) => void }) {
  const [query, setQuery] = useState('')
  return <input value={query} onChange={e => setQuery(e.target.value)} />
}
```

**Key rules**:
- Server Components cannot use `useState`, `useEffect`, `useContext`, browser APIs, or event handlers
- Server Components CAN be async/await directly
- Client Components CAN render Server Components passed as `children` (interleaving pattern)
- A `"use client"` file makes ALL its imports become client-side (the boundary cascades)

#### Composition Patterns

**Children Pattern** (preferred over prop drilling):
```tsx
// Instead of passing 8 props, compose:
<Card>
  <Card.Header><h2>{title}</h2></Card.Header>
  <Card.Body>{children}</Card.Body>
  <Card.Footer><Button>Save</Button></Card.Footer>
</Card>
```

**Compound Components** (shared implicit state):
```tsx
// app/ui/Tabs.tsx
'use client'
import { createContext, useContext, useState } from 'react'

interface TabsContextType {
  activeTab: string
  setActiveTab: (tab: string) => void
}
const TabsContext = createContext<TabsContextType | null>(null)

export function Tabs({ children, defaultTab }: {
  children: React.ReactNode; defaultTab: string
}) {
  const [activeTab, setActiveTab] = useState(defaultTab)
  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      <div>{children}</div>
    </TabsContext.Provider>
  )
}

Tabs.List = function TabList({ children }: { children: React.ReactNode }) {
  return <div role="tablist">{children}</div>
}

Tabs.Tab = function Tab({ id, children }: { id: string; children: React.ReactNode }) {
  const ctx = useContext(TabsContext)!
  return (
    <button
      role="tab"
      aria-selected={ctx.activeTab === id}
      onClick={() => ctx.setActiveTab(id)}
    >
      {children}
    </button>
  )
}

Tabs.Panel = function TabPanel({ id, children }: { id: string; children: React.ReactNode }) {
  const ctx = useContext(TabsContext)!
  if (ctx.activeTab !== id) return null
  return <div role="tabpanel">{children}</div>
}
```

**Render Props** (use when children depends on parent state):
```tsx
// Useful for: measuring DOM, toggling UI, data-as-children
function Toggle({ children }: { children: (on: boolean, toggle: () => void) => React.ReactNode }) {
  const [on, setOn] = useState(false)
  const toggle = useCallback(() => setOn(prev => !prev), [])
  return <>{children(on, toggle)}</>
}
// Usage:
<Toggle>{(open, toggle) => <button onClick={toggle}>{open ? 'Close' : 'Open'}</button>}</Toggle>
```

#### Hooks Mastery

**useMemo / useCallback Decision Tree**:
```
Should I memoize this value/function?
        │
        ▼
Is it passed as a prop to a React.memo child?
        │
   ┌────┴────┐
   YES       NO
   │          │
   ▼          ▼
useMemo/   Is it a dependency of useEffect/useMemo?
useCallback     │
            ┌───┴───┐
            YES     NO
            │        │
            ▼        ▼
       useMemo/  DON'T memoize.
       useCallback Just compute inline.
```

**Critical rule**: NEVER memoize unless profiler (React DevTools or `<Profiler>`) shows measurable benefit. Premature memoization adds complexity and can hurt performance.

**useRef vs useState**:
```tsx
// useState: triggers re-render when value changes
const [count, setCount] = useState(0)   // count change → re-render

// useRef: mutable container, does NOT trigger re-render
const countRef = useRef(0)              // countRef.current = 5 → NO re-render
const inputRef = useRef<HTMLInputElement>(null)  // DOM reference

// useRef for previous value (derived state tracking)
function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T>()
  useEffect(() => { ref.current = value })
  return ref.current
}
```

**useId** (accessibility — unique IDs for SSR):
```tsx
function EmailField() {
  const id = useId()  // :r0: (guaranteed unique across server and client)
  return (
    <>
      <label htmlFor={id}>Email</label>
      <input id={id} type="email" />
    </>
  )
}
```

**useDeferredValue** (de-prioritize expensive renders):
```tsx
'use client'
import { useState, useDeferredValue, useMemo } from 'react'

function SearchResults({ query }: { query: string }) {
  // query updates immediately, deferredQuery lags behind during heavy renders
  const deferredQuery = useDeferredValue(query)
  // Expensive computation uses the DEFERRED value
  const results = useMemo(() => {
    return heavySearch(deferredQuery)
  }, [deferredQuery])

  return (
    <div style={{ opacity: query !== deferredQuery ? 0.5 : 1 }}>
      {results.map(r => <ResultItem key={r.id} {...r} />)}
    </div>
  )
}
```

**useTransition** (mark updates as non-urgent, integrate with Suspense):
```tsx
'use client'
import { useState, useTransition, Suspense } from 'react'

export function TabContainer() {
  const [tab, setTab] = useState('home')
  const [isPending, startTransition] = useTransition()

  function switchTab(nextTab: string) {
    startTransition(() => setTab(nextTab))
  }

  return (
    <div>
      <nav>
        {['home', 'settings', 'reports'].map(t => (
          <button key={t} onClick={() => switchTab(t)}>
            {t}
          </button>
        ))}
      </nav>
      {isPending && <Spinner />}
      <Suspense fallback={<Skeleton />}>
        <TabContent tab={tab} />
      </Suspense>
    </div>
  )
}
```
Use `useTransition` when: switching tabs, navigating routes, or any update where keeping the current UI responsive is more important than instant update.

**useSyncExternalStore** (subscribe to external mutable stores):
```tsx
// Connecting to a non-React store (e.g., Redux, browser API, custom store)
function useOnlineStatus(): boolean {
  return useSyncExternalStore(
    (callback) => {
      window.addEventListener('online', callback)
      window.addEventListener('offline', callback)
      return () => {
        window.removeEventListener('online', callback)
        window.removeEventListener('offline', callback)
      }
    },
    () => navigator.onLine,              // snapshot on client
    () => true                             // snapshot on server (SSR fallback)
  )
}
```

#### State Management Strategy

```
       WHERE DOES THIS STATE LIVE?
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
  SERVER        CLIENT          URL
    │              │              │
    ▼              ▼              ▼
TanStack       Zustand         nuqs
Query          (global)        (query params)
  or            Jotai
Server         (atomic)
Actions
```

**TanStack Query** (server state — caching, refetching, mutations):
```tsx
// Query: fetch + cache + background refetch
const { data, isLoading, error } = useQuery({
  queryKey: ['users', userId],
  queryFn: () => fetch(`/api/users/${userId}`).then(r => r.json()),
  staleTime: 30_000,        // 30s before considered stale
  gcTime: 5 * 60_000,       // 5min before garbage collected
})

// Mutation with optimistic update
const mutation = useMutation({
  mutationFn: (newName: string) =>
    fetch(`/api/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name: newName }),
    }),
  onMutate: async (newName) => {
    await queryClient.cancelQueries({ queryKey: ['users', userId] })
    const previous = queryClient.getQueryData(['users', userId])
    queryClient.setQueryData(['users', userId], old => ({ ...old, name: newName }))
    return { previous }  // rollback context
  },
  onError: (_err, _newName, context) => {
    queryClient.setQueryData(['users', userId], context?.previous)
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['users', userId] })
  },
})

// Prefetch on hover for instant navigation
const queryClient = useQueryClient()
function prefetchUser(id: string) {
  queryClient.prefetchQuery({
    queryKey: ['users', id],
    queryFn: () => fetch(`/api/users/${id}`).then(r => r.json()),
  })
}
```

**Zustand** (client state — small, fast, no boilerplate):
```tsx
import { create } from 'zustand'
import { persist, devtools } from 'zustand/middleware'

// Slice pattern for large stores
interface BearSlice { bears: number; addBear: () => void }
interface FishSlice { fish: number; addFish: () => void }

const useStore = create<BearSlice & FishSlice>()(
  devtools(
    persist(
      (...a) => ({
        ...createBearSlice(...a),
        ...createFishSlice(...a),
      }),
      { name: 'app-store' }
    )
  )
)

// Selector: component only re-renders when selected values change
function BearCounter() {
  const bears = useStore(s => s.bears)  // ONLY re-renders when `bears` changes
  return <span>{bears}</span>
}
```

**Jotai** (atomic state — bottom-up, derived, async):
```tsx
import { atom, useAtom, useAtomValue } from 'jotai'
import { atomWithQuery } from 'jotai-tanstack-query'

const countAtom = atom(0)
const doubleAtom = atom(get => get(countAtom) * 2)  // derived atom

// Async atom that suspends
const userAtom = atom(async () => {
  const res = await fetch('/api/me')
  return res.json()
})
// Component: <Suspense fallback={...}><UserProfile /></Suspense>
```

**URL state with nuqs** (shareable, bookmarkable state):
```tsx
'use client'
import { useQueryState } from 'nuqs'

export function ProductFilters() {
  const [category, setCategory] = useQueryState('category')
  const [page, setPage] = useQueryState('page', { defaultValue: '1' })

  return (
    <select value={category ?? ''} onChange={e => setCategory(e.target.value || null)}>
      <option value="">All</option>
      <option value="books">Books</option>
      <option value="electronics">Electronics</option>
    </select>
  )
}
```

**Form state — React Hook Form + Zod**:
```tsx
'use client'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

const schema = z.object({
  email: z.string().email('Invalid email'),
  age: z.number().min(18, 'Must be 18+').max(120),
})

type FormData = z.infer<typeof schema>

export function SignupForm() {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', age: 0 },
  })

  return (
    <form onSubmit={handleSubmit(data => console.log(data))}>
      <input {...register('email')} />
      {errors.email && <span role="alert">{errors.email.message}</span>}
      <input type="number" {...register('age', { valueAsNumber: true })} />
      {errors.age && <span role="alert">{errors.age.message}</span>}
      <button type="submit" disabled={isSubmitting}>Submit</button>
    </form>
  )
}
```

---

### Performance

#### React.memo Deep Dive

```tsx
// React.memo: re-renders ONLY if props changed (shallow compare)
const ExpensiveList = React.memo(function ExpensiveList({ items }: { items: Item[] }) {
  return items.map(item => <ExpensiveItem key={item.id} {...item} />)
})

// Custom comparator (rarely needed — only for deep equality escape hatches)
const MemoComponent = React.memo(Component, (prev, next) => {
  return prev.user.id === next.user.id  // true = skip re-render
})
```

**When NOT to use React.memo**:
- Props are always new (objects created inline, anonymous functions without `useCallback`)
- Component is cheap to render (a few DOM elements)
- Props change on every render anyway

#### Code Splitting Patterns

```tsx
import { lazy, Suspense } from 'react'

// Route-level splitting (most impactful)
const Dashboard = lazy(() => import('./Dashboard'))
const Settings = lazy(() => import('./Settings'))
const Reports = lazy(() => import('./Reports'))

export function App() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/reports" element={<Reports />} />
      </Routes>
    </Suspense>
  )
}

// Named export lazy loading
const HeavyChart = lazy(() =>
  import('./HeavyChart').then(mod => ({ default: mod.HeavyChart }))
)
```

#### Next.js Image Optimization

```tsx
import Image from 'next/image'
import heroImage from '@/public/hero.jpg'

// Local image: auto width/height, blur placeholder
<Image
  src={heroImage}
  alt="Hero banner"
  placeholder="blur"          // blur-up from tiny base64
  priority                    // preload for LCP — use ONLY for above-fold hero
  sizes="100vw"
/>

// Remote image: must configure domains in next.config.js
<Image
  src="https://cdn.example.com/photo.jpg"
  alt="User photo"
  width={400}
  height={300}
  loading="lazy"              // default for below-fold images
/>
```

**Rules**:
- Always provide `sizes` for responsive images
- Use `priority` ONLY on LCP image (1 per page max)
- Don't use `priority` for lazy-loaded images (wastes bandwidth)

#### Bundle Analysis

```bash
# Next.js built-in bundle analyzer
ANALYZE=true next build

# Or add @next/bundle-analyzer to next.config.js
```

```js
// next.config.js
const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
})
module.exports = withBundleAnalyzer({ /* config */ })
```

Look for:
- Duplicate dependencies (same lib in multiple chunks)
- Large moment.js / lodash (use tree-shakeable alternatives: date-fns, lodash-es)
- Accidental server-only imports leaking into client bundles

---

### Testing

#### Vitest + React Testing Library

```tsx
// UserProfile.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { UserProfile } from './UserProfile'

describe('UserProfile', () => {
  it('renders user name after loading', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      json: () => Promise.resolve({ name: 'Alice', email: 'alice@test.com' }),
    } as Response)

    // Act
    render(<UserProfile userId="1" />)

    // Assert — loading state
    expect(screen.getByRole('status')).toHaveTextContent('Loading...')

    // Assert — loaded state
    await waitFor(() => expect(screen.getByText('Alice')).toBeInTheDocument())
  })

  it('calls onDelete when delete button clicked', async () => {
    const onDelete = vi.fn()
    render(<UserProfile userId="1" onDelete={onDelete} />)

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /delete user/i }))

    expect(onDelete).toHaveBeenCalledWith('1')
  })
})
```

**Query priority** (most to least preferred):
```
getByRole          ← always preferred (accessible)
getByLabelText     ← form fields
getByPlaceholderText
getByText          ← non-interactive text content
getByDisplayValue  ← filled form values
getByAltText       ← images
getByTitle         ← fallback
getByTestId        ← LAST RESORT (when nothing else works)
```

#### Testing Components with Suspense

```tsx
// Async component test
import { Suspense } from 'react'
import { render, screen, waitFor } from '@testing-library/react'

it('renders async data', async () => {
  render(
    <Suspense fallback={<div>Loading...</div>}>
      <AsyncUserList />
    </Suspense>
  )

  expect(screen.getByText('Loading...')).toBeInTheDocument()
  await waitFor(() => {
    expect(screen.getByRole('list')).toBeInTheDocument()
  })
})
```

#### Playwright E2E

```tsx
// e2e/checkout.spec.ts
import { test, expect } from '@playwright/test'

test('complete checkout flow', async ({ page }) => {
  await page.goto('/products')
  await page.getByRole('button', { name: 'Add to Cart' }).first().click()
  await page.getByRole('link', { name: /cart/i }).click()

  await expect(page.getByTestId('cart-count')).toHaveText('1')

  await page.getByRole('button', { name: 'Checkout' }).click()
  await page.getByLabel('Card Number').fill('4242424242424242')
  await page.getByRole('button', { name: 'Pay Now' }).click()

  await expect(page.getByText('Order Confirmed')).toBeVisible()
})
```

#### Snapshot Testing

```tsx
// Use for: UI components that render predictably
// DON'T use for: dynamic data, icons, dates, random IDs
import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

it('matches snapshot', () => {
  const { container } = render(<Button variant="primary">Click</Button>)
  expect(container.firstChild).toMatchSnapshot()
})
```

---

### Advanced Patterns

#### Error Boundaries

```tsx
'use client'
import { Component, type ReactNode } from 'react'

interface Props { children: ReactNode; fallback: ReactNode }
interface State { hasError: boolean; error?: Error }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) return this.props.fallback
    return this.props.children
  }
}

// Preferred: use react-error-boundary library
import { ErrorBoundary } from 'react-error-boundary'

function ErrorFallback({ error, resetErrorBoundary }: {
  error: Error; resetErrorBoundary: () => void
}) {
  return (
    <div role="alert">
      <p>Something went wrong:</p>
      <pre>{error.message}</pre>
      <button onClick={resetErrorBoundary}>Try again</button>
    </div>
  )
}

// Usage: wrap any component tree that may throw
<ErrorBoundary FallbackComponent={ErrorFallback} onReset={() => {/* reset state */}}>
  <DangerousComponent />
</ErrorBoundary>
```

Place Error Boundaries around:
- Individual feature sections (isolate failures)
- Top of the tree for a global fallback
- NEVER inside event handlers (use try/catch instead)

#### Portals

```tsx
import { createPortal } from 'react-dom'

export function Modal({ isOpen, onClose, children }: {
  isOpen: boolean; onClose: () => void; children: React.ReactNode
}) {
  if (!isOpen) return null
  return createPortal(
    <div role="dialog" aria-modal="true" className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        {children}
      </div>
    </div>,
    document.getElementById('portal-root')!  // renders outside parent DOM hierarchy
  )
}

// In layout.tsx (or _document): <div id="portal-root" />
```

#### HoC vs Hooks

```
HoC (Higher-Order Component)          Hooks (Preferred for React 18+)
─────────────────────────────          ──────────────────────────────
function withAuth(Component) {        function useAuth() {
  return function Protected(props) {    const { user, isLoading } = useSession()
    const { user } = useSession()       return { user, isLoading }
    if (!user) return <Login />       }
    return <Component {...props} />
  }                                   function Dashboard() {
}                                       const { user, isLoading } = useAuth()
                                        if (isLoading) return <Spinner />
// Usage:                                if (!user) return <Login />
export default withAuth(Dashboard)      return <DashboardContent />
                                      }
```

**Rule**: Use Hooks for new code. HoCs remain useful for:
- Wrapping class components with hook-based logic
- Cross-cutting concerns that need to wrap render output (like error boundaries)
- Injecting identical behavior into many components without duplication

#### Controlled vs Uncontrolled Components

```tsx
// Controlled: React owns the state (single source of truth)
function ControlledInput() {
  const [value, setValue] = useState('')
  return <input value={value} onChange={e => setValue(e.target.value)} />
}

// Uncontrolled: DOM owns the state (React reads when needed)
function UncontrolledForm() {
  const inputRef = useRef<HTMLInputElement>(null)
  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    console.log(inputRef.current?.value)  // read from DOM on submission
  }
  return (
    <form onSubmit={handleSubmit}>
      <input ref={inputRef} defaultValue="" />
    </form>
  )
}
```

**When to use uncontrolled**: File inputs (browser security), large forms (performance), integrating with non-React libraries.

#### ForwardRef + useImperativeHandle

```tsx
import { forwardRef, useImperativeHandle, useRef } from 'react'

export interface FancyInputHandle {
  focus: () => void
  clear: () => void
  select: () => void
}

export const FancyInput = forwardRef<FancyInputHandle, { label: string }>(
  function FancyInput({ label }, ref) {
    const inputRef = useRef<HTMLInputElement>(null)

    useImperativeHandle(ref, () => ({
      focus: () => inputRef.current?.focus(),
      clear: () => { if (inputRef.current) inputRef.current.value = '' },
      select: () => inputRef.current?.select(),
    }))

    return (
      <label>
        {label}
        <input ref={inputRef} />
      </label>
    )
  }
)

// Parent usage
function Parent() {
  const inputRef = useRef<FancyInputHandle>(null)
  return (
    <>
      <FancyInput ref={inputRef} label="Name" />
      <button onClick={() => inputRef.current?.focus()}>Focus input</button>
    </>
  )
}
```

---

### Next.js App Router

#### Component Decision Map

```
┌──────────────────────────────────────────────────────┐
│                  Next.js App Router                    │
│                                                        │
│  app/                                                  │
│  ├── layout.tsx     (Server by default, wraps children) │
│  ├── page.tsx        (Server by default)               │
│  ├── loading.tsx     (Server, Suspense fallback)       │
│  ├── error.tsx       (Client — must be "use client")   │
│  ├── not-found.tsx   (Server or Client)                │
│  ├── route.ts        (API route handler)               │
│  └── global-error.tsx (Client, catches root errors)    │
└──────────────────────────────────────────────────────┘
```

#### Layout Patterns

```tsx
// app/(marketing)/layout.tsx  — Route Group (doesn't affect URL)
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <MarketingNav />
      {children}
      <MarketingFooter />
    </div>
  )
}

// app/dashboard/layout.tsx — Nested layout (wraps all /dashboard/* pages)
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex">
      <DashboardSidebar />
      <main>{children}</main>
    </div>
  )
}
```

#### Loading / Error / Not-Found

```tsx
// app/products/loading.tsx — shown while page.tsx resolves
export default function Loading() {
  return <ProductsSkeleton />
}

// app/products/[id]/not-found.tsx — when notFound() is called
export default function NotFound() {
  return <h1>Product not found</h1>
}

// In page.tsx:
import { notFound } from 'next/navigation'

export default async function ProductPage({ params }: { params: { id: string } }) {
  const product = await db.product.findUnique({ where: { id: params.id } })
  if (!product) notFound()
  return <ProductDetail product={product} />
}
```

```tsx
// app/products/error.tsx — MUST be "use client"
'use client'
export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={reset}>Try again</button>
    </div>
  )
}
```

#### Server Actions

```tsx
// app/actions/users.ts
'use server'
import { revalidatePath } from 'next/cache'
import { z } from 'zod'

const schema = z.object({ name: z.string().min(1), email: z.string().email() })

export async function createUser(formData: FormData) {
  const parsed = schema.safeParse(Object.fromEntries(formData))

  if (!parsed.success) {
    return { error: parsed.error.flatten().fieldErrors }
  }

  await db.user.create({ data: parsed.data })
  revalidatePath('/users')
  return { success: true }
}
```

```tsx
// app/users/CreateUserForm.tsx
'use client'
import { useFormStatus } from 'react-dom'
import { createUser } from '@/app/actions/users'

function SubmitButton() {
  const { pending } = useFormStatus()
  return <button disabled={pending}>{pending ? 'Saving...' : 'Create User'}</button>
}

export function CreateUserForm() {
  const [state, formAction] = useActionState(createUser, null)  // useFormState renamed in React 19

  return (
    <form action={formAction}>
      <input name="name" required />
      {state?.error?.name && <span>{state.error.name}</span>}
      <input name="email" type="email" required />
      {state?.error?.email && <span>{state.error.email}</span>}
      <SubmitButton />
    </form>
  )
}
```

#### Route Handlers (API Routes)

```tsx
// app/api/users/route.ts
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const page = parseInt(searchParams.get('page') ?? '1')
  const users = await db.user.findMany({ skip: (page - 1) * 10, take: 10 })
  return NextResponse.json(users)
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  const user = await db.user.create({ data: body })
  return NextResponse.json(user, { status: 201 })
}
```

#### Middleware

```tsx
// middleware.ts (at root, NOT inside app/)
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const token = request.cookies.get('token')
  const isAuthPage = request.nextUrl.pathname.startsWith('/login')

  if (!token && !isAuthPage) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  if (token && isAuthPage) {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*', '/login'],  // only run on these paths
}
```

---

### Anti-Patterns (with Fixes)

#### 1. `useEffect` for Derived State

```tsx
// ❌ BAD: useEffect to derive state from props
function Bad({ first, last }: { first: string; last: string }) {
  const [fullName, setFullName] = useState('')
  useEffect(() => { setFullName(`${first} ${last}`) }, [first, last])
  return <span>{fullName}</span>
}
// Causes: extra render, desync window where fullName is stale

// ✅ GOOD: compute during render (no useEffect needed)
function Good({ first, last }: { first: string; last: string }) {
  const fullName = `${first} ${last}`
  return <span>{fullName}</span>
}
// For expensive derivations, use useMemo:
// const fullName = useMemo(() => `${first} ${last}`, [first, last])
```

#### 2. `useContext` for High-Frequency State

```tsx
// ❌ BAD: every keystroke re-renders entire tree
const SearchContext = createContext('')
function App() {
  const [query, setQuery] = useState('')
  return (
    <SearchContext.Provider value={query}>
      <SearchBar />      {/* re-renders on every keystroke */}
      <SlowResults />    {/* re-renders on every keystroke */}
    </SearchContext.Provider>
  )
}

// ✅ GOOD: use Zustand selector for fine-grained subscriptions
// Only the component that reads `query` will re-render
```

#### 3. New Object/Array/Function Refs in Dependencies

```tsx
// ❌ BAD: inline object creates new reference every render, useEffect runs every render
function Bad({ id }: { id: string }) {
  useEffect(() => {
    fetch(`/api/items/${id}`)
  }, [{ id }])  // new object every render = always triggers
}

// ❌ BAD: inline function in deps
const Bad = memo(function Bad({ onSave }: { onSave: (d: Data) => void }) {
  useEffect(() => {
    onSave(data)  // onSave is new on every parent render without useCallback
  }, [onSave])
})

// ✅ GOOD: use primitive deps or stable references
function Good({ id }: { id: string }) {
  useEffect(() => {
    fetch(`/api/items/${id}`)
  }, [id])  // primitive string, stable identity
}
```

#### 4. Over-Memoization

```tsx
// ❌ BAD: memoizing everything blindly adds overhead
const Bad = memo(function Title({ text }: { text: string }) {
  return <h1>{text}</h1>  // cheaper to re-render than to compare props!
})

// ❌ BAD: useMemo for trivial computation
const doubled = useMemo(() => items.length * 2, [items])  // unnecessary overhead

// ✅ GOOD: only memoize when profiler confirms benefit
// Open React DevTools > Profiler > record interaction > look for slow commits
```

#### 5. Using `index` as Key

```tsx
// ❌ BAD: key={index} breaks React's reconciliation when list order changes
{items.map((item, i) => <Item key={i} {...item} />)}

// ✅ GOOD: use stable unique identifiers
{items.map(item => <Item key={item.id} {...item} />)}
// If no stable ID, generate one at creation time, NEVER in render
```

#### 6. `useEffect` without Cleanup

```tsx
// ❌ BAD: no cleanup — memory leaks, stale event listeners
useEffect(() => {
  const handler = () => setWidth(window.innerWidth)
  window.addEventListener('resize', handler)
  // Missing: return () => window.removeEventListener('resize', handler)
}, [])

// ✅ GOOD: always return cleanup function for subscriptions
useEffect(() => {
  const handler = () => setWidth(window.innerWidth)
  window.addEventListener('resize', handler)
  return () => window.removeEventListener('resize', handler)
}, [])
```

---

### File Convention

```
src/
├── app/                      # Next.js App Router pages and layouts
│   ├── (marketing)/          # Route group (doesn't affect URL)
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── pricing/
│   │       └── page.tsx
│   ├── dashboard/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── loading.tsx
│   │   ├── error.tsx
│   │   └── settings/
│   │       └── page.tsx
│   ├── api/
│   │   └── users/
│   │       └── route.ts
│   ├── layout.tsx            # Root layout
│   ├── page.tsx              # Root page
│   ├── loading.tsx
│   ├── error.tsx
│   ├── not-found.tsx
│   └── global-error.tsx
├── components/               # Shared UI components
│   ├── ui/                   # Primitive UI (Button, Input, Modal, etc.)
│   │   ├── Button.tsx
│   │   ├── Button.test.tsx
│   │   └── index.ts
│   └── layout/               # Layout components (Header, Sidebar, Footer)
│       ├── Sidebar.tsx
│       └── Sidebar.test.tsx
├── features/                 # Feature modules (vertical slices)
│   ├── auth/
│   │   ├── actions.ts        # Server Actions
│   │   ├── components/       # Feature-specific components
│   │   ├── hooks/            # Feature-specific hooks
│   │   ├── schemas.ts        # Zod schemas
│   │   └── index.ts
│   └── billing/
│       └── ...
├── hooks/                    # Shared hooks
│   ├── useAuth.ts
│   └── useMediaQuery.ts
├── lib/                      # Third-party wrapper/config, utilities
│   ├── db.ts                 # Database client
│   ├── auth.ts               # Auth configuration
│   └── utils.ts              # Pure utility functions
├── types/                    # Shared TypeScript types
│   └── index.ts
└── styles/                   # Global styles, design tokens
    └── globals.css
```

**Naming rules**:
- **Components**: PascalCase — `UserProfile.tsx`, `SubmitButton.tsx`
- **Hooks**: camelCase with `use` prefix — `useAuth.ts`, `useMediaQuery.ts`
- **Utilities**: camelCase — `formatDate.ts`, `cn.ts`
- **Types**: camelCase — `user.ts`, `api.ts`
- **Tests**: Co-locate with source — `Button.test.tsx` next to `Button.tsx`
- **Barrel exports**: `index.ts` files for clean imports

---

### Common Troubleshooting

#### "Too Many Re-renders"

```
Cause: setState called unconditionally during render, creating infinite loop.

❌ { setCount(count + 1) }           // calls setState during render
❌ <button onClick={setCount(count + 1)}>  // calls setCount immediately
✅ <button onClick={() => setCount(count + 1)}>  // calls on click only
✅ useEffect(() => { setCount(count + 1) }, [dep])  // controlled dependency
```

#### "useEffect Running Twice" in StrictMode

```tsx
// React 18 StrictMode intentionally double-invokes effects in development
// to detect missing cleanups. This is NOT a bug.

// If you see double-fetching:
// 1. Check that your effect has proper cleanup
// 2. Consider using TanStack Query (deduplicates requests)
// 3. Use AbortController to cancel stale requests:

useEffect(() => {
  const controller = new AbortController()
  fetch('/api/data', { signal: controller.signal })
    .then(r => r.json())
    .then(setData)
  return () => controller.abort()
}, [])
```

#### "State Not Updating"

```tsx
// ❌ State updates are batched — logging immediately after setState shows old value
function Bad() {
  const [count, setCount] = useState(0)
  function increment() {
    setCount(count + 1)
    console.log(count)  // still 0! State update is asynchronous
  }
}

// ✅ Use the functional updater to access latest state
function Good() {
  const [count, setCount] = useState(0)
  function increment() {
    setCount(prev => prev + 1)  // always gets latest state
  }
}

// ✅ Or use useEffect to react to state changes
useEffect(() => {
  console.log(count)  // logs AFTER state update
}, [count])
```

#### "Stale Closures"

```tsx
// ❌ The useEffect captures the `count` value at the time it was created
function Bad() {
  const [count, setCount] = useState(0)
  useEffect(() => {
    const id = setInterval(() => {
      console.log(count)  // ALWAYS logs 0 — stale closure!
    }, 1000)
    return () => clearInterval(id)
  }, [])  // empty deps = captures initial count
}

// ✅ Use functional update to access current value
function Good() {
  const [count, setCount] = useState(0)
  useEffect(() => {
    const id = setInterval(() => {
      setCount(c => c + 1)  // functional update reads latest value
    }, 1000)
    return () => clearInterval(id)
  }, [])
}

// Alternative: useRef to keep a mutable reference to latest value
function AlsoGood() {
  const [count, setCount] = useState(0)
  const countRef = useRef(count)
  countRef.current = count  // keep ref in sync

  useEffect(() => {
    const id = setInterval(() => {
      console.log(countRef.current)  // always reads latest
    }, 1000)
    return () => clearInterval(id)
  }, [])
}
```

#### "Hydration Mismatch"

```
Cause: Server-rendered HTML doesn't match client-rendered HTML.
Common causes:
  - Using browser APIs (window, localStorage) during render
  - Random values (Math.random(), Date.now()) during render
  - Conditional rendering based on undefined/mismatched values
  - Incorrect HTML nesting (div inside p, etc.)
```

```tsx
// ❌ BAD: localStorage accessed during render — different server vs client
function Bad() {
  const theme = localStorage.getItem('theme')  // crashes on server
  return <div className={theme}>...</div>
}

// ✅ GOOD: useEffect for browser-only code
function Good() {
  const [theme, setTheme] = useState('light')
  useEffect(() => {
    setTheme(localStorage.getItem('theme') ?? 'light')
  }, [])
  return <div className={theme}>...</div>
}

// ✅ Or use suppressHydrationWarning for intentional differences
// (e.g., time-ago components where exact timestamps differ slightly)
<time suppressHydrationWarning>{formatRelative(timestamp)}</time>
```

---

### Security in React

#### XSS Prevention

```tsx
// React automatically escapes JSX values — you're safe by default
const userInput = '<img src=x onerror=alert(1)>'
return <div>{userInput}</div>  // Renders as text, NOT HTML — SAFE

// ❌ DANGEROUS: dangerouslySetInnerHTML bypasses escaping
// ONLY use with sanitized content
import DOMPurify from 'dompurify'

function SafeHtml({ html }: { html: string }) {
  const sanitized = DOMPurify.sanitize(html)
  return <div dangerouslySetInnerHTML={{ __html: sanitized }} />
}

// ❌ DANGEROUS: Passing user input to href without validation
<a href={userInput}>Click</a>  // javascript:alert(1) would execute

// ✅ Validate URLs before using in href
function SafeLink({ url, children }: { url: string; children: React.ReactNode }) {
  const safe = url.startsWith('https://') || url.startsWith('/')
  if (!safe) return <span>{children}</span>
  return <a href={url}>{children}</a>
}
```

#### CSRF Protection with Next.js

```tsx
// Server Actions have built-in CSRF protection via Next.js
// For custom API routes, use SameSite cookies + CSRF tokens:

// middleware.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  // Validate origin/referer for mutating requests
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(request.method)) {
    const origin = request.headers.get('origin')
    const host = request.headers.get('host')
    if (origin && !origin.includes(host!)) {
      return new NextResponse(null, { status: 403 })
    }
  }
  return NextResponse.next()
}

// Cookie configuration for auth tokens:
// Set-Cookie: token=...; HttpOnly; Secure; SameSite=Lax; Path=/
// SameSite=Lax: allows GET navigations, blocks cross-site POST
// SameSite=Strict: blocks all cross-site requests (stricter)
```

#### Environment Variables

```tsx
// NEXT_PUBLIC_* variables are exposed to the browser — NEVER put secrets here
// ❌ NEXT_PUBLIC_DATABASE_URL=postgres://...  (visible in browser JS!)
// ✅ DATABASE_URL=postgres://...               (server only)

// Use server-only package to prevent accidental client usage:
// lib/db.ts
import 'server-only'
import { PrismaClient } from '@prisma/client'
export const db = new PrismaClient()
// Any client component importing this will throw a build error
```

---

### Implementation Checklist

**Architecture Phase**:
- [ ] Server Components used as default; Client Components only when needed
- [ ] `"use client"` boundary placement minimizes client JS
- [ ] State management strategy documented (server, client, URL state)
- [ ] Error Boundaries placed at feature section boundaries
- [ ] Loading, empty, error states designed for every async component

**Development Phase**:
- [ ] TypeScript strict mode enabled (no `any`)
- [ ] TanStack Query for server state (caching, refetching, mutations)
- [ ] Zustand or Jotai for client state (not Redux by default)
- [ ] React Hook Form + Zod for form validation
- [ ] Only memoize when profiler confirms benefit (not prematurely)
- [ ] `useId()` for unique IDs in SSR contexts

**Performance Phase**:
- [ ] Server Components for data fetching (no client-side waterfalls)
- [ ] `next/image` with `sizes` attribute for responsive images
- [ ] Route-level lazy loading (`lazy()` + `Suspense`)
- [ ] Core Web Vitals: LCP < 2.5s, INP < 200ms, CLS < 0.1
- [ ] Bundle analyzed (`ANALYZE=true next build`) — no dupes, no leaks

**Testing Phase**:
- [ ] Vitest + React Testing Library for unit/component tests
- [ ] Query priority: getByRole > getByLabelText > getByText > getByTestId
- [ ] Playwright for critical user journey E2E tests
- [ ] Snapshot tests for stable UI components
- [ ] Accessibility testing via jest-axe or Lighthouse CI

**Security Phase**:
- [ ] CSP headers configured (script-src 'self')
- [ ] `dangerouslySetInnerHTML` only with DOMPurify sanitized content
- [ ] URL validation before `href` usage
- [ ] Environment variables: `NEXT_PUBLIC_*` for client-safe only; secrets server-only
- [ ] `server-only` package import for server-side code protection

**Deployment Phase**:
- [ ] Next.js build succeeds (`next build`) with no errors
- [ ] ISR/SSG strategy defined per route
- [ ] Environment variables configured per deployment environment
- [ ] Monitoring: Web Vitals, error tracking (Sentry), RUM
- [ ] Feature flags for gradual rollout

