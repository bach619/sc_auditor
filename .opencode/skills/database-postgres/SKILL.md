---
name: database-postgres
description: PostgreSQL (Advanced): indexing (B-tree, GiST, GIN, BRIN), query optimization, partitioning, window functions, CTEs, extensions (pgvector, PostGIS, pg_stat_statements), replication, PgBouncer, performance tuning, security, backup/recovery, and zero-downtime migrations
license: MIT
compatibility: opencode
metadata:
  audience: backend-developers
  domain: database
  paradigm: relational
  capabilities:
    - index-strategy
    - query-optimization
    - partitioning
    - window-functions
    - cte-recursive
    - jsonb-operations
    - full-text-search
    - vector-search
    - spatial-queries
    - replication-ha
    - connection-pooling
    - performance-tuning
    - row-level-security
    - backup-recovery
    - zero-downtime-migrations
  integrates_with:
    - backend-python
    - backend-go
    - backend-elixir
    - database-event-sourcing
    - infra-observability
---

## Database PostgreSQL Skill

---

### 1. Indexing Strategy

#### B-tree (Default Index Type)

B-tree is the default and most versatile index. Use it for equality and range lookups.

**Supported operators**: `<`, `<=`, `=`, `>=`, `>`, `BETWEEN`, `IN`, `IS NULL`, `LIKE 'prefix%'`

**Not used for**: `LIKE '%suffix'`, `LIKE '%middle%'` (no left-anchored prefix), regex without anchor.

```sql
-- Standard B-tree
CREATE INDEX idx_users_email ON users (email);

-- Multi-column: column order is CRITICAL
-- Good for: WHERE a = ? AND b = ?   (uses both columns)
-- Good for: WHERE a = ?             (uses leading column)
-- Bad  for: WHERE b = ?             (cannot skip leading column)
CREATE INDEX idx_orders_user_status ON orders (user_id, status);

-- Partial index: index only a subset of rows
CREATE INDEX idx_active_subscriptions ON subscriptions (user_id)
    WHERE status = 'active';

-- Covering index (INCLUDE): enables index-only scans
-- Key columns used for filtering; INCLUDE columns returned in result
CREATE INDEX idx_users_email_name ON users (email)
    INCLUDE (name, avatar_url);

-- Descending sort on newer data
CREATE INDEX idx_events_ts_desc ON events (created_at DESC);

-- Unique partial index: enforce uniqueness only for non-null / active rows
CREATE UNIQUE INDEX idx_users_active_email ON users (email)
    WHERE deleted_at IS NULL;
```

**Column ordering rules**:
1. Equality conditions first (`=`, `IN`)
2. Range / sort conditions next (`>`, `BETWEEN`, `ORDER BY`)
3. Highest selectivity columns before low-selectivity (e.g., `status` field)

**Fillfactor**: Reserve space in index pages for future updates (reduces page splits). Default is 90. Lower to 70-80 for heavily updated tables.

```sql
CREATE INDEX idx_events_ts ON events (created_at) WITH (fillfactor = 70);
```

#### GIN (Generalized Inverted Index)

Best for composite types: arrays, JSONB, full-text search vectors, hstore, range types.

```sql
-- JSONB indexing
CREATE INDEX idx_products_data ON products USING GIN (data jsonb_path_ops);

-- Query containment: data @> '{"category": "electronics"}'
-- Query existence:    data ? 'tags'
-- Query any:          data ?| array['tag1', 'tag2']

-- Array containment
CREATE INDEX idx_posts_tags ON posts USING GIN (tags);
-- Query: tags @> ARRAY['postgresql']      -- posts that have ALL these tags
-- Query: tags && ARRAY['postgresql']       -- posts that have ANY of these tags

-- Full-text search (alternative: GiST, which is smaller but slower for reads)
CREATE INDEX idx_articles_fts ON articles USING GIN (to_tsvector('english', body));
```

**GIN vs GiST for FTS**: GIN is 2-3x faster for reads but slower to build/update and larger on disk. Use GIN for read-heavy, GiST for write-heavy FTS workloads.

#### GiST (Generalized Search Tree)

Used for geometric data, full-text search, and KNN (K-Nearest Neighbor) queries.

```sql
-- Geometric / PostGIS
CREATE INDEX idx_locations_coords ON locations USING GIST (coord);
-- Query: SELECT * FROM locations ORDER BY coord <-> point '(1,2)' LIMIT 10;

-- Full-text search (lower write overhead than GIN)
CREATE INDEX idx_articles_fts_gist ON articles USING GIST (to_tsvector('english', body));

-- Exclusion constraints (e.g., no overlapping reservations)
CREATE EXTENSION btree_gist;
ALTER TABLE reservations ADD CONSTRAINT no_overlap
    EXCLUDE USING GIST (room_id WITH =, tsrange(start_time, end_time) WITH &&);
```

#### BRIN (Block Range Index)

Tiny index for very large tables with natural physical correlation. Ideal for append-only time-series data.

```sql
-- BRIN on timestamp column of append-only table
CREATE INDEX idx_events_ts_brin ON events USING BRIN (created_at)
    WITH (pages_per_range = 32);

-- Query: SELECT * FROM events WHERE created_at BETWEEN '2026-01-01' AND '2026-01-02';
-- BRIN reads only block ranges that overlap the WHERE range.

-- BRIN is ~1000x smaller than B-tree for the same column
-- Trade-off: approximate — reads some blocks outside the range
-- Tune pages_per_range: lower = more precise but larger
```

