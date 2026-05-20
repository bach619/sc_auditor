# Protocols: Agent Behavioral Rules

## 1. Non-Interference Protocol

### 1.1 Status Check (MANDATORY before any action)

Every agent MUST execute this check before touching any file or task:

```
Step 1: Read shared_state.agents.<own_id> — confirm own status is "active"
Step 2: Read shared_state.files[target] — check quality_state and owner
Step 3: Read shared_state.agents.<owner> — check owner's status
Step 4: Decide action based on decision table below
```

### 1.2 Decision Table

| Self Status | File Quality | File Owner | Owner Status | Action |
|-------------|-------------|------------|--------------|--------|
| active | green | self | active | Proceed normally |
| active | green | other | performing_well | **HALT.** No action. |
| active | green | other | struggling | Offer via event queue. Wait. |
| active | yellow | other | performing_well | **HALT.** Trust owner. |
| active | yellow | other | stalled | Escalate to aw |
| active | red | any | any | Take action (critical only) |
| idle | any | any | any | Wait for assignment |

### 1.3 The Offer Pattern

When agent B wants to help agent A:

```yaml
event:
  type: "offer_assistance"
  from: "bc"
  to: "apw"
  payload:
    file: "src/hero.js"
    concern: "animation performance may degrade on mobile"
    suggestion: "reduce parallax layers from 5 to 3"
    severity: "medium"
  accept_deadline: "2min"
```

Agent A has 2 minutes to accept or decline. If no response, `aw` escalates.

## 2. Silent Mode Protocol

### 2.1 Speak Conditions (EXHAUSTIVE)

| Event | Speak? | Template |
|-------|--------|----------|
| Phase start | YES | `[Phase N] <name> starting.` |
| Phase complete | YES | `[Phase N] done. <duration>. Gate: <result>.` |
| Project start | YES | `Nexus online. N agents. Autopilot.` |
| Project complete | YES | `Done. <summary>. <files> files, <issues> issues resolved.` |
| Critical failure | YES | `Blocked at <task>: <reason>. Strategies exhausted.` |
| User asks status | YES | Dashboard (see below) |
| User asks question | YES | Concise answer |
| Everything else | NO | SILENCE |

### 2.2 Dashboard Format (on user request)

```
Nexus Status [autopilot]
Phase: 3/5 — Implementation
├── apw: src/sections/hero.js [79%] green
├── bc:  scanning... 2 yellow, 0 red
├── ud: idle
├── aw: watching 4 agents, 0 conflicts
└── ap: strategy A active, 0 adjustments
Files: 12 changed, 0 locked
```

### 2.3 Violation Examples

❌ "I'll now check the hero section for bugs..."  
❌ "Let me look at the CSS tokens..."  
❌ "The code looks good, moving on..."  
❌ "Running the bug checker now..."  

✅ *silence* (then: phase complete message)  
✅ `[Phase 2] Gate RED: 4 bugs in hero.css. Self-correcting...`  

## 3. File Lock Protocol

### 3.1 Lock Acquisition

```
Agent requests lock:
  1. Send event: {type: "lock_request", from: agent_id, to: "aw", payload: {file, reason, estimated_duration}}
  2. aw checks lock_map
  3. IF file unlocked → aw grants lock, sets owner, starts timeout
  4. IF file locked → aw adds to queue, returns position
  5. IF lock expired (10min) → aw force-releases, grants to requester
```

### 3.2 Lock Release

```
Agent releases lock:
  1. Send event: {type: "lock_release", from: agent_id, to: "aw", payload: {file}}
  2. aw removes lock
  3. aw checks queue → grants to next requester
  4. aw updates file quality_state based on bc scan
```

### 3.3 Conflict Resolution

When two agents request same file simultaneously:
1. `apw` (frontend implementation) > `bc` (quality check)
2. `bc` (fixing critical bug) > `apw` (new feature)
3. `ud` (architecture re-analysis) > `apw` (implementation)
4. `ap` (emergency correction) > all others

## 4. Adaptation Protocol

### 4.1 Strategy Selection

```
On failure detection:
  1. ap reads failure context (agent, task, error_type, attempt_count)
  2. ap selects strategy: current_attempt_index + 1
  3. ap dispatches strategy instructions to target agent
  4. ap records in strategy_history

Strategy order:
  A → B → C → D → (repeat C→D once) → E (human escalation)
```

### 4.2 Strategy Descriptions

| ID | Name | Instruction |
|----|------|-------------|
| A | Full Build | Build complete solution from scratch using apple-parallax-web patterns |
| B | Incremental | Start with minimal working version, enhance step by step |
| C | Simplify | Remove complex animations, use simpler patterns, reduce scope |
| D | Decompose | Split task into independent sub-tasks, process sequentially |
| E | Escalate | If all above fail, surface to user with diagnosis |

### 4.3 Pattern Learning

```
After each adaptation:
  ap records in strategy_history:
    - which strategy worked for which context
    - which strategies failed and why
    - time to resolution

On future similar context:
  ap checks history → prefers proven strategy → skips known failures
```

## 5. Bug Checker Protocol

### 5.1 Scan Categories

| Category | Checks | Tool/Method |
|----------|--------|-------------|
| Code Quality | Syntax, best practices, complexity | Internal linter |
| Performance | Render-blocking, bundle size, lazy loading | Lighthouse metrics |
| Accessibility | ARIA, contrast, keyboard nav, semantic HTML | axe-core rules |
| SEO | Meta tags, structured data, heading hierarchy | SEO best practices |
| Security | XSS, CSP, input sanitization | OWASP patterns |

