---
name: redis
description: Redis mastery — data structures, caching, pub/sub, rate limiting, sessions, queues, high availability, Redis Stack, Sentinel, Cluster, and production patterns with ioredis
license: MIT
compatibility: opencode
metadata:
  audience: backend-developers
  domain: database
  paradigm: key-value
  capabilities:
    - caching-patterns
    - pub-sub-messaging
    - rate-limiting
    - session-management
    - background-jobs
    - distributed-locking
    - real-time-leaderboards
    - redis-stack
    - high-availability
    - performance-tuning
    - security-hardening
  integrates_with:
    - backend-nodejs
    - backend-go
    - backend-python
    - database-event-sourcing
    - infra-observability
  libraries:
    - ioredis
    - bullmq
    - connect-redis
    - redis-om
---

# Skill: Redis — Production-Grade Data Store Mastery

## Redis Mental Model

```
┌──────────────────────────────────────────────────────────────────┐
│                    REDIS ECOSYSTEM MAP                             │
│                                                                    │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │                  CORE DATA STRUCTURES                      │    │
│   │  String │ Hash │ List │ Set │ ZSet │ Stream │ Bitmap │ HLL │   │
│   └──────────────────────────────────────────────────────────┘    │
│                          │                                         │
│                          ▼                                         │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │                   REDIS STACK MODULES                      │    │
│   │  JSON │ Search │ TimeSeries │ Graph │ Bloom │ Gears       │   │
│   └──────────────────────────────────────────────────────────┘    │
│                          │                                         │
│                          ▼                                         │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │                 PRODUCTION OPERATIONS                      │    │
│   │  Persistence │ Sentinel │ Cluster │ ACL │ TLS │ Monitor   │   │
│   └──────────────────────────────────────────────────────────┘    │
│                          │                                         │
│                          ▼                                         │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │              APPLICATION PATTERNS                          │    │
│   │  Cache │ Session │ Rate Limit │ Queue │ Lock │ Leaderboard│   │
│   └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘

Redis is an in-memory data structure server. It is NOT a primary database.
It is a cache, message broker, and analytics engine all in one.
```

---

## 1. Redis Fundamentals — Data Structures

### 1.1 Type Reference

| Structure   | Max Size    | Persistence   | Use Case                                    |
|-------------|-------------|---------------|---------------------------------------------|
| `STRING`    | 512 MB      | RDB/AOF       | Cache, counters, distributed locks          |
| `HASH`      | 4B fields   | RDB/AOF       | Objects, partial updates, maps              |
| `LIST`      | 4B elements | RDB/AOF       | Queue, timeline, message buffer             |
| `SET`       | 4B members  | RDB/AOF       | Tags, unique visitors, relationships        |
| `ZSET`      | 4B members  | RDB/AOF       | Leaderboards, rate limits, priority queues  |
| `STREAM`    | 4B entries  | RDB/AOF       | Event log, message queue, pub/sub with ack  |
| `BITMAP`    | 512 MB      | RDB/AOF       | Analytics, bloom-like counting              |
| `HYPERLOGLOG` | 12 KB    | RDB/AOF       | Approximate counting                        |
| `GEO`       | —           | RDB/AOF       | Geospatial queries                          |
| `JSON`      | —           | RDB/AOF       | Nested documents (Redis Stack)              |
| `TIMESERIES`| —           | RDB/AOF       | Time-series data (Redis Stack)              |
| `GRAPH`     | —           | RDB/AOF       | Graph traversal (Redis Stack)               |

### 1.2 Decision Tree: Which Data Structure?

```
Need to store a value?                       → STRING
Need to store an object with fields?         → HASH
  > Is the object deeply nested (>1 level)?  → JSON (Stack)
Need a simple queue (FIFO)?                  → LIST
  > Need blocking pop?                       → LIST (BLPOP/BRPOP)
  > Need acknowledgment/failover?            → STREAM
Need a set of unique items?                  → SET
  > Need intersections/unions/diffs?         → SET (SINTER/SUNION/SDIFF)
Need ranked ordering?                        → ZSET
  > Need real-time leaderboard?              → ZSET (ZINCRBY/ZREVRANGE)
  > Need sliding window rate limit?          → ZSET
Need messaging/pub-sub?                      → PUB/SUB channels (fire-and-forget)
  > Need message persistence + ack?          → STREAM (XREADGROUP)
Need approximate unique count?               → HYPERLOGLOG (PFADD/PFCOUNT)
Need geospatial queries?                     → GEO (GEOADD/GEORADIUS)
Need bit-level operations?                   → BITMAP (SETBIT/BITCOUNT)
```

### 1.3 STRING — The Foundation

```typescript
import Redis from 'ioredis'
const redis = new Redis()

// Basic ops
await redis.set('user:1:name', 'Alice')
await redis.set('user:1:login_count', 0)
await redis.incr('user:1:login_count') // → 1
await redis.incrby('user:1:login_count', 5) // → 6

// SET with options
await redis.set('session:abc', JSON.stringify({ userId: 1 }), 'EX', 3600) // TTL 1h
await redis.set('lock:resource', 'locked', 'PX', 30000, 'NX') // Only if not exists

// MSET/MGET — batch
await redis.mset('a', '1', 'b', '2', 'c', '3')
const [a, b] = await redis.mget('a', 'b')

// Atomic counter per time window
const key = `rate:${req.ip}:${Math.floor(Date.now() / 60000)}`
const count = await redis.incr(key)
if (count === 1) await redis.expire(key, 60)
```

### 1.4 HASH — Object Storage

```typescript
// Set object fields
await redis.hset('user:1', {
  name: 'Alice',
  email: 'alice@example.com',
  role: 'admin',
})

// Get all fields
const user = await redis.hgetall('user:1')

// Get specific fields
const [name, email] = await redis.hmget('user:1', 'name', 'email')

// Increment a field
await redis.hincrby('user:1', 'login_count', 1)

// Field exists
const exists = await redis.hexists('user:1', 'email')

// Partial update without full read
await redis.hset('user:1', 'last_login', new Date().toISOString())
```

### 1.5 LIST — Queue & Timeline

```typescript
// Push to right (end)
await redis.rpush('queue:emails', 'email1', 'email2', 'email3')

// Pop from left (front) — FIFO
const email = await redis.lpop('queue:emails')

// Blocking pop — wait for item (timeout 0 = infinite)
const [queue, item] = await redis.blpop('queue:emails', 0)

// Trim to length
await redis.ltrim('queue:emails', 0, 99) // Keep first 100

// Range
const items = await redis.lrange('timeline:user:1', 0, 19) // Latest 20

// Length
const len = await redis.llen('queue:emails')
```

### 1.6 SET — Unique Members & Relationships

```typescript
// Add tags
await redis.sadd('post:1:tags', 'redis', 'cache', 'database')

// Check membership
const isTagged = await redis.sismember('post:1:tags', 'redis')

// Intersection — common tags
const common = await redis.sinter('post:1:tags', 'post:2:tags')

// Union — all tags
const all = await redis.sunion('post:1:tags', 'post:2:tags')

// Difference — tags in A not in B
const diff = await redis.sdiff('post:1:tags', 'post:2:tags')

// Random member
const random = await redis.srandmember('post:1:tags', 3) // 3 random

// Count
const count = await redis.scard('post:1:tags')

// Remove
await redis.srem('post:1:tags', 'database')
```

### 1.7 ZSET — Sorted Set (The Powerhouse)

```typescript
// Leaderboard — add scores
await redis.zadd('leaderboard:global', 100, 'user:1')
await redis.zadd('leaderboard:global', 85, 'user:2')
await redis.zadd('leaderboard:global', 95, 'user:3')

// Top 10 (highest to lowest)
const top10 = await redis.zrevrange('leaderboard:global', 0, 9, 'WITHSCORES')

// Bottom 10 (lowest to highest)
const bottom10 = await redis.zrange('leaderboard:global', 0, 9, 'WITHSCORES')

// Get rank (0-indexed)
const rank = await redis.zrevrank('leaderboard:global', 'user:1') // → 0

// Get score
const score = await redis.zscore('leaderboard:global', 'user:1')

// Increment score atomically
await redis.zincrby('leaderboard:global', 10, 'user:1')

// Range by score — get users with scores between 90 and 100
const highScorers = await redis.zrangebyscore('leaderboard:global', 90, 100)

// Count members in score range
const count = await redis.zcount('leaderboard:global', 0, 50)

// Remove by rank — trim leaderboard to top 100
await redis.zremrangebyrank('leaderboard:global', 0, -101)
```

### 1.8 STREAM — Persistent Message Queue

```typescript
// Add entry to stream
const entryId = await redis.xadd(
  'mystream',
  '*', // auto-ID (millisecondsTime-sequenceNumber)
  'field1', 'value1',
  'field2', 'value2'
)

// Read from start
const entries = await redis.xrange('mystream', '-', '+', 'COUNT', 10)

// Read new entries (non-blocking)
const newEntries = await redis.xread('COUNT', 10, 'STREAMS', 'mystream', '0')

// Consumer group
await redis.xgroup('CREATE', 'mystream', 'mygroup', '$', 'MKSTREAM')

// Read as consumer group — pending + new
const messages = await redis.xreadgroup(
  'GROUP', 'mygroup', 'consumer1',
  'COUNT', 10,
  'BLOCK', 2000,
  'STREAMS', 'mystream', '>'
)

// Acknowledge
await redis.xack('mystream', 'mygroup', messageId)

// Check pending entries
const pending = await redis.xpending('mystream', 'mygroup')

// Claim stalled messages (pending > 5 min)
const claimed = await redis.xclaim(
  'mystream', 'mygroup', 'consumer2',
  300000, // min idle time (ms)
  pendingEntryId
)
```

### 1.9 BITMAP — Bit-Level Operations

```typescript
// Track daily active users (bit position = user ID)
await redis.setbit('dau:2026-05-17', 42, 1) // user 42 active
await redis.setbit('dau:2026-05-17', 100, 1)

// Check if user was active
const wasActive = await redis.getbit('dau:2026-05-17', 42)

// Count active users that day
const activeCount = await redis.bitcount('dau:2026-05-17')

// OR across days — users active on any day
await redis.bitop('OR', 'dau:week-20', 'dau:2026-05-17', 'dau:2026-05-18', 'dau:2026-05-19')
const weeklyActive = await redis.bitcount('dau:week-20')
```

### 1.10 HYPERLOGLOG — Approximate Counting

```typescript
// Count unique visitors (0.81% standard error, 12KB constant memory)
await redis.pfadd('visitors:unique', 'ip:192.168.1.1', 'ip:192.168.1.2')
await redis.pfadd('visitors:unique', 'ip:192.168.1.1') // duplicate, ignored

const uniqueCount = await redis.pfcount('visitors:unique')

// Merge multiple HLLs
await redis.pfmerge('visitors:monthly', 'visitors:week1', 'visitors:week2', 'visitors:week3')
```

---

## 2. Redis Stack — Module Extensions

Redis Stack bundles Redis with modules for modern use cases.

### 2.1 RedisJSON — Native JSON Document Store

```typescript
// Requires: redis-om or raw FT.CREATE / JSON.SET
import { Client, Repository, Schema } from 'redis-om'

const client = await new Client().open('redis://localhost:6379')

const userSchema = new Schema('user', {
  name: { type: 'string' },
  email: { type: 'string' },
  age: { type: 'number' },
  address: { type: 'string' },
  tags: { type: 'string[]' },
})

const repository = new Repository(userSchema, client)

// Create
const user = await repository.createAndSave({
  name: 'Alice',
  email: 'alice@example.com',
  age: 30,
  tags: ['redis', 'node'],
})

// Search
const results = await repository.search()
  .where('age').gte(18)
  .where('tags').contains('redis')
  .return.all()

// Raw JSON commands
await redis.call('JSON.SET', 'doc:1', '$', JSON.stringify({ name: 'Alice', nested: { value: 42 } }))
const value = await redis.call('JSON.GET', 'doc:1', '$.nested.value')
// → "42"
```

