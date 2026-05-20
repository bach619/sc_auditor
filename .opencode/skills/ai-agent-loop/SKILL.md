---
name: ai-agent-loop
description: Agent loop architectures: ReAct (Reasoning+Acting), Plan-and-Execute, Self-Improving (Reflexion, Chain-of-Verification), Tree-of-Thought, Graph-of-Thought, LLM Compiler, CodeAct, sub-task decomposition, human-in-the-loop. Implementation patterns with LangGraph, CrewAI, AutoGen, and custom state machines.
license: MIT
compatibility: opencode
metadata:
  audience: ai-engineers
  domain: ai-agent
  paradigm: agentic
  capabilities:
    - react-loop
    - plan-execute-loop
    - self-improving-loop
    - tree-of-thought
    - graph-of-thought
    - llm-compiler
    - codeact
    - sub-task-decomposition
    - human-in-the-loop
    - langgraph-implementation
    - crewai-implementation
    - autogen-implementation
    - loop-safety
    - loop-evaluation
  integrates_with:
    - ai-memory
    - ai-rag
    - understanding
    - workflow-general
---

## AI Agent Loop Architectures Skill

### Philosophical Foundation

Agent loops are the cognitive architecture of autonomous AI systems. They determine how an agent
perceives, reasons, acts, and learns. The choice of loop architecture is the single most consequential
decision in agent design -- it governs the agent's capability ceiling, failure modes, cost profile,
and safety properties. No amount of prompt engineering or tool quality can compensate for a poorly
chosen loop.

Three axioms underpin loop design:

1. **The Loop Is the Mind** -- The loop IS the agent's cognitive architecture. Changing the loop
   changes what the agent can think, how it can fail, and what it can learn.

2. **Complexity Must Be Earned** -- Start with the simplest loop that could possibly work. ReAct
   solves 70% of problems. Only escalate to ToT/GoT when the problem structure demands it.

3. **Safety Is a Loop Property** -- Safety cannot be bolted on after loop design. Max iterations,
   cost tracking, human gates, and circuit breakers must be first-class loop constructs.

---

### 1. ReAct (Reasoning + Acting) Loop

The foundational agent loop. Interleaves reasoning traces with tool-use actions, allowing the agent
to think step-by-step while interacting with its environment.

#### Full Algorithm

```
Algorithm: ReAct(goal, tools, llm, max_steps=10, context=None)
  Input:  goal (string), tools (Tool[]), llm (LLM), max_steps (int)
  Output: result (any) or TIMEOUT / HALTED

  history = [(role: "system", content: build_system_prompt(tools, goal))]
  observation = None

  for step in 1..max_steps:
    // 1. REASONING: generate thought + action
    thought, action = llm.generate(
      history + [(role: "user", content: format_observation(observation, step))]
    )
    history.append(role: "assistant", content: f"Thought: {thought}\nAction: {action}")

    // 2. ACTING: execute action, get result
    if action.type == "Finish":
      return action.answer                   // terminal: agent declares done

    if action.type not in available_tools:
      history.append(role: "user", content: f"Error: unknown tool '{action.type}'")
      continue

    result = execute_tool(action, tools)     // timeout per tool execution

    // 3. OBSERVE: feed result back for next iteration
    observation = f"Observation: {result}"
    if is_final(result):
      return result

  return TIMEOUT                             // max_steps exhausted
```

#### Strengths and Weaknesses (Expanded)

| Aspect | Strength | Weakness |
|--------|----------|----------|
| **Flexibility** | Adapts to new information mid-trajectory; no rigid plan to follow | Can meander, switch goals, or lose thread across long trajectories |
| **Simplicity** | Easy to implement; ~50 lines of code for a basic loop | Simplicity means no built-in error recovery beyond retry |
| **Token efficiency** | Only generates one step at a time; context grows linearly with steps | Long trajectories balloon context window; thought compression required |
| **Error handling** | Can observe tool errors and self-correct in next thought | Repeated tool failures cause loops; no automatic escalation |
| **Multi-step tasks** | Chains tool calls naturally (search -> read -> summarize) | No global plan means suboptimal ordering for complex tasks |
| **Transparency** | Every thought + action is logged; fully auditable | Debugging requires reading the full trajectory |

#### Optimization Strategies

1. **Max Steps Limit** -- Always set a hard cap (default 10-15). After exhaustion, return the best
   partial answer with metadata: `{answer: partial, stopped_reason: "max_steps", step: N}`.

2. **Action Validation** -- Validate tool arguments BEFORE execution. Schema-validate against the
   tool's JSON Schema. Return validation errors immediately as observations so the agent can fix
   malformed calls without wasting an execution cycle.

3. **Thought Compression** -- When context exceeds a threshold (e.g., 4000 tokens), compress older
   thought-action-observation triples into summaries. Use a sliding window: keep the last N turns
   verbatim, summarize everything older. Preserve critical facts (numbers, identifiers, URLs).

4. **Action Parsing Robustness** -- LLMs produce inconsistent formats. Support multiple formats:
   `Action: tool_name[arg]`, `Action: {"tool": "...", "args": {...}}`, and markdown code blocks.
   Fall back to asking the LLM "Please reformat your action as valid JSON" on parse failure.

5. **Tool Result Truncation** -- Cap observation lengths (e.g., 4000 characters). Truncate with
   `"...[truncated, N chars omitted]"`. For structured data, show head + tail. Never silently
   drop information -- always signal truncation.

#### Implementation: LangChain AgentExecutor

