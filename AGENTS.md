# AGENTS.md — FEDS (frontend-developer-FTE)

FEDS is an AI employee for frontend work: one Python repo run with `uv`, no
build step. At runtime it is two processes: `worker.py` (the agent loop)
spawns the `frontend_workspace_mcp` server over stdio, which is the only
thing allowed to touch Neon (pgvector).

## Start here (first 15 minutes, human or agent)

- Three surfaces, one codebase: `worker.py` (the agent loop, runnable
  headless), `frontend_workspace_mcp/server.py` (the only process allowed to
  touch Neon, spawned over stdio), and `feds_cli/` (the terminal TUI, which
  imports the worker in-process — it never spawns it).
- Read in this order: this file → `README.md` (product and wedge) →
  `docs/plan.md` (the ten design decisions) → `sanghaar.md` (the open queue)
  → `worker.py` + `config.py` (implementation) → `SYSTEM_PROMPT.md` (the
  agent's contract; changing it invalidates the eval numbers).
- Setup: `uv sync` (add `--extra cli` for the TUI), copy `.env.example` →
  `.env` and fill it, `uv run python setup_neon.py`. Without a `.env` the
  worker cannot run a turn or reach the database; the exact behavior of the
  offline gate on a clean clone is not yet verified (see `## Open work`).
- Definition of done for a change: `uv run python run_tests.py` green (3
  suites, including the planted-secret scanner), no credentials anywhere in
  the diff, then commit and confirm the push with `git ls-remote origin HEAD`.
- Live checks are opt-in (`RUN_LIVE_TESTS=1`) and quota-bound; exit code 2 is
  "quota skipped cases", never a pass. `eval_results.md` may contain only
  numbers from real runs; NULL costs stay NULL.
- Touching the TUI? Run `uv run python -m feds_cli.smoke [--live]` too (see
  `feds_cli/README.md`).
- If this file and the code disagree, the code and its tests win — fix this
  file in the same commit.

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
- **DB-enforced approval (v1-06):** `feds_app` role CANNOT write `approvals`
  table; only `feds_approver` role can write it. SECURITY DEFINER functions
  `promote_task()`, `promote_memory()` + triggers enforce approval at the DB
  level. Worker-side `require_approval` removed; DB is the authority.
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
  restricted runtime role. Set `FEDS_APPROVER_DB_PASSWORD` for the approval role.
- Offline gate before any push: `uv run python run_tests.py` → 3 suites
  (config wiring, provider fallback router, guardrails and inputs). Exits
  non-zero on failure; keep it green. CI runs exactly this gate with
  `RUN_LIVE_TESTS` unset. The live credential probe
  `uv run python test_config.py --strict` (fails on a stale key) is manual
  today — run it after touching `.env`, `config.py`, or provider wiring.
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
- Interactive TUI (opencode-style, same in-process worker): `uv sync --extra cli`
  then `uv run feds` from the repo root; headless check with
  `uv run python -m feds_cli.smoke [--live]`. See `feds_cli/README.md`.
- Resume a parked approval: `uv run python worker.py --decide <run_id>
  approve|reject [operator]`. Decisions are policy-checked:
  `FEDS_ALLOWED_OPERATORS` (unset = only `operator-local`); a refusal is
  audited as `approval_refused` and exits non-zero (2 = usage error).
- Resume a session: `uv run python worker.py --resume <conversation_id>
  [user_input] [--max-iterations N] [--max-cost CENTS] [--max-time SECONDS]`.
- Provider availability: `uv run python status_providers.py`.
- Ingest reference material: `uv run python ingest_refs.py --dir <path>
  [--source label] [--apply]` — dry-run by default, idempotent per
  (source, title), so re-running only adds new files.
- Approval console (web UI): `uv run python approval_console.py` → http://localhost:8080
- Budget management: `uv run python budget_manager.py set|status|check ...`
- Verifier (zero-quota): `uv run python verifier.py <url|file|html> <task_id> <conv_id>`

## Provider Chain (v1-04 complete)

```
gemini → gemini-fallback → openrouter (Claude) → ollama (gpt-oss:120b) → openai (gpt-4o-mini)
```

- 5 provider entries, 4 independent quota pools
- All providers authenticate (HTTP 200)
- Embeddings: Gemini (×2, 768-dim) + OpenAI (`text-embedding-3-small`)
- Ollama Cloud is chat-only on this account and its models are plan-gated: a
  free-plan key answers 402 for Pro models and 410 for retired ones. Probe with
  `uv run python status_providers.py` before changing `OLLAMA_CHAT_MODEL`; the
  health check itself uses the official `ollama` client, while the agent loop
  uses `https://ollama.com/v1` (OpenAI-compatible, tool calls + streaming).
- Groq removed; OpenRouter + OpenAI added

## Database Schema (v1 complete)

**New tables:**
- `verifications` — CWV + axe-core results, before/after deltas, screenshot artifact
- `approvals` — only `feds_approver` can write; `feds_app` can only read
- `workspace_budgets` — monthly caps, warning threshold, hard cap
- `run_states` — operator column, advisory locking for concurrent decisions

**New roles:**
- `feds_approver` — only role that can write `approvals`; executes `promote_task()`, `promote_memory()`

**SECURITY DEFINER functions + triggers:**
- `promote_task()` + BEFORE UPDATE trigger on `documents` (publish)
- `promote_memory()` + called directly by MCP (promote)

## New Tools (v1)

| Tool | Purpose |
|---|---|
| `approval_console.py` | FastAPI web UI for parked runs |
| `approval_notifier.py` | Slack/email notifications on approval park |
| `budget_manager.py` | Monthly caps, warning threshold, hard-cap guardrail |
| `verifier.py` | Playwright + axe-core CWV + a11y verification |
| `sandbox_executor.py` | Isolated Python/Node/Shell execution, credentials stripped |
| `security_ingestion.py` | Provenance stamping, injection detection, red-team tests |

**New MCP tools:**
- `set_user(user_id, user_name)` / `get_current_user()` — per-request identity (v1-11)

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
- Current measured state: trigger precision 11/11 (single sample), system-prompt
  eval 8/8 run, 6 passed pre-fix; both failures were real bugs (mode instability,
  guardrail contradiction), now fixed and pinned offline, stability re-run
  pending quota. Numbers never carry over: after touching `SYSTEM_PROMPT.md`
  or the guardrail, re-run.
- Quick scoreboard: `uv run python eval_summary.py`.

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

- `updated/done.md` — every shipped feature with a description (founders'
  overview).
- `sanghaar.md` — Sanghaar's queue: only items that are NOT done (OPEN as of
  v1: v1-16, D1–D3, then the v1.1/v2 plan).
