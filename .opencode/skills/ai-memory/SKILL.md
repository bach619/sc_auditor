---
name: ai-memory
description: >-
  AI memory systems: Vector Memory (embedding stores), Graph Memory (knowledge graphs),
  Episodic Memory (experience replay), Working Memory (attention mechanisms), Procedural Memory
  (skill acquisition), memory consolidation, forgetting mechanisms, implementation patterns,
  and evaluation methodology
license: MIT
compatibility: opencode
metadata:
  audience: ai-engineers
  domain: ai-agent
  paradigm: memory-systems
  capabilities:
    - vector-memory
    - graph-memory
    - episodic-memory
    - working-memory
    - procedural-memory
    - memory-consolidation
    - forgetting-mechanisms
    - memory-evaluation
    - privacy-preserving-memory
  integrates_with:
    - ai-agent-loop
    - ai-rag
    - database-postgres
    - database-event-sourcing
    - infra-observability
---

## AI Memory Systems Skill

---

### 1. Memory Architecture (Kahneman-Inspired)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MEMORY ARCHITECTURE                           │
│                                                                      │
│  ┌──────────────┐                      ┌──────────────────────┐     │
│  │  System 1    │◄──── fast path ─────►│     System 2          │     │
│  │  (Intuitive) │                      │     (Analytical)      │     │
│  │  < 100ms     │                      │     > 500ms           │     │
│  │  Pattern     │                      │     Deliberate        │     │
│  │  recognition │                      │     reasoning         │     │
│  └──────┬───────┘                      └──────────┬───────────┘     │
│         │                                         │                  │
│         │      ┌──────────────────────┐           │                  │
│         └─────►│   Working Memory     │◄──────────┘                  │
│                │   (active context)   │                               │
│                │   ~7±2 chunks        │                               │
│                │   ~4K-128K tokens    │                               │
│                └──────────┬───────────┘                               │
│                           │                                           │
│              ┌────────────┼────────────┐                              │
│              │            │            │                              │
│              ▼            ▼            ▼                              │
│  ┌───────────────┐ ┌──────────────┐ ┌──────────────────┐            │
│  │ Short-Term    │ │ Attention    │ │ Active Plan      │            │
│  │ Memory (STM)  │ │ Filter       │ │ & Goals          │            │
│  │ minutes-hours │ │ (salience)   │ │                  │            │
│  └───────┬───────┘ └──────┬───────┘ └──────────────────┘            │
│          │                │                                          │
│          ▼                ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              CONSOLIDATION ENGINE                              │   │
│  │  cluster → summarize → extract patterns → forget low-import.  │   │
│  └──────────────────────────┬───────────────────────────────────┘   │
│                             │                                        │
│                             ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              LONG-TERM MEMORY (LTM)                            │   │
│  │                                                                │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │   │
│  │  │  Semantic    │  │  Episodic    │  │  Procedural      │    │   │
│  │  │  (Vector)    │  │  (Timeline)  │  │  (Skills)        │    │   │
│  │  │              │  │              │  │                  │    │   │
│  │  │ Facts        │  │ Experiences  │  │ Action sequences │    │   │
│  │  │ Concepts     │  │ Interactions │  │ Learned patterns │    │   │
│  │  │ Knowledge    │  │ Outcomes     │  │ Task templates   │    │   │
│  │  │              │  │              │  │                  │    │   │
│  │  │ Store:       │  │ Store:       │  │ Store:           │    │   │
│  │  │ Vector DB    │  │ Append Log   │  │ Relational DB    │    │   │
│  │  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘    │   │
│  │         │                 │                    │              │   │
│  │         └─────────┬───────┴────────────────────┘              │   │
│  │                   │                                           │   │
│  │                   ▼                                           │   │
│  │  ┌──────────────────────────────────────────────────────┐     │   │
│  │  │              GRAPH MEMORY (Cross-Store Index)         │     │   │
│  │  │  Links entities across Semantic, Episodic, Procedural │     │   │
│  │  │  Store: Neo4j / ArangoDB / Kuzu                        │     │   │
│  │  └──────────────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**System 1 (Fast)**: Intuitive, pattern-matching retrieval. No deliberation. For routine queries,
reflexive actions, and well-rehearsed skills stored in procedural memory. Operates on
compressed representations in working memory.

**System 2 (Slow)**: Deliberate reasoning, planning, and novel problem-solving. Engages when
System 1 confidence is low or when a task requires multi-step reasoning. Draws from all LTM
stores and may trigger consolidation of new insights.

**Interaction flow**: System 1 proposes → Working Memory evaluates confidence → If low, System 2
intervenes → System 2 results may be consolidated back into System 1 patterns (learning).

**Key principle**: Memory is not a single store. It is a multi-component system where each
component has different capacity, latency, durability, and retrieval characteristics.
Design your memory architecture to match these biological principles.

---

### 2. Vector Memory (Semantic)

Vector memory stores knowledge as dense embeddings in high-dimensional space, enabling
semantic (not just keyword) retrieval.

#### Embedding Model Selection

| Model | Dims | Max Tokens | Strengths | Weaknesses |
|-------|------|------------|-----------|------------|
| `text-embedding-3-small` | 512/1536 | 8191 | Cheap, fast, good baseline | Not best for complex queries |
| `text-embedding-3-large` | 256/1024/3072 | 8191 | Best OpenAI quality | Costlier, slower |
| `voyage-3-large` | 1024 | 32000 | Code-optimized, long context | Vendor-specific |
| `bge-m3` | 1024 | 8192 | Multilingual, dense+sparse | Needs GPUs for self-host |
| `jina-embeddings-v3` | 1024 | 8192 | Task-specific LoRA adapters | Newer ecosystem |
| `nomic-embed-text-v2` | 768/1376 | 8192 | Open, Matryoshka (truncatable) | Less battle-tested |
| `gte-Qwen2-7B-instruct` | 3584 | 32768 | SOTA on MTEB leaderboard | Heavy, needs GPU |

**Selection heuristic**: For general use, `text-embedding-3-large` (managed) or `bge-m3` (self-hosted).
For long documents, `voyage-3-large` or `jina-embeddings-v3`. For multilingual, `bge-m3`.

**Matryoshka embeddings**: Models like `text-embedding-3-*` and `nomic-embed-text-v2` support
truncation. Store at full dimension, query at reduced dimension for speed/space tradeoffs
without re-embedding. `embedding[:256]` gives a 256-dim vector with ~98% quality.

#### Vector Stores

