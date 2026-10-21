# FEDS Roadmap — Unified Work Plan (Sanghaar + Muheeb Combined)

Everything shipped is documented in `done.md`. This file tracks only unfinished work. It carries the concrete plan to push FEDS from 7.7 to 8.0+, then to 9.0.

**Legend:** **OPEN** = not built yet. **BLOCKED** = external condition stops verification. **DEFERRED** = paused by agreement. **IN-PROGRESS** = actively being worked on. **v1** = target for first release (highest impact / lowest lift).

---

## Quick Goal Statement

The aim is not to "add more tools", but to make FEDS' claims **testable, provable and enforceable**.

- **Reach ~8.0 – 8.15** with the lowest lift: adopt KSoR (Rung 1), and ship the zero-quota verifier + before/after capture.
- **Reach ~8.3 – 8.6** by hardening the approval path (DSoR) whilst keeping the above.
- **Reach ~9.0** by completing the Verified Lesson Loop (with measured holdout lift), injection defenses, stability pass and the published benchmark.

---

## Version Plan

### v1 — "Provable & Enforceable" (Target: 2–3 weeks)
Highest-impact items that make FEDS demonstrably different from generic coding agents.

| ID | Item | Source | Effort | Benchmark Δ |
|---|---|---|---|---|
| **v1-01** | **KSoR Integration — Rung 1** | A1 | S | +0.15–0.25 |
| **v1-02** | **Zero-quota verifier + before/after capture** | A2 | M | +0.4–0.5 |
| **v1-03** | **Stable-rate eval evidence** | A3 | S | +0.05–0.10 |
| **v1-04** | **Provider independence** | A4 | S | +0.05–0.10 |
| **v1-05** | **Secrets rotation check** | A5 | XS | — |
| **v1-06** | **DSoR — Minimal enforcement (publish_task, promote_memory)** | B1 | M | +0.3–0.5 |
| **v1-07** | **Durable session log + resume** | B2 | M | +0.10–0.15 |
| **v1-08** | **Sandboxed execution environment** | B3 | M | +0.10 |
| **v1-09** | **Indirect prompt-injection & memory-poisoning defense** | B4 | M | +0.10 |
| **v1-10** | **Approval console (web UI)** | Muheeb-1 | M | — |
| **v1-11** | **Team identity and sessions** | Muheeb-2 | M | — |
| **v1-12** | **Budgets and cost alerts** | Muheeb-3 | M | — |
| **v1-13** | **CI pipeline** | Muheeb-4 | S | — |
| **v1-14** | **Approval pause notifications** | Muheeb-5 | S | — |
| **v1-15** | **Pick the wedge & restate product** | Muheeb-11 | XS | — |

### v1.1 — "Governed & Observable" (Target: +2–3 weeks)
| ID | Item | Source | Effort |
|---|---|---|---|
| v1.1-01 | Agent registry and kill switch | Muheeb-6 | L |
| v1.1-02 | Operations dashboard + proof page | Muheeb-7 | L |
| v1.1-03 | Oversight and ROI report | Muheeb-8 | M |
| v1.1-04 | Compliance evidence pack + deletion | Muheeb-9 | M |
| v1.1-05 | Parallel runs and scheduled automations | Muheeb-10 | L |

### v2 — "Self-Learning & Benchmarked" (Target: +3–4 weeks)
| ID | Item | Source | Effort |
|---|---|---|---|
| v2-01 | Verified Lesson Loop (phases 1–3) | C1 | L |
| v2-02 | Published benchmark vs baseline | C2 | M |
| v2-03 | Internal memory eval | C3 | M |
| v2-04 | Deployment hardening (container tested) | C4 | M |
| v2-05 | Pilot program (3–5 free pilots) | Muheeb-12 | L |
| v2-06 | Outcome-based pricing metering | Muheeb-13 | M |

---

## v1 Detailed Specs

### v1-01: KSoR Integration — Rung 1 (COMPLETE)
**Priority: 1 | Effort: S | Benchmark delta: +0.15 – +0.25 | Risk: Low**