- `muheeb.md` — no longer exists; that queue was merged into `sanghaar.md`.
- `eval_results.md` — measured results only. `docs/plan.md` — the ten design
  decisions behind the architecture.
- `docs/deployment.md` — the operations reference: least-privilege
  credentials, connection settings, provider rotation semantics, trust
  boundaries.
- `SYSTEM_PROMPT.md` — the agent's runtime contract; changes invalidate the
  section-A eval numbers.
- `docs/FEDS-Self-Learning-Algorithm-Design.docx` — the Verified Lesson Loop
  design for the next phase; `sanghaar.md` maps its seven phases to what
  exists.
- `updated/cli.md` — complete CLI reference for all commands.
- `ROADMAP.md` — curated contributor view of the queue; `sanghaar.md` stays
  the source of truth, so never add roadmap-only work.
- `docs/extending-feds.md` — how to add a skill, an MCP tool, or a standalone
  integration (`templates/skill/SKILL.md` is the copyable boilerplate).
- `feds_cli/README.md` — the terminal TUI: run instructions, keys, commands,
  architecture, known gaps.
- This file — the working contract for contributors and agents; the
  `## Open work` section at the end lists what is missing right now.

## v1 Status — 14 shipped, v1-03 evidence quota-blocked (v1-16 + D1–D3 still open)

| ID | Item | Status |
|---|---|---|
| v1-01 | KSoR Integration (Rung 1) | ✅ 35 skills migrated, `llms.txt` generated |
| v1-02 | Zero-quota Verifier + Before/After | ✅ Playwright + axe-core, `verifications` table |
| v1-03 | Stable-rate Eval Evidence | ⚠️ Quota-blocked (harness ready) |
| v1-04 | Provider Independence | ✅ 4 families, 3 quota pools |
| v1-05 | Secrets Rotation | ✅ `.env` updated, scanner passes |
| v1-06 | DB-Enforced Approval | ✅ `approvals` table, `feds_approver` role, triggers |
| v1-07 | Durable Session Log + Resume | ✅ `--resume`, event-slice API, stopping conditions |
| v1-08 | Sandboxed Execution | ✅ `sandbox_executor.py`, credentials stripped |
| v1-09 | Injection Defense | ✅ `security_ingestion.py`, provenance, red-team tests |
| v1-10 | Approval Console (Web UI) | ✅ `approval_console.py` (FastAPI) |
| v1-11 | Team Identity & Sessions | ✅ Per-request `set_user`/`get_current_user` |
| v1-12 | Budgets & Cost Alerts | ✅ `budget_manager.py`, `workspace_budgets`, hard-cap |
| v1-13 | CI Pipeline | ✅ `.github/workflows/ci.yml` |
| v1-14 | Approval Pause Notifications | ✅ `approval_notifier.py` (Slack/email) |
| v1-15 | Pick the Wedge | ✅ README: "audited frontend performance & a11y fixes" |

## Key Files to Read First

