# Protocols: Context Router Behavioral Rules

## 1. Intent Detection Protocol

### 1.1 Prompt Ingestion

```
Every incoming user message triggers:
  1. Strip formatting → lowercase → tokenize
  2. Remove stop words (yang, dan, di, ke, dari, untuk, dengan, ini, itu, saya, tolong, bisa, bantu, help, please, can, you, the, a, an)
  3. Preserve named entities (GSAP, Lenis, SEO, JSON-LD, LCP, CLS, INP, H1, H2, React, Vue, CSS, HTML, JS)
  4. Pass tokens to keyword matcher
```

### 1.2 Keyword Weighting

```
Keyword weights (default: 10 per keyword, modified by specificity):

Generic keywords (weight: 5):
  - buat, tambah, ubah, ganti, hapus, perbaiki, cek, lihat, baca

Domain keywords (weight: 10):
  - design_ui: landing, hero, parallax, animasi, desain, UI, tampilan
  - seo: SEO, meta, schema, ranking, optimasi, keyword, structured data
  - bug_fix: bug, error, crash, fix, debug, broken
  - project_build: bangun, setup, dari awal, project baru, scaffold

Technology keywords (weight: 8, modify domain context):
  - GSAP, Lenis, ScrollTrigger, Splitting.js → boost design_ui by ×2
  - React, Vue, TypeScript, Tailwind → boost project_build by ×1.5
  - Google, Lighthouse, Core Web Vitals → boost seo by ×1.5

Named entity keywords (weight: 15):
  - Exact skill names: "apple-parallax-web", "seo-optimizer", "orchestrator"
  - Finding an exact skill name → immediate routing (100% confidence)
```

### 1.3 Pattern Matching (Regex)

```
Design/UI patterns:
  - /(buat|bangun|desain|redesign|bikin)\s+(landing|hero|halaman|page|section|component)/i
  - /(tambah|pasang|gunakan)\s+(animasi|parallax|scroll|GSAP|Lenis)/i
  - /(styling|CSS|tailwind|warna|font|tipografi)/i

SEO patterns:
  - /(optimasi|optimize|tingkatkan)\s+SEO/i
  - /(audit|cek|periksa)\s+SEO/i
  - /(meta\s*(tag|description)|schema|structured\s*data|JSON-LD)/i
  - /(title|heading|H1|alt\s*text|keyword|peringkat|ranking)/i

Bug patterns:
  - /(fix|perbaiki|debug|solve)\s+(bug|error|issue|problem|masalah)/i
  - /(tidak|nggak|gak)\s*(berfungsi|jalan|bisa|muncul|tampil)/i
  - /(error|crash|broken|glitch|bug)/i

Project build patterns:
  - /(buat|bangun|setup|inisialisasi|scaffold)\s+(website|project|aplikasi|app|site)/i
  - /(dari\s*awal|from\s*scratch|baru|new)/i

Audit patterns:
  - /(audit|review|periksa|evaluasi)\s+(kode|code|website|site|halaman)/i
  - /(lighthouse|quality|skor|score|performa|performance)/i
```

## 2. Routing Protocol

### 2.1 Pre-Route Checks

```
Before routing, Router MUST verify:
  1. Target skill directory exists: Test-Path ".opencode/skills/<skill-name>/SKILL.md"
  2. Target skill has valid YAML frontmatter with 'compatibility: opencode'
  3. Target skill is not the same as current (no self-routing)
  4. Target skill is not already active (check for active session)

If any check fails:
  → Use fallback skill from mapping table
  → If fallback also fails → skill("orchestrator") as ultimate fallback
```

### 2.2 Route Execution

```
Route command format:
  skill("<target-skill-name>")

With enriched prompt format:
  "[Router routed from context-router] <original user prompt>
  
  Context:
  - Project: <project-name> (<framework>, <css-framework>, <language>)
  - Relevant files: <file-list>
  - Detected intent: <domain> (<confidence>%)
  
  Instructions: <domain-specific routing instructions>"
```

### 2.3 Domain-Specific Routing Instructions

