"""Prove bulk reference ingestion live: attributed, chunked, idempotent.

Writes two disposable reference files into a temp directory, runs the real
`ingest_refs.py` CLI against it, proves a second run skips them, checks the
stored rows and their provenance, then removes everything it created.

    uv run python smoke_ingest.py

The source label is unique to this smoke test, so cleanup can never touch
library data.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import psycopg

from config import NEON_DATABASE_URL

SOURCE = "smoke-reference"
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def run(dir_path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "ingest_refs.py", "--dir", str(dir_path), "--source", SOURCE, "--apply"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent,
    )
    return proc.returncode, proc.stdout + proc.stderr


def cleanup() -> None:
    with psycopg.connect(NEON_DATABASE_URL) as conn:
        conn.execute("DELETE FROM documents WHERE source = %s", (SOURCE,))
        conn.commit()


def main() -> int:
    cleanup()  # in case an earlier run died before cleaning up

    root = Path(tempfile.mkdtemp(prefix="feds-smoke-refs-"))
    try:
        (root / "sticky-headers.md").write_text(
            "---\ntitle: Sticky header overlap on a marketing page\n"
            "context: layout stability checklist\n---\n\n"
            "The header overlapped the hero because a spacer div still reserved height "
            "for the old fixed header. Removing the spacer and placing the header in a "
            "reserved grid row restored the layout and brought CLS back under threshold.\n",
            encoding="utf-8",
        )
        (root / "grid-notes.txt").write_text(
            "CSS grid notes: use minmax with auto-fit for card rows, keep an explicit "
            "line for the header, and prefer aspect-ratio boxes so media reserves space "
            "before it decodes.\n",
            encoding="utf-8",
        )

        code, out = run(root)
        check("the ingester exits zero", code == 0, f"code={code}\n{out}")
        ingested = [line for line in out.splitlines() if line.strip().startswith("ingested ")]
        check("both documents are ingested", len(ingested) == 2, out)

        code, out = run(root)
        check("a second run exits zero", code == 0, f"code={code}\n{out}")
        check("a second run skips them (idempotent)", "nothing to do" in out, out)

        with psycopg.connect(NEON_DATABASE_URL) as conn:
            docs = conn.execute(
                "SELECT id, title, metadata FROM documents WHERE source = %s ORDER BY title",
                (SOURCE,),
            ).fetchall()
            check("two documents are stored", len(docs) == 2, str([row[1] for row in docs]))
            titles = {row[1] for row in docs}
            check(
                "the frontmatter title survives the round trip",
                "Sticky header overlap on a marketing page" in titles,
                str(titles),
            )
            check(
                "the file-name fallback title survives the round trip",
                "Grid notes" in titles,
                str(titles),
            )
            if docs:
                ids = [row[0] for row in docs]
                chunks = conn.execute(
                    "SELECT document_id, model, count(*), bool_and(length(chunk_text) > 0) "
                    "FROM embeddings WHERE document_id = ANY(%s) "
                    "GROUP BY document_id, model",
                    (ids,),
                ).fetchall()
                check("every document has embedded chunks", len(chunks) == 2, str(chunks))
                check("chunks carry non-empty text", all(row[3] for row in chunks), str(chunks))
                check("the embedding model is recorded", all(row[1] for row in chunks), str(chunks))
                meta = docs[0][2]
                check(
                    "provenance is stamped on the document",
                    meta.get("source") == SOURCE and bool(meta.get("ingested_from")),
                    str(meta),
                )
    finally:
        cleanup()
        shutil.rmtree(root, ignore_errors=True)

    if FAILURES:
        print(f"\n{len(FAILURES)} CHECKS FAILED: {FAILURES}")
        return 1
    print("\nREFERENCE INGESTION SMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
