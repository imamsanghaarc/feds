# Extending FEDS

Three extension points, ordered by how often they get used. Everything here
is guarded by the offline gate — run `uv run python run_tests.py` before you
push.

## 1. A new skill (the common contribution)

Skills are discovered, not registered. `worker._skill_index()` globs
`.claude/skills/*/SKILL.md` and puts `name: description` into the system
prompt; the model then calls `load_skill` for the one task it actually needs.

1. Copy [`templates/skill/SKILL.md`](../templates/skill/SKILL.md) to
   `.claude/skills/<your-skill-name>/SKILL.md`.
2. Directory name == frontmatter `name` == the argument `load_skill` takes
   (kebab-case).
3. Write the description as triggers: `Use when …` with the exact phrases a
   user might say, and a `Do NOT use for …` line naming the neighbouring
   skill it could be confused with. The index carries only name and
   description — that sentence is the model's entire decision input.
4. Put long material in `references/*.md` beside `SKILL.md`. `load_skill`
   appends those files automatically when the skill is loaded, so they cost
   nothing until a task needs them. Never inline the corpus.
5. Keep advice aligned to Core Web Vitals (LCP ≤ 2.5s, INP ≤ 200ms,
   CLS ≤ 0.1 at p75).
6. Prove it: `uv run python run_tests.py`. Optionally add trigger coverage
   the way `eval_set.md` / `eval_triggers.py` do (quota-bound, opt-in).

Rules that exist for a reason: a missing or malformed skill must degrade
gracefully and never crash a turn, and only `.claude/skills/` (with `skills/`
as fallback) counts — a test pins both locations.

## 2. A new MCP tool (the only path to the database)

`frontend_workspace_mcp/server.py` is the single runtime access path to
Neon; the worker itself never writes SQL.

- Register an `async def` with the `@mcp.tool()` decorator and copy an
  existing tool (e.g. `lookup_task`) for its error shape and the
  `_invocation` / `_audit` helpers, so the call is metered like the rest.
- **Scoped predicates only.** Private memory stays
  `scope = 'private' AND owner = $2` — never "simplify" those away. No broad
  SQL, no DDL: the runtime role cannot run it, and an offline test fails if
  `worker.py` or `server.py` contains `CREATE`/`ALTER`/`DROP`.
- **Approval gates:** writes that reach shared state (`publish_task`,
  `promote_memory`) require a recorded human approval. If you add another
  such write, gate it in `worker._mcp_server`, and keep `feds_app` unable to
  write the `approvals` table — the DB is the authority, not the code.
- New tables belong in `setup_neon.py` (idempotent), never in runtime code.
- Prove it without spending quota: `uv run python smoke_mcp.py`,
  `smoke_app_role.py`, `smoke_memory.py`.

## 3. A standalone integration (webhooks, notifications, dashboards, gateways)

The pattern set by `approval_notifier.py`, `budget_manager.py`, and
`verifier.py`:

- One top-level script with an argparse CLI; read configuration only through
  `config.py` (it loads the gitignored `.env`; real environment variables
  always win).
- Default to `--dry-run` for anything that writes, be idempotent on re-run,
  and clean up any test artifacts you create.
- Honest exit codes: `0` success, `1` failure, `2` usage error or
  quota-skipped — never report 2 as a pass.
- No credentials in code: the planted-secret scanner in `test_config.py`
  scans every committed `.py`, `.md`, and `.yml`.
- Third-party services (Slack, email, payment gateways, webhooks) stay in
  their own scripts like `approval_notifier.py` — keep them out of
  `worker.py` and `frontend_workspace_mcp/` so the trust boundary stays
  thin.

## Choosing what to extend

| You want to… | Extend |
|---|---|
| Teach FEDS a method or domain | a skill (§1) |
| Let the agent read/write workspace data | an MCP tool (§2) |
| React to events or talk to a third party | a standalone integration (§3) |
| Change how FEDS answers by default | `SYSTEM_PROMPT.md` — which invalidates the eval numbers; re-run them |