```python
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain.tools import tool

@tool
def search(query: str) -> str:
    """Search the web for information. Input: search query string."""
    return web_search(query)

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression. Input: valid python expression."""
    return str(eval(expression))

tools = [search, calculator]

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Use tools when needed.\n\n"
     "You have access to: {tools}\n\n"
     "Use this format:\n"
     "Thought: your reasoning\n"
     "Action: tool_name\n"
     "Action Input: {{arg}}\n"
     "Observation: tool result\n"
     "... (repeat)\n"
     "Thought: I have the answer\n"
     "Final Answer: the answer"),
    ("placeholder", "{chat_history}"),
    ("user", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_react_agent(llm, tools, prompt)
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    max_iterations=10,
    handle_parsing_errors=True,       # auto-retry on malformed output
    return_intermediate_steps=True,   # for debugging
    max_execution_time=120,           # seconds
    early_stopping_method="generate", # generate best answer if max iterations hit
)
result = executor.invoke({"input": "What is the population of Tokyo?"})
```

#### Implementation: LangGraph StateGraph

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    iteration: int
    max_iterations: int

def should_continue(state: AgentState) -> str:
    """Decision edge: continue, finish, or halt."""
    if state["iteration"] >= state["max_iterations"]:
        return "halt"
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "act"
    return "finish"

def call_model(state: AgentState) -> AgentState:
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response], "iteration": state["iteration"] + 1}

def execute_tools(state: AgentState) -> AgentState:
    last_msg = state["messages"][-1]
    tool_results = []
    for tc in last_msg.tool_calls:
        result = tools_by_name[tc["name"]].invoke(tc["args"])
        tool_results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return {"messages": tool_results}

workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", execute_tools)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue, {
    "act": "tools", "finish": END, "halt": END
})
workflow.add_edge("tools", "agent")
app = workflow.compile()
```

#### Prompt Engineering for ReAct

The ReAct prompt is the single biggest lever for loop quality. Critical elements:

```
SYSTEM PROMPT STRUCTURE:
1. ROLE: "You are an AI assistant that solves problems step-by-step using tools."
2. TOOL DESCRIPTION: List each tool with name, arguments, and description.
3. FORMAT INSTRUCTION (explicit):
   Thought: <your reasoning about what to do next>
   Action: <tool_name>
   Action Input: <json or string argument>
4. TERMINATION RULE: "When you have the final answer, output: Final Answer: <answer>"
5. CONSTRAINTS: "Always reason before acting. If a tool fails, diagnose why."
6. EXAMPLES (few-shot): 2-3 complete trajectories showing reasoning + tool use + finish.

GOLDEN RULES:
- Never use ReAct without format instructions and at least one example.
- Match the format instruction to your parser (XML, JSON, or plaintext).
- Include error recovery examples: show a malformed action being corrected.
- For multi-step tasks, include an example with 3+ tool calls.
```

---

### 2. Plan-and-Execute Loop

Separates strategic planning from tactical execution. The agent first creates a complete plan,
then executes it step-by-step, revising when observations deviate from expectations.

#### Full Algorithm

```
Algorithm: PlanAndExecute(goal, tools, llm, max_steps=20)
  Input:  goal (string), tools (Tool[]), llm (LLM)
  Output: result (any)

  // PHASE 1: PLANNING
  context = gather_context(goal, tools)
  plan = llm.generate(
    prompt=PLAN_PROMPT,
    goal=goal,
    tools=tools,
    context=context
  )  // plan = [Step(description, tool, expected_outcome), ...]

  // PHASE 2: EXECUTION
  history = []
  for i, step in enumerate(plan):
    if i >= max_steps: return TIMEOUT

    // Execute current step
    observation = execute(step, tools)
    history.append((step, observation))

    // Check if step outcome matches expectation
    if not matches_expectation(observation, step.expected_outcome):
      // PHASE 3: REPLAN
      plan = replan(llm, goal, plan, i, observation, history)
      continue

    // Check if goal is achieved
    if is_goal_achieved(goal, observation, history):
      return synthesize_answer(llm, goal, history)

  return synthesize_answer(llm, goal, history)
```

#### Plan Creation Strategies

1. **Zero-shot planning**: Ask the LLM "Create a step-by-step plan to achieve X." Works well for
   well-defined problems. Prompt: "List the steps required, in order. For each step, specify the
   tool to use and the expected outcome."

2. **Structured decomposition**: Force the plan into a template:
   ```
   Step 1: [Gather] Search for information about X using tool Y
   Expected: List of relevant sources
   Step 2: [Analyze] Read top 3 sources and extract key facts
   Expected: Structured data with citations
   Step 3: [Synthesize] Combine findings into answer
   Expected: Complete answer with source references
   ```

3. **Hierarchical planning**: For complex tasks, create a high-level plan first, then expand
   each high-level step into sub-steps before execution. High-level: "Research X" -> Sub-steps:
   "Search X", "Read top results", "Cross-reference with Y".

4. **Plan-as-DAG**: When steps are independent, generate a DAG (Directed Acyclic Graph) instead
   of a linear list. Execute parallel-ready steps concurrently. Example: market research requires
   searching competitors + pricing + regulations -- these three searches are independent.

#### Plan Revision on Observation Mismatch

When a step's observation contradicts its expected outcome:

```python
def replan(llm, goal, original_plan, current_step_idx, observation, history):
    prompt = f"""
    Original goal: {goal}
    Original plan: {original_plan}
    Executed so far: {history}
    Current step {current_step_idx} failed. Expected: {original_plan[current_step_idx].expected}
    Actual: {observation}

    Revise the remaining plan (steps {current_step_idx+1} onward) to account for this.
    Keep completed steps unchanged. Output the revised plan in the same format.
    """
    revised_tail = llm.generate(prompt)
    return history_steps + revised_tail
