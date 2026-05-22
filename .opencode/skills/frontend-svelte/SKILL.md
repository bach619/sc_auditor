---
name: frontend-svelte
description: Svelte 5 runes ($state, $derived, $effect, $props, $bindable, $inspect), SvelteKit patterns, fine-grained reactivity, performance optimization, testing, and troubleshooting
license: MIT
compatibility: opencode
metadata:
  audience: frontend-developers
  domain: frontend
  paradigm: reactive
  capabilities:
    - svelte5-runes
    - sveltekit-advanced-routing
    - form-actions
    - state-management
    - compile-time-optimization
    - transitions-animations
    - actions-directives
    - snippets
    - testing-vitest
    - e2e-playwright
  integrates_with:
    - frontend-animation
    - mobile-tauri
    - workflow-general
---

## Frontend Svelte/SvelteKit Skill

---

### 1. Svelte 5 Runes (MANDATORY)

Runes are compiler directives that replace Svelte 4's reactive syntax (`$:`, `export let`).
They are function-like symbols that the compiler recognizes and transforms into fine-grained
reactive code at build time. Zero runtime overhead.

#### `$state` — Reactive Variable Declaration

Replaces `let count = 0` + `$:` reactivity. Svelte 5 provides **deep reactivity** by default —
mutating nested properties on objects or calling array methods like `.push()` automatically
triggers updates.

```svelte
<script>
  // Primitive — reactive by declaration
  let count = $state(0)

  // Object — deeply reactive (nested mutations trigger updates)
  let user = $state({ name: 'Alice', profile: { bio: 'Dev' } })

  // Array — push, pop, splice, sort all trigger reactivity
  let items = $state([1, 2, 3])

  // Array with objects — nested mutations also reactive
  let todos = $state([{ id: 1, text: 'Learn Svelte', done: false }])

  function increment() { count++ }
  function rename() { user.name = 'Bob' }                        // triggers update
  function addTodo() { todos.push({ id: Date.now(), text: '', done: false }) }
  function toggle(id) {
    const todo = todos.find(t => t.id === id)
    if (todo) todo.done = !todo.done                             // triggers update
  }
  // Note: for complete array replacement, reassign directly
  function resetAll() { todos = [] }
</script>

<p>Count: {count}</p>
<button onclick={increment}>+1</button>
<p>User: {user.name}</p>
<p>Bio: {user.profile.bio}</p>
<ul>
  {#each todos as todo (todo.id)}
    <li>
      <input type="checkbox" checked={todo.done} onchange={() => toggle(todo.id)} />
      {todo.text}
    </li>
  {/each}
</ul>
```

**Key rules for `$state`**:
- Declare at the top level of `<script>`, not inside functions
- Objects and arrays are **deeply reactive** — unlike Svelte 4 stores
- Reassignment (`user = newUser`) also triggers reactivity
- For class instances, used with `$state` snapshots the instance

#### `$derived` — Computed Values

Replaces reactive declarations (`$: double = count * 2`). Automatically tracks dependencies —
only re-evaluates when a dependency actually changes.

```svelte
<script>
  let count = $state(0)
  let list = $state([10, 20, 30])

  // Simple derivation — auto-tracks `count`
  let doubled = $derived(count * 2)

  // Multiple dependencies — auto-tracks both
  let summary = $derived(`Count: ${count}, Items: ${list.length}`)

  // Array derivations — recomputed when list mutates
  let filtered = $derived(list.filter(n => n > 15))

  // Template literal usage
  let label = $derived(`You have ${count} item${count !== 1 ? 's' : ''}`)
</script>
```

**`$derived.by`** — For complex derivations requiring intermediate variables:

```svelte
<script>
  let items = $state([5, 12, 8, 3, 20])

  let stats = $derived.by(() => {
    if (items.length === 0) return { min: 0, max: 0, avg: 0 }
    let min = Infinity, max = -Infinity, sum = 0
    for (const n of items) {
      if (n < min) min = n
      if (n > max) max = n
      sum += n
    }
    return { min, max, avg: sum / items.length }
  })
</script>
```

**`$derived` rules**:
- Must be pure — no side effects inside
- Cannot be assigned to directly (read-only)
- Use `$derived.by` when you need local variables in the derivation
- Never call `$state` or `$effect` inside `$derived`

#### `$effect` — Side Effects

Replaces `$: { ... }`, `onMount`, `onDestroy`, `beforeUpdate`, `afterUpdate`. Runs whenever
its tracked dependencies change. Returns a cleanup function that runs before the next effect
execution or on component destruction.

