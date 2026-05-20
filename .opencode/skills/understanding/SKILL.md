---
name: understanding
description: Deep context comprehension for brainstorming: first-principles analysis, intent extraction, constraint mapping, assumption surfacing, domain synthesis, and structured thinking frameworks
license: MIT
compatibility: opencode
metadata:
  audience: all-developers
  domain: workflow
  paradigm: analytical
  capabilities:
    - intent-extraction
    - context-mapping
    - constraint-identification
    - assumption-surfacing
    - domain-synthesis
    - questioning-frameworks
    - brainstorming
    - stakeholder-analysis
    - risk-register
    - decision-logging
  prerequisites: none
  integrates_with:
    - workflow-general
    - all domain-specific skills
---

## Understanding & Brainstorming Skill

### Philosophical Foundation

The act of understanding is not passive consumption but active construction. Every request, bug report,
feature ask, or architectural question is a puzzle whose surface form rarely reflects its true shape.
The gap between what someone says and what they need is the most expensive gap in software engineering.

Three axioms underpin this skill:

1. **The Map Is Not the Territory** -- Words are lossy compression of mental models. Your first parse of
   a statement is almost certainly incomplete. Treat every input as a first draft of meaning.

2. **Problems Exist in Systems, Not in Isolation** -- A "database performance issue" may be a schema
   design problem, a query pattern problem, an ORM misuse problem, a missing index problem, or a business
   logic problem masquerading as all of the above. Trace the edges of the system before narrowing.

3. **Understanding Is Iterative and Convergent** -- You will never fully understand on the first pass.
   Each question you ask, each constraint you surface, each assumption you test brings you closer to
   ground truth. Stop when the cost of further understanding exceeds the cost of being wrong.

```
   Certainty
      ^
      |                                    _______________
      |                              _____/  Convergent
      |                         ____/       Understanding
      |                    ____/
      |               ____/  Each iteration
      |          ____/       reduces uncertainty
      |     ____/
      |____/
      |
      +------------------------------------------------> Iterations
      0    1     2     3     4     5     6     7
```

### The Understanding Pipeline

```
Raw Input  Intent      Context     Constraint  Assumption  Domain     Validated
  |         Extraction  Mapping     Ident.      Surfacing   Synthesis  Understanding
  |            |           |           |           |           |           |
  v            v           v           v           v           v           v
[Text] --> [What do  --> [Where   --> [What     --> [What   --> [Which   --> [Confirm
            they mean?]    does      can't we     are we      domains    alignment]
                           this fit?]  change?]    guessing?]  touch?]
```

---

### Stage 1: Intent Extraction

**Goal**: Move from "what they said" to "what they need."

#### Detailed Process

1. **Parse explicit requests** -- Identify the literal ask. What words did they use? What action verb
   anchors the request? ("fix", "add", "explain", "review", "optimize", "design")

2. **Identify implicit needs** -- What problem drove them to make this request? What were they doing
   when they encountered the issue? What would success look like for them?

3. **Detect emotional signals** -- Language betrays emotion. Look for:
   - **Frustration**: "I've tried everything", "nothing works", "wasted hours"
   - **Urgency**: "ASAP", "blocking", "production", "customers affected"
   - **Uncertainty**: "I think", "maybe", "not sure", "probably", question marks
   - **Overwhelm**: Vague requests, topic jumping, contradictory statements

4. **Separate solution from problem** -- People often request a specific solution rather than stating
   the underlying problem. "Add a cache" may mean "the page is slow." "Write a script" may mean "I
   do this task manually every week."

#### Decision Tree for Intent Extraction

```
Incoming Request
    |
    +-- Contains a proposed solution? --> YES --> Ask: "What problem does this solve?"
    |                                              |
    |                                              +--> Surface the underlying need
    |
    +-- Vague or ambiguous? --> YES --> Ask: "Can you walk me through what happened?"
    |                                   |
    |                                   +--> Reconstruct the scenario
    |
    +-- Emotionally charged? --> YES --> Acknowledge emotion first
    |                                   |
    |                                   +--> Then redirect to problem
    |
    +-- Clear problem + clear context? --> PROCEED to Stage 2
```

#### Concrete Examples

| What They Said | What They Meant |
|---|---|
| "I need a Redis cache for user sessions" | "Session lookups are slow under load" |
| "The login page is broken" | "I got an error when logging in with SSO at 9:14am" |
| "We should rewrite this in Rust" | "The current service uses too much memory and crashes" |
| "Can you add a button that exports to CSV?" | "I need to share this data with the finance team weekly" |
| "The API is down" | "I'm getting 504 timeouts on /api/orders after 30s" |

#### Traps & Gotchas

| Trap | Why It Happens | Mitigation |
|---|---|---|
| **XY Problem** | User asks about their attempted solution (Y) instead of the original problem (X) | Always ask "what are you trying to accomplish?" |
| **Anchoring on first interpretation** | The first plausible reading of a request feels right | Generate at least 3 possible interpretations before settling |
| **Ignoring emotional context** | Technical people default to technical parsing | Emotions carry signal about severity, urgency, and trust |
| **Assuming domain knowledge** | You fill in gaps with your own experience | Explicitly state "I'm assuming you mean X -- is that correct?" |

---

### Stage 2: Context Mapping

**Goal**: Locate the request within its full environment before analyzing it.

#### Five Context Dimensions

```
                    TEMPORAL
                   /    |    \
                  /     |     \
            SOCIAL --- REQUEST --- BUSINESS
                  \     |     /
                   \    |    /
                  TECHNICAL --- CONSTRAINT
```

**Temporal Context** -- When?
- What happened immediately before this request? (Trigger event)
- What is the history of this system/area? (Accrued tech debt? Recent changes?)
- What follows this request? (Deadlines? Dependent work? Release cycles?)
- Is this a recurring issue or a first-time occurrence?

**Technical Context** -- What stack?
- Language, framework, database, infrastructure
- Architecture pattern (monolith, microservices, event-driven, etc.)
- Existing code conventions, testing patterns, CI/CD pipeline
- Dependencies and their versions; known compatibility issues

**Social Context** -- Who?
- Who made the request and what is their role?
- Who else is affected by this? Who will review/approve the work?
- What are the team dynamics? (Skill levels, communication norms, decision-making process)
- Are there unstated constraints from organizational politics?

