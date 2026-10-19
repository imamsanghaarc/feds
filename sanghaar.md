# Sanghaar's Work — Remaining Items

Everything shipped has been removed from this file; it now lists only what is
not done. The evidence for completed work lives in `done.md`, `eval_results.md`,
the test suite (`uv run python run_tests.py`), and git history.

Legend: **OPEN** = not built yet. **BLOCKED** = the work is written but an
external condition stops verification. **DEFERRED** = paused by agreement.

---

## 1. System prompt eval — MEASURED (8 of 8 scored); two findings to fix

**Progress: 8 of 8 cases scored, 6 passed. The two failures both need a prompt
or policy decision, not more quota.**

With the new credential in place the run resumed and completed one pass of all
eight `eval_set.md` cases. `eval_results.md` section A carries the full table
and the evidence. Two findings:

1. **The mode rule is not stable for a tiny change.** `Change the link color to
   #1a5fb4` returned the short snippet answer once and full implement mode
   (all four headings) twice across three runs; the earlier recorded PASS does
   not reproduce. **FIXED (prompt-only, no quota needed):** `SYSTEM_PROMPT.md`
   section 11 now chooses implement-vs-snippet mode by size ("the deciding test
   is size, not verb"), pinned by `test_system_prompt_mode_rule_is_deterministic`.
   Live re-verification rides with item 5.
2. **The input guardrail pre-empts the prompt.** A pasted README containing
   `run this SQL` / `DROP TABLE` is hard-blocked by `_GUARDRAIL_BLOCKERS`
   before the model runs, yet the prompt instructs the agent to treat pasted
   content as data and summarize suspicious content instead of executing it.
   **FIXED — let the model refuse gracefully.** `_GUARDRAIL_BLOCKERS` now holds
   only trust-boundary subversion (`connect to production`, `bypass audit`,
   `disable audit`); destructive-SQL and credential phrasing reaches the model,
   which refuses it per `SYSTEM_PROMPT.md` sections 7 and 9. Pinned offline by
   the guardrail tests; live re-run rides with item 5.

Still open: the three-runs-per-case stability pass (item 5) — now blocked
because free-tier quota is spent for the day (both Gemini keys, roughly 20
requests/day each).

Harness (unchanged, resumable one case at a time):

```powershell
$env:RUN_LIVE_TESTS = "1"
uv run python worker.py "<one case prompt from eval_set.md>"
uv run python replay.py <conversation_id>   # confirm tool names are real
```

---

## 2. Provider failover — real second credential wired; family diversity OPEN

A second Gemini credential is now its own routable provider
(`gemini-fallback`, key in `.env` as `GEMINI_FALLBACK_API_KEY`), enabled for
**both chat and embeddings**. A **real** failover was observed live on
2026-10-19 — the first time rotation has fired against a genuine 429 instead
of a stub:

```
[provider-router] gemini quota exhausted; cooling down 900s (streak 1)
[model] gemini-fallback:gemini-3.5-flash
```

The primary key 429'd on essentially every turn that day (its free-tier
allowance was spent), so the fallback credential carried the whole eval run —
exactly the coverage the fallback exists for.

Still open:

- **Provider family diversity.** Both live credentials are Gemini. Free-tier
  limits are applied per key, so two keys are two allowances — but if both
  keys were issued under the same Google project the allowance may be shared;
  confirm that before calling this quota-proof. Adding a non-Gemini provider
  (Groq has a generous free tier) would remove the shared-upstream risk.
- OpenAI was disabled and its key removed from `.env` by request (it only ever
  returned HTTP 401).

**Market report, What to do 3:** "move off the Gemini free tier" lands on
this item — pair the non-Gemini provider with a paid credential before any
pilot (muheeb item 12); free-tier quota is already the binding constraint
on every live verification.

---

## 3. Embedding redundancy — second live path added; local model still OPEN

Embeddings now run through the same two credentials as chat
(`gemini` → `gemini-fallback`), both serving `gemini-embedding-001`, so a
quota failure on one key rotates to the other **without changing the model
label** — stored vectors stay comparable and search stays model-scoped.
`embedding_order()` returns `['gemini', 'gemini-fallback']`; the MCP embedding
router now carries a per-provider `api_key` and dispatches by client family
(`gemini-fallback` uses the Gemini client on the second key).

