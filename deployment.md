# Deployment and Operations

## Process shape

Two processes, normally one container:

1. `worker.py` — the agent loop, skills, guardrails, approvals, audit hooks.
2. `frontend_workspace_mcp/server.py` — the scoped business-data surface,
   launched by the worker as a stdio child.

The MCP server defaults to `streamable-http` for external consumers, but the
agent sets `MCP_TRANSPORT=stdio`. A single container is therefore the correct
deployment unit: parent and child share a lifecycle.

## Container configuration

`Dockerfile` and `compose.yml` are provided. **Neither has been run**: Docker was
unavailable in this environment, so treat them as reviewed-but-unverified. Do
not treat them as a tested deployment.

Design notes:

- Dependencies are installed before source is copied, so code edits do not
  invalidate the dependency layer.
- `init: true` gives the worker proper signal handling and child reaping, which
  matters because it spawns the MCP server as a subprocess.
- The healthcheck only verifies database reachability, which is the single
  external dependency that must be up before any turn can succeed.
- `ALLOW_PRODUCTION_PUBLISH` is intentionally unset in compose. Publishing to
  production requires an explicit operator decision.

## Database connections

- `statement_cache_size=0` is required: PgBouncer in transaction mode does not
  support prepared statements.
- `pool_pre_ping=True` on the SQLAlchemy engine and `min_size=1` on the asyncpg
  pool, because pooled Neon connections drop while idle.
- Audit writes use a dedicated short-lived `psycopg` connection rather than the
  agent's engine, so audit logging cannot deadlock against the session pool.
- The worker's engine is disposed in a `finally` block on every path, including
  guardrail trips and approval pauses.

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
4. Restrict the Neon branch; the worker only needs its own schema.
5. Never set `ALLOW_PRODUCTION_PUBLISH=1` on a broadly reachable host.

`test_config.py` exists to catch a drifted or mistyped credential early; run it
with `--strict` in CI.

## Known gaps

- The container configuration is unverified.
- Restart supervision, rate limiting, and backpressure under load are untested.
- Cost rollups per conversation are not implemented; `capability_invocations`
  has the `cost_cents` column but nothing writes it yet.