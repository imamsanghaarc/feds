# FEDS Self-Learning Algorithm
## Mathematical Foundations & Seven-Phase Roadmap

---

## 1. Overview

The **FEDS Self-Learning Algorithm** is a reinforcement-loop system that enables FEDS to:
- Learn from each frontend engineering task executed
- Promote verified lessons to shared knowledge (skills, design-system patterns)
- Maintain confidence dynamics that govern knowledge retention and retirement
- Provide measurable holdout lift when promoted lessons are active
- Operate within the existing FEDS trust boundary (audit, approvals, least-privilege)

The algorithm is **quota-honest**: every learning step either consumes zero model calls (offline/smoke tests) or is fully cached/resumable. No fabricated numbers are ever produced.

---

## 2. Mathematical Foundations

### 2.1 Reward Function

After each task attempt, the **Verifier** (A2: headless CWV/accessibility checker) produces a vector of metrics:

$$\mathbf{m} = [\Delta\text{LCP},\ \Delta\text{INP},\ \Delta\text{CLS},\ n_{\text{violations}},\ \text{screenshot\_hash}]$$

The **reward score** $R \in [0, 1]$ is a normalized linear combination:

$$R = \sigma\Big(w_1 \cdot \phi_{\text{LCP}}(\Delta\text{LCP}) + w_2 \cdot \phi_{\text{INP}}(\Delta\text{INP}) + w_3 \cdot \phi_{\text{CLS}}(\Delta\text{CLS}) + w_4 \cdot \phi_{\text{violations}}(n_{\text{violations}})\Big)$$

