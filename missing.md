# Sanghaar's Work — Remaining Items

Everything shipped has been removed from this file; it now lists only what is
not done. The evidence for completed work lives in `eval_results.md`, in the
test suite (`uv run python run_tests.py`), and in git history.

Legend: **OPEN** = not built yet. **BLOCKED** = the work is written but a
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
compatible) would make the semantic library quota-proof. After adding any
second model, run `reembed.py --dry-run` first: vectors from different
models must never be mixed (search is model-scoped by design).

---

## 4. Bulk reference ingestion — OPEN

No reader for articles, pattern documents, or prior component libraries
beyond individual saved tasks. `seed_corpus.py` covers resolved-case data
only. Needs an ingester that normalizes external reference material into
`documents` + `embeddings` with source attribution.

---

## 5. Operator authorization — OPEN

`decide_run(run_id, decision, operator)` now records *who* decided
(`run_states.operator` + an `approval_decided` audit row), but nothing
enforces *who is allowed* to decide. Until a role model exists, every
recorded operator is claimed, not verified. Build: identity for operators,
a policy checked inside `decide_run`, and a test that an unauthorized
operator is refused (including via the CLI's `--decide` path).

---

## 6. Secrets rotation before sharing the repo — OPEN

Credentials already live in the gitignored `.env` and a planted-secret
scanner in `test_config.py` keeps them out of source. What remains is the
rotation itself: rotate the Neon password and the provider key before this
repo or host is shared with anyone.

---

## 7. Stable-rate eval evidence — OPEN

The trigger eval is 11/11 as a **single sample per case** (recorded with the
load-vs-reply evidence split in `eval_results.md` section B). A stronger
claim needs three runs per case for a stable rate, and — if "selected" and
"loaded" are ever to be the same claim — a harness condition that forces the
`load_skill` call before scoring. Quota-gated like item 1.

---

## 8. Deployment and operations — DEFERRED by agreement

- **Tested container deployment.** `Dockerfile`, `compose.yml`, and
  `.dockerignore` are provided and reviewed (including the
  `!SYSTEM_PROMPT.md` exception and the `.claude/skills/` shipping
  behavior), but Docker was unavailable in this environment — reviewed,
  never executed. Run it once before trusting it.
- Restart supervision, rate limiting, and backpressure under load.
- Cost-shape estimate (course Part 5) — the rollup data
  (`replay.py --costs`) now exists to build it from.

---

## Priority order

1. **System prompt eval** (item 1, needs quota) — converts the last PARTIAL
   into a measurement.
2. **Second chat provider** (item 2) — restores real failover.
3. **Local embedding model** (item 3) — makes embeddings quota-proof.
4. **Operator authorization** (item 5) — closes the trust gap the attribution
   work opened.
5. **Secrets rotation** (item 6) — required before any sharing.
6. **Bulk ingestion** (item 4), **stable-rate evals** (item 7), then the
   deferred deployment work (item 8).

Co-founder features live in `muheeb.md` (approval console, identity,
budgets, CI, notifications); this file is Sanghaar's queue only.
