---
name: brainstorming
description: God-tier interactive brainstorming: SCAMPER, Six Thinking Hats, TRIZ, First Principles, Systems Thinking, Lateral Thinking, Socratic Questioning, Divergent/Convergent thinking, Decision Matrices, Creative Problem Solving, and interactive dialogue patterns for deep exploration with lore-master
license: MIT
compatibility: opencode
metadata:
  audience: all-developers
  domain: workflow
  paradigm: analytical
  capabilities:
    - interactive-brainstorming
    - divergent-thinking
    - convergent-thinking
    - first-principles-analysis
    - systems-thinking
    - lateral-thinking
    - scamper-technique
    - six-thinking-hats
    - triz-methodology
    - socratic-questioning
    - decision-matrix
    - creative-problem-solving
    - assumption-challenging
    - scenario-planning
    - pre-mortem-analysis
  prerequisites: none
  integrates_with:
    - understanding
    - prompt-engineering
    - workflow-general
    - all domain-specific skills
---

## Brainstorming Skill — God-Tier Interactive Exploration

### Core Philosophy

> **Brainstorming is not "throwing ideas at a wall." It is structured exploration of possibility space.**
> The best ideas emerge at the intersection of divergent thinking (expand) and convergent thinking (focus).

```
┌─────────────────────────────────────────────────────────────┐
│              BRAINSTORMING FLOW                               │
│                                                              │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│   │ DIVERGE  │───▶│ EXPLORE  │───▶│ CONVERGE │              │
│   │ (Expand) │    │ (Connect)│    │ (Focus)  │              │
│   └──────────┘    └──────────┘    └──────────┘              │
│        │               │               │                    │
│        ▼               ▼               ▼                    │
│   Generate         Find             Select                 │
│   possibilities    patterns         best option            │
│   (no judgment)    (synthesize)     (criteria-based)       │
│                                                            │
│   Techniques:      Techniques:      Techniques:            │
│   • SCAMPER        • Systems Map    • Decision Matrix      │
│   • Six Hats       • Analogy        • Weighted Score       │
│   • Random Input   • Cross-domain   • Pre-mortem           │
│   • What-if        • Pattern match  • Feasibility filter   │
│                                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Interactive Brainstorming Protocol

### 1.1 Session Structure

Every brainstorming session follows this flow:

```
┌─────────────────────────────────────────────────────────┐
│              SESSION FLOW                                │
│                                                         │
│  Phase 1: FRAMING (2-3 min)                             │
│  ├─ Define the problem/question                         │
│  ├─ Set constraints & boundaries                        │
│  └─ Establish success criteria                          │
│                                                         │
│  Phase 2: DIVERGENCE (5-10 min)                         │
│  ├─ Generate ideas (quantity > quality)                 │
│  ├─ No judgment, no filtering                           │
│  └─ Push boundaries: "What if...?"                      │
│                                                         │
│  Phase 3: EXPLORATION (5-10 min)                        │
│  ├─ Connect ideas across domains                        │
│  ├─ Find patterns & synergies                           │
│  └─ Challenge assumptions                               │
│                                                         │
│  Phase 4: CONVERGENCE (3-5 min)                         │
│  ├─ Apply selection criteria                            │
│  ├─ Score & rank options                                │
│  └─ Select top 3 candidates                             │
│                                                         │
│  Phase 5: VALIDATION (2-3 min)                          │
│  ├─ Pre-mortem: "If this fails, why?"                   │
│  ├─ Feasibility check                                   │
│  └─ Next steps                                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Interactive Dialogue Pattern

Lore-master uses this pattern during brainstorming:

