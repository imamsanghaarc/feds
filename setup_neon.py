"""One-time Neon schema setup for FEDS, the Frontend Engineering Digital Specialist.

Reads the connection string from config (which loads .env / the environment).
Run `uv run python setup_neon.py` after setting NEON_DATABASE_URL.
"""

from __future__ import annotations

import sys

import psycopg

from config import NEON_DATABASE_URL, require_config

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
"""


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

    with psycopg.connect(NEON_DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            )
            print("tables:", [row[0] for row in cur.fetchall()])
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            print("vector extension:", [row[0] for row in cur.fetchall()])


if __name__ == "__main__":
    main()