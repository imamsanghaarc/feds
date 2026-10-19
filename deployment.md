# Deployment and Operations

## Process shape

Two processes, normally one container:

1. `worker.py` — the agent loop, skills, guardrails, approvals, audit hooks.
2. `frontend_workspace_mcp/server.py` — the scoped business-data surface,
   launched by the worker as a stdio child.

The MCP server defaults to `stdio`, which is how the worker launches it. It
can also serve `streamable-http` for external consumers
(`MCP_TRANSPORT=streamable-http`), but it refuses to bind a non-loopback
`MCP_HOST` unless `MCP_ALLOW_REMOTE=1` is set — promotion approval is
enforced in the worker, so a reachable endpoint would bypass it. A single
container is the correct deployment unit: parent and child share a lifecycle.

## Container configuration

`Dockerfile` and `compose.yml` are provided. **Neither has been run**: Docker was
unavailable in this environment, so treat them as reviewed-but-unverified. Do
not treat them as a tested deployment.

Design notes:

- Dependencies are installed before source is copied, so code edits do not
  invalidate the dependency layer.
- `.dockerignore` excludes root-level markdown (design docs stay out of the
  image) but explicitly re-includes `SYSTEM_PROMPT.md`: the worker reads it at
  startup and would otherwise silently run with a one-line fallback identity.
  The skill corpus in `.claude/skills/` is nested, so the root-level `*.md`
  rule does not exclude it and the skills ship with the image. A regression
  test pins the `!SYSTEM_PROMPT.md` exception.
- `init: true` gives the worker proper signal handling and child reaping, which
  matters because it spawns the MCP server as a subprocess.
- The healthcheck only verifies database reachability, which is the single
  external dependency that must be up before any turn can succeed.
- `ALLOW_PRODUCTION_PUBLISH` is intentionally unset in compose. Publishing to
  production requires an explicit operator decision.

## Database connections

- Two credentials. `NEON_DATABASE_URL` is the schema owner: only
  `setup_neon.py` and the operator ingest/migration CLIs
  (`seed_corpus.py`, `ingest_refs.py`, `reembed.py`) use it. The worker and the
  MCP server connect with `FEDS_APP_DATABASE_URL` instead, a restricted role
  created by `setup_neon.py`; `config.DATABASE_URL` resolves to it, falling
  back to the owner only when it is unset. See "Runtime least privilege".
- `statement_cache_size=0` is required: PgBouncer in transaction mode does not
  support prepared statements.
- `pool_pre_ping=True` on the SQLAlchemy engine and `min_size=1` on the asyncpg
  pool, because pooled Neon connections drop while idle.
- Audit writes use a dedicated short-lived `psycopg` connection rather than the
  agent's engine, so audit logging cannot deadlock against the session pool.
- The worker's engine is disposed in a `finally` block on every path, including
  guardrail trips and approval pauses.

## Runtime least privilege

`setup_neon.py` can create a `feds_app` login for the running processes when
`FEDS_APP_DB_PASSWORD` is set:

- it is not a member of `neondb_owner` and holds no elevated attributes
  (no `SUPERUSER`, `CREATEDB`, `CREATEROLE`, or `BYPASSRLS`);
- it has `USAGE` on `public` but no `CREATE`, so it cannot add, alter, or drop
  objects, create schemas, or administer roles;
- it has `SELECT/INSERT/UPDATE/DELETE` only on the working tables and their
  sequences.

The point is blast radius: a compromise of the app environment (the running
host's `.env`) yields ordinary data access, not schema ownership or role
administration. The setup script verifies the attributes and exits non-zero if
the role is elevated. `smoke_app_role.py` proves the live behaviour — the
worker's whole write path and the SQLAlchemy engine succeed as `feds_app`, and
`CREATE TABLE`, `CREATE SCHEMA`, `ALTER TABLE`, and `DROP TABLE` are refused
with a privilege error.

Because the runtime cannot run DDL, schema changes belong in `setup_neon.py` —
including the Agents SDK's own session tables (`agent_sessions`,
`agent_messages`) and the `run_states.operator` column, which is why they were
moved out of runtime code. An offline test fails if `worker.py` or `server.py`
contains a `CREATE`/`ALTER`/`DROP TABLE` statement.

## Provider resilience

Three provider slots exist (Gemini, OpenAI, and room for one more); two are
enabled-capable for embeddings. Chat and embeddings rotate independently.

- Rotation happens on quota, balance, and rate-limit errors only.
- Upstreams signal exhaustion inconsistently: `429 insufficient_quota` and
  `402 Insufficient Balance` are both treated as routable.
