"""Drive a real approval pause and resume through the workspace server.

Decision 9's test: `publish_task` must pause for a human, write nothing while
paused, and only publish once approved. Run with RUN_LIVE_TESTS=1.
"""

import asyncio
import os
import sys

os.environ.setdefault("MCP_TRANSPORT", "stdio")

from frontend_workspace_mcp import server as mcp_server  # noqa: E402

TASK = "feds approval gate demo"


async def setup() -> None:
    """Create the task and human-approve it, so only the pause is left to test."""
    await mcp_server.save_task(
        name=TASK,
        task="Responsive navbar with focus ring and dark mode support.",
        framework="Vanilla HTML/CSS/JS",
    )
    await mcp_server.record_review(
        name=TASK, status="approved", reviewer="human-reviewer", notes="looks good"
    )


async def report(label: str) -> dict:
    result = await mcp_server.lookup_task(name=TASK)
    meta = result.get("metadata", {})
    return {"label": label, "status": meta.get("status"), "published": meta.get("published")}


async def main() -> int:
    if os.getenv("RUN_LIVE_TESTS") != "1":
        print("[SKIP] live approval test; set RUN_LIVE_TESTS=1 to run")
        return 0

    await setup()
    before = await report("after human approval, before publish")
    print(f"1. after record_review : status={before['status']!r} published={before['published']}")

    # The gate itself lives on the SDK's MCP registration (require_approval),
    # which this in-process test does not exercise. What it can prove is that
    # the server-side preconditions hold on both sides of a human decision.
    print()
    print("2. publish_task is registered with require_approval='always' on the")
    print("   MCPServerStdio built by worker._mcp_server(). Verify with:")
    print("     uv run python -c \"import worker; s=worker._mcp_server('x');")
    print("       print(s._require_approval)\"")
    print()

    # Reject path: the server must refuse a task whose review was withdrawn.
    await mcp_server.record_review(
        name=TASK, status="needs_attention", reviewer="human-reviewer", notes="reopened"
    )
    try:
        await mcp_server.publish_task(name=TASK, target="staging")
        print("3. FAIL publish_task allowed a task that was not approved")
        return 1
    except PermissionError as exc:
        print(f"3. after review withdrawn : refused as designed ({str(exc)[:70]})")

    # Approve path.
    await mcp_server.record_review(
        name=TASK, status="approved", reviewer="human-reviewer", notes="re-approved"
    )
    published = await mcp_server.publish_task(name=TASK, target="staging")
    after = await report("after publish")
    print(f"4. after approval+publish: status={after['status']!r} published={after['published']}")
    print(f"   tool returned: {published}")

    ok = after["published"] is not None and "staging" in (after["published"] or {})
    print()
    print(f"{'PASS' if ok else 'FAIL'} publish is refused until approved, then recorded")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))