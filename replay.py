"""Reconstruct a conversation from the audit trail.

The narrative lives in `audit_log` and the quantitative trace lives in
`capability_invocations`. This joins both for one conversation so a run can be
replayed and regression-checked after the fact.

Usage:
    uv run python replay.py                       # list recent conversations
    uv run python replay.py <conversation_id>     # replay one conversation
    uv run python replay.py <conversation_id> --json
"""

from __future__ import annotations

import argparse
import json
import sys

import psycopg

from config import NEON_DATABASE_URL

CONVERSATION_QUERY = """
    SELECT c.session_id,
           c.user_id,
           c.started_at,
           c.ended_at,
           c.summary,
           (SELECT count(*) FROM audit_log a WHERE a.conversation_id = c.session_id) AS audit_rows,
           (SELECT count(*) FROM capability_invocations v
              WHERE v.conversation_id = c.session_id) AS capability_rows
    FROM conversations c
    ORDER BY c.started_at DESC
    LIMIT %s
"""

REPLAY_QUERY = """
    SELECT created_at, actor, action, target, payload, result
    FROM audit_log
    WHERE conversation_id = %s
    ORDER BY created_at ASC, id ASC
"""

CAPABILITY_QUERY = """
    SELECT created_at, capability, arguments, status, latency_ms, cost_cents
    FROM capability_invocations
    WHERE conversation_id = %s
    ORDER BY created_at ASC
"""


def list_conversations(limit: int) -> int:
    with psycopg.connect(NEON_DATABASE_URL) as conn:
        rows = conn.execute(CONVERSATION_QUERY, (limit,)).fetchall()
    if not rows:
        print("no conversations recorded yet")
        return 0
    print(f"{'session id':34s} {'audit':>6s} {'tools':>6s}  summary")
    for session_id, _user_id, _started, _ended, summary, audit_rows, cap_rows in rows:
        text = (summary or "")[:52].replace("\n", " ")
        print(f"{session_id:34s} {audit_rows:6d} {cap_rows:6d}  {text}")
    return 0


def replay(conversation_id: str, as_json: bool) -> int:
    with psycopg.connect(NEON_DATABASE_URL) as conn:
        header = conn.execute(
            "SELECT session_id, user_id, started_at, ended_at, summary "
            "FROM conversations WHERE session_id = %s",
            (conversation_id,),
        ).fetchone()
        if header is None:
            print(f"conversation not found: {conversation_id}")
            return 1
        audit = conn.execute(REPLAY_QUERY, (conversation_id,)).fetchall()
        capabilities = conn.execute(CAPABILITY_QUERY, (conversation_id,)).fetchall()

    if as_json:
        print(
            json.dumps(
                {
                    "conversation": {
                        "session_id": header[0],
                        "user_id": header[1],
                        "started_at": header[2].isoformat() if header[2] else None,
                        "ended_at": header[3].isoformat() if header[3] else None,
                        "summary": header[4],
                    },
                    "audit": [
                        {
                            "at": row[0].isoformat(),
                            "actor": row[1],
                            "action": row[2],
                            "target": row[3],
                            "payload": row[4],
                            "result": row[5],
                        }
                        for row in audit
                    ],
                    "capabilities": [
                        {
                            "at": row[0].isoformat(),
                            "capability": row[1],
                            "arguments": row[2],
                            "status": row[3],
                            "latency_ms": row[4],
                            "cost_cents": row[5],
                        }
                        for row in capabilities
                    ],
                },
                indent=2,
                default=str,
            )
        )
        return 0

    print(f"conversation : {header[0]}")
    print(f"user         : {header[1]}")
    print(f"started      : {header[2]}")
    print(f"ended        : {header[3] or '(still open)'}")
    print(f"summary      : {header[4]}")
    print(f"\n--- audit trail ({len(audit)} rows) ---")
    for row in audit:
        target = f" -> {row[3]}" if row[3] else ""
        detail = ""
        if isinstance(row[4], dict):
            detail = ", ".join(f"{k}={v!r}" for k, v in list(row[4].items())[:3])
            detail = f" [{detail}]" if detail else ""
        print(f"{row[0].strftime('%H:%M:%S')} {row[1]:34s} {row[2]:20s}{target}{detail}")

    print(f"\n--- capability metrics ({len(capabilities)} rows) ---")
    if not capabilities:
        print("(none recorded)")
    total_latency = 0
    for row in capabilities:
        latency = row[4] or 0
        total_latency += latency
        print(
            f"{row[0].strftime('%H:%M:%S')} {row[1]:24s} {row[3]:8s} {latency:6d} ms"
            + (f"  cost={row[5]}c" if row[5] else "")
        )
    if capabilities:
        failures = sum(1 for row in capabilities if row[3] != "ok")
        print(
            f"\n{len(capabilities)} calls, {failures} failed, "
            f"{total_latency} ms total, "
            f"{round(total_latency / len(capabilities))} ms average"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("conversation_id", nargs="?", default=None)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--limit", type=int, default=15, help="conversations to list")
    args = parser.parse_args()

    if not args.conversation_id:
        return list_conversations(args.limit)
    return replay(args.conversation_id, args.json)


if __name__ == "__main__":
    sys.exit(main())