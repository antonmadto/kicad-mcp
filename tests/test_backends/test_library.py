"""Library + JLCPCB search (Phase 5)."""

from __future__ import annotations

import sqlite3

import pytest

from kicad_mcp.backends import library as lib
from kicad_mcp.backends.base import BackendError

# --- symbol/footprint search (needs installed KiCad libraries) ---------------


@pytest.mark.requires_kicad
def test_search_symbols_finds_device_r():
    if lib._library_root() is None:
        pytest.skip("no KiCad library root found")
    results = lib.search_symbols("Device:R", env={})
    ids = {r["id"] for r in results}
    assert any(i.startswith("Device:R") for i in ids)
    # Child unit symbols (R_0_1) must be filtered out.
    assert not any(r["symbol"].endswith(("_0_1", "_1_1")) for r in results)


@pytest.mark.requires_kicad
def test_search_footprints_finds_0402():
    if lib._library_root() is None:
        pytest.skip("no KiCad library root found")
    results = lib.search_footprints("R_0402", env={})
    assert any("0402" in r["footprint"] for r in results)


# --- JLCPCB (synthetic SQLite DB, runs everywhere) ---------------------------


def _make_db(path):
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE components (lcsc INTEGER, mfr TEXT, description TEXT, "
        "package TEXT, basic INTEGER, price REAL, stock INTEGER)"
    )
    con.executemany(
        "INSERT INTO components VALUES (?,?,?,?,?,?,?)",
        [
            (25804, "0402WGF1002TCE", "1k 0402 resistor", "0402", 1, 0.001, 100000),
            (12345, "STM32F103C8T6", "ARM MCU LQFP48", "LQFP-48", 0, 1.20, 5000),
        ],
    )
    con.commit()
    con.close()


def test_jlcpcb_search_returns_rows(tmp_path):
    db = tmp_path / "jlc.sqlite3"
    _make_db(db)
    rows = lib.search_jlcpcb_parts("STM32", env={"KICAD_MCP_JLCPCB_DB": str(db)})
    assert len(rows) == 1
    assert rows[0]["lcsc"] == "C12345"
    assert rows[0]["mpn"] == "STM32F103C8T6"
    assert rows[0]["basic_part"] is False


def test_jlcpcb_basic_only_filter(tmp_path):
    db = tmp_path / "jlc.sqlite3"
    _make_db(db)
    rows = lib.search_jlcpcb_parts("0402", env={"KICAD_MCP_JLCPCB_DB": str(db)}, basic_only=True)
    assert len(rows) == 1 and rows[0]["basic_part"] is True


def test_jlcpcb_missing_db_is_actionable():
    with pytest.raises(BackendError, match="KICAD_MCP_JLCPCB_DB"):
        lib.search_jlcpcb_parts("anything", env={})


def test_jlcpcb_negative_limit_is_clamped(tmp_path):
    # SQLite treats a negative LIMIT as "unlimited" -- a stray -1 (or 0) must
    # not silently defeat pagination and dump the whole matching result set.
    db = tmp_path / "jlc.sqlite3"
    _make_db(db)
    rows = lib.search_jlcpcb_parts("resistor", env={"KICAD_MCP_JLCPCB_DB": str(db)}, limit=-1)
    assert len(rows) <= 1000  # clamped, not "unlimited"


def test_jlcpcb_like_metacharacters_are_escaped(tmp_path):
    # A bare '%' or '_' in the query must not act as a SQL LIKE wildcard, or a
    # query like "5%" (a tolerance spec) would match every row.
    db = tmp_path / "jlc.sqlite3"
    _make_db(db)
    rows = lib.search_jlcpcb_parts("%", env={"KICAD_MCP_JLCPCB_DB": str(db)})
    assert rows == []


# --- symbol scanner regex (space-indented vendor libraries) ------------------


def test_search_symbols_matches_space_indented_file(tmp_path):
    # KiCad's own writer uses a tab, but KICAD_MCP_SYMBOL_PATHS is documented
    # to point at arbitrary vendor libraries, which commonly use spaces.
    sym_dir = tmp_path / "symbols"
    sym_dir.mkdir()
    (sym_dir / "Vendor.kicad_sym").write_text(
        '(kicad_symbol_lib (version 20211014) (generator vendor)\n'
        '  (symbol "ESP32-WROOM-32" (in_bom yes) (on_board yes)\n'
        '    (property "Reference" "U")\n'
        '  )\n'
        ')\n',
        encoding="utf-8",
    )
    results = lib.search_symbols("ESP32", env={"KICAD_MCP_SYMBOL_PATHS": str(sym_dir)})
    ids = {r["id"] for r in results}
    assert "Vendor:ESP32-WROOM-32" in ids


def test_search_symbols_negative_limit_does_not_crash(tmp_path):
    sym_dir = tmp_path / "symbols"
    sym_dir.mkdir()
    (sym_dir / "Vendor.kicad_sym").write_text(
        '\t(symbol "R" (in_bom yes))\n', encoding="utf-8"
    )
    results = lib.search_symbols("R", env={"KICAD_MCP_SYMBOL_PATHS": str(sym_dir)}, limit=-5)
    assert results == []
