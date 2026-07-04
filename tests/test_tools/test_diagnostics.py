from __future__ import annotations

import json

from kicad_mcp.context import AppContext
from kicad_mcp.tools.diagnostics import build_status


def test_build_status_shape():
    ctx = AppContext.create()
    status = build_status(ctx)

    assert status["server"] == "kicad-mcp"
    assert "version" in status
    assert set(status["backends"].keys()) == {"kicad-cli", "sexpr", "kicad-ipc"}
    assert isinstance(status["capabilities"], list)
    assert "search_paths" in status["config"]
    # Whole payload must be JSON-serializable (it crosses the MCP boundary).
    json.dumps(status)


def test_build_status_reports_cli_version_when_available():
    ctx = AppContext.create()
    status = build_status(ctx)
    cli = status["backends"]["kicad-cli"]
    if cli["available"]:
        # Either a version string or a captured error, never a crash.
        assert "version" in cli or "version_error" in cli
