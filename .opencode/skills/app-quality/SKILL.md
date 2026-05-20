---
name: app-quality
description: High-quality app evaluation framework — 12 dimension quality scoring, code quality, security, performance, accessibility, UX, architecture, testing, deployment readiness, observability, documentation
license: MIT
compatibility: opencode
metadata:
  audience: developers, code-reviewers, architects
  domain: general
  paradigm: quality-first
  capabilities:
    - code-quality-scoring
    - security-audit
    - performance-benchmarking
    - accessibility-evaluation
    - ux-review
    - architecture-assessment
    - testing-coverage
    - deployment-readiness
    - documentation-quality
    - typescript-strictness
    - error-handling-review
    - observability-check
  integrates_with:
    - security-audit
    - frontend-react
    - backend-nodejs
    - database-postgres
    - database-security
    - devops-platform-engineering
    - backend-go
    - typescript
---

# Aplikasi Kualitas Tinggi Standard Evaluasi

> Framework komprehensif 12-dimensi untuk menilai apakah suatu aplikasi memenuhi standar kualitas tinggi.
> Digunakan oleh @code-reviewer agent untuk evaluasi otomatis dan manual.

```
┌─────────────────────────────────────────────────────────────┐
│                    EVALUATION PIPELINE                       │
│                                                             │
│  Input: Source Code + Config + Dependencies + Build Output  │
│                                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────────┐  │
│  │ Static  │→ │ Dynamic │→ │ Security│→ │   Report     │  │
│  │ Analysis│  │ Analysis│  │ Audit   │  │   Generator  │  │
│  └─────────┘  └─────────┘  └─────────┘  └──────────────┘  │
│       │            │            │               │          │
│       └────────────┴────────────┴───────────────┘          │
│                         │                                   │
│                    ┌─────▼──────┐                           │
│                    │ 12-DIM     │                           │
│                    │ SCORING    │                           │
│                    └─────┬──────┘                           │
│                          │                                   │
│                    ┌─────▼──────┐                           │
│                    │ GRADE +    │                           │
│                    │ REPORT     │                           │
│                    └────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. The 12-Dimension Quality Framework

Setiap aplikasi dievaluasi dalam 12 dimensi independen. Masing-masing diberi skor 0-10, lalu dikalikan dengan bobot untuk mendapatkan skor akhir.

### Scoring Table

| # | Dimensi | Bobot | Fokus Utama |
|---|---------|-------|-------------|
| 1 | Code Quality & Maintainability | 15% | Readability, DRY, SOLID, complexity |
| 2 | Security Posture | 15% | OWASP Top 10, dependency, secrets |
| 3 | Performance & Core Web Vitals | 12% | LCP, INP, CLS, bundle, render |
| 4 | Accessibility (a11y) | 10% | WCAG AAA, semantic HTML, keyboard |
| 5 | Architecture & Design | 10% | Separation of concerns, patterns |
| 6 | Testing Maturity | 10% | Coverage, types, quality |
| 7 | UX & User Experience | 8% | Consistency, loading, error states |
| 8 | TypeScript Strictness | 6% | Strict mode, proper types |
| 9 | Error Handling | 5% | Graceful degradation, logging |
| 10 | Documentation | 4% | Code comments, README, API docs |
| 11 | Observability & Monitoring | 3% | Logs, metrics, traces, alerts |
| 12 | Deployment Readiness | 2% | CI/CD, env config, rollback |
| | **Total** | **100%** | |

### Scoring Flow

```
┌──────────────────┐
│  Start Evaluation│
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ For Each Dimension (D1 - D12):       │
│                                      │
│  ┌────────────┐  ┌───────────────┐   │
│  │ Run Checks │→ │ Score 0 - 10  │   │
│  └────────────┘  └───────┬───────┘   │
│                          │           │
│                          ▼           │
│  ┌──────────────────────────────┐    │
│  │ Weighted Score = Raw × Weight│    │
│  └──────────────────────────────┘    │
└──────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ Aggregate: Total = Σ Weighted Scores │
├──────────────────────────────────────┤
│ Grade: A(90-100) B(75-89) C(60-74)  │
│        D(40-59) F(<40)              │
├──────────────────────────────────────┤
│ Generate Report with Findings        │
└──────────────────────────────────────┘
```

---

## 2. Scoring Rubric

Setiap dimensi dinilai dengan skala berikut:

| Skor | Level | Deskripsi |
|------|-------|-----------|
| 10 | Sempurna | Best-in-class, reference implementation |
| 9 | Excellent | Production-ready, minor nitpicks only |
| 8 | Very Good | Solid, one or two minor improvements |
| 7 | Good | Solid with room for improvement |
| 6 | Adequate+ | Functional, noticeable issues |
| 5 | Adequate | Passable, needs work |
| 4 | Poor- | Significant issues in multiple areas |
| 3 | Poor | Major shortcomings |
| 2 | Critical- | Fundamentally broken |
| 1 | Critical | Needs complete rewrite |
| 0 | None | Not implemented at all |

### Scoring Rules

1. Start at 10 (perfect), subtract points for each failed check
2. Critical/security issues force max score of 4 regardless of other checks
3. If >50% checks fail, max score is 5
4. If >80% checks fail, max score is 2
5. Score is floored to nearest integer

---

## 3. Dimension 1: Code Quality & Maintainability (Bobot: 15%)

### Area Penilaian

#### 3.1 Readability (30% dari dimensi)
- [ ] Meaningful variable/function/class names (self-documenting)
- [ ] Consistent formatting (enforced by Prettier/dprint)
- [ ] No magic numbers — all constants named
- [ ] No magic strings — string literals extracted to constants
- [ ] Consistent casing convention per language (camelCase, PascalCase, etc.)
- [ ] Code reads like prose — clear intent without comments
- [ ] No deeply nested ternaries (max 1 level)
- [ ] Boolean variables named as predicates (`isLoading`, `hasError`, `canSubmit`)

#### 3.2 DRY Principle (20% dari dimensi)
- [ ] No duplicated code blocks (>3 lines repeated)
- [ ] Proper abstraction for repeated patterns
- [ ] Utility functions extracted for shared logic
- [ ] No copy-pasted API calls — use service layer
- [ ] Shared types/interfaces extracted
- [ ] Configuration values centralized (not scattered)

#### 3.3 SOLID Principles (20% dari dimensi)
- [ ] **Single Responsibility**: each class/function has one reason to change
- [ ] **Open/Closed**: open for extension, closed for modification
- [ ] **Liskov Substitution**: subtypes behave correctly when substituted
- [ ] **Interface Segregation**: small focused interfaces, not god objects
- [ ] **Dependency Inversion**: depend on abstractions, not concretions

#### 3.4 Complexity Control (15% dari dimensi)
- [ ] Cyclomatic complexity < 10 per function
- [ ] Nesting depth <= 3 levels
- [ ] Function length < 50 lines
- [ ] File length < 300 lines (except generated/config files)
- [ ] No deeply nested callbacks — use async/await or Promise chain

#### 3.5 Imports & Dependencies (10% dari dimensi)
- [ ] Imports organized (external → internal, absolute → relative)
- [ ] No unused imports (checked by ESLint `no-unused-vars`)
- [ ] No circular dependencies (checked by madge/dependency-cruiser)
- [ ] No barrel files that cause circular imports
- [ ] Dependencies version pinned (no `^` range in production)

#### 3.6 Code Smells (5% dari dimensi)
- [ ] No `any` type usage (unless documented exception)
- [ ] No `// @ts-ignore` or `// @ts-expect-error` (unless documented)
- [ ] No commented-out code
- [ ] No `console.log` in production code (use proper logger)
- [ ] No empty catch blocks
- [ ] No `TODO`/`FIXME`/`HACK` without ticket reference
- [ ] No mutable global state
- [ ] No direct DOM manipulation (in React/Svelte apps)