**BRIN requirements**: Physical row order must correlate with indexed column. Use `CLUSTER` or `pg_repack` to reorder rows if correlation decays over time.

#### Expression / Functional Indexes

```sql
-- Case-insensitive search
CREATE INDEX idx_users_lower_email ON users (LOWER(email));

-- JSON field extraction
CREATE INDEX idx_orders_data_status ON orders ((data->>'status'));

-- Computed date truncation
CREATE INDEX idx_events_day ON events ((date_trunc('day', created_at)));

-- Query must use EXACT expression to hit the index:
-- Hits index:  SELECT * FROM users WHERE LOWER(email) = 'user@example.com';
-- Misses index: SELECT * FROM users WHERE email = 'user@example.com';
```

#### Index Maintenance

```sql
-- Check index size and bloat
SELECT schemaname, tablename, indexname,
       pg_size_pretty(pg_relation_size(indexrelid)) AS size,
       pg_stat_get_numscans(indexrelid) AS scans
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;

-- Rebuild bloated index (locks table — use CONCURRENTLY for availability)
REINDEX INDEX CONCURRENTLY idx_users_email;

-- Find unused indexes (low scan count, not a constraint)
SELECT relname AS table, indexrelname AS index,
       idx_scan, idx_tup_read, idx_tup_fetch,
       pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE idx_scan < 10
  AND indisunique = false
  AND indisprimary = false
ORDER BY pg_relation_size(indexrelid) DESC;
```

---

### 2. Query Optimization

#### EXPLAIN ANALYZE Deep Dive

```sql
-- Always run with ANALYZE and BUFFERS for full picture
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT u.name, COUNT(o.id) AS order_count
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE u.created_at > NOW() - INTERVAL '30 days'
GROUP BY u.id, u.name
ORDER BY order_count DESC
LIMIT 20;
```

**Key fields to inspect**:
| Field | What It Tells You |
|---|---|
| `actual time` | `startup..total` ms — startup (first row) vs total (all rows) |
| `rows` | estimated vs actual — big gap = stale statistics |
| `loops` | how many times the node executed |
| `Buffers: shared hit` | blocks found in shared_buffers (fast) |
| `Buffers: shared read` | blocks read from disk (slow) |
| `Buffers: shared dirtied` | blocks modified by this query |
| `Buffers: local` | temp table activity |

**Warning signs in EXPLAIN output**:
- `Seq Scan` on a table with millions of rows when querying a few
- `actual rows` vastly different from `rows` estimate (run `ANALYZE`)
- `Nested Loop` joining two large tables (each side > 10K rows)
- `Sort` with `external merge` — ran out of `work_mem`, wrote to disk
- High `Buffers: shared read` count — data not cached

#### Join Types — When Each Is Chosen

| Join Type | When Used | Good For | Bad For |
|---|---|---|---|
| **Nested Loop** | One side is very small or indexed | `WHERE id = 1` + join to big table | Both sides large and unindexed |
| **Hash Join** | Both sides moderately large, no indexes | Equality joins on big tables | High memory use (needs `work_mem`) |
| **Merge Join** | Both inputs sorted on join key | Already-sorted inputs (from index scan) | Requires sort if not already ordered |

```sql
-- Force planner to avoid specific join type (for debugging):
SET enable_nestloop = off;   -- to test hash/merge join alternatives
-- Always RESET after testing.
```

#### pg_stat_statements — Finding Problem Queries

```sql
CREATE EXTENSION pg_stat_statements;

-- Top queries by total time
SELECT queryid,
       LEFT(query, 120) AS query_snippet,
       calls,
       ROUND(mean_exec_time::numeric, 2) AS avg_ms,
       ROUND(total_exec_time::numeric, 2) AS total_ms,
       rows,
       shared_blks_hit,
       shared_blks_read
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- Reset stats: SELECT pg_stat_statements_reset();
```

Set `pg_stat_statements.track = all` in `postgresql.conf` to track nested statements (inside functions).

#### Query Plan Operator Cheat Sheet

| Operator | Meaning | Good or Bad? |
|---|---|---|
| `Seq Scan` | Full table scan | Bad on large tables; fine on small (< 100 pages) |
| `Index Scan` | Reads index then heap | Typical for indexed lookups returning many rows |
| `Index Only Scan` | Reads index only (no heap fetch) | Best; requires covering index + visibility map up-to-date |
| `Bitmap Index Scan` | Builds bitmap of matching rows | Good for moderate selectivity, combines multiple indexes |
| `Bitmap Heap Scan` | Fetches heap rows from bitmap | Partner to Bitmap Index Scan; batch I/O |
| `Parallel Seq Scan` | Multi-worker sequential scan | Good for large sequential reads |
| `Materialize` | Caches subquery result | Can help if subquery re-scanned in nested loop |
| `Hash` / `Hash Join` | Build hash table, probe for matches | Good for unindexed equality joins |

---

### 3. Advanced Features

#### Window Functions

