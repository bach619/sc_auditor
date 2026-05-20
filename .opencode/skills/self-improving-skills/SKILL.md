---
name: self-improving-skills
description: Meta-skill for autonomous skill evolution: usage tracking, feedback collection, gap analysis, automated improvement cycles, version control, effectiveness scoring, pattern extraction from failures, and continuous knowledge integration
license: MIT
compatibility: opencode
metadata:
  audience: all-agents
  domain: meta-learning
  paradigm: self-improvement
  capabilities:
    - skill-usage-tracking
    - feedback-collection
    - gap-analysis
    - automated-improvement
    - version-control
    - effectiveness-scoring
    - failure-pattern-extraction
    - knowledge-integration
    - skill-evolution
    - cross-skill-synthesis
    - best-practice-discovery
    - anti-pattern-detection
    - skill-deprecation
    - skill-merging
    - skill-splitting
  prerequisites: none
  integrates_with:
    - all skills
    - understanding
    - workflow-general
    - prompt-engineering
---

## Self-Improving Skills — Meta-Learning System

### Core Philosophy

> **Skills are not static documents. They are living knowledge bases that evolve through usage, feedback, and deliberate improvement.**
> A skill that doesn't improve is a skill that decays. Technology moves fast — skills must move faster.

```
┌─────────────────────────────────────────────────────────────┐
│              SELF-IMPROVING SKILL LIFECYCLE                  │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │  CREATE  │──▶│  DEPLOY  │──▶│  TRACK   │──▶│ COLLECT  │  │
│  │  SKILL   │   │  & USE   │   │  USAGE   │   │ FEEDBACK │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│       ▲                                              │      │
│       │                                              ▼      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ DEPLOY   │◀──│  REVIEW  │◀──│ GENERATE │◀──│ ANALYZE  │  │
│  │  v2.0    │   │  & TEST  │   │ IMPROVE  │   │  & GAP   │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
│                                                              │
│  Continuous Loop: Every usage → feedback → analysis → improve│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Skill Metadata & Versioning

### 1.1 Skill Registry Format

Every skill maintains a `SKILL_META.md` file alongside `SKILL.md`:

```yaml
# SKILL_META.md
skill: frontend-react
version: 3.2.1
created: 2026-01-15
last_updated: 2026-05-17
author: lore-master

# Usage Metrics
usage_count: 147
success_rate: 0.94
avg_effectiveness: 8.7/10
last_used: 2026-05-17

# Feedback
positive_feedback: 23
negative_feedback: 3
suggestions: 7

# Evolution
changelog:
  - version: 3.2.1
    date: 2026-05-17
    changes:
      - "Added React 19 Server Actions patterns"
      - "Fixed outdated useEffect cleanup example"
    reason: "User feedback: missing React 19 patterns"
  - version: 3.2.0
    date: 2026-04-20
    changes:
      - "Added use() hook documentation"
      - "Updated Suspense patterns"
    reason: "React 19 release"

# Known Gaps
gaps:
  - "Missing React Compiler (React 19) optimization patterns"
  - "Need more examples for Server Components data fetching"
  - "Outdated testing section (still references React Testing Library)"

# Dependencies
depends_on:
  - typescript
  - frontend-tailwind
used_by:
  - mobile-tauri
  - apple-parallax-web

# Effectiveness by Category
effectiveness:
  code_generation: 9.2
  debugging: 8.5
  architecture: 8.8
  best_practices: 9.0
  troubleshooting: 7.8
```

### 1.2 Version Semantics

| Version Change | When | Example |
|---------------|------|---------|
| **MAJOR** (1.0.0 → 2.0.0) | Breaking changes, paradigm shift | React 18 → React 19 patterns |
| **MINOR** (1.2.0 → 1.3.0) | New patterns, sections, examples | Added use() hook documentation |
| **PATCH** (1.2.1 → 1.2.2) | Bug fixes, corrections, clarifications | Fixed incorrect useEffect example |

---

## 2. Usage Tracking

### 2.1 Usage Log Format

Every skill usage is logged in `.opencode/skills/<name>/USAGE_LOG.md`:

```markdown
# Usage Log: frontend-react