### 2.2 RedisSearch — Full-Text & Vector Search

```typescript
// Create index (raw)
await redis.call(
  'FT.CREATE', 'idx:users',
  'ON', 'HASH',
  'PREFIX', '1', 'user:',
  'SCHEMA',
  'name', 'TEXT', 'WEIGHT', '2.0',
  'email', 'TEXT',
  'age', 'NUMERIC',
  'role', 'TAG',
)

// Search
const results = await redis.call(
  'FT.SEARCH', 'idx:users',
  '@name:Alice @age:[18 65]',
  'LIMIT', 0, 10
)

// Aggregation — group by role, count
const agg = await redis.call(
  'FT.AGGREGATE', 'idx:users',
  '*',
  'GROUPBY', '1', '@role',
  'REDUCE', 'COUNT', '0', 'AS', 'count'
)

// Drop index
await redis.call('FT.DROPINDEX', 'idx:users')
```

### 2.3 RedisTimeSeries — Time-Series Data

```typescript
// Create time-series with retention policy
await redis.call(
  'TS.CREATE', 'ts:sensor:temp',
  'RETENTION', 86400000, // 24h in ms
  'LABELS', 'sensor_id', 'temp-01', 'type', 'temperature'
)

// Add sample
await redis.call('TS.ADD', 'ts:sensor:temp', '*', 23.5)

// Range query with aggregation
const data = await redis.call(
  'TS.RANGE', 'ts:sensor:temp',
  Date.now() - 3600000, // 1 hour ago
  Date.now(),
  'AGGREGATION', 'avg', 60000 // 1-minute buckets
)

// Multi-key query by label
await redis.call(
  'TS.MRANGE', '-', '+',
  'FILTER', 'type=temperature',
  'AGGREGATION', 'avg', 300000 // 5-min buckets
)
```

### 2.4 RedisGraph — Graph Database

```typescript
// Create graph
await redis.call('GRAPH.QUERY', 'social', 'CREATE (:Person {name: "Alice"})-[:KNOWS]->(:Person {name: "Bob"})')

// Query
const result = await redis.call(
  'GRAPH.QUERY', 'social',
  'MATCH (a:Person)-[:KNOWS]->(b:Person) WHERE a.name = "Alice" RETURN b.name'
)

// Delete graph
await redis.call('GRAPH.DELETE', 'social')
```

### 2.5 RedisBloom — Probabilistic Data Structures

```typescript
// Bloom filter — use for cache-penetration prevention
await redis.call('BF.RESERVE', 'bloom:usernames', 0.01, 1000000) // 1% error, 1M items
await redis.call('BF.ADD', 'bloom:usernames', 'alice')
const mightExist = await redis.call('BF.EXISTS', 'bloom:usernames', 'alice') // → 1

// Cuckoo filter — supports deletion
await redis.call('CF.ADD', 'cf:emails', 'alice@example.com')
await redis.call('CF.DEL', 'cf:emails', 'alice@example.com')

// Count-Min Sketch — frequency estimation
await redis.call('CMS.INCRBY', 'cms:clicks', 'page:/home', 1)
const freq = await redis.call('CMS.QUERY', 'cms:clicks', 'page:/home')

// Top-K — most frequent items
await redis.call('TOPK.ADD', 'topk:searches', 'redis', 'cache')
```

---

## 3. Client Libraries — ioredis vs node-redis

### 3.1 Comparison

| Feature               | ioredis                         | node-redis (v4+)                |
|-----------------------|---------------------------------|----------------------------------|
| **Cluster**           | First-class support             | Supported                        |
| **Sentinel**          | First-class support             | Supported                        |
| **Lua scripting**     | `redis.eval()` + `defineCommand` | `redis.scriptLoad()` + `evalSha()` |
| **Pipeline/transactions**| `redis.pipeline()` / `multi()` | `redis.multi()`                  |
| **Promise API**       | Native promises                 | Native promises                  |
| **Streaming**         | Readable stream interface       | Readable stream interface        |
| **Auto-reconnect**    | Built-in with retry strategy    | Built-in                         |
| **Offline queue**     | Built-in (queues commands while connecting) | Enable with `enableOfflineQueue: true` |
| **Monitor**           | `redis.monitor()`               | `redis.monitor()`                |
| **TypeScript**        | Full types included             | `@types/redis` + v4 types        |
| **Performance**       | Slightly faster in benchmarks   | Comparable                       |
| **Popularity**        | More popular (npm downloads)    | Growing                          |

**Pick ioredis if:** You need Cluster, Sentinel, or Lua `defineCommand` for clean abstractions.

**Pick node-redis if:** You prefer official Redis maintainer library and minimal dependencies.

### 3.2 ioredis — Connection Setup

```typescript
import Redis from 'ioredis'

// Single instance
const redis = new Redis({
  host: 'localhost',
  port: 6379,
  password: 'optional',
  db: 0,
  retryStrategy: (times) => {
    const delay = Math.min(times * 100, 3000) // cap at 3s
    return delay
  },
  maxRetriesPerRequest: 5,
  enableReadyCheck: true,
  lazyConnect: true, // connect manually later
  showFriendlyErrorStack: process.env.NODE_ENV !== 'production',
})

await redis.connect() // only if lazyConnect: true

// Connection events
redis.on('connect', () => console.log('Connected'))
redis.on('ready', () => console.log('Ready'))
redis.on('error', (err) => console.error('Redis error:', err))
redis.on('close', () => console.log('Connection closed'))
redis.on('reconnecting', (delay) => console.log(`Reconnecting in ${delay}ms`))
redis.on('end', () => console.log('Connection ended'))

// Graceful shutdown
async function shutdown() {
  await redis.quit() // wait for pending commands
  process.exit(0)
}
process.on('SIGTERM', shutdown)
```

### 3.3 Connection Pooling with ioredis

```typescript
// ioredis manages a single connection + auto-reconnect
// For high concurrency, use one instance per app — it's internally pipelined

// If you need multi-tenancy (different DBs per tenant):
class RedisPool {
  private tenants: Map<string, Redis> = new Map()

  getForTenant(tenantId: string): Redis {
    if (!this.tenants.has(tenantId)) {
      this.tenants.set(tenantId, new Redis({ db: this.tenantToDb(tenantId) }))
    }
    return this.tenants.get(tenantId)!
  }

  private tenantToDb(tenantId: string): number {
    // Map tenant to DB index (0-15)
    return Math.abs(hash(tenantId)) % 16
  }
}

// For read replicas (primary + replica):
const primary = new Redis(6379, 'primary.redis.internal')
const replica = new Redis(6379, 'replica.redis.internal')

async function getWithFallback<T>(key: string, fallback: () => Promise<T>): Promise<T> {
  try {
    const val = await replica.get(key)
    if (val !== null) return JSON.parse(val)
  } catch { /* fallback to primary */ }
  const val = await primary.get(key)
  if (val !== null) return JSON.parse(val)
  return fallback()
}
```

### 3.4 Redis Sentinel

```
┌─────────────────────────────────────────────────────────────────────┐
│                      REDIS SENTINEL ARCHITECTURE                      │
│                                                                       │
│                          ┌──────────────┐                             │
│                          │  Sentinel-1   │                             │
│                          │  (monitor)    │                             │
│                          └──────┬───────┘                             │
│                                 │                                      │
│            ┌────────────────────┼────────────────────┐                │
│            │                    │                     │                │
│   ┌────────▼───────┐  ┌────────▼───────┐  ┌─────────▼───────┐        │
│   │   Sentinel-2    │  │   Sentinel-3    │  │   Application   │        │
│   │   (quorum vote) │  │   (quorum vote) │  │   (ioredis)     │        │
│   └────────────────┘  └────────────────┘  └────────────────┘          │
│                                 │                                      │
│                                 ▼                                      │
│   ┌──────────────────────────────────────────────────────────┐       │
│   │                  Redis Primary (master)                    │       │
│   │                  sentinel:master=mymaster                  │       │
│   └──────────────────────────────────────────────────────────┘       │
│                            │  replication                              │
│                            ▼                                           │
│   ┌──────────────────────────────────────────────────────────┐       │
│   │               Redis Replica 1 (slave)                     │       │
│   └──────────────────────────────────────────────────────────┘       │
│                            │  replication                              │
│                            ▼                                           │
│   ┌──────────────────────────────────────────────────────────┐       │
│   │               Redis Replica 2 (slave)                     │       │
│   └──────────────────────────────────────────────────────────┘       │
│                                                                       │
│   Failover: Sentinel-1 detects primary down → vote → promote replica │
│   → ioredis detects new master via sentinel pub/sub                  │
└─────────────────────────────────────────────────────────────────────┘
```

```typescript
import Redis from 'ioredis'

const redis = new Redis({
  sentinels: [
    { host: 'sentinel-1.internal', port: 26379 },
    { host: 'sentinel-2.internal', port: 26379 },
    { host: 'sentinel-3.internal', port: 26379 },
  ],
  name: 'mymaster', // sentinel monitor name
  role: 'master', // 'master' for writes, 'slave' for reads
  sentinelPassword: 'optional',
  retryStrategy: (times) => Math.min(times * 100, 3000),
})

// For read-scaling: connect to slave
const readOnly = new Redis({
  sentinels: [
    { host: 'sentinel-1.internal', port: 26379 },
    { host: 'sentinel-2.internal', port: 26379 },
    { host: 'sentinel-3.internal', port: 26379 },
  ],
  name: 'mymaster',
  role: 'slave',
  preferredSlaves: [{ priority: 100, ip: 'replica-1.internal' }],
})
```

### 3.5 Redis Cluster

```
┌─────────────────────────────────────────────────────────────────────┐
│                      REDIS CLUSTER ARCHITECTURE                       │
│                                                                       │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│   │  Node A     │  │  Node B     │  │  Node C     │  │  Node D     │   │
│   │  (master)   │  │  (master)   │  │  (master)   │  │  (master)   │   │
│   │  slots      │  │  slots      │  │  slots      │  │  slots      │   │
│   │  0-4095     │  │  4096-8191  │  │  8192-12287 │  │  12288-16383│   │
│   └─────┬───────┘  └─────┬───────┘  └─────┬───────┘  └─────┬───────┘   │
│         │                 │                 │                 │          │
│   ┌─────▼───────┐  ┌─────▼───────┐  ┌─────▼───────┐  ┌─────▼───────┐   │
│   │  Replica A1  │  │  Replica B1  │  │  Replica C1  │  │  Replica D1  │   │
│   └────────────┘  └────────────┘  └────────────┘  └────────────┘   │
│                                                                       │
│   Gossip protocol: Nodes ping each other, detect failures             │
│   Smart client: ioredisCluster computes slot → node mapping           │
│   MOVED redirect: Client follows slot reassignment                    │
│   ASK redirect: Client retries during resharding                      │
└─────────────────────────────────────────────────────────────────────┘
```

```typescript
import Redis from 'ioredis'

const cluster = new Redis.Cluster(
  [
    { host: 'node-a.internal', port: 6379 },
    { host: 'node-b.internal', port: 6379 },
    { host: 'node-c.internal', port: 6379 },
  ],
  {
    clusterRetryStrategy: (times) => Math.min(times * 100, 2000),
    enableReadyCheck: true,
    scaleReads: 'slave', // read from replicas
    maxRedirections: 16,
    retryDelayOnFailover: 100,
    retryDelayOnClusterDown: 300,
    redisOptions: {
      password: 'optional',
      enableAutoPipelining: true,
    },
  }
)

// Works transparently like a single Redis instance
await cluster.set('key:{hash_tag}', 'value') // hash tags ensure same slot
const val = await cluster.get('key:{hash_tag}')

// Use hash tags {} to co-locate related keys on same node
// Example: user:123:profile and user:123:sessions both on same slot
// Correct: {user:123}:profile, {user:123}:sessions
```

