# Roadmap

A curated view for contributors. It **organizes** the queue — it never
replaces it:

- [`sanghaar.md`](sanghaar.md) — the source of truth: priorities, estimates,
  acceptance criteria for everything not shipped.
- [`AGENTS.md`](AGENTS.md) → *Open work* — immediately actionable items with
  file pointers and "done when" criteria.

If an item lives in neither, add it there first; do not create roadmap-only
work.

## Now — pick-up-able work

| Area | What | Tracked in |
|---|---|---|
| CLI | Token streaming, `/model` switching, `/compact`, tab completion, context-panel gaps, clean-clone verification | AGENTS.md → Open work |
| DevOps | CI job for the TUI smoke (`uv sync --extra cli` + `feds_cli.smoke`), scheduled `test_config.py --strict`, container build | AGENTS.md → Open work |
| Docs | Ledgers behind reality (`updated/done.md` lacks the CLI/Ollama entries), pull-request template, macOS/Linux manual pass | AGENTS.md → Open work, `sanghaar.md` D2 |
| Eval | Stable-rate evidence run — harness ready, blocked on model quota only | `sanghaar.md` v1-03 |

## Next — v1 leftovers (needs a plan before coding)

- **Durable execution / nervous system** (`sanghaar.md` v1-16 + D1): cron and
  webhook triggers, crash-safe steps with retries, concurrency and throttle
  control, human-in-the-loop gates — the background-jobs layer. Design in
  `updated/nervous-system.md`; keep it zero-import and swap-ready.
- **DSoR minimal slice** (`sanghaar.md` D1): requirement mapping for
  `publish_task` / `promote_memory` against the DSoR spec.

## Then — v1.1 "Governed & Observable"

| ID | Item |
|---|---|
| v1.1-01 | Agent registry and kill switch |
| v1.1-02 | Operations dashboard + proof page |
| v1.1-03 | Oversight and ROI report |
| v1.1-04 | Compliance evidence pack + deletion |
| v1.1-05 | Parallel runs and scheduled automations |

## Later — v2 "Self-Learning & Benchmarked"

| ID | Item |
|---|---|
| v2-01 | Verified Lesson Loop (phases 1–3) |
| v2-02 | Published benchmark vs baseline |
| v2-03 | Internal memory eval |
| v2-04 | Deployment hardening — the container finally tested |
| v2-05 | Pilot program (3–5 free pilots) |
| v2-06 | Outcome-based pricing metering |

## Where common asks already live

Before filing something new, check whether it is already planned:

- **API docs / architecture diagrams** → `area/docs` issue against the
  existing surfaces (`frontend_workspace_mcp/server.py`,
  `approval_console.py`, this file).
- **Query performance / caching (Redis etc.)** → nothing exists today:
  retrieval reads pgvector directly. Propose it as an `area/database` issue
  with measurements before building.
- **Error tracking / monitoring** → part of v1.1-02 (operations dashboard).
- **Webhooks, background jobs, scheduled runs** → v1-16 (nervous system) and
  v1.1-05 (parallel runs + scheduled automations).
- **Auth/OAuth, multi-tenant SaaS** → not planned; access is the operator
  allowlist + per-request identity (see README → *Security & access*).
