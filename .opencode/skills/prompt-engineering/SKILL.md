---
name: prompt-engineering
description: High-quality prompt generation: frameworks (CREATE, TRACE, TAG), patterns (CoT, few-shot, role-play, ReAct), templates for all use cases, optimization, evaluation, and anti-patterns
license: MIT
compatibility: opencode
metadata:
  audience: all-developers
  domain: ai
  paradigm: declarative
  capabilities:
    - prompt-frameworks
    - prompt-patterns
    - prompt-templates
    - prompt-optimization
    - prompt-evaluation
    - multi-turn-conversation
    - system-prompt-design
    - few-shot-engineering
  integrates_with:
    - ai-agent-loop
    - ai-rag
    - ai-memory
    - understanding
---

## Prompt Engineering Skill

### Core Philosophy

> **A prompt is not a question — it is a program written in natural language.**
> Good prompts are deterministic, composable, and testable. Bad prompts are vague, ambiguous, and unpredictable.

```
┌─────────────────────────────────────────────────────────┐
│              PROMPT QUALITY HIERARCHY                     │
│                                                          │
│                    ▲                                     │
│                   /  \                                   │
│                  /    \    Self-Refining                  │
│                 / Meta \   (prompt improves itself)      │
│                /________\                                │
│               /          \                               │
│              /  Structured \  (format + constraints)     │
│             /______________\                             │
│            /                \                            │
│           /     Contextual   \  (role + background)      │
│          /____________________\                          │
│         /                      \                         │
│        /        Basic           \  (just a question)     │
│       /__________________________\                       │
│                                                          │
│  Most prompts fail at layer 2-3. Aim for layer 4+.       │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Prompt Frameworks

### 1.1 CREATE Framework (Universal)

The most comprehensive framework for any prompt:

| Component | Purpose | Example |
|-----------|---------|---------|
| **C** — Character | Define the AI's role/persona | "You are a senior Go engineer with 10 years experience in distributed systems" |
| **R** — Request | What you want done | "Design a rate limiter middleware for our API" |
| **E** — Examples | Few-shot examples | "Example input: 100 req/s → Output: token bucket with capacity 100, refill rate 100/s" |
| **A** — Adjustments | Constraints, style, format | "Use chi router. Include tests. Follow our project's error handling pattern" |
| **T** — Type of Output | Exact output format | "Return: (1) architecture diagram (ASCII), (2) code, (3) test cases, (4) trade-offs" |
| **E** — Extras | Edge cases, gotchas | "Handle burst traffic. Consider distributed scenario. Mention limitations" |

**Template:**
```
# Character
You are [role] with expertise in [domain]. Your approach is [style/methodology].

# Request
[What you want done — be specific and actionable]

# Examples
Input: [example input]
Output: [expected output]

Input: [another example]
Output: [another expected output]

# Adjustments
- Constraint 1: [e.g., "No external dependencies"]
- Constraint 2: [e.g., "Must handle 10k concurrent requests"]
- Style: [e.g., "Follow Clean Architecture"]
- Format: [e.g., "Return code + explanation + tests"]

# Type of Output
1. [First deliverable]
2. [Second deliverable]
3. [Third deliverable]

# Extras
- Edge cases to consider: [list]
- Common pitfalls to avoid: [list]
- If uncertain: [what should the AI do? ask? assume? state assumptions?]
```

### 1.2 TRACE Framework (For Complex Tasks)

For multi-step, complex problem-solving:

| Component | Purpose |
|-----------|---------|
| **T** — Task | Define the exact task |
| **R** — Reasoning | Specify the reasoning approach (CoT, tree-of-thought, etc.) |
| **A** — Action | What actions to take |
| **C** — Check | Self-validation criteria |
| **E** — Execute | Final output format |

**Template:**
```
Task: [specific task]

Reasoning Process:
1. First, analyze [what to analyze]
2. Then, consider [what to consider]
3. Evaluate [what to evaluate]
4. Finally, synthesize [what to synthesize]

Actions:
- [action 1]
- [action 2]

Validation Criteria:
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

Output Format:
[exact format expected]
```

### 1.3 TAG Framework (Quick Prompts)

For simple, everyday prompts:

| Component | Purpose |
|-----------|---------|
| **T** — Task | What to do |
| **A** — Action | How to do it |
| **G** — Goal | Why / success criteria |

**Template:**
```
Task: [what]
Action: [how — constraints, format, style]
Goal: [why — success looks like...]
```

---

## 2. Prompt Patterns

### 2.1 Chain-of-Thought (CoT)

Force the model to show its reasoning step-by-step.

**Basic CoT:**
```
Think step by step before answering.
Show your reasoning process.
```

**Advanced CoT (with structure):**
```
Before providing your answer, work through this reasoning process:

1. **Understand**: Restate the problem in your own words
2. **Decompose**: Break it into sub-problems
3. **Analyze**: Solve each sub-problem
4. **Synthesize**: Combine solutions
5. **Verify**: Check your answer against constraints

Then provide your final answer.
```

**Zero-Shot CoT (magic phrase):**
```
Let's think step by step.
```

### 2.2 Few-Shot Pattern

Provide examples to guide the output format and quality.

**Template:**
```
[Task description]

Example 1:
Input: "..."
Output: "..."

Example 2:
Input: "..."
Output: "..."

Example 3:
Input: "..."
Output: "..."

Now solve this:
Input: "[your actual input]"
Output:
```

**Key Rules:**
- Use 3-5 examples (more = better, but diminishing returns after 5)
- Examples should cover the range of expected inputs
- Include at least one edge case example
- Format examples exactly as you want the output

### 2.3 Role-Play Pattern

Assign a specific persona to the AI.

**Weak:**
```
You are a helpful assistant.
```

**Strong:**
```
You are a principal software engineer at a FAANG company with 15 years of experience.
You specialize in distributed systems, database design, and API architecture.
Your communication style is direct, technical, and pragmatic.
You always consider edge cases, failure modes, and scalability.
You cite specific technologies, patterns, and trade-offs — never vague advice.
```

**Role Library:**
```
# Code Reviewer
You are a senior code reviewer who focuses on: correctness first, then security,
then performance, then maintainability. You cite specific CWE/OWASP references
for security issues. You suggest exact code changes, not vague recommendations.

# Architect
You are a solutions architect who thinks in systems. You always consider:
data flow, failure modes, scalability limits, cost implications, and team velocity.
You produce ASCII diagrams for every architecture discussion.

# Security Auditor
You are a penetration tester and security researcher. You think like an attacker.
You always consider: OWASP Top 10, STRIDE threat model, supply chain risks,
and zero-trust principles. You provide CVSS scores for vulnerabilities.

# Performance Engineer
You are a performance optimization specialist. You think in metrics:
latency (p50, p95, p99), throughput, memory usage, CPU utilization.
You always suggest measurable optimizations with expected impact.
```

### 2.4 ReAct Pattern (Reason + Act)

For tasks that require external tool use or multi-step reasoning.

**Template:**
```
You can use the following tools: [list tools]

