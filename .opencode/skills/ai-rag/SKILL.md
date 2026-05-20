---
name: ai-rag
description: Advanced RAG: Corrective RAG, Self-RAG, HyDE, agentic RAG, multi-step retrieval, embedding strategies, chunking, reranking, fusion retrieval, parent-child chunking, sentence window retrieval, multi-vector retrieval, contextual compression, FLARE, evaluation (RAGAS, NDCG, MRR), production pipelines, monitoring, and caching
license: MIT
compatibility: opencode
metadata:
  audience: ai-engineers
  domain: ai-agent
  paradigm: retrieval
  capabilities:
    - embedding-model-selection
    - vector-store-comparison
    - chunking-strategies
    - corrective-rag
    - self-rag
    - hyde
    - agentic-rag
    - reranking
    - fusion-retrieval
    - parent-child-chunking
    - sentence-window-retrieval
    - multi-vector-retrieval
    - contextual-compression
    - flare-active-retrieval
    - ragas-evaluation
    - production-pipelines
    - embedding-caching
  integrates_with:
    - ai-agent-loop
    - ai-memory
    - database-postgres
    - database-event-sourcing
    - backend-python
    - infra-observability
---

## AI RAG (Retrieval Augmented Generation) Skill

### Retrieval Architecture

#### Embedding Models

| Model | Max Tokens | Dimensions | Multilingual | Cost (per 1M tokens) | Best For |
|-------|-----------|------------|--------------|----------------------|----------|
| OpenAI text-embedding-3-small | 8191 | 512/1536 | English-primary | $0.02 | Budget, high throughput |
| OpenAI text-embedding-3-large | 8191 | 256/1024/3072 | English-primary | $0.13 | Maximum quality, MMLU |
| voyage-3-large | 32000 | 1024 | Limited | $0.06 | Long documents, code |
| jina-embeddings-v3 | 8192 | 1024 | 89 languages | Free (self-host) / API | Multilingual, task-specific LoRA |
| bge-m3 (BAAI) | 8192 | 1024 | 100+ languages | Free (self-host) | Multi-lingual, dense+sparse |
| Cohere Embed v3 | 512 | 1024 | English-primary | $0.10 | Classification, clustering |
| multilingual-e5-large | 512 | 1024 | 100+ languages | Free (self-host) | Multilingual parity |
| gte-Qwen2-7B-instruct | 32768 | 3584 | Multilingual | Free (self-host) | Maximum context, instruction-following |

**Selection rubric**: (1) Language requirements → multilingual model if non-English content; (2) Document length → long-context model if > 2K tokens per chunk; (3) Latency budget → smaller model for real-time; (4) Self-host vs API → bge-m3/jina for air-gapped deployments.

**Embedding best practices**:
- Always prepend task-specific instructions to queries: `"Represent this query for retrieval: {query}"` (instruction-tuned models)
- Batch embed at 100-200 texts per call for throughput
- Normalize embeddings to unit length for cosine similarity (most APIs do this)
- Store embeddings as half-precision (float16) to halve storage
- Rotate embedding models carefully — embeddings are NOT cross-model compatible; re-embed corpus on model change

#### Vector Stores

| Store | Architecture | Filtering | Quantization | Hybrid Search | Tenancy | Best For |
|-------|-------------|-----------|--------------|---------------|---------|----------|
| Qdrant | Rust, gRPC | Full payload filtering | Scalar, Binary, Product | Dense + Sparse | Multi-tenant | Production, filtering-heavy |
| Pinecone | Serverless, closed-source | Metadata filtering | None (server-managed) | Sparse-dense | Namespaces | Zero-ops, fast start |
| Weaviate | Go, GraphQL | Full GraphQL filtering | PQ, BQ, SQ | BM25 + Dense hybrid | Multi-tenant | Hybrid search, schema-rich |
| Chroma | Python, Rust | Metadata filtering | None | None (add-on) | Collections | Local dev, prototyping |
| pgvector | PostgreSQL extension | Full SQL WHERE | None (IVFFlat/HNSW) | Via tsvector + pgvector | PostgreSQL schemas | Existing Postgres infra |
| Milvus | C++, distributed | Scalar filtering | IVF_PQ, HNSW | BM25 + Dense | Multi-tenant | Billion-scale, GPU index |
| Elasticsearch | Java, Lucene | Full query DSL | PQ, SQ | BM25 + kNN native | Index-based | Already on ES stack |
| LanceDB | Rust, embedded | SQL filtering | IVF_PQ | None (columnar) | Tables | Local-first, multimodal |