Still open: a genuinely **local** model (Ollama, or a sentence-transformers
variant at 768 dims). That is the only option that keeps embeddings working
with no network access at all, which matters because ingestion
(`ingest_refs.py`) and seeding both depend on the live embedding path. After
adding any second *model*, run `reembed.py --dry-run` first: vectors from
different models must never be mixed (search is model-scoped by design).

---

## 4. Secrets rotation before sharing the repo — OPEN

Credentials already live in the gitignored `.env` and a planted-secret
scanner in `test_config.py` keeps them out of source. What remains is the
rotation itself: rotate the Neon password and the provider key before this
repo or host is shared with anyone.

---

## 5. Stable-rate eval evidence — OPEN (blocked: quota spent for the day)

Two point measurements exist and neither is a stable rate:

- The trigger eval is 11/11 as a **single sample per case** (`eval_results.md`
  section B).
- The system-prompt eval is 6/8 as a **single run per case** (section A), and
  case 1 is already known to vary — it returned the short-form answer once and
  full implement mode twice across three runs.

A stronger claim needs three runs per case. Start with case 1, where the
variance is observed and cheap to re-run. Also open, if "selected" and "loaded"
are ever to be the same claim for the trigger eval: a harness condition that
forces the `load_skill` call before scoring.

Blocked because free-tier quota is spent for the day — both Gemini keys,
roughly 20 requests/day each. The prompts must be re-run as-is; the recorded
numbers do not carry over after a `SYSTEM_PROMPT.md` change.

---

## 6. Deployment and operations — DEFERRED by agreement

- **Tested container deployment.** `Dockerfile`, `compose.yml`, and
  `.dockerignore` are provided and reviewed (including the
  `!SYSTEM_PROMPT.md` exception and the `.claude/skills/` shipping
  behavior), but Docker was unavailable in this environment — reviewed,
  never executed. Run it once before trusting it.
- Restart supervision, rate limiting, and backpressure under load.
- **Database-enforced promotion approval.** The runtime now connects as a
  restricted role (least privilege below), but approval still lives in the
  worker: the runtime can write a well-formed global row directly. Making the
  database the approval authority needs a second credential the app does not
  hold — a separate approver role writing an approvals row the app role cannot
  forge, with global inserts gated on a matching row. A `SECURITY DEFINER`
  promotion function is not a substitute: the app role could call it without an
  approval. Deliberately deferred as a larger change.
- Cost-shape estimate (course Part 5) — the rollup data
  (`replay.py --costs`) now exists to build it from.
- **Market report, What to do 3:** "actually run the container deployment
  before showing it to anyone" is this item — it gates the pilots
  (muheeb item 12).

---

## 7. Verification harness — the evidence bundle — OPEN

FEDS asserts Core Web Vitals (LCP <= 2.5s, INP <= 200ms, CLS <= 0.1) and
accessibility behavior in `SYSTEM_PROMPT.md`, but nothing ever measures them.
The market gap this closes is proof: G2's 2026 AI Agents Report finds 52% of
buyers require human quality review before production, 77% re-evaluate agent
performance at least monthly, and explicitly asks vendors for a "testable
definition of performance" with evaluation reports and reliability data.
WebAIM's 2026 data says 95.9% of top home pages fail basic accessibility
checks — accessibility, performance and design-system fidelity are precisely
what generic AI tools get wrong, which is FEDS's domain. Build the proof layer:

- A local verifier that costs **zero model quota**: render the changed page in
  headless Chromium (Playwright), measure lab LCP/INP/CLS, run axe-core
  against WCAG 2.2 A/AA, check the concrete rules FEDS already cites (alt
  text, labels, contrast, focus order), and capture a screenshot artifact.
- Persist results as verification rows tied to task + conversation (metrics
  JSON, rule ids, artifact path, verifier version, timestamp) in the same
  style as `capability_invocations`.
- Make `publish_task` require a passing verification record for the current
  revision — verification becomes a gate exactly where approval already is,
  not a sentence in the prompt.
