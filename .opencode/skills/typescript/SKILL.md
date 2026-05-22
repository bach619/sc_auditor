---
name: typescript
description: TypeScript mastery — advanced types, generics, conditional/mapped/template literal types, declaration files, strictness, inference, performance optimization, and production patterns
license: MIT
compatibility: opencode
metadata:
  audience: frontend-developers
  domain: frontend
  paradigm: typed-functional
  capabilities:
    - advanced-types
    - generics
    - type-inference
    - declaration-files
    - strict-mode
---

# Skill: typescript

## TypeScript Mastery — Advanced Types, Generics, Inference, and Production Patterns

### Core Philosophy

TypeScript is not JavaScript with types. TypeScript is a **type-level programming language** embedded in JavaScript. Every JS expression has a corresponding type-level computation. The goal is to encode business logic invariants into the type system so that illegal states are **unrepresentable**.

```
┌──────────────────────────────────────────────────────────────┐
│                  TYPESCRIPT MENTAL MODEL                      │
│                                                               │
│   Runtime (JS)            Type-Level (TS)                     │
│   ────────────            ────────────────                    │
│   const x = 5            type X = 5                           │
│   function f(a,b)        type F<A,B> = ...                    │
│   if/else                Conditional types                    │
│   for/map                Mapped types                         │
│   template literals      Template literal types               │
│   spread/rest            Variadic tuple types                 │
│   return value           infer                                │
│   try/catch              Result<T,E>                          │
│                                                               │
│   "Move validation from runtime to compile-time"              │
└──────────────────────────────────────────────────────────────┘
```

---

### 1. Type System Fundamentals

#### 1.1 Primitive Types

```typescript
// Primitives (lowercase — NEVER use uppercase wrappers)
const str: string = 'hello'
const num: number = 42
const bool: boolean = true
const big: bigint = 100n
const sym: symbol = Symbol('foo')
const undef: undefined = undefined
const nil: null = null

// ❌ NEVER use String, Number, Boolean (object wrappers)
const bad: String = 'hello'  // typeof bad === 'object' at runtime
```

#### 1.2 Object, Array, Tuple, Enum

```typescript
// Object
type User = { id: string; name: string; age: number }

// Array — two syntaxes, be consistent
const items: string[] = ['a', 'b']           // preferred
const stuff: Array<string> = ['x', 'y']      // JSX-generic syntax

// Tuple — fixed-length, ordered types
type Point = [x: number, y: number, z?: number]  // labeled tuples (TS 4.0+)
const origin: Point = [0, 0, 0]

// Readonly tuple
type RGB = readonly [number, number, number]
const red: RGB = [255, 0, 0]

// Enum — prefer const enum or string union instead
enum Color { Red, Green, Blue }            // numeric, use with caution
const enum Direction { Up, Down, Left, Right }  // const enum = zero runtime cost
type Status = 'active' | 'inactive' | 'pending'  // string union > enum for most cases
```

#### 1.3 Union, Intersection, Literal

```typescript
// Union — "this OR that"
type ID = string | number
type Result = Success | Error

// Intersection — "this AND that"
type Named = { name: string }
type Aged = { age: number }
type Person = Named & Aged  // { name: string; age: number }

// Intersection merging conflicts — never
type Conflict = { a: string } & { a: number }  // a: never (impossible)

// Literal — exact value as type
type Direction = 'up' | 'down' | 'left' | 'right'
type DiceRoll = 1 | 2 | 3 | 4 | 5 | 6
type Truthy = true  // literal true type
```

#### 1.4 `type` vs `interface` — Decision Tree

```
Need a type?
    │
    ├── Can the shape be expressed as an object?
    │       │
    │       ├── YES ──► Are you writing a library (public API)?
    │       │               │
    │       │               ├── YES ──► interface (extendable by consumers)
    │       │               └── NO  ──► type (union/intersection)
    │       │
    │       └── NO ──► type (unions, primitives, tuples, conditional)
    │
    ├── Do you need union/intersection/mapped/conditional? ──► type
    ├── Do you need declaration merging? ──► interface
    └── Do you need performance (cached by TS)? ──► interface
```

```typescript
// Use interface for: public API shapes, class contracts, declaration merging
interface User {
  name: string
  email: string
}
interface User {  // declaration merging — re-opened
  age?: number
}

// Use type for: everything else
type ID = string | number
type Point = [number, number]
type DeepPartial<T> = { [K in keyof T]?: DeepPartial<T[K]> }
type Handler = (event: Event) => void
```

#### 1.5 Readonly, Optional, Non-Null Assertion

```typescript
// Optional — may or may not exist
type Config = { url: string; port?: number; timeout?: number }

// Readonly — cannot be reassigned after creation
type Immutable = { readonly id: string; readonly createdAt: Date }
const obj: Immutable = { id: '1', createdAt: new Date() }
// obj.id = '2'  // ❌ Error: Cannot assign to 'id' because it is a read-only property

// Non-null assertion — use SPARINGLY (only when TS can't infer what you know)
const el = document.getElementById('root')!  // el: HTMLElement (not HTMLElement | null)
```

#### 1.6 Type Assertions vs Declarations

```typescript
// Type assertion — "I know more than TS" (use with caution)
const value = someFunc() as string      // ❌ can lie
const value2 = someFunc() as unknown as number  // ❌ double assertion = escape hatch

// Type declaration — let TS validate the shape
const value3: string = someFunc()  // ✅ TS checks assignability

// `satisfies` operator (TS 4.9+) — best of both: validates shape + infers narrow type
const palette = {
  red: [255, 0, 0],
  green: '#00ff00',
  blue: [0, 0, 255],
} satisfies Record<string, string | number[]>

// palette.red is inferred as number[] (narrow), but satisfies the Record constraint
```

#### 1.7 Type Narrowing

```typescript
// typeof narrowing
function format(input: string | number): string {
  if (typeof input === 'string') return input.toUpperCase()
  return input.toFixed(2)  // TS knows it's `number` here
}

// instanceof narrowing
class ApiError extends Error { code: number }
function handleError(err: Error | ApiError) {
  if (err instanceof ApiError) console.log(err.code)
  else console.log(err.message)
}

// Discriminated unions — THE most important narrowing pattern
type Shape =
  | { kind: 'circle'; radius: number }
  | { kind: 'rectangle'; width: number; height: number }
  | { kind: 'triangle'; base: number; height: number }

function area(shape: Shape): number {
  switch (shape.kind) {
    case 'circle':   return Math.PI * shape.radius ** 2
    case 'rectangle': return shape.width * shape.height
    case 'triangle':  return (shape.base * shape.height) / 2
    default:          return exhaustive(shape)  // never — if this compiles, we missed a case
  }
}

function exhaustive(_: never): never { throw new Error('Unreachable') }

// Type predicates — custom user-defined type guards
function isFish(pet: Fish | Bird): pet is Fish {
  return (pet as Fish).swim !== undefined
}
function feed(pet: Fish | Bird) {
  if (isFish(pet)) {
    pet.swim()       // TS knows pet is Fish here
  }
}

// `in` operator narrowing
function move(animal: Fish | Bird) {
  if ('swim' in animal) animal.swim()
  else animal.fly()
}
```

#### 1.8 Assertion Functions

```typescript
// Assertion functions — throw if condition fails, narrows type
function assertIsString(value: unknown): asserts value is string {
  if (typeof value !== 'string') throw new Error('Not a string')
}

function process(input: unknown) {
  assertIsString(input)
  input.toUpperCase()  // TS knows input is `string` here
}

// Simple assertion — asserts truthiness
function assert(condition: any, msg?: string): asserts condition {
  if (!condition) throw new Error(msg ?? 'Assertion failed')
}

function getConfig(key: string): string {
  const val = process.env[key]
  assert(val !== undefined, `Missing env var: ${key}`)
  return val  // TS knows val is string (not string | undefined)
}
```

---

### 2. Generics Mastery

#### 2.1 Generic Functions, Interfaces, Classes

```typescript
// Generic functions
function identity<T>(arg: T): T {
  return arg
}
const result = identity('hello')  // T inferred as 'hello' (literal, not string)

// Generic interfaces
interface Repository<T extends { id: string }> {
  getById(id: string): Promise<T | null>
  getAll(): Promise<T[]>
  create(data: Omit<T, 'id'>): Promise<T>
  update(id: string, data: Partial<T>): Promise<T>
  delete(id: string): Promise<void>
}

// Generic classes
class Stack<T> {
  private items: T[] = []
  push(item: T): void { this.items.push(item) }
  pop(): T | undefined { return this.items.pop() }
  peek(): T | undefined { return this.items[this.items.length - 1] }
  get length(): number { return this.items.length }
}

// Constraints with extends
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key]
}
const user = { name: 'Alice', age: 30, email: 'alice@test.com' }
getProperty(user, 'name')  // string
getProperty(user, 'age')   // number
// getProperty(user, 'ssn')  // ❌ Error: 'ssn' not in keyof user
```

#### 2.2 Generic Inference

```typescript
// How TS infers generics from usage
function pair<T, U>(a: T, b: U): [T, U] {
  return [a, b]
}
const p1 = pair('hello', 42)          // inferred: [string, number]
const p2 = pair({ x: 1 }, [1, 2, 3])  // inferred: [{ x: number }, number[]]

// Inference with literal types — use `as const` to preserve literals
function createArray<T>(items: T[]): T[] { return items }
const arr1 = createArray(['a', 'b'])             // inferred: string[]
const arr2 = createArray(['a', 'b'] as const)    // inferred: ("a" | "b")[]

// Inference fails — provide explicit type
function merge<T, U>(a: T, b: U): T & U { return { ...a, ...b } }
const merged = merge({ name: 'Alice' }, { age: 30 })
// merged: { name: string } & { age: number }
```

#### 2.3 Generic Defaults

```typescript
// Default type parameters
interface ApiResponse<T = unknown> {
  data: T
  status: number
  message: string
}

const response1: ApiResponse = { data: {}, status: 200, message: 'OK' }
// T defaults to unknown

const response2: ApiResponse<User> = {
  data: { id: '1', name: 'Alice' },
  status: 200,
  message: 'OK',
}

// Defaults in functions
function createStore<T, S = T>(initial: T, transform?: (val: T) => S) {
  let state = initial
  return {
    getState: () => state,
    setState: (next: T | ((prev: T) => T)) => {
      state = next instanceof Function ? next(state) : next
    },
  }
}
const store = createStore({ count: 0 })
// store inferred as { count: number }
```

#### 2.4 Higher-Order Generics

```typescript
// Generic function returning a generic function
function createComparator<T>() {
  return function compare<U extends T>(a: U, b: U): number {
    if (a < b) return -1
    if (a > b) return 1
    return 0
  }
}

const compareNumbers = createComparator<number>()
compareNumbers(1, 2)  // -1

// Generic middleware factory
type Middleware<T, R> = (context: T, next: () => Promise<R>) => Promise<R>

function composeMiddlewares<T, R>(...middlewares: Middleware<T, R>[]) {
  return (context: T, final: () => Promise<R>): Promise<R> => {
    const dispatch = (index: number): Promise<R> => {
      const middleware = middlewares[index]
      if (!middleware) return final()
      return middleware(context, () => dispatch(index + 1))
    }
    return dispatch(0)
  }
}
```

#### 2.5 Variadic Tuple Types

```typescript
// Variadic tuples — spread types into tuples (TS 4.0+)
type Concatenate<T extends unknown[], U extends unknown[]> = [...T, ...U]
type Result = Concatenate<[1, 2], [3, 4]>               // [1, 2, 3, 4]

// Function overloads with variadic tuples
function concat<T extends unknown[], U extends unknown[]>(
  arr1: [...T],
  arr2: [...U],
): [...T, ...U]
function concat(arr1: unknown[], arr2: unknown[]): unknown[] {
  return [...arr1, ...arr2]
}

// Typed currying with variadic tuples
type Curry<A extends unknown[], R> =
  A extends [infer First, ...infer Rest]
    ? (arg: First) => Curry<Rest, R>
    : R

function curry<A extends unknown[], R>(
  fn: (...args: A) => R,
): Curry<A, R> {
  return ((...args: unknown[]) => {
    if (args.length >= fn.length) return fn(...args as A)
    return curry(fn.bind(null, ...args) as (...args: unknown[]) => R)
  }) as Curry<A, R>
}

const add = (a: number, b: number, c: number) => a + b + c
const curriedAdd = curry(add)  // (a: number) => (b: number) => (c: number) => number

// Leading/middle spread
type Head<T extends unknown[]> = T extends [infer First, ...unknown[]] ? First : never
type Tail<T extends unknown[]> = T extends [unknown, ...infer Rest] ? Rest : never
type Last<T extends unknown[]> = T extends [...unknown[], infer Last] ? Last : never
```

#### 2.6 Const Type Parameters

```typescript
// `const` type parameters (TS 5.0+) — preserve literal types without `as const` at call site
function tuple<T extends readonly unknown[]>(...items: [...T]): T {
  return items
}

const result = tuple('hello', 42, true)
// Before TS 5.0: (string | number | boolean)[]
// With const T: readonly ['hello', 42, true]

// String manipulation with const type params
function join<T extends readonly string[]>(separator: string, ...strings: [...T]): string {
  return strings.join(separator)
}
const path = join('/', 'users', 'profile', 'edit')
// path: string (runtime) — but the actual args are validated as strings
```

#### 2.7 Generic Patterns