```sql
-- ROW_NUMBER: unique sequential number within partition
SELECT id, created_at,
       ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn
FROM orders;

-- RANK vs DENSE_RANK (RANK leaves gaps on ties, DENSE_RANK does not)
SELECT name, score,
       RANK() OVER (ORDER BY score DESC) AS rank,
       DENSE_RANK() OVER (ORDER BY score DESC) AS dense_rank
FROM players;

-- LAG / LEAD: access previous or next row
SELECT created_at,
       LAG(created_at) OVER (ORDER BY created_at) AS prev_order,
       created_at - LAG(created_at) OVER (ORDER BY created_at) AS gap
FROM orders
WHERE user_id = 42;

-- NTILE: divide into N buckets
SELECT id, amount, NTILE(4) OVER (ORDER BY amount DESC) AS quartile
FROM sales;

-- Aggregate with frame clause
SELECT created_at::date AS day,
       SUM(amount) OVER (ORDER BY created_at::date
           ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS rolling_7day_sum
FROM sales;

-- Named window (reuse window definition)
SELECT id, amount,
       SUM(amount) OVER w AS running_total,
       AVG(amount) OVER w AS running_avg
FROM sales
WINDOW w AS (ORDER BY created_at ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW);
```

**Frame clause options**: `ROWS` (physical), `RANGE` (logical — groups peers), `GROUPS` (peer groups). Prefer `ROWS` for predictable performance.

#### Common Table Expressions (CTEs)

```sql
-- Basic CTE
WITH recent_users AS (
    SELECT id, name FROM users WHERE created_at > NOW() - INTERVAL '30 days'
)
SELECT r.name, COUNT(o.id) AS orders
FROM recent_users r
JOIN orders o ON o.user_id = r.id
GROUP BY r.id, r.name;

-- MATERIALIZED hint: force CTE to be computed once (optimization fence)
-- Useful when CTE is referenced multiple times with expensive computation
WITH user_totals AS MATERIALIZED (
    SELECT user_id, SUM(amount) AS total_spent
    FROM orders GROUP BY user_id
)
SELECT u.name, t.total_spent
FROM users u
JOIN user_totals t ON t.user_id = u.id
WHERE t.total_spent > 1000;

-- Recursive CTE for tree/graph traversal
WITH RECURSIVE org_chart AS (
    -- Base case: root nodes (no manager)
    SELECT id, name, manager_id, 0 AS depth
    FROM employees WHERE manager_id IS NULL

    UNION ALL

    -- Recursive step: one level deeper
    SELECT e.id, e.name, e.manager_id, oc.depth + 1
    FROM employees e
    JOIN org_chart oc ON oc.id = e.manager_id
)
SELECT * FROM org_chart ORDER BY depth, name;

-- Generate series via recursive CTE
WITH RECURSIVE dates(d) AS (
    SELECT '2026-01-01'::date
    UNION ALL
    SELECT d + 1 FROM dates WHERE d < '2026-01-31'
)
SELECT d FROM dates;
```

#### JSONB Operations

```sql
-- Containment queries (uses GIN index)
SELECT * FROM products
WHERE data @> '{"category": "electronics", "brand": "Apple"}';
-- Returns rows where data contains ALL specified key/values

-- Key existence
SELECT * FROM products WHERE data ? 'warranty_years';

-- Any key in array
SELECT * FROM products WHERE data ?| ARRAY['color', 'size'];

-- Path extraction with jsonb_path_query (SQL/JSON path language)
SELECT id, jsonb_path_query(data, '$.specs.weight[*]') AS weight
FROM products
WHERE data @? '$.specs.weight';

-- jsonb_set: update or add a key
UPDATE products
SET data = jsonb_set(data, '{pricing,discount}', '0.15'::jsonb, true);

-- jsonb_array_elements: unnest array to rows
SELECT id, jsonb_array_elements_text(data->'tags') AS tag
FROM products;

-- Deduplication: jsonb_strip_nulls, jsonb_pretty
UPDATE products SET data = jsonb_strip_nulls(data);
```

#### Full-Text Search

```sql
-- Build tsvector from text
SELECT to_tsvector('english', 'The quick brown fox jumps over the lazy dog');
-- 'brown':3 'dog':9 'fox':4 'jump':5 'lazi':8 'quick':2

-- Build tsvector combining columns with weights
ALTER TABLE articles ADD COLUMN fts tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(body, '')), 'B')
    ) STORED;

CREATE INDEX idx_articles_fts ON articles USING GIN (fts);

-- Search with ranking
SELECT title,
       ts_rank(fts, plainto_tsquery('english', 'postgresql performance')) AS rank,
       ts_headline('english', body, plainto_tsquery('english', 'postgresql performance'))
FROM articles
WHERE fts @@ plainto_tsquery('english', 'postgresql performance')
ORDER BY rank DESC
LIMIT 20;

-- Phrase search (words must be adjacent)
SELECT * FROM articles
WHERE fts @@ phraseto_tsquery('english', 'postgresql performance tuning');

-- Custom dictionary / thesaurus configuration
-- CREATE TEXT SEARCH DICTIONARY my_synonyms (...)
```

#### pgvector (Vector Similarity Search)

