"""Skill trigger evaluation for FEDS.

Concept 3: the `description` is the trigger surface. Whether a skill fires is
decided from its frontmatter description alone, so precision and false-positive
rate are the numbers that matter.

Method
------
Each case names a skill that SHOULD fire or SHOULD stay quiet. For each case the
agent is given the skill index and asked to pick a skill and load it. A run
passes when the expected skill was loaded (should-fire) or when no workflow skill
was loaded (should-not-fire).

Only the 5 authored workflow skills count as "a skill fired"; the language and
framework skills are reference material, and loading `frontend-development` for
a generic frontend question is not a trigger miss.

Run:  set RUN_LIVE_TESTS=1 && uv run python eval_triggers.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys

import worker
from agents import Runner

# Cases mirror eval_set.md, expressed against FEDS's own skills.
# expect: a skill name, or None meaning "no workflow skill should load".
CASES: list[dict[str, object]] = [
    {
        "id": "should-fire-summarize",
        "prompt": "Write a handoff note for the navbar task before I escalate this.",
        "expect": "summarize-component",
        "why": "handoff phrasing, never says summarize",
    },
    {
        "id": "should-fire-similar",
        "prompt": "Have we built a responsive navbar like this before? Check the workspace.",
        "expect": "find-similar-components",
        "why": "prior-art question before net-new work",
    },
    {
        "id": "should-fire-escalate",
        "prompt": "QC blocked this on WCAG grounds and the user is frustrated. I need this handed off.",
        "expect": "escalate-review",
        "why": "accessibility risk plus negative sentiment",
    },
    {
        "id": "should-not-fire-link-color",
        "prompt": "Change the link color to #1a5fb4.",
        "expect": None,
        "why": "one-line CSS change needs no workflow skill",
    },
    {
        "id": "should-not-fire-framework-advice",
        "prompt": "What framework should I use for a small marketing site?",
        "expect": None,
        "why": "advice, not a handoff, search, or escalation",
    },
    {
        "id": "should-not-fire-summarize-lookalike",
        "prompt": "Draft a friendly reply to the customer who says the page is slow.",
        "expect": None,
        "why": "look-alike for summarize-component",
    },
    {
        "id": "should-not-fire-similar-lookalike",
        "prompt": "Find the latest MDN documentation about container queries.",
        "expect": None,
        "why": "look-alike for find-similar-components (docs, not our workspace)",
    },
    {
        "id": "should-fire-escalate-explicit",
        "prompt": "Please hand this over to another engineer, I am not confident in this fix.",
        "expect": "escalate-review",
        "why": "explicit human-review request",
    },
]

WORKFLOW_SKILLS = {
    "summarize-component",
    "find-similar-components",
    "escalate-review",
    "frontend-workspace",
}

LOAD_RE = re.compile(r"load(?:ed|ing)?(?:_skill)?[:\s\"']*([a-z0-9\-]+)", re.I)


def build_trigger_agent():
    """An agent whose only job is to pick a skill and load it."""
    agent, _ = worker.build_agent()
    agent.instructions = (
        "You select exactly one skill for the request, then load it.\n\n"
        "Reply in this exact format and nothing else:\n"
        "SKILL: <name>\n"
        "or\n"
        "SKILL: none\n\n"
        f"Available skills:\n{worker._skill_index()}\n"
    )
    return agent


async def run_case(case: dict[str, object]) -> dict[str, object]:
    agent = build_trigger_agent()
    try:
        result = await Runner.run(agent, str(case["prompt"]))
        output = str(result.final_output or "")
    except Exception as exc:  # noqa: BLE001
        return {**case, "error": f"{type(exc).__name__}: {exc}"}

    match = re.search(r"SKILL:\s*([a-z0-9\-]+)", output, re.I)
    chosen = (match.group(1) if match else "").strip().lower()
    if chosen in {"none", "no", ""}:
        chosen = None

    # Fall back to scanning for a skill that was actually loaded.
    if chosen is None:
        for candidate in WORKFLOW_SKILLS:
            if re.search(rf"\b{re.escape(candidate)}\b", output, re.I):
                chosen = candidate
                break

    expected = case["expect"]
    if expected is None:
        passed = chosen is None
        observed: object = chosen or "none"
    else:
        passed = chosen == expected
        observed = chosen or "none"

    return {**case, "chosen": observed, "passed": passed, "raw": output[:200]}


async def main() -> int:
    if os.getenv("RUN_LIVE_TESTS") != "1":
        print("[SKIP] trigger eval; set RUN_LIVE_TESTS=1 to run (consumes quota)")
        return 0

    results: list[dict[str, object]] = []
    skipped = 0
    for case in CASES:
        outcome = await run_case(case)
        results.append(outcome)
        if "error" in outcome:
            skipped += 1
            print(f"[SKIP] {outcome['id']:34s} {str(outcome['error'])[:60]}")
            # A dead provider will not recover mid-run; stop and report honestly
            # rather than burning one call per remaining case.
            if "Exhausted" in str(outcome["error"]):
                print("      (provider exhausted; stopping this run)")
                break
            continue
        mark = "PASS" if outcome["passed"] else "FAIL"
        print(
            f"[{mark}] {outcome['id']:34s} expected={str(outcome['expect']):22s} "
            f"got={outcome['chosen']}"
        )

    scored = [r for r in results if "error" not in r]
    passed = sum(1 for r in scored if r["passed"])
    print()
    suffix = f" ({skipped} not scored)" if skipped else ""
    print(f"trigger accuracy: {passed}/{len(scored)} scored{suffix}")
    for row in results:
        if "error" not in row and not row["passed"]:
            print(f"  MISS {row['id']}: {row['raw'][:120]!r}")

    Path = __import__("pathlib").Path
    Path("eval_trigger_results.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )
    print("wrote eval_trigger_results.json")

    if skipped:
        print("\nINCOMPLETE: some cases could not be scored. Do not report this as a")
        print("final accuracy figure; re-run when a provider has quota.")
        return 2
    return 0 if passed == len(scored) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))