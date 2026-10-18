# Muheeb's Work — Feature Ledger

Features assigned to Muheeb (co-founder). None of these are built yet; each
entry defines what to build, where it hooks into the existing system, and how
we will know it works. Sanghaar's queue is `missing.md` — the two files do
not overlap on purpose.

Legend: **OPEN** = not built yet. **DEFERRED** = paused by agreement.

---

## 1. Approval console (web UI) — OPEN

FEDS parks approval-gated runs (`publish_task`, `promote_memory`) and today
they are resumed only from the CLI (`worker.py --decide <run_id> approve
[operator]`). Build the human-facing console:

- Queue of parked runs from `run_states`, with the conversation trail
  rendered from `audit_log` (the same reconstruction `replay.py` does).
- Approve / reject with the operator's real name — it must flow into the
  existing `decide_run(run_id, decision, operator)` so `run_states.operator`
  and the `approval_decided` audit row stay the single source of truth.
- Read-only views stay ungated (reads run free); only the decision button
  writes.

**Done when:** approving from the console resumes the parked run through the
same code path as the CLI, the operator appears in the trail, and a second
console request for the same run is refused while the first is deciding
(the per-conversation advisory lock already in `decide_run`).

---

## 2. Team identity and sessions — OPEN

Right now the MCP server sees one process-level identity
(`FRONTEND_USER_ID`, defaulting to `unconfigured-user`), so memory isolation
is proven only between simulated users in one process. Build:

- Real user accounts with login and a stable user id.
- The worker injects that id per request (replacing the env-var identity),
  so `save_memory` / `list_memories` / `delete_memory` isolate per request,
  not per process.

**Done when:** two logged-in users cannot read each other's private memories
under concurrent use — the same isolation `smoke_memory.py` proves for two
simulated ids, now proven across real sessions.

---

## 3. Budgets and cost alerts — OPEN

Token and cost rollups now land on every `chat.turn` row in
`capability_invocations` (`cost_cents`, labelled
`cost_basis: "list_price_estimate"`). Build the spending controls:

- Monthly budget per workspace (and later per user), computed from those
  rollups — the same aggregation `replay.py --costs` exposes.
- Warning threshold and hard cap; a hard cap must block new turns through
  the guardrail path rather than silently degrading quality.

**Done when:** a budget set below the month's actual spend is reported
correctly, and rows with unknown pricing (`cost_cents IS NULL`) are excluded
from totals — never counted as zero.

---

## 4. CI pipeline — OPEN

No automated gate exists; suites are run by hand. Add GitHub Actions:

- On every push: `uv run python run_tests.py` (3 suites, must stay green)
  plus the secret scanner and skill-tree validation that ship in the suite.
- Scheduled, resumable live evals (`eval_triggers.py`, `eval_set.md`)
  only when provider secrets are present — skipped, not failed, when they
  are not.

**Done when:** a failing offline suite turns the PR red, and a scheduled
live run records PARTIAL honestly (exit code 2) instead of being reported
as a pass.

---

## 5. Approval pause notifications — OPEN

When a run parks waiting for approval, nobody finds out unless they poll.
Build:

- A notifier (Slack webhook or email) fired when a run enters the parked
  state, carrying the run id, what is being approved, and the exact decide
  command to run.
- The console from item 1 linked from the message.

**Done when:** parking a run produces exactly one notification, a resumed
run produces none, and a notification failure never breaks the pause
itself (same best-effort rule the metrics writes follow).

---

## Suggested order

1. **Approval console** (item 1) — unblocks the human-in-the-loop path
   everyone else depends on.
2. **Notifications** (item 5) — small, and the console links from it.
3. **Identity** (item 2) — prerequisite for multi-user memory being real.
4. **CI** (item 4) — cheap insurance for every later change.
5. **Budgets** (item 3) — once live turns generate enough rollup data to
   set realistic numbers.
