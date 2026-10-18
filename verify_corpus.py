"""Prove the seeded library ranks by meaning, not keywords.

Decision 5's confusable pairs only matter if search serves the right case for a
colloquial probe. This script embeds a few live phrasings and checks that the
correct seed case ranks above its surface-similar sibling.

Usage:
    uv run python verify_corpus.py --probe "when the header sticks the hero breaks"
    uv run python verify_corpus.py           # run the built-in probes
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import asyncpg

from frontend_workspace_mcp.server import (
    NEON_DATABASE_URL,
    _embed_texts,
    _EMBEDDING_MODELS,
    _embedding_order,
    _vector_literal,
)

# probe text -> an authoritative phrase the matching seed title must contain.
PROBES: list[tuple[str, str]] = [
    ("when the header sticks the hero section gets overlapped", "Navbar A"),
    ("checkout users press the order button twice and get two orders", "Form F"),
    ("keyboard users cannot sort the report columns", "Table J"),
    ("the page flashes white before the dark theme applies", "Theme L"),
    ("laggy pipette on the chart, tooltip lags behind the mouse", "Chart N"),
]

MODEL_SEARCH_REQUIRED = True


async def rank(pool: asyncpg.Pool, model: str, query: str, top: int = 4):
    vectors, used_model = await _embed_texts([query])
    if used_model != model:
        return None
    qliteral = _vector_literal(vectors[0])
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT d.title, e.embedding <=> $2::vector AS distance
            FROM embeddings e
            JOIN documents d ON d.id = e.document_id
            WHERE e.model = $1
            ORDER BY distance
            LIMIT $3
            """,
            model,
            qliteral,
            top,
        )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="append", default=[], help="extra probe phrasing")
    args = parser.parse_args()

    order = _embedding_order()
    model = _EMBEDDING_MODELS[order[0]]
    pool = await asyncpg.create_pool(
        NEON_DATABASE_URL, min_size=1, max_size=2, statement_cache_size=0, ssl="require"
    )
    failures: list[str] = []
    try:
        print(f"model {model}")
        for query, must_rank_first in PROBES + [(p, "") for p in args.probe]:
            rows = await rank(pool, model, query)
            if rows is None:
                print(f"SKIP (wrong model served): {query}")
                continue
            titles = [row["title"] for row in rows]
            marker = must_rank_first or ""
            headline = (
                f"{query!r}\n  top: {titles[0]} (d={rows[0]['distance']:.4f})"
                if titles
                else f"{query!r}\n  no rows"
            )
            print(headline)
            for row in rows[1:3]:
                print(f"  next: {row['title']} (d={row['distance']:.4f})")
            if marker and (not titles or marker not in titles[0]):
                failures.append(f"{marker} did not rank first for {query!r}; got {titles[0:1]}")
        if failures:
            for failure in failures:
                print(f"FAIL {failure}")
            return 1
        print("\ncorpus ranking verified.")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
