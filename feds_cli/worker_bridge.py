"""Bridge between the FEDS CLI and the worker process logic.

The CLI imports `worker` directly (same process, same config); nothing is
spawned. Because the worker prints its answer to stdout* — the CLI owns the
terminal — every turn is run with stdout/stderr captured and turned into a
structured result instead of leaking into the Textual screen.

*The worker was written as a headless CLI, so its final answer is a `print`.
Capturing that text is the honest bridge until the worker grows a callback.
"""

from __future__ import annotations

import contextlib
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

# Repo root must be importable so `worker` and `worker`'s siblings resolve.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if TYPE_CHECKING:
    from feds_cli.models import Session

_MODEL_LINE = re.compile(r"^\[model\]\s+(?P<label>\S+?)(?:\s+\(stream\))?\s*$")


@contextlib.contextmanager
def _real_streams():
    """Expose real stdout/stderr while a turn runs, if they were replaced.

    A TUI owns the terminal, and Textual's test driver (and some embedders)
    swap `sys.stdout` for a stream with no file descriptor. The MCP server is
    launched over stdio and the sandbox touches the fd, so those turns fail with
    `[Errno 9] Bad file descriptor`. Nothing is written during a captured turn,
    so restoring the real streams for its duration is safe and invisible.
    """
    swapped: list[tuple[str, object]] = []
    for name in ("stdout", "stderr", "stdin"):
        stream = getattr(sys, name, None)
        real = getattr(sys, f"__{name}__", None)
        try:
            fd = stream.fileno()  # type: ignore[union-attr]
            valid = isinstance(fd, int) and fd >= 0
        except Exception:  # noqa: BLE001 - the reason we are here
            valid = False
        if not valid and real is not None and real is not stream:
            swapped.append((name, stream))
            setattr(sys, name, real)
    try:
        yield
    finally:
        for name, original in swapped:
            setattr(sys, name, original)


