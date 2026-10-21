# FEDS

**F**rontend **E**ngineering **D**igital **S**pecialist — an AI Employee that
delivers **audited frontend performance and accessibility fixes**, approved by a human.
---

## Quick start

```powershell
cd frontend-developer-FTE
uv sync
Copy-Item .env.example .env     # then fill in NEON_DATABASE_URL and a key
uv run python setup_neon.py
uv run python worker.py "Create a responsive navigation bar"
```

Credentials live in `.env`, which is gitignored and never committed. A deployed
process should supply real environment variables instead; those always win.

Ask FEDS who it is and it will answer by name:

```powershell
uv run python worker.py "Who are you?"
> I am FEDS — Frontend Engineering Digital Specialist.
```

---

## The Wedge (v1-15)

FEDS does **not** compete on "general frontend coding" — Cursor, Claude Code, v0, Lovable, Bolt, and Devin already own that space.

**FEDS's wedge:** **Frontend performance and accessibility fixes, audited and approved by a human.**

| What FEDS claims | How it's proven |
|---|---|
| "This change improves LCP by 400ms" | Zero-quota verifier measures before/after LCP/INP/CLS (v1-02) |
| "This change fixes 3 accessibility violations" | axe-core WCAG 2.2 A/AA scan with rule IDs (v1-02) |
| "A human approved this" | DB-enforced approval gate; worker cannot bypass (v1-06) |
| "No code was injected" | Sandbox execution with credentials stripped (v1-08) |
| "This prompt was not hijacked" | Ingestion provenance + retrieval contract (v1-09) |

**What FEDS explicitly does NOT claim:**
- Better general frontend coding than Cursor/Claude/v0
- Autonomous operation without human approval
- Perfect code generation without verification

---

## What FEDS Does

| Capability | Tool |
| --- | --- |
| Save a frontend task, component, or layout pattern | `save_task` |
| Find prior work by meaning, not keywords | `find_similar_tasks` |
| Browse what is already saved | `list_tasks` |
| Look up one task by name | `lookup_task` |
| Record a human review outcome | `record_review` |
| Promote an already-approved task to staging/production | `publish_task` |

FEDS also loads a skill before answering, so it follows a specific engineering
method rather than improvising. Thirty-five skills are available, covering
frontend fundamentals, languages and formats, CSS preprocessors, template
languages, WebAssembly, and three workflow skills (`summarize-component`,
`find-similar-components`, `escalate-review`).

---

## Architecture

| Piece | File | Role |
| --- | --- | --- |
| Agent | `worker.py` | Loop, skills, guardrails, approvals, audit hooks |
| Identity and config | `config.py` | The FEDS name, keys, models, provider registry |
| Identity contract | `SYSTEM_PROMPT.md` | How FEDS behaves and answers |
| Scoped MCP server | `frontend_workspace_mcp/server.py` | All runtime business-data access |
| Provider routing | `provider_router.py` | Quota-aware fallback across providers |
| Schema setup | `setup_neon.py` | Tables, pgvector, HNSW index |
| Re-embedding | `reembed.py` | Rebuilds vectors on a model change, dedupes tasks |
| Audit replay | `replay.py` | Reconstructs a conversation from the trail |
| Design record | `plan.md` | The significant decisions and why |
| Backlog | `sanghaar.md` | Done, deferred, or blocked |

### Runtime rules

- All business data goes through the scoped `frontend-workspace` MCP server.
  FEDS never writes SQL.
- Publication requires a recorded human approval first.
- Input guardrails block destructive and audit-bypass requests before any model
  or persistence work happens.
- Every stored embedding records the model that produced it, so vectors from
  different providers are never compared.

---

## Skills and progressive disclosure

On a Unix-like host the SDK's sandbox `Skills` capability loads skills lazily. On
Windows that capability is unavailable, so FEDS uses an equivalent skill index
plus a `load_skill` tool.

All 35 skills live in `.claude/skills/`, the standard location Claude Code,
OpenCode, and the sandbox SDK all read. `_resolve_skills_root()` prefers that
path and falls back to `skills/`, so neither loader can disagree about where
the corpus is.

Either way only the skill a task actually needs is read:

| | Characters |
| --- | --- |
| Skill index | ~11,400 |
| Everything inlined | ~100,700 |

An 88.6% reduction in context cost per turn.

---

## Providers

Chat and embeddings route independently, because not every provider offers
both.

| Provider | Chat | Embeddings | State |
| --- | --- | --- | --- |
| Gemini | yes | yes | **enabled and working** (`gemini-3.5-flash` / `gemini-embedding-001`) |
| OpenAI | yes | yes | disabled; credential rejected (401) |