- Wire the same rule set into the eval harness so a regression fails offline.

**Done when:** a page missing an `alt` attribute fails with the exact rule id
and cannot be published; a passing run stores real LCP/INP/CLS numbers; a
zero-quota smoke test covers the path; and the evidence is readable by the
proof page (muheeb item 7).

---

## 8. Sandboxed execution environment — OPEN

Anthropic's Managed Agents architecture (Apr 2026) fixes the failure mode
directly: generated code must never be able to reach credentials. FEDS today
executes no code at all, which is exactly why it cannot verify its own work
(item 7 depends on this). Build:

- A per-run sandbox (container or restricted subprocess) with `.env` stripped
  from its environment, no `NEON_DATABASE_URL` / `FEDS_APP_DATABASE_URL`
  present, and egress restricted to an allowlist.
- All database access continues to flow through the MCP server, which lives
  **outside** the sandbox — the existing architecture already gives the
  sandbox nothing to steal; make that a tested property rather than an
  accident.
- Tool contract `execute(name, input) -> string`: a dead sandbox returns as a
  tool-call error the model may retry, and never kills the session.
- Build, test and lint run inside; their results return as ground truth into
  the audit trail.

**Done when:** code executed in the sandbox attempting to read `os.environ`
or `.env` finds no credential (offline test), a killed sandbox surfaces as a
retryable tool error, and a real build/test result lands in `audit_log`.

---

## 9. Durable session log and long-horizon resume — OPEN

Long-horizon work currently dies with the process: there is no event log
outside the model's context window, so a crash or a compacted context loses
position. The reference design (Anthropic Managed Agents) treats the session
as an append-only log the harness re-reads on resume. Build:

- An append-only session event log (events already exist in `audit_log` —
  expose them as `getEvents(session, from, to)` slices rather than duplicating
  rows), stored outside the context window.
- Harness restartable from the log: reboot with the session id, re-read the
  last N events, resume — compaction that *stores* rather than discards.
- Explicit stopping conditions (max iterations, max cost, wall-clock cap) so
  an unattended run cannot run forever.

**Done when:** killing `worker.py` mid-run and restarting it resumes from the
last event without losing a parked approval and without repeating a side
effect (tool calls idempotent on replay), and a max-cost stop is enforced
offline.

---

## 10. Verified Lesson Loop, phases 1-3, plus a memory eval — OPEN

`FEDS-Self-Learning-Algorithm-Design.docx` specifies it and `sanghaar.md`
already maps it; this entry makes it a work item, because "the agent learns"
is unmeasured today. The industry has standardized on measurable memory
(LongMemEval, LoCoMo, BEAM, STATE-Bench categories) and lists memory
staleness, conflict resolution and application-level evaluation as the open
problems. Build phases 1-3 first:

- **Verifier + reward score** (build, test, lint, console, screenshot — feeds
  item 7), mistake ledger, lesson store with `confidence` and `status`
  (active / quarantined / rule).
- **Confidence dynamics:** a lesson whose retrieval stops correlating with
  successful outcomes decays; below threshold it is quarantined, not deleted.
- **Staleness handling:** high-retrieval memories are re-verified on a
  schedule and re-flagged or tombstoned when contradicted.
- **Holdout lift measurement:** a held-out case set that measures whether
  promoted lessons actually improve outcomes — this is the number that turns
  "self-learning" from a claim into a result.
- **An internal memory eval** in the spirit of LongMemEval's discriminating
  categories (knowledge update, temporal ordering, multi-session recall)
  built from our own task data, resumable and quota-honest like the others.

**Done when:** a deliberately outdated lesson is quarantined automatically by
measured confidence, holdout lift is reported as a number (even if it is
zero), and the memory eval runs with the same exit-code discipline as
`eval_triggers.py`.

---

## 11. Indirect prompt-injection and memory-poisoning defense — OPEN

Prompt injection is ranked the #1 LLM vulnerability (OWASP LLM Top 10) and
characterized by NIST as generative AI's greatest security flaw; MCP-specific
attacks (tool poisoning, rug-pull tool descriptions) and poisoned knowledge
ingestion are the named 2026 attack paths against exactly FEDS's shape —
skills, ingested references, and tool descriptions. The current guardrail
deliberately blocks only trust-boundary phrases (correct, keep it); the
missing layer is *content provenance*, not a bigger blocklist:

