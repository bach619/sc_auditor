---
name: systems-ebpf
description: eBPF programming: program types (XDP, TC, tracing, cgroup), maps, CO-RE, BTF, verification constraints, and production use cases (networking, observability, security)
license: MIT
compatibility: opencode
metadata:
  audience: systems-engineers
  domain: systems
  paradigm: kernel-extensibility
  integrates_with: [infra-kubernetes, infra-observability, security-audit, systems-embedded]
---

## Systems eBPF Skill

### eBPF Architecture
```
User Space                    Kernel Space
  Program                        eBPF Program
    ↓ (load via bpf())             ↓ (attach to hook)
  Maps ←--- (read/write) ---→    Maps (shared)
    ↓                             ↓ (output)
  Perf Buffer ←--- (events) ---→ Perf Event Array
```

### Program Types & Hooks
- **XDP (eXpress Data Path)**: Earliest packet processing; drop/redirect/pass at driver level; ~10x faster than DPDK
- **TC (Traffic Control)**: Ingress/egress classification; more context than XDP (skb metadata)
- **kprobe/kretprobe**: Dynamic kernel function tracing; can hook any non-inlined function
- **tracepoint**: Stable kernel tracepoints; preferred over kprobes when available
- **uprobe/uretprobe**: Userspace function tracing
- **cgroup/skb**: Per-cgroup packet filtering; socket-level control
- **cgroup/sock**: Socket operations (connect, bind, sendmsg)
- **LPM (Longest Prefix Match)**: Routing table lookups in eBPF

### Maps (Data Structures Shared Kernel↔Userspace)
- **BPF_MAP_TYPE_HASH**: Key-value; dynamic, unordered; most common
- **BPF_MAP_TYPE_ARRAY**: Fixed-size; zero-initialized; fastest for known keys
- **BPF_MAP_TYPE_LRU_HASH**: Hash with automatic eviction of least-recently-used
- **BPF_MAP_TYPE_PERCPU_HASH**: Per-CPU copy for lock-free writes
- **BPF_MAP_TYPE_RINGBUF**: Circular buffer for events; multi-producer, single-consumer
- **BPF_MAP_TYPE_QUEUE/STACK**: FIFO/LIFO for data passing
- **BPF_MAP_TYPE_LPM_TRIE**: Longest prefix match for IP routing

### CO-RE (Compile Once, Run Everywhere)
- **BTF (BPF Type Format)**: Kernel type information; enables portable eBPF programs
- **libbpf**: Userspace library; auto-relocation via BTF
- **vmlinux.h**: Auto-generated header with all kernel types; #include "vmlinux.h"
- **BPF_CORE_READ**: Macro for portable struct field access; handles field offsets
- **Compile once**: One ELF binary runs on any kernel version (with BTF)

### Verifier Constraints
- **Maximum instructions**: 1M (v5.2+); was 4096 (check kernel version)
- **No unbounded loops**: Loops must have proven exit; bounded by verifier
- **No global variables**: Use maps for inter-program data
- **Stack limit**: 512 bytes; use maps for larger data
- **Helper access**: Only whitelisted functions; check bpf-helpers(7)
- **Pointer arithmetic**: Only with scalar and bounds checking

### Production Use Cases
- **Cilium**: CNI with identity-based security; replaces kube-proxy
- **Falco**: Runtime security monitoring; syscall-level anomaly detection
- **Pixie**: Auto-instrumented observability for Kubernetes
- **Katran**: Facebook's L4 load balancer; XDP-based; 10M pps per core
- **bpftrace**: Dynamic tracing language for ad-hoc observability

### Development Flow
1. Write eBPF C code (#include "vmlinux.h", license = "GPL")
2. Compile with clang -target bpf (-O2 -g for BTF)
3. Generate skeleton with bpftool gen skeleton
4. Load with libbpf (auto-relocation via BTF)
5. Attach to hook (XDP, tc, kprobe, etc.)
6. Read maps / perf buffer from userspace

### Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Unbounded loops in BPF | Verifier rejects program; BPF programs must provably terminate | Use bounded loops with known iteration count; avoid while-true |
| Map not freed on program unload | Map persists in kernel consuming memory | Pin maps with `bpftool` and clean up on teardown; use auto-pinning |
| Blocking operations in BPF | No sleep, no mutex, no wait — BPF runs in atomic context | Use spinlocks only (short critical sections); defer to userspace for blocking work |
| kprobes instead of tracepoints | kprobes are unstable across kernel versions; can be inlined away | Prefer tracepoints (stable ABI); fall back to kprobes only when no tracepoint exists |
| Too-large programs | Verifier rejects programs over instruction limit or complexity | Split across multiple programs; use tail calls; simplify logic |
| Not BTF-aware | Program breaks when kernel struct layouts change | Always use CO-RE: `#include "vmlinux.h"` and `BPF_CORE_READ` macros |
| Pointer arithmetic without bounds check | Verifier rejects unverified memory access | Bounds-check all pointer accesses; use `bpf_probe_read_kernel` for kernel memory |
| Ignoring return codes | BPF helpers return error codes; ignoring them causes silent failures | Check return value of every helper call; handle errors explicitly |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| `BPF program failed to load` | Verifier rejected the program | `bpftool prog load` output shows verifier log; check instruction number and complexity | Read verifier log line-by-line; simplify program; add bounds checks |
| `R0 invalid mem access` | Reading uninitialized memory; null pointer dereference | Verifier log shows the exact code path | Initialize all variables; check pointers before dereference |
| `program too large` | Instruction count exceeds kernel limit (1M for v5.2+) | `bpftool prog show` shows instruction count | Split program; use tail calls; optimize code |
| Map lookup returns empty | Key not found; map not shared between programs | Check `bpftool map dump` to verify entries exist | Verify map type is shared; use `BPF_MAP_TYPE_HASH` not `PERCPU` for shared data |
| `bpf_printk` output not showing | Trace pipe not mounted; log level too low | `cat /sys/kernel/debug/tracing/trace_pipe` | Mount debugfs; check kernel log level; use `bpftool prog tracelog` |
| Program works on one kernel, fails on another | Kernel struct layout changed; missing kernel config option | Check BTF availability: `bpftool btf dump`; verify config | Use CO-RE and `vmlinux.h`; check kernel config for BPF options |
| Map operations too slow in hot path | Hash collisions; large map; not using per-CPU maps | Use `bpftool map event_pipe` to profile | Use `BPF_MAP_TYPE_PERCPU_HASH` for lock-free; pre-allocate maps |

### Implementation Checklist

- [ ] BPF program compiled with `-target bpf -O2 -g` (CO-RE + BTF support)
- [ ] `#include "vmlinux.h"` used for kernel type definitions
- [ ] `BPF_CORE_READ` macros used for portable struct field access
- [ ] Verifier constraints respected: max instructions, bounded loops, stack limit
- [ ] All maps properly sized and type-selected (HASH vs ARRAY vs PERCPU vs RINGBUF)
- [ ] `bpftool gen skeleton` used for userspace loader
- [ ] Program attached to correct hook (XDP, TC, kprobe, tracepoint, cgroup)
- [ ] Return codes checked on all BPF helper calls
- [ ] Error handling: allocate and handle error cases in program
- [ ] Userspace side reads maps/perf buffers correctly
- [ ] Program upgrade strategy: pin maps across reloads; avoid downtime
- [ ] `bpftool prog show` to verify program loaded and attached
- [ ] CO-RE tested across target kernel version range
- [ ] Observability: BPF program runtime stats exported to Prometheus
- [ ] Security: BPF programs run with minimum required capabilities (CAP_BPF)