**Business Context** -- Why does it matter?
- What business problem does solving this address?
- What is the cost of NOT solving it? (Revenue loss, user churn, compliance risk)
- What is the expected ROI or impact?
- Is this aligned with current business priorities?

**Constraint Context** -- What boundaries?
- Budget (money, headcount, time allocation)
- Technical (must work on existing infra, must use approved libraries)
- Regulatory (GDPR, SOC2, HIPAA, PCI-DSS)
- Organizational (team boundaries, ownership, approval chains)

#### Context Mapping Methodology

```
1. Start with what you know (the explicit)
       |
2. Ask: "What don't I know that I need to know?"
       |
3. Categorize gaps into the five dimensions
       |
4. Ask targeted questions per dimension
       |
5. Document the context map (see Output Templates)
```

#### Traps & Gotchas

| Trap | Why It Happens | Mitigation |
|---|---|---|
| **Context collapse** | You tunnel-vision on one dimension (usually technical) | Force yourself to check all 5 dimensions explicitly |
| **Availability bias** | You overweight context that's easy to recall (recent incidents) | Seek out data, not just anecdotes |
| **Over-contextualizing** | You gather so much context you never start | Set a timebox: "I will spend 15 min on context, then proceed" |
| **Assuming context is static** | You treat the environment as frozen | Ask: "Has anything changed recently that might affect this?" |

---

### Stage 3: Constraint Identification

**Goal**: Define the solution space by identifying what CANNOT or MUST NOT change.

#### Constraint Taxonomy

```
CONSTRAINTS
    |
    +-- HARD (Non-negotiable)
    |     |
    |     +-- Physical: Memory limit, CPU cores, network latency floor
    |     +-- Legal/Regulatory: GDPR, HIPAA, export controls
    |     +-- Deadline: Hard ship date (conference, contract)
    |     +-- Compatibility: Must support IE11, must run on ARM64
    |
    +-- SOFT (Negotiable with cost)
    |     |
    |     +-- Performance targets: "P99 < 200ms" (maybe 250ms is okay?)
    |     +-- Budget limits: "Under $500/month" (maybe $600 with approval?)
    |     +-- Tech stack: "Must use React" (maybe Preact or SolidJS?)
    |     +-- Timeline: "By end of Q2" (maybe early Q3 with good reason?)
    |
    +-- IMAGINED (Self-imposed, not real)
          |
          +-- "We've always done it this way"
          +-- "The team doesn't know that technology"
          +-- "That's not how things work here"
          +-- "The customer wouldn't want that"
```

#### Constraint Prioritization Matrix

For each constraint, score:
- **Impact** (1-5): How much does this constrain the solution space?
- **Inflexibility** (1-5): How hard is this to change?
- **Certainty** (1-5): How sure are we this constraint actually exists?

Multiply: Impact x Inflexibility = Priority Score. Sort descending.
Attach Certainty as a confidence flag.

| Constraint | Impact | Inflexibility | Certainty | Score | Flag |
|---|---|---|---|---|---|
| Must deploy on AWS (gov contract) | 5 | 5 | 5 | 25 | CONFIRMED |
| Budget capped at $2000/month | 4 | 3 | 2 | 12 | VERIFY |
| "Team only knows Python" | 4 | 2 | 1 | 8 | CHALLENGE |

#### Constraint Mining Questions

- "What would we absolutely NOT be allowed to change?"
- "What is the one thing that, if changed, would make everything else easier?"
- "What deadline are we working toward, and who set it?"
- "What happens if we miss that deadline?"
- "Is there a budget approval process? What's the threshold?"
- "Are there any compliance or audit requirements I should know about?"
- "What would get this project immediately rejected?"

#### Traps & Gotchas

| Trap | Example | Mitigation |
|---|---|---|
| **Treating soft constraints as hard** | "We must use Python" when the constraint is actually "team is most productive in Python" | Ask: "What would have to be true for this constraint to change?" |
| **Ignoring implicit constraints** | Not realizing the team has no on-call capacity for new services | Ask: "Who maintains this after it's built?" |
| **Constraint El Dorado** | Looking for one constraint that, if removed, solves everything | Most complex problems have multiple interacting constraints; solve the system |
| **Accepting constraints without verification** | "The client said the budget is $X" without checking if that's a soft ceiling | Ask: "Who controls this constraint? Can we talk to them?" |

---

### Stage 4: Assumption Surfacing

**Goal**: Make all implicit beliefs explicit so they can be tested.

#### Assumption Categories

```
ASSUMPTIONS
    |
    +-- FACTUAL: About the world/reality
    |     Example: "The database has 1M rows"
    |     Test: Query the database
    |
    +-- CAUSAL: About cause-effect relationships
    |     Example: "Adding an index will fix the slow query"
    |     Test: Benchmark before and after
    |
    +-- BEHAVIORAL: About how people will act
    |     Example: "Users will adopt the new UI without training"
    |     Test: Usability testing, analytics, feedback
    |
    +-- TEMPORAL: About timing and sequence
    |     Example: "The backend team will finish their API before we start"
    |     Test: Check their sprint plan, add buffer
    |
    +-- STRUCTURAL: About how systems/orgs are organized
          Example: "The auth team owns the login endpoint"
          Test: Check ownership docs, ask the team directly
```

#### Assumption Confidence Scoring

```
HIGH   (confidence > 80%) -- Evidence exists, verified by multiple sources
MEDIUM (confidence 40-80%) -- Some evidence, but not conclusive
LOW    (confidence < 40%) -- Speculation, educated guess, or hearsay
```

#### Dangerous Assumption Patterns

These are the assumptions most likely to cause catastrophic failure if wrong:

1. **Silent Dependency**: "Service X will always be available" -- What if it's not?
2. **Infinite Capacity**: "The database can handle any load" -- What's the actual limit?
3. **Perfect Knowledge**: "We understand all the requirements" -- What haven't they told you?
4. **No Regime Change**: "The current context will remain stable" -- What if the team restructures?
5. **Happy Path Only**: "The user will follow the intended flow" -- What about edge cases?

#### Assumption Elicitation Techniques

- **Pre-mortem question**: "Imagine we shipped this and it failed spectacularly. What assumption was wrong?"
- **Inversion**: "What would have to be false for our entire approach to be invalid?"
- **Outsider test**: "If someone from a different team looked at this, what would they question?"
- **Historical scan**: "What assumptions have been wrong in similar past projects?"