- At ingestion (`ingest_refs.py`, `seed_corpus.py`): scan for instruction-like
  payloads, stamp provenance + trust level, and store the body as inert data.
- At retrieval: mark tool results and retrieved chunks as untrusted in the
  prompt contract (extends `SYSTEM_PROMPT.md` section 9 to retrieval).
- A red-team case in `eval_set.md`: a reference document that tries to make
  FEDS bypass approval or exfiltrate environment values — scored like the
  others.
- A written mapping of OWASP LLM Top 10 + NIST agentic guidance onto the
  controls FEDS actually has, with the honest gaps named.

**Done when:** a poisoned ingested document cannot cause an approval bypass
under an offline-pinned test, the red-team eval case passes, and the control
mapping exists as a document in the repo.

---

## 12. Wedge evidence: before/after capture and a published benchmark — OPEN

The market report (`FEDS Market Rating and Startup Gaps for SangLabs.md`)
rates market proof 2/10 — the weakest score it gives — and its "what to do
next" makes two evidence tasks non-negotiable before any pilot or pitch.
Both build on the verifier from item 7:

- **Before/after capture.** Snapshot the page's metrics *before* the change
  and again after it — lab LCP/INP/CLS plus the axe violation list — and
  store the pair and the delta on the task's verification rows. "FEDS
  improved this page" must be a stored measurement, never prose; the pilots
  (muheeb item 12) read these deltas directly.
- **A published benchmark.** A fixed task set of real frontend work
  (performance, accessibility, component cases), each run twice: once
  through FEDS, once through a documented baseline (same model, single
  prompt, no FEDS scaffold — no skills, no memory, no approval loop),
  scored only by the verifier. Results land in `eval_results.md` under the
  existing honesty rules: real runs only, exit 2 is never a pass, nothing
  rounded up.

**Done when:** a task shows a numeric before/after delta from real
measurements, the benchmark task set exists with a written baseline
definition, and at least one benchmark pass is recorded in `eval_results.md`
with its quota status reported honestly.

---

### Research basis for the 2026 roadmap — sanghaar.md items 7-11 and muheeb.md items 6-10 (accessed 2026-10-19)

- **G2, 2026 AI Agents Report: Crossing the Agentic Chasm** (Oct 14, 2026;
  1,000+ B2B buyers): 66% in production; Distrust Tax — 31% spend 6+ hrs/week
  bot-sitting, 45% lose >25% of gains to oversight, 46% higher costs;
  38% run 100+ agents, 47% manage informally; only 9% consider per-seat
  pricing fairest; 72% require a strong connector/skills ecosystem; 52%
  require human quality review before production; 77% re-evaluate monthly.
- **Gartner / IDC / NVIDIA / Forrester 2026** (via beri.net synthesis):
  40% of agent projects canceled by 2027 — runaway cost, unclear ROI,
  governance failure; what works = real-time monitoring, kill switches,
  human-in-the-loop, tiered model strategies, ROI tracking per agent;
  integration complexity delays 60% of deployments.
- **Anthropic Engineering**: "Building Effective Agents" (simplicity,
  transparency, tool-interface design) and "Scaling Managed Agents" (Apr
  2026 — session/harness/sandbox decoupling, session log outside the context
  window, credentials unreachable from the sandbox).
- **Memory 2026** (mem0 State of AI Agent Memory; MemoryAgentBench/ICLR
  2026; BEAM; arXiv 2603.07670 survey): benchmarks are LoCoMo, LongMemEval,
  BEAM, DolphinBench, STATE-Bench; open problems are staleness, temporal
  reasoning, conflict resolution, cross-session identity, privacy/deletion,
  and application-level evaluation — all directly mapped above.