**Selection rubric**:
- **Postgres shop with < 10M vectors** → pgvector (no new infra)
- **Need filtering + vector search, < 100M vectors** → Qdrant
- **Zero-ops, serverless, fast time-to-market** → Pinecone
- **Hybrid search (BM25 + vector) is critical** → Weaviate or Elasticsearch
- **Billion-scale, custom indexing** → Milvus
- **Local dev / prototyping** → Chroma or LanceDB

#### Chunking Strategy Deep Dive

```
Chunking Decision Tree:
                      ┌─ Fixed-size (512 tokens) ─── Simple, predictable, good baseline
Semantic-aware ───────┤
  (preferred)         ├─ Recursive character split ─ Respects paragraph/sentence boundaries
                      ├─ Semantic chunker ────────── Uses embedding similarity to find breakpoints
                      └─ Document-aware ──────────── Respects Markdown headings, code blocks, tables
```

**Fixed-size chunking**: Split every N tokens. Fast, deterministic. Overlap 10-20% to preserve context at boundaries.

**Recursive split**: Split by `\n\n` → `\n` → `. ` → ` ` in descending priority. Respects natural document structure. LangChain `RecursiveCharacterTextSplitter` is the standard implementation.

**Semantic chunking**: Compute embedding similarity between consecutive sentences. Place split boundaries at minima in the similarity curve. Produces chunks that are semantically coherent. 2-3x slower to index but 10-30% better retrieval precision.

**Chunk sizing rules**:
- 256-512 tokens: Best for factoid QA, high precision
- 512-1024 tokens: Best for summarization, medium-complexity queries
- 1024-2048 tokens: Best for multi-hop reasoning, complex documents
- Smaller chunks = higher precision, lower recall (may miss context)
- Larger chunks = higher recall, lower precision (noise dilutes relevance)

**Metadata enrichment**: Every chunk must carry:
- `source`: file path, URL, or document ID
- `page_number` / `section`: for citation
- `heading_hierarchy`: `["H1", "H2", "H3"]` for structural context
- `chunk_index`: position within document (for neighbor retrieval)
- `created_at` / `updated_at`: for temporal filtering
- `content_type`: `text`, `code`, `table`, `image_caption`

#### Token Limits and Embedding Dimension Tradeoffs

| Dimension | Storage (1M vectors) | Recall@10 (approx) | Query Speed | Notes |
|-----------|---------------------|--------------------|-------------|-------|
| 256 | 1 GB | 92% of 1536-dim | 4x faster | Good for high-throughput, budget-sensitive |
| 512 | 2 GB | 96% of 1536-dim | 2x faster | text-embedding-3-small sweet spot |
| 768 | 3 GB | 98% of 1536-dim | 1.5x faster | Common open-source dimension |
| 1024 | 4 GB | 99% of 1536-dim | 1x baseline | Jina, bge-m3, voyage-3 default |
| 1536 | 6 GB | 100% (baseline) | 1x baseline | OpenAI ada-002 legacy |
| 3072 | 12 GB | ~101% | 0.5x speed | text-embedding-3-large max; marginal gain |

**Rule**: OpenAI `text-embedding-3-*` supports Matryoshka representation — you can truncate to any smaller dimension without re-embedding. Use `dimensions=1024` for the best cost/quality tradeoff.

### Corrective RAG (CRAG)

**Full algorithm**:
```
CRAG(query, retriever, generator, evaluator, fallback):
  1. docs = retriever.retrieve(query, k=10)
  2. scores = evaluator.score(query, docs)           # relevance per doc
  3. relevant = [d for d, s in zip(docs, scores) if s > CONFIDENCE_THRESHOLD]
  
  4. if |relevant| == 0:
       # Gate: no documents are relevant
       if fallback == "web_search":
         docs = web_search(query)
       elif fallback == "refuse":
         return "I don't have enough information to answer this."
  
  5. elif |relevant| < KNOWLEDGE_THRESHOLD:
       # Partial relevance: rephrase and re-retrieve
       rewritten_queries = [query] + rephrase(query, n=3)
       additional_docs = []
       for q in rewritten_queries:
         additional_docs.extend(retriever.retrieve(q, k=5))
       docs = deduplicate(relevant + additional_docs)
  
  6. docs = reranker.rerank(query, docs, top_k=5)
  7. answer = generator.generate(query, docs)
  8. return answer
```

**Retrieval quality evaluation**:
- Train a lightweight classifier (distilBERT fine-tuned) to score doc relevance given (query, doc) pairs
- Use LLM-as-judge: `"On a scale of 1-5, how relevant is this document to the query?"` — accurate but slower
- Heuristic fallback: BM25 score, embedding cosine similarity threshold