#### Traps & Gotchas

| Trap | Example | Mitigation |
|---|---|---|
| **Blind spot persistence** | The assumption you don't know you're making is the dangerous one | Run pre-mortems; ask outsiders to review your assumption log |
| **Confidence inflation** | "I'm 90% sure" when you have zero data | Require evidence for any confidence claim above 60% |
| **Assumption fatigue** | Listing 50 assumptions and treating them all equally | Prioritize: which 3 assumptions, if wrong, would change everything? |
| **Groupthink on assumptions** | Everyone in the room shares the same unverified belief | Bring in a designated dissenter or outsider |

---

### Stage 5: Domain Synthesis

**Goal**: Map which technical and business domains the problem touches, and how they interact.

#### Domain Identification

```
                      Frontend
                      (React/Svelte/Flutter/etc.)
                     /         |         \
                    /          |          \
           Mobile/Desktop    Design     Animation
                  \            |            /
                   \           |           /
             Backend ------ Domain ------ Infrastructure
            (API/DB/Biz      Hub        (Cloud/K8s/CI-CD)
              Logic)          |
                   /           |           \
                  /            |            \
            Database       Security       Observability
         (SQL/NoSQL/      (Auth/Crypto/   (Logs/Metrics/
          Event Src)       Compliance)      Traces)
```

#### Cross-Domain Interaction Analysis

For each pair of domains that interact, document:

1. **Interface**: How do they communicate? (API calls, events, shared DB, file exchange)
2. **Contract**: What guarantees does each side expect? (latency, format, availability)
3. **Failure mode**: What happens when the interaction breaks?
4. **Change coupling**: If one side changes, does the other need to change?

```
Example Cross-Domain Analysis:

Frontend <--> Backend
  Interface: REST API over HTTPS
  Contract: Frontend expects JSON with specific schema; <200ms P95
  Failure mode: Loading spinners, error toasts, degraded UX
  Change coupling: API versioning reduces coupling; backward-incompatible
                   changes require coordinated deployment

Backend <--> Database
  Interface: Connection pool via ORM
  Contract: ACID transactions, connection timeout 30s
  Failure mode: 500 errors, cascading timeouts, connection pool exhaustion
  Change coupling: Schema migrations are coupled; can be decoupled with
                   expand-contract pattern
```

#### Subagent Dispatch Decision Matrix

After identifying domains, determine which subagents to invoke:

| Domain | Subagent | When to Invoke |
|---|---|---|
| Frontend/UI/UX | @ui-god | Any visual, interaction, or accessibility work |
| Backend/API/DB | @backend-architect | Data modeling, API design, business logic |
| Infrastructure/Cloud | @cloud-sage | Deployment, scaling, observability, networking |
| Systems/OS/Low-level | @systems-shaman | Performance-critical, kernel, embedded, WASM |
| Security/Crypto | @security-oracle | Auth, encryption, compliance, threat modeling |
| AI/ML/Agents | @ai-architect | RAG, agent loops, memory, model selection |
| Mobile/Desktop | @mobile-master | Flutter, React Native, Tauri, SwiftUI |
| Mathematics/HPC/ML | @math-scientist | Numerical, optimization, training, CUDA |
| Code Review/Quality | @code-reviewer | After any significant code change |
| Cross-domain/Multi | @lore-master | When 3+ domains interact or architecture decisions needed |

#### Traps & Gotchas

| Trap | Example | Mitigation |
|---|---|---|
| **Domain siloing** | Treating frontend and backend as separate problems when they share a data contract | Always analyze the interfaces between domains |
| **Over-decomposition** | Invoking 5 subagents for a 2-line CSS fix | Only dispatch when domain expertise adds value beyond general knowledge |
| **Missing domain dependencies** | Not realizing a frontend change requires a backend migration | Trace data flow end-to-end before committing to a domain scope |
| **Wrong domain model** | Applying microservice patterns to a monolith problem | Match the solution pattern to the actual architecture, not the ideal one |

---

### Stage 6: Validated Understanding

**Goal**: Confirm alignment between your understanding and the requestor's intent before acting.

#### Validation Protocol

```
1. SYNTHESIZE: Combine findings from Stages 1-5 into a coherent picture
       |
2. STRUCTURE: Format understanding using the Problem Statement Template
       |
3. PRESENT: Share understanding back to requestor
       |
4. LISTEN: Watch for corrections, hesitations, additions
       |
5. ITERATE: If alignment < 100%, go back to relevant pipeline stage
       |
6. LOCK: When confirmed, freeze the understanding as the basis for action
```

#### Alignment Signals

**Signals of Alignment (green flags)**:
- Requestor says "yes, exactly" or "that's right"
- Requestor adds detail that fits within your framework ("and also...")
- Requestor's body language/energy shifts from tense to relaxed
- Requestor starts talking about next steps or implementation

**Signals of Misalignment (red flags)**:
- Requestor says "not quite" or "kind of, but..."
- Requestor re-explains the same thing using different words
- Requestor hesitates, pauses, or sounds uncertain
- Requestor asks questions that reveal a different mental model
- "Yes, but actually..." -- the "but" invalidates the "yes"

#### The Shape of the Solution Space

Before proposing specific solutions, describe the abstract characteristics of the solution space:

```
Solution Space Characteristics:
  - Complexity ceiling: [simple script .. enterprise-grade system]
  - Time horizon: [one-off fix .. long-lived service]
  - Risk tolerance: [experimental .. safety-critical]
  - Evolution path: [throwaway .. extensible platform]
  - Ownership: [individual .. team .. organization-wide]
  - Performance envelope: [batch job .. real-time with strict SLOs]
```

#### Traps & Gotchas

| Trap | Example | Mitigation |
|---|---|---|
| **False validation** | Requestor says "sure" to be polite, not because they agree | Ask a specific, falsifiable question: "So you confirm the P99 latency target is 200ms, not 100ms?" |
| **Premature freezing** | Locking understanding after Stage 1 without running all stages | Never validate until you've completed the full pipeline |
| **Over-validation** | Asking "is this right?" 15 times on minor details | Validate at the problem level, not the implementation detail level |
| **Language mismatch** | You use technical jargon, they use business terms, both think you agree | Restate using their vocabulary, not yours |

---

