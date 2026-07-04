"""Library search (Phase 5): KiCad symbol/footprint libraries + JLCPCB parts DB.

Symbol/footprint search scans the installed KiCad libraries (discovered next to
kicad-cli, or via ``KICAD_MCP_SYMBOL_PATHS`` / ``KICAD_MCP_FOOTPRINT_PATHS``).
JLCPCB search queries a local SQLite parts DB (``KICAD_MCP_JLCPCB_DB``) — the
schema of the popular ``jlcparts`` export — with an actionable error when absent.
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

from .base import BackendError

# Per-platform KiCad library roots to probe when env overrides are unset.
_LIB_ROOT_CANDIDATES = (
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport",
    r"C:\Program Files\KiCad\9.0\share\kicad",
    "/usr/share/kicad",
)


def _library_root() -> Path | None:
    for root in _LIB_ROOT_CANDIDATES:
        if Path(root).is_dir():
            return Path(root)
    return None


def _symbol_dirs(env: dict) -> list[Path]:
    override = env.get("KICAD_MCP_SYMBOL_PATHS")
    if override:
        return [Path(p) for p in override.split(os.pathsep) if p]
    root = _library_root()
    return [root / "symbols"] if root else []


def _footprint_dirs(env: dict) -> list[Path]:
    override = env.get("KICAD_MCP_FOOTPRINT_PATHS")
    if override:
        return [Path(p) for p in override.split(os.pathsep) if p]
    root = _library_root()
    return [root / "footprints"] if root else []


_SYMBOL_RE = re.compile(r'^\t\(symbol "([^"]+)"', re.M)


def _match_score(query: str, lib: str, name: str) -> int | None:
    """Match rank (lower = better) or None. A ``Lib:Name`` query matches lib AND
    name separately; a bare query matches either. Exact > prefix > substring."""

    def name_rank(q: str, s: str) -> int | None:
        s = s.lower()
        if s == q:
            return 0
        if s.startswith(q):
            return 1
        if q in s:
            return 2
        return None

    if ":" in query:
        lib_q, name_q = (p.strip().lower() for p in query.split(":", 1))
        if lib_q and lib_q not in lib.lower():
            return None
        return name_rank(name_q, name) if name_q else 3
    q = query.lower()
    nr = name_rank(q, name)
    if nr is not None:
        return nr
    return 4 if q in lib.lower() else None


def search_symbols(query: str, env: dict | None = None, limit: int = 40) -> list[dict]:
    """Search installed KiCad symbol libraries; returns ``Lib:Symbol`` ids.

    A ``Lib:Name`` query (e.g. ``Device:R``) matches the library and symbol name
    separately; a bare query matches either. Results are ranked exact > prefix >
    substring so the closest match comes first.
    """
    env = os.environ if env is None else env
    scored: list[tuple[int, str, dict]] = []
    for sym_dir in _symbol_dirs(env):
        if not sym_dir.is_dir():
            continue
        for lib_file in sorted(sym_dir.glob("*.kicad_sym")):
            lib = lib_file.stem
            try:
                text = lib_file.read_text(encoding="utf-8")
            except Exception:  # noqa: S112 - skip an unreadable/oddly-encoded lib file
                continue
            for name in _SYMBOL_RE.findall(text):
                if re.search(r"_\d+_\d+$", name):  # skip child units like R_0_1
                    continue
                score = _match_score(query, lib, name)
                if score is not None:
                    scored.append(
                        (
                            score,
                            f"{lib}:{name}",
                            {"id": f"{lib}:{name}", "library": lib, "symbol": name},
                        )
                    )
    scored.sort(key=lambda t: (t[0], t[1]))
    return [item for _, _, item in scored[:limit]]


def search_footprints(query: str, env: dict | None = None, limit: int = 40) -> list[dict]:
    """Search installed KiCad footprint libraries (``.pretty`` dirs)."""
    env = os.environ if env is None else env
    scored: list[tuple[int, str, dict]] = []
    for fp_dir in _footprint_dirs(env):
        if not fp_dir.is_dir():
            continue
        for pretty in sorted(fp_dir.glob("*.pretty")):
            lib = pretty.stem
            for mod in sorted(pretty.glob("*.kicad_mod")):
                name = mod.stem
                score = _match_score(query, lib, name)
                if score is not None:
                    scored.append(
                        (
                            score,
                            f"{lib}:{name}",
                            {"id": f"{lib}:{name}", "library": lib, "footprint": name},
                        )
                    )
    scored.sort(key=lambda t: (t[0], t[1]))
    return [item for _, _, item in scored[:limit]]


# --- JLCPCB parts (SQLite; jlcparts-style schema) ----------------------------


def jlcpcb_db_path(env: dict) -> Path | None:
    raw = env.get("KICAD_MCP_JLCPCB_DB")
    return Path(raw) if raw else None


def search_jlcpcb_parts(
    query: str, env: dict | None = None, basic_only: bool = False, limit: int = 20
) -> list[dict]:
    """Search a local JLCPCB parts SQLite DB by MPN / description.

    Expects a ``components`` table with columns lcsc, mfr, description, package,
    basic, price, stock (the jlcparts export). Raises with guidance if the DB is
    not configured or missing.
    """
    env = os.environ if env is None else env
    db = jlcpcb_db_path(env)
    if db is None:
        raise BackendError(
            "JLCPCB parts search needs a local SQLite DB. Set KICAD_MCP_JLCPCB_DB to a "
            "jlcparts-style database (see github.com/yaqwsx/jlcparts)."
        )
    if not db.exists():
        raise BackendError(f"JLCPCB DB not found at {db}. Check KICAD_MCP_JLCPCB_DB.")

    # Escape the path into the sqlite file: URI so odd characters don't break it,
    # and open read-only + immutable (we never mutate the parts DB).
    from urllib.request import pathname2url

    uri = f"file:{pathname2url(str(db.resolve()))}?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    try:
        con.row_factory = sqlite3.Row
        like = f"%{query}%"
        sql = (
            "SELECT lcsc, mfr, description, package, basic, price, stock "
            "FROM components WHERE (mfr LIKE ? OR description LIKE ?) "
        )
        params: list = [like, like]
        if basic_only:
            sql += "AND basic = 1 "
        sql += "ORDER BY basic DESC, stock DESC LIMIT ?"
        params.append(limit)
        rows = con.execute(sql, params).fetchall()
    except sqlite3.Error as exc:
        raise BackendError(f"JLCPCB DB query failed (unexpected schema?): {exc}") from exc
    finally:
        con.close()

    return [
        {
            "lcsc": f"C{row['lcsc']}" if str(row["lcsc"]).isdigit() else row["lcsc"],
            "mpn": row["mfr"],
            "description": row["description"],
            "package": row["package"],
            "basic_part": bool(row["basic"]),
            "price": row["price"],
            "stock": row["stock"],
        }
        for row in rows
    ]
