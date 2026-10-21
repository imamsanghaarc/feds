"""Scoped MCP server for FEDS, the Frontend Engineering Digital Specialist."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import urllib.request
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import asyncpg
from mcp.server.mcpserver import MCPServer

from provider_router import Provider, ProviderRouter

_EMBEDDING_ROUTER: ProviderRouter | None = None

from config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODELS as _EMBEDDING_MODELS,
    # Kept as module attributes so test_config's credential-parity check can
    # compare this process's copy against config's; calls use the per-provider
    # key from PROVIDER_API_KEYS.
    DATABASE_URL,
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_MODEL,
    GEMINI_NATIVE_BASE_URL as GEMINI_BASE_URL,
    NEON_DATABASE_URL,
    OPENAI_API_KEY,
    OPENAI_EMBEDDING_MODEL,
    PROVIDER_API_KEYS as _PROVIDER_API_KEYS,
    PROVIDER_COOLDOWN_SECONDS,
    embedding_order as _embedding_order,
)

_EMBEDDING_ROUTER: ProviderRouter | None = None


def embedding_router() -> ProviderRouter:
    """Process-wide embedding router (created lazily so tests can import first)."""
    global _EMBEDDING_ROUTER
    if _EMBEDDING_ROUTER is None:
        _EMBEDDING_ROUTER = ProviderRouter(
            [
                Provider(
                    name=name,
                    cooldown_seconds=PROVIDER_COOLDOWN_SECONDS,
                    metadata={
                        "model": _EMBEDDING_MODELS[name],
                        "api_key": _PROVIDER_API_KEYS.get(name, ""),
                    },
                )
                for name in _embedding_order()
            ],
            cooldown_seconds=PROVIDER_COOLDOWN_SECONDS,
            on_event=lambda message: print(message, file=sys.stderr),
        )
    return _EMBEDDING_ROUTER


def model_for_provider(provider_name: str) -> str:
    return _EMBEDDING_MODELS[provider_name]


def _validate(vector: list[float], provider_name: str) -> list[float]:
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"embedding dimension mismatch: {len(vector)} != {EMBEDDING_DIMENSIONS} "
            f"(provider={provider_name}, model={_EMBEDDING_MODELS[provider_name]})"
        )
    return vector


def _embed_openai(texts: list[str], api_key: str) -> list[list[float]]:
    from openai import OpenAI

    response = OpenAI(api_key=api_key).embeddings.create(
        model=OPENAI_EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    ordered = sorted(response.data, key=lambda item: item.index)
    return [_validate([float(v) for v in item.embedding], "openai") for item in ordered]


def _embed_gemini(texts: list[str], api_key: str) -> list[list[float]]:
    """Batch embed through Gemini's batchEmbedContents endpoint."""
    url = f"{GEMINI_BASE_URL}/models/{GEMINI_EMBEDDING_MODEL}:batchEmbedContents?key={api_key}"
    body = {
        "requests": [
            {
                "model": f"models/{GEMINI_EMBEDDING_MODEL}",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": EMBEDDING_DIMENSIONS,
            }
            for text in texts
        ]
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    return [
        _validate([float(value) for value in item["values"]], "gemini")
        for item in payload["embeddings"]
    ]


_EMBED_FNS = {"gemini": _embed_gemini, "openai": _embed_openai}


def _embed_texts_sync(texts: list[str], provider_name: str) -> list[list[float]]:
    """Embed a batch with one specific provider (no routing; used by the router)."""
    if not texts:
        return []
    cleaned = [text.strip()[:8000] or " " for text in texts]
    # "gemini-fallback" is the same client family as "gemini" on a second key,
    # so the credential rotates without the model label ever changing.
    family = provider_name.split("-", 1)[0]
    embed = _EMBED_FNS.get(family)
    if embed is None:
        raise RuntimeError(f"no embedding implementation for provider {provider_name!r}")
    return embed(cleaned, _PROVIDER_API_KEYS.get(provider_name, ""))


async def _embed_texts(
    texts: list[str],
) -> tuple[list[list[float]], str]:
    """Embed a batch, rotating providers on quota exhaustion.

    Returns the vectors together with the model that actually produced them, so
    callers never store a vector under the wrong model label.
    """
    if not texts:
        router = embedding_router()
        return [], model_for_provider(router.providers[0].name)

    router = embedding_router()

    async def attempt(provider: Provider) -> list[list[float]]:
        return await asyncio.to_thread(_embed_texts_sync, texts, provider.name)

    vectors, provider = await router.run(attempt)
    return vectors, model_for_provider(provider.name)


async def _embed_text(text: str) -> tuple[list[float], str]:
    if not text.strip():
        raise ValueError("text is required for embedding")
    (vector,), model = await _embed_texts([text])
    return vector, model


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(repr(value) for value in values) + "]"


# Chunking targets roughly 400 tokens (~300 words) with overlap, and prefers to
# break on natural boundaries so a chunk stays semantically self-contained.
CHUNK_WORDS = 300
CHUNK_OVERLAP_WORDS = 50
_BOUNDARIES = ("\n\n", "\n", ". ", ".\n", "! ", "? ", "; ", ", ")


def _split_on_boundaries(words: list[str]) -> list[list[str]]:
    """Group words into paragraphs, then split oversized paragraphs on sentences."""
    text = " ".join(words)
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [text]
    return [p.split() for p in paragraphs if p]


def _chunk_text(text: str) -> list[str]:
    """Chunk text at natural boundaries with a fixed word overlap."""
    words = (text or "").split()
    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []

    for paragraph in _split_on_boundaries(words):
        if len(paragraph) > CHUNK_WORDS:
            # Flush the pending chunk, then sentence-split the oversized block.
            if current:
                chunks.append(" ".join(current))
                current = current[-CHUNK_OVERLAP_WORDS:]
            joined = " ".join(paragraph)
            sentences = re.split(r"(?<=[.!?])\s+", joined)
            buffer: list[str] = []
            for sentence in sentences:
                buffer.extend(sentence.split())
                if len(buffer) >= CHUNK_WORDS:
                    chunks.append(" ".join(buffer))
                    buffer = buffer[-CHUNK_OVERLAP_WORDS:]
            if buffer:
                current = current + buffer
        else:
            current.extend(paragraph)
            if len(current) >= CHUNK_WORDS:
                chunks.append(" ".join(current))
                current = current[-CHUNK_OVERLAP_WORDS:]

    if current and " ".join(current).strip():
        tail = " ".join(current)
        if not chunks or tail != chunks[-1]:
            chunks.append(tail)
    return [chunk for chunk in chunks if chunk.strip()]


mcp = MCPServer(
    "frontend-workspace",
    instructions=(
        "Scoped runtime database surface for FEDS, the Frontend Engineering Digital Specialist. "
        "Save, search, lookup, list, review, and publish frontend tasks. "
        "publish_task only promotes human-approved tasks. Never run ad-hoc SQL."
    ),
)

_POOL: asyncpg.Pool | None = None


async def _pool() -> asyncpg.Pool:
    global _POOL
    if _POOL is None:
        _POOL = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            statement_cache_size=0,
            ssl="require",
        )
    return _POOL