```
design_ui:
  "Follow the apple-parallax-web workflow. Analyze brief → design decisions → build → animate. Apply Apple design constitution rules."

seo:
  "Follow the seo-optimizer workflow. Audit all pages → output scorecard → prioritize fixes → apply optimizations → validate."

bug_fix:
  "Run orchestrator in BugChecker-focused mode. Scan project for issues matching: <extracted keywords>. Fix critical and high severity issues. Report medium/low for review."

audit:
  "Run orchestrator audit mode. Full quality scan: code quality, accessibility, performance, SEO. Output comprehensive audit report."

project_build:
  "Run orchestrator full lifecycle (Phase 0-5). Requirements mining → design → implementation → QA → delivery."

content:
  "Route to orchestrator. Focus on content analysis, text-to-HTML ratio, keyword placement, heading structure."

unknown:
  "No specific domain matched. Analyze the prompt as a general software engineering task. Use all available skills as needed."
```

## 3. Context Enrichment Protocol

### 3.1 Project Analysis (Always)

```
1. Read package.json → extract:
   - name, dependencies (React/Vue/etc.), devDependencies (Tailwind/Vite/etc.)
   - scripts (build, dev, test, lint)

2. Scan src/ → determine:
   - Framework presence: .tsx → React+TS, .vue → Vue, .jsx → React+JS
   - Component count and structure
   - Pages/routes count

3. Scan config files:
   - tailwind.config.js → Tailwind in use
   - vite.config.ts → Vite build tool
   - eslint.config.js → Linting rules

4. Output: context_package with all findings
```

### 3.2 Domain-Specific Enrichment

```
design_ui intent:
  → Read existing CSS files (src/index.css, styles/)
  → Read existing layout components
  → Extract color palette from tailwind.config.js
  → Identify existing sections/components to preserve

seo intent:
  → List all HTML/TSX files with <head> or meta tags
  → Read index.html for current SEO setup
  → Identify pages missing meta tags
  → Check for existing structured data

bug_fix intent:
  → Scan for error logs, console.error patterns
  → Read recently modified files (git diff)
  → Identify files mentioned in prompt
  → Check ESLint configuration

project_build intent:
  → Analyze current project structure
  → Identify existing components and pages
  → Map dependencies
```

### 3.3 Context Cache

```
Context is cached per session for efficiency:
  - First prompt: full analysis (3-5 seconds)
  - Subsequent prompts: cached context, only refresh if:
    - New files detected
    - User switches topic/domain
    - >5 minutes since last refresh
```

## 4. Fallback Protocol

### 4.1 Fallback Chain

```
Primary skill unavailable:
  1. Try fallback from mapping table
  2. If fallback also unavailable → orchestrator
  3. If orchestrator unavailable → report: "No skills available"

Domain unrecognized (no keywords):
  1. Route to orchestrator as general handler
  2. Pass: "Analyze this prompt and determine the best approach using available skills."
  3. Let orchestrator's Understanding (ud) agent handle classification

Empty prompt or greeting:
  1. Do NOT route
  2. Respond: list available skills
  3. Wait for task prompt
```

### 4.2 Degraded Mode

```
If .opencode/skills/ directory is missing or empty:
  → Report: "No skills found. Core tools only."
  → Continue as normal opencode session (no routing)

If SKILL.md can't be read for target skill:
  → Skip that skill in availability list
  → Use next available skill or orchestrator

If skill activation fails:
  → Log: [Router] Failed to activate <skill>: <reason>
  → Try fallback skill
  → If all fail: report to user and offer manual routing
```

## 5. Notification Protocol

### 5.1 Speak Conditions (EXHAUSTIVE)

| Event | Speak? | Template |
|-------|--------|----------|
| Routing occurs | YES | `[Router] Intent: <domain> (<conf>%) → <skill>` |
| Ambiguity detected | YES | Ask user to choose (2 options only) |
| Fallback used | YES | `[Router] <skill> unavailable. Falling back to <fallback>.` |
| Skill completes | YES | `[Router] Done. <skill> completed.` |
| Error routing | YES | `[Router] Failed to route: <reason>. Available skills: <list>.` |
| Greeting | YES | Available skills list |
| `/skills` command | YES | Full skill catalog |
| `/status` command | YES | Current routing state |
| All other cases | NO | SILENCE |

### 5.2 Silent Mode

