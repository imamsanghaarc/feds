# FEDS — Remaining Work

**F**rontend **E**ngineering **D**igital **S**pecialist, built from the
*Building a Digital FTE: A 4-Hour Crash Course* architecture.

This is the complete accounting: what is finished, what is verified, and what is
left. Items are marked **OPEN** (work remains), **BLOCKED** (work is written but
unverifiable right now), or **DEFERRED** (deliberately not done).

Current score against the course: **8.5 / 10**.

---

## How to read this

| Marker | Meaning |
| --- | --- |
| **DONE** | Implemented and verified |
| **OPEN** | Not built yet |
| **BLOCKED** | Built, but cannot be verified in this environment |
| **DEFERRED** | Deliberately skipped, by agreement |

---

## Providers

| Provider | Chat | Embeddings | State |
| --- | --- | --- | --- |
| Gemini | yes | yes | enabled; `gemini-3.5-flash`, `gemini-embedding-001` |
| OpenAI | yes | yes | disabled; credential returns HTTP 401 |

**BLOCKED — quota.** Gemini's free tier is exhausted, so live verification is
intermittent. Everything marked BLOCKED below fails only because of this.

Notes worth keeping:

- `gemini-2.5-flash` is **retired for newly provisioned keys** and returns HTTP
  404 "no longer available to new users". The default is now `gemini-3.5-flash`.
- Verified working on the current credential: `gemini-3.5-flash`,
  `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.6-flash`,
  `gemini-3.8-flash`. `gemini-flash-latest` and `gemini-3.7-flash` were
  saturated (503) when checked.
- **OPEN — reinstate a fallback chat provider.** Only Gemini is enabled, so there
  is no failover today. Add OpenAI once a funded key exists
  (`$env:OPENAI_ENABLED = "1"`), or Groq, which has a generous free tier.
- DeepSeek was evaluated and removed: the key authenticated but the balance was
  0.00 (HTTP 402), and it has no embeddings endpoint.
- Groq was evaluated and not added: viable for chat, no embeddings endpoint.
- **OPEN — embeddings have no redundancy.** Only Gemini and OpenAI serve
  embeddings. A local `sentence-transformers` model (384 dims) would remove the
  API dependency permanently. This is a schema change and needs agreement.

---

## 1. Semantic Reference Library and Embeddings

**Status: DONE.**

**DONE**
- pgvector schema, HNSW index, `VECTOR(768)`.
- Chunking at natural boundaries, ~300 words with 50 words of overlap.
- Batch embedding, run off the event loop.
- Retrieval provenance returned: `vector` or `full_text`, the model used, and
  per-match distance.
- Search is scoped to the model that embedded the query, so vectors from
  different models are never compared.
- `reembed.py` with `--dry-run`, `--apply`, `--dedupe`, `--purge-orphans`.
- Verified live: dedupe removed 2 duplicate tasks; every remaining task carries
  Gemini embeddings. Current workspace: 9 documents, 9 embeddings, 0 duplicates,
  0 documents missing a vector.

**OPEN**
- **Seed corpus (Decision 5).** The course seeds a varied library of past
  resolved cases so semantic search has something to distinguish. FEDS has ~7
  real frontend tasks but no generated, varied corpus. This is the main reason
  the semantic-search proof is thin.
- **Bulk reference ingestion.** No reader for articles, patterns, or prior
  component libraries alongside tasks.

---

## 2. Skills Packaging and Discoverability

**Status: progressive disclosure DONE. Trigger evaluation BLOCKED. Packaging OPEN.**

**DONE**
- 35 skills: 5 authored workflow skills plus frontend language and framework
  reference skills.
- Skill index plus a `load_skill` tool: ~11,400 characters in the prompt instead
  of ~100,700 (**88.6% reduction**).
- `references/` files for the three workflow skills, loaded only on use.
- `load_skill` tolerates casing and hyphen/underscore variants.
- Descriptions follow Concept 3 discipline: what it produces, when to reach for
  it, real user phrasings, and an explicit do-NOT line. Each passes the
  "delete the obvious keyword" self-check.

**BLOCKED**
- **Trigger evaluation, 7 of 8 cases unscored.** The harness
  (`eval_triggers.py`) scored 1 of 8 before quota ran out. The single pass is
  *"Write a handoff note for the navbar task before I escalate"* →
  `summarize-component`, which is the phrasing that never says "summarize" —
  the exact failure mode Concept 3 warns about. **Passing the only case it
  reached says nothing about over-firing**, which is the harder half. The four
  `should-not-fire` cases are the false-positive check and none have run.

