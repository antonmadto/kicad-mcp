"""Advanced tools (Phase 6): async fab export, autoroute, review history."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kicad_mcp import history
from kicad_mcp.backends import freerouting
from kicad_mcp.context import AppContext

from ._common import confine_output, resolve
from .export import export_fab_package_impl

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def export_fab_package_async_impl(ctx: AppContext, project: str, output: str | None = None) -> dict:
    """Kick off a fab-package export on the background queue; return a task_id."""
    task = ctx.tasks.submit(
        "export_fab_package", lambda: export_fab_package_impl(ctx, project, output)
    )
    return task.summary()


def autoroute_board_impl(ctx: AppContext, dsn_path: str, output_ses: str | None = None) -> dict:
    """Autoroute a Specctra DSN with Freerouting on the background queue."""
    dsn = confine_output(ctx, dsn_path)
    ses = confine_output(ctx, output_ses) if output_ses else None
    jar = ctx.config.freerouting_jar
    if not freerouting.freerouting_available(jar):
        # Fail fast with guidance rather than queueing a doomed task.
        freerouting.route_dsn(dsn, jar, ses)  # raises the actionable BackendError
    task = ctx.tasks.submit("autoroute", lambda: freerouting.route_dsn(dsn, jar, ses))
    return task.summary()


def get_review_history_impl(ctx: AppContext, project: str, kind: str | None = None) -> list[dict]:
    proj = resolve(ctx, project)
    return history.read(proj.directory, kind=kind)


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def export_fab_package_async(project: str, output: str | None = None) -> dict:
        """Start a fab-package export in the background; poll it with
        get_task_status. Use for large boards that may exceed the request timeout."""
        return export_fab_package_async_impl(ctx, project, output)

    @mcp.tool()
    def autoroute_board(dsn_path: str, output_ses: str | None = None) -> dict:
        """Autoroute a Specctra .dsn with Freerouting (background task → task_id).
        Needs KICAD_MCP_FREEROUTING_JAR and Java. Note: KiCad 9 cannot export DSN
        headlessly, so export the .dsn from the KiCad GUI first."""
        return autoroute_board_impl(ctx, dsn_path, output_ses)

    @mcp.tool()
    def get_review_history(project: str, kind: str | None = None) -> list[dict]:
        """Show past review/DRC runs for a project (counts over time). Filter by
        kind: 'review' or 'drc'."""
        return get_review_history_impl(ctx, project, kind)