```typescript
// Builder pattern
class QueryBuilder<T, S extends unknown[] = []> {
  private constructor(private readonly conditions: string[] = []) {}

  static create<T>() {
    return new QueryBuilder<T>()
  }

  where<K extends keyof T & string>(
    field: K,
    operator: '=' | '!=' | '>' | '<' | 'LIKE',
    value: T[K],
  ): QueryBuilder<T, [...S, { field: K; op: typeof operator; value: T[K] }]> {
    return new QueryBuilder([...this.conditions, `${field} ${operator} ${value}`])
  }

  build(): string {
    return `SELECT * FROM table WHERE ${this.conditions.join(' AND ')}`
  }
}
const qb = QueryBuilder.create<User>().where('name', '=', 'Alice').where('age', '>', 18)

// Repository pattern
interface Identifiable { id: string }
interface Entity<T extends Identifiable> {
  toJSON(): T
  equals(other: Entity<T>): boolean
}

class Repository<T extends Identifiable> {
  private items = new Map<string, T>()

  add(entity: T): this {
    this.items.set(entity.id, entity)
    return this
  }

  findById(id: T['id']): T | undefined {
    return this.items.get(id)
  }

  findAll(): T[] {
    return Array.from(this.items.values())
  }

  update(id: T['id'], partial: Partial<T>): this {
    const existing = this.items.get(id)
    if (existing) this.items.set(id, { ...existing, ...partial })
    return this
  }
}

// Strategy pattern with generics
interface Strategy<TInput, TOutput> {
  canHandle(input: TInput): boolean
  execute(input: TInput): TOutput
}

class StrategyExecutor<TInput, TOutput> {
  constructor(private strategies: Strategy<TInput, TOutput>[]) {}

  execute(input: TInput): TOutput {
    const strategy = this.strategies.find(s => s.canHandle(input))
    if (!strategy) throw new Error('No strategy found')
    return strategy.execute(input)
  }
}

// Factory pattern
interface Factory<T> {
  create(): T
  destroy(instance: T): void
}

class ComponentFactory<T> implements Factory<T> {
  constructor(
    private readonly ctor: new (...args: any[]) => T,
    private readonly deps: any[],
  ) {}

  create(): T {
    return new this.ctor(...this.deps)
  }

  destroy(instance: T): void {
    const maybeDisposable = instance as { dispose?: () => void }
    maybeDisposable.dispose?.()
  }
}
```

---

### 3. Advanced Types (God Tier)

#### 3.1 Conditional Types

```typescript
// Basic conditional: T extends U ? X : Y
type IsString<T> = T extends string ? true : false
type A = IsString<'hello'>    // true
type B = IsString<42>         // false

// Conditional chains (type-level if/else if/else)
type TypeName<T> =
  T extends string  ? 'string' :
  T extends number  ? 'number' :
  T extends boolean ? 'boolean' :
  T extends undefined ? 'undefined' :
  T extends null    ? 'null' :
  T extends Function ? 'function' :
  T extends symbol  ? 'symbol' :
  'object'

type T1 = TypeName<string>       // 'string'
type T2 = TypeName<() => void>   // 'function'

// Filtering with conditional types
type NonNullable<T> = T extends null | undefined ? never : T
type T3 = NonNullable<string | null | undefined>  // string
```

#### 3.2 Distributive Conditional Types

```typescript
// Conditional types distribute over unions by default
type ToArray<T> = T extends unknown ? T[] : never
type Result = ToArray<string | number>
// Result: string[] | number[]  (NOT (string | number)[])

// Prevent distribution with tuple wrapping
type ToArrayNonDist<T> = [T] extends [unknown] ? T[] : never
type Result2 = ToArrayNonDist<string | number>
// Result2: (string | number)[]  (single array type)

// Practical: extract values matching a kind
type ExtractByKind<T, K> = T extends { kind: K } ? T : never
type ShapeEvent = ExtractByKind<Shape, 'circle'>
// ShapeEvent = { kind: 'circle'; radius: number }
```

#### 3.3 Mapped Types

```typescript
// Basic mapped type — transform each property
type Readonly<T> = { readonly [K in keyof T]: T[K] }
type Optional<T> = { [K in keyof T]?: T[K] }

// Key remapping via `as` clause (TS 4.1+)
type Getters<T> = {
  [K in keyof T as `get${Capitalize<K & string>}`]: () => T[K]
}
type UserGetters = Getters<{ name: string; age: number }>
// { getName: () => string; getAge: () => number }

// Filter keys by type
type StringKeys<T> = {
  [K in keyof T as T[K] extends string ? K : never]: T[K]
}
type UserStrings = StringKeys<{ name: string; age: number; email: string }>
// { name: string; email: string }

// Transform value types
type Nullable<T> = { [K in keyof T]: T[K] | null }

// Property modification with + / - prefixes
type Mutable<T> = { -readonly [K in keyof T]: T[K] }
type Required2<T> = { [K in keyof T]-?: T[K] }

// Mapping with property predicates
type FunctionsOf<T> = {
  [K in keyof T as T[K] extends (...args: any[]) => any ? K : never]: T[K]
}
```

#### 3.4 Template Literal Types

```typescript
// Template literal types (TS 4.1+) — string manipulation at type level
type EventName<T extends string> = `on${Capitalize<T>}`
type ClickHandler = EventName<'click'>  // 'onClick'
type FocusHandler = EventName<'focus'>  // 'onFocus'

// Intrinsic string types
type Upper = Uppercase<'hello'>     // 'HELLO'
type Lower = Lowercase<'HELLO'>     // 'hello'
type Capital = Capitalize<'hello'>  // 'Hello'
type Uncap = Uncapitalize<'Hello'>  // 'hello'

// Parsing with template literals
type ExtractId<T extends string> =
  T extends `${string}/id/${infer Id}` ? Id : never
type UserId = ExtractId<'/api/users/id/abc123'>  // 'abc123'

// CSS properties (practical)
type CSSUnit = 'px' | 'rem' | 'em' | '%' | 'vh' | 'vw'
type CSSValue = `${number}${CSSUnit}`
const width: CSSValue = '100px'   // ✅
const bad: CSSValue = '100'        // ❌

// API path builder
type ApiPath<Resource extends string, Action extends string> =
  Resource extends 'users'
    ? Action extends 'list' ? '/api/users'
    : Action extends 'get' ? `/api/users/:id`
    : Action extends 'create' ? '/api/users'
    : Action extends 'update' ? `/api/users/:id`
    : Action extends 'delete' ? `/api/users/:id`
    : never
  : never

type UserListPath = ApiPath<'users', 'list'>  // '/api/users'
type UserGetPath = ApiPath<'users', 'get'>    // '/api/users/:id'

// Fluent API paths
type FluentPath<T, Prefix extends string = ''> = {
  [K in keyof T & string]: T[K] extends Record<string, any>
    ? FluentPath<T[K], `${Prefix}${K}.`>
    : `${Prefix}${K}`
}[keyof T & string]

const nested = { a: { b: { c: 1 } }, d: 2 }
type NestedPaths = FluentPath<typeof nested>  // 'a.b.c' | 'd'
```

#### 3.5 Recursive Types

```typescript
// Recursive JSON type — THE classic
type JSONValue =
  | string
  | number
  | boolean
  | null
  | JSONValue[]
  | { [key: string]: JSONValue }

// DeepPartial — recursive optional
type DeepPartial<T> = T extends object
  ? { [K in keyof T]?: DeepPartial<T[K]> }
  : T

// DeepReadonly — recursive readonly
type DeepReadonly<T> = T extends object
  ? { readonly [K in keyof T]: DeepReadonly<T[K]> }
  : T

// DeepRequired — recursive required + non-nullable
type DeepRequired<T> = T extends object
  ? { [K in keyof T]-?: DeepRequired<NonNullable<T[K]>> }
  : NonNullable<T>

// DeepNonNullable — strip null/undefined from all levels
type DeepNonNullable<T> =
  T extends null | undefined ? never :
  T extends object ? { [K in keyof T]: DeepNonNullable<T[K]> } :
  T

// Recursive tree type
type TreeNode<T> = {
  value: T
  children: TreeNode<T>[]
}

// Recursive URL params
type ExtractParams<T extends string> =
  T extends `${string}:${infer Param}/${infer Rest}`
    ? { [K in Param | keyof ExtractParams<Rest>]: string }
    : T extends `${string}:${infer Param}`
      ? { [K in Param]: string }
      : {}

type UserParams = ExtractParams<'/api/users/:userId/posts/:postId'>
// { userId: string; postId: string }
```

#### 3.6 `infer` Keyword

```typescript
// infer captures a type within a conditional — type-level pattern matching

// Extract return type of a function
type ReturnType<T> = T extends (...args: any[]) => infer R ? R : never
type Fn = ReturnType<() => string[]>  // string[]

// Extract parameters of a function
type Parameters<T> = T extends (...args: infer P) => any ? P : never
type Params = Parameters<(a: string, b: number) => void>  // [string, number]

// Extract array element type
type ElementType<T> = T extends (infer U)[] ? U : never
type El = ElementType<string[]>  // string

// Extract Promise inner type
type Unwrap<T> = T extends Promise<infer U> ? U : T
type Inner = Unwrap<Promise<string>>  // string

// Extract constructor parameters
type ConstructorParams<T> = T extends new (...args: infer P) => any ? P : never

// Extract instance type from constructor
type InstanceType<T> = T extends new (...args: any[]) => infer R ? R : never

// Deep inference — unwrap nested promises
type DeepUnwrap<T> = T extends Promise<infer U> ? DeepUnwrap<U> : T
type Nested = DeepUnwrap<Promise<Promise<Promise<string>>>>  // string

// Infer in template literals
type ExtractName<T extends string> =
  T extends `Hello, ${infer Name}!` ? Name : never
type Name = ExtractName<'Hello, World!'>  // 'World'

// Infer in tuple types
type First<T> = T extends [infer F, ...unknown[]] ? F : never
type Last<T> = T extends [...unknown[], infer L] ? L : never
type F = First<[1, 2, 3]>  // 1
type L = Last<[1, 2, 3]>   // 3
```

#### 3.7 Branded / Nominal Types

```typescript
// Branded types — simulate nominal typing in a structural type system
type Brand<T, B> = T & { __brand: B }

type UserId = Brand<string, 'UserId'>
type ProductId = Brand<string, 'ProductId'>
type Email = Brand<string, 'Email'>

function getUser(id: UserId): User { /**/ }
function getProduct(id: ProductId): Product { /**/ }

const uid = 'user_123' as UserId
const pid = 'prod_456' as ProductId

getUser(uid)       // ✅
getUser(pid)       // ❌ Type 'ProductId' not assignable to 'UserId'
getUser('raw')     // ❌ Type 'string' not assignable to 'UserId'

// Branded factory
function createUserId(raw: string): UserId {
  if (!raw.startsWith('user_')) throw new Error('Invalid user ID')
  return raw as UserId
}

// Type-safe currencies (classic use case)
type USD = Brand<number, 'USD'>
type EUR = Brand<number, 'EUR'>

function addUSD(a: USD, b: USD): USD {
  return (a + b) as USD
}
function convertToEUR(usd: USD, rate: number): EUR {
  return (usd * rate) as EUR
}

// Flavoring — same idea, lighter branding
type Flavor<T, F> = T & { _flavor?: F }
type Meters = Flavor<number, 'meters'>
type Seconds = Flavor<number, 'seconds'>
```

#### 3.8 `satisfies` Operator (TS 4.9+)

```typescript
// satisfies: validate shape WITHOUT widening the type
// Old way — type widening loses literal info
const palette: Record<string, string | number[]> = {
  red: [255, 0, 0],
  green: '#00ff00',
}
// palette.red.map(...)  // ❌ Error: number[] | string — no .map()

// With satisfies — validates + preserves narrow types
const palette2 = {
  red: [255, 0, 0],
  green: '#00ff00',
} satisfies Record<string, string | number[]>

palette2.red.map(x => x)  // ✅ TS knows red is number[]
palette2.green.toUpperCase()  // ✅ TS knows green is string

// Practical: API config
const apiConfig = {
  baseUrl: 'https://api.example.com',
  timeout: 5000,
  retries: 3,
  headers: { 'Content-Type': 'application/json' },
} satisfies {
  baseUrl: string
  timeout: number
  retries: number
  headers: Record<string, string>
}

// Union narrowing with satisfies
type Color = string | { r: number; g: number; b: number; a?: number }
const primaryColor = { r: 255, g: 0, b: 0 } satisfies Color
primaryColor.r  // ✅ TS knows it's the object variant, not string
```

#### 3.9 `using` Declarations (TS 5.2+)

```typescript
// using = TC39 Explicit Resource Management (like C# using / Python with)
// Requires target: ES2022 or ESNext

interface Disposable {
  [Symbol.dispose](): void
}

class FileHandler implements Disposable {
  constructor(private path: string) {
    console.log(`Opening file: ${path}`)
  }

  read(): string {
    return `content of ${this.path}`
  }

  [Symbol.dispose]() {
    console.log(`Closing file: ${this.path}`)
  }
}

function processFile(path: string) {
  using file = new FileHandler(path)
  return file.read()
}  // file[Symbol.dispose]() called automatically here

// Async disposable
interface AsyncDisposable {
  [Symbol.asyncDispose](): Promise<void>
}

class DatabaseConnection implements AsyncDisposable {
  async query(sql: string) { /**/ }
  async [Symbol.asyncDispose]() {
    await this.close()
  }
  private async close() { /**/ }
}

async function fetchData() {
  await using db = new DatabaseConnection()
  return db.query('SELECT * FROM users')
}  // db[Symbol.asyncDispose]() called automatically
```

#### 3.10 Import Attributes (TS 5.4+)

```typescript
// Import attributes — metadata for import resolution
import data from './data.json' with { type: 'json' }

// CSS module imports (bundler-dependent)
import styles from './button.module.css' with { type: 'css' }
// type: 'css' is supported by Vite, webpack, etc.

// Re-export with attributes
export { default as schema } from './schema.json' with { type: 'json' }
```