| Date | Agent | Task Type | Outcome | Effectiveness | Feedback |
|------|-------|-----------|---------|---------------|----------|
| 2026-05-17 | lore-master | Code Generation | Success | 9/10 | "Perfect, exactly what I needed" |
| 2026-05-16 | ui-god | Debugging | Success | 7/10 | "Worked but missing edge case" |
| 2026-05-15 | vibe-coder | Architecture | Partial | 6/10 | "Good start, needed more detail" |
| 2026-05-14 | lore-master | Code Generation | Failed | 3/10 | "Outdated patterns, React 19 not covered" |
```

### 2.2 Automatic Usage Detection

When a skill is loaded via `skill` tool, the system automatically:

1. **Increment usage count** in SKILL_META.md
2. **Record task type**: Code Generation, Debugging, Architecture, Review, etc.
3. **Track outcome**: Success, Partial, Failed
4. **Request effectiveness score**: 1-10 rating
5. **Collect feedback**: What worked, what didn't, what's missing

### 2.3 Usage Analytics

```
┌─────────────────────────────────────────────────────────┐
│              USAGE ANALYTICS DASHBOARD                   │
│                                                         │
│  Skill: frontend-react                                  │
│  Version: 3.2.1                                         │
│                                                         │
│  Usage Over Time:                                       │
│  Jan: ████ 12    Feb: ██████ 18    Mar: ████████ 24    │
│  Apr: ██████████ 30    May: ██████████████ 42          │
│                                                         │
│  Success Rate: 94% (138/147)                            │
│  Avg Effectiveness: 8.7/10                              │
│                                                         │
│  By Task Type:                                          │
│  Code Generation: 67 uses → 9.2/10                      │
│  Debugging: 34 uses → 8.5/10                            │
│  Architecture: 28 uses → 8.8/10                         │
│  Review: 18 uses → 7.9/10                               │
│                                                         │
│  Trend: ↗ Improving (last 30 days: +0.3 effectiveness) │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Feedback Collection

### 3.1 Feedback Types

| Type | Trigger | Action |
|------|---------|--------|
| **Explicit** | User rates output | Record score + comment |
| **Implicit** | Agent retries with different approach | Infer low effectiveness |
| **Error-Based** | Generated code fails | Log error pattern |
| **Gap-Based** | Agent says "skill doesn't cover X" | Add to gaps list |
| **Outdated** | Agent notes deprecated patterns | Flag for update |
| **Success** | Agent says "this worked perfectly" | Reinforce pattern |

### 3.2 Feedback Collection Protocol

```
┌─────────────────────────────────────────────────────────┐
│              FEEDBACK COLLECTION FLOW                    │
│                                                         │
│  After skill usage:                                     │
│                                                         │
│  1. Agent self-evaluates:                               │
│     "How effective was this skill for the task?"        │
│     Score: 1-10                                        │
│                                                         │
│  2. Agent identifies gaps:                              │
│     "What was missing from the skill?"                  │
│     → Add to gaps list                                 │
│                                                         │
│  3. Agent notes outdated content:                       │
│     "What patterns are deprecated?"                     │
│     → Flag for update                                  │
│                                                         │
│  4. Agent extracts successful patterns:                 │
│     "What worked exceptionally well?"                   │
│     → Reinforce in skill                               │
│                                                         │
│  5. If score < 7:                                       │
│     → Trigger immediate improvement cycle              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 3.3 Feedback Aggregation

```yaml
# Aggregated feedback for skill
feedback_summary:
  total_responses: 147
  avg_score: 8.7
  score_distribution:
    10: 23
    9: 45
    8: 38
    7: 22
    6: 12
    5: 5
    4: 2
    3: 0
    2: 0
    1: 0

  common_praise:
    - "Clear examples" (34 mentions)
    - "Comprehensive coverage" (28 mentions)
    - "Up-to-date patterns" (22 mentions)

  common_complaints:
    - "Missing React 19 patterns" (8 mentions)
    - "Testing section outdated" (5 mentions)
    - "Need more performance examples" (4 mentions)

  improvement_suggestions:
    - "Add React Compiler optimization section"
    - "Update testing to Vitest + React Testing Library v14"
    - "Add Server Components data fetching patterns"