```

#### Checkpoints and Incremental Replanning

- **Checkpoint**: After every N steps (default N=3), evaluate progress: "On a scale of 1-10, how
  close are we to the goal? If < 5, replan from scratch."
- **Incremental replanning**: Only revise future steps, never invalidate completed work. Completed
  steps are immutable facts.
- **Plan staleness detection**: If the same step is replanned > 3 times, escalate: ask the LLM
  to reconsider the overall approach or request human guidance.

#### When Plan-and-Execute Beats ReAct

| Scenario | ReAct | Plan-and-Execute |
|----------|-------|-------------------|
| Simple Q&A (1-3 tool calls) | Better -- lower overhead | Overkill |
| Multi-step research (5+ tool calls) | Can meander, lose thread | Better -- structured, trackable |
| Steps have dependencies | Works but may backtrack | Better -- plan captures dependencies |
| Steps are independent | Sequential by default | Better -- can parallelize |
| Environment is unpredictable | Better -- adapts per-step | Plan may be invalidated frequently |
| Need user visibility | User sees individual tool calls | User sees the plan upfront (trust) |
| Cost-sensitive | Pay-as-you-go per thought | Upfront planning cost + execution cost |

---

### 3. Self-Improving Loop (Reflexion Pattern)

The agent generates an initial result, critiques it against quality criteria, then iteratively
improves. Based on the Reflexion framework (Shinn et al., 2023).

#### Full Algorithm

```
Algorithm: SelfImproving(goal, tools, llm, quality_criteria, budget=3)
  Input:  goal, tools, llm, quality_criteria (list of criteria), budget (int)
  Output: best_result, reflection_log

  // Initial attempt
  result = execute_base_loop(goal, tools, llm)
  reflection = critique(result, goal, quality_criteria)

  best_result = result
  best_score = score_reflection(reflection)
  iterations = 0

  while not satisfactory(reflection) and iterations < budget:
    // Generate improvement from reflection
    improvement = generate_improvement(reflection, result, goal)
    result = execute_improvement(improvement, tools, llm)
    reflection = critique(result, goal, quality_criteria)
    score = score_reflection(reflection)

    if score > best_score:
      best_result = result
      best_score = score

    iterations += 1

  return best_result
```

#### Reflection/Critique Generation

The critique prompt must be specific and actionable:

```
CRITIQUE PROMPT:
Review the following answer against these criteria:
1. Accuracy: Are all factual claims correct? Flag uncertain statements.
2. Completeness: Does it fully answer the question? What's missing?
3. Clarity: Is the reasoning clear and logical?
4. Source quality: Are sources cited and authoritative?
5. Format compliance: Does it follow the required output format?

Original question: {goal}
Generated answer: {result}

For each criterion, provide:
- PASS / FAIL
- Specific issues found (quote the problematic text)
- Concrete suggestion for improvement

Then provide: Overall assessment (PASS / NEEDS_IMPROVEMENT)
```

#### Improvement Generation

```
IMPROVEMENT PROMPT:
The following answer needs improvement based on this critique:

Original question: {goal}
Current answer: {result}
Critique: {reflection}

Generate a revised answer that addresses every FAIL in the critique.
For factual errors, correct them with verified information.
For missing information, add it with sources.
For clarity issues, restructure the explanation.

Output the complete revised answer.
```

#### Chain-of-Verification (CoVe) Pattern

A specialized self-improving loop where the agent generates verification questions, answers them
independently, and cross-checks:

```
1. Generate baseline response to the query
2. Generate verification questions from the baseline:
   "For each factual claim in the response, generate a yes/no verification question
    that would confirm or refute it."
3. Answer each verification question independently (without seeing the baseline)
4. Cross-check: compare verification answers with baseline claims
5. Revise: correct any claims that verification answers contradict
6. Output: corrected final response
```

#### Early Stopping Criteria

- **Score plateau**: If the last 2 iterations have scores within 5% of each other, stop.
- **Perfection achieved**: If all criteria pass with no FAILs, stop immediately.
- **Divergence detection**: If the score DECREASES, the reflection system may be broken -- stop.
- **Budget exhausted**: Always stop after `budget` iterations, return best result seen so far.

#### When Self-Improving Is Worth the Cost

- High-stakes outputs (legal, medical, financial) where errors are costly
- Quality-critical tasks (exam answers, report generation)
- When the base model is known to hallucinate on the domain
- NOT worth it for: real-time responses, simple lookups, deterministic tasks

---

### 4. Tree-of-Thought (ToT)

Explores multiple reasoning paths simultaneously, evaluating and pruning to focus on promising
branches. Inspired by Yao et al. (2023).

#### Full Algorithm

```
Algorithm: TreeOfThought(problem, llm, k=3, beam_width=5, max_depth=4)
  Input:  problem, llm, k (branches per node), beam_width, max_depth
  Output: best_solution

  root = ThoughtNode(state=problem, depth=0)
  frontier = PriorityQueue([(score=0, root)])
  best_solution = None
  best_score = -inf

  while frontier is not empty:
    score, node = frontier.pop()       // highest-score first (best-first)

    if node.depth >= max_depth:
      if is_solution(node) and score > best_score:
        best_solution = node
        best_score = score
      continue

    // Generate k candidate next thoughts
    branches = generate_branches(node, k=k, llm=llm)

    // Evaluate each branch
    for branch in branches:
      branch_score = evaluate(branch, problem, llm)
      frontier.push((branch_score, branch))

    // Prune: keep only beam_width best nodes
    frontier = frontier[:beam_width]

  return extract_answer(best_solution)