---

### 4. Utility Types — Deep Dive

#### 4.1 Built-in Utility Types

```typescript
// Partial<T> — all properties optional
type PartialUser = Partial<User>  // { name?: string; age?: number; email?: string }

// Required<T> — all properties required
type RequiredConfig = Required<{ url?: string; port?: number }>  // { url: string; port: number }

// Readonly<T> — all properties readonly
type ReadonlyUser = Readonly<User>  // { readonly name: string; readonly age: number; ... }

// Pick<T, K> — select specific keys
type UserName = Pick<User, 'name' | 'email'>  // { name: string; email: string }

// Omit<T, K> — exclude specific keys
type UserWithoutEmail = Omit<User, 'email'>  // { name: string; age: number }

// Record<K, T> — object type with keys K and values T
type PageInfo = Record<string, string>        // { [key: string]: string }
type HttpStatus = Record<number, string>      // { [key: number]: string }
type HttpHeaders = Record<string, string | string[]>  // flexible header values

// Exclude<T, U> — exclude types from union
type Primitive = Exclude<string | number | boolean | object, object>
// Primitive = string | number | boolean

// Extract<T, U> — extract types from union
type StringOrNumber = Extract<string | number | boolean, string | number>
// StringOrNumber = string | number

// NonNullable<T> — remove null & undefined
type Maybe = string | null | undefined
type Definite = NonNullable<Maybe>  // string

// Parameters<T> — function parameter tuple
type FnParams = Parameters<(name: string, age: number) => void>
// FnParams = [name: string, age: number]

// ReturnType<T> — function return type
type FnResult = ReturnType<() => Promise<User>>
// FnResult = Promise<User>

// InstanceType<T> — instance type of constructor
class MyClass { x = 1 }
type Instance = InstanceType<typeof MyClass>  // MyClass

// Awaited<T> — unwrap promises (TS 4.5+)
type AsyncData = Awaited<Promise<Promise<string[]>>>
// AsyncData = string[]  (fully unwrapped)

// ConstructorParameters<T>
type CtorParams = ConstructorParameters<typeof MyClass>  // []

// ThisParameterType<T> — extract `this` parameter type
type ThisType = ThisParameterType<(this: Window, x: number) => void>  // Window

// OmitThisParameter<T> — remove `this` parameter
type NoThis = OmitThisParameter<(this: Window, x: number) => void>  // (x: number) => void

// String manipulation utilities
type Upper = Uppercase<'hello'>      // 'HELLO'
type Lower = Lowercase<'HELLO'>      // 'hello'
type Capital = Capitalize<'hello'>   // 'Hello'
type Uncap = Uncapitalize<'Hello'>   // 'hello'
```

#### 4.2 Custom Utility Types

```typescript
// DeepPartial — recursive optional at all levels
type DeepPartial<T> = T extends object
  ? { [K in keyof T]?: DeepPartial<T[K]> }
  : T

// DeepRequired — recursive required, removes null/undefined
type DeepRequired<T> = T extends object
  ? { [K in keyof T]-?: DeepRequired<NonNullable<T[K]>> }
  : NonNullable<T>

// DeepReadonly — recursive readonly
type DeepReadonly<T> = T extends (...args: any[]) => any
  ? T
  : T extends object
    ? { readonly [K in keyof T]: DeepReadonly<T[K]> }
    : T

// NonEmptyArray — type-safe non-empty array
type NonEmptyArray<T> = [T, ...T[]]

function first<T>(arr: NonEmptyArray<T>): T {
  return arr[0]
}
first([1, 2, 3])  // ✅
// first([])       // ❌ — would never compile

// Brand type
type Brand<T, B> = T & { __brand: B }

// Maybe — nullable wrapper
type Maybe<T> = T | null | undefined

// Result type — success or error
type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E }

// Safe function wrapper
function safe<T, E = Error>(fn: () => T): Result<T, E> {
  try {
    return { ok: true, value: fn() }
  } catch (error) {
    return { ok: false, error: error as E }
  }
}

// AsyncReturnType — unwrap async return
type AsyncReturnType<T extends (...args: any[]) => any> =
  Awaited<ReturnType<T>>

// DeepPick — pick nested properties
type DeepPick<T, Path extends string> =
  Path extends keyof T
    ? { [K in Path]: T[K] }
    : Path extends `${infer K}.${infer Rest}`
      ? K extends keyof T
        ? { [P in K]: DeepPick<T[K], Rest> }
        : never
      : never

type DeepPickExample = DeepPick<{ a: { b: number; c: string } }, 'a.b'>
// { a: { b: number } }

// UnionToIntersection — convert union to intersection (advanced)
type UnionToIntersection<U> =
  (U extends any ? (k: U) => void : never) extends (k: infer I) => void ? I : never
type Intersected = UnionToIntersection<{ a: 1 } | { b: 2 }>
// { a: 1 } & { b: 2 }

// StringKeys — only keys with string values
type StringKeys<T> = {
  [K in keyof T as T[K] extends string ? K : never]: T[K]
}

// FunctionKeys — only keys that are functions
type FunctionKeys<T> = {
  [K in keyof T as T[K] extends (...args: any[]) => any ? K : never]: T[K]
}
```

#### 4.3 Promise Unwrapping

```typescript
// PromiseType — extract inner type from Promise
type PromiseType<T> = T extends Promise<infer U> ? U : never

type Unwrapped = PromiseType<Promise<User[]>>  // User[]

// Deep promise unwrapping (multiple layers)
type DeepPromise<T> = T extends Promise<infer U> ? DeepPromise<U> : T
type Deep = DeepPromise<Promise<Promise<string[]>>>  // string[]

// Promise all types
type PromiseAll<T extends readonly unknown[]> = {
  [K in keyof T]: Awaited<T[K]>
}

async function PromiseAll<T extends readonly unknown[]>(
  promises: T,
): Promise<PromiseAll<T>> {
  return Promise.all(promises) as any
}

const [user, posts] = await PromiseAll([
  fetchUser(),
  fetchPosts(),
] as const)
// user: User, posts: Post[]
```

#### 4.4 Function Overload Utilities

```typescript
// Overloaded function type extraction
type Overloads<T> = T extends {
  (...args: infer A1): infer R1
  (...args: infer A2): infer R2
  (...args: infer A3): infer R3
} ? [A1, R1] | [A2, R2] | [A3, R3]
  : T extends {
    (...args: infer A1): infer R1
    (...args: infer A2): infer R2
  } ? [A1, R1] | [A2, R2]
    : T extends (...args: infer A) => infer R
      ? [A, R]
      : never

// Primitive overload pattern
function process(value: string): string
function process(value: number): number
function process(value: boolean): boolean
function process(value: string | number | boolean): string | number | boolean {
  if (typeof value === 'string') return value.toUpperCase()
  if (typeof value === 'number') return value * 2
  return !value
}
```

#### 4.5 Path Utilities

```typescript
// Type-safe path builder for nested objects
type Path<T, Prefix extends string = ''> = {
  [K in keyof T & string]: T[K] extends Record<string, any>
    ? `${Prefix}${K}` | Path<T[K], `${Prefix}${K}.`>
    : `${Prefix}${K}`
}[keyof T & string]

type DeepObj = { user: { profile: { name: string; age: number }; settings: { theme: string } } }
type Paths = Path<DeepObj>
// 'user' | 'user.profile' | 'user.profile.name' | 'user.profile.age' | 'user.settings' | 'user.settings.theme'

// Type-safe get function
function get<T, P extends Path<T>>(obj: T, path: P): PathValue<T, P>
function get(obj: any, path: string): unknown {
  return path.split('.').reduce((acc, part) => acc?.[part], obj)
}

type PathValue<T, P extends string> =
  P extends keyof T ? T[P] :
  P extends `${infer K}.${infer Rest}`
    ? K extends keyof T ? PathValue<T[K], Rest> : never
    : never

// Type-safe set function (returns new object)
type SetValue<T, P extends string, V> =
  P extends keyof T ? Omit<T, P> & { [K in P]: V } :
  P extends `${infer K}.${infer Rest}`
    ? K extends keyof T ? Omit<T, K> & { [P in K]: SetValue<T[K], Rest, V> } : never
    : never
```

---

### 5. Type Inference Patterns

#### 5.1 How TS Infers

```typescript
// Contextual inference — inferred from how a value is used
window.addEventListener('click', (event) => {
  // event: MouseEvent (inferred from addEventListener signature)
})

// Return type inference — inferred from return expressions
function createUser(name: string) {
  return { id: crypto.randomUUID(), name, createdAt: new Date() }
  // return type: { id: string; name: string; createdAt: Date }
}

// Generic inference — inferred from argument types
function map<T, U>(arr: T[], fn: (item: T) => U): U[] {
  return arr.map(fn)
}
const lengths = map(['a', 'bb', 'ccc'], s => s.length)
// lengths: number[] (T=string, U=number)

// Best common type — for arrays/literals
const mixed = [1, 'hello', true]        // (string | number | boolean)[]
const nums = [1, 2, 3]                  // number[]
const tuple = [1, 'a'] as const         // readonly [1, 'a'] (literal)
```

#### 5.2 Controlling Inference with `NoInfer` (TS 5.4+)

```typescript
// NoInfer<T> — mark a type as "don't infer from here, just validate"
// Prevents TS from using this position for generic inference

// Without NoInfer: TS infers T from both parameters
function createPair<T>(first: T, second: T): [T, T] {
  return [first, second]
}
const pair = createPair('hello', 'world')
// T = string — fine, but what if we want to force the second param?

// With NoInfer: second parameter is only validated, not used for inference
function createValidatedPair<T>(
  first: T,
  second: NoInfer<T>,  // TS won't infer T from second
): [T, T] {
  return [first, second]
}

const validated = createValidatedPair('hello', 'world')  // ✅ T = string
// createValidatedPair('hello', 42)  // ❌ Error: 42 not assignable to string

// Practical: API key validation
function fetchResource<T extends string>(
  url: T,
  options: NoInfer<RequestInit>,
): Promise<Response> {
  return fetch(url, options)
}

// Practical: comparing against a set of valid values
function isOneOf<T, U extends T[]>(value: T, options: NoInfer<[...U]>): value is U[number] {
  return options.includes(value as any)
}
const x = Math.random() > 0.5 ? 'a' : 'b'
if (isOneOf(x, ['a', 'c', 'd'])) {
  // x narrowed to 'a' | 'c' | 'd'
}
```

#### 5.3 Const Assertions

```typescript
// `as const` — deep readonly, preserves literal types
const config = {
  api: 'https://api.example.com',
  timeout: 5000,
  features: ['auth', 'billing'],
} as const

// Without as const: { api: string; timeout: number; features: string[] }
// With as const: {
//   readonly api: 'https://api.example.com';
//   readonly timeout: 5000;
//   readonly features: readonly ['auth', 'billing'];
// }

// Practical: action types
export const ActionTypes = {
  SET_USER: 'SET_USER',
  DELETE_USER: 'DELETE_USER',
  UPDATE_USER: 'UPDATE_USER',
} as const

type ActionType = (typeof ActionTypes)[keyof typeof ActionTypes]
// ActionType = 'SET_USER' | 'DELETE_USER' | 'UPDATE_USER'

// Const assertions in function parameters
function border<T extends readonly [string, string, ...string[]]>(
  ...values: T
): Record<T[number], string> {
  const result = {} as Record<T[number], string>
  values.forEach(v => { result[v] = '' })
  return result
}
const b = border('top', 'right', 'bottom', 'left')
// Keys preserved as literal: { top: ''; right: ''; bottom: ''; left: '' }
```

#### 5.4 `satisfies` for Inference + Validation

```typescript
// Problem: type widening loses literal info
const routes = {
  home: '/',
  users: '/users/:id',
  settings: '/settings',
} as const satisfies Record<string, `/${string}`>
// routes.home = '/' (literal), type-checked to start with '/'

// Complex validation
type RGB = readonly [number, number, number]
type HSL = readonly [number, number, number]

type ColorConfig = Record<string, RGB | HSL | string>

const colors = {
  primary: [255, 0, 0] as const,
  secondary: '#00ff00' as const,
  accent: { hue: 240, sat: 100, light: 50 },
} satisfies ColorConfig

// colors.primary is typed as readonly [255, 0, 0] (narrow)
// colors.primary[0] = number (satisfies RGB)
```

#### 5.5 Inference from Discriminated Unions

```typescript
// Discriminated union with automatic narrowing
type ApiEvent =
  | { type: 'loading'; requestId: string }
  | { type: 'success'; data: unknown; duration: number }
  | { type: 'error'; error: Error; requestId: string }

function handleEvent(event: ApiEvent) {
  switch (event.type) {
    case 'loading':
      console.log(event.requestId)  // TS knows event has requestId
      break
    case 'success':
      console.log(event.data, event.duration)  // TS knows data + duration
      break
    case 'error':
      console.log(event.error.message, event.requestId)
      break
  }
}

// Inference from generic discriminated unions
type FormState<T> =
  | { status: 'idle' }
  | { status: 'dirty'; values: Partial<T> }
  | { status: 'submitting'; values: T }
  | { status: 'success'; response: T }
  | { status: 'error'; error: Error; values: Partial<T> }

function useFormState<T>() {
  const [state, setState] = useState<FormState<T>>({ status: 'idle' })
  return { state, setState } as const
}

const { state } = useFormState<{ name: string; email: string }>()
// When state.status === 'success', state.response is { name: string; email: string }
```

#### 5.6 Inferring Function Parameters and Return Types