```

---

## 4. Gap Analysis

### 4.1 Automatic Gap Detection

The system identifies gaps through:

```
┌─────────────────────────────────────────────────────────┐
│              GAP DETECTION METHODS                       │
│                                                         │
│  1. FREQUENCY ANALYSIS                                  │
│     If users repeatedly ask for X not in skill → GAP   │
│                                                         │
│  2. ERROR PATTERN MATCHING                              │
│     If generated code consistently fails → GAP          │
│                                                         │
│  3. VERSION DRIFT                                       │
│     If skill references old version → OUTDATED          │
│                                                         │
│  4. CROSS-SKILL COMPARISON                              │
│     If related skill has pattern this lacks → GAP       │
│                                                         │
│  5. TECHNOLOGY EVOLUTION                                │
│     If new major release → NEEDS UPDATE                 │
│                                                         │
│  6. USER FEEDBACK                                       │
│     Direct "missing X" comments → GAP                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Gap Priority Matrix

```
┌─────────────────────────────────────────────────────────┐
│              GAP PRIORITY MATRIX                         │
│                                                         │
│                  HIGH IMPACT     LOW IMPACT              │
│              ┌──────────────┬──────────────────┐        │
│   HIGH       │  FIX NOW     │  FIX SOON        │        │
│   FREQUENCY  │  Critical    │  Important       │        │
│              │  [gaps]      │  [gaps]          │        │
│              ├──────────────┼──────────────────┤        │
│   LOW        │  MONITOR     │  BACKLOG         │        │
│   FREQUENCY  │  Watch for   │  Low priority    │        │
│              │  increase    │  [gaps]          │        │
│              └──────────────┴──────────────────┘        │
│                                                         │
│  Priority Score = (Impact × Frequency) / Effort         │
│  Fix highest score first                                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.3 Gap Analysis Report

```markdown
# Gap Analysis: frontend-react
Date: 2026-05-17

## Critical Gaps (Fix Now)
1. **React 19 Server Actions** — 8 user requests, high impact
   - Missing: Server Actions patterns, form handling, mutations
   - Effort: Medium (2-3 hours)
   - Priority Score: 9.2

2. **React Compiler optimization** — 5 user requests, high impact
   - Missing: Automatic memoization, optimization patterns
   - Effort: Medium (2 hours)
   - Priority Score: 8.5

## Important Gaps (Fix Soon)
3. **Testing section outdated** — 5 complaints, medium impact
   - Current: Jest + React Testing Library v12
   - Needed: Vitest + RTL v14 + Testing Library best practices
   - Effort: Low (1 hour)
   - Priority Score: 7.8

## Backlog
4. **Animation patterns** — 2 requests, low impact
   - Missing: Framer Motion integration patterns
   - Effort: High (4 hours)
   - Priority Score: 4.2
