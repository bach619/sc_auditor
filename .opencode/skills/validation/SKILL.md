---
name: validation
description: Data validation mastery — Zod v4 and Valibot. Schema composition, error handling, React Hook Form integration, API validation, TypeScript type inference, tRPC integration, performance optimization, and testing patterns.
license: MIT
compatibility: opencode
metadata:
  audience: fullstack-developers
  domain: validation
  paradigm: declarative-schema
  capabilities:
    - zod-v4
    - valibot
    - react-hook-form
    - api-validation
    - type-inference
    - error-handling
    - schema-composition
    - performance-optimization
  integrates_with:
    - typescript
    - frontend-react
    - backend-nodejs
    - supabase
---

# Skill: validation

## Data Validation — Zod v4 & Valibot — Tingkat Dewa

### Core Philosophy

Schema validation is the **single source of truth** for both runtime validation and TypeScript types. Every application boundary (user input, API response, env vars, form submission) must pass through a validated schema. This eliminates entire classes of bugs at the boundary before they reach business logic.

```
┌──────────────────────────────────────────────────────────────────┐
│              VALIDATION LAYERS IN A TYPICAL APP                  │
│                                                                   │
│   User Input → Form Schema → React Hook Form → API Call          │
│                     ↓                          ↓                  │
│              Zod/Valibot validation     Zod/Valibot on server     │
│                     ↓                          ↓                  │
│               TypeScript type          Sanitized request body     │
│                     ↓                          ↓                  │
│               Rendered UI              Database/Service layer     │
│                                                                   │
│   "Trust no input. Validate at every boundary."                    │
└──────────────────────────────────────────────────────────────────┘
```

**Single Source of Truth principle:**
- Define the schema ONCE
- Infer TypeScript types from the schema (never write `interface` by hand)
- Use the same schema on client and server (shared package)
- Error messages are part of the schema, not scattered in components

---

### 1. Schema Validation Philosophy

#### 1.1 Zod vs Valibot — Decision Tree

```
┌──────────────────────────────────────┐
│        Zod vs Valibot Choice         │
├──────────────────────────────────────┤
│                                      │
│  Need maximum DX + ecosystem?        │
│       │              │               │
│       YES             NO             │
│       ▼               ▼              │
│     Zod v4      Bundle size        │
│                  critical?          │
│                   │        │         │
│                   YES      NO       │
│                   ▼        ▼        │
│               Valibot    Zod v4    │
│                                      │
│  Zod: richer API, larger bundle      │
│  Valibot: tree-shakeable, modular    │
└──────────────────────────────────────┘
```

#### 1.2 Bundle Size Comparison

| Library | Minified | Gzipped | Tree-shakeable |
|---------|----------|---------|----------------|
| Zod v4 | ~35 KB | ~10 KB | Partial |
| Valibot | ~7 KB | ~2.5 KB | Full (per-schema) |
| Yup | ~25 KB | ~6 KB | No |
| Joi | ~50+ KB | ~14 KB | No |

**Rule of thumb:**
- Full-stack monorepo with shared types → **Zod v4** (richer ecosystem, tRPC-first)
- Browser-only or bundle-sensitive → **Valibot** (tree-shake to ~2 KB for basic schemas)
- API-only backend → **Either** (Zod for Fastify/NestJS, Valibot for minimal lambda)

#### 1.3 When to Use What

```typescript
// Zod — full power, full ecosystem
import { z } from 'zod'
const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  role: z.enum(['admin', 'user']),
})

// Valibot — tree-shaken, modular
import { object, string, email, picklist } from 'valibot'
const UserSchema = object({
  id: string([uuid()]),
  email: string([email()]),
  role: picklist(['admin', 'user']),
})
```

---

### 2. Zod v4

#### 2.1 Primitives

```typescript
import { z } from 'zod'

z.string()                         // string
z.number()                         // number
z.boolean()                        // boolean
z.bigint()                         // bigint
z.symbol()                         // symbol
z.date()                           // Date object
z.undefined()                      // undefined
z.null()                           // null
z.void()                           // undefined (accepts null)
z.any()                            // anything — opt-out of validation
z.unknown()                        // unknown — forces refinement before use
z.never()                          // impossible type

// String validators
z.string().min(1, 'Required')
z.string().max(100)
z.string().length(8)
z.string().email('Invalid email')
z.string().url('Invalid URL')
z.string().uuid()
z.string().regex(/^[A-Z]/)
z.string().includes('@')
z.string().startsWith('https://')
z.string().endsWith('.com')
z.string().datetime()
z.string().ip()
z.string().emoji()
z.string().cuid2()
z.string().ulid()
z.string().trim()
z.string().toLowerCase()
z.string().toUpperCase()

// Number validators
z.number().min(0)
z.number().max(100)
z.number().int()
z.number().positive()
z.number().negative()
z.number().nonnegative()
z.number().multipleOf(5)
z.number().finite()
z.number().safe()  // rejects NaN, Infinity
```

#### 2.2 Objects

```typescript
const User = z.object({
  name: z.string(),
  age: z.number().int().positive(),
  email: z.string().email(),
  address: z.object({
    street: z.string(),
    city: z.string(),
    zip: z.string().regex(/^\d{5}$/),
  }).optional(),
})

// Type inference
type User = z.infer<typeof User>
// { name: string; age: number; email: string; address?: { street: string; city: string; zip: string } }

// Strict objects — reject unknown keys
z.object({ name: z.string() }).strict()

// Passthrough — allow unknown keys
z.object({ name: z.string() }).passthrough()

// Catchall — additional keys must match pattern
z.object({ name: z.string() }).catchall(z.string())
```

#### 2.3 Arrays, Tuples, Records, Maps, Sets

```typescript
// Arrays
z.array(z.string())                 // string[]
z.string().array()                  // same as above
z.array(z.number()).min(1)          // non-empty array
z.array(z.number()).max(10)
z.array(z.number()).nonempty()
z.array(z.number()).length(3)

// Tuples — fixed length, positional types
z.tuple([z.string(), z.number()])
z.tuple([z.string(), z.number()]).rest(z.boolean())
// [string, number, ...boolean[]]

// Records — string key → value schema
z.record(z.number())                 // { [key: string]: number }
z.record(z.enum(['x', 'y']), z.number())

// Maps
z.map(z.string(), z.number())        // Map<string, number>

// Sets
z.set(z.number())                    // Set<number>
z.set(z.string()).nonempty()
z.set(z.number()).min(1).max(100)
```

#### 2.4 Unions, Discriminated Unions, Intersections

```typescript
// Union — "either schema A or B"
z.union([z.string(), z.number()])
z.string().or(z.number())            // shorthand

// Discriminated Union — **crucial for perf** (no sequential trial)
const ApiResponse = z.discriminatedUnion('status', [
  z.object({ status: z.literal('success'), data: z.unknown() }),
  z.object({ status: z.literal('error'), message: z.string() }),
  z.object({ status: z.literal('loading') }),
])
// Compiles to a switch statement — O(1) not O(n)

// Intersection
z.intersection(
  z.object({ name: z.string() }),
  z.object({ age: z.number() })
)
z.object({ name: z.string() }).and(z.object({ age: z.number() }))
```

#### 2.5 Enums

```typescript
// Zod enum — array of string literals
z.enum(['admin', 'user', 'guest'])
// Infers as: 'admin' | 'user' | 'guest'

// nativeEnum — from TypeScript enum
enum Role { Admin = 'ADMIN', User = 'USER' }
z.nativeEnum(Role)

// Better approach — const object + nativeEnum
const ROLE = { Admin: 'admin', User: 'user' } as const
z.nativeEnum(ROLE)
```

#### 2.6 Optional, Nullable, Default