```svelte
<script>
  let count = $state(0)
  let search = $state('')

  // Runs when `count` changes — auto-tracks dependencies
  $effect(() => {
    console.log(`Count changed to ${count}`)
  })

  // Cleanup function — runs before re-execution or on destroy
  $effect(() => {
    const interval = setInterval(() => {
      console.log('tick')
    }, 1000)
    return () => clearInterval(interval)     // cleanup on destroy
  })

  // DOM manipulation after render
  let divRef = $state(null)
  $effect(() => {
    if (divRef) {
      divRef.scrollTop = divRef.scrollHeight
    }
  })

  // Debounced search (no external library needed)
  $effect(() => {
    const query = search                         // snapshot value
    const timer = setTimeout(() => {
      console.log('Search:', query)
    }, 300)
    return () => clearTimeout(timer)             // cleanup on re-run
  })
</script>
```

**When NOT to use `$effect`**:
- **Deriving state** → Use `$derived` instead
- **Responding to events** → Use `onclick={handler}` instead
- **Synchronizing two pieces of state** → Restructure to avoid the need
- **Transforming props** → Use `$derived` on the prop value
- **Setting initial state** → Use initializer or `$state` default

```svelte
<script>
  // ❌ BAD: using $effect for derivation
  let first = $state('Ada')
  let last = $state('Lovelace')
  let fullName = $state('')
  $effect(() => { fullName = `${first} ${last}` })  // extra render, possible desync

  // ✅ GOOD: use $derived
  let fullName2 = $derived(`${first} ${last}`)
</script>
```

#### `$props` — Component Props Declaration

Replaces `export let`. Supports destructuring, default values, rest props, and class/className
forwarding.

```svelte
<script>
  // Basic props with default values
  let { name, age = 0, role = 'user' } = $props()

  // Rest props — captures everything not explicitly destructured
  let { name: title, ...attributes } = $props()

  // Typed props (TypeScript)
  interface Props {
    name: string
    age?: number
    onSave: (data: FormData) => void
    children: Snippet
  }
  let { name, age = 0, onSave, children }: Props = $props()
</script>

<div {...attributes}>
  <h1>{title}</h1>
  {@render children?.()}
</div>
```

**Class/className forwarding** — `class` and `className` are special: they merge with the
component's own classes (not overwrite):

```svelte
<!-- Button.svelte -->
<script>
  let { class: klass = '', ...rest } = $props()
</script>
<button class="btn-default {klass}" {...rest}><slot /></button>

<!-- Usage -->
<Button class="large primary">Click</Button>
<!-- Renders: <button class="btn-default large primary">Click</button> -->
```

#### `$bindable` — Two-Way Binding Props

Replaces `export let value` + `bind:value`. Creates a prop that can be bound from the parent.

```svelte
<script>
  // Simple bindable with default value
  let { value = $bindable('') } = $props()

  // With type annotation
  let { open = $bindable(false), items = $bindable([]) } = $props()
</script>

<input bind:value />

{#if open}
  <dialog open onclose={() => open = false}>
    <slot />
  </dialog>
{/if}
```

```svelte
<!-- Parent usage -->
<MyInput bind:value={name} />
```

#### `$inspect` — Debugging Reactive Changes

Development-only. Logs whenever the inspected expression changes. Never ships to production
(compiler eliminates it).

```svelte
<script>
  let count = $state(0)
  let user = $state({ name: 'Alice' })

  // Basic — logs value on every change
  $inspect(count)
  // Console: [log] 0, [log] 1, [log] 2, ...

  // With label
  $inspect('User changed:', user)

  // Multiple values
  $inspect(count, user.name)

  // $inspect.trace — includes stack trace to find the source of the change
  $inspect.trace(count)
</script>
```

#### `$host` — Custom Element Host Access

When compiling to custom elements (`<svelte:options customElement="my-el" />`), `$host`
returns a reference to the host DOM element.

```svelte
<svelte:options customElement="my-counter" />
<script>
  let count = $state(0)
  const host = $host()
</script>
<button onclick={() => count++}>
  Clicks: {count}
</button>
```

#### Class and Function Shorthand

Svelte 5 allows using class or function as component building blocks when the component
only needs to return markup:

```svelte
<!-- Instead of full component syntax, as a function block -->
<script>
  function Greeting({ name }) {
    return `<h1>Hello, {name}!</h1>`
  }
</script>
<!-- Note: This is a conceptual direction; the primary patterns use standard
     .svelte files with runes -->
```

---

### 2. SvelteKit Patterns

#### Project Structure

```
src/
├── routes/                    # File-based routing
│   ├── +page.svelte          # Page component
│   ├── +page.ts              # Universal load function
│   ├── +page.server.ts       # Server-only load function
│   ├── +layout.svelte        # Layout wrapping child routes
│   ├── +layout.ts            # Layout load function
│   ├── +error.svelte         # Error boundary
│   ├── +server.ts            # API route handler
│   └── (app)/                # Route group (doesn't affect URL)
│       ├── dashboard/
│       │   ├── +page.svelte
│       │   └── settings/
│       │       └── +page.svelte
│       └── +layout.svelte
├── lib/                       # Shared code (aliased as $lib/)
│   ├── components/
│   ├── server/                # Server-only utilities
│   └── utils.ts
├── hooks.server.ts            # Server-side hooks
├── hooks.client.ts            # Client-side hooks
└── app.html                   # Root HTML template
```

