# AGENTS.md — FEDS (frontend-developer-FTE)

FEDS is an AI employee for frontend work: one Python repo run with `uv`, no
build step. At runtime it is two processes: `worker.py` (the agent loop)
spawns the `frontend_workspace_mcp` server over stdio, which is the only
thing allowed to touch Neon (pgvector).

## Identity and product rules (non-negotiable)

- The official name is **FEDS** (Frontend Engineering Digital Specialist);
  never describe it as a generic assistant or another name.
- Load skills through the skill index, then `load_skill` for the one that
  matches; never inline the corpus. Missing or malformed skills must be
  handled gracefully, never crash a turn.
- Keep frontend advice aligned to Core Web Vitals: LCP ≤ 2.5s, INP ≤ 200ms,
  CLS ≤ 0.1 (p75 field thresholds).
- Prefer the local Unix sandbox while developing; the Windows fallback must
  keep the same progressive-disclosure behavior.
- Runtime database access uses only the scoped `frontend-workspace` MCP
  tools; broad SQL is forbidden.
- Every stored vector records the model that produced it; never compare
  vectors across models.
- Credentials come from the gitignored `.env` and flow through `config.py`
  as the single import surface for both the worker and the MCP server. Never
  hard-code or commit them — `test_config.py` carries a planted-secret
  scanner. A deployed process supplies real environment variables instead.
- Two database credentials. `NEON_DATABASE_URL` is the schema owner and belongs
  only to `setup_neon.py` and the ingest/migration CLIs. The worker and MCP
  server connect with `FEDS_APP_DATABASE_URL` (the restricted `feds_app` role);
  `config.DATABASE_URL` resolves to it and falls back to the owner only when it
  is unset. Because the runtime role cannot run DDL, all schema changes go in
  `setup_neon.py` — never add a runtime `CREATE`/`ALTER`/`DROP` (an offline test
  fails if `worker.py` or `server.py` contains one).
- Rotate providers on quota exhaustion only; never route around a rejected
  credential or a real bug. Signals: 429 insufficient-quota and 402
  insufficient-balance rotate; a model 404 means retired-for-credential —
  revalidate names with `uv run python status_providers.py` and resolve a
  replacement from the provider's catalog instead of guessing; 503 is a
  saturated (transient) endpoint, not a reason to abandon a provider.
- Publication requires a recorded human approval first. The approval-gated
  tools are exactly `publish_task` and `promote_memory`; if you add another
  write that reaches shared state, gate it in `worker._mcp_server`. A
  `publish_task` to `production` additionally needs
  `ALLOW_PRODUCTION_PUBLISH=1` (compose.yml deliberately leaves it unset).
- `_GUARDRAIL_BLOCKERS` holds only phrases that subvert FEDS's own trust
  boundary (`connect to production`, `bypass audit`, `disable audit`).
  Destructive-SQL or credential phrasing in pasted content reaches the model,
  which refuses gracefully — that is what `eval_set.md` case 3 checks, and two
  offline tests pin both sides of this choice. Re-hardening the blocklist
  would reintroduce a known bug, not improve safety.
- DeepSeek was removed deliberately and there is no web-search tool by
  decision; do not add either back (the `ddgs` entry in `pyproject.toml` is
  unused — do not wire it up as one).
- Snippet vs implement mode is decided by size — roughly 20 lines or fewer
  that add no new component, page, state, or file — not by the verb. The
  deciding test lives in `SYSTEM_PROMPT.md` §11 and is pinned offline.

## Commands

- One-time setup: `uv sync`, copy `.env.example` → `.env`, fill it, then
  `uv run python setup_neon.py` (idempotent schema; re-run after schema
  edits). Set `FEDS_APP_DB_PASSWORD` in `.env` first to also provision the
  restricted runtime role.
- Offline gate before any push: `uv run python run_tests.py` → 3 suites
  (config wiring, provider fallback router, guardrails and inputs). Exits
  non-zero on failure; keep it green. CI additionally runs
  `uv run python test_config.py --strict`, which live-probes the credentials
  and fails on a stale one.
- Zero-quota live schema proof: `uv run python smoke_memory_schema.py` runs
  the real promotion statements and the constraint/append-only probes inside
  a rolled-back transaction, so the memory rules are proven at the database
  without touching the shared layer.
- Zero-quota live privilege proof: `uv run python smoke_app_role.py` proves the
  runtime role is least-privilege — the worker's write path and the SQLAlchemy
  engine succeed as `feds_app`, while DDL is refused. Skips when
  `FEDS_APP_DATABASE_URL` is unset.
- Other live probes with no chat-model turns (they hit the real workspace DB,
  some through the embedding endpoint — see each docstring): `smoke_mcp.py`
  (server tools outside the agent loop), `smoke_memory.py` (memory isolation +
  promotion gates), `smoke_ingest.py` (idempotent bulk ingest),
  `smoke_operator_auth.py` (operator-refusal, self-cleaning).
- Fastest single-suite run: `uv run python test_worker_offline.py`.
- Live checks are quota-consuming and opt-in: set `RUN_LIVE_TESTS=1`
  (PowerShell: `$env:RUN_LIVE_TESTS = "1"`) — that unlocks the live suites
  inside `run_tests.py`, `eval_triggers.py`, and `test_approval_gate.py`.