```typescript
// Optional — value can be undefined
z.string().optional()                // string | undefined
z.optional(z.string())               // same

// Nullable — value can be null
z.string().nullable()                // string | null

// nullish — value can be null or undefined
z.string().nullish()                 // string | null | undefined

// Default — if undefined/null, replace with default
z.string().default('anonymous')      // string (always has value)
z.number().default(0)
z.array(z.string()).default([])

// Combining
z.string().optional().nullable()     // string | null | undefined
z.string().nullish().default('')     // string (default applied to null/undefined)
```

#### 2.7 Transform, Refine, SuperRefine

```typescript
// Transform — parse → modify → output
const Slug = z.string().transform(s => s.toLowerCase().replace(/\s+/g, '-'))
// Input: "Hello World" → Output: "hello-world"
// TypeScript type: string (output type)

// Multiple transforms chain
const Price = z.string()
  .transform(s => s.replace('$', ''))
  .transform(s => parseFloat(s))
  .transform(n => Math.round(n * 100) / 100)
// string → string → number → number

// Refine — simple boolean check (no custom error path)
z.string().refine(s => s.length > 0, 'Cannot be empty')

// Refine with object error
z.string().refine(s => s.length > 0, { message: 'Required' })

// SuperRefine — full control: add multiple issues, custom paths, ctx
const PasswordSchema = z.string().superRefine((val, ctx) => {
  if (val.length < 8) {
    ctx.addIssue({
      code: z.ZodIssueCode.too_small,
      minimum: 8,
      type: 'string',
      inclusive: true,
      message: 'Minimum 8 characters',
    })
  }
  if (!/[A-Z]/.test(val)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Need uppercase letter',
    })
  }
  if (!/[0-9]/.test(val)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Need a number',
    })
  }
})
// Produces 3 separate error issues, one per violation
```

#### 2.8 Effects, Pipe, Brand, Catch

```typescript
// Pipe (Zod v4) — sequential processing
z.string().pipe(z.number())
// Parse as string first, then validate as number

// Brand — nominal typing (prevents accidental assignment)
type UserId = z.BRAND<'UserId'>
const UserIdSchema = z.string().brand<'UserId'>()
// const id: z.infer<typeof UserIdSchema> = 'abc-123'
// const name: string = id          // ❌ Type error — brand mismatch

// Catch — if parse fails, use fallback instead of throwing
z.string().catch('fallback')
z.number().catch(0)
z.object({ id: z.string().catch('unknown') })

// Readonly — mark all fields as readonly
z.object({ name: z.string() }).readonly()
```

#### 2.9 safeParse vs parse

```typescript
// parse — throws on invalid
const user = User.parse(input)
// ZodError thrown if invalid

// safeParse — returns result object (PREFERRED in production)
const result = User.safeParse(input)
if (result.success) {
  // result.data is typed as User
  console.log(result.data.name)
} else {
  // result.error is ZodError
  console.log(result.error.flatten())
}

// async versions
const result = await schema.safeParseAsync(input)
const data = await schema.parseAsync(input)

// parse with path — parse specific subpath
schema.parse(input, { path: ['address', 'city'] })
```

```
┌─────────────────────────────────────────────┐
│          safeParse Flow (Production)         │
│                                               │
│   Input → Schema.safeParse(input)             │
│              │                                │
│              ▼                                │
│        Is valid?                              │
│        │         │                            │
│       YES       NO                            │
│        ▼         ▼                            │
│   result.success result.success = false       │
│   = true         │                            │
│   result.data    result.error                 │
│   (typed)        result.error.issues[]        │
│                  result.error.flatten()       │
│                  result.error.format()         │
│                                               │
│   "parse() for tests, safeParse() for prod"   │
└─────────────────────────────────────────────┘
```

---

### 3. Valibot

#### 3.1 Primitives & Pipe

Valibot uses a **pipe** pattern: base schema → array of validations/transforms, executed left→right.

```typescript
import {
  string, number, boolean, bigint, null_, undefined_,
  optional, nullable, nullish, default as vDefault,
  pipe, minValue, maxValue, minLength, maxLength,
  email, url, regex, uuid, integer, picklist,
  object, array, tuple, record, union, variant, intersect,
  transform, fallback, custom, check,
  toTrimmed, toLowerCase,
  parse, safeParse, flatten,
} from 'valibot'

// Primitives
string()              // string
number()              // number
boolean()             // boolean
bigint()              // bigint
null_()               // null  (underscore to avoid JS keyword)
undefined_()          // undefined

// Pipe — sequential validation
const EmailSchema = pipe(
  string(),
  toTrimmed(),
  toLowerCase(),
  email('Invalid email format'),
)

const AgeSchema = pipe(
  number(),
  integer(),
  minValue(0, 'Must be positive'),
  maxValue(150, 'Suspicious age'),
)

const UsernameSchema = pipe(
  string(),
  minLength(3),
  maxLength(50),
  regex(/^[a-zA-Z0-9_]+$/, 'Only letters, numbers, underscores'),
)
```

#### 3.2 Object, Array, Union

```typescript
// Object
const UserSchema = object({
  name: pipe(string(), minLength(1)),
  email: pipe(string(), email()),
  age: pipe(number(), integer(), minValue(0)),
  role: picklist(['admin', 'user', 'guest']),
})

// Array
const TagsSchema = array(pipe(string(), minLength(1)))
const NonEmptyTags = array(pipe(string()), [minLength(1)])

// Union — two or more schemas
const IdSchema = union([string(), number()])

// Variant (discriminated union in Valibot) — **preferred for perf**
const ApiResponse = variant('status', [
  object({ status: 'success', data: unknown() }),
  object({ status: 'error', message: string() }),
])

// Intersect
const FullSchema = intersect([
  object({ name: string() }),
  object({ age: number() }),
])

// Tuple
const Point = tuple([number(), number(), number()])

// Record
const Scores = record(string(), number())
```

#### 3.3 Optional, Nullable, Default, Fallback

```typescript
import { optional, nullable, nullish, default as vDefault, fallback } from 'valibot'

// Optional — allow undefined
optional(string())

// Nullable — allow null
nullable(string())

// Nullish — allow null or undefined
nullish(string())

// Default — replace undefined with value
vDefault(string(), 'anonymous')

// Fallback — if INVALID, use fallback (Zod's catch equivalent)
fallback(number(), 0)
fallback(pipe(string(), email()), 'default@email.com')

// Combining
vDefault(nullish(string()), 'n/a')
```

#### 3.4 Transform, Custom, Async

```typescript
import { transform, custom, checkAsync, pipeAsync } from 'valibot'

// Transform
const SlugSchema = pipe(
  string(),
  transform(input => input.toLowerCase().replace(/\s+/g, '-')),
)

const PriceSchema = pipe(
  string(),
  transform(input => input.replace('$', '')),
  transform(input => parseFloat(input)),
)

// Custom validation
const EvenNumber = pipe(
  number(),
  custom(input => input % 2 === 0, 'Must be even'),
)

// Async validation (pipeAsync)
const UniqueEmailSchema = pipeAsync(
  string(),
  email(),
  checkAsync(async (email) => {
    const exists = await db.user.findUnique({ where: { email } })
    return !exists
  }, 'Email already taken'),
)
```

#### 3.5 toTrimmed, toLowerCase, toUpperCase

```typescript
import { toTrimmed, toLowerCase, toUpperCase } from 'valibot'

// Auto-sanitize user input
const SanitizedString = pipe(
  string(),
  toTrimmed(),
  toLowerCase(),
)

// Good for emails, usernames, slugs
const EmailInput = pipe(string(), toTrimmed(), toLowerCase(), email())
```

---

### 4. Advanced Schema Patterns

#### 4.1 Recursive Schemas (Zod lazy / Valibot lazy)

