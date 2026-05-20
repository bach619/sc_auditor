---
name: paradigm-actor
description: Actor Model patterns: Erlang/Elixir OTP, Akka (Scala/Java), Orleans (.NET), message-passing concurrency, supervision trees, location transparency, and fault tolerance
license: MIT
compatibility: opencode
metadata:
  audience: all-developers
  domain: paradigm
  paradigm: actor-model
  integrates_with: [backend-elixir, paradigm-functional, database-event-sourcing, workflow-general]
---

## Paradigm Actor Model Skill

### Actor Model Foundations
- **Everything is an actor**: Primitive unit of computation; has address, mailbox, behavior
- **Communication via messages**: Asynchronous, non-blocking sends; message ordering preserved between same sender-receiver pair
- **Isolated state**: Each actor has private state; no shared memory; no locks
- **Location transparency**: Actor address is virtual; can be local or remote
- **Let it crash**: Failure is expected; supervision handles recovery; defensive programming is anti-pattern

### Erlang/Elixir OTP
- **GenServer**: handle_call (sync), handle_cast (async), handle_info (messages); init/1; terminate/2
- **Supervisor**: Strategy: :one_for_one, :one_for_all, :rest_for_one, :simple_one_for_one; max_restarts, max_seconds
- **Application**: Start callback; supervision tree root; config via Application.get_env
- **DynamicSupervisor**: Start children on demand; start_child with unique id
- **Registry**: Named process lookup; :unique (one per key) or :duplicate (per partition)
- **Process monitoring**: Process.monitor; handle_info {:DOWN, ref, :process, pid, reason}

### Akka (Scala/Java)
- **ActorSystem**: Root of actor hierarchy; config (reference.conf); dispatcher selection
- **ActorRef**: Immutable handle to actor; never access Actor directly
- **Behaviors**: Behavior[T] (typed); setup, receive, receiveMessage; become for state change
- **Supervision**: OneForOneStrategy, AllForOneStrategy; Restart, Resume, Stop, Escalate
- **Cluster**: akka-cluster; gossip protocol; leader election; sharding via ClusterSharding
- **Persistence**: EventSourcedBehavior; event sourcing with snapshot support; akka-persistence

### Message Patterns
- **Request-Response**: Ask pattern (Future); prefer tell (!) over ask (?); match on response
- **Fire-and-Forget**: Tell (!); sender doesn't wait; actor sends confirmation separately
- **Pub/Sub**: EventBus or PubSub; topic-based; actors subscribe to events
- **Scatter-Gather**: Send to multiple actors, aggregate responses; timeout for partial results
- **Saga**: Long-running transaction; compensating actions on failure; each step is an actor
- **Backpressure**: Pull-based (actor requests work); bounded mailboxes; reject on overflow

### Supervision Strategy
```
Root Supervisor
 ├─ Worker Pool Supervisor (one-for-one, max 5 restarts / 60s)
 │   ├─ Worker 1 (transient: restart kills children)
 │   ├─ Worker 2 (temporary: never restarted)
 │   └─ Worker N
 └─ Database Connection Supervisor (one-for-all)
     ├─ Connection Pool
     └─ Health Checker
```
- **One-for-One**: Only failed child restarted
- **One-for-All**: All children restarted (when they depend on each other)
- **Rest-for-One**: Failed child + children started after it

### Fault Tolerance
- **Crash-only design**: Assume crashes are normal; recover via restart; no defensive null checks
- **Circuit breaker**: After N failures, stop trying for timeout period; actor model naturally supports this
- **Bulkheading**: Partition actors into groups; one group's failure doesn't cascade
- **Timeout**: All expects-reply patterns need timeout; handle timeout as failure

### When to Use Actor Model
- Highly concurrent systems with mutable state
- Fault-tolerant distributed systems
- Systems where message-passing maps naturally to domain (telecom, IoT, gaming)
- Long-running stateful services
- When you need hot code reloading (Erlang/Elixir)

### When NOT to Use
- CPU-bound computation without concurrency
- Simple CRUD applications
- When team has no actor model experience
- When strong consistency is required (actors are eventually consistent across nodes)

### Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| God actors | Single actor handles too many message types; becomes monolithic bottleneck | Split by responsibility; one actor type per bounded context |
| Assuming message ordering | Network partitions, restarts, and retries can reorder messages | Design for idempotent message handling; use causality IDs for ordering |
| Unbounded mailboxes | Actor receives messages faster than it processes; memory exhaustion | Use bounded mailboxes with backpressure; drop policy for overflow |
| Blocking inside actor | Blocks the actor's message processing; stalls the entire actor system | Offload blocking work to separate thread/future; use `pipeTo` (Akka) or `Task` (Elixir) |
| Request-response for everything | Tight coupling; caller blocks waiting for response | Prefer fire-and-forget (tell) + separate confirmation message; use ask pattern sparingly |
| No supervision hierarchy | All actors are top-level; single failure cascades everywhere | Design supervision tree: root → domain supervisors → workers |
| Storing large state in actor | Large state causes GC pauses; message processing starves | Split state across child actors; use external storage with caching |
| Exposing actor internals | Direct access to actor state breaks encapsulation and location transparency | Only communicate via messages; never expose ActorRef internals |
| Not handling message timeouts | Actor waits forever for response; cascading timeouts upstream | Every ask pattern must have timeout; handle timeout as domain error |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| Actor not responding (timeout) | Mailbox overwhelmed; actor crashed; deadlock | Check mailbox size; check supervision events; enable debug logging | Increase mailbox size; fix crash; add timeout handling |
| Messages silently dropped | Dead letter queue; actor stopped before processing | Check dead letter count/log; verify actor lifecycle | Monitor dead letters; add graceful shutdown with drain |
| High memory usage | Large actor state; unbounded mailbox; message retention | Check actor heap size; mailbox count | Split state; use bounded mailbox; add TTL on messages |
| Increasing message processing latency | Slow handler; blocking operations; GC pressure | Profile handler execution time; check for blocking calls | Optimize handler; offload blocking work; use async processing |
| Cluster split-brain | Network partition; leader election failure | Check cluster membership; verify split-brain resolver config | Use SBR (Split Brain Resolver); keep majority quorum |
| Supervision restart loop | Child actor crashes, restarts, crashes immediately | Check restart count; exponential backoff | Fix root cause in child; add max restart limit with escalation |

### Implementation Checklist

- [ ] Actor model chosen for appropriate use case (stateful, concurrent, fault-tolerant)
- [ ] Supervision tree designed with clear failure domains
- [ ] All communication via messages (no direct state access)
- [ ] Message timeouts defined for all request-response patterns
- [ ] Bounded mailboxes with backpressure strategy configured
- [ ] Dead letter monitoring configured and alertable
- [ ] Idempotent message handling designed (at-least-once delivery)
- [ ] Actor state kept small; large state externalized
- [ ] Supervision strategies documented per actor type (one-for-one, one-for-all, etc.)
- [ ] Crash-only design: actors accept crashes as normal; defensive null checks avoided
- [ ] Clustering tested with network partition scenarios
- [ ] Message serialization format chosen (Protobuf, Avro, JSON)
- [ ] Testing: unit tests for actor behavior; property-based tests for invariants
- [ ] Monitoring: actor mailbox sizes, processing latency, error rates, dead letters
