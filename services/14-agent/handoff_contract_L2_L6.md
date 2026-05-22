# Handoff Contract — T2-T6 Agent Memory System Integration

> **Dari**: lore-master
> **Ke**: @vibe-coder
> **Proyek**: sc_auditor (Vyper Agent Service)
> **Tanggal**: 2026-05-20

---

## 1. Problem Statement

Memory module files sudah dibuat di `services/14-agent/src/memory/` tapi ada **shadowing bug** + **API mismatches** yang menyebabkan semua consumer code use OLD in-memory AgentMemory.

### 🔴 Root Cause
File `services/14-agent/src/memory.py` (stale duplicate of `inmem_memory.py`) **shadows** directory `services/14-agent/src/memory/`. Semua `from src.memory import AgentMemory` resolve ke file, bukan package.

### 🔴 API Mismatches
Consumer code (`agent.py`, `daemon.py`, `feedback.py`, `app.py`) memanggil method yang:
- Tidak ada di VectorMemory (e.g., `search()`)
- Signature berbeda (e.g., `graph.add_node()`, `vector.store()`)
- Nama berbeda (e.g., `episodic_store` vs `episodic`, `get_all_stats` vs `memory_stats`)

---

## 2. Execution Plan (8 tasks, ~35 min)

| # | Task | File | Action |
|---|------|------|--------|
| 1 | Hapus shadowing | `src/memory.py` | 🗑️ DELETE file |
| 2 | Add helpers ke VectorMemory | `src/memory/vector_store.py` | ✏️ Add `search()` alias + `store_text()` |
| 3 | Add helper ke EpisodicMemory | `src/memory/episodic.py` | ✏️ Add `store_text()` |
| 4 | Enhance AgentMemory `__init__.py` | `src/memory/__init__.py` | ✏️ Add `get_all_stats()`, fix imports |
| 5 | Fix consumer: agent.py | `src/agent.py` | ✏️ Fix all memory API calls |
| 6 | Fix consumer: feedback.py | `src/learning/feedback.py` | ✏️ Fix memory calls |
| 7 | Fix consumer: daemon.py | `src/daemon.py` | ✏️ Fix vector.store() calls |
| 8 | Fix consumer: app.py | `app.py` | ✏️ Fix `get_all_stats()` call |

---

## 3. Detailed Spec Per Task

### Task 1: Hapus `src/memory.py`
- File ini adalah DUPLIKAT persis dari `src/inmem_memory.py`
- Hapus file `services/14-agent/src/memory.py`

### Task 2: VectorMemory — Add convenience methods
**File**: `src/memory/vector_store.py`

Add method `search()` sebagai alias dari `retrieve()`:
```python
async def search(self, query: str, limit: int = 5, **filters) -> list[MemoryEntry]:
    """Search by semantic similarity. Alias for retrieve()."""
    return await self.retrieve(query, limit=limit)
```

Add method `store_text()` untuk convenience key+content+metadata:
```python
async def store_text(self, key: str, content: str, metadata: dict | None = None) -> str:
    """Store text as MemoryEntry (convenience wrapper)."""
    entry = MemoryEntry(
        content=content,
        metadata={"key": key, **(metadata or {})},
        entry_id=key,
    )
    return await self.store(entry)
```

### Task 3: EpisodicMemory — Add `store_text()`
**File**: `src/memory/episodic.py`

```python
async def store_text(self, key: str, content: Any, metadata: dict | None = None) -> str:
    """Store as MemoryEntry with key+content+metadata (convenience)."""
    entry = MemoryEntry(
        content=str(content),
        metadata={"key": key, **(metadata or {})},
        entry_id=key,
    )
    return await self.store(entry)
```

### Task 4: AgentMemory `__init__.py`
**File**: `src/memory/__init__.py`

Changes:
1. Add `from src.inmem_memory import AgentMemory as InMemoryAgentMemory` (sudah ada - keep)
2. Add method `get_all_stats()`:
```python
def get_all_stats(self) -> dict:
    return {
        "working": len(self.working),
        "episodic_inmem": len(self.episodic),
        "semantic": len(self.semantic),
        "vector_persistent": len(self.vector.entries),
        "graph_nodes": len(self.graph.nodes),
        "graph_edges": len(self.graph.edges),
    }
```