- One agent turn: `uv run python worker.py "prompt"`. Inspect afterwards:
  `uv run python replay.py <conversation_id>`.
- Resume a parked approval: `uv run python worker.py --decide <run_id>
  approve|reject [operator]`. Decisions are policy-checked:
  `FEDS_ALLOWED_OPERATORS` (unset = only `operator-local`); a refusal is
  audited as `approval_refused` and exits non-zero (2 = usage error).
- Provider availability: `uv run python status_providers.py`.
- Ingest reference material: `uv run python ingest_refs.py --dir <path>
  [--source label] [--apply]` — dry-run by default, idempotent per
  (source, title), so re-running only adds new files.

## Evaluation rules (honesty is the point)

- `eval_results.md` may contain only numbers produced by real runs. It once
  held fabricated results (byte-identical "passes" naming a tool that never
  existed) — never reintroduce them, never round a partial run up.
- `uv run python eval_triggers.py` is resumable: passing cases are cached
  and skipped. `RETRY_ALL=1` re-scores everything; naming case ids on the
  command line re-scores exactly those (named cases ignore the cache).
- Exit codes: `0` all scored and passed, `1` a case failed, `2` incomplete
  (provider quota skipped cases). Exit 2 is the normal quota outcome —
  rerun later, and never report it as a pass.
- Trigger scoring uses recorded `load_skill` calls as ground truth; the
  agent's `SKILL: <name>` reply is only the fallback. The per-case
  evidence split lives in `eval_results.md`.
- Current measured state (2026-10-19): trigger precision is 11/11 — single
  sample per case, and only 1 pass backed by a recorded `load_skill`, so
  never claim the agent "always loads" what it selects. The system-prompt
  eval (`eval_set.md`, no harness — run each case via `worker.py`, verify
  tool names with `replay.py`) is 8/8 run, 6 passed pre-fix; both failures
  were real bugs (mode instability, guardrail contradiction), now fixed and
  pinned offline, with the stability re-run pending quota. Numbers never
  carry over: after touching `SYSTEM_PROMPT.md` or the guardrail, re-run.
- Quick scoreboard from `eval_trigger_results.json`:
  `uv run python eval_summary.py`.

## Gotchas worth knowing before they cost you time

- Development box is Windows/PowerShell: there is no `grep` (use
  `Select-String`), and git errors print as PS noise — confirm a push with
  `git ls-remote origin HEAD` before believing it failed.
- The MCP server defaults to stdio (how the worker launches it) and refuses a
  non-loopback bind without `MCP_ALLOW_REMOTE=1`: approval is enforced in the
  worker, so a reachable MCP endpoint would bypass it.
- `Dockerfile` and `compose.yml` were reviewed but never run (no Docker in the
  dev environment) — treat container deployment as untested. `.dockerignore`
  must keep its `!SYSTEM_PROMPT.md` re-include: the worker reads that file at
  startup and would silently run with a one-line fallback identity.
- Thinking models return a thought part before the text; never assume
  `parts[0]["text"]`.
- Gemini free-tier quota is the binding constraint on every live
  verification; all live harnesses are cached/resumable for that reason.
- Cost honesty: `capability_invocations.cost_cents` stays NULL when a
  model's price is unknown — NULL is not zero, do not "fill it in".
- `reembed.py --apply --dedupe --purge-orphans` only after a `--dry-run`;
  mixing models in the vector store would silently corrupt search.
- `seed_corpus.py --apply` is idempotent; `verify_corpus.py` must keep
  ranking the confusable pairs first.
- `FRONTEND_CONVERSATION_ID` and `FRONTEND_USER_ID` are injected by the
  worker into the MCP server's env; without a user id the server fails
  closed and refuses to serve memory at all — it never falls back to one
  shared identity.
- Memory isolation lives in the SQL (`scope = 'private' AND owner = $2`);
  do not "simplify" those predicates away. The promotion gates live in
  `promote_memory` plus the `memories` constraints and append-only trigger in
  `setup_neon.py`; a promotion needs a recorded verification, a `generalizable`
  flag, and a clean `sanitized_body`, and the shared copy comes only from that
  body. Do not weaken either layer.
- Skills live in `.claude/skills/` (35 of them); `_resolve_skills_root()`
  falls back to `skills/` — a test pins both locations.
- The parent directory `E:\agency-agents` holds credential-looking files
  (`neon.txt`, `neon-pw.txt`) and course docs outside this repo. Never copy
  them into the repo, never paste their contents anywhere.
- Git identity for commits: `imam sanghaar <imamsanghaarc@gmail.com>`.

## Status ledgers (read before planning anything)

- `done.md` — every shipped feature with a description (founders' overview).
- `sanghaar.md` — Sanghaar's queue: only items that are NOT done.
- `muheeb.md` — Muheeb's queue: features not built yet.
- `eval_results.md` — measured results only. `plan.md` — the ten design
  decisions behind the architecture.
- `deployment.md` — the operations reference: least-privilege credentials,
  connection settings, provider rotation semantics, trust boundaries.
- `SYSTEM_PROMPT.md` — the agent's runtime contract; changes invalidate the
  section-A eval numbers.
- `FEDS-Self-Learning-Algorithm-Design.docx` — the Verified Lesson Loop design
  for the next phase; `sanghaar.md` maps its seven phases to what exists.