- `404` on a model means it is retired for that credential (not exhaustion), so
  it propagates rather than rotating away from a working provider.
- `503` means live but saturated. It is transient, so it propagates and the SDK
  retries; it is not a reason to abandon a provider.
- A server-supplied retry delay is honored; repeated failures back off
  exponentially, and the wait is capped so recovery is prompt once quota returns.
- A rejected credential (`401`) or a genuine bug propagates immediately, so a
  misconfiguration cannot masquerade as a healthy system.
- Streaming rotates at stream start only. A mid-stream failure propagates rather
  than replaying already-emitted output.
- `FallbackChatModel` serializes model calls through the router, so a rotation
  can never interleave two clients mid-request.

Tune with `PROVIDER_COOLDOWN_SECONDS`. Disable a provider with
`GEMINI_ENABLED=0` or `OPENAI_ENABLED=0`.

Adding a provider means adding one entry to `_CHAT_PROVIDERS` in `config.py`;
nothing else changes. A chat-only provider must not be added to
`EMBEDDING_MODELS`, which a test enforces.

## Model lifecycle

`gemini-2.5-flash` was retired for newly provisioned keys and returns HTTP 404.
Model names therefore need periodic re-validation, not one-time trust:

```powershell
uv run python status_providers.py
```

FEDS defaults to `gemini-3.5-flash`. When a model 404s, resolve a replacement
from the provider's live catalog rather than guessing a new name.

## Embeddings and model changes

- Vectors are 768-dimensional and every row records the model that produced it.
- Search compares only vectors matching the query's own model, so a provider
  switch can never produce a silently wrong result.
- After a model change, rebuild with
  `uv run python reembed.py --apply --dedupe --purge-orphans`.
- Embedding runs before the transaction opens, so no connection is held for the
  duration of a provider call.

## Guardrails

- The input guardrail runs before any model or persistence work and writes a
  `guardrail_tripped` row when it trips.
- The audit action vocabulary is closed and asserted by a test.
- Publication requires a recorded human approval. Production additionally
  requires `ALLOW_PRODUCTION_PUBLISH=1`.

## Observability

`replay.py` joins the narrative trail with the metrics trail:

```powershell
uv run python replay.py <conversation_id>
uv run python replay.py <conversation_id> --json
```

Use it as a post-run regression check: every significant action should have both
an audit row and a capability row with a latency.

## Secret hardening

Credentials are embedded in `config.py` as requested for this live deployment.
Before sharing or hosting this source:

1. Move keys to a managed secret store and read them from the environment.
2. Rotate both the Neon password and the provider keys.
3. Drop `config.py`'s literals and keep only `os.getenv` lookups.
4. Give the runtime the restricted role (see "Runtime least privilege") and keep
   `NEON_DATABASE_URL` owner-only; a leaked runtime credential should not be
   able to reshape the schema.
5. Never set `ALLOW_PRODUCTION_PUBLISH=1` on a broadly reachable host.

`test_config.py` exists to catch a drifted or mistyped credential early; run it
with `--strict` in CI.

## Promotion trust boundary

The shared global layer is written only by `promote_memory`, and its human
approval is enforced in the worker (`require_approval`), not in the database.
Three things keep that honest:

1. The MCP server defaults to stdio and refuses a non-loopback bind without
   `MCP_ALLOW_REMOTE=1`, so the tool surface is not reachable except through the
   worker.
2. The runtime connects as the restricted `feds_app` role (see "Runtime least
   privilege"), so a leaked app credential cannot alter the schema, the
   constraints, or the append-only trigger that back the promotion rules, and
   cannot create a role to replace them.
3. The database still refuses malformed promotions — non-sentinel owner,
   missing provenance, updates/deletes of global rows — even from a direct
   connection (proven by `smoke_memory_schema.py`).

What least privilege does *not* do is make the database the approval authority:
`feds_app` can still insert a well-formed global row, because approval is a
worker concept. A `SECURITY DEFINER` promotion function would not change that —
the app role could simply call it without an approval, so it would add a
mechanism without adding a gate. Enforcing approval in the database requires a
second credential that only the human approval step holds: a separate approver
role writing an approvals row the app role cannot forge, with global inserts
gated on a matching row. That is a deliberate, larger change, recorded in
`missing.md` rather than half-built.

## Known gaps

- The container configuration is unverified.
- The restricted runtime role is proven at the database (`smoke_app_role.py`)
  but no full agent turn has been run under it, because a turn spends provider
  quota. The first live turn is the remaining confirmation.
- Restart supervision, rate limiting, and backpressure under load are untested.
- Cost rollups per conversation are not implemented; `capability_invocations`
  has the `cost_cents` column but nothing writes it yet.