| Store | Architecture | Best For | Limitations |
|-------|-------------|----------|-------------|
| **Pinecone** | Serverless, managed | Production, scale-to-zero | Vendor lock-in, cost at scale |
| **Qdrant** | Self-hosted or cloud | Rich filtering, quantization | Operational burden if self-hosted |
| **Weaviate** | Self-hosted or cloud | Hybrid search (dense+sparse) | Complex configuration |
| **Chroma** | Embedded library | Local dev, prototyping | Not production-grade |
| **pgvector** | PostgreSQL extension | Simplicity, existing PG infra | Performance at >10M vectors |
| **Milvus** | Distributed, cloud-native | Billion-scale, GPU indexing | Heavy ops, complex deployment |
| **LanceDB** | Embedded, columnar | Local-first, multimodal | Newer, smaller ecosystem |

**Store selection matrix**:

```
< 100K vectors, existing PG     → pgvector (no new infra)
< 1M vectors, need filtering    → Qdrant (best filtering)
< 10M vectors, managed          → Pinecone (zero ops)
> 10M vectors, multimodal       → Milvus (scale)
Local dev / testing             → Chroma or LanceDB
Hybrid search required          → Weaviate
```

#### Similarity Metrics

| Metric | Formula | Range | Best For |
|--------|---------|-------|----------|
| **Cosine** | cos(θ) = A·B / (‖A‖‖B‖) | [-1, 1] | Normalized embeddings (default) |
| **L2 (Euclidean)** | ‖A - B‖₂ | [0, ∞) | When magnitude matters |
| **Dot Product** | A·B | (-∞, ∞) | When embeddings aren't normalized |
| **Inner Product** | Same as dot | (-∞, ∞) | Optimized for certain models |

**Rule**: Use cosine similarity unless your embedding model specifically recommends dot product
(e.g., `text-embedding-ada-002`). Always check model documentation for recommended metric.

#### Metadata Filtering Strategies

```
Query Flow:
  1. Pre-filter by metadata (date range, source, category) → narrows candidate set
  2. Vector similarity search on pre-filtered candidates
  3. Post-filter if needed (e.g., deduplicate by source)

Filter Types:
  - Equality: source = "documentation"
  - Range: created_at BETWEEN '2024-01-01' AND '2024-12-31'
  - Set membership: category IN ('python', 'rust', 'go')
  - Geographic: geo_distance(lat, lon, 50km)
  - Boolean combinations: (source = "docs" AND category = "api") OR priority = "high"
```

**Performance**: Pre-filtering reduces the candidate set, making vector search faster AND more
relevant. Always use pre-filtering when you have known constraints. Qdrant and Weaviate have
the most sophisticated filtering; Pinecone serverless has basic metadata filtering.

#### Hybrid Search (Dense + Sparse Fusion)

```
Dense (Semantic)                    Sparse (Keyword/BM25)
  ↕                                     ↕
Embed query → dense_vec             Tokenize query → sparse_vec
  ↕                                     ↕
ANN search → dense_results          Inverted index → sparse_results
  ↕                                     ↕
          └──────────┬──────────┘
                     ▼
              Fusion Algorithm
        ┌────────────┼────────────┐
        │            │            │
   RRF (Reciprocal   Convex       Learned
   Rank Fusion)      Combination  Weighting
        │            │            │
        └────────────┼────────────┘
                     ▼
               Final Results
```

**RRF (Reciprocal Rank Fusion)**: `score(d) = Σ 1/(k + rank_i(d))` where `k=60` typically.
No normalization needed. Simple, effective, parameter-free.

**Convex combination**: `score(d) = α * dense_score(d) + (1-α) * sparse_score(d)`. Requires
score normalization (min-max or sigmoid). α is tunable.

**When to use hybrid**: Domain-specific terminology, code search, precise queries where keyword
matching is important alongside semantic understanding. Weaviate and Elasticsearch have
built-in hybrid search.

#### Chunking Strategies for Memory

```
STRATEGY                 │  SIZE   │  OVERLAP  │  BEST FOR
─────────────────────────┼─────────┼───────────┼─────────────────────
Fixed-size               │ 256-512 │  10-20%   │ General purpose
                         │ tokens  │           │
Semantic (split by       │ Varies  │  0-5%     │ Documents with clear
sentence/paragraph/      │         │           │ structure
section boundaries)      │         │           │
─────────────────────────┼─────────┼───────────┼─────────────────────
Recursive (split by      │ 512-1024│  10%      │ Code files, markdown
separators hierarchy:    │ tokens  │           │
\n\n → \n → . → space)   │         │           │
─────────────────────────┼─────────┼───────────┼─────────────────────
Agentic (LLM decides     │ Dynamic │  None     │ High-value knowledge
boundaries based on      │         │           │ extraction
semantic coherence)      │         │           │
─────────────────────────┼─────────┼───────────┼─────────────────────
Proposition (extract     │ ~1-3    │  None     │ Factual knowledge
atomic fact statements)  │ sentences│          │ bases
─────────────────────────┼─────────┼───────────┼─────────────────────
```

**Chunk metadata**: Always attach `chunk_index`, `source_document`, `heading_path`, `page_number`,
and `created_at` to every chunk. This enables precise recall tracking and source attribution.

---

### 3. Graph Memory (Relational)

Graph memory captures relationships between entities, enabling multi-hop reasoning and structured
knowledge traversal that pure vector search cannot achieve.

#### Node Type Taxonomy

```
NODE TYPES
├── Entity Nodes (concrete things)
│   ├── Person: { name, role, properties... }
│   ├── Organization: { name, industry, size... }
│   ├── Location: { name, coordinates, type... }
│   ├── Product: { name, category, price... }
│   └── Artifact: { name, type, content_hash... }
│
├── Concept Nodes (abstract ideas)
│   ├── Category: { name, description }
│   ├── Principle: { name, statement }
│   ├── Pattern: { name, template, examples }
│   └── Rule: { condition, action, priority }
│
├── Event Nodes (temporal occurrences)
│   ├── Interaction: { timestamp, type, participants }
│   ├── Decision: { timestamp, outcome, rationale }
│   └── Milestone: { timestamp, description, significance }
│
└── Memory Nodes (system-level)
    ├── Session: { id, start_time, end_time, summary }
    ├── User: { id, preferences, context }
    └── Task: { id, goal, status, parent_task }
```

#### Edge Type Taxonomy