```typescript
// Zod — recursive with lazy
interface TreeNode {
  value: string
  children: TreeNode[]
}
const TreeNodeSchema: z.ZodType<TreeNode> = z.object({
  value: z.string(),
  children: z.lazy(() => TreeNodeSchema.array()),
})

// Valibot — recursive with lazy
import { lazy } from 'valibot'
const TreeNodeSchema: any = object({
  value: string(),
  children: array(lazy(() => TreeNodeSchema)),
})

// JSON recursive type
type JSONValue = string | number | boolean | null | JSONValue[] | { [key: string]: JSONValue }
const JSONSchema: z.ZodType<JSONValue> = z.lazy(() =>
  z.union([
    z.string(),
    z.number(),
    z.boolean(),
    z.null(),
    z.array(JSONSchema),
    z.record(JSONSchema),
  ])
)
```

#### 4.2 Conditional Schemas

```typescript
// Conditional validation based on field value
const PaymentSchema = z.discriminatedUnion('method', [
  z.object({
    method: z.literal('credit_card'),
    cardNumber: z.string().regex(/^\d{16}$/),
    cvv: z.string().regex(/^\d{3}$/),
    expiry: z.string().regex(/^\d{2}\/\d{2}$/),
  }),
  z.object({
    method: z.literal('bank_transfer'),
    accountNumber: z.string().regex(/^\d{10}$/),
    bankCode: z.string().length(3),
  }),
  z.object({
    method: z.literal('wallet'),
    walletId: z.string().uuid(),
  }),
])

// Conditional with superRefine (cross-field)
const SignupSchema = z.object({
  password: z.string().min(8),
  confirmPassword: z.string(),
  acceptTerms: z.boolean(),
}).superRefine((data, ctx) => {
  if (data.password !== data.confirmPassword) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Passwords must match',
      path: ['confirmPassword'],
    })
  }
  if (!data.acceptTerms) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Must accept terms',
      path: ['acceptTerms'],
    })
  }
})
```

#### 4.3 Branded Types

```typescript
// Zod Brand — nominal typing
type UserId = z.BRAND<'UserId'>
type OrderId = z.BRAND<'OrderId'>

const UserIdSchema = z.string().brand<'UserId'>()
const OrderIdSchema = z.string().brand<'OrderId'>()

function getUser(id: z.infer<typeof UserIdSchema>) {}
function getOrder(id: z.infer<typeof OrderIdSchema>) {}

const uid = UserIdSchema.parse('abc')
const oid = OrderIdSchema.parse('xyz')

getUser(uid)      // ✅
getUser(oid)      // ❌ Type error — brand mismatch
getOrder(oid)     // ✅

// Valibot — branded type via transform
import { brand } from 'valibot'
const UserIdSchema = pipe(
  string([uuid()]),
  brand('UserId'),
)
type UserId = Output<typeof UserIdSchema>  // string & Brand<'UserId'>
```

#### 4.4 Preprocess, Coerce

```typescript
// Preprocess — transform input BEFORE validation
const NumberFromString = z.preprocess(
  (val) => (typeof val === 'string' ? parseFloat(val) : val),
  z.number()
)
NumberFromString.parse('42')   // → 42
NumberFromString.parse(42)     // → 42

// Coerce — automatic type coercion (Zod v4)
z.coerce.string()              // any → string
z.coerce.number()              // any → number
z.coerce.boolean()             // '0'/'false' → false, other → true
z.coerce.date()                // string/number → Date

// Common pattern: form inputs are always strings
const FormNumber = z.coerce.number()
FormNumber.parse('123')        // → 123
FormNumber.parse('')           // → Error

// Valibot equivalent — transform
import { transform, number, pipe, string } from 'valibot'
const NumberFromForm = pipe(
  string(),
  transform(val => parseFloat(val)),
  number(),
)
```

#### 4.5 Pick, Omit, Partial, Required, Merge

```typescript
// Base schema
const User = z.object({
  id: z.string().uuid(),
  name: z.string(),
  email: z.string().email(),
  password: z.string().min(8),
  role: z.enum(['admin', 'user']),
  createdAt: z.date(),
})

// Pick — subset of keys
const PublicUser = User.pick({ id: true, name: true, email: true, role: true })

// Omit — remove sensitive fields
const SafeUser = User.omit({ password: true })

// Partial — all fields optional
const UpdateUser = User.partial()

// Required — all fields required (for turning optional to required)
const CompleteUser = User.required()

// Partial nested
const PartialUser = User.partial({
  email: true,        // email becomes optional
  name: true,         // name becomes optional
})

// Merge — combine two object schemas
const Timestamps = z.object({ createdAt: z.date(), updatedAt: z.date() })
const UserWithTimestamps = User.merge(Timestamps)
// Equivalent to: User.and(Timestamps)

// Deep partial (partial applied recursively)
const DeepPartial = User.deepPartial()
```

#### 4.6 Literal Defaults

```typescript
// Default values for complex objects
const DefaultConfig = z.object({
  theme: z.enum(['light', 'dark']).default('light'),
  locale: z.string().default('id-ID'),
  pageSize: z.number().int().min(10).max(100).default(25),
  notifications: z.boolean().default(true),
  filters: z.object({
    search: z.string().default(''),
    category: z.string().optional(),
    sort: z.enum(['asc', 'desc']).default('desc'),
  }).default({}),
}).default({})

const config = DefaultConfig.parse(undefined)
// All defaults applied recursively
```

---

### 5. Integration with React Hook Form

#### 5.1 zodResolver vs valibotResolver

```typescript
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { valibotResolver } from '@hookform/resolvers/valibot'
import { z } from 'zod'
import { object, string, pipe, email, minLength, number, integer, minValue } from 'valibot'

// --- Zod Resolver ---
const LoginSchema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(6, 'Min 6 characters'),
})

type LoginForm = z.infer<typeof LoginSchema>

function LoginForm() {
  const {
    register, handleSubmit, formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(LoginSchema),
  })

  return (
    <form onSubmit={handleSubmit(data => api.login(data))}>
      <input {...register('email')} />
      {errors.email && <span>{errors.email.message}</span>}
      <input type="password" {...register('password')} />
      {errors.password && <span>{errors.password.message}</span>}
      <button type="submit">Login</button>
    </form>
  )
}

// --- Valibot Resolver (bundle-friendly) ---
const LoginSchemaV = object({
  email: pipe(string(), email('Invalid email')),
  password: pipe(string(), minLength(6, 'Min 6 characters')),
})

function LoginFormV() {
  const { register, handleSubmit, formState: { errors } } = useForm({
    resolver: valibotResolver(LoginSchemaV),
  })
  // ... same as above
}
```

#### 5.2 Nested Form Validation

```typescript
const AddressSchema = z.object({
  street: z.string().min(1),
  city: z.string().min(1),
  state: z.string().min(2).max(2),
  zip: z.string().regex(/^\d{5}$/),
})

const ProfileSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
  address: AddressSchema,
  billingAddress: AddressSchema.optional(),
})

type Profile = z.infer<typeof ProfileSchema>

function ProfileForm() {
  const { register, handleSubmit, formState: { errors } } = useForm<Profile>({
    resolver: zodResolver(ProfileSchema),
  })

  return (
    <form onSubmit={handleSubmit(d => api.save(d))}>
      <input {...register('name')} />
      <input {...register('address.street')} />
      {errors.address?.street && <span>{errors.address.street.message}</span>}
      <input {...register('address.city')} />
      <input {...register('address.state')} />
      {errors.billingAddress?.zip && <span>{errors.billingAddress.zip.message}</span>}
    </form>
  )
}
```

#### 5.3 Field Arrays

