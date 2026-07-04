from __future__ import annotations

import os
from pathlib import Path

from kicad_mcp.config import (
    DEFAULT_CLI_TIMEOUT,
    DEFAULT_IPC_TIMEOUT,
    Config,
    _default_search_paths,
)


def test_defaults_when_env_empty():
    cfg = Config.from_env({})
    assert cfg.allow_schematic_write is False
    assert cfg.cli_path is None
    assert cfg.freerouting_jar is None
    assert cfg.cli_timeout == DEFAULT_CLI_TIMEOUT
    assert cfg.ipc_timeout == DEFAULT_IPC_TIMEOUT
    assert cfg.search_paths == _default_search_paths()
    assert cfg.project_roots == cfg.search_paths


def test_search_paths_parsed_and_expanded():
    raw = os.pathsep.join(["/a/b", "~/c"])
    cfg = Config.from_env({"KICAD_MCP_SEARCH_PATHS": raw})
    assert cfg.search_paths[0] == Path("/a/b")
    assert cfg.search_paths[1] == Path("~/c").expanduser()
    assert len(cfg.search_paths) == 2


def test_empty_search_paths_fall_back_to_defaults():
    cfg = Config.from_env({"KICAD_MCP_SEARCH_PATHS": ""})
    assert cfg.search_paths == _default_search_paths()


def test_allow_schematic_write_truthy_variants():
    for val in ("1", "true", "TRUE", "Yes", "on"):
        assert Config.from_env({"KICAD_MCP_ALLOW_SCHEMATIC_WRITE": val}).allow_schematic_write
    for val in ("0", "false", "no", "off", "", "maybe"):
        assert not Config.from_env({"KICAD_MCP_ALLOW_SCHEMATIC_WRITE": val}).allow_schematic_write


def test_cli_and_freerouting_paths():
    cfg = Config.from_env(
        {"KICAD_MCP_CLI_PATH": "/opt/kicad-cli", "KICAD_MCP_FREEROUTING_JAR": "~/fr.jar"}
    )
    assert cfg.cli_path == Path("/opt/kicad-cli")
    assert cfg.freerouting_jar == Path("~/fr.jar").expanduser()


def test_timeout_parsing_and_fallback():
    assert Config.from_env({"KICAD_MCP_CLI_TIMEOUT": "30"}).cli_timeout == 30.0
    bad = Config.from_env({"KICAD_MCP_CLI_TIMEOUT": "not-a-number"})
    assert bad.cli_timeout == DEFAULT_CLI_TIMEOUT


def test_describe_is_json_serializable():
    import json

    cfg = Config.from_env({"KICAD_MCP_CLI_PATH": "/opt/kicad-cli"})
    payload = cfg.describe()
    json.dumps(payload)  # must not raise
    assert payload["cli_path"] == "/opt/kicad-cli"
    assert payload["allow_schematic_write"] is False