```
USER: [presents problem/idea]

LORE-MASTER:
┌─ PHASE 1: FRAMING
│  "Let me make sure I understand. You want to [restate].
│   Is that correct? Any constraints I should know about?"
│
├─ PHASE 2: DIVERGENCE
│  "Here are 10 possibilities, no filtering:
│   1. ...
│   2. ...
│   ...
│   10. ...
│   Which direction interests you most?"
│
├─ PHASE 3: EXPLORATION
│  "Interesting. Let's go deeper on #[selected].
│   What if we combine it with #[another idea]?
│   What assumption are we making here?
│   What would [expert in X] say about this?"
│
├─ PHASE 4: CONVERGENCE
│   "Based on [criteria], here's how they rank:
│    1. Option A — Score: 8.5/10 — Why: ...
│    2. Option B — Score: 7.2/10 — Why: ...
│    3. Option C — Score: 6.8/10 — Why: ...
│    My recommendation: Option A because ..."
│
└─ PHASE 5: VALIDATION
   "Before we commit, let's do a pre-mortem:
    If this fails in 6 months, what went wrong?
    ...
    Given these risks, should we:
    a) Proceed with mitigation plan
    b) Pivot to Option B
    c) Explore further"
```

---

## 2. Brainstorming Frameworks

### 2.1 SCAMPER Technique

Systematic idea generation by modifying existing concepts:

| Letter | Action | Questions | Example |
|--------|--------|-----------|---------|
| **S** — Substitute | Replace something | "What can we swap out?" | Replace database with cache-first |
| **C** — Combine | Merge elements | "What can we combine?" | Merge auth + rate limiting |
| **A** — Adapt | Adjust for new context | "What else is like this?" | Adapt React patterns for Svelte |
| **M** — Modify/Magnify | Change scale/attributes | "What if we make it bigger/smaller?" | Scale from single to multi-tenant |
| **P** — Put to other use | Repurpose | "Where else could this work?" | Use event sourcing for audit log |
| **E** — Eliminate | Remove elements | "What can we remove?" | Remove middleware layer |
| **R** — Reverse/Rearrange | Invert or reorder | "What if we do the opposite?" | Client renders, server validates |

**Interactive Template:**
```
Let's apply SCAMPER to [problem/concept]:

**S** — What can we substitute?
→ [idea 1], [idea 2], [idea 3]

**C** — What can we combine?
→ [idea 1], [idea 2], [idea 3]

**A** — What can we adapt?
→ [idea 1], [idea 2], [idea 3]

**M** — What can we modify?
→ [idea 1], [idea 2], [idea 3]

**P** — What other uses?
→ [idea 1], [idea 2], [idea 3]

**E** — What can we eliminate?
→ [idea 1], [idea 2], [idea 3]

**R** — What can we reverse?
→ [idea 1], [idea 2], [idea 3]

Now, which of these 21 ideas has the most potential?
```

### 2.2 Six Thinking Hats

Explore a problem from 6 distinct perspectives:

```
┌─────────────────────────────────────────────────────────┐
│              SIX THINKING HATS                           │
│                                                         │
│   ⚪ WHITE (Facts)          🔴 RED (Emotions)           │
│   "What do we know?"        "How do we feel about it?"  │
│   Data, info, gaps          Intuition, gut, concerns    │
│                                                         │
│   ⚫ BLACK (Caution)        🟡 YELLOW (Optimism)         │
│   "What could go wrong?"    "What could go right?"      │
│   Risks, flaws, limits      Benefits, value, upside     │
│                                                         │
│   🟢 GREEN (Creativity)     🔵 BLUE (Process)            │
│   "What are new ideas?"     "What's our next step?"     │
│   Alternatives, innovation  Structure, action plan      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Interactive Template:**
```
Let's examine [problem] through all 6 hats:

⚪ **WHITE HAT** (Facts)
- What we know: [facts]
- What we don't know: [gaps]
- Data available: [data]