```typescript
// Infer parameter types from function
function createApi<T extends Record<string, (...args: any[]) => any>>(api: T) {
  return api
}

const api = createApi({
  getUsers: () => fetch('/api/users').then(r => r.json()),
  getUser: (id: string) => fetch(`/api/users/${id}`).then(r => r.json()),
  createUser: (data: { name: string; email: string }) =>
    fetch('/api/users', { method: 'POST', body: JSON.stringify(data) }),
})

// api.getUser('123')  — T inferred as the full API interface
type ApiType = typeof api
// ApiType.getUser: (id: string) => Promise<any>

// Inferring event handler types
type EventHandler<Events extends Record<string, unknown[]>> = {
  [K in keyof Events]: (...args: Events[K]) => void
}

type MyEvents = {
  click: [x: number, y: number]
  keypress: [key: string, code: number]
  focus: []
}

type MyHandlers = EventHandler<MyEvents>
// {
//   click: (x: number, y: number) => void
//   keypress: (key: string, code: number) => void
//   focus: () => void
// }
```

---

### 6. Modules & Declaration Files

#### 6.1 Module Resolution Strategies

```
┌─────────────────────────────────────────────────────────────┐
│                 MODULE RESOLUTION STRATEGIES                  │
│                                                              │
│  node        — Node.js classic: looks at node_modules, .js   │
│                extension-agnostic, no exports map             │
│                                                              │
│  nodenext    — Node.js ESM/CJS aware: respects package.json  │
│  (TS 5.x)      exports, requires .js extension in imports,    │
│                conditional exports support                    │
│                                                              │
│  bundler     — For Vite/webpack/esbuild: like nodenext but   │
│  (TS 5.0+)     doesn't require extensions, more lenient       │
│                                                              │
│  RECOMMENDED: node16 or nodenext for Node.js projects         │
│  RECOMMENDED: bundler for frontend (Vite/Next.js/Turbopack)  │
└─────────────────────────────────────────────────────────────┘
```

```jsonc
// tsconfig.json — bundler (frontend projects)
{
  "compilerOptions": {
    "module": "ESNext",
    "moduleResolution": "bundler",
    "target": "ES2022",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true
  }
}

// tsconfig.json — Node.js ESM
{
  "compilerOptions": {
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "target": "ES2022",
    "verbatimModuleSyntax": true
  }
}
```

#### 6.2 Ambient Declarations

```typescript
// declare module — declare structure of npm packages without types
declare module 'untyped-library' {
  export function doSomething(input: string): number
  export const VERSION: string
  export interface Options {
    debug: boolean
    timeout: number
  }
}

// declare global — augment global scope
declare global {
  interface Window {
    __APP_CONFIG__: {
      apiUrl: string
      environment: 'development' | 'production' | 'staging'
    }
  }

  namespace NodeJS {
    interface ProcessEnv {
      NODE_ENV: 'development' | 'production' | 'test'
      DATABASE_URL: string
      API_KEY: string
    }
  }
}

// declare module with wildcard pattern
declare module '*.module.css' {
  const classes: { readonly [key: string]: string }
  export default classes
}

declare module '*.svg' {
  const content: React.FunctionComponent<React.SVGAttributes<SVGElement>>
  export default content
}

declare module '*.jpg' {
  const src: string
  export default src
}
```

#### 6.3 Augmenting Third-Party Modules

```typescript
// Augment a library's types (e.g., express Request)
import 'express'

declare module 'express' {
  interface Request {
    user?: {
      id: string
      role: 'admin' | 'user'
    }
  }
}

// Augment a library's interfaces
import { Session } from 'next-auth'

declare module 'next-auth' {
  interface Session {
    user: {
      id: string
      role: 'admin' | 'user'
      permissions: string[]
    }
  }
}

// Augment column types (e.g., Prisma or Drizzle)
import { ColumnType } from 'drizzle-orm'

declare module 'drizzle-orm' {
  interface ColumnTypeMap {
    'jsonb': typeof ColumnType
    'uuid': typeof ColumnType
  }
}
```

#### 6.4 `.d.ts` vs `.ts` — When to Use

```
.d.ts (declaration files)      .ts (source files)
─────────────────────────      ─────────────────
Pure type definitions          Contains runtime code
Library public API             Application source
Ambient declarations           Exports + implementations
No import/export (ambient)     Always has import/export
declare everything             Just write normally

Rule: Write .ts with `isolatedModules: true`.
      Generate .d.ts via `declaration: true`.
      Only write .d.ts manually for ambient declarations.
```

```typescript
// Manual .d.ts example: globals.d.ts
// No import/export allowed in ambient .d.ts files with triple-slash

/// <reference types="node" />
/// <reference path="./custom-types.d.ts" />

declare namespace Express {
  interface Request {
    user?: { id: string; role: string }
  }
}

// Triple-slash directives (avoid when possible — use tsconfig paths)
/// <reference path="./other-types.d.ts" />
/// <reference types="vite/client" />
/// <reference lib="es2022" />
```

#### 6.5 Publishing TypeScript Packages

```jsonc
// package.json for a TypeScript library
{
  "name": "@org/my-library",
  "version": "1.0.0",
  "main": "./dist/index.js",           // CJS entry
  "module": "./dist/index.mjs",         // ESM entry
  "types": "./dist/index.d.ts",         // Declaration entry
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",     // TypeScript entry
      "import": "./dist/index.mjs",     // ESM
      "require": "./dist/index.js"      // CJS
    },
    "./utils": {
      "types": "./dist/utils.d.ts",
      "import": "./dist/utils.mjs",
      "require": "./dist/utils.js"
    },
    "./package.json": "./package.json"
  },
  "files": ["dist/**"],
  "sideEffects": false
}
```

#### 6.6 Declaration Maps

```jsonc
// tsconfig.json
{
  "compilerOptions": {
    "declaration": true,          // Generate .d.ts files
    "declarationMap": true,       // Source maps for .d.ts (goto definition works)
    "sourceMap": true             // Source maps for .js
  }
}
// declarationMap: true allows users to "Go to Definition" and land on your .ts source
// instead of the generated .d.ts — critical for good developer experience
```

---

### 7. Strictness & Configuration

#### 7.1 `strict: true` Breakdown

```typescript
// strict: true enables ALL of these:
{
  "strict": true,                    // Enables all below
  /* Individual flags (don't set manually if strict: true): */
  "strictNullChecks": true,          // null/undefined not assignable to everything
  "strictFunctionTypes": true,       // Bivariant parameter check for function types
  "strictBindCallApply": true,       // Typed bind/call/apply
  "strictPropertyInitialization": true,  // Class properties must be initialized
  "noImplicitAny": true,             // Error on implicit any
  "noImplicitThis": true,            // Error on implicit any for this
  "alwaysStrict": true,              // "use strict" in output
}
```

```typescript
// strictNullChecks — THE most impactful flag
// Without: const el = document.getElementById('root')  // HTMLElement
// With:    const el = document.getElementById('root')  // HTMLElement | null

// strictFunctionTypes — catches unsafe function assignments
function fn(x: string) { return x.length }
type Fn = (x: string | number) => number
// Without strictFunctionTypes: fn is assignable to Fn (unsafe)
// With strictFunctionTypes: fn NOT assignable to Fn (safe — string | number doesn't extend string)

// strictBindCallApply — types apply/call correctly
function add(a: number, b: number): number { return a + b }
add.apply(null, [1, 2])  // ✅
// add.apply(null, [1, '2'])  // ❌ with strictBindCallApply

// strictPropertyInitialization — must initialize in constructor
class UserService {
  private client: DatabaseClient
  // ❌ Error: Property 'client' has no initializer (with strictPropertyInitialization)
  constructor() {
    this.client = new DatabaseClient()
  }
}

// noImplicitThis — catch this being used without context
function onClick() {
  console.log(this)  // ❌ Error: 'this' implicitly has type 'any'
}
```

#### 7.2 Additional Strict Flags

```typescript
{
  // exactOptionalPropertyTypes — optional means "missing" NOT "undefined"
  "exactOptionalPropertyTypes": true,
  // { foo?: string } means foo can be missing, but if present must be string (not undefined)

  // noUncheckedIndexedAccess — access to indexed types includes undefined
  "noUncheckedIndexedAccess": true,
  // const arr: string[] = ['a', 'b']
  // arr[0]  // string | undefined with this flag

  // noPropertyAccessFromIndexSignature — forces bracket notation for index signatures
  "noPropertyAccessFromIndexSignature": true,
  // const obj: { [key: string]: string } = { a: '1' }
  // obj.a  // ❌ — must use obj['a']

  // noUnusedLocals / noUnusedParameters — catch dead code
  "noUnusedLocals": true,
  "noUnusedParameters": true,

  // noFallthroughCasesInSwitch — prevent accidental fallthrough
  "noFallthroughCasesInSwitch": true,

  // exactOptionalPropertyTypes — stricter optional semantics
  "exactOptionalPropertyTypes": true
}
```

#### 7.3 Paths, Base URL, Root/Out Dir

```jsonc
{
  "compilerOptions": {
    "baseUrl": ".",                     // Base for non-relative imports
    "rootDir": "src",                   // Source root
    "outDir": "dist",                   // Output directory
    "paths": {
      "@/*": ["./src/*"],               // import { x } from '@/utils'
      "@components/*": ["./src/components/*"],
      "@lib/*": ["./src/lib/*"],
      "@types/*": ["./src/types/*"],
      "@features/*": ["./src/features/*"]
    }
  }
}
```

#### 7.4 Module Resolution Decision

```
Node.js app?
  ├── ESM (package.json: "type": "module") → "module": "NodeNext"
  └── CJS → "module": "commonjs" (with "moduleResolution": "node")

Frontend app?
  ├── Vite/Next.js/Turbopack → "module": "ESNext", "moduleResolution": "bundler"
  └── webpack → "module": "ESNext", "moduleResolution": "bundler"

Library author?
  ├── Want dual CJS/ESM → "module": "NodeNext" + build step
  └── Pure ESM → "module": "NodeNext", "type": "module" in package.json
```

#### 7.5 Project References (Monorepo)

```jsonc
// tsconfig.json — root (references all projects)
{
  "files": [],
  "references": [
    { "path": "./packages/core" },
    { "path": "./packages/ui" },
    { "path": "./apps/web" },
    { "path": "./apps/api" }
  ]
}

// packages/core/tsconfig.json
{
  "compilerOptions": {
    "composite": true,                // Required for project references
    "declaration": true,
    "declarationMap": true,
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*"]
}

// apps/web/tsconfig.json
{
  "compilerOptions": {
    "composite": true,
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*"],
  "references": [
    { "path": "../../packages/core" },
    { "path": "../../packages/ui" }
  ]
}
```

---

### 8. Error Handling with Types

#### 8.1 Result Pattern

```typescript
// Result<T, E> — typed error handling WITHOUT exceptions
type Result<T, E = Error> =
  | { success: true; value: T }
  | { success: false; error: E }

// Helper constructors
function ok<T, E = never>(value: T): Result<T, E> {
  return { success: true, value }
}

function fail<T = never, E = Error>(error: E): Result<T, E> {
  return { success: false, error }
}

// Usage: never throw, always return Result
async function fetchUser(id: string): Promise<Result<User, ApiError>> {
  try {
    const response = await fetch(`/api/users/${id}`)
    if (!response.ok) return fail(new ApiError(response.statusText, response.status))
    const data = await response.json()
    return ok(data as User)
  } catch (error) {
    return fail(new ApiError('Network error', 0))
  }
}

// Consumer — must handle both cases
async function displayUser(id: string) {
  const result = await fetchUser(id)
  if (result.success) {
    renderUser(result.value)  // TS knows value is User
  } else {
    showError(result.error)   // TS knows error is ApiError
  }
}

// Result combinator functions
function map<T, U, E>(result: Result<T, E>, fn: (value: T) => U): Result<U, E> {
  return result.success ? ok(fn(result.value)) : result
}

function flatMap<T, U, E>(result: Result<T, E>, fn: (value: T) => Result<U, E>): Result<U, E> {
  return result.success ? fn(result.value) : result
}

// Result.all — aggregate multiple results
function all<T extends readonly unknown[], E>(
  results: { [K in keyof T]: Result<T[K], E> },
): Result<{ [K in keyof T]: T[K] }, E> {
  const values: unknown[] = []
  for (const result of results) {
    if (!result.success) return result as Result<{ [K in keyof T]: T[K] }, E>
    values.push(result.value)
  }
  return ok(values as { [K in keyof T]: T[K] })
}
```

#### 8.2 Either/Option/Maybe Monads

```typescript
// Option — maybe has a value (no null/undefined)
type Option<T> = Some<T> | None<T>

interface Some<T> { type: 'some'; value: T }
interface None<T> { type: 'none' }

function some<T>(value: T): Option<T> {
  return { type: 'some', value }
}

function none<T = never>(): Option<T> {
  return { type: 'none' } as None<T>
}

function mapOption<T, U>(opt: Option<T>, fn: (value: T) => U): Option<U> {
  return opt.type === 'some' ? some(fn(opt.value)) : none()
}

function flatMapOption<T, U>(opt: Option<T>, fn: (value: T) => Option<U>): Option<U> {
  return opt.type === 'some' ? fn(opt.value) : none()
}

// Practical: safe object access
function getOption<T, K extends keyof T>(obj: T, key: K): Option<T[K]> {
  return key in obj ? some(obj[key]) : none()
}

// Practical: safe array access
function headOption<T>(arr: readonly T[]): Option<T> {
  return arr.length > 0 ? some(arr[0]) : none()
}

// Unwrap with default
function getOrElse<T>(opt: Option<T>, defaultValue: T): T {
  return opt.type === 'some' ? opt.value : defaultValue
}
```

