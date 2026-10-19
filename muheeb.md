# Muheeb's Work — Feature Ledger

Features assigned to Muheeb (co-founder). None of these are built yet; each
entry defines what to build, where it hooks into the existing system, and how
we will know it works. Sanghaar's queue is `sanghaar.md` — the two files do
not overlap on purpose. The roadmap research behind items 6-10 (G2, Gartner,
Anthropic, WebAIM — accessed 2026-10-19) and the work taken from
`FEDS Market Rating and Startup Gaps for SangLabs.md` (items 11-13) are
recorded there, including the coverage map showing every report gap's owner;
those eight entries keep the two queues at equal weight.

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

## 6. Agent registry and kill switch — OPEN

G2's 2026 AI Agents Report calls unmanaged agents "the new shadow IT": 38%
of organizations with agents in production run more than 100 of them, 47%
manage them informally, and buyers now expect every agent to carry an
automatic record — owner, workflow, identity, permissions, connected
systems, activity, cost — plus a one-click pause or revoke. Build the
control plane:

- An `agent_registry` table created in `setup_neon.py` (no runtime DDL):
  name, owner, purpose, permission scope, connected systems, status
  (active/paused), created, last activity, cost rollup — kept truthful by
  worker/MCP writes and reconcilable against `audit_log`.
- Console views on top of item 1's approval console: the registry, each
  agent's activity trail (the same reconstruction `replay.py` does), and a
  **Pause** button that writes status under the operator's name.
- The enforcement hook, written against the same code path the worker
  already uses: a check before any model call and before any write tool, so
  a paused agent's next turn stops with an audited row and zero model spend,
  and a revoked tool returns a clean refusal to the model instead of
  vanishing silently.

**Done when:** pausing from the console halts the next turn before a single
model call (offline test), revoking `publish_task` makes it refuse with an
audit row, and the registry's activity for a period matches `replay.py`.

---

## 7. Operations dashboard: observability, alerts, and the proof page — OPEN

The audit trail is thorough and invisible: no view reads it, nothing alerts,
nothing streams — while 52% of buyers require human quality review before
production and 77% re-evaluate agent performance at least monthly (G2 2026).
Build the surface that answers them:

- **Spans.** Emit OpenTelemetry GenAI spans from the worker/MCP write sites
  using `gen_ai.*` attributes (model, operation, token counts, tool name,
  latency), sourced from the same rows `capability_invocations` records,
  with an env-gated OTLP exporter (off by default; SQL replay stays the
  source of truth).
- **Dashboard.** Live views over those spans plus `audit_log`: error rate,
  p95 latency, cost per hour, guardrail-trip rate, approval wait time —
  with threshold alerts routed through item 5's notifier.
- **Proof page.** Render each task's verification evidence rows — measured
  LCP/INP/CLS, failing rule ids, screenshot artifact, verifier version —
  which `sanghaar.md` item 7 persists. This is the artifact a buyer asks
  for before allowing a production publish.

**Done when:** one live turn appears in the dashboard with model and token
attributes, an alert fires on a synthetic threshold breach, opening a
completed task shows its measured Core Web Vitals and accessibility results,
and no credential or PII leaves the process (the exporter's payload checked
offline).

---

## 8. Oversight and ROI report — OPEN

The market's biggest measured failure is the "distrust tax": 45% of buyers
say oversight consumes more than a quarter of the productivity gains they
expected, 46% report higher-than-expected operating costs, 31% spend 6+
hours a week bot-sitting (G2 2026), and Gartner forecasts 40% of agent
projects canceled by 2027 over runaway cost and unclear ROI. FEDS records
every ingredient; nobody does the arithmetic. Build:

- Per-outcome metrics computed from existing rows: wall-clock duration,
  model cost (`cost_cents` — NULL excluded honestly, never counted as zero),
  human minutes from `approval_decided` / `record_review` timestamps,
  verification result, retries.
- Derived ratios: net cycle time, oversight ratio (human minutes ÷ estimated
  human baseline), cost per approved outcome.
- A queryable surface (CLI or console endpoint) that renders a workspace
  report — the "are we ahead or behind" answer a co-founder reads weekly.

**Done when:** a completed task reports cost, human review minutes and the
oversight ratio from real rows; tasks with `cost_cents IS NULL` are excluded
from cost totals rather than counted as zero; and every number reproduces
from `audit_log` alone.

---

## 9. Compliance evidence pack and memory deletion request — OPEN

2026 moved agent security from optional toward formal requirement (NIST AI
agent standards initiative; EU AI Act obligations), and memory privacy —
retention, inspection, deletion — is a named open problem in the 2026
memory literature. Two buyer-facing artifacts:

- **Evidence pack:** one command that exports audit trail, approval records,
  operator authorization policy, permission scope, eval results and
  verification history as a machine-readable bundle plus a human-readable
  report — what an enterprise reviewer asks for in the first meeting.
- **Deletion request:** a console flow that honors an erasure request on a
  private memory as an auditable tombstone (content replaced with a
  redaction marker, original hash retained, request and actor recorded,
  retrieval excludes tombstones), preserving the append-only trigger's
  integrity — the shared layer must still refuse a raw UPDATE/DELETE
  afterwards.

**Done when:** the bundle generates from a fresh database, a deletion
request is honored end-to-end (content unreadable, tombstone audited), and
the append-only trigger still refuses a raw UPDATE/DELETE after the request
was served.

---

## 10. Parallel runs and scheduled automations — OPEN

Cursor cloud agents and Claude Cowork run fleets in parallel and on
schedules; unattended work ("works when you don't") is on the market's
must-have list, and FEDS today is one process handling one turn at a time.
Build the automations feature:

- N concurrent runs with distinct conversation ids, each with its own
  guardrail scope, approval parking and per-run budget — sharing the
  quota-aware provider router that already exists.
- A scheduler that starts a run at a given time or cron expression, gated by
  the stopping conditions `sanghaar.md` item 9 owns (max iterations, max
  cost, wall clock).
- Idempotency and per-run locking so two runs cannot touch the same task row
  (extend the existing advisory-lock pattern), and a console page listing
  scheduled and running jobs with their budgets.

**Done when:** three runs execute concurrently without audit cross-talk
(`replay.py` shows three clean trails), a scheduled run fires with no human
present, and a budget stop halts it with an audited reason.

---

## 11. Pick the wedge and restate the product — OPEN

`FEDS Market Rating and Startup Gaps for SangLabs.md` scores product
differentiation 5/10 — Cursor, Claude Code, v0, Lovable, Bolt and Devin
already own "general frontend coding", and nothing in the repo claims FEDS
writes better UI than they do. Its What to do 1 is to stop competing there:

- **Decide and record the wedge:** "frontend performance and accessibility
  fixes, audited and approved by a human." Write it into `README.md` and
  every product-facing description; general frontend coding is explicitly
  not the pitch.
- **A competitive note** against the six named tools: what each does, what
  FEDS does not claim, and where governance + verified outcomes (the areas
  they handle thinly) is the whole story.
- **Turn honesty into the pitch** (What to do 5): publish the evaluation
  posture — single-sample labels, exit codes, no rounded-up runs — as
  customer-facing material, plus what trends.vc calls "outcome
  verification audits": every change ships with its before/after evidence
  (this file item 7's proof page, measured by `sanghaar.md` item 12).

**Done when:** the README opens with the wedge, every marketing claim maps
to a number or artifact that exists in the repo, and no claim asserts
stability the evals have not measured.

---

## 12. Pilot program — 3–5 free pilots — OPEN

What to do 2 in the market report: prove the wedge with real customers
before widening. Market proof is rated 2/10 — the report's lowest score —
and no amount of engineering closes it; only pilots do:

- Recruit 3–5 agencies or startups and run their real frontend tasks
  through FEDS, capturing a before/after Core Web Vitals and accessibility
  table per task from `sanghaar.md` item 12's stored measurements.
- Structured notes per pilot: oversight hours spent (feeds the ROI report,
  item 8), willingness to pay under outcome pricing (item 13), and the
  report's explicitly-unsourced regional/SMB hypothesis — Urdu and
  right-to-left layouts, local payment integrations, price sensitivity —
  tested in conversation, not built blind.
- The same evidence discipline as `eval_results.md`: numbers only from runs
  that happened, failures written down as failures.

**Done when:** three pilots are complete, each with a before/after table and
a candid note on what did not work, and the notes state plainly which wedge
hypotheses were confirmed and which were not.

---

## 13. Outcome-based pricing metering — OPEN

Gap 4 of the market report: trends.vc expects outcome-based pricing to
become dominant (roughly $3 per resolution against a $150,000/year flat
contract), and G2 2026 finds only 9% of buyers consider per-seat pricing
fairest. For FEDS the proposed unit is the **merged change that stays inside
a performance and accessibility budget**:

- Metering over existing rows: a billable outcome is a published change
  whose verification passed **and** whose approval is recorded — pricing
  rides the same gates as publication, so nothing can be billed without
  them, and `audit_log` remains the source of truth.
- Budget coupling: the "inside budget" test reads the verifier's numbers
  (LCP/INP/CLS, violation count) against the thresholds in
  `SYSTEM_PROMPT.md` — a change that shipped but broke the budget does not
  count as an outcome.
- A price display in the console (unit, month-to-date, evidence links per
  line) feeding the ROI report (item 8), so cost and value are readable
  side by side.

**Done when:** a completed task either counts as a billable outcome with
its evidence links or does not with the reason recorded, rows with unknown
cost never enter price math, and the month's meter reproduces from
`audit_log` alone.

---

## Suggested order

**Core five (original):**

1. **Approval console** (item 1) — unblocks the human-in-the-loop path
   everyone else depends on.
2. **Notifications** (item 5) — small, and the console links from it.
3. **Identity** (item 2) — prerequisite for multi-user memory being real.
4. **CI** (item 4) — cheap insurance for every later change.
5. **Budgets** (item 3) — once live turns generate enough rollup data to
   set realistic numbers.

**Roadmap five (items 6-10, dependency-ordered):**

6. **Registry + kill switch** (item 6) — builds on the console from item 1;
   it is the governance gate enterprises now ask for first.
7. **Dashboard + proof page** (item 7) — needs `sanghaar.md` item 7's
   verifier rows for the proof view; the spans and dashboard stand alone
   before that.
8. **ROI report** (item 8) — needs enough completed tasks for ratios to
   mean anything; the report is only honest once the rows exist.
9. **Compliance pack** (item 9) — lands before any real enterprise pilot;
   pure export plus a deletion flow, no new architecture.
10. **Parallel + scheduled runs** (item 10) — last, because it depends on
    `sanghaar.md` item 9's stopping conditions and item 6's kill switch to
    be safe unattended.

**Market-report three (items 11-13, from `FEDS Market Rating and Startup
Gaps for SangLabs.md`):**

11. **The wedge** (item 11) — decided first of everything: it directs the
    roadmap below it, the copy, and what the pilots ask.
12. **Pilots** (item 12) — after `sanghaar.md` items 12 (before/after
    measurements), 6 (container actually run) and 2 (off the free tier);
    three pilots is the market-proof score closing.
13. **Outcome pricing** (item 13) — last, once pilots supply real
    willingness-to-pay and budgets (item 3) plus the ROI report (item 8)
    give the numbers to price against.