```
EDGE TYPES
├── Structural
│   ├── PART_OF: Component → Whole hierarchy
│   ├── INSTANCE_OF: Entity → Category/Type
│   └── BELONGS_TO: Entity → Group/Collection
│
├── Causal
│   ├── CAUSED_BY: Effect → Cause
│   ├── LEADS_TO: Action → Consequence
│   └── DEPENDS_ON: Component → Dependency
│
├── Relational
│   ├── RELATES_TO: Generic relationship
│   ├── SIMILAR_TO: Entity → Similar Entity
│   ├── CONTRADICTS: Statement → Contradicting Statement
│   └── SUPPORTS: Evidence → Claim
│
├── Temporal
│   ├── PRECEDES: Earlier Event → Later Event
│   ├── FOLLOWS: Later Event → Earlier Event (inverse)
│   └── DURING: Event → Timeframe
│
├── Ownership / Agency
│   ├── CREATED_BY: Artifact → Creator
│   ├── OWNS: Owner → Owned Entity
│   └── PERFORMED_BY: Action → Actor
│
└── Semantic
    ├── SYNONYM_OF: Term → Equivalent Term
    ├── HYPONYM_OF: Specific → General
    └── ANTONYM_OF: Term → Opposite Term
```

#### Construction from Text

```
Pipeline:
  Raw Text
    │
    ▼
  [NER + Relation Extraction] (LLM or dedicated model)
    │
    ├── Extract entities: "Alice" → Person, "Acme Corp" → Organization
    ├── Extract relations: "Alice works at Acme Corp" → (Alice)-[EMPLOYED_BY]->(Acme)
    └── Resolve coreferences: "She" → "Alice"
    │
    ▼
  [Entity Resolution / Deduplication]
    │  Merge "Alice Johnson" and "A. Johnson" into same node
    │  Use embedding similarity + rule-based matching
    │
    ▼
  [Graph Insertion]
    │  MERGE (a:Person {name: "Alice"})
    │  MERGE (o:Organization {name: "Acme Corp"})
    │  MERGE (a)-[:EMPLOYED_BY]->(o)
    │
    ▼
  [Community Detection]
    │  Louvain / Leiden algorithm to find clusters
    │  Generate community summaries via LLM
    │
    ▼
  GraphRAG-ready Knowledge Graph
```

**LLM extraction prompt template**:
```
Extract entities and relationships from the text below.
Output JSON with "entities" (id, type, name, properties) and
"relations" (source_id, target_id, type, evidence).

Text: {chunk}
```

#### GraphRAG and Community Summarization

Community summarization is the key GraphRAG innovation: after building the graph, detect
communities (densely connected subgraphs) and summarize each community into a natural
language description. These summaries become the retrieval units for global queries.

```
GraphRAG Query Flow:

  GLOBAL queries ("What are the main themes?")
    → Map: each community summary evaluated for relevance
    → Reduce: relevant summaries combined, LLM generates answer

  LOCAL queries ("What does entity X relate to?")
    → Starting entity → expand to neighbors → multi-hop traversal
    → Combine context from traversed nodes + edges → LLM generates answer

  HYBRID (community summaries + entity-level details)
    → Both local and global retrieval in parallel
    → Merge contexts → LLM generates answer
```

#### Cypher Query Patterns

```cypher
-- Find all entities related to "Alice" within 2 hops
MATCH (p:Person {name: "Alice"})-[r*1..2]-(connected)
RETURN p, r, connected

-- Find the shortest path between two entities
MATCH path = shortestPath(
  (a:Person {name: "Alice"})-[*]-(b:Organization {name: "Acme Corp"})
)
RETURN path

-- Find common connections between two entities
MATCH (a:Person {name: "Alice"})-[r]-(common)-[s]-(b:Person {name: "Bob"})
RETURN common, type(r), type(s)

-- Community-aware traversal (if using community labels)
MATCH (c:Community {id: $community_id})
MATCH (c)<-[:MEMBER_OF]-(n)
OPTIONAL MATCH (n)-[r]-(neighbor)
RETURN n, r, neighbor
```

**Graph DB selection**: Neo4j (mature, Cypher, managed AuraDB), ArangoDB (multi-model, document+graph),
Kuzu (embedded, fast, no server overhead), FalkorDB (Redis-based, ultra-low latency).

#### Multi-Hop Reasoning

Multi-hop reasoning chains graph traversals with LLM reasoning at each hop:

```
Algorithm: Multi-Hop Reasoning

1. START: query → embed → find seed entity/entities in graph
2. EXPAND: traverse N hops from seed, collect neighbor nodes + edges
3. REASON: LLM evaluates: "Do I have enough to answer? If not, what do I need?"
4. REFINE: If insufficient, use LLM-generated next-hop direction to traverse further
5. REPEAT steps 2-4 until answer found or max hops reached
6. SYNTHESIZE: LLM synthesizes answer from all traversed context

Max hops: 3-5 (beyond this, relevance decays and cost explodes)
```

---

### 4. Episodic Memory (Experiential)

Episodic memory captures the agent's experiences as timestamped records, enabling learning
from past interactions.

#### Event Schema

```json
{
  "event_id": "uuid",
  "session_id": "uuid",
  "timestamp": "2026-05-12T14:30:00Z",
  "event_type": "interaction | action | observation | reflection | decision",
  "actor": "user | agent | system",
  "input": {
    "query": "user's message or trigger",
    "context": { "task_id": "...", "relevant_facts": ["..."] }
  },
  "action": {
    "type": "tool_call | response | internal_thought",
    "name": "search_knowledge_base",
    "parameters": { "query": "..." },
    "reasoning": "why this action was chosen"
  },
  "outcome": {
    "status": "success | failure | partial",
    "result_summary": "what happened",
    "feedback": "user_satisfaction_score or error",
    "latency_ms": 230
  },
  "tags": ["python", "error-handling"],
  "importance": 0.7,
  "embedding": [0.1, 0.3, ...]
}
```

#### Retrieval Strategies

```
TEMPORAL RETRIEVAL                    SEMANTIC RETRIEVAL
─────────────────                     ──────────────────
• Recent bias: last N events          • Embed query → ANN search
• Time-range: events in [t1, t2]      • Similarity threshold filter
• Session-bound: same session_id      • Hybrid: embed + metadata filter
• Recency-weighted scoring            • Tag-based filtering
                                      • Outcome-based (only successes)

COMBINED SCORING:
score(event) = α · temporal_score(event) + β · semantic_score(event)
             + γ · importance_score(event) + δ · outcome_score(event)

temporal_score  = e^(-λ · age)        (exponential decay)
semantic_score  = cosine(query_emb, event_emb)
importance      = normalized importance (0-1)
outcome_score   = 1.0 for success, 0.3 for failure, 0.5 for partial
```

#### Consolidation: Episodes → Knowledge

