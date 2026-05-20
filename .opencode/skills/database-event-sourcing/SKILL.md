---
name: database-event-sourcing
description: Event Sourcing + CQRS + CRDT patterns: append-only event stores, read/write separation, eventual consistency, conflict-free resolution, event-driven architecture, event store implementations, testing strategies, and production patterns
license: MIT
compatibility: opencode
metadata:
  audience: backend-developers
  domain: database
  paradigm: event-driven
  capabilities:
    - event-sourcing
    - cqrs
    - crdt
    - event-driven-architecture
    - outbox-pattern
    - event-store-design
    - schema-evolution
    - read-model-projection
    - eventual-consistency
    - event-testing
  integrates_with:
    - database-postgres
    - backend-go
    - backend-python
    - backend-elixir
    - infra-observability
    - paradigm-functional
    - workflow-general
---

## Database Event Sourcing + CQRS + CRDT Skill

---

### 1. Event Sourcing Fundamentals

#### Events as Immutable Facts

Events are the single source of truth. They record what happened, not what should happen.

```
Event Schema:
  eventId:        UUIDv7           // globally unique, time-sortable
  eventType:      string           // "OrderPlaced", past-tense verbs only
  aggregateType:  string           // "Order", "Account"
  aggregateId:    string           // identifies the entity
  version:        integer          // monotonic within aggregate
  timestamp:      datetime (UTC)   // when the event occurred
  causationId:    UUID | null      // links to the command that caused this event
  correlationId:  UUID | null      // links related events across aggregates
  userId:         string | null    // who triggered the change
  payload:        JSON             // the event data (immutable, self-contained)
  metadata:       JSON             // tracing, IP, user-agent, etc.
```

**Rules**: Events are facts — never delete, update, or reinterpret. Payloads are complete — all data needed to rebuild state must be in the event. Event types use past-tense verbs (`OrderPlaced`, not `PlaceOrder`).

#### Append-Only Store & Concurrency

```sql
CREATE TABLE events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type  VARCHAR(100) NOT NULL,
    aggregate_id    VARCHAR(100) NOT NULL,
    version         INTEGER      NOT NULL,
    event_type      VARCHAR(200) NOT NULL,
    payload         JSONB        NOT NULL,
    metadata        JSONB        DEFAULT '{}',
    causation_id    UUID,
    correlation_id  UUID,
    occurred_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    recorded_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_aggregate_version UNIQUE (aggregate_type, aggregate_id, version)
);
CREATE INDEX idx_events_agg ON events (aggregate_type, aggregate_id, version);
CREATE INDEX idx_events_correlation ON events (correlation_id) WHERE correlation_id IS NOT NULL;
```

**Atomic append with optimistic concurrency**:
```sql
INSERT INTO events (...) VALUES (...)
ON CONFLICT (aggregate_type, aggregate_id, version) DO NOTHING
RETURNING event_id;
-- If empty return: version conflict → reload aggregate, retry with next_version + 1
```

For pessimistic locking (rarely needed): `pg_advisory_xact_lock(hashtext(aggregate_type || aggregate_id))`.

**Guarantees**: Full audit trail (every state change, who/what/when), time-travel debugging, no data loss (soft deletes via tombstone events), reproducibility (same events → same state).

#### Idempotency

Processing the same command twice must produce the same result — critical for at-least-once delivery.

| Strategy | Implementation |
|----------|---------------|
| **Idempotency key on command** | Client generates UUID; server stores (key, result) mapping; replay returns cached result |
| **Event-level deduplication** | event_id as PK → `INSERT ON CONFLICT DO NOTHING` |
| **Handler-level idempotency** | Projectors track `last_processed_event_id` atomically; skip already-processed events |

```sql
CREATE TABLE projector_checkpoints (
    projector_name  VARCHAR(200) PRIMARY KEY,
    last_event_id   UUID        NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Poll: SELECT * FROM events WHERE event_id > (SELECT last_event_id FROM ...) ORDER BY event_id LIMIT 100;
```

#### Rebuilding State & Snapshots

```
fold :: [Event] -> InitialState -> CurrentState

function load(aggregateType, aggregateId):
    events = SELECT * FROM events WHERE aggregate_type=$t AND aggregate_id=$id ORDER BY version
    aggregate = empty()
    for e in events: aggregate = aggregate.apply(e)
    return aggregate
```

`apply(event)` must be a pure function — same input always produces same output.