NEVER output:
- "Let me analyze your prompt..."
- "I'm detecting the intent..."
- "Checking available skills..."
- "The context has been enriched..."
- "Routing to..."
- Any intermediate analysis chatter

## 6. Ambiguity Resolution Protocol

### 6.1 Detection

```
Ambiguity condition: Two or more domains with scores within 15% of each other AND all ≥ 40%.

Example:
  design_ui: 65%
  seo: 52%      ← within 15% of design_ui
  bug_fix: 10%
  → AMBIGUOUS between design_ui and seo
```

### 6.2 Resolution Flow

```
1. Present 2 options with brief descriptions
2. User answers with number (1/2) or "semua"/"all"
3. If "1" or "2" → route to that skill
4. If "semua"/"all" → route to first skill, after completion route to second
5. If timeout (30s no response) → route to highest scoring domain

Question format:
  "Saya deteksi 2 konteks:
   1. Design/UI → apple-parallax-web
   2. SEO → seo-optimizer
   Pilih 1 atau 2 (atau 'semua'):"
```

## 7. Multi-Skill Sequential Protocol

```
When user selects "semua" for ambiguous routing:

  1. Route to first skill → wait for completion
  2. After first skill completes → route to second skill
  3. Pass previous skill's output summary to next skill as context
  4. After both complete → [Router] All done. <skill1> + <skill2> completed.

Max sequential routing: 3 skills. If user wants more, ask for confirmation.
```

## 8. Special Command Protocol

### 8.1 Skills List (triggered by "/skills", "skill apa aja", "list skill", "available skills")

```
Output:
  ## Available Skills
  
  | Skill | Description | Activation |
  |-------|-------------|-------------|
  | apple-parallax-web | Apple-quality landing pages with GSAP, Lenis, Splitting.js | Prompt containing "landing", "hero", "animasi", "parallax" |
  | seo-optimizer | SEO audit, optimization, structured data, Core Web Vitals | Prompt containing "SEO", "meta", "schema", "optimasi" |
  | orchestrator | Multi-agent project lifecycle (design→build→QA→deliver) | General tasks, bug fixes, project builds |
  | context-router | (You are here) Intent detection and skill routing | Default entry point |
  
  Just describe what you want — I'll route to the right skill.
```

### 8.2 Status Command (triggered by "/status", "status")

```
Output:
  [Router] Status:
  ├── Active skill: <name or "none">
  ├── Last routed: <domain> → <skill> (<time ago>)
  ├── Session tasks: <count completed>
  └── Available skills: <count>
```

### 8.3 Reset Command (triggered by "/reset", "reset")

```
Action:
  1. Clear all cached context
  2. Clear routing history
  3. Reset to idle state
  4. Confirm: "[Router] Reset complete. Ready for new task."
```

## 9. Integration with Orchestrator Awareness Protocol

```
When routing to orchestrator, context-router temporarily joins the orchestrator's agent bus:

  1. aw (Awareness) detects context-router as external trigger
  2. router becomes passive observer — does not interfere
  3. When orchestrator completes → router receives milestone report
  4. Router outputs completion summary to user

Router does NOT participate in:
  - File locking
  - Quality gates
  - Strategy adjustments
  - Bug checking

Router is a pure delegator — never an executor.
```

## 10. Edge Cases

### 10.1 Very Long Prompts
```
If prompt > 500 words:
  - Extract first 100 words + keywords from full text
  - Treat as multi-domain task → route to orchestrator
  - Orchestrator's Understanding agent handles full analysis
```

### 10.2 Code Blocks in Prompt
```
If prompt contains ```code``` blocks:
  - Ignore code for intent detection (prevents false matches)
  - Only analyze natural language portions
  - If natural language < 5 words → route to orchestrator
```

### 10.3 Non-Task Messages
```
Messages that are NOT tasks:
  - "terima kasih", "thank you" → respond "Siap. Ada yang bisa dibantu?" + skills hint
  - "ok", "sip", "good" → acknowledge, wait for next task
  - Questions about opencode → answer directly (no routing)
  - Feedback → acknowledge, log for improvement
```

### 10.4 Indonesian ↔ English Bilingual Handling
```
Keywords are defined in BOTH languages.
Indonesian prompt → Indonesian keyword match
English prompt → English keyword match
Mixed prompt → match both, take highest scoring
```