**Query rephrasing strategies**:
1. **Keyword extraction**: Extract key entities and concepts, search each independently
2. **Question decomposition**: Break into sub-questions, search each, aggregate
3. **Perspective shift**: Rephrase the query from different angles (definition, example, how-to, comparison)
4. **Synonym expansion**: Replace key terms with synonyms using a thesaurus or LLM

**Fallback chain**: Local index → Broader index (all documents, no filters) → Public web search (Tavily, Brave, SerpAPI) → Refuse to answer

### Self-RAG

Self-RAG trains an LLM to predict special reflection tokens during generation.

**Reflection token vocabulary**:
- `[Retrieve]`: The model needs external knowledge for the next segment
- `[NoRetrieve]`: Parametric knowledge is sufficient
- `[ISREL]`: Retrieved passage is relevant
- `[IRREL]`: Retrieved passage is irrelevant
- `[ISSUP]`: Generated text is fully supported by retrieved passage
- `[PARTSUP]`: Generated text is partially supported
- `[NO SUP]`: Generated text is not supported (hallucination risk)
- `[ISUSE]`: Response is useful to the user (1-5)

**Generation loop**:
```
SelfRAG(query, retriever, generator):
  context = []
  segments = []
  
  while not done:
    # Model predicts whether to retrieve
    token = generator.predict_retrieval_token(query, context, segments)
    
    if token == "[Retrieve]":
      # Generate retrieval query from current context
      retrieval_query = generator.generate_retrieval_query(query, segments)
      docs = retriever.retrieve(retrieval_query, k=5)
      context.extend(docs)
    
    segment = generator.generate_segment(query, context, segments)
    
    # Model self-critiques with reflection tokens
    relevance = generator.predict_relevance(context)
    support = generator.predict_support(segment, context)
    usefulness = generator.predict_usefulness(segment)
    
    if relevance == "[IRREL]":
      context = drop_irrelevant(context)
    if support == "[NO SUP]":
      segment = generator.regenerate_with_support(segment, context)
    
    segments.append(segment)
    if done_token in segment:
      break
  
  return concatenate(segments)
```

**Parametric vs retrieved tradeoff**:
- Self-RAG uses `[NoRetrieve]` when the model is confident in its parametric knowledge (common knowledge, definitions, simple facts)
- Uses `[Retrieve]` when the query requires specific, changing, or domain-specific information
- Training data: pairs of (query, oracle-retrieval-decision) generated by GPT-4 with ground-truth annotations

### HyDE (Hypothetical Document Embeddings)

**Core insight**: Queries and documents exist in different semantic spaces. A short query (`"climate change effects"`) and a relevant document (`"Rising global temperatures have caused..."`) have low embedding similarity despite being topically aligned. HyDE bridges this gap by generating a hypothetical document from the query, then embedding that document.

**Algorithm**:
```
HyDE(query, generator, retriever):
  # Step 1: Generate hypothetical answer document
  hypothetical_doc = generator.generate(
    f"Write a passage that answers the question: {query}"
    # Use zero-shot instruction: no retrieval, just parametric generation
  )
  
  # Step 2: Embed the hypothetical document (NOT the query)
  hyp_embedding = embed(hypothetical_doc)
  
  # Step 3: Search for similar real documents
  real_docs = retriever.search_by_embedding(hyp_embedding, k=10)
  
  return real_docs
```

**When HyDE works best**:
- **Short, under-specified queries**: "What is the capital of France?" → generates full paragraph → better match
- **Asymmetric search**: Query is 3 words, documents are 500 words
- **Zero-shot scenarios**: No query-document pairs for fine-tuning a cross-encoder
- **Factoid QA**: Precision-critical retrieval where query alone is too sparse

**When HyDE underperforms standard retrieval**:
- Long, detailed queries (query already rich enough)
- Domain-specific jargon (LLM may generate incorrect hypothetical content, misleading retrieval)
- High-latency scenarios (adds 1 LLM generation call to every query)

### Agentic RAG

**Multi-step retrieval with tool calling**:
```
AgenticRAG(query, tools, retriever, generator, max_steps=5):
  context = []
  steps = 0
  
  while steps < max_steps:
    action = generator.decide_action(query, context, tools)
    
    if action.type == "RETRIEVE":
      sub_query = action.query
      source = action.source  # specific index, tool, or API
      docs = execute_retrieve(sub_query, source, retriever, tools)
      context.append({"query": sub_query, "docs": docs})
    
    elif action.type == "REASON":
      context.append({"reasoning": action.thought})
    
    elif action.type == "GENERATE":
      return generator.generate(query, context)
    
    steps += 1
  
  # Exhausted steps: force generate with partial context
  return generator.generate(query, context)
```