---

## 4. Caching Patterns

### 4.1 Decision Tree

```
Need to cache database results?
  │
  ├─ Read-heavy, tolerate stale data? → Cache-Aside (most common)
  │
  ├─ Write-heavy, need strong consistency? → Write-Through
  │
  ├─ Accept eventual consistency, maximize throughput? → Write-Behind
  │
  ├─ Need to prevent cache stampede? → Cache-Aside + Lock + Probabilistic TTL
  │
  ├─ Multi-level? → L1 (local) + L2 (Redis) + L3 (DB)
```

### 4.2 Cache-Aside (Most Common)

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│  App     │     │  Redis   │     │   DB     │
└────┬────┘     └────┬────┘     └────┬────┘
     │                │                │
     │  1. GET key    │                │
     │───────────────>│                │
     │  2. MISS (nil) │                │
     │<───────────────│                │
     │                │                │
     │  3. SELECT * FROM users WHERE id=1     │
     │───────────────────────────────────────>│
     │  4. result                              │
     │<───────────────────────────────────────│
     │                │                │
     │  5. SET key data EX 300        │
     │───────────────>│                │
     │  6. return data│                │
     │<───────────────│                │
     │                │                │
  Next request:       │                │
     │  7. GET key    │                │
     │───────────────>│                │
     │  8. HIT data   │                │
     │<───────────────│                │
```

```typescript
class CacheAside<T> {
  constructor(
    private redis: Redis,
    private fetch: (key: string) => Promise<T>,
    private ttl = 300,
    private prefix = 'cache:'
  ) {}

  async get(key: string): Promise<T> {
    const cacheKey = `${this.prefix}${key}`
    const cached = await this.redis.get(cacheKey)
    if (cached !== null) {
      return JSON.parse(cached) as T
    }
    const data = await this.fetch(key)
    await this.redis.setex(cacheKey, this.ttl, JSON.stringify(data))
    return data
  }

  async set(key: string, data: T): Promise<void> {
    await this.redis.setex(`${this.prefix}${key}`, this.ttl, JSON.stringify(data))
  }

  async invalidate(key: string): Promise<void> {
    await this.redis.del(`${this.prefix}${key}`)
  }
}

// Usage
const userCache = new CacheAside<User>(
  redis,
  async (id) => db.user.findUnique({ where: { id: Number(id) } }),
  600 // 10 min TTL
)
const user = await userCache.get('1')
```

### 4.3 Read-Through — Cache Is the Authority

```typescript
// Similar to cache-aside, but app always reads from cache.
// If miss, cache internally loads from DB (via library or Lua).
// ioredis doesn't support this natively, but you can implement:

class ReadThroughCache<T> extends CacheAside<T> {
  async get(key: string): Promise<T> {
    const cacheKey = `${this.prefix}${key}`
    const cached = await this.redis.get(cacheKey)
    if (cached !== null) return JSON.parse(cached)
    const data = await this.fetch(key)
    await this.redis.setex(cacheKey, this.ttl, JSON.stringify(data))
    return data
  }
}
```

### 4.4 Write-Through — Write to Cache First

```typescript
class WriteThroughCache<T extends { id: string | number }> {
  constructor(
    private redis: Redis,
    private write: (data: T) => Promise<T>,
    private ttl = 300,
    private prefix = 'cache:'
  ) {}

  async set(key: string, data: T): Promise<T> {
    const saved = await this.write(data) // write to DB first
    await this.redis.setex(`${this.prefix}${key}`, this.ttl, JSON.stringify(saved))
    return saved
  }
}
```

### 4.5 Write-Behind — Async Write to DB

```typescript
class WriteBehindCache<T> {
  private queue: string

  constructor(
    private redis: Redis,
    private persist: (data: T) => Promise<void>,
    private ttl = 300,
    private prefix = 'cache:'
  ) {
    this.queue = `${prefix}write_queue`
  }

  async set(key: string, data: T): Promise<void> {
    // Update cache immediately
    await this.redis.setex(`${this.prefix}${key}`, this.ttl, JSON.stringify(data))
    // Queue async write to DB
    await this.redis.lpush(this.queue, JSON.stringify({ key, data }))
  }

  async processQueue(batchSize = 10): Promise<void> {
    const batch = await this.redis.lrange(this.queue, 0, batchSize - 1)
    if (batch.length === 0) return
    const parsed = batch.map((item) => JSON.parse(item))
    await Promise.all(parsed.map((item) => this.persist(item.data)))
    await this.redis.ltrim(this.queue, batchSize, -1)
  }
}
```

### 4.6 Cache Stampede Prevention

```typescript
class StampedeProtection<T> {
  constructor(
    private redis: Redis,
    private fetch: (key: string) => Promise<T>,
    private ttl = 300,
    private lockTtl = 5, // lock TTL in seconds
    private prefix = 'cache:'
  ) {}

  async get(key: string): Promise<T> {
    const cacheKey = `${this.prefix}${key}`
    const cached = await this.redis.get(cacheKey)
    if (cached !== null) {
      // Probabilistic early expiration — if TTL is almost up, serve stale + refresh
      const ttl = await this.redis.ttl(cacheKey)
      if (ttl > 30) return JSON.parse(cached) // fresh enough

      // Serve stale but refresh in background (only one request refreshes)
      this.refreshInBackground(key)
      return JSON.parse(cached)
    }

    // Cache miss — acquire distributed lock to prevent stampede
    const lockKey = `lock:${key}`
    const lock = await this.redis.set(lockKey, '1', 'EX', this.lockTtl, 'NX')
    if (lock === 'OK') {
      try {
        const data = await this.fetch(key)
        await this.redis.setex(cacheKey, this.ttl, JSON.stringify(data))
        return data
      } finally {
        await this.redis.del(lockKey) // release lock
      }
    }

    // Another request holds the lock — wait and retry
    await new Promise((resolve) => setTimeout(resolve, 200))
    return this.get(key) // recursive retry
  }

  private async refreshInBackground(key: string): Promise<void> {
    const refreshLock = `refresh_lock:${key}`
    const lock = await this.redis.set(refreshLock, '1', 'EX', 10, 'NX')
    if (lock !== 'OK') return // already being refreshed
    try {
      const data = await this.fetch(key)
      await this.redis.setex(`${this.prefix}${key}`, this.ttl, JSON.stringify(data))
    } finally {
      await this.redis.del(refreshLock)
    }
  }
}
```

### 4.7 Cache Invalidation Strategies

| Strategy       | Mechanism                            | Pros                         | Cons                          |
|----------------|--------------------------------------|------------------------------|-------------------------------|
| **TTL**        | Expire after N seconds               | Simple, automatic            | Stale data until expiry       |
| **LRU**        | Redis eviction: `allkeys-lru`        | Automatic memory management  | Unpredictable evictions       |
| **LFU**        | Redis eviction: `allkeys-lfu`        | Keep popular items           | Less popular items evicted    |
| **Manual**     | DEL key on write/update              | Immediate consistency        | Must remember to invalidate   |
| **Write-Through**| Update cache on DB write           | Cache always fresh           | Higher write latency          |
| **Write-Behind**| Async DB write from cache           | Low write latency            | Risk of data loss             |

```typescript
// Manual invalidation pattern — delete cache keys matching pattern
async function invalidatePattern(pattern: string): Promise<void> {
  // NEVER use KEYS in production — use SCAN
  let cursor = '0'
  do {
    const [nextCursor, keys] = await redis.scan(cursor, 'MATCH', pattern, 'COUNT', 100)
    cursor = nextCursor
    if (keys.length > 0) {
      await redis.del(...keys)
    }
  } while (cursor !== '0')
}
```

---

## 5. Session Management

### 5.1 Session Store with Redis

```typescript
// Express session with connect-redis
import session from 'express-session'
import RedisStore from 'connect-redis'
import Redis from 'ioredis'

const redis = new Redis()
const redisStore = new RedisStore({
  client: redis,
  prefix: 'sess:', // key namespace
  ttl: 86400, // 24h (seconds)
  disableTouch: false, // refresh TTL on access
})

app.use(session({
  store: redisStore,
  secret: process.env.SESSION_SECRET!,
  name: 'sid', // cookie name
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 24 * 60 * 60 * 1000, // 24h
  },
}))
```

### 5.2 Custom Session Store (ioredis)

```typescript
interface SessionData {
  userId: number
  role: string
  createdAt: string
  lastAccess: string
}

class SessionStore {
  constructor(
    private redis: Redis,
    private prefix = 'sess:',
    private defaultTtl = 86400
  ) {}

  async create(sessionId: string, data: SessionData): Promise<void> {
    await this.redis.hset(`${this.prefix}${sessionId}`, data as any)
    await this.redis.expire(`${this.prefix}${sessionId}`, this.defaultTtl)
  }

  async get(sessionId: string): Promise<SessionData | null> {
    const data = await this.redis.hgetall(`${this.prefix}${sessionId}`)
    if (!data || Object.keys(data).length === 0) return null
    // Refresh TTL on access
    await this.redis.expire(`${this.prefix}${sessionId}`, this.defaultTtl)
    return data as unknown as SessionData
  }

  async update(sessionId: string, data: Partial<SessionData>): Promise<void> {
    await this.redis.hset(`${this.prefix}${sessionId}`, data as any)
    await this.redis.expire(`${this.prefix}${sessionId}`, this.defaultTtl)
  }

  async destroy(sessionId: string): Promise<void> {
    await this.redis.del(`${this.prefix}${sessionId}`)
  }

  async touch(sessionId: string): Promise<void> {
    await this.redis.expire(`${this.prefix}${sessionId}`, this.defaultTtl)
  }

  // Session rotation — invalidate old, create new
  async rotate(oldSessionId: string, newSessionId: string, data: SessionData): Promise<void> {
    const multi = this.redis.multi()
    multi.del(`${this.prefix}${oldSessionId}`)
    multi.hset(`${this.prefix}${newSessionId}`, data as any)
    multi.expire(`${this.prefix}${newSessionId}`, this.defaultTtl)
    await multi.exec()
  }
}
```

### 5.3 Session Rotation (Security Best Practice)

```typescript
// After login, rotate session ID to prevent session fixation
app.post('/login', async (req, res) => {
  const user = await authenticate(req.body)
  if (!user) return res.status(401).send('Invalid credentials')

  // Regenerate session ID
  req.session.regenerate(async (err) => {
    if (err) return res.status(500).send('Session error')
    req.session.userId = user.id
    req.session.role = user.role
    res.json({ ok: true })
  })
})
```

---

## 6. Rate Limiting

### 6.1 Fixed Window Counter

```typescript
// Simple but has boundary problem (burst at window edge)
// Redis: INCR + EXPIRE

async function fixedWindowRateLimit(
  key: string,
  maxRequests: number,
  windowSeconds: number
): Promise<{ allowed: boolean; remaining: number; resetAt: number }> {
  const windowKey = `ratelimit:${key}:${Math.floor(Date.now() / (windowSeconds * 1000))}`
  const count = await redis.incr(windowKey)
  if (count === 1) {
    await redis.expire(windowKey, windowSeconds)
  }
  const ttl = await redis.ttl(windowKey)
  return {
    allowed: count <= maxRequests,
    remaining: Math.max(0, maxRequests - count),
    resetAt: Date.now() + ttl * 1000,
  }
}
```

### 6.2 Sliding Window Log (ZSET)

```typescript
// Uses sorted set with timestamp as score, removes old entries
// Atomic with Lua for correct multi-client behavior

