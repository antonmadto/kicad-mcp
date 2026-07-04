"""Async task-management tools (PLAN.md §3): poll long-running operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kicad_mcp.context import AppContext

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def get_task_status_impl(ctx: AppContext, task_id: str) -> dict:
    # Snapshot under the store lock; include the result once finished.
    snap = ctx.tasks.get_summary(task_id, full=False)
    if snap is None:
        raise ValueError(f"No task with id '{task_id}'. Use list_tasks to see active tasks.")
    if snap["status"] in ("done", "error"):
        return ctx.tasks.get_summary(task_id, full=True) or snap
    return snap


def list_tasks_impl(ctx: AppContext) -> list[dict]:
    return ctx.tasks.list_summaries()


def cleanup_tasks_impl(ctx: AppContext) -> dict:
    return {"removed": ctx.tasks.cleanup()}


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def get_task_status(task_id: str) -> dict:
        """Poll a background task (autoroute, batch export). Returns the result
        once status is 'done'."""
        return get_task_status_impl(ctx, task_id)

    @mcp.tool()
    def list_tasks() -> list[dict]:
        """List background tasks and their statuses (newest first)."""
        return list_tasks_impl(ctx)

    @mcp.tool()
    def cleanup_tasks() -> dict:
        """Drop finished background tasks from the queue."""
        return cleanup_tasks_impl(ctx)
