from __future__ import annotations

from pathlib import Path

import pytest

from kicad_mcp.backends import (
    Backends,
    BackendUnavailableError,
    Capability,
    CliBackend,
    IpcBackend,
    SexprBackend,
    create_backends,
)
from kicad_mcp.backends.base import Backend
from kicad_mcp.config import Config


def _backends_with_cli_down() -> Backends:
    cfg = Config.from_env({})
    return Backends(
        cli=CliBackend(cfg, path=Path("/nope/kicad-cli")),
        sexpr=SexprBackend(cfg),
        ipc=IpcBackend(cfg),
    )


def test_create_backends_types():
    backends = create_backends(Config.from_env())
    assert isinstance(backends.cli, CliBackend)
    assert isinstance(backends.sexpr, SexprBackend)
    assert isinstance(backends.ipc, IpcBackend)
    assert set(backends.summary().keys()) == {"kicad-cli", "sexpr", "kicad-ipc"}


def test_verify_unavailable_when_cli_down():
    backends = _backends_with_cli_down()
    assert Capability.VERIFY not in backends.available_capabilities()
    assert Capability.EXPORT not in backends.available_capabilities()
    assert backends.providers(Capability.VERIFY) == []


def test_require_raises_actionable_error():
    backends = _backends_with_cli_down()
    with pytest.raises(BackendUnavailableError) as exc:
        backends.require(Capability.VERIFY)
    assert "KICAD_MCP_CLI_PATH" in str(exc.value)


def test_edit_board_error_is_actionable_when_ipc_down():
    backends = _backends_with_cli_down()
    if backends.providers(Capability.EDIT_BOARD):
        pytest.skip("a live KiCad IPC connection is available in this environment")
    with pytest.raises(BackendUnavailableError) as exc:
        backends.require(Capability.EDIT_BOARD)
    msg = str(exc.value)
    assert "Enable KiCad API" in msg  # tells the user exactly what to switch on
    assert "Headless" in msg  # and that analysis/export still work


def test_schematic_read_available_when_sexpr_present():
    backends = create_backends(Config.from_env())
    if not backends.sexpr.is_available():
        pytest.skip("sexpdata/kicad-skip not installed")
    assert Capability.READ_SCHEMATIC in backends.available_capabilities()


def test_write_capability_requires_flag():
    disabled = SexprBackend(Config.from_env({}))
    enabled = SexprBackend(Config.from_env({"KICAD_MCP_ALLOW_SCHEMATIC_WRITE": "1"}))
    if not disabled.is_available():
        pytest.skip("sexpdata/kicad-skip not installed")
    assert Capability.WRITE_SCHEMATIC not in disabled.capabilities()
    assert Capability.WRITE_SCHEMATIC in enabled.capabilities()


class _FakeBackend(Backend):
    """Toy backend whose availability we control, to exercise the probe cache."""

    name = "fake"

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self.online = False
        self.probe_count = 0

    def _detect_available(self) -> bool:
        self.probe_count += 1
        return self.online

    def _capabilities_when_available(self) -> frozenset[Capability]:
        return frozenset({Capability.VERIFY})


def test_is_available_reprobes_until_positive():
    # A GUI/CLI that appears mid-session (started after the server) must be
    # picked up without a restart -- a False/None probe is never cached.
    backend = _FakeBackend(Config.from_env())
    assert backend.is_available() is False
    assert backend.probe_count == 1
    assert backend.is_available() is False
    assert backend.probe_count == 2  # re-probed: still not cached

    backend.online = True
    assert backend.is_available() is True
    assert backend.probe_count == 3


def test_is_available_caches_positive_result():
    backend = _FakeBackend(Config.from_env())
    backend.online = True
    assert backend.is_available() is True
    assert backend.probe_count == 1
    assert backend.is_available() is True
    assert backend.probe_count == 1  # not re-probed once positive