const slidingWindowLua = `
  local key = KEYS[1]
  local now = tonumber(ARGV[1])
  local window = tonumber(ARGV[2])
  local max = tonumber(ARGV[3])
  local windowStart = now - window

  -- Remove old entries outside window
  redis.call('ZREMRANGEBYSCORE', key, 0, windowStart)

  -- Count entries in current window
  local count = redis.call('ZCARD', key)

  if count < max then
    redis.call('ZADD', key, now, now .. ':' .. math.random())
    redis.call('EXPIRE', key, math.ceil(window / 1000))
    return {1, max - count - 1}
  else
    -- Return remaining time until oldest entry expires
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local resetIn = math.ceil((tonumber(oldest[2]) + window - now) / 1000)
    return {0, 0, resetIn}
  end
`

// Register as ioredis command
redis.defineCommand('slidingWindowRateLimit', {
  numberOfKeys: 1,
  lua: slidingWindowLua,
})

async function slidingWindowRateLimit(
  key: string,
  maxRequests: number,
  windowMs: number
): Promise<{ allowed: boolean; remaining: number; resetIn: number }> {
  const result = await (redis as any).slidingWindowRateLimit(
    key,
    Date.now(),
    windowMs,
    maxRequests
  )
  return {
    allowed: result[0] === 1,
    remaining: result[1],
    resetIn: result[2] || 0,
  }
}
```

### 6.3 Token Bucket (Lua)

```typescript
const tokenBucketLua = `
  local key = KEYS[1]
  local now = tonumber(ARGV[1])
  local capacity = tonumber(ARGV[2])
  local refillRate = tonumber(ARGV[3])   -- tokens per second
  local refillInterval = tonumber(ARGV[4]) -- how often to refill (ms)
  local cost = tonumber(ARGV[5])

  -- Get current state
  local state = redis.call('HMGET', key, 'tokens', 'last_refill')
  local tokens = tonumber(state[1])
  local lastRefill = tonumber(state[2])

  if tokens == nil then
    -- First request — start full
    tokens = capacity
    lastRefill = now
  end

  -- Calculate tokens to add since last refill
  local elapsed = now - lastRefill
  local refills = math.floor(elapsed / refillInterval)
  if refills > 0 then
    tokens = math.min(capacity, tokens + refills * refillRate)
    lastRefill = lastRefill + refills * refillInterval
  end

  -- Try to consume
  if tokens >= cost then
    tokens = tokens - cost
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', lastRefill)
    redis.call('EXPIRE', key, math.ceil(capacity / refillRate) + 1)
    return {1, tokens}
  else
    local waitMs = math.ceil((cost - tokens) / refillRate * refillInterval)
    return {0, tokens, waitMs}
  end
`

redis.defineCommand('tokenBucketRateLimit', {
  numberOfKeys: 1,
  lua: tokenBucketLua,
})
```

### 6.4 Leaky Bucket (Lua)

```typescript
const leakyBucketLua = `
  local key = KEYS[1]
  local now = tonumber(ARGV[1])
  local capacity = tonumber(ARGV[2])
  local leakRate = tonumber(ARGV[3])    -- requests per second
  local leakInterval = tonumber(ARGV[4]) -- ms between leaks

  -- State: current water level, last leak time
  local state = redis.call('HMGET', key, 'water', 'last_leak')
  local water = tonumber(state[1])
  local lastLeak = tonumber(state[2])

  if water == nil then
    water = 0
    lastLeak = now
  end

  -- Leak water based on time elapsed
  local elapsed = now - lastLeak
  local leaked = math.floor(elapsed / leakInterval)
  if leaked > 0 then
    water = math.max(0, water - leaked * leakRate)
    lastLeak = lastLeak + leaked * leakInterval
  end

  -- Try to add request
  if water < capacity then
    water = water + 1
    redis.call('HMSET', key, 'water', water, 'last_leak', lastLeak)
    redis.call('EXPIRE', key, math.ceil(capacity / leakRate) + 1)
    return {1, water}
  else
    local waitMs = math.ceil((water - capacity + 1) * leakInterval / leakRate)
    return {0, water, waitMs}
  end
`
```

### 6.5 Rate Limiter Middleware (Express)

```typescript
import rateLimit from 'express-rate-limit'
import RedisStore from 'rate-limit-redis'

const limiter = rateLimit({
  store: new RedisStore({
    sendCommand: (...args: string[]) => redis.call(...args),
    prefix: 'rl:',
  }),
  windowMs: 60 * 1000, // 1 minute
  max: 100, // 100 requests per minute
  standardHeaders: true,
  legacyHeaders: false,
  handler: (req, res) => {
    res.status(429).json({
      error: 'Too many requests',
      retryAfter: Math.ceil(60 - (Date.now() / 1000) % 60),
    })
  },
})

app.use('/api/', limiter)
```

---

## 7. Pub/Sub & Messaging

### 7.1 Pub/Sub Channels (Fire-and-Forget)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      REDIS PUB/SUB ARCHITECTURE                       │
│                                                                       │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐   │
│   │ Publisher  │     │ Subscriber│    │ Subscriber│    │ Subscriber│   │
│   │ (App A)    │     │ (App B)   │    │ (App C)   │    │ (App D)   │   │
│   └─────┬──────┘     └─────┬──────┘    └─────┬──────┘    └─────┬──────┘   │
│         │                  │                  │                  │       │
│         │     PUBLISH      │     SUBSCRIBE    │     SUBSCRIBE    │       │
│         │     channel:     │     channel:     │     channel:     │       │
│         │   'orders:new'   │   'orders:new'   │   'orders:new'   │       │
│         │                  │                  │                  │       │
│         └──────────────────┼──────────────────┼──────────────────┘       │
│                            ▼                  ▼                          │
│                     ┌────────────────────────────────────┐               │
│                     │         Redis Pub/Sub Engine         │               │
│                     │  (no persistence, no ack, fan-out)  │               │
│                     └────────────────────────────────────┘               │
│                                                                           │
│   NOTE: No message persistence. If subscriber is offline, message lost.  │
│   For durable messaging → use Redis Streams                              │
└─────────────────────────────────────────────────────────────────────┘
```

```typescript
// Publisher (any Redis instance)
const publisher = new Redis()
await publisher.publish('orders:new', JSON.stringify({ orderId: 123, amount: 99.99 }))

// Subscriber (dedicated connection — cannot use same connection for other ops)
const subscriber = new Redis()
subscriber.subscribe('orders:new', 'orders:cancelled', (err, count) => {
  if (err) console.error('Subscribe error:', err)
  else console.log(`Subscribed to ${count} channels`)
})

subscriber.on('message', (channel, message) => {
  const data = JSON.parse(message)
  console.log(`[${channel}]`, data)
})

// Pattern subscription
subscriber.psubscribe('orders:*')
subscriber.on('pmessage', (pattern, channel, message) => {
  console.log(`[${pattern}] matched [${channel}]`)
})

// Unsubscribe
await subscriber.unsubscribe('orders:new')
await subscriber.punsubscribe('orders:*')
```

### 7.2 Redis Streams — Durable Messaging

```
┌─────────────────────────────────────────────────────────────────────┐
│                      REDIS STREAMS ARCHITECTURE                       │
│                                                                       │
│   ┌────────────────────────────────────────────────────────────────┐  │
│   │                        STREAM                                    │  │
│   │   "orders:stream"                                               │  │
│   │                                                                  │  │
│   │   1712345678000-0 → {orderId: 1, status: "created"}            │  │
│   │   1712345679000-0 → {orderId: 2, status: "created"}            │  │
│   │   1712345680000-0 → {orderId: 3, status: "created"}  ← last   │  │
│   └────────────────────────────────────────────────────────────────┘  │
│                                  │                                     │
│        ┌─────────────────────────┴────────────────────────┐           │
│        ▼                                                    ▼           │
│   ┌──────────────┐                                    ┌──────────────┐│
│   │ Consumer Group │                                    │ Consumer Group │
│   │ "email-group"  │                                    │ "sms-group"    ││
│   │                │                                    │                ││
│   │ consumer-1     │                                    │ consumer-1     ││
│   │ consumer-2     │                                    │ consumer-2     ││
│   │ consumer-3     │                                    │                ││
│   └────────────────┘                                    └────────────────┘│
│                                                                           │
│   Each message goes to ONE consumer in the group (competing consumers)    │
│   Messages persist until XDEL or XTRIM                                   │
│   Pending Entries List (PEL) ensures at-least-once delivery              │
└─────────────────────────────────────────────────────────────────────┘
```

```typescript
// Producer
async function produceOrderEvent(order: any): Promise<string> {
  return redis.xadd(
    'orders:stream',
    '*', // auto-generated ID (timestamp-seq)
    'orderId', String(order.id),
    'amount', String(order.amount),
    'status', 'created',
    'timestamp', new Date().toISOString()
  )
}

// Consumer group setup
async function setupConsumerGroup(): Promise<void> {
  try {
    await redis.xgroup('CREATE', 'orders:stream', 'email-service', '0', 'MKSTREAM')
  } catch (err: any) {
    // BUSYGROUP means group already exists
    if (!err.message.includes('BUSYGROUP')) throw err
  }
}

// Consumer
async function consumeOrders(
  group: string,
  consumer: string,
  batchSize = 10,
  blockMs = 2000
): Promise<void> {
  while (true) {
    try {
      const result = await redis.xreadgroup(
        'GROUP', group, consumer,
        'COUNT', batchSize,
        'BLOCK', blockMs,
        'STREAMS', 'orders:stream', '>'
      )

      if (!result) continue // timeout, no messages

      for (const [stream, messages] of result) {
        for (const [id, fields] of messages) {
          const order = Object.fromEntries(
            fields.reduce((acc: any[], val: string, i: number) => {
              if (i % 2 === 0) acc.push([val, fields[i + 1]])
              return acc
            }, [])
          )

          try {
            // Process message
            await processOrder(order)
            // Acknowledge — message is removed from PEL
            await redis.xack('orders:stream', group, id)
          } catch (err) {
            console.error(`Failed to process order ${id}:`, err)
            // Don't ack — it stays in PEL for retry
          }
        }
      }
    } catch (err) {
      console.error('Consumer error:', err)
      await new Promise((r) => setTimeout(r, 1000))
    }
  }
}

// Claim stalled messages (other consumers that crashed)
async function claimStalled(group: string, consumer: string, minIdleMs = 300000): Promise<void> {
  const pending = await redis.xpending('orders:stream', group)
  if (!pending || pending.pending === 0) return

  // Get pending entries
  const entries = await redis.xpending(
    'orders:stream', group, '-', '+', 100
  )

  for (const entry of entries) {
    if (entry[1] > minIdleMs) { // idle for > 5 min
      const claimed = await redis.xclaim(
        'orders:stream', group, consumer, minIdleMs, entry[0], 'JUSTID'
      )
      if (claimed.length > 0) {
        // Re-process
        console.log(`Claimed stalled message: ${entry[0]}`)
      }
    }
  }
}
```

### 7.3 Work Queue Pattern (Stream)

```typescript
class WorkQueue {
  constructor(
    private redis: Redis,
    private stream: string,
    private group: string,
    private consumer: string
  ) {}

  async enqueue(data: any): Promise<string> {
    return redis.xadd(
      this.stream, '*',
      'payload', JSON.stringify(data),
      'enqueued_at', Date.now().toString()
    )
  }

  async process(batchSize = 1, blockMs = 5000): Promise<void> {
    const result = await redis.xreadgroup(
      'GROUP', this.group, this.consumer,
      'COUNT', batchSize,
      'BLOCK', blockMs,
      'STREAMS', this.stream, '>'
    )

    if (!result) return

    for (const [, messages] of result) {
      for (const [id, fields] of messages) {
        const payload = JSON.parse(fields[1]!)
        try {
          await this.handle(payload)
          await this.ack(id)
        } catch (err) {
          await this.nack(id, err)
        }
      }
    }
  }

  private async ack(id: string): Promise<void> {
    await redis.xack(this.stream, this.group, id)
  }

  private async nack(id: string, error: any): Promise<void> {
    // Log failure, don't ack — message stays in PEL
    console.error(`Failed message ${id}:`, error)
    // Optionally: move to dead-letter stream
    await redis.xadd(
      `${this.stream}:dead`, '*',
      'original_id', id,
      'error', error.message,
      'failed_at', Date.now().toString()
    )
  }
}
```