**Query decomposition strategies**:
1. **Least-to-most**: Decompose complex query into dependencies. Answer sub-question 1 → use result in sub-question 2 → synthesize final answer
2. **Plan-and-execute**: Generate a retrieval plan (list of queries + their order) → execute each → aggregate
3. **Tree decomposition**: Break into independent sub-queries (parallel retrieval) + dependent sub-queries (sequential) — build a retrieval DAG
4. **IRCoT** (Interleaving Retrieval with Chain-of-Thought): Retrieve → reason → retrieve (informed by reasoning) → reason → ... until answer

**Dynamic source selection**:
- Route queries to appropriate indices based on query type: code docs → code index, API specs → spec index, architecture → design docs index
- Use query classifier (fine-tuned BERT or LLM few-shot) to determine which sources to query
- Merge results from multiple sources with source-weighted scoring

### Reranking

**Two-stage retrieval architecture**:
```
Stage 1: Candidate Retrieval (fast, approximate, high recall)
  Query → Embedding → Vector Search (k=50-200) → Candidate Set
  
Stage 2: Reranking (slower, precise, high precision)
  (Query, Candidate) → Cross-Encoder → Relevance Score → Top-k (k=5-10)
```

**Cross-encoder rerankers comparison**:

| Reranker | Architecture | Max Tokens | Multilingual | Cost | Notes |
|----------|-------------|------------|--------------|------|-------|
| Cohere Rerank v3 | Proprietary | 4096 | English-primary | $2/1M searches | Best overall quality |
| bge-reranker-v2-m3 | BAAI, open-source | 8192 | 100+ languages | Free (self-host) | Multilingual powerhouse |
| jina-reranker-v2 | Open-source | 8192 | Multilingual | Free (self-host) | Good quality, CodeBERT-based |
| ColBERTv2 | Late interaction | 512 | English | Free (self-host) | Token-level matching |
| mxbai-rerank-base | Open-source | 512 | English | Free (self-host) | Lightweight, fast |
| RankLLM | LLM-based | Varies | Depends on LLM | High | Listwise, best for small k |

**Listwise vs Pointwise reranking**:
- **Pointwise**: Score each (query, doc) pair independently. Faster, parallelizable. Use for k > 20.
- **Listwise**: Score the entire candidate list jointly, considering relative ordering. Better quality for small k. Use for k ≤ 20 (e.g., RankLLM, RankGPT).
- **Late interaction** (ColBERT): Store per-token embeddings. At query time, compute MaxSim between query tokens and document tokens. Balances speed and quality.

**Performance impact of reranking**:
- Without reranking: Precision@5 ≈ 60-70% (depends on embedding model)
- With reranking (cohere.rerank-v3): Precision@5 ≈ 85-95%
- Cost: Reranking 100 candidates costs ~10-50ms with self-hosted models, ~200ms with API
- **Rule**: Always rerank when context window is limited (e.g., 5-10 chunks). Skip reranking if retrieving 50+ chunks for summarization.

### Advanced Techniques

#### Fusion Retrieval

Combine results from multiple retrieval strategies for higher recall.

```
FusionRetrieval(query, retrievers, k=10):
  all_results = []
  for retriever in retrievers:
    results = retriever.retrieve(query, k=k*2)
    all_results.append(results)
  
  # Reciprocal Rank Fusion (RRF)
  scores = defaultdict(0)
  for results in all_results:
    for rank, doc in enumerate(results):
      scores[doc.id] += 1.0 / (k_fusion + rank)  # k_fusion typically 60
  
  return sorted(scores.keys(), key=lambda id: scores[id], reverse=True)[:k]
```

**Common retriever combinations**:
- Dense (embedding similarity) + Sparse (BM25/SPLADE) for complementary strengths
- Multi-query: retrieve from 3 rephrased versions of the same query + RRF merge
- Multi-index: retrieve from separate indices (code, docs, issues) + merge

#### Parent-Child Chunking

**Problem**: Small chunks are good for precise retrieval but lack context for generation. Large chunks provide rich context but dilute retrieval precision.

**Solution**: Index small "child" chunks for retrieval. At generation time, fetch the parent chunk containing each child.