```sql
CREATE EXTENSION vector;

CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(1536)  -- dimension must match model
);

-- ivfflat: clusters vectors, faster build, good for up to ~2M vectors
CREATE INDEX ON embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
-- lists: typically sqrt(rows) for best recall-vs-speed trade-off

-- hnsw: graph-based, faster queries, slower build, good for >1M vectors
CREATE INDEX ON embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
-- m: connections per layer (default 16); ef_construction: build quality (default 64)

-- Similarity operators
-- <=> : cosine distance
-- <#> : negative inner product
-- <+> : L2 distance

-- Top-K semantic search
SELECT content, embedding <=> query_embedding AS distance
FROM embeddings
ORDER BY embedding <=> query_embedding
LIMIT 10;

-- Hybrid search: combine vector + keyword
SELECT content,
       (embedding <=> query_embedding) * 0.7 +
       (CASE WHEN content ILIKE '%keyword%' THEN 0 ELSE 0.3 END) AS score
FROM embeddings
ORDER BY score
LIMIT 10;

-- Tuning tip: set ivfflat.probes for query-time accuracy
SET ivfflat.probes = 20;  -- increase for better recall, decrease for speed
```

#### PostGIS (Spatial)

```sql
CREATE EXTENSION postgis;

CREATE TABLE places (
    id SERIAL PRIMARY KEY,
    name TEXT,
    location geography(Point, 4326)  -- WGS84 lon/lat
);

CREATE INDEX idx_places_location ON places USING GIST (location);

-- Find places within 5km of a point
SELECT name, ST_Distance(location, ST_MakePoint(-73.9857, 40.7484)::geography) AS dist_m
FROM places
WHERE ST_DWithin(location, ST_MakePoint(-73.9857, 40.7484)::geography, 5000)
ORDER BY dist_m;

-- Geo clustering (k-means)
SELECT ST_ClusterKMeans(location::geometry, 5) OVER () AS cluster_id, name
FROM places;

-- Bounding box (uses geometry index on geography via cast)
SELECT name FROM places
WHERE location && ST_MakeEnvelope(-74.0, 40.7, -73.9, 40.8, 4326)::geography;

-- Transform geometry to different SRID
SELECT ST_Transform(geom, 3857) FROM parcels;
```

---

### 4. Partitioning

#### Declarative Partitioning

```sql
-- Create partitioned table
CREATE TABLE events (
    id SERIAL,
    created_at TIMESTAMPTZ NOT NULL,
    event_type TEXT,
    payload JSONB
) PARTITION BY RANGE (created_at);

-- Create partitions
CREATE TABLE events_2026_01 PARTITION OF events
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE events_2026_02 PARTITION OF events
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

-- Add index on parent — each partition inherits it
CREATE INDEX ON events (created_at);
CREATE INDEX ON events (event_type);

-- List partitioning by discrete values
CREATE TABLE orders (
    id SERIAL,
    region TEXT,
    amount NUMERIC
) PARTITION BY LIST (region);

CREATE TABLE orders_us PARTITION OF orders FOR VALUES IN ('US', 'CA');
CREATE TABLE orders_eu PARTITION OF orders FOR VALUES IN ('UK', 'DE', 'FR');

-- Hash partitioning for uniform distribution
CREATE TABLE sessions (
    id UUID,
    user_id INTEGER,
    data JSONB
) PARTITION BY HASH (user_id);

CREATE TABLE sessions_p0 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE sessions_p1 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE sessions_p2 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE sessions_p3 PARTITION OF sessions FOR VALUES WITH (MODULUS 4, REMAINDER 3);
```

#### Partition Maintenance

```sql
-- Default partition catches rows that don't match any partition
CREATE TABLE events_default PARTITION OF events DEFAULT;

-- Detach partition (avoid locking parent during maintenance)
ALTER TABLE events DETACH PARTITION events_2024_01;
-- ... archive or drop it later ...

-- Attach existing table as partition (must satisfy constraints)
ALTER TABLE events ATTACH PARTITION events_2024_01
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Sub-partitioning
CREATE TABLE events (
    id SERIAL,
    created_at TIMESTAMPTZ NOT NULL,
    region TEXT NOT NULL
) PARTITION BY RANGE (created_at);

CREATE TABLE events_2026 PARTITION OF events
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01')
    PARTITION BY LIST (region);

CREATE TABLE events_2026_us PARTITION OF events_2026
    FOR VALUES IN ('US', 'CA');
CREATE TABLE events_2026_eu PARTITION OF events_2026
    FOR VALUES IN ('UK', 'DE', 'FR');

-- Automatic partition pruning
EXPLAIN SELECT * FROM events WHERE created_at >= '2026-06-01';
-- Shows only events_2026 partitions scanned
```

---

### 5. Connection Management

#### PgBouncer

```
┌──────────┐      ┌───────────┐      ┌────────────┐
│ App Pool │ ───> │ PgBouncer │ ───> │ PostgreSQL │
│ (20 conn)│      │(pool: 50) │      │(max_conn:50)│
└──────────┘      └───────────┘      └────────────┘
```

| Pool Mode | How It Works | Use Case |
|---|---|---|
| **Transaction** | Connection returned to pool after each transaction | Web apps, stateless workloads (default) |
| **Session** | Connection held for the session (like direct PG connection) | Prepared statements, `SET` variables, advisory locks |
| **Statement** | Most aggressive; returned after each statement | Extreme connection scarcity; breaks transactions |

