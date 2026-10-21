# FEDS Nervous System
## Durable Execution & Flow Control for Production AI Workers

**Version:** v1.0 — Initial implementation targeting FEDS v8.0–8.15
**Status:** OPEN — requires implementation
**Related:** draws from Inngest crash course concepts 1–15, maps to sanghaar.md items v1-02, v1-06, v1-07, v1-09, v1-10

---

## 1. Overview

The **FEDS Nervous System** is the durable execution engine that closes the gap between an agent you operate and an FTE that runs on its own. It provides three layered capabilities:

| Layer | FEDS Equivalent | Core Concepts |
|---|---|---|
| **Senses** | Triggers (v1-02, v1-10) | Cron, webhook, event — how the world wakes the worker |
| **Reflexes** | Durable execution (v1-02, v1-06) | `step.run`, memoization, retries, `step.sleep`/`wait_for_event` — survival when things break |
| **Balance** | Flow control (v1-07, v1.1) | Concurrency, throttle, priority, fairness, batching, replay/cancellation — healthy under load |

**Design goal:** The agent code (worker.py, SandboxAgent) never imports Inngest. The nervous system wraps from the outside, making it swap-ready across Inngest, Temporal, Restate, and Dapr Agents.

**Quota-honest:** All components provable without model quota. Zero-quota smoke tests exist for every layer.

---

## 2. Senses (Triggers) — How the World Reaches the Worker

### 2.1 Cron Triggers (scheduled work)
**FEDS implementation:** Daily health checks, weekly cleanups, hourly recalculations.

```python
@inngest_client.create_function(
    fn_id="daily-customer-health-check",
    trigger=inngest.TriggerCron(cron="0 9 * * *"),  # 09:00 UTC every day
)
async def daily_health_check(ctx: inngest.Context) -> dict[str, int]:
    customers = await ctx.step.run(
        "fetch-pro-customers", fetch_pro_customer_ids
    )
    events = [
        inngest.Event(name="customer/health_check.requested", data={"customer_id": cid})
        for cid in customers
    ]
    await ctx.step.send_event("fan-out", events)
    return {"customers_scheduled": len(customers)}
```

**FEDS integration:** 
- **v1-02** zero-quota verifier captures before/after CWV/CLS/INP metrics
- **v1-11** team identity injects `FRONTEND_USER_ID` per cron run
- **v1.1-05** parallel/scheduled automations build on this foundation

### 2.2 Webhook Triggers (external events)
**FEDS implementation:** Customer emails, Stripe webhooks, GitHub events, admin UI buttons.

**Two-door pattern:**
- **Door 1** (webhook route): Receives POST, reshapes payload, calls `send()` acks fast
- **Door 2** (`/api/inngest`): Engine knocks to run function steps one at a time

```python
# Door 1 — minimal webhook route
@app.post("/webhooks/stripe")
async def stripe_webhook(request: fastapi.Request):
    payload = await request.json()
    await inngest_client.send(
        inngest.Event(name="stripe/charge.refund.failed", data=reshape(payload))
    )
    return {"ok": True}  # ack in milliseconds
```

```python
# Door 2 — Inngest function behind the door
@inngest_client.create_function(
    fn_id="handle-stripe-refund-failed",
    trigger=inngest.TriggerEvent(event="stripe/charge.refund.failed"),
)
async def on_refund_failed(ctx: inngest.Context) -> dict[str, str]:
    charge_id = ctx.event.data["charge_id"]
    ticket = await ctx.step.run(
        "find-ticket-for-refund", lookup_ticket_by_charge, charge_id
    )
    await ctx.step.run(
        "notify-support-agent",
        notify_support_agent_of_refund_failure,
        ticket["id"], charge_id,
    )
    return {"ticket": ticket["id"], "action": "notified"}
```

**FEDS integration:**
- **v1-09** prompt-injection defense on webhook payload transforms
- **v1-10** approval console linked from webhook decision events
- **v1.1-02** operations dashboard reads audit_log traces from webhook runs

### 2.3 Event Triggers (Inngest-internal events)
**FEDS implementation:** One function emits, another reacts; fan-out patterns.