```
Index time:
  parent_chunks = split(document, chunk_size=2048, overlap=200)
  for parent in parent_chunks:
    child_chunks = split(parent, chunk_size=256, overlap=50)
    for child in child_chunks:
      index.embed(child.text, metadata={parent_id: parent.id, child_index: i})

Query time:
  child_results = index.search(query_embedding, k=10)
  parent_ids = set(r.metadata.parent_id for r in child_results)
  context_chunks = [docstore.get(pid) for pid in parent_ids]
  return context_chunks  # full-size parent chunks for generation
```

#### Sentence Window Retrieval

```
SentenceWindowRetrieval(query, index, docstore, k=10, window=3):
  sentences = index.search(query_embedding, k=k)  # retrieve individual sentences
  context_snippets = []
  for sent in sentences:
    doc = docstore.get(sent.metadata.doc_id)
    sent_idx = sent.metadata.sentence_index
    # Expand: take `window` sentences before and after
    start = max(0, sent_idx - window)
    end = min(len(doc.sentences), sent_idx + window + 1)
    window_text = " ".join(doc.sentences[start:end])
    context_snippets.append(window_text)
  return deduplicate(context_snippets)
```

**Pros**: Very granular retrieval (sentence-level). **Cons**: Higher index cardinality, more storage.

#### Multi-Vector Retrieval

Store multiple embeddings per document chunk (e.g., summary vector + content vector + keyword vector).

```
Index time:
  for chunk in chunks:
    summary_emb = embed(f"Summarize: {chunk.text}")
    keyword_emb = embed(f"Keywords: {extract_keywords(chunk.text)}")
    content_emb = embed(chunk.text)
    index.add(chunk.id, [summary_emb, keyword_emb, content_emb])

Query time:
  query_emb = embed(query)
  # Search against all vector spaces, fuse results
  results = index.multi_vector_search(query_emb, top_k=10)
```

#### Contextual Compression

Use an LLM to compress retrieved documents before generation. Removes irrelevant sentences, keeps only query-relevant content.

```
ContextualCompression(query, docs, compressor_llm):
  compressed = []
  for doc in docs:
    compressed_doc = compressor_llm.compress(
      f"Given the query: {query}\n"
      f"Extract only the sentences relevant to answering the query:\n"
      f"{doc.text}"
    )
    if compressed_doc.strip():
      compressed.append(compressed_doc)
  return compressed
```

**When to use**: Extremely long retrieved documents (2K+ tokens each). **Cost**: Adds N LLM calls (one per retrieved doc). Use a small, fast model (GPT-3.5-turbo or Llama-3-8B).

#### FLARE (Forward-Looking Active REtrieval)

Active retrieval during generation: generate a temporary next sentence, use it as a retrieval query if it contains uncertain tokens, then regenerate with retrieved context.

```
FLARE(query, generator, retriever):
  output_tokens = []
  
  while not done:
    # Generate a temporary next sentence
    temp_sentence = generator.generate_next_sentence(output_tokens)
    
    # Check for low-probability tokens (uncertainty signal)
    if has_low_probability_tokens(temp_sentence):
      # Use the temporary sentence as a retrieval query
      retrieval_query = temp_sentence
      docs = retriever.retrieve(retrieval_query, k=3)
      # Regenerate the sentence with retrieved context
      sentence = generator.generate_next_sentence(output_tokens, docs)
    else:
      sentence = temp_sentence
    
    output_tokens.append(sentence)
  
  return output_tokens
```

**When FLARE shines**: Long-form generation (articles, reports, tutorials) where different sections need different knowledge. Retrieval happens naturally at knowledge boundaries.

### Evaluation

#### RAGAS Framework

RAGAS (RAG Assessment) evaluates RAG pipelines across three dimensions:

```
┌─────────────────────────────────────────────────────┐
│                   RAGAS Evaluation                    │
│                                                       │
│  ┌─────────────┐   ┌─────────────┐   ┌────────────┐  │
│  │  Generation  │   │  Retrieval  │   │   End-to-  │  │
│  │   Quality    │   │   Quality   │   │    End     │  │
│  └──────┬──────┘   └──────┬──────┘   └──────┬─────┘  │
│         │                 │                 │         │
│    ┌────┴────┐       ┌────┴────┐       ┌───┴───┐    │
│    │Faithful-│       │ Context │       │Answer │    │
│    │ness     │       │Precision│       │Relev. │    │
│    └─────────┘       └─────────┘       └───────┘    │
│                      ┌─────────┐                     │
│                      │ Context │                     │
│                      │ Recall  │                     │
│                      └─────────┘                     │
└─────────────────────────────────────────────────────┘
```