### 5.2 Severity Classification

| Severity | Definition | Auto-Fix? |
|----------|-----------|-----------|
| critical | Blocks functionality, security vulnerability, 500 error | YES — immediate |
| high | Major UX break, accessibility barrier, 404 | YES — queued |
| medium | Minor UX issue, SEO gap, perf regression <20% | NO — flag only |
| low | Style inconsistency, minor improvement | NO — note only |

### 5.3 Auto-Fix Protocol

```
1. bc detects issue
2. IF severity == critical:
   a. Request immediate lock on file from aw
   b. Apply fix
   c. Release lock
   d. Re-scan
   e. Notify aw & ap
3. IF severity == high:
   a. Queue fix behind current agent work
   b. Request lock when file available
   c. Apply fix
   d. Re-scan
4. IF severity <= medium:
   a. Record in issues list
   b. Report to aw
   c. Do NOT fix (let owning agent handle)
```

## 6. Understanding Protocol

### 6.1 Context Map Structure

```yaml
context_map:
  project_type: "landing_page" | "web_app" | "dashboard" | "portfolio"
  
  tech_stack:
    frontend: [html5, css3, js_es6]
    frameworks: []
    animations: [gsap, lenis, splitting_js]
    cdn_deps: [{name, version, usage_file}]
  
  architecture:
    pages: [{name, route}]
    components: [{name, file, dependencies}]
    sections: [{name, file, type: hero|features|stats|pricing|footer}]
  
  requirements:
    functional: [{id, description, implemented: bool}]
    non_functional: [{id, description, metric}]
  
  risk_map:
    high: [{area, mitigation}]
    medium: [{area, mitigation}]
    low: [{area}]
  
  gap_analysis:
    missing_requirements: [string]
    missing_components: [string]
    technical_debt: [{file, issue}]
```

### 6.2 Context Refresh Triggers

```
ud refreshes context_map when:
  - New file created (any .html, .css, .js)
  - File renamed or moved
  - Dependency added/removed
  - aw detects project structure change
  - ap changes strategy
  - Phase transition
```

### 6.3 Gap Detection

```
ud compares: requirements_map vs implemented_map
IF requirement has no matching implementation → GAP
IF implementation has no matching requirement → ORPHAN CODE
IF component depends on non-existent component → BROKEN DEPENDENCY

Report gaps to aw. aw decides: escalate or auto-fill.
```

## 7. Awareness Protocol

### 7.1 Tracking Granularity (FILE LEVEL)

```
Per file, aw tracks:
  - path
  - owner_agent
  - status: "planned" | "in_progress" | "completed" | "locked"
  - last_modified_timestamp
  - modification_count
  - quality_state: "green" | "yellow" | "red"
  - bc_issues: [{id, severity, resolved}]
  - version_hash (sha256 of content)
  - agent_history: [{agent, action, timestamp}]
```

### 7.2 Conflict Detection

```
aw runs conflict scan every 30 seconds:
  FOR each agent in active_agents:
    FOR each file in agent.working_set:
      IF file.owner != agent AND file.status != "completed":
        → CONFLICT
        → aw resolves via lock protocol priority
```

### 7.3 Progress Tracking

```
aw computes progress per phase:
  total_files = count(files in phase scope)
  completed_files = count(files with status "completed" AND quality "green")
  progress_pct = (completed_files / total_files) * 100

Progress delta tracked per 30s. If delta = 0 for >5min → stall detected.
```

### 7.4 Agent Health Monitoring

```
aw checks each agent every 60 seconds:
  - Heartbeat: last file change within 5min? → "active"
  - Over 5min no change on in_progress → "stalling" → ping agent
  - Over 10min no change → "stalled" → notify ap
  - 3 consecutive stalls → "unhealthy" → ap reassigns
```

## 8. Integration with External Skills

### 8.1 Apple-Parallax-Web Integration

```
awp receives task from aw → executes SKILL.md workflow
aw monitors apw file by file
bc scans each apw output
ud validates apw output against requirements

Non-interference: bc and ud watch silently unless:
  - bc finds critical bug → immediate report
  - apw stalls → aw escalates
  - apw completes → aw runs gate check
```

### 8.2 Future Skill Onboarding

```
To add a new skill:
  1. Drop SKILL.md into .opencode/skills/<skill-name>/
  2. aw auto-detects on next scan
  3. ud reads skill metadata, maps capabilities
  4. ap integrates into strategy library
  5. aw registers in agent roster
```

## 9. Emergency Protocols

### 9.1 Catastrophic Recovery

```
IF 3 agents report "stalled" simultaneously:
  → aw declares emergency
  → ap selects Strategy D (decompose)
  → ud re-analyzes entire project
  → All agents pause
  → aw re-delegates from scratch
  → Report: "Recovery initiated. Rebuilding task graph..."
```

### 9.2 Data Integrity

```
IF shared_state corrupted:
  → aw restores from last checkpoint
  → ud rebuilds context_map from file system
  → bc full re-scan
  → Resume from last known green phase
```

## 10. Delivery Checklist

Before declaring project complete:

- [ ] All phases passed quality gates
- [ ] bc full audit: all scores ≥ 90
- [ ] aw: 0 unresolved events
- [ ] aw: 0 locked files
- [ ] ud: 0 gaps (or all gaps explicitly waived)
- [ ] ap: strategy history shows stable resolution
- [ ] All files green quality state
- [ ] No agent stalled or unhealthy
- [ ] CDN dependencies validated
- [ ] Mobile responsive verified (375px)
- [ ] prefers-reduced-motion respected

Output final milestone report. Then: **SILENCE.**