```ini
# pgbouncer.ini
[databases]
mydb = host=localhost port=5432 dbname=mydb

[pgbouncer]
pool_mode = transaction
default_pool_size = 25          # per user/database pair
max_client_conn = 500           # max connections from apps
max_db_connections = 50         # max connections to PostgreSQL
```

#### Connection Pool Sizing

```
connections_per_pool = (CPU_cores * 2) + (effective_spindles)
total_pgbouncer_pools = connections_per_pool * pgbouncer_instances

Example: 16 cores, SSD → (16 * 2) + 0 = 32 PostgreSQL connections
With 3 app instances × 20 workers each = 60
Setup: PgBouncer with pool_size=15, 3 PgBouncer instances
Result: 60 virtual clients → 45 max real PG connections
```

#### Timeouts — Set ALL Three

```sql
-- Cancel statements that run too long (protects DB from runaway queries)
ALTER DATABASE mydb SET statement_timeout = '30s';

-- Kill idle-in-transaction sessions (leaked transactions)
ALTER DATABASE mydb SET idle_in_transaction_session_timeout = '5min';

-- Cancel queries waiting on locks too long
ALTER DATABASE mydb SET lock_timeout = '10s';

-- Set per-role for specific users
ALTER ROLE app_user SET statement_timeout = '10s';
```

**Caution**: `statement_timeout` applies to `VACUUM` and `CREATE INDEX` too. Set it higher for maintenance roles.

#### Monitoring Connections

```sql
-- Active connections and their state
SELECT state, COUNT(*)
FROM pg_stat_activity
GROUP BY state;
-- active, idle, idle in transaction, idle in transaction (aborted)

-- Long-running queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - pg_stat_activity.query_start > INTERVAL '30 seconds'
ORDER BY duration DESC;

-- Connections waiting on locks
SELECT blocked.pid AS blocked_pid,
       blocked.query AS blocked_query,
       blocking.pid AS blocking_pid,
       blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_locks b_lock ON b_lock.pid = blocked.pid AND NOT b_lock.granted
JOIN pg_stat_activity blocking ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
JOIN pg_locks blk_lock ON blk_lock.pid = blocking.pid
    AND blk_lock.relation = b_lock.relation AND blk_lock.granted;
```

---

### 6. Replication and High Availability

#### Streaming Replication

```sql
-- Primary: postgresql.conf
wal_level = replica
max_wal_senders = 10
wal_keep_size = '1GB'

-- Primary: pg_hba.conf (allow replication connections)
-- host  replication  repl_user  10.0.0.0/8  scram-sha-256

-- Standby: create base backup, then start in recovery mode
-- pg_basebackup -h primary_host -D /var/lib/postgresql/data -R -P

-- Sync vs async (set per standby in primary)
-- synchronous_standby_names = 'FIRST 1 (standby1, standby2)'  -- sync
-- synchronous_standby_names = ''                                -- async (default)

-- Check replication lag on primary
SELECT application_name, state,
       pg_wal_lsn_diff(sent_lsn, replay_lsn) AS replay_lag_bytes,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS total_lag_bytes
FROM pg_stat_replication;
```

#### Logical Replication (Pub/Sub)

```sql
-- Publisher side
CREATE PUBLICATION orders_pub FOR TABLE orders (id, user_id, amount, status);
ALTER PUBLICATION orders_pub ADD TABLE order_items;

-- Subscriber side
CREATE SUBSCRIPTION orders_sub
    CONNECTION 'host=publisher port=5432 dbname=mydb'
    PUBLICATION orders_pub;

-- Monitor subscription status
SELECT subscription_name, received_lsn, latest_end_lsn,
       pg_wal_lsn_diff(latest_end_lsn, received_lsn) AS lag_bytes
FROM pg_stat_subscription;
```

**When to use logical over streaming**: Selective table replication, cross-major-version upgrades, multi-master topologies, partial data replication.

#### Auto-Failover

| Tool | Approach | Best For |
|---|---|---|
| **Patroni** | etcd/Consul/ZooKeeper for leader election; manages PostgreSQL + callbacks | Production, any cloud / on-prem |
| **Stolon** | etcd/Consul; proxy layer separates client routing | Multi-DC, complex topologies |
| **Cloud-native** | RDS Multi-AZ, Cloud SQL HA, Azure Flexible Server | Managed services |
| **repmgr** | Simpler; tool-based failover (not automatic by default) | Small deployments |

**Key principle**: Auto-failover MUST have quorum-based leader election. Never use a single monitoring node — split-brain risk.

---

### 7. Performance Tuning

#### Memory Configuration

```ini
# postgresql.conf — key memory parameters

shared_buffers = 4GB
# Rule: 25% of system RAM (up to ~8GB; diminishing returns beyond)
# This is PostgreSQL's internal cache for data pages

effective_cache_size = 12GB
# Rule: 75% of system RAM
# NOT allocated — planner hint for index vs seq scan decisions

work_mem = 64MB
# Per-operation sort/hash memory; a single query may use work_mem * N times
# Rule: (Total RAM / max_connections) / 4  — conservative starting point
# Set per-role for reporting/ETL users:
#   ALTER ROLE etl_user SET work_mem = '256MB';

maintenance_work_mem = 1GB
# Used by VACUUM, CREATE INDEX, REINDEX, ALTER TABLE ADD FOREIGN KEY
# Set higher for large databases; can be set per-session before maintenance

wal_buffers = 64MB
# Rule: 3% of shared_buffers, up to 64MB (max useful for most workloads)
```

