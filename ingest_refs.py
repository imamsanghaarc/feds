"""Ingest external reference material into the semantic library.

`seed_corpus.py` covers resolved frontend cases authored by hand. This reader
covers everything else an engineer drops in: pattern notes, article summaries,
component-library docs, review checklists. Each file becomes one `documents`
row plus its chunked `embeddings`, stamped with the source label it came from,
so `find_similar_tasks` retrieves it alongside task history.

Conventions shared with `seed_corpus.py` and `reembed.py`:

- the stored chunk text is the raw body; the embedding input also carries the
  title and any frontmatter `context`, so retrieval keys on meaning, not on
  keyword overlap;
- the model that produced a vector is recorded on every row (search is
  model-scoped; vectors from different models are never compared);
- a file's title comes from frontmatter `title:` when present, otherwise from
  a humanized file name.

Idempotent: a file whose (source, title) is already stored is skipped, so
adding files and re-running only ingests the new ones. Files that fail to
embed are reported and leave nothing behind, so a partial run can be retried.

Usage:
    uv run python ingest_refs.py --dir docs/reference            # dry-run
    uv run python ingest_refs.py --dir docs/reference --list     # enumerate only
    uv run python ingest_refs.py --dir docs/reference --apply
    uv run python ingest_refs.py --dir notes --source design-notes --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import asyncpg

from frontend_workspace_mcp.server import (
    NEON_DATABASE_URL,
    _chunk_text,
    _embed_texts,
    _embedding_order,
    _EMBEDDING_MODELS,
    _vector_literal,
)
from worker import _frontmatter

DEFAULT_SOURCE = "reference-doc"
TEXT_SUFFIXES = {".md", ".markdown", ".txt"}


def iter_reference_files(root: Path) -> list[Path]:
    """Every ingestible file under root, sorted for a stable report."""
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
    )


def _title_from_path(path: Path) -> str:
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    if not stem:
        return path.name
    return stem[:1].upper() + stem[1:]


def parse_reference(text: str, path: Path, source: str) -> dict | None:
    """Normalize one file into a document, or None when it has no content.

    The frontmatter block is split exactly the way `worker._frontmatter` reads
    it, so the title the ingester reports is the title the rest of the system
    would have seen.
    """
    fields = _frontmatter(text)
    body = text
    if fields:
        parts = text.split("---", 2)
        body = parts[2] if len(parts) >= 3 else text
    body = body.strip()
    if not body:
        return None

    title = (fields.get("title") or "").strip() or _title_from_path(path)
    return {
        "title": title,
        "body": body,
        "context": (fields.get("context") or "").strip(),
        "metadata": {
            "ingested_from": path.as_posix(),
            "source": source,
            "bytes": len(body.encode("utf-8")),
            "title_from": "frontmatter" if fields.get("title") else "filename",
        },
    }


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dir", required=True, help="directory of .md/.txt reference files")
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=f"stored source label for attribution (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--apply", action="store_true", help="insert and embed (default: dry-run)"
    )
    parser.add_argument(
        "--list", action="store_true", help="only list the files that would be read"
    )
    args = parser.parse_args()

    root = Path(args.dir)
    files = iter_reference_files(root)
    if not files:
        print(f"no .md/.txt files under {root}")
        return 1

    documents: list[dict] = []
    empty: list[Path] = []
    for path in files:
        parsed = parse_reference(
            path.read_text(encoding="utf-8", errors="replace"), path, args.source
        )
        if parsed is None:
            empty.append(path)
        else:
            documents.append(parsed)

    print(f"reference dir  : {root}")
    print(f"files found    : {len(files)}")
    print(f"empty          : {len(empty)} (nothing after frontmatter)")
    print(f"source label   : {args.source}")
    if args.list:
        for path in files:
            print(f"  - {path}")
        return 0

    order = _embedding_order()
    model = _EMBEDDING_MODELS[order[0]]
    print(f"embedding model: {model}")

    pool = await asyncpg.create_pool(
        NEON_DATABASE_URL,
        min_size=1,
        max_size=2,
        statement_cache_size=0,
        ssl="require",
    )
    try:
        rows = await pool.fetch(
            "SELECT lower(title) AS title FROM documents WHERE source = $1", args.source
        )
        existing = {row["title"] for row in rows}
        fresh = [doc for doc in documents if doc["title"].lower() not in existing]

        print(f"already stored : {len(documents) - len(fresh)}")
        print(f"to ingest      : {len(fresh)}")
        for doc in fresh:
            print(f"  - {doc['title']}  ({doc['metadata']['ingested_from']})")
        if not args.apply:
            print("\nDRY RUN. Re-run with --apply to insert and embed.")
            return 0
        if not fresh:
            print("\nnothing to do: every reference file is already stored.")
            return 0

        ingested = 0
        failures: list[str] = []
        for doc in fresh:
            chunks = _chunk_text(doc["body"]) or [doc["body"]]
            inputs = [
                f"{doc['title']}. {chunk}. {doc['context']}".strip() for chunk in chunks
            ]
            try:
                vectors, used_model = await _embed_texts(inputs)
            except Exception as exc:  # quota or provider failure: nothing is written
                failures.append(doc["title"])
                print(f"  [FAIL] {doc['title']}: {exc}")
                continue

            async with pool.acquire() as conn:
                async with conn.transaction():
                    document_id = await conn.fetchval(
                        """
                        INSERT INTO documents (source, title, body, metadata)
                        VALUES ($1, $2, $3, $4::jsonb)
                        RETURNING id
                        """,
                        args.source,
                        doc["title"],
                        doc["body"],
                        json.dumps(doc["metadata"]),
                    )
                    for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
                        await conn.execute(
                            """
                            INSERT INTO embeddings
                                (document_id, chunk_text, chunk_index, embedding, model)
                            VALUES ($1, $2, $3, $4, $5)
                            """,
                            document_id,
                            chunk[:6000],
                            index,
                            _vector_literal(vector),
                            used_model,
                        )
            ingested += 1
            print(f"  ingested {doc['title']!r} ({len(chunks)} chunks, {used_model})")

        print(f"\ndone: {ingested} reference document(s) ingested and embedded.")
        if failures:
            print(f"{len(failures)} file(s) failed to embed and were not written: {failures}")
            return 1
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
