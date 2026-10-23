"""Headless smoke check for the FEDS TUI.

Textual needs a real terminal, so `uv run feds` cannot be inspected from a
script. This drives the same App through Textual's Pilot instead: it renders
the layout, exercises every cheap slash command, opens both modals, and
optionally runs one real worker turn.

    uv run python -m feds_cli.smoke           # no model quota consumed
    uv run python -m feds_cli.smoke --live    # one real turn (quota + DB)

Exit code 0 means every check passed. Failures print the rendered screen so a
layout or wiring regression is visible without a TTY.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from feds_cli.main import ChatView, FedsCLI, HelpScreen, SessionPickerScreen

SIZE = (120, 42)
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}")
    if not condition:
        FAILURES.append(f"{label} — {detail}" if detail else label)


def safe_print(text: str) -> None:
    """Print even on a legacy Windows code page."""
    stream = sys.__stdout__ or sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(encoding, "replace").decode(encoding, "replace"))


def screen_text(app: FedsCLI) -> str:
    strips = app.screen._compositor.render_strips()
    return "\n".join(strip.text for strip in strips).rstrip()


async def exercise(live: bool) -> int:
    app = FedsCLI()
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()

        screen = screen_text(app)
        check("layout renders", "Frontend Engineering Digital Specialist" in screen)
        check("banner shows the product name", "#####" in screen or "██" in screen)
        check("worker preloaded", app.preload_error is None, str(app.preload_error))
        check("session created", app.session is not None)
        check("status bar populated", "session" in screen.lower())

        for command in ("/version", "/whoami", "/model", "/skills", "/cost", "/doctor", "/replay"):
            app._handle_command(command)
            await pilot.pause()
        transcript = app.query_one(ChatView)._transcript
        check("slash commands write to the transcript", "Doctor" in transcript and "PASS" in transcript)
        app._handle_command("/definitely-not-a-command")
        await pilot.pause()
        check(
            "unknown command message",
            "Unknown command" in app.query_one(ChatView)._transcript,
        )

        app._handle_command("/help")
        await pilot.pause()
        check("help modal opens", isinstance(app.screen, HelpScreen), type(app.screen).__name__)
        await pilot.press("escape")
        await pilot.pause()
        check("help modal closes", not isinstance(app.screen, HelpScreen))

        app._handle_command("/sessions")
        await pilot.pause()
        check(
            "session picker opens",
            isinstance(app.screen, SessionPickerScreen),
            type(app.screen).__name__,
        )
        await pilot.press("escape")
        await pilot.pause()
        check("session picker closes", not isinstance(app.screen, SessionPickerScreen))

        # Enter submits; an unknown command must not touch the worker.
        app.query_one("PromptInput").load_text("/nope")
        await pilot.press("enter")
        await pilot.pause()
        check("enter submits", "/nope" not in app.query_one("PromptInput").text)
        check(
            "submission handled in-app",
            "Unknown command" in app.query_one(ChatView)._transcript,
        )

        if live:
            before = len(app.session.messages)
            app.query_one("PromptInput").load_text("Reply with exactly: CLI_SMOKE_OK")
            await pilot.press("enter")
            for _ in range(240):
                await pilot.pause(0.5)
                if not app._busy:
                    break
            check("live turn finishes", not app._busy)
            answers = [m.content for m in app.session.messages[before:] if m.role == "assistant"]
            check("live turn captured", any("CLI_SMOKE_OK" in text for text in answers), str(answers))
            check("usage recorded", bool(app.session.context.last_turn.get("tokens")))

        if FAILURES:
            safe_print("\n--- rendered screen ---")
            safe_print(screen_text(app))
            safe_print("\n--- transcript ---")
            safe_print(app.query_one(ChatView)._transcript[-2000:])

    return 1 if FAILURES else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Headless FEDS CLI smoke check")
    parser.add_argument("--live", action="store_true", help="also run one real worker turn")
    args = parser.parse_args()
    code = asyncio.run(exercise(args.live))
    print("\nSMOKE PASS" if code == 0 else f"\nSMOKE FAIL ({len(FAILURES)})")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
