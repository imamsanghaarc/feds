"""FEDS CLI â€” Textual TUI.

Layout (opencode-style): banner, chat pane on the left, context panel on the
right, status bar and footer at the bottom. The worker is imported in-process
through `worker_bridge`; no subprocess is spawned.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Footer, ListItem, ListView, Markdown, Static, TextArea

from feds_cli import __version__
from feds_cli.banner import banner as banner_text
from feds_cli.models import (
    ContextSnapshot,
    Message as ChatMessage,
    Session,
    SessionMeta,
)
from feds_cli.session import (
    generate_title,
    get_sessions_dir,
    list_sessions,
    load_session,
    new_session_id,
    save_session,
)
from feds_cli.worker_bridge import TurnResult, get_bridge

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- widgets -----------------------------------------------------------------


class FedsBanner(Static):
    """Big ASCII/Unicode logo with the tagline."""

    def render(self) -> Text:
        text = Text()
        lines = banner_text(__version__).rstrip("\n").split("\n")
        logo_done = False
        for line in lines:
            if not logo_done and line.strip():
                text.append(line + "\n", style="bold bright_cyan")
            elif not logo_done:
                text.append("\n")
            elif line.strip().lower().startswith("by sanglabs"):
                text.append(line + "\n", style="dim italic")
            elif line.strip().startswith("v"):
                text.append(line + "\n", style="dim")
            else:
                text.append(line + "\n", style="bold white")
            if not line.strip():
                logo_done = True
        return text


class ChatView(VerticalScroll):
    """Scrolling transcript."""

    def __init__(self) -> None:
        super().__init__()
        self._transcript = ""

    def compose(self) -> ComposeResult:
        yield Static("", id="chat-lines", markup=True)

    @property
    def _body(self) -> Static:
        return self.query_one("#chat-lines", Static)

    def _append(self, chunk: str) -> None:
        self._transcript = f"{self._transcript}\n{chunk}".lstrip("\n")
        self._body.update(self._transcript)
        self.scroll_end(animate=False)

    def add_user_message(self, content: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self._append(f"\n[bold cyan]You[/bold cyan] [dim]{stamp}[/dim]\n{_escape(content)}")

    def add_assistant_message(
        self,
        content: str,
        model: str | None = None,
        thought: str | None = None,
    ) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        label = f" [dim]({_escape(model)})[/dim]" if model else ""
        block = [
            f"\n[bold green]FEDS[/bold green]{label} [dim]{stamp}[/dim]",
        ]
        if thought:
            block.append(f"[italic dim]Thinking: {_escape(thought)}[/italic dim]")
        block.append(_escape(content))
        self._append("\n".join(block))

    def add_system_message(self, content: str) -> None:
        self._append(f"\n[yellow]{content}[/yellow]")

    def reset(self) -> None:
        self._transcript = ""
        self._body.update("")


class ContextPanel(Vertical):
    """Right-hand state panel."""

    def compose(self) -> ComposeResult:
        yield Static("CONTEXT", classes="panel-heading")
        yield Static(id="session-info", classes="panel-block")
        yield Static(id="tokens-cost", classes="panel-block")
        yield Static(id="skills-loaded", classes="panel-block")
        yield Static(id="mcp-status", classes="panel-block")
        yield Static(id="providers", classes="panel-block")

    def refresh_from(
        self,
        session: Session,
        status: dict,
        mcp_status: str,
        skills: Iterable[str] = (),
    ) -> None:
        self.query_one("#session-info", Static).update(
            "[bold]Session[/bold]\n"
            f"{_escape(session.title)}\n"
            f"[dim]id[/dim] {session.id}\n"
            f"[dim]cwd[/dim] {_escape(_short_path(session.cwd))}\n"
            f"[dim]git[/dim] {_escape(session.git_root or 'â€”')}\n"
            f"[dim]msgs[/dim] {len(session.messages)}"
        )

        turn = session.context.last_turn or {}
        tokens = turn.get("tokens") or {}
        cost = turn.get("cost_cents")
        self.query_one("#tokens-cost", Static).update(
            "[bold]Tokens & cost[/bold]\n"
            f"[dim]in[/dim] {tokens.get('input_tokens', 'â€”')}  "
            f"[dim]out[/dim] {tokens.get('output_tokens', 'â€”')}\n"
            f"[dim]cost[/dim] {_cost_label(cost)}"
        )

        loaded = list(session.context.skills_loaded) or []
        self.query_one("#skills-loaded", Static).update(
            "[bold]Skills[/bold]\n"
            + ("\n".join(f"Â· {_escape(name)}" for name in loaded[-6:]) or "[dim]none loaded[/dim]")
        )

        self.query_one("#mcp-status", Static).update(
            f"[bold]MCP[/bold]\n{_escape(mcp_status)}"
        )

        order = status.get("chat_order") or []
        models = status.get("models") or {}
        lines = ["[bold]Providers[/bold]"]
        for index, name in enumerate(order):
            marker = "â–¶" if index == 0 else "Â·"
            lines.append(f"{marker} {_escape(name)} [dim]{_escape(str(models.get(name, '')))}[/dim]")
        if not order:
            lines.append(f"[red]{_escape(status.get('error', 'none enabled'))}[/red]")
        self.query_one("#providers", Static).update("\n".join(lines))


class StatusBar(Static):
    """One-line status strip above the footer."""

    def set_state(self, session: Session, model: str | None, busy: bool) -> None:
        chips = [
            f"[bold]#{_escape(__version__)}[/bold]",
            f"[dim]session[/dim] {session.id}",
            f"[dim]model[/dim] {_escape(model or 'selectingâ€¦')}",
            "[yellow]workingâ€¦[/yellow]" if busy else "[green]ready[/green]",
        ]
        self.update("  ".join(chips))


class PromptInput(TextArea):
    """Enter submits, Ctrl+J (or Shift+Enter where supported) inserts a newline."""

    BINDINGS = [
        Binding("ctrl+j", "newline", "Newline", show=False),
    ]

    @dataclass
    class Submitted(Message):
        """Posted when the user presses Enter."""

        value: str

    def __init__(self) -> None:
        super().__init__(
            "",
            id="input-area",
            show_line_numbers=False,
            soft_wrap=True,
            tab_behavior="focus",
            placeholder="Ask FEDS to build, review, or debug frontend workâ€¦",
        )

    async def _on_key(self, event) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.post_message(self.Submitted(self.text))
            return
        await super()._on_key(event)

    def action_newline(self) -> None:
        self.insert("\n")


class SessionPickerScreen(ModalScreen[Optional[str]]):
    """Pick a saved session."""

    BINDINGS = [Binding("escape", "dismiss_picker", "Close", show=False)]

    def __init__(self) -> None:
        super().__init__()
        self._sessions = list_sessions()

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-box"):
            yield Static("SESSIONS", classes="modal-title")
            if self._sessions:
                yield ListView(
                    *[
                        ListItem(
                            Static(
                                f"[bold]{_escape(item.get('title') or 'Untitled')}[/bold]\n"
                                f"[dim]{item['id']} Â· {item['message_count']} msgs Â· "
                                f"{str(item.get('updated_at'))[:16]}[/dim]"
                            ),
                            id=f"pick-{item['id']}",
                        )
                        for item in self._sessions
                    ],
                    id="session-list",
                )
            else:
                yield Static("[dim]No saved sessions yet.[/dim]")
            yield Static("[dim]enter open Â· esc close[/dim]", classes="modal-hint")

    def _id_list(self) -> list[str]:
        return [item["id"] for item in self._sessions]

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        ids = self._id_list()
        index = event.index
        if index is not None and index < len(ids):
            self.dismiss(ids[index])

    def action_dismiss_picker(self) -> None:
        self.dismiss(None)


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("f1", "close", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Markdown(HELP_MARKDOWN, id="help-content")
            yield Static("[dim]esc / F1 to close[/dim]", classes="modal-hint")

    def action_close(self) -> None:
        self.dismiss(None)


# --- app ---------------------------------------------------------------------


class FedsCLI(App):
    """FEDS â€” Frontend Engineering Digital Specialist."""

    TITLE = "FEDS"
    SUB_TITLE = "Frontend Engineering Digital Specialist"
    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }
    FedsBanner {
        height: auto;
        padding: 0 2;
        margin-bottom: 1;
    }
    #main-container {
        height: 1fr;
    }
    #chat-container {
        width: 2fr;
        min-width: 40;
    }
    ChatView {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    #chat-lines {
        width: 100%;
    }
    #input-area {
        height: 5;
        max-height: 10;
        margin-top: 1;
        border: round $accent;
        padding: 0 1;
    }
    #input-area:focus {
        border: round $accent-lighten-2;
    }
    ContextPanel {
        width: 38;
        min-width: 30;
        border: round $primary;
        padding: 0 1;
        overflow-y: auto;
    }
    .panel-heading {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    .panel-block {
        margin-bottom: 1;
    }
    StatusBar {
        height: 1;
        padding: 0 2;
        background: $panel;
        color: $text-muted;
    }
    SessionPickerScreen, HelpScreen {
        align: center middle;
    }
    #picker-box {
        width: 70%;
        height: 70%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #help-box {
        width: 85%;
        height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    .modal-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    .modal-hint {
        margin-top: 1;
    }
    #session-list {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "graceful_quit", "Quit", show=True, priority=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=True, priority=True),
        Binding("ctrl+p", "sessions", "Sessions", show=True, priority=True),
        Binding("ctrl+k", "toggle_context", "Context", show=True, priority=True),
        Binding("ctrl+up", "history_prev", "History", show=False, priority=True),
        Binding("ctrl+down", "history_next", "History", show=False, priority=True),
        Binding("f1", "help", "Help", show=True),
    ]

    def __init__(
        self,
        session_id: str | None = None,
        max_cost_cents: int | None = None,
        wall_clock_limit: int | None = None,
    ) -> None:
        super().__init__()
        self.session: Session | None = None
        self.session_id = session_id
        self.max_cost_cents = max_cost_cents
        self.wall_clock_limit = wall_clock_limit

        self.bridge = get_bridge()
        self.preload_error = self.bridge.preload()
        self.history: list[str] = []
        self.history_index = 0
        self.last_model: str | None = None
        self._busy = False
        self._status: dict = {}

    # --- layout -----------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield FedsBanner()
        with Horizontal(id="main-container"):
            with Vertical(id="chat-container"):
                yield ChatView()
                yield PromptInput()
            yield ContextPanel()
        yield StatusBar(id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        self.session = self._load_or_create_session()
        save_session(self.session)
        self._status = self.bridge.get_provider_status()

        order = self._status.get("chat_order") or []
        models = self._status.get("models") or {}
        if self.last_model is None and order:
            self.last_model = f"{order[0]}:{models.get(order[0], '')}"

        self._refresh_panels()

        self.query_one(PromptInput).focus()
        history = [m.content for m in self.session.messages if m.role == "user"]
        self.history = history
        self.history_index = len(history)

        chat = self.query_one(ChatView)
        if self.preload_error:
            chat.add_system_message(
                "[red]Worker failed to load:[/red] "
                f"{_escape(self.preload_error)}\n"
                "[dim]Run the CLI from the repository root after `uv sync`.[/dim]"
            )
        elif self.session.messages:
            chat.add_system_message(
                f"Resumed [bold]{_escape(self.session.title)}[/bold] "
                f"({len(self.session.messages)} messages) â€” /replay to review."
            )
        else:
            chat.add_system_message(
                "Ready. Describe a frontend task, or type [bold]/help[/bold] for commands."
            )
        self._update_status()

    # --- session ----------------------------------------------------------

    def _load_or_create_session(self) -> Session:
        if self.session_id:
            loaded = load_session(self.session_id)
            if loaded:
                return loaded
        cwd = os.getcwd()
        return Session(
            id=new_session_id(),
            title="New Session",
            cwd=cwd,
            git_root=_git_root(cwd),
            meta=SessionMeta(cli_version=__version__),
            context=ContextSnapshot(),
        )

    def _refresh_panels(self) -> None:
        if self.session is None:
            return
        self.query_one(ContextPanel).refresh_from(
            self.session,
            self._status,
            self.bridge.get_mcp_status(),
        )
        self.query_one(StatusBar).set_state(self.session, self.last_model, self._busy)

    def _update_status(self) -> None:
        if self.session:
            self.query_one(StatusBar).set_state(self.session, self.last_model, self._busy)

    # --- turns ------------------------------------------------------------

    def on_prompt_input_submitted(self, event: PromptInput.Submitted) -> None:
        text = event.value.strip()
        self.query_one(PromptInput).clear()
        if not text:
            return
        if text.startswith("/"):
            self._handle_command(text)
            return
        self._start_turn(text)

    def _start_turn(self, text: str) -> None:
        if self._busy:
            self.query_one(ChatView).add_system_message(
                "Still working on the previous turn; wait or press Ctrl+C."
            )
            return
        if self.session is None:
            return

        if self.session.title == "New Session":
            self.session.title = generate_title(text)

        self.history.append(text)
        self.history_index = len(self.history)

        chat = self.query_one(ChatView)
        chat.add_user_message(text)
        self.session.messages.append(ChatMessage(role="user", content=text))
        save_session(self.session)

        self._busy = True
        self._update_status()
        self.query_one(PromptInput).disabled = True
        chat.add_system_message("[dim]FEDS is workingâ€¦[/dim]")
        self._run_turn(text)

    @work(exclusive=True, group="turn")
    async def _run_turn(self, text: str) -> None:
        assert self.session is not None
        chat = self.query_one(ChatView)
        try:
            result: TurnResult = await self.bridge.run_turn(self.session, text)
        except Exception as exc:  # noqa: BLE001 - never crash the UI
            result = TurnResult(text="", error=f"{type(exc).__name__}: {exc}")

        if result.error:
            chat.add_system_message(f"[red]Turn failed: {_escape(result.error)}[/red]")
        else:
            self.last_model = result.model or self.last_model
            chat.add_assistant_message(result.text or "(no output)", model=result.model)
            self.session.messages.append(
                ChatMessage(role="assistant", content=result.text, model=result.model)
            )
            for event in result.events:
                chat.add_system_message(f"[dim]{_escape(event)}[/dim]")

        self.session.updated_at = datetime.now().isoformat()
        save_session(self.session)
        await self._refresh_usage()

        self._busy = False
        self.query_one(PromptInput).disabled = False
        self.query_one(PromptInput).focus()
        self._refresh_panels()

    async def _refresh_usage(self) -> None:
        """Pull this conversation's token/cost rollup, if the DB is reachable."""
        if self.session is None:
            return
        usage = await asyncio.to_thread(_conversation_usage, self.session.id)
        if usage:
            self.session.context.last_turn = {"tokens": usage, "cost_cents": usage.get("cost_cents")}

    # --- commands ---------------------------------------------------------

    def _handle_command(self, text: str) -> None:
        parts = text[1:].split(maxsplit=1)
        command = parts[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""
        handler = getattr(self, f"_cmd_{command}", None)
        if handler is None:
            self.chat().add_system_message(f"Unknown command [bold]/{_escape(command)}[/bold]. Try /help.")
            return
        handler(argument)

    def chat(self) -> ChatView:
        return self.query_one(ChatView)

    def _cmd_help(self, _: str) -> None:
        self.push_screen(HelpScreen())

    def _cmd_clear(self, _: str) -> None:
        self.chat().reset()
        self.chat().add_system_message("Chat cleared. Session history is intact (/replay).")

    def _cmd_reset(self, _: str) -> None:
        self.session = Session(
            id=new_session_id(),
            title="New Session",
            cwd=os.getcwd(),
            git_root=_git_root(os.getcwd()),
            meta=SessionMeta(cli_version=__version__),
        )
        save_session(self.session)
        self.chat().reset()
        self.history = []
        self.history_index = 0
        self.last_model = None
        self.chat().add_system_message(f"New session [bold]{self.session.id}[/bold].")
        self._refresh_panels()

    def _cmd_sessions(self, _: str) -> None:
        def apply(session_id: Optional[str]) -> None:
            if session_id:
                self._resume(session_id)

        self.push_screen(SessionPickerScreen(), apply)

    def _cmd_whoami(self, _: str) -> None:
        assert self.session is not None
        self.chat().add_system_message(
            f"[bold]FEDS[/bold] v{__version__} â€” Frontend Engineering Digital Specialist\n"
            f"session {self.session.id}\n"
            f"cwd {_escape(self.session.cwd)}\n"
            f"git {_escape(self.session.git_root or 'â€”')}"
        )

    def _cmd_version(self, _: str) -> None:
        self.chat().add_system_message(f"FEDS CLI v{__version__}")

    def _cmd_exit(self, _: str) -> None:
        self.action_graceful_quit()

    def _cmd_quit(self, _: str) -> None:
        self.action_graceful_quit()

    def _cmd_model(self, argument: str) -> None:
        order = self._status.get("chat_order") or []
        models = self._status.get("models") or {}
        if argument:
            self.chat().add_system_message(
                f"Runtime model switching is not wired yet. To use [bold]{_escape(argument)}[/bold], "
                "set the provider's *_CHAT_MODEL in .env and restart the CLI. "
                f"Active chain: {', '.join(order) or 'none'}."
            )
            return
        listing = "\n".join(
            f"{'â–¶' if i == 0 else 'Â·'} [bold]{_escape(name)}[/bold] "
            f"[dim]{_escape(str(models.get(name, '')))}[/dim]"
            for i, name in enumerate(order)
        ) or "[red]no provider enabled[/red]"
        self.chat().add_system_message(
            f"Chat chain (first healthy wins):\n{listing}\n"
            f"[dim]last turn model: {_escape(self.last_model or 'â€”')}[/dim]"
        )

    def _cmd_skills(self, _: str) -> None:
        skills = _installed_skills()
        if not skills:
            self.chat().add_system_message("No skills found under .claude/skills.")
            return
        preview = "\n".join(f"Â· {_escape(name)}" for name in skills)
        self.chat().add_system_message(f"[bold]{len(skills)} skills installed[/bold]\n{preview}")

    def _cmd_mcp(self, _: str) -> None:
        self._show_mcp_tools()

    @work(exclusive=True, group="mcp")
    async def _show_mcp_tools(self) -> None:
        try:
            from frontend_workspace_mcp import server as mcp_server

            tools = await mcp_server.mcp.list_tools()
            names = ", ".join(tool.name for tool in tools)
            self.chat().add_system_message(
                f"[bold]MCP[/bold] {self.bridge.get_mcp_status()}\n"
                f"[dim]{len(tools)} tools:[/dim] {_escape(names)}"
            )
        except Exception as exc:  # noqa: BLE001
            self.chat().add_system_message(f"[red]MCP check failed: {_escape(str(exc))}[/red]")

    def _cmd_cost(self, _: str) -> None:
        self._show_cost()

    @work(exclusive=True, group="cost")
    async def _show_cost(self) -> None:
        assert self.session is not None
        usage = await asyncio.to_thread(_conversation_usage, self.session.id)
        if not usage:
            self.chat().add_system_message(
                "No metered turns recorded for this session yet (or the database is unreachable)."
            )
            return
        self.session.context.last_turn = {"tokens": usage, "cost_cents": usage.get("cost_cents")}
        self._refresh_panels()
        self.chat().add_system_message(
            f"[bold]Usage[/bold] Â· {usage['turns']} turn(s)\n"
            f"in {usage['input_tokens']} Â· out {usage['output_tokens']} Â· "
            f"total {usage['total_tokens']}\n"
            f"cost {_cost_label(usage.get('cost_cents'))} [dim](list-price estimate; "
            "NULL means the model has no known price)[/dim]"
        )

    def _cmd_doctor(self, _: str) -> None:
        checks: list[tuple[bool, str]] = []

        try:
            import config

            problems = config.require_config()
            checks.append((not problems, "config: " + ("ok" if not problems else "; ".join(problems))))
            checks.append((bool(config.chat_order()), f"chat chain: {', '.join(config.chat_order())}"))
        except Exception as exc:  # noqa: BLE001
            checks.append((False, f"config: {type(exc).__name__}: {exc}"))

        checks.append((self.bridge.get_mcp_status().startswith("ready"), f"mcp: {self.bridge.get_mcp_status()}"))

        try:
            sessions_dir = get_sessions_dir()
            probe = sessions_dir / ".write-probe"
            probe.write_text("ok")
            probe.unlink()
            checks.append((True, f"sessions: writable ({sessions_dir})"))
        except Exception as exc:  # noqa: BLE001
            checks.append((False, f"sessions: {type(exc).__name__}: {exc}"))

        checks.append((REPO_ROOT.exists(), f"repo root: {REPO_ROOT}"))
        checks.append(
            (
                bool(self._status.get("chat_order")),
                f"providers enabled: {', '.join(self._status.get('chat_order') or []) or 'none'}",
            )
        )

        lines = ["[bold]Doctor[/bold]"]
        for ok, detail in checks:
            lines.append(f"{'[green]PASS[/green]' if ok else '[red]FAIL[/red]'} {_escape(detail)}")
        self.chat().add_system_message("\n".join(lines))

    def _cmd_replay(self, argument: str) -> None:
        assert self.session is not None
        limit = 10
        if argument.isdigit():
            limit = max(1, int(argument))
        messages = self.session.messages[-limit:]
        if not messages:
            self.chat().add_system_message("Nothing to replay in this session yet.")
            return
        lines = [f"[bold]Replay[/bold] Â· last {len(messages)} message(s)"]
        for message in messages:
            who = {"user": "You", "assistant": "FEDS"}.get(message.role, message.role)
            model = f" ({message.model})" if message.model else ""
            lines.append(f"[dim]{who}{_escape(model)} Â· {message.ts[:19]}[/dim]\n{_escape(message.content)}")
        self.chat().add_system_message("\n\n".join(lines))

    def _cmd_compact(self, _: str) -> None:
        self.chat().add_system_message(
            "Compaction is not implemented yet. Planned: summarize older turns with the "
            "`summarize-component` skill and keep the JSON transcript on disk."
        )

    def _cmd_update(self, _: str) -> None:
        self.chat().add_system_message(
            f"FEDS CLI v{__version__} Â· running from {_escape(str(REPO_ROOT))}\n"
            "[dim]Update with `git pull` (dev checkout) or `uv tool install -e . --force` "
            "(installed tool). Automatic update checks are not wired yet.[/dim]"
        )

    # --- actions ----------------------------------------------------------

    def action_sessions(self) -> None:
        self._cmd_sessions("")

    def action_help(self) -> None:
        self._cmd_help("")

    def action_clear_chat(self) -> None:
        self._cmd_clear("")

    def action_toggle_context(self) -> None:
        panel = self.query_one(ContextPanel)
        panel.display = not panel.display

    def action_history_prev(self) -> None:
        if not self.history:
            return
        self.history_index = max(0, self.history_index - 1)
        self._set_input(self.history[self.history_index])

    def action_history_next(self) -> None:
        if not self.history:
            return
        self.history_index = min(len(self.history), self.history_index + 1)
        value = self.history[self.history_index] if self.history_index < len(self.history) else ""
        self._set_input(value)

    def _set_input(self, value: str) -> None:
        widget = self.query_one(PromptInput)
        widget.load_text(value)
        lines = value.split("\n")
        widget.move_cursor((len(lines) - 1, len(lines[-1])))

    def action_graceful_quit(self) -> None:
        if self.session is not None:
            save_session(self.session)
        self.exit()

    # --- session switching ------------------------------------------------

    def _resume(self, session_id: str) -> None:
        loaded = load_session(session_id)
        if loaded is None:
            self.chat().add_system_message(f"[red]No such session: {_escape(session_id)}[/red]")
            return
        self.session = loaded
        self.history = [m.content for m in loaded.messages if m.role == "user"]
        self.history_index = len(self.history)
        self.last_model = next(
            (m.model for m in reversed(loaded.messages) if m.model),
            None,
        )
        self.chat().reset()
        self.chat().add_system_message(
            f"Resumed [bold]{_escape(loaded.title)}[/bold] ({len(loaded.messages)} messages)."
        )
        self._refresh_panels()


# --- helpers -----------------------------------------------------------------


def _escape(value: str) -> str:
    """Neutralise Rich markup in user/model text."""
    return str(value).replace("[", r"\[")


def _short_path(path: str) -> str:
    text = str(path)
    if len(text) <= 34:
        return text
    return "â€¦" + text[-33:]


def _cost_label(value) -> str:
    if value is None:
        return "â€” [dim](unpriced)[/dim]"
    return f"${value / 100:.4f}"


def _git_root(path: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:  # noqa: BLE001 - git is optional
        return None
    return None


def _installed_skills() -> list[str]:
    try:
        import worker

        root = Path(getattr(worker, "SKILLS_ROOT", REPO_ROOT / ".claude" / "skills"))
    except Exception:  # noqa: BLE001
        root = REPO_ROOT / ".claude" / "skills"
    if not root.exists():
        return []
    return sorted(path.parent.name for path in root.glob("*/SKILL.md"))


def _conversation_usage(conversation_id: str) -> dict | None:
    """Token/cost rollup for one conversation, from the recorded turn rows."""
    try:
        import psycopg

        import config

        if not config.DATABASE_URL:
            return None
        with psycopg.connect(config.DATABASE_URL, connect_timeout=10) as conn:
            row = conn.execute(
                """
                SELECT count(*) AS turns,
                       coalesce(sum((result->>'input_tokens')::int), 0) AS input_tokens,
                       coalesce(sum((result->>'output_tokens')::int), 0) AS output_tokens,
                       coalesce(sum((result->>'total_tokens')::int), 0) AS total_tokens,
                       sum(cost_cents) AS cost_cents
                FROM capability_invocations
                WHERE conversation_id = %s AND capability = 'chat.turn'
                """,
                (conversation_id,),
            ).fetchone()
    except Exception:  # noqa: BLE001 - telemetry is optional
        return None
    if not row or not row[0]:
        return None
    return {
        "turns": int(row[0]),
        "input_tokens": int(row[1]),
        "output_tokens": int(row[2]),
        "total_tokens": int(row[3]),
        "cost_cents": row[4],
    }


HELP_MARKDOWN = """
# FEDS CLI

## Keys

| Key | Action |
|---|---|
| `Enter` | Send |
| `Ctrl+J` | Newline (Shift+Enter where the terminal reports it) |
| `Ctrl+L` | Clear transcript |
| `Ctrl+P` | Session picker |
| `Ctrl+K` | Toggle context panel |
| `Ctrl+Up` / `Ctrl+Down` | Prompt history |
| `F1` | This help |
| `Ctrl+C` | Save and quit |

## Commands

| Command | What it does |
|---|---|
| `/help` | This screen |
| `/clear` | Clear the transcript (session file keeps history) |
| `/reset` | Start a new session |
| `/sessions` | Open a saved session |
| `/whoami` | Identity, cwd, git root |
| `/version` | CLI version |
| `/model [name]` | Show the provider chain |
| `/skills` | List installed skills |
| `/mcp` | MCP status and tool list |
| `/cost` | Token/cost rollup for this session |
| `/replay [n]` | Reprint the last n messages |
| `/doctor` | Environment checks |
| `/compact` | Not implemented yet |
| `/update` | Show update instructions |
| `/exit` | Save and quit |

## Notes

- The worker runs in-process; turns are captured, so its logs never corrupt the screen.
- Sessions live in `.feds/sessions/` inside a repo, otherwise the platform data dir.
- Streaming token-by-token is not wired yet: a turn appears when the worker finishes.
"""


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="feds", description="FEDS CLI")
    parser.add_argument("session_id", nargs="?", help="resume this session id")
    parser.add_argument("--max-cost", type=int, default=None, dest="max_cost_cents")
    parser.add_argument("--max-time", type=int, default=None, dest="wall_clock_limit")
    return parser.parse_args(argv)


def main() -> None:
    """Console entry point."""
    args = _parse_args(sys.argv[1:])
    if not (REPO_ROOT / "worker.py").exists():
        print(
            f"FEDS CLI must run from the repository checkout (looked in {REPO_ROOT}).",
            file=sys.stderr,
        )
        raise SystemExit(2)
    app = FedsCLI(
        session_id=args.session_id,
        max_cost_cents=args.max_cost_cents,
        wall_clock_limit=args.wall_clock_limit,
    )
    app.run()


if __name__ == "__main__":
    main()