### Questioning Frameworks

#### The 5 Whys

Originated at Toyota. Drill from symptom to root cause by asking "why?" five times.

```
Problem: "The deployment failed in production."

Why #1: Why did the deployment fail?
    --> "The health check timed out after 30 seconds."

Why #2: Why did the health check time out?
    --> "The application took 45 seconds to start up."

Why #3: Why did the application take 45 seconds to start?
    --> "It's loading a 2GB ML model into memory on startup."

Why #4: Why is it loading the model on every startup instead of caching?
    --> "The model is stored in the container image, not on a shared volume."

Why #5: Why is the model in the container image?
    --> "The ML team wasn't aware of the shared volume infrastructure option."

ROOT CAUSE: Cross-team knowledge gap about infrastructure capabilities.
SOLUTION: Model served from shared volume; startup time drops to 3 seconds.
NOT THE SOLUTION: Increasing the health check timeout (that's treating the symptom).
```

**When 5 Whys is insufficient**: Some problems have multiple interacting root causes.
In that case, switch to a Fishbone (Ishikawa) diagram or a causal tree.

#### Socratic Questioning for Technical Problems

Adapted from the Socratic method. Six categories of questions to probe deeper:

```
1. CLARIFICATION
   "What exactly do you mean by 'slow'?"
   "Can you give me a specific example?"
   "How would we measure that?"

2. CHALLENGING ASSUMPTIONS
   "What are we assuming about the user's workflow?"
   "Is it necessarily true that we need a relational database here?"
   "What if the opposite were true?"

3. EVIDENCE PROBING
   "What data supports that conclusion?"
   "How do we know this is the bottleneck and not something else?"
   "Has this pattern been observed elsewhere in the system?"

4. ALTERNATIVE PERSPECTIVES
   "How would the frontend team view this problem?"
   "What would a competitor do differently?"
   "If we had unlimited budget, what would change?"

5. IMPLICATIONS & CONSEQUENCES
   "If we make this change, what else might break?"
   "What's the worst-case scenario if we're wrong?"
   "Does this decision constrain future options?"

6. META-QUESTIONING
   "Why is this the question we're asking?"
   "What's the bigger problem we should be solving instead?"
   "Are we even solving the right problem?"
```

#### Inversion Thinking

Instead of asking "How do I make this succeed?" ask "How do I make this fail?"

```
Standard: "How do we make this API reliable?"
Inverted:  "What would make this API completely unusable?"

Standard questions become inverted:
  "How do we improve performance?"
  --> "What would make this system as slow as possible?"

  "How do we make this code maintainable?"
  --> "What would make future developers hate this codebase?"

  "How do we increase user adoption?"
  --> "What would make every user abandon this feature immediately?"

  "How do we ship on time?"
  --> "What would guarantee we miss every deadline?"

For each failure vector identified, design a specific mitigation.
This reveals risks that optimistic thinking hides.
```

#### Rubber Duck Debugging Guide

The act of explaining a problem out loud (or in writing) triggers different cognitive pathways
and often reveals the solution without external input.

**Step-by-step protocol:**

```
1. SET THE SCENE
   - State the problem in one sentence
   - Describe what you expected to happen
   - Describe what actually happened

2. TRACE THE FLOW
   - Walk through the code/process step by step
   - At each step, state: "I expect X to happen because Y"
   - When you reach a step where you can't explain WHY, you've found the gap

3. STATE ASSUMPTIONS ALOUD
   - "I'm assuming the input format is always JSON..."
   - "I'm assuming this function returns a list, not a single object..."
   - Listen for hesitation in your own voice -- that's a clue

4. ASK THE DUCK
   - The duck asks only one question: "Why?"
   - Answer the duck for every decision, assumption, and line of code
   - If you can't answer the duck, you've found the problem

5. SIMPLIFY TO REPRODUCE
   - Can you reproduce this with the simplest possible input?
   - If you remove half the code, does the problem persist?
   - Binary search on complexity until the minimal reproduction is isolated
```

---

### Brainstorming Frameworks

#### First-Principles Decomposition: Step-by-Step with Example

**Example Problem**: "Our user dashboard takes 15 seconds to load."

```
STEP 1: IDENTIFY THE PROPOSITION
  "The dashboard is too slow" -- this is a claim, not a fact.
  15 seconds is the observation. "Too slow" is the judgment.

STEP 2: DECONSTRUCT TO FUNDAMENTALS
  What is a dashboard load, physically?
  --> Browser sends HTTP request
  --> Server receives request, authenticates, authorizes
  --> Server queries database for dashboard data
  --> Database executes queries, returns results
  --> Server transforms data, renders or serializes
  --> Server sends response to browser
  --> Browser parses, renders, executes JavaScript

STEP 3: IDENTIFY ATOMIC TRUTHS
  - The network has latency (physics: speed of light, TCP handshakes)
  - Databases have finite IOPS and memory
  - Browsers have a single main thread for JS execution
  - Data must be transferred (can't be compressed to zero bytes)
  - Every computation takes non-zero time

STEP 4: QUESTION EVERY COMPONENT
  - Does the dashboard need ALL the data at load time?
  - Which queries are taking the most time? (pg_stat_statements)
  - Is the browser rendering thousands of DOM elements?
  - Are we making serial API calls that could be parallel?
  - Are we sending redundant data (same user info in 10 widgets)?

STEP 5: SYNTHESIZE NEW SOLUTIONS FROM FUNDAMENTALS
  - If we can't change physics, we can change what we send (lazy loading)
  - If we can't make queries faster individually, run them in parallel
  - If rendering is slow, render less (virtualization, pagination)
  - If auth is the bottleneck, cache the auth result within the session
  - If data hasn't changed, don't re-fetch (ETags, cache headers)

STEP 6: EVALUATE AGAINST CONSTRAINTS
  - Will lazy loading break existing integrations? (Check)
  - Can we add parallel queries without hitting DB connection limits? (Verify)
  - Is the team comfortable with the proposed caching strategy? (Align)
```

#### Design Thinking Sprints: 5-Stage Guide

```
EMPATHIZE ──> DEFINE ──> IDEATE ──> PROTOTYPE ──> TEST
    |            |           |            |            |
    |            |           |            |            |
    v            v           v            v            v
  Observe     Frame       Generate     Build        Validate
  Users       Problem     Solutions    Quickly      & Learn
```

