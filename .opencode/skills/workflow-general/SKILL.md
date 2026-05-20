---
name: workflow-general
description: General development workflow patterns: requirement analysis, planning, implementation, testing, review, deployment lifecycle. Vibe-Coding alignment and quality-first methodology.
license: MIT
compatibility: opencode
metadata:
  audience: all-developers
  domain: workflow
  paradigm: methodology
  capabilities:
    - requirements-elicitation
    - architecture-planning
    - implementation-strategy
    - testing-hierarchy
    - code-review
    - deployment-strategy
    - agile-methodologies
    - git-workflows
    - project-management
    - team-collaboration
  integrates_with:
    - understanding
    - all domain-specific skills
    - code-reviewer
---

## General Development Workflow Skill

### The Quality-First Lifecycle
```
Requirements → Architecture → Implementation → Testing → Review → Deploy → Monitor
     ↑              ↑              ↑              ↑          ↑         ↑         ↑
     └──────────────┴──────────────┴──────────────┴──────────┴─────────┴─────────┘
                              Continuous Validation Loop
```

---

### Phase 1: Requirements Analysis

**Goal**: Transform ambiguous intent into precise, testable specification.

#### Requirements Elicitation Techniques

| Technique | When to Use | Output |
|---|---|---|
| **User Interviews** | New feature, no existing data | Raw needs, pain points |
| **Job Shadowing** | Workflow optimization | Observed bottlenecks |
| **Surveys** | Large user base, quantitative data | Statistical preferences |
| **Competitive Analysis** | Market positioning, feature parity | Gap analysis |
| **Data Analytics Review** | Existing product, optimizing flows | Funnel drop-offs, heatmaps |
| **Stakeholder Workshops** | Cross-team alignment | Shared understanding, trade-offs |

#### User Story Format
```
As a <role/persona>,
I want <goal/capability>,
So that <benefit/value>.

Acceptance Criteria:
- [ ] Given <precondition>, when <action>, then <expected outcome>
- [ ] Given <precondition>, when <action>, then <expected outcome>

Definition of Done:
- [ ] Code reviewed and merged
- [ ] Tests pass (unit + integration + E2E if applicable)
- [ ] Documentation updated
- [ ] Feature flagged (if applicable)
- [ ] Monitored in production
```

#### Acceptance Criteria Templates

| Type | Template |
|---|---|
| **Functional** | "When user clicks X, Y happens within Z seconds" |
| **Performance** | "Page loads in < 200ms P95 under 1000 concurrent users" |
| **Security** | "Only users with role X can access endpoint Y" |
| **Error Handling** | "On network failure, show retry dialog; persist unsaved data" |
| **Accessibility** | "All interactive elements navigable via keyboard; contrast ratio >= 4.5:1" |

#### Constraint Identification

For each requirement, document:
- **Hard constraints** (non-negotiable): deadlines, compliance (GDPR, HIPAA, SOC2), platform support, budget ceiling, team capacity
- **Soft constraints** (negotiable): preferred tech stack, performance targets, timeline flexibility, scope trade-offs
- **Constraint question bank**:
  - "What happens if we miss the deadline by 1 week? By 1 month?"
  - "Is the budget an absolute ceiling or a target?"
  - "Which features are must-have vs. nice-to-have?"
  - "Who decides priority when constraints conflict?"