### Scoring Formula D1

```text
Let pass = number of checks passed
Let total = number of applicable checks
Let rawScore = (pass / total) * 10
Let finalScore = Math.min(10, Math.floor(rawScore * 10) / 10)
```

---

## 4. Dimension 2: Security Posture (Bobot: 15%)

### 4.1 OWASP Top 10 (2021) — 40% dari dimensi

#### A01 — Broken Access Control
- [ ] Proper authorization checks on all protected routes/endpoints
- [ ] Role-based access control (RBAC) implemented
- [ ] No IDOR vulnerabilities (user A cannot access user B's data)
- [ ] API endpoints validate ownership before returning data
- [ ] No direct object references without authorization

#### A02 — Cryptographic Failures
- [ ] Passwords hashed with bcrypt (cost >= 10) or argon2
- [ ] HTTPS enforced (HTTP redirects to HTTPS)
- [ ] No weak crypto (MD5, SHA1 for security contexts)
- [ ] TLS >= 1.2 configured on server
- [ ] Sensitive data encrypted at rest
- [ ] API keys/tokens stored securely (not in code)

#### A03 — Injection
- [ ] All SQL queries parameterized (no string concatenation)
- [ ] ORM used with parameterized queries (Prisma, TypeORM, Drizzle)
- [ ] No eval/Function constructor with user input
- [ ] No dangerouslySetInnerHTML (React) without sanitization
- [ ] Input validation on all user inputs (Zod, Valibot, Joi)
- [ ] No NoSQL injection vectors (MongoDB sanitization)

#### A04 — Insecure Design
- [ ] Rate limiting on auth endpoints
- [ ] Account lockout after N failed attempts
- [ ] CSRF tokens on mutating requests
- [ ] Secure password reset flow
- [ ] MFA available for sensitive actions

#### A05 — Security Misconfiguration
- [ ] CORS configured correctly (not `Access-Control-Allow-Origin: *`)
- [ ] Security headers set (CSP, X-Frame-Options, HSTS, etc.)
- [ ] Error messages don't leak stack traces to users
- [ ] Debug mode disabled in production
- [ ] Default credentials changed
- [ ] Unused routes/endpoints removed

#### A06 — Vulnerable Components
- [ ] `npm audit` passes with 0 critical vulnerabilities
- [ ] Dependencies regularly updated (Dependabot/Renovate configured)
- [ ] No known-vulnerable versions in use
- [ ] Snyk/CodeQL scanning active
- [ ] Lockfile committed (package-lock.json, yarn.lock)

#### A07 — Authentication Failures
- [ ] JWT with short expiry (< 15 min for access token)
- [ ] Refresh token rotation
- [ ] Secure cookie flags (httpOnly, secure, sameSite)
- [ ] Session invalidation on logout
- [ ] Password complexity requirements enforced
- [ ] No hardcoded credentials

#### A08 — Data Integrity Failures
- [ ] Signed data (JWT, HMAC) verified on every request
- [ ] No unsafe deserialization
- [ ] File upload validation (type, size, scan)
- [ ] CSP prevents script injection

#### A09 — Logging & Monitoring
- [ ] Security-relevant events logged (login, logout, admin actions)
- [ ] Failed auth attempts logged
- [ ] Audit trail for data changes
- [ ] Logs include user ID, timestamp, action
- [ ] Alerting on anomalous patterns

#### A10 — SSRF
- [ ] URL validation on external fetch requests
- [ ] Internal network addresses blocked
- [ ] Allowlist for outbound connections
- [ ] URL parsing done server-side, not user-supplied

### 4.2 Dependency Audit — 20% dari dimensi
- [ ] `npm audit` (or equivalent) — 0 critical, 0 high
- [ ] No deprecated packages actively in use
- [ ] Direct dependencies minimized (no unnecessary deps)
- [ ] Dev dependencies separated from production
- [ ] Snyk/Dependabot/CodeQL integrated in CI

### 4.3 Secrets Management — 20% dari dimensi
- [ ] No secrets in code (API keys, passwords, tokens)
- [ ] Environment variables for all secrets
- [ ] .env.example committed (with placeholder values)
- [ ] .env in .gitignore
- [ ] Secret scanning in CI (truffleHog, git-secrets)

### 4.4 HTTP Security — 20% dari dimensi
- [ ] Helmet.js (or equivalent) middleware
- [ ] Content-Security-Policy header configured
- [ ] X-Content-Type-Options: nosniff
- [ ] X-Frame-Options: DENY (or SAMEORIGIN)
- [ ] Strict-Transport-Security (HSTS) with preload
- [ ] Referrer-Policy: strict-origin-when-cross-origin
- [ ] Permissions-Policy configured

### Security Violation — Automatic Score Cap

```
IF any critical issue found (hardcoded secret, SQL injection, eval):
  D2 Score = MIN(D2 Score, 2)
  Flag as CRITICAL in report
```

---

## 5. Dimension 3: Performance & Core Web Vitals (Bobot: 12%)

### 5.1 Core Web Vitals — 30% dari dimensi

#### Largest Contentful Paint (LCP) — target < 2.5s
- [ ] LCP < 2.5s (field data / Lighthouse)
- [ ] No render-blocking resources above fold
- [ ] Optimized hero images (WebP/AVIF, responsive sizes)
- [ ] Preload key resources (fonts, hero image)
- [ ] Server-side rendering or static generation for above-fold content

#### Interaction to Next Paint (INP) — target < 200ms
- [ ] INP < 200ms (field data)
- [ ] No long tasks (>50ms) on main thread
- [ ] Event handlers not blocking UI
- [ ] Debounced/throttled expensive handlers (scroll, resize, input)
- [ ] Web Workers for CPU-intensive operations

#### Cumulative Layout Shift (CLS) — target < 0.1
- [ ] CLS < 0.1
- [ ] Explicit width/height on images and embeds
- [ ] No late-loading content that shifts layout
- [ ] Font swap behavior prevents layout shift
- [ ] Dynamic content has reserved space

### 5.2 Bundle Optimization — 25% dari dimensi
- [ ] Production JS bundle < 200KB (gzipped, initial load)
- [ ] Route-level code splitting implemented
- [ ] Component-level lazy loading for below-fold content
- [ ] No large dependencies without tree-shaking
- [ ] Bundle analysis tools used (next/bundle-analyzer, vite-bundle-visualizer)
- [ ] Dynamic imports for heavy libraries
- [ ] Moment.js avoided (use date-fns, dayjs, or native Intl)
- [ ] Lodash imported selectively (`lodash/get` not `lodash`)

### 5.3 Image & Asset Optimization — 15% dari dimensi
- [ ] Images in modern format (WebP/AVIF)
- [ ] Lazy loading for below-fold images (`loading="lazy"`)
- [ ] Responsive image sizes (`srcset` + `sizes`)
- [ ] Image CDN or optimization pipeline (next/image, Cloudinary)
- [ ] Fonts self-hosted or preloaded with `font-display: swap`
- [ ] SVGs optimized (removed unnecessary metadata)
- [ ] No oversized images (actual display size matched)

### 5.4 Caching Strategy — 10% dari dimensi
- [ ] HTTP caching headers (Cache-Control, ETag)
- [ ] CDN configured for static assets
- [ ] Service worker for offline capability / faster loads
- [ ] API responses cached where appropriate (Stale-While-Revalidate)
- [ ] Browser caching for static assets (immutable)

### 5.5 Rendering Optimization — 10% dari dimensi
- [ ] Server Components used for static content (Next.js App Router)
- [ ] Virtual list for long scrollable lists (TanStack Virtual, react-window)
- [ ] Debounced search inputs
- [ ] Infinite scroll with proper cleanup
- [ ] Memoization for expensive computations (useMemo, useCallback)
- [ ] Stable references for child component props

### 5.6 Database Performance — 10% dari dimensi
- [ ] N+1 queries detected and resolved
- [ ] Indexes on frequently queried columns
- [ ] Connection pooling configured
- [ ] Query optimization (EXPLAIN ANALYZE)
- [ ] Pagination for large result sets (no offset without limit)
- [ ] Eager loading for related data (not lazy)

### Performance Budget

```text
| Metric               | Target     | Critical |
|----------------------|------------|----------|
| LCP                  | < 2.5s     | > 4.0s   |
| INP                  | < 200ms    | > 500ms  |
| CLS                  | < 0.1      | > 0.25   |
| TTFB                 | < 800ms    | > 1.8s   |
| FCP                  | < 1.8s     | > 3.0s   |
| Total Bundle (gzip)  | < 200KB    | > 500KB  |
| TBT (Total Blocking) | < 200ms    | > 500ms  |
| SI (Speed Index)     | < 3.4s     | > 5.8s   |
```

---

## 6. Dimension 4: Accessibility (a11y) (Bobot: 10%)

### 6.1 WCAG AAA Compliance — 50% dari dimensi

#### Perceivable
- [ ] All non-text content has text alternatives (alt text on images)
- [ ] Captions provided for audio/video content
- [ ] Content can be presented without loss of information (responsive)
- [ ] Color is not the only means of conveying information
- [ ] Contrast ratio >= 7:1 for normal text (< 18px)
- [ ] Contrast ratio >= 4.5:1 for large text (>= 18px bold / >= 24px)
- [ ] Text can be resized up to 200% without loss of functionality
- [ ] Images of text not used (except logo)

#### Operable
- [ ] All functionality available via keyboard
- [ ] No keyboard traps
- [ ] Visible focus indicator (focus ring, minimum 2px)
- [ ] Focus order matches visual order
- [ ] Skip navigation link provided
- [ ] No flashing content > 3 times per second
- [ ] Time limits adjustable or disabled
- [ ] Motion animation triggered by interaction can be disabled

#### Understandable
- [ ] Language attribute set on `<html>` element
- [ ] Unusual words defined (glossary, tooltip)
- [ ] Abbreviations explained on first use
- [ ] Reading level appropriate for target audience
- [ ] Navigation consistent across pages
- [ ] Components with same functionality labelled consistently
- [ ] Error messages suggest correction (not just "Error")
- [ ] Form inputs have associated labels

#### Robust
- [ ] Semantic HTML elements used (`<nav>`, `<main>`, `<header>`, etc.)
- [ ] ARIA roles used correctly (no role="button" on `<button>`)
- [ ] ARIA labels provided where needed (`aria-label`, `aria-labelledby`)
- [ ] aria-live regions for dynamic content updates
- [ ] aria-expanded, aria-controls for expandable content
- [ ] aria-current for active navigation item
- [ ] Proper heading hierarchy (h1 → h2 → h3, no skips)
- [ ] Lists marked up as `<ul>`/`<ol>` not styled divs

### 6.2 Color & Contrast — 20% dari dimensi
- [ ] Color contrast ratio >= 7:1 for normal text (AAA)
- [ ] Color contrast ratio >= 4.5:1 for large text
- [ ] Focus indicator contrast >= 3:1
- [ ] No color-only indicators (error states include icon)
- [ ] Dark mode tested for contrast
- [ ] Color-blind safe palette considered

### 6.3 Focus Management — 15% dari dimensi
- [ ] Visible focus ring on all interactive elements
- [ ] Logical tab order (tabIndex only 0 or -1)
- [ ] Focus trapped in modals/dialogs (focus trap)
- [ ] Focus returned to trigger after modal close
- [ ] Skip to main content link (first focusable item)
- [ ] No tabIndex > 0

### 6.4 Screen Reader — 10% dari dimensi
- [ ] Proper heading hierarchy
- [ ] aria-live="polite/assertive" for dynamic content
- [ ] aria-hidden for decorative elements
- [ ] role="status" or role="alert" for notifications
- [ ] alt text on images (empty alt="" for decorative)
- [ ] Form error messages linked to inputs via aria-describedby

### 6.5 Reduced Motion — 5% dari dimensi
- [ ] `prefers-reduced-motion` respected
- [ ] Animations disabled or reduced when user prefers reduced motion
- [ ] CSS `@media (prefers-reduced-motion: reduce)` implemented
- [ ] No auto-playing animations without user control

### Testing Requirements
- [ ] Lighthouse a11y score = 100
- [ ] axe-core scan passes with 0 violations
- [ ] Manual keyboard navigation test passes
- [ ] Screen reader test (VoiceOver/NVDA/JAWS) passes
- [ ] Zoom to 200% — no content loss

---

## 7. Dimension 5: Architecture & Design (Bobot: 10%)

### 7.1 Component Decomposition — 20% dari dimensi
- [ ] Components have single responsibility
- [ ] No god components (> 500 lines) — split into smaller pieces
- [ ] Component hierarchy makes logical sense
- [ ] Presentational vs container separation (or hooks pattern)
- [ ] Composable small components over monolithic ones
- [ ] Atomic design or similar pattern followed

### 7.2 Data Flow — 15% dari dimensi
- [ ] Unidirectional data flow
- [ ] State management chosen appropriately for app complexity
- [ ] No prop drilling beyond 3 levels
- [ ] State co-located near where it's used
- [ ] Server state separated from UI state (TanStack Query, SWR)
- [ ] URL state for shareable/filterable views

### 7.3 Separation of Concerns — 15% dari dimensi
- [ ] Business logic separated from UI (services, hooks, utilities)
- [ ] API layer abstracted from components
- [ ] Database access layer separated from business logic
- [ ] Configuration separated from code
- [ ] No direct database calls in UI components

### 7.4 Scalability & Extensibility — 15% dari dimensi
- [ ] Architecture supports future features without rewrite
- [ ] Plugin/extension points where appropriate
- [ ] Feature flags in place for gradual rollout
- [ ] Module boundaries clear and enforced
- [ ] Low coupling between modules
- [ ] High cohesion within modules

### 7.5 Dependency Injection — 5% dari dimensi
- [ ] Dependencies injectable (constructor, parameter)
- [ ] No hardcoded service instances
- [ ] Easy to mock dependencies in tests
- [ ] IoC container used for complex apps (tsyringe, inversify)

### 7.6 API Design — 15% dari dimensi
- [ ] RESTful conventions followed (nouns, HTTP verbs)
- [ ] Consistent response format (wrapped: `{ data, meta, error }`)
- [ ] Proper HTTP status codes (200, 201, 204, 400, 401, 403, 404, 500)
- [ ] API versioning (`/api/v1/...`)
- [ ] Pagination with cursor or offset + limit
- [ ] Field selection for large resources
- [ ] Error responses include code, message, details

### 7.7 Error Boundaries — 10% dari dimensi
- [ ] React Error Boundaries at feature level
- [ ] Graceful fallback UI for each section
- [ ] Error boundary catches rendering errors
- [ ] Fallback component provides recovery action (retry)
- [ ] Async error handling with try/catch

### 7.8 Async Patterns — 5% dari dimensi
- [ ] Proper async/await usage (no unhandled promises)
- [ ] Request cancellation on unmount (AbortController)
- [ ] Loading states managed properly
- [ ] Race conditions handled (stale closure, stale responses)
- [ ] Concurrent request deduplication

---

## 8. Dimension 6: Testing Maturity (Bobot: 10%)

### 8.1 Unit Tests — 25% dari dimensi
- [ ] Coverage >= 80% (lines, branches, functions)
- [ ] Tests test behavior, not implementation
- [ ] No snapshot tests as primary testing strategy
- [ ] Edge cases tested (empty, null, invalid, boundary)
- [ ] Descriptive test names (should do X when Y)
- [ ] One assertion concept per test
- [ ] Mocks proper — not over-mocked or under-mocked
- [ ] No flaky tests (deterministic)

### 8.2 Integration Tests — 20% dari dimensi
- [ ] API endpoint tests with real/simulation database
- [ ] Database integration tests (CRUD operations)
- [ ] Auth flow tests (login, register, token refresh, logout)
- [ ] External service integration tests (with mocked HTTP)
- [ ] File upload/download flow tests

### 8.3 E2E Tests — 20% dari dimensi
- [ ] Critical user journeys covered (login, signup, main feature)
- [ ] Cross-browser testing (Playwright/Cypress)
- [ ] Mobile viewport testing
- [ ] API mocking for E2E stability
- [ ] Test data setup/teardown clean

### 8.4 Component Tests (Frontend) — 15% dari dimensi
- [ ] Component renders correctly (happy path)
- [ ] Component handles loading state
- [ ] Component handles error state
- [ ] Component handles empty/null state
- [ ] User interaction tests (click, type, submit)
- [ ] Accessibility tests (jest-axe)

### 8.5 Test Infrastructure — 10% dari dimensi
- [ ] Tests run in CI on every PR
- [ ] Lint + TypeScript check run before tests
- [ ] Coverage report generated and visible in PR
- [ ] Test failure blocks merge
- [ ] No test duplication (test files mirror source structure)

### 8.6 Performance Tests — 10% dari dimensi
- [ ] Lighthouse CI with performance budget
- [ ] Load test for critical endpoints (k6, autocannon)
- [ ] Bundle size regression test
- [ ] API response time regression test

---

## 9. Dimension 7: UX & User Experience (Bobot: 8%)

### 9.1 Loading States — 15% dari dimensi
- [ ] Skeletons/spinners displayed during data fetching
- [ ] Skeleton matches page layout (prevents CLS)
- [ ] Progress bar for multi-step operations
- [ ] Loading states for individual sections, not whole page
- [ ] Optimistic updates for predictable operations

### 9.2 Empty States — 15% dari dimensi
- [ ] Meaningful empty state message (not just "No data")
- [ ] CTA in empty state (what user should do next)
- [ ] Illustration or icon appropriate to context
- [ ] Empty state personalized when possible
- [ ] Filter/search empty results distinguished from no-data

### 9.3 Error States — 15% dari dimensi
- [ ] User-friendly error messages (no "500 Internal Server Error")
- [ ] Error messages explain what happened in plain language
- [ ] Retry action provided for recoverable errors
- [ ] Offline detection with offline message
- [ ] Network timeout handling
- [ ] Partial failure handled gracefully

### 9.4 Edge Cases — 15% dari dimensi
- [ ] Very long text handled (truncated, wrapped)
- [ ] Very short text handled
- [ ] Special characters handled
- [ ] Extremely rapid clicks handled (debounce)
- [ ] Double form submission prevented
- [ ] Back button behavior correct
- [ ] Browser refresh state preserved
- [ ] Tab visibility change handled

### 9.5 Responsive Design — 15% dari dimensi
- [ ] Mobile-first approach
- [ ] All breakpoints tested (320px, 480px, 768px, 1024px, 1440px)
- [ ] Touch targets >= 44px (WCAG)
- [ ] Horizontal scrolling avoided
- [ ] Forms usable on mobile (not zooming on input focus)
- [ ] Tables responsive (horizontal scroll or card layout)

### 9.6 Consistency — 10% dari dimensi
- [ ] Same patterns used across pages
- [ ] Consistent terminology
- [ ] Consistent button placement (primary action position)
- [ ] Consistent color usage (error always red, success always green)
- [ ] Consistent spacing and typography

### 9.7 Feedback & Notifications — 10% dari dimensi
- [ ] Toast/snackbar for action confirmation
- [ ] Successful operations show confirmation
- [ ] Form validation feedback on field blur
- [ ] Inline validation for real-time feedback
- [ ] Undo option for destructive actions

### 9.8 Internationalization — 5% dari dimensi
- [ ] Proper pluralization rules (ICU MessageFormat)
- [ ] Date/number formatting per locale
- [ ] Text direction support (LTR/RTL)
- [ ] String externalization (no hardcoded UI strings)

---

## 10. Dimension 8: TypeScript Strictness (Bobot: 6%)

### 10.1 TypeScript Configuration — 25% dari dimensi

```jsonc
// tsconfig.json — required strict settings
{
  "compilerOptions": {
    "strict": true,                    // enables all strict checks
    "noImplicitAny": true,             // error on implicit any
    "strictNullChecks": true,          // null/undefined are distinct
    "noUncheckedIndexedAccess": true,  // access on dynamic keys
    "noImplicitReturns": true,         // all paths must return
    "noFallthroughCasesInSwitch": true,// no fall-through
    "exactOptionalPropertyTypes": true,// exact optional types
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": false              // check .d.ts files
  }
}
```

- [ ] `strict: true` enabled
- [ ] `noImplicitAny: true` (or strict: true)
- [ ] `strictNullChecks: true`
- [ ] `noUncheckedIndexedAccess: true`
- [ ] `noImplicitReturns: true`
- [ ] `exactOptionalPropertyTypes: true`
- [ ] `skipLibCheck: false` (or documented why disabled)

### 10.2 Type Usage — 25% dari dimensi
- [ ] No `any` type (exceptions documented with `// eslint-disable-next-line`)
- [ ] `unknown` used instead of `any` where type is truly unknown
- [ ] Function return types explicitly annotated
- [ ] Function parameter types explicitly annotated
- [ ] Object types defined as interfaces/types (not inline)
- [ ] Union types used for finite states
- [ ] Discriminated unions for complex state
- [ ] Template literal types used for string patterns

### 10.3 Null/Undefined Handling — 15% dari dimensi
- [ ] Optional chaining for deeply nested access (`user?.address?.city`)
- [ ] Nullish coalescing for defaults (`??` not `||`)
- [ ] All nullable values handled before usage
- [ ] No implicit undefined returns
- [ ] Proper error handling instead of returning null

### 10.4 Exhaustiveness — 15% dari dimensi
- [ ] Switch statements exhaustive with `never` type
- [ ] Discriminated union exhaustiveness checks
- [ ] Type guards used for union narrowing
- [ ] Assertion functions for invariants
- [ ] `satisfies` keyword for type validation (TS 4.9+)

```typescript
// Exhaustive switch pattern
type Action = 'create' | 'update' | 'delete';

function handleAction(action: Action): string {
  switch (action) {
    case 'create': return 'Creating...';
    case 'update': return 'Updating...';
    case 'delete': return 'Deleting...';
    default:
      const _exhaustive: never = action;
      throw new Error(`Unhandled action: ${_exhaustive}`);
  }
}
```

### 10.5 Generics — 10% dari dimensi
- [ ] Proper generic constraints (`extends`)
- [ ] Generic utility types created where needed
- [ ] No `as any` casts to bypass type system
- [ ] Conditional types used for complex type logic
- [ ] Mapped types used for object transformations

### 10.6 Type Organization — 10% dari dimensi
- [ ] Shared types exported from barrel file (index.ts)
- [ ] Types co-located with implementation
- [ ] Third-party types properly declared (`declare module 'x'`)
- [ ] @types/ packages in devDependencies (not dependencies)

---

## 11. Dimension 9: Error Handling (Bobot: 5%)

### 11.1 Global Error Handler — 20% dari dimensi
- [ ] React Error Boundary at root level
- [ ] Error boundaries at feature section level
- [ ] Express global error middleware (backend)
- [ ] Next.js error.tsx or global-error.tsx
- [ ] Unhandled promise rejection handler
- [ ] Uncaught exception handler

### 11.2 Graceful Degradation — 20% dari dimensi
- [ ] Feature-specific fallback UI when a feature fails
- [ ] App continues working when non-critical feature fails
- [ ] Third-party service failure doesn't crash the app
- [ ] Database connection failure returns appropriate error
- [ ] Feature flags can disable problematic features remotely

### 11.3 User-Facing Errors — 20% dari dimensi
- [ ] Error messages in plain language (no stack traces)
- [ ] Error message includes what happened and what user can do
- [ ] Different errors for auth failures (401 vs 403)
- [ ] Form field-level error messages
- [ ] Toast/inline error for async operations

### 11.4 Structured Error Logging — 20% dari dimensi
- [ ] All errors logged with structured format (JSON)
- [ ] Each log includes: timestamp, requestId, userId, action, error
- [ ] Log levels used correctly (error/warn/info/debug)
- [ ] No sensitive data in logs (passwords, tokens, PII)
- [ ] Error correlation ID for tracking across services

### 11.5 Retry & Recovery — 10% dari dimensi
- [ ] Exponential backoff for transient failures
- [ ] Max retry limit to prevent infinite loops
- [ ] Idempotency keys for mutation retries
- [ ] Circuit breaker pattern for external services
- [ ] Offline queue with sync on reconnect

### 11.6 Fallback UI — 10% dari dimensi
- [ ] Each Error Boundary has custom fallback
- [ ] Fallback includes retry button
- [ ] Fallback may include "report this issue" link
- [ ] Fallback appropriate to context (not always blank page)

---

## 12. Dimension 10: Documentation (Bobot: 4%)

### 12.1 README — 25% dari dimensi
- [ ] Project name and description
- [ ] Tech stack overview
- [ ] Prerequisites (Node version, package manager, etc.)
- [ ] Quick start / setup instructions
- [ ] Environment variables listed (with .env.example)
- [ ] Architecture overview (diagram helpful)
- [ ] Available scripts
- [ ] Testing instructions
- [ ] Deployment instructions
- [ ] Link to live demo / staging

### 12.2 API Documentation — 20% dari dimensi
- [ ] OpenAPI/Swagger spec (or equivalent)
- [ ] All endpoints documented with request/response schemas
- [ ] Auth requirements documented per endpoint
- [ ] Error responses documented
- [ ] Rate limits documented
- [ ] API changelog maintained

### 12.3 Code Comments — 20% dari dimensi
- [ ] Comments explain WHY not WHAT (code should be self-documenting)
- [ ] Complex algorithms have explanatory comments
- [ ] Business rules and edge cases documented
- [ ] Non-obvious workarounds documented with reasoning
- [ ] JSDoc for public API functions
- [ ] TODO/FIXME linked to issue tracker

### 12.4 Architecture Decision Records — 15% dari dimensi
- [ ] ADRs for significant architecture decisions
- [ ] Each ADR includes: context, decision, consequences
- [ ] ADRs stored in `docs/adr/` directory
- [ ] ADRs referenced in code comments where relevant

### 12.5 Changelog — 10% dari dimensi
- [ ] CHANGELOG.md maintained
- [ ] Follows Keep a Changelog format
- [ ] Each version has date and description
- [ ] Breaking changes clearly marked
- [ ] Unreleased section for upcoming changes

### 12.6 Contributing Guide — 10% dari dimensi
- [ ] CONTRIBUTING.md exists
- [ ] Code standards documented (lint, format, naming)
- [ ] PR process described
- [ ] Branch naming convention documented
- [ ] Commit message convention documented (Conventional Commits)

---

## 13. Dimension 11: Observability & Monitoring (Bobot: 3%)

### 13.1 Structured Logging — 25% dari dimensi
- [ ] Logs in structured JSON format
- [ ] Log levels: debug, info, warn, error, fatal
- [ ] Each log entry includes: timestamp, level, message, service, requestId
- [ ] No console.log in production (proper logger)
- [ ] Log correlation ID across services
- [ ] Centralized log aggregation (ELK, Grafana Loki, Datadog)

### 13.2 Metrics — 25% dari dimensi
- [ ] Business metrics tracked (users, orders, revenue, etc.)
- [ ] Technical metrics tracked (response time, error rate, throughput)
- [ ] RED metrics (Rate, Errors, Duration) for each service
- [ ] USE metrics (Utilization, Saturation, Errors) for resources
- [ ] Prometheus metrics endpoint or equivalent
- [ ] Custom metrics for business KPIs

### 13.3 Distributed Tracing — 20% dari dimensi
- [ ] OpenTelemetry instrumentation
- [ ] Traces propagate across services (trace ID in headers)
- [ ] Spans for key operations (DB queries, HTTP calls, queue operations)
- [ ] Trace sampling strategy configured
- [ ] Trace visualization (Jaeger, Grafana Tempo, Honeycomb)

### 13.4 Health Checks — 15% dari dimensi
- [ ] `/health` endpoint returns 200 if service is alive
- [ ] `/ready` endpoint returns 200 only if dependencies available
- [ ] Health check includes: DB connection, cache, external services
- [ ] Health check timeout configured
- [ ] Liveness and readiness probes in Kubernetes

### 13.5 Alerting — 15% dari dimensi
- [ ] Alerts on error rate spike (> 1% of requests)
- [ ] Alerts on P95 latency > threshold (> 1s)
- [ ] Alerts on service availability < 99.9%
- [ ] Alerts on disk/memory/CPU threshold
- [ ] Alert fatigue minimized (meaningful thresholds, no duplicative alerts)
- [ ] On-call rotation defined
- [ ] Runbook for common incidents

---

## 14. Dimension 12: Deployment Readiness (Bobot: 2%)

### 14.1 CI/CD Pipeline — 25% dari dimensi
- [ ] Automated build on every commit/PR
- [ ] Automated test run (lint + typecheck + unit + integration)
- [ ] Automated deployment on merge to main
- [ ] CI pipeline fails fast (lint before test)
- [ ] Deployments to staging for PR preview
- [ ] Rollback button in CI dashboard

### 14.2 Environment Configuration — 20% dari dimensi
- [ ] Dev/staging/production environments separated
- [ ] Environment-specific config files
- [ ] No hardcoded environment names in code
- [ ] Secrets managed via secrets manager (not env files in production)
- [ ] .env.example covers all required variables

### 14.3 Database Migrations — 15% dari dimensi
- [ ] Automated migration run during deploy
- [ ] Migrations reversible (down migration)
- [ ] Migration tested in CI
- [ ] No destructive changes without data migration
- [ ] Migration timeout configured

### 14.4 Rollback Strategy — 15% dari dimensi
- [ ] Rollback procedure documented
- [ ] Quick rollback (previous version redeploy)
- [ ] Database migration rollback tested
- [ ] Canary or blue-green deployment
- [ ] Feature flags for gradual rollout

### 14.5 Docker — 15% dari dimensi
- [ ] Multi-stage Dockerfile (build → production)
- [ ] Slim base image (alpine, distroless)
- [ ] Non-root user in container
- [ ] `.dockerignore` configured
- [ ] Docker image scanned for vulnerabilities
- [ ] Image tagged with semantic version or commit hash

### 14.6 Zero-Downtime — 10% dari dimensi
- [ ] Blue-green or rolling deployment strategy
- [ ] Health checks before traffic switch
- [ ] Graceful shutdown (SIGTERM handling)
- [ ] Connection draining on shutdown
- [ ] Warmup/ready endpoint for new instances

---

## 15. Report Template

```markdown
# App Quality Evaluation Report

**Project:** {project-name}
**Version:** {version}
**Date:** {YYYY-MM-DD}
**Evaluator:** {tool/agent name}

---

## Overall Score: XX/100

| # | Dimension | Raw (0-10) | Weight | Weighted |
|---|-----------|------------|--------|----------|
| 1 | Code Quality & Maintainability | X.X | 15% | X.X |
| 2 | Security Posture | X.X | 15% | X.X |
| 3 | Performance & Core Web Vitals | X.X | 12% | X.X |
| 4 | Accessibility | X.X | 10% | X.X |
| 5 | Architecture & Design | X.X | 10% | X.X |
| 6 | Testing Maturity | X.X | 10% | X.X |
| 7 | UX & User Experience | X.X | 8% | X.X |
| 8 | TypeScript Strictness | X.X | 6% | X.X |
| 9 | Error Handling | X.X | 5% | X.X |
| 10 | Documentation | X.X | 4% | X.X |
| 11 | Observability & Monitoring | X.X | 3% | X.X |
| 12 | Deployment Readiness | X.X | 2% | X.X |
| | **Total** | | **100%** | **XX.X** |

## Grade: A / B / C / D / F

## Executive Summary

{2-3 paragraph summary of overall quality, major strengths, and critical weaknesses}

---

## Dimension Breakdown

### D1: Code Quality & Maintainability — X/10
**Justification:** {why this score}
**Checklist Results:**
- Readability: X/8 passed
- DRY: X/6 passed
- SOLID: X/5 passed
- Complexity: X/6 passed
- Imports: X/5 passed
- Code Smells: X/8 passed
**Key Findings:**
- ✅ {strength}
- ❌ {issue}
- ⚠️ {warning}
**Recommendations:**
- {specific actionable recommendation}
- {specific actionable recommendation}

### D2: Security Posture — X/10
**Justification:** {why this score}
**Checklist Results:**
- OWASP Top 10: X/10 passed
- Dependency Audit: X/5 passed
- Secrets Management: X/4 passed
- HTTP Security: X/7 passed
**Key Findings:**
- ✅ {strength}
- ❌ {issue}
**Recommendations:**
- {specific recommendation}

### D3: Performance & Core Web Vitals — X/10
**Justification:** {why this score}
**Checklist Results:**
- Core Web Vitals: X/8 passed
- Bundle: X/8 passed
- Images: X/7 passed
- Caching: X/5 passed
- Rendering: X/6 passed
- Database: X/6 passed
**Key Findings:**
- ✅ {strength}
- ❌ {issue}
**Performance Budget Status:**
| Metric | Measured | Target | Status |
|--------|----------|--------|--------|
| LCP | X.Xs | <2.5s | ✅/❌ |
| INP | Xms | <200ms | ✅/❌ |
| CLS | X.XX | <0.1 | ✅/❌ |
| Bundle | XKB | <200KB | ✅/❌ |
**Recommendations:**
- {specific recommendation}

### D4: Accessibility — X/10
**Justification:** {why this score}
**Checklist Results:**
- WCAG AAA: X/16 passed
- Color Contrast: X/6 passed
- Focus: X/6 passed
- Screen Reader: X/6 passed
- Reduced Motion: X/4 passed
**Key Findings:**
- ✅ {strength}
- ❌ {issue}
**Lighthouse a11y Score:** XX/100
**axe-core Violations:** X critical, X serious
**Recommendations:**
- {specific recommendation}

### D5: Architecture & Design — X/10
**Justification:** {why this score}
**Checklist Results:**
- Components: X/6 passed
- Data Flow: X/6 passed
- Separation: X/5 passed
- Scalability: X/6 passed
- DI: X/4 passed
- API Design: X/7 passed
- Error Boundaries: X/5 passed
- Async: X/5 passed
**Key Findings:**
- ✅ {strength}
- ❌ {issue}
**Recommendations:**
- {specific recommendation}

### D6: Testing Maturity — X/10
**Justification:** {why this score}
**Checklist Results:**
- Unit Tests: X/8 passed
- Integration Tests: X/5 passed
- E2E Tests: X/5 passed
- Component Tests: X/6 passed
- Test Infrastructure: X/5 passed
- Performance Tests: X/4 passed
**Coverage Summary:**
- Lines: XX%
- Branches: XX%
- Functions: XX%
**Key Findings:**
- ✅ {strength}
- ❌ {issue}
**Recommendations:**
- {specific recommendation}

### D7: UX & User Experience — X/10
**Justification:** {why this score}
**Checklist Results:**
- Loading States: X/5 passed
- Empty States: X/5 passed
- Error States: X/6 passed
- Edge Cases: X/8 passed
- Responsive: X/6 passed
- Consistency: X/5 passed
- Feedback: X/5 passed
- i18n: X/4 passed
**Key Findings:**
- ✅ {strength}
- ❌ {issue}
**Recommendations:**
- {specific recommendation}

### D8: TypeScript Strictness — X/10
**Justification:** {why this score}
**Checklist Results:**
- Config: X/7 passed
- Type Usage: X/8 passed
- Null/Undefined: X/5 passed
- Exhaustiveness: X/5 passed
- Generics: X/5 passed
- Type Organization: X/4 passed
**Key Findings:**
- ✅ {strength}
- ❌ {issue}
**Type Error Count:** X errors in X files
**Recommendations:**
- {specific recommendation}

### D9: Error Handling — X/10
**Justification:** {why this score}
**Checklist Results:**
- Global Handler: X/6 passed
- Graceful Degradation: X/5 passed
- User-facing Errors: X/5 passed
- Structured Logging: X/5 passed
- Retry & Recovery: X/5 passed
- Fallback UI: X/4 passed
**Key Findings:**
- ✅ {strength}
- ❌ {issue}
**Recommendations:**
- {specific recommendation}

### D10: Documentation — X/10
**Justification:** {why this score}
**Checklist Results:**
- README: X/10 passed
- API Docs: X/6 passed
- Code Comments: X/6 passed
- ADRs: X/4 passed
- Changelog: X/5 passed
- Contributing: X/5 passed
**Key Findings:**
- ✅ {strength}
- ❌ {issue}
**Recommendations:**
- {specific recommendation}

### D11: Observability & Monitoring — X/10
**Justification:** {why this score}
**Checklist Results:**
- Structured Logging: X/6 passed
- Metrics: X/6 passed
- Tracing: X/5 passed
- Health Checks: X/5 passed
- Alerting: X/7 passed
**Key Findings:**
- ✅ {strength}
- ❌ {issue}
**Recommendations:**
- {specific recommendation}

### D12: Deployment Readiness — X/10
**Justification:** {why this score}
**Checklist Results:**
- CI/CD: X/5 passed
- Environment Config: X/5 passed
- DB Migrations: X/5 passed
- Rollback: X/5 passed
- Docker: X/6 passed
- Zero-Downtime: X/5 passed
**Key Findings:**
- ✅ {strength}
- ❌ {issue}
**Recommendations:**
- {specific recommendation}

---

## Critical Issues (Must Fix Before Production)

1. **{issue}** — {why critical} — {file:line}
2. **{issue}** — {why critical} — {file:line}
3. **{issue}** — {why critical} — {file:line}

## High Priority Issues

1. **{issue}** — {why important} — {file:line}
2. **{issue}** — {why important} — {file:line}
3. **{issue}** — {why important} — {file:line}

## Recommended Improvements

1. **{improvement}** — {expected impact} — {estimated effort}
2. **{improvement}** — {expected impact} — {estimated effort}
3. **{improvement}** — {expected impact} — {estimated effort}

## Score History (if applicable)

| Date | Version | Total | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | D10 | D11 | D12 |
|------|---------|-------|----|----|----|----|----|----|----|----|----|-----|-----|-----|
| {date} | {v1.0} | XX | X | X | X | X | X | X | X | X | X | X | X | X |

---

> Generated by the App Quality Evaluation Framework
```

---

## 16. Grading Scale

| Grade | Range | Meaning | Action Required |
|-------|-------|---------|-----------------|
| A | 90-100 | Production Excellence | Ship it |
| B | 75-89 | Good Quality | Ship with minor fixes |
| C | 60-74 | Adequate | Significant work before production |
| D | 40-59 | Poor | Major refactoring needed |
| F | < 40 | Critical | Fundamental rewrite needed |

### Grade Distribution Diagram

```
Score:  0────10────20────30────40────50────60────70────80────90────100
       F       F        D        D        C        B        A     A
       <──── Critical ────><─── Poor ────><─── Adequate ──>< Good ──>< Excellent
```

---

## 17. Quick Assessment Checklist (50+ Items)

Gunakan checklist ini untuk assessment cepat dalam < 5 menit.

### Code Quality
- [ ] All SQL queries parameterized
- [ ] No magic numbers or strings (all named constants)
- [ ] No files > 500 lines
- [ ] No functions > 50 lines
- [ ] Nesting depth <= 3 levels
- [ ] No TODO without ticket reference
- [ ] No console.log in production code
- [ ] Imports organized and unused imports removed

### Security
- [ ] No hardcoded secrets in code
- [ ] HTTPS enforced (HTTP → HTTPS redirect)
- [ ] CORS not set to wildcard in production
- [ ] Content-Security-Policy header present
- [ ] Input validation on all user inputs
- [ ] npm audit passes (0 critical, 0 high)
- [ ] Passwords hashed (bcrypt/argon2)
- [ ] JWT short-lived (< 15 min access token)
- [ ] Rate limiting on auth endpoints

### Performance
- [ ] LCP < 2.5s (measured)
- [ ] CLS < 0.1 (measured)
- [ ] Bundle size < 200KB gzipped
- [ ] Code splitting implemented at route level
- [ ] Images lazy loaded
- [ ] Images in WebP/AVIF format
- [ ] No N+1 database queries

### Accessibility
- [ ] Lighthouse a11y score = 100
- [ ] Semantic HTML (nav, main, header, etc.)
- [ ] Alt text on all images
- [ ] Proper heading hierarchy (h1 > h2 > h3)
- [ ] Visible focus ring on all interactive elements
- [ ] Skip navigation link present
- [ ] Color contrast meets AAA (7:1 ratio)
- [ ] prefers-reduced-motion respected
- [ ] Forms have associated labels

### Architecture
- [ ] Error boundaries in place (frontend)
- [ ] Global error handler (backend)
- [ ] Consistent API response format
- [ ] Proper HTTP status codes used
- [ ] Pagination for list endpoints
- [ ] State management appropriate for app scale

### Testing
- [ ] Unit tests with > 80% coverage
- [ ] Tests run in CI
- [ ] No flaky tests
- [ ] Edge cases tested (null, empty, error)

### TypeScript
- [ ] TypeScript strict mode enabled
- [ ] No `any` type usage
- [ ] strictNullChecks: true
- [ ] Return types annotated on functions

### Documentation
- [ ] README exists and is complete
- [ ] .env.example committed
- [ ] CHANGELOG.md maintained
- [ ] Setup instructions work (tested)

### Deployment
- [ ] CI/CD pipeline configured
- [ ] Dockerfile with multi-stage build
- [ ] Environment config separated
- [ ] Database migrations automated
- [ ] Rollback procedure documented

### Observability
- [ ] Structured logging (JSON)
- [ ] /health endpoint
- [ ] Error rate alerting configured
- [ ] Metrics tracked (RED metrics)

### Scoring Quick Assessment

```text
Passed / Total = X/55
Score = (X / 55) * 10

Score >= 8 : Likely Grade A/B
Score 5-7  : Likely Grade C
Score < 5  : Likely Grade D/F
```

---

## 18. Evaluation Methodology

### 18.1 Static Analysis

| Tool | What It Checks | How to Run |
|------|---------------|------------|
| ESLint | Code quality, unused imports, best practices | `npx eslint src/` |
| Prettier | Code formatting consistency | `npx prettier --check src/` |
| TypeScript | Type errors, strict mode compliance | `npx tsc --noEmit` |
| dependency-cruiser | Circular dependencies, module boundaries | `npx depcruise src/` |
| CodeQL | Security vulnerabilities, code quality | GitHub code scanning |
| SonarQube | Code smells, bugs, vulnerabilities, duplications | `sonar-scanner` |
| madge | Circular dependencies | `npx madge --circular src/` |

### 18.2 Dynamic Analysis

| Tool | What It Checks | How to Run |
|------|---------------|------------|
| Lighthouse | Performance, a11y, SEO, best practices | `npx lighthouse http://localhost:3000` |
| Playwright/Cypress | E2E tests, accessibility | `npx playwright test` |
| axe-core | Accessibility violations | `npx axe http://localhost:3000` |
| WAVE | Accessibility evaluation | Browser extension |

### 18.3 Dependency Audit

| Tool | What It Checks | How to Run |
|------|---------------|------------|
| npm audit | Known vulnerabilities in deps | `npm audit --audit-level=high` |
| Snyk | Open source vulnerabilities | `snyk test` |
| OWASP DC | Dependency vulnerabilities | `npx owasp-dependency-check` |
| Renovate/Dependabot | Automated dependency updates | GitHub/GitLab integration |

### 18.4 Performance Testing

| Tool | What It Checks | How to Run |
|------|---------------|------------|
| Lighthouse CI | Performance budget, Core Web Vitals | `npx lhci autorun` |
| k6 | Load testing, stress testing | `k6 run test.js` |
| autocannon | HTTP benchmarking | `npx autocannon http://localhost:3000` |
| WebPageTest | Detailed performance analysis | webpagetest.org |
| Bundle Analyzer | JS bundle composition | `ANALYZE=true npm run build` |

### 18.5 Security Testing

| Tool | What It Checks | How to Run |
|------|---------------|------------|
| OWASP ZAP | Active/passive scanning | `zap-cli quick-scan http://localhost:3000` |
| semgrep | Custom security rules | `semgrep --config=auto src/` |
| truffleHog | Secrets in git history | `trufflehog git file://. --results=verified` |
| SQLMap | SQL injection testing | `sqlmap -u "http://localhost:3000/api"` |

### 18.6 Code Review Process

Manual code review should complement automated tools:

```
1. Automated checks pass (lint, typecheck, test)
2. Security scan complete (no critical findings)
3. Performance budget met
4. Manual review of:
   a. Business logic correctness
   b. Error handling completeness
   c. UX flow correctness
   d. Edge case coverage
5. Architecture alignment verified
```

### 18.7 Evaluation Pipeline (Recommended Order)

```
┌─────────────────────────────────────────────────────────┐
│                     EVALUATION ORDER                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Static Analysis (lint + typecheck + circular deps)  │
│     → Fail fast on critical issues                      │
│                                                         │
│  2. Dependency Audit (npm audit + Snyk)                  │
│     → Block on critical CVEs                            │
│                                                         │
│  3. Unit + Integration Tests                            │
│     → Coverage report                                   │
│                                                         │
│  4. Performance Budget (Lighthouse CI)                   │
│     → Core Web Vitals + bundle size                     │
│                                                         │
│  5. Accessibility Scan (axe-core + Lighthouse)           │
│     → WCAG AAA compliance                               │
│                                                         │
│  6. Security Scan (ZAP + semgrep + truffleHog)           │
│     → OWASP Top 10 coverage                             │
│                                                         │
│  7. E2E Tests (critical user journeys)                   │
│     → Cross-browser + mobile                            │
│                                                         │
│  8. Manual Code Review                                  │
│     → Architecture, business logic, UX                  │
│                                                         │
│  9. Scoring + Report Generation                          │
│     → 12 dimensions → grade → actionable plan           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 19. Integration with Other Skills

### 19.1 security-audit
Load `security-audit` skill for in-depth OWASP assessment. Use D2 checklist as initial triage, then delegate to security-audit for full penetration testing.

### 19.2 frontend-react
Load `frontend-react` skill for React-specific code quality, component patterns, and server component evaluation. D1, D5, D7 benefit directly.

### 19.3 backend-nodejs / backend-go
Load backend skill for backend-specific evaluation: middleware patterns, request validation, database access layer. Relevant to D1, D2, D5.

### 19.4 database-postgres / database-security
Load database skills for query optimization, indexing strategy, migration safety. Relevant to D3 (performance) and D2 (security).

### 19.5 devops-platform-engineering
Load for CI/CD pipeline evaluation, infrastructure review, deployment strategy. Relevant to D12.

### 19.6 typescript
Load for deep TypeScript pattern analysis, advanced type safety verification. Relevant to D8.

### Integration Flow

```
app-quality
  │
  ├── security-audit ───→ D2 (Security Posture)
  ├── frontend-react ───→ D1, D5, D7, D9
  ├── backend-nodejs ───→ D1, D2, D5
  ├── backend-go ───────→ D1, D2, D5
  ├── database-postgres ─→ D3 (Performance)
  ├── database-security ─→ D2 (Injection, Access Control)
  ├── devops-platform ───→ D12 (Deployment)
  └── typescript ────────→ D8 (TypeScript)
```

---

## 20. Implementation Example

### Scoring Function (Reference Implementation)

```typescript
interface DimensionResult {
  dimension: number;
  name: string;
  weight: number; // e.g., 0.15
  rawScore: number; // 0-10
  weightedScore: number; // rawScore * weight
  checksPassed: number;
  checksTotal: number;
  findings: Finding[];
}

interface Finding {
  type: 'critical' | 'high' | 'medium' | 'low' | 'info';
  checkId: string;
  passed: boolean;
  message: string;
  file?: string;
  line?: number;
  recommendation?: string;
}

interface EvaluationResult {
  projectName: string;
  version: string;
  date: string;
  totalScore: number;
  grade: 'A' | 'B' | 'C' | 'D' | 'F';
  dimensions: DimensionResult[];
  criticalIssues: Finding[];
  summary: string;
}

function calculateGrade(score: number): 'A' | 'B' | 'C' | 'D' | 'F' {
  if (score >= 90) return 'A';
  if (score >= 75) return 'B';
  if (score >= 60) return 'C';
  if (score >= 40) return 'D';
  return 'F';
}

function calculateScore(checklist: boolean[], weights?: number[]): number {
  const pass = checklist.filter(Boolean).length;
  const total = checklist.length;
  return Math.round((pass / total) * 10 * 10) / 10;
}
```

### Quick Start: Running an Evaluation

```bash
# 1. Clone the project and install dependencies
git clone <project> && cd <project> && npm install

# 2. Run static analysis
npx tsc --noEmit
npx eslint src/
npx prettier --check src/

# 3. Run tests
npm run test -- --coverage

# 4. Run security audit
npm audit --audit-level=high
npx snyk test

# 5. Run performance audit
npx lhci autorun

# 6. Run accessibility audit
npx axe

# 7. Score each dimension using checklists in this skill

# 8. Generate report
```

---

## 21. Quick Reference Card

### Score → Grade → Action

| Score | Grade | Action |
|-------|-------|--------|
| 90-100 | A | Ship to production |
| 75-89 | B | Fix minor issues, ship |
| 60-74 | C | Address gaps, re-review |
| 40-59 | D | Major refactor required |
| < 40 | F | Rewrite from scratch |

### Critical Automatic Fails

ANY of these → D2 score capped at 2:
- Hardcoded API key / password / token in source
- String-concatenated SQL query with user input
- `eval()` or `new Function()` with user input
- CORS `Access-Control-Allow-Origin: *`
- No CSRF protection on mutating endpoints

### Minimum Viable Quality Checklist

Minimum to pass any review:
1. TypeScript strict mode
2. All SQL parameterized
3. No secrets in code
4. Error boundaries/react boundaries
5. README with setup instructions
6. Tests run and pass
7. No critical CVEs in dependencies

---

## Performance Budget Reference

```text
┌────────────────────┬─────────────┬──────────────┐
│ Metric             │ Target      │ Critical     │
├────────────────────┼─────────────┼──────────────┤
│ LCP                │ < 2.5s      │ > 4.0s       │
│ INP                │ < 200ms     │ > 500ms      │
│ CLS                │ < 0.1       │ > 0.25       │
│ TTFB               │ < 800ms     │ > 1.8s       │
│ FCP                │ < 1.8s      │ > 3.0s       │
│ TBT                │ < 200ms     │ > 500ms      │
│ SI                 │ < 3.4s      │ > 5.8s       │
│ Bundle (gzip)      │ < 200KB     │ > 500KB      │
│ Lighthouse Score    │ > 90        │ < 50         │
└────────────────────┴─────────────┴──────────────┘
```

---

*This skill is part of the Opencode quality evaluation framework. Use with `skill({name: "app-quality"})` to load. For discipline-specific deep dives, combine with specialized skills listed in integrates_with.*
