# Contributing to FEDS

Thanks for helping. By participating you agree to the
[Code of Conduct](CODE_OF_CONDUCT.md).

**Read [`AGENTS.md`](AGENTS.md) first** — it is the working contract for this
repo and is written so both humans and coding agents can act on it. Its
`Start here` section gives the read order and the definition of done; its
`Open work` section lists what is missing right now with file pointers and
acceptance criteria.

## Set up the full stack locally

FEDS is one Python repo (`uv`, no build step) plus a hosted Postgres. There
is no local database container and nothing to compile.

| You want to… | What you need |
|---|---|
| Read code and run the offline gate | `uv sync` only (no secrets) |
| Run an agent turn or live tests | `.env` with at least one chat-provider key |
| Touch schema, memory, or MCP tools | `NEON_DATABASE_URL` (owner role) + `FEDS_APP_DB_PASSWORD` (runtime role) |
| Work on the terminal UI | `uv sync --extra cli` |

```bash
git clone https://github.com/imamsanghaarc/feds.git
cd feds
uv sync --extra cli
cp .env.example .env        # fill it in; .env is gitignored, real env vars win
uv run python setup_neon.py # idempotent schema — re-run after schema edits
uv run python run_tests.py  # offline gate
```

- **Database:** the schema lives on a Neon Postgres branch (pgvector). All
  DDL ships in `setup_neon.py`; the runtime role cannot run DDL, and an
  offline test fails if `worker.py` or `server.py` contains a runtime
  `CREATE`/`ALTER`/`DROP`.
- **Containers:** `Dockerfile` and `compose.yml` exist (worker + an optional
  HTTP MCP service on `127.0.0.1:8001`) but have **never been executed** —
  Docker was unavailable in the development environment. If you have Docker,
  making `docker compose up` work end to end is a welcome contribution
  (`area/devops`).

## Branch naming

`<type>/<area>/<short-name>`:

```text
feat/cli/tab-completion
fix/database/vector-merge
docs/readme-provider-table
test/eval/stable-rate-rerun
chore/devops/ci-smoke-job
```

- Types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`.
- Areas match the issue labels: `backend`, `database`, `devops`, `security`,
  `docs`, `cli`, `eval`.
- Lowercase-with-dashes for the short name. Link the issue in the PR body
  (`Closes #12`).

## Tests by layer

| Layer | Command | Cost |
|---|---|---|
| Everything (offline gate) | `uv run python run_tests.py` | none — before every push |
| TUI layout, commands, modals | `uv run python -m feds_cli.smoke` | none, no TTY needed |
| TUI + one real turn | `uv run python -m feds_cli.smoke --live` | one model turn |
| DB rules without quota | `uv run python smoke_memory_schema.py` then `smoke_app_role.py` | none (DB only, self-cleaning) |
| MCP tools outside the loop | `uv run python smoke_mcp.py` | none (DB/embeddings) |
| Provider fallback (live) | `RUN_LIVE_TESTS=1 uv run python run_tests.py` | model quota |
| Credential freshness | `uv run python test_config.py --strict` | none (auth probes) |

Before you push:

- Never commit credentials: `.env` is gitignored and `test_config.py` carries
  a planted-secret scanner that runs inside the gate.
- Live tests are opt-in (`RUN_LIVE_TESTS=1`) and quota-bound. Exit code 2
  means "quota skipped cases" — never report it as a pass, never fabricate
  numbers for `eval_results.md`.
- Commits use the identity `imam sanghaar <imamsanghaarc@gmail.com>`; confirm
  a push with `git ls-remote origin HEAD` (git errors on PowerShell print as
  noise).

## Issue labels

| Label | Use it for |
|---|---|
| `area/backend` | agent loop, MCP tools, provider routing, console API |
| `area/database` | schema (`setup_neon.py`), queries, pgvector, indexing |
| `area/devops` | Docker, GitHub Actions, deployment, monitoring |
| `area/security` | guardrails, dependency audits, auth hardening, secrets |
| `area/docs` | README, ADRs, API and architecture docs |
| `area/cli` | the terminal UI (`feds_cli/`) |
| `area/eval` | evaluation harnesses, scoring, honest evidence |
| `good first issue` | small and well-scoped, no deep context needed |
| `help wanted` | maintainer is happy to hand this over |

Combine one `area/*` with `good first issue`, and write the "Done when"
acceptance criterion in the issue body — the `Open work` table in
`AGENTS.md` is the model to copy.

## Extending FEDS

- **New skill** (the most common contribution): copy
  [`templates/skill/SKILL.md`](templates/skill/SKILL.md) into
  `.claude/skills/<name>/` — no registration step.
- **New MCP tool or standalone integration:** follow
  [`docs/extending-feds.md`](docs/extending-feds.md) for the rules each layer
  must keep (scoped predicates, approval gates, dry-run defaults).

## Scope of changes

- **Good first issues:** the `feds_cli` (TUI) rows in the `Open work` table
  of `AGENTS.md`.
- **Larger efforts** (durable execution, eval evidence, KSoR/DSoR) live in
  `sanghaar.md` with priorities and estimates — read the item before starting.
  [`ROADMAP.md`](ROADMAP.md) is the curated view of the same queue.
- The non-negotiable product rules at the top of `AGENTS.md` (approval gate,
  memory isolation SQL, no secrets in source, no DeepSeek, no web-search
  tool) are not open for reinterpretation.

## License

Contributions are distributed under the repository's [MIT License](LICENSE).
By opening a pull request you agree to license your work under the same terms.
