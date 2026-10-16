"""Exercise the scoped MCP server's tools directly, outside the agent loop.

Isolates whether a tool failure comes from the server itself or from how the
agent calls it.
"""

import asyncio
import json
import os
import sys

os.environ.setdefault("MCP_TRANSPORT", "stdio")

from frontend_workspace_mcp import server as mcp_server  # noqa: E402


async def main() -> int:
    failures = 0

    print("=== save_task ===")
    try:
        result = await mcp_server.save_task(
            name="feds smoke test navbar",
            task=(
                "Build a responsive navbar component in vanilla HTML/CSS/JS. "
                "It must expose a visible focus ring, support dark mode, and "
                "keep tap targets at least 44px."
            ),
            framework="Vanilla HTML/CSS/JS",
            wcag_notes="Visible focus ring required; dark-mode contrast must pass AA.",
            responsiveness_notes="Collapse to a disclosure button below 768px.",
        )
        print("OK ", json.dumps(result, indent=2)[:400])
    except Exception as exc:  # noqa: BLE001
        failures += 1
        print(f"FAIL {type(exc).__name__}: {exc}")

    print()
    print("=== find_similar_tasks ===")
    try:
        result = await mcp_server.find_similar_tasks(
            description="an accessible responsive navigation bar with focus styles",
            limit=3,
        )
        print("OK ", json.dumps(result, indent=2)[:600])
    except Exception as exc:  # noqa: BLE001
        failures += 1
        print(f"FAIL {type(exc).__name__}: {exc}")

    print()
    print("=== lookup_task ===")
    try:
        result = await mcp_server.lookup_task(name="feds smoke test navbar")
        print("OK ", json.dumps(result, indent=2)[:300])
    except Exception as exc:  # noqa: BLE001
        failures += 1
        print(f"FAIL {type(exc).__name__}: {exc}")

    print()
    print("=== list_tasks ===")
    try:
        result = await mcp_server.list_tasks(limit=5)
        print(f"OK  count={result['count']}")
        for task in result["tasks"]:
            print(f"     - {task['name']} [{task['status']}/{task['framework']}]")
    except Exception as exc:  # noqa: BLE001
        failures += 1
        print(f"FAIL {type(exc).__name__}: {exc}")

    print()
    print("=== publish_task (must refuse unapproved) ===")
    try:
        await mcp_server.publish_task(name="feds smoke test navbar", target="staging")
        print("FAIL publish_task allowed an unapproved task")
        failures += 1
    except PermissionError as exc:
        print(f"OK  refused as designed: {exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"??  {type(exc).__name__}: {exc}")

    print()
    print(f"router status: {mcp_server.embedding_router().status()}")
    print(f"failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))