**Stage 1: EMPATHIZE**
- Conduct user interviews (5-7 users, 30-45 min each)
- Shadow users in their work environment
- Collect pain points, workarounds, and wish-list features
- Output: Empathy map (what users say, think, feel, do)
- **Trap**: Interviewing only power users; include newcomers and edge-case users

**Stage 2: DEFINE**
- Synthesize empathy findings into a focused problem statement
- Format: "[User type] needs [need] because [insight]"
- Prioritize: Which problem, if solved, makes the biggest impact?
- Output: Problem statement + success metrics
- **Trap**: Solving the loudest complaint instead of the most impactful problem

**Stage 3: IDEATE**
- Quantity over quality: aim for 50+ ideas before filtering
- Use techniques: brainwriting (silent ideation), worst-possible-idea, analogies
- Cluster related ideas into themes
- Vote on themes (dot-voting or impact/effort matrix)
- Output: Top 3-5 solution concepts
- **Trap**: Falling in love with the first idea; use constraints to force creativity

**Stage 4: PROTOTYPE**
- Build the simplest thing that can generate useful feedback
- Fidelity options: paper sketches -> wireframes -> clickable mockups -> functional prototype
- The goal is LEARNING, not polish
- Time-box: 1 hour to 2 days depending on complexity
- Output: Something testable
- **Trap**: Over-building the prototype; if you'd be sad to throw it away, it's too polished

**Stage 5: TEST**
- Put the prototype in front of real users
- Observe don't explain (let them figure it out)
- Capture: what worked, what confused, what they wished for
- Iterate: test findings feed back into Define or Ideate
- Output: Validated (or invalidated) assumptions + next iteration plan
- **Trap**: Defending your prototype instead of listening to feedback

#### TRIZ: Contradiction Matrix and Inventive Principles

TRIZ is based on the insight that most problems have already been solved in another domain.

**The Contradiction Matrix** maps "What are we improving?" against "What gets worse?" to find
inventive principles that have resolved similar contradictions before.

```
CONTRADICTION: We want to improve X, but doing so makes Y worse.

Example Contradictions:
  - Improving STRENGTH of a material makes WEIGHT worse
  - Improving SPEED of software makes ACCURACY worse
  - Improving SECURITY of a system makes USABILITY worse
  - Improving SCALABILITY makes COMPLEXITY worse

Separation Principles:
  - SEPARATE IN TIME: X happens at one time, Y at another
    Example: Compress data for storage (slow), decompress in memory (fast)
  
  - SEPARATE IN SPACE: X happens in one location, Y in another
    Example: Sensitive data encrypted at rest (secure), decrypted in app (usable)
  
  - SEPARATE BY SCALE: X applies at one scale, Y at another
    Example: Full dataset indexed (slow queries), recent subset cached (fast queries)
  
  - SEPARATE BY CONDITION: X under one condition, Y under another
    Example: Full security checks on login (thorough), token validation after (fast)
```

**40 Inventive Principles (Key Selection)**:

| # | Principle | Software Example |
|---|---|---|
| 1 | Segmentation | Microservices instead of monolith |
| 2 | Taking out / Extraction | Separate read and write paths (CQRS) |
| 5 | Merging / Combining | Monorepo for shared tooling |
| 7 | Nested doll | Recursive components (trees, nested layouts) |
| 10 | Preliminary action | Prefetching, precomputing, prewarming caches |
| 13 | The other way round | Push instead of pull (webhooks, event-driven) |
| 15 | Dynamicity | Feature flags, runtime configuration |
| 17 | Another dimension | Multi-region deployment, edge computing |
| 19 | Periodic action | Cron jobs, scheduled maintenance, heartbeat checks |
| 20 | Continuity of useful action | Keep connections alive (HTTP keep-alive, connection pools) |
| 22 | Blessing in disguise | Convert error logs into monitoring signals |
| 24 | Intermediary | API gateway, load balancer, message queue |
| 25 | Self-service | Internal developer platform, self-serve analytics |
| 26 | Copying | Use existing open-source library instead of building |
| 28 | Mechanics substitution | Replace manual process with automation |
| 32 | Color changes | A/B testing, dark mode, theme system |
| 35 | Parameter changes | Configurable timeouts, adjustable pool sizes |

#### Futurespective / Pre-Mortem: Detailed Template

```
PRE-MORTEM: Project [NAME]
Date: [DATE]
Facilitator: [NAME]
Participants: [LIST]

SCENARIO: It is [DATE + 6 MONTHS]. This project has been a complete disaster.
All goals were missed. The team is demoralized. Stakeholders are angry.

INSTRUCTIONS: Each participant independently writes down answers to:
(5 minutes of silent writing, then share)

1. WHAT WENT WRONG?
   - List specific failures, not generalities
   - Bad: "Communication was poor"
   - Good: "The backend team changed the API schema without notifying
     the frontend team, breaking the release 3 days before launch"

2. WHY DID EACH FAILURE OCCUR? (Use 5 Whys on each)

3. WHAT EARLY WARNING SIGNS DID WE IGNORE?
   - What did we notice but dismiss as "probably fine"?
   - What meeting did someone raise a concern but we moved on?

4. WHAT ASSUMPTIONS WERE WRONG?
   - Which of our Stage 4 assumptions turned out to be false?

5. WHAT WOULD HAVE PREVENTED EACH FAILURE?
   - Be specific about processes, checks, or decisions

SYNTHESIS & MITIGATION:
   Group similar failures into themes.
   For each theme, create a concrete mitigation:
   
   Theme: API Contract Breakage
   Mitigation: 
     - Publish API contracts (OpenAPI spec) before implementation
     - Automated contract tests that run on every PR
     - Designated API steward who approves all schema changes
     - Bi-weekly cross-team sync for API consumers

   Theme: Scope Creep from Stakeholder Requests
   Mitigation:
     - Formal change request process with impact assessment
     - Stakeholder prioritization meeting every sprint
     - Clear "minimum viable" definition agreed by all parties
```

#### SCAMPER Technique

SCAMPER provides seven lenses to re-examine an existing solution or problem.