```typescript
import { useFieldArray } from 'react-hook-form'

const InvoiceSchema = z.object({
  customer: z.string().min(1),
  items: z.array(z.object({
    name: z.string().min(1),
    quantity: z.coerce.number().int().min(1),
    price: z.coerce.number().min(0),
  })).min(1, 'At least one item'),
})

type Invoice = z.infer<typeof InvoiceSchema>

function InvoiceForm() {
  const { control, register, handleSubmit, formState: { errors } } = useForm<Invoice>({
    resolver: zodResolver(InvoiceSchema),
    defaultValues: { customer: '', items: [{ name: '', quantity: 1, price: 0 }] },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'items' })

  return (
    <form onSubmit={handleSubmit(d => api.createInvoice(d))}>
      <input {...register('customer')} />
      {fields.map((field, i) => (
        <div key={field.id}>
          <input {...register(`items.${i}.name`)} />
          <input type="number" {...register(`items.${i}.quantity`)} />
          <input type="number" step="0.01" {...register(`items.${i}.price`)} />
          <button type="button" onClick={() => remove(i)}>Remove</button>
        </div>
      ))}
      <button type="button" onClick={() => append({ name: '', quantity: 1, price: 0 })}>
        Add Item
      </button>
    </form>
  )
}
```

#### 5.4 Conditional Validation (Cross-Field)

```typescript
const BookingSchema = z.object({
  hasCompanion: z.boolean(),
  companionName: z.string().optional(),
  companionEmail: z.string().email().optional(),
}).superRefine((data, ctx) => {
  if (data.hasCompanion && !data.companionName) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Companion name required',
      path: ['companionName'],
    })
  }
  if (data.hasCompanion && !data.companionEmail) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Companion email required',
      path: ['companionEmail'],
    })
  }
})

// In component — use watch for reactively conditional fields
function BookingForm() {
  const { register, handleSubmit, watch, formState: { errors } } = useForm({
    resolver: zodResolver(BookingSchema),
    defaultValues: { hasCompanion: false },
  })

  const hasCompanion = watch('hasCompanion')

  return (
    <form>
      <label>
        <input type="checkbox" {...register('hasCompanion')} />
        Bringing a companion?
      </label>
      {hasCompanion && (
        <>
          <input {...register('companionName')} placeholder="Name" />
          {errors.companionName && <span>{errors.companionName.message}</span>}
          <input {...register('companionEmail')} placeholder="Email" />
        </>
      )}
    </form>
  )
}
```

#### 5.5 Async Validation

```typescript
const RegisterSchema = z.object({
  username: z.string().min(3).superRefine(async (val, ctx) => {
    const taken = await checkUsernameTaken(val)
    if (taken) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Username already taken',
      })
    }
  }),
  email: z.string().email().superRefine(async (val, ctx) => {
    const exists = await db.user.findUnique({ where: { email: val } })
    if (exists) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Email already registered',
      })
    }
  }),
})

function RegisterForm() {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(RegisterSchema),
  })

  return (
    <form onSubmit={handleSubmit(d => api.register(d))}>
      <input {...register('username')} />
      {errors.username && <span>{errors.username.message}</span>}
      <input {...register('email')} />
      {errors.email && <span>{errors.email.message}</span>}
      <button type="submit" disabled={isSubmitting}>Register</button>
    </form>
  )
}
```

---

### 6. API Validation with Zod

#### 6.1 Request Body Validation

```typescript
// Generic validation middleware
import { z, ZodError } from 'zod'
import { Request, Response, NextFunction } from 'express'

function validate<T>(schema: z.ZodType<T>) {
  return (req: Request, res: Response, next: NextFunction) => {
    const result = schema.safeParse(req.body)
    if (!result.success) {
      return res.status(400).json({
        error: 'Validation failed',
        details: result.error.flatten(),
      })
    }
    req.body = result.data as T
    next()
  }
}

// Usage
const CreateUserSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
  age: z.number().int().min(0).optional(),
})

router.post('/users', validate(CreateUserSchema), (req, res) => {
  // req.body is now safely typed
  const user = await db.user.create({ data: req.body })
  res.json(user)
})
```

#### 6.2 Query Params & Path Params

```typescript
// Query params validation
const ListUsersSchema = z.object({
  page: z.coerce.number().int().positive().default(1),
  limit: z.coerce.number().int().min(1).max(100).default(20),
  search: z.string().optional(),
  sortBy: z.enum(['name', 'email', 'createdAt']).default('createdAt'),
  order: z.enum(['asc', 'desc']).default('desc'),
})

function validateQuery<T>(schema: z.ZodType<T>) {
  return (req: Request, res: Response, next: NextFunction) => {
    const result = schema.safeParse(req.query)
    if (!result.success) {
      return res.status(400).json({ error: 'Invalid query params', details: result.error.flatten() })
    }
    req.query = result.data as any
    next()
  }
}

app.get('/users', validateQuery(ListUsersSchema), listUsersHandler)

// Path params validation
const UserIdSchema = z.object({
  id: z.string().uuid(),
})

app.get('/users/:id', validateQuery(UserIdSchema), (req, res) => {
  // req.params.id is validated UUID
})
```

#### 6.3 Response Validation

```typescript
// Validate API responses — catch bugs at boundaries
const UserResponseSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  email: z.string().email(),
  role: z.enum(['admin', 'user']),
  createdAt: z.string().datetime(),
})

async function handler(req: Request, res: Response) {
  const user = await db.user.findUnique({ where: { id: req.params.id } })
  // Validate response before sending
  const result = UserResponseSchema.safeParse(user)
  if (!result.success) {
    console.error('Response validation failed:', result.error.issues)
    return res.status(500).json({ error: 'Internal server error' })
  }
  res.json(result.data)
}
```

#### 6.4 zod-to-json-schema

```typescript
import { zodToJsonSchema } from 'zod-to-json-schema'

const UserSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(100),
  email: z.string().email(),
  role: z.enum(['admin', 'user']),
})

// Generate OpenAPI-compatible JSON Schema
const jsonSchema = zodToJsonSchema(UserSchema, 'User')
// {
//   $schema: 'http://json-schema.org/draft-07/schema#',
//   $ref: '#/definitions/User',
//   definitions: {
//     User: {
//       type: 'object',
//       properties: { id: { type: 'string', format: 'uuid' }, ... },
//       required: ['id', 'name', 'email', 'role'],
//     }
//   }
// }

// Use with OpenAPI/Swagger
app.openapi({
  method: 'post',
  path: '/users',
  request: { body: { content: { 'application/json': { schema: jsonSchema } } } },
  responses: { 201: { description: 'Created' } },
}, createUserHandler)
```

#### 6.5 Fastify Schema Validation

```typescript
import Fastify from 'fastify'

const app = Fastify()

const CreateUserBody = z.object({
  name: z.string().min(1),
  email: z.string().email(),
})

app.post('/users', {
  schema: {
    body: zodToJsonSchema(CreateUserBody),
  },
}, async (req, reply) => {
  // Fastify auto-validates against JSON Schema
  const { name, email } = req.body as z.infer<typeof CreateUserBody>
  const user = await db.user.create({ data: { name, email } })
  return user
})
```

#### 6.6 Nest.js ValidationPipe with Zod

```typescript
import { PipeTransform, Injectable, ArgumentMetadata, BadRequestException } from '@nestjs/common'
import { z, ZodError } from 'zod'

@Injectable()
export class ZodValidationPipe implements PipeTransform {
  constructor(private schema: z.ZodType) {}

  transform(value: unknown, metadata: ArgumentMetadata) {
    const result = this.schema.safeParse(value)
    if (!result.success) {
      throw new BadRequestException({
        message: 'Validation failed',
        errors: result.error.flatten(),
      })
    }
    return result.data
  }
}

// Usage in controller
@Controller('users')
class UsersController {
  @Post()
  create(
    @Body(new ZodValidationPipe(CreateUserSchema))
    body: z.infer<typeof CreateUserSchema>,
  ) {
    return this.usersService.create(body)
  }

  @Get(':id')
  findOne(
    @Param('id', new ZodValidationPipe(z.string().uuid()))
    id: string,
  ) {
    return this.usersService.findOne(id)
  }
}
```