#### Load Functions (`+page.ts` vs `+page.server.ts`)

**Universal load** (`+page.ts`) — runs on server AND client (hydration). Use for data that
can be fetched from the client (public APIs, non-sensitive data).

**Server load** (`+page.server.ts`) — runs ONLY on server. Use for database queries, private
APIs, auth-protected data, reading environment variables.

```typescript
// src/routes/products/+page.server.ts  (server-only)
import { db } from '$lib/server/db'

export async function load({ params, url, locals }) {
  const page = Number(url.searchParams.get('page') ?? '1')
  const products = await db.product.findMany({
    skip: (page - 1) * 20,
    take: 20
  })
  return { products, page }
}
```

```typescript
// src/routes/products/+page.ts  (universal — runs client + server)
export async function load({ fetch, params }) {
  const res = await fetch(`/api/products/${params.id}`)
  const product = await res.json()
  return { product }
}
```

```svelte
<!-- src/routes/products/+page.svelte -->
<script>
  let { data } = $props()   // data comes from load function
</script>

<h1>Products</h1>
<ul>
  {#each data.products as product (product.id)}
    <li><a href="/products/{product.id}">{product.name}</a></li>
  {/each}
</ul>
```

**Streaming data with promises**:

```typescript
// src/routes/dashboard/+page.server.ts
export async function load() {
  return {
    // Resolves immediately
    user: await db.user.findFirst(),
    // Streamed — page renders with fallback, updates when resolved
    analytics: db.analytics.aggregate({ /* heavy query */ })
  }
}
```

```svelte
<!-- src/routes/dashboard/+page.svelte -->
<script>
  let { data } = $props()
</script>

<h2>Welcome, {data.user.name}</h2>

{#await data.analytics}
  <p>Loading analytics...</p>
{:then stats}
  <p>Total sales: {stats.total}</p>
{:catch error}
  <p class="error">Failed to load analytics</p>
{/await}
```

#### `+layout.svelte` — Persistent Layouts

Layouts persist across navigations within their route segment. Load data flows from
layout to child pages.

```typescript
// src/routes/+layout.server.ts
export async function load({ locals }) {
  return {
    session: await locals.auth()
  }
}
```

```svelte
<!-- src/routes/+layout.svelte -->
<script>
  let { data, children } = $props()
</script>

<nav>
  <a href="/">Home</a>
  {#if data.session}
    <a href="/dashboard">Dashboard</a>
    <span>{data.session.user.name}</span>
  {:else}
    <a href="/login">Login</a>
  {/if}
</nav>

<main>
  {@render children()}
</main>
```

**Layout invalidation** — use `invalidate()` or `depends()`:

```typescript
// +page.server.ts
export async function load({ depends }) {
  depends('app:session')     // layout re-runs when this key is invalidated
  return { /* ... */ }
}

// In another action/component:
import { invalidate } from '$app/navigation'
await invalidate('app:session')
```

#### `+error.svelte` — Error Boundaries

```svelte
<!-- src/routes/products/[id]/+error.svelte -->
<script>
  let { error } = $props()
</script>

<h1>Error: {error.message}</h1>
{#if error.code === 'NOT_FOUND'}
  <p>This product does not exist.</p>
{:else}
  <p>Something went wrong. Please try again.</p>
{/if}
<a href="/products">Back to products</a>
```

#### `+server.ts` — API Routes

```typescript
// src/routes/api/users/+server.ts
import { json } from '@sveltejs/kit'
import { db } from '$lib/server/db'

export async function GET({ url }) {
  const page = Number(url.searchParams.get('page') ?? '1')
  const users = await db.user.findMany({ skip: (page - 1) * 10, take: 10 })
  return json(users)
}

export async function POST({ request }) {
  const body = await request.json()
  const user = await db.user.create({ data: body })
  return json(user, { status: 201 })
}

// Named fallback for unsupported methods
export function fallback({ request }) {
  return json({ error: `Method ${request.method} not allowed` }, { status: 405 })
}
```

#### Form Actions with `use:enhance`

Form actions are the SvelteKit-preferred way to handle mutations. They work without
JavaScript (progressive enhancement) and integrate with `use:enhance` for SPA-like UX.