#### 8.3 Typed Errors — Discriminated Union Error Types

```typescript
// Discriminated error types
type AppError =
  | { type: 'validation'; field: string; message: string }
  | { type: 'not_found'; resource: string; id: string }
  | { type: 'unauthorized'; message: string }
  | { type: 'rate_limited'; retryAfter: number }
  | { type: 'network'; cause: string }
  | { type: 'internal'; message: string }

function handleError(error: AppError): string {
  switch (error.type) {
    case 'validation':
      return `Field ${error.field}: ${error.message}`
    case 'not_found':
      return `${error.resource} with id ${error.id} not found`
    case 'unauthorized':
      return `Access denied: ${error.message}`
    case 'rate_limited':
      return `Too many requests. Retry after ${error.retryAfter}s`
    case 'network':
      return `Network error: ${error.cause}`
    case 'internal':
      return `Internal error: ${error.message}`
    default:
      return exhaustive(error)
  }
}

// Wrapping fetch with typed errors
async function apiFetch<T>(
  url: string,
  options?: RequestInit,
): Promise<Result<T, AppError>> {
  try {
    const response = await fetch(url, options)

    if (response.status === 429) {
      const retryAfter = parseInt(response.headers.get('Retry-After') ?? '5')
      return fail({ type: 'rate_limited', retryAfter })
    }
    if (response.status === 401 || response.status === 403) {
      return fail({ type: 'unauthorized', message: response.statusText })
    }
    if (response.status === 404) {
      return fail({ type: 'not_found', resource: url, id: url })
    }
    if (!response.ok) {
      return fail({ type: 'internal', message: response.statusText })
    }

    const data = await response.json()
    return ok(data as T)
  } catch (e) {
    return fail({ type: 'network', cause: (e as Error).message })
  }
}
```

#### 8.4 `never` Type for Exhaustive Checks

```typescript
// never — the impossible type
// Use for exhaustive switch/if-else checks

function exhaustive(value: never): never {
  throw new Error(`Unhandled case: ${value}`)
}

// Exhaustive check with switch
type Circle = { kind: 'circle'; radius: number }
type Square = { kind: 'square'; side: number }
type Triangle = { kind: 'triangle'; base: number; height: number }

type Shape = Circle | Square | Triangle  // add new variant → compiler error!

function area(shape: Shape): number {
  switch (shape.kind) {
    case 'circle':   return Math.PI * shape.radius ** 2
    case 'square':   return shape.side ** 2
    case 'triangle': return (shape.base * shape.height) / 2
    default: return exhaustive(shape)  // Compiler error if new Shape variant added
  }
}

// Exhaustive check with if/else
function process(value: string | number | boolean): string {
  if (typeof value === 'string') return value.toUpperCase()
  if (typeof value === 'number') return value.toFixed(2)
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  return exhaustive(value)  // If new type joins the union, TS flags this
}

// Using never for type-level validation
// Check that a type is exactly what you expect
type Expect<T extends true> = T
type Equal<X, Y> = (<T>() => T extends X ? 1 : 2) extends <T>() => T extends Y ? 1 : 2
  ? true : false

// This fails at compile time if User is not { name: string; age: number }
type _UserShapeCheck = Expect<Equal<User, { name: string; age: number }>>
```

#### 8.5 Custom Type Guards

```typescript
// User-defined type guard — function that returns `value is T`
function isString(value: unknown): value is string {
  return typeof value === 'string'
}

function processValues(values: unknown[]) {
  const strings = values.filter(isString)  // string[] — TS infers from type guard
  const nums = values.filter((v): v is number => typeof v === 'number')
  // nums: number[]
}

// Complex guards with discriminated unions
type APIResponse = { status: 'ok'; data: unknown } | { status: 'error'; message: string }

function isOkResponse(response: APIResponse): response is { status: 'ok'; data: unknown } {
  return response.status === 'ok'
}

function handleResponse(response: APIResponse) {
  if (isOkResponse(response)) {
    console.log(response.data)  // TS knows
  } else {
    console.error(response.message)  // TS knows
  }
}

// Array element guard
function isDefined<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined
}

const maybeNumbers: (number | null)[] = [1, null, 3, null, 5]
const numbers: number[] = maybeNumbers.filter(isDefined)

// Async type guards
async function isStringAsync(value: unknown): Promise<value is string> {
  const result = await someCheck(value)
  return result
}
```

---

### 9. Performance Optimization

#### 9.1 Compiler Performance Tips

```
┌─────────────────────────────────────────────────────────────┐
│               TYPESCRIPT COMPILER PERFORMANCE                │
│                                                              │
│  MEASURE FIRST: tsc --generateTrace → analyze in Chrome      │
│  at chrome://tracing                                          │
│                                                              │
│  Fastest → Slowest:                                           │
│    tsc --noEmit (type-check only)                             │
│    tsc --build (incremental with project references)          │
│    tsc (full compilation)                                     │
│                                                              │
│  Common bottlenecks:                                          │
│  1. Large union types (1000+ members)                        │
│  2. Deeply nested recursive types                             │
│  3. Conditional type chains with many branches                │
│  4. Complex mapped types on large interfaces                  │
│  5. Many .d.ts files from node_modules                        │
└─────────────────────────────────────────────────────────────┘
```

```jsonc
{
  "compilerOptions": {
    // Speed optimizations
    "incremental": true,                    // Cache .tsbuildinfo
    "skipLibCheck": true,                   // Don't check .d.ts files
    "skipDefaultLibCheck": true,
    "isolatedModules": true,                // Ensure each file can be transpiled independently
    "verbatimModuleSyntax": true,           // Faster emit, no elision logic

    // Faster with exactOptionalPropertyTypes off
    // "exactOptionalPropertyTypes": false,

    // Use esbuild/swc for transpilation instead of tsc
    // tsconfig.json:
    // "tsc": { "transpileOnly": true }
  }
}
```

#### 9.2 Project References for Incremental Builds

```jsonc
// --build mode: only rebuild changed projects + their dependents
// npm script: "tsc -b" or "tsc --build"

// tsconfig.json (root)
{
  "files": [],
  "references": [
    { "path": "./packages/core" },
    { "path": "./packages/shared" },
    { "path": "./packages/ui" }
  ]
}

// Each package needs:
{
  "compilerOptions": {
    "composite": true,        // Required
    "declaration": true,      // Required
    "declarationMap": true,   // Helpful
    "outDir": "./dist",
    "rootDir": "./src",
    "tsBuildInfoFile": "./dist/.tsbuildinfo"  // Cache location
  }
}

// Build all: tsc -b tsconfig.json
// Build specific: tsc -b packages/core
// Clean: tsc -b --clean
```

#### 9.3 Type vs Interface Performance

```
DECISION: type vs interface (PERFORMANCE)
────────────────────────────────────────

interface: Cached by TS, faster for:
  - Object shapes
  - Extends/implement
  - Declaration merging
  - Large codebases

type: Computed each time, but necessary for:
  - Unions/intersections
  - Mapped/conditional types
  - Primitives/tuples
  - Utility types

RULE: Prefer interface for public API shapes.
      Prefer type for everything that can't be expressed as interface.
      Use type aliases for primitive aliases and complex expressions.
```

#### 9.4 Avoiding Excessive Type Instantiation

```typescript
// ❌ BAD: creates new type instantiation for every combination
type DeepMap<T, F> = {
  [K in keyof T]: T[K] extends object ? DeepMap<T[K], F> : F
}
// This is fine in isolation, but avoid using it in "hot" paths
// like function signatures that are called in many places

// ❌ BAD: deeply nested conditional types in function signatures
function process<T>(
  input: T,
): T extends string ? string : T extends number ? number : unknown {
  return input as any
}  // Every call site creates a new conditional evaluation

// ✅ GOOD: simplify by using overloads
function process(input: string): string
function process(input: number): number
function process(input: unknown): unknown {
  return input
}

// ✅ GOOD: use interfaces instead of intersection types for complex shapes
// ❌ type Complex = A & B & C & D & E
// ✅ interface Complex extends A, B, C, D, E {}

// ❌ BAD: huge union types in generic constraints
// function handle<T extends OneOf200Things>(val: T) { }

// ✅ GOOD: narrow the constraint
// function handle<T extends { type: string }>(val: T) { }
```

#### 9.5 Benchmarking Type-Checking Time

```bash
# Generate a trace of type-checking operations
npx tsc --generateTrace trace-output
# Open in Chrome at chrome://tracing, load the trace file

# Quick performance analysis
npx tsc --extendedDiagnostics

# Per-file check times
# Look for files with very high "Own time" — those are bottlenecks

# Using perf with VS Code
# 1. Open Developer: Typescript: Open TS Server Logs
# 2. Look for high "checkFile" times

# Tools
npm install -g typescript-performance
typescript-performance analyze --project tsconfig.json
```

---

### 10. Testing TypeScript

#### 10.1 Type Testing with `expect-type`

```typescript
// expect-type — assert types at compile time
import { expectTypeOf, type Equal } from 'expect-type'
// Available: "vitest", "tsd", or standalone "expect-type" package

// Basic assertions
expectTypeOf(42).toBeNumber()
expectTypeOf('hello').toBeString()
expectTypeOf(true).toBeBoolean()
expectTypeOf({}).toBeObject()
expectTypeOf([]).toBeArray()
expectTypeOf(undefined).toBeUndefined()

// Type equality
expectTypeOf<string>().toEqualTypeOf<string>()
expectTypeOf<'hello'>().not.toEqualTypeOf<string>()

// Generic assertions
function identity<T>(value: T): T { return value }
const result = identity('hello')
expectTypeOf(result).toEqualTypeOf<'hello'>()
expectTypeOf(result).not.toBeAny()

// Complex type assertions
type Result = ReturnType<() => { name: string; age: number }>
expectTypeOf<Result>().toHaveProperty('name')
expectTypeOf<Result>().toHaveProperty('age')
expectTypeOf<Result>().not.toHaveProperty('email')
```

#### 10.2 Testing with tsd

```typescript
// tsd — TypeScript Definition tests
// Install: pnpm add -D tsd
// Add to package.json: "tsd": { "directory": "test-d" }

// test-d/types.test-d.ts
import { expectType, expectError, expectNotType, expectAssignable } from 'tsd'
import { deepMerge, DeepPartial } from '../src/types'

// Test return type
const merged = deepMerge({ a: 1 }, { b: 2 })
expectType<{ a: number; b: number }>(merged)

// Test error cases
expectError(deepMerge(42, { b: 2 }))  // Should not accept numbers

// Test type narrowing
const partial: DeepPartial<{ name: string; age: number }> = { name: 'test' }
expectType<{ name?: string; age?: number }>(partial)

// Test assignability
expectAssignable<string>('hello')
expectNotType<string>(42)
```

#### 10.3 Testing Conditional Types

```typescript
// Type-level tests — compile-time verification
import { type Equal, type Expect } from '../types/test-utils'

// Type-level test utilities
export type Equal<X, Y> =
  (<T>() => T extends X ? 1 : 2) extends (<T>() => T extends Y ? 1 : 2)
    ? true
    : false

export type Expect<T extends true> = T

// Test IsString conditional type
type IsString<T> = T extends string ? true : false
type Test1 = Expect<Equal<IsString<'hello'>, true>>
type Test2 = Expect<Equal<IsString<42>, false>>
type Test3 = Expect<Equal<IsString<string>, true>>
type Test4 = Expect<Equal<IsString<undefined>, false>>

// Test DeepPartial
type TestDeepPartial = Expect<Equal<
  DeepPartial<{ a: { b: number; c: string } }>,
  { a?: { b?: number; c?: string } }
>>

// Test Extraction
type TestExtract = Expect<Equal<
  Extract<'a' | 'b' | 'c', 'a' | 'c'>,
  'a' | 'c'
>>

// Test utility correctness
type TestOmit = Expect<Equal<
  Omit<{ a: number; b: string; c: boolean }, 'a' | 'c'>,
  { b: string }
>>
```

#### 10.4 Testing Type Guards

```typescript
// Runtime + type-level testing for type guards
function isUser(value: unknown): value is { name: string; age: number } {
  if (typeof value !== 'object' || value === null) return false
  const obj = value as Record<string, unknown>
  return typeof obj.name === 'string' && typeof obj.age === 'number'
}

// Unit test the guard logic
describe('isUser type guard', () => {
  it('returns true for valid user objects', () => {
    expect(isUser({ name: 'Alice', age: 30 })).toBe(true)
  })

  it('returns false for malformed objects', () => {
    expect(isUser({ name: 'Alice' })).toBe(false)       // missing age
    expect(isUser({ name: 42, age: 30 })).toBe(false)   // wrong types
    expect(isUser(null)).toBe(false)                     // null
    expect(isUser('string')).toBe(false)                 // primitive
  })
})

// Type-level test for the guard
const testValue: unknown = { name: 'Alice', age: 30 }
if (isUser(testValue)) {
  expectTypeOf(testValue).toEqualTypeOf<{ name: string; age: number }>()
}
```

#### 10.5 Type-Level Test Patterns