```
CONSOLIDATION PIPELINE

  Episodic Log
      │
      ▼
  [Clustering] ── Group by: time window, semantic similarity, task type
      │
      ▼
  [Summarization] ── LLM: "Summarize what was learned from these {N} interactions"
      │               Output: { insight, pattern, mistake, improvement }
      │
      ├──→ Semantic Memory: Extract stable facts, add to vector store
      ├──→ Procedural Memory: Extract successful action patterns
      └──→ Graph Memory: Link new entities discovered in episodes

  Consolidation trigger: every N events (e.g., 100), daily batch, or
  when novelty score exceeds threshold (events sufficiently different
  from what's already known).
```

#### Append-Only Log Design

```
WRITE PATH (append-only, immutable):
  Event → validate schema → assign UUID → append to log → update index
  │                                                         │
  └── NEVER update or delete events                        │
                                                            │
READ PATH (indexed access):                                │
  In-memory index (by session, timestamp, tags) ← updated on append
  Vector index (by embedding) ← async reindexing
  Graph index (linked entities) ← async extraction
```

**Storage backends**:
- **Redis Streams**: Lightweight, TTL-based auto-eviction, consumer groups. Best for
  short-lived episodic memory (hours to days) with real-time processing.
- **Kafka**: Persistent, partitioned, replayable. Best for long-term episodic memory
  when you need guaranteed durability and replay capability.
- **PostgreSQL**: Append-only table with BRIN index on timestamp. Simple, ACID,
  good for moderate throughput (<10K events/sec).
- **MongoDB**: Capped collections for fixed-size window, TTL indexes for auto-deletion.
  Good for session-scoped episodic memory.

---

### 5. Working Memory (Attention)

Working memory is the active, limited-capacity buffer that holds the current context. It is
the most performance-critical component — every token in working memory adds latency and cost.

#### Token Budget Management

```
TOKEN BUDGET = Context Window Limit - (System Prompt + Reserved for Output)

Example for 128K window:
  System prompt:           4K tokens
  Output reserve:          4K tokens
  Available for memory:   120K tokens

Allocation within 120K budget:
  ┌─────────────────────────────────────────────────────────┐
  │  Active task context:      20K  (current goal, plan)    │
  │  Recent observations:      30K  (last N interactions)   │
  │  Retrieved relevant:       50K  (from LTM stores)       │
  │  Scratchpad:               20K  (thoughts, calculations)│
  └─────────────────────────────────────────────────────────┘
```

**Budget overflow strategies**:
1. **Prioritize**: Keep task-critical context, drop the rest
2. **Summarize**: Compress older messages into dense summaries
3. **Paginate**: Move less-relevant retrieved context to "page 2", swapped in on demand
4. **Abstract**: Replace detailed context with high-level abstractions

#### Attention Mechanisms for Importance Scoring

```
IMPORTANCE SCORE = f(relevance, recency, uniqueness, task_alignment)

relevance_score   = cosine(query_emb, memory_emb)
recency_score     = e^(-λ · age_in_seconds)       λ tuned for desired half-life
uniqueness_score  = 1 - max_similarity_to_other_memories
task_score        = cosine(task_goal_emb, memory_emb)

COMBINED: importance = Σ w_i · score_i
                       (weights tuned per application)

THRESHOLD: if importance < τ, memory is eligible for eviction or archival
```

**Attention allocation over time**: Start of conversation: allocate budget evenly. As
conversation continues, shift budget toward task-relevant memory and away from stale
greeting/small-talk context. Monitor task progress and adjust dynamically.

#### Summarization and Compression

```
COMPRESSION TECHNIQUES (ordered by lossiness):

1. EXTRACTION (lossless for kept info):
   Keep only top-K most important messages by importance score. Drop rest.

2. ABSTRACTIVE SUMMARIZATION (lossy):
   LLM summarizes N messages → 1 dense summary paragraph.
   ~90% compression, ~15% information loss.

3. BULLET-POINT EXTRACTION (moderate loss):
   Extract key facts, decisions, and action items from conversation.
   ~80% compression, ~10% information loss.

4. KEY-VALUE ABSTRACTION (high compression):
   Store only structured key-value pairs: {decision: "X", reason: "Y", next_step: "Z"}
   ~95% compression, ~25% information loss.

5. PROGRESSIVE SUMMARIZATION:
   Keep recent messages verbatim, summarize mid-range (last hour), heavily compress old.
   Recency-weighted detail.
```

#### Sliding Window Strategies

```
WINDOW CONFIGURATION:

  [Full detail]  [Compressed]  [Heavily compressed]  [Archived]
  ◄── 15 min ──►◄── 1 hour ──►◄────── 24 hours ────►◄── older

  Full detail:      Every message verbatim, all tool calls, all observations
  Compressed:       Summarized by topic/task, key decisions preserved
  Heavy compressed: One-line summary per task/session
  Archived:         Moved to episodic memory, retrieved on demand only
```

#### Recency vs Relevance Tradeoff

```
DECISION MATRIX:

  ┌──────────────────┬──────────────────┬──────────────────────┐
  │                  │  HIGH RECENCY    │   LOW RECENCY        │
  ├──────────────────┼──────────────────┼──────────────────────┤
  │ HIGH RELEVANCE   │ KEEP (priority)  │ KEEP (important      │
  │                  │                  │  context, may be     │
  │                  │                  │  from earlier task)  │
  ├──────────────────┼──────────────────┼──────────────────────┤
  │ LOW RELEVANCE    │ COMPRESS         │ EVICT / ARCHIVE      │
  │                  │ (keep brief      │ (remove from working │
  │                  │  context)        │  memory entirely)    │
  └──────────────────┴──────────────────┴──────────────────────┘
```

---

### 6. Memory Consolidation

Consolidation transforms raw episodic experiences into structured, reusable long-term memory.
It is the bridge between experience and knowledge.

#### Episodic → Semantic (Fact Extraction)

```
INPUT:  Cluster of related episodes (e.g., 50 interactions about "PostgreSQL connection pooling")
        │
        ▼
STEP 1: Pattern Identification
  LLM: "Identify recurring patterns, facts, and principles across these episodes"
  Output: List of candidate knowledge items with supporting episode references
        │
        ▼
STEP 2: Validation
  Cross-reference candidate facts against existing semantic memory
  Resolve contradictions (prefer newer evidence or flag for human review)
  Merge or update existing facts
        │
        ▼
STEP 3: Storage
  Each validated fact → create/update vector memory entry
  Link fact → source episodes in graph memory (PROVENANCE edge)
  Update confidence score based on number and consistency of supporting episodes
```