---

## 8. Background Jobs — BullMQ

### 8.1 Queue Setup

```typescript
import { Queue, Worker, Job, QueueScheduler } from 'bullmq'
import Redis from 'ioredis'

const connection = new Redis({
  host: 'localhost',
  port: 6379,
  maxRetriesPerRequest: null, // BullMQ manages retries
})

// Queue
const emailQueue = new Queue('email', {
  connection,
  defaultJobOptions: {
    attempts: 3,
    backoff: { type: 'exponential', delay: 2000 },
    removeOnComplete: { age: 86400, count: 1000 }, // keep 24h or 1000 completed
    removeOnFail: { age: 604800 }, // keep failed for 7 days
  },
})

// Producer
await emailQueue.add('send-welcome', {
  userId: 42,
  email: 'user@example.com',
  template: 'welcome',
})

// Delayed job (+5 minutes)
await emailQueue.add('send-reminder', { userId: 42 }, { delay: 300000 })

// Repeatable job (cron)
await emailQueue.add('daily-digest', {}, {
  repeat: {
    pattern: '0 8 * * *', // every day at 08:00
    tz: 'Asia/Jakarta',
  },
})

// Job with priority
await emailQueue.add('urgent-notification', { alertId: 1 }, {
  priority: 10, // lower = higher priority
})
```

### 8.2 Worker

```typescript
const worker = new Worker(
  'email',
  async (job: Job) => {
    switch (job.name) {
      case 'send-welcome':
        await sendEmail(job.data.email, 'Welcome!', renderTemplate(job.data.template))
        break
      case 'send-reminder':
        await sendEmail(job.data.email, 'Reminder', 'Don\'t forget!')
        break
      case 'daily-digest':
        const digest = await generateDigest()
        await broadcastEmail(digest)
        break
      default:
        console.warn(`Unknown job: ${job.name}`)
    }
  },
  {
    connection,
    concurrency: 20, // process 20 jobs in parallel
    limiter: {
      max: 100, // max jobs
      duration: 1000, // per second
    },
    lockDuration: 30000, // job lock time (ms)
    stalledInterval: 30000, // check stalled jobs every 30s
    maxStalledCount: 3, // max times a job can be stalled
  }
)

// Job lifecycle events
worker.on('completed', (job: Job) => {
  console.log(`Job ${job.id} completed in ${job.finishedOn! - job.processedOn!}ms`)
})

worker.on('failed', (job: Job | undefined, err: Error) => {
  console.error(`Job ${job?.id} failed:`, err.message)
})

worker.on('progress', (job: Job, progress: number) => {
  console.log(`Job ${job.id} is ${progress}% complete`)
})

worker.on('stalled', (jobId: string) => {
  console.warn(`Job ${jobId} stalled — being retried`)
})

// Graceful shutdown
async function shutdown() {
  await worker.close()
  await emailQueue.close()
  await connection.quit()
}
```

### 8.3 Job Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                      BULLMQ JOB LIFECYCLE                             │
│                                                                       │
│   ┌──────────┐                                                        │
│   │   Added   │ ──── add()                                            │
│   └────┬─────┘                                                        │
│        │                                                               │
│        ▼                                                               │
│   ┌──────────┐     ┌───────────┐                                      │
│   │  Waiting  │────>│  Delayed   │ (if delay > 0)                      │
│   └────┬─────┘     └───────────┘                                      │
│        │                                                               │
│        ▼                                                               │
│   ┌──────────┐                                                        │
│   │  Active   │ ──── worker picks up                                   │
│   └────┬─────┘                                                        │
│        │                                                               │
│   ┌────┴────┐                                                         │
│   │         │                                                         │
│   ▼         ▼                                                         │
│ ┌──────┐  ┌──────┐                                                    │
│ │Completed│ │ Failed │ ──── retry if attempts < maxAttempts → Waiting  │
│ └──────┘  └──────┘          else → Waiting (for delayed retry)        │
│              │                                                         │
│              ▼                                                         │
│         ┌──────────┐                                                  │
│         │Unrecoverable│ ──── removeOnFail or manual intervention       │
│         └──────────┘                                                  │
│                                                                       │
│   States (in Redis as a ZSET):                                        │
│   bull:email:wait     → List     (FIFO)                               │
│   bull:email:active   → Set      (being processed)                    │
│   bull:email:delayed  → ZSet     (score = timestamp)                  │
│   bull:email:completed→ ZSet     (score = timestamp)                  │
│   bull:email:failed   → ZSet     (score = timestamp)                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.4 Job Events & Observability

```typescript
// Listen to global events (across all workers)
const queueEvents = new QueueEvents('email', { connection })

queueEvents.on('completed', ({ jobId, returnvalue }) => {
  console.log(`Job ${jobId} completed with:`, returnvalue)
})

queueEvents.on('failed', ({ jobId, failedReason }) => {
  console.log(`Job ${jobId} failed:`, failedReason)
})

queueEvents.on('progress', ({ jobId, data }) => {
  console.log(`Job ${jobId}: ${data}%`)
})

queueEvents.on('delayed', ({ jobId }) => {
  console.log(`Job ${jobId} delayed`)
})

// Get job counts
const counts = await emailQueue.getJobCounts()
// { waiting: 5, active: 2, completed: 100, failed: 1, delayed: 3 }

// Get jobs by state
const failedJobs = await emailQueue.getJobs('failed', 0, 10)

// Get job details
const job = await emailQueue.getJob('jobId')
if (job) {
  console.log(job.data, job.attemptsMade, job.finishedOn)
  await job.retry() // Retry a failed job
  await job.remove() // Remove from queue
}
```

---

## 9. Leaderboard & Counting

### 9.1 Real-Time Leaderboard

```typescript
class Leaderboard {
  constructor(
    private redis: Redis,
    private key: string
  ) {}

  async submit(playerId: string, score: number): Promise<number> {
    return redis.zadd(this.key, score, playerId)
  }

  async incrementScore(playerId: string, delta: number): Promise<number> {
    return redis.zincrby(this.key, delta, playerId)
  }

  async top(n: number): Promise<Array<{ playerId: string; score: number; rank: number }>> {
    const results = await redis.zrevrange(this.key, 0, n - 1, 'WITHSCORES')
    const entries: Array<{ playerId: string; score: number; rank: number }> = []
    for (let i = 0; i < results.length; i += 2) {
      entries.push({
        playerId: results[i],
        score: Number(results[i + 1]),
        rank: i / 2,
      })
    }
    return entries
  }

  async aroundPlayer(playerId: string, radius = 5): Promise<any[]> {
    const rank = await redis.zrevrank(this.key, playerId)
    if (rank === null) return []
    const start = Math.max(0, rank - radius)
    const end = rank + radius
    const results = await redis.zrevrange(this.key, start, end, 'WITHSCORES')
    const entries = []
    for (let i = 0; i < results.length; i += 2) {
      entries.push({
        playerId: results[i],
        score: Number(results[i + 1]),
        rank: start + i / 2,
      })
    }
    return entries
  }

  async playerRank(playerId: string): Promise<{ rank: number; score: number } | null> {
    const [rank, score] = await Promise.all([
      redis.zrevrank(this.key, playerId),
      redis.zscore(this.key, playerId),
    ])
    if (rank === null || score === null) return null
    return { rank: rank + 1, score }
  }

  async totalPlayers(): Promise<number> {
    return redis.zcard(this.key)
  }

  async removePlayer(playerId: string): Promise<number> {
    return redis.zrem(this.key, playerId)
  }
}
```

### 9.2 Atomic Counters

```typescript
class Counter {
  constructor(private redis: Redis, private prefix = 'counter:') {}

  async increment(key: string, amount = 1): Promise<number> {
    return redis.incrby(`${this.prefix}${key}`, amount)
  }

  async decrement(key: string, amount = 1): Promise<number> {
    return redis.decrby(`${this.prefix}${key}`, amount)
  }

  async get(key: string): Promise<number> {
    const val = await redis.get(`${this.prefix}${key}`)
    return val !== null ? Number(val) : 0
  }

  async reset(key: string): Promise<void> {
    await redis.del(`${this.prefix}${key}`)
  }

  // Atomic counter with expiry for daily/monthly counts
  async incrementWithExpiry(key: string, ttl: number, amount = 1): Promise<number> {
    const multi = redis.multi()
    multi.incrby(`${this.prefix}${key}`, amount)
    multi.expire(`${this.prefix}${key}`, ttl)
    const results = await multi.exec()
    return results?.[0]?.[1] as number ?? 0
  }
}

// Usage: daily active users count
const counter = new Counter(redis)
const today = new Date().toISOString().slice(0, 10)
await counter.incrementWithExpiry(`dau:${today}`, 86400)
```

### 9.3 Rate of Change — Tracking Velocity

```typescript
async function trackVelocity(
  metric: string,
  value: number,
  windowSeconds: number
): Promise<{ count: number; rate: number }> {
  const now = Date.now()
  const key = `velocity:${metric}`
  const windowStart = now - windowSeconds * 1000

  // Add data point
  await redis.zadd(key, now, `${now}:${Math.random()}`)
  await redis.expire(key, windowSeconds + 60)

  // Remove old data
  await redis.zremrangebyscore(key, 0, windowStart)

  // Count in window
  const count = await redis.zcard(key)
  return {
    count,
    rate: count / windowSeconds,
  }
}
```

---

## 10. Distributed Locking

### 10.1 Simple Lock (SET NX EX)

```typescript
class SimpleLock {
  constructor(private redis: Redis, private prefix = 'lock:') {}

  async acquire(resource: string, ttlMs = 30000): Promise<string | null> {
    const lockKey = `${this.prefix}${resource}`
    const token = crypto.randomUUID() // unique token for safe release
    const result = await redis.set(lockKey, token, 'PX', ttlMs, 'NX')
    return result === 'OK' ? token : null
  }

  async release(resource: string, token: string): Promise<boolean> {
    // Lua script ensures only the owner can release
    const script = `
      if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
      else
        return 0
      end
    `
    const result = await redis.eval(script, 1, `${this.prefix}${resource}`, token)
    return result === 1
  }

  async execute<T>(
    resource: string,
    task: () => Promise<T>,
    ttlMs = 30000
  ): Promise<T> {
    const token = await this.acquire(resource, ttlMs)
    if (!token) throw new Error(`Could not acquire lock for ${resource}`)
    try {
      return await task()
    } finally {
      await this.release(resource, token)
    }
  }
}
```

### 10.2 Lock with Auto-Renewal

```typescript
class AutoRenewingLock {
  private lockKey: string
  private token: string
  private renewTimer: NodeJS.Timeout | null = null
  private ttlMs: number

  constructor(
    private redis: Redis,
    resource: string,
    ttlMs = 30000,
    private prefix = 'lock:'
  ) {
    this.lockKey = `${prefix}${resource}`
    this.token = crypto.randomUUID()
    this.ttlMs = ttlMs
  }

  async acquire(): Promise<boolean> {
    const result = await redis.set(this.lockKey, this.token, 'PX', this.ttlMs, 'NX')
    if (result === 'OK') {
      this.startRenewal()
      return true
    }
    return false
  }

  private startRenewal(): void {
    // Renew at 1/3 of TTL
    const interval = Math.floor(this.ttlMs / 3)
    this.renewTimer = setInterval(async () => {
      const script = `
        if redis.call("GET", KEYS[1]) == ARGV[1] then
          return redis.call("PEXPIRE", KEYS[1], ARGV[2])
        else
          return 0
        end
      `
      await redis.eval(script, 1, this.lockKey, this.token, this.ttlMs)
    }, interval)
  }

  async release(): Promise<void> {
    if (this.renewTimer) clearInterval(this.renewTimer)
    const script = `
      if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
      else
        return 0
      end
    `
    await redis.eval(script, 1, this.lockKey, this.token)
  }
}
```

