# Contributing to FEDS

Thanks for helping. By participating you agree to the
[Code of Conduct](CODE_OF_CONDUCT.md).

**Read [`AGENTS.md`](AGENTS.md) first** — it is the working contract for this
repo and is written so both humans and coding agents can act on it. Its `Start here` section gives the read order and the
definition of done; its `Open work` section lists what is missing right now
with file pointers and acceptance criteria.

## Setup

```bash
uv sync                      # add --extra cli to work on the terminal TUI
cp .env.example .env         # then fill in credentials
uv run python setup_neon.py  # idempotent schema (needs NEON_DATABASE_URL)
```

## Before you push

```bash
uv run python run_tests.py                        # offline gate — must be green
uv run python -m feds_cli.smoke                   # if you touched feds_cli/
```

- Never commit credentials: `.env` is gitignored and `test_config.py` carries
  a planted-secret scanner that runs in the gate.
- Live tests are opt-in (`RUN_LIVE_TESTS=1`) and quota-bound. Exit code 2
  means "quota skipped cases" — never report it as a pass, never fabricate
  numbers for `eval_results.md`.
- Commits use the identity `imam sanghaar <imamsanghaarc@gmail.com>`; confirm
  a push with `git ls-remote origin HEAD` (git errors on PowerShell print as
  noise).

## Scope of changes

- **Good first issues:** the `feds_cli` (TUI) rows in the `Open work` table
  of `AGENTS.md`.
- **Larger efforts** (durable execution, eval evidence, KSoR/DSoR) live in
  `sanghaar.md` with priorities and estimates — read the item before starting.
- The non-negotiable product rules at the top of `AGENTS.md` (approval gate,
  memory isolation SQL, no secrets in source, no DeepSeek, no web-search
  tool) are not open for reinterpretation.

## License

Not yet chosen — see the `LICENSE` item in `AGENTS.md` → `Open work`. Don't
assume one.
