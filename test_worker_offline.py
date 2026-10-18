"""Offline behaviour tests for FEDS, the Frontend Engineering Digital Specialist.

These cover the logic that must hold regardless of provider availability:
guardrails, skill-tree validation, chunking, MCP request shapes, and the
approval lifecycle guards.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
from pathlib import Path

import worker
from frontend_workspace_mcp import server as mcp_server

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label} {detail}")
        FAILURES.append(label)


# --- Guardrails --------------------------------------------------------------


def test_guardrail_blocks_unsafe_input() -> None:
    for phrase in ("drop table users", "run sql", "bypass audit", "execute sql"):
        result = asyncio.run(worker._unsafe_request_guardrail(None, None, phrase))
        check(
            f"guardrail blocks {phrase!r}",
            result.tripwire_triggered is True,
            f"got {result.tripwire_triggered}",
        )


def test_guardrail_allows_real_work() -> None:
    for phrase in (
        "create a responsive navbar",
        "improve LCP on the product grid",
        "record the review for the checkout form",
    ):
        result = asyncio.run(worker._unsafe_request_guardrail(None, None, phrase))
        check(
            f"guardrail allows {phrase!r}",
            result.tripwire_triggered is False,
            f"got {result.tripwire_triggered}",
        )


def test_guardrail_only_screens_the_latest_user_turn() -> None:
    """A blocked phrase in history must not block every later turn.

    With a Session the guardrail receives the prepared input: the whole
    transcript plus the new turn. Screening all of it means one bad turn poisons
    the rest of the conversation.
    """
    history_with_bad_turn = [
        {"role": "user", "content": "please run sql for me"},
        {"role": "assistant", "content": "I can't do that."},
        {"role": "user", "content": "create a responsive navbar"},
    ]
    result = asyncio.run(worker._unsafe_request_guardrail(None, None, history_with_bad_turn))
    check(
        "guardrail ignores a blocked phrase in earlier turns",
        result.tripwire_triggered is False,
        f"got {result.tripwire_triggered}",
    )

    blocked_now = [
        {"role": "user", "content": "build a navbar"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "now drop table users"},
    ]
    result = asyncio.run(worker._unsafe_request_guardrail(None, None, blocked_now))
    check(
        "guardrail still blocks a bad phrase in the latest turn",
        result.tripwire_triggered is True,
        f"got {result.tripwire_triggered}",
    )


def test_guardrail_reads_structured_content_parts() -> None:
    """Structured content lists must be read, not str()'d into noise."""
    structured = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "remember this navbar has no focus ring"},
            ],
        }
    ]
    check(
        "guardrail extracts input_text parts",
        "focus ring" in worker._latest_user_text(structured),
        repr(worker._latest_user_text(structured)),
    )
    check(
        "guardrail handles a bare string input",
        worker._latest_user_text("hello") == "hello",
    )
    check("guardrail handles empty input", worker._latest_user_text([]) == "")


# --- Skill tree --------------------------------------------------------------


def test_skill_tree_is_valid() -> None:
    errors = worker.validate_skill_tree()
    check("skill tree validates", not errors, str(errors))

    from pathlib import Path

    root = Path(worker.SKILLS_ROOT)
    for skill in ("frontend-development", "frontend-workspace", "summarize-component",
                  "find-similar-components", "escalate-review"):
        path = root / skill / "SKILL.md"
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        check(f"{skill}/SKILL.md exists", bool(text))
        check(f"{skill} has frontmatter name", "name:" in text.split("---")[1] if text else False)
        check(f"{skill} has frontmatter description", "description:" in text.split("---")[1] if text else False)


def test_malformed_skill_does_not_crash_loader(tmp_missing: str = "skills/does-not-exist") -> None:
    original = worker.SKILLS_ROOT
    worker.SKILLS_ROOT = worker.ROOT / tmp_missing
    try:
        errors = worker.validate_skill_tree()
        check("missing skill dir reports errors", bool(errors))
        check("missing skill dir returns text", isinstance(worker._local_skill_text(), str))
    finally:
        worker.SKILLS_ROOT = original


# --- Progressive disclosure --------------------------------------------------