### 10.3 Redlock Algorithm

```typescript
interface RedisInstance {
  host: string
  port: number
}

class Redlock {
  private instances: Redis[]
  private quorum: number

  constructor(instances: RedisInstance[]) {
    this.instances = instances.map((i) => new Redis(i))
    this.quorum = Math.floor(instances.length / 2) + 1
  }

  async acquire(resource: string, ttlMs: number): Promise<string | null> {
    const token = crypto.randomUUID()
    const start = Date.now()
    let acquired = 0

    await Promise.all(
      this.instances.map(async (redis) => {
        try {
          const result = await redis.set(resource, token, 'PX', ttlMs, 'NX')
          if (result === 'OK') acquired++
        } catch { /* ignore failed instance */ }
      })
    )

    const elapsed = Date.now() - start
    if (acquired >= this.quorum && elapsed < ttlMs) {
      return token
    }

    // Release partial locks
    await this.release(resource, token)
    return null
  }

  async release(resource: string, token: string): Promise<void> {
    const script = `
      if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
      else
        return 0
      end
    `
    await Promise.all(
      this.instances.map((redis) =>
        redis.eval(script, 1, resource, token).catch(() => {})
      )
    )
  }
}
```

---

## 11. Performance

### 11.1 Pipelining

```typescript
// Without pipeline — N round trips
for (const id of userIds) {
  await redis.get(`user:${id}`)
}

// With pipeline — 1 round trip
const pipeline = redis.pipeline()
for (const id of userIds) {
  pipeline.get(`user:${id}`)
}
const results = await pipeline.exec()
// results = [[null, 'value1'], [null, 'value2'], ...]

// Automatic pipelining (ioredis Cluster)
const cluster = new Redis.Cluster([{ host: '...', port: 6379 }], {
  enableAutoPipelining: true,
  autoPipeliningIgnoredCommands: ['ping'],
})
```

### 11.2 Batching with MULTI/EXEC

```typescript
// Transaction — atomic batch
const multi = redis.multi()
multi.set('key:1', 'value1')
multi.set('key:2', 'value2')
multi.set('key:3', 'value3')
multi.incr('counter')
multi.expire('key:1', 300)
const [set1, set2, set3, incr, exp1] = await multi.exec()

// Conditional transaction with WATCH
async function transfer(from: string, to: string, amount: number): Promise<boolean> {
  const retries = 3
  for (let i = 0; i < retries; i++) {
    await redis.watch(from, to)
    const [fromBal, toBal] = await Promise.all([
      redis.get(from).then(Number),
      redis.get(to).then(Number),
    ])
    if (fromBal < amount) {
      await redis.unwatch()
      return false
    }
    const multi = redis.multi()
    multi.decrby(from, amount)
    multi.incrby(to, amount)
    const results = await multi.exec()
    if (results !== null) return true // success
    // results === null → WATCH triggered, retry
  }
  return false
}
```

### 11.3 Connection Pooling

```typescript
// Best practice: single ioredis instance per app
// ioredis uses a connection pool internally (single TCP connection + command queue)
// For high throughput, this is sufficient

// For multi-tenancy or DB isolation:
class RedisManager {
  private pools: Map<number, Redis> = new Map()

  getDatabase(db: number): Redis {
    if (!this.pools.has(db)) {
      this.pools.set(db, new Redis({
        port: 6379,
        host: 'localhost',
        db,
        lazyConnect: true,
      }))
    }
    return this.pools.get(db)!
  }

  async connectAll(): Promise<void> {
    await Promise.all(
      Array.from(this.pools.values()).map((r) => r.connect())
    )
  }

  async disconnectAll(): Promise<void> {
    await Promise.all(
      Array.from(this.pools.values()).map((r) => r.quit())
    )
    this.pools.clear()
  }
}
```

### 11.4 Monitoring with Redis INFO

```typescript
async function getRedisHealth(): Promise<{
  connectedClients: number
  memoryUsed: number
  totalCommands: number
  hits: number
  misses: number
  hitRate: string
  opsPerSecond: number
  latencyPercentiles: Record<string, number>
}> {
  // Get full INFO
  const info = await redis.info()

  // Get specific sections
  const stats = await redis.info('stats')
  const memory = await redis.info('memory')
  const clients = await redis.info('clients')
  const keyspace = await redis.info('keyspace')
  const commandstats = await redis.info('commandstats')

  // Parse key metrics
  const totalCommands = parseInt(stats.match(/total_commands_processed:(\d+)/)?.[1] ?? '0', 10)
  const opsPerSecond = parseInt(stats.match(/instantaneous_ops_per_sec:(\d+)/)?.[1] ?? '0', 10)
  const hits = parseInt(stats.match(/keyspace_hits:(\d+)/)?.[1] ?? '0', 10)
  const misses = parseInt(stats.match(/keyspace_misses:(\d+)/)?.[1] ?? '0', 10)

  return {
    connectedClients: parseInt(clients.match(/connected_clients:(\d+)/)?.[1] ?? '0', 10),
    memoryUsed: parseInt(memory.match(/used_memory_human:(\d+)/)?.[1] ?? '0', 10),
    totalCommands,
    hits,
    misses,
    hitRate: ((hits / (hits + misses)) * 100).toFixed(2) + '%',
    opsPerSecond,
    latencyPercentiles: {}, // Use LATENCY HISTOGRAM for this
  }
}
```

### 11.5 Slow Log Analysis

```typescript
// Configure slow log (in redis.conf or CONFIG SET)
// slowlog-log-slower-than 10000 (10ms)
// slowlog-max-len 128

// Get slow queries
async function getSlowQueries(count = 128): Promise<any[]> {
  const slowLogs = await redis.call('SLOWLOG', 'GET', count)
  return (slowLogs as any[]).map((entry: any) => ({
    id: entry[0],
    timestamp: new Date(entry[1] * 1000).toISOString(),
    durationUs: entry[2],
    command: entry[3]?.join(' ') ?? '',
    client: entry[4],
    clientName: entry[5],
  }))
}

// Reset slow log
await redis.call('SLOWLOG', 'RESET')
```

### 11.6 Memory Analysis

```typescript
async function analyzeMemory(): Promise<void> {
  // Memory usage of a key
  const size = await redis.call('MEMORY', 'USAGE', 'user:1')
  console.log(`Memory used by user:1: ${size} bytes`)

  // Memory doctor
  const diagnosis = await redis.call('MEMORY', 'DOCTOR')
  console.log(diagnosis)

  // Memory stats
  const memStats = await redis.call('MEMORY', 'STATS')
  console.log(memStats)

  // Find largest keys
  let cursor = '0'
  const largeKeys: Array<{ key: string; type: string; size: number }> = []
  do {
    const [nextCursor, keys] = await redis.scan(cursor, 'COUNT', 1000)
    cursor = nextCursor
    for (const key of keys) {
      const size = await redis.call('MEMORY', 'USAGE', key) as number
      if (size > 1024 * 100) { // > 100KB
        const type = await redis.type(key)
        largeKeys.push({ key: key as string, type, size })
      }
    }
  } while (cursor !== '0')

  // Sort by size descending
  largeKeys.sort((a, b) => b.size - a.size)
  console.log('Large keys:', largeKeys.slice(0, 20))
}
```

---

## 12. Persistence

### 12.1 RDB vs AOF Decision Tree

```
Need persistence?
  ├─ No → disable both (max performance)
  │      save "" in redis.conf
  │      appendonly no
  │
  ├─ Accept up to last backup loss?
  │   Use RDB (default)
  │   └─ Pros: Compact, fast restart, good for backups
  │   └─ Cons: Lose up to last save interval (5-60 min default)
  │   └─ config: save 900 1 save 300 10 save 60 10000
  │
  ├─ Need second-level durability?
  │   Use AOF
  │   └─ appendonly yes
  │   └─ appendfsync everysec (best trade-off)
  │   └─ Pros: Durable (1s max loss), append-only log
  │   └─ Cons: Larger file, slower restarts
  │
  └─ Need both? (recommended for production)
      Use RDB + AOF
      └─ RDB for fast restart, AOF for durability
      └─ Redis uses AOF for restart if both enabled
```

### 12.2 RDB Configuration

```bash
# redis.conf — RDB
save 900 1        # save if at least 1 key changed in 900s (15min)
save 300 10       # save if at least 10 keys changed in 300s (5min)
save 60 10000     # save if at least 10000 keys changed in 60s (1min)

stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /var/lib/redis
```

### 12.3 AOF Configuration

```bash
# redis.conf — AOF
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec    # fsync every second (recommended)
# appendfsync always    # fsync every write (slow, ~100x)
# appendfsync no        # let OS handle (dangerous)

auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

aof-load-truncated yes
aof-use-rdb-preamble yes   # Redis 5+: mix RDB + AOF for faster rewrite
```

### 12.4 Backup/Restore Strategy

```typescript
import { execSync } from 'child_process'

// Backup RDB
async function backupRDB(): Promise<void> {
  // Tell Redis to save RDB now
  await redis.bgsave()
  // Wait for save to complete
  let lastSave = await redis.lastsave()
  await new Promise<void>((resolve) => {
    const check = setInterval(async () => {
      const currentSave = await redis.lastsave()
      if (currentSave > lastSave) {
        clearInterval(check)
        resolve()
      }
    }, 500)
  })
  // Copy dump.rdb from Redis dir to backup location
  execSync('cp /var/lib/redis/dump.rdb /backups/redis/$(date +%Y%m%d-%H%M%S).rdb')
}

// Restore from RDB
async function restoreRDB(backupPath: string): Promise<void> {
  await redis.quit()
  execSync(`
    redis-cli shutdown
    cp ${backupPath} /var/lib/redis/dump.rdb
    redis-server /etc/redis/redis.conf
  `)
}
```

---

## 13. High Availability

