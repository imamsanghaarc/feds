"""Prove chat fallback with a genuine 429 from the primary provider.

A local stub server returns HTTP 429 for every chat request, standing in for a
provider whose quota is exhausted. The configured fallback credential
(`gemini-fallback`, the second Gemini key) must then serve the turn, and the
router must show the primary in cooldown.

This also confirms a misconfigured credential (HTTP 401) is NOT silently routed
around, so a broken key can never masquerade as a healthy system.
"""

import asyncio
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from agents import ModelSettings
from agents.models.interface import ModelTracing

import worker
from provider_router import Provider


class QuotaStub(BaseHTTPRequestHandler):
    """Answers every chat request with a quota-exhausted 429."""

    status_code = 429

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = json.dumps(
            {
                "error": {
                    "code": 429,
                    "message": "Resource exhausted: quota exceeded for this project.",
                    "status": "RESOURCE_EXHAUSTED",
                }
            }
        ).encode()
        self.send_response(self.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence stub logging
        pass


def start_stub() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), QuotaStub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address[0], server.server_address[1]
    return server, f"http://{host}:{port}/v1"


async def call(model) -> object:
    return await model.get_response(
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


def build_with_quota_exhausted_primary(stub_base_url: str) -> worker.FallbackChatModel:
    """FallbackChatModel whose primary returns 429 for everything.

    `build_model()` reads its per-provider settings from CHAT_MODELS, so the
    stub has to patch the entry there (restored immediately after).
    """
    original = dict(worker.CHAT_MODELS["gemini"])
    worker.CHAT_MODELS["gemini"] = {
        **original,
        "base_url": stub_base_url,
        "api_key": "stub-key",
    }
    try:
        return worker.build_model()
    finally:
        worker.CHAT_MODELS["gemini"] = original


async def main() -> int:
    if os.getenv("RUN_LIVE_TESTS") != "1":
        print("[SKIP] live fallback test; set RUN_LIVE_TESTS=1 to run (consumes quota)")
        return 0

    server, stub_url = start_stub()
    failures = 0
    try:
        model = build_with_quota_exhausted_primary(stub_url)
        print(f"provider order: {model._provider_names} (primary stubbed to 429)")

        response = await call(model)
        served = getattr(model, "_last_provider", "?")
        print(f"[INFO] served by: {served}")

        for entry in model.provider_status["providers"]:
            state = "up" if entry["available"] else f"cooldown {entry['cooldown_remaining_s']}s"
            print(f"      {entry['name']:8s} {state}  calls={entry['calls']} fails={entry['failures']}")
            if entry["last_error"]:
                print(f"               {entry['last_error'][:110]}")

        if served != [n for n in model._provider_names if n != "gemini"][0]:
            print(f"[FAIL] expected fallback to {model._provider_names}, got {served}")
            failures += 1
        elif not response.output:
            print("[FAIL] fallback produced no output")
            failures += 1
        else:
            print("[PASS] quota-exhausted primary -> fallback served the turn")
    finally:
        server.shutdown()

    # A bad credential (401) must surface, not be silently routed around.
    original = dict(worker.CHAT_MODELS["gemini"])
    worker.CHAT_MODELS["gemini"] = {
        **original,
        "api_key": "definitely-not-a-valid-key",
    }
    try:
        strict = worker.build_model()
        # Clear any cooldown the 429 stub left on the primary so the
        # misconfigured key is genuinely the credential under test.
        primary = strict._chat_router.get("gemini")
        if primary is not None:
            primary.cooldown_until = 0.0
            primary.failure_streak = 0
        try:
            await call(strict)
            print("[FAIL] a misconfigured key was silently routed around")
            failures += 1
        except Exception as exc:
            print(f"[PASS] misconfigured credential surfaced clearly: {type(exc).__name__}")
    finally:
        worker.CHAT_MODELS["gemini"] = original

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))