async def _audit(action: str, target: str, payload: dict[str, Any], result: dict[str, Any]) -> None:
    pool = await _pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_log
                (conversation_id, actor, action, target, payload, result)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
            """,
            _conversation_id(),
            "mcp:frontend-workspace",
            action,
            target,
            json.dumps(payload),
            json.dumps(result),
        )


def _conversation_id() -> str | None:
    """Conversation id injected by the worker for this MCP process."""
    return os.getenv("FRONTEND_CONVERSATION_ID") or None


async def _record_capability(
    conversation_id: str,
    tool: str,
    arguments: dict[str, Any],
    result: dict[str, Any] | None,
    status: str,
    latency_ms: int,
) -> None:
    """Best-effort metrics write. Never raises."""
    try:
        pool = await _pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO capability_invocations
                    (conversation_id, capability, arguments, result, status, latency_ms)
                VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6)
                """,
                conversation_id,
                tool,
                json.dumps(_truncate(arguments)),
                json.dumps(_truncate(result)) if result is not None else None,
                status,
                latency_ms,
            )
    except Exception:
        # Telemetry must never fail a business call. Intentionally swallowed.
        return


@asynccontextmanager
async def _invocation(tool: str, arguments: dict[str, Any]):
    """Record one capability invocation with latency and outcome.

    Metrics go to capability_invocations (quantitative) while audit_log keeps
    the narrative trace. Metrics failures must never break the tool call.

    NOTE: this must never `return` from the `finally` block. A generator that
    returns while an exception is propagating swallows it, which would turn a
    refused publish into a silent success. Logging is delegated to a plain
    async function so the control flow here stays trivial.
    """
    started = time.perf_counter()
    status = "ok"
    result: dict[str, Any] | None = None
    try:
        yield
    except BaseException:
        status = "error"
        raise
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)
        conversation_id = _conversation_id()
        if conversation_id:
            await _record_capability(
                conversation_id, tool, arguments, result, status, latency_ms
            )