**Example**:
- Episodes: 20 interactions where users hit "too many connections" error
- Extracted fact: "PostgreSQL default max_connections is 100; increase to 200 for web workloads"
- Confidence: High (20 consistent episodes, 0 contradicting)
- Provenance: Linked to all 20 source episodes

#### Episodic → Procedural (Skill Formation)

```
INPUT:  Successful action sequences across similar tasks
        │
        ▼
STEP 1: Sequence Extraction
  Identify action → outcome pairs that consistently succeeded
  Extract the conditions under which each action was taken
        │
        ▼
STEP 2: Template Creation
  For each recurring task type, create a procedure template:
  { preconditions, action_sequence, expected_outcomes, rollback_steps }
        │
        ▼
STEP 3: Optimization
  Compare multiple successful sequences for the same task
  Identify the shortest / most reliable / most efficient variant
  Store as the "preferred procedure"
        │
        ▼
STEP 4: Storage
  Store procedure in procedural memory store
  Link to source episodes (provenance)
  Set initial confidence based on success rate
```

#### Importance Scoring

```
IMPORTANCE = w1 · recency + w2 · frequency + w3 · salience + w4 · utility

recency:    How recently was this memory accessed or reinforced?
            score = e^(-λ · days_since_last_access)

frequency:  How often is this memory retrieved?
            score = min(1.0, access_count / saturation_threshold)

salience:   How emotionally or contextually significant was the event?
            score = 0-1 (assigned by LLM at recording time based on:
            - Error/failure events (high salience)
            - Positive feedback events (high salience)
            - Routine interactions (low salience)

utility:    How useful has this memory been for solving tasks?
            score = successes_using_this_memory / total_uses

DEFAULT WEIGHTS: recency=0.15, frequency=0.25, salience=0.20, utility=0.40
```

#### Forgetting Curves and Decay

```
EBBINGHAUS FORGETTING CURVE (adapted for AI memory):

Retention
  1.0 │●
      │  ●
  0.8 │    ●
      │      ●
  0.6 │        ●
      │           ●
  0.4 │              ●
      │                 ●
  0.2 │                     ●
      │                          ●●●●●●●
  0.0 └─────────────────────────────────────→ Time
      0   1h   6h   24h   1w   1m   6m   1y

RETENTION FUNCTION: R(t) = e^(-t/s) where s = strength
Strength increases with each reinforcement (retrieval or consolidation)

REINFORCEMENT: Each time a memory is retrieved or consolidated:
  strength_new = strength_old + reinforcement_gain
  where reinforcement_gain depends on:
  - Depth of processing (shallow retrieval < deep consolidation)
  - Emotional salience
  - Association strength (how many other memories link to it)
```

**Decay policies**:

| Memory Type | Half-Life | Decay Strategy |
|-------------|-----------|----------------|
| Working memory | Minutes | Auto-evict when out of budget |
| Short-term episodic | Hours-Days | Exponential decay, archive below threshold |
| Long-term semantic | Weeks-Months | Slow decay, consolidate before deletion |
| Long-term procedural | Months | Only decay if unused AND better procedure exists |
| Graph relationships | Indefinite | Decay only when source entities are removed |

#### Dream-Like Consolidation

```
DREAM CONSOLIDATION (offline / background process):

TRIGGER: Low activity period (nightly batch, idle time, after session close)

PROCESS:
  1. Select recent episodic memories not yet consolidated
  2. Replay them in random order (interleaving)
  3. LLM identifies cross-episode patterns and insights
  4. Generate "dream insights": non-obvious connections
  5. Strengthen graph edges between related entities
  6. Weaken edges that weren't reinforced
  7. Create new semantic memories from discovered patterns
  8. Prune low-importance episodic memories

SCHEDULE: Daily for active users, weekly for inactive users
COST: Can be expensive (many LLM calls). Batch and throttle.
```

---

### 7. Procedural Memory

Procedural memory stores learned skills, action sequences, and task templates. Unlike semantic
memory (knowing "what"), procedural memory stores "how" — the steps to accomplish a task.

#### Representation

```json
{
  "procedure_id": "uuid",
  "name": "Deploy FastAPI app to AWS ECS",
  "description": "Steps to containerize and deploy a FastAPI application",
  "preconditions": [
    "Dockerfile exists in project root",
    "AWS credentials configured",
    "ECR repository exists"
  ],
  "steps": [
    {
      "order": 1,
      "action": "build_docker_image",
      "command": "docker build -t app:latest .",
      "expected_duration_seconds": 60,
      "failure_handling": "retry_with_backoff",
      "max_retries": 3
    },
    {
      "order": 2,
      "action": "tag_and_push",
      "command": "aws ecr get-login-password | docker login...",
      "expected_duration_seconds": 120,
      "failure_handling": "abort_and_notify",
      "max_retries": 1
    }
  ],
  "postconditions": ["App running on ECS", "Load balancer health check passing"],
  "success_rate": 0.95,
  "avg_duration_seconds": 420,
  "last_executed": "2026-05-10T09:00:00Z",
  "source_episodes": ["ep_123", "ep_456"],
  "alternatives": ["proc_deploy_to_lambda", "proc_deploy_to_ec2"],
  "embedding": [0.2, 0.5, ...]
}
```

#### Retrieval-Augmented Action Selection

```
INPUT: Current task description + context
  │
  ▼
1. EMBED task description → task_embedding
2. VECTOR SEARCH in procedural memory → top-K similar procedures
3. FILTER by preconditions match (can we execute this now?)
4. RANK by: similarity · success_rate · recency
5. RETURN top-ranked procedure (or synthesize from multiple if none match well)
6. EXECUTE procedure, record outcome → update success_rate, last_executed
7. If failure: flag procedure, try alternative, initiate skill refinement
```

#### Skill Refinement Loop

```
EXECUTE → OBSERVE OUTCOME → REFLECT → REFINE

REFLECT: LLM analyzes execution trace:
  - What went well? (reinforce)
  - What went wrong? (identify failure point)
  - Was there a faster way? (optimization opportunity)
  - Were preconditions wrong or incomplete? (update)

REFINE: Update the procedure:
  - Adjust steps ordering or commands
  - Add/modify preconditions
  - Update failure_handling per step
  - Increase/decrease confidence (success_rate)
  - If major change, create new procedure version, link to old
```

#### Cross-Task Pattern Transfer

```
When a pattern succeeds across multiple different task types, promote it
to a GENERAL STRATEGY:

Example discovery:
  "Breaking complex tasks into subtasks improves success rate"
  → Promote from specific-task pattern to general procedural principle
  → Store as { strategy: "decompose_and_conquer", applicability: "any complex task" }
  → This strategy is now available as a meta-procedure applied before task execution
```