- **Security/compliance**: OWASP LLM Top 10 (prompt injection #1), MCP
  tool-poisoning and rug-pull patterns, NIST AI agent standards initiative
  2026, EU AI Act obligations.
- **Frontend domain**: WebAIM 2026 — 95.9% of top home pages fail basic
  accessibility checks; 2026 tool reviews converge on accessibility,
  performance and design-system fidelity as what AI still gets wrong.

---

### Market-report coverage map — `FEDS Market Rating and Startup Gaps for SangLabs.md` (2026-10-19)

Every item of work in that report has exactly one owner:

| Report item | Owner | Where it lives |
|---|---|---|
| Gap 1 — governance/sprawl (94% concerned, 12% have a platform) | Muheeb | muheeb item 6 (registry + kill switch), on top of the approval console (muheeb item 1) |
| Gap 2 — the "last 30%", accessibility, before/after proof | Sanghaar | this file item 7 + item 12 |
| Gap 3 — outcome verification audits (trust in AI-employee claims) | Muheeb | muheeb item 7 (proof page) + item 11 (the claim itself) |
| Gap 4 — outcome-based pricing | Muheeb | muheeb item 13 |
| Gap 5 — memory that learns a company's design system | Sanghaar | this file item 10 (Verified Lesson Loop) |
| Gap 6 — regional/SMB demand, marked unsourced in the report | Muheeb | muheeb item 12 (tested as a hypothesis in pilot interviews, not built blind) |
| What to do 1 — choose the wedge | Muheeb | muheeb item 11 |
| What to do 2 — run 3–5 free pilots with before/after scores | Muheeb | muheeb item 12, reading this file item 12's measurements |
| What to do 3 — move off the free tier, run the container | Sanghaar | this file items 2 and 6, both marked below |
| What to do 4 — publish a small benchmark vs a baseline | Sanghaar | this file item 12 |
| What to do 5 — keep the honest-evaluation habit, sell it | split | the habit: this file item 5; the selling: muheeb item 11 |

---

## Design input received: the Verified Lesson Loop

`FEDS-Self-Learning-Algorithm-Design.docx` (v1.0 draft) specifies the next
phase: a per-task loop of verify → repair → reflect → gate → save, with a
reward score, tiered memory, confidence dynamics, a consolidator, a knowledge
cache, holdout lift measurement and a shared global layer. Its roadmap
(section 15) has seven phases:

1. Verifier and reward score (build, tests, lint, console, screenshot)
2. Lesson store, gate, mistake ledger and retrieval
3. Confidence updates, quarantine and holdout lift measurement
4. Consolidator, regression evals and versioned rollback
5. Knowledge cache and framework learning
6. Shared global layer and privacy controls
7. Local model routing

What already exists here and maps onto it: the memory store with private and
global scopes, three automated promotion gates (recorded verification, a
`generalizable` flag with `project_specific` refused, and a sanitized rewrite
free of identity, credentials and code), promotion provenance plus human
approval, model-scoped semantic retrieval over the task library, and the
reference ingester for knowledge-cache style material. What the design adds and is **not built yet**: confidence
dynamics (`confidence`, `status` = active/quarantined/rule), the normalized
mistake ledger, duplicate-merge and contradiction checks, the weighted reward
score, holdout lift measurement, consolidation and rollback, and local model
routing. Phases 1–3 are the natural first workstream.

---

## Completed since this list was last rewritten

- **Operator authorization** — decisions are policy-checked against
  `FEDS_ALLOWED_OPERATORS` inside `decide_run` before the run is touched;
  refusals are audited as `approval_refused` and the CLI exits non-zero.
  Proven live by `smoke_operator_auth.py` (zero model quota).
- **Bulk reference ingestion** — `ingest_refs.py` normalizes a directory of
  reference text into documents + embeddings with source attribution, idempotent
  per (source, title). Proven live by `smoke_ingest.py`.
- **Schema gap fixed** — `run_states` is now created by `setup_neon.py`
  (it previously existed only where it had been made by hand, so a fresh
  deployment could not park an approval at all).
- **Memory hardening** — every promotion gate is now automated: the server
  fails closed without an identity, `promote_memory` takes a required
  `sanitized_body` (framework-level prose) and refuses code, credentials or
  the author's identity in it, only affirmatively `generalizable` lessons
  promote, global rows are constrained to the sentinel owner and made
  append-only by a trigger, and the MCP server defaults to stdio and refuses
  a non-loopback bind. Approval remains the only human step. Pinned offline
  and proven live by `smoke_memory.py`.
- **Least-privilege runtime role** — `setup_neon.py` provisions a restricted
  `feds_app` login (no ownership, DDL, role/database admin, or RLS bypass) and
  the worker and MCP server connect with it via `FEDS_APP_DATABASE_URL`
  instead of the schema owner, so a leaked app credential cannot reshape the
  schema, constraints, or triggers. All runtime DDL was moved into
  `setup_neon.py`. Proven live by `smoke_app_role.py` (worker write path and
  SQLAlchemy engine succeed as `feds_app`; DDL refused).

---

## Priority order

**Tier A — foundation (existing items, unchanged):**

1. **Fix the two system-prompt findings** (item 1) — **both fixed, no quota
   needed:** `SYSTEM_PROMPT.md` section 11 now chooses mode by size, and the
   guardrail no longer hard-blocks pasted SQL (it blocks only trust-boundary
   subversion). Both are pinned by offline tests; live re-verification rides
   with item 5's stability pass.
2. **Provider family diversity** (item 2) — a real failover now works, but both
   live credentials are Gemini; a non-Gemini provider removes the shared-upstream
   risk.
3. **Local embedding model** (item 3) — the only option that makes embeddings
   (and ingestion) work with no network at all.
4. **Secrets rotation** (item 4) — required before any sharing.
5. **Stable-rate evals** (item 5), then the deferred deployment work (item 6).

**Tier B — the 10/10 critical path (this file items 7-11; the other half of
the roadmap is `muheeb.md` items 6-10, split evenly so neither queue
dominates):**

6. **Item 8 (sandbox) → item 7 (verification harness) → item 12 (before/after
   capture and benchmark) → item 10 (lesson loop
   phases 1-3)** — this chain is the product's core differentiator: measured
   proof of frontend work. Nothing else in either file is defensible without
   it, and the verifier costs zero model quota, so it keeps progress moving
   while Gemini free-tier limits stay the binding constraint on live checks.
7. **Item 9 (durable session log) → muheeb item 10 (parallel + scheduled
   runs)** — what makes FEDS behave like a product instead of a CLI, and the
   prerequisite for anything unattended. The stopping conditions this file
   owns are the safety rail that feature depends on.
8. **Muheeb items 6-8 (registry + kill switch, observability dashboard +
   proof page, ROI report)** — the governance-and-cost story buyers now gate
   on; those entries are UI over this file's worker/MCP hooks, so the hooks
   are written to contract first.
9. **Item 11 (injection/poisoning defense) and muheeb item 9 (compliance
   evidence pack)** — security work that must land before any real enterprise
   pilot; the defense item is tests-plus-documentation, not new architecture.
10. **Item 5's stability pass and item 6's deployment work** stay where they
    are — they gate honesty claims and first sharing, respectively.

How each item maps to the rating matrix in `Rating.txt` (this is what turns
7.7/10 into 10/10):

| Rating criterion | Closed by |
|---|---|
| 5. Autonomy breadth | this file 7, 8, 9; muheeb 10 |
| 9. Evaluation rigor | this file 5, 7, 10; muheeb 7 |
| 3. Memory quality | this file 10 |
| 7. Security | this file 11; muheeb 9 |
| 12. Deployment / enterprise | muheeb 6, 9; this file 6 |
| 8. Observability | muheeb 7, 8 |
| 10. Provider independence | this file 2, 3 |
| 11. Integration surface | muheeb 10; this file 6 |
| 6. Approval integrity | this file 6; muheeb 1 |
| 1, 2, 4 (already 9.0+) | held up by this file 5's eval discipline |

The market report's own weak areas map the same way: **market proof 2/10**
→ this file item 12 plus muheeb items 11–12; **production readiness 4/10**
→ this file items 2 and 6 (both marked What to do 3); **product
differentiation 5/10** → muheeb item 11 (the wedge).

Co-founder features live in `muheeb.md` (approval console, identity,
budgets, CI, notifications, plus new items 6-10); this file is Sanghaar's
queue only.
