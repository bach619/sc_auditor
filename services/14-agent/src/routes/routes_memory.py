from __future__ import annotations

from typing import Any

import app
from app import _err, _ok, _truncate
from fastapi import APIRouter
from pydantic import BaseModel, Field
from src.models import ApiResponse

router = APIRouter()


class MemorySearchRequest(BaseModel):
    query: str
    store: str = "vector"  # vector | episodic | graph
    limit: int = 10
    filters: dict[str, Any] = Field(default_factory=dict)


@router.get("/memory")
async def get_memory() -> ApiResponse:
    """Get current agent memory contents."""
    if app.state is None or app.state.agent is None:
        raise _err("Service not initialized", 503)

    memory = app.state.agent.memory
    return _ok({
        "working": {k: _truncate(v) for k, v in memory.working.items()},
        "episodic": [
            {
                "key": e.key,
                "content": _truncate(e.content),
                "timestamp": e.timestamp,
            }
            for e in memory.last_episodes(10)
        ],
        "semantic": {k: _truncate(v) for k, v in list(memory.semantic.items())[:10]},
        "total_entries": memory.total_entries,
    })


@router.post("/memory/search")
async def memory_search(body: MemorySearchRequest) -> ApiResponse:
    """Search across memory stores.

    **Request body**::

        {
            "query": "reentrancy vulnerability",
            "store": "vector",
            "limit": 10
        }
    """
    if app.state is None or app.state.agent is None:
        raise _err("Service not initialized", 503)

    memory = app.state.agent.memory

    try:
        if body.store == "vector":
            results = await memory.vector.search(
                body.query, limit=body.limit, **body.filters
            )
        elif body.store == "episodic":
            results = await memory.episodic_store.search(
                body.query, limit=body.limit, **body.filters
            )
        elif body.store == "graph":
            results = await memory.graph.search(
                body.query, limit=body.limit, **body.filters
            )
        else:
            raise _err(f"Unknown store: {body.store}", 400)

        return _ok({
            "store": body.store,
            "query": body.query,
            "results": results,
            "total": len(results),
        })
    except Exception as exc:
        raise _err(f"Memory search failed: {exc}", 500)


@router.get("/memory/stats")
async def memory_stats() -> ApiResponse:
    """Get detailed memory store statistics."""
    if app.state is None or app.state.agent is None:
        raise _err("Service not initialized", 503)

    return _ok(app.state.agent.memory.get_all_stats())


@router.get("/knowledge")
async def get_knowledge() -> ApiResponse:
    """Get system knowledge loaded from SYSTEM_KNOWLEDGE.md.

    Returns all knowledge chunks currently in vector memory
    that have metadata.source == 'system_knowledge'.
    """
    if app.state is None or app.state.agent is None:
        raise _err("Service not initialized", 503)

    try:
        entries = app.state.agent.memory.vector_store.get_all()
        knowledge_entries = [
            e.to_dict()
            for e in entries
            if e.metadata.get("source") == "system_knowledge"
        ]

        return _ok({
            "total_chunks": len(knowledge_entries),
            "chunks": sorted(knowledge_entries, key=lambda e: e.get("metadata", {}).get("section_index", 0)),
            "source": "SYSTEM_KNOWLEDGE.md",
            "note": "Antonio uses this knowledge in MODE 1 (direct answers) and for semantic search during audits.",
        })
    except Exception as exc:
        app.log.warning("knowledge_retrieval_failed", error=str(exc))
        return _ok({
            "total_chunks": 0,
            "chunks": [],
            "error": str(exc),
        })