---

### 8. Implementation Patterns

#### Mem0 Integration

```python
from mem0 import Memory

# Mem0 provides a managed memory layer with auto-consolidation
memory = Memory()

# Add memories (auto-embedded, auto-categorized)
memory.add("User prefers dark mode and Python", user_id="alice")
memory.add("Project X uses PostgreSQL with pgvector", user_id="alice")

# Semantic search across all memories
results = memory.search("What database does Project X use?", user_id="alice")

# Get all memories for a user (with optional filtering)
all_memories = memory.get_all(user_id="alice")

# Update or delete specific memories
memory.update(memory_id="mem_123", data="Updated preference")
memory.delete(memory_id="mem_456")

# Mem0 architecture:
# ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
# │   Add text  │───►│  Embedding   │───►│  Vector DB   │
# │             │    │  + Metadata  │    │  (Qdrant)    │
# └─────────────┘    └──────────────┘    └──────────────┘
#                            │
#                     ┌──────▼──────┐
#                     │  Graph DB   │ (Neo4j — entity links)
#                     └──────┬──────┘
#                            │
#                     ┌──────▼──────┐
#                     │  History DB │ (PostgreSQL — full log)
#                     └─────────────┘
```

#### LangChain Memory Classes

```python
from langchain.memory import (
    ConversationBufferMemory,
    ConversationSummaryMemory,
    ConversationBufferWindowMemory,
    ConversationSummaryBufferMemory,
    ConversationTokenBufferMemory,
    VectorStoreRetrieverMemory,
    CombinedMemory,
)

# Buffer: keeps ALL messages (dangerous — infinite growth)
buffer = ConversationBufferMemory(return_messages=True)

# Window: keeps last K messages
window = ConversationBufferWindowMemory(k=20, return_messages=True)

# Summary: progressively summarizes old messages
summary = ConversationSummaryMemory(llm=llm, return_messages=True)

# Summary Buffer: window + summary of older messages (RECOMMENDED)
summary_buffer = ConversationSummaryBufferMemory(
    llm=llm,
    max_token_limit=4000,  # summary threshold
    return_messages=True,
)

# Token buffer: limits by token count, not message count
token_buffer = ConversationTokenBufferMemory(
    llm=llm,
    max_token_limit=4000,
    return_messages=True,
)

# Vector memory: retrieve relevant past messages via embedding
vector_memory = VectorStoreRetrieverMemory(
    retriever=vectorstore.as_retriever(k=10),
    memory_key="relevant_history",
)

# Combined: use multiple memory types together
combined = CombinedMemory(memories=[summary_buffer, vector_memory])
```

#### Custom Multi-Store Memory Manager

```python
from dataclasses import dataclass, field
from typing import Any
import uuid
import time
import math

@dataclass
class MemoryItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    memory_type: str = "semantic"  # semantic | episodic | procedural
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    importance: float = 0.5
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0

class MemoryManager:
    """Routes memory operations to appropriate stores based on type."""

    def __init__(
        self,
        vector_store,       # Qdrant / Pinecone / pgvector client
        graph_store,        # Neo4j driver
        relational_store,   # PostgreSQL / SQLite connection
        episodic_store,     # Redis / Kafka client
        embed_fn,           # embedding function: str → list[float]
        llm,                # LLM for consolidation
    ):
        self.vector = vector_store
        self.graph = graph_store
        self.relational = relational_store
        self.episodic_log = episodic_store
        self.embed = embed_fn
        self.llm = llm

    async def add(self, content: str, memory_type: str = "semantic", **metadata):
        item = MemoryItem(content=content, memory_type=memory_type, metadata=metadata)

        if memory_type == "episodic":
            await self._store_episodic(item)
        elif memory_type == "semantic":
            item.embedding = await self.embed(content)
            await self._store_semantic(item)
        elif memory_type == "procedural":
            item.embedding = await self.embed(content)
            await self._store_procedural(item)

        # Cross-store indexing: always link in graph
        await self._index_in_graph(item)
        return item.id

    async def retrieve(
        self,
        query: str,
        memory_types: list[str] | None = None,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[MemoryItem]:
        if memory_types is None:
            memory_types = ["semantic", "episodic", "procedural"]

        query_emb = await self.embed(query)
        results = []

        if "semantic" in memory_types:
            results.extend(await self._search_semantic(query_emb, top_k, filters))
        if "episodic" in memory_types:
            results.extend(await self._search_episodic(query_emb, top_k, filters))
        if "procedural" in memory_types:
            results.extend(await self._search_procedural(query_emb, top_k, filters))

        # Multi-hop graph enrichment
        results = await self._enrich_with_graph(results)

        # Rerank across stores by combined importance
        results.sort(key=lambda m: self._score(m, query_emb), reverse=True)
        return results[:top_k]

    async def consolidate(self, time_window_hours: int = 24):
        """Run consolidation: episodes → semantic + procedural"""
        recent = await self._get_recent_episodes(time_window_hours)
        if len(recent) < 10:
            return  # not enough data to consolidate

        clusters = await self._cluster_episodes(recent)
        for cluster in clusters:
            summary = await self._summarize_cluster(cluster)
            self.add(summary["facts"], memory_type="semantic",
                     source_episodes=[e.id for e in cluster])
            if summary.get("procedure"):
                self.add(summary["procedure"], memory_type="procedural",
                         source_episodes=[e.id for e in cluster])

    async def forget(self, strategy: str = "decay"):
        """Apply forgetting based on Ebbinghaus decay curve."""
        now = time.time()
        for store_type in ["semantic", "episodic", "procedural"]:
            memories = await self._get_all_by_type(store_type)
            for mem in memories:
                age = now - mem.last_accessed
                retention = math.exp(-age / mem.importance * 100000)
                if retention < 0.1:  # below 10% retention
                    await self._archive_or_delete(mem)

    def _score(self, item: MemoryItem, query_emb: list[float]) -> float:
        relevance = cosine_similarity(query_emb, item.embedding) if item.embedding else 0.5
        recency = math.exp(-(time.time() - item.created_at) / 86400)  # 1-day half-life
        return 0.4 * relevance + 0.2 * recency + 0.4 * item.importance
```

#### Memory Routing API