where:
- $\sigma(x) = \frac{1}{1 + e^{-k(x - \theta)}}$ is the sigmoid squash (steepness $k$, midpoint $\theta$)
- $\phi_{\text{LCP}}(x) = \max(0, 1 - \frac{|x - \text{target}_{\text{LCP}}|}{\text{tolerance}_{\text{LCP}})$ clamped to $[0, 1]$, with $\text{target}_{\text{LCP}} = 2.5\text{s}$, $\text{tolerance} = 0.5\text{s}$
- $\phi_{\text{INP}}(x) = \max(0, 1 - \frac{|x - \text{target}_{\text{INP}}|}{\text{tolerance}_{\text{INP}})$, $\text{target}_{\text{INP}} = 200\text{ms}$, $\text{tolerance} = 50\text{ms}$
- $\phi_{\text{CLS}}(x) = \max(0, 1 - \frac{|x - \text{target}_{\text{CLS}}|}{\text{tolerance}_{\text{CLS}})$, $\text{target}_{\text{CLS}} = 0.1$, $\text{tolerance} = 0.02$
- $\phi_{\text{violations}}(n) = e^{-\lambda n}$ with $\lambda = 0.3$ (exponential penalty per violation)
- Weights: $w_1 = 0.4,\ w_2 = 0.3,\ w_3 = 0.2,\ w_4 = 0.1$ (summing to 1.0)

**Interpretation**: $R \approx 1$ = task met all Core Web Vitals + accessibility budget; $R \approx 0$ = significant regression.

---

### 2.2 Confidence Dynamics

Each **lesson** $\ell$ has a confidence score $c_\ell \in [0, 1]$ that evolves per task completion:

$$c_\ell(t+1) = \begin{cases}
\min(c_\ell(t) + \alpha \cdot R(t), & 1) & \text{if lesson } \ell \text{ was retrieved and task succeeded} \\
\max(c_\ell(t) - \beta, & 0) & \text{if lesson } \ell \text{ was retrieved and task failed} \\
c_\ell(t) & \text{if lesson } \ell \text{ was not retrieved this turn}
\end{cases}$$

where $\alpha = 0.05$ (learning rate on success) and $\beta = 0.02$ (decay on failure).

**Staleness detection**: If lesson $\ell$ has not been retrieved for $T_{\text{stale}} = 50$ tasks, its confidence is decayed:

$$c_\ell \leftarrow c_\ell \cdot \gamma \quad \text{with}\quad \gamma = 0.95$$

---

### 2.3 Promotion Criteria

A lesson $\ell$ is **promoted** from `active` $\to` `rule` status only when all of the following hold simultaneously:

1. **Confidence threshold**: $c_\ell \geq c_{\text{promote}} = 0.80$
2. **Success consistency**: $\frac{\text{success\_count}_\ell}{\text{retrieval\_count}_\ell} \geq 0.75$ (at least 3 successful retrievals)
3. **Recency**: $t - \text{last\_verified}_\ell \leq T_{\text{recency}} = 30$ tasks (lesson must be freshly verified)
4. **No quarantine**: $\text{status}_\ell \neq \text{quarantined}$

If promotion conditions are met, the lesson is moved to the **KSoR (Rung 1)** governed knowledge store as a `stable` doc with full provenance (sources, verification, generation, audience).

---

### 2.4 Holdout Lift Measurement

A **holdout set** $\mathcal{H}$ of tasks is maintained (fixed size $|\mathcal{H}| = 20$, never sees promoted lessons). The **lift** $\Delta$ is:

$$\Delta = \frac{1}{|\mathcal{H}|} \sum_{t \in \mathcal{H}} \Big(R^{\text{with-lessons}}_t - R^{\text{without-lessons}}_t\Big)$$

where:
- $R^{\text{with-lessons}}_t$ = reward score when active lessons are enabled for task $t$
- $R^{\text{without-lessons}}_t$ = reward score when lessons are disabled (baseline)

**Statistical requirement**: $|\Delta|$ must be computed over at least $N = 3$ independent run-throughs of the holdout set (cached/resumable, zero quota). The sign of $\Delta$ (positive or negative) is the reported metric; a reported lift of 0 is honest if the data supports it.

**Quarantine rule**: If $\Delta < 0$ (lessons degrade performance), the lesson is automatically quarantined regardless of its confidence $c_\ell$.

---

## 3. The Seven-Phase Roadmap (Formalized)

### Phase 1 – Verifier + Reward Score

**Input**: Task attempt output $\mathcal{O}$, ground-truth metrics from Verifier (A2)

**Compute**: Reward score $R$ as defined in Section 2.1

**Output**: $R \in [0, 1]$ stored on the `chat.turn` row as `reward_score`; audit row `capability_invoked` with `reward_computed`

**Zero-quota path**: Verifier runs locally (Playwright + axe-core); no model calls required.

---

### Phase 2 – Lesson Store + Gate + Mistake Ledger

**Data model** (SQL `lessons` table, extension of existing memory schema):

| Column | Type | Description |
|---|---|---|
| `lesson_id` | UUID | Primary key |
| `body_sanitized` | TEXT | Rewritten without identity, credentials, code fences |
| `confidence` | REAL | $c_\ell \in [0, 1]$, default 0.5 |
| `status` | TEXT | `active` $\mid$ `quarantined` $\mid$ `rule` |
| `retrieval_count` | INTEGER | Count of times this lesson was selected for a task |
| `success_count` | INTEGER | Count of retrievals where task succeeded (verifier $R \geq 0.7$) |
| `last_verified_at` | TIMESTAMP | Last turn where verifier $R$ was computed using this lesson |
| `quarantined_reason` | TEXT | Null unless `status = quarantined`; stores the measured reason |
| `created_at` | TIMESTAMP | Auto-set on insertion |
| `owner` | TEXT | `FRONTEND_USER_ID` for private lessons; `'-'` for shared |

**Mistake ledger** (append-only, never UPDATE/DELETE):

Each failed task where a lesson was incorrectly trusted inserts a ledger row:

$$\text{ledger}.\text{entry} = \{\text{lesson\_id},\ \text{task\_id},\ \text{verifier\_metrics},\ \text{quarantined\_reason},\ \text{operator},\ \text{timestamp}\}$$

**Promotion gate** (automated, no human step needed beyond the confidence/success checks in Section 2.3):

- If $c_\ell \geq 0.80$ AND $\frac{\text{success\_count}}{\text{retrieval\_count}} \geq 0.75$ AND recency $\leq 30$ AND $\text{status} \neq \text{quarantined}$ $\rightarrow$ promote to `rule` and write to KSoR (Rung 1)
- If $\Delta < 0$ (holdout lift negative) $\rightarrow$ set $\text{status} = \text{quarantined}$, record `quarantined_reason = "negative holdout lift \Delta = <value>"`

---

### Phase 3 – Confidence Dynamics + Holdout Lift

**Per-turn update** (after Phase 1's $R$ is computed):

1. If a lesson $\ell$ was **retrieved** this turn:
   - If $R \geq 0.7$ (task succeeded): $c_\ell \leftarrow \min(c_\ell + \alpha, 1)$, $\text{success\_count}_\ell \leftarrow \text{success\_count}_\ell + 1$
   - If $R < 0.7$ (task failed): $c_\ell \leftarrow \max(c_\ell - \beta, 0)$, $\text{failure\_count}_\ell \leftarrow \text{failure\_count}_\ell + 1$
2. If no lesson was retrieved: $c_\ell$ unchanged for all $\ell$
3. After $T_{\text{stale}} = 50$ turns without retrieval: apply staleness decay $c_\ell \leftarrow c_\ell \cdot \gamma$

**Holdout measurement** (after every $N = 20$ tasks):

- Evaluate $|\mathcal{H}| = 20$ holdout tasks with lessons active $\rightarrow$ compute $R^{\text{with-lessons}}_t$
- Evaluate same $20$ tasks with lessons disabled $\rightarrow$ compute $R^{\text{without-lessons}}_t$
- Compute $\Delta = \frac{1}{20}\sum(R^{\text{with}} - R^{\text{without}})$
- Record $\Delta$ in `eval_results.md`; if $\Delta < 0$, automatically quarantine the most-retrieved lesson(s) responsible

---

### Phase 4 – Lesson Graduation & Knowledge-Base Integration

When a lesson is promoted to `rule` status (end of Phase 2/start of Phase 4):

1. **KSoR Rung 1 integration**: The lesson body (sanitized) is written to `feds-ksor/knowledge/` as a Markdown doc with OKF frontmatter:
   ```yaml
   owner: feds-system
   audience: [public]
   status: stable
   sources: [FEDS self-learning algorithm]
   freshness: <timestamp>
   lifecycle: permanent
   ```
2. **Skill generation**: A new reference skill is auto-generated from the rule body and indexed in the skill index (progressive disclosure: the new skill is ~1,200 chars in the index, not the full corpus).
3. **Memory constraint**: The sanitized body is stored in the shared `memories` global layer (owner = `'-'`), but **only** as a provenance anchor. Retrieval of `find_similar_tasks` continues to use pgvector embeddings; the rule doc in KSoR is consulted via a separate governance gate (never mixed ungoverned material).

**Trust boundary**: KSoR content is authoritative for "institutional method questions" but is **never** merged into the pgvector embedding space used by `find_similar_tasks` unless a `source='ksor'` + `generation` + `audience` filter is explicitly applied.

---

### Phase 5 – Meta-Learning Across Tasks

**Goal**: Identify higher-level patterns across lessons to enable faster learning on new task types.

**Pattern extraction**: After a task type completes (e.g., "navbar rebuild", "form with validation"), compute a **type signature**:

$$\mathcal{T} = \big(\text{component\_type},\ \text{framework},\ \text{CWV\_profile},\ \text{accessibility\_class}\big)$$

Lessons are grouped by $\mathcal{T}$, and their confidences are adjusted:

$$c_\ell \leftarrow c_\ell \cdot \rho_{\mathcal{T}} \quad \text{where}\quad \rho_{\mathcal{T}} = \frac{\text{successes across all tasks of type }\mathcal{T}}{\text{total retrievals of type }\mathcal{T}}$$

**Transfer**: If a new task arrives with $\mathcal{T}_{\text{new}}$ that matches an existing type $\mathcal{T}_{\text{existing}}$ with $\rho_{\mathcal{T}_{\text{existing}}} \geq 0.7$, the new task's initial lesson pool is seeded with the existing lesson's confidence as a prior.

---

### Phase 6 – Staleness & Forgetting Mechanism

Lessons degrade over time if not reinforced. The **staleness score** $s_\ell$ is:

$$s_\ell(t) = 1 - c_\ell(t) \cdot \rho_{\mathcal{T}(t)} \cdot \mathbb{I}[t - \text{last\_verified}_\ell \leq T_{\text{recency}}]$$

where $\mathbb{I}$ is the indicator function (1 if recency condition met, 0 otherwise).

**Forgetting trigger**: If $s_\ell(t) > 0.75$ for $T_{\text{stale}} = 50$ consecutive turns, the lesson is moved to `quarantined` with reason `"staleness > 0.75 sustained"`.

**Renewal**: A quarantined lesson can be revived if a new task using the same $\mathcal{T}$ achieves $R \geq 0.8$, which sets $c_\ell \leftarrow 0.8$ and $\text{status} \leftarrow \text{active}$.

---

### Phase 7 – Reporting & Audit Closure

Every learning cycle writes a **learning audit row**:

| Field | Description |
|---|---|
| `run_id` | FK to `run_states` |
| `lesson_id` | FK to `lessons` (or NULL if no lesson activated) |
| `reward_score` | $R$ from Phase 1 |
| `lesson_confidence_before` | $c_\ell$ at start of turn |
| `lesson_confidence_after` | $c_\ell$ at end of turn |
| `holdout_lift_delta` | $\Delta$ from Phase 3 (if holdout round) |
| `action` | `"promote"`, `"quarantine"`, `"decay"`, `"revive"`, `"none"` |
| `operator` | Who triggered the action (or `system-auto`) |
| `timestamp` | UTC |

All learning audit rows are append-only (enforced by DB trigger) and retrievable via `replay.py` for full traceability.

**Quarterly summary** (written to `eval_results.md` honestly, no fabricated numbers):

- Total lessons active: $N_{\text{active}}$
- Total lessons quarantined: $N_{\text{quar}}$
- Total lessons ruled: $N_{\text{rule}}$
- Average confidence: $\bar{c} = \frac{1}{N_{\text{lessons}}}\sum c_\ell$
- Holdout lift median: $\tilde{\Delta}$
- Lessons promoted this quarter: $N_{\text{promote}}$
- Lessons quarantined this quarter: $N_{\text{quarantine}}$

---

## 4. Integration with Existing FEDS Components

### 4.1 Verifier (A2)

- The verifier runs **before** the learning algorithm (Phase 1)
- Output metrics $\mathbf{m}$ feed directly into the reward function $R$
- Verifier is zero-quota (local Playwright + axe-core); all learning metrics are quota-honest

### 4.2 Memory Architecture

- **Private lessons**: Owned by `FRONTEND_USER_ID`, isolation via SQL predicate `owner = requester`
- **Shared lessons**: Stored in global layer with owner `'-'`, append-only trigger protects against UPDATE/DELETE
- **Promotion**: Lessons promoted to `rule` status flow through the same three-gate system (verification, generalizable flag, clean sanitized body) as memory lessons (Section 5 of done.md)

### 4.3 Audit Trail

- Every learning action writes to the closed audit vocabulary (Section 8 of AGENTS.md)
- CHECK constraint on `audit_log.action` ensures only approved action verbs are emitted
- `replay.py` can reconstruct any learning cycle from audit rows alone

### 4.4 Provider Resilience

- Learning algorithm never routes around quota; all steps are offline/smoke-test first
- If model-based components are needed (e.g., for embedding-based lesson similarity), the provider router (Section 7 of AGENTS.md) handles rotation on 429/402 only
- Dual Gemini credentials with fallback (`gemini-fallback`) ensure learning continues even if one key exhausts

### 4.5 Skill Index (Progressive Disclosure)

- New lessons auto-generating skills are inserted at ~1,200 chars in the skill index (88.6% reduction from full corpus)
- Tolerant loading accepts casing/hyphen-variants; missing lessons degrade gracefully
- Skill composition: `summarize-component` may reference a promoted rule lesson; `escalate-review` consumes handoff notes verbatim

---

## 5. Zero-Quota Provability

Every component of the self-learning algorithm is provable without model quota:

| Component | Provable Offline | Smoke Test |
|---|---|---|
| Reward function $R$ | Deterministic formula from verifier metrics (no model) | `smoke_ingest.py` pattern; dry-run embedding generation |
| Confidence dynamics | Difference equations with fixed $\alpha, \beta, \gamma$ | Unit test: verify $c$ increases on success, decays on staleness |
| Promotion criteria | Threshold checks ($c \geq 0.80$, success ratio $\geq 0.75$, recency $\leq 30$) | `test_config.py` styled check; all gates enumerated |
| Holdout lift $\Delta$ | Fixed holdout set, no model calls needed (verifier is local) | `smoke_memory_schema.py` pattern; rolled-back transaction |
| KSoR integration | YAML frontmatter schema validation | Offline test: doc generated, OKF frontmatter parsed |
| Audit trail | DB trigger enforces append-only; verb CHECK constraint | `smoke_app_role.py` proves restricted role cannot forge entries |

**Theorem**: If all offline tests pass, the self-learning algorithm cannot introduce fabricated numbers, audit bypass, or credential leakage into a live run, because every step either (a) uses zero-model verifier output, or (b) is constrained by DB-enforced gates that are proven offline.

---

## 6. roadmap Timeline Alignment

| Quarter | Primary Focus | Deliverable |
|---|---|---|
| Q1 | Phases 1–3 foundation | Verifier integrated; confidence dynamics coded; holdout measurement operational; all zero-quota smoke tests passing |
| Q2 | Phases 4–5 | KSoR Rung 1 integration; lesson graduation promoted to stable rules; meta-learning type signatures working |
| Q3 | Phase 6 | Staleness/forgetting mechanism; automated quarantine on negative holdout lift; renewal path from quarantine |
| Q4 | Phase 7 | Full audit reporting; quarterly summaries in `eval_results.md`; provenance chain validated end-to-end |

**Success metrics** (honest, from real runs only):
- 11/11 trigger precision maintained (learning never breaks existing eval harness)
- Holdout lift $\Delta$ reported with $\pm$ statistical sign (never rounded up)
- No fabricated confidence numbers; NULL stays NULL when pricing/model unknown
- All promotion gates fire automatically; zero manual intervention needed for routine promotion/quarantine

---

*Algorithm formalism version 1.0. roadmap subject to adjustment based on quota availability, market feedback, and founder prioritization. Progress tracked in `sanghaar.md` and `plan.md`.*

---
## Areas for Potential Extension (10/10 Enhancement Path)

To achieve a full 10/10 rating and future-proof the algorithm, the following extensions are recommended. Each is optional for v1.0 but essential for production-scale self-learning:

### E1. Pseudocode Flowcharts for Every Phase
Add deterministic pseudocode (Python-adjacent, no runtime dependency) for Phases 1–7, enabling:
- Direct implementation reference for developers
- Unit test generation (every `if/else` branch covered)
- Educational material for contributors new to the codebase

**Example skeleton** (add per phase):
```python
def phase1_verifier_reward(task_output, metrics):
    """Compute reward R from verifier metrics. Zero-quota, local-only."""
    lcp, inp, cls, n_violations = metrics
    phi_lcp = max(0, 1 - abs(lcp - 2.5) / 0.5)
    phi_inp = max(0, 1 - abs(inp - 0.2) / 0.05)
    phi_cls = max(0, 1 - abs(cls - 0.1) / 0.02)
    phi_violations = exp(-0.3 * n_violations)
    R = 1 / (1 + exp(-k * (0.4*phi_lcp + 0.3*phi_inp + 0.2*phi_cls + 0.1*phi_violations - theta)))
    return R
```

### E2. Edge-Case & Quota-Exhaustion Protocols
Document and test what happens when Gemini free-tier quota runs out mid-learning cycle:
- **Graceful degradation**: Learning continues offline using last-known-confidence values; no fabricated reward scores.
- **Cached resumability**: Holdout lift $\Delta$ recomputed on next quota recovery; exit code 2 (incomplete) never reported as pass.
- **Fallback to deterministic rules**: If verifier cannot run, promote lessons only if $c_\ell$ was already $\geq 0.90$ pre-quota-exhaustion (stricter gate).

**Acceptance test**: `smoke_operator_auth.py` pattern — simulate quota exhaustion, verify no audit rows corrupted, no fabricated numbers written.

### E3. Visual Confidence Cycle Diagram
Create a mermaid.js or draw.io flowchart of the confidence dynamics loop:

```
cₜ  ──[success, R ≥ 0.7]──► cₜ₊₁ = min(cₜ + α, 1)
 │                              │
 │                              └─[failure, R < 0.7]──► cₜ₊₁ = max(cₜ - β, 0)
 │                                      │
 │                                      └─[no retrieval]──► cₜ₊₁ = cₜ
 │
 └─[T_stale = 50 turns]──────────────► cₜ ← cₜ · γ (staleness decay)
          │
          └─[sₜ > 0.75 for 50 turns]───► status → quarantined
                                   │
                                   └─[new task R ≥ 0.8]────► cₜ ← 0.8, status → active (revival)
```

**Why 10/10**: Visuals enable rapid onboarding; mermaid.js renders natively in GitHub READMEs and many wiki systems.

### E4. Compact Equation Quick-Reference Summary
Add a "cheat sheet" page (appendix) with all equations reduced to their minimal forms for quick scanning:

| Symbol | Equation | Meaning |
|---|---|---|
| $R$ | $\sigma(\sum w_i \phi_i)$ | Reward score [0,1] |
| $c_\ell(t+1)$ | $\begin{cases} \min(c_\ell + \alpha R, 1) & \text{success} \\ \max(c_\ell - \beta, 0) & \text{failure} \\ c_\ell & \text{no retrieval} \end{cases}$ | Confidence update |
| Promotion | $c_\ell \geq 0.80 \land \frac{\text{success}}{\text{retrieval}} \geq 0.75 \land \text{recency} \leq 30$ | Active $\to$ rule |
| $\Delta$ | $\frac{1}{20}\sum(R^{\text{with}} - R^{\text{without}})$ | Holdout lift |
| $s_\ell$ | $1 - c_\ell \cdot \rho_{\mathcal{T}} \cdot \mathbb{I}[\text{recency}]$ | Staleness score |

**Why 10/10**: Enables executives/ founders to grasp the algorithm without reading the full formalism; perfect for LinkedIn infographics.

### E5. Multi-User & Concurrent Run Considerations
Extend confidence dynamics to N concurrent users, each with isolated `FRONTEND_USER_ID`:
- Per-user confidence tables (already SQL-isolated via `owner = requester`)
- Shared `holdout set $\mathcal{H}$` must be partitioned per workspace (not per user) to avoid cross-contamination
- Quarantine decisions by user A must not affect user B's confidence $c_\ell$
- Audit rows must carry `FRONTEND_USER_ID` so replay.py can reconstruct per-user learning curves

**Acceptance**: `smoke_memory.py` already isolates per `FRONTEND_USER_ID`; extend lesson confidence checks to respect this boundary.

### E6. KSoR Rung 2 Integration Hint
KSoR Rung 1 (current) governs draft $\to$ review $\to$ stable. Rung 2 adds:
- **Versioned policy compilation**: When a `rule` lesson is updated (new $c_\ell$, new verifier metrics), a new KSoR version is auto-generated; old versions remain readable but retrieval prefers newest `status = stable`.
- **Authority-boundary filter**: `find_similar_tasks` query includes `AND source != 'ksor_v1'` unless explicitly requesting governed knowledge; prevents accidental mixing of authoritative KSoR with memory-authoritative embeddings.

**Note**: Rung 2 is out of scope for algorithm v1.0 (requires separate Node/pnpm KSoR project), but the hint file is included for roadmap completeness.

### E7. Quota-Free Learning Guarantee Theorem
Formalize and document the zero-quota provability as a provable theorem:

> **Theorem**: If all steps of the FEDS self-learning algorithm either (a) use the local Playwright+axe-core verifier (zero model calls) or (b) are constrained by DB-enforced gates proven offline in `smoke_*` tests, then no model quota is consumed during algorithm execution, and every written metric (reward score, confidence, holdout lift) is either (i) derived from zero-quota output or (ii) NULL (never fabricated).

**Proof sketch**: By induction over task turns; base case (turn 1) verified by `smoke_memory_schema.py`; inductive step relies on cached/resumable eval harness discipline ( `eval_triggers.py` rules: RETRY_ALL, exit code 2 honesty, no rounding up).

**Why 10/10**: This is the philosophical core of FEDS. Making it an explicit, provable theorem (not just an assertion) cements the "honest evaluation culture" as a rigorous, defensible claim.

---
### E8. Roadmap to 10/10 Prioritization
If resources are limited, prioritize extensions in this order (highest ROI first):

1. **E4 (Compact equation quick-ref)** – 1 day; immediate value for docs/infographics
2. **E1 (Pseudocode flowcharts)** – 2–3 days; enables implementation and testing
3. **E2 (Quota-exhaustion protocols)** – 2 days; critical for production reliability
4. **E3 (Visual confidence cycle)** – 1 day; high-impact visual for LinkedIn/marketing
5. **E5 (Multi-user isolation)** – 3–4 days; required if FEDS multi-user mode is launched
6. **E6 (KSoR Rung 2 hint)** – 1 day; roadmap-only, no implementation needed for v1.0
7. **E7 (Quota-free theorem)** – 2 days; philosophical completeness, no code change needed

*Estimated total effort for full 10/10: 10–12 developer-days, overlapping with Tier A (A1+A2) implementation timeline.*

---
*All extensions maintain the FEDS charter: zero-quota provability, honest evaluation (no fabricated numbers), and trust-boundary integrity. Progress on any extension is tracked in `sanghaar.md`; completion of E1–E4 upgrades the algorithm.md rating to a documented 10/10.*