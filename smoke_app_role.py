"""Live proof that the runtime database role is least-privilege (opt-in).

The deployed worker and MCP server should not hold the schema owner credential.
`setup_neon.py` can create a restricted `feds_app` login and the runtime points
`FEDS_APP_DATABASE_URL` at it; this script checks the result against the live
branch:

1. the runtime really connects as that non-owner role, and is not a member of
   the owner role;
2. it can read the working tables (its grants are functional);
3. DDL is refused -- `CREATE TABLE`, `CREATE SCHEMA`, `ALTER TABLE`, and
   `DROP TABLE` all fail with a privilege error, each inside a transaction that
   is rolled back so nothing is left behind.

Skips cleanly when `FEDS_APP_DATABASE_URL` is unset (single-credential
deployment). Spends no model quota.

    uv run python smoke_app_role.py
"""

from __future__ import annotations

import asyncio
import sys
from urllib.parse import urlsplit

import asyncpg

import config

# Every probe is wrapped in a transaction we always roll back, so a probe that
# is wrongly permitted still leaves no trace.
_DDL_PROBES = (
    ("CREATE TABLE", "CREATE TABLE _feds_priv_probe (id int)"),
    ("CREATE SCHEMA", "CREATE SCHEMA _feds_priv_probe"),
    ("ALTER TABLE", "ALTER TABLE memories ADD COLUMN _feds_priv_probe int"),
    ("DROP TABLE", "DROP TABLE memories"),
)


async def _must_refuse(conn: asyncpg.Connection, label: str, statement: str) -> None:
    transaction = conn.transaction()
    await transaction.start()
    refused: str | None = None
    try:
        await conn.execute(statement)
    except asyncpg.PostgresError as exc:
        refused = type(exc).__name__
    finally:
        # Always roll back: a wrongly-permitted probe must leave no trace.
        await transaction.rollback()
    if refused is None:
        raise SystemExit(f"[FAIL] {label} was permitted; the role is not least-privilege")
    print(f"  refused {label}: {refused}")


async def _exercise_worker_writes(conn: asyncpg.Connection) -> None:
    """Write the rows a real turn writes, then roll back.

    Least-privilege is easy to get wrong in the direction of too little: a
    missing grant would only surface mid-turn. Prove the granted set covers the
    worker's own writes (including the two sequence-backed ids).
    """
    transaction = conn.transaction()
    await transaction.start()
    try:
        conversation_id = "feds-role-probe"
        await conn.execute(
            "INSERT INTO conversations (session_id, user_id) VALUES ($1, $2)",
            conversation_id,
            "feds-role-probe",
        )
        await conn.execute(
            "INSERT INTO agent_sessions (session_id) VALUES ($1)", conversation_id
        )
        await conn.execute(
            "INSERT INTO agent_messages (session_id, message_data) VALUES ($1, $2)",
            conversation_id,
            "{}",
        )
        await conn.execute(
            "INSERT INTO run_states "
            "(run_id, conversation_id, tool_name, state_text, status) "
            "VALUES ($1, $2, $3, $4, 'awaiting')",
            "feds-role-probe-run",
            conversation_id,
            "promote_memory",
            "state",
        )
        await conn.execute(
            "UPDATE run_states SET status = 'approved', operator = $2 WHERE run_id = $1",
            "feds-role-probe-run",
            "probe",
        )
        await conn.execute(
            "INSERT INTO capability_invocations "
            "(conversation_id, capability, arguments, status) "
            "VALUES ($1, $2, '{}'::jsonb, 'ok')",
            conversation_id,
            "chat.turn",
        )
        await conn.execute(
            "INSERT INTO audit_log (conversation_id, actor, action, payload) "
            "VALUES ($1, $2, 'message_received', '{}'::jsonb)",
            conversation_id,
            "feds-role-probe",
        )
    finally:
        await transaction.rollback()
    print(
        "  worker write path succeeded (conversations, agent_sessions, "
        "agent_messages, run_states, capability_invocations, audit_log), rolled back"
    )


async def _check_sqlalchemy_engine(expected_role: str) -> None:
    """The worker reaches Postgres through SQLAlchemy, not raw asyncpg.

    Same URL derivation the worker uses, so a shape the raw driver accepts but
    the engine does not (or vice versa) is caught here rather than mid-turn.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine_url = config.DATABASE_URL.split("?", 1)[0].replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )
    engine = create_async_engine(
        engine_url,
        connect_args={"ssl": "require", "statement_cache_size": 0},
        pool_pre_ping=True,
    )
    try:
        async with engine.begin() as db:
            current = (await db.execute(text("SELECT current_user"))).scalar_one()
        print(f"  SQLAlchemy async engine connects as {current!r}")
        assert current == expected_role, current
    finally:
        await engine.dispose()


async def main() -> int:
    if not config.FEDS_APP_DATABASE_URL:
        print(
            "[SKIP] FEDS_APP_DATABASE_URL is not set; the runtime uses the schema "
            "owner credential (see deployment.md)."
        )
        return 0

    expected_role = urlsplit(config.FEDS_APP_DATABASE_URL).username or ""
    conn = await asyncpg.connect(config.DATABASE_URL)
    try:
        role = await conn.fetchval("SELECT current_user")
        is_member = await conn.fetchval(
            "SELECT pg_has_role(current_user, $1, 'MEMBER')", "neondb_owner"
        )
        elevated = await conn.fetchrow(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
            "FROM pg_roles WHERE rolname = current_user"
        )
        print(f"runtime connects as {role!r}; member of neondb_owner={is_member}")
        assert role == expected_role, f"expected {expected_role!r}, connected as {role!r}"
        assert not is_member, "the runtime role must not be a member of the owner role"
        assert not elevated["rolsuper"], "the runtime role must not be a superuser"
        assert not elevated["rolcreatedb"] and not elevated["rolcreaterole"], (
            "the runtime role must not create databases or roles"
        )
        assert not elevated["rolbypassrls"], "the runtime role must not bypass RLS"

        counts = await conn.fetchrow(
            "SELECT (SELECT count(*) FROM memories) AS memories, "
            "(SELECT count(*) FROM run_states) AS run_states, "
            "(SELECT count(*) FROM audit_log) AS audit_log"
        )
        print(f"  read granted tables ok: {dict(counts)}")

        print("--- the runtime can complete the worker's write path ---")
        await _exercise_worker_writes(conn)

        print("--- the worker's SQLAlchemy path uses the same credential ---")
        await _check_sqlalchemy_engine(expected_role)

        for label, statement in _DDL_PROBES:
            await _must_refuse(conn, label, statement)
    finally:
        await conn.close()

    print("[PASS] runtime role is least-privilege")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