def _truncate(value: Any, limit: int = 400) -> Any:
    """Bound payloads so metrics/audit rows stay small."""
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, dict):
        return {key: _truncate(item, limit) for key, item in value.items()}
    if isinstance(value, list):
        return [_truncate(item, limit) for item in value[:20]]
    return value


def _as_dict(metadata: Any) -> dict[str, Any]:
    if isinstance(metadata, str):
        try:
            return json.loads(metadata)
        except json.JSONDecodeError:
            return {}
    return metadata or {}


@mcp.tool()
async def lookup_task(name: str, status: str | None = None) -> dict[str, Any]:
    """Lookup a saved frontend task by name."""
    name = name.strip()
    if not name:
        raise ValueError("name is required")

    async with _invocation("lookup_task", {"name": name, "status": status}):
        pool = await _pool()
        if status is not None:
            query = """
                SELECT id, title, body, metadata, updated_at
                FROM documents
                WHERE source = 'frontend-task'
                  AND lower(title) = lower($1)
                  AND (metadata->>'status') = $2
                ORDER BY updated_at DESC
                LIMIT 1
            """
            params = [name, status]
        else:
            query = """
                SELECT id, title, body, metadata, updated_at
                FROM documents
                WHERE source = 'frontend-task'
                  AND lower(title) = lower($1)
                ORDER BY updated_at DESC
                LIMIT 1
            """
            params = [name]

        row = await pool.fetchrow(query, *params)
        await _audit(
            "capability_invoked",
            "frontend-workspace",
            {"tool": "lookup_task", "name": name, "status": status},
            {"found": row is not None},
        )
        if row is None:
            return {"found": False, "name": name, "status": status}
        metadata = _as_dict(row["metadata"])
        return {
            "found": True,
            "id": str(row["id"]),
            "name": row["title"],
            "status": metadata.get("status", status),
            "framework": metadata.get("framework"),
            "metadata": metadata,
            "updated_at": row["updated_at"].isoformat(),
        }