```
MEMORY ROUTER: Unified API that intelligently routes to appropriate store.

┌─────────────────────────────────────────────────────────┐
│                    MemoryRouter                          │
│                                                          │
│  add(content, type_hint=None)                            │
│    ├── type_hint="episodic"    → Episodic Store          │
│    ├── type_hint="semantic"    → Vector Store            │
│    ├── type_hint="procedural"  → Procedural Store        │
│    └── type_hint=None          → Auto-classify via LLM   │
│                                                          │
│  search(query, stores="all", top_k=10)                   │
│    ├── stores="semantic"       → Vector search only      │
│    ├── stores="episodic"       → Temporal + similarity   │
│    ├── stores="graph"          → Graph traversal         │
│    └── stores="all"            → Federated search + rerank│
│                                                          │
│  consolidate(trigger="auto")                             │
│    └── Auto-triggered when episodic buffer > threshold   │
└─────────────────────────────────────────────────────────┘
```

---

### 9. Memory Evaluation

#### Recall Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| **Recall@K** | |{relevant} ∩ {retrieved K}| / |{relevant}| | > 0.90 @ K=10 |
| **MRR** (Mean Reciprocal Rank) | 1/|Q| Σ 1/rank_of_first_relevant | > 0.80 |
| **Hit Rate** | fraction of queries where at least 1 relevant retrieved | > 0.95 |
| **NDCG@K** | DCG@K / IDCG@K | > 0.85 |
| **Latency P50** | median retrieval time | < 100ms |
| **Latency P99** | 99th percentile retrieval time | < 500ms |

#### Precision and Relevance

```
PRECISION@K = |{relevant} ∩ {retrieved K}| / K

MEASUREMENT:
  For each test query, annotate ground-truth relevant memories.
  Run retrieval, check overlap.

LLM-AS-JUDGE (no human annotation):
  For each retrieved memory, ask LLM:
  "On a scale of 0-3, how relevant is this memory to the query '{query}'?"
  0 = irrelevant, 1 = tangentially related, 2 = relevant, 3 = directly answers

  Consider scores ≥ 2 as "relevant" for precision/recall calculation.
```

#### Consolidation Quality

```
CONSOLIDATION QUALITY CHECKLIST:

□ FACTUAL ACCURACY: Are extracted facts correct?
  Test: Sample 20 consolidated facts, verify against source episodes.

□ COMPLETENESS: Are important insights extracted?
  Test: Have human annotator list "key insights" from episodes.
        Check what fraction were captured in consolidation.

□ COMPRESSION RATIO: How much did we compress?
  Measure: tokens_before_consolidation / tokens_after_consolidation
  Target: 10:1 to 50:1 without significant information loss.

□ NOVELTY: Are consolidated items adding new information?
  Test: Check cosine similarity of new semantic memories against existing.
  Flag duplicates (cosine > 0.95) for deduplication.

□ HALLUCINATION RATE: Are any consolidated facts fabricated?
  Test: LLM-pair evaluation — one LLM checks if fact is supported by source.
  Target: < 1% hallucination rate.
```

#### Retention Over Time

```
LONGITUDINAL RETENTION TEST:

1. Store N memories at T0
2. At T1 (1 hour), T2 (1 day), T3 (1 week), T4 (1 month):
   - Query for each stored memory
   - Measure: retrieval success rate, rank position, latency

METRICS:
  Retention Rate(t) = successfully_retrieved_at_t / total_stored
  Rank Decay(t) = avg_rank_at_t - avg_rank_at_T0

EXPECTED:
  - Semantic memory: stable retention (98%+ at 1 month)
  - Episodic memory: rapid decay unless consolidated (50% at 1 week)
  - Procedural memory: very stable (> 95% at 1 month)
```

#### Memory Latency Benchmarks

```
BENCHMARK STANDARDS (for retrieval across stores):

  Vector Search (ANN, 1M vectors):
    P50: < 10ms | P99: < 50ms

  Graph Traversal (1-3 hops, 100K nodes):
    P50: < 20ms | P99: < 100ms

  Episodic Retrieval (last 10K events):
    P50: < 30ms | P99: < 150ms

  Federated Search (all stores combined):
    P50: < 100ms | P99: < 300ms

  Consolidation (100 episodes → 10 facts):
    < 10 seconds (batch, async)
```

---

### 10. Privacy and Security

#### Data Isolation

```
ISOLATION LEVELS:

  USER-LEVEL: Each user's memories are fully isolated.
    - Separate vector namespaces per user
    - Separate graph subgraphs per user
    - Episodic logs partitioned by user_id

  SESSION-LEVEL: Memories exist only within a session.
    - In-memory only, no persistence
    - Cleared on session end

  ORGANIZATION-LEVEL: Shared memory within org, isolated from other orgs.
    - Tenant-aware routing in all stores
    - Access control lists on graph nodes

  GLOBAL (DANGEROUS): Mixed memories across users.
    - Only for anonymized, aggregated knowledge (e.g., "common patterns")
    - NEVER for personal or sensitive data
```

#### Sensitive Information Handling

```
DETECTION: Before storing any memory, scan for:
  - PII: emails, phone numbers, SSNs, addresses
  - Secrets: API keys, passwords, tokens
  - Financial data: credit card numbers, bank accounts

ACTION: If sensitive data detected:
  1. Redact (replace with [REDACTED]) before embedding
  2. Store redacted version in memory
  3. Log detection event (without the sensitive data)
  4. Optionally: abort storage, notify user

TOOLS: Presidio (Microsoft), spaCy NER, custom regex patterns
```

#### Access Control

```
ACCESS CONTROL MATRIX:

  MEMORY TYPE      │  READ             │  WRITE            │  DELETE
  ─────────────────┼───────────────────┼───────────────────┼────────────
  Semantic         │ Agent + User      │ Agent (auto) +    │ User only
                   │                   │ User (explicit)   │
  Episodic         │ Agent (own) +     │ Agent (own) +     │ Auto-expire
                   │ User (all own)    │ System (auto)     │
  Procedural       │ Agent (all)       │ Agent (auto) +    │ Admin only
                   │                   │ Admin             │
  Graph            │ Agent (own        │ Agent (auto)      │ User (own
                   │ subgraph)         │                   │ subgraph)
```

#### Encryption and Compliance

```
AT REST: AES-256-GCM encryption for all persistent memory stores.
  - Vector DB: encrypted storage (most managed services provide this)
  - Graph DB: encrypted volumes
  - Episodic logs: encrypted with per-user keys

IN TRANSIT: TLS 1.3 minimum for all store connections.

RIGHT TO BE FORGOTTEN (GDPR Art. 17):
  1. Identify all memories associated with user_id
  2. Delete from all stores (vector, graph, episodic, procedural)
  3. Cascade: delete graph edges pointing to deleted nodes
  4. Log deletion for audit trail
  5. Confirm deletion within 30 days

DATA RETENTION POLICIES:
  - Episodic: auto-expire after configurable TTL (default 90 days)
  - Semantic: persist indefinitely (user knowledge), user can delete
  - Procedural: persist indefinitely (shared skills), admin can prune unused
  - Graph: persist as long as linked entities exist
```