---

### 7. Environment Variables Validation

#### 7.1 Zod Environment Schema

```typescript
import { z } from 'zod'

const EnvSchema = z.object({
  // Required
  NODE_ENV: z.enum(['development', 'production', 'test']),
  DATABASE_URL: z.string().url(),
  JWT_SECRET: z.string().min(32),

  // Optional with defaults
  PORT: z.coerce.number().int().positive().default(3000),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
  CORS_ORIGIN: z.string().url().default('http://localhost:5173'),

  // Optional
  REDIS_URL: z.string().url().optional(),
  SENTRY_DSN: z.string().url().optional(),

  // Boolean coercion
  ENABLE_SWAGGER: z.coerce.boolean().default(false),
  DEBUG_MODE: z.coerce.boolean().default(false),

  // Number coercion
  DB_POOL_MIN: z.coerce.number().int().min(0).default(2),
  DB_POOL_MAX: z.coerce.number().int().min(1).max(50).default(10),
  API_TIMEOUT_MS: z.coerce.number().int().positive().default(5000),
})

// Type-safe env access
type Env = z.infer<typeof EnvSchema>

// Invalidate Node process.env cache on validation failure
let envCache: Env | null = null

export function getEnv(): Env {
  if (!envCache) {
    const result = EnvSchema.safeParse(process.env)
    if (!result.success) {
      console.error('❌ Invalid environment variables:')
      const formatted = result.error.flatten()
      for (const [key, errors] of Object.entries(formatted.fieldErrors)) {
        console.error(`  ${key}: ${errors.join(', ')}`)
      }
      process.exit(1)  // Fail fast — don't run with misconfigured env
    }
    envCache = result.data
  }
  return envCache
}

// Usage
const env = getEnv()
console.log(`Starting server on port ${env.PORT}`)
```

#### 7.2 With dotenv / Loaded File

```typescript
import { config } from 'dotenv'
import { resolve } from 'path'

// Load .env file based on NODE_ENV
config({ path: resolve(process.cwd(), `.env.${process.env.NODE_ENV || 'development'}`) })
config({ path: resolve(process.cwd(), '.env') })

// Then validate
const env = getEnv()

// Or with explicit load
function loadAndValidate(configDir: string) {
  const result = config({ path: resolve(configDir, '.env') })
  const parsed = EnvSchema.safeParse({ ...process.env, ...result.parsed })
  if (!parsed.success) {
    throw new Error(`Invalid .env: ${JSON.stringify(parsed.error.flatten())}`)
  }
  return parsed.data
}
```

#### 7.3 Valibot Environment Schema

```typescript
import { object, string, pipe, email, minLength, url, picklist, transform, fallback } from 'valibot'
import { parse } from 'valibot'
import { config } from 'dotenv'

const EnvSchema = object({
  NODE_ENV: pipe(string(), picklist(['development', 'production', 'test'])),
  DATABASE_URL: pipe(string(), url()),
  JWT_SECRET: pipe(string(), minLength(32)),
  PORT: pipe(
    string(),
    transform(v => parseInt(v, 10)),
    fallback(3000),
  ),
  LOG_LEVEL: pipe(
    string(),
    picklist(['debug', 'info', 'warn', 'error']),
    fallback('info'),
  ),
})

export function loadEnv() {
  config()
  const result = parse(EnvSchema, process.env, { abortEarly: false })
  // If abortEarly: false, collects all errors
  return result
}
```

---

### 8. Error Handling

#### 8.1 Custom Error Messages (i18n)

```typescript
// Zod — messages directly in schema
const UserSchema = z.object({
  name: z.string().min(1, { message: 'Nama wajib diisi' }),
  email: z.string().email({ message: 'Format email tidak valid' }),
  age: z.number().int().positive({ message: 'Usia harus positif' }),
})

// With i18n key system
type Messages = Record<string, string>
const messages: Messages = {
  'name.required': 'Nama wajib diisi',
  'email.invalid': 'Format email tidak valid',
  'age.positive': 'Usia harus positif',
}

const UserSchemaI18n = z.object({
  name: z.string().min(1, messages['name.required']),
  email: z.string().email(messages['email.invalid']),
  age: z.number().int().positive(messages['age.positive']),
})

// Valibot — messages as second argument
import { email, minLength, custom } from 'valibot'
const EmailSchema = pipe(
  string(),
  email('Format email tidak valid'),
  custom(v => !v.includes('+'), 'Email dengan plus tidak diizinkan'),
)
```

#### 8.2 Error Formatting

```typescript
const schema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
  tags: z.array(z.string().min(1)).min(1),
  address: z.object({
    street: z.string().min(1),
    zip: z.string().regex(/^\d{5}$/),
  }),
})

const result = schema.safeParse({
  name: '',
  email: 'bad',
  tags: [],
  address: { street: '', zip: 'abc' },
})

if (!result.success) {
  // Option 1: Flatten → simple key-value errors
  const flat = result.error.flatten()
  // flat.fieldErrors → { name: ['Required'], email: ['Invalid email'], ... }
  // flat.formErrors → [] (form-level errors)

  // Option 2: Format → nested structure matching schema
  const formatted = result.error.format()
  // formatted.name._errors → ['Required']
  // formatted.email._errors → ['Invalid email']
  // formatted.address.street._errors → ['Required']

  // Option 3: Raw issues — access individual errors with paths
  for (const issue of result.error.issues) {
    console.log({
      path: issue.path.join('.'),      // 'address.street'
      message: issue.message,           // 'Required'
      code: issue.code,                 // 'too_small'
      // ... other metadata
    })
  }
}

// Custom formatter for consistent API response
function formatZodError(error: z.ZodError) {
  return {
    errors: error.issues.map(issue => ({
      field: issue.path.join('.'),
      message: issue.message,
      code: issue.code,
    })),
    message: 'Validation failed',
  }
}
```

#### 8.3 Error Map Customization

```typescript
// Zod — global error map override
import { z } from 'zod'

const customErrorMap: z.ZodErrorMap = (issue, ctx) => {
  switch (issue.code) {
    case z.ZodIssueCode.invalid_type:
      if (issue.expected === 'string') return { message: 'Harus berupa teks' }
      if (issue.expected === 'number') return { message: 'Harus berupa angka' }
      return { message: `Tipe tidak valid: diharapkan ${issue.expected}` }

    case z.ZodIssueCode.too_small:
      if (issue.type === 'string') return { message: `Minimal ${issue.minimum} karakter` }
      if (issue.type === 'array') return { message: `Minimal ${issue.minimum} item` }
      if (issue.type === 'number') return { message: `Minimal ${issue.minimum}` }
      return { message: ctx.defaultError }

    case z.ZodIssueCode.custom:
      return { message: issue.message || 'Input tidak valid' }

    default:
      return { message: ctx.defaultError }
  }
}

z.setErrorMap(customErrorMap)
```