```
SNAPSHOT TABLE: aggregate_type, aggregate_id, version (last event included), state (JSONB), created_at
PRIMARY KEY (aggregate_type, aggregate_id)

REBUILD: load snapshot → load events WHERE version > snapshot.version → apply delta events

SNAPSHOT STRATEGIES:
  - Every N events (e.g., every 100) — simple, predictable
  - On significant state transitions (status changes)
  - Time-based (hourly/daily) for write-heavy aggregates
  - Lazy: snapshot on load if events-since-snapshot exceeds threshold
```

Snapshots are derived data — they can be deleted and rebuilt from events at any time.

---

### 2. CQRS (Command Query Responsibility Segregation)

```
┌──────────┐     ┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│  COMMAND │────▶│ AGGREGATE│────▶│ EVENT STORE  │────▶│  PROJECTOR   │────▶│ QUERY DB │
│  (Write) │     │ validate │     │  (Append)    │     │  (read model)│     │  (Read)  │
└──────────┘     └──────────┘     └──────────────┘     └──────────────┘     └──────────┘
```

#### Command Side

Commands are intent (may be rejected). Events are facts (always accepted).

```
COMMAND SCHEMA: { commandId: UUID, commandType, aggregateId, payload, userId, timestamp }

COMMAND HANDLER pseudocode:
  function handle(cmd):
    if alreadyProcessed(cmd.commandId): return cachedResult     // idempotency
    aggregate = load(cmd.aggregateType, cmd.aggregateId)
    events = aggregate.process(cmd)                             // pure business logic
    appendToStore(events, expectedVersion=aggregate.version)    // atomic, concurrency check
    cacheResult(cmd.commandId, events)
    return events
```

**Rules**: Business rules live in the aggregate, not the handler. Command handlers are thin orchestrators. Commands can be rejected; events cannot.

#### Query Side (Read Model Projection)

Read models are denormalized projections optimized for specific queries.

```
PROJECTOR pseudocode:
  function handle(event):
    match event.type:
      "OrderPlaced":     db.insert(order_summaries, {order_id, status:"placed", total, ...})
      "PaymentCaptured": db.update(order_summaries, SET status="paid" WHERE order_id=...)
      "OrderShipped":    db.update(order_summaries, SET status="shipped", tracking_id=...)
```

**Denormalization choices**:
| Pattern | Use When | Example |
|---------|----------|---------|
| 1:1 event-to-row | Simple projections | Each OrderPlaced → one row |
| Aggregated views | Analytics, dashboards | count(*) GROUP BY status |
| Search indexes | Free-text search | Project to Elasticsearch |
| Cached values | Frequently-read | Redis hash of preferences |
| Nested documents | Complex reads | MongoDB with embedded line items |

#### Synchronization

```
OUTBOX PATTERN (recommended):
  Events + outbox row in same DB transaction → atomicity guarantee
  Poller reads pending outbox rows → publishes to message broker → marks published

  outbox table: event_id, topic, status(pending|published|failed), retries, last_error, created_at
  INDEX on (status, created_at) WHERE status = 'pending'

CDC ALTERNATIVE:
  Debezium tails PostgreSQL WAL → emits to Kafka directly, no outbox table needed
  Pro: cleaner schema. Con: more infrastructure.

NATIVE: EventStoreDB subscriptions — built-in, no external broker needed.
```

#### Consistency Models

| Model | Implementation |
|-------|---------------|
| **Eventual** (default) | Read model eventually reflects writes |
| **Read-your-writes** | Command returns `{orderId, version:5}`; client sends `If-Version: >=5` on GET; query side waits or warns |
| **Monotonic reads** | Reads never go backward; server tracks client's last-seen version |
| **Strong** | Read from command-side DB — defeats CQRS purpose, use sparingly |

---

### 3. CRDT (Conflict-Free Replicated Data Types)

CRDTs enable multi-writer without coordination. Merge is commutative, associative, idempotent.