```typescript
// Pattern: Type-level test suite
// Put these in a file like src/types/__tests__/type-tests.ts
// They're compile-time only — zero runtime impact

import { type Equal, type Expect } from '../test-utils'

// ── Utility Type Tests ──

// DeepPartial
type Input_DeepPartial = { a: { b: number; c: string }; d: boolean[] }
type Expected_DeepPartial = { a?: { b?: number; c?: string }; d?: boolean[] }
type _Test_DeepPartial = Expect<Equal<DeepPartial<Input_DeepPartial>, Expected_DeepPartial>>

// NonEmptyArray
type _Test_NonEmptyArray = Expect<Equal<
  NonEmptyArray<number>,
  [number, ...number[]]
>>

// Path utility
type TestObj = { user: { profile: { name: string } } }
type _Test_Path1 = Expect<Equal<Path<TestObj>, 'user' | 'user.profile' | 'user.profile.name'>>

// Brand types
type UserId = Brand<string, 'UserId'>
type _Test_Brand = Expect<Equal<UserId, string & { __brand: 'UserId' }>>
type _Test_BrandSafety = Expect<Equal<
  UserId extends string ? true : false,
  true
>>

// ── Function Type Tests ──

function identity<T>(value: T): T { return value }
type _Test_Identity_String = Expect<Equal<ReturnType<typeof identity<'hello'>>, 'hello'>>
type _Test_Identity_Number = Expect<Equal<ReturnType<typeof identity<42>>, 42>>

// ── Conditional Type Tests ──

type _Test_IsString = Expect<Equal<IsString<'x'>, true>>
type _Test_IsString_False = Expect<Equal<IsString<42>, false>>
type _Test_NonNullable = Expect<Equal<NonNullable<string | null | undefined>, string>>
```

---

### 11. Migration Strategy

#### 11.1 JS to TS Gradual Migration

```jsonc
// Step 1: Add TypeScript with lenient settings
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowJs": true,                    // Accept .js files
    "checkJs": false,                   // Don't type-check .js yet
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": false,                    // Be lenient at first
    "noEmit": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"]
}
```

```typescript
// Step 2: Add // @ts-check to individual .js files you want to validate
// src/utils/format.js
// @ts-check

/** @param {string} name */
export function greet(name) {
  return `Hello, ${name}`
}

/** @typedef {{ id: string; name: string; age: number }} User */

/** @type {(users: User[], id: string) => User | undefined} */
export function findUser(users, id) {
  return users.find(u => u.id === id)
}
```

```typescript
// Step 3: Rename .js → .ts incrementally (file by file)
// Use `any` as escape hatch during migration
function legacyFunction(input: any): any {
  return input
}

// Step 4: Enable strict flags one by one
// Order: noImplicitAny → strictNullChecks → strictFunctionTypes → strict: true
```

#### 11.2 Strict Mode Rollout — Step by Step

```
WEEK 1:  allowJs: true, checkJs: false, noImplicitAny: false
WEEK 2:  noImplicitAny: true (fix implicit anys)
WEEK 3:  strictNullChecks: true (fix null/undefined issues)
WEEK 4:  strictBindCallApply: true
WEEK 5:  strictFunctionTypes: true
WEEK 6:  strictPropertyInitialization: true
WEEK 7:  noImplicitThis: true
WEEK 8:  strict: true (all of above)
WEEK 9:  noUncheckedIndexedAccess: true
WEEK 10: exactOptionalPropertyTypes: true
WEEK 11: noUnusedLocals: true, noUnusedParameters: true
WEEK 12: noFallthroughCasesInSwitch: true
```

#### 11.3 Third-Party Library Types

```bash
# Install type definitions for popular packages
npm install -D @types/react
npm install -D @types/express
npm install -D @types/lodash
npm install -D @types/node

# Some packages bundle their own types:
#   react@19: has types built-in
#   next: has types built-in
#   vitest: has types built-in

# For packages without types, create a declaration file:
```

```typescript
// src/types/ambient.d.ts
declare module 'legacy-lib' {
  export function doSomething(input: string): number
  export const VERSION: string
}
```

#### 11.4 Migration Patterns for Common JS Patterns

```typescript
// Pattern: Dynamic require → typed import
// ❌ Before (JS)
const lib = require('some-lib')

// ✅ After (TS) — if ESM
import lib from 'some-lib'

// ✅ After (TS) — if CJS (with esModuleInterop)
import lib = require('some-lib')

// Pattern: Default exports
// ❌ Before (JS)
module.exports = class UserService { /**/ }

// ✅ After (TS)
export default class UserService { /**/ }

// Pattern: CommonJS interop
// ❌ Before (JS)
const { readFile } = require('fs')

// ✅ After (TS ESM)
import { readFile } from 'node:fs'

// Pattern: module.exports as function
// ❌ Before (JS)
module.exports = function(input) { return input * 2 }

// ✅ After (TS)
export default function double(input: number): number {
  return input * 2
}

// Pattern: namespace patterns
// ❌ Before (JS — old pattern)
namespace MyApp {
  export class Helper {}
}

// ✅ After (TS — modern)
export class Helper {}
```

#### 11.5 Handling Common Migration Gotchas

```typescript
// 1. Optional parameters
// JS: function greet(name) { return `Hello ${name || 'World'}` }
// TS: function greet(name?: string): string { return `Hello ${name ?? 'World'}` }

// 2. Polymorphic functions
// JS: function clone(obj) { return JSON.parse(JSON.stringify(obj)) }
// TS: function clone<T>(obj: T): T { return JSON.parse(JSON.stringify(obj)) }

// 3. Dynamic property access
// JS: function get(obj, key) { return obj[key] }
// TS: function get<T, K extends keyof T>(obj: T, key: K): T[K] { return obj[key] }

// 4. Mixins / Composition
// Use intersection types or interface merging

// 5. this context
// JS: onclick = function() { console.log(this) }
// TS: onclick = (this: HTMLElement) => { console.log(this) }

// 6. Spread with unknown types
// Use Record<string, unknown> instead of {}
```

---

### 12. Patterns & Best Practices

#### 12.1 Functional Pipes with Types

```typescript
// Typed pipe — compose functions left to right
type PipeFn = {
  <A, B>(a: A, ab: (a: A) => B): B
  <A, B, C>(a: A, ab: (a: A) => B, bc: (b: B) => C): C
  <A, B, C, D>(a: A, ab: (a: A) => B, bc: (b: B) => C, cd: (c: C) => D): D
  <A, B, C, D, E>(a: A, ab: (a: A) => B, bc: (b: B) => C, cd: (c: C) => D, de: (d: D) => E): E
}

const pipe: PipeFn = (value: unknown, ...fns: ((x: unknown) => unknown)[]) => {
  return fns.reduce((acc, fn) => fn(acc), value)
}

// Usage
const result = pipe(
  'hello world',
  s => s.split(' '),
  arr => arr.map(w => w.toUpperCase()),
  arr => arr.join('_'),
)
// result: string — fully inferred

// Typed compose (right to left)
type ComposeFn = {
  <A, B, C>(bc: (b: B) => C, ab: (a: A) => B): (a: A) => C
  <A, B, C, D>(cd: (c: C) => D, bc: (b: B) => C, ab: (a: A) => B): (a: A) => D
}

// Typed identity
const identity = <T>(value: T): T => value

// Safe access chain
type SafeChain<T> = T | null | undefined
function prop<K extends string>(key: K) {
  return <T extends Record<K, any>>(obj: T): T[K] => obj[key]
}
```

#### 12.2 Builder Pattern with Generics

```typescript
// Type-safe builder with state tracking via generics
class URLBuilder<
  Scheme extends string = 'https',
  HasPath extends boolean = false,
  HasQuery extends boolean = false,
> {
  private parts: { scheme: string; host: string; path: string; query: Record<string, string> } = {
    scheme: 'https',
    host: '',
    path: '',
    query: {},
  }

  static create<H extends string>(host: H) {
    const builder = new URLBuilder()
    builder.parts.host = host
    return builder as URLBuilder<'https', false, false>
  }

  withScheme<S extends string>(scheme: S): URLBuilder<S, HasPath, HasQuery> {
    this.parts.scheme = scheme
    return this as any
  }

  withPath<P extends string>(path: P): URLBuilder<Scheme, true, HasQuery> {
    this.parts.path = path
    return this as any
  }

  withQuery<K extends string, V extends string>(
    key: K,
    value: V,
  ): URLBuilder<Scheme, HasPath, true> {
    this.parts.query[key] = value
    return this as any
  }

  build(): string {
    let url = `${this.parts.scheme}://${this.parts.host}`
    if (this.parts.path) url += `/${this.parts.path}`
    const qs = new URLSearchParams(this.parts.query).toString()
    if (qs) url += `?${qs}`
    return url
  }
}

// Usage
const url = URLBuilder.create('api.example.com')
  .withScheme('https')
  .withPath('users')
  .withQuery('page', '1')
  .withQuery('limit', '10')
  .build()
// url: 'https://api.example.com/users?page=1&limit=10'
```

#### 12.3 Repository Pattern with Typed Queries

```typescript
// Typed repository with query builder
interface Identifiable { id: string }

interface Query<T> {
  filter(predicate: (item: T) => boolean): Query<T>
  sort(comparator: (a: T, b: T) => number): Query<T>
  limit(n: number): Query<T>
  skip(n: number): Query<T>
  execute(): Promise<T[]>
}

class InMemoryQuery<T extends Identifiable> implements Query<T> {
  private filters: Array<(item: T) => boolean> = []
  private sorter: ((a: T, b: T) => number) | null = null
  private limitCount: number | null = null
  private skipCount: number = 0

  constructor(private data: T[]) {}

  filter(predicate: (item: T) => boolean): Query<T> {
    this.filters.push(predicate)
    return this
  }

  sort(comparator: (a: T, b: T) => number): Query<T> {
    this.sorter = comparator
    return this
  }

  limit(n: number): Query<T> {
    this.limitCount = n
    return this
  }

  skip(n: number): Query<T> {
    this.skipCount = n
    return this
  }

  async execute(): Promise<T[]> {
    let result = [...this.data]
    this.filters.forEach(f => { result = result.filter(f) })
    if (this.sorter) result.sort(this.sorter)
    if (this.skipCount) result = result.slice(this.skipCount)
    if (this.limitCount !== null) result = result.slice(0, this.limitCount)
    return result
  }
}

interface Repository<T extends Identifiable> {
  findById(id: string): Promise<T | null>
  findAll(): Query<T>
  save(entity: T): Promise<T>
  delete(id: string): Promise<void>
  count(): Promise<number>
}

class UserRepository implements Repository<User> {
  private users: User[] = []

  async findById(id: string): Promise<User | null> {
    return this.users.find(u => u.id === id) ?? null
  }

  findAll(): Query<User> {
    return new InMemoryQuery(this.users)
  }

  async save(entity: User): Promise<User> {
    const index = this.users.findIndex(u => u.id === entity.id)
    if (index >= 0) this.users[index] = entity
    else this.users.push(entity)
    return entity
  }

  async delete(id: string): Promise<void> {
    this.users = this.users.filter(u => u.id !== id)
  }

  async count(): Promise<number> {
    return this.users.length
  }
}
```

#### 12.4 Event Emitter with Typed Events

```typescript
// Type-safe event emitter
type EventMap = Record<string, unknown[]>

interface TypedEventEmitter<Events extends EventMap> {
  on<K extends keyof Events>(event: K, listener: (...args: Events[K]) => void): () => void
  emit<K extends keyof Events>(event: K, ...args: Events[K]): void
  once<K extends keyof Events>(event: K, listener: (...args: Events[K]) => void): void
  off<K extends keyof Events>(event: K, listener: (...args: Events[K]) => void): void
  removeAllListeners<K extends keyof Events>(event?: K): void
}

function createEventEmitter<Events extends EventMap>(): TypedEventEmitter<Events> {
  const listeners = new Map<keyof Events, Set<Function>>()

  return {
    on(event, listener) {
      if (!listeners.has(event)) listeners.set(event, new Set())
      listeners.get(event)!.add(listener)
      return () => listeners.get(event)?.delete(listener)
    },

    emit(event, ...args) {
      listeners.get(event)?.forEach(fn => fn(...args))
    },

    once(event, listener) {
      const wrapper = (...args: unknown[]) => {
        listener(...args)
        this.off(event, wrapper)
      }
      this.on(event, wrapper as any)
    },

    off(event, listener) {
      listeners.get(event)?.delete(listener)
    },

    removeAllListeners(event) {
      if (event) listeners.delete(event)
      else listeners.clear()
    },
  }
}

// Usage
type AppEvents = {
  userLogin: [userId: string, timestamp: number]
  userLogout: [userId: string]
  error: [error: Error, context?: string]
  dataUpdate: [data: { id: string; changes: Partial<User> }]
}

const emitter = createEventEmitter<AppEvents>()

// Auto-complete for event names and parameter types
const unsubscribe = emitter.on('userLogin', (userId, timestamp) => {
  console.log(`User ${userId} logged in at ${timestamp}`)
})

emitter.emit('userLogin', 'user_123', Date.now())  // ✅ correct args
// emitter.emit('userLogin', 42)  // ❌ Type error
```

#### 12.5 State Machine Types

```typescript
// Typed state machine
type StateMachine<State extends string, Event extends string> = {
  initial: State
  states: Record<State, {
    on: Partial<Record<Event, State>>
  }>
}

type MachineState<
  M extends StateMachine<any, any>,
  Current extends M['initial'] = M['initial']
> = {
  state: Current
  transition<E extends keyof M['states'][Current]['on']>(
    event: E,
  ): MachineState<M, M['states'][Current]['on'][E]>
  matches<S extends M['initial']>(...states: S[]): boolean
}

function createMachine<S extends string, E extends string>(
  config: StateMachine<S, E>,
): MachineState<StateMachine<S, E>, S> {
  let currentState = config.initial as S

  const machine: MachineState<any, any> = {
    get state() { return currentState },

    transition(event) {
      const stateDef = config.states[currentState]
      const nextState = stateDef.on[event as string]
      if (!nextState) throw new Error(`Invalid transition: ${currentState} via ${String(event)}`)
      currentState = nextState
      return machine
    },

    matches(...states) {
      return states.includes(currentState)
    },
  }

  return machine
}