| File | Purpose |
|---|---|
| `worker.py` | Agent loop, skills, guardrails, approvals, resume |
| `config.py` | Single config surface (providers, DB, pricing) |
| `frontend_workspace_mcp/server.py` | MCP tools, DB access, memory isolation |
| `setup_neon.py` | Full schema, roles, triggers, functions |
| `provider_router.py` | Quota-aware fallback logic |
| `SYSTEM_PROMPT.md` | Agent runtime contract |
| `verifier.py` | Zero-quota CWV + a11y verification |
| `sandbox_executor.py` | Isolated code execution |
| `security_ingestion.py` | Provenance, injection detection |
| `approval_console.py` | Web UI for approvals |
| `feds_cli/main.py` | Textual TUI: banner, screens, widgets, slash commands |
| `feds_cli/worker_bridge.py` | In-process worker calls, stdio restoration, snapshots |
| `feds_cli/smoke.py` | Headless TUI regression check (no TTY needed) |

## Open work — what is missing

`sanghaar.md` holds the prioritized queue with estimates (items marked
**OPEN**); this section is the short list an outside contributor can act on
today. Close an item by updating this table in the same PR.

### FEDS CLI (`feds_cli/`) — good first issues

| Gap | Files | Done when |
|---|---|---|
| No token streaming: a turn appears only when the worker prints its final answer | `worker.py` (`run_task` needs an `on_token` hook beside `_say`/`_CAPTURE`), `feds_cli/worker_bridge.py`, `feds_cli/main.py` | text renders incrementally in `ChatView`, `uv run python -m feds_cli.smoke --live` still passes, headless worker output unchanged |
| `/model` prints the chain but cannot switch; changing models means editing `.env` and restarting | `feds_cli/main.py`, `feds_cli/worker_bridge.py` | a model picked in the TUI is used by the next turn, shown in the status bar, pinned by an offline test |
| `/compact` and `/update` announce a plan instead of acting | `feds_cli/main.py` | `/compact` shrinks the stored context and reports the delta; `/update` performs a real check and degrades gracefully offline |
| Context panel gaps: live provider cooldown state is absent; `skills_loaded` never fills from `load_skill` calls | `feds_cli/main.py`, `feds_cli/worker_bridge.py`, `worker.py` | panel reflects the router's current cooldowns and lists skills loaded that turn |
| Prompt ergonomics: no tab completion for slash commands or skills; history only on Ctrl+Up/Down (plain Up/Down must keep moving the cursor in the prompt — do not rebind it) | `feds_cli/main.py` | Tab completes without breaking `TextArea` cursor movement; the smoke test covers it |
| `/cost` has only been observed on zero-cost (free-tier) turns; unpriced rows must stay NULL, never 0 | `feds_cli/worker_bridge.py` | a turn on a priced model shows non-zero cents and NULL still renders as unpriced |
| Not verified on a clean clone: `uv sync --extra cli` + `uv run python -m feds_cli.smoke` should pass with no `.env` at all — confirm, then pin it in `feds_cli/README.md` | `feds_cli/smoke.py` | documented after a real no-`.env` run |

### CI and repository hygiene

| Gap | Where | Done when |
|---|---|---|
| CI never builds or exercises the TUI: the workflow syncs `--frozen` (no `--extra cli`) and runs only `run_tests.py` | `.github/workflows/ci.yml` | a job runs `uv sync --extra cli` then `uv run python -m feds_cli.smoke` on Linux |
| No credential probe in CI (`test_config.py --strict` is manual) | `.github/workflows/ci.yml` | a scheduled/dispatch job runs `--strict` with repository secrets and fails on a stale key |
| No pull-request template (CONTRIBUTING.md, CODE_OF_CONDUCT.md, and both issue templates exist) | `.github/` | a PR template points authors at AGENTS.md → Start here for the definition of done |
| `README.md` never mentions the TUI (`uv run feds`) and its quick start is PowerShell-only | `README.md` | quick start shows PowerShell, cmd, and bash (macOS/Linux) |
| Containers untested: `Dockerfile`/`compose.yml` were reviewed but never run (no Docker in the dev environment) | `Dockerfile`, `compose.yml` | CI builds the image, or the README labels the container path untested |
| Ledger drift: `updated/done.md` covers v1-01…v1-15 but not the FEDS CLI (`feds_cli`) or the Ollama provider (D2) | `updated/done.md` | done.md lists the CLI and Ollama work too; sanghaar.md holds only open work |
| Cross-platform: everything was verified on Windows (PowerShell/cmd) plus a headless harness — macOS/Linux only have the CI signal | `feds_cli/` | a manual pass on macOS and Linux is recorded in `feds_cli/README.md` |

### Needs a plan, not a drive-by change

- **v1-16 / D1 — nervous system (durable execution):** three-layer engine
  (senses, reflexes, balance), zero-import and swap-ready across
  Inngest/Temporal/Restate/Dapr; specs in `sanghaar.md` and
  `updated/nervous-system.md`.
- **v1-03 — stable-rate eval evidence:** harness ready, runs quota-blocked;
  exit code 2 is never a pass and the numbers may never be fabricated.
- **D2/D3 — status docs and market-report traceability:** update ledgers and
  the gap→coverage→evidence table as items land.
- **KSoR/DSoR beyond Rung 1:** see the implementation notes at the end of
  `sanghaar.md` (least privilege, no ungoverned mixing into `embeddings`).