@mcp.tool()
async def list_tasks(
    status: str | None = None,
    framework: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """List saved frontend tasks, optionally filtered by lifecycle status or framework."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    async with _invocation("list_tasks", {"status": status, "framework": framework, "limit": limit}):
        pool = await _pool()
        rows = await pool.fetch(
            """
            SELECT id, title, body, metadata, updated_at
            FROM documents
            WHERE source = 'frontend-task'
              AND ($1::text IS NULL OR metadata->>'status' = $1)
              AND ($2::text IS NULL OR lower(metadata->>'framework') = lower($2))
            ORDER BY updated_at DESC
            LIMIT $3
            """,
            status,
            framework,
            limit,
        )
        tasks = [
            {
                "id": str(row["id"]),
                "name": row["title"],
                "status": _as_dict(row["metadata"]).get("status"),
                "framework": _as_dict(row["metadata"]).get("framework"),
                "summary": row["body"][:280],
                "updated_at": row["updated_at"].isoformat(),
            }
            for row in rows
        ]
        await _audit(
            "capability_invoked",
            "frontend-workspace",
            {"tool": "list_tasks", "status": status, "framework": framework},
            {"count": len(tasks)},
        )
        return {"tasks": tasks, "count": len(tasks)}


@mcp.tool()
async def find_similar_tasks(description: str, framework: str | None = None, limit: int = 5) -> dict[str, Any]:
    """Find saved frontend tasks relevant to a description."""
    description = description.strip()
    if not description:
        raise ValueError("description is required")
    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20")

    async with _invocation(
        "find_similar_tasks",
        {"description": description, "framework": framework, "limit": limit},
    ):
        pool = await _pool()
        # Scope the vector search to the model that embedded the query so vectors
        # from a different model are never compared in the wrong space.
        query_embedding, query_model = await _embed_text(description)
        query_vector = _vector_literal(query_embedding)
        rows = await pool.fetch(
            """
            SELECT ranked.id, ranked.title, ranked.body, ranked.metadata,
                   ranked.updated_at, ranked.distance
            FROM (
                SELECT DISTINCT ON (d.id)
                       d.id, d.title, d.body, d.metadata, d.updated_at,
                       (e.embedding <=> $1::vector) AS distance
                FROM documents d
                JOIN embeddings e ON e.document_id = d.id
                WHERE d.source = 'frontend-task'
                  AND e.embedding IS NOT NULL
                  AND e.model = $3
                  AND ($4::text IS NULL OR lower(d.metadata->>'framework') = lower($4))
                ORDER BY d.id, distance ASC
            ) AS ranked
            ORDER BY ranked.distance ASC, ranked.updated_at DESC
            LIMIT $2
            """,
            query_vector,
            limit,
            query_model,
            framework,
        )
        retrieval = "vector"
        if not rows:
            retrieval = "full_text"
            rows = await pool.fetch(
                """
                SELECT id, title, body, metadata, updated_at, NULL::float8 AS distance
                FROM documents
                WHERE source = 'frontend-task'
                  AND ($3::text IS NULL OR lower(metadata->>'framework') = lower($3))
                  AND to_tsvector(
                      'english',
                      coalesce(title, '') || ' ' || coalesce(body, '') || ' ' ||
                      coalesce(metadata->>'wcag_notes', '') || ' ' ||
                      coalesce(metadata->>'responsiveness_notes', '')
                  ) @@ plainto_tsquery('english', $1)
                ORDER BY ts_rank(
                    to_tsvector(
                      'english',
                      coalesce(title, '') || ' ' || coalesce(body, '') || ' ' ||
                      coalesce(metadata->>'wcag_notes', '') || ' ' ||
                      coalesce(metadata->>'responsiveness_notes', '')
                    ),
                    plainto_tsquery('english', $1)
                ) DESC,
                updated_at DESC
                LIMIT $2
                """,
                description,
                limit,
                framework,
            )

        matches = [
            {
                "id": str(row["id"]),
                "name": row["title"],
                "framework": _as_dict(row["metadata"]).get("framework"),
                "status": _as_dict(row["metadata"]).get("status"),
                "summary": row["body"][:500],
                "distance": round(float(row["distance"]), 4) if row["distance"] is not None else None,
                "updated_at": row["updated_at"].isoformat(),
            }
            for row in rows
        ]
        await _audit(
            "capability_invoked",
            "frontend-workspace",
            {"tool": "find_similar_tasks", "description": description[:500], "framework": framework},
            {"count": len(matches), "retrieval": retrieval, "model": query_model},
        )
        return {
            "matches": matches,
            "count": len(matches),
            "retrieval": retrieval,
            "embedding_model": query_model if retrieval == "vector" else None,
        }


@mcp.tool()
async def save_task(
    name: str,
    task: str,
    framework: str = "General Frontend",
    wcag_notes: str = "",
    responsiveness_notes: str = "",
) -> dict[str, Any]:
    """Save a narrowly typed frontend task or component design.

    Re-saving the same name updates the existing record instead of duplicating it.
    """
    name = name.strip()
    task = task.strip()
    if not name or not task:
        raise ValueError("name and task are required")

    async with _invocation(
        "save_task",
        {
            "name": name,
            "framework": framework,
            "wcag_notes": wcag_notes,
            "responsiveness_notes": responsiveness_notes,
        },
    ):
        pool = await _pool()

        # Embed before opening the transaction: network latency must never be
        # spent holding a database transaction open.
        chunks = _chunk_text(task)
        embed_inputs = [
            f"{name}. {chunk}. {wcag_notes} {responsiveness_notes}".strip()
            for chunk in chunks
        ]
        vectors, embed_model = await _embed_texts(embed_inputs)

        # Idempotent write: one canonical record per normalized task name.
        async with pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchval(
                    """
                    SELECT id FROM documents
                    WHERE source = 'frontend-task' AND lower(title) = lower($1)
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    name,
                )
                metadata = {
                    "framework": framework,
                    "wcag_notes": wcag_notes,
                    "responsiveness_notes": responsiveness_notes,
                    "status": "draft",
                }
                if existing is None:
                    document_id = await conn.fetchval(
                        """
                        INSERT INTO documents (source, title, body, metadata)
                        VALUES ($1, $2, $3, $4::jsonb)
                        RETURNING id
                        """,
                        "frontend-task",
                        name,
                        task,
                        json.dumps(metadata),
                    )
                    created = True
                else:
                    document_id = existing
                    created = False
                    await conn.execute(
                        """
                        UPDATE documents
                        SET body = $2,
                            metadata = metadata || $3::jsonb,
                            updated_at = now()
                        WHERE id = $1
                        """,
                        document_id,
                        task,
                        json.dumps(metadata),
                    )

                # Superseded vectors are dropped so retrieval never mixes
                # embeddings from different revisions or different models.
                await conn.execute(
                    "DELETE FROM embeddings WHERE document_id = $1",
                    document_id,
                )
                for chunk_index, (chunk, vector) in enumerate(zip(chunks, vectors)):
                    await conn.execute(
                        """
                        INSERT INTO embeddings
                            (document_id, chunk_text, chunk_index, embedding, model)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        document_id,
                        chunk[:6000],
                        chunk_index,
                        _vector_literal(vector),
                        embed_model,
                    )

                await conn.execute(
                    """
                    INSERT INTO audit_log
                        (conversation_id, actor, action, target, payload, result)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                    """,
                    _conversation_id(),
                    "mcp:frontend-workspace",
                    "capability_invoked",
                    "documents",
                    json.dumps(
                        {
                            "tool": "save_task",
                            "name": name,
                            "created": created,
                            "embedding_model": embed_model,
                        }
                    ),
                    json.dumps({"document_id": str(document_id), "chunks": len(chunks)}),
                )

        return {
            "saved": True,
            "created": created,
            "document_id": str(document_id),
            "name": name,
            "chunks_embedded": len(chunks),
            "embedding_model": embed_model,
        }


@mcp.tool()
async def record_review(name: str, status: str, reviewer: str, notes: str = "") -> dict[str, Any]:
    """Record review and quality outcomes for one task."""
    if status not in {"approved", "rejected", "needs_attention"}:
        raise ValueError("status must be approved, rejected, or needs_attention")
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValueError("reviewer is required")

    async with _invocation(
        "record_review",
        {"name": name, "status": status, "reviewer": reviewer, "notes": notes},
    ):
        pool = await _pool()
        row = await pool.fetchrow(
            """
            SELECT id FROM documents
            WHERE source = 'frontend-task' AND lower(title) = lower($1)
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            name.strip().lower(),
        )
        if row is None:
            raise ValueError(f"task not found: {name}")

        document_id = str(row["id"])
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE documents
                    SET metadata = metadata || $1::jsonb,
                        updated_at = now()
                    WHERE id = $2
                    """,
                    json.dumps(
                        {
                            "status": status,
                            "reviewer": reviewer,
                            "review_notes": notes,
                            "reviewed_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                    row["id"],
                )
                await conn.execute(
                    """
                    INSERT INTO audit_log
                        (conversation_id, actor, action, target, payload, result)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                    """,
                    _conversation_id(),
                    "mcp:frontend-workspace",
                    "capability_invoked",
                    "documents",
                    json.dumps({"tool": "record_review", "name": name, "status": status}),
                    json.dumps({"document_id": document_id}),
                )

        return {"reviewed": True, "document_id": document_id, "status": status}


@mcp.tool(
    annotations={"read_only_hint": False, "destructive_hint": False, "idempotent_hint": True}
)
async def publish_task(name: str, target: str = "staging") -> dict[str, Any]:
    """Move an approved frontend task into a publishable target state.

    This is the highest-trust write in this server: it only promotes tasks that
    a human already reviewed and approved. The database enforces approval via
    a trigger that requires a matching row in the approvals table.
    """
    name = name.strip()
    target = target.strip().lower()
    if not name:
        raise ValueError("name is required")
    if target not in {"staging", "production"}:
        raise ValueError("target must be staging or production")
    if target == "production" and os.getenv("ALLOW_PRODUCTION_PUBLISH") != "1":
        raise PermissionError(
            "production publish is disabled; set ALLOW_PRODUCTION_PUBLISH=1 to enable"
        )

    async with _invocation("publish_task", {"name": name, "target": target}):
        pool = await _pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT id, metadata FROM documents
                    WHERE source = 'frontend-task' AND lower(title) = lower($1)
                    ORDER BY updated_at DESC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    name,
                )
                if row is None:
                    raise ValueError(f"task not found: {name}")

                metadata = _as_dict(row["metadata"])
                if metadata.get("status") != "approved":
                    raise PermissionError(
                        f"task must be human-approved before publishing; current status is "
                        f"{metadata.get('status')!r}"
                    )

                document_id = str(row["id"])
                published_at = datetime.now(timezone.utc).isoformat()
                published = metadata.get("published") or {}
                published[target] = published_at
                # Store target in metadata so the trigger knows where it's being published
                metadata["published"] = published
                metadata["status"] = "published"
                metadata["published_target"] = target

                await conn.execute(
                    """
                    UPDATE documents
                    SET metadata = metadata || $1::jsonb, updated_at = now()
                    WHERE id = $2
                    """,
                    json.dumps({"published": published, "status": "published", "published_target": target}),
                    row["id"],
                )
                await conn.execute(
                    """
                    INSERT INTO audit_log
                        (conversation_id, actor, action, target, payload, result)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                    """,
                    _conversation_id(),
                    "mcp:frontend-workspace",
                    "capability_invoked",
                    "documents",
                    json.dumps({"tool": "publish_task", "name": name, "target": target}),
                    json.dumps({"document_id": document_id, "published_at": published_at}),
                )

        return {"published": True, "document_id": document_id, "name": name, "target": target}


# --- Memory (section 6a): private per-user memory plus the shared global layer.

GLOBAL_OWNER = "-"
"""Sentinel owner for global rows. They are readable by everyone, writable by
promotion only, and never deletable: the shared corpus must stay auditable."""


class IdentityError(RuntimeError):
    """Raised when no per-user identity is configured.

    Serving under one anonymous identity is how private memory leaks between
    users, so the server refuses rather than falling back to a shared bucket.
    """


def _identity_variants() -> list[str]:
    """Every configured spelling of this user's identity.

    `FRONTEND_USER_ID` is the isolation key; `FRONTEND_USER_NAME` is the
    display name the sanitizer must also refuse. Values shorter than three
    characters are ignored so a stub id cannot match unrelated text.
    """
    raw = [os.getenv("FRONTEND_USER_ID", ""), os.getenv("FRONTEND_USER_NAME", "")]
    return [value.strip() for value in raw if len(value.strip()) >= 3]


# Per-conversation user identity mapping (v1-11: Team Identity)
# Allows per-request user injection without process-level env var.
_user_identity_cache: dict[str, str] = {}  # conversation_id -> user_id


def set_conversation_user(conversation_id: str, user_id: str) -> None:
    """Set the user identity for a conversation (called by worker)."""
    if conversation_id and user_id:
        _user_identity_cache[conversation_id] = user_id.strip()


def clear_conversation_user(conversation_id: str) -> None:
    """Clear user identity for a conversation."""
    _user_identity_cache.pop(conversation_id, None)


def _requester() -> str:
    """The user this MCP process serves; the isolation boundary.

    Priority:
    1. Per-conversation user identity (set by worker via set_conversation_user)
    2. Process-level FRONTEND_USER_ID env var (fallback for backward compat)
    
    With no identity the server fails closed by refusing to serve, instead of
    silently merging every user into one private bucket.
    """
    conv_id = _conversation_id()
    if conv_id and conv_id in _user_identity_cache:
        return _user_identity_cache[conv_id]
    
    # Fallback to process-level env var
    user_id = (os.getenv("FRONTEND_USER_ID") or "").strip()
    if not user_id:
        raise IdentityError(
            "FRONTEND_USER_ID is not configured; refusing to serve personal memory"
        )
    return user_id


_SECRET_MARKERS = re.compile(
    r"(api[_-]?key|token|password|secret|bearer)\s*[=:]\s*\S", re.I
)

# Code-shaped material that must not travel to the shared layer. A promoted
# lesson is framework-level knowledge, not someone's implementation: the FTE is
# expected to rewrite it as prose and pass that as `sanitized_body`. This is a
# backstop against a raw implementation slipping through, not a code parser.
_CODE_MARKERS = (
    re.compile(r"```"),  # a fenced code block
    re.compile(r"^\s*(?:import|export|const|let|var|function|class)\s", re.M),
    re.compile(r"\brequire\s*\("),
    re.compile(r"<[A-Z][A-Za-z0-9]*[\s/>]"),  # JSX / component tag
    re.compile(r"(?:\.{1,2}/|[A-Za-z]:\\|\\\\)"),  # local or absolute path
)


def _assert_sanitizable(body: str) -> None:
    """Refuse a promotion body that still carries identity, secrets, or code.

    Identity and credentials are whole-token checks; code is a heuristic
    backstop. All three run before the human sees the request, so only prose the
    FTE wrote for publication can reach the shared layer.
    """
    lowered = body.lower()
    for variant in _identity_variants():
        if re.search(rf"(?<![a-z0-9]){re.escape(variant.lower())}(?![a-z0-9])", lowered):
            raise PermissionError(
                "memory contains the author's identity; sanitize it before promoting"
            )
    if _SECRET_MARKERS.search(body):
        raise PermissionError(
            "memory looks like it carries a credential; sanitize it before promoting"
        )
    for marker in _CODE_MARKERS:
        if marker.search(body):
            raise PermissionError(
                "memory still looks like code; rewrite it as framework-level "
                "prose before promoting"
            )


@mcp.tool()
async def save_memory(body: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Save one lesson, preference, or correction as private memory for this user."""
    body = body.strip()
    if not body:
        raise ValueError("body is required")
    if len(body) > 4000:
        raise ValueError("body must stay under 4000 characters; split it into lessons")
    metadata = dict(metadata or {})

    async with _invocation("save_memory", {"body_len": len(body)}):
        pool = await _pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                memory_id = await conn.fetchval(
                    """
                    INSERT INTO memories (scope, owner, body, metadata)
                    VALUES ('private', $1, $2, $3::jsonb)
                    RETURNING id
                    """,
                    _requester(),
                    body,
                    json.dumps(metadata),
                )
                await conn.execute(
                    """
                    INSERT INTO audit_log
                        (conversation_id, actor, action, target, payload, result)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                    """,
                    _conversation_id(),
                    "mcp:frontend-workspace",
                    "capability_invoked",
                    "memories",
                    json.dumps({"tool": "save_memory", "scope": "private"}),
                    json.dumps({"memory_id": str(memory_id)}),
                )
        return {"saved": True, "memory_id": str(memory_id), "scope": "private"}