### Task 5: Fix `agent.py`
**File**: `src/agent.py`

Changes:
1. Line 112: `await self.memory.vector.search(...)` → `await self.memory.vector.retrieve(...)`
2. Lines 129-137: `await self.memory.graph.add_node(label=..., node_type=..., properties=...)` → fix signature:
   ```python
   session_node_id = str(uuid.uuid4())[:8]
   self.memory.graph.add_node(
       node_id=session_node_id,
       node_type="session",
       properties={
           "label": f"Session {session_id}: {goal[:50]}",
           "session_id": session_id,
           "task_type": task_type.value,
           "goal": goal[:200],
       },
   )
   self.memory.set_working("_graph_session_node", session_node_id)
   ```
3. Lines 143-150: `await self.memory.episodic_store.store(...)` → `await self.memory.episodic.store_text(...)`
4. Lines 205-214: `await self.memory.vector.store(...)` → `await self.memory.vector.store_text(...)`
5. Lines 224-228: `await self.memory.graph.add_node(label=..., node_type=..., properties=...)` → same fix as #2
6. Line 231: `await self.memory.graph.add_edge(source_id=..., target_id=..., relation=..., weight=...)` → fix signature:
   ```python
   graph_node = self.memory.get_working("_graph_session_node")
   if graph_node:
       self.memory.graph.add_edge(
           from_id=graph_node,
           to_id=finding_node_id,
           relation="found",
           properties={"weight": 1.0},
       )
   ```
7. Lines 296-313: `await self.memory.episodic_store.store(...)` → `await self.memory.episodic.store_text(...)`

### Task 6: Fix `feedback.py`
**File**: `src/learning/feedback.py`

Changes:
1. Line 150: `await self.memory.vector.store(...)` → `await self.memory.vector.store_text(...)`
2. Line 165: `await self.memory.episodic_store.store(...)` → `await self.memory.episodic.store_text(...)`

### Task 7: Fix `daemon.py`
**File**: `src/daemon.py`

Changes:
1. Line 240: `await self.agent.memory.vector.store(...)` → `await self.agent.memory.vector.store_text(...)`
2. Line 283: `await self.agent.memory.vector.store(...)` → `await self.agent.memory.vector.store_text(...)`

### Task 8: Fix `app.py`
**File**: `app.py`

Changes:
1. Line 281: `memory_entries=state.agent.memory.total_entries` → verify `total_entries` property exists (it does from InMemoryAgentMemory)
2. Line 612: `state.agent.memory.get_all_stats()` → should work after Task 4

---

## 4. Verification Checklist

After all tasks:

- [ ] `from src.memory import AgentMemory` resolves to `memory/__init__.py`, NOT `memory.py`
- [ ] `agent.py` line 59: `self.memory = AgentMemory()` creates enhanced version with `.vector`, `.episodic`, `.graph`
- [ ] `agent.py` `vector.search()` → `vector.retrieve()` ✅
- [ ] `agent.py` `graph.add_node()` → signature matches GraphMemory ✅
- [ ] `agent.py` `episodic_store` → `episodic` ✅
- [ ] `daemon.py` `vector.store()` → `vector.store_text()` ✅
- [ ] `feedback.py` `vector.store()` → `vector.store_text()` ✅
- [ ] `feedback.py` `episodic_store` → `episodic` ✅
- [ ] `app.py` `get_all_stats()` → exists on AgentMemory ✅
- [ ] No `from src.memory import AgentMemory` resolves to stale inmem version
- [ ] Service 14-agent starts without ImportError or AttributeError

---

## 5. Rollback Plan

If something breaks:
1. Restore `src/memory.py` from `src/inmem_memory.py`
2. Revert any changed file (git checkout)
3. File-by-file regression: test import chain

---

*Handoff Contract v1.0 — lore-master → @vibe-coder*
