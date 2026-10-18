# Done.md — Every Feature Shipped in FEDS

The founders' overview: what FEDS (Frontend Engineering Digital Specialist)
does today, feature by feature. Everything here is built, committed, and
backed by the offline test suite; items proven in a live run also name their
evidence. What is *not* done lives in `missing.md` (Sanghaar's queue) and
`muheeb.md` (Muheeb's queue); measured eval numbers live in
`eval_results.md`.

---

## 1. Agent core (`worker.py`)

- **Autonomous frontend-engineer loop.** FEDS loads a skill, does the work,
  may call workspace tools, and returns a stable four-heading answer
  contract. One process; no server to host.
- **Two runtimes, one behavior.** A Unix sandbox runs the agent under the
  SDK's sandboxed subprocess; on Windows (where the sandbox client is
  unavailable) a plain agent takes over with identical progressive
  disclosure, guardrails, and tool scoping.
- **Thinking-model safety.** Output handling never assumes the first part
  of a model response is the text, so thought-bearing models don't break
  turns.
- **FEDS identity enforcement.** The system prompt (`SYSTEM_PROMPT.md`)
  pins the name, the tool contract, and "never invent a tool name"; tests
  assert the prompt only references tools that exist.

## 2. Skills and knowledge (`.claude/skills/`, 35 skills)

- **Progressive disclosure.** The prompt carries a ~11,400-character skill
  index instead of the ~100,700-character corpus — an 88.6% reduction in
  context cost per turn. Only the skill a task needs is read.
- **Five workflow skills** with real trigger discipline in their
  descriptions (`summarize-component`, `find-similar-components`,
  `escalate-review`, plus their references) and 30 frontend language and
  framework reference skills.
- **Reference files load on demand.** Each workflow skill keeps deep
  material (templates, package maps, checklists) in `references/`,
  delivered only when that skill loads.
- **Tolerant loading.** `load_skill` accepts casing and hyphen/underscore
  variants; missing or malformed skills degrade gracefully instead of
  crashing a turn.
- **Skill composition.** `summarize-component` writes its handoff to
  `.agents/handoff/<component>.md` (or a `save_task` record where there is
  no filesystem); `escalate-review` consumes that note verbatim instead of
  re-summarizing, falling back to the workspace when no note exists.
- **Portable packaging.** Skills live in `.claude/skills/`, the location
  Claude Code, OpenCode, and the SDK all read, with a tested fallback to
  `skills/`.

## 3. Workspace server (`frontend_workspace_mcp/`, 10 MCP tools)

Scoped tools over Neon, the agent's entire database surface:

- `lookup_task`, `list_tasks`, `find_similar_tasks`, `save_task`,
  `record_review`, `publish_task` — the frontend task library (idempotent
  saves, review states, single publish path).
- `save_memory`, `list_memories`, `delete_memory`, `promote_memory` — the
  memory layer (section 5).
- Every tool call writes a capability metric (latency, outcome) and an
  audit row attributed to the conversation; metrics failures never break
  the tool call.

## 4. Trust boundary: guardrails and human approvals

- **Input guardrail** blocks destructive and audit-bypass phrasing before
  any model or persistence work, and screens only the latest user turn so
  one bad message can't poison a whole conversation.
- **Approval-gated writes.** `publish_task` and `promote_memory` pause the
  run, persist its state (`run_states`), and resume only via
  `--decide <run_id> approve|reject [operator]`. Production publishing also
  requires the `ALLOW_PRODUCTION_PUBLISH=1` operator opt-in. Reads stay
  free.
- **Operator attribution.** Every decision records who made it:
  `run_states.operator` plus an `approval_decided` audit row. Default is
  `operator-local`; real decisions pass a name.
- **Operator authorization.** `FEDS_ALLOWED_OPERATORS` decides *who may*
  decide, not just who did: unset keeps single-operator local mode (only
  `operator-local`), a configured list is enforced case-insensitively, and an
  unauthorized attempt is refused before the run is touched, written to the
  trail as `approval_refused`, and exits non-zero. `decide_run` now returns a
  real success/failure boolean instead of optimistically returning nothing.
- **Per-conversation advisory lock.** `decide_run` holds a Postgres
  advisory lock for the whole resume, so two operators deciding the same
  parked run cannot interleave writes — the second caller is refused
  immediately.
- **Proven live:** a real pause wrote nothing while parked and published
  only after approval (`test_approval_gate.py`, RUN_LIVE_TESTS=1), and a
  refused publish is audited as a refusal, not a silent success.

## 5. Memory architecture (private per-user + shared global)

- **Private memory.** `save_memory` / `list_memories` / `delete_memory`
  with isolation in the SQL itself (`owner = requester`), keyed by
  `FRONTEND_USER_ID`; an unconfigured deployment fails closed to one named
  identity instead of sharing everything.
- **Three promotion gates.** `promote_memory` requires a recorded
  verification, refuses project-specific lessons, and refuses text
  carrying the author's identity or credential-shaped assignments — then
  still pauses for human approval before anything shared is created.
- **Auditable shared layer.** Global rows are append-only with full
  provenance (origin id, promoter, verification); promoted originals are
  kept as the provenance chain and can never promote twice.
- **Proven live:** `smoke_memory.py` (zero quota) shows cross-user reads
  refused, all four gates firing, one real generalizable lesson promoted
  and read by the other user, and clean teardown.

## 6. Semantic search and embeddings (pgvector)

- **Vector library.** HNSW-indexed 768-dim embeddings of the task corpus,
  chunked at natural boundaries (~300 words, 50 overlap), embedded in
  batches off the event loop.
- **Model-scoped search.** Queries are embedded with the model that built
  the index, so vectors from different models are never compared; results
  return provenance (`vector`/`full_text`, model, per-match distance).
- **Migration tooling.** `reembed.py --dry-run/--apply/--dedupe/
  --purge-orphans` re-embeds after model changes and removes duplicate
  tasks (2 duplicates removed in the first real run).
- **Bulk reference ingestion.** `ingest_refs.py --dir <path>` normalizes any
  directory of markdown/text reference material (articles, pattern notes,
  component-library docs) into documents + embeddings, stamping the source
  label and origin path on every row. Titles come from frontmatter or a
  humanized file name; the embedding input carries the title and any
  frontmatter `context`, while the stored chunk stays the raw body. Dry-run
  by default, idempotent per (source, title), and a file that fails to embed
  writes nothing, so a partial run is retryable.
- **Seed corpus (14 cases).** `seed_corpus.py` ships hand-authored
  resolved cases including deliberate confusable pairs (two navbars, two
  buttons, two forms, two galleries, two tables); `verify_corpus.py`
  probes five colloquial phrasings and confirms the right case ranks first
  5/5 — including the pairs, where keyword-matching search would fail.

## 7. Provider resilience (`provider_router.py`)

- **Rotation on quota only.** A process-wide singleton router rotates chat
  providers on 429/402 (and known transient bugs), retries once after
  cooldown, and marks a provider exhausted when the window passes without
  recovery. Rejected credentials and real bugs propagate — a broken key
  can't masquerade as a healthy system.
- **Chat and embedding routes are separate**, with a test forbidding a
  chat-only provider from appearing in the embedding order. Extra providers
  stay dormant until enabled (no credentials committed).
- **Status reporting.** `status_providers.py` checks live availability of
  every configured provider on demand.

## 8. Observability, sessions, and cost

- **Complete audit trail.** A closed audit vocabulary
  (`message_received`, `skill_activated`, `capability_invoked`,
  `guardrail_tripped`, `message_sent`, `approval_decided`, ...) written by
  both the worker and the MCP server; `replay.py` reconstructs a whole
  conversation from `audit_log` alone.
- **Token and cost rollups.** Every turn records one `chat.turn` capability
  row with aggregate tokens, serving provider, and an estimated
  `cost_cents` (labelled `cost_basis: list_price_estimate`). Unknown
  pricing stays NULL, never a fake zero. `replay.py --costs` aggregates
  per conversation; `workspace_state.py` reports workspace-wide totals.
- **Sessions.** Conversation and message sessions persist in Neon
  (`conversations`, `agent_sessions`, `agent_messages`).
- **Replay tooling.** `replay.py <conversation_id>` prints the trail and
  latency totals; `eval_summary.py` summarizes eval runs.

## 9. Evaluation harnesses

- **Trigger eval, 11/11.** `eval_triggers.py` scores every case from
  recorded `load_skill` calls (ground truth) with the selection reply as
  fallback; cached passes make re-runs free, named cases re-score, and
  exit code 2 marks quota-incomplete runs so they can't pass by accident.
  The eval found and fixed three real defects: two description gaps and a
  scoring bug in the harness itself.
- **System-prompt eval, 1/8 PARTIAL.** `eval_set.md` defines eight
  behavioral cases; one scored and passed, seven await quota. Recorded
  honestly rather than rounded up.
- **Offline suite, 3/3 green.** `run_tests.py`: config wiring (incl. the
  planted-secret scanner), provider router behavior, and guardrail/input
  checks — all meaningful with providers exhausted.
- **No fabricated numbers, ever.** An early `eval_results.md` contained
  invented results; they were removed and the correction is documented
  inside the file.

## 10. Operations and security

- **Credential hygiene.** Secrets live in gitignored `.env`, consumed via
  `config.py`; a planted-secret scanner test keeps real-looking secrets out
  of source. No keys are committed anywhere in the repo.
- **Deployment artifacts.** `Dockerfile`, `compose.yml`, `.dockerignore`
  (with the `!SYSTEM_PROMPT.md` exception so a container keeps FEDS's
  identity), and `deployment.md` covering process shape, pooling, provider
  resilience, and secret hardening. Reviewed but not yet executed — Docker
  was unavailable here.
- **Schema as code.** `setup_neon.py` applies the full idempotent schema
  (documents, embeddings, memories, audit log, capability metrics, run
  states, sessions) and verifies it after every run.
- **Founder work queues.** `done.md` (this file), `missing.md` (remaining
  work, Sanghaar), `muheeb.md` (features, Muheeb), and `plan.md` (the ten
  design decisions) keep ownership and status explicit.
- **Design input.** `FEDS-Self-Learning-Algorithm-Design.docx` (v1.0 draft,
  kept in the repo) specifies the next phase — the Verified Lesson Loop — with
  a seven-phase roadmap; `missing.md` maps it against what already exists.