---

### 11. Anti-Patterns

| # | Anti-Pattern | Why It Fails | Fix |
|---|-------------|--------------|-----|
| 1 | **Single store for all memory types** | Vector search alone cannot express relationships, temporal order, or procedures | Use multi-store architecture: vector + graph + episodic + procedural |
| 2 | **Infinite working memory** | Growing context window kills latency, costs, and eventually exceeds model limits | Aggressive budget management: summarize, compress, evict. Never exceed 80% of context limit |
| 3 | **No consolidation** | Raw episodes accumulate without extraction of patterns; high storage cost, low utility | Schedule regular consolidation (daily batch or event-count trigger) |
| 4 | **No forgetting** | Storage grows unbounded; retrieval becomes slower and less precise as noise accumulates | Implement decay curves; archive low-importance memories; respect TTLs |
| 5 | **Embedding without chunking** | Full documents as single embeddings lose granularity; retrieval returns entire documents instead of relevant passages | Chunk documents semantically; embed per chunk; attach metadata |
| 6 | **Ignoring metadata filtering** | Pure vector search on millions of embeddings without pre-filtering wastes latency and reduces precision | Pre-filter by metadata (date, source, category) before ANN search |
| 7 | **No provenance tracking** | Consolidated facts lose connection to source episodes; impossible to verify or update | Always link consolidated knowledge to source episodes via graph edges |
| 8 | **Stale embeddings** | Embedding model updated but stored vectors use old model; retrieval quality degrades | Track embedding model version per vector; plan re-embedding migrations |
| 9 | **Graph without community detection** | Flat graph traversal at query time is slow; no high-level understanding of knowledge domains | Pre-compute communities (Louvain/Leiden); summarize each; use for global queries |
| 10 | **No memory evaluation** | Memory system degrades silently; you don't know when retrieval quality drops | Implement recall@K, MRR, and latency benchmarks; run regularly; alert on regression |
| 11 | **Blocking consolidation** | Consolidation runs synchronously during user requests, adding latency | Consolidation must be async (background job, queue, cron). Never block the user for memory maintenance |
| 12 | **Hardcoded importance weights** | Fixed weights for recency/relevance/importance don't adapt to different domains or users | Make weights tunable per application; consider learning optimal weights from user feedback |
| 13 | **No privacy isolation** | User A's memories visible in User B's retrieval results | Strict namespace isolation per user/org at every store level; tenant-aware routing |
| 14 | **Caching without invalidation** | Retrieved memories cached but never invalidated; stale memories fed to agent | TTL on cache entries; invalidate on memory update/delete; version-track all memories |
| 15 | **Procedural memory without verification** | Stored procedures become outdated (API changes, deprecations) but are still retrieved and executed | Version procedures; verify preconditions before execution; track success_rate and auto-deprecate failing procedures |

---

### Cross-Skill Integration Patterns

**With ai-agent-loop** — Memory is the persistence layer for agent behavior:
- Agent trajectories (Thought → Action → Observation) are stored in episodic memory using the event schema from Section 4
- Working memory IS the agent's active context buffer — the ReAct `history` array. Use budget management (Section 5) to prevent overflow
- Procedural memory (Section 7) stores learned action sequences retrieved during agent task execution
- After a session closes, the consolidation engine (Section 6) extracts stable facts from episode clusters into semantic memory

**With ai-rag** — Memory and RAG solve complementary retrieval problems:
- **RAG** retrieves external, static knowledge (documentation, code, articles)
- **Semantic Memory** retrieves the agent's personal knowledge from past interactions
- Both use vector stores — they can share infrastructure but should be logically separated (different collections/namespaces)
- When a RAG retrieval answers a query, the retrieved document can be stored in semantic memory with a "source=external" tag to avoid redundant future retrievals

**With database-event-sourcing** — Episodic memory is event sourcing applied to agent cognition:
- The append-only episodic log (Section 4) follows the same pattern as the event store (database-event-sourcing Section 1)
- Event schema: eventId, eventType (past-tense), aggregateId, timestamp, payload — identical concepts
- Snapshots (Section 6 consolidation) serve the same purpose as event store snapshots — avoid replaying the full log
- CQRS pattern: Episodic log = write model; Semantic/Procedural stores = read models built by projectors (consolidation engine)

**With database-postgres** — Production memory storage uses PostgreSQL patterns:
- Episodic event log: Use BRIN index on `created_at` for append-only time-series data
- Working memory checkpoints: Partition by `session_id` for efficient cleanup
- Vector memory with pgvector: Apply the index strategies from database-postgres Section 1

**With infra-observability** — Multi-store memory requires comprehensive monitoring:
- Vector store: query latency P50/P99, index size, recall@10
- Graph store: traversal latency, node/edge count, community count
- Episodic log: append rate, log size, consolidation throughput
- OpenTelemetry spans across all store operations with store type as an attribute

**Skill loading order**: `understanding` → `ai-memory` → `database-postgres` (if using pgvector) or `database-event-sourcing` (for event log patterns) → `ai-agent-loop` (the consumer) → `ai-rag` (for shared retrieval infrastructure)

---

### 12. Implementation Checklist

- [ ] Multi-store architecture defined (vector + graph + episodic + procedural)
- [ ] Embedding model selected and dimension configured
- [ ] Vector store provisioned with metadata filtering enabled
- [ ] Graph schema defined (node types, edge types, constraints)
- [ ] Episodic log configured (append-only, indexed, TTL set)
- [ ] Working memory budget defined (< 80% of context window)
- [ ] Summarization/compression pipeline implemented
- [ ] Consolidation scheduler configured (trigger, batch size, async)
- [ ] Forgetting curves parameterized (half-life per memory type)
- [ ] Memory routing API implemented (auto-classify, federated search, rerank)
- [ ] Evaluation harness built (recall@K, MRR, latency benchmarks)
- [ ] Privacy isolation verified (user-level namespace separation)
- [ ] Sensitive information detection and redaction active
- [ ] Access control enforced per memory type
- [ ] Encryption at rest and in transit for all stores
- [ ] Right-to-be-forgotten deletion cascade implemented
- [ ] Monitoring dashboards: retrieval latency, store sizes, consolidation throughput
- [ ] Alerting: retrieval latency p99 > 500ms, recall@10 < 0.80, consolidation failures