```
S -- SUBSTITUTE: What can we replace?
    "What if we substituted PostgreSQL with SQLite for this use case?"
    "What if we replaced synchronous calls with async?"

C -- COMBINE: What can we merge or integrate?
    "Can we combine the user profile and settings into one view?"
    "Can we merge the two microservices that always deploy together?"

A -- ADAPT: What can we borrow from elsewhere?
    "How does Amazon handle this same problem at scale?"
    "Can we adapt the caching strategy from the search service?"

M -- MODIFY (Magnify/Minify): What if we change magnitude?
    "What if we stored only the last 30 days of data instead of all history?"
    "What if we indexed every column instead of just the primary key?"
    "What if the timeout was 500ms instead of 30s?"

P -- PUT TO ANOTHER USE: Can this solve a different problem?
    "The audit log already captures all changes; can it serve as event sourcing?"
    "The health check endpoint could double as a lightweight status API"

E -- ELIMINATE: What can we remove?
    "Do we actually need user registration? Can we use OAuth only?"
    "What happens if we remove this entire middleware layer?"

R -- REARRANGE (Reverse): What if we change the order or invert?
    "What if we deployed the database migration BEFORE the code change?"
    "What if the client pushed data to the server instead of the server polling?"
    "What if we rendered server-side first, then hydrated client-side?"
```

#### Six Thinking Hats

A parallel thinking technique where the group "wears" one hat at a time.

```
WHITE HAT -- Facts, Data, Information
  Questions: "What do we know? What data do we have? What's missing?"
  Mindset: Neutral, objective. No interpretation, just information.

RED HAT -- Emotions, Intuition, Gut Feelings
  Questions: "How do I feel about this? What's my gut telling me?"
  Mindset: No justification needed. "I feel uneasy about the database choice."
  Time limit: 30 seconds per person.

BLACK HAT -- Critical Judgment, Risks, Weaknesses
  Questions: "What could go wrong? What are the risks? Why might this fail?"
  Mindset: Devil's advocate. The most used and most abused hat.
  Caution: Overuse leads to negativity paralysis.

YELLOW HAT -- Optimism, Benefits, Value
  Questions: "What's the best possible outcome? What value does this create?"
  Mindset: Constructive, opportunity-seeking. Counterbalances black hat.

GREEN HAT -- Creativity, Alternatives, Possibilities
  Questions: "What's a completely different way to solve this? What if there
              were no constraints? What would a startup do?"
  Mindset: No criticism allowed. Build on others' ideas.

BLUE HAT -- Process Control, Meta-Thinking
  Questions: "What hat should we use next? Are we stuck? What's our goal?"
  Mindset: The facilitator. Manages the thinking process, not the content.

USAGE PATTERNS:
  - Exploration: White (facts) -> Green (ideas) -> Yellow (benefits)
  - Evaluation: Yellow (pros) -> Black (cons) -> Red (intuition)
  - Decision: Blue (process) -> White -> Green -> Yellow -> Black -> Red -> Blue (conclude)
  - Conflict Resolution: Red (feelings) -> White (facts) -> Green (solutions)
```

---

### Stakeholder Analysis

#### Stakeholder Identification

```
PRIMARY STAKEHOLDERS -- Directly affected, use the output
  - End users of the system being built/changed
  - Developers who will maintain it
  - Operations team who will run it
  - Product owner who defined the requirements

SECONDARY STAKEHOLDERS -- Indirectly affected, provide input
  - Dependent teams (consuming your API/data)
  - Compliance/legal/security teams
  - QA/testers
  - Technical writers

TERTIARY STAKEHOLDERS -- Interested but not directly involved
  - Executive leadership
  - Other product teams
  - External partners/vendors
  - Customer support team
```

#### Stakeholder Mapping: Influence/Interest Grid

```
                         HIGH INFLUENCE
                              |
        Keep Satisfied        |       Key Players
        (Meet their needs)    |    (Actively collaborate)
                              |
   LOW INTEREST ------------+------------ HIGH INTEREST
                              |
        Minimal Effort        |       Keep Informed
        (Monitor only)        |    (Regular updates)
                              |
                         LOW INFLUENCE

Examples:
  Key Players (High Influence + High Interest):
    - Product owner, tech lead, primary users
    - Strategy: Frequent syncs, involve in decisions, seek active input

  Keep Satisfied (High Influence + Low Interest):
    - CTO, VP of Engineering, architects
    - Strategy: Concise status reports, ask for sign-off on major decisions

  Keep Informed (Low Influence + High Interest):
    - Dependent teams, QA, support team
    - Strategy: Regular broadcasts, demos, early access

  Minimal Effort (Low Influence + Low Interest):
    - Other product teams not affected, external observers
    - Strategy: Available documentation, no proactive communication
```

#### Stakeholder Priority Elicitation

For each Key Player stakeholder, document:

```
Stakeholder: [Name/Role]
Primary Concern: [What metric/outcome do they care about most?]
Definition of Done (from their perspective): [When would they consider this done?]
Communication Preference: [Sync meetings / async docs / Slack / email]
Decision Authority: [What can they approve/veto?]
Unstated Needs: [What aren't they saying but likely care about?]
```

---

### Anti-Patterns in Understanding