```

#### Exploration Strategies

| Strategy | Algorithm | Best For |
|----------|-----------|----------|
| **BFS** | Explore level-by-level (all depth=1, then all depth=2, ...) | Shallow solutions, guaranteed shortest path |
| **DFS** | Go deep on one path first, backtrack if dead-end | Deep solutions, memory-constrained |
| **Best-First** | Always expand the highest-scored node (like A*) | When evaluation function is reliable |
| **Beam Search** | Keep only top-N nodes at each depth; prune rest | Large branching factors, cost-sensitive |

#### Beam Search Variant (Recommended Default)

Beam search balances exploration breadth with computational cost. At each depth level:

1. Generate k branches for EACH node in the current beam
2. This produces (beam_size * k) candidate nodes
3. Score all candidates
4. Keep the top `beam_size` candidates for the next depth
5. Discard the rest (pruning)

Parameters: `k=3` (branches per node), `beam_width=5` (nodes per level). Total nodes evaluated:
`1 + beam_width * k * max_depth` = 1 + 5*3*4 = 61 LLM calls for a depth-4 tree.

#### Pruning Strategies

1. **Score threshold**: Prune nodes with score < threshold. Threshold can be absolute (e.g., < 0.3)
   or relative (e.g., bottom 50% at each level).

2. **Redundancy pruning**: If two nodes represent the same state (high cosine similarity between
   their text representations), keep only the higher-scored one.

3. **Infeasibility pruning**: If a node's state is clearly impossible (contradiction, dead end),
   prune immediately regardless of score. Use heuristics: "Does this state contain contradictory
   statements?" or "Is there still a plausible path to the goal?"

4. **Lookahead pruning**: Generate a quick 1-step lookahead for each candidate. If the best
   possible next step still scores poorly, prune the candidate.

#### Evaluation Functions

Good evaluation functions are the difference between ToT working and ToT failing:

```
EVALUATION PROMPT:
Evaluate this partial solution to the problem on a scale of 1-10.

Problem: {problem}
Partial solution: {node_state}

Criteria:
- Progress: How far along is this toward solving the problem? (1-10)
- Plausibility: How likely is it that this path leads to a correct solution? (1-10)
- Coherence: Is the reasoning internally consistent? (1-10)
- Efficiency: Is this path elegantly solving the problem, or overcomplicating? (1-10)

For each criterion, give a score and a one-sentence justification.
Then give a weighted average: (0.4 * Progress + 0.3 * Plausibility + 0.2 * Coherence + 0.1 * Efficiency)
Output: {{"progress": N, "plausibility": N, "coherence": N, "efficiency": N, "total": N.N}}
```

#### When ToT Is Justified

- Creative tasks with many possible approaches (writing, design, strategy)
- Mathematical/algorithmic problems with branching solution paths
- Tasks where the FIRST idea is rarely the best (brainstorming-driven)
- When ReAct consistently fails -- ToT explores alternatives ReAct never considers

---

### 5. Graph-of-Thought (GoT)

Extends Tree-of-Thought by allowing nodes to merge, not just branch. Information from separate
reasoning paths can be combined into more powerful composite insights.

#### Full Algorithm

```
Algorithm: GraphOfThought(problem, llm, max_operations=20)
  Input:  problem, llm, max_operations (int)
  Output: best answer

  graph = initialize([ThoughtNode(state=problem)])
  converged = False
  ops = 0

  while not converged and ops < max_operations:
    // 1. THINK: generate new thoughts from frontier nodes
    frontier = graph.get_leaves()            // nodes with no outgoing edges
    new_nodes = []
    for node in frontier:
      branches = generate_branches(node, k=2, llm=llm)
      for branch in branches:
        branch_score = evaluate(branch, problem, llm)
        graph.add_node(branch, score=branch_score)
        graph.add_edge(node, branch, type="expansion")
        new_nodes.append(branch)

    // 2. AGGREGATE: combine related nodes into synthesized nodes
    clusters = cluster_by_similarity(new_nodes, threshold=0.8)
    for cluster in clusters:
      if len(cluster) >= 2:
        aggregated = aggregate_nodes(cluster, problem, llm)
        graph.add_node(aggregated, score=evaluate(aggregated, problem, llm))
        for node in cluster:
          graph.add_edge(node, aggregated, type="aggregation")

    // 3. REFINE: improve low-scored nodes using high-scored context
    low_nodes = [n for n in graph.nodes if graph.scores[n] < 0.5]
    high_nodes = [n for n in graph.nodes if graph.scores[n] > 0.8]
    for low in low_nodes[:3]:               // refine at most 3 per cycle
      context = select_best_context(low, high_nodes)
      refined = refine_node(low, context, problem, llm)
      graph.add_node(refined, score=evaluate(refined, problem, llm))
      graph.add_edge(low, refined, type="refinement")

    // 4. PRUNE: remove low-score leaves
    prune_threshold = percentile(graph.scores, 30)
    graph.prune(lambda n: graph.scores[n] < prune_threshold and n.is_leaf())

    // 5. CONVERGENCE CHECK
    if graph.best_score() > 0.95 or ops_since_improvement > 5:
      converged = True

    ops += 1

  return extract_best_answer(graph)
```

#### Graph Operations

| Operation | Input | Output | Description |
|-----------|-------|--------|-------------|
| **Think** | Node | N child nodes | Generate alternative next thoughts from a node |
| **Aggregate** | M nodes | 1 synthesized node | Merge overlapping or complementary thoughts into a richer one |
| **Refine** | 1 node + context | 1 improved node | Improve a thought using insights from better-scored nodes |
| **Prune** | Graph | Reduced graph | Remove nodes unlikely to lead to a solution |

#### Information Merging

The aggregate operation is GoT's key differentiator. It combines insights from separate reasoning
paths that explored different aspects of the problem:

```
AGGREGATE PROMPT:
You have two (or more) partial solutions to the same problem.
Synthesize them into a single, better solution that incorporates
the strongest insights from each.

Problem: {problem}

Solution A: {node_a.state}
Score: {score_a}
Key insight: {key_insight_a}

Solution B: {node_b.state}
Score: {score_b}
Key insight: {key_insight_b}