#### Autovacuum Tuning

Autovacuum prevents transaction ID wraparound and updates table statistics. Tune it aggressively for write-heavy databases.

```sql
-- Scale autovacuum with database size
ALTER SYSTEM SET autovacuum_max_workers = 4;      -- default 3
ALTER SYSTEM SET autovacuum_naptime = '30s';       -- default 1min
ALTER SYSTEM SET autovacuum_vacuum_scale_factor = 0.05;  -- default 0.2

-- Per-table tuning for high-churn tables
ALTER TABLE events SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_vacuum_cost_limit = 2000    -- default 200; more aggressive
);

-- Monitor autovacuum activity
SELECT relname,
       n_dead_tup,
       last_vacuum,
       last_autovacuum,
       autovacuum_count,
       vacuum_count
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC;
```

#### Parallel Query

```sql
-- Enable parallel query (default in PG 12+)
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;  -- per query
ALTER SYSTEM SET max_parallel_workers = 8;             -- system total
ALTER SYSTEM SET parallel_tuple_cost = 0.01;           -- lower = more parallel
ALTER SYSTEM SET parallel_setup_cost = 100;            -- lower = more parallel

-- Check if query uses parallel workers
EXPLAIN (ANALYZE, VERBOSE)
SELECT count(*) FROM events WHERE created_at > '2026-01-01';
-- Look for: "Workers Planned: 4" and "Workers Launched: 4"

-- Force parallel for testing
SET max_parallel_workers_per_gather = 4;
SET min_parallel_table_scan_size = '1MB';  -- lower threshold
```

#### Statistics

```sql
-- Update table statistics
ANALYZE users;
ANALYZE VERBOSE users;  -- see what ANALYZE is doing

-- Increase statistics target for columns with skewed data
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 1000;
-- Default is 100; increase for columns with >100 distinct values
-- where the planner makes bad selectivity estimates

-- Check last ANALYZE time
SELECT schemaname, relname, last_analyze, last_autoanalyze,
       n_mod_since_analyze
FROM pg_stat_user_tables
WHERE n_mod_since_analyze > 10000
ORDER BY n_mod_since_analyze DESC;
```

---

### 8. Security in PostgreSQL

#### Row-Level Security (RLS)

```sql
-- Enable RLS on table
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- Policy: users can only see their own documents
CREATE POLICY user_own_docs ON documents
    FOR ALL
    TO app_user
    USING (user_id = current_setting('app.current_user_id')::INTEGER);

-- Policy: admins can see all documents
CREATE POLICY admin_all_docs ON documents
    FOR ALL
    TO admin_role
    USING (true);

-- Policy for specific operations
CREATE POLICY user_insert_own ON documents
    FOR INSERT
    TO app_user
    WITH CHECK (user_id = current_setting('app.current_user_id')::INTEGER);

-- Bypass RLS for specific roles
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
-- Even table owner is restricted (unless BYPASSRLS attribute or superuser)
```

#### Column-Level Permissions

```sql
-- Grant access to specific columns
GRANT SELECT (id, name, email) ON users TO app_user;
-- Revoke access to sensitive columns (salary, ssn)
REVOKE SELECT (salary, ssn) ON users FROM app_user;

-- Column-level grants only work for SELECT, INSERT, UPDATE
GRANT UPDATE (name, email) ON users TO app_user;
```

#### pg_hba.conf Configuration

```
# TYPE  DATABASE   USER        ADDRESS          METHOD
local   all        postgres                     peer
host    mydb       app_user    10.0.0.0/8       scram-sha-256
host    mydb       readonly    0.0.0.0/0        scram-sha-256
host    replication repl_user  10.0.0.0/8       scram-sha-256

# Rules are processed top-to-bottom, first match wins
# Always: deny all, then allow specific
host    all        all         0.0.0.0/0        reject
```

Run `SELECT pg_reload_conf();` after changes (no restart needed).

#### SSL/TLS

```ini
# postgresql.conf
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
ssl_ca_file = 'ca.crt'     # for client certificate verification
```

```sql
-- Enforce SSL per user
ALTER ROLE app_user SET sslmode = 'require';

-- Verify SSL status for current connections
SELECT pid, usename, ssl, client_addr
FROM pg_stat_ssl
JOIN pg_stat_activity USING (pid)
WHERE ssl = false AND usename != 'postgres';
```

#### Audit Logging (pgaudit)

```sql
CREATE EXTENSION pgaudit;

-- Log all DDL and specific table access
ALTER SYSTEM SET pgaudit.log = 'write, ddl';
ALTER SYSTEM SET pgaudit.log_relation = 'on';
ALTER SYSTEM SET pgaudit.log_level = 'notice';

-- Audit specific role actions
ALTER SYSTEM SET pgaudit.log = 'all';
ALTER ROLE auditor SET pgaudit.log = 'all';

-- Session-level audit (temporary)
SET pgaudit.log = 'read, write';
SELECT * FROM users;  -- logged
RESET pgaudit.log;
```

---

### 9. Backup and Recovery

#### pg_dump (Logical Backup)

