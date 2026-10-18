"""Prove operator authorization live, with zero model quota.

Creates a disposable conversation and a parked approval run, then tries to
decide it as an operator the policy does not allow. Asserts the decision is
refused, the parked run is untouched, and the refusal lands on the trail.
Everything it created is deleted afterwards, so it is safe to re-run.

    uv run python smoke_operator_auth.py
"""

from __future__ import annotations

import asyncio
import os
import uuid

import psycopg

import worker
from config import DEFAULT_OPERATOR, NEON_DATABASE_URL

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def cleanup(session_id: str, run_id: str) -> None:
    with psycopg.connect(NEON_DATABASE_URL) as conn:
        conn.execute("DELETE FROM run_states WHERE run_id = %s", (run_id,))
        conn.execute("DELETE FROM audit_log WHERE conversation_id = %s", (session_id,))
        conn.execute("DELETE FROM conversations WHERE session_id = %s", (session_id,))
        conn.commit()


def main() -> int:
    session_id = f"smoke-operator-{uuid.uuid4().hex}"
    run_id = f"smoke-run-{uuid.uuid4().hex}"
    saved = os.environ.pop("FEDS_ALLOWED_OPERATORS", None)

    try:
        with psycopg.connect(NEON_DATABASE_URL) as conn:
            conn.execute(
                "INSERT INTO conversations (session_id, user_id) VALUES (%s, %s)",
                (session_id, "smoke-operator"),
            )
            conn.execute(
                "INSERT INTO run_states (run_id, conversation_id, tool_name, state_text, status) "
                "VALUES (%s, %s, 'publish_task', '{}', 'awaiting')",
                (run_id, session_id),
            )
            conn.commit()

        # No allowlist: local mode, where only the default operator may decide.
        refused = asyncio.run(worker.decide_run(run_id, "approve", "smoke-stranger"))
        check("an unauthorized operator is refused", refused is False, f"returned {refused!r}")

        with psycopg.connect(NEON_DATABASE_URL) as conn:
            row = conn.execute(
                "SELECT status, operator FROM run_states WHERE run_id = %s", (run_id,)
            ).fetchone()
        check(
            "the parked run is untouched",
            row is not None and row[0] == "awaiting" and row[1] is None,
            str(row),
        )

        with psycopg.connect(NEON_DATABASE_URL) as conn:
            audit = conn.execute(
                "SELECT payload, result FROM audit_log WHERE conversation_id = %s "
                "AND payload->>'event' = 'approval_refused' ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        check("the refusal is on the trail", audit is not None, str(audit))
        if audit:
            payload, result = audit
            check(
                "the refusal names the operator",
                payload.get("operator") == "smoke-stranger",
                str(payload),
            )
            check(
                "the refusal is marked refused",
                result.get("status") == "refused",
                str(result),
            )

        # A list is a policy, not a blanket refusal: the default operator still
        # passes while no list is set. A real resume needs a live model and is
        # proven separately by test_approval_gate.py.
        check(
            "the default operator passes policy when no list is set",
            worker.operator_authorized(DEFAULT_OPERATOR),
        )
        os.environ["FEDS_ALLOWED_OPERATORS"] = "dana"
        check(
            "a configured list admits its members",
            worker.operator_authorized("dana"),
        )
        check(
            "a configured list excludes the anonymous default",
            not worker.operator_authorized(DEFAULT_OPERATOR),
        )
    finally:
        os.environ.pop("FEDS_ALLOWED_OPERATORS", None)
        if saved is not None:
            os.environ["FEDS_ALLOWED_OPERATORS"] = saved
        cleanup(session_id, run_id)

    if FAILURES:
        print(f"\n{len(FAILURES)} CHECKS FAILED: {FAILURES}")
        return 1
    print("\nOPERATOR AUTHORIZATION SMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