Instructions:
1. Identify overlapping ideas (merge into one)
2. Identify complementary ideas (combine both)
3. Identify contradictions (resolve by choosing the better-supported one)
4. Output the synthesized solution (do NOT just concatenate)
```

#### Convergence Criteria

- **Score convergence**: Best node score hasn't improved in 5+ operation cycles
- **Score ceiling**: Best node score exceeds 0.95 (near-certain solution)
- **Operation budget**: `max_operations` exhausted
- **Structural convergence**: No new nodes were added in the last cycle (graph is stable)
- **Combined**: (score_converged OR score_ceiling) AND NOT operation_budget

---

### 6. Advanced Loop Patterns

#### LLM Compiler (Parallel Function Calling)

Inspired by the LLM Compiler paper. Instead of sequential tool calls, the agent generates a DAG
of function calls with dependencies, then executes them in parallel where possible.

```
Algorithm: LLMCompiler(goal, tools, llm)
  1. PLAN: llm generates a DAG of function calls:
     - Each node: (function_name, arguments, dependencies)
     - Dependencies: node IDs that must complete before this node can run
  2. EXECUTE: Topological sort -> execute independent nodes in parallel
  3. JOIN: When all dependencies for a node are met, execute it
  4. REPLAN: If any function fails, replan from that node onward
  5. RETURN: Final result from the sink node
```

Benefits: Dramatically faster for tasks with independent sub-tasks. A research task that needs
5 independent searches runs in 1 round instead of 5 sequential rounds.

#### CodeAct (Generate + Execute)

The agent writes and executes code to solve problems, rather than using predefined tools.
The "action" is a code block; the "tool" is a Python interpreter.

```
Algorithm: CodeAct(goal, llm, sandbox, max_steps=10)
  for step in 1..max_steps:
    code, explanation = llm.generate(
      prompt=f"Write Python code to solve: {goal}\n"
             f"Previous results: {history}\n"
             f"Output code between ```python and ``` tags."
    )
    result = sandbox.execute(code)     // isolated execution environment
    history.append((code, result))
    if task_complete(result):
      return result
```

Best for: data analysis, mathematical computation, file manipulation, API interactions.

#### Sub-Task Decomposition Loops

For complex goals, decompose into sub-tasks and solve each independently:

```
Algorithm: SubTaskDecomposition(goal, llm, sub_agent_loop):
  1. DECOMPOSE: llm generates sub-tasks from goal:
     {sub_task_id: string, description: string, dependencies: [sub_task_id]}
  2. EXECUTE: For each sub-task with satisfied dependencies:
     result = sub_agent_loop.run(description)    // can be ReAct, Plan-Execute, etc.
     store result
  3. SYNTHESIZE: Combine sub-task results into final answer
  4. VERIFY: Check that synthesis fully addresses original goal
```

#### Human-in-the-Loop (HITL) Integration

Insert human judgment at critical decision points:

```
Algorithm: HITL_Loop(goal, tools, llm, approval_threshold=0.8):
  while not done:
    thought, action = llm.generate(...)

    risk_score = estimate_risk(action)
    if risk_score > THRESHOLD or action.type in ALWAYS_APPROVE:
      approved = request_human_approval(thought, action)
      if not approved:
        history.append("Human rejected action. Reason: ...")
        continue

    result = execute(action)
    ...
```

**Approval gate categories**:
- **Always approve**: Read-only operations (search, fetch, read)
- **Approve if high risk**: Write operations (create, update, delete)
- **Never execute without approval**: Destructive operations (delete all, deploy, send email)
- **Conditional**: Approve if cost > $X, if affecting > N users, if data volume > threshold

---

### 7. Implementation with Frameworks

#### LangGraph Deep Dive

LangGraph is the most flexible framework for building agent loops. Core concepts:

**StateGraph**: A directed graph where nodes modify shared state and edges define transitions.

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated, Literal
from operator import add

class State(TypedDict):
    messages: Annotated[list, add]       # reducer: append (not replace)
    iteration: int
    plan: list[str]
    final_answer: str | None

# Conditional edges: the function returns a string key
def router(state: State) -> Literal["tool_a", "tool_b", "reflect", "finish"]:
    last = state["messages"][-1]
    if "FINAL ANSWER" in last.content:
        return "finish"
    if "ToolA" in last.content:
        return "tool_a"
    if "need to reconsider" in last.content.lower():
        return "reflect"
    return "tool_b"

workflow = StateGraph(State)
workflow.add_node("agent", call_model)
workflow.add_node("tool_a", execute_tool_a)
workflow.add_node("tool_b", execute_tool_b)
workflow.add_node("reflect", reflect_on_progress)
workflow.add_conditional_edges("agent", router)
workflow.add_edge("tool_a", "agent")
workflow.add_edge("tool_b", "agent")
workflow.add_edge("reflect", "agent")
workflow.set_entry_point("agent")

# Checkpointing: persist state after each node
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

# Resume from checkpoint
config = {"configurable": {"thread_id": "conversation-1"}}
app.invoke({"messages": [HumanMessage(content="Research AI safety")]}, config)
```

**Streaming**: LangGraph supports multiple streaming modes:
```python
# Stream node-by-node updates
for event in app.stream(input, config, stream_mode="updates"):
    print(event)  # {node_name: state_update}

# Stream LLM tokens (when using chat models)
for token_chunk in app.stream(input, config, stream_mode="messages"):
    print(token_chunk.content)

# Custom streaming: yield from within nodes
def streaming_node(state):
    for chunk in llm.stream(state["messages"]):
        yield {"messages": [chunk]}
```

**Checkpointing**: Persist graph state after each node execution. Enables:
- Resuming interrupted runs
- Time-travel debugging (rewind to any checkpoint)
- Branching from any past state (explore alternatives)
- Human-in-the-loop: pause, review state, approve/revise, resume

#### CrewAI

Role-based multi-agent framework. Each agent has a role, goal, backstory, and tool set.