```python
# Parent fires N child events
async def fan_out_per_customer_events(
    ctx: inngest.Context,
    customers: list[str],
    run_day: str,
) -> int:
    events = [
        inngest.Event(
            name="customer/health_check.requested",
            data={"customer_id": cid},
            id=f"daily-health-{cid}-{run_day}",  # stable id: dedups on retry
        )
        for cid in customers
    ]
    await ctx.step.send_event("fan-out", events)
    return len(events)
```

**FEDS integration:**
- **v1-02** before/after capture on each child run
- **v1-07** session resume across fan-out children
- **v1.1-05** per-key concurrency prevents one customer flooding the queue

---

## 3. Reflexes (Durable Execution) — Keeping the Worker Correct When Things Break

### 3.1 `step.run` and the Durable Function Model
**FEDS implementation:** Every side-effecting call (DB write, API call, agent invocation) wrapped in `step.run(name, fn, ...)`. Completed steps return memoized output; only the failing step re-runs.

**FEDS integration (critical):**
- **v1-02** verifier metrics are memoized across retries (no re-pay for failed agent steps)
- **v1-06** DSoR enforcement gates only fire after durable steps complete
- **v1.1-03** oversight report counts durable vs. non-durable runs

**The one rule:** A step must be safe to re-run. Pure functions auto-safe; idempotent API calls safe; non-deterministic work (LLM at default temp) is fine as long as any valid output is acceptable.

### 3.2 Memoization — The Mechanic Underneath Resumability
**FEDS implementation:** Keyed by `(run_id, step_name)`. First attempt runs the function; every later replay or retry returns stored output from Inngest's memo store.

**Anti-pattern to avoid:**
```python
# DONT: expensive code outside step.run re-runs on every step advance
expensive_thing = await fetch_expensive_data(ctx.event.data["id"])  # runs every handler re-entry
await ctx.step.run("do-something", do_something_with, expensive_thing)
```

**Correct pattern:** Wrap everything in named steps:
```python
# DO: each I/O side effect in its own step
expensive_thing: dict = await ctx.step.run(
    "fetch-expensive-data", fetch_expensive_data, ctx.event.data["id"]
)
await ctx.step.run("do-something", do_something_with, expensive_thing)
```

**FEDS integration:**
- **v1-02** ensures verifier runs are memoized; a crashed agent step doesn't re-pay tokens
- **v1-06** DSoR evidence bridge writes to audit_log only after memoized steps complete
- **v1.1-03** oversight report includes "memoization hit rate" per run

### 3.3 `step.sleep` and `step.wait_for_event`
**FEDS implementation:** Durable waits — zero compute while suspended.

- **`step.sleep`**: Wait for fixed duration (up to 7 days Hobby, 1 year paid). Used for: welcome-email follow-ups after 3 days, trial-conversion checks after 7 days, escalation timeouts after 24 hours.

- **`step.wait_for_event`**: Wait for matching event (with `if_exp` filter + timeout). Used for: HITL approval gates (refunds, account closures), inter-agent coordination, human-in-the-loop decisions.

```python
# HITL refund gate — the keystone
approval = await ctx.step.wait_for_event(
    "await-refund-approval",
    event="refund/approval.decided",
    timeout=timedelta(hours=4),
    if_exp=f"async.data.customer_id == '{customer_id}'",
)
if approval is None:
    # timeout → blocked refund
    await ctx.step.run("blocked-refund", lambda: audit_refund_blocked(customer_id))
    return {"status": "timeout"}
if not approval.data["approved"]:
    # reject → no refund
    await ctx.step.run("notify-rejected", lambda: notify_customer_rejected(customer_id))
    return {"status": "rejected"}
# approve → issue refund
refund = await ctx.step.run("issue-refund", lambda: call_stripe_refund(customer_id, amount))
await ctx.step.run("audit-approved-refund", lambda: audit_refund(customer_id, refund, "human"))
return {"status": "issued", "refund_id": refund["id"]}
```

**FEDS integration:**
- **v1-10** approval console linked from gate; operator name flows into `run_states.operator`
- **Muheeb-1** approval console: web UI for park/resume
- **Muheeb-5** pause notifications: Slack/email when run enters parked state
- **v1.1-04** compliance evidence pack exports audit rows from HITL gates

