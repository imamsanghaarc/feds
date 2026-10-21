# FEDS — Frontend Engineering Digital Specialist
## Features & Differentiators

---

### 1. Agent Core & Runtime
- **Autonomous frontend-engineer loop** — Single process, no server to host; loads skills, does work, returns stable four-heading answer contract
- **Two runtimes, one behavior** — Unix sandbox under SDK; Windows fallback with plain agent that maintains identical progressive disclosure, guardrails, and tool scoping
- **Thinking-model safety** — Output handling never assumes the first part of a model response is text; thought-bearing models don't break turns
- **FEDS identity enforcement** — SYSTEM_PROMPT.md pins the name, tool contract, and "never invent a tool name"; tests assert prompt only references existing tools

### 2. Skills & Knowledge System
- **Progressive disclosure** — ~11,400-char skill index vs ~100,700-char corpus: 88.6% reduction in context cost per turn; only needed skills are loaded
- **5 workflow skills with trigger discipline** — `summarize-component`, `find-similar-components`, `escalate-review` plus references; 30+ frontend language/framework reference skills
- **Reference files load on demand** — Each workflow skill keeps deep material (templates, package maps, checklists) in `references/`, delivered only when that skill loads
- **Tolerant loading** — `load_skill` accepts casing and hyphen/underscore variants; missing/malformed skills degrade gracefully
- **Skill composition** — `summarize-component` writes handoff notes; `escalate-review` consumes them verbatim, falling back to workspace when none exist
- **Portable packaging** — Skills live in `.claude/skills/`, read by Claude Code, OpenCode, and SDK; tested fallback to `skills/`

### 3. Workspace MCP Server (10 Tools)
- **Task library** — `lookup_task`, `list_tasks`, `find_similar_tasks`, `save_task`, `record_review`, `publish_task` — idempotent saves, review states, single publish path
- **Memory layer** — `save_memory`, `list_memories`, `delete_memory`, `promote_memory` — section 5 memory management
- **Capability metrics** — Every tool call writes latency, outcome, and audit row attributed to conversation; metric failures never break the tool call
- **Fail-closed MCP server** — Defaults to stdio; refuses non-loopback bind without `MCP_ALLOW_REMOTE=1`, preventing approval bypass over network

### 4. Trust Boundary & Guardrails
- **Input guardrail** — Blocks only attempts to subvert FEDS's trust boundary (audit bypass, production publication); screens only latest user turn
- **Approval-gated writes** — `publish_task` and `promote_memory` pause run, persist state via `run_states`, resume only via `--decide <run_id> approve|reject [operator]`
- **Production publishing opt-in** — `publish_task` to `production` additionally requires `ALLOW_PRODUCTION_PUBLISH=1` (deliberately unset in compose.yml)
- **Operator attribution** — Every decision records who made it: `run_states.operator` plus `approval_decided` audit row; default is `operator-local`
- **Operator authorization** — `FEDS_ALLOWED_OPERATORS` decides who may decide; unset = single-operator local mode only; unauthorized attempts refused and audited as `approval_refused`
- **Per-conversation advisory lock** — Postgres advisory lock for whole resume prevents two operators deciding same parked run from interleaving writes
- **Proven live** — Real pause/write patterns tested and audited; refusal paths exercised in live tests

### 5. Memory Architecture
- **Private per-user memory** — Isolation in SQL itself (`owner = requester`), keyed by `FRONTEND_USER_ID`; unconfigured MCP server refuses to serve rather than collapsing users into one bucket
- **Three automated promotion gates** — Verification recorded, lesson flagged `metadata.generalizable` (not `project_specific`), sanitized body free of identity/credential/code
- **Shared layer is append-only** — Global rows constrained to `'-'` sentinel owner, require promotion attribution; provenance carries origin id, promoter, verification, source/shared sizes
- **Least-privilege runtime role** — `setup_neon.py` provisions restricted `feds_app` login (no ownership, DDL, role/db admin, or RLS bypass); worker and MCP server connect with it
- **Proven live** — `smoke_memory.py`, `smoke_memory_schema.py`, `smoke_app_role.py` exercise full end-to-end rules without quota