```typescript
// src/routes/login/+page.server.ts
import { fail, redirect } from '@sveltejs/kit'
import { z } from 'zod'

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8)
})

export const actions = {
  default: async ({ request, cookies }) => {
    const data = await request.formData()
    const result = schema.safeParse(Object.fromEntries(data))

    if (!result.success) {
      return fail(400, {
        errors: result.error.flatten().fieldErrors,
        email: data.get('email') as string
      })
    }

    const token = await authenticate(result.data)
    cookies.set('token', token, { path: '/', httpOnly: true, secure: true, sameSite: 'lax' })
    throw redirect(303, '/dashboard')
  }
}
```

```svelte
<!-- src/routes/login/+page.svelte -->
<script>
  let { form } = $props()
  import { enhance } from '$app/forms'
</script>

<form method="POST" use:enhance>
  <input name="email" type="email" value={form?.email ?? ''} />
  {#if form?.errors?.email}
    <span class="error">{form.errors.email}</span>
  {/if}
  <input name="password" type="password" />
  {#if form?.errors?.password}
    <span class="error">{form.errors.password}</span>
  {/if}
  <button type="submit">Login</button>
</form>
```

**Custom `use:enhance` callback** for optimistic updates, resetting, etc.:

```svelte
<form method="POST" use:enhance={({ formElement, formData, action, cancel }) => {
  // Before submission
  loading = true

  return async ({ result, update }) => {
    // After response
    loading = false
    if (result.type === 'success') {
      formElement.reset()
    }
    update()  // re-run load functions to refresh page data
  }
}}>
```

#### Advanced Routing

```
src/routes/
├── (app)/                      # Route group — does NOT affect URL
│   ├── +layout.svelte
│   └── dashboard/+page.svelte  # URL: /dashboard (not /app/dashboard)
├── (marketing)/
│   ├── +layout.svelte
│   └── pricing/+page.svelte    # URL: /pricing
├── [id]/+page.svelte           # Dynamic param: /123
├── [...rest]/+page.svelte      # Rest param: /a/b/c
├── [[lang]]/+page.svelte       # Optional param: /en or /
└── [id=integer]/+page.svelte   # Matcher: only numeric IDs
```

**Param matchers** (`src/params/integer.ts`):

```typescript
// src/params/integer.ts
export function match(param: string): boolean {
  return /^\d+$/.test(param)
}
```

#### Hooks

```typescript
// src/hooks.server.ts
import { sequence } from '@sveltejs/kit/hooks'

// handle — runs on every server request (before load functions)
async function auth({ event, resolve }) {
  const token = event.cookies.get('token')
  if (token) {
    event.locals.user = await verifyToken(token)
  }
  return resolve(event)
}

async function logging({ event, resolve }) {
  const start = Date.now()
  const response = await resolve(event)
  console.log(`${event.request.method} ${event.url.pathname} — ${Date.now() - start}ms`)
  return response
}

export const handle = sequence(auth, logging)

// handleFetch — intercept server-side fetch calls
export async function handleFetch({ request, fetch }) {
  if (request.url.startsWith('https://internal-api.example.com')) {
    request.headers.set('x-api-key', process.env.INTERNAL_API_KEY!)
  }
  return fetch(request)
}

// handleError — catch unhandled errors
export function handleError({ error, event }) {
  console.error(`Error at ${event.url.pathname}:`, error)
  return {
    message: 'An unexpected error occurred',
    code: error?.code ?? 'UNKNOWN'
  }
}
```

---

### 3. Performance

#### Compile-Time Optimization

Svelte is a **compiler**, not a runtime framework. At build time:
- Components are compiled to imperative DOM manipulation code
- There is no virtual DOM — updates surgically modify only changed nodes
- The Svelte runtime is typically < 2KB gzipped (for a non-SvelteKit app)

#### `$derived` for Automatic Memoization

`$derived` only recalculates when its tracked dependencies change — no manual `useMemo` or dependency
arrays required. The compiler knows the exact dependency graph at build time.

```svelte
<script>
  let items = $state([...])              // large array
  let filter = $state('all')

  // Only recomputed when `items` or `filter` changes
  let filtered = $derived(items.filter(item => {
    if (filter === 'all') return true
    return item.category === filter
  }))
</script>
```

#### CSS Scoping and Elimination

- Component styles are **automatically scoped** — class names are hashed at compile time
- **Unused CSS is eliminated** — the compiler knows which classes are used in markup
- CSS is extracted to `.css` files, not injected via JS (no FOUC)
- Use `:global()` for styles that should escape scoping:

```svelte
<style>
  .card { /* scoped to this component */ }
  :global(.theme-dark) .card { /* targets .card when ancestor has .theme-dark */ }
  :global(body) { /* targets the real <body> element */ }
</style>
```

#### Code Splitting

SvelteKit auto-splits by route. For manual splitting:

```svelte
<script>
  import { onMount } from 'svelte'

  // Dynamic import — loads HeavyComponent only when needed
  onMount(async () => {
    const { default: HeavyChart } = await import('$lib/charts/HeavyChart.svelte')
    // ... use HeavyChart
  })
</script>
```