### 13.1 Redis Sentinel — Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      REDIS SENTINEL ARCHITECTURE                       │
│                                                                        │
│                          ┌──────────────────┐                          │
│                          │  Application       │                        │
│                          │  (ioredis client)  │                        │
│                          └────────┬─────────┘                          │
│                                   │                                     │
│            ┌──────────────────────┼──────────────────────┐             │
│            │                      │                      │             │
│     ┌──────▼──────┐      ┌───────▼──────┐      ┌───────▼──────┐      │
│     │ Sentinel-1   │      │ Sentinel-2    │      │ Sentinel-3    │      │
│     │ port: 26379  │      │ port: 26379   │      │ port: 26379   │      │
│     │ (quorum)     │      │ (quorum)      │      │ (quorum)      │      │
│     └──────┬───────┘      └───────┬───────┘      └───────┬───────┘      │
│            └──────────────────────┼──────────────────────┘             │
│                                   │                                     │
│                           ┌───────▼──────┐                             │
│                           │   sentinel    │                             │
│                           │  monitor mymaster                          │
│                           │  192.168.1.10 6379 2                       │
│                           └──────────────┘                             │
│                                   │                                     │
│                                   ▼                                     │
│   ┌────────────────────────────────────────────────────────────────┐    │
│   │  ┌──────────────────────┐          ┌──────────────────────┐    │    │
│   │  │   PRIMARY (master)    │          │   REPLICA 1 (slave)   │    │    │
│   │  │   192.168.1.10:6379   │──────────│   192.168.1.11:6379   │    │    │
│   │  └──────────────────────┘          └──────────────────────┘    │    │
│   │                                              │                   │    │
│   │                                     ┌──────────────────────┐    │    │
│   │                                     │   REPLICA 2 (slave)   │    │    │
│   │                                     │   192.168.1.12:6379   │    │    │
│   │                                     └──────────────────────┘    │    │
│   └────────────────────────────────────────────────────────────────┘    │
│                                                                        │
│   Failover Flow:                                                        │
│   1. Sentinel-1 detects primary is down (no response to PING)          │
│   2. Sentinel-1 marks as sdown (subjective down)                       │
│   3. Quorum (2) sdown notifications → odown (objective down)           │
│   4. Sentinel leader election starts                                   │
│   5. Leader picks best replica (highest replication offset)            │
│   6. Leader executes SLAVEOF NO ONE on promoted replica                │
│   7. Configuration propagated to all sentinels                         │
│   8. ioredis detects role change via sentinel pub/sub                  │
│   9. Application continues with new master                             │
└──────────────────────────────────────────────────────────────────────┘
```

### 13.2 Redis Cluster — Sharding Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                    REDIS CLUSTER ARCHITECTURE                        │
│                                                                      │
│   Hash Slot Range: 0 - 16383 (16384 slots total)                     │
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │  SLOT MAPPING (CRC16(key) % 16384)                          │   │
│   │                                                              │   │
│   │  {key:123} → slot 4567 → Node A                             │   │
│   │  user:name  → slot 7890 → Node B                            │   │
│   │  session:abc → slot 1234 → Node C                           │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│   │  NODE A       │  │  NODE B       │  │  NODE C       │              │
│   │  Master       │  │  Master       │  │  Master       │              │
│   │  Slots:       │  │  Slots:       │  │  Slots:       │              │
│   │  0-5460       │  │  5461-10922   │  │  10923-16383  │              │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│          │                  │                  │                       │
│   ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐              │
│   │  REPLICA A1   │  │  REPLICA B1   │  │  REPLICA C1   │              │
│   │  (failover)   │  │  (failover)   │  │  (failover)   │              │
│   └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                      │
│   Communication:                                                     │
│   - Gossip protocol: nodes exchange state via PING/PONG              │
│   - Cluster bus: TCP port 10000+6379 (16379)                         │
│   - MOVED: client directed to correct node                           │
│   - ASK: temporary redirection during resharding                     │
│                                                                      │
│   Resharding:                                                        │
│   1. redis-cli --cluster reshard 127.0.0.1:6379                      │
│   2. Select number of slots to move                                  │
│   3. Select target node                                              │
│   4. Slots migrated incrementally (source → target)                  │
│   5. During migration: ASK redirects                                 │
└────────────────────────────────────────────────────────────────────┘
```

### 13.3 Cluster Configuration

```typescript
import Redis from 'ioredis'

const cluster = new Redis.Cluster(
  [
    { host: 'cluster-node-1', port: 6379 },
    { host: 'cluster-node-2', port: 6379 },
    { host: 'cluster-node-3', port: 6379 },
    { host: 'cluster-node-4', port: 6379 },
    { host: 'cluster-node-5', port: 6379 },
    { host: 'cluster-node-6', port: 6379 },
  ],
  {
    clusterRetryStrategy: (times) => Math.min(times * 100, 2000),
    enableReadyCheck: true,
    scaleReads: 'slave', // offload reads to replicas
    maxRedirections: 16,
    redisOptions: {
      enableAutoPipelining: true,
      enableOfflineQueue: true,
    },
  }
)

// Hash tags — force keys to same slot
await cluster.set('{user:42}:profile', 'data')
await cluster.set('{user:42}:sessions', 'data')
// Both keys hash to same slot since only {user:42} is hashed

// Read from replica (when scaleReads: 'slave')
const staleAllowed = await cluster.get('cache:data')

// Cluster info
const info = await cluster.cluster('INFO')
const nodes = await cluster.cluster('NODES')
const slots = await cluster.cluster('SLOTS')
```

---

## 14. Security

### 14.1 ACL (Redis 6+)

```bash
# redis.conf — Create users
# Default user has no permissions
user default off

# Application user — read/write on app: keys
user app-user on >strongpassword123 +@all -@dangerous ~app:* ~pubsub:*

# Read-only user for analytics
user analytics-user on >readonlypass +@read ~analytics:*

# Admin user
user admin on >adminpass +@all ~*
```

```typescript
// Connect with ACL user
const redis = new Redis({
  host: 'localhost',
  port: 6379,
  username: 'app-user',
  password: 'strongpassword123',
})

// ACL commands
await redis.call('ACL', 'LIST') // list all users
await redis.call('ACL', 'GETUSER', 'app-user') // get user details
await redis.call('ACL', 'SETUSER', 'analytics-user', '+@read', '~analytics:*')
await redis.call('ACL', 'DELUSER', 'old-user')
await redis.call('ACL', 'LOG', '5') // recent ACL denials
```

### 14.2 TLS Encryption

```typescript
// redis.conf
tls-port 6380
port 0                    # disable plain-text port
tls-cert-file /etc/redis/redis.crt
tls-key-file /etc/redis/redis.key
tls-ca-cert-file /etc/redis/ca.crt
tls-auth-clients yes
tls-protocols "TLSv1.2 TLSv1.3"

// Client connection
import { Redis } from 'ioredis'
import { readFileSync } from 'fs'

const redis = new Redis({
  host: 'redis.internal',
  port: 6380,
  tls: {
    key: readFileSync('/etc/ssl/client.key'),
    cert: readFileSync('/etc/ssl/client.crt'),
    ca: [readFileSync('/etc/ssl/ca.crt')],
    rejectUnauthorized: true,
  },
  password: process.env.REDIS_PASSWORD,
})
```

### 14.3 Dangerous Commands — rename-command

```bash
# redis.conf — Disable or rename dangerous commands
rename-command FLUSHALL ""
rename-command FLUSHDB ""
rename-command CONFIG "ADMIN_CONFIG"
rename-command KEYS "SEARCH_KEYS"
rename-command SHUTDOWN "SHUTDOWN_REDIS"
rename-command DEBUG "DEBUG_REDIS"
rename-command SCRIPT "SCRIPT_EVAL"
# KEYS should be renamed or disabled in production
```

### 14.4 Key Namespace Separation

```typescript
class NamespacedRedis {
  constructor(private redis: Redis, private namespace: string) {}

  private key(k: string): string {
    return `${this.namespace}:${k}`
  }

  async get(key: string): Promise<string | null> {
    return this.redis.get(this.key(key))
  }

  async set(key: string, value: string, ...args: any[]): Promise<'OK' | null> {
    return this.redis.set(this.key(key), value, ...args)
  }

  async setex(key: string, ttl: number, value: string): Promise<'OK'> {
    return this.redis.setex(this.key(key), ttl, value)
  }

  async del(key: string): Promise<number> {
    return this.redis.del(this.key(key))
  }

  async scan(cursor: string, pattern: string): Promise<[string, string[]]> {
    return this.redis.scan(cursor, 'MATCH', `${this.namespace}:${pattern}`, 'COUNT', 100)
  }

  // Proxy unknown methods
  get client(): Redis {
    return this.redis
  }
}

// Usage — separate namespaces per service
const userRedis = new NamespacedRedis(redis, 'users')
const orderRedis = new NamespacedRedis(redis, 'orders')
await userRedis.setex('profile:1', 3600, JSON.stringify({ name: 'Alice' }))
// Actual key in Redis: "users:profile:1"
```

### 14.5 Firewall & Network Security

```bash
# iptables — only allow application servers
iptables -A INPUT -p tcp --dport 6379 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 6379 -j DROP

# Redis bind to internal interface
bind 10.0.0.10
protected-mode yes
requirepass your-strong-password
```

---

## 15. Testing

### 15.1 Mock Redis (ioredis-mock)

```typescript
import RedisMock from 'ioredis-mock'
import { RateLimiter } from './rate-limiter'

// Pure unit tests — no Redis needed
describe('RateLimiter', () => {
  let redis: RedisMock

  beforeEach(() => {
    redis = new RedisMock()
  })

  afterEach(() => {
    redis.flushall()
  })

  it('should allow requests within limit', async () => {
    const limiter = new RateLimiter(redis)
    const result = await limiter.check('ip:1.2.3.4', 10, 60)
    expect(result.allowed).toBe(true)
    expect(result.remaining).toBe(9)
  })

  it('should block requests over limit', async () => {
    const limiter = new RateLimiter(redis)
    for (let i = 0; i < 10; i++) {
      await limiter.check('ip:1.2.3.4', 10, 60)
    }
    const result = await limiter.check('ip:1.2.3.4', 10, 60)
    expect(result.allowed).toBe(false)
    expect(result.remaining).toBe(0)
  })
})
```

### 15.2 Integration Tests with Testcontainers

```typescript
import { GenericContainer, StartedTestContainer } from 'testcontainers'
import Redis from 'ioredis'

describe('SessionStore integration', () => {
  let container: StartedTestContainer
  let redis: Redis
  let store: SessionStore

  beforeAll(async () => {
    container = await new GenericContainer('redis:7-alpine')
      .withExposedPorts(6379)
      .start()

    redis = new Redis({
      host: container.getHost(),
      port: container.getMappedPort(6379),
    })

    store = new SessionStore(redis)
  }, 30000)

  afterAll(async () => {
    await redis.quit()
    await container.stop()
  })

  beforeEach(async () => {
    await redis.flushall()
  })

  it('should create and retrieve session', async () => {
    await store.create('sess-1', {
      userId: 1,
      role: 'admin',
      createdAt: new Date().toISOString(),
      lastAccess: new Date().toISOString(),
    })

    const session = await store.get('sess-1')
    expect(session).not.toBeNull()
    expect(session!.userId).toBe(1)
  })

  it('should destroy session', async () => {
    await store.create('sess-1', { userId: 1, role: 'admin', createdAt: '', lastAccess: '' })
    await store.destroy('sess-1')
    const session = await store.get('sess-1')
    expect(session).toBeNull()
  })

  it('should rotate session', async () => {
    await store.create('sess-old', { userId: 1, role: 'admin', createdAt: '', lastAccess: '' })
    await store.rotate('sess-old', 'sess-new', { userId: 1, role: 'admin', createdAt: '', lastAccess: '' })
    const oldSession = await store.get('sess-old')
    const newSession = await store.get('sess-new')
    expect(oldSession).toBeNull()
    expect(newSession).not.toBeNull()
  })
})
```

### 15.3 Testing Fake for BullMQ

```typescript
import { Queue, Worker, Job } from 'bullmq'
import RedisMock from 'ioredis-mock'

describe('Email Queue', () => {
  const connection = new RedisMock()

  it('should process email jobs', async () => {
    const queue = new Queue('email', { connection })
    const handler = jest.fn()

    const worker = new Worker('email', async (job: Job) => {
      handler(job.data)
    }, { connection })

    await queue.add('send-email', { to: 'test@test.com', subject: 'Hello' })
    // Give time for the job to be processed
    await new Promise((r) => setTimeout(r, 500))

    expect(handler).toHaveBeenCalledWith({ to: 'test@test.com', subject: 'Hello' })

    await worker.close()
    await queue.close()
  })
})
```

---

## 16. Anti-Patterns — What NOT to Do

### 16.1 Do NOT Use KEYS in Production

```typescript
// ❌ BAD — blocks Redis for millions of keys
const allUserKeys = await redis.keys('user:*')

// ✅ GOOD — use SCAN (non-blocking, cursor-based)
const scanKeys: string[] = []
let cursor = '0'
do {
  const [nextCursor, keys] = await redis.scan(cursor, 'MATCH', 'user:*', 'COUNT', 100)
  cursor = nextCursor
  scanKeys.push(...(keys as string[]))
} while (cursor !== '0')
```