### 6. Semantic Search & Embeddings (pgvector)
- **HNSW-indexed 768-dim embeddings** — Task corpus chunked at natural boundaries (~300 words, 50 overlap), embedded in batches off event loop
- **Model-scoped search** — Queries embedded with model that built index; vectors from different models never compared; results return provenance (`vector`/`full_text`, model, per-match distance)
- **Migration tooling** — `reembed.py --dry-run/--apply/--dedupe/--purge-orphans` re-embeds after model changes, removes duplicates (2 removed in first real run)
- **Bulk reference ingestion** — `ingest_refs.py --dir <path>` normalizes markdown/text into documents+embeddings, stamps source label and origin path; titles from frontmatter or humanized file name
- **Seed corpus (14 cases)** — Hand-authored resolved cases including deliberate confusable pairs; `verify_corpus.py` confirms right case ranks first 5/5 including pairs where keyword search would fail

### 7. Provider Resilience
- **Rotation on quota only** — Router rotates chat providers on 429/402 (known transient bugs); retries once after cooldown; marks provider exhausted when window passes without recovery
- **Separate chat/embedding routes** — Test forbids chat-only provider appearing in embedding order; extra providers dormant until enabled
- **Dual Gemini credentials** — `GEMINI_FALLBACK_API_KEY` as `gemini-fallback` provider for both chat and embeddings; one key running out hands work to the other; stored vector label never changes
- **Status reporting** — `status_providers.py` checks live availability of every configured provider on demand, skipping unconfigured ones
- **Proven live failover** — 2026-10-19: primary key returned genuine 429; router served turn from `gemini-fallback` — first real, non-stub failover

### 8. Observability & Cost
- **Complete audit trail** — Closed vocabulary with CHECK constraint as source of truth for actions (`message_received`, `skill_activated`, `capability_invoked`, `message_sent`, `guardrail_tripped`, `refund_issued`, `refund_blocked`, `corpus_seeded`); decision events (`approval_decided`, `approval_refused`, `approval_pending`, `started`, `completed`) inside payloads
- **Token and cost rollups** — Every turn records `chat.turn` row with aggregate tokens, serving provider, estimated `cost_cents` (labelled `cost_basis: list_price_estimate`); unknown pricing stays NULL, never fake zero
- **Session persistence** — Conversation and message sessions in Neon (`conversations`, `agent_sessions`, `agent_messages`)
- **Replay tooling** — `replay.py <conversation_id>` prints trail and latency totals; `eval_summary.py` summarizes eval runs

### 9. Evaluation Harnesses
- **Trigger eval, 11/11** — `eval_triggers.py` scores every case from recorded `load_skill` calls (ground truth); cached passes make re-runs free; exit code 2 marks quota-incomplete runs (never report as pass)
- **System-prompt eval** — `eval_set.md` defines 8 behavioral cases; all 8 have real single-run results; 2 failures drove fixes (mode instability, guardrail contradiction), now pinned offline
- **Offline suite, 3/3 green** — `run_tests.py`: config wiring, provider router behavior, guardrail/input checks
- **Honesty guarantee** — No fabricated numbers; early `eval_results.md` contained invented results; they were removed and correction documented
- **Quick scoreboard** — `uv run python eval_summary.py`

### 10. Operations & Security
- **Credential hygiene** — Secrets in gitignored `.env`, consumed via `config.py`; planted-secret scanner test keeps real-looking secrets out of source; no keys committed in repo
- **Deployment artifacts** — `Dockerfile`, `compose.yml`, `.dockerignore` (with `!SYSTEM_PROMPT.md` exception); `deployment.md` covering process shape, pooling, provider resilience, secret hardening
- **Schema as code** — `setup_neon.py` applies full idempotent schema (conversations, documents, embeddings, audit log, capability metrics, memories, run states, sessions); approval table created here
- **Zero-quota live proofs** — `smoke_mcp.py`, `smoke_memory.py`, `smoke_ingest.py`, `smoke_operator_auth.py` exercise real Neon behavior without spending model quota
- **Founder work queues** — `done.md`, `sanghaar.md`, `muheeb.md`, `plan.md` keep ownership and status explicit
- **Design input** — `FEDS-Self-Learning-Algorithm-Design.docx` (v1.0 draft) specifies Verified Lesson Loop seven-phase roadmap