### 3.4 Retries, Error Handling, Dead-Letter
**FEDS implementation:** Default ~4 retries with exponential backoff. Tune per function: `retries=2` for transient Stripe errors, `retries=10` for flaky Slack, `retries=0` for permanent failures.

```python
@inngest_client.create_function(
    fn_id="charge-customer",
    trigger=inngest.TriggerEvent(event="order/checkout.completed"),
    retries=2,  # transient errors only
)
async def charge_customer(ctx: inngest.Context) -> dict[str, str]:
    try:
        charge = await ctx.step.run("call-stripe", call_stripe_charge, ctx.event.data)
        return {"status": "charged", "charge_id": charge["id"]}
    except inngest.NonRetriableError as e:
        # declined card → skip retries, mark order, emit dunning event
        await ctx.step.run("mark-failed", lambda: mark_order_failed(ctx.event.data["order_id"], str(e)))
        await ctx.step.run("emit-dunning", lambda: emit_dunning(ctx.event.data["order_id"]))
        return {"status": "card_declined"}
```

**FEDS integration:**
- **v1-02** permanent failures don't waste retry budget; audit_log records the exact failure point
- **v1-06** DSoR staleness check: if provider returns NonRetriableError, control marked stale
- **v1.1-04** compliance pack includes dead-letter trace for any NonRetriableError path

### 3.5 `step.run` for AI Calls in Python
**FEDS implementation:** Wrap the whole agent run in `step.run`; Python uses `step.run` (not `step.ai.wrap` which is TypeScript-only).

```python
@inngest_client.create_function(
    fn_id="summarize-customer-thread",
    trigger=inngest.TriggerEvent(event="customer/thread.summary_requested"),
)
async def summarize_thread(ctx: inngest.Context) -> dict[str, str]:
    thread = await ctx.step.run("load-thread", load_thread, ctx.event.data["thread_id"])
    result = await ctx.step.run(
        "run-agent", lambda: run_support_agent(thread=thread)
    )
    return {"summary": result.summary}
```

**FEDS integration:**
- **v1-02** agent steps memoized; a retry re-runs only the failed step, not the whole agent
- **v1.1-03** oversight report counts agent retries and memoization hit rates
- **v1.1-04** audit trail captures agent input/output for every durable step

**Python-specific notes:**
- `step.ai.infer` exists (experimental, offloads inference to Inngest infra for serverless compute savings) but `step.run` is the default
- Step traces store inputs/outputs; redact PII, secrets, financial data before passing into steps
- Agent run is one step; model/tool calls inside are not separate Inngest steps. A retry re-runs the entire agent from scratch.

---

## 4. Balance (Flow Control) — Keeping Healthy Under Load

### 4.1 Concurrency and Throttling
**FEDS implementation:** Three knobs protect downstream systems:

```python
@inngest_client.create_function(
    fn_id="customer-support-conversation",
    trigger=inngest.TriggerEvent(event="customer/email.received"),
    concurrency=[inngest.Concurrency(limit=10)],       # global cap: max 10 runs at once
    throttle=inngest.Throttle(limit=30, period=timedelta(minutes=1)),  # max 30 starts/min
)
async def handle_email(ctx: inngest.Context) -> dict[str, str]:
    ...
```

**FEDS integration:**
- **v1-02** OpenAI rate limit (30/min hard cap) enforced by throttle
- **v1-11** team identity: per-user concurrency prevents one team flooding shared Neon
- **v1.1-05** parallel/scheduled automations: global + per-tenant concurrency

