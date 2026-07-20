"""FastMCP server assembly.

``create_server`` builds the :class:`AppContext`, constructs a FastMCP instance,
and registers every tool module. ``main`` is the console entry point
(``kicad-mcp``) and runs over stdio.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .context import AppContext
from .prompts import review as review_prompt
from .prompts import workflows as workflow_prompts
from .tools import (
    advanced,
    board,
    board_edit,
    diagnostics,
    export,
    impedance,
    library,
    project,
    review,
    router,
    routing,
    schematic_edit,
    schematic_read,
    tasks,
    validate,
)

SERVER_NAME = "kicad-mcp"
SERVER_INSTRUCTIONS = (
    "kicad-mcp lets you analyze, review, and export KiCad 9 designs, and (with a "
    "running KiCad) edit boards live. Call get_server_status first to see which "
    "capabilities are available in this environment. review_design audits a board "
    "against the Hartley/Phil's Lab rule catalog."
)

_TOOL_MODULES = (
    diagnostics,
    project,
    board,
    schematic_read,
    validate,
    export,
    review,
    impedance,
    board_edit,
    routing,
    schematic_edit,
    library,
    tasks,
    advanced,
    router,
)

_PROMPT_MODULES = (review_prompt, workflow_prompts)


def create_server(context: AppContext | None = None) -> FastMCP:
    ctx = context if context is not None else AppContext.create()
    mcp = FastMCP(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)
    for module in _TOOL_MODULES:
        module.register(mcp, ctx)
    for module in _PROMPT_MODULES:
        module.register(mcp, ctx)
    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
