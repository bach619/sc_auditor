---
name: paradigm-functional
description: Functional programming patterns: pure functions, immutability, algebraic data types, monads, functors, pattern matching, lazy evaluation, and implementations in Haskell, OCaml, Scala, Rust, and TypeScript
license: MIT
compatibility: opencode
metadata:
  audience: all-developers
  domain: paradigm
  paradigm: functional
  integrates_with: [paradigm-actor, backend-elixir, backend-python, database-event-sourcing]
---

## Paradigm Functional Programming Skill

### Core Principles
- **Pure functions**: Same input → same output; no side effects; referentially transparent
- **Immutability**: Never mutate; new copies on 'change'; persistent data structures (structural sharing)
- **Function composition**: f ∘ g; pipe(|>) and compose; point-free style where readable
- **Higher-order functions**: Functions that take/return functions; map, filter, reduce/fold
- **Recursion over iteration**: No loops; tail-call optimization; structural recursion on data types

### Algebraic Data Types (ADTs)
- **Sum types (OR)**: type Result = Ok a | Err e; exhaustive pattern matching; no null
- **Product types (AND)**: Records, tuples; combine values
- **Pattern matching**: Exhaustive compiler checks; destructuring; guards
- **Option/Maybe**: Some/None instead of null; map/flatMap for chaining
- **Result/Either**: Ok/Err or Right/Left; railway-oriented programming

### Type System Features
- **Generics/Polymorphism**: Parametric polymorphism; compile-time type checking
- **Type classes / Traits**: Interface-like behavior; ad-hoc polymorphism
- **Higher-kinded types**: Abstract over type constructors (Functor, Monad)
- **Phantom types**: Type parameter not used in value space; for compile-time constraints
- **GADTs**: Generalized ADTs; type refinement in pattern match

### Key Abstractions (Haskell-style)
- **Functor**: fmap / map; lift function into context
- **Applicative**: pure + <*>; apply function in context to value in context
- **Monad**: return + >>= (bind); sequencing computations with context
- **Monoid**: mempty + mappend; combine values with identity
- **Foldable/Traversable**: fold, traverse; reduce structure, transform with effects
- **Lens**: Compositional getters/setters; view/set/over; deep immutable update

### Language-Specific Patterns
- **Haskell**: do notation for monads; where/let bindings; laziness by default; STM for concurrency
- **Scala (FP style)**: Cats Effect (IO monad); ZIO (effect system); for-comprehensions; case classes + sealed traits
- **Rust (FP-ish)**: Iterator combinators; match exhaustion; Result/Option; ? operator; traits not type classes
- **TypeScript (FP libraries)**: effect-ts (Effect, Option, Either); fp-ts; pipe(data, fn1, fn2); never throw, return Either

### Design Patterns in FP
- **Railway-Oriented Programming**: Chain Either/Result; happy path on right; errors short-circuit
- **Reader Monad**: Dependency injection as function argument; pass context implicitly
- **State Monad**: Thread state through pure functions; State s a = s -> (a, s)
- **Free Monad**: Separate description from interpretation; for DSLs and testability
- **Tagless Final**: Encode DSL as type class; different interpreters; no intermediate AST

### Anti-Patterns
- Mutating function arguments (use return values)
- Throwing exceptions (use Result/Either)
- Deep nesting of callbacks (use flatMap/bind)
- Imperative-style loops (use recursion or combinators)
- Over-abstracting too early (concrete types are fine)

### Common Anti-Patterns (Expanded)

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Deeply nested monadic chains | Unreadable pyramid of `flatMap`/`bind` calls | Use `do`-notation (Haskell), `for`-comprehensions (Scala), or `pipe` (TypeScript) |
| Throwing exceptions in pure functions | Breaks referential transparency; callers unaware | Return `Either`/`Result` for expected errors; `Option`/`Maybe` for absence |
| Over-abstraction with type classes | Abstracting too early before patterns emerge concretely | Concrete types first; abstract only when the second use case appears |
| Lazy I/O mixing with pure functions | Side effects hidden in lazy values; debugging nightmare | Separate pure from effectful; use IO monad or explicit effect types |
| Mutating function arguments | Side effects make functions untestable and unpredictable | Return new values; use persistent/immutable data structures |
| Inefficient recursion without TCO | Stack overflow on large inputs | Use tail-call optimized recursive functions; verify with compiler flags |
| Using `null` instead of `Option`/`Maybe` | NullPointerException; missing null checks scattered everywhere | Never return null; wrap in `Option`/`Maybe`; use `Option.getOrElse` for defaults |
| Monad transformer stacks too deep | Complex types like `EitherT[OptionT[IO, *], Error, A]` become unreadable | Use effect systems (ZIO, Cats Effect) that handle stacking natively |
| Premature point-free style | Point-free code is terse but unreadable when taken too far | Use point-free when it clarifies; revert to explicit arguments when unclear |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| Stack overflow in recursive function | Missing tail-call optimization | Check if function is tail-recursive; verify compiler optimization | Add `@tailrec` annotation (Scala); restructure to tail-recursive form |
| `Either` chain short-circuits unexpectedly | `flatMap` on `Left`/`Err` skips remaining steps | Add logging at each `flatMap` step to see where it short-circuits | Use `Either.cond` with explicit error paths |
| Pattern match exhaustivity warning | Missing case in pattern match | Compiler warning shows uncovered patterns | Add wildcard `_` case or handle all variants |
| Lazy value not evaluating | Thunk not forced; dependency not triggered | Force evaluation with `deepseq` (Haskell) or explicit `.value` call | Use strict evaluation where needed; trace evaluation order |
| Type inference fails | Overly generic type; missing type annotation | Add explicit type signature to narrow inference | Annotate function signatures; use typed holes (`_`) to guide compiler |
| Performance degradation with immutable structures | Creating full copies for every "mutation" | Profile allocation rate; check for unnecessary copies | Use persistent data structures (structural sharing); `lens` for deep updates |

### Implementation Checklist

- [ ] All functions pure where possible (no side effects, deterministic)
- [ ] Immutable data structures used throughout; mutations isolated
- [ ] `Option`/`Maybe` used instead of `null` — zero `null` references
- [ ] `Either`/`Result` used for error handling — zero thrown exceptions in pure code
- [ ] Pattern matching is exhaustive (compiler warnings treated as errors)
- [ ] Tail-call optimization verified for recursive functions
- [ ] Side effects isolated to effect types (IO, Task, ZIO, Effect)
- [ ] Dependency injection via Reader monad or explicit parameter passing
- [ ] Algebraic Data Types used to model domain (sealed traits/case classes, discriminated unions)
- [ ] Monad laws verified for custom monadic types
- [ ] Property-based testing for algebraic laws (QuickCheck, ScalaCheck, fast-check)
- [ ] Documentation: type signatures serve as documentation; comments explain "why" not "what"
- [ ] Refactoring: equational reasoning used to simplify code without changing behavior
