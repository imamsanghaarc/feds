# Sanghaar's Work — Remaining Items

Everything shipped has been removed from this file; it now lists only what is
not done. The evidence for completed work lives in `done.md`, `eval_results.md`,
the test suite (`uv run python run_tests.py`), and git history.

Legend: **OPEN** = not built yet. **BLOCKED** = the work is written but an
external condition stops verification. **DEFERRED** = paused by agreement.

---

## 1. System prompt eval — MEASURED (8 of 8 scored); two findings to fix

**Progress: 8 of 8 cases scored, 6 passed. The two failures both need a prompt
or policy decision, not more quota.**

With the new credential in place the run resumed and completed one pass of all
eight `eval_set.md` cases. `eval_results.md` section A carries the full table
and the evidence. Two findings:

1. **The mode rule is not stable for a tiny change.** `Change the link color to
   #1a5fb4` returned the short snippet answer once and full implement mode
   (all four headings) twice across three runs; the earlier recorded PASS does
   not reproduce. **FIXED (prompt-only, no quota needed):** `SYSTEM_PROMPT.md`
   section 11 now chooses implement-vs-snippet mode by size ("the deciding test
   is size, not verb"), pinned by `test_system_prompt_mode_rule_is_deterministic`.
   Live re-verification rides with item 5.
2. **The input guardrail pre-empts the prompt.** A pasted README containing
   `run this SQL` / `DROP TABLE` is hard-blocked by `_GUARDRAIL_BLOCKERS`
   before the model runs, yet the prompt instructs the agent to treat pasted
   content as data and summarize suspicious content instead of executing it.
   **FIXED — let the model refuse gracefully.** `_GUARDRAIL_BLOCKERS` now holds
   only trust-boundary subversion (`connect to production`, `bypass audit`,
   `disable audit`); destructive-SQL and credential phrasing reaches the model,
   which refuses it per `SYSTEM_PROMPT.md` sections 7 and 9. Pinned offline by
   the guardrail tests; live re-run rides with item 5.

Still open: the three-runs-per-case stability pass (item 5) — now blocked
because free-tier quota is spent for the day (both Gemini keys, roughly 20
requests/day each).

Harness (unchanged, resumable one case at a time):

```powershell
$env:RUN_LIVE_TESTS = "1"
uv run python worker.py "<one case prompt from eval_set.md>"
uv run python replay.py <conversation_id>   # confirm tool names are real
```

---

## 2. Provider failover — real second credential wired; family diversity OPEN

A second Gemini credential is now its own routable provider
(`gemini-fallback`, key in `.env` as `GEMINI_FALLBACK_API_KEY`), enabled for
**both chat and embeddings**. A **real** failover was observed live on
2026-10-19 — the first time rotation has fired against a genuine 429 instead
of a stub:

```
[provider-router] gemini quota exhausted; cooling down 900s (streak 1)
[model] gemini-fallback:gemini-3.5-flash
```

The primary key 429'd on essentially every turn that day (its free-tier
allowance was spent), so the fallback credential carried the whole eval run —
exactly the coverage the fallback exists for.

Still open:

- **Provider family diversity.** Both live credentials are Gemini. Free-tier
  limits are applied per key, so two keys are two allowances — but if both
  keys were issued under the same Google project the allowance may be shared;
  confirm that before calling this quota-proof. Adding a non-Gemini provider
  (Groq has a generous free tier) would remove the shared-upstream risk.
- OpenAI was disabled and its key removed from `.env` by request (it only ever
  returned HTTP 401).

---

## 3. Embedding redundancy — second live path added; local model still OPEN

Embeddings now run through the same two credentials as chat
(`gemini` → `gemini-fallback`), both serving `gemini-embedding-001`, so a
quota failure on one key rotates to the other **without changing the model
label** — stored vectors stay comparable and search stays model-scoped.
`embedding_order()` returns `['gemini', 'gemini-fallback']`; the MCP embedding
router now carries a per-provider `api_key` and dispatches by client family
(`gemini-fallback` uses the Gemini client on the second key).

Still open: a genuinely **local** model (Ollama, or a sentence-transformers
variant at 768 dims). That is the only option that keeps embeddings working
with no network access at all, which matters because ingestion
(`ingest_refs.py`) and seeding both depend on the live embedding path. After
adding any second *model*, run `reembed.py --dry-run` first: vectors from
different models must never be mixed (search is model-scoped by design).

---

## 4. Secrets rotation before sharing the repo — OPEN

Credentials already live in the gitignored `.env` and a planted-secret
scanner in `test_config.py` keeps them out of source. What remains is the
rotation itself: rotate the Neon password and the provider key before this
repo or host is shared with anyone.

---

## 5. Stable-rate eval evidence — OPEN (blocked: quota spent for the day)

Two point measurements exist and neither is a stable rate:

- The trigger eval is 11/11 as a **single sample per case** (`eval_results.md`
  section B).
- The system-prompt eval is 6/8 as a **single run per case** (section A), and
  case 1 is already known to vary — it returned the short-form answer once and
  full implement mode twice across three runs.

A stronger claim needs three runs per case. Start with case 1, where the
variance is observed and cheap to re-run. Also open, if "selected" and "loaded"
are ever to be the same claim for the trigger eval: a harness condition that
forces the `load_skill` call before scoring.