#### Image Optimization

Use the built-in `<enhanced:img>` for SvelteKit (requires `@sveltejs/enhanced-img`):

```svelte
<script>
  import hero from './hero.jpg?w=800;400&format=webp;avif'
</script>

<enhanced:img src={hero} alt="Hero" />
<!-- Generates: responsive srcset, <picture> with multiple formats, lazy-loaded -->
```

Without SvelteKit, prefer: explicit `width`/`height` attributes, lazy loading, and serving
properly sized images from a CDN.

---

### 4. State Management

#### Decision Matrix

| Approach | Scope | When to Use |
|----------|-------|-------------|
| `$state` (component-local) | Single component | UI state, form inputs, toggles |
| `$state` (module-level) | All components in the app | Truly global state (theme, auth, feature flags) |
| Svelte stores | Cross-component, subscriber-based | Shared state with reactive get/set, interop with non-Svelte code |
| Context API (`setContext`/`getContext`) | Component subtree | Scoped shared state (form state, list selection) |

#### Module-Level `$state` (Recommended for Global State)

Since Svelte 5 `$state` is just a JavaScript variable to the compiler, declaring it
at the module level makes it globally reactive:

```typescript
// src/lib/stores/theme.svelte.ts
function createTheme() {
  let theme = $state<'light' | 'dark'>('light')

  return {
    get current() { return theme },
    toggle() { theme = theme === 'light' ? 'dark' : 'light' }
  }
}

export const theme = createTheme()
```

```svelte
<!-- Any component — auto-subscribes to theme changes -->
<script>
  import { theme } from '$lib/stores/theme.svelte'
</script>

<button onclick={() => theme.toggle()}>
  Current: {theme.current}
</button>
```

**`$state` module-level** pros: Zero boilerplate, no `.subscribe()`, no `$store` prefix.
Cons: Not serializable like stores, must be initialized at module load time.

#### Svelte Stores (Legacy-Compatible)

Still fully supported in Svelte 5. Required when you need to interop with non-Svelte code
or when you need to initialize state asynchronously.

```typescript
// src/lib/stores/cart.ts
import { writable, derived, readable } from 'svelte/store'

export const items = writable<CartItem[]>([])

export const itemCount = derived(items, $items =>
  $items.reduce((sum, item) => sum + item.quantity, 0)
)

export const total = derived(items, $items =>
  $items.reduce((sum, item) => sum + item.price * item.quantity, 0)
)

// Readable store — only computed once, never externally set
export const isChristmas = readable(checkIfChristmas())

// In components (Svelte 5), use the $store rune:
// <script>
//   import { items, itemCount } from '$lib/stores/cart'
//   let cartItems = $store(items)
//   let count = $store(itemCount)
// </script>
```

#### Context API (Scoped State)

Best for component-subtree-scoped state (forms, accordion, tab groups):

```svelte
<!-- Parent.svelte -->
<script>
  import { setContext } from 'svelte'

  function createFormState() {
    let values = $state<Record<string, string>>({})
    let errors = $state<Record<string, string>>({})

    return {
      get values() { return values },
      get errors() { return errors },
      setField(name: string, value: string) { values[name] = value },
      setError(name: string, msg: string) { errors[name] = msg }
    }
  }

  const form = createFormState()
  setContext('form', form)
</script>

<!-- Child component -->
<script>
  import { getContext } from 'svelte'
  const form = getContext<ReturnType<typeof createFormState>>('form')
</script>

<input
  value={form.values.email ?? ''}
  oninput={e => form.setField('email', e.currentTarget.value)}
/>
```

---

### 5. Advanced Patterns

#### Actions (`use:` directive)

Functions that run when an element is mounted. Can receive parameters and return a
destroy function with an update method.

```svelte
<script>
  // Simple action — focus on mount
  function autofocus(node: HTMLElement) {
    node.focus()
  }

  // Action with parameter and update
  function tooltip(node: HTMLElement, text: string) {
    let tip: HTMLElement
    function show() {
      tip = document.createElement('div')
      tip.className = 'tooltip'
      tip.textContent = text
      document.body.append(tip)
      const rect = node.getBoundingClientRect()
      tip.style.top = `${rect.bottom + 4}px`
      tip.style.left = `${rect.left}px`
    }
    function hide() { tip?.remove() }

    node.addEventListener('mouseenter', show)
    node.addEventListener('mouseleave', hide)

    return {
      update(newText: string) { text = newText },
      destroy() {
        node.removeEventListener('mouseenter', show)
        node.removeEventListener('mouseleave', hide)
        hide()
      }
    }
  }

  let tooltipText = $state('Hello!')
</script>

<input use:autofocus />
<button use:tooltip={tooltipText}>Hover me</button>
```

