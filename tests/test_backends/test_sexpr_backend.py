"""SexprBackend write-path tests: ERC soft-gate must never mask a committed write.

``edit_schematic`` commits its mutation via ``os.replace()`` BEFORE either ERC
call. A cli_backend whose ``run_erc`` raises (CLI crash, missing report,
malformed JSON) must not turn an already-successful write into a reported
failure — see CLAUDE.md "Review-engine invariants" / PLAN.md §7 (ERC is
informational, not an auto-rollback).
"""

from __future__ import annotations

import shutil

import pytest

from kicad_mcp.backends.base import BackendError
from kicad_mcp.backends.sexpr import SexprBackend
from kicad_mcp.config import Config


def _backend(tmp_path) -> SexprBackend:
    cfg = Config.from_env(
        {
            "KICAD_MCP_SEARCH_PATHS": str(tmp_path),
            "KICAD_MCP_ALLOW_SCHEMATIC_WRITE": "1",
        }
    )
    return SexprBackend(cfg)


def _project_sch(tmp_path):
    dst = tmp_path / "proj"
    shutil.copytree("tests/fixtures/sample_project", dst)
    return dst / "sample.kicad_sch"


def _set_r1_value(new_value: str):
    def mutate(sch_obj):
        for s in sch_obj.symbol:
            if s.property.Reference.value == "R1":
                s.property.Value.value = new_value
                return
        raise AssertionError("R1 not found in fixture")

    return mutate


class _BaselineOkPostWriteFails:
    """Baseline ERC (pre-edit) succeeds; the post-write ERC always raises."""

    def __init__(self, error: str = "kicad-cli exploded"):
        self._error = error
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def run_erc(self, _path):
        self.calls += 1
        if self.calls == 1:
            return {"counts": {"error": 0}, "total": 0, "violations": []}
        raise BackendError(self._error)


class _BaselineFailsPostWriteOk:
    """Baseline ERC (pre-edit, on the ORIGINAL file) raises; post-write succeeds."""

    def __init__(self):
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def run_erc(self, _path):
        self.calls += 1
        if self.calls == 1:
            raise BackendError("baseline ERC boom")
        return {"counts": {"error": 0}, "total": 0, "violations": []}


def test_post_write_erc_failure_is_reported_not_raised(tmp_path):
    # Regression: previously the post-write run_erc() call was unguarded, so a
    # CLI crash AFTER the atomic os.replace() propagated as a BackendError,
    # telling the caller the edit failed when the schematic on disk was
    # already successfully mutated (a retrying caller could double-clone).
    backend = _backend(tmp_path)
    sch = _project_sch(tmp_path)
    fake_cli = _BaselineOkPostWriteFails()

    result = backend.edit_schematic(sch, _set_r1_value("999k"), cli_backend=fake_cli)

    assert result["erc"] == {"error": "post-edit ERC could not run: kicad-cli exploded"}
    # The write committed despite the ERC gate failing afterward.
    comps = backend.read_components(sch)
    assert any(c["reference"] == "R1" and c["value"] == "999k" for c in comps)


def test_baseline_erc_failure_does_not_block_the_edit(tmp_path):
    # Regression: previously the baseline run_erc() call (on the pre-edit file)
    # ran unguarded, before the write's try-block, so it could block an
    # otherwise-safe edit entirely if ERC couldn't process the original file.
    backend = _backend(tmp_path)
    sch = _project_sch(tmp_path)
    fake_cli = _BaselineFailsPostWriteOk()

    result = backend.edit_schematic(sch, _set_r1_value("1k"), cli_backend=fake_cli)

    assert result["erc"]["new_errors"] == 0  # unknown baseline treated as 0, not raised
    comps = backend.read_components(sch)
    assert any(c["reference"] == "R1" and c["value"] == "1k" for c in comps)


def test_normal_erc_success_path_unaffected(tmp_path):
    # Sanity: a cli_backend that is simply unavailable still behaves as before
    # (erc omitted), so the non-fatal wrapping doesn't change the happy path.
    backend = _backend(tmp_path)
    sch = _project_sch(tmp_path)

    class _Unavailable:
        def is_available(self):
            return False

    result = backend.edit_schematic(sch, _set_r1_value("4k7"), cli_backend=_Unavailable())
    assert result["erc"] is None


@pytest.mark.requires_kicad
def test_real_cli_erc_gate_smoke(tmp_path):
    # Light smoke test against a real kicad-cli, if present, that the happy
    # path still reports a proper erc dict (not the error-shaped one).
    from kicad_mcp.backends.cli import CliBackend

    backend = _backend(tmp_path)
    sch = _project_sch(tmp_path)
    cli = CliBackend(Config.from_env())
    result = backend.edit_schematic(sch, _set_r1_value("10k"), cli_backend=cli)
    assert "error" not in (result["erc"] or {})