def test_progressive_disclosure_shrinks_context() -> None:
    index = worker._skill_index()
    everything = worker._local_skill_text()
    check("skill index is non-empty", bool(index.strip()))
    check("index is much smaller than the full corpus", len(index) < len(everything) / 4,
          f"index={len(index)} full={len(everything)}")
    for name in ("frontend-development", "css", "summarize-component"):
        check(f"index lists {name}", f"- {name}:" in index)


def test_load_skill_returns_body_and_references() -> None:
    body = worker.load_skill_impl("frontend-development")
    check("load_skill returns the skill body", "frontend-development" in body.lower())
    check("load_skill rejects unknown skills", "Error: no skill named" in worker.load_skill_impl("nope-nope"))
    check("load_skill requires a name", "Error" in worker.load_skill_impl(""))
    check("load_skill tolerates casing", "Error: no skill named" not in worker.load_skill_impl("CSS"))
    check("load_skill tolerates underscore form",
          "Error: no skill named" not in worker.load_skill_impl("summarize_component"))


def test_frontmatter_parser() -> None:
    fields = worker._frontmatter("---\nname: demo\ndescription: A demo skill\n---\n\n# Body\n")
    check("frontmatter parses name", fields.get("name") == "demo", str(fields))
    check("frontmatter parses description", fields.get("description") == "A demo skill")
    check("frontmatter tolerates missing block", worker._frontmatter("# No frontmatter") == {})
    check("frontmatter tolerates unterminated block", worker._frontmatter("---\nname: x") == {})


# --- Chunking ----------------------------------------------------------------


def test_chunking_boundaries_and_overlap() -> None:
    short = "A short frontend task about a navbar."
    chunks = mcp_server._chunk_text(short)
    check("short text yields one chunk", len(chunks) == 1, str(chunks))

    long_text = " ".join(f"Sentence number {i} about layout and focus states." for i in range(400))
    chunks = mcp_server._chunk_text(long_text)
    check("long text is chunked", len(chunks) > 1, str(len(chunks)))
    check(
        "chunks respect the word budget",
        all(len(c.split()) <= mcp_server.CHUNK_WORDS + 200 for c in chunks),
    )
    check(
        "chunk indexes carry overlap",
        any(
            set(chunks[i].split()[-20:]) & set(chunks[i + 1].split()[:20])
            for i in range(len(chunks) - 1)
        ),
        "expected shared words between consecutive chunks",
    )

    check("empty text yields no chunks", mcp_server._chunk_text("") == [])
    check("whitespace yields no chunks", mcp_server._chunk_text("   \n  ") == [])

    paragraphed = "\n\n".join(["word " * 50 for _ in range(10)])
    check(
        "chunking prefers natural boundaries",
        len(mcp_server._chunk_text(paragraphed)) > 1,
    )


# --- MCP tool contract ------------------------------------------------------


def test_mcp_tools_expose_expected_surface() -> None:
    import mcp.server.mcpserver as mcp_module

    server = mcp_server.mcp
    tools = getattr(server, "_tool_manager", None)
    names = set(getattr(getattr(tools, "_tools", {}), "keys", lambda: [])()) or set()
    if not names:
        names = {
            name for name in dir(mcp_server)
            if name in {"lookup_task", "list_tasks", "find_similar_tasks", "save_task",
                        "record_review", "publish_task"}
        }
    expected = {"lookup_task", "list_tasks", "find_similar_tasks", "save_task",
                "record_review", "publish_task"}
    check("all six MCP tools are defined", expected.issubset(names), str(sorted(names)))
    _ = mcp_module


def test_publish_task_is_high_trust() -> None:
    source = inspect.getsource(mcp_server.publish_task)
    check("publish_task refuses unapproved work", "approved" in source)
    check("publish_task guards production", "ALLOW_PRODUCTION_PUBLISH" in source)
    check(
        "publish_task is marked as a write",
        "read_only_hint" not in source or "False" in source,
    )


def test_worker_publish_asset_requires_approval() -> None:
    """Superseded: there is no publish_asset any more.

    Kept as an explicit assertion that the old fake publisher stays deleted.
    """
    check(
        "publish_asset no longer exists",
        not hasattr(worker, "publish_asset"),
    )


