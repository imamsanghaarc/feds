"""One-time Neon schema setup for FEDS, the Frontend Engineering Digital Specialist.

Reads the connection string from config (which loads .env / the environment).
Run `uv run python setup_neon.py` after setting NEON_DATABASE_URL.

When `FEDS_APP_DB_PASSWORD` is set it also provisions the restricted runtime
role (`FEDS_APP_DB_ROLE`, default `feds_app`): a login that can read and write
the working tables but cannot own them, run DDL, create roles, or bypass RLS.
Point `FEDS_APP_DATABASE_URL` at that role so the running worker and MCP server
do not hold the schema owner credential.
"""

from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql

from config import NEON_DATABASE_URL, require_config

APP_ROLE_DEFAULT = "feds_app"

# Privileges the runtime genuinely needs: read/write the working tables and
# advance the identity sequences. Deliberately no CREATE (no new objects), no
# ownership, no role/database administration, and no RLS bypass.
_APP_ROLE_GRANTS = (
    "GRANT USAGE ON SCHEMA public TO {role}",
    "REVOKE CREATE ON SCHEMA public FROM {role}",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}",
    "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
    "GRANT USAGE, SELECT ON SEQUENCES TO {role}",
)

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

CREATE TABLE IF NOT EXISTS conversations (
    session_id  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at    TIMESTAMPTZ,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary     TEXT
);
CREATE INDEX IF NOT EXISTS idx_conversations_user
    ON conversations(user_id, started_at DESC);

CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);

CREATE TABLE IF NOT EXISTS embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    conversation_id TEXT REFERENCES conversations(session_id) ON DELETE CASCADE,
    chunk_text      TEXT NOT NULL,
    chunk_index     INT NOT NULL,
    embedding       VECTOR(768) NOT NULL,
    model           TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (document_id IS NOT NULL)::int + (conversation_id IS NOT NULL)::int = 1
    )
);
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw
    ON embeddings USING hnsw (embedding vector_cosine_ops);

DO $$ BEGIN
    ALTER TABLE embeddings ALTER COLUMN embedding TYPE vector(768);
EXCEPTION WHEN others THEN NULL;
END $$;


CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(session_id) ON DELETE SET NULL,
    actor           TEXT NOT NULL,
    action          TEXT NOT NULL CHECK (action IN (
        'message_received',
        'message_sent',
        'skill_activated',
        'capability_invoked',
        'refund_issued',
        'refund_blocked',
        'guardrail_tripped',
        'corpus_seeded'
    )),
    target          TEXT,
    payload         JSONB NOT NULL,
    result          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_conv
    ON audit_log(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_action
    ON audit_log(action, created_at);

CREATE TABLE IF NOT EXISTS capability_invocations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id TEXT NOT NULL REFERENCES conversations(session_id) ON DELETE CASCADE,
    capability      TEXT NOT NULL,
    arguments       JSONB NOT NULL,
    result          JSONB,
    status          TEXT NOT NULL CHECK (status IN ('ok', 'error', 'blocked', 'timeout')),
    latency_ms      INT,
    cost_cents      INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cap_conv
    ON capability_invocations(conversation_id, created_at);

-- Section 6a: private per-user memory and the shared global layer.
-- Private rows are owned by one user id (the isolation boundary).
-- Global rows are only ever created by promote_memory and use owner = '-'
-- as the shared sentinel; their metadata carries promotion provenance.
CREATE TABLE IF NOT EXISTS memories (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope        TEXT NOT NULL CHECK (scope IN ('private', 'global')),
    owner        TEXT NOT NULL,
    body         TEXT NOT NULL,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    status       TEXT NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active', 'promoted', 'superseded')),
    verification TEXT,
    promoted_by  TEXT,
    promoted_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_memories_scope_owner
    ON memories(scope, owner, created_at);

-- Backfill promotion attribution for global rows created before the promoted_*
-- columns existed, from the provenance already stored in metadata, so the
-- provenance constraint below can be validated instead of merely enforced.
UPDATE memories
SET promoted_by = COALESCE(promoted_by, metadata->>'promoted_by'),
    promoted_at = COALESCE(promoted_at, created_at)
WHERE scope = 'global'
  AND (promoted_by IS NULL OR promoted_at IS NULL);

-- Section 6a hardening: the shared layer can only take the sentinel owner and
-- must carry its promotion attribution, and global rows are append-only, so the
-- shared corpus stays auditable no matter what calls the database.
DO $$ BEGIN
    ALTER TABLE memories
        ADD CONSTRAINT memories_global_owner CHECK (scope <> 'global' OR owner = '-');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE memories
        ADD CONSTRAINT memories_global_provenance
        CHECK (scope <> 'global' OR promoted_by IS NOT NULL);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE OR REPLACE FUNCTION memories_global_is_append_only()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' AND OLD.scope = 'global' THEN
        RAISE EXCEPTION 'global memories are append-only and cannot be deleted';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.scope = 'global' THEN
        RAISE EXCEPTION 'global memories are append-only and cannot be updated';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_memories_global_append_only ON memories;
CREATE TRIGGER trg_memories_global_append_only
    BEFORE UPDATE OR DELETE ON memories
    FOR EACH ROW EXECUTE FUNCTION memories_global_is_append_only();

-- Decision 9: a gated tool pauses its run and parks the serialized agent state
-- here until an operator decides with --decide. This table is created (not
-- merely altered below) so a fresh deployment can park and resume approvals at
-- all; before this it existed only in environments where it had been made by
-- hand.
CREATE TABLE IF NOT EXISTS run_states (
    run_id          TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(session_id) ON DELETE CASCADE,
    tool_name       TEXT NOT NULL,
    state_text      TEXT NOT NULL,
    status          TEXT NOT NULL
                    CHECK (status IN ('awaiting', 'approved', 'rejected', 'resumed', 'error')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_run_states_conversation
    ON run_states(conversation_id, created_at DESC);

-- Added when operator attribution landed: who approved or rejected each run.
-- `IF NOT EXISTS` keeps the statement safe on a database that already has it.
ALTER TABLE run_states ADD COLUMN IF NOT EXISTS operator TEXT;

-- The Agents SDK persistence layer (`SQLAlchemySession`) can create these two
-- tables itself, but it defaults to doing so lazily on first use. Creating them
-- here means the restricted runtime role never has to issue DDL: the SDK's
-- `create_all(checkfirst=True)` then finds them and is a no-op. Column types
-- mirror the SDK's own metadata (String key, identity, TEXT payload, timestamps).
CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id  TEXT PRIMARY KEY,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id              SERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL
                    REFERENCES agent_sessions(session_id) ON DELETE CASCADE,
    message_data    TEXT NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agent_messages_session_time
    ON agent_messages(session_id, created_at);
"""


def _provision_app_role(conn: psycopg.Connection) -> None:
    """Create or update the restricted runtime role and its grants.

    Idempotent: re-running setup after a schema change re-applies the grants so
    a table added later is never silently readable only by the owner.
    """
    role = os.getenv("FEDS_APP_DB_ROLE", APP_ROLE_DEFAULT).strip() or APP_ROLE_DEFAULT
    password = os.getenv("FEDS_APP_DB_PASSWORD", "").strip()
    if not password:
        print(
            "[SKIP] FEDS_APP_DB_PASSWORD is not set; leaving the runtime on the "
            "owner credential (see deployment.md for the least-privilege setup)."
        )
        return

    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
        if cur.fetchone() is None:
            cur.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
            print(f"[OK] created restricted runtime role {role!r}")
        else:
            cur.execute(
                sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
            print(f"[OK] refreshed restricted runtime role {role!r}")

        # A freshly created login is already non-superuser and non-BYPASSRLS;
        # `neondb_owner` is not a superuser, so it cannot (and need not) set
        # those superuser-only attributes. Don't try: verify them instead, so a
        # pre-existing role with wide rights is caught rather than assumed safe.
        for statement in _APP_ROLE_GRANTS:
            cur.execute(sql.SQL(statement).format(role=sql.Identifier(role)))
    conn.commit()
    _verify_app_role(conn, role)


def _verify_app_role(conn: psycopg.Connection, role: str) -> None:
    """Refuse to continue if the runtime role holds elevated attributes."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
            "FROM pg_roles WHERE rolname = %s",
            (role,),
        )
        row = cur.fetchone()
    if row is None:
        sys.exit(f"[ERROR] runtime role {role!r} was not found after provisioning.")
    elevated = [
        name
        for name, flag in zip(
            ("SUPERUSER", "CREATEDB", "CREATEROLE", "BYPASSRLS"), row, strict=True
        )
        if flag
    ]
    if elevated:
        sys.exit(
            f"[ERROR] runtime role {role!r} holds elevated attributes {elevated}; "
            "revoke them in Neon before pointing FEDS_APP_DATABASE_URL at it."
        )
    print(
        f"[OK] runtime role {role!r} is least-privilege "
        "(no SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS)"
    )


def main() -> None:
    if not NEON_DATABASE_URL:
        for problem in require_config() or ["NEON_DATABASE_URL is not set."]:
            print(f"[ERROR] {problem}")
        print("\nCopy .env.example to .env, fill in NEON_DATABASE_URL, then re-run.")
        sys.exit(1)

    with psycopg.connect(NEON_DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()
        _provision_app_role(conn)

    with psycopg.connect(NEON_DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            )
            print("tables:", [row[0] for row in cur.fetchall()])
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            print("vector extension:", [row[0] for row in cur.fetchall()])
            cur.execute(
                "SELECT rolname FROM pg_roles WHERE rolname = %s",
                (os.getenv("FEDS_APP_DB_ROLE", APP_ROLE_DEFAULT).strip() or APP_ROLE_DEFAULT,),
            )
            print("runtime role:", [row[0] for row in cur.fetchall()])


if __name__ == "__main__":
    main()