### Key Differentiators vs. Other Frontend Agents
1. **Governance by design** — Approval gates, audit records, scoped credentials are built-in, not tacked on
2. **Verified outcome promotion** — Lessons promoted only after automated verification and sanitization gates
3. **Model-agnostic vector search** — Embeddings scoped to their source model; never compare across models
4. **Dual-database architecture** — Schema owner vs. restricted runtime role; all DDL through setup migrations only
5. **Progressive disclosure skills** — 88.6% context reduction vs loading entire corpus
6. **Live-zero-quota provability** — Every major feature proven via offline smoke tests without model quota
7. **Honest evaluation culture** — Fabricated results removed; exit code 2 explicitly means "incomplete, not failed"
8. **Founder transparency** — Work queues (`done.md`, `sanghaar.md`, `muheeb.md`) make ownership and status explicit

---
*Compiled from done.md, AGENTS.md, eval_results.md, and related documentation. Features represent implemented capability as of 2026-10-19.*

---
## Future Enhancements (Planned)

### Near-Term (Next 3 Months)
- **Verified Lesson Loop v1.0** — Implement the seven-phase roadmap from `FEDS-Self-Learning-Algorithm-Design.docx`; enable automatic lesson promotion with full provenance tracking and company design system learning
- **Core Web Vitals & Accessibility Auditing** — Built-in before/after CWV/CLS/INP measurement for every task; automated accessibility compliance checks with remediation guidance
- **Multi-Model Vector Reconciliation** — Bridge vectors across different embedding models with transformation layers; enable search across model-agnostic task corpus
- **Fine-Grained RBAC for MCP Tools** — Role-based access control beyond the current `feds_app` least-privilege role; per-operator tool permitting/denying

### Mid-Term (Next 6-12 Months)
- **Browser Automated Testing** — Integrated Playwright/Selenium harness for automated before/after CWV/accessibility measurement; visual regression detection
- **Enterprise Design System Onboarding** — Guided onboarding for companies to import their component library, style guide, and design token inventory; automatic skill generation from design system docs
- **Collaborative Workspaces** — Multi-operator sessions with shared memory zones, conflict resolution, and combined audit trails; true team FEDS mode
- **Plugin Ecosystem** — Public plugin API for third-party skills and integrations; versioned plugin registry with compatibility scoring
- **Real-time Collaboration** — WebSocket-based real-time editing and task tracking; live cursor presence and co-editing of generated UI components

### Long-Term (12+ Months)
- **AI-Employee Marketplace** — Publish and discover FEDS skills as monetized assets; rating system, usage analytics, and credential verification
- **Cross-Language Framework Support** — Automatic translation of frontend solutions between React, Vue, Svelte, and Solid; shared component marketplace
- **Advanced Analytics Dashboard** —Workspace-wide analytics on skill usage, token consumption, cost tracking, and outcome metrics; predictive staffing recommendations
- **Edge Deployment** — FEDS functions deployed at the edge with sub-100ms cold starts; local-first operation with offline capability and sync when connectivity restores
- **Generative Design-to-Code** — AI-assisted design system evolution; automatic component generation from Figma/Sketch files with version-aware output

### Research & Experimental
- **Neuro-symbolic Reasoning** — Integration of symbolic logic with LLM reasoning for guaranteed constraint satisfaction in frontend code
- **Quantum-Ready Architecture** — Architecture patterns that will translate to quantum-assisted optimization for frontend problem-solving
- **Automated Accessibility Law Compliance** — WCAG 2.2/EN 301 549 automated compliance checking with remediation prioritization by jurisdiction
- **Zero-Trust Network Architecture** — Full zero-trust network mode for FEDS deployment in highly regulated environments

*Roadmap subject to change based on market feedback, quota availability, and founder prioritization. Progress tracked in `sanghaar.md` and `plan.md`.*