| Anti-Pattern | Concrete Example | Why It Fails | Fix |
|---|---|---|---|
| **Solution-jumping** | User says "query is slow" and you immediately say "add an index" without checking if the table even has 100 rows | Treats symptom, misses root cause, wastes time on wrong fix | Complete at least Stage 1-3 before proposing any solution. Count to 10 before responding with a fix. |
| **Confirmation bias** | You suspect the ORM is the bottleneck, so you only look at ORM profiling data and ignore the 30-second network timeout in the logs | Cherry-picks evidence to support preconception; misses the real issue | Actively seek disconfirming evidence. Ask: "What would prove my theory wrong?" Then go look for that. |
| **Scope creep in understanding** | A request to "fix a login button" spirals into a 3-hour analysis of the entire authentication architecture, including SSO, OAuth, MFA, and session management for a button that was missing a CSS class | Analysis becomes the product instead of the tool. Delivers zero value. | Set an analysis budget proportional to the request. A button fix gets 5 minutes of understanding. An architectural decision gets 2 hours. |
| **False consensus** | You assume "everyone agrees we should use React" because two vocal devs said so, not realizing the other 5 devs prefer Vue but didn't speak up | Silent majority stays silent. Decision lacks buy-in. Project faces passive resistance. | Use anonymous input (polls, surveys). Explicitly ask quiet participants: "I'd like to hear from people who haven't spoken yet." |
| **Context collapse** | You're so deep analyzing the database schema that you forget the original question was "how do I get a CSV export of last month's sales?" | Loses sight of the user's actual need. Produces an elegant solution to the wrong problem. | Write the original request on a sticky note. If you can't see it, you've drifted. Regularly ask: "Is what I'm doing right now actually helping answer the original question?" |
| **Premature abstraction** | Before understanding the problem domain, you start designing generic interfaces, abstract factories, and plugin architectures for a one-off script | Future-proofing a solution to an unverified problem. Adds complexity no one needs. | "You aren't gonna need it" (YAGNI). Solve the concrete problem first. Abstract only when the second concrete case appears. |
| **Expert blind spot** | You've solved this class of problem 50 times, so you skip the understanding phase entirely and apply the template solution | Every problem has unique context. The template may be 90% right, but the 10% gap might be where the real problem lives. | Deliberately adopt a "beginner's mind." Ask: "What's different about this instance of the problem?" |
| **Proxy metrics fixation** | You optimize for "queries per second" blissfully unaware that what users care about is "time to first interaction" | You improve a metric that doesn't map to user value. Dashboard looks green, users are unhappy. | Always trace metrics back to user experience. Ask: "If this number improves, will a user notice?" |
| **Groupthink cascade** | One senior person says "we should use Kubernetes" and everyone nods because challenging the senior person feels socially risky | One unchecked opinion becomes group consensus without scrutiny. Worst-case: everyone knew it was wrong but no one spoke up. | Anonymize early input. Use round-robin where everyone speaks before discussion. Designate a "10th man" to argue the opposite. |

---

### Output Templates

#### Problem Statement Template

```markdown
## Problem Statement

**One-Liner**: [Single sentence describing the core problem]

**Current State**: [What is happening now? Be specific with data.]

**Desired State**: [What should be happening? Include measurable targets.]

**Gap**: [The delta between current and desired. Quantify if possible.]

**Impact**: [Who is affected? How severe? What's the cost of inaction?]

**Stakeholders**: [Who cares about this problem and why?]

**Success Criteria**:
- [ ] [Measurable criterion 1]
- [ ] [Measurable criterion 2]
- [ ] [Measurable criterion 3]
```

#### Context Map Template

```markdown
## Context Map

### Temporal Context
- **Trigger**: [What happened that made this request arise now?]
- **History**: [Previous attempts, related issues, accrued decisions]
- **Deadline**: [When is this needed? What depends on it?]
- **Cadence**: [One-off, recurring, or ongoing?]

### Technical Context
- **Stack**: [Language, framework, database, infra]
- **Architecture**: [Monolith, microservices, event-driven, etc.]
- **Dependencies**: [External services, libraries, APIs consumed]
- **Constraints from stack**: [What the existing stack forces or prevents]

### Social Context
- **Requestor**: [Name/Role, technical level, communication style]
- **Team**: [Who will build/maintain this? Skills and capacity?]
- **Decision-makers**: [Who approves? Who can veto?]
- **Communication channels**: [Where are discussions happening?]

### Business Context
- **Business problem**: [What business need does this address?]
- **Value**: [Revenue impact, cost savings, user satisfaction, compliance]
- **Risk of not doing**: [What happens if we don't solve this?]
- **Strategic alignment**: [Does this align with current business priorities?]

### Constraint Context
- **Hard constraints**: [Non-negotiable boundaries]
- **Soft constraints**: [Negotiable boundaries with cost of change]
- **Unknowns**: [Constraints we need to verify]
```

#### Assumptions Log Template

```markdown
## Assumptions Log

| ID | Assumption | Category | Confidence | Validated? | Validation Method | Owner | Date |
|----|-----------|----------|------------|------------|-------------------|-------|------|
| A1 | The API will always return JSON | Factual | HIGH | Yes | Checked API docs | Jane | 2026-01-15 |
| A2 | Users prefer dark mode by default | Behavioral | MEDIUM | No | A/B test needed | Mark | - |
| A3 | Database migration won't cause downtime | Causal | LOW | No | Test in staging | Sarah | - |
| A4 | Auth team provides OIDC endpoint by Q2 | Temporal | MEDIUM | No | Confirm with auth team | Tom | - |

**Dangerous Assumptions (cascading if wrong)**:
- A3: If migration causes downtime, all dependent services fail
- A4: If OIDC isn't ready, authentication feature must be descoped
```

#### Decision Log Template

```markdown
## Decision Log

| ID | Decision | Options Considered | Chosen Option | Rationale | Decided By | Date | Review Date |
|----|----------|-------------------|---------------|-----------|------------|------|-------------|
| D1 | Database choice | PostgreSQL, MongoDB, CockroachDB | PostgreSQL | Team expertise, ACID requirements, existing tooling | Tech Lead | 2026-01-10 | - |
| D2 | API style | REST, GraphQL, gRPC | REST | Client simplicity, caching requirements, team familiarity | Architecture Review | 2026-01-12 | 2026-04-01 |
| D3 | Deployment strategy | Blue-green, Canary, Rolling | Canary | Gradual rollout, metric-based promotion, lower infra cost | SRE Team | 2026-01-15 | - |
```

#### Risk Register Template

```markdown
## Risk Register

| ID | Risk Description | Likelihood (1-5) | Impact (1-5) | Score | Mitigation | Contingency | Owner |
|----|-----------------|-------------------|-------------|-------|------------|-------------|-------|
| R1 | Third-party API deprecation during development | 3 | 5 | 15 | Pin API version, monitor deprecation notices | Abstract API behind adapter interface | Jane |
| R2 | Key team member leaves mid-project | 2 | 5 | 10 | Cross-train at least 2 people per component, document architecture | Have contractor contacts ready | Tom |
| R3 | Performance degradation under peak load | 3 | 4 | 12 | Load test before launch, establish auto-scaling policies | Feature flag to degrade non-critical features under load | Sarah |
| R4 | Security vulnerability found in dependency | 4 | 4 | 16 | Automated dependency scanning (Dependabot), regular updates | Incident response plan, rollback procedure | Security Team |

**Risk Score Legend**:
- 1-4: Monitor (low priority)
- 5-9: Mitigate (allocate resources)
- 10-16: Escalate (needs active mitigation plan)
- 17-25: Critical (must resolve before proceeding)
```

