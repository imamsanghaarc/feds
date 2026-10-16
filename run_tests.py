"""Run the offline test suite for FEDS, the Frontend Engineering Digital Specialist.

Every check here works without a model provider, so the suite is meaningful even
while quotas are exhausted.

    uv run python run_tests.py

Live provider checks are opt-in:
    set RUN_LIVE_TESTS=1 && uv run python test_chat_fallback.py
    uv run python test_config.py --strict
"""

from __future__ import annotations

import subprocess
import sys

OFFLINE_SUITE = [
    ("config wiring", "test_config.py", ["--offline"]),
    ("provider fallback router", "test_provider_router.py", []),
    ("guardrails and inputs", "test_worker_offline.py", []),
]

LIVE_SUITE = [
    ("chat provider fallback", "test_chat_fallback.py", []),
    ("forced quota rotation", "test_fallback_forced.py", []),
]


def run(label: str, script: str, args: list[str]) -> bool:
    print(f"\n=== {label} ({script}) ===")
    result = subprocess.run(
        [sys.executable, script, *args],
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    print(output.strip())
    ok = result.returncode == 0
    print(f"--- {label}: {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    results = [run(label, script, args) for label, script, args in OFFLINE_SUITE]

    import os

    if os.getenv("RUN_LIVE_TESTS") == "1":
        results += [run(label, script, args) for label, script, args in LIVE_SUITE]
    else:
        print("\n=== live provider tests ===\n[SKIP] set RUN_LIVE_TESTS=1 to run")

    passed = sum(results)
    print(f"\n{passed}/{len(results)} suites passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())