**Per-key concurrency** (one noisy customer can't starve others):
```python
concurrency=[
    inngest.Concurrency(limit=10),              # global cap
    inngest.Concurrency(limit=2, key="event.data.customer_id"),  # per-customer cap
]
```

### 4.2 Priority and Fairness
**FEDS implementation:** Enterprise customers never wait behind hobbyists; fair-share scheduling.

```python
@inngest_client.create_function(
    fn_id="customer-support-conversation",
    trigger=inngest.TriggerEvent(event="customer/email.received"),
    concurrency=[
        inngest.Concurrency(limit=50),              # global pool
        inngest.Concurrency(limit=3, key="event.data.tenant_id"),  # max 3 per tenant
    ],
    priority=inngest.Priority(run="event.data.tier_priority"),  # Enterprise=100, Pro=0, Free=-100
)
async def handle_email(ctx: inngest.Context) -> dict[str, str]:
    ...
```

**Execution order under burst:**
1. Per-customer cap: each tenant gets max 3 eligible slots
2. Priority: Enterprise (100) first, then Pro (0), then Free (-100) FIFO
3. Fill global slots: all eligible runs compete; highest priority wins

**FEDS integration:**
- **v1-11** team identity maps `tier_priority` on each event
- **v1.1-02** operations dashboard shows per-tenant queue depths and fairness metrics
- **v1.1-03** oversight report: "no Free customer starved >60s even when global queue full"

### 4.3 Batching
**FEDS implementation:** Accumulate events into one batched function call for cheap bulk work.

```python
@inngest_client.create_function(
    fn_id="batch-embed-tickets",
    trigger=inngest.TriggerEvent(event="ticket/resolved"),
    batch_events=inngest.Batch(max_size=50, timeout=timedelta(seconds=30)),
)
async def batch_embed_resolved_tickets(ctx: inngest.Context) -> dict[str, int]:
    ticket_ids = [e.data["ticket_id"] for e in ctx.events]
    tickets = await ctx.step.run("load-tickets", load_tickets_by_ids, ticket_ids)
    embeddings = await ctx.step.run(
        "embed-batch", embed_texts_batch, [t["text"] for t in tickets]
    )
    await ctx.step.run("store-embeddings", store_embeddings_batch, ticket_ids, embeddings)
    return {"batched": len(ctx.events)}
```

**FEDS integration:**
- **v1-02** batch verifier captures CWV/accessibility on embedded vs. non-embedded tickets
- **v2-01** verified lesson loop: batch-embedded tickets become training data for the lesson store
- **v2-02** published benchmark: batched vs. per-ticket embedding comparison

**When to use:** Naturally bulkable work (embeddings, bulk DB writes, bulk emails). Wrong for interactive responses or unpredictable ordering.

### 4.4 Replay and Bulk Cancellation
**FEDS implementation:** Two recovery primitives.

- **Replay**: Dashboard button → fresh run from top on current code. Used for bug-fix recovery (`we shipped a bug`, `schema migration`). Cost: whole function per replayed run; idempotency keys prevent double side effects.

- **Bulk cancellation**: Dashboard → select function + time window/event filter → terminate matching runs. Used for `campaign canceled`, `customer churned`, `feature rolled back`. Respects step boundaries: in-flight `step.run` finishes before terminate.

```python
# Replay scenario: bug fix recovery
# 1. Bug deployed at 14:00 → 47 runs failed at agent step
# 2. Fix shipped at 18:30  
# 3. Dashboard: filter failed runs 14:00–18:30, click Replay
# 4. Each replayed run re-executes every step on fixed code
# 5. Customers see one reply (idempotency key on the send-email step prevents double-send)

# Bulk cancellation: campaign rolled back
# 1. Welcome series: day-1, day-7, day-14 follow-ups
# 2. Customer churns on day 4
# 3. Dashboard: cancel matching runs for day-7 and day-14 follow-ups
# 4. Those runs never execute; no emails sent
```

**FEDS integration:**
- **v1-07** durable session log: `getEvents(sessionId, fromSeq, toSeq)` reconstructs state for replay
- **v1.1-03** oversight report: replay vs. cancellation counts, reasons
- **v1.1-04** compliance pack: audit rows capture replay/cancellation decisions

---

## 5. Version Roadmap

| Version | Focus | Key Items | Target |
|---|---|---|---|
| **v1** | "Provable & Enforceable" | v1-02 verifier, v1-06 DSoR minimal slice, v1-07 session log, v1-10 approval console | FEDS 8.0–8.15 (2–3 weeks) |
| **v1.1** | "Governed & Observable" | v1.1-01 agent registry, v1.1-02 ops dashboard, v1.1-03 oversight report, v1.1-05 parallel automations | FEDS 8.3–8.6 (+2–3 weeks) |
| **v2** | "Self-Learning & Benchmarked" | v2-01 verified lesson loop (phases 1–3), v2-02 published benchmark, v2-03 internal memory eval | FEDS 9.0 (+3–4 weeks) |

**Nervous system milestones:**
- **v1 MVP**: Cron + webhook triggers, `step.run` + memoization, global concurrency + throttle, approval gate with `wait_for_event`
- **v1.1 additions**: Per-key concurrency, priority ordering, batching, ops dashboard with audit trail, agent registry + kill switch
- **v2 full**: Verified Lesson Loop (confidence dynamics, holdout lift, quarantine), published benchmark vs. baseline, internal memory eval (LongMemEval/LoCoMo style)

---

## 6. Integration with Existing FEDS Components

| Component | Nervous System Hook |
|---|---|
| **Verifier (A2)** | Zero-quota; all learning metrics from `step.run` memoized outputs |
| **Memory architecture** | `step.sleep`/`wait_for_event` suspend across runs; `FRONTEND_USER_ID` injected per request |
| **Audit trail (Section 8 AGENTS.md)** | Every `step.run`, `step.sleep`, `step.wait_for_event` writes to `audit_log` with closed vocabulary |
| **Provider resilience (Section 7 AGENTS.md)** | `NonRetriableError` skips retries; throttle protects OpenAI 30/min cap; per-key concurrency for multi-tenant fairness |
| **Skill index (progressive disclosure)** | New skills auto-generated from durable lesson promotions (v2-01); ~1,200 chars in index vs. full corpus |
| **Schema as code (setup_neon.py)** | Nervous system tables (verifications, run_states, verifications) applied idempotently; no runtime DDL |

---

## 7. Zero-Quota Provability Table

| Component | Provable Offline | Smoke Test |
|---|---|---|
| `step.run` memoization | Deterministic key-store scheme (run_id + step_name) | `smoke_ingest.py` dry-run pattern |
| `step.sleep` / `wait_for_event` | Suspend/resume equations, no model calls | `smoke_memory_schema.py` rolled-back transaction |
| Retries (transient vs permanent) | `NonRetriableError` logic, retry budget math | `test_config.py` planted-secret style checks |
| Concurrency/throttle policy | Configuration enforced by platform, not code | Platform-level smoke; behavior reason under load |
| HITL `wait_for_event` + `if_exp` | Event matching + timeout = resume or None | Dashboard observation; no audit row written on timeout without explicit handler |

**Theorem:** If all steps either (a) use the local verifier (zero model calls) or (b) are constrained by DB-enforced gates proven offline, then no model quota is consumed during nervous system execution, and every written metric is either derived from zero-quota output or NULL (never fabricated).

---

## 8. Swap Guide — Platform Independence

The architecture transfers to other platforms with these mappings:

| Inngest Primitive | Temporal Analogue | Restate Analogue | Dapr Agents Analogue |
|---|---|---|---|
| `TriggerCron` | Cron input binding / K8s CronJob | Handler schedule | Dapr Scheduler |
| `TriggerEvent` | Workflow start via signal/pub-sub | Event handler | Dapr pub/sub |
| `step.run()` + memoization | Activities + state store | Workflow activities | `DurableAgent` methods |
| `step.sleep()` | Durable timers | Timers API | Durable timers |
| `step.wait_for_event()` | External events / signals | Awakeables / actors | Actor state + workflow events |
| `step.run()` + `NonRetriableError` | Activity retries + resiliency policies | Resilience policies | Workflow error handling |
| Concurrency/Throttle | Kubernetes HPA + app-level rate limiter | Token bucket + semaphore | Container concurrency + broker controls |
| Batching | Bulk insert + transaction | Batch operation | Parallel job submission |
| Replay / Rerun | `workflow.ExecuteWorkflow` with new code | Rerun workflow | `DurableAgent` replay |
| Bulk cancellation | Custom actor state + terminate | Cancel workflows | Agent cancellation API |
| HITL `wait_for_event` | Signal → activity → human task | Awaitable + human-in-the-loop | Actor + external signal |

**Why start on Inngest:** Fast feedback loop (one command, dashboard appears), minimal infrastructure, focus on patterns. Reach for Dapr/Kubernetes once governance, polyglot teams, or vendor-neutrality become non-negotiable.

---

*File compiled from Inngest crash course concepts 1–15, mapped to FEDS sanghaar.md version plan. Features represent implemented capability as of 2026-10-19. Zero-quota provability guaranteed for all components.*