@mcp.tool()
async def list_memories(limit: int = 25) -> dict[str, Any]:
    """List this user's private memories and the shared global layer.

    Isolation lives in the SQL: a private row is only returned when its owner
    matches this requester, so another user's lessons can never be read here.
    """
    limit = max(1, min(int(limit), 100))
    async with _invocation("list_memories", {"limit": limit}):
        pool = await _pool()
        rows = await pool.fetch(
            """
            SELECT id, scope, owner, body, metadata, status, verification, created_at
            FROM memories
            WHERE (scope = 'global' AND owner = $1)
               OR (scope = 'private' AND owner = $2)
            ORDER BY created_at DESC
            LIMIT $3
            """,
            GLOBAL_OWNER,
            _requester(),
            limit,
        )
        return {
            "requester": _requester(),
            "count": len(rows),
            "memories": [
                {
                    "id": str(row["id"]),
                    "scope": row["scope"],
                    "body": row["body"],
                    "metadata": _as_dict(row["metadata"]),
                    "status": row["status"],
                    "verification": row["verification"],
                }
                for row in rows
            ],
        }


@mcp.tool()
async def delete_memory(memory_id: str) -> dict[str, Any]:
    """Delete one of this user's active private memories.

    Promoted rows are kept: the global copy references them as provenance, so
    removing the origin would break the chain. Global rows are never deletable.
    """
    memory_id = memory_id.strip()
    async with _invocation("delete_memory", {"memory_id": memory_id}):
        pool = await _pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    DELETE FROM memories
                    WHERE id = $1
                      AND scope = 'private'
                      AND owner = $2
                      AND status = 'active'
                    RETURNING id
                    """,
                    uuid.UUID(memory_id) if memory_id else uuid.UUID(int=0),
                    _requester(),
                )
                if row is None:
                    raise PermissionError(
                        "memory not found among this user's active private "
                        "memories; global and promoted rows are never deletable"
                    )
                await conn.execute(
                    """
                    INSERT INTO audit_log
                        (conversation_id, actor, action, target, payload, result)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                    """,
                    _conversation_id(),
                    "mcp:frontend-workspace",
                    "capability_invoked",
                    "memories",
                    json.dumps({"tool": "delete_memory", "memory_id": memory_id}),
                    json.dumps({"deleted": True}),
                )
        return {"deleted": True, "memory_id": memory_id}


@mcp.tool()
async def set_user(user_id: str, user_name: str = "") -> dict[str, Any]:
    """Set the user identity for the current conversation (v1-11: Team Identity).

    Called by the worker at the start of each task to establish per-request
    user identity for memory isolation. This allows multiple users to share
    the same MCP server process while maintaining strict memory isolation.

    Args:
        user_id: The unique identifier for the user (required).
        user_name: Optional display name for the user.
    """
    user_id = user_id.strip()
    if not user_id:
        raise ValueError("user_id is required")
    if len(user_id) < 3:
        raise ValueError("user_id must be at least 3 characters")
    
    conv_id = _conversation_id()
    if not conv_id:
        raise PermissionError("No conversation ID available; cannot set user identity")
    
    set_conversation_user(conv_id, user_id)
    
    # Also store user_name if provided
    if user_name:
        user_name = user_name.strip()
        # Store in cache with a suffix
        _user_identity_cache[f"{conv_id}:name"] = user_name
    
    await _audit(
        "capability_invoked",
        "frontend-workspace",
        {"tool": "set_user", "user_id": user_id},
        {"status": "ok", "conversation_id": conv_id},
    )
    
    return {"ok": True, "user_id": user_id, "conversation_id": conv_id}


@mcp.tool()
async def get_current_user() -> dict[str, Any]:
    """Get the current user identity for the conversation."""
    conv_id = _conversation_id()
    if not conv_id:
        return {"user_id": None, "user_name": None}
    
    user_id = _user_identity_cache.get(conv_id)
    user_name = _user_identity_cache.get(f"{conv_id}:name")
    
    if not user_id:
        # Fallback to env var
        user_id = (os.getenv("FRONTEND_USER_ID") or "").strip() or None
        user_name = (os.getenv("FRONTEND_USER_NAME") or "").strip() or None
    
    return {"user_id": user_id, "user_name": user_name, "conversation_id": conv_id}


async def _promote_memory_in(
    conn: Any, memory_id: str, sanitized_body: str, verification: str
) -> dict[str, Any]:
    """The promotion transaction body, on a caller-provided connection.

    Now calls the SECURITY DEFINER function promote_memory() which enforces
    approval via the approvals table. The function returns the global_id.
    """
    # Validate locally first (sanitization, gates) before calling DB function
    row = await conn.fetchrow(
        """
        SELECT id, scope, owner, body, metadata, status
        FROM memories
        WHERE id = $1
          AND scope = 'private'
          AND owner = $2
          AND status = 'active'
        FOR UPDATE
        """,
        uuid.UUID(memory_id) if memory_id else uuid.UUID(int=0),
        _requester(),
    )
    if row is None:
        raise PermissionError(
            "active private memory not found for this user; nothing was promoted"
        )
    metadata = _as_dict(row["metadata"])
    if metadata.get("project_specific"):
        raise PermissionError(
            "memory is marked project_specific; generalizable lessons only"
        )
    if metadata.get("generalizable") is not True:
        raise PermissionError(
            "memory is not flagged generalizable; set metadata "
            "generalizable=true on framework-level lessons before promoting"
        )
    _assert_sanitizable(sanitized_body)

    # Call the SECURITY DEFINER function which:
    # 1. Re-validates the private memory exists and is promotable
    # 2. Checks for approval in approvals table
    # 3. Inserts the global row with sanitized body
    # 4. Updates the origin memory status
    # 5. Returns the global_id
    global_id = await conn.fetchval(
        "SELECT promote_memory($1, $2, $3)",
        row["id"],
        sanitized_body,
        verification,
    )
    await conn.execute(
        """
        INSERT INTO audit_log
            (conversation_id, actor, action, target, payload, result)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
        """,
        _conversation_id(),
        "mcp:frontend-workspace",
        "capability_invoked",
        "memories",
        json.dumps(
            {
                "tool": "promote_memory",
                "memory_id": memory_id,
                "verified_by": verification,
            }
        ),
        json.dumps({"global_id": str(global_id)}),
    )
    return {
        "promoted": True,
        "global_id": str(global_id),
        "verification": verification,
    }


@mcp.tool(
    annotations={"read_only_hint": False, "destructive_hint": False, "idempotent_hint": False}
)
async def promote_memory(
    memory_id: str, sanitized_body: str, verification: str
) -> dict[str, Any]:
    """Promote one private memory to the shared global layer.

    Like `publish_task`, this is the human-gated write: it pauses for approval
    before anything shared is created. All three gates must hold:

    1. verified - recorded by the `verification` argument (a reviewer's name,
       an eval id, or an automated check), not merely asserted;
    2. generalizable - the lesson must be flagged `generalizable` and must not
       be flagged `project_specific`;
    3. sanitized - `sanitized_body` is the FTE's framework-level rewrite. The
       raw private body never leaves the private layer, and identity,
       credential-shaped text, and code are refused outright.

    Needs `FRONTEND_USER_ID`-independent human attribution, which the approval
    operator supplies when resuming.
    """
    memory_id = memory_id.strip()
    sanitized_body = sanitized_body.strip()
    verification = verification.strip()
    if not verification:
        raise ValueError(
            "verification is required: record who or what verified this lesson"
        )
    if not sanitized_body:
        raise ValueError(
            "sanitized_body is required: rewrite the lesson as framework-level "
            "prose with no user code, names, or identifiers, then promote that"
        )
    async with _invocation(
        "promote_memory", {"memory_id": memory_id, "verified_by": verification}
    ):
        pool = await _pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                return await _promote_memory_in(
                    conn, memory_id, sanitized_body, verification
                )


def main() -> None:
    # Default to stdio: the worker spawns this server as a child process, and
    # promotion approval is enforced by the worker, so a network endpoint is a
    # bypass unless it is deliberately opted into.
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        mcp.run(transport="stdio")
        return
    host = os.getenv("MCP_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "::1", "localhost"} and os.getenv("MCP_ALLOW_REMOTE") != "1":
        raise SystemExit(
            f"refusing to bind MCP_HOST={host!r}: promotion approval is enforced "
            "in the worker, so a remote MCP endpoint would bypass it. Bind "
            "loopback, or set MCP_ALLOW_REMOTE=1 only behind an authenticating proxy."
        )
    port = int(os.getenv("MCP_PORT", "8001"))
    mcp.run(transport="streamable-http", host=host, port=port, path="/mcp")


if __name__ == "__main__":
    main()