| Type | Data Structure | Operations | Value | Merge | Use Case |
|------|---------------|------------|-------|-------|----------|
| **G-Counter** | `Map<ReplicaId, int>` | `inc()` per replica | `sum(all)` | `max(a[i], b[i])` per replica | Like counts, view counts |
| **PN-Counter** | P: G-Counter, N: G-Counter | `inc()` on P, `dec()` on N | `P - N` | Merge P and N independently | Inventory, upvote/downvote |
| **G-Set** | Set of elements | `add(e)` only | all elements | `a ∪ b` | Tags, "seen" sets |
| **2P-Set** | A: G-Set (added), R: G-Set (removed) | `add(e)`, `remove(e)` only if in A | `e ∈ A ∧ e ∉ R` | Merge A and R independently | One-time remove (cannot re-add) |
| **OR-Set** | `Map<element, Set<tag>>` | `add(e)` generates unique tag; `remove(e)` clears tags | element with non-empty tags | Union tags minus union tombstones | Playlists, shopping carts (re-add OK) |
| **LWW-Register** | `{value, timestamp}` | Set if incoming timestamp > current | stored value | Keep entry with higher timestamp | Preferences, cache (accepts data loss) |
| **CRDT Map** | `Map<String, CRDT>` | Mutate inner CRDTs at keys | per-key values | Recursively merge inner CRDTs | Collaborative docs, shared forms |

**PN-Counter example**: Replica A: P={A:5}, N={A:2} → value=3. Replica B: P={A:3}, N={A:1} → value=2. Merge: P={A:5}, N={A:2} → value=3.

**OR-Set key insight**: Each `add("item")` generates a unique tag. `remove("item")` only removes currently known tags. Re-adding generates new tags — not blocked by prior removal.

**Conflict resolution strategies**: CRDT auto-merge (for commutative ops), LWW (when data loss acceptable), MWW/Multi-Value Register (preserve all conflicts for app resolution), Operational Transformation (real-time collaborative editing), Custom merge functions (domain-specific logic).

---

### 4. Event-Driven Architecture

#### Event Bus Selection

| Bus | Ordering | Throughput | Retention | Best For |
|-----|----------|------------|-----------|----------|
| **Kafka** | Per-partition strict | 1M+ msg/s | Days-years | Event sourcing backbone, replay, durability |
| **NATS JetStream** | Per-subject | High | Configurable | Lightweight pub/sub, low latency |
| **Redis Streams** | Per-stream | High | Configurable | Simple deployments, already using Redis |
| **AWS SQS+SNS** | FIFO: per-group | High | 14 days max | AWS-native architectures |
| **RabbitMQ** | Per-queue | Medium | Ack only | Traditional message queuing |

**Kafka partition strategy**: Key = `aggregateType:aggregateId` → all events for one aggregate go to same partition → strict ordering per aggregate → consumer group distributes partitions.

#### Outbox Pattern (Detailed)

```sql
CREATE TABLE outbox (
    id           BIGSERIAL PRIMARY KEY,
    event_id     UUID NOT NULL REFERENCES events(event_id),
    event_type   VARCHAR(200) NOT NULL,
    payload      JSONB NOT NULL,
    topic        VARCHAR(200) NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'pending',
    retries      INTEGER NOT NULL DEFAULT 0,
    last_error   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_outbox_status ON outbox (status, created_at) WHERE status = 'pending';
```

**Poller (pseudocode)**: Loop every 100ms → `SELECT * FROM outbox WHERE status='pending' ORDER BY created_at LIMIT 100` → publish each to broker → on success: `UPDATE SET status='published'` → on failure: increment retries, set last_error → if retries > max: `SET status='failed'` → DLQ.

#### Dead Letter Queue & Schema Evolution

**DLQ**: `dlq_id, original_event(JSONB), error_message, stack_trace, handler_name, retry_count, status(pending_review|resolved|ignored)`. Retry strategy: immediate → exponential backoff (1s, 2s, 4s, 8s...) → after max retries → DLQ. Replay from DLQ by republishing to outbox after fixing root cause.

**Schema evolution rules**: NEVER remove fields (add with defaults). NEVER change field types (create new field). NEVER rename fields (add new name alongside old). Upcast on READ, never rewrite stored events. Chain upcasters: V1→V2→V3. Add upcaster BEFORE deploying new schema consumers.

```
Upcaster pseudocode:
  function upcast(event):
    while (event.type, event.version) in registry:
      event = registry[(event.type, event.version)].upcast(event)
    return event
```

Use Avro/Protobuf with Confluent or Apicurio schema registry. Validate on write AND read.

---

### 5. Event Store Implementations

```sql
-- PostgreSQL Event Store (full table design above in Section 1)

-- Snapshots table
CREATE TABLE snapshots (
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id   VARCHAR(100) NOT NULL,
    version        INTEGER      NOT NULL,
    state          JSONB        NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (aggregate_type, aggregate_id)
);
```