```

---

## 5. Automated Improvement Cycle

### 5.1 Improvement Trigger Conditions

| Trigger | Threshold | Action |
|---------|-----------|--------|
| **Low effectiveness** | Avg score < 7.0 | Immediate review |
| **High failure rate** | > 20% failed usages | Immediate review |
| **Critical gap** | 3+ requests for same gap | Schedule improvement |
| **Version drift** | Major version released | Schedule update |
| **Regular cycle** | Every 30 days | Routine review |
| **Cross-skill sync** | Related skill updated | Check for sync needed |

### 5.2 Improvement Process

```
┌─────────────────────────────────────────────────────────┐
│              IMPROVEMENT PROCESS                         │
│                                                         │
│  Step 1: IDENTIFY                                       │
│  - What needs improvement?                              │
│  - Why? (feedback, errors, gaps, outdated)              │
│  - Priority? (impact × frequency / effort)              │
│                                                         │
│  Step 2: RESEARCH                                       │
│  - Latest documentation                                 │
│  - Best practices from community                        │
│  - Real-world examples                                  │
│  - Common pitfalls                                      │
│                                                         │
│  Step 3: DRAFT                                          │
│  - Write new content                                    │
│  - Add code examples                                    │
│  - Update diagrams                                      │
│  - Add to changelog                                     │
│                                                         │
│  Step 4: VALIDATE                                       │
│  - Test examples                                        │
│  - Check accuracy                                       │
│  - Review completeness                                  │
│  - Cross-reference with related skills                  │
│                                                         │
│  Step 5: DEPLOY                                         │
│  - Update SKILL.md                                      │
│  - Update SKILL_META.md (version, changelog)            │
│  - Log improvement in USAGE_LOG.md                      │
│  - Notify dependent skills                              │
│                                                         │
│  Step 6: MONITOR                                        │
│  - Track effectiveness after update                     │
│  - Collect feedback on new content                      │
│  - Verify gap is closed                                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 5.3 Improvement Template

```markdown
# Improvement: [Skill Name] — [What]
Date: YYYY-MM-DD
Trigger: [Low effectiveness / Gap / Version drift / Regular cycle]

## Current State
- Version: X.Y.Z
- Avg effectiveness: N/10
- Known gaps: [list]
- User complaints: [list]

## Proposed Changes
1. [Change 1] — Impact: [High/Med/Low] — Effort: [H/M/L]
2. [Change 2] — Impact: [High/Med/Low] — Effort: [H/M/L]
3. [Change 3] — Impact: [High/Med/Low] — Effort: [H/M/L]

## Implementation
[Detailed changes with code examples]

## Validation
- [ ] Examples tested
- [ ] Accuracy verified
- [ ] Completeness checked
- [ ] Cross-references updated

## Expected Impact
- Effectiveness: X/10 → Y/10
- Gaps closed: N
- User complaints resolved: N

## Post-Deployment Monitoring
- Track effectiveness for 7 days
- Collect feedback on new content
- Verify gap closure
```

---

## 6. Effectiveness Scoring

### 6.1 Scoring Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| **Accuracy** | 0.25 | Is the information correct and up-to-date? |
| **Completeness** | 0.20 | Does it cover all common use cases? |
| **Clarity** | 0.15 | Is it easy to understand and apply? |
| **Relevance** | 0.15 | Is it applicable to the current task? |
| **Examples** | 0.15 | Are examples practical and working? |
| **Structure** | 0.10 | Is it well-organized and navigable? |

### 6.2 Effectiveness Calculation

```
Effectiveness = Σ(dimension_score × weight)

Example:
Accuracy: 9/10 × 0.25 = 2.25
Completeness: 8/10 × 0.20 = 1.60
Clarity: 9/10 × 0.15 = 1.35
Relevance: 10/10 × 0.15 = 1.50
Examples: 8/10 × 0.15 = 1.20
Structure: 9/10 × 0.10 = 0.90
─────────────────────────────────────
Total: 8.80/10
```

### 6.3 Effectiveness Thresholds

| Score | Status | Action |
|-------|--------|--------|
| 9.0-10.0 | Excellent | Maintain, share patterns |
| 8.0-8.9 | Good | Minor improvements |
| 7.0-7.9 | Adequate | Schedule improvements |
| 6.0-6.9 | Needs Work | Priority improvement |
| < 6.0 | Critical | Immediate overhaul |

---

## 7. Cross-Skill Synthesis

### 7.1 Pattern Extraction Across Skills

When multiple skills are used together, extract cross-skill patterns:

```
┌─────────────────────────────────────────────────────────┐
│              CROSS-SKILL PATTERN EXTRACTION              │
│                                                         │
│  Skills Used Together:                                  │
│  frontend-react + backend-nodejs + database-postgres    │
│                                                         │
│  Common Pattern Detected:                               │
│  "Full-stack form with validation"                      │
│                                                         │
│  Extracted Pattern:                                     │
│  1. Frontend: React Hook Form + Zod validation          │
│  2. Backend: Express + Zod validation (same schema)     │
│  3. Database: Prisma + Zod-generated types              │
│                                                         │
│  Action:                                                │
│  → Create cross-skill pattern doc                       │
│  → Reference in all three skills                        │
│  → Add to skill improvement queue                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Skill Dependency Graph

```
┌─────────────────────────────────────────────────────────┐
│              SKILL DEPENDENCY GRAPH                      │
│                                                         │
│  typescript ──▶ frontend-react ──▶ frontend-animation   │
│       │                │                                  │
│       ▼                ▼                                  │
│  backend-nodejs ──▶ database-postgres                    │
│       │                                                   │
│       ▼                                                   │
│  smartcontract-auditor                                   │
│                                                         │
│  If typescript updates:                                 │
│  → Check frontend-react for sync                        │
│  → Check backend-nodejs for sync                        │
│  → Check smartcontract-auditor for sync                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 8. Skill Evolution Strategies

### 8.1 Evolution Types

| Type | When | Example |
|------|------|---------|
| **Incremental** | Minor updates, patches | Add new example, fix typo |
| **Minor** | New patterns, sections | Add React 19 patterns |
| **Major** | Paradigm shift, rewrite | React class → hooks |
| **Merge** | Two skills overlap | frontend-css + frontend-tailwind → frontend-styling |
| **Split** | Skill too broad | backend → backend-go + backend-python |
| **Deprecate** | Technology obsolete | jQuery patterns → mark deprecated |

### 8.2 Evolution Decision Tree

```
┌─────────────────────────────────────────────────────────┐
│              SKILL EVOLUTION DECISION                    │
│                                                         │
│  Is the skill still relevant?                           │
│  ├─ NO → Deprecate                                     │
│  └─ YES                                                │
│       │                                                 │
│       Is it too broad? (> 5000 lines, 10+ topics)      │
│       ├─ YES → Split into focused skills                │
│       └─ NO                                             │
│            │                                            │
│            Does it overlap with another skill?          │
│            ├─ YES → Merge or clarify boundaries         │
│            └─ NO                                         │
│                 │                                       │
│                 Are there critical gaps?                │
│                 ├─ YES → Major update                   │
│                 └─ NO                                    │
│                      │                                  │
│                      Are there minor gaps?              │
│                      ├─ YES → Minor update              │
│                      └─ NO                              │
│                           │                             │
│                           Is it outdated?               │
│                           ├─ YES → Patch update         │
│                           └─ NO → Maintain              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 9. Knowledge Integration

### 9.1 External Knowledge Sources

| Source | Integration Method | Frequency |
|--------|-------------------|-----------|
| **Official Docs** | Manual review + update | On release |
| **GitHub Issues** | Scan for common problems | Weekly |
| **Stack Overflow** | Analyze top questions | Monthly |
| **Blog Posts** | Extract new patterns | Monthly |
| **Conference Talks** | Capture new techniques | Quarterly |
| **User Feedback** | Direct integration | Continuous |
| **Error Logs** | Pattern extraction | Continuous |

### 9.2 Knowledge Integration Process

```
┌─────────────────────────────────────────────────────────┐
│              KNOWLEDGE INTEGRATION                       │
│                                                         │
│  1. DISCOVER                                            │
│     New pattern/technique identified                     │
│                                                         │
│  2. VALIDATE                                            │
│     - Is it widely adopted?                             │
│     - Is it stable?                                     │
│     - Does it solve a real problem?                     │
│     - What are the trade-offs?                          │
│                                                         │
│  3. INTEGRATE                                           │
│     - Add to relevant skill                             │
│     - Add code examples                                 │
│     - Add to changelog                                  │
│     - Update version                                    │
│                                                         │
│  4. PROPAGATE                                           │
│     - Notify dependent skills                           │
│     - Update cross-references                           │
│     - Update skill dependency graph                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 10. Self-Improvement Commands

### 10.1 Skill Management Commands