```python
from crewai import Agent, Task, Crew, Process

researcher = Agent(
    role="Senior Research Analyst",
    goal="Uncover cutting-edge developments in {topic}",
    backstory="You are a veteran analyst at a top think tank.",
    tools=[search_tool, scrape_tool],
    verbose=True,
)

writer = Agent(
    role="Technical Writer",
    goal="Craft compelling reports from research findings",
    backstory="You transform complex research into clear, actionable reports.",
    tools=[],
    verbose=True,
)

research_task = Task(
    description="Research the latest in {topic}. Identify 5 key trends.",
    agent=researcher,
    expected_output="A structured research brief with 5 trends, each with supporting evidence.",
)

write_task = Task(
    description="Write a executive summary based on the research brief.",
    agent=writer,
    expected_output="A 500-word executive summary in markdown format.",
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process=Process.sequential,    # or Process.hierarchical
    verbose=True,
)

result = crew.kickoff(inputs={"topic": "quantum computing"})
```

**CrewAI Process types**:
- `Process.sequential`: Tasks executed in order (output of task N -> input of task N+1)
- `Process.hierarchical`: A manager agent delegates tasks to worker agents dynamically

#### AutoGen (Microsoft)

Conversational agents that can write and execute code.

```python
import autogen

config_list = [{"model": "gpt-4", "api_key": os.environ["OPENAI_API_KEY"]}]

assistant = autogen.AssistantAgent(
    name="assistant",
    llm_config={"config_list": config_list},
    system_message="You are a helpful AI assistant. Write Python code to solve tasks.",
)

user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    human_input_mode="TERMINATE",     # ask human before terminating
    max_consecutive_auto_reply=10,
    code_execution_config={
        "work_dir": "coding",
        "use_docker": True,           # isolate code execution
    },
)

user_proxy.initiate_chat(
    assistant,
    message="Download stock data for AAPL and TSLA for 2023, plot their prices, and calculate correlation.",
)
```

#### Custom Loop Implementation Pattern

When frameworks are too heavy, implement a clean custom loop:

```python
from dataclasses import dataclass, field
from enum import Enum
import time, json

class LoopStatus(Enum):
    RUNNING = "running"
    FINISHED = "finished"
    HALTED = "halted"
    TIMEOUT = "timeout"
    ERROR = "error"

@dataclass
class LoopState:
    messages: list[dict] = field(default_factory=list)
    iteration: int = 0
    status: LoopStatus = LoopStatus.RUNNING
    result: any = None
    metadata: dict = field(default_factory=dict)

class AgentLoop:
    def __init__(self, llm, tools, max_iterations=10, timeout=120):
        self.llm = llm
        self.tools = tools
        self.max_iterations = max_iterations
        self.timeout = timeout

    def run(self, goal: str, context: dict | None = None) -> LoopState:
        state = LoopState(messages=[{"role": "system", "content": self._build_system_prompt(goal)}])
        if context:
            state.messages.append({"role": "user", "content": f"Context: {json.dumps(context)}"})

        start_time = time.monotonic()

        while state.iteration < self.max_iterations:
            if time.monotonic() - start_time > self.timeout:
                state.status = LoopStatus.TIMEOUT
                break

            response = self.llm.invoke(state.messages)
            state.messages.append({"role": "assistant", "content": response})
            state.iteration += 1

            # Parse action from response
            action = self._parse_action(response)
            if action["type"] == "finish":
                state.status = LoopStatus.FINISHED
                state.result = action["answer"]
                break

            # Execute tool
            try:
                result = self.tools[action["tool"]](**action["args"])
                state.messages.append({"role": "user", "content": f"Result: {result}"})
            except Exception as e:
                state.messages.append({"role": "user", "content": f"Error: {e}"})

        if state.status == LoopStatus.RUNNING:
            state.status = LoopStatus.HALTED

        state.metadata["iterations"] = state.iteration
        state.metadata["duration"] = time.monotonic() - start_time
        return state
```

---

### 8. Loop Safety and Governance

#### Max Iterations and Cost Tracking

```python
class BoundedLoop:
    def __init__(self, max_iterations=10, max_cost_usd=1.00, max_tokens=50000):
        self.max_iterations = max_iterations
        self.max_cost = max_cost_usd
        self.max_tokens = max_tokens
        self.tokens_used = 0
        self.cost_accumulated = 0.0

    def _check_budget(self, iteration: int, tokens_this_step: int):
        self.tokens_used += tokens_this_step
        self.cost_accumulated = self._estimate_cost(self.tokens_used)

        violations = []
        if iteration >= self.max_iterations:
            violations.append(f"max_iterations ({self.max_iterations})")
        if self.cost_accumulated > self.max_cost:
            violations.append(f"max_cost (${self.max_cost:.2f})")
        if self.tokens_used > self.max_tokens:
            violations.append(f"max_tokens ({self.max_tokens})")

        if violations:
            raise BudgetExceededError(f"Budget exceeded: {', '.join(violations)}")
```

#### Human Approval Gates

```python
class ApprovalGate:
    ALWAYS_APPROVE = {"search", "fetch", "read", "list", "get"}
    APPROVE_IF_HIGH_RISK = {"create", "update", "send", "post"}
    NEVER_WITHOUT_APPROVAL = {"delete", "drop", "deploy", "publish", "charge"}

    def requires_approval(self, action_type: str, action_args: dict) -> tuple[bool, str]:
        if action_type in self.NEVER_WITHOUT_APPROVAL:
            return True, "CRITICAL"
        if action_type in self.APPROVE_IF_HIGH_RISK:
            risk = self._assess_risk(action_args)
            if risk > 0.7:
                return True, f"HIGH_RISK ({risk:.0%})"
        if action_type in self.ALWAYS_APPROVE:
            return False, ""
        return True, "UNKNOWN_TOOL"  # unknown tools require approval

    def _assess_risk(self, args: dict) -> float:
        risk = 0.0
        if args.get("amount", 0) > 100:
            risk += 0.5
        if args.get("recipients", 1) > 10:
            risk += 0.3
        if args.get("force", False):
            risk += 0.8
        return min(risk, 1.0)
```