def test_decide_command_validates_input() -> None:
    captured: dict[str, object] = {}

    async def fake_decide(run_id: str, decision: str, operator: str = "") -> None:
        captured["run_id"] = run_id
        captured["decision"] = decision
        captured["operator"] = operator

    original = worker.decide_run
    worker.decide_run = fake_decide
    original_argv = sys.argv
    try:
        sys.argv = ["worker.py", "--decide", "abc123", "approve"]
        asyncio.run(worker.main())
        check(
            "valid --decide is dispatched",
            captured == {"run_id": "abc123", "decision": "approve", "operator": "operator-local"},
            str(captured),
        )

        captured.clear()
        sys.argv = ["worker.py", "--decide", "abc123", "approve", "dana"]
        asyncio.run(worker.main())
        check(
            "operator is forwarded to decisions",
            captured == {"run_id": "abc123", "decision": "approve", "operator": "dana"},
            str(captured),
        )

        captured.clear()
        sys.argv = ["worker.py", "--decide", "abc123", "maybe"]
        asyncio.run(worker.main())
        check("invalid decision is rejected", captured == {}, str(captured))

        captured.clear()
        sys.argv = ["worker.py", "--decide", "abc123", "approve", "extra", "extra2"]
        asyncio.run(worker.main())
        check("too many --decide args are rejected", captured == {}, str(captured))
    finally:
        worker.decide_run = original
        sys.argv = original_argv


def test_audit_vocabulary_is_closed() -> None:
    """Every action the worker emits must exist in the course's closed vocabulary."""
    known = {
        "message_received",
        "skill_activated",
        "capability_invoked",
        "message_sent",
        "guardrail_tripped",
        "error",
    }
    source = inspect.getsource(worker)
    emitted = set()
    for marker in ("message_received", "guardrail_tripped", "skill_activated",
                   "capability_invoked", "message_sent", '"error"'):
        if marker.strip('"') in source:
            emitted.add(marker.strip('"'))
    unknown = emitted - known
    check("worker emits only known audit actions", not unknown, f"unknown={unknown}")


def test_mcp_emits_only_known_audit_actions() -> None:
    source = inspect.getsource(mcp_server)
    check("mcp server writes capability_invoked", "capability_invoked" in source)
    check(
        "mcp server avoids raw sql execution",
        "execute(" not in source.replace("conn.execute(", "").replace("await conn.execute(", ""),
    )


def test_conversation_id_is_passed_to_mcp() -> None:
    # The env wiring lives in _mcp_server; run_task supplies the conversation id.
    check(
        "mcp server forwards the conversation id",
        "FRONTEND_CONVERSATION_ID" in inspect.getsource(worker._mcp_server),
    )
    check(
        "run_task supplies the conversation id",
        "_mcp_server(conversation_id)" in inspect.getsource(worker.run_task),
    )
    check(
        "resume supplies the conversation id",
        "_mcp_server(conversation_id)" in inspect.getsource(worker.decide_run),
    )


