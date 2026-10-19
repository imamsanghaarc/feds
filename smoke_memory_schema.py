"""Prove the memory layer's database-level rules against the live workspace.

`server.py` enforces the promotion gates in code and `smoke_memory.py` proves
them through the tools. This proves the same rules also hold at the database,
so a direct connection cannot bypass them:

1. A global row must use the sentinel owner `-`.
2. A global row must carry promotion attribution (`promoted_by`).
3. Global rows are append-only: UPDATE and DELETE are refused by a trigger.
4. The two promotion writes themselves (`_PROMOTE_ORIGIN_SQL` on a private row
   and `_PROMOTE_GLOBAL_SQL` on the shared row) are accepted by the schema —
   the private update is not blocked by the append-only trigger.

Every probe runs inside a transaction (with per-probe savepoints) that is rolled
back, so the shared layer is never actually written. Runs as the runtime
credential (`config.DATABASE_URL`), so "a direct connection cannot bypass them"
is proven against the same restricted role the server uses. Zero model quota.

Usage:
    uv run python smoke_memory_schema.py
"""

from __future__ import annotations

import asyncio
import json
import sys

import asyncpg

import config
from frontend_workspace_mcp import server


async def refuses(conn, label: str, sql: str, *args) -> None:
    """Assert the database refuses a write that must never be allowed.

    Each probe runs in its own savepoint so a rejected statement does not
    poison the surrounding transaction; the savepoint is rolled back either
    way, so nothing persists.
    """
    savepoint = conn.transaction()
    await savepoint.start()
    try:
        await conn.execute(sql, *args)
    except asyncpg.PostgresError as exc:
        first_line = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        print(f"  database refuses ({label}): {first_line[:84]}")
        await savepoint.rollback()
        return
    await savepoint.rollback()
    raise AssertionError(f"{label}: the database allowed a write it must refuse")


async def main() -> int:
    if not config.DATABASE_URL:
        for problem in config.require_config() or ["NEON_DATABASE_URL is not set."]:
            print(f"[ERROR] {problem}")
        return 1

    conn = await asyncpg.connect(config.DATABASE_URL)
    outer = conn.transaction()
    await outer.start()
    try:
        print("--- the shared sentinel owner is enforced at the database ---")
        await refuses(
            conn,
            "global row with a non-sentinel owner",
            server._PROMOTE_GLOBAL_SQL,
            "intruder",
            "hardening probe",
            "{}",
            "probe",
            "probe",
        )

        print("--- promotion attribution is enforced at the database ---")
        await refuses(
            conn,
            "global row without promoted_by",
            server._PROMOTE_GLOBAL_SQL,
            server.GLOBAL_OWNER,
            "hardening probe",
            "{}",
            "probe",
            None,
        )

        print("--- the real promotion writes are accepted by the schema ---")
        private_id = await conn.fetchval(
            """
            INSERT INTO memories (scope, owner, body, metadata)
            VALUES ('private', 'smoke-schema-probe', 'private probe', '{}'::jsonb)
            RETURNING id
            """
        )
        await conn.execute(
            server._PROMOTE_ORIGIN_SQL, private_id, "probe verification", "probe"
        )
        origin = await conn.fetchrow(
            "SELECT scope, status, promoted_by FROM memories WHERE id = $1", private_id
        )
        assert origin["status"] == "promoted" and origin["promoted_by"] == "probe", origin
        print("  private origin row promotes (append-only trigger allows private updates)")
        global_id = await conn.fetchval(
            server._PROMOTE_GLOBAL_SQL,
            server.GLOBAL_OWNER,
            "hardening probe row (rolled back)",
            json.dumps({"promoted_by": "probe", "probe": True}),
            "probe verification",
            "probe",
        )
        shared = await conn.fetchrow(
            "SELECT owner, promoted_by FROM memories WHERE id = $1", global_id
        )
        assert origin["status"] == "promoted" and origin["promoted_by"] == "probe", origin
        assert shared["owner"] == server.GLOBAL_OWNER and shared["promoted_by"] == "probe", shared
        print(
            f"  shared row is accepted (id={str(global_id)[:8]}..., "
            f"owner={shared['owner']!r}, promoted_by={shared['promoted_by']!r})"
        )

        print("--- global rows are append-only ---")
        await refuses(
            conn,
            "update of a global row",
            "UPDATE memories SET body = 'tampered' WHERE id = $1",
            global_id,
        )
        await refuses(
            conn,
            "delete of a global row",
            "DELETE FROM memories WHERE id = $1",
            global_id,
        )
    finally:
        await outer.rollback()
        await conn.close()

    print("--- database-level memory rules hold: PASS ---")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