```sql
-- Full database dump
pg_dump -h localhost -U postgres -Fc -f mydb_20260101.dump mydb
-- -Fc: custom format (compressed, restorable with pg_restore)
-- -Fp: plain SQL (human-readable, pipe to psql)

-- Schema only
pg_dump -h localhost -U postgres -s -f schema.sql mydb

-- Data only, specific tables
pg_dump -h localhost -U postgres -a -t users -t orders -f data.sql mydb

-- Parallel restore
pg_restore -h localhost -U postgres -d mydb -j 4 mydb_20260101.dump
```

#### pg_basebackup (Physical Backup)

```bash
# Full cluster backup
pg_basebackup -h primary_host -D /backup/base/20260101 \
    -Ft -z -P -R
# -Ft: tar format; -z: gzip; -P: progress; -R: write recovery.conf

# Verify backup
pg_verifybackup /backup/base/20260101
```

#### Point-in-Time Recovery (PITR)

```ini
# postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /archive/%f && cp %p /archive/%f'
archive_timeout = 60   # force WAL switch after 60s to limit data loss
```

**Recovery procedure**:
1. Restore base backup
2. Set `restore_command` in `postgresql.conf` or standby.signal file: `restore_command = 'cp /archive/%f %p'`
3. Set `recovery_target_time = '2026-01-15 14:30:00 UTC'` for PITR to specific moment
4. Start PostgreSQL — it replays WAL up to the target

```sql
-- After recovery completes, promote to primary
SELECT pg_promote();

-- Check recovery progress
SELECT pg_is_in_recovery();
SELECT pg_last_wal_replay_lsn(), pg_last_wal_receive_lsn();
```

#### Backup Validation

```bash
# Verify physical backup
pg_verifybackup /backup/base/20260101

# Test restore: restore to temp instance and validate
export PGDATA=/tmp/restore_test
pg_basebackup -h primary -D $PGDATA -R
pg_ctl -D $PGDATA start
psql -c "SELECT count(*) FROM critical_table;"
pg_ctl -D $PGDATA stop
```

---

### 10. Migration Patterns and Zero-Downtime Schema Changes

#### Safe Pattern: Expand, Migrate, Contract

```
Phase 1 (EXPAND): Add new column/schema; deploy app that writes to BOTH
                  old and new. Backfill data in background.

Phase 2 (MIGRATE): Deploy app that reads from NEW. Old data still there.

Phase 3 (CONTRACT): Stop writing to old. Drop old column/table.
```

```sql
-- Phase 1: Add nullable column (instant, no table rewrite in PG 11+)
ALTER TABLE users ADD COLUMN full_name TEXT;

-- Backfill in batches to avoid long locks
DO $$
DECLARE batch_size INT := 1000;
BEGIN
    LOOP
        UPDATE users SET full_name = first_name || ' ' || last_name
        WHERE id IN (
            SELECT id FROM users
            WHERE full_name IS NULL LIMIT batch_size
        );
        EXIT WHEN NOT FOUND;
        COMMIT;
        PERFORM pg_sleep(0.1);  -- reduce replication pressure
    END LOOP;
END $$;

-- Phase 3: Drop old column
ALTER TABLE users DROP COLUMN first_name;
ALTER TABLE users DROP COLUMN last_name;
```

#### Safe Operations (Avoid Table Rewrite)

| Operation | Safe? | Notes |
|---|---|---|
| `ADD COLUMN` (nullable) | Safe (PG 11+) | Instant; no rewrite |
| `ADD COLUMN` (with default) | Safe (PG 11+) | No rewrite on creation; default stored in catalog |
| `DROP COLUMN` | Safe | Instant; space reclaimed by VACUUM |
| `SET DEFAULT` / `DROP DEFAULT` | Safe | Catalog change only |
| `SET NOT NULL` | Rewrite | Use `ADD CONSTRAINT ... NOT NULL VALID` then validate |
| `ALTER TYPE` | Rewrite | Create new column, migrate in batches, drop old |
| `ADD FOREIGN KEY` | Safe with NOT VALID | `ALTER TABLE ... ADD CONSTRAINT fk ... NOT VALID;` — then validate later |
| Rename column / table | Safe (with caution) | Use `ALTER TABLE RENAME COLUMN` — update app code simultaneously |

```sql
-- Safe NOT NULL constraint (avoid full table scan lock)
ALTER TABLE users ADD CONSTRAINT users_email_not_null
    CHECK (email IS NOT NULL) NOT VALID;
ALTER TABLE users VALIDATE CONSTRAINT users_email_not_null;

-- Safe foreign key
ALTER TABLE orders ADD CONSTRAINT fk_orders_user
    FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
ALTER TABLE orders VALIDATE CONSTRAINT fk_orders_user;

-- Concurrent index creation (does not block writes)
CREATE INDEX CONCURRENTLY idx_users_email ON users (email);
-- Note: CONCURRENTLY takes longer and cannot run inside a transaction
```

#### Using pg_repack for Non-Blocking Table Changes

```bash
# Install: CREATE EXTENSION pg_repack;
# Reorder table and reclaim space WITHOUT blocking writes
pg_repack -t orders -d mydb

# Cluster on index without downtime (unlike CLUSTER which locks)
pg_repack -t orders -i idx_orders_user_id -d mydb
```

---