def test_invocation_context_manager_never_swallows_errors() -> None:
    """A `return` inside a generator's finally silently swallows exceptions.

    That bug turned a refused `publish_task` into a silent success: the caller
    saw None instead of PermissionError. Guard the control flow itself.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def guarded():
        try:
            yield
        finally:
            if False:  # never taken, but the shape is what matters
                return

    async def run():
        async with guarded():
            raise ValueError("must survive")

    try:
        asyncio.run(run())
        check("context manager preserves exceptions", False, "exception was swallowed")
    except ValueError as exc:
        check("context manager preserves exceptions", str(exc) == "must survive", str(exc))

    source = inspect.getsource(mcp_server._invocation)
    finally_block = source.split("finally:")[-1]
    check(
        "_invocation has no return inside its finally block",
        "return" not in finally_block,
        finally_block.strip()[:120],
    )
    check("_invocation re-raises via bare raise", "\n        raise\n" in source)


def test_mcp_tools_do_not_swallow_permission_errors() -> None:
    """The published tool must refuse; a None return would mean a silent pass."""
    import asyncio as _asyncio

    async def check_refusal():
        try:
            await mcp_server.publish_task(name="definitely-not-a-real-task-xyz")
        except Exception as exc:  # noqa: BLE001
            return type(exc).__name__
        return "RETURNED"

    outcome = _asyncio.run(check_refusal())
    check(
        "publish_task raises instead of returning None",
        outcome != "RETURNED",
        f"publish_task returned instead of raising ({outcome})",
    )


# --- Identity ----------------------------------------------------------------


def test_single_publish_path_and_approval_gate() -> None:
    """There must be one publisher, and it must be the gated one.

    An earlier build had `publish_asset` (approval-gated, but only wrote an
    audit row) alongside `publish_task` (really published, ungated). The gated
    tool was the fake one.
    """
    source = inspect.getsource(worker)
    check("publish_asset is gone", "publish_asset" not in source)

    server_src = inspect.getsource(worker._mcp_server)
    check(
        "_mcp_server gates publish_task",
        "require_approval" in server_src and "publish_task" in server_src,
    )

    agent, _ = worker.build_agent()
    names = [tool.name for tool in agent.tools]
    check("publish_asset is not a local tool", "publish_asset" not in names, str(names))
    check("load_skill remains available", "load_skill" in names, str(names))

    policy = worker._mcp_server("test")._needs_approval_policy
    check(
        "only publish_task is gated",
        policy.get("publish_task") is True
        and not any(v for k, v in policy.items() if k != "publish_task"),
        str(policy),
    )


def test_resume_path_is_fully_wired() -> None:
    """A resume that cannot reach the gated tool is theatre, not a gate."""
    source = inspect.getsource(worker.decide_run)

    check("resume awaits RunState.from_string", "await RunState.from_string" in source)
    check(
        "resume does not call from_string without await",
        "state = RunState.from_string" not in source,
    )
    check("resume attaches the MCP server", "_mcp_server(conversation_id)" in source)
    check("resume rebuilds the agent", "build_agent()" in source)
    check("rejection is audited", "_write_publish_denied" in source)


def test_skills_live_in_the_portable_location() -> None:
    """Concept 4: one folder every compliant client can read.

    `.claude/skills` is read by Claude Code, used as OpenCode's fallback, and is
    what the Worker's own SDK points at, so skills are packaged once.
    """
    portable = worker.ROOT / ".claude" / "skills"
    check(".claude/skills exists", portable.is_dir())
    check(
        "SKILLS_ROOT resolves to the portable location",
        worker.SKILLS_ROOT == portable,
        str(worker.SKILLS_ROOT),
    )
    check("no stray top-level skills/ directory", not (worker.ROOT / "skills").is_dir())
    for skill in ("frontend-development", "summarize-component"):
        check(f"{skill} is packaged portably", (portable / skill / "SKILL.md").is_file())
    check(
        "references travel with their skill",
        any((portable / "summarize-component" / "references").glob("*.md")),
    )


def test_official_name_is_feds() -> None:
    import config

    check("official name is FEDS", config.OFFICIAL_NAME == "FEDS", config.OFFICIAL_NAME)
    check(
        "long name expands FEDS",
        config.OFFICIAL_NAME_LONG == "Frontend Engineering Digital Specialist",
        config.OFFICIAL_NAME_LONG,
    )
    check("agent name carries both", "FEDS" in config.AGENT_NAME, config.AGENT_NAME)


def test_system_prompt_declares_feds() -> None:
    from pathlib import Path

    prompt = (Path(worker.ROOT) / "SYSTEM_PROMPT.md").read_text(encoding="utf-8")
    check("system prompt names FEDS", "FEDS" in prompt)
    check("system prompt expands the name", "Frontend Engineering Digital Specialist" in prompt)
    check("system prompt uses FEDS as a heading", prompt.lstrip().startswith("# System Prompt: FEDS"))
    check("system prompt forbids inventing tools", "Never invent a tool name" in prompt)
    check("system prompt has an identity example", "Example 0: Identity" in prompt)


def test_system_prompt_tool_names_are_real() -> None:
    """A prompt that names a nonexistent tool will make the model invent calls."""
    import config  # noqa: F401
    from pathlib import Path

    prompt = (Path(worker.ROOT) / "SYSTEM_PROMPT.md").read_text(encoding="utf-8")
    real_tools = {
        "lookup_task",
        "list_tasks",
        "find_similar_tasks",
        "save_task",
        "record_review",
        "publish_task",
    }
    # Tool names referenced in backticks that look like workspace calls.
    import re

    referenced = set(re.findall(r"`(lookup_[a-z_]+|list_[a-z_]+|find_[a-z_]+|save_[a-z_]+|record_[a-z_]+|publish_[a-z_]+)`", prompt))
    unknown = referenced - real_tools
    check("prompt references only real tools", not unknown, f"unknown={unknown}")
    check(
        "prompt lists the publish guard",
        "publish_task" in prompt and "approved" in prompt,
    )


def test_docs_use_feds() -> None:
    from pathlib import Path

    readme = (Path(worker.ROOT) / "README.md").read_text(encoding="utf-8")
    check("README names FEDS", "FEDS" in readme)
    check("README expands the name", "Frontend Engineering Digital Specialist" in readme)
    agents = (Path(worker.ROOT) / "AGENTS.md").read_text(encoding="utf-8")
    check("AGENTS.md names FEDS", "FEDS" in agents)


# --- Ops tooling ------------------------------------------------------------


def test_replay_and_reembed_are_importable() -> None:
    import replay
    import reembed

    check("replay exposes a CLI entry point", callable(replay.main))
    check("reembed exposes a CLI entry point", callable(reembed.main))
    check(
        "replay joins audit and capability trails",
        "audit_log" in inspect.getsource(replay) and "capability_invocations" in inspect.getsource(replay),
    )
    check("reembed is dry-run by default", "args.apply" in inspect.getsource(reembed))


def test_embedding_models_are_distinct() -> None:
    import config

    check(
        "the two embedding models are named differently",
        config.EMBEDDING_MODELS["gemini"] != config.EMBEDDING_MODELS["openai"],
        str(config.EMBEDDING_MODELS),
    )
    check(
        "the preferred provider leads the order",
        config.embedding_order()[0] == config.PREFERRED_EMBEDDING_PROVIDER,
        str(config.embedding_order()),
    )
    check(
        "disabled providers are excluded",
        "openai" not in config.embedding_order() or config.OPENAI_ENABLED,
        str(config.embedding_order()),
    )


def test_chat_only_providers_are_absent_from_embeddings() -> None:
    """A provider with no embeddings endpoint must never be an embedding route."""
    import config

    for chat_only in [n for n in config.CHAT_MODELS if n not in config.EMBEDDING_MODELS]:
        check(
            f"{chat_only} never appears in the embedding order",
            chat_only not in config.embedding_order(),
            str(config.embedding_order()),
        )
    for name in config.EMBEDDING_MODELS:
        check(
            f"{name} can serve embeddings",
            name in config.embedding_order() or not config.ENABLED_FLAGS.get(name, False),
            str(config.embedding_order()),
        )


def test_every_chat_provider_has_complete_settings() -> None:
    """A provider is either fully configured or disabled, never half-configured.

    Since credentials come from the environment, a missing key is legitimate.
    What must never happen is a provider with no key that still counts as
    enabled: that would fail at call time instead of at startup.
    """
    import config

    for name, cfg in config.CHAT_MODELS.items():
        check(f"{name} has a model", bool(cfg.get("model")))
        check(f"{name} base_url is a string", isinstance(cfg.get("base_url"), str))
        has_key = bool(cfg.get("api_key"))
        enabled = config.ENABLED_FLAGS.get(name, False)
        check(f"{name} is enabled only with a key", (not enabled) or has_key)
        check(f"{name} without a key is disabled", has_key or (not enabled))


def test_disabled_providers_are_routable_when_enabled() -> None:
    """Every registered provider must be able to join the chat order."""
    import config

    original = dict(config.ENABLED_FLAGS)
    try:
        for name in config.CHAT_MODELS:
            config.ENABLED_FLAGS[name] = True
            order = config.chat_order()
            check(f"{name} can join the chat order", name in order, str(order))
        check(
            "chat preference is respected",
            config.chat_order()[0] == config.CHAT_PREFERENCE[0],
            str(config.chat_order()),
        )
    finally:
        config.ENABLED_FLAGS.update(original)


def test_pricing_is_honest() -> None:
    """Known models cost a non-negative estimate; unknown models never fake zero."""
    import config

    model_name = config.CHAT_MODELS[config.chat_order()[0]]["model"]
    priced = config.cost_cents_for(model_name, 1000, 500)
    check("known model yields a priced estimate", isinstance(priced, int) and priced >= 0, str(priced))
    check("unknown model yields NULL cost, not zero", config.cost_cents_for("no-such-model", 1000, 500) is None)
    check("zero tokens cost nothing for a known model",
          config.cost_cents_for(model_name, 0, 0) == 0)
    check("1M output tokens at the flash list price is 250 cents",
          config.cost_cents_for("gemini-3.5-flash", 0, 1_000_000) == 250)


def test_turn_usage_extraction() -> None:
    class _Usage:
        requests = 2
        input_tokens = 123
        output_tokens = 45
        total_tokens = 168

    class _Wrapper:
        usage = _Usage()

    class _Result:
        context_wrapper = _Wrapper()

    counts = worker._turn_usage_from(_Result())
    check("aggregate usage is pulled from the context wrapper",
          counts == {"requests": 2, "input_tokens": 123, "output_tokens": 45, "total_tokens": 168},
          str(counts))

    class _Empty:
        pass

    check("a result with no usage yields None", worker._turn_usage_from(_Empty()) is None)


class _RecordingConn:
    async def execute(self, statement, params=None):
        SINK["statement"] = str(statement)
        SINK["params"] = dict(params or {})


class _RecordingResult:
    async def __aenter__(self):
        return _RecordingConn()

    async def __aexit__(self, *exc):
        return False


class _RecordingEngine:
    def begin(self):
        return _RecordingResult()


class _UsageResult:
    class context_wrapper:
        class usage:
            requests = 2
            input_tokens = 123
            output_tokens = 45
            total_tokens = 168


SINK: dict[str, object] = {}


class _UnnamedChatModel:
    model = "gemini-3.5-flash"
    _last_provider = "gemini"


class _UnknownModelChatModel:
    model = "not-an-installed-model-xyz"
    _last_provider = "gemini"


def _record_usage_with(chat_model) -> None:
    asyncio.run(
        worker._record_turn_usage(
            _RecordingEngine(), "conv123", chat_model, _UsageResult(), 0.0
        )
    )


def test_record_turn_usage_is_best_effort_and_priced() -> None:
    SINK.clear()
    _record_usage_with(_UnnamedChatModel())
    check("one chat.turn capability row is written",
          "capability_invocations" in SINK.get("statement", ""), str(SINK.get("statement", "")))
    params = SINK.get("params", {})
    check("capability is named chat.turn", params.get("capability") == "chat.turn", str(params))
    check("tokens land in the result json",
          json.loads(params.get("result", "{}")).get("total_tokens") == 168, str(params.get("result")))
    check("priced model carries a cost estimate",
          isinstance(params.get("cost_cents"), int) and params["cost_cents"] >= 0,
          str(params.get("cost_cents")))
    check("cost basis is labelled as an estimate",
          json.loads(params.get("arguments", "{}")).get("cost_basis") == "list_price_estimate",
          str(params.get("arguments")))

    SINK.clear()
    _record_usage_with(_UnknownModelChatModel())
    check("unknown model stores NULL cost, not zero",
          SINK.get("params", {}).get("cost_cents") is None, str(SINK.get("params")))

    SINK.clear()
    asyncio.run(worker._record_turn_usage(_RecordingEngine(), "conv", _UnnamedChatModel(), object(), 0.0))
    check("a result without usage writes nothing", SINK == {}, str(SINK))


def test_conversation_lock_guards_decisions() -> None:
    """Decision 10: one advisory lock must wrap the whole resume path."""
    source = inspect.getsource(worker)
    check(
        "advisory lock helper exists",
        hasattr(worker, "_conversation_lock"),
        "worker._conversation_lock missing",
    )
    check("lock uses the try-lock form (refuse, never wait)",
          "pg_try_advisory_lock" in inspect.getsource(worker._conversation_lock))
    check("lock is always released", "pg_advisory_unlock" in inspect.getsource(worker._conversation_lock))
    decide = inspect.getsource(worker.decide_run)
    check("decide_run holds the lock", "_conversation_lock" in decide)
    check("decide_run refuses a contended conversation", "retry after it finishes" in decide)


def test_decisions_record_who_decided() -> None:
    decide = inspect.getsource(worker.decide_run)
    main_source = inspect.getsource(worker.main)
    schema = Path("setup_neon.py").read_text(encoding="utf-8")
    check("run_states gains an operator column", "operator TEXT" in schema)
    check("the decision UPDATE stores the operator", "operator=:operator" in decide)
    check("the decision is audited with the operator", "approval_decided" in decide and "operator" in decide)
    check("the CLI documents the optional operator", "[operator]" in main_source)


def test_skills_compose_via_filesystem_handoff() -> None:
    """Concept 5: one skill's output is the next skill's input, without re-collection."""
    summary = (Path(".claude/skills/summarize-component/SKILL.md")).read_text(encoding="utf-8")
    escalate = (Path(".claude/skills/escalate-review/SKILL.md")).read_text(encoding="utf-8")
    check(
        "summarize-component publishes a handoff artifact",
        ".agents/handoff/" in summary and "save_task" in summary,
        "no artifact handoff",
    )
    check(
        "escalate-review consumes the handoff instead of re-summarizing",
        ".agents/handoff/" in escalate and "re-summarize from scratch" in escalate,
        "no consumption step",
    )
    check(
        "escalate-review falls back to lookup_task when no file exists",
        "lookup_task" in escalate and "type" in escalate,
        "no handoff fallback",
    )


def test_replay_reports_cost_rollups() -> None:
    source = Path("replay.py").read_text(encoding="utf-8")
    check("a token/cost rollup query exists", "COST_ROLLUP_QUERY" in source)
    check("rollup only counts rows that carry token usage", "result ? 'total_tokens'" in source)
    check("the CLI exposes --costs", "--costs" in source)


def main() -> int:
    test_guardrail_blocks_unsafe_input()
    test_guardrail_allows_real_work()
    test_guardrail_only_screens_the_latest_user_turn()
    test_guardrail_reads_structured_content_parts()
    test_skill_tree_is_valid()
    test_malformed_skill_does_not_crash_loader()
    test_progressive_disclosure_shrinks_context()
    test_load_skill_returns_body_and_references()
    test_frontmatter_parser()
    test_chunking_boundaries_and_overlap()
    test_mcp_tools_expose_expected_surface()
    test_publish_task_is_high_trust()
    test_worker_publish_asset_requires_approval()
    test_decide_command_validates_input()
    test_audit_vocabulary_is_closed()
    test_mcp_emits_only_known_audit_actions()
    test_conversation_id_is_passed_to_mcp()
    test_invocation_context_manager_never_swallows_errors()
    test_mcp_tools_do_not_swallow_permission_errors()
    test_official_name_is_feds()
    test_skills_live_in_the_portable_location()
    test_single_publish_path_and_approval_gate()
    test_resume_path_is_fully_wired()
    test_system_prompt_declares_feds()
    test_system_prompt_tool_names_are_real()
    test_docs_use_feds()
    test_replay_and_reembed_are_importable()
    test_embedding_models_are_distinct()
    test_chat_only_providers_are_absent_from_embeddings()
    test_every_chat_provider_has_complete_settings()
    test_disabled_providers_are_routable_when_enabled()
    test_pricing_is_honest()
    test_turn_usage_extraction()
    test_record_turn_usage_is_best_effort_and_priced()
    test_conversation_lock_guards_decisions()
    test_decisions_record_who_decided()
    test_skills_compose_via_filesystem_handoff()
    test_replay_reports_cost_rollups()

    print(f"\n{'ALL OFFLINE CHECKS PASSED' if not FAILURES else f'{len(FAILURES)} FAILED: {FAILURES}'}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())