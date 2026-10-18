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
    # Collisions found by the first eval run, kept as regression cases.
    {
        "id": "should-fire-summarize-despite-escalate",
        "prompt": "Give me a note on this navbar bug before I escalate it.",
        "expect": "summarize-component",
        "why": "asks for a note; 'escalate' must not hijack it",
    },
    {
        "id": "should-fire-escalate-qa-blocked",
        "prompt": "QA blocked this on accessibility grounds and the user is frustrated. Hand it off.",
        "expect": "escalate-review",
        "why": "review blocked it; no proof of a build attempt needed",
    },
    {
        "id": "should-not-fire-reference-skill-ok",
        "prompt": "Find the latest MDN documentation about container queries.",
        "expect": None,
        "why": "a reference skill may load; no workflow skill should",
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
        # A reference skill (css, html, typescript...) firing on a frontend
        # question is exactly what progressive disclosure is for, so it is not a
        # false positive. Only a *workflow* skill firing is a miss.
        fired_workflow = chosen in WORKFLOW_SKILLS
        passed = not fired_workflow
        observed = chosen or "none"
        if not passed:
            observed = f"{chosen} (workflow skill)"
    else:
        passed = chosen == expected
        observed = chosen or "none"

    return {**case, "chosen": observed, "passed": passed, "raw": output[:200]}


RESULTS_PATH = "eval_trigger_results.json"


def _load_previous() -> dict[str, dict]:
    """Load prior results so a run can resume across quota cycles."""
    from pathlib import Path

    path = Path(RESULTS_PATH)
    if not path.is_file():
        return {}
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {row["id"]: row for row in prior if isinstance(row, dict) and "id" in row}


def _save(rows: list[dict]) -> None:
    from pathlib import Path

    Path(RESULTS_PATH).write_text(
        json.dumps(rows, indent=2, default=str), encoding="utf-8"
    )


async def main() -> int:
    if os.getenv("RUN_LIVE_TESTS") != "1":
        print("[SKIP] trigger eval; set RUN_LIVE_TESTS=1 to run (consumes quota)")
        return 0

    only = set(sys.argv[1:]) or None
    previous = _load_previous()

    fresh: list[dict[str, object]] = []
    skipped = 0
    for case in CASES:
        case_id = str(case["id"])
        if only and case_id not in only:
            continue

        prior = previous.get(case_id)
        if prior and "error" not in prior and not os.getenv("RETRY_ALL"):
            print(f"[CACHED] {case_id:34s} {prior.get('chosen')}")
            continue

        outcome = await run_case(case)
        fresh.append(outcome)
        if "error" in outcome:
            skipped += 1
            print(f"[SKIP] {case_id:34s} {str(outcome['error'])[:56]}")
            if "Exhausted" in str(outcome["error"]):
                print("      (provider exhausted; stopping this run)")
                break
            continue
        mark = "PASS" if outcome["passed"] else "FAIL"
        print(
            f"[{mark}] {case_id:34s} expected={str(outcome['expect']):22s} "
            f"got={outcome['chosen']}"
        )

    # Merge fresh results over any previous ones, keyed by case id.
    merged = dict(previous)
    merged.update({row["id"]: row for row in fresh})
    ordered = [merged[str(c["id"])] for c in CASES if str(c["id"]) in merged]
    _save(ordered)

    scored = [r for r in ordered if "error" not in r]
    passed = sum(1 for r in scored if r["passed"])
    outstanding = [c for c in CASES if str(c["id"]) not in merged]

    print()
    print(f"trigger accuracy: {passed}/{len(scored)} scored")
    for row in scored:
        if not row["passed"]:
            print(f"  MISS {row['id']}: expected={row['expect']} got={row['chosen']}")
    if outstanding:
        print(f"not yet run   : {[str(c['id']) for c in outstanding]}")
    print(f"wrote {RESULTS_PATH}")

    if outstanding or skipped:
        print("\nINCOMPLETE. Re-run later; completed cases are cached.")
        return 2
    return 0 if passed == len(scored) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))