// Usage
const paymentMachine = createMachine({
  initial: 'idle',
  states: {
    idle: { on: { START: 'processing' } },
    processing: { on: { SUCCESS: 'completed', FAIL: 'failed' } },
    completed: { on: { RESET: 'idle' } },
    failed: { on: { RETRY: 'processing', RESET: 'idle' } },
  },
})

paymentMachine.transition('START')
paymentMachine.matches('processing')  // true
paymentMachine.transition('SUCCESS')
paymentMachine.matches('completed')   // true
```

#### 12.6 API Client — Typed Fetch Wrapper

```typescript
// Typed API client
interface ApiClientOptions {
  baseUrl: string
  headers?: Record<string, string>
  credentials?: RequestCredentials
}

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface ApiResponse<T> {
  data: T
  status: number
  ok: boolean
}

class ApiClient {
  constructor(private options: ApiClientOptions) {}

  private async request<T>(
    method: HttpMethod,
    path: string,
    body?: unknown,
    options?: Partial<RequestInit>,
  ): Promise<ApiResponse<T>> {
    const url = `${this.options.baseUrl}${path}`
    const response = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...this.options.headers,
        ...options?.headers,
      },
      body: body ? JSON.stringify(body) : undefined,
      credentials: this.options.credentials,
      ...options,
    })

    const data = response.headers.get('content-type')?.includes('application/json')
      ? await response.json()
      : await response.text()

    return {
      data: data as T,
      status: response.status,
      ok: response.ok,
    }
  }

  get<T>(path: string): Promise<ApiResponse<T>> {
    return this.request<T>('GET', path)
  }

  post<T>(path: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>('POST', path, body)
  }

  put<T>(path: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>('PUT', path, body)
  }

  patch<T>(path: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.request<T>('PATCH', path, body)
  }

  delete<T>(path: string): Promise<ApiResponse<T>> {
    return this.request<T>('DELETE', path)
  }
}

// Typed endpoints with path parameters
interface Endpoint<TParams, TResponse> {
  build(params: TParams): string
  response: TResponse
}

// Usage
const api = new ApiClient({ baseUrl: 'https://api.example.com' })
const users = await api.get<User[]>('/users')
// users.data: User[]
// users.status: number
```

#### 12.7 Form State with Discriminated Unions

```typescript
// Form state as discriminated union — make illegal states unrepresentable
type FormState<T> =
  | { status: 'idle' }
  | { status: 'editing'; values: Partial<T>; errors: Partial<Record<keyof T, string>> }
  | { status: 'submitting'; values: T }
  | { status: 'validation_error'; values: Partial<T>; errors: Record<keyof T, string> }
  | { status: 'success'; response: unknown }
  | { status: 'error'; error: Error; previousValues: Partial<T> }

// Zod schema
import { z } from 'zod'

const userSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  email: z.string().email('Invalid email'),
  age: z.number().min(18, 'Must be 18+').max(120),
})

type UserForm = z.infer<typeof userSchema>  // { name: string; email: string; age: number }

// Form hook with discriminated union state
function useForm<T extends Record<string, unknown>>(schema: z.ZodSchema<T>) {
  const [state, setState] = useState<FormState<T>>({ status: 'idle' })

  const startEditing = (initial?: Partial<T>) => {
    setState({
      status: 'editing',
      values: initial ?? {} as Partial<T>,
      errors: {},
    })
  }

  const updateField = <K extends keyof T>(field: K, value: T[K]) => {
    if (state.status !== 'editing') return
    setState({
      ...state,
      values: { ...state.values, [field]: value },
    })
  }

  const submit = async () => {
    if (state.status !== 'editing') return

    const result = schema.safeParse(state.values)
    if (!result.success) {
      const errors: Record<string, string> = {}
      result.error.errors.forEach(err => {
        const path = err.path.join('.')
        errors[path] = err.message
      })
      setState({
        status: 'validation_error',
        values: state.values,
        errors: errors as Record<keyof T, string>,
      })
      return
    }

    setState({ status: 'submitting', values: result.data })

    try {
      const response = await submitToApi(result.data)
      setState({ status: 'success', response })
    } catch (error) {
      setState({
        status: 'error',
        error: error as Error,
        previousValues: state.values,
      })
    }
  }

  return { state, startEditing, updateField, submit } as const
}
```

#### 12.8 Redux/Zustand Store Types

```typescript
// Zustand store with typed actions and state
import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

interface AuthSlice {
  user: User | null
  token: string | null
  isLoading: boolean

  login: (email: string, password: string) => Promise<void>
  logout: () => void
  setUser: (user: User) => void
}

interface UIStore {
  sidebar: 'open' | 'closed'
  theme: 'light' | 'dark' | 'system'
  toasts: Toast[]

  toggleSidebar: () => void
  setTheme: (theme: 'light' | 'dark' | 'system') => void
  addToast: (toast: Toast) => void
  removeToast: (id: string) => void
}

// Compose slices
type AppStore = AuthSlice & UIStore

const useStore = create<AppStore>()(
  devtools(
    persist(
      (set, get) => ({
        // Auth slice
        user: null,
        token: null,
        isLoading: false,

        login: async (email, password) => {
          set({ isLoading: true })
          try {
            const response = await fetch('/api/auth/login', {
              method: 'POST',
              body: JSON.stringify({ email, password }),
            })
            const data = await response.json()
            set({ user: data.user, token: data.token, isLoading: false })
          } catch {
            set({ isLoading: false })
          }
        },

        logout: () => set({ user: null, token: null }),
        setUser: (user) => set({ user }),

        // UI slice (initialized inline for brevity)
        sidebar: 'open',
        theme: 'system',
        toasts: [],

        toggleSidebar: () => set(s => ({ sidebar: s.sidebar === 'open' ? 'closed' : 'open' })),
        setTheme: (theme) => set({ theme }),
        addToast: (toast) => set(s => ({ toasts: [...s.toasts, toast] })),
        removeToast: (id) => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })),
      }),
      { name: 'app-store' },
    ),
  ),
)

// Typed selectors
const useUser = () => useStore(s => s.user)
const useTheme = () => useStore(s => s.theme)
const useIsAuthenticated = () => useStore(s => s.user !== null)
```

#### 12.9 Next.js App Router Types

```typescript
// Next.js 15+ App Router types
import { type PageProps, type LayoutProps } from 'next'

// Page with params
// app/users/[id]/page.tsx
type UserPageProps = PageProps<{ id: string }>
// { params: { id: string }; searchParams: { [key: string]: string | string[] | undefined } }

export default async function UserPage({ params, searchParams }: UserPageProps) {
  const { id } = await params        // params is a Promise in Next.js 15
  const { page } = await searchParams // searchParams is a Promise in Next.js 15

  const user = await fetchUser(id)
  return <UserProfile user={user} />
}

// Layout with params
// app/users/[id]/layout.tsx
type UserLayoutProps = LayoutProps<{ id: string }>
// { params: { id: string }; children: React.ReactNode }

export default async function UserLayout({ params, children }: UserLayoutProps) {
  const { id } = await params
  return (
    <div>
      <UserNav userId={id} />
      {children}
    </div>
  )
}

// Route handler types
// app/api/users/route.ts
import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const page = searchParams.get('page')
  return NextResponse.json({ page })
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  return NextResponse.json(body, { status: 201 })
}

// Middleware
// middleware.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const token = request.cookies.get('token')
  const url = request.nextUrl.clone()

  if (!token && !url.pathname.startsWith('/login')) {
    url.pathname = '/login'
    return NextResponse.redirect(url)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*', '/profile/:path*'],
}
```

---

### 13. Workspace & Monorepo

#### 13.1 TypeScript Project References in Monorepo

```
monorepo/
├── tsconfig.json              # Root — references all projects
├── packages/
│   ├── core/
│   │   ├── tsconfig.json      # composite: true
│   │   ├── src/
│   │   └── dist/
│   ├── shared/
│   │   ├── tsconfig.json      # composite: true
│   │   └── src/
│   └── ui/
│       ├── tsconfig.json      # composite: true
│       ├── src/
│       └── dist/
├── apps/
│   ├── web/
│   │   ├── tsconfig.json      # references core, shared, ui
│   │   └── src/
│   └── api/
│       ├── tsconfig.json      # references core, shared
│       └── src/
└── package.json
```

```jsonc
// Root tsconfig.json
{
  "files": [],
  "references": [
    { "path": "./packages/core/tsconfig.json" },
    { "path": "./packages/shared/tsconfig.json" },
    { "path": "./packages/ui/tsconfig.json" },
    { "path": "./apps/web/tsconfig.json" },
    { "path": "./apps/api/tsconfig.json" }
  ]
}

// packages/core/tsconfig.json
{
  "compilerOptions": {
    "composite": true,
    "declaration": true,
    "declarationMap": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "tsBuildInfoFile": "./dist/.tsbuildinfo",
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"]
}
```

#### 13.2 Turborepo + TypeScript

```jsonc
// turbo.json — cached TypeScript build
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "inputs": ["src/**/*.ts", "tsconfig.json"],
      "outputs": ["dist/**"]
    },
    "typecheck": {
      "dependsOn": ["^build"],
      "inputs": ["src/**/*.ts", "tsconfig.json"]
    },
    "lint": {
      "dependsOn": ["^build"]
    },
    "test": {
      "dependsOn": ["build"],
      "inputs": ["src/**/*.ts", "test/**/*.ts"]
    }
  }
}

// package.json scripts
{
  "scripts": {
    "build": "turbo run build",
    "typecheck": "turbo run typecheck",
    "dev": "turbo run dev --parallel",
    "lint": "turbo run lint"
  }
}
```

#### 13.3 Shared Types Across Packages

```typescript
// packages/shared/src/types/index.ts
export interface User {
  id: string
  name: string
  email: string
  role: 'admin' | 'user' | 'viewer'
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}

export type ApiResponse<T> =
  | { ok: true; data: T; status: number }
  | { ok: false; error: { code: string; message: string }; status: number }

// packages/core/src/api.ts — consuming shared types
import type { User, PaginatedResponse, ApiResponse } from '@myorg/shared'

export async function getUsers(page: number): Promise<ApiResponse<PaginatedResponse<User>>> {
  const response = await fetch(`/api/users?page=${page}`)
  return response.json()
}
```

#### 13.4 Composite Projects

```jsonc
// composite: true — enables project references
// Side effect: enables incremental builds, declaration generation

{
  "compilerOptions": {
    "composite": true,
    "declaration": true,
    "declarationMap": true,
    "emitDeclarationOnly": true,    // Only emit .d.ts, not .js (use bundler for JS)
    "outDir": "./dist",
    "rootDir": "./src",
    "tsBuildInfoFile": "./dist/.tsbuildinfo"
  }
}
```

#### 13.5 Declaration Maps for Monorepo Navigation

```jsonc
{
  "compilerOptions": {
    "declaration": true,        // Generate .d.ts
    "declarationMap": true,     // Source maps back to .ts originals
    "sourceMap": true           // Source maps for .js
  }
}
// With declarationMap: "Go to Definition" in VS Code navigates from
// usage in apps/web → packages/core's .d.ts → packages/core's original .ts source
// Without: lands on the .d.ts file (much less useful)
```

---

### 14. File Convention

```
project/
├── src/
│   ├── types/                     # Shared type definitions
│   │   ├── api.ts                 # API response/request types
│   │   ├── models.ts              # Domain model types
│   │   ├── events.ts              # Event type definitions
│   │   ├── utilities.ts           # Utility type definitions
│   │   └── test-utils.ts          # Type-level test utilities (Expect, Equal)
│   │
│   ├── lib/                       # Pure utilities, third-party wrappers
│   │   ├── api-client.ts          # Typed HTTP client
│   │   ├── validation.ts          # Zod schemas
│   │   ├── db.ts                  # Database client
│   │   └── utils.ts               # General utilities
│   │
│   ├── features/                  # Feature modules (vertical slices)
│   │   ├── auth/
│   │   │   ├── types.ts           # Feature-specific types
│   │   │   ├── auth-service.ts    # Service logic
│   │   │   ├── auth-hooks.ts      # Feature hooks
│   │   │   └── index.ts           # Barrel
│   │   └── billing/
│   │       ├── types.ts
│   │       ├── billing-service.ts
│   │       └── index.ts
│   │
│   ├── config/                    # Configuration files
│   │   └── env.ts                 # Typed environment variables
│   │
│   ├── middleware/                # Middleware (if Express/Next.js)
│   │   ├── auth.ts
│   │   ├── rate-limit.ts
│   │   └── error-handler.ts
│   │
│   └── index.ts                   # Main export
│
├── test/                          # Test files
│   ├── types/                     # Type-level tests (.test-d.ts for tsd)
│   │   ├── types.test-d.ts
│   │   └── utilities.test-d.ts
│   ├── unit/                      # Unit tests
│   │   └── api-client.test.ts
│   └── integration/               # Integration tests
│
├── dist/                          # Build output (gitignored)
│
├── tsconfig.json
├── tsconfig.build.json            # Build-specific config (references)
├── tsconfig.node.json             # Node.js specific (if needed)
├── package.json
└── vitest.config.ts
```

**Naming conventions**:
- **Type files**: `types.ts` per feature, or `*.types.ts` for co-location
- **Type-level tests**: `*.test-d.ts` (tsd convention) or `type-tests.ts`
- **Utility types**: PascalCase in `utilities.ts` or per-category files
- **Declaration files**: `.d.ts` ONLY for ambient declarations (no `export`/`import`)
- **Test utilities**: `test-utils.ts` with `Expect`, `Equal` helpers

---

### 15. Anti-Patterns (with Fixes)

#### 15.1 Overusing `any`

```typescript
// ❌ BAD: any = opt-out of type checking
function process(input: any): any {
  return input * 2
}