#### 8.4 Error Handling Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│                  ERROR HANDLING PIPELINE                      │
│                                                               │
│   Schema.safeParse(input)                                     │
│       │                                                       │
│       ▼                                                       │
│   ZodError / Valibot Errors                                   │
│       │                                                       │
│       ▼                                                       │
│   ┌─────────────────┐        ┌─────────────────┐             │
│   │ result.error    │        │ result.error    │             │
│   │   .issues[]     │  or    │   .flatten()    │  or         │
│   │ Raw issue list  │        │ Simple key-val  │             │
│   └─────────────────┘        └─────────────────┘             │
│       │                                                       │
│       ▼                                                       │
│   ┌─────────────────────────────────────────────────────────┐ │
│   │  FORMAT FOR CONSUMER                                    │ │
│   │                                                         │ │
│   │  API Response:  { errors: [{field, message, code}],    │ │
│   │                   message: "Validation failed" }         │ │
│   │                                                         │ │
│   │  React Hook Form: errors.field.message (auto-mapped)   │ │
│   │                                                         │ │
│   │  Console/Log:   [Validation] field "email": invalid     │ │
│   └─────────────────────────────────────────────────────────┘ │
│       │                                                       │
│       ▼                                                       │
│   Return error response or set form errors                    │
└──────────────────────────────────────────────────────────────┘
```

---

### 9. Integration with tRPC

#### 9.1 Zod as First-Class in tRPC

```typescript
import { initTRPC } from '@trpc/server'
import { z } from 'zod'

const t = initTRPC.create()

const PostsRouter = t.router({
  // Input validated with Zod automatically
  list: t.procedure
    .input(z.object({
      limit: z.number().int().positive().default(10),
      cursor: z.string().optional(),
    }))
    .query(({ input }) => {
      // input is typed: { limit: number; cursor?: string }
      return db.post.findMany({ take: input.limit })
    }),

  // Output validated with Zod
  create: t.procedure
    .input(z.object({
      title: z.string().min(1).max(200),
      content: z.string().min(1),
      tags: z.array(z.string()).optional(),
    }))
    .output(z.object({
      id: z.string().uuid(),
      title: z.string(),
      createdAt: z.date(),
    }))
    .mutation(({ input }) => {
      return db.post.create({ data: input })
    }),

  // Complex input with discriminated union
  search: t.procedure
    .input(z.discriminatedUnion('type', [
      z.object({ type: z.literal('user'), userId: z.string().uuid() }),
      z.object({ type: z.literal('tag'), tag: z.string() }),
      z.object({ type: z.literal('all') }),
    ]))
    .query(({ input }) => {
      switch (input.type) {
        case 'user': return db.post.findByUser(input.userId)
        case 'tag': return db.post.findByTag(input.tag)
        case 'all': return db.post.findAll()
      }
    }),
})

// Type inference for client
type PostsRouter = typeof PostsRouter
```

#### 9.2 Input & Output Validation

```typescript
// Separate input/output schemas for complex cases
const CreatePostInput = z.object({
  title: z.string().min(1).max(200),
  content: z.string().min(1),
  publishAt: z.date().optional(),
})

const PostResponse = z.object({
  id: z.string().uuid(),
  title: z.string(),
  slug: z.string(),
  content: z.string(),
  author: z.object({
    id: z.string().uuid(),
    name: z.string(),
  }),
  createdAt: z.date(),
  publishedAt: z.date().nullable(),
})

const postCreate = t.procedure
  .input(CreatePostInput)
  .output(PostResponse)
  .mutation(async ({ input, ctx }) => {
    const post = await db.post.create({
      data: {
        ...input,
        authorId: ctx.user.id,
        slug: input.title.toLowerCase().replace(/\s+/g, '-'),
      },
    })
    return PostResponse.parse(post)  // double-check output
  })
```

#### 9.3 Shared Schema Package

```typescript
// packages/shared/src/schemas/user.ts
import { z } from 'zod'

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string().min(1).max(100),
  role: z.enum(['admin', 'user']),
})

export const CreateUserSchema = UserSchema.omit({ id: true })
export const UpdateUserSchema = UserSchema.partial().omit({ id: true })
export const UserListSchema = z.object({
  users: z.array(UserSchema),
  total: z.number().int(),
  page: z.number().int(),
})

export type User = z.infer<typeof UserSchema>
export type CreateUser = z.infer<typeof CreateUserSchema>

// Used in both:
// - Server: tRPC router input/output
// - Client: tRPC client receives typed responses
// - Forms: zodResolver(UserSchema)
// - API docs: zodToJsonSchema(UserSchema)
```

---

### 10. Performance

#### 10.1 Schema Compilation

```
┌──────────────────────────────────────────────────────────┐
│                SCHEMA COMPILATION FLOW                    │
│                                                           │
│   Schema Definition (module load time)                    │
│       │                                                   │
│       ▼                                                   │
│   Compilation Phase (Zod fast mode)                       │
│       │                                                   │
│       ├── Zod v4: Pre-compiled validator functions        │
│       │   - Discriminated unions → switch statements       │
│       │   - Simple checks → inlined                       │
│       │   - Cached after first parse                      │
│       │                                                   │
│       └── Valibot: Tree-shakeable pipeline                │
│           - Only imports used validators                  │
│           - No global ZodError object                     │
│           - Pipe items compiled at schema creation        │
│                                                           │
│   Result: Cached validator function                       │
│       │                                                   │
│       ▼                                                   │
│   Runtime: Input → Validator → Typed output               │
└──────────────────────────────────────────────────────────┘
```

#### 10.2 Zod Fast Mode

```typescript
// Zod v4 — schemas are compiled lazily on first .parse()
// First call compiles, subsequent calls use cached validator

// For hot paths — pre-compile by parsing once at startup
const validator = z.object({
  name: z.string(),
  email: z.string().email(),
})

// "Warm up" the validator cache
validator.parse({ name: 'test', email: 'test@test.com' })

// Now subsequent parses are faster

// For discriminated unions — always prefer discriminatedUnion
// (compiles to switch statement) over union (sequential trial)
// ✅ Fast (O(1))
const FastResponse = z.discriminatedUnion('type', [
  z.object({ type: z.literal('a'), data: z.string() }),
  z.object({ type: z.literal('b'), data: z.number() }),
])

// ❌ Slow (O(n) — tries schemas sequentially)
const SlowResponse = z.union([
  z.object({ type: z.literal('a'), data: z.string() }),
  z.object({ type: z.literal('b'), data: z.number() }),
])
```

#### 10.3 Valibot Tree-Shaking

```typescript
// Valibot — only pay for what you use

// ✅ Tree-shakeable — imports only the validators used
import { object, string, pipe, email, minLength, number, integer, minValue } from 'valibot'

// ❌ Non-tree-shakeable — imports entire Valibot
import * as v from 'valibot'

// ✅ Bundle comparison:
// Import 3 validators: ~1.5 KB gzipped
// Import 10 validators: ~2.5 KB gzipped
// Import full Zod: ~10 KB gzipped

// For API-only (server doesn't care about bundle):
// Use Zod for better DX
// For client-side forms in bundle-sensitive apps:
// Use Valibot
```

#### 10.4 Lazy Compilation for Large Schemas

```typescript
// For very large schemas (>50 fields), split into smaller schemas

// ❌ Bad — huge monolithic schema (slow to compile + parse)
const HugeForm = z.object({
  // 100 fields...
})

// ✅ Good — compose smaller schemas
const PersonalInfo = z.object({ name: z.string(), email: z.string().email() })
const AddressInfo = z.object({ street: z.string(), city: z.string(), zip: z.string() })
const Preferences = z.object({ theme: z.enum(['light', 'dark']), notifications: z.boolean() })

const FullForm = z.object({
  ...PersonalInfo.shape,
  address: AddressInfo,
  preferences: Preferences,
})

// Even better — parse independently
result = PersonalInfo.safeParse(formData)  // quick parse, scoped errors
```

#### 10.5 Benchmarking

```typescript
// Simple benchmark harness
import { z } from 'zod'
import * as v from 'valibot'

const schema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email(),
  age: z.number().int().min(0).max(150),
})

const valibotSchema = v.object({
  name: v.pipe(v.string(), v.minLength(1), v.maxLength(100)),
  email: v.pipe(v.string(), v.email()),
  age: v.pipe(v.number(), v.integer(), v.minValue(0), v.maxValue(150)),
})

