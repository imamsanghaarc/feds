# Build Plan: FEDS

This is the decision record for the Digital FTE. The crash course's worked
example is a customer-support agent; this project deliberately adapts it to a
frontend engineering domain. Every significant choice and its reason is written
down here.

## Decision 0: The official name is FEDS

**FEDS** — **F**rontend **E**ngineering **D**igital **S**pecialist.

The name is defined once in `config.py` as `OFFICIAL_NAME` and flows to the
agent name, the audit trail's `user_id`, the workflow name, the system prompt,
and the docs, so it cannot drift between surfaces.

The system prompt states the name in the identity section, adds an explicit
identity example showing the expected answer to "Who are you?", forbids
describing itself as a generic assistant, and closes with a reminder to answer
as FEDS. A test asserts the name appears in the prompt, the README, and
`AGENTS.md`.

Reason: a named employee is accountable and recognizable in transcripts and
audit rows; "the frontend agent" is neither.

## Decision 1: Adapt the course's generic example to a frontend domain

The course teaches the architecture with customers, tickets, and orders. The
architecture is domain independent, so the domain is swapped rather than the
design.

- **Frontend tasks** replace tickets.
- **Components and layout patterns** replace orders.
- **Reviews** replace refunds.
- **Core Web Vitals** (LCP < 2.5s, FID/INP < 100ms, CLS < 0.1) become the
  quality bar that reviews check against.

Reason: the agent is a Frontend Developer FTE, and a support-shaped vocabulary
would make its skills and tools misleading.

## Decision 2: Neon Postgres with pgvector as the system of record

Chosen over Supabase because pgvector plus a plain connection string is enough,
and the course's own examples target Neon.

- `documents` stores frontend tasks and references.
- `embeddings` stores 768-dimension vectors with an explicit `model` column.
- `audit_log` keeps the narrative trace.
- `capability_invocations` keeps per-tool metrics.
- `conversations` / `agent_sessions` / `agent_messages` hold session state.

Reason: one managed Postgres removes a second vendor and keeps embeddings next to
the business rows.

## Decision 3: Every stored vector records its model

`embeddings.model` is not decoration. It is the mechanism that makes provider
switching safe.

- Retrieval compares only vectors whose `model` matches the model that embedded
  the query.
- `reembed.py` rebuilds vectors when a model is introduced or changed.

Reason: vectors from different models are not comparable. Without the column, a
provider switch would silently corrupt search results instead of visibly
returning nothing.

## Decision 4: A quota-aware provider router instead of a single vendor

`provider_router.py` tries providers in priority order and rotates on quota
exhaustion only.

- Preferred provider first, the other one as fallback.
- A server-supplied retry delay is honored; repeated failures back off
  exponentially and the wait is capped so recovery is prompt.
- Only quota/rate-limit failures rotate. A bad credential or a real bug
  propagates immediately.

Reason: one exhausted free tier should not take the whole FTE offline, but
silently routing around a misconfiguration would let a broken key look healthy.

## Decision 5: All runtime business access goes through the scoped MCP server

The agent never writes SQL. `frontend-workspace` exposes exactly six tools:
`lookup_task`, `list_tasks`, `find_similar_tasks`, `save_task`, `record_review`,
`publish_task`.

Reason: matches the course's scoping rule and keeps the trust boundary small
enough to reason about.

## Decision 6: The highest-trust action requires human review first

`publish_task` refuses any task that is not already `approved`, and production
additionally needs an operator opt-in (`ALLOW_PRODUCTION_PUBLISH=1`). A separate
`publish_asset` tool in the worker additionally pauses for explicit approval via
the SDK's approval flow and can be resumed in another process.

Reason: the FTE can draft and record, but publishing is a human decision.

## Decision 7: Progressive disclosure on every host

On a Unix-like sandbox the SDK's `Skills` capability loads skills lazily. On
Windows that capability is unavailable, so the worker reproduces the same
behavior with a skill index plus a `load_skill` tool.

- Context cost drops from roughly 100,700 characters to about 11,400.
- Reference files under `skills/*/references/` load only when needed.

Reason: dumping every skill into the prompt on the fallback host wasted tokens
and defeated the course's core progressive-disclosure idea.

## Decision 8: Writes are idempotent

`save_task` updates an existing same-named task instead of inserting a duplicate,
and supersedes its old vectors in the same transaction.

Reason: retries and re-runs are normal in an agent loop; duplicate records and
stale vectors were both observed in the workspace before this was fixed.

## Decision 9: Embeddings run before the transaction opens

`save_task` chunks and embeds first, then opens a short transaction for the
writes.

Reason: a network call inside an open transaction holds a database connection
for the duration of the provider's latency.

## Verification status

Proven offline, without any model provider:

- guardrails block unsafe input and allow real work
- skill index and `load_skill`, including malformed and missing skill trees
- chunking boundaries, overlap, and empty input
- all six MCP tools present, with `publish_task` approval guards
- provider rotation, cooldown, recovery, and bug propagation
- `--decide` input validation
- configuration parity between worker and MCP server

Proven live:

- semantic save and search over pgvector with 768-dimension embeddings
- re-embedding migration and duplicate cleanup

Blocked on provider quota:

- a full model-driven agent turn
- live approval pause and resume
- live end-to-end audit replay of a complete run