**OPEN**
- **`.claude/skills/` packaging (Concept 4).** Skills live in `skills/` behind a
  custom loader. The course's standard is `.claude/skills/`, the one location
  Claude Code, OpenCode, and the Worker's own SDK all read. Moving them there
  would restore true portability.
- **Skill composition via filesystem handoff (Concept 5).** Not implemented.

---

## 3. Business Records and Runtime Scope

**Status: DONE.**

- Six scoped tools: `lookup_task`, `list_tasks`, `find_similar_tasks`,
  `save_task`, `record_review`, `publish_task`.
- No `run_sql`, no DDL tool, no broad access.
- Idempotent `save_task`: one canonical record per normalized name, old vectors
  superseded in the same transaction.
- Provenance on every record: framework, WCAG notes, responsiveness notes,
  status, reviewer, review timestamps, publication targets.
- Embedding runs *before* the transaction opens, so no connection is held across
  a provider call.

---

## 4. Audit Trail and Observability

**Status: DONE.**

- Every MCP tool writes one `audit_log` row and one `capability_invocations` row
  with status and latency, through a separate connection from the worker's audit
  path.
- The worker passes `FRONTEND_CONVERSATION_ID` to the MCP process, so rows are
  attributed to a real conversation instead of being NULL orphans.
- Metrics failures are swallowed by design, so telemetry can never fail a
  business call.
- Guardrail and hook rows use the course's closed action vocabulary, asserted by
  a test.
- `replay.py` reconstructs a conversation from the trail and prints latency
  totals.

Current workspace: 78 audit rows, 2 capability rows, 19 conversations. The
capability count is low because the metrics wiring is new; earlier conversations
predate it.

**OPEN**
- Token and cost rollups per conversation. `capability_invocations.cost_cents`
  exists but nothing writes it.

---

## 5. Guardrails, Trusted Actions, and Approval

**Status: DONE and proven live.**

**DONE**
- Input guardrail blocks destructive and audit-bypass phrasing, writes a
  `guardrail_tripped` row, and runs before any model or persistence work.
- **The guardrail screens only the latest user turn.** With a Session the
  prepared input is the whole transcript; screening all of it would let one bad
  turn poison the rest of the conversation. Covered by regression tests.
- `publish_task` is the single publisher and the only approval-gated tool.
  Reads stay free, per "reads run free, writes are gated."
- It refuses any task not already `approved`, and production additionally needs
  `ALLOW_PRODUCTION_PUBLISH=1`.
- The pause persists `RunState` to `run_states` and resumes in a separate
  process via `--decide <run_id> approve|reject`.
- A declined publish is itself audited.

**Proven live**
```
run feds-gate-e2e    -> Approval required: run_id=cb93e87c... tool=publish_task
while paused         -> published=None
--decide ... approve -> published: true
final state          -> published={'staging': '2026-10-16T12:40:50...'}
run_states           -> cb93e87c59a1  publish_task  resumed
```

Current workspace: 2 approved tasks, 2 published, and `run_states` holds
1 `resumed` and 1 `awaiting` (the rejected-path run).

**OPEN**
- Production approval policy for operators: who can approve, and how that is
  recorded beyond the audit row.

---

## 6. Provider Resilience

**Status: DONE and tested.**

- `provider_router.py` rotates on quota and balance exhaustion, honors a server
  retry delay, backs off exponentially on repeats, and caps the wait so recovery
  is prompt.
- Handles both upstream conventions: `429 insufficient_quota` and
  `402 Insufficient Balance`.
- The router is a **process-wide singleton**, so cooldown outlives an agent
  build and an exhausted provider is not hammered again.
- Streaming rotates at stream start only; a mid-stream failure propagates rather
  than replaying already-emitted output.
- Only quota and balance errors rotate. Rejected credentials and real bugs
  propagate, verified by test, so a broken key cannot look like a healthy system.
- Chat and embeddings route independently; a test enforces that a chat-only
  provider can never appear in the embedding order.

**OPEN**
- Only one enabled provider, so rotation cannot be exercised live. The logic is
  proven by test and by a forced 429/402 stub, not by a real failover.

---

## 7. Deployment and Operations

**Status: documented. Deployment DEFERRED by agreement.**

**DONE**
- Two-process shape, SSL and pooling conventions, provider resilience, and
  secret-hardening notes are in `deployment.md`.
- `Dockerfile`, `compose.yml`, `.dockerignore` provided.
- Live provider checks are opt-in via `RUN_LIVE_TESTS=1`, so the offline suite
  stays meaningful while quota is exhausted.