#### Timeout and Circuit Breaker

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, reset_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = 0
        self.state = "CLOSED"          # CLOSED, OPEN, HALF_OPEN

    def before_call(self):
        if self.state == "OPEN":
            if time.monotonic() - self.last_failure_time > self.reset_timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")

    def on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
```

**Circuit breaker integration**: Each tool call passes through the breaker. After N consecutive
failures (same tool, same error type), the breaker opens, preventing further calls to that tool
for a cooldown period. This prevents cascading failures and gives downstream services time to recover.

#### Observable Loops

Every loop must emit structured telemetry:

```python
@dataclass
class LoopEvent:
    timestamp: float
    event_type: str                      # "step_start", "step_end", "tool_call", "error", "finish"
    iteration: int
    data: dict

class ObservableLoop:
    def __init__(self, callback=None):
        self.events: list[LoopEvent] = []
        self.callback = callback         # external observer (e.g., for UI progress bar)

    def emit(self, event_type: str, iteration: int, data: dict):
        event = LoopEvent(
            timestamp=time.monotonic(),
            event_type=event_type,
            iteration=iteration,
            data=data,
        )
        self.events.append(event)
        if self.callback:
            self.callback(event)
```

**Key telemetry events**:
- `step_start` / `step_end`: iteration timing (detect slow steps)
- `tool_call` / `tool_result`: which tools used, latency, success/failure
- `budget_warning`: approaching limits (80%, 90%, 95% of max)
- `error`: what failed, error type, recovery action
- `finish` / `halt` / `timeout`: termination reason
- `human_approval`: what was approved/rejected, time waiting for human

---

### 9. Evaluation and Benchmarking

#### Loop Quality Metrics

| Metric | Definition | How to Measure |
|--------|------------|----------------|
| **Task Success Rate** | % of tasks where the agent achieved the goal | Binary pass/fail per task on a test suite |
| **Trajectory Efficiency** | Steps taken vs optimal steps | optimal_steps / actual_steps (1.0 = optimal) |
| **Token Efficiency** | Tokens consumed per task | Total tokens (input + output) across all LLM calls |
| **First-Attempt Success** | % of tasks solved on first try without self-improvement | Measure before reflexion loop activates |
| **Error Recovery Rate** | % of tool errors successfully recovered from | (successful_recoveries / total_errors) |
| **Hallucination Rate** | % of responses containing unsupported claims | Human or LLM-as-judge evaluation |
| **Latency** | End-to-end time from goal to result | Wall-clock time, P50/P95/P99 |
| **Cost per Task** | USD cost per completed task | Sum of all LLM API costs for a task |

#### Comparing Loop Strategies

When choosing between loop architectures, evaluate on YOUR specific task distribution:

1. **Create a benchmark**: 20-50 representative tasks spanning easy/medium/hard
2. **Ground truth**: For each task, define the correct answer AND the optimal tool-use trajectory
3. **Run each loop** on all tasks with identical LLM, tools, and budget constraints
4. **Compare across dimensions**:

```
| Loop Type      | Success | Steps/Task | Tokens/Task | Cost/Task | P95 Latency |
|----------------|---------|------------|-------------|-----------|-------------|
| ReAct          |   72%   |    6.2     |    4,200    |  $0.08    |    12.3s    |
| Plan-Execute   |   81%   |    5.1     |    5,800    |  $0.11    |    18.7s    |
| ReAct+Reflex   |   89%   |    8.4     |   12,400    |  $0.24    |    35.2s    |
| ToT (beam=5)   |   91%   |   14.2     |   38,000    |  $0.72    |    42.1s    |
```

5. **Decision**: Choose the loop that meets your success rate target at the lowest cost.

#### A/B Testing Agent Loops in Production

For production agents serving real users:

```
1. RANDOMIZE: Assign each user session to loop variant A or B
2. INSTRUMENT: Log success, latency, cost, user satisfaction (thumbs up/down)
3. MONITOR: Dashboard showing real-time metrics per variant
4. STATISTICAL SIGNIFICANCE: Use bootstrap or Bayesian analysis
   - Minimum sample: 100 sessions per variant
   - Run for at least 1 week to capture weekly patterns
5. PROMOTE: Switch all traffic to winning variant
6. ARCHIVE: Store A/B results as decision record for future reference
```

---

### 10. Common Pitfalls and Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| **No max iterations** | Loop runs until context window overflows or API rate limit hits | Always set max_iterations (default: 10-15); halt gracefully |
| **ReAct without format instructions** | LLM outputs freeform text that can't be parsed as tool calls | Provide explicit format with examples in the system prompt |
| **Silent tool errors** | Tool returns empty string or generic error; agent doesn't know it failed | Always return structured error: `{"error": true, "message": "...", "suggestion": "..."}` |
| **Over-engineering the loop** | ToT for a simple search task; costs 10x more for no gain | Match loop complexity to task difficulty; start with ReAct |
| **Unbounded context growth** | History grows linearly; eventually exceeds context window | Thought compression; summarize old turns; keep last N turns verbatim |
| **Single point of failure in plan** | Plan-and-Execute with one rigid plan; if early step fails, all later steps are invalid | Generate plan with fallback steps; replan on observation mismatch |
| **No termination condition** | Agent keeps going even when goal is achieved | Check after each step: "Is the goal accomplished?"; if yes, stop |
| **Ignoring tool documentation** | Agent invents tool arguments that don't exist | Include tool schemas in system prompt; validate arguments before execution |
| **ToT with poor evaluation** | Evaluation function is noisy or biased; best paths get pruned | Calibrate evaluation prompt; use majority voting across multiple LLM calls |
| **No observability** | Agent runs invisibly; can't debug failures or optimize | Log every step with structured events; build a trace viewer |
| **Human-in-the-loop as afterthought** | Human approval bolted on; approval requests lack context | Design approval gates into the loop from the start; show thought + action + risk |
| **Stale tools** | Tool API changed but agent still calls old signature | Version tools; validate tool signatures on agent startup |
| **Reflexion without stopping criteria** | Self-improvement runs until budget exhausted even when good enough | Set quality thresholds; stop when all criteria pass or score plateaus |
| **Mixing loop concerns** | Loop handles planning AND execution AND reflection in one monolithic function | Separate concerns: Planner, Executor, Critic as composable components |

---

### Decision Flowchart: Choosing the Right Loop

```
Problem type?
  │
  ├─ Single tool call, deterministic ──> Direct function call (no loop needed)
  │
  ├─ 1-3 tool calls, sequential ──> ReAct
  │
  ├─ 3-8 tool calls, structured plan possible ──> Plan-and-Execute
  │
  ├─ Quality-critical, errors costly ──> ReAct + Self-Improving (Reflexion)
  │
  ├─ Many possible approaches, creative ──> Tree-of-Thought
  │
  ├─ Multi-faceted, insights must combine ──> Graph-of-Thought
  │
  ├─ Independent sub-tasks, latency-sensitive ──> LLM Compiler (parallel)
  │
  ├─ Computationally intensive, code-driven ──> CodeAct
  │
  └─ Human decisions required ──> Any loop + HITL approval gates
