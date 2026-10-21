# FEDS CLI Reference

Complete command-line interface for FEDS (Frontend Engineering Digital Specialist).

---

## Quick Start

```powershell
cd frontend-developer-FTE
uv run python worker.py "Create an accessible responsive navbar"
```

---

## Commands

### `worker.py` — Main Agent Loop

```powershell
# Run a frontend task
uv run python worker.py "<task description>"

# Interactive mode (no args)
uv run python worker.py

# Resume a parked session
uv run python worker.py --resume <conversation_id> [user_input] [--max-iterations N] [--max-cost CENTS] [--max-time SECONDS]

# Apply approval decision
uv run python worker.py --decide <run_id> approve|reject [operator]
```

#### Arguments

| Flag | Description |
|---|---|
| `--resume <conversation_id>` | Resume a session from audit_log |
| `--decide <run_id>` | Apply approve/reject to parked run |
| `--max-iterations N` | Max agent iterations (default: 50) |
| `--max-cost CENTS` | Hard cost cap in cents |
| `--max-time SECONDS` | Wall-clock limit |

#### Examples

```powershell
# Simple task
uv run python worker.py "Create a responsive card component with hover effects"

# Complex task with constraints
uv run python worker.py "Build an accessible data table with sorting, pagination, and keyboard navigation. LCP must be < 2.5s."

# Resume interrupted session
uv run python worker.py --resume abc123def456 "Continue from where we left off"

# Resume with limits
uv run python worker.py --resume abc123def456 --max-cost 500 --max-time 300

# Approve a parked run
uv run python worker.py --decide run_abc123 approve alice

# Reject a parked run
uv run python worker.py --decide run_abc123 reject bob
```

---

## Utility Commands

### `setup_neon.py` — Database Schema

```powershell
# One-time schema setup (run after setting NEON_DATABASE_URL)
uv run python setup_neon.py

# Provisions: tables, indexes, HNSW vector index, roles (feds_app, feds_approver)
```

### `status_providers.py` — Provider Health

```powershell
# Check all configured provider credentials
uv run python status_providers.py
```

Output:
```
enabled flags : gemini=on, gemini-fallback=on, openrouter=on, openai=on
chat order    : ['gemini', 'gemini-fallback', 'openrouter', 'openai']
embed order   : ['gemini', 'gemini-fallback', 'openai']

gemini    -> HTTP 200  USABLE   works, replied ''
gemini-fb -> HTTP 200  USABLE   works, replied ''
openai    -> HTTP 200  USABLE   credential works

RESULT: usable now: gemini, gemini-fb, openai
```

### `test_config.py` — Configuration Validation

```powershell
# Offline validation (default)
uv run python test_config.py

# Strict live credential check (fails on bad keys)
uv run python test_config.py --strict

# Skip live probes
uv run python test_config.py --offline
```

### `run_tests.py` — Full Test Suite

```powershell
# All offline tests (3 suites)
uv run python run_tests.py

# With live provider tests (requires RUN_LIVE_TESTS=1)
$env:RUN_LIVE_TESTS = "1"; uv run python run_tests.py
```

### `eval_triggers.py` — Trigger Evaluation

```powershell
# Run trigger eval (resumable, cached)
uv run python eval_triggers.py

# Re-score all cases
$env:RETRY_ALL = "1"; uv run python eval_triggers.py

# Re-score specific cases
uv run python eval_triggers.py case_1 case_3
```

### `eval_summary.py` — Evaluation Summary

```powershell
# Print eval results summary
uv run python eval_summary.py
```

### `replay.py` — Conversation Reconstruction

```powershell
# List recent conversations
uv run python replay.py

# Replay one conversation
uv run python replay.py <conversation_id>

# JSON output
uv run python replay.py <conversation_id> --json

# Cost rollup
uv run python replay.py --costs
```

### `reembed.py` — Vector Re-embedding

```powershell
# Dry run (what would change)
uv run python reembed.py --dry-run

# Apply with deduping and orphan purge
uv run python reembed.py --apply --dedupe --purge-orphans
```

### `ingest_refs.py` — Bulk Reference Ingestion

```powershell
# Dry run
uv run python ingest_refs.py --dir docs/reference

# List files only
uv run python ingest_refs.py --dir docs/reference --list

# Apply (idempotent per source+title)
uv run python ingest_refs.py --dir docs/reference --apply --source design-notes
```

### `seed_corpus.py` — Seed Corpus

```powershell
# Dry run
uv run python seed_corpus.py --dry-run

# Apply (14 hand-authored cases)
uv run python seed_corpus.py --apply
```

### `verify_corpus.py` — Corpus Validation

```powershell
# Verify seed corpus rankings
uv run python verify_corpus.py
```

### `budget_manager.py` — Budget Management

```powershell
# Set budget
uv run python budget_manager.py set my-workspace 50 --warning 80 --recipients https://hooks.slack.com/xxx

# Show status
uv run python budget_manager.py status my-workspace

# Run periodic check
uv run python budget_manager.py check
```

### `approval_console.py` — Web UI

```powershell
# Start approval console (default port 8080)
uv run python approval_console.py

# Open http://localhost:8080
```

### `approval_notifier.py` — Notifications

```powershell
# Test notification
uv run python approval_notifier.py
```

### `verifier.py` — Frontend Verification

```powershell
# Verify a URL
uv run python verifier.py https://example.com task-123 conv-456

# Verify local HTML file
uv run python verifier.py ./dist/index.html task-123 conv-456

# Verify raw HTML
uv run python verifier.py "<html>...</html>" task-123 conv-456
```

### `status_providers.py` — Quick Provider Check

```powershell
uv run python status_providers.py
```

---

## Environment Variables

Required in `.env`:

```bash
# Database (required)
NEON_DATABASE_URL=postgresql://...

# Providers (at least one required)
GEMINI_API_KEY=...
GEMINI_FALLBACK_API_KEY=...
OPENROUTER_API_KEY=...
OPENAI_API_KEY=...

# Optional
FEDS_APP_DB_PASSWORD=...          # Restricted runtime role
FEDS_APPROVER_DB_PASSWORD=...     # Approver role
FEDS_ALLOWED_OPERATORS=alice,bob  # Who can approve
FEDS_SLACK_WEBHOOK_URL=...        # Slack notifications
FEDS_CONSOLE_URL=https://...      # Approval console URL
```

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Failure (validation, provider, runtime) |
| `2` | Usage error / incomplete (quota) |

---

## Tips

- **Offline development**: All tests run without API keys via `uv run python run_tests.py`
- **Live testing**: Set `$env:RUN_LIVE_TESTS = "1"` for provider calls
- **Quota management**: Router auto-rotates on 429/402; check `status_providers.py`
- **Cost tracking**: Every turn logs `chat.turn` to `capability_invocations`; use `replay.py --costs`