**DEFERRED**
- A **tested** container or hosted-sandbox deployment. Docker was unavailable in
  this environment, so the configuration is reviewed but unverified.
- Restart supervision, rate limiting, and backpressure under load.
- Cost shape estimate (course Part 5).

---

## 8. Documentation and Ownership

**Status: DONE.**

- `plan.md` — ten significant design decisions, each with its reason.
- `README.md` — setup, run, test, operations, provider state.
- `SYSTEM_PROMPT.md` — 16-section behaviour contract including FEDS's identity.
- `AGENTS.md` — the short rule set.
- `eval_set.md` / `eval_results.md` — the eval harness and honest results.
- `missing.md` — this file.

**OPEN**
- Secrets are embedded in `config.py` as requested. Move them to a managed
  secret store before sharing or hosting this source, and rotate both the Neon
  password and the provider key.

---

## 9. Verification

### Proven offline — `uv run python run_tests.py`, 3/3 suites, 110 assertions

Guardrails (including the latest-turn-only rule), skill tree and malformed-skill
handling, progressive disclosure, frontmatter parsing, chunking, all six MCP
tools present, approval guards, `--decide` input validation, closed audit
vocabulary, provider rotation (429 / 402 / 401 / bugs / recovery / all-exhausted),
conversation-id propagation, FEDS identity, single publish path, resume wiring.

### Proven live

- **Full agent turn.** FEDS loads a skill, calls `save_task` through the scoped
  MCP server, and returns the four-heading output contract.
- **Complete audit replay.** One conversation produced `message_received` →
  `skill_activated` (load_skill) → `capability_invoked` (load_skill, save_task)
  → the MCP server's own row → `message_sent`, with a capability metric row
  carrying latency. Reconstructable from `audit_log` alone.
- **Approval pause and resume.** Proven above.
- Semantic search ranking by meaning with per-match distance.
- Re-embedding migration and duplicate cleanup.
- `publish_task` refusing an unapproved task.

### Blocked on quota

| Item | Progress |
| --- | --- |
| System prompt eval (`eval_set.md`) | 1 of 8 cases scored, passed |
| Skill trigger eval (`eval_triggers.py`) | 1 of 8 cases scored, passed |

Both are recorded as **PARTIAL** in `eval_results.md` rather than rounded up. The
harnesses exit non-zero on skipped cases so an incomplete run cannot be mistaken
for a clean pass.

To finish both:
```powershell
$env:RUN_LIVE_TESTS = "1"
uv run python eval_triggers.py
```

---

## 10. Bugs Found and Fixed

Recorded because each was silent and would have been hard to diagnose later.

| Bug | Consequence | Fixed |
| --- | --- | --- |
| `GEMINI_EMBEDDING_MODEL` NameError | Every `save_task` call failed | provider config |
| Cross-model vector contamination | Silently wrong search results | model-scoped search |
| Non-idempotent `save_task` | Duplicate tasks, stale vectors | upsert + vector supersede |
| Embedding inside an open transaction | Held a DB connection across a network call | embed first |
| `FRONTEND_CONVERSATION_ID` never passed | `capability_invocations` wrote NULL orphans | env wiring |
| `return` in a generator's `finally` | **Swallowed exceptions — a refused publish looked like success** | control flow + regression test |
| cp1252 console encoding | Turn died printing `≥` | UTF-8 stdout |
| Guardrail screened the whole transcript | One bad turn blocked every later turn | latest-user-turn only |
| Two publish paths, gated one was a no-op | Trust boundary guarded nothing | collapsed to one |
| `RunState.from_string` called synchronously | `--decide` never worked | awaited |
| Resume had no MCP servers | Resume could not reach the gated tool | server attached |
| Router not a singleton | Exhausted provider hammered per agent | module-level singleton |

---

## Priority order for what remains

1. **Finish the two evals** (needs quota). Highest value: converts assumption
   into measurement.
2. **Seed corpus** (Decision 5). Makes the semantic-search claim real.
3. **A second enabled chat provider.** Restores actual failover.
4. **`.claude/skills/` packaging.** Restores portability.
5. **Local embedding model.** Makes embeddings quota-proof.
6. **Per-conversation advisory lock** (Decision 10, optional).
7. **Tested container deployment** (deferred by agreement).



New {
  give each user a private memory, and add a shared global layer. A lesson reaches the global layer only if it is verified, generalizable (framework-level, not tied to one project) and stripped of the user’s code and names. This lets FEDS improve from everyone without leaking anyone’s work.
}