# FEDS CLI

An opencode-style terminal UI for the FEDS worker (`worker.py`). It is an
interface, not a second agent: the worker is imported in-process and its
`run_task` / `resume_session` / `decide_run` entry points are called directly.
Nothing is spawned.

## Run it

From the repository root (the worker resolves skills and `SYSTEM_PROMPT.md`
relative to its own file, and the DB config comes from `.env`):

```powershell
cd E:\agency-agents\frontend-developer-FTE
uv sync --extra cli
uv run feds
```

Optional arguments:

```powershell
uv run feds <session-id>          # open a saved session
uv run feds --max-cost 25         # recorded for resumed turns
```

Install as a global command:

```powershell
uv tool install -e . --force
feds
```

## Headless check (no TTY needed)

The TUI cannot be inspected from a script, so the same App is driven through
Textual's Pilot:

```powershell
uv run python -m feds_cli.smoke          # layout, commands, modals (no model quota)
uv run python -m feds_cli.smoke --live   # adds one real worker turn
```

## Layout

```
+--------------------------------------------------------------+
|  #####  #####  ####   ####        ASCII (or block) logo      |
|    Frontend Engineering Digital Specialist                    |
|    By SangLabs                                                |
+--------------------------------------+-----------------------+
|  transcript                          |  CONTEXT              |
|  You / FEDS messages                 |  session, tokens,     |
|                                      |  skills, MCP,         |
|  +--------------------------------+    |  provider chain       |
|  | prompt (Enter sends)           |    |                       |
|  +--------------------------------+    |                       |
+--------------------------------------+-----------------------+
| status bar: version · session · model · ready/working        |
| footer: key bindings                                          |
+--------------------------------------------------------------+
```

The banner uses ANSI-shadow block letters when the terminal encoding is UTF-8
and pure ASCII otherwise, so a legacy Windows console never renders `?`.
Override with `FEDS_CLI_UNICODE=1` / `FEDS_CLI_UNICODE=0`.

## Keys

| Key | Action |
|---|---|
| `Enter` | Send |
| `Ctrl+J` | Newline (`Shift+Enter` where the terminal reports it) |
| `Ctrl+L` | Clear transcript |
| `Ctrl+P` | Session picker |
| `Ctrl+K` | Toggle context panel |
| `Ctrl+Up` / `Ctrl+Down` | Prompt history |
| `F1` | Help |
| `Ctrl+C` | Save and quit |

`Up`/`Down` stay native text navigation inside the prompt; history is on
`Ctrl+Up`/`Ctrl+Down` because a global `Up` binding would break cursor movement.

## Commands

`/help`, `/clear`, `/reset`, `/sessions`, `/whoami`, `/version`, `/model`,
`/skills`, `/mcp`, `/cost`, `/replay [n]`, `/doctor`, `/compact`, `/update`,
`/exit`.

Real data is used where it exists:

- `/skills` reads `.claude/skills/*/SKILL.md`.
- `/mcp` lists the tools registered on the workspace MCP server.
- `/cost` sums `capability_invocations` rows (`chat.turn`) for the session and
  reports `NULL` cost as unpriced rather than zero.
- `/doctor` checks config, provider chain, MCP import, session dir writability
  and repo root.

## How a turn works

1. `feds_cli.main.FedsCLI` appends the user message and saves the session.
2. `worker_bridge.WorkerBridge.run_turn` calls `worker.run_task(text,
   conversation_id=<session id>)` in a Textual worker, so the UI stays live.
3. The worker emits its answer through `worker._say`. The bridge sets
   `worker._CAPTURE`, so output is collected instead of printed into the TUI —
   the worker keeps its normal `uv run python worker.py` behaviour.
4. The bridge also restores real `stdout`/`stderr`/`stdin` for the duration of
   a turn: Textual redirects them to capture objects whose `fileno()` is `-1`,
   and the MCP server is launched over stdio, which needs a real descriptor.
5. Tokens and cost are read back from the DB for the context panel.

The worker is preloaded in `FedsCLI.__init__`, before Textual takes over the
streams, because `mcp.client.stdio` binds `errlog=sys.stderr` at import time.

## Sessions

Stored as JSON, one file per session:

- `.feds/sessions/` when started inside a git checkout (gitignored), else
- `platformdirs.user_data_dir("feds", "feds-cli")/sessions`.

The CLI session id is passed to the worker as its conversation id, so
`uv run python replay.py <session-id>` and `worker.py --resume <session-id>`
work on the same conversation the CLI recorded.

## Known gaps

- No token-by-token streaming: the worker prints its final answer, so a turn
  appears when it completes. Real streaming needs an `on_token` hook in
  `worker.run_task`.
- `/compact` and `/update` report the plan instead of acting.
- `/model` shows the chain; switching still means editing `.env`
  (`GEMINI_CHAT_MODEL`, `OLLAMA_CHAT_MODEL`, …) and restarting.
- The context panel does not yet show the live cooldown state of the provider
  router (it shows the configured order and the last model used).
- `skills_loaded` is not yet populated from `load_skill` calls.