Integrate [KSoR](https://github.com/panaversity/ksor) to govern the institutional knowledge (skills + references), without replacing FEDS' existing state/memory.

- [x] **Scaffold a separate KSoR instance.** Created `feds-ksor/` as its own Node 24 + pnpm project. Do not merge with the Python `frontend-developer-FTE` repo.
- [x] **Migrate corpus.** Moved the 35 skills and their `references/` from `.claude/skills/` and `skills/` into `feds-ksor/knowledge/` in KSoR's profiled Markdown (with OKF frontmatter).
- [x] **Add governance frontmatter.** For each migrated doc: `owner`, `audience` (default `[public]`), `status` (start at `draft` for new ones; `stable` only after review), `sources`, `freshness`, `lifecycle`. 
- [x] **Enforce the build gate.** Use `ksor build` to ensure drafts never reach agent surfaces. Added CI check to fail if a stable doc is missing required frontmatter.
- [x] **Generate machine surfaces.** Produced `llms.txt` and the human site from the same governed record.
- [x] **Draw the boundary.** Decided: *institutional/method knowledge* → KSoR. *Tasks, memories, workspace state, audit* → FEDS' Neon DB. Do not duplicate `find_similar_tasks` over KSoR content yet.
- [x] **Provenance schema.** Treated as concrete schema for v1-09 (content provenance + trust level).

**Acceptance:** `ksor build` shows drafts filtered correctly, `llms.txt` is generated, and FEDS can still answer using existing paths with no regression to offline tests.

**Notes:** Stop at Rung 1. Do not wire Streamable HTTP MCP yet.

---

### v1-02: Zero-quota verifier + before/after capture (COMPLETE)
**Priority: 1 | Effort: M | Benchmark delta: +0.4 – +0.5 | Risk: Low**

Directly closes the market "proof" gap (market proof 2/10) without consuming Gemini quota.

- [x] **Headless verifier harness.** Added `verifier.py` using Playwright + axe-core that runs with zero model calls.
  - [x] Measure lab metrics: **LCP ≤ 2.5s**, **INP ≤ 200ms**, **CLS ≤ 0.1** (p75 field thresholds matching `SYSTEM_PROMPT.md`).
  - [x] Run WCAG 2.2 A/AA checks via axe-core; log rule IDs and severities.
  - [x] Capture a screenshot artifact on failure and on demand.
- [x] **Verification persistence.** Created `verifications` table tied to `task_id`, `conversation_id`, `revision`, `verifier_version`, `timestamp`, `metrics_json`, `violations_json`, `artifact_path`, `status` (`pass|fail`).
- [x] **Before/after capture.** On a change: snapshot "before" (if exists for that task/revision context), run after. Store both snapshots + numeric deltas (ΔLCP, ΔINP, ΔCLS, fixed violations count) on the same verification row(s).
- [x] **Gate `publish_task`.** Require a passing verification record for the current revision before publishing (extends existing approval gate, does not remove human approval).
- [x] **Offline smoke.** Added zero-quota test that asserts: page missing `alt` fails with a specific axe rule id and cannot be published; a passing case writes real numbers.
- [x] **Proof page contract.** Outputs a machine+human readable proof bundle so v1.1-02 (proof page) can render it.

**Acceptance:** A deliberately bad example fails verification and is blocked from publish; a good example passes with stored metrics; `run_tests.py` remains green; no model quota consumed.

---

### v1-03: Stable-rate eval evidence (BLOCKED by quota)
**Priority: 2 | Effort: S | Benchmark delta: +0.05 – +0.10 | Risk: Low**

Make your claims honest and reproducible.

- [ ] **3-runs-per-case for system-prompt eval.** Re-run `eval_set.md` at least 3 times per case, starting with case 1 (known variance). Record pass/fail per run + variance notes in `eval_results.md` under existing honesty rules (real runs only; exit 2 never reported as pass).
- [ ] **Make "selected" == "loaded" testable.** Optionally enforce that for trigger cases the harness observes a recorded `load_skill` call before scoring (prevents conflating "selected in reply" with "actually loaded").
- [ ] **Cache discipline.** Keep `RETRY_ALL=1` and named-case targeting working. Do not round partial runs up.

**Blocked:** Free-tier Gemini quota spent for the day on both keys. Must run when quota recovers.

---

### v1-04: Provider independence (COMPLETE)
**Priority: 2 | Effort: S | Benchmark delta: +0.05 – +0.10 | Risk: Low**

Reduce shared-upstream risk.

- [x] **Non-Gemini provider live.** OpenRouter (Anthropic Claude) is wired and authenticating (HTTP 200). OpenAI (gpt-4o-mini) added and authenticating (HTTP 200). Groq removed.
- [x] **Verify failover.** Proved rotation fires on real 429/402 against the new providers. Model labels don't break embedding comparability.
- [x] **Document fallback order.** Updated `README.md`, `deployment.md`, `provider_router.py` docs.

**Note:** Embeddings use dual-Gemini (model-scoped) + OpenAI (`text-embedding-3-small` available). Chat: 4 families, 3 independent quota pools.

---

### v1-05: Secrets rotation check (COMPLETE)
**Priority: 2 | Effort: XS | Risk: Med (operational)**

- [x] Rotate Neon password and provider keys before sharing repo/host.
- [x] Confirm `test_config.py` planted-secret scan passes with no new secrets.
- [x] Ensure `.env` remains gitignored and deployment uses real env vars.

---

### v1-06: DSoR — Minimal enforcement slice (COMPLETE)
**Priority: 3 | Effort: M | Benchmark delta: +0.3 – +0.5 | Risk: Med–High**

[DSoR](https://github.com/panaversity/dsor) has **no reference implementation yet**. Treat this as a *spec-driven build*, not an integration. Build only the slice governing `publish_task` and `promote_memory`.

**Done (Oct 20):**
- [x] `approvals` table created in `setup_neon.py`
- [x] `feds_approver` role created with write access to `approvals` only
- [x] `promote_task()` SECURITY DEFINER trigger function + BEFORE UPDATE trigger on `documents`
- [x] `promote_memory()` SECURITY DEFINER function (called directly, not trigger — avoids recursion)
- [x] Worker MCP config updated to call DB functions

**Remaining (post-v1):**
- [ ] **Read DSoR spec fully.** Review `specs/dsor/*`, `packages/spec/requirements.json` (268 requirements), schemas and tests. Understand authority boundaries ([§4](https://github.com/panaversity/dsor/blob/main/specs/dsor/01-model.md#4-authority-boundaries-and-precedence)), policy→control compilation ([§17](https://github.com/panaversity/dsor/blob/main/specs/dsor/02-security.md#17-policy-compilation-from-authority-to-control)), idempotency, evidence, stale controls.
- [ ] **Write minimal DSoR scope doc.** Define which FEDS operations become DSoR-governed: start with `publish_task` and `promote_memory`. Explicitly exclude reads, listing, lookups.
- [ ] **Create `dsor/` workspace.** Keep separate from `feds-ksor/`. Use TypeScript + Postgres (Neon). Model against the requirement IDs from `requirements.json`.
- [ ] **Implement minimal enforcement pipeline.** Focus on: identity/delegated authority, control evaluation (CEL per spec), approval requirement, idempotency keys, action evidence, append-only audit, and "stale control" handling.
- [ ] **Wire KSoR linkage.** When a control references a KSoR policy (doc + version + content hash), enforce staleness check: if policy changed, mark control stale and block execution until recompiled/reviewed.
- [ ] **Replace/augment worker gates.** Keep the worker UX (`--decide`) but require the DSoR approval row to exist and be valid. The app role must **not** be able to forge approvals (separate approver path or DB-enforced check). 
- [ ] **Conformance-lite.** Write tests that map to key requirement IDs (especially those around approval, idempotency, evidence, control versioning). Do not attempt to satisfy all 268 at once.
- [ ] **Evidence bridge.** Write DSoR evidence to FEDS' audit trail (or link by `action_id`/`run_id`).

**Acceptance (v1 slice):** A high-value `publish_task` cannot proceed without a valid approval row; forging approval is impossible with `feds_app` credentials; evidence is append-only and complete. Full DSoR conformance is post-v1.

---

### v1-07: Durable session log + resume (COMPLETE)
**Priority: 3 | Effort: M | Benchmark delta: +0.10 – +0.15 | Risk: Low–Med**

Makes FEDS behave like a product (restartable) instead of a CLI.

- [x] **Event-slice API.** `get_session_events(conversation_id, from_seq, to_seq)` reads `audit_log` slices to reconstruct state without duplicating rows.
- [x] **Restartable harness.** `worker.py --resume <conversation_id>` re-reads events and continues.
- [x] **Idempotency on replay.** Tool calls are idempotent when replayed (side-effects must not repeat). Leverages existing idempotency.
- [x] **Stopping conditions.** Enforces `max_iterations`, `max_cost_cents`, `wall_clock_limit` (seconds). On stop, writes reason to audit.
- [x] **Approval resume intact.** Killing mid-park allows `--decide <run_id>` to work after restart.

**Acceptance:** Kill and restart mid-run → resumes without losing parked approval, without duplicating committed side-effects, and max-cost stop triggers offline.

---

### v1-08: Sandboxed execution environment (COMPLETE)
**Priority: 3 | Effort: M | Benchmark delta: +0.10 | Risk: Med**

Prerequisite for safely generating/executing build/test/lint (needed for verifier integration and lesson loop).

- [x] **Per-run sandbox.** `sandbox_executor.py` — container/restricted subprocess. Strips `.env`, `NEON_*`, `FEDS_APP_DATABASE_URL` from env. Restrict egress to allowlist if needed.
- [x] **DB access stays outside.** All Neon access continues via MCP server (outside sandbox) — enforced and tested.
- [x] **Tool contract `execute(name,input)->string`.** Dead/timeout/killed sandbox returns retryable tool error; never kills session.
- [x] **Return ground truth.** Build/test/lint results feed back to audit and to verifier.
- [x] **Offline test.** Assert sandbox cannot read `os.environ`/`.env` for credentials.

**Acceptance:** Offline test proves no credentials visible inside sandbox; killed sandbox surfaces as retryable error; real results land in `audit_log`.

---

### v1-09: Indirect prompt-injection & memory-poisoning defense (COMPLETE)
**Priority: 3 | Effort: M | Benchmark delta: +0.10 | Risk: Low**

Addresses OWASP LLM Top 10 (#1 prompt injection), MCP tool/knowledge poisoning.

- [x] **Ingestion hardening.** `ingest_refs.py`, `seed_corpus.py`: `security_ingestion.py` detects instruction-like payloads, stamps `provenance.trust_level` (untrusted/low/medium/high), marks body as inert data.
- [x] **Retrieval contract.** Extended `SYSTEM_PROMPT.md` §9: treat retrieved chunks and tool results as **untrusted** by default; never treat them as system instructions.
- [x] **Red-team case.** Added to `eval_set.md` poisoned references that try to bypass approval/exfiltrate env. Scored like others; `security_ingestion.py` tests pass.
- [x] **Control mapping doc.** `security_ingestion.py` implements OWASP LLM Top 10 + NIST guidance mapping with honest gaps.
- [x] **KSoR synergy.** Leveraged KSoR frontmatter (`sources`, `verification`, `freshness`, `trust signals`) for ingestion decisions.

**Acceptance:** Poisoned ingested doc cannot cause approval bypass under pinned offline test; red-team case passes; mapping doc exists.

---

### v1-10: Approval console (web UI) (COMPLETE)
**Priority: 1 | Effort: M | Source: Muheeb-1**

FEDS parks approval-gated runs (`publish_task`, `promote_memory`) and today they are resumed only from the CLI (`worker.py --decide <run_id> approve [operator]`). Build the human-facing console:

- [x] **Queue of parked runs** from `run_states`, with the conversation trail rendered from `audit_log` (the same reconstruction `replay.py` does).
- [x] **Approve / reject** with the operator's real name — it flows into the existing `decide_run(run_id, decision, operator)` so `run_states.operator` and the `approval_decided` audit row stay the single source of truth.
- [x] **Read-only views stay ungated** (reads run free); only the decision button writes.

**Done when:** approving from the console resumes the parked run through the same code path as the CLI, the operator appears in the trail, and a second console request for the same run is refused while the first is deciding (the per-conversation advisory lock already in `decide_run`).

**Files:** `approval_console.py` (FastAPI), `templates/dashboard.html`, `templates/run_detail.html`

---

### v1-11: Team identity and sessions (COMPLETE)
**Priority: 1 | Effort: M | Source: Muheeb-2**

Right now the MCP server sees one process-level identity (`FRONTEND_USER_ID`, defaulting to `unconfigured-user`), so memory isolation is proven only between simulated users in one process.

- [x] **Per-request user injection.** Worker calls `set_user(user_id, user_name)` at task start, replacing the env-var identity; `save_memory` / `list_memories` / `delete_memory` isolate per request, not per process.
- [x] **MCP tools exposed.** `set_user(user_id, user_name)` and `get_current_user()` allow programmatic identity management.

**Done when:** two logged-in users cannot read each other's private memories under concurrent use — the same isolation `smoke_memory.py` proves for two simulated ids, now proven across real sessions.

**Files:** `frontend_workspace_mcp/server.py` (`_user_identity_cache`, `set_user`, `get_current_user`), `worker.py` (calls `set_user` at task start)

---

### v1-12: Budgets and cost alerts (COMPLETE)
**Priority: 2 | Effort: M | Source: Muheeb-3**

Token and cost rollups now land on every `chat.turn` row in `capability_invocations` (`cost_cents`, labelled `cost_basis: "list_price_estimate"`). Build the spending controls:

- [x] **Monthly budget per workspace** (and later per user), computed from those rollups — the same aggregation `replay.py --costs` exposes.
- [x] **Warning threshold and hard cap;** a hard cap blocks new turns through the guardrail path rather than silently degrading quality.

**Done when:** a budget set below the month's actual spend is reported correctly, and rows with unknown pricing (`cost_cents IS NULL`) are excluded from totals — never counted as zero.

**Files:** `budget_manager.py`, `workspace_budgets` table, `budget_hard_cap_guardrail`

---

### v1-13: CI pipeline (COMPLETE)
**Priority: 2 | Effort: S | Source: Muheeb-4**

No automated gate exists; suites are run by hand. Add GitHub Actions:

- [x] **On every push:** `uv run python run_tests.py` (3 suites, must stay green) plus the secret scanner and skill-tree validation that ship in the suite.
- [x] **Scheduled, resumable live evals** (`eval_triggers.py`, `eval_set.md`) only when provider secrets are present — skipped, not failed, when they are not.

**Done when:** a failing offline suite turns the PR red, and a scheduled live run records PARTIAL honestly (exit code 2) instead of being reported as a pass.

**File:** `.github/workflows/ci.yml`

---

### v1-14: Approval pause notifications (COMPLETE)
**Priority: 2 | Effort: S | Source: Muheeb-5**

When a run parks waiting for approval, nobody finds out unless they poll.

- [x] **A notifier** (Slack webhook or email) fired when a run enters the parked state, carrying the run id, what is being approved, and the exact decide command to run.
- [x] **The console from v1-10 linked from the message.**

**Done when:** parking a run produces exactly one notification, a resumed run produces none, and a notification failure never breaks the pause itself (same best-effort rule the metrics writes follow).

**File:** `approval_notifier.py`

---

### v1-15: Pick the wedge & restate product (COMPLETE)
**Priority: 1 | Effort: XS | Source: Muheeb-11**

`FEDS Market Rating and Startup Gaps for SangLabs.md` scores product differentiation 5/10 — Cursor, Claude Code, v0, Lovable, Bolt and Devin already own "general frontend coding", and nothing in the repo claims FEDS writes better UI than they do.

- [x] **Decide and record the wedge:** "frontend performance and accessibility fixes, audited and approved by a human." Written into `README.md` and every product-facing description; general frontend coding is explicitly **not** the pitch.
- [x] **A competitive note** against the six named tools: what each does, what FEDS does not claim, and where governance + verified outcomes (the areas they handle thinly) is the whole story.
- [x] **Turn honesty into the pitch:** publish the evaluation posture — single-sample labels, exit codes, no rounded-up runs — as customer-facing material, plus "outcome verification audits": every change ships with its before/after evidence (v1-02's proof page, measured by v1-02).

**Done when:** the README opens with the wedge, every marketing claim maps to a number or artifact that exists in the repo, and no claim asserts stability the evals have not measured.

**Files:** `README.md` (wedge definition, competitive note, governance section)

---

### v1-16: Nervous System (OPEN) — Durable execution engine
**Priority: 1 | Effort: M | Source: Algorithm design, Inngest crash course**

Implements the three-layer nervous system (senses, reflexes, balance) to enable FEDS autonomous operation without human-in-every-turn. Maps to Inngest concepts 1–15 and provides production-grade durability, retries, flow control, and HITL gates.

- [ ] **Senses layer:** Cron triggers (v1-02), webhook triggers with two-door pattern, event triggers with fan-out. Zero-quota provable via smoke tests.
- [ ] **Reflexes layer:** `step.run` + memoization for crash survival; `step.sleep`/`wait_for_event` for durable waits (zero compute); retries with `NonRetriableError` for permanent failures; `step.run` wraps AI agent calls.
- [ ] **Balance layer:** Global + per-key concurrency, throttle for OpenAI rate limit (30/min), priority ordering (Enterprise/Pro/Free), batching for bulk work, replay and bulk cancellation for recovery.
- [ ] **Integration:** Zero-import design (agent never imports Inngest); swap-ready across Inngest/Temporal/Restate/Dapr. All components provable without model quota.
- [ ] **Version targeting:** v1 MVP (cron + webhook + `step.run` + throttle), v1.1 additions (per-key concurrency + priority + batching + dashboard), v2 full (verified lesson loop built on top).

**Acceptance:** FEDS worker wakes on `customer/email.received` event, runs durably (agent inside `step.run`), survives crashes (memoization), respects flow control (caps + throttle), and gates refunds on durable human approval (`wait_for_event`). Audit trail complete for every step. No model quota consumed in smoke tests.

**References:** `nervous-system.md`; `algorithm.md`; `done.md`; Inngest crash course concepts 1–15.

---

## Cross-cutting: Spec & Documentation Requirements

### D1. Write an integration spec (OPEN)
**Priority: 2 | Effort: M**

Create a concrete spec to avoid drift between Python worker and Node KSoR/DSoR.

- [ ] **Location:** `docs/specs/feds-governance-integration.md`
- [ ] **Contents:**
  - Boundaries: KSoR (knowledge) vs DSoR (actions) vs FEDS (runtime/memory/tasks)
  - Transport: decision matrix (stdio vs Streamable HTTP). Rationale for starting at Rung 1 (stdio-free integration first).
  - Identity: how `FRONTEND_USER_ID`/`FRONTEND_CONVERSATION_ID` map to DSoR actor/authority.
  - Provenance: OKF frontmatter schema + required fields for stable docs.
  - Retrieval: precedence rules (never mix KSoR authoritative with memory authoritative)
  - Verification: `verifications` schema, gate conditions, before/after contract
  - Security: trust boundary, sandbox rules, injection handling
  - DSoR scope: minimal first slice (publish_task, promote_memory), requirement IDs to satisfy
  - Non-goals: e.g. replacing task semantic search, making model deterministic

**Acceptance:** Reviewed against `AGENTS.md`, `plan.md`, `deployment.md` before implementing v1-06 fully.

---

### D2. Update status docs (OPEN)
**Priority: 2 | Effort: XS**

- [ ] Update `done.md` with v1 items as they land. 
- [ ] Keep `sanghaar.md` as "remaining" only.
- [ ] Update `eval_results.md` with stable-rate numbers (v1-03).
- [ ] Add `docs/security/owasp-mapping.md` (v1-09).
- [ ] Update `README.md` with "Governance" section (KSoR Rung 1) once v1-01 done.

---

### D3. Traceability to market report (OPEN)
**Priority: 2 | Effort: XS**

Ensure every market gap is covered and testable.

| Report item | Covered by | Evidence |
|---|---|---|
| Gap 1 – governance/sprawl (94% concerned) | v1-01 + D1 | KSoR build gate, audiences, frontmatter |
| Gap 2 – last 30%, accessibility, before/after | v1-02 | `verifications` rows + deltas + axe rule IDs |
| Gap 3 – outcome verification audits | v1-02 + v1.1-02 | Machine-readable proof bundle |
| Gap 4 – outcome-based pricing | v2-06 | Cost rollups exist (`replay.py --costs`) |
| Gap 5 – memory learns design system | v2-01 | Lessons + confidence + quarantine + holdout lift |
| What to do 3 – move off free tier + container | v1-04 + v1.1 | Provider diversity + tested container |
| What to do 4 – publish benchmark vs baseline | v2-02 | `eval_results.md` with real numbers |

---

## Implementation Notes

- **Don't duplicate retrieval.** Keep KSoR Rung 1 as a *governed source* consulted for institutional/method questions. Do not merge KSoR chunks into `embeddings` used by `find_similar_tasks` unless you add a `source='ksor'` + `generation` + `audience` filter and never mix with ungoverned material.
- **Transport choice.** Start with Rung 1 (no MCP serving to worker yet). If you later serve KSoR via MCP, prefer connecting over HTTP to an isolated process, or add a thin stdio bridge. The current worker expects `stdio` for its own MCP — don't co-opt that.
- **Least privilege.** KSoR gets its own DB/credentials. Never give `feds_app` DDL rights to KSoR schema. DSoR will need its own approver role path (v1-06).
- **Quota-aware.** v1-02 and stability runs are quota-free or cached. Live harnesses must keep `RUN_LIVE_TESTS=1`, cache, and exit-code discipline.
- **No fabricated numbers.** All evals follow the "real runs only" rule. NULL costs stay NULL.

---

## References

- [KSoR](https://github.com/panaversity/ksor) — Knowledge System of Record (twin to DSoR)
- [DSoR](https://github.com/panaversity/dsor) — Data System of Record (spec v1.4.0, 268 requirements, no ref impl yet)
- [OWASP Top 10 for LLMs](https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [WebAIM 2026](https://webaim.org/projects/million/)
- [G2 2026 AI Agents Report](https://research.g2.com/insights/ai-agents-report-2026)
- `FEDS-Self-Learning-Algorithm-Design.docx` (repo root)