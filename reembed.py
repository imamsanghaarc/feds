"""Re-embed stored documents with the currently configured embedding model.

Vectors from different embedding models are not comparable, so a model change
invalidates every previously stored vector. This helper rebuilds them safely and
is safe to re-run.

Usage:
    uv run python reembed.py --dry-run
    uv run python reembed.py --apply
    uv run python reembed.py --apply --purge-orphans
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import asyncpg

from frontend_workspace_mcp.server import (
    EMBEDDING_DIMENSIONS,
    NEON_DATABASE_URL,
    _chunk_text,
    _embed_texts,
    _embedding_order,
    _EMBEDDING_MODELS,
    embedding_router,
    _vector_literal,
)

SOURCE_FILTER = "frontend-task"


async def _stale_documents(pool: asyncpg.Pool, model: str) -> list[asyncpg.Record]:
    """Documents that have no embedding for the given model."""
    return await pool.fetch(
        """
        SELECT d.id, d.title, d.body, d.metadata
        FROM documents d
        WHERE d.source = $1
          AND NOT EXISTS (
              SELECT 1 FROM embeddings e
              WHERE e.document_id = d.id AND e.model = $2
          )
        ORDER BY d.created_at
        """,
        SOURCE_FILTER,
        model,
    )


async def _foreign_documents(pool: asyncpg.Pool, model: str) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        SELECT DISTINCT d.title, e.model
        FROM documents d
        JOIN embeddings e ON e.document_id = d.id
        WHERE d.source = $1 AND e.model <> $2
        ORDER BY d.title
        """,
        SOURCE_FILTER,
        model,
    )


async def _duplicate_titles(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    """Groups of same-named frontend tasks; the oldest row is kept."""
    return await pool.fetch(
        """
        SELECT lower(title) AS title, count(*) AS n,
               array_agg(id ORDER BY created_at) AS ids
        FROM documents
        WHERE source = $1
        GROUP BY lower(title)
        HAVING count(*) > 1
        ORDER BY lower(title)
        """,
        SOURCE_FILTER,
    )


async def _dedupe(pool: asyncpg.Pool) -> int:
    """Collapse duplicate task rows, keeping the newest record."""
    removed = 0
    for group in await _duplicate_titles(pool):
        ids = list(group["ids"])
        # array_agg ordered by created_at ascending, so the last id is newest.
        keep, drop = ids[-1], ids[:-1]
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM embeddings WHERE document_id = ANY($1::uuid[])",
                    drop,
                )
                deleted = await conn.execute(
                    "DELETE FROM documents WHERE id = ANY($1::uuid[])",
                    drop,
                )
        count = len(drop)
        removed += count
        print(f"  deduped {group['title']!r}: kept {keep}, removed {count}")
        _ = deleted
    return removed


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write changes (default is dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report only; this is the default behavior",
    )
    parser.add_argument(
        "--purge-orphans",
        action="store_true",
        help="delete embeddings whose model is not the active model",
    )
    parser.add_argument(
        "--dedupe",
        action="store_true",
        help="collapse duplicate same-named frontend tasks, keeping the newest",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="target embedding model (default: the primary provider's model)",
    )
    args = parser.parse_args()

    order = _embedding_order()
    model = args.model or _EMBEDDING_MODELS[order[0]]

    pool = await asyncpg.create_pool(
        NEON_DATABASE_URL,
        min_size=1,
        max_size=2,
        statement_cache_size=0,
        ssl="require",
    )
    try:
        print(f"target model      : {model} ({EMBEDDING_DIMENSIONS}d)")
        print(f"provider order    : {' -> '.join(order)}")
        print(f"router status     : {embedding_router().status()['active']}")

        stale = await _stale_documents(pool, model)
        foreign = await _foreign_documents(pool, model)
        active = await pool.fetchrow(
            "SELECT count(*) AS n FROM embeddings WHERE model = $1", model
        )
        obsolete = await pool.fetchrow(
            "SELECT count(*) AS n FROM embeddings WHERE model <> $1", model
        )
        duplicates = await _duplicate_titles(pool)

        print(f"documents needing : {len(stale)}")
        print(f"rows with target  : {active['n']}")
        print(f"rows other model  : {obsolete['n']}")
        for row in foreign:
            print(f"  stale: {row['title']!r} currently {row['model']}")
        print(f"duplicate titles  : {len(duplicates)}")
        for group in duplicates:
            print(f"  {group['title']!r} x{group['n']}")

        if not args.apply:
            print("\nDRY RUN. Re-run with --apply to rebuild these vectors.")
            return 0

        if args.dedupe:
            removed = await _dedupe(pool)
            print(f"deduped documents : {removed}")

        if not stale:
            print("nothing to re-embed.")
        for document in stale:
            metadata = document["metadata"] or {}
            if isinstance(metadata, str):
                import json

                metadata = json.loads(metadata)
            wcag = metadata.get("wcag_notes", "") or ""
            responsive = metadata.get("responsiveness_notes", "") or ""
            chunks = _chunk_text(document["body"] or "")
            if not chunks:
                print(f"  skipped {document['title']!r}: empty body")
                continue

            inputs = [
                f"{document['title']}. {chunk}. {wcag} {responsive}".strip()
                for chunk in chunks
            ]
            vectors, used_model = await _embed_texts(inputs)

            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "DELETE FROM embeddings WHERE document_id = $1",
                        document["id"],
                    )
                    for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
                        await conn.execute(
                            """
                            INSERT INTO embeddings
                                (document_id, chunk_text, chunk_index, embedding, model)
                            VALUES ($1, $2, $3, $4, $5)
                            """,
                            document["id"],
                            chunk[:6000],
                            index,
                            _vector_literal(vector),
                            used_model,
                        )
            print(
                f"  re-embedded {document['title']!r} "
                f"({len(chunks)} chunks, {used_model})"
            )

        if args.purge_orphans:
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM embeddings WHERE model <> $1", model
                )
            print(f"purged rows not matching {model}")

        print("done.")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))