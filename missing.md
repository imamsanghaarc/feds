# Sanghaar's Work — Remaining Items

Everything shipped has been removed from this file; it now lists only what is
not done. The evidence for completed work lives in `done.md`, `eval_results.md`,
the test suite (`uv run python run_tests.py`), and git history.

Legend: **OPEN** = not built yet. **BLOCKED** = the work is written but an
external condition stops verification. **DEFERRED** = paused by agreement.

---

## 1. System prompt eval — BLOCKED (provider quota)

**Progress: 1 of 8 cases scored, and it passed. 7 cases never ran.**

`eval_set.md` defines the eight cases; `eval_results.md` section A records the
scored one and the seven unscored honestly as PARTIAL. The harness procedure:

```powershell
$env:RUN_LIVE_TESTS = "1"
uv run python worker.py "<one case prompt from eval_set.md>"
uv run python replay.py <conversation_id>   # confirm tool names are real
```

Free-tier Gemini quota exhausted mid-run before; the run is resumable one
case at a time. Do not round a partial pass rate into a score.

**Resuming (planned for tomorrow, with the new API key):** put the new key in
`.env` (`GEMINI_API_KEY=...`, or add the new provider and mark it enabled),
then run one case at a time with the commands above. No code changes are
needed — the worker and the harness both read the key through `config.py`.

---

## 2. Second enabled chat provider — OPEN

Only Gemini is enabled. The OpenAI key returns 401 (disabled), so rotation
cannot be exercised live — the failover logic is proven by tests and forced
429/402 stubs only. Either re-enable OpenAI with a valid key or add Groq
(generous free tier), then run a real failover once.

---

## 3. Embedding redundancy and a local embedding model — OPEN

Gemini and OpenAI are the only embedding-capable providers configured, and
OpenAI is disabled — so embeddings have exactly one live path. A local model
(Ollama, or a sentence-transformers variant at 768 dims so vectors stay
compatible) would make the semantic library quota-proof. Note that ingestion
(`ingest_refs.py`) and seeding both depend on that single live path. After
adding any second model, run `reembed.py --dry-run` first: vectors from
different models must never be mixed (search is model-scoped by design).

---

## 4. Secrets rotation before sharing the repo — OPEN

Credentials already live in the gitignored `.env` and a planted-secret
scanner in `test_config.py` keeps them out of source. What remains is the
rotation itself: rotate the Neon password and the provider key before this
repo or host is shared with anyone.

---

## 5. Stable-rate eval evidence — OPEN

The trigger eval is 11/11 as a **single sample per case** (recorded with the
load-vs-reply evidence split in `eval_results.md` section B). A stronger
claim needs three runs per case for a stable rate, and — if "selected" and
"loaded" are ever to be the same claim — a harness condition that forces the
`load_skill` call before scoring. Quota-gated like item 1, so it also resumes
with the new API key tomorrow.

---

## 6. Deployment and operations — DEFERRED by agreement

- **Tested container deployment.** `Dockerfile`, `compose.yml`, and
  `.dockerignore` are provided and reviewed (including the
  `!SYSTEM_PROMPT.md` exception and the `.claude/skills/` shipping
  behavior), but Docker was unavailable in this environment — reviewed,
  never executed. Run it once before trusting it.
- Restart supervision, rate limiting, and backpressure under load.
- Cost-shape estimate (course Part 5) — the rollup data
  (`replay.py --costs`) now exists to build it from.

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
global scopes, three save gates (evidence required, project-specific refused,
sanitized), promotion provenance plus human approval, model-scoped semantic
retrieval over the task library, and the reference ingester for knowledge-cache
style material. What the design adds and is **not built yet**: confidence
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

---

## Priority order

1. **System prompt eval** (item 1, needs quota) — converts the last PARTIAL
   into a measurement.
2. **Second chat provider** (item 2) — restores real failover.
3. **Local embedding model** (item 3) — makes embeddings (and ingestion)
   quota-proof.
4. **Secrets rotation** (item 4) — required before any sharing.
5. **Stable-rate evals** (item 5), then the deferred deployment work (item 6).

Co-founder features live in `muheeb.md` (approval console, identity,
budgets, CI, notifications); this file is Sanghaar's queue only.