**Common action use cases**: click-outside detection, lazy-loading images, drag-and-drop,
intersection observer wiring, clipboard integration.

#### Transitions and Animations

Svelte has a built-in transition/animation engine that compiles to efficient CSS and JS.

```svelte
<script>
  import { fly, fade, slide, scale, blur } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { quintOut } from 'svelte/easing'

  let visible = $state(true)
  let items = $state([1, 2, 3, 4, 5])
  let nextId = $state(6)
</script>

<button onclick={() => visible = !visible}>Toggle</button>

{#if visible}
  <!-- Enter (transition:) AND exit (transition:) -->
  <div transition:fly={{ y: 20, duration: 300 }}>
    I fly in and out
  </div>

  <!-- Separate enter/exit animations -->
  <div in:fade={{ duration: 200 }} out:slide={{ duration: 300 }}>
    Different enter and exit
  </div>

  <!-- Custom easing -->
  <div transition:scale={{ duration: 400, easing: quintOut, start: 0.8 }}>
    Scale with bounce-like easing
  </div>
{/if}

<!-- FLIP animation for list reordering -->
<ul>
  {#each items as item (item)}
    <li animate:flip={{ duration: 200 }}>
      {item}
      <button onclick={() => items = items.filter(i => i !== item)}>Remove</button>
    </li>
  {/each}
</ul>
<button onclick={() => { items = [...items, nextId]; nextId++ }}>
  Add
</button>
```

Built-in transition functions: `fly`, `fade`, `slide`, `scale`, `blur`, `draw` (SVG),
`crossfade` (for sending elements between lists).

#### Snippets — Reusable Markup Blocks (Svelte 5)

Snippets replace Svelte 4's slot system for most use cases. They are reusable chunks of
markup with parameters.

```svelte
<script>
  let items = $state([
    { id: 1, name: 'Alice', role: 'Admin' },
    { id: 2, name: 'Bob', role: 'User' },
  ])
</script>

<!-- Define a snippet — reusable markup block -->
{#snippet row(item, index)}
  <tr class={index % 2 === 0 ? 'even' : 'odd'}>
    <td>{item.id}</td>
    <td>{item.name}</td>
    <td><span class="badge">{item.role}</span></td>
  </tr>
{/snippet}

<table>
  <thead><tr><th>ID</th><th>Name</th><th>Role</th></tr></thead>
  <tbody>
    {#each items as item, index}
      {@render row(item, index)}
    {/each}
  </tbody>
</table>
```

**Snippets as component props** — the new way to pass renderable content:

```svelte
<!-- DataTable.svelte -->
<script>
  let {
    items = [],
    columns = [],
    row: RowSnippet
  }: {
    items: any[]
    columns: { key: string; label: string }[]
    row: Snippet<[item: any, index: number]>
  } = $props()
</script>

<table>
  <thead><tr>{#each columns as col}<th>{col.label}</th>{/each}</tr></thead>
  <tbody>
    {#each items as item, index}
      {@render RowSnippet(item, index)}
    {/each}
  </tbody>
</table>
```

```svelte
<!-- Parent usage -->
<DataTable {items} {columns}>
  {#snippet row(item, index)}
    <tr>
      <td>{item.name}</td>
      <td>
        <button onclick={() => deleteItem(item.id)}>Delete</button>
      </td>
    </tr>
  {/snippet}
</DataTable>
```

#### Slots vs Snippets

| Feature | Slots (Svelte 4) | Snippets (Svelte 5) |
|---------|-------------------|----------------------|
| Default content | `<slot>Default</slot>` | `{@render children?.() ?? <p>Default</p>}` |
| Named slots | `<slot name="header" />` | Pass snippets as props |
| Multiple renders | Slot rendered once | Snippet can be rendered multiple times |
| Parameters | `<slot prop={value} />` | `{@render snippet(param1, param2)}` |

Snippets are strictly more powerful. Slots are still supported for backward compatibility
but snippets are the recommended Svelte 5 pattern.

#### Custom Event Dispatching

Svelte 5 encourages **callback props** over `createEventDispatcher`:

```svelte
<!-- Child.svelte -->
<script>
  let { ondelete } = $props<{ ondelete: (id: string) => void }>()
  let id = $state('item-1')
</script>

<button onclick={() => ondelete(id)}>Delete</button>

<!-- If you need native DOM-like events (bubbling, etc.) -->
<script>
  function handleClick(e: MouseEvent) {
    const custom = new CustomEvent('delete', { detail: { id }, bubbles: true })
    e.currentTarget?.dispatchEvent(custom)
  }
</script>
```

---

### 6. Testing

#### Vitest + Testing Library