const validInput = { name: 'Alice', email: 'alice@test.com', age: 30 }

function benchmark(schema: any, runs = 10000) {
  const start = performance.now()
  for (let i = 0; i < runs; i++) {
    schema.safeParse(validInput)
  }
  return (performance.now() - start) / runs
}

// Results (approx, varies by runtime):
// Zod v4: ~0.005ms per parse (cached)
// Valibot: ~0.008ms per parse (tree-shaken)
// Perbedaan: negligible for human-scale operations (<1000/s)
```

---

### 11. Testing

#### 11.1 Testing Schema Behavior

```typescript
import { describe, it, expect } from 'vitest'
import { z } from 'zod'

const UserSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
  age: z.number().int().positive().optional(),
})

describe('UserSchema', () => {
  // ✅ Happy path
  it('validates a correct user object', () => {
    const result = UserSchema.safeParse({
      name: 'Alice',
      email: 'alice@test.com',
      age: 30,
    })
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.name).toBe('Alice')
    }
  })

  // ✅ Edge cases — empty values
  it('rejects empty name', () => {
    const result = UserSchema.safeParse({ name: '', email: 'a@b.com' })
    expect(result.success).toBe(false)
  })

  // ✅ Edge cases — missing optional
  it('accepts missing optional field', () => {
    const result = UserSchema.safeParse({ name: 'Bob', email: 'bob@test.com' })
    expect(result.success).toBe(true)
  })

  // ✅ Edge cases — wrong types
  it('rejects numeric email', () => {
    const result = UserSchema.safeParse({ name: 'X', email: 123 })
    expect(result.success).toBe(false)
  })

  // ✅ Edge cases — boundary values
  it('rejects age 0', () => {
    const result = UserSchema.safeParse({ name: 'X', email: 'a@b.com', age: 0 })
    expect(result.success).toBe(false)
  })

  // ✅ Transform behavior
  it('applies default for missing optional with default', () => {
    const WithDefault = z.object({
      name: z.string().default('anonymous'),
    })
    const result = WithDefault.safeParse({})
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.name).toBe('anonymous')
    }
  })

  // ✅ Discriminated union
  it('discriminates based on type field', () => {
    const Schema = z.discriminatedUnion('type', [
      z.object({ type: z.literal('a'), value: z.string() }),
      z.object({ type: z.literal('b'), value: z.number() }),
    ])

    expect(Schema.safeParse({ type: 'a', value: 'hello' }).success).toBe(true)
    expect(Schema.safeParse({ type: 'b', value: 42 }).success).toBe(true)
    expect(Schema.safeParse({ type: 'a', value: 42 }).success).toBe(false)
    expect(Schema.safeParse({ type: 'c' }).success).toBe(false)
  })
})
```

#### 11.2 Async Validation Testing

```typescript
import { describe, it, expect, vi } from 'vitest'
import { z } from 'zod'

describe('async validation', () => {
  it('validates async constraints', async () => {
    const checkEmail = vi.fn().mockResolvedValue(false)

    const RegisterSchema = z.object({
      email: z.string().email().superRefine(async (val, ctx) => {
        const taken = await checkEmail(val)
        if (taken) ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Taken' })
      }),
    })

    const result = await RegisterSchema.safeParseAsync({
      email: 'existing@test.com',
    })

    // Mock the check to return true (email exists)
    checkEmail.mockResolvedValue(true)
    const failResult = await RegisterSchema.safeParseAsync({
      email: 'existing@test.com',
    })

    expect(result.success).toBe(true)
    expect(failResult.success).toBe(false)
  })
})
```

#### 11.3 Type-Level Testing

```typescript
// Type-level testing — ensure inferred types match expectations
import { z } from 'zod'
import { expectTypeOf } from 'vitest'

const UserSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  email: z.string().email(),
  role: z.enum(['admin', 'user']),
})

// Type-level tests
type User = z.infer<typeof UserSchema>

expectTypeOf<User>().toEqualTypeOf<{
  id: string
  name: string
  email: string
  role: 'admin' | 'user'
}>()

// Brand type test
const UserIdSchema = z.string().brand<'UserId'>()
type UserId = z.infer<typeof UserIdSchema>

// ✅ This would be a type error if not branded:
// const id: UserId = 'abc' as string — should fail with brand

// Transform type test
const SlugSchema = z.string().transform(s => s.toLowerCase())
type Slug = z.infer<typeof SlugSchema>
// Slug should be string (output type of transform)

expectTypeOf<Slug>().toBeString()
```

#### 11.4 Error Messages Testing

```typescript
describe('error messages', () => {
  const schema = z.object({
    email: z.string().email('Custom error: invalid email'),
  })

  it('returns custom error messages', () => {
    const result = schema.safeParse({ email: 'bad' })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].message).toBe('Custom error: invalid email')
    }
  })

  it('flattens errors correctly', () => {
    const result = schema.safeParse({ email: '' })
    expect(result.success).toBe(false)
    if (!result.success) {
      const flat = result.error.flatten()
      expect(flat.fieldErrors.email).toBeDefined()
      expect(flat.fieldErrors.email[0]).toBeTruthy()
    }
  })

  it('issues have correct paths', () => {
    const Nested = z.object({
      address: z.object({ zip: z.string().length(5) }),
    })
    const result = Nested.safeParse({ address: { zip: '123' } })
    if (!result.success) {
      expect(result.error.issues[0].path).toEqual(['address', 'zip'])
    }
  })
})
```

---

### 12. File Convention

#### 12.1 Schema File Organization

```
src/
├── schemas/                  # All Zod/Valibot schemas
│   ├── index.ts              # Re-exports all schemas
│   ├── user.schema.ts        # User-related schemas
│   ├── auth.schema.ts        # Login, register, reset password
│   ├── post.schema.ts        # Blog/forum post schemas
│   ├── payment.schema.ts     # Payment & transaction schemas
│   ├── env.schema.ts         # Environment variables
│   ├── api/                  # API request/response schemas
│   │   ├── request.ts        # Query params, body validators
│   │   ├── response.ts       # Response shape validators
│   │   └── common.ts         # Shared API schemas (pagination, etc.)
│   └── forms/                # Form-specific schemas
│       ├── login.ts
│       ├── register.ts
│       ├── profile.ts
│       └── checkout.ts
```

#### 12.2 Naming Convention

```typescript
// Schema naming: PascalCase + Schema suffix
export const UserSchema = z.object({ ... })
export const CreateUserSchema = UserSchema.omit({ id: true })
export const UpdateUserSchema = UserSchema.partial().omit({ id: true, email: true })
export const UserListSchema = z.object({ users: z.array(UserSchema), total: z.number() })

// Type naming: infer from schema, PascalCase (no prefix/suffix)
export type User = z.infer<typeof UserSchema>
export type CreateUser = z.infer<typeof CreateUserSchema>

// File naming: kebab-case
// user.schema.ts — contains UserSchema, CreateUserSchema, User type
// auth.schema.ts — contains LoginSchema, RegisterSchema

// API schemas: <entity>.schema.ts or api/<verb>.ts
// api/request.ts — PaginationSchema, SortingSchema, FilterSchema
// api/response.ts — ErrorResponseSchema, SuccessResponseSchema
```

#### 12.3 Shared Package Structure (Monorepo)

```
packages/
├── shared/
│   ├── src/
│   │   ├── schemas/
│   │   │   ├── user.schema.ts
│   │   │   ├── post.schema.ts
│   │   │   └── index.ts
│   │   └── index.ts
│   └── package.json           # depends on zod