```

### Quick Reference: Parameter Defaults

| Parameter | ReAct | Plan-Execute | Self-Improving | ToT | GoT |
|-----------|-------|--------------|----------------|-----|-----|
| max_iterations | 10 | 20 | 5 (improvement cycles) | - | 20 (operations) |
| max_depth | - | - | - | 4 | - |
| k (branches) | - | - | - | 3 | 2 |
| beam_width | - | - | - | 5 | - |
| timeout (seconds) | 120 | 300 | 180 | 600 | 900 |
| max_cost (USD) | $0.50 | $2.00 | $3.00 | $5.00 | $10.00 |
| early_stop | after max | on goal achieved | on score plateau | on solution found | on convergence |

---

### Cross-Skill Integration Patterns

The Agent Loop skill is the **orchestrator** of the AI skill ecosystem. It consumes memory, RAG, and evaluation from sibling skills and produces structured execution traces.

**With ai-memory** — Every loop execution should persist to memory:
- **Episodic Memory**: Each ReAct step (Thought → Action → Observation) is an event appended to the episodic log. Use the episodic event schema from ai-memory to capture agent trajectories
- **Procedural Memory**: Successful action sequences extracted via consolidation become procedural templates that ReAct loops can retrieve for similar tasks (see ai-memory Section 7)
- **Working Memory**: The ReAct loop's `history` array is the working memory buffer. Apply the budget management strategies from ai-memory Section 5 to prevent context overflow
- **Consolidation**: Schedule off-peak consolidation (ai-memory Section 6) to extract facts from agent trajectories into semantic memory

**With ai-rag** — Retrieval is the primary tool for knowledge-grounded agents:
- **Agentic RAG**: The ReAct loop with a `retrieve` tool is the Agentic RAG pattern from ai-rag. Each retrieval decision is a ReAct action step
- **Self-RAG Integration**: Self-RAG's `[Retrieve]` and `[NoRetrieve]` reflection tokens map directly to the ReAct `Thought` step — the agent decides whether to call the retrieval tool
- **Corrective RAG**: When tool calls return irrelevant results, the CRAG pattern (ai-rag) triggers rephrasing and re-retrieval as additional ReAct iterations
- **HyDE**: Use HyDE (ai-rag) when the agent needs to search for information where the query and documents are in different semantic spaces

**With workflow-general** — Agent development follows the quality-first lifecycle:
- **Requirements**: Define the agent's goal, success criteria, and constraints BEFORE choosing a loop architecture (see workflow-general Phase 1)
- **Testing**: Apply the Given/When/Then testing pattern from workflow-general: Given [initial state + tools], When [user input], Then [expected trajectory + answer]
- **Deployment**: Agent loops are long-running processes; apply the deployment patterns from workflow-general Phase 6 with appropriate health checks and graceful shutdown
- **6-Dimension Scoring**: Score agent loop implementations against Correctness (did it achieve the goal?), Performance (latency + token cost), Security (tool sandboxing), Maintainability (loop modularity), Completeness (error handling), and Alignment (appropriate loop choice)

**With infra-observability** — Every agent loop must be observable:
- Structured logging at each ReAct step with trace_id
- OpenTelemetry spans: one span per loop iteration, child spans for each tool call
- Prometheus metrics: `agent_loop_duration_seconds`, `agent_loop_tool_calls_total`, `agent_loop_success_rate`
- SLOs: Agent success rate > 80%, P95 end-to-end latency < 30s

**Skill loading order**: `understanding` → `workflow-general` → `ai-agent-loop` → `ai-memory` (if persistence needed) → `ai-rag` (if knowledge retrieval needed) → `infra-observability` (for production)

---

### Implementation Checklist

- [ ] Loop type selected based on task characteristics
- [ ] max_iterations set and halt behavior defined
- [ ] All tools have structured error responses
- [ ] System prompt includes format instructions + examples
- [ ] Action parser handles common LLM output variations
- [ ] Context window management (compression / sliding window)
- [ ] Circuit breaker on tool failures (threshold + cooldown)
- [ ] Budget tracking (tokens, cost, time) with thresholds
- [ ] Human approval gates for high-risk actions
- [ ] Structured telemetry emitted at every step
- [ ] Evaluation benchmark defined for the task domain
- [ ] A/B testing framework for comparing loop variants
- [ ] Rollback path: if new loop underperforms, revert to baseline
- [ ] Loop can be paused and resumed (checkpointing)