```typescript
// src/lib/components/Counter.test.ts
import { render, screen, fireEvent } from '@testing-library/svelte/svelte5'
import { describe, it, expect } from 'vitest'
import Counter from './Counter.svelte'

describe('Counter', () => {
  it('renders initial count', () => {
    render(Counter, { props: { initial: 5 } })
    expect(screen.getByText('Count: 5')).toBeDefined()
  })

  it('increments count on button click', async () => {
    render(Counter, { props: { initial: 0 } })
    const button = screen.getByRole('button', { name: 'Increment' })
    await fireEvent.click(button)
    expect(screen.getByText('Count: 1')).toBeDefined()
  })

  it('calls onchange callback', async () => {
    const onChange = vi.fn()
    render(Counter, { props: { initial: 0, onchange: onChange } })
    await fireEvent.click(screen.getByRole('button', { name: 'Increment' }))
    expect(onChange).toHaveBeenCalledWith(1)
  })
})
```

**Testing runes components**: `@testing-library/svelte/svelte5` is required for Svelte 5
components using runes. Use `render` from this package (not the Svelte 4 variant).

**Testing with context**:

```typescript
import { render } from '@testing-library/svelte/svelte5'
import { setContext } from 'svelte'

// Set up context before rendering
render(ChildComponent, {
  context: new Map([['form-key', mockFormValue]])
})
```

#### Playwright E2E

```typescript
// e2e/checkout.test.ts
import { test, expect } from '@playwright/test'

test('completes checkout flow', async ({ page }) => {
  await page.goto('/products')

  // Add first product to cart
  await page.getByRole('button', { name: 'Add to Cart' }).first().click()

  // Navigate to cart
  await page.getByRole('link', { name: 'Cart' }).click()
  await expect(page.getByTestId('cart-count')).toHaveText('1')

  // Proceed to checkout
  await page.getByRole('button', { name: 'Checkout' }).click()
  await expect(page).toHaveURL('/checkout')

  // Fill form and submit
  await page.getByLabel('Name').fill('Test User')
  await page.getByRole('button', { name: 'Place Order' }).click()

  // Verify success
  await expect(page.getByText('Order Confirmed')).toBeVisible()
})
```

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test'

export default defineConfig({
  webServer: {
    command: 'npm run build && npm run preview',
    port: 4173
  },
  testDir: 'e2e',
  use: {
    baseURL: 'http://localhost:4173'
  }
})
```

---

### 7. Troubleshooting

#### Reactivity Not Triggering

**Problem**: State changes but UI doesn't update.

| Cause | Fix |
|-------|-----|
| Variable not declared with `$state` | Add `$state()` wrapper |
| Using `let x = something` instead of `let x = $state(something)` | Convert to `$state` |
| Mutating a non-reactive variable from outside the component | Use module-level `$state` or a store |
| Reassigning a `$derived` value (read-only) | Only derive; use `$state` for writable |
| Async callback without proper `$state` reference | Ensure variable is captured in `$state` |

#### Common `$effect` Mistakes

**Problem**: Infinite loop.

```svelte
<script>
  let count = $state(0)
  // ❌ INFINITE LOOP: effect sets count, which triggers effect
  $effect(() => {
    count = count + 1
  })

  // ✅ What you probably wanted:
  // Use onMount-style pattern with no reactive deps
  $effect(() => {
    count = 1  // only runs once (count = 1 doesn't change count → no re-trigger)
  })
</script>
```

**Problem**: Effect runs too often.

```svelte
<script>
  let user = $state({ name: 'Ada', email: 'ada@example.com' })
  // ❌ This runs on EVERY property change of `user`
  $effect(() => {
    console.log(user.name)  // but also triggers on user.email change
  })

  // ✅ Track only what you use — extract to a plain variable
  let name = $derived(user.name)
  $effect(() => {
    console.log(name)  // only triggers when user.name changes
  })
</script>
```

**Problem**: Effect depends on a value that doesn't trigger reactivity.

```svelte
<script>
  let items = $state([1, 2, 3])
  // ❌ items.length is NOT tracked if we only read .length
  // (Svelte 5 tracks the array object, not .length specifically — test behavior)
  $effect(() => {
    console.log(`Item count: ${items.length}`)
  })
</script>
```

#### Hydration Issues

**Problem**: "Hydration failed because the initial UI does not match what was rendered on the server."

Common causes and fixes:

```svelte
<script>
  import { browser } from '$app/environment'

  // ❌ BAD: browser-only code in module scope
  const stored = localStorage.getItem('theme')  // crashes on server

  // ❌ BAD: random/dynamic values in render
  let id = Math.random()  // different on server vs client

  // ✅ GOOD: guard with browser check
  let theme = $state('light')
  $effect(() => {
    if (browser) {
      theme = localStorage.getItem('theme') ?? 'light'
    }
  })

  // ✅ GOOD: use a deterministic fallback during SSR
  let randomId = $state(crypto.randomUUID?.() ?? 'ssr-placeholder')
  $effect(() => {
    if (!browser) return
    randomId = crypto.randomUUID()
  })
