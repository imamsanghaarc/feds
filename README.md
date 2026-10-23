# FEDS

**Frontend Engineering Digital Specialist** — an AI employee that delivers
**audited frontend performance and accessibility fixes, approved by a human**.

[![FEDS CI](https://github.com/imamsanghaarc/feds/actions/workflows/ci.yml/badge.svg)](https://github.com/imamsanghaarc/feds/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![uv](https://img.shields.io/badge/uv-managed-orange)

---

## Why FEDS

FEDS does **not** compete on general frontend coding — Cursor, Claude Code,
v0, Lovable, Bolt and Devin already own that space.

**The wedge:** frontend performance and accessibility fixes that are
**measured, audited, and human-approved**.

| What FEDS claims | How it is proven |
|---|---|
| "This change improves LCP by 400 ms" | Zero-quota verifier measures before/after LCP/INP/CLS (v1-02) |
| "This change fixes 3 accessibility violations" | axe-core WCAG 2.2 A/AA scan with rule IDs (v1-02) |
| "A human approved this" | DB-enforced approval gate; the worker cannot bypass it (v1-06) |
| "No code was injected" | Sandbox execution with credentials stripped (v1-08) |
| "This prompt was not hijacked" | Ingestion provenance + retrieval contract (v1-09) |

**FEDS explicitly does not claim:** better general frontend coding than
Cursor/Claude/v0, autonomous operation without human approval, or perfect code
generation without verification.

---

## Quick start

**Prerequisites:** Python 3.10+, [`uv`](https://docs.astral.sh/uv/), a
Postgres database with pgvector (e.g. [Neon](https://neon.tech)), and at least
one chat-provider key.

```bash
git clone https://github.com/imamsanghaarc/feds.git
cd feds

uv sync
cp .env.example .env        # fill in the values; .env is gitignored
uv run python setup_neon.py # idempotent schema (needs NEON_DATABASE_URL)

uv run python worker.py "Create a responsive navigation bar"
```

<details>
<summary>PowerShell / cmd equivalents</summary>

```powershell
uv sync
Copy-Item .env.example .env
uv run python setup_neon.py
uv run python worker.py "Create a responsive navigation bar"
```

```cmd
uv sync
copy .env.example .env
uv run python setup_neon.py
uv run python worker.py "Create a responsive navigation bar"
```

</details>

Ask FEDS who it is and it will answer by name:

```console
$ uv run python worker.py "Who are you?"
I am FEDS — Frontend Engineering Digital Specialist.
```

### Terminal UI

An opencode-style TUI over the same worker (it imports `worker.py`
in-process — nothing is spawned):

```bash
uv sync --extra cli
uv run feds
```

Split screen with chat, a live context panel (tokens, skills, MCP tools,
provider chain), session picker, and slash commands. Full reference:
[`feds_cli/README.md`](feds_cli/README.md).

---

## Capabilities

| Capability | Tool |
|---|---|
| Save a frontend task, component, or layout pattern | `save_task` |
| Find prior work by meaning, not keywords | `find_similar_tasks` |
| Browse what is already saved | `list_tasks` |
| Look up one task by name | `lookup_task` |
| Record a human review outcome | `record_review` |
| Promote an already-approved task to staging/production | `publish_task` |

FEDS loads a skill before answering, so it follows a specific engineering
method instead of improvising. **35 skills** cover frontend fundamentals,
languages and formats, CSS preprocessors, template languages, WebAssembly,
and three workflow skills (`summarize-component`, `find-similar-components`,
`escalate-review`).

---

## Architecture

| Piece | File | Role |
|---|---|---|
| Agent | `worker.py` | Loop, skills, guardrails, approvals, resume |
| Config | `config.py` | Single config surface: providers, models, pricing, DB |
| Identity contract | `SYSTEM_PROMPT.md` | How FEDS behaves and answers |
| Scoped MCP server | `frontend_workspace_mcp/server.py` | All runtime business-data access |
| Terminal UI | `feds_cli/` | Textual TUI; imports the worker in-process |
| Provider routing | `provider_router.py` | Quota-aware fallback across providers |
| Schema setup | `setup_neon.py` | Tables, roles, triggers, pgvector, HNSW index |
| Re-embedding | `reembed.py` | Rebuilds vectors on a model change, dedupes |
| Audit replay | `replay.py` | Reconstructs a conversation from the trail |
| Design record | `docs/plan.md` | The ten significant decisions and why |
| Open queue | `sanghaar.md` | Everything not shipped yet |

### Runtime rules

- All business data goes through the scoped `frontend-workspace` MCP server.
  The worker never writes SQL, and the runtime role cannot run DDL.
- Publication requires a recorded human approval first; `publish_task` to
  production additionally needs `ALLOW_PRODUCTION_PUBLISH=1`.
- Input guardrails block destructive and audit-bypass requests before any
  model or persistence work happens.
- Every stored embedding records the model that produced it, so vectors from
  different providers are never compared.

---

## Skills and progressive disclosure

On a Unix-like host the SDK's sandbox `Skills` capability loads skills lazily.
On Windows that capability is unavailable, so FEDS uses an equivalent skill
index plus a `load_skill` tool.

All 35 skills live in `.claude/skills/`, the standard location Claude Code,
OpenCode, and the sandbox SDK all read. `_resolve_skills_root()` prefers that
path and falls back to `skills/`, so neither loader can disagree about where
the corpus is.

Either way, only the skill a task actually needs is read:

| | Characters |
|---|---|
| Skill index | ~11,400 |
| Everything inlined | ~100,700 |

An **88.6% reduction** in context cost per turn.

---

## Providers

Chat and embeddings route independently, because not every provider offers
both. Five entries, four independent quota pools — all authenticate:

| Provider | Chat | Embeddings | Role |
|---|---|---|---|
| Gemini | yes | yes | Preferred (`gemini-3.5-flash`, `gemini-embedding-001`) |
| Gemini (2nd key) | yes | yes | Separate fallback quota pool |
| OpenRouter | yes | — | Third pool (Claude) |
| Ollama Cloud | yes | — | Fourth pool (`gpt-oss:120b`, tool calling) |
| OpenAI | yes | yes | Last resort + `text-embedding-3-small` |

```text
gemini → gemini-fallback → openrouter → ollama → openai
```

The router rotates automatically on quota or balance exhaustion, honors a
server-supplied retry delay, and returns to the preferred provider once its
quota recovers. Exhaustion is reported inconsistently across hosts — `429
insufficient_quota` and `402 insufficient_balance` both rotate.

Only quota and balance failures rotate. A rejected credential or a genuine
bug propagates, so a broken key can never look like a healthy system.

Model notes:

- `gemini-2.5-flash` is retired for newly provisioned keys (HTTP 404); FEDS
  defaults to `gemini-3.5-flash` (`GEMINI_CHAT_MODEL` to change). A live but
  saturated endpoint returns `503`, which is transient and never a rotation
  trigger.
- Ollama Cloud models are plan-gated: a free-plan key answers `402` for Pro
  models and `410` for retired ones. Probe before changing
  `OLLAMA_CHAT_MODEL`.

```bash
uv run python status_providers.py     # probe every provider
uv run python test_config.py --strict # credential + wiring validation
```

---

## Testing

The offline suite needs no model provider — run it before every push:

```bash
uv run python run_tests.py            # 3 suites: config wiring, router, guardrails
uv run python -m feds_cli.smoke       # TUI layout/commands, no TTY needed
```

Live checks are opt-in because they consume quota:

```bash
RUN_LIVE_TESTS=1 uv run python run_tests.py    # PowerShell: $env:RUN_LIVE_TESTS = "1"
RUN_LIVE_TESTS=1 uv run python test_chat_fallback.py
uv run python test_config.py --strict
uv run python -m feds_cli.smoke --live         # one real worker turn through the TUI
```

Exit code 2 from an eval means *quota-skipped cases*, never a pass — see
[`AGENTS.md`](AGENTS.md) for the full evaluation rules.

---

## Operations

```bash
uv run python replay.py                       # list recent conversations
uv run python replay.py <conversation_id>     # replay one conversation
uv run python replay.py <conversation_id> --json

uv run python reembed.py --dry-run            # what would change
uv run python reembed.py --apply --dedupe --purge-orphans

uv run python ingest_refs.py --dir docs/reference          # dry-run (default)
uv run python ingest_refs.py --dir docs/reference --apply  # idempotent per source/title

uv run python budget_manager.py status        # monthly caps and thresholds
uv run python approval_console.py             # web UI for parked runs (:8080)
```

Approvals — who may decide is policy, not a name typed into an argument:

```bash
uv run python worker.py --decide <run_id> approve
uv run python worker.py --decide <run_id> reject
```

With no `FEDS_ALLOWED_OPERATORS` set, only `operator-local` can decide; set a
comma-separated allowlist to grant real names. An unauthorized decision
writes an `approval_refused` audit row and exits non-zero.

---

## Governance

| Feature | Implementation | Status |
|---|---|---|
| DB-enforced approval | `feds_approver` role + SECURITY DEFINER triggers; `feds_app` cannot forge approvals | v1-06 ✅ |
| Durable session log | `audit_log` event slices; `--resume` restarts from the last event | v1-07 ✅ |
| Sandbox execution | Isolated Python/Node/Shell; credentials stripped | v1-08 ✅ |
| Injection defense | Provenance stamping, retrieval contract, red-team tests | v1-09 ✅ |
| Approval console | Web UI for parked runs, Slack/email notifications | v1-10 / v1-14 ✅ |
| Team identity | Per-request user injection; per-owner memory isolation | v1-11 ✅ |
| Budgets and alerts | Monthly caps, warning thresholds, hard-cap guardrail | v1-12 ✅ |
| CI pipeline | GitHub Actions: offline suite + secret scan, scheduled live evals | v1-13 ✅ |

### Evidence artifacts

| Artifact | Produced by | Purpose |
|---|---|---|
| `verifications` rows | Zero-quota verifier (v1-02) | Before/after CWV + axe-core deltas |
| `approvals` rows | `feds_approver` role | Human approval record |
| `audit_log` | Every write + guardrail trip | Full reconstruction |
| `capability_invocations` | Every turn + tool call | Cost + latency rollups |
| `verification_artifacts/` | Verifier screenshots | Visual proof |

---

## Security

**No credentials live in this repository.** They are read from `.env`
(gitignored) or from real environment variables in a deployment; environment
variables always win.

- `test_config.py` fails if a credential pattern appears in any committed
  `.py`, `.md`, or `.yml` file — the same scanner runs in the offline gate,
  so a key cannot be reintroduced by accident.
- A provider with no key is treated as disabled rather than misconfigured.
- The runtime database role is least-privilege: it cannot run DDL and cannot
  write the `approvals` table.
- If a key was ever committed, rotate it — git history is permanent.

Report a vulnerability privately to **imamsanghaarc@gmail.com** rather than
in a public issue.

---

## Deployment

`Dockerfile` and `compose.yml` are provided but **have not been run** — Docker
was unavailable in the development environment. Treat container deployment as
untested. See [`docs/deployment.md`](docs/deployment.md) for the process
shape, connection conventions, provider resilience, and secret-hardening
steps.

---

## Project layout

```text
worker.py                       agent loop (skills, guardrails, approvals, resume)
config.py                       single config surface: providers, pricing, DB
SYSTEM_PROMPT.md                agent identity contract (changes reset eval numbers)
frontend_workspace_mcp/         scoped MCP server — the only DB access path
feds_cli/                       terminal TUI (imports the worker in-process)
.claude/skills/                 35 skills with progressive disclosure
setup_neon.py                   schema, roles, triggers, pgvector
provider_router.py              quota-aware provider fallback
verifier.py                     zero-quota CWV + axe-core verification
approval_console.py             FastAPI UI for parked approvals
docs/                           plan, deployment, benchmark material
updated/                        ledgers: done.md, cli.md, work notes
sanghaar.md                     open queue (what is not built yet)
AGENTS.md                       working contract for contributors and agents
```

---

## Contributing

- Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) — setup, the offline gate,
  and the rules before you push.
- [`AGENTS.md`](AGENTS.md) is the working contract: read order, definition of
  done, and **Open work** — the current backlog of what is missing, with file
  pointers and acceptance criteria.
- Participation is governed by our [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

---

## Project status and license

v1 governance and proof features are shipped; the terminal TUI landed
recently. The prioritized roadmap lives in [`sanghaar.md`](sanghaar.md), and
what is missing right now is tracked in the **Open work** section of
[`AGENTS.md`](AGENTS.md).

**No license file yet.** The choice (MIT vs Apache-2.0) is tracked in
`AGENTS.md` → Open work. Until it lands, all rights are reserved — do not
assume permissive terms.