The router rotates automatically on quota or balance exhaustion, honors a
server-supplied retry delay, and returns to the preferred provider once its quota
recovers. Exhaustion is reported inconsistently across hosts — `429
insufficient_quota` and `402 Insufficient Balance` both rotate.

Only quota and balance failures rotate. A rejected credential or a genuine bug
propagates, so a broken key can never look like a healthy system.

> **Note on models:** `gemini-2.5-flash` is retired for newly provisioned keys
> and returns HTTP 404 "no longer available to new users". FEDS defaults to
> `gemini-3.5-flash`. Change it with `GEMINI_CHAT_MODEL`. Models that are live
> but saturated return `503`, which is transient and not a rotation trigger.

```powershell
$env:OPENAI_ENABLED = "1"     # after installing a funded, valid key
uv run python status_providers.py   # check every provider
```

---

## Tests

The offline suite needs no model provider:

```powershell
uv run python run_tests.py
```

Live provider checks are opt-in because they consume quota:

```powershell
$env:RUN_LIVE_TESTS = "1"; uv run python test_chat_fallback.py
$env:RUN_LIVE_TESTS = "1"; uv run python test_fallback_forced.py
uv run python test_config.py --strict
```

---

## Operations

```powershell
uv run python replay.py                       # list recent conversations
uv run python replay.py <conversation_id>     # replay one conversation
uv run python replay.py <conversation_id> --json

uv run python reembed.py --dry-run            # what would change
uv run python reembed.py --apply --dedupe --purge-orphans

uv run python ingest_refs.py --dir docs/reference            # dry-run
uv run python ingest_refs.py --dir docs/reference --apply    # idempotent per (source, title)
```

Approvals:

```powershell
uv run python worker.py --decide <run_id> approve
uv run python worker.py --decide <run_id> reject
```

Who may decide is policy, not a name typed into the argument. With no
`FEDS_ALLOWED_OPERATORS` set, only `operator-local` can decide; set a
comma-separated allowlist (`FEDS_ALLOWED_OPERATORS=alice,bob`) to grant real
names — the anonymous default is then refused unless it is listed too. An
unauthorized decision writes an `approval_refused` audit row and the CLI
exits non-zero.

---

## Governance (v1)

| Feature | Implementation | Status |
|---|---|---|
| **DB-enforced approval** | `feds_approver` role + SECURITY DEFINER triggers; `feds_app` cannot forge approvals | v1-06 ✅ |
| **Durable session log** | `audit_log` event slices; `--resume` restarts from last event | v1-07 ✅ |
| **Sandbox execution** | Isolated Python/Node/Shell; credentials stripped; retryable errors | v1-08 ✅ |
| **Injection defense** | Provenance stamping, retrieval contract, red-team tests | v1-09 ✅ |
| **Approval console** | Web UI for parked runs (Slack/email notify) | v1-10 ✅ |
| **Team identity** | Per-request user injection; memory isolation | v1-11 ✅ |
| **Budgets & alerts** | Monthly caps, warning thresholds, hard-cap guardrail | v1-12 ✅ |
| **CI pipeline** | GitHub Actions: offline tests, secret scan, skill validation, scheduled live evals | v1-13 ✅ |
| **Pause notifications** | Slack/email on approval park | v1-14 ✅ |

### Evidence artifacts

| Artifact | Produced by | Purpose |
|---|---|---|
| `verifications` rows | Zero-quota verifier (v1-02) | Before/after CWV + axe-core deltas |
| `approvals` rows | `feds_approver` role | Human approval record |
| `audit_log` | Every write + guardrail trip | Full reconstruction |
| `capability_invocations` | Every turn + tool call | Cost + latency rollups |
| `verification_artifacts/` | Verifier screenshots | Visual proof |

---

## Deployment

`Dockerfile` and `compose.yml` are provided but **have not been run** — Docker
was unavailable in this environment. See `deployment.md` for the process shape,
connection conventions, provider resilience, and secret-hardening steps.

---

## Security

Credentials are **not** in the source. They live in `.env` (gitignored) or in
real environment variables.

- `test_config.py` fails the build if a credential pattern appears in any
  committed `.py`, `.md`, or `.yml` file, so a key cannot be reintroduced by
  accident.
- A provider with no key is treated as disabled rather than misconfigured.
- `ALLOW_PRODUCTION_PUBLISH=1` should only ever be set on a host allowed to
  publish to production.

If a key was ever committed, rotating it is the only fix: git history is
permanent.