</script>

<!-- For HTML that can't match exactly, use SvelteKit's browser-only rendering pattern: -->
{#if browser}
  <div>{new Date().toLocaleTimeString()}</div>
{/if}
<!-- Note: Svelte does NOT have suppressHydrationWarning; use browser-only blocks or handle dynamic content in $effect -->
```

#### `$derived` Not Updating

`$derived` only tracks **reads that happen synchronously** during evaluation. If you read a
reactive value inside a Promise, `setTimeout`, or event handler inside `$derived`, it will
NOT be tracked:

```svelte
<script>
  let count = $state(0)

  // ❌ BAD: the reactive read `count` happens asynchronously — not tracked
  let derived = $derived.by(() => {
    setTimeout(() => console.log(count), 100)  // count change won't trigger this
    return 'nope'
  })

  // ✅ GOOD: read synchronously in derivation
  let derived2 = $derived(count * 2)
</script>
```

---

### 8. Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| **Using `$effect` for derived state** | Extra render cycle, possible desync window | Use `$derived` |
| **Mutating props directly** | Props are parent-owned; mutation breaks the data flow | Use `$bindable` or callback props |
| **`$state` inside functions/loops** | Runes must be at top-level of `<script>` | Declare at top-level, mutate in functions |
| **Calling `$state` inside `$derived` or `$effect`** | Runes can't be nested | Create all `$state` at top-level only |
| **Over-using stores when `$state` suffices** | Adds boilerplate (subscribe, $ prefix) | Use module-level `$state` for global state |
| **Large objects in `$state` without consideration** | Deep reactivity on huge objects has cost | Split into smaller `$state` variables |
| **`{#each}` without key** | Dom re-creation on mutation, broken transitions | Always provide unique `(item.id)` key |
| **Heavy computation in template expressions** | Runs on every render | Use `$derived` to memoize |
| **Global `$effect` without cleanup** | Memory leaks, stale event listeners | Always return cleanup function from `$effect` when subscribing |
| **Using Svelte 4 patterns (`$:`, `export let`) in Svelte 5** | Legacy mode, misses fine-grained reactivity benefits | Migrate to runes |
| **Over-fetching in load functions** | Slow page loads, redundant data | Use streaming promises, co-locate data requirements |
| **CSS `:global()` without scoping prefix** | Leaks styles across the entire app | Use parent selector: `:global(.parent-class .child)` |

---

### Implementation Checklist

**Architecture Phase**:
- [ ] Svelte 5 runes used exclusively (`$state`, `$derived`, `$effect`, `$props`)
- [ ] Svelte 4 legacy patterns migrated (`$:` → `$derived`, `export let` → `$props`)
- [ ] State: `$state` for component, module-level `$state` for global, Context for scoped
- [ ] Snippets used for reusable markup (over slots where multiple renders needed)
- [ ] Load functions: `+page.server.ts` for sensitive, `+page.ts` for public data

**Development Phase**:
- [ ] `$derived` for all computed values (never `$effect` for derivation)
- [ ] `$effect` with cleanup return for all subscriptions
- [ ] `$bindable` for two-way binding props
- [ ] Form actions with `use:enhance` for progressive enhancement
- [ ] `{#each}` always with unique key `(item.id)`
- [ ] Actions (`use:`) for reusable DOM behavior (click-outside, tooltip, lazy-load)

**Performance Phase**:
- [ ] CSS auto-scoped (no global pollution); `:global()` used sparingly
- [ ] `$derived` for automatic memoization (compiler tracks dependencies)
- [ ] Route-level code splitting (SvelteKit default)
- [ ] `<enhanced:img>` for responsive images
- [ ] Transitions on compositor-only properties (transform, opacity)

**Testing Phase**:
- [ ] Vitest + `@testing-library/svelte/svelte5` for Svelte 5 components
- [ ] Playwright for E2E tests
- [ ] Context setup via `setContext`/`getContext` in component tests
- [ ] Browser-only code guarded with `import { browser } from '$app/environment'`

**Security Phase**:
- [ ] `+page.server.ts` for private data (database, secrets, auth)
- [ ] `$lib/server/` directory for server-only code
- [ ] Form actions with Zod validation on server side
- [ ] CSP headers via `svelte.config.js` or hooks
- [ ] No secrets in `$lib/` (shared code) or `+page.ts` (runs on client)

**Deployment Phase**:
- [ ] SvelteKit adapter selected (`adapter-node`, `adapter-static`, `adapter-vercel`)
- [ ] `svelte.config.js` configured with correct adapter options
- [ ] Environment variables: `$env/static/private` for secrets, `$env/static/public` for public
- [ ] Build succeeds (`npm run build`) with no warnings
- [ ] Prerendering configured for static pages where applicable