### 11. Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| **Indexing every column** | Write amplification; each INSERT/UPDATE/DELETE touches every index; wasted disk | Only create indexes that match query patterns; drop unused indexes |
| **`SELECT *` in application code** | Breaks on schema changes; fetches unnecessary data; prevents index-only scans | Explicitly list columns |
| **No `WHERE` clause on `UPDATE`/`DELETE`** | Accidentally modifies/deletes all rows | Use explicit WHERE; set `BEGIN` before manual changes |
| **Using `VARCHAR` without limit or `TEXT` for everything** | No validation; `TEXT` is fine but `VARCHAR(n)` provides a constraint | Choose type based on domain constraints, not performance |
| **Not using `CONCURRENTLY` for index creation** | Index creation locks the table for writes | Always use `CREATE INDEX CONCURRENTLY` in production |
| **Large transactions** | Long-held locks; bloated WAL; replication lag; vacuum can't clean up | Batch operations: 1000-10000 rows per transaction |
| **Application-side pagination with `OFFSET`** | Scans and discards offset rows every page; performance degrades with high offsets | Use keyset pagination: `WHERE id > last_seen_id ORDER BY id LIMIT 20` |
| **UUID primary keys without tuning** | Random UUIDs fragment B-tree; poor cache locality; large index size | Use `uuid_generate_v7()` (time-ordered) or `BIGSERIAL` |
| **No connection pooling** | Each connection forks a backend process (~5-10MB); max_connections ceiling hit quickly | Always use PgBouncer in transaction mode |
| **Relying on `SERIAL` for distributed systems** | Serial is node-local; can't scale horizontally | Use UUIDv7 or Snowflake-like IDs |
| **Using `HAVING` instead of `WHERE` for row filtering** | HAVING filters groups after aggregation; WHERE filters rows before (faster) | Use WHERE for row-level filters, HAVING only for aggregate conditions |
| **Advisory locks as a queue** | Lock contention under high concurrency; no persistence guarantees | Use `SKIP LOCKED` with a work table, or a proper queue (RabbitMQ, Redis) |

---

### 12. Common Performance Issues and Solutions

| Symptom | Root Cause | Diagnosis | Solution |
|---|---|---|---|
| **Slow SELECT on large table** | Missing index | `EXPLAIN ANALYZE` shows Seq Scan | Add index on WHERE/JOIN columns |
| **Slow SELECT with index** | Planner choosing Seq Scan over index | `EXPLAIN` shows high cost estimate for index scan | `SET enable_seqscan = off` to test; then tune `random_page_cost` (SSD: 1.1) or `effective_cache_size` |
| **Query getting slower over time** | Table/index bloat | `pg_stat_user_tables.n_dead_tup` is high; index has many dead tuples | Tune autovacuum; `VACUUM FULL` or `pg_repack` (last resort) |
| **Slow INSERT/UPDATE on indexed table** | Too many indexes | Check index count per table; `EXPLAIN ANALYZE` on INSERT showing many index updates | Drop unused indexes; consolidate overlapping indexes |
| **Transaction ID wraparound warning** | Autovacuum can't keep up | `SELECT age(datfrozenxid) FROM pg_database;` — approaching 2 billion | Increase autovacuum workers; run manual `VACUUM FREEZE` |
| **Connection spikes, then timeouts** | Connection pool exhausted | `pg_stat_activity` shows many idle connections | Add PgBouncer; tune pool size; set `idle_in_transaction_session_timeout` |
| **Replication lag growing** | Standby can't keep up with WAL | `pg_stat_replication.replay_lag` increasing | Tune `max_wal_senders`; check standby I/O; enable compression in pg_basebackup |
| **UPDATE causing unexpected table scan** | No index on WHERE clause of UPDATE | `EXPLAIN` on `UPDATE ... WHERE ...` | Index the column(s) used in WHERE of frequent UPDATEs |
| **Slow COUNT(*)** | PostgreSQL always scans entire table for COUNT | On large tables, COUNT takes linear time | Use estimate: `SELECT reltuples::bigint FROM pg_class WHERE relname = 'table_name'` |
| **High CPU, low throughput** | Too many connections context-switching | 200+ active connections; CPU in system/kernel | Reduce connections via PgBouncer; fewer connections = higher throughput |

---

### Quick Reference: Essential Settings Summary

```ini
# Memory
shared_buffers = 4GB              # 25% of RAM
effective_cache_size = 12GB       # 75% of RAM
work_mem = 64MB                   # conservative; raise per-session for reporting
maintenance_work_mem = 1GB        # for VACUUM / CREATE INDEX

# WAL / Checkpoint
wal_level = replica
max_wal_size = 8GB
min_wal_size = 2GB
checkpoint_timeout = 15min
checkpoint_completion_target = 0.9

# Planner
random_page_cost = 1.1            # SSD (default 4.0 is for HDD)
effective_io_concurrency = 200    # SSD concurrent I/O
default_statistics_target = 100   # raise to 500-1000 for problematic columns

# Autovacuum
autovacuum_max_workers = 4
autovacuum_naptime = 30s

# Connections
max_connections = 100             # keep low; use PgBouncer

# Query timeout (per database)
statement_timeout = 30s
idle_in_transaction_session_timeout = 5min
lock_timeout = 10s

# Logging
log_min_duration_statement = 1000  # log queries > 1s
log_checkpoints = on
log_autovacuum_min_duration = 0    # log all autovacuum activity
log_lock_waits = on
```