#### Anti-Patterns in Requirements

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Gold plating (scope creep) | Delivers features nobody asked for, delays core value | MoSCoW prioritization (Must, Should, Could, Won't) |
| Solutionizing instead of problem-stating | "Build a Redis cache" vs. "Dashboard loads in 15s" | Always ask "What problem does this solve?" |
| Big upfront design | Assumes perfect knowledge; requirements evolve | Define MVP, iterate based on feedback |

---

### Phase 2: Architecture & Planning

**Goal**: Design a solution structure that satisfies all requirements within constraints.

#### Architecture Decision Records (ADR)

Every significant decision documented with:
```markdown
## ADR-NNN: <Title>

**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Date**: YYYY-MM-DD
**Deciders**: <names>

**Context**: What problem are we solving? What constraints apply?

**Options Considered**:
1. Option A: <description>
   - Pros: ...
   - Cons: ...
2. Option B: <description>
   - Pros: ...
   - Cons: ...

**Decision**: We chose Option X because...

**Consequences**:
- Positive: ...
- Negative: ...
- Mitigation for negatives: ...
```

#### Component Decomposition Strategies

| Strategy | When to Use | Example |
|---|---|---|
| **By Feature/Vertical** | Product with distinct feature areas | `users/`, `billing/`, `search/` |
| **By Layer/Horizontal** | Simple app, small team | `models/`, `views/`, `controllers/` |
| **By Domain (DDD)** | Complex business logic | Bounded contexts: `OrderManagement`, `Inventory` |
| **By Technical Concern** | Cross-cutting infrastructure | `auth/`, `logging/`, `messaging/` |

#### Interface Contract Design

Every module-to-module or service-to-service interface must specify:
- **Signature**: Input types, output types, method name
- **Preconditions**: What must be true before calling
- **Postconditions**: What is guaranteed after calling
- **Error modes**: What errors can be returned and when
- **Performance contract**: Expected latency, throughput, availability
- **Versioning strategy**: How backward-incompatible changes are handled

#### ASCII Architecture Diagram Standard
```
┌─────────────────────────────────────────────────┐
│                    CLIENTS                       │
│  [Web Browser]  [Mobile App]  [External API]    │
└─────┬────────────────┬────────────────┬─────────┘
      │                │                │
      ▼                ▼                ▼
┌─────────────────────────────────────────────────┐
│                 API GATEWAY                      │
│         (rate limiting, auth, routing)           │
└─────┬────────────────┬────────────────┬─────────┘
      │                │                │
      ▼                ▼                ▼
┌──────────┐   ┌──────────────┐   ┌──────────┐
│  Auth    │   │   Business    │   │  Worker  │
│ Service  │◄─►│   Logic Svc   │──►│  Queue   │
└────┬─────┘   └──────┬───────┘   └────┬─────┘
     │                │                │
     ▼                ▼                ▼
┌──────────┐   ┌──────────────┐   ┌──────────┐
│  Users   │   │   Primary    │   │  Cache   │
│    DB    │   │     DB       │   │ (Redis)  │
└──────────┘   └──────────────┘   └──────────┘
```

#### Risk Matrix

| Risk ID | Description | Likelihood (1-5) | Impact (1-5) | Score | Mitigation | Contingency |
|---|---|---|---|---|---|---|
| R1 | Third-party API deprecation | 3 | 5 | 15 | Pin version, monitor changelog | Adapter pattern, swap implementation |
| R2 | Key person dependency | 2 | 5 | 10 | Cross-train, document architecture | Maintain contractor contacts |
| R3 | Performance under peak load | 3 | 4 | 12 | Load test, auto-scaling | Feature flag to degrade non-critical features |
| R4 | Dependency vulnerability | 4 | 3 | 12 | Dependabot, regular updates | Incident response plan, rollback procedure |

**Scoring**: 1-5 (Low), 6-10 (Monitor), 11-16 (Mitigate actively), 17-25 (Escalate: resolve before proceeding)

---

### Phase 3: Implementation

**Goal**: Build working software incrementally, maintaining quality at every step.

#### Branching Strategies

| Strategy | Pattern | Best For |
|---|---|---|
| **Trunk-Based** | Short-lived branches (< 1 day), merge to main via PR | CI/CD, small teams, continuous deployment |
| **GitHub Flow** | Feature branches off main, PR + review, merge | Most web applications |
| **Gitflow** | main/develop + feature/release/hotfix branches | Versioned software with release cycles |

#### Commit Conventions (Conventional Commits)
```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]

Types: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert
Examples:
  feat(auth): add OAuth2 login flow
  fix(api): handle null response from payment gateway
  refactor(db): extract query builder to shared module
  perf(search): add composite index on (user_id, created_at)
  test(cart): add integration tests for checkout flow
```

#### Code Review Protocols

**For Author**:
1. Keep PRs small (< 400 lines changed)
2. Self-review before requesting review: read the diff, leave self-comments on tricky parts
3. Link PR to issue/ticket
4. Include screenshot/video for UI changes
5. Pre-merge checklist: tests pass, lint passes, no debug code, no secrets

**For Reviewer**:
1. First pass: understand the intent. Second pass: scrutinize the code.
2. Check: correctness, security, performance, readability, test coverage
3. Distinguish blocking ("must fix") from non-blocking ("consider this pattern")
4. Review within 4 business hours (team agreement)
5. Approve = "I would ship this"

#### Pair Programming Patterns

| Pattern | Description | When to Use |
|---|---|---|
| **Driver-Navigator** | Driver writes code, Navigator reviews strategy | Most common, learning tasks |
| **Ping-Pong** | Driver writes test, Navigator implements to pass | TDD adoption |
| **Strong-Style** | Navigator dictates intent, Driver translates to code | Knowledge transfer, onboarding |
| **Tour** | Expert walks through existing codebase | Onboarding, architecture overview |

#### Incremental Delivery

- Ship every merge to main (continuous deployment) or ship on a regular cadence
- Use **feature flags** to decouple deployment from release
- Deploy dark (code in prod, flag off) → internal test → % rollout → full launch
- Never branch feature development for more than 2 days

---

### Phase 4: Testing

**Goal**: Verify correctness, prevent regressions, and enable confident refactoring.

#### The Test Pyramid

```
        ╱  E2E  ╲          ← Few: critical user journeys only
       ╱──────────╲
      ╱ Integration ╲      ← Some: component interactions, API contracts
     ╱────────────────╲
    ╱    Unit Tests     ╲   ← Many: every function, every branch, every edge case
   ╱──────────────────────╲
```

| Layer | Scope | Speed | Cost to Write | Cost to Maintain | Confidence |
|---|---|---|---|---|---|
| **Unit** | Single function/module | ms | Low | Low | Low (isolated) |
| **Integration** | Multiple modules, DB, API | ms-s | Medium | Medium | Medium |
| **E2E** | Full system, browser/device | s-min | High | High | High |

#### TDD: Red-Green-Refactor

```
RED: Write a failing test
  ↓
GREEN: Write minimal code to pass
  ↓
REFACTOR: Improve code without changing behavior
  ↓ (tests stay green)
Repeat
```

When to TDD: bug fixes, well-defined features, pure logic. When NOT to TDD: exploratory spikes, UI experimentation, throwaway prototypes.

#### Property-Based Testing

Instead of testing specific inputs/outputs, define properties that hold for all valid inputs:
- **Example**: "Sorting a list does not change its length" `length(sort(xs)) == length(xs)`
- **Example**: "Reversing twice returns the original" `reverse(reverse(xs)) == xs`
- **Example**: "Serializing and deserializing is identity" `decode(encode(x)) == x`
- **Tools**: Hypothesis (Python), fast-check (TypeScript), test.check (Clojure)

#### Mutation Testing

Tests that pass when mutants (deliberately broken code) are introduced are weak. Mutation testing:
1. Introduce small bugs (mutants): flip `>` to `<`, remove null check, swap `+` for `-`
2. Run test suite: if a mutant survives (tests pass), tests are inadequate
3. **Tools**: Stryker (JS/TS/C#), Pitest (Java), mutmut (Python)

#### Snapshot Testing

Capture serialized output and compare to stored snapshot. Best for: UI components (rendering output), API responses, configuration files, data transformations. Never snapshot: dynamic data (timestamps, random IDs), large binary blobs, secrets.

#### Coverage Targets

| Coverage Type | Minimum | Target | Notes |
|---|---|---|---|
| **Line** | 80% | 90%+ | Basic safety net |
| **Branch** | 75% | 85%+ | Catches untested conditions |
| **Function** | 90% | 95%+ | Ensures all code paths exercised |
| **Mutation Score** | 60% | 75%+ | Tests that actually verify behavior |

---

### Phase 5: Review & Self-Evaluation

**Goal**: Ensure quality before shipping to users.

#### 6-Dimension Scoring (0-100)

| Dimension | What to Check | Red Flags |
|---|---|---|
| **Correctness** | Does it do what it claims? Edge cases handled? | Missing error handling, off-by-one, undefined behavior |
| **Performance** | Is it fast enough under expected load? | N+1 queries, unbounded loops, blocking in async context |
| **Security** | Are inputs validated? Data sanitized? Secrets exposed? | Raw SQL, unsanitized HTML, hardcoded keys, missing auth checks |
| **Maintainability** | Can a new team member understand this in 30 min? | Magic numbers, 500-line functions, undocumented assumptions |
| **Completeness** | Are all AC met? Error/loading/empty states covered? | Missing states, no tests for edge cases, partial implementation |
| **Alignment** | Does this solve the actual problem? | Scope creep, gold plating, wrong problem solved |

**Pass threshold**: 80+ in all dimensions. Any dimension below 80 requires iteration.

#### Self-Review Checklist

```
Before requesting peer review:
  [ ] I've read the full diff and nothing surprises me
  [ ] No commented-out code, debug logs, console.log, or TODO markers without tickets
  [ ] All new functions have corresponding tests
  [ ] Error states are handled (not just happy path)
  [ ] No hardcoded secrets, URLs, or magic numbers
  [ ] Variable/function names are self-documenting
  [ ] Linter and type-checker pass with zero warnings
  [ ] All existing tests pass
  [ ] Documentation updated (README, API docs, changelog)
```

#### Peer Review Protocols

```
Reviewer checks in order of priority:
  1. SECURITY: Injection, XSS, auth bypass, data exposure
  2. CORRECTNESS: Logic errors, edge cases, error handling
  3. PERFORMANCE: N+1 queries, memory leaks, unnecessary work
  4. MAINTAINABILITY: Naming, structure, coupling, comments
  5. STYLE: Formatting, conventions (should be automated via linter)

Reviewer should NOT:
  - Rewrite code in review comments (suggest alternative patterns instead)
  - Block merge on personal style preferences (use linter for style)
  - Approve without understanding what the code does
```

---

### Phase 6: Deployment

**Goal**: Deliver value safely and recoverably.

#### CI/CD Pipeline Design

```
Push → Lint → Typecheck → Unit Tests → Build → Integration Tests → Security Scan → Deploy Staging → E2E Tests → Deploy Prod
  │       │         │           │        │            │               │              │           │               │
  └───────┴─────────┴───────────┴────────┴────────────┴───────────────┴──────────────┴───────────┴───────────────┘
                                     Fast Feedback (< 5 min)                              Gated Promotion
```

#### Feature Flags (Decouple Deploy from Release)

| Flag Type | Example | Use Case |
|---|---|---|
| **Release toggle** | `new_checkout_flow` | Incomplete feature, not ready for users |
| **Experiment toggle** | `blue_button_variant` | A/B testing |
| **Ops toggle** | `disable_search_indexing` | Kill switch for emergency |
| **Permission toggle** | `admin_export_csv` | Feature gated by role |

#### Canary Deployment

```
1. Deploy new version alongside old
2. Route 5% traffic to new version
3. Compare metrics (error rate, latency, success rate)
4. If healthy → 25% → 50% → 100%
5. If unhealthy at any stage → auto-rollback to old version
```

#### Blue-Green Deployment

```
1. Blue environment serves 100% traffic (current stable)
2. Green environment gets new version (standby)
3. Smoke test Green
4. Switch router: Green now serves 100%, Blue is standby
5. If issue found, switch router back to Blue (instant rollback)
```

#### Rollback Strategies

| Strategy | Speed | Use When |
|---|---|---|
| **Router switch (blue-green)** | Instant | Full deployment swap |
| **Feature flag off** | Instant (flag change) | Feature-level rollback |
| **Database migration rollback** | Minutes | Must have reverse migration tested |
| **Revert commit + redeploy** | Pipeline duration (5-30 min) | Small changes, no data migration |

#### Post-Deployment Monitoring

```
First 5 minutes:  Watch error rate, latency, saturation
First 1 hour:    Compare to baseline (previous release)
First 24 hours:  Watch for slow-burn issues (memory leaks, connection pool exhaustion)
First 7 days:    Business metrics (conversion, revenue, user engagement)

Alert if:
  - Error rate increases > 2x baseline
  - P99 latency increases > 50%
  - Any critical user journey fails > 0.1% of requests
```

---

## Development Methodologies

### Agile / Scrum

**Cadence**: 1-4 week sprints with fixed scope negotiation.

| Ceremony | Frequency | Duration | Purpose |
|---|---|---|---|
| Sprint Planning | Per sprint | 2-4 hours | Select backlog items for sprint |
| Daily Standup | Daily | 15 min | What did I do? What will I do? Any blockers? |
| Sprint Review/Demo | Per sprint | 1 hour | Show completed work to stakeholders |
| Sprint Retrospective | Per sprint | 1-1.5 hours | What went well? What to improve? Action items |

**Roles**: Product Owner (prioritizes), Scrum Master (facilitates), Development Team (executes).

**Artifacts**: Product Backlog (ordered wishlist), Sprint Backlog (commitment), Increment (done work).

### Kanban

**Principle**: Continuous flow, limit WIP, no timeboxes.

```
Backlog → Ready → In Progress → Review → Done
              ↑         ↑           ↑
           WIP:3     WIP:2       WIP:2
```

**Core Practices**: Visualize workflow, limit work-in-progress, manage flow, make policies explicit, improve collaboratively.

**When to choose Kanban over Scrum**: Continuous delivery teams, ops/support teams, variable priority work, maintenance mode.

### Shape Up (Basecamp Method)

**Cadence**: 6-week cycles + 2-week cooldown.

```
Cycle (6 weeks):
  - Shaped pitch: problem + appetite + solution sketch + rabbit holes + no-gos
  - Fixed time, variable scope
  - Ship or kill at end of cycle (no extensions)

Cooldown (2 weeks):
  - Bug fixes, tech debt, exploration for next cycle
```

**Key Concepts**:
- **Appetite**: "How much time is this worth?" vs. "How long will this take?"
- **Shaping**: Define problem/solution before committing, at the right level of abstraction
- **Betting**: Stakeholders bet on pitches, not assign stories
- **Hill charts**: Visual progress tracking (uphill = unknowns, downhill = execution)

### When to Use Which

| Methodology | Best For |
|---|---|
| **Scrum** | Predictable delivery, cross-functional teams, stakeholder visibility needed |
| **Kanban** | Continuous delivery, ops/support, variable priorities, mature teams |
| **Shape Up** | Product teams, appetite-driven development, avoiding sprint fatigue |
| **Waterfall (rare)** | Fixed-price contracts, regulatory submission, physical construction dependencies |

---

## Code Quality Standards

### SOLID Principles

| Principle | Meaning | Example |
|---|---|---|
| **S**ingle Responsibility | A class/module has one reason to change | `UserAuthService` vs. `UserAuthAndEmailService` |
| **O**pen/Closed | Open for extension, closed for modification | Strategy pattern, plugin architecture |
| **L**iskov Substitution | Subtypes must be substitutable for base types | Square extends Rectangle (breaks: setWidth changes height) |
| **I**nterface Segregation | Many small interfaces > one fat interface | `Readable` + `Writable` vs. `ReadWrite` |
| **D**ependency Inversion | Depend on abstractions, not concretions | Inject `Database` interface, not `PostgreSQL` class |

### Core Design Principles

| Principle | Meaning | Good | Bad |
|---|---|---|---|
| **DRY** (Don't Repeat Yourself) | Every piece of knowledge has one authoritative representation | Extract shared validation to `validateEmail()` | Copy-pasting regex across 5 files |
| **KISS** (Keep It Simple, Stupid) | Favor simplicity over cleverness | `for` loop | 3-level nested reduce with ternaries |
| **YAGNI** (You Aren't Gonna Need It) | Don't build it until you need it | Concrete class | AbstractFactoryFactory for one implementation |
| **Law of Demeter** | Only talk to immediate friends | `order.getCustomer().getName()` | `order.customer.account.manager.name` |
| **Fail Fast** | Validate early, report errors immediately | Guard clause at function start | Null check on line 150 after 20 operations |

### Naming Conventions

| Construct | Convention | Example |
|---|---|---|
| **Variables** | camelCase, descriptive nouns | `userEmail`, `isActive`, `orderCount` |
| **Functions** | camelCase, verb + noun | `getUserById()`, `calculateTotal()`, `isValid()` |
| **Classes/Components** | PascalCase, nouns | `UserService`, `ShoppingCart`, `OrderController` |
| **Constants** | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT_MS` |
| **Boolean variables** | `is`, `has`, `can`, `should` prefix | `isLoading`, `hasPermission`, `canEdit` |
| **Event handlers** | `handle` + event name | `handleClick`, `handleSubmit`, `handleKeyDown` |
| **Files** | Match primary export name | `UserService.ts`, `useAuth.ts`, `ShoppingCart.tsx` |

### File/Folder Structure Conventions

```
src/
├── components/          # Shared UI components
│   ├── Button/
│   │   ├── Button.tsx
│   │   ├── Button.test.tsx
│   │   └── index.ts
│   └── ...
├── features/            # Feature modules (vertical slices)
│   ├── auth/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types.ts
│   │   └── index.ts
│   ├── billing/
│   └── ...
├── hooks/               # Shared hooks
├── services/            # API clients, external integrations
├── utils/               # Pure utility functions
├── constants/           # App-wide constants
├── types/               # Shared TypeScript types
└── lib/                 # Third-party wrapper/config
```

### Comment/Documentation Standards

```
WHEN TO COMMENT:
  - WHY, not WHAT: Code tells what; comments tell why
  - Non-obvious business rules: "Refunds only valid within 30 days per GDPR Article X"
  - Performance workarounds: "Using for-loop instead of .map because V8 deoptimizes on large sparse arrays"
  - TODO format: "// TODO(handle): Remove after migration v2 is complete (tracked in JIRA-1234)"

WHEN NOT TO COMMENT:
  - Self-documenting code: getActiveUsers() needs no "gets active users" comment
  - Version history: that's what git is for
  - Dead code: delete it, don't comment it out
  - Obvious language features: "// increment the counter" on i++
```

---

## Git Workflows

### Trunk-Based Development

```
main ────●────●────●────●────● (always deployable)
          \   /    \   /
           ●─●      ●─●  (short-lived feature branches, <1 day)
```

- Feature flags hide incomplete work
- Pair programming / ensemble programming for complex changes
- CI prevents broken main (branch protection: require passing builds before merge)

### GitHub Flow

```
main ───●────────────●────────────●
         \          / \          /
       feature-a──●   feature-b──●
                    \
                     bugfix-c──●
```

1. Branch from main: `git checkout -b feature/xyz`
2. Commit and push frequently
3. Open PR when ready (or earlier for early feedback as Draft PR)
4. Review, discuss, iterate
5. Merge to main, deploy immediately

### Gitflow (for versioned releases)

```
main ──●──────(v1.0)─────●──────(v1.1)─────●
        \                / \                /
develop──●──●──●──●──●──●──●──●──●──●──●──●
              \          /        \    /
           release/1.0──●     hotfix/1.0.1──●
```

- `main`: Production releases only
- `develop`: Integration branch
- `feature/*`: New features from develop
- `release/*`: Release preparation (bug fixes, version bump)
- `hotfix/*`: Emergency production fixes

### Branch Naming Conventions

| Pattern | Example | When |
|---|---|---|
| `feat/<description>` | `feat/oauth-login` | New feature |
| `fix/<description>` | `fix/null-pointer-on-logout` | Bug fix |
| `chore/<description>` | `chore/update-deps` | Maintenance |
| `docs/<description>` | `docs/api-authentication` | Documentation |
| `refactor/<description>` | `refactor/extract-auth-service` | Refactoring |
| `perf/<description>` | `perf/add-query-index` | Performance |
| `<ticket-id>/<description>` | `JIRA-4321/oauth-login` | Linked to issue tracker |

### Commit Message Format (Conventional Commits)

```
<type>(<optional scope>): <short summary>
<BLANK LINE>
<optional body - explain WHY, not what>
<BLANK LINE>
<optional footer - BREAKING CHANGE: ..., Closes #123, Refs #456>

Types: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert

Rules:
  - Summary line <= 72 characters
  - Imperative mood: "add" not "added" or "adds"
  - No period at end of summary
  - Body at 72 character wrap
  - BREAKING CHANGE: in footer for breaking changes (triggers major version bump)
```

---

## Project Management Integration

### Issue Tracking Integration

```
Issue lifecycle:
  Backlog → To Do → In Progress → In Review → Done

Issue linking convention:
  - Branch name includes ticket: JIRA-1234/feature-description
  - Commit message references ticket: feat(auth): add OAuth login (JIRA-1234)
  - PR description closes ticket: Closes #1234 or Fixes JIRA-1234
```

### Estimation Techniques

| Technique | How It Works | Best For |
|---|---|---|
| **Story Points** | Relative sizing (1, 2, 3, 5, 8, 13 Fibonacci) | Sprint planning, velocity tracking |
| **T-Shirt Sizes** | XS, S, M, L, XL | Quick triage, backlog grooming |
| **Ideal Days/Hours** | "This would take 4 hours without interruptions" | Single developer, well-known task |
| **No Estimates** | Break work into equally sized small chunks; count throughput | Continuous delivery, mature teams |

**Story Point Reference**:
- 1 point: Trivial (typo fix, 1-line change, no risk)
- 2 points: Simple (well-understood, single file, under 30 min)
- 3 points: Moderate (multiple files, known pattern, 1-3 hours)
- 5 points: Complex (new component, multiple edge cases, 4-8 hours)
- 8 points: Challenging (new feature, research needed, 1-3 days)
- 13+ points: Too large, must be split into smaller stories

### Velocity Tracking

```
Sprint 1: 24 pts completed
Sprint 2: 28 pts completed
Sprint 3: 18 pts completed (holiday week)
Sprint 4: 26 pts completed
Sprint 5: 30 pts completed

Average (excluding Sprint 3 outlier): 27 pts/sprint
```

- Calculate rolling average of last 3-5 sprints
- Use for capacity planning, NOT for commitments or performance evaluation
- Decreasing velocity = signal to investigate (tech debt, unclear requirements, team morale)

### Burndown / Burnup Charts

```
Burndown (remaining work):
  30 │╲
  25 │ ╲
  20 │  ╲___   (stalled - investigate)
  15 │      ╲
  10 │       ╲
   5 │        ╲___
   0 └─────────────
     1  2  3  4  5  Sprint Days

Burnup (completed vs total):
  50 │        ┌───── Total scope (may grow)
  40 │        │
  30 │    ┌───┤
  20 │ ┌──┘   └────── Completed
  10 │─┘
   0 └─────────────
     1  2  3  4  5  Sprint Days
```

---

## Team Collaboration

### Communication Protocols

| Channel | Use For | Response Expectation |
|---|---|---|
| **Issue Tracker** | Requirements, bugs, decisions | Comment within 24 hours |
| **Chat (Slack/Teams)** | Quick questions, coordination | Within 2 hours (business hours) |
| **Email** | External, formal, cross-org | Within 24 business hours |
| **Video Call** | Complex discussion, pair programming | Scheduled or on-demand |
| **Wiki/Notion** | Long-lived documentation, decisions, architecture | Updated proactively |
| **PR Comments** | Code-specific feedback | Within 4 business hours |

**Async-first culture**: Default to async communication. Sync meetings only when async fails (complex discussion, conflict resolution, brainstorming).

### Decision-Making Frameworks

| Framework | Process | When to Use |
|---|---|---|
| **RAPID** | Recommend, Agree, Perform, Input, Decide - each role assigned | Complex cross-team decisions |
| **RACI** | Responsible, Accountable, Consulted, Informed | Role clarity in execution |
| **Consent-based** | "Do you have a reasoned objection?" vs. "Do you agree?" | Team decisions, low stakes |
| **Advice Process** | Anyone can decide; must consult affected parties and experts | Empowered, decentralized teams |
| **DACI** | Driver, Approver, Contributors, Informed | Project-level decisions |

### Knowledge Sharing Practices

1. **Architecture Decision Records (ADR)**: Document "why" not just "what" for future developers
2. **Brown-bag sessions**: Weekly 30-min informal knowledge sharing over lunch
3. **Code walkthroughs**: New features presented by author to team before merging
4. **Rotation program**: Engineers rotate through different domains every quarter
5. **Living documentation**: READMEs, runbooks, and FAQs updated alongside code changes
6. **Postmortem write-ups**: Incidents documented and shared; blame-free, focus on learning

### Onboarding Patterns

```
Week 1 - Environment & Context:
  - Day 1: Company/team mission, values, communication norms
  - Day 2-3: Dev environment setup, run existing tests, deploy to staging
  - Day 4-5: Architecture overview, read ADRs, pair with team members

Week 2 - First Contribution:
  - First PR: small bug fix or documentation improvement
  - Shadow code review process
  - Attend all team ceremonies

Week 3-4 - Ramp Up:
  - Pair on feature work
  - Own a small feature end-to-end
  - Participate in on-call shadow rotation

Month 2-3:
  - Independent feature work
  - Contribute to design discussions
  - Join on-call rotation
```

---

## Anti-Patterns in Depth

| # | Anti-Pattern | Concrete Example | Why It Fails | Fix |
|---|---|---|---|---|
| 1 | **Premature optimization** | Adding Redis caching before measuring if the query is slow | Wastes time, adds complexity, may optimize the wrong thing | Profile first. Only optimize when data shows a bottleneck. 80/20 rule. |
| 2 | **Gold plating** | Building an admin dashboard with drag-and-drop widgets when the ask was "export users to CSV" | Delivers unrequested work, delays core value, frustrates stakeholders | Ask: "Is this in the acceptance criteria?" If no, don't build it. |
| 3 | **Big bang merges** | Working on a feature branch for 3 weeks, then opening a 5000-line PR | Review is impossible, conflicts are massive, feedback comes too late | Merge daily. Use feature flags. Split large features into small PRs (< 400 lines). |
| 4 | **Skipping tests** | "This is a simple change, I tested it manually" | Manual testing doesn't scale. One missed edge case causes production incident. 6 months later nobody remembers why the code exists. | Write at least one test per behavior. If it's too simple to test, it's too simple to break. |
| 5 | **Ignoring linter warnings** | Team accumulates 500 ESLint warnings; "we'll fix them later" | Warning fatigue: real issues hidden in noise. Later never comes. | Zero-warning policy. Fix existing warnings in a dedicated cleanup PR. Block CI on new warnings. |
| 6 | **Copying code without understanding** | Stack Overflow snippet with `eval()` pasted into production code | Security vulnerabilities, subtle bugs (the snippet was for Python 2 but you're on 3), maintenance nightmare | Understand every line you commit. If you can't explain it to a teammate, don't merge it. |
| 7 | **Hero culture** | One developer works 60-hour weeks, knows all the critical systems, never documents, is the "only one who can fix it" | Bus factor of 1. Hero burns out. Team doesn't learn. | Rotate ownership. Mandatory documentation. Pair programming on critical systems. No single point of knowledge. |
| 8 | **Analysis paralysis** | 2 weeks debating Postgres vs. MySQL vs. CockroachDB for a 10-user internal tool | Decision cost exceeds cost of wrong decision. Delivers zero value. | Time-box decisions. For reversible decisions: any reasonable choice is fine. Save deep analysis for irreversible decisions. |
| 9 | **Sunk cost fallacy** | "We've already spent 3 months on this architecture; we can't change now" | Throwing good time after bad. The 3 months are gone regardless. | Evaluate based on future value, not past cost. Ask: "If we started today, would we choose this approach?" |
| 10 | **Cargo culting** | "Google uses Kubernetes so we should too" (5-person team, static site) | Solutions exist in context. Google's context (scale, team size, problems) differs from yours. | Understand the problem first, then choose a solution. Ask: "What problem does this solve for us specifically?" |
| 11 | **Not invented here** | Rewriting a date library because "we can do it better" | Reinventing wheels wastes time, introduces bugs, and produces worse results than battle-tested libraries. | Evaluate existing solutions first. Only build if nothing exists or license prevents use. Document why existing solutions were rejected. |
| 12 | **Status-driven architecture** | Choosing microservices because "it's what modern companies use" | Microservices solve organizational scaling, not technical scaling. A monolith is often the right choice for < 20 engineers. | Match architecture to current team size, not aspirational team size. Monolith first, extract services when pain is measurable. |
| 13 | **Blame culture** | Post-incident review focuses on "who caused this?" | Engineers hide mistakes, incidents aren't reported, same failures recur because root causes go unfixed. | Blameless postmortems. Ask: "What in our process allowed this to happen?" Not: "Who did it?" Focus on systemic fixes. |
| 14 | **Documentation as afterthought** | "We'll document the API after we ship" → 6 months later, no docs exist | Onboarding time triples. Support tickets flood in. Integration is guesswork. | Documentation is part of the feature. PR is not done until docs are updated. Use docs-driven development for APIs. |
| 15 | **Over-engineering for scale** | Designing a system to handle 1M requests/second when you have 100 users | Complex distributed systems cost more to build and maintain. You never reach the scale that justifies the complexity. | Design for 10x current load, not 10,000x. Scale horizontally when metrics show it's needed. YAGNI applies to infrastructure too. |

---

## Quality Metrics

### DORA Metrics (DevOps Research & Assessment)

| Metric | Elite | High | Medium | Low |
|---|---|---|---|---|
| **Deployment Frequency** | On-demand (multiple/day) | Once/day to once/week | Once/week to once/month | Once/month to once/6 months |
| **Lead Time for Changes** | < 1 hour | 1 day to 1 week | 1 week to 1 month | 1-6 months |
| **Mean Time to Recover (MTTR)** | < 1 hour | < 1 day | < 1 week | > 1 month |
| **Change Failure Rate** | 0-5% | 5-10% | 10-15% | 15-60% |

### Code Health Metrics

| Metric | Target | How to Measure |
|---|---|---|
| **Cyclomatic Complexity** | < 10 per function | SonarQube, ESLint complexity rule |
| **Duplication** | < 3% of codebase | SonarQube, jscpd |
| **Code Churn** | < 15% of files changed per sprint | Git history analysis |
| **Hotspots** | Identify files with high churn + high complexity | CodeScene, custom analysis |
| **Technical Debt Ratio** | < 5% (debt time / total dev time) | SonarQube |

### Test Coverage Metrics

| Metric | Target | Warning |
|---|---|---|
| **Line Coverage** | 85%+ | Below 70% is dangerous |
| **Branch Coverage** | 80%+ | Below 60% doesn't catch condition bugs |
| **Function Coverage** | 95%+ | Untested functions = dead code or risk |
| **Mutation Score** | 75%+ | Below 50% means tests don't actually verify behavior |

### Performance Metrics

| Metric | Example Target | Context |
|---|---|---|
| **LCP (Largest Contentful Paint)** | < 2.5s | Web frontend |
| **FID/TBT (First Input Delay / Total Blocking Time)** | < 100ms / < 200ms | Web frontend |
| **CLS (Cumulative Layout Shift)** | < 0.1 | Web frontend |
| **API P95 latency** | < 200ms | Backend |
| **API P99 latency** | < 500ms | Backend |
| **Error rate** | < 0.1% | Backend |
| **Availability** | 99.9% (3 nines) to 99.99% (4 nines) | System |
| **Startup time** | < 30s | Mobile app |

---

## Implementation Checklist

### Phase 1: Requirements Analysis Checklist
- [ ] Problem stated in one sentence (what, who, why)
- [ ] Success criteria defined and measurable
- [ ] User personas identified (if multiple user types)
- [ ] Acceptance criteria written in Given-When-Then format
- [ ] Constraints documented: time, budget, tech, compliance, team capacity
- [ ] Dependencies identified (other teams, external APIs, data)
- [ ] Non-functional requirements specified (performance, security, accessibility)
- [ ] Scope boundaries defined (what is explicitly OUT of scope)
- [ ] Stakeholders identified and aligned
- [ ] Assumptions logged with confidence scores

### Phase 2: Architecture & Planning Checklist
- [ ] System decomposed into components with clear responsibilities
- [ ] Component interfaces documented (inputs, outputs, contracts)
- [ ] Data model designed (entities, relationships, constraints)
- [ ] State management strategy chosen (server state, client state, URL state)
- [ ] Error handling strategy defined (retry, circuit breaker, fallback, user messaging)
- [ ] Authentication/authorization model documented
- [ ] Architecture diagram created and reviewed
- [ ] Technology choices justified in ADRs
- [ ] Risk matrix with mitigations
- [ ] Migration plan for existing data/systems (if applicable)
- [ ] Observability plan: what to log, metric, trace

### Phase 3: Implementation Checklist
- [ ] Branch created with conventional name
- [ ] Types/interfaces written before implementation
- [ ] Core logic implemented with error handling
- [ ] Loading state handled (if async)
- [ ] Empty state handled
- [ ] Error state handled with user-friendly message
- [ ] Edge cases considered (null, empty, boundary, concurrent)
- [ ] Structured logging added (no console.log)
- [ ] No hardcoded secrets, URLs, or magic numbers
- [ ] Feature flagged if incomplete or behind experiment
- [ ] Self-reviewed before opening PR
- [ ] PR description links issue, explains why and how, includes screenshots if UI

### Phase 4: Testing Checklist
- [ ] Unit tests for all new functions (happy path + edge cases)
- [ ] Integration tests for component interactions
- [ ] E2E tests for critical user journeys (if applicable)
- [ ] Snapshot tests for UI components (if applicable)
- [ ] Tests verify behavior, not implementation
- [ ] Test data is realistic and not production data
- [ ] All existing tests pass (no regressions)
- [ ] Coverage meets or exceeds target thresholds
- [ ] Performance tests for performance-critical paths (if applicable)
- [ ] Accessibility tests for UI components (if applicable)

### Phase 5: Review Checklist
- [ ] Linter passes with zero warnings
- [ ] Type checker passes
- [ ] All comments resolved (or acknowledge non-blocking)
- [ ] Security review: no injection, XSS, auth bypass, data exposure
- [ ] Performance review: no N+1 queries, memory leaks, unnecessary work
- [ ] Maintainability review: naming clear, structure logical, complexity acceptable
- [ ] 6-dimension scoring >= 80 in all dimensions
- [ ] Documentation updated

### Phase 6: Deployment Checklist
- [ ] All CI checks pass (lint, typecheck, test, build)
- [ ] Security scan passes
- [ ] Staging deployment verified
- [ ] Database migrations tested (forward + rollback)
- [ ] Feature flags configured (if applicable)
- [ ] Monitoring dashboards updated for new features
- [ ] Alerts configured for new critical paths
- [ ] Rollback plan documented and tested
- [ ] Release notes written
- [ ] Stakeholders notified of deployment

### Post-Deployment Checklist
- [ ] Error rate within acceptable range
- [ ] Latency within SLO
- [ ] No unexpected log patterns
- [ ] Feature flag enabled incrementally (if applicable)
- [ ] Business metrics monitored
- [ ] On-call team briefed on new changes
- [ ] Deployment marked as success or rollback initiated

---

### Integration Patterns

The Workflow General skill provides the **process framework**. It should be loaded alongside domain-specific skills:

```
User Input
    |
    v
[Load: understanding] ── Understand intent, context, constraints
    |
    v
[Load: workflow-general] ── Plan the execution approach
    |
    v
[Load: domain-specific skill(s)] ── Execute with domain best practices
    |
    v
[Load: code-reviewer] ── Self-evaluate against 6 dimensions
```

This skill applies to ALL development work regardless of domain. Load it second (after understanding) for any implementation task.