**Metrics defined**:
- **Faithfulness** (0-1): Claims in the answer that can be inferred from context / total claims. Detects hallucination.
- **Answer Relevance** (0-1): How well the answer addresses the query. Uses reverse-generation: generate questions from answer, compare similarity to original query.
- **Context Precision** (0-1): Percentage of retrieved chunks that are relevant. `|relevant_chunks| / |retrieved_chunks|`. Penalizes noise.
- **Context Recall** (0-1): Percentage of ground-truth-relevant chunks that were retrieved. `|retrieved_relevant| / |total_relevant|`. Penalizes missing info.
- **Answer Correctness** (0-1): Factual accuracy against ground truth (requires reference answer).

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

results = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall]
)
# results = {'faithfulness': 0.89, 'answer_relevancy': 0.92, ...}
```

#### Traditional IR Metrics

| Metric | Formula | What It Measures | Best For |
|--------|---------|-----------------|----------|
| **NDCG@k** | DCG / IDCG, where DCG = Σ(rel_i / log2(i+1)) | Position-weighted relevance; higher-ranked relevant docs score more | Ranking quality, reranking comparison |
| **MRR** | 1 / rank of first relevant doc, averaged | How quickly you find a relevant document | FAQ-style, single-answer QA |
| **Hit Rate@k** | Avg(any relevant in top-k) | Does at least one relevant doc appear in top-k? | Binary relevance, coarse filter |
| **Recall@k** | Relevant retrieved / Total relevant | Coverage of all relevant docs in top-k | Exhaustive retrieval, summarization |
| **Precision@k** | Relevant in top-k / k | Density of relevant docs in top-k | Precision-critical, limited context window |

#### Benchmarking Methodology

1. **Build evaluation dataset**: 100-500 query-document pairs with relevance judgments (binary or graded)
2. **Annotate**: Human annotators or LLM-as-judge (GPT-4) for relevance labeling. LLM-as-judge correlates 0.85+ with human judgments for RAG evaluation
3. **Run pipeline**: For each query, retrieve + generate. Store all intermediate results (retrieved docs, scores, generated answer)
4. **Compute metrics on retrieval** (NDCG, MRR, Hit Rate) BEFORE computing generation metrics (faithfulness, relevance)
5. **Regression testing**: Re-run evaluation on every pipeline change. Store metric history. Alert on >5% degradation.

### Production RAG

#### Indexing Pipeline

```
Source Documents
      │
      ▼
Ingestion (S3/GCS/Local) → Format Detection (PDF parser, HTML stripper, OCR for images)
      │
      ▼
Document Processing → Clean → Normalize → Extract metadata (title, author, date)
      │
      ▼
Chunking (semantic + recursive) → Enrich with metadata → Assign chunk IDs
      │
      ▼
Embedding (batch, async, with retry) → Upsert to vector store (with IDs, metadata)
      │
      ▼
Post-index hooks → Validate (spot-check 1% of embeddings) → Update docstore with full text
```

**Parallelization**: Use a task queue (Celery/BullMQ) for chunking + embedding. Batch embed 100 chunks per API call. Process documents in parallel (one worker per document).

#### Incremental Updates

- **New documents**: Ingest → Chunk → Embed → Upsert (with new chunk IDs)
- **Modified documents**: Soft-delete old chunks (mark `is_active: false`) → Ingest new version → Upsert with new IDs
- **Deleted documents**: Soft-delete all chunks → Async cleanup job removes inactive chunks weekly
- **Model rotation**: When switching embedding models, create a new index/collection. Run A/B testing before switchover. Old index serves as fallback.

#### Monitoring and Observability

```
Production RAG Metrics Dashboard:
┌───────────────────────────────────────────────────────┐
│  Retrieval Health          Generation Health           │
│  ────────────────          ────────────────            │
│  • P50/P95 query latency   • P50/P95 generation time   │
│  • Embedding API error %   • LLM API error rate        │
│  • Vector store QPS        • Tokens generated/sec      │
│  • Index size (vectors)    • Avg tokens per request     │
│  • Reindex progress %      • Hallucination rate         │
│                                                         │
│  Quality Metrics (sampled)                              │
│  ────────────────                                       │
│  • Faithfulness score (weekly sample of 1000)           │
│  • Answer relevance score                               │
│  • User feedback score (thumbs up/down)                 │
│  • Retrieval precision@5 (golden set)                   │
└───────────────────────────────────────────────────────┘
```

**Alerting rules**:
- Embedding API error rate > 1% → page
- Vector store p95 latency > 500ms → warn
- Faithfulness score drops > 10% from baseline → investigate
- Indexing pipeline stalled > 2 hours → page

#### Cost Optimization

| Strategy | Savings | Tradeoff |
|----------|---------|----------|
| Embedding cache (Redis) | 30-60% on repeat queries | Cache invalidation on index update |
| Smaller embedding dimension (Matryoshka) | 25-50% storage + faster search | ~2-4% recall drop at 256-dim |
| Quantization (scalar/int8) | 50-75% storage | 1-3% recall drop |
| Semantic caching for full responses | 40-70% on repeat queries | Staleness for time-sensitive answers |
| Smaller reranker (bge-reranker-base vs large) | 50% latency reduction | 2-5% ranking quality drop |
| Hybrid search (BM25 as primary, vector as fallback) | Lower embedding API costs | Setup complexity |

#### Embedding Caching Strategies

```python
# Cache key = hash(query_text + model_name)
import hashlib
import json
from functools import lru_cache

def embed_with_cache(text: str, model: str, cache: redis.Redis) -> list[float]:
    cache_key = f"emb:{model}:{hashlib.sha256(text.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)
    embedding = embed(text, model=model)
    cache.setex(cache_key, 3600, json.dumps(embedding))  # 1 hour TTL
    return embedding
```

**Cache invalidation**: Flush cache on embedding model change. Use versioned cache keys (`emb:v2:model:hash`) to avoid stale entries.

### Anti-Patterns

| Anti-Pattern | Example | Why It Fails | Fix |
|---|---|---|---|
| **Single chunk size for all documents** | Using 512-token chunks for both code snippets and long-form articles | Code needs 128-256 tokens for precision; articles need 512-1024 for context | Use document-type-aware chunking: different sizes per content type |
| **No evaluation pipeline** | "It looks good" after manual testing | Undetected regressions accumulate silently | Run RAGAS evaluation on a golden dataset before every deployment |
| **Ignoring metadata filtering** | Searching entire vector store for "latest Q4 report" when Q4 filter would eliminate 95% of vectors | Noise dominates relevance; top-10 results are all from wrong quarters | Always apply metadata filters BEFORE vector search; pre-filter aggressively |
| **No reranker** | k=20 retrieved chunks stuffed into context window | Context dilution: important docs buried under marginally relevant ones | Two-stage retrieval: retrieve 50 → rerank to top-10 → generate |
| **Embedding model without instruction prefix** | `embed("climate change")` vs `embed("Represent this query for retrieval: climate change")` | 5-15% recall loss on instruction-tuned models (bge, e5, instructor) | Always prepend the model's expected instruction prefix |
| **Same index for all content types** | Mixing code, docs, issues, and chat logs in one index | Semantic space is polluted; legal docs pollute code searches and vice versa | Separate indices per content type; route queries to appropriate index |
| **Chunking without overlap** | `split(text, chunk_size=512, overlap=0)` | Sentences split mid-thought; context lost at chunk boundaries | Minimum 10% overlap (50-100 tokens) between consecutive chunks |
| **Full document embedding** | Embedding entire 50-page PDF as one vector | "Needle in a haystack": relevant paragraph drowned by 49 pages of noise | Chunk documents to 256-1024 tokens. Never embed a full document. |
| **Embedding documents and queries with different models** | BGE for documents, OpenAI for queries | Different embedding spaces; cosine similarity is meaningless | Always use the same model (or a compatible pair) for both queries and documents |
| **Neglecting formatting in chunk text** | Stripping markdown, code fences, and tables during chunking | LLM receives unstructured wall of text; loses table alignment, code syntax, heading hierarchy | Preserve markdown formatting in chunks. For tables, convert to text or keep as HTML. |
| **Hot index updates during peak traffic** | Updating the vector index while serving queries | Index rebuilds cause latency spikes; partial updates cause inconsistent results | Schedule reindexing during low-traffic windows. Use blue-green index deployment. |
| **No hybrid search** | Pure embedding similarity for exact-match queries (IDs, error codes, version numbers) | Embedding similarity fails on exact matches; "ERR-4321" matches "ERR-1234" better than "ERR-4321" | Add BM25/sparse retrieval + RRF fusion for queries containing code, IDs, or numeric values |

### Cross-Skill Integration Patterns

**With ai-agent-loop** — RAG is the retrieval engine that agents use:
- Define a `retrieve(query)` tool that wraps your RAG pipeline; agents call it via ReAct
- Agentic RAG (Section: Agentic RAG) = ReAct loop + RAG tool + query decomposition
- Self-RAG's retrieval decision tokens are equivalent to the agent's Thought step: "Do I need to retrieve, or can I answer from parametric knowledge?"
- For multi-step complex queries, use Plan-and-Execute with RAG: plan includes retrieval steps, execute runs them sequentially

**With ai-memory** — RAG and Memory share infrastructure but serve different roles:
- RAG: external, static, domain knowledge (documentation, knowledge bases)
- Semantic Memory: internal, dynamic, personal knowledge (past interactions, learned facts)
- Both use vector stores for similarity search — consider a shared vector store with different namespaces/collections
- When RAG retrieves external content, cache it in semantic memory for faster future lookups (with TTL for freshness)
- The chunking and embedding strategies (ai-memory Section 2) apply to RAG document ingestion

**With database-postgres** — Production RAG uses PostgreSQL for vector search:
- pgvector for embeddings (database-postgres Section 3, pgvector)
- BRIN indexes on document metadata timestamps for efficient time-range filtering
- Connection pooling via PgBouncer (database-postgres Section 5) for high-throughput retrieval
- Table partitioning by document source for efficient index management

**With security-audit** — RAG systems have unique security considerations:
- OWASP Top 10 #3 (Injection): Malicious documents in the corpus can inject into prompts. Validate all ingested documents
- Access control: Document-level ACLs enforced at retrieval time via metadata filtering
- PII handling: Redact PII from retrieved content before passing to the LLM
- Data exfiltration: Monitor what retrieved content is returned to users

**With infra-observability** — Every RAG pipeline component must emit telemetry:
- Ingestion pipeline: documents processed, chunks created, embedding latency
- Retrieval: query latency P50/P99, recall@10, MRR
- Generation: faithfulness score, answer relevance, token usage
- OpenTelemetry spans: one span per RAG query, child spans for retrieval, reranking, generation
- RAGAS evaluation metrics (Section: Evaluation) should be exported as Prometheus metrics and tracked over time

**Skill loading order**: `understanding` → `ai-rag` → `database-postgres` (for pgvector) → `ai-agent-loop` (for Agentic RAG) → `ai-memory` (for caching retrieved content) → `security-audit` (for production hardening)

---

### Implementation Checklist

**Design Phase**:
- [ ] Chunking strategy selected (doc-type-aware, semantic preferred)
- [ ] Embedding model chosen (multilingual if needed, instruction-tuned preferred)
- [ ] Vector store provisioned (pgvector for Postgres shops, Qdrant for filtering-heavy workloads)
- [ ] Metadata schema designed (source, page, heading hierarchy, content type, timestamps)
- [ ] Reranker selected (cohere.rerank-v3 for API, bge-reranker-v2 for self-hosted)
- [ ] Evaluation dataset created (100+ query-document pairs with relevance judgments)

**Indexing Phase**:
- [ ] Document ingestion pipeline built (parsers, cleaners, metadata extractors)
- [ ] Chunking implemented with overlap and metadata enrichment
- [ ] Embedding batch pipeline built (with retry logic, error handling)
- [ ] Incremental update strategy defined (new/modified/deleted document handling)
- [ ] Embedding cache implemented (Redis, with versioned keys)
- [ ] Blue-green index deployment for reindexing
- [ ] Index validation: spot-check 1% of embeddings for correctness

**Query Phase**:
- [ ] Embedding model instruction prefix configured
- [ ] Metadata pre-filtering applied before vector search
- [ ] Two-stage retrieval pipeline: candidate retrieval (k=50) → reranking (k=10)
- [ ] Fallback chain implemented: local index → broad index → web search → refusal
- [ ] HyDE or query rephrasing for short/ambiguous queries
- [ ] Contextual compression for long retrieved documents (optional)
- [ ] Response generation with proper citation of sources

**Evaluation & Monitoring**:
- [ ] RAGAS evaluation pipeline running on golden dataset
- [ ] NDCG@5, MRR, Hit Rate@10 tracked per evaluation run
- [ ] Faithfulness and answer relevance monitored in production (sampled)
- [ ] Retrieval latency (P50, P95, P99) monitored
- [ ] Embedding API error rate and vector store QPS tracked
- [ ] User feedback collected (thumbs up/down, optional free-text)
- [ ] Regression alerts: notify on >5% metric degradation

**Optimization**:
- [ ] Hybrid search (dense + sparse) evaluated and enabled if beneficial
- [ ] Fusion retrieval (multi-query + RRF) evaluated for complex queries
- [ ] Embedding dimension reduced via Matryoshka (if using OpenAI) and benchmarked
- [ ] Vector quantization evaluated (scalar/int8) with recall impact measured
- [ ] Semantic response cache for high-frequency queries (with TTL)
- [ ] Cost per query calculated and optimized