---

### Integration Patterns

#### How Understanding Integrates with Other Skills

The Understanding skill is a **precondition skill** -- it should be loaded and exercised BEFORE
domain-specific skills are activated. Here is the integration flow:

```
User Input
    |
    v
[Load: understanding] <---- ALWAYS FIRST
    |
    v
[Run: Understanding Pipeline (Stages 1-6)]
    |
    v
[Output: Validated Understanding]
    |
    +--> Which domains are involved?
    |
    v
[Load: domain-specific skill(s)] <---- BASED ON UNDERSTANDING OUTPUT
    |
    v
[Execute: implementation using domain skills]
    |
    v
[Load: code-reviewer] <---- AFTER IMPLEMENTATION
```

#### Specific Integration Scenarios

| Scenario | Skills to Load | Sequence |
|---|---|---|
| Bug report comes in | understanding -> (domain skill based on bug location) -> code-reviewer | Understand the bug first, then fix, then review |
| New feature request | understanding -> workflow-general -> (domain skills) -> code-reviewer | Understand the need, plan the work, implement, review |
| Architecture decision | understanding -> (all relevant domain skills) -> code-reviewer | Understand the system, evaluate options across domains, validate |
| Performance investigation | understanding -> infra-observability -> (domain skill) | Understand the symptoms, check observability data, then optimize |
| Security incident | understanding -> security-audit -> (domain skill) -> security-crypto | Understand the breach, audit the surface, fix, harden |
| Cross-team project | understanding (stakeholder analysis) -> workflow-general -> (domain skills per team) | Map stakeholders and context before any technical work |

#### Anti-Integration Patterns (What NOT to do)

```
WRONG: Load frontend-react skill immediately upon seeing "React" in the request
RIGHT: Load understanding first. The user said "React" but the problem might be
       a data fetching issue, a state management issue, or even an infra issue
       manifesting in the frontend.

WRONG: Start coding immediately because "the request is simple"
RIGHT: Run a 30-second understanding check. Even simple requests have context:
       "Add a button" -> Where? What should it do? Is there an API to call?
       What should happen on error? Loading state? Disabled state?

WRONG: Load every skill just in case
RIGHT: Load understanding, then load only the skills indicated by the synthesis.
       Skill loading has cognitive and context cost. Be surgical.
```

---

### Maturity Model

#### Level 0: Unconscious Incompetence

**Characteristics**:
- Jumps directly to solutions without any understanding phase
- Cannot articulate the difference between what was said and what was meant
- Treats all requests as equally well-specified
- Frequently builds the wrong thing or solves the wrong problem

**Symptoms**:
- High rate of rework due to misunderstood requirements
- Stakeholders say "that's not what I asked for"
- Solutions are technically correct but contextually wrong

**Path to Level 1**: Recognize that understanding is a separate, explicit phase of work.
Start by asking "What problem are we solving?" before every task.

#### Level 1: Conscious Incompetence (Beginner)

**Characteristics**:
- Aware that understanding is important but inconsistent in applying it
- Asks clarifying questions but doesn't have a systematic approach
- Sometimes catches misunderstandings before they become problems
- Can identify the 5 context dimensions but doesn't always check all of them

**Practice**:
- Before every task, write down: "The problem is ___" and "We'll know it's solved when ___"
- Keep an informal assumptions list (even if just mental)
- After completing a task, check: Did the understanding match reality?

**Checklist**:
- [ ] Asked at least one clarifying question
- [ ] Identified who the primary stakeholder is
- [ ] Stated the problem in my own words before starting

#### Level 2: Competent Practitioner (Intermediate)

**Characteristics**:
- Consistently runs the Understanding Pipeline before implementation
- Maintains written assumption logs and decision logs for significant work
- Can switch between brainstorming frameworks based on problem type
- Recognizes when understanding is sufficient vs. when more analysis is needed
- Uses questioning frameworks (5 Whys, Socratic) effectively

**Practice**:
- Document assumptions and validate high-risk ones before committing to a solution
- Use pre-mortems for significant projects or architectural decisions
- Apply First-Principles Decomposition to novel problems
- Explicitly map stakeholders and their priorities

**Checklist**:
- [ ] All 6 pipeline stages completed (depth proportional to task size)
- [ ] Top 3 assumptions validated or flagged for verification
- [ ] Cross-domain interactions analyzed
- [ ] Understanding confirmed with requestor before implementation

#### Level 3: Advanced Practitioner

**Characteristics**:
- Intuitively senses when understanding is incomplete, even without explicit signals
- Teaches and facilitates understanding frameworks for teams
- Can run design thinking sprints and pre-mortems with groups
- Seamlessly integrates stakeholder analysis into technical decision-making
- Recognizes organizational patterns that block understanding (e.g., "the HIPPO effect"
  where the Highest Paid Person's Opinion overrides analysis)

**Practice**:
- Facilitate pre-mortems and design sprints for the team
- Train junior developers in the Understanding Pipeline
- Use SCAMPER and Six Thinking Hats in group decision-making
- Build understanding artifacts (assumption logs, context maps) that outlive the project

**Checklist**:
- [ ] Understanding artifacts are referenceable by the team months later
- [ ] Can facilitate a pre-mortem that reveals risks the team hadn't considered
- [ ] Stakeholders report feeling "truly heard" after interaction
- [ ] Decision log shows explicit trade-offs, not just outcomes

#### Level 4: Mastery

**Characteristics**:
- Understanding is a superpower applied to organizational-level problems, not just technical ones
- Can diagnose and fix broken understanding processes in teams and organizations
- Designs systems and processes that bake understanding into the workflow
- Recognizes when the problem is not technical but epistemological (how the org knows things)
- Moves fluidly between all frameworks, inventing hybrid approaches when needed

**Practice**:
- Diagnose organizational anti-patterns: "This team doesn't understand their users because
  there's no feedback loop between support tickets and the product backlog"
- Design understanding systems: requirements intake processes, stakeholder feedback loops,
  decision-making frameworks for complex organizations
- Coach technical leaders on how to build a culture of deep understanding

**Hallmarks**:
- Projects consistently solve the right problem on the first attempt
- Teams you've worked with adopt understanding practices independently
- You're called in not for technical expertise but for problem-clarification expertise
- You can predict project failure modes during the first stakeholder conversation