For each step, follow this format:
Thought: [what you're thinking]
Action: [which tool to use and why]
Observation: [result from tool]
... (repeat until done)
Final Answer: [your conclusion]

Begin.
```

### 2.5 Self-Consistency Pattern

Generate multiple answers and pick the best one.

**Template:**
```
Generate 3 different solutions to this problem.
For each solution, provide:
1. The approach
2. Pros and cons
3. Complexity analysis
4. When to use it

Then, compare all 3 and recommend the best one with justification.
```

### 2.6 Tree-of-Thought Pattern

Explore multiple reasoning paths simultaneously.

**Template:**
```
Imagine three different experts are discussing this problem.
Each expert has a different perspective:

Expert A (Optimist): Focuses on benefits and opportunities
Expert B (Pessimist): Focuses on risks and failure modes
Expert C (Pragmatist): Focuses on trade-offs and practical implementation

Have each expert present their analysis.
Then, synthesize a balanced recommendation.
```

### 2.7 Meta-Prompt Pattern

Ask the AI to improve your prompt.

**Template:**
```
I want to [describe goal]. Here's my current prompt:

"[your prompt]"

Analyze this prompt and identify:
1. Ambiguities that could lead to inconsistent outputs
2. Missing context the AI might need
3. Constraints that should be added
4. Format specifications that would improve output quality

Then, rewrite the prompt to be more effective.
```

### 2.8 Constraint-Based Pattern

Force specific behavior through explicit constraints.

**Template:**
```
[Task]

Constraints:
- MUST: [non-negotiable requirements]
- MUST NOT: [things to avoid]
- SHOULD: [preferred but not required]
- MAY: [optional enhancements]

If any constraint cannot be satisfied, explicitly state which one and why.
```

### 2.9 Output Schema Pattern

Force structured output.

**Template:**
```
[Task]

Respond in this exact format:

## Summary
[1-2 sentence overview]

## Analysis
[Detailed analysis]

## Recommendations
1. [Recommendation 1] — Priority: [HIGH/MED/LOW] — Effort: [XS/S/M/L/XL]
2. [Recommendation 2] — Priority: [HIGH/MED/LOW] — Effort: [XS/S/M/L/XL]

## Code
```[language]
[code here]
```

## Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ... | ... | ... | ... |
```

### 2.10 Iterative Refinement Pattern

Progressively improve output through feedback loops.

**Template:**
```
[Initial task]

After generating your response, apply these refinement passes:

Pass 1 — Correctness: Verify all facts, code, and logic
Pass 2 — Completeness: Check all edge cases and error handling
Pass 3 — Clarity: Simplify language, remove ambiguity
Pass 4 — Format: Ensure output matches the specified format

Show the final refined output only.
```

---

## 3. Prompt Templates by Use Case

### 3.1 Code Generation

```
# Role
You are a [language] expert specializing in [domain].

# Task
Generate [what] that [does what].

# Requirements
- Language: [language + version]
- Framework: [framework + version]
- Pattern: [design pattern]
- Error handling: [strategy]
- Testing: [include tests? which framework?]

# Constraints
- No external dependencies beyond [list]
- Follow [style guide/convention]
- Handle edge cases: [list]
- Performance target: [metrics]

# Context
[Relevant code, types, interfaces, or existing patterns]

# Output
1. Implementation code
2. Test cases
3. Usage example
4. Complexity analysis
```

### 3.2 Code Review

```
# Role
You are a senior code reviewer with expertise in [language/domain].

# Task
Review the following code for:

1. **Correctness**: Logic errors, edge cases, race conditions
2. **Security**: OWASP Top 10, injection, auth, data exposure
3. **Performance**: Time/space complexity, N+1, memory leaks
4. **Maintainability**: Readability, modularity, naming, DRY
5. **Best Practices**: Language-specific idioms and patterns

# Code
```[language]
[code here]
```

# Output Format
For each issue found:
- **Location**: [file:line]
- **Severity**: [CRITICAL/HIGH/MEDIUM/LOW]
- **Issue**: [description]
- **Fix**: [exact code change]

End with a summary score (0-100) for each dimension.
```

### 3.3 Architecture Design

```
# Role
You are a solutions architect with expertise in [domain].

# Task
Design an architecture for [system description].

# Requirements
- Scale: [expected load]
- Latency: [target p95/p99]
- Availability: [target SLA]
- Budget: [constraints]
- Team: [size, expertise]

# Constraints
- Must use: [required tech]
- Cannot use: [restricted tech]
- Must integrate with: [existing systems]

# Deliverables
1. ASCII architecture diagram
2. Component responsibility matrix
3. Data flow description
4. Technology selection with rationale
5. Failure mode analysis
6. Scalability plan
7. Cost estimation
```

### 3.4 Debugging

```
# Role
You are a debugging expert specializing in [language/domain].

# Problem
[Describe the bug]

# Context
- Error message: [exact error]
- Stack trace: [if available]
- Expected behavior: [what should happen]
- Actual behavior: [what actually happens]
- Steps to reproduce: [steps]

# Environment
- OS: [os]
- Language: [version]
- Framework: [version]
- Dependencies: [relevant packages]

# What I've Tried
1. [attempt 1] → [result]
2. [attempt 2] → [result]

# Output
1. Root cause analysis
2. Most likely cause (with confidence %)
3. Step-by-step fix
4. Prevention strategy
```

### 3.5 Documentation Generation

```
# Role
You are a technical writer specializing in [domain].

# Task
Generate documentation for [what].

# Audience
[Who will read this — developers, users, managers?]

# Content
[Code, API, or system to document]

# Requirements
- Include: [what must be covered]
- Format: [markdown, API spec, tutorial, etc.]
- Examples: [number and type of examples]
- Diagrams: [ASCII diagrams for architecture/flow]

# Style
- Tone: [technical, friendly, formal]
- Language: [language]
- Structure: [table of contents or sections]
```

### 3.6 Test Generation

```
# Role
You are a QA engineer specializing in [language/framework].

# Task
Generate comprehensive tests for [code/functionality].

# Code to Test
```[language]
[code here]
```

# Requirements
- Framework: [test framework]
- Coverage target: [percentage]
- Test types: [unit, integration, e2e, property-based]

# Must Cover
- Happy path
- Edge cases: [list]
- Error states: [list]
- Boundary conditions: [list]
- Race conditions (if applicable)

# Output
1. Test code
2. Coverage report (estimated)
3. Test execution instructions
4. Known gaps (what's not tested and why)
```

### 3.7 Refactoring

```
# Role
You are a refactoring expert specializing in [language/patterns].

# Task
Refactor the following code to improve [maintainability/performance/readability].

# Current Code
```[language]
[code here]
```

# Goals
- [ ] Improve [specific metric]
- [ ] Reduce [complexity/dependencies/lines]
- [ ] Apply [pattern/principle]
- [ ] Maintain backward compatibility

# Constraints
- Behavior must not change
- API must remain compatible
- [other constraints]

# Output
1. Refactored code
2. Diff summary (what changed and why)
3. Risk assessment
4. Migration steps (if breaking changes)
```

### 3.8 Learning / Explanation

```
# Role
You are a teacher who explains complex concepts clearly and accurately.

# Topic
[What to explain]

# Audience Level
[Beginner / Intermediate / Advanced]

# Requirements
- Start with intuition (analogy or real-world example)
- Then explain the technical details
- Include code examples
- Show common misconceptions
- Provide further reading resources

# Output Structure
1. Intuition (analogy)
2. Technical explanation
3. Code example
4. Common pitfalls
5. When to use / when not to use
6. Further reading
```

---

## 4. Prompt Optimization

### 4.1 Prompt Compression

Remove unnecessary words while preserving meaning.

**Before (bloated):**
```
I would like you to please help me write some code that can do the following thing,
which is to create a function that takes in a list of numbers and then returns the
sum of all the even numbers in that list. It would be great if you could also add
some comments to explain what the code is doing.
```

**After (compressed):**
```
Write a function that sums even numbers in a list. Include comments.
```

**Compression Rules:**
- Remove filler words: "please", "I would like", "it would be great if"
- Use imperative verbs: "Write", "Generate", "Analyze"
- Be specific, not verbose
- One sentence per requirement

### 4.2 Prompt Amplification

Add missing context and constraints to vague prompts.

**Before (vague):**
```
Make a login page.
```

**After (amplified):**
```
Create a login page component with:
- Email + password fields
- Form validation (email format, password min 8 chars)
- Error display for invalid credentials
- "Remember me" checkbox
- "Forgot password" link
- Loading state during submission
- Accessible (WCAG AA): labels, aria attributes, keyboard navigation
- Responsive: mobile-first, works on 320px+ screens
- Tech: React + TypeScript + Tailwind
```

### 4.3 Prompt Testing

Test prompts like you test code — with inputs and expected outputs.

**Template:**
```
Prompt: [your prompt]

Test Cases:
| Input | Expected Output | Actual Output | Pass/Fail |
|-------|-----------------|---------------|-----------|
| ... | ... | ... | ... |

If any test fails, revise the prompt and re-test.
```

---

## 5. Anti-Patterns

### ❌ Vague Requests
```
Bad:  "Make it better"
Good: "Reduce cyclomatic complexity from 12 to <5 by extracting helper functions"
```

### ❌ Missing Context
```
Bad:  "Fix this error"
Good: "Fix this TypeError: Cannot read property 'map' of undefined at line 42.
       The data comes from API endpoint /users. Sometimes the response is null."
```

### ❌ Contradictory Constraints
```
Bad:  "Make it fast but don't optimize"
Good: "Optimize for readability. Performance target: <100ms for 1000 items."
```

### ❌ Over-Specification
```
Bad:  "Write a function named calculateTotalAmountWithTaxAndDiscount
       that takes exactly 7 parameters in this specific order..."
Good:  "Calculate order total with tax and discount.
       Signature: (items, taxRate, discount?) => number"
```

### ❌ No Output Format
```
Bad:  "Review this code"
Good:  "Review this code. Output: table with columns [Line, Issue, Severity, Fix]"
```

### ❌ Assuming Knowledge
```
Bad:  "Do it like last time"
Good:  "Use the same pattern as the rate limiter in middleware/rate_limit.go:
       token bucket algorithm, Redis-backed, 100 req/s per IP"
```

---

## 6. Advanced Techniques

### 6.1 Prompt Chaining

Break complex tasks into sequential prompts.

```
Prompt 1: "Analyze this code and list all potential bugs"
    ↓ (output)
Prompt 2: "For each bug identified, write a test case that reproduces it"
    ↓ (output)
Prompt 3: "Fix each bug and verify the test passes"
```

**Why it works:** Each prompt has a focused scope. The model doesn't lose context trying to do everything at once.

### 6.2 Prompt Routing

Use a meta-prompt to route to specialized prompts.

```
Analyze this request and determine which specialist should handle it:
- If it's about UI/UX → use the Frontend Specialist prompt
- If it's about database → use the Database Specialist prompt
- If it's about security → use the Security Auditor prompt
- If it spans multiple domains → use the Architect prompt

Request: [user request]

Selected specialist: [which one]
Reason: [why]

Now, as the [selected specialist], handle the request:
[load the appropriate prompt template]
```

### 6.3 Prompt Caching

Reuse proven prompts. Store them in a library.

```
# Prompt Library Structure
prompts/
├── code/
│   ├── generate-function.md
│   ├── review-code.md
│   ├── refactor.md
│   └── generate-tests.md
├── architecture/
│   ├── design-system.md
│   ├── review-architecture.md
│   └── technology-selection.md
├── debugging/
│   ├── analyze-error.md
│   └── performance-profile.md
└── documentation/
    ├── generate-docs.md
    └── write-readme.md
```

### 6.4 Dynamic Prompt Generation

Generate prompts programmatically based on context.

```python
def generate_code_review_prompt(code, language, focus_areas):
    return f"""
# Role
You are a senior {language} code reviewer.

# Task
Review the following code focusing on: {', '.join(focus_areas)}

# Code
```{language}
{code}
```

# Output
For each issue: Location, Severity, Issue, Fix
"""
```

### 6.5 Self-Correction Prompt

Ask the model to check its own work.

```
[Generate output]

Now, review your own output:
1. Are there any factual errors?
2. Are there any logical inconsistencies?
3. Is the code correct and complete?
4. Did you follow all constraints?
5. Is the output format correct?

If you find any issues, correct them and provide the final version.
```

---

## 7. Evaluation Rubric

Score your prompts on these dimensions:

| Dimension | 1 (Poor) | 3 (Good) | 5 (Excellent) |
|-----------|----------|----------|---------------|
| **Clarity** | Vague, ambiguous | Clear intent | Crystal clear, no ambiguity |
| **Context** | No background | Some context | Complete context + examples |
| **Constraints** | None specified | Some constraints | All constraints explicit |
| **Format** | No format specified | Basic format | Detailed output schema |
| **Examples** | No examples | 1-2 examples | 3-5 diverse examples |
| **Edge Cases** | Not considered | Mentioned | Explicitly listed |
| **Validation** | No self-check | Basic check | Multi-pass refinement |

**Target: Average score ≥ 4.0**

---

## 8. Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    PROMPT CHEAT SHEET                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ALWAYS INCLUDE:                                            │
│  ✓ Role/Persona        → "You are a [expert in X]"          │
│  ✓ Task                → "Do [specific action]"             │
│  ✓ Context             → "Given [background info]"          │
│  ✓ Constraints         → "Must/Must not [requirements]"     │
│  ✓ Output Format       → "Return [exact format]"            │
│  ✓ Examples            → "Example: input → output"          │
│                                                             │
│  MAGIC PHRASES:                                             │
│  • "Think step by step"          → Chain-of-Thought         │
│  • "Let's work this out"         → Better reasoning         │
│  • "What are the edge cases?"    → Comprehensive coverage   │
│  • "Explain like I'm 5"          → Simplify                 │
│  • "Act as a [role]"             → Role-play                │
│  • "Show your work"              → Transparent reasoning    │
│                                                             │
│  AVOID:                                                     │
│  ✗ Vague requests ("make it better")                        │
│  ✗ Missing context ("fix this error")                       │
│  ✗ Contradictory constraints                                │
│  ✗ Over-specification (micromanaging)                       │
│  ✗ No output format                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Implementation Checklist

Before sending any prompt, verify:

- [ ] **Role defined**: Does the AI know who it should be?
- [ ] **Task clear**: Is the action specific and actionable?
- [ ] **Context provided**: Does the AI have enough background?
- [ ] **Constraints explicit**: Are MUST/MUST NOT stated?
- [ ] **Output format specified**: Does the AI know exactly how to respond?
- [ ] **Examples included**: Are there 1-5 examples of expected output?
- [ ] **Edge cases considered**: Are boundary conditions mentioned?
- [ ] **No contradictions**: Do all constraints work together?
- [ ] **Compressed**: Are unnecessary words removed?
- [ ] **Tested**: Has the prompt been tested with sample inputs?

---

## 10. Common Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Output too generic | No role/persona | Add specific expert role |
| Output wrong format | No format spec | Add exact output schema |
| Misses edge cases | No constraints | Add MUST/MUST NOT list |
| Inconsistent outputs | No examples | Add 3-5 few-shot examples |
| Too verbose | No compression | Remove filler words |
| Hallucinates facts | No grounding | Add "If uncertain, state assumptions" |
| Ignores constraints | Constraints buried | Put constraints at top, use bullet list |
| Wrong tone | No style guide | Add "Tone: technical/friendly/formal" |