🔴 **RED HAT** (Emotions/Intuition)
- Gut feeling: [intuition]
- Concerns: [worries]
- Excitement: [what's exciting]

⚫ **BLACK HAT** (Caution/Risks)
- What could fail: [risks]
- Worst case: [worst scenario]
- Constraints: [limitations]

🟡 **YELLOW HAT** (Optimism/Benefits)
- Best case: [best scenario]
- Benefits: [advantages]
- Opportunities: [opportunities]

🟢 **GREEN HAT** (Creativity/New Ideas)
- Alternative approaches: [ideas]
- What if we: [wild ideas]
- Unconventional: [out-of-box ideas]

🔵 **BLUE HAT** (Process/Next Steps)
- Summary: [key takeaways]
- Decision: [what to do]
- Next step: [action item]
```

### 2.3 TRIZ Methodology

Theory of Inventive Problem Solving — systematic innovation.

**40 Inventive Principles (Top 15 for Software):**

| # | Principle | Software Application |
|---|-----------|---------------------|
| 1 | Segmentation | Microservices, modular architecture |
| 2 | Extraction | Extract shared logic into library |
| 3 | Local Quality | Optimize hot paths, leave rest simple |
| 5 | Merging | Combine services, reduce network calls |
| 7 | Nested Doll | Embed functionality within functionality |
| 8 | Anti-Weight | Use async to reduce blocking |
| 10 | Preliminary Action | Pre-compute, cache, pre-warm |
| 13 | The Other Way Round | Invert control, reverse data flow |
| 15 | Dynamics | Adaptive algorithms, auto-scaling |
| 19 | Periodic Action | Cron jobs, batch processing |
| 24 | Intermediary | Message queue, proxy, API gateway |
| 28 | Mechanics Substitution | Replace polling with webhooks |
| 32 | Color Changes | Use metadata/tags for classification |
| 35 | Parameter Changes | Change data types, encoding |
| 38 | Strong Oxidants | Use powerful tools (AI, automation) |

**Contradiction Matrix Pattern:**
```
Problem: We want [improving parameter] but it worsens [worsening parameter].

Example: We want faster response time but it increases memory usage.

TRIZ suggests these principles:
1. Principle 10 (Preliminary Action) → Pre-compute results
2. Principle 28 (Mechanics Substitution) → Use cache instead of DB
3. Principle 35 (Parameter Changes) → Change data structure

Apply each principle and evaluate.
```

### 2.4 First Principles Thinking

Deconstruct to fundamental truths, rebuild from scratch.

```
┌─────────────────────────────────────────────────────────┐
│              FIRST PRINCIPLES PROCESS                     │
│                                                         │
│  Step 1: IDENTIFY ASSUMPTIONS                           │
│  "What are we assuming to be true?"                     │
│  → List every assumption                                │
│                                                         │
│  Step 2: CHALLENGE EACH ASSUMPTION                      │
│  "Is this actually true? What evidence?"                │
│  → Question every assumption                            │
│  → Find which are facts vs. beliefs                     │
│                                                         │
│  Step 3: DECONSTRUCT TO FUNDAMENTALS                    │
│  "What are the irreducible truths?"                     │
│  → Physics, math, economics, human behavior             │
│  → Things that cannot be further reduced                │
│                                                         │
│  Step 4: REBUILD FROM SCRATCH                           │
│  "Given only these fundamentals, what's optimal?"       │
│  → Design without legacy constraints                    │
│  → Often produces radically different solutions         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Interactive Template:**
```
Let's apply First Principles to [problem]:

**Step 1: Assumptions**
1. [assumption 1]
2. [assumption 2]
3. [assumption 3]

**Step 2: Challenge**
- Assumption 1: Is this true? → [analysis] → [fact or belief?]
- Assumption 2: Is this true? → [analysis] → [fact or belief?]
- Assumption 3: Is this true? → [analysis] → [fact or belief?]

**Step 3: Fundamentals**
- Irreducible truth 1: [truth]
- Irreducible truth 2: [truth]
- Irreducible truth 3: [truth]

**Step 4: Rebuild**
Given only these truths, the optimal solution is:
[solution built from scratch, ignoring existing approaches]
```

### 2.5 Systems Thinking

View problems as interconnected systems, not isolated parts.

**Key Concepts:**
- **Feedback loops**: Reinforcing (amplifies) vs. Balancing (stabilizes)
- **Stocks & flows**: Accumulations vs. rates of change
- **Delays**: Time between action and effect
- **Leverage points**: Where small changes produce big results
- **Emergence**: System behavior that parts don't have individually

**Systems Map Template:**
```
┌─────────────────────────────────────────────────────────┐
│              SYSTEMS MAP: [Problem]                      │
│                                                         │
│   [Element A] ──(+)──▶ [Element B] ──(+)──▶ [Element C] │
│       │                                    │            │
│       │              (-)                    │            │
│       └────────────────────────────────────┘            │
│                                                         │
│   Legend:                                               │
│   (+) = Reinforcing (more A → more B)                   │
│   (-) = Balancing (more A → less B)                     │
│   (delay) = Time lag between cause and effect           │
│                                                         │
│   Feedback Loops:                                       │
│   R1: A → B → C → A (reinforcing)                       │
│   B1: A → C → A (balancing)                             │
│                                                         │
│   Leverage Points:                                      │
│   1. [element] — small change here has big impact       │
│   2. [element] — high sensitivity                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2.6 Lateral Thinking

Solve problems through indirect, creative approaches.

**Techniques:**

| Technique | How | Example |
|-----------|-----|---------|
| **Random Input** | Introduce unrelated concept | "What if we apply restaurant menu design to API design?" |
| **Provocation** | Make impossible statement | "What if the database didn't exist?" |
| **Challenge** | Question the obvious | "Why must it be a web app? Why not CLI?" |
| **Concept Extraction** | Extract principle from one domain, apply to another | "Subscription model from SaaS → apply to infrastructure" |
| **Reversal** | Flip the problem | Instead of "how to make it faster" → "how to make it feel faster" |
| **Analogy** | Map to different domain | "This is like a traffic light system..." |

**Interactive Template:**
```
Let's think laterally about [problem]:

**Random Input**: [random word/concept]
→ How does this relate? [connection]
→ What idea emerges? [idea]

**Provocation**: "What if [impossible statement]?"
→ If that were true, what would change? [analysis]
→ What partial version is possible? [practical idea]

**Challenge**: "Why do we assume [obvious thing]?"
→ Is there another way? [alternative]

**Reversal**: Instead of "[normal approach]", what if "[opposite]"?
→ What does this reveal? [insight]

**Analogy**: This is like [different domain] because [reason].
→ How do they solve it there? [transferable idea]
```

### 2.7 Socratic Questioning

Deep exploration through disciplined questioning.

**6 Types of Socratic Questions:**

| Type | Purpose | Examples |
|------|---------|----------|
| **Clarification** | Understand the question | "What do you mean by...?" "Can you rephrase?" |
| **Assumption** | Challenge premises | "What are we assuming?" "Is this always true?" |
| **Evidence** | Demand proof | "What data supports this?" "How do we know?" |
| **Perspective** | Explore viewpoints | "How would [stakeholder] see this?" "What's the counter-argument?" |
| **Implication** | Explore consequences | "If we do this, what follows?" "What are the second-order effects?" |
| **Question** | Meta-questioning | "Is this the right question?" "What question should we be asking?" |

**Interactive Template:**
```
Let's explore [problem] through Socratic questioning:

**Clarification**: What exactly are we trying to solve?
→ [restated problem]

**Assumption**: What are we taking for granted?
→ [assumption 1], [assumption 2], [assumption 3]
→ Are these valid? [analysis]

**Evidence**: What supports our current approach?
→ [evidence for], [evidence against]

**Perspective**: How would different stakeholders view this?
→ User: [viewpoint]
→ Developer: [viewpoint]
→ Business: [viewpoint]
→ Security: [viewpoint]

**Implication**: If we proceed, what are the consequences?
→ First-order: [direct effect]
→ Second-order: [indirect effect]
→ Third-order: [unexpected effect]

**Meta-Question**: Are we asking the right question?
→ Original: "[original question]"
→ Better: "[reframed question]"
```

---

## 3. Decision-Making Frameworks

### 3.1 Decision Matrix

Score options against weighted criteria.

```
┌─────────────────────────────────────────────────────────┐
│              DECISION MATRIX                             │
│                                                         │
│  Criteria          Weight   Option A   Option B   Option C│
│  ─────────────────────────────────────────────────────  │
│  Feasibility        0.25      8          6          9    │
│  Impact             0.25      7          9          5    │
│  Cost               0.15      6          8          7    │
│  Risk               0.15      7          5          8    │
│  Time to implement  0.10      8          7          6    │
│  Scalability        0.10      6          8          7    │
│  ─────────────────────────────────────────────────────  │
│  WEIGHTED SCORE              7.15       7.15       7.10  │
│                                                         │
│  Winner: Option A & B (tie) → need tiebreaker           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Interactive Template:**
```
Let's score our options:

**Criteria & Weights** (total = 1.0):
1. [criterion 1]: [weight]
2. [criterion 2]: [weight]
3. [criterion 3]: [weight]
...

**Scores** (1-10 scale):
| Criteria | Weight | Option A | Option B | Option C |
|----------|--------|----------|----------|----------|
| ... | ... | ... | ... | ... |

**Weighted Scores:**
- Option A: [score]
- Option B: [score]
- Option C: [score]

**Recommendation**: [winner] because [reason]
```

### 3.2 Pre-Mortem Analysis

Assume failure, work backward to find causes.

```
┌─────────────────────────────────────────────────────────┐
│              PRE-MORTEM: [Project/Decision]              │
│                                                         │
│  Scenario: It's 6 months from now. The project failed.  │
│  Why did it fail?                                        │
│                                                         │
│  Technical Causes:                                      │
│  1. [cause] — Likelihood: [H/M/L] — Impact: [H/M/L]    │
│  2. [cause] — Likelihood: [H/M/L] — Impact: [H/M/L]    │
│                                                         │
│  Process Causes:                                        │
│  1. [cause] — Likelihood: [H/M/L] — Impact: [H/M/L]    │
│  2. [cause] — Likelihood: [H/M/L] — Impact: [H/M/L]    │
│                                                         │
│  External Causes:                                       │
│  1. [cause] — Likelihood: [H/M/L] — Impact: [H/M/L]    │
│  2. [cause] — Likelihood: [H/M/L] — Impact: [H/M/L]    │
│                                                         │
│  Mitigation Plan:                                       │
│  For each high-likelihood + high-impact cause:          │
│  → Prevention: [what to do now]                         │
│  → Detection: [how to catch early]                      │
│  → Response: [what to do if it happens]                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 3.3 Eisenhower Matrix for Ideas

Prioritize ideas by urgency and importance.

```
┌─────────────────────────────────────────────────────────┐
│              EISENHOWER MATRIX: Ideas                    │
│                                                         │
│                  URGENT          NOT URGENT              │
│              ┌──────────────┬──────────────────┐        │
│   IMPORTANT  │  DO NOW      │  SCHEDULE        │        │
│              │  Quick wins   │  Strategic bets  │        │
│              │  [ideas]      │  [ideas]         │        │
│              ├──────────────┼──────────────────┤        │
│  NOT         │  DELEGATE    │  ELIMINATE       │        │
│  IMPORTANT   │  Nice-to-have │  Distractions    │        │
│              │  [ideas]      │  [ideas]         │        │
│              └──────────────┴──────────────────┘        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Advanced Brainstorming Techniques

### 4.1 Divergent Thinking Expansion

Generate maximum ideas quickly:

| Technique | Description | Prompt |
|-----------|-------------|--------|
| **Brainwriting** | Write ideas silently, build on others | "Write 10 ideas in 2 minutes" |
| **Round Robin** | Each person adds one idea in turn | "Your turn: one idea" |
| **Starbursting** | Generate questions, not answers | "What questions should we ask?" |
| **Worst Possible Idea** | Intentionally bad ideas → flip to good | "What's the worst solution?" → invert |
| **10x Thinking** | What if we need 10x improvement? | "How would we 10x this?" |
| **Constraint Removal** | Remove all constraints | "If money/time/tech were unlimited..." |
| **Cross-Pollination** | Import ideas from unrelated fields | "How does [industry] solve this?" |

### 4.2 Convergent Thinking Filters

Narrow down to best options:

| Filter | Question | Purpose |
|--------|----------|---------|
| **Feasibility** | "Can we actually build this?" | Technical reality check |
| **Viability** | "Should we build this?" | Business value check |
| **Desirability** | "Do users want this?" | User needs check |
| **Alignment** | "Does this fit our strategy?" | Strategic fit check |
| **Uniqueness** | "Is this differentiated?" | Competitive advantage check |
| **Speed** | "How fast can we deliver?" | Time-to-market check |

### 4.3 Idea Combination Matrix

Systematically combine ideas to create hybrids.

```
┌─────────────────────────────────────────────────────────┐
│              IDEA COMBINATION MATRIX                     │
│                                                         │
│              Idea A      Idea B      Idea C              │
│  Idea A      —          A+B         A+C                 │
│  Idea B      A+B         —          B+C                 │
│  Idea C      A+C        B+C          —                  │
│                                                         │
│  Evaluate each combination:                             │
│  A+B: [synergy description] — Score: [1-10]            │
│  A+C: [synergy description] — Score: [1-10]            │
│  B+C: [synergy description] — Score: [1-10]            │
│                                                         │
│  Best combination: [winner] because [reason]            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.4 Scenario Planning

Explore multiple futures.

```
┌─────────────────────────────────────────────────────────┐
│              SCENARIO PLANNING                           │
│                                                         │
│  Key Uncertainties:                                     │
│  1. [uncertainty 1]: [low] ←——→ [high]                  │
│  2. [uncertainty 2]: [low] ←——→ [high]                  │
│                                                         │
│  Four Scenarios:                                        │
│  ┌──────────────┬──────────────┐                        │
│  │ Scenario 1   │ Scenario 2   │                        │
│  │ Low U1       │ High U1      │                        │
│  │ Low U2       │ Low U2       │                        │
│  │ [name]       │ [name]       │                        │
│  ├──────────────┼──────────────┤                        │
│  │ Scenario 3   │ Scenario 4   │                        │
│  │ Low U1       │ High U1      │                        │
│  │ High U2      │ High U2      │                        │
│  │ [name]       │ [name]       │                        │
│  └──────────────┴──────────────┘                        │
│                                                         │
│  For each scenario:                                     │
│  - What happens?                                        │
│  - What's our response?                                 │
│  - What early signals would indicate this scenario?     │
│                                                         │
│  Robust strategy: works well across ALL scenarios       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.5 Assumption Mapping

Identify, validate, and prioritize assumptions.

```
┌─────────────────────────────────────────────────────────┐
│              ASSUMPTION MAP                              │
│                                                         │
│                  HIGH IMPACT     LOW IMPACT              │
│              ┌──────────────┬──────────────────┐        │
│   HIGH       │  TEST FIRST  │  TEST SECOND     │        │
│   UNCERTAINTY│  Critical    │  Important       │        │
│              │  [assumptions]│  [assumptions]   │        │
│              ├──────────────┼──────────────────┤        │
│   LOW        │  MONITOR     │  ACCEPT          │        │
│   UNCERTAINTY│  Watch for   │  Low risk        │        │
│              │  changes     │  [assumptions]   │        │
│              └──────────────┴──────────────────┘        │
│                                                         │
│  For each "Test First" assumption:                      │
│  - Assumption: [statement]                              │
│  - How to test: [experiment]                            │
│  - Success criteria: [metric]                           │
│  - Timeline: [when to test]                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Interactive Brainstorming Commands

### 5.1 Quick Commands

During a brainstorming session, user can trigger:

| Command | Effect |
|---------|--------|
| `/diverge` | Generate 20+ ideas, no filtering |
| `/converge` | Score and rank current ideas |
| `/scamper` | Apply SCAMPER to selected idea |
| `/hats` | Apply Six Thinking Hats analysis |
| `/first-principles` | Deconstruct to fundamentals |
| `/systems` | Create systems map |
| `/lateral` | Apply lateral thinking techniques |
| `/socratic` | Deep questioning session |
| `/pre-mortem` | Assume failure, find causes |
| `/combine` | Create idea combination matrix |
| `/scenario` | Generate scenario planning matrix |
| `/assumptions` | Map and prioritize assumptions |
| `/10x` | Think 10x bigger |
| `/reverse` | Reverse the problem |
| `/random` | Introduce random input for creativity |
| `/worst` | Generate worst possible ideas, then invert |

### 5.2 Session Control

| Command | Effect |
|---------|--------|
| `/start [topic]` | Begin brainstorming session |
| `/focus [idea#]` | Deep dive on specific idea |
| `/park [idea#]` | Park idea for later |
| `/merge [idea#] [idea#]` | Combine two ideas |
| `/score [criteria]` | Add scoring criteria |
| `/export` | Export session summary |
| `/end` | End session with summary |

---

## 6. Brainstorming Quality Checklist

Before ending any brainstorming session, verify:

- [ ] **Divergence achieved**: Generated 10+ distinct ideas
- [ ] **No premature judgment**: Ideas were not filtered during generation
- [ ] **Multiple perspectives**: Explored from at least 3 angles
- [ ] **Assumptions surfaced**: Listed and challenged key assumptions
- [ ] **Connections made**: Found synergies between ideas
- [ ] **Convergence applied**: Scored and ranked top options
- [ ] **Pre-mortem done**: Identified failure modes
- [ ] **Next steps clear**: Action items defined for top choice
- [ ] **Parked ideas saved**: Good-but-not-now ideas documented
- [ ] **Session exported**: Summary captured for future reference

---

## 7. Common Brainstorming Anti-Patterns

| Anti-Pattern | Symptom | Fix |
|--------------|---------|-----|
| **Premature convergence** | Jumping to first good idea | Force divergence: "Give me 10 more" |
| **Groupthink** | Everyone agrees too quickly | Assign devil's advocate role |
| **Anchoring** | Fixating on first idea | Use anonymous brainstorming first |
| **HiPPO effect** | Highest paid person's opinion wins | Score ideas objectively with matrix |
| **Analysis paralysis** | Over-analyzing, no decision | Time-box: "Decide in 5 minutes" |
| **Idea hoarding** | Not sharing ideas | Use brainwriting (silent first) |
| **Solution jumping** | Solving before understanding | Force problem exploration first |
| **Scope creep** | Brainstorming expands endlessly | Define boundaries upfront |
| **No follow-through** | Great session, no action | End with concrete next steps |
| **Echo chamber** | Same perspectives repeated | Force perspective shifts (Six Hats) |

---

## 8. Brainstorming Session Templates

### 8.1 Technical Architecture Brainstorm

```
# Architecture Brainstorm: [System Name]

## Context
- Current state: [description]
- Problem: [what needs solving]
- Constraints: [budget, time, tech, team]
- Success criteria: [how we know it worked]

## Divergence (15 min)
Generate architecture approaches:
1. [approach 1]
2. [approach 2]
...
10. [approach 10]

## Exploration (10 min)
For top 3 approaches:
- Pros: [list]
- Cons: [list]
- Trade-offs: [list]
- Unknowns: [list]

## Convergence (5 min)
Decision matrix scoring:
| Criteria | Weight | Option A | Option B | Option C |
|----------|--------|----------|----------|----------|
| ... | ... | ... | ... | ... |

## Pre-Mortem (5 min)
If chosen approach fails, why?
1. [cause] → Mitigation: [plan]
2. [cause] → Mitigation: [plan]

## Decision
Selected: [option]
Reason: [justification]
Next step: [action]
```

### 8.2 Product Feature Brainstorm

```
# Feature Brainstorm: [Product Area]

## User Problem
- Who: [persona]
- What: [pain point]
- Why it matters: [impact]

## Divergence (15 min)
Feature ideas:
1. [idea 1]
2. [idea 2]
...
15. [idea 15]

## Prioritization (10 min)
Eisenhower Matrix:
- DO NOW: [quick wins]
- SCHEDULE: [strategic bets]
- DELEGATE: [nice-to-haves]
- ELIMINATE: [distractions]

## Validation (5 min)
For top 3 features:
- User value: [high/med/low]
- Effort: [XS/S/M/L/XL]
- RICE score: [Reach × Impact × Confidence / Effort]

## Decision
Build first: [feature]
Reason: [RICE score + strategic fit]
Next step: [spec + design]
```

### 8.3 Problem-Solving Brainstorm

```
# Problem-Solving: [Problem Statement]

## Problem Definition
- What's happening: [description]
- Impact: [severity, frequency]
- Root cause hypothesis: [theory]

## First Principles (10 min)
Assumptions:
1. [assumption] → Valid? [yes/no] → Evidence: [data]
2. [assumption] → Valid? [yes/no] → Evidence: [data]

Fundamentals:
1. [irreducible truth]
2. [irreducible truth]

## Divergence (10 min)
Solutions:
1. [solution 1]
2. [solution 2]
...
10. [solution 10]

## SCAMPER (10 min)
Apply SCAMPER to top solution:
- S: [substitution idea]
- C: [combination idea]
- A: [adaptation idea]
- M: [modification idea]
- P: [put-to-other-use idea]
- E: [elimination idea]
- R: [reversal idea]

## Decision Matrix (5 min)
| Criteria | Weight | Option A | Option B | Option C |
|----------|--------|----------|----------|----------|
| Effectiveness | 0.30 | ... | ... | ... |
| Feasibility | 0.25 | ... | ... | ... |
| Speed | 0.20 | ... | ... | ... |
| Cost | 0.15 | ... | ... | ... |
| Risk | 0.10 | ... | ... | ... |

## Pre-Mortem (5 min)
If solution fails:
1. [cause] → Prevention: [plan]
2. [cause] → Prevention: [plan]

## Decision
Selected: [option]
Implementation plan: [steps]
Success metric: [how to measure]
```

---

## 9. Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                  BRAINSTORMING CHEAT SHEET                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SESSION FLOW:                                              │
│  Frame → Diverge → Explore → Converge → Validate           │
│                                                             │
│  DIVERGENCE TECHNIQUES:                                     │
│  • SCAMPER: Substitute, Combine, Adapt, Modify,            │
│    Put to use, Eliminate, Reverse                           │
│  • Six Hats: White, Red, Black, Yellow, Green, Blue        │
│  • Lateral: Random input, Provocation, Reversal, Analogy   │
│  • 10x: "How would we 10x this?"                           │
│  • Worst idea: Generate terrible ideas, then invert        │
│                                                             │
│  CONVERGENCE TECHNIQUES:                                    │
│  • Decision Matrix: Score options × weighted criteria      │
│  • Eisenhower: Urgent/Important matrix                     │
│  • RICE: Reach × Impact × Confidence / Effort              │
│  • Feasibility filter: Can we actually build it?           │
│                                                             │
│  VALIDATION TECHNIQUES:                                     │
│  • Pre-mortem: Assume failure, find causes                 │
│  • Assumption map: Identify & prioritize assumptions       │
│  • Scenario planning: Explore multiple futures             │
│                                                             │
│  MAGIC QUESTIONS:                                           │
│  • "What assumption are we making?"                        │
│  • "What would [expert] say?"                              │
│  • "What if the opposite were true?"                       │
│  • "What's the simplest version that works?"               │
│  • "What are we not seeing?"                               │
│  • "If we had to ship tomorrow, what would we cut?"        │
│                                                             │
│  ANTI-PATTERNS TO AVOID:                                    │
│  ✗ Jumping to first good idea                              │
│  ✗ Filtering ideas during generation                       │
│  ✗ Not challenging assumptions                             │
│  ✗ No pre-mortem analysis                                  │
│  ✗ Great session, no action items                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 10. Implementation Checklist

Before starting a brainstorming session:

- [ ] **Problem defined**: Clear problem statement written
- [ ] **Constraints known**: Budget, time, tech, team limits identified
- [ ] **Success criteria**: How we'll know we succeeded
- [ ] **Participants**: Who needs to be involved
- [ ] **Time-boxed**: Session duration set (typically 30-60 min)
- [ ] **Tools ready**: Whiteboard, sticky notes, or digital tool
- [ ] **No distractions**: Phones away, focus mode on

During session:

- [ ] **Divergence first**: Generate before evaluating
- [ ] **No judgment**: All ideas welcome during generation
- [ ] **Build on ideas**: "Yes, and..." not "Yes, but..."
- [ ] **Track everything**: Capture all ideas, don't lose any
- [ ] **Watch time**: Move phases on schedule

After session:

- [ ] **Top 3 identified**: Clear ranking of best options
- [ ] **Pre-mortem done**: Failure modes identified
- [ ] **Next steps defined**: Action items with owners & deadlines
- [ ] **Parked ideas saved**: Good-but-not-now ideas documented
- [ ] **Session summary exported**: Captured for future reference