### 16.2 Do NOT Ignore Connection Errors

```typescript
// ❌ BAD — no error handling
const redis = new Redis()

// ✅ GOOD — handle and reconnect
const redis = new Redis({
  retryStrategy: (times) => {
    console.error(`Redis connection lost, retry #${times}`)
    return Math.min(times * 200, 5000)
  },
  maxRetriesPerRequest: 3,
})
redis.on('error', (err) => console.error('Redis error:', err))
redis.on('end', () => {
  // Connection permanently lost after max retries
  // Consider circuit breaker or shutdown
  process.exit(1)
})
```

### 16.3 Do NOT Store Large Objects

```typescript
// ❌ BAD — storing 50MB CSV in Redis
await redis.set('export:users', hugeCsvString)

// ✅ GOOD — Redis value limit is 512MB, but practical limit is ~10-50KB
// Use Redis for hot data only, store blobs elsewhere (S3, DB)
await redis.set(
  'export:users:meta',
  JSON.stringify({ size: hugeCsvString.length, url: 's3://exports/users.csv' })
)
```

### 16.4 Do NOT Forget TTL

```typescript
// ❌ BAD — cache grows unbounded
await redis.set('user:42:profile', JSON.stringify(profile))

// ✅ GOOD — always set TTL for cache data
await redis.setex('user:42:profile', 3600, JSON.stringify(profile))

// Even for session data
await redis.setex('sess:abc', 86400, JSON.stringify(session))
```

### 16.5 Do NOT Use Redis as Primary Database

```typescript
// ❌ BAD — using Redis as primary store
// All data is in-memory → expensive, limited, no complex queries
// Server restart → data loss (if no persistence) or slow restart

// ✅ GOOD — Redis is a cache layer on top of PostgreSQL/MongoDB/etc
// Write to primary DB, cache result in Redis
async function getUser(id: number) {
  const cached = await redis.get(`user:${id}`)
  if (cached) return JSON.parse(cached)
  const user = await db.user.findUnique({ where: { id } })
  if (user) await redis.setex(`user:${id}`, 300, JSON.stringify(user))
  return user
}
```

### 16.6 Do NOT Make Too Many Round Trips

```typescript
// ❌ BAD — N round trips for N keys
for (const id of ids) {
  await redis.get(`user:${id}`)
}

// ✅ GOOD — pipeline or mget
const pipeline = redis.pipeline()
for (const id of ids) {
  pipeline.get(`user:${id}`)
}
const results = await pipeline.exec()

// Or for strings
const values = await redis.mget(...ids.map((id) => `user:${id}`))
```

### 16.7 More Anti-Patterns

```
✗ Using MONITOR in production (CPU intensive)
✗ Not using connection pooling (creating new Redis() per request)
✗ Mixing pub/sub and regular commands on same connection
✗ Large batch operations without pipeline (N > 1000)
✗ Not handling WATCH retries in optimistic locking
✗ Using same database for prod and dev (always separate instances)
✗ Running without persistence but expecting data survival
✗ Overusing hash tags in Cluster (key distribution imbalance)
✗ Storing binary data without encoding (use Buffer/hex)
✗ Ignoring Bloom filters for cache penetration protection
✗ Single point of failure — no Sentinel/Cluster in production
✗ Default config in production (change bind, port, protected-mode)

Memory Anti-Patterns:
✗ Storing millions of tiny keys (use HASH for related fields)
✗ Not monitoring memory fragmentation
✗ Using maxmemory-policy noeviction in cache use case
✗ Forgetting to set maxmemory (OOM kill risk)
```

---

## 17. Redis Implementation Checklist

### Production Readiness
```
[ ] Redis version ≥ 7 (or latest stable)
[ ] Password set (requirepass) or ACL configured
[ ] Protected mode enabled
[ ] Bind to internal IP only
[ ] TLS enabled for external connections
[ ] Dangerous commands renamed (FLUSHALL, CONFIG, KEYS)
[ ] maxmemory set (e.g., 80% of available RAM)
[ ] maxmemory-policy set (allkeys-lru for cache, noeviction for DB)
[ ] RDB + AOF persistence configured
[ ] appendfsync everysec
[ ] Slow log configured (slowlog-log-slower-than 10000)
[ ] Connection count limits (maxclients)
```

### Application Patterns
```
[ ] Connection: single ioredis instance per process
[ ] Connection: error handling + retry strategy
[ ] Connection: graceful shutdown handler
[ ] Cache: TTL set on every cache key
[ ] Cache: cache-aside pattern for reads
[ ] Cache: stampede protection for hot keys
[ ] Cache: Bloom filter for miss-prediction
[ ] Cache: SCAN instead of KEYS
[ ] Session: connect-redis or custom store with TTL
[ ] Session: rotation on privilege escalation
[ ] Rate limit: Lua scripts for atomicity
[ ] Rate limit: sliding window (ZSET) or token bucket
[ ] Queue: BullMQ for complex jobs
[ ] Queue: Redis Streams for lightweight messaging
[ ] Queue: consumer groups + ack + PEL handling
[ ] Queue: dead-letter stream for failed messages
[ ] Lock: SET NX EX with unique token
[ ] Lock: Lua-based safe release
[ ] Lock: auto-renewal for long operations
[ ] Lock: Redlock for multi-master setups
[ ] Pipeline: batch related operations
[ ] Pipeline: enableAutoPipelining for Cluster
```

### Monitoring & Observability
```
[ ] Redis INFO scraped every 60s
[ ] Alert on: OOM, master link down, over 1M ops/sec
[ ] Slow log reviewed regularly
[ ] Memory USAGE tracked for top keys
[ ] hit_rate tracked (keyspace_hits / total)
[ ] connected_clients monitored
[ ] Replication lag monitored (master_repl_offset - slave_repl_offset)
[ ] Latency monitored (LATENCY HISTOGRAM)
[ ] Backup tested weekly (restore from RDB)
[ ] AOF rewrite size monitored
```

### Testing
```
[ ] Unit tests with ioredis-mock
[ ] Integration tests with testcontainers
[ ] Failover tests (kill master, verify promotion)
[ ] Load tests (verify rate limiting, connection pooling)
[ ] Redis Stack module tests (JSON, Search, TimeSeries)
[ ] Queue tests (job lifecycle, retries, stalled handling)
[ ] Lock tests (contention, timeout, safe release)
```

### Security Checklist
```
[ ] Firewall limits Redis port to app servers
[ ] Password or ACL on every instance
[ ] TLS for external-facing Redis
[ ] Dangerous commands renamed/disabled
[ ] Key namespacing per service/tenant
[ ] Last ACL denial review (ACL LOG)
[ ] Redis running as non-root user
[ ] No default config in production
```

---

## Lua Script Quick Reference

```lua
-- Compare-and-delete (safe lock release)
-- KEYS[1] = lock key, ARGV[1] = expected token
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
else
  return 0
end

-- Compare-and-expire (safe lock renewal)
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("PEXPIRE", KEYS[1], ARGV[2])
else
  return 0
end

-- Increment hash field atomically
-- KEYS[1] = hash key, ARGV[1] = field, ARGV[2] = amount
return redis.call("HINCRBY", KEYS[1], ARGV[1], ARGV[2])

-- Batch insert with TTL
for i, key in ipairs(KEYS) do
  redis.call("SETEX", key, ARGV[#ARGV], ARGV[i])
end
return #KEYS
```

### Registering Lua Commands in ioredis

```typescript
redis.defineCommand('safereleaselock', {
  numberOfKeys: 1,
  lua: `
    if redis.call("GET", KEYS[1]) == ARGV[1] then
      return redis.call("DEL", KEYS[1])
    else
      return 0
    end
  `,
})

// Usage
const released = await (redis as any).safereleaselock('lock:resource', 'mytoken')
```

---

## Key Naming Convention (Recommended)

```
Format:    <namespace>:<entity>:<id>[:<sub-entity>:<sub-id>]
Examples:  user:42:profile
           user:42:sessions:abc-123
           order:20260517-001:items
           rate:api:login:user:42
           cache:product:500

Rules:
- Lowercase only
- Colons as delimiters
- Namespace first (for scan/namespace isolation)
- ID next (for easy pattern matching)
- Descriptive suffixes last

Hash tags for Cluster:
- {namespace}:<entity>:<id> → e.g., {user}:42:profile
- All keys with same {user:42} tag land on same slot
```

---

## Environment-Based Configuration

```typescript
function createRedisClient(): Redis {
  const { REDIS_URL, REDIS_SENTINEL, REDIS_CLUSTER } = process.env

  if (REDIS_CLUSTER) {
    const nodes = JSON.parse(REDIS_CLUSTER) as Array<{ host: string; port: number }>
    return new Redis.Cluster(nodes, {
      scaleReads: 'slave',
      enableAutoPipelining: true,
    })
  }

  if (REDIS_SENTINEL) {
    const config = JSON.parse(REDIS_SENTINEL)
    return new Redis({
      sentinels: config.sentinels,
      name: config.masterName,
      role: 'master',
    })
  }

  if (REDIS_URL) {
    return new Redis(REDIS_URL, {
      retryStrategy: (times) => Math.min(times * 200, 5000),
      maxRetriesPerRequest: 5,
    })
  }

  return new Redis({
    host: process.env.REDIS_HOST || 'localhost',
    port: Number(process.env.REDIS_PORT) || 6379,
    password: process.env.REDIS_PASSWORD,
    db: Number(process.env.REDIS_DB) || 0,
  })
}
```

---

## Error Handling Pattern

```typescript
class RedisService {
  private redis: Redis
  private circuitOpen = false
  private failureCount = 0
  private readonly threshold = 5
  private readonly resetTimeout = 30000

  constructor() {
    this.redis = this.createClient()
  }

  private createClient(): Redis {
    return new Redis({
      retryStrategy: (times) => {
        if (times > 10) {
          this.circuitOpen = true
          setTimeout(() => {
            this.circuitOpen = false
            this.failureCount = 0
          }, this.resetTimeout)
          return null // stop retrying
        }
        return Math.min(times * 200, 5000)
      },
    })
  }

  async execute<T>(operation: () => Promise<T>): Promise<T> {
    if (this.circuitOpen) {
      throw new Error('Redis circuit breaker open')
    }
    try {
      const result = await operation()
      this.failureCount = 0
      return result
    } catch (err) {
      this.failureCount++
      if (this.failureCount >= this.threshold) {
        this.circuitOpen = true
      }
      throw err
    }
  }

  async get(key: string): Promise<string | null> {
    return this.execute(() => this.redis.get(key))
  }

  async set(key: string, value: string): Promise<'OK'> {
    return this.execute(() => this.redis.set(key, value))
  }
}
```

---

## Production Config Template (redis.conf)

```bash
# Network
bind 10.0.0.10
port 6379
tls-port 6380
protected-mode yes

# Security
requirepass YOUR_STRONG_PASSWORD
rename-command FLUSHALL ""
rename-command FLUSHDB ""
rename-command CONFIG "ADMIN_CONFIG"
rename-command KEYS "SEARCH_KEYS"

# Persistence
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes

appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
aof-use-rdb-preamble yes

# Memory
maxmemory 4gb
maxmemory-policy allkeys-lru

# Connection
maxclients 10000
timeout 300
tcp-keepalive 300

# Slow log
slowlog-log-slower-than 10000
slowlog-max-len 128

# Latency monitor
latency-monitor-threshold 100

# Replication
replica-serve-stale-data yes
replica-read-only yes
repl-diskless-sync yes
repl-backlog-size 64mb

# TLS (if applicable)
tls-cert-file /etc/redis/redis.crt
tls-key-file /etc/redis/redis.key
tls-ca-cert-file /etc/redis/ca.crt
```