| Command | Effect |
|---------|--------|
| `/skill-audit` | Run full audit on all skills |
| `/skill-audit [name]` | Audit specific skill |
| `/skill-score [name]` | Show effectiveness score |
| `/skill-gaps [name]` | Show known gaps |
| `/skill-improve [name]` | Trigger improvement cycle |
| `/skill-deprecate [name]` | Mark skill as deprecated |
| `/skill-merge [a] [b]` | Merge two skills |
| `/skill-split [name]` | Split skill into multiple |
| `/skill-sync [name]` | Sync with related skills |
| `/skill-report` | Generate improvement report |
| `/skill-evolve` | Run evolution decision tree |
| `/skill-history [name]` | Show version history |

### 10.2 Automated Improvement Schedule

```yaml
# Self-improvement schedule
daily:
  - Track usage metrics
  - Collect feedback
  - Log errors

weekly:
  - Analyze usage patterns
  - Identify new gaps
  - Check for version drift

monthly:
  - Run full skill audit
  - Generate improvement report
  - Update effectiveness scores
  - Cross-skill sync check

quarterly:
  - Run evolution decision tree
  - Review deprecation candidates
  - Merge/split evaluation
  - Major version planning
```

---

## 11. Implementation Checklist

For each skill, verify self-improving infrastructure:

- [ ] **SKILL_META.md created**: Version, metrics, gaps, changelog
- [ ] **USAGE_LOG.md created**: Usage tracking table
- [ ] **Feedback mechanism active**: Score collection after usage
- [ ] **Gap analysis running**: Automatic gap detection
- [ ] **Improvement queue maintained**: Prioritized list of improvements
- [ ] **Version control active**: Semantic versioning, changelog
- [ ] **Dependency graph updated**: Cross-skill dependencies tracked
- [ ] **Effectiveness scoring active**: 6-dimension scoring
- [ ] **External knowledge integration**: Sources monitored
- [ ] **Automated schedule configured**: Daily/weekly/monthly/quarterly tasks

---

## 12. Anti-Patterns

| Anti-Pattern | Symptom | Fix |
|--------------|---------|-----|
| **Stagnant skill** | No updates in 90+ days | Trigger improvement cycle |
| **Version drift** | References old technology | Schedule update |
| **Feedback ignored** | Low scores but no changes | Prioritize improvement |
| **Scope creep** | Skill covers too many topics | Split into focused skills |
| **Overlap** | Two skills cover same thing | Merge or clarify boundaries |
| **Orphaned skill** | No dependencies, no usage | Consider deprecation |
| **Broken examples** | Code examples don't work | Test and fix immediately |
| **Missing context** | Skill assumes prior knowledge | Add prerequisites section |

---

## 13. Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│              SELF-IMPROVING SKILLS CHEAT SHEET               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  EVERY SKILL NEEDS:                                         │
│  ✓ SKILL_META.md — Version, metrics, gaps, changelog       │
│  ✓ USAGE_LOG.md — Usage tracking table                     │
│  ✓ Feedback mechanism — Score collection after usage       │
│  ✓ Gap analysis — Automatic gap detection                  │
│  ✓ Improvement queue — Prioritized improvements            │
│                                                             │
│  IMPROVEMENT TRIGGERS:                                      │
│  • Avg score < 7.0 → Immediate review                      │
│  • Failure rate > 20% → Immediate review                   │
│  • 3+ requests for same gap → Schedule improvement         │
│  • Major version released → Schedule update                │
│  • Every 30 days → Routine review                          │
│                                                             │
│  EFFECTIVENSCORE:                                           │
│  Accuracy (25%) + Completeness (20%) + Clarity (15%)       │
│  + Relevance (15%) + Examples (15%) + Structure (10%)      │
│                                                             │
│  EVOLUTION TYPES:                                           │
│  Incremental → Minor → Major → Merge → Split → Deprecate   │
│                                                             │
│  COMMANDS:                                                  │
│  /skill-audit  /skill-score  /skill-gaps  /skill-improve   │
│  /skill-sync   /skill-report  /skill-evolve  /skill-history│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
