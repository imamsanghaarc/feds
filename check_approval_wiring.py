"""Show which workspace tools are approval-gated, using the real SDK objects."""

import asyncio

import worker


async def main() -> None:
    server = worker._mcp_server("test-conversation")
    print(f"approval policy: {server._needs_approval_policy}")
    print()
    async with server:
        tools = await server.list_tools()
        print(f"{len(tools)} tools exposed by frontend-workspace:")
        gated = []
        for tool in tools:
            needs = server._get_needs_approval_for_tool(tool, None)
            flag = True if callable(needs) else bool(needs)
            if flag:
                gated.append(tool.name)
            status = "GATED (pauses for a human)" if flag else "free"
            print(f"   {tool.name:22s} {status}")

    print()
    print(f"gated: {gated}")
    expected = ["publish_task"]
    ok = gated == expected
    print(f"{'PASS' if ok else 'FAIL'} only {expected} should be gated")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())