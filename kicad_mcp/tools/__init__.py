"""MCP tool modules.

Each module exposes a ``register(mcp, ctx)`` function that binds its tools to the
FastMCP server. The tool bodies delegate to plain, importable functions so the
logic is unit-testable without a live MCP session.
"""
