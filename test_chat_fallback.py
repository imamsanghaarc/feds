"""Live check: the chat model must work on whichever provider still has quota.

Runs one real model call through the FallbackChatModel and prints which provider
served it, then reports the router's view of provider health.
"""

import asyncio
import os
import sys

from agents import ModelSettings
from agents.models.interface import ModelTracing

import worker


async def main() -> int:
    if os.getenv("RUN_LIVE_TESTS") != "1":
        print("[SKIP] live model call; set RUN_LIVE_TESTS=1 to run (consumes quota)")
        return 0

    model = worker.build_model()
    print(f"provider order: {model._provider_names}")

    try:
        result = await model.get_response(
            system_instructions="You are a terse assistant.",
            input="Reply with exactly: ONLINE",
            model_settings=ModelSettings(),
            tools=[],
            output_schema=None,
            handoffs=[],
            tracing=ModelTracing.DISABLED,
            previous_response_id=None,
            conversation_id=None,
        )
    except Exception as exc:
        print(f"[FAIL] no provider could serve a call: {exc}")
        return 1

    text_out = str(result.output or "")
    print(f"[OK] served by: {getattr(model, '_last_provider', '?')}")
    print(f"     output: {text_out[:80]!r}")
    print(f"     usage: {getattr(result, 'usage', None)}")

    status = model.provider_status
    for entry in status["providers"]:
        state = "up" if entry["available"] else f"cooldown {entry['cooldown_remaining_s']}s"
        print(f"     {entry['name']:8s} {state}  calls={entry['calls']} fails={entry['failures']}")
        if entry["last_error"]:
            print(f"              last_error: {entry['last_error'][:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))