@dataclass
class TurnResult:
    """What one worker turn produced."""

    text: str
    model: str | None = None
    events: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class WorkerBridge:
    """Async facade over the worker's public entry points."""

    def __init__(self) -> None:
        self._worker = None
        self._initialized = False

    # --- init -------------------------------------------------------------

    def preload(self, attempts: int = 3) -> str | None:
        """Import the worker before the TUI takes over the process streams.

        Textual redirects `sys.stdout`/`sys.stderr` to capture objects whose
        `fileno()` is -1 for the entire run. The MCP stdio client binds its
        `errlog` default to `sys.stderr` at import time and hands it to
        `subprocess`, which then fails with `[Errno 9] Bad file descriptor`.
        Importing here — before `App.run()` — keeps the real stream bound.

        Windows Smart App Control can block a native DLL for a moment after the
        interpreter starts (`_util_cy`), so a blocked load is retried; only a
        persistent failure is reported.
        """
        last: str | None = None
        for attempt in range(attempts):
            try:
                self._ensure_initialized()
                return None
            except Exception as exc:  # noqa: BLE001 - shown in the chat view
                last = f"{type(exc).__name__}: {exc}"
                if attempt + 1 < attempts:
                    time.sleep(0.4)
        return last

    def _ensure_initialized(self):
        if self._initialized:
            return self._worker
        try:
            import worker  # imported lazily: heavy imports (agents, DB drivers)
        except ImportError as exc:  # pragma: no cover - setup problem
            raise RuntimeError(
                f"Failed to import the FEDS worker: {exc}. "
                "Run the CLI from the repository root."
            ) from exc
        self._worker = worker
        self._initialized = True
        return worker

    # --- turns ------------------------------------------------------------

    async def run_turn(self, session: "Session", user_input: str) -> TurnResult:
        """Run one agent turn for the session and capture its output.

        The worker resolves skills and the system prompt relative to the
        repository root, so the process working directory is deliberately left
        alone; the session's own cwd is recorded in the session, not applied.

        Output is collected through the worker's own capture hook instead of
        redirecting `sys.stdout`: the MCP child is launched over stdio, and a
        redirected stream has no file descriptor for it to inherit.
        """
        worker = self._ensure_initialized()
        capture: dict[str, list[str]] = {"out": [], "err": []}
        worker._CAPTURE = capture
        try:
            with _real_streams():
                await worker.run_task(user_input, conversation_id=session.id)
        except Exception as exc:  # noqa: BLE001 - surfaced in the chat view
            return TurnResult(text="", error=f"{type(exc).__name__}: {exc}")
        finally:
            worker._CAPTURE = None

        return TurnResult(
            text=_clean_output("\n".join(capture.get("out", []))),
            model=_model_label("\n".join(capture.get("err", []))),
            events=_events("\n".join(capture.get("err", []))),
        )

    async def run_task(self, session: "Session", user_input: str) -> str:
        """Backwards-compatible single-turn entry point returning just the text."""
        result = await self.run_turn(session, user_input)
        if result.error:
            raise RuntimeError(result.error)
        return result.text or "(no output)"

    async def resume_session(
        self,
        session: "Session",
        user_input: str = "",
        max_iterations: int = 50,
        max_cost_cents: int | None = None,
        wall_clock_limit: int | None = None,
    ) -> TurnResult:
        """Resume a parked session from its audit trail."""
        worker = self._ensure_initialized()
        capture: dict[str, list[str]] = {"out": [], "err": []}
        worker._CAPTURE = capture
        try:
            await worker.resume_session(
                conversation_id=session.id,
                user_input=user_input,
                max_iterations=max_iterations,
                max_cost_cents=max_cost_cents,
                wall_clock_limit=wall_clock_limit,
            )
        except Exception as exc:  # noqa: BLE001
            return TurnResult(text="", error=f"{type(exc).__name__}: {exc}")
        finally:
            worker._CAPTURE = None
        return TurnResult(
            text=_clean_output("\n".join(capture.get("out", []))),
            model=_model_label("\n".join(capture.get("err", []))),
            events=_events("\n".join(capture.get("err", []))),
        )

    async def decide_run(
        self,
        run_id: str,
        decision: str,
        operator: str = "operator-local",
    ) -> bool:
        """Apply an approval decision to a parked run."""
        worker = self._ensure_initialized()
        capture: dict[str, list[str]] = {"out": [], "err": []}
        worker._CAPTURE = capture
        try:
            return bool(await worker.decide_run(run_id, decision, operator))
        finally:
            worker._CAPTURE = None

    # --- status -----------------------------------------------------------

    def get_provider_status(self) -> dict:
        """Chat/embedding order plus live cooldown state, without a network call."""
        try:
            import config
            from provider_router import ProviderRouter
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

        status: dict = {
            "chat_order": [],
            "embed_order": [],
            "enabled": {},
            "models": {},
        }
        try:
            status["chat_order"] = config.chat_order()
            status["embed_order"] = config.embedding_order()
        except Exception as exc:  # noqa: BLE001
            status["error"] = str(exc)
        status["enabled"] = dict(config.ENABLED_FLAGS)
        status["models"] = {
            name: str(cfg.get("model", "")) for name, cfg in config.CHAT_MODELS.items()
        }

        # Cooldown state lives on the worker's process-wide router, when built.
        worker = self._worker
        router = getattr(worker, "_CHAT_ROUTER", None) if worker is not None else None
        if isinstance(router, ProviderRouter):
            status["router"] = router.status()
        return status

    def get_mcp_status(self) -> str:
        """Cheap MCP wiring check: the module the worker launches must import."""
        try:
            import frontend_workspace_mcp.server  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            return f"unavailable ({type(exc).__name__})"
        return "ready (stdio)"


def _clean_output(raw: str) -> str:
    """Drop log noise from captured worker stdout, keep the answer."""
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith("[provider-router]"):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _model_label(raw_stderr: str) -> str | None:
    for line in raw_stderr.splitlines():
        match = _MODEL_LINE.match(line.strip())
        if match:
            return match.group("label")
    return None


def _events(raw_stderr: str) -> list[str]:
    return [
        line.strip()
        for line in raw_stderr.splitlines()
        if line.strip().startswith("[provider-router]")
    ]


_bridge: WorkerBridge | None = None


def get_bridge() -> WorkerBridge:
    """Process-wide bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = WorkerBridge()
    return _bridge