// ✅ GOOD: unknown forces type narrowing
function process(input: unknown): unknown {
  if (typeof input === 'number') return input * 2
  return input
}

// ✅ BETTER: precise types
function process(input: number): number {
  return input * 2
}
```

#### 15.2 Using `as` Casting Instead of Proper Narrowing

```typescript
// ❌ BAD: type assertion bypasses the type system
const element = document.getElementById('root') as HTMLDivElement
const value = someFunc() as string

// ✅ GOOD: proper narrowing
const element = document.getElementById('root')
if (element instanceof HTMLDivElement) {
  element.innerHTML = 'Hello'
}

// ✅ BETTER: use optional chaining
document.getElementById('root')?.textContent
```

#### 15.3 Overly Complex Conditional Types

```typescript
// ❌ BAD: deeply nested conditional types
type DeepConditional<T> =
  T extends { a: infer A } ? 
    A extends { b: infer B } ?
      B extends { c: infer C } ?
        C extends string ? C :
          C extends number ? `${C}` :
            never :
        never :
      never :
    never

// ✅ GOOD: decompose into smaller, named types
type ExtractA<T> = T extends { a: infer A } ? A : never
type ExtractB<T> = T extends { b: infer B } ? B : never
type ExtractC<T> = T extends { c: infer C } ? C : never

type Simplified<T> =
  ExtractC<ExtractB<ExtractA<T>>> extends string
    ? ExtractC<ExtractB<ExtractA<T>>>
    : ExtractC<ExtractB<ExtractA<T>>> extends number
      ? `${ExtractC<ExtractB<ExtractA<T>>>}`
      : never
```

#### 15.4 Not Using Strict Mode

```typescript
// ❌ BAD: no strictNullChecks
// const element = document.getElementById('root')  // HTMLElement (wrong)
// element.innerHTML = ''  // Runtime crash if element is null

// ✅ GOOD: strict mode catches this
// const element = document.getElementById('root')  // HTMLElement | null
// if (element) element.innerHTML = ''  // ✅
```

#### 15.5 Ignoring TS Errors with `// @ts-ignore`

```typescript
// ❌ BAD: suppress errors instead of fixing them
// @ts-ignore
const data: string = someFunction()

// ✅ GOOD: fix the actual issue
const data: unknown = someFunction()
// Proper narrowing
```

#### 15.6 Circular Type References

```typescript
// ❌ BAD: circular reference (TS can fail with "Type instantiation is excessively deep")
type TreeNode<T> = {
  value: T
  children: TreeNode<T>[]  // Circular but acceptable (self-referencing)
}

// ❌ BAD: mutually circular (compiler error)
// A depends on B, B depends on A
interface TypeA { items: TypeB[] }
interface TypeB { parent: TypeA }  // ✅ Actually fine in TS

// ❌ BAD: extremely deep recursion
type DeepNested<T> = {
  [K in keyof T]: T[K] extends object ? DeepNested<T[K]> : DeepNested<T[K]>
}

// ✅ GOOD: limit recursion depth
type DeepNestedSafe<T, Depth extends number = 5> =
  Depth extends 0 ? T :
  {
    [K in keyof T]: T[K] extends object ? DeepNestedSafe<T[K], Prev[Depth]> : T[K]
  }
```

#### 15.7 Using `namespace` Instead of Modules

```typescript
// ❌ BAD: old-style namespaces (pre-ES6)
namespace MyApp {
  export interface User { name: string }
  export class UserService { /**/ }
}

// ✅ GOOD: ES modules
export interface User { name: string }
export class UserService { /**/ }
```

#### 15.8 Using `Function` Type

```typescript
// ❌ BAD: Function = any callable (unsafe)
function handler(fn: Function) {
  fn(1, 2, 3)  // any args, any return
}

// ✅ GOOD: specific function signature
function handler(fn: (...args: unknown[]) => unknown) {
  fn(1, 2, 3)
}

// ✅ BETTER: generic function parameter
function handler<T extends (...args: any[]) => any>(fn: T): ReturnType<T> {
  return fn()
}
```

#### 15.9 Not Using `readonly` for Immutable Data

```typescript
// ❌ BAD: mutable by default
interface Config { url: string; port: number }
const config: Config = { url: '...', port: 3000 }
config.url = 'hacked'  // Allowed!

// ✅ GOOD: readonly
interface Config { readonly url: string; readonly port: number }

// ✅ BETTER: Readonly utility
type SafeConfig = Readonly<{ url: string; port: number }>
```

#### 15.10 Large Union Types as Constraints

```typescript
// ❌ BAD: huge union type as constraint (slow compilation)
// type AllEvents = 'click' | 'focus' | 'blur' | ... 200 more
// function handle(event: AllEvents) { }

// ✅ GOOD: narrow constraint, wider type for data
function handle<E extends string>(event: E): void { }
// Usage: handle('click') — TS validates but doesn't expand the union

// ✅ BETTER: use a const array
const EVENTS = ['click', 'focus', 'blur'] as const
type EventType = (typeof EVENTS)[number]
function handle(event: EventType): void { }
```

---

### 16. Implementation Checklist

**Configuration Phase**:
- [ ] `strict: true` enabled (all strict flags)
- [ ] `moduleResolution` set correctly (`bundler` for frontend, `NodeNext` for Node)
- [ ] `paths` configured for clean `@/` imports
- [ ] `declaration: true` + `declarationMap: true` for libraries
- [ ] `skipLibCheck: true` enabled (unless publishing types)
- [ ] `verbatimModuleSyntax: true` for strict import handling
- [ ] `noUncheckedIndexedAccess: true` for array safety

**Type Design Phase**:
- [ ] Domain types defined as discriminated unions (make illegal states unrepresentable)
- [ ] `type` vs `interface` decision applied consistently
- [ ] Branded types for type-safe IDs and currencies
- [ ] `satisfies` operator used for validation + narrow inference
- [ ] Generic constraints properly bounded with `extends`
- [ ] No `any` anywhere in the codebase (exceptions only with comment justification)

**Advanced Types Usage**:
- [ ] Conditional types for type-level computations
- [ ] Mapped types for property transformations
- [ ] Template literal types for string parsing/manipulation
- [ ] Recursive types for nested data (JSON, trees)
- [ ] Variadic tuples for type-safe varargs
- [ ] `NoInfer` to control generic inference where needed
- [ ] `never` used for exhaustive switch/check patterns

**Patterns & Practices**:
- [ ] Result/Either pattern for error handling instead of exceptions
- [ ] Typed event emitter for pub/sub
- [ ] Typed API client with generics
- [ ] Builder pattern with state tracking via generics
- [ ] Exhaustive switch checks on discriminated unions
- [ ] Custom type guards for runtime validation

**Testing Phase**:
- [ ] Type-level tests via `expect-type` or `tsd`
- [ ] Conditional type outputs verified at compile time
- [ ] Type guard functions have both runtime + type-level tests
- [ ] Generic utility types tested with edge cases

**Performance Phase**:
- [ ] No circular type references
- [ ] No deeply nested conditional types in "hot" paths
- [ ] Complex types decomposed into named intermediates
- [ ] Interfaces preferred over intersections for complex shapes
- [ ] `tsc --generateTrace` analyzed for bottlenecks

**Monorepo Phase**:
- [ ] Project references configured with `composite: true`
- [ ] `tsc -b` used for incremental builds
- [ ] Shared types extracted to a common package
- [ ] Declaration maps enabled for navigation
- [ ] Turborepo or Nx caching for TypeScript builds

---

### 17. Common Troubleshooting

#### "Type instantiation is excessively deep and possibly infinite"

```
Cause: Recursive type that doesn't have a base case.
       Or: generic type used in a way that creates infinite expansion.

Fix:
  - Add a depth limit parameter with a default
  - Use interface instead of type for recursive shapes
  - Simplify conditional type chains
  - Use `extends` constraints to limit recursion

Example fix:
  // Before: type DeepPartial<T> = { [K in keyof T]?: DeepPartial<T[K]> }
  // Use interface break (if possible) or limit depth
```

#### "Expression produces a union type that is too complex to represent"

```
Cause: Large union type (>100,000 members) from conditional type distribution.

Fix:
  - Prevent distribution: wrap in [T] instead of bare T
  - Narrow the input type before passing to conditional
  - Use interface instead of type alias for the union
```

#### "Type 'X' is not assignable to type 'Y'"

```
Common causes:
  1. Missing discriminator in discriminated union
  2. Generics not properly constrained
  3. Excess property check (object literal with extra properties)
  4. Readonly vs mutable mismatch
  5. Branded type mismatch

Fix: Check the exact type difference. Use a helper:
  type Debug<T> = { [K in keyof T]: T[K] }
  // Hover over Debug<YourType> to see the full structure
```

#### "Cannot find module 'X' or its corresponding type declarations"

```
Causes:
  1. Missing @types/ package
  2. Wrong moduleResolution setting
  3. Missing tsconfig.json include/ paths
  4. No .d.ts for the module

Fix:
  - npm install -D @types/package-name
  - Check tsconfig moduleResolution matches your bundler
  - Create ambient declaration: declare module 'package-name'
```

#### "This expression is not callable" / "Type has no call signatures"

```
Cause: Union type where only some members are callable functions.

Fix: Narrow with typeof check or type guard.
  if (typeof x === 'function') x()
```

#### "Object is possibly 'undefined'" / "Object is possibly 'null'"

```
Cause: strictNullChecks enabled, TS detected nullable access.

Fix:
  - Use optional chaining: obj?.prop
  - Use nullish coalescing: obj ?? defaultValue
  - Use early return/throw guard
  - Use non-null assertion ONLY when you're 100% sure
```

#### "Type 'X' is not assignable to type 'NoInfer<X>'"

```
Cause: Misuse of NoInfer — trying to infer a type from a position marked NoInfer.

Fix: Move the inferred type to a position that IS used for inference.
      NoInfer should only "validate" not "determine" the type.
```

#### "All declarations of 'X' must have identical modifiers"

```
Cause: interface declaration merging with conflicting modifiers.

Fix: Ensure all declarations of the same interface have matching modifiers.
     Use type alias instead if merging isn't needed.
```

#### "An interface can only extend an object type or intersection of object types"

```
Cause: Trying to extend a type that is a union or primitive.

Fix: Use intersection (&) instead of extends.
  type Result = SomeUnion & { extra: string }
```

#### "A rest parameter must be of an array type"

```
Cause: Using ...rest with non-array type.

Fix: Use array/tuple type: ...args: T[] or ...args: [...T]
```

#### Debugging Types — Practical Tips

```typescript
// 1. Hover in VS Code — see inferred types (Cmd+I)

// 2. Use a type debugger — intentionally cause error to see the type
type Debug<T> = T
const x: Debug<YourComplexType> = {} as any
// Hover over the error to see the full expanded type

// 3. Type inspection at compile time
type Inspect<T> = { [K in keyof T]: T[K] }  // Expands mapped types

// 4. Compiler flags for debugging
// tsc --noEmit --extendedDiagnostics
// tsc --generateTrace /tmp/trace && open chrome://tracing

// 5. Use "Quick Info" in VS Code
// Right-click → "Go to Type Definition" to see the type

// 6. Self-documenting type errors
type Assert<T, U> = T extends U ? true : never
type _Check = Assert<YourType, ExpectedType>
// If fails, the error shows the mismatch
```

---

### Appendix: TypeScript Version Feature Matrix

```
TS 4.0: Variadic tuple types, labeled tuples
TS 4.1: Template literal types, key remapping in mapped types
TS 4.2: Leading/middle rest elements in tuples
TS 4.3: override keyword, import statement completions
TS 4.4: Control flow analysis for aliased conditions
TS 4.5: Awaited type, type imports in import type
TS 4.6: Control flow for destructured discriminated unions
TS 4.7: Optional variance annotations, module detection
TS 4.8: Improved intersection/union narrowing
TS 4.9: satisfies operator, unlisted property narrowing
TS 5.0: const type parameters, --moduleResolution bundler
TS 5.1: Improved return type inference for functions
TS 5.2: using declarations (Explicit Resource Management)
TS 5.3: Improved narrowing for switch-case
TS 5.4: NoInfer, import attributes, preserved narrowing
TS 5.5: Inferred type predicates, control flow narrowing
TS 5.6: Iterator helper types, improved isolatedDeclarations
TS 5.7: Path rewriting for --outDir, improved declaration emit
```

---

### Quick Reference: Common Patterns

```typescript
// Type-safe Object.keys
function keys<T extends Record<string, unknown>>(obj: T): (keyof T)[] {
  return Object.keys(obj) as (keyof T)[]
}

// Type-safe Object.entries
function entries<T extends Record<string, unknown>>(obj: T): { [K in keyof T]: [K, T[K]] }[keyof T][] {
  return Object.entries(obj) as any
}

// Type-safe hasOwnProperty
function hasOwn<T extends Record<string, unknown>, K extends string>(
  obj: T,
  key: K,
): obj is T & Record<K, unknown> {
  return Object.prototype.hasOwnProperty.call(obj, key)
}

// Type-safe Object.fromEntries
function fromEntries<T extends [PropertyKey, unknown][]>(
  entries: T,
): { [K in T[number] as K[0]]: K[1] } {
  return Object.fromEntries(entries) as any
}

// Type-safe JSON parse
function parseJSON<T>(json: string): Result<T, SyntaxError> {
  try {
    return ok(JSON.parse(json) as T)
  } catch (error) {
    return fail(error as SyntaxError)
  }
}
```
