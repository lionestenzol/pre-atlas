"""MCP server exposing fest_py.FestClient as tools over stdio."""

from typing import Optional

from mcp.server.fastmcp import FastMCP

from fest_py.client import FestClient, FestError

fest = FestClient()
mcp = FastMCP("fest")


@mcp.tool()
def fest_list(status: Optional[str] = None, include_dungeon: bool = False) -> list[dict]:
    """List festivals.

    status: one of "active", "planning", "completed", "dungeon", "dungeon/completed",
            "dungeon/archived", "dungeon/someday". None = active + planning.
    include_dungeon: pass True to include completed and dungeon festivals.
    """
    return [f.model_dump() for f in fest.list(status, all_=include_dungeon)]


@mcp.tool()
def fest_progress(festival: str) -> dict:
    """Return detailed progress (per-phase, per-sequence, per-task) for a festival."""
    return fest.progress(festival).model_dump()


@mcp.tool()
def fest_next(festival: str) -> dict:
    """Return the next actionable task in a festival, with parallel-group and reason."""
    return fest.next(festival).model_dump()


@mcp.tool()
def fest_status() -> dict:
    """Return top-level fest system status."""
    return fest.status()


@mcp.tool()
def fest_promote(festival: str, dungeon: Optional[str] = None, force: bool = False) -> str:
    """Promote a festival through its lifecycle.

    dungeon: pass "completed", "archived", or "someday" to short-circuit to a dungeon status.
             Leave None to advance one step (planning -> ready -> active -> completed).
    force: skip readiness validation.
    """
    try:
        return fest.promote(festival, dungeon=dungeon, force=force)
    except (FestError, FileNotFoundError) as e:
        return f"error: {e}"


@mcp.tool()
def fest_task_complete(festival: str, task_id: str) -> str:
    """Mark a task complete inside a festival."""
    try:
        return fest.task_complete(festival, task_id)
    except (FestError, FileNotFoundError) as e:
        return f"error: {e}"


if __name__ == "__main__":
    mcp.run()
