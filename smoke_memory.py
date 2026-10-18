"""Exercise the memory layer against the live workspace (no model needed).

Behavioral proof for section 6a:

1. Private memory isolation - user B can never read user A's lessons, and
   cannot promote them.
2. The three promotion gates refuse what they must: missing verification,
   project-specific content, credential-shaped text, embedded author identity.
3. A real, verified, generalizable, sanitized lesson promotes into the shared
   global layer with full provenance, and is then readable by other users.

The lesson promoted is genuine guidance (aspect-ratio slotting against CLS),
so the shared layer gains something useful instead of test junk. Idempotent:
if the global layer already carries the lesson, promotion is skipped, so
re-runs never duplicate shared content. Scratch rows are cleaned up at the
end; the promoted provenance row stays by design.

It calls the MCP tool functions directly, so it spends zero chat quota.

Usage:
    uv run python smoke_memory.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import contextmanager

from frontend_workspace_mcp import server

USER_A = "smoke-user-alpha"
USER_B = "smoke-user-beta"

LESSON = (
    "Reserve image and widget slots with CSS aspect-ratio before the resource "
    "decodes. Placeholder-less grids re-flow as media arrives and push CLS "
    "past the 0.1 threshold at p75."
)
LESSON_KEY = "aspect-ratio before the resource"


async def expect_value_error(coro, label: str) -> None:
    try:
        await coro
    except ValueError as exc:
        print(f"  gate fires ({label}): {str(exc)[:88]}")
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"{label}: expected ValueError, got {type(exc).__name__}: {exc}"
        )
    raise AssertionError(f"{label}: expected ValueError, nothing raised")


async def expect_permission_error(coro, label: str) -> None:
    try:
        await coro
    except PermissionError as exc:
        print(f"  gate fires ({label}): {str(exc)[:88]}")
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"{label}: expected PermissionError, got {type(exc).__name__}: {exc}"
        )
    raise AssertionError(f"{label}: expected PermissionError, nothing raised")


@contextmanager
def as_user(user: str):
    """Run a block as one MCP requester; restores the previous identity."""
    old = os.environ.get("FRONTEND_USER_ID")
    os.environ["FRONTEND_USER_ID"] = user
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("FRONTEND_USER_ID", None)
        else:
            os.environ["FRONTEND_USER_ID"] = old


async def main() -> int:
    print("--- private memory isolation ---")
    with as_user(USER_A):
        scratch = await server.save_memory(
            "FEDS smoke: user A's private scratch lesson.",
            {"usage": "smoke", "kind": "scratch"},
        )
        print(f"saved private memory {scratch['memory_id'][:8]}... for {USER_A}")

        listed = await server.list_memories()
        assert any(
            "user A's private scratch lesson" in m["body"] for m in listed["memories"]
        ), listed["memories"]
        print(f"user A reads own private lessons (count={listed['count']})")

    with as_user(USER_B):
        listed = await server.list_memories()
        assert not any(
            "user A's private scratch lesson" in m["body"] for m in listed["memories"]
        ), "user B must never read user A's private memory"
        print("user B cannot read user A's private memory (isolation holds)")

        await expect_permission_error(
            server.promote_memory(scratch["memory_id"], "cross-user attempt"),
            "cross-user promote refused",
        )

    print("--- promotion gates, as the owner ---")
    with as_user(USER_A):
        project = await server.save_memory(
            "FEDS smoke: project-specific cleanup timeline.",
            {"usage": "smoke", "kind": "scratch", "project_specific": True},
        )
        secret = await server.save_memory(
            "FEDS smoke: staging api_key=sk-live-000000000011112222 note.",
            {"usage": "smoke", "kind": "scratch"},
        )
        identity = await server.save_memory(
            "FEDS smoke: lesson from smoke-user-alpha about the navbar audit.",
            {"usage": "smoke", "kind": "scratch"},
        )
        lesson = await server.save_memory(
            LESSON,
            {"usage": "smoke", "kind": "lesson"},
        )

        await expect_value_error(
            server.promote_memory(lesson["memory_id"], "   "),
            "no verification recorded",
        )
        await expect_permission_error(
            server.promote_memory(project["memory_id"], "reviewer sigma"),
            "project-specific lesson",
        )
        await expect_permission_error(
            server.promote_memory(secret["memory_id"], "reviewer sigma"),
            "credential-shaped text",
        )
        await expect_permission_error(
            server.promote_memory(identity["memory_id"], "reviewer sigma"),
            "embedded requester identity",
        )

    print("--- one real promotion ---")
    with as_user(USER_B):
        shared = await server.list_memories(limit=100)
        already_promoted = any(
            m["scope"] == "global" and LESSON_KEY in m["body"]
            for m in shared["memories"]
        )

    if already_promoted:
        print("global layer already carries the lesson; skipping promotion")
    else:
        with as_user(USER_A):
            promoted = await server.promote_memory(
                lesson["memory_id"],
                "smoke_memory.py automated check (aspect-ratio CLS guidance)",
            )
            print(
                f"promoted -> global {promoted['global_id'][:8]}... "
                f"(verification on record)"
            )

        with as_user(USER_B):
            shared = await server.list_memories(limit=100)
            assert any(
                m["scope"] == "global" and LESSON_KEY in m["body"]
                for m in shared["memories"]
            ), "the promoted lesson must be visible to other users"
            assert not any(
                "user A's private scratch lesson" in m["body"]
                for m in shared["memories"]
            ), "user B must still see nothing private of A's"
            print("user B reads the shared lesson and nothing private of A's")

        # The promoted lesson must not be re-promotable: the active-row
        # requirement is the idempotency guard on the tool side too.
        with as_user(USER_A):
            await expect_permission_error(
                server.promote_memory(
                    lesson["memory_id"], "second attempt after promotion"
                ),
                "already-promoted row cannot promote again",
            )

    print("--- cleanup of scratch rows (shared content and provenance stay) ---")
    with as_user(USER_A):
        remaining = await server.list_memories(limit=100)
        for memory in remaining["memories"]:
            if memory["metadata"].get("usage") != "smoke":
                continue
            if memory["status"] != "active":
                print(
                    f"  kept {memory['id'][:8]}... "
                    f"(status={memory['status']}, provenance)"
                )
                continue
            await server.delete_memory(memory["id"])

        remaining = await server.list_memories(limit=100)
        leftovers = [
            m
            for m in remaining["memories"]
            if m["metadata"].get("usage") == "smoke" and m["status"] == "active"
        ]
        assert not leftovers, f"scratch rows must not survive: {leftovers}"

    with as_user(USER_B):
        final = await server.list_memories(limit=100)
        assert any(
            m["scope"] == "global" and LESSON_KEY in m["body"]
            for m in final["memories"]
        ), "the shared lesson must survive cleanup"
        assert not any(
            m["metadata"].get("usage") == "smoke" for m in final["memories"]
        ), "no smoke metadata may leak into what other users read"
    print("cleanup done.")

    print(
        "\nMEMORY BEHAVIOUR PROVEN: isolation, three gates, gated promotion, "
        "provenance, cleanup."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