├── server/                    # depends on shared
├── web/                       # depends on shared
└── mobile/                    # depends on shared (if using Zod)
```

---

### 13. Anti-Patterns

#### 13.1 Throwing Instead of safeParse

```typescript
// ❌ BAD — parse() throws on invalid input
function createUser(req: Request) {
  try {
    const data = UserSchema.parse(req.body)
    return db.user.create({ data })
  } catch (err) {
    if (err instanceof z.ZodError) {
      return res.status(400).json(err.flatten())
    }
    throw err
  }
}

// ✅ GOOD — safeParse returns result type
function createUser(req: Request) {
  const result = UserSchema.safeParse(req.body)
  if (!result.success) {
    return res.status(400).json({ errors: result.error.flatten() })
  }
  return db.user.create({ data: result.data })
}
// Kenapa? safeParse tidak throw, flow lebih jelas, TypeScript narrows result type
```

#### 13.2 Duplicate Validation (Client + Server)

```typescript
// ❌ BAD — separate schemas
// client/schemas/order.ts
const ClientOrderSchema = z.object({
  items: z.array(z.object({ id: z.string(), qty: z.number() })),
})

// server/schemas/order.ts (WRITTEN AGAIN — maintenance nightmare)
const ServerOrderSchema = z.object({
  items: z.array(z.object({ id: z.string(), qty: z.number() })),
})

// ✅ GOOD — shared schema
// packages/shared/schemas/order.ts
export const OrderSchema = z.object({
  items: z.array(z.object({ id: z.string(), qty: z.number() })),
})
// Used in both client and server
```

#### 13.3 Zod for TypeScript-Only Types

```typescript
// ❌ BAD — Zod schema defined but only used for types
const UserSchema = z.object({ name: z.string(), email: z.string().email() })
// ... never used to validate any input
// Just use: type User = { name: string; email: string }

// ✅ GOOD — schema used for validation AND types
const UserSchema = z.object({ name: z.string(), email: z.string().email() })
type User = z.infer<typeof UserSchema>

function handleUser(input: unknown) {  // input is unknown, not User
  const result = UserSchema.safeParse(input)
  if (!result.success) throw new Error('Invalid input')
  // result.data is User
  saveToDb(result.data)
}
```

#### 13.4 Overly Complex Schemas

```typescript
// ❌ BAD — trying to validate everything in one schema
const ComplexSchema = z.object({
  data: z.union([
    z.object({ type: z.literal('a'), nested: z.object({ ... }) }),
    z.object({ type: z.literal('b'), nested: z.object({ ... }) }),
  ]).transform(d => d.nested).pipe(z.object({ ... })),
  meta: z.record(z.unknown()).optional(),
})

// ✅ GOOD — split into clear, testable schemas
const DataA = z.object({ type: z.literal('a'), value: z.string() })
const DataB = z.object({ type: z.literal('b'), value: z.number() })
const InputSchema = z.discriminatedUnion('type', [DataA, DataB])

// Parse first, then transform separately
function processInput(input: unknown) {
  const parsed = InputSchema.parse(input)
  // Now transform with pure functions (testable separately)
  return transformData(parsed)
}
```

#### 13.5 Not Using Discriminated Unions

```typescript
// ❌ BAD — union tries schemas sequentially (O(n))
const Response = z.union([
  z.object({ ok: z.literal(true), data: z.unknown() }),
  z.object({ ok: z.literal(false), error: z.string() }),
])

// ✅ GOOD — discriminatedUnion compiles to switch (O(1))
const Response = z.discriminatedUnion('ok', [
  z.object({ ok: z.literal(true), data: z.unknown() }),
  z.object({ ok: z.literal(false), error: z.string() }),
])

// Bonus: discriminatedUnion has better error messages
// — tells you exactly which discriminator matched/failed
```

#### 13.6 Ignoring Validation at System Boundaries

```typescript
// ❌ BAD — trusting third-party API responses
async function fetchUser(id: string) {
  const res = await fetch(`/api/users/${id}`)
  return res.json()  // unknown shape, could be anything
}

// ✅ GOOD — validate at system boundary
async function fetchUser(id: string) {
  const res = await fetch(`/api/users/${id}`)
  const result = UserSchema.safeParse(await res.json())
  if (!result.success) {
    throw new Error(`Invalid API response: ${result.error.message}`)
  }
  return result.data
}
```

#### 13.7 Mixing Validation Logic with Business Logic

```typescript
// ❌ BAD — business logic inside schema validation
const OrderSchema = z.object({
  items: z.array(z.object({ price: z.number(), qty: z.number() }))
    .refine(items => {
      return items.reduce((sum, i) => sum + i.price * i.qty, 0) > 0
    }, 'Total must be positive'),  // Business rule in validation layer
})

// ✅ GOOD — validation = shape, business logic = separate
const OrderShape = z.object({
  items: z.array(z.object({ price: z.number(), qty: z.number() })).min(1),
})

type Order = z.infer<typeof OrderShape>

function calculateTotal(order: Order): number {
  return order.items.reduce((sum, i) => sum + i.price * i.qty, 0)
}

function placeOrder(input: unknown) {
  const order = OrderShape.parse(input)
  const total = calculateTotal(order)
  if (total <= 0) throw new Error('Order total must be positive')
  // ... proceed
}
```

---

### 14. Implementation Checklist

#### Getting Started
- [ ] Choose Zod v4 or Valibot based on bundle size needs
- [ ] Install: `npm install zod` or `npm install valibot`
- [ ] For RHF: `npm install @hookform/resolvers`
- [ ] For tRPC: `npm install @trpc/server` (Zod included)
- [ ] For env: `npm install dotenv`
- [ ] For JSON Schema: `npm install zod-to-json-schema`

#### Schema Design
- [ ] Define schemas in `src/schemas/` per entity
- [ ] Use `z.infer` for TypeScript types (never manual interfaces)
- [ ] Use discriminatedUnion for API response types
- [ ] Export input + output schemas separately (CreateUser, UserResponse)
- [ ] Use `safeParse` everywhere (not `parse`)
- [ ] Add custom error messages for user-facing schemas

#### Form Integration
- [ ] Use `zodResolver` / `valibotResolver` with React Hook Form
- [ ] Define full form shape in schema (nested fields included)
- [ ] Use `register('address.street')` for nested fields
- [ ] Use `superRefine` for cross-field validation
- [ ] Use `useFieldArray` for dynamic lists
- [ ] Call `safeParseAsync` for async validation

#### API Layer
- [ ] Validate request body, query params, path params
- [ ] Validate API responses at client boundary
- [ ] Generate JSON Schema from Zod for Fastify/OpenAPI
- [ ] Use Zod parsing in Express middleware / Nest.js pipes
- [ ] For tRPC: Zod schema as `.input()` directly
- [ ] Share schemas between client and server via monorepo

#### Environment
- [ ] Define typed env schema with defaults
- [ ] Use `z.coerce.number()/boolean()` for env vars
- [ ] Fail fast on invalid env (process.exit at startup)
- [ ] Cache parsed env object

#### Testing
- [ ] Test happy path for each schema
- [ ] Test edge cases: empty strings, null, missing fields, boundaries
- [ ] Test discriminated unions with each variant
- [ ] Test error messages match expectations
- [ ] Test transform outputs
- [ ] Test type-level inference with `expectTypeOf`
- [ ] Test async validation

#### Performance
- [ ] Prefer discriminatedUnion over union for variants
- [ ] Warm up schema cache at startup for hot paths
- [ ] Split large schemas into composable pieces
- [ ] Use Valibot for bundle-sensitive clients
- [ ] Never validate the same data twice in same boundary

#### Review
- [ ] No `parse()` in production code (use `safeParse`)
- [ ] All system boundaries have validation (forms, API, env, storage)
- [ ] Zod is not used for TypeScript-only types
- [ ] Schemas are shared, not duplicated
- [ ] Business logic is separate from validation logic
- [ ] Error messages are user-friendly (i18n ready)
- [ ] Discriminated unions used for variant data