Blocked because free-tier quota is spent for the day — both Gemini keys,
roughly 20 requests/day each. The prompts must be re-run as-is; the recorded
numbers do not carry over after a `SYSTEM_PROMPT.md` change.

---

## 6. Deployment and operations — DEFERRED by agreement

- **Tested container deployment.** `Dockerfile`, `compose.yml`, and
  `.dockerignore` are provided and reviewed (including the
  `!SYSTEM_PROMPT.md` exception and the `.claude/skills/` shipping
  behavior), but Docker was unavailable in this environment — reviewed,
  never executed. Run it once before trusting it.
- Restart supervision, rate limiting, and backpressure under load.
- **Database-enforced promotion approval.** The runtime now connects as a
  restricted role (least privilege below), but approval still lives in the
  worker: the runtime can write a well-formed global row directly. Making the
  database the approval authority needs a second credential the app does not
  hold — a separate approver role writing an approvals row the app role cannot
  forge, with global inserts gated on a matching row. A `SECURITY DEFINER`
  promotion function is not a substitute: the app role could call it without an
  approval. Deliberately deferred as a larger change.
- Cost-shape estimate (course Part 5) — the rollup data
  (`replay.py --costs`) now exists to build it from.

---

## Design input received: the Verified Lesson Loop

`FEDS-Self-Learning-Algorithm-Design.docx` (v1.0 draft) specifies the next
phase: a per-task loop of verify → repair → reflect → gate → save, with a
reward score, tiered memory, confidence dynamics, a consolidator, a knowledge
cache, holdout lift measurement and a shared global layer. Its roadmap
(section 15) has seven phases:

1. Verifier and reward score (build, tests, lint, console, screenshot)
2. Lesson store, gate, mistake ledger and retrieval
3. Confidence updates, quarantine and holdout lift measurement
4. Consolidator, regression evals and versioned rollback
5. Knowledge cache and framework learning
6. Shared global layer and privacy controls
7. Local model routing

What already exists here and maps onto it: the memory store with private and
global scopes, three automated promotion gates (recorded verification, a
`generalizable` flag with `project_specific` refused, and a sanitized rewrite
free of identity, credentials and code), promotion provenance plus human
approval, model-scoped semantic retrieval over the task library, and the
reference ingester for knowledge-cache style material. What the design adds and is **not built yet**: confidence
dynamics (`confidence`, `status` = active/quarantined/rule), the normalized
mistake ledger, duplicate-merge and contradiction checks, the weighted reward
score, holdout lift measurement, consolidation and rollback, and local model
routing. Phases 1–3 are the natural first workstream.

---

## Completed since this list was last rewritten

- **Operator authorization** — decisions are policy-checked against
  `FEDS_ALLOWED_OPERATORS` inside `decide_run` before the run is touched;
  refusals are audited as `approval_refused` and the CLI exits non-zero.
  Proven live by `smoke_operator_auth.py` (zero model quota).
- **Bulk reference ingestion** — `ingest_refs.py` normalizes a directory of
  reference text into documents + embeddings with source attribution, idempotent
  per (source, title). Proven live by `smoke_ingest.py`.
- **Schema gap fixed** — `run_states` is now created by `setup_neon.py`
  (it previously existed only where it had been made by hand, so a fresh
  deployment could not park an approval at all).
- **Memory hardening** — every promotion gate is now automated: the server
  fails closed without an identity, `promote_memory` takes a required
  `sanitized_body` (framework-level prose) and refuses code, credentials or
  the author's identity in it, only affirmatively `generalizable` lessons
  promote, global rows are constrained to the sentinel owner and made
  append-only by a trigger, and the MCP server defaults to stdio and refuses
  a non-loopback bind. Approval remains the only human step. Pinned offline
  and proven live by `smoke_memory.py`.
- **Least-privilege runtime role** — `setup_neon.py` provisions a restricted
  `feds_app` login (no ownership, DDL, role/database admin, or RLS bypass) and
  the worker and MCP server connect with it via `FEDS_APP_DATABASE_URL`
  instead of the schema owner, so a leaked app credential cannot reshape the
  schema, constraints, or triggers. All runtime DDL was moved into
  `setup_neon.py`. Proven live by `smoke_app_role.py` (worker write path and
  SQLAlchemy engine succeed as `feds_app`; DDL refused).

---

## Priority order

1. **Fix the two system-prompt findings** (item 1) — **both fixed, no quota
   needed:** `SYSTEM_PROMPT.md` section 11 now chooses mode by size, and the
   guardrail no longer hard-blocks pasted SQL (it blocks only trust-boundary
   subversion). Both are pinned by offline tests; live re-verification rides
   with item 5's stability pass.
2. **Provider family diversity** (item 2) — a real failover now works, but both
   live credentials are Gemini; a non-Gemini provider removes the shared-upstream
   risk.
3. **Local embedding model** (item 3) — the only option that makes embeddings
   (and ingestion) work with no network at all.
4. **Secrets rotation** (item 4) — required before any sharing.
5. **Stable-rate evals** (item 5), then the deferred deployment work (item 6).

Co-founder features live in `muheeb.md` (approval console, identity,
budgets, CI, notifications); this file is Sanghaar's queue only.