| Decision | Postgres | EventStoreDB | Custom |
|----------|----------|--------------|--------|
| **Setup effort** | Low — already in stack | Medium — new tool | High — build from scratch |
| **Query events** | SQL | Stream API (`$all` stream) | Custom |
| **Replay speed** | Medium | Fast (purpose-built) | Variable |
| **Snapshots** | Manual | Built-in | Manual |
| **Projections** | Manual | Built-in JavaScript | Manual |
| **Operations** | Familiar tooling | New operational knowledge | Fully DIY |

**Postgres**: Best when you already run Postgres, need strong consistency, and have < 100M events. Use table partitioning by time for large event volumes.

**EventStoreDB**: Purpose-built — streams, catch-up subscriptions (client-tracked), persistent subscriptions (server-tracked, shareable across consumers), built-in projections. Best for heavy event sourcing where you want operational simplicity over SQL flexibility.

---

### 6. Testing Event-Sourced Systems

#### Testing Aggregates (Given/When/Then)

Tests are purely in-memory — no real I/O.

```
TEST: PlaceOrder with sufficient inventory
  GIVEN:  [InventoryItemCreated(itemId="SKU-1", qty=100)]
          → aggregate.state = {qty:100, reserved:0}
  WHEN:   command = ReserveInventory(itemId="SKU-1", qty=3)
          events = inventory.process(command)
  THEN:   events == [InventoryReserved(itemId="SKU-1", qty=3)]
          no exception thrown

TEST: PlaceOrder with insufficient inventory
  GIVEN:  [InventoryItemCreated(itemId="SKU-1", qty=2)]
  WHEN:   command = ReserveInventory(itemId="SKU-1", qty=5)
  THEN:   throws InsufficientInventoryError, no events emitted
```

**Rules**: Given = historical events → rebuild state. When = process command → capture events/error. Then = assert events match expected or error matches expected. Cover happy path, all edge cases, and all error states.

#### Testing Projections & Event Handlers

```
PROJECTION TEST:
  GIVEN:  events = [OrderPlaced(orderId="1", total=50), PaymentCaptured(orderId="1")]
  WHEN:   projector = OrderSummaryProjector(testDB)
          for e in events: projector.handle(e)
  THEN:   row = testDB.query("SELECT * FROM order_summaries WHERE order_id='1'")
          assert row.status == "paid" AND row.total == 50

HANDLER IDEMPOTENCY TEST:
  GIVEN:  event = OrderPlaced(orderId="1"), handler already processed it
  WHEN:   handler.handle(event)  // second call
  THEN:   assert emailService.sendEmail was called exactly once
```

**Projection test checklist**: Handles ALL event types (no silent ignores), idempotent (same event twice = same result), handles out-of-order events (where possible), correctly uses checkpointing.

**Snapshot testing**: `assert event.to_dict() == stored_snapshot` — fails if event schema changes. Golden-file testing for full event streams.

---

### 7. Production Patterns

#### Event Versioning & Upcasting

Upcasting middleware runs on READ. Never rewrites stored events. Chain upcasters (V1→V2→V3). Tests must cover every upcasting path. Deploy upcaster BEFORE deploying consumers expecting the new schema.

#### Rebuilding Read Models

```
FULL REBUILD: Create new table (v2) → deploy projector writing to v2 → replay ALL events → switch reads to v2 → drop old table.

INCREMENTAL (from checkpoint): Detect gap (projection_version < latest_event_version) → load events from version+1 to latest → apply → update checkpoint.

TRIGGERS: New projection added, projection bug fix, schema change in read model, corruption detected.
```

#### Resharding & Archiving

**When to reshard**: Hot aggregates (single aggregateId getting most writes), tenant isolation, storage limits.

**Strategy**: Create new partitions → route new events to correct partition → old events stay (or migrate in background) → subscribers consume from both → optionally archive old partition. **Mitigation**: Design aggregates to be small (single entity), avoid "god aggregates."

**Archiving cold events**: Archive events older than N months to Parquet files on S3 (partitioned by aggregate_type/year=/month=). Keep snapshot at archive boundary. Delete from hot store after verification. Restore rarely — only for compliance audits.

---

### 8. Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| **Events as CRUD wrappers** | `UserUpdated` says nothing about WHY. Loses business intent. | `UserChangedEmail`, `UserUpgradedPlan` — model business actions |
| **Giant events** | Entire order with 1000 line items in one event. Expensive to replay, hard to evolve. | Granular: `OrderPlaced`, `LineItemAdded`, `LineItemRemoved` |
| **Missing aggregate boundaries** | `ShoppingCartFullUpdate` carries entire cart — no history, just snapshots-as-events | Each add/remove is its own event. State is derived, not stored. |
| **Mixing events and commands** | `ReserveInventory` as event — what if it fails? Past tense for events, imperative for commands. | Event: `InventoryReserved`. Command: `ReserveInventory`. |
| **No schema registry** | JSON blobs without versioning. Consumers break on field addition. | Avro/Protobuf + schema registry. Embed version in metadata. |
| **Reading from write DB** | Querying event stream directly. Replays full stream every time. | Build dedicated read models. Streams are for writes, not queries. |
| **Synchronous event handlers** | Projection calls external API inside handler. Downstream outage stalls projection. | Handlers update read models only. Side effects in separate async handlers. |
| **No idempotency** | `if (!exists) { create() }` without key. Duplicate event → duplicate row. | Always check event_id or `INSERT ON CONFLICT DO NOTHING`. |
| **Ignoring eventual consistency** | POST /orders then immediate GET /orders/{id} expecting latest status. | Return version from POST. Accept If-Version on GET. |
| **Snapshots as source of truth** | Restoring from snapshot without event replay. Events are primary. | Events are truth. Snapshots are a performance optimization. Always rebuildable. |
| **Version number gaps** | Versions 1, 2, 5 — consumers assume contiguity. | Always use contiguous versions. Record explicit gap markers if unavoidable. |

---

### 9. Implementation Checklist

**Foundation**: Event schema defined (eventId, aggregateType/Id, version, eventType, payload, metadata), event store table with unique constraint on aggregate version, past-tense business-meaningful event names, self-contained payloads.

**Command Side**: Idempotency keys on commands, pure aggregate validate+emit functions, optimistic concurrency via version check, command handler returns version for read-your-writes, all business rules tested via Given/When/Then.

**Query Side**: Projections from events (never from command DB), idempotent projectors (upsert/ON CONFLICT), checkpointed processing, read models rebuildable from scratch, If-Version/ETag support on query API.

**Integration**: Outbox pattern (events + outbox row in same TX), outbox poller with configurable interval, message broker publication (Kafka/NATS), DLQ with retry + alerting, schema registry in place.

**Production Readiness**: Snapshots configured, upcasting middleware for schema evolution, documented+tested read model rebuild, cold event archiving, observability (event processing lag, DLQ depth), alerts (DLQ>0, lag>5min, outbox pending>1000), runbooks for rebuild/replay/migration.

**Testing**: Aggregate tests (Given/When/Then), projection tests, handler idempotency tests, schema evolution tests (old event→upcast→new consumer), full end-to-end integration test.

---

### 10. When to Use vs Not Use

#### Use Event Sourcing When:

| Signal | Why |
|--------|-----|
| Full audit trail required | Finance, healthcare, compliance — every change must be traceable |
| Complex business processes | Order management, claims, workflows — where WHY matters |
| Multiple read models needed | Same data viewed differently by different consumers |
| Temporal queries | "What was the balance on Jan 15?" — replay events to that point |
| Debugging/provenance | Time-travel to reconstruct exactly what happened and when |
| Collaboration/multi-writer | CRDTs enable offline-capable, multi-device sync |
| Event-driven integration | Other systems react to business events in real-time |
| Regulatory retention | Events preserved for years (legal, SOX, GDPR) |

#### Do NOT Use Event Sourcing When:

| Signal | Why |
|--------|-----|
| Simple CRUD | Forms, config, content management — no business logic to capture |
| No audit requirement | Nobody will ask "what changed and why?" — events add complexity without value |
| Strong consistency required | Stale reads unacceptable and eventual consistency cannot be tolerated |
| Low throughput | A blog with 100 visitors/day doesn't need Kafka + projections |
| Team unfamiliarity | Steep learning curve; without buy-in, it will be misused |
| Short-lived data | Ephemeral state (cache, sessions, rate-limit counters) |
| Frequent schema changes | Event versioning is painful with rapidly evolving models |

#### Hybrid Approach

Apply event sourcing in specific bounded contexts, not everywhere. Example: Orders (event sourced for audit trail) + Products (CRUD) + Analytics (event sourced for real-time projections). Start small with one aggregate where audit matters. Expand as the team gains experience.
