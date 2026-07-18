"""Review/DRC history tracking (PLAN.md §6): append-only, best-effort read."""

from __future__ import annotations

from kicad_mcp import history


def test_record_and_read_roundtrip(tmp_path):
    history.record(tmp_path, "review", {"findings": 3})
    history.record(tmp_path, "drc", {"violations": 1})
    entries = history.read(tmp_path)
    assert [e["kind"] for e in entries] == ["review", "drc"]


def test_read_filters_by_kind(tmp_path):
    history.record(tmp_path, "review", {"findings": 3})
    history.record(tmp_path, "drc", {"violations": 1})
    entries = history.read(tmp_path, kind="drc")
    assert len(entries) == 1 and entries[0]["kind"] == "drc"


def test_read_missing_file_returns_empty(tmp_path):
    assert history.read(tmp_path) == []


def test_read_skips_non_utf8_line(tmp_path):
    # A stray non-UTF-8 byte (disk fault, interrupted write) must not crash
    # the read -- read() is documented best-effort, same as record().
    history.record(tmp_path, "review", {"findings": 1})
    path = tmp_path / ".kicad-mcp" / "history.jsonl"
    with path.open("ab") as f:
        f.write(b"\xff\xfe not utf8\n")
    entries = history.read(tmp_path)
    assert len(entries) == 1
    assert entries[0]["kind"] == "review"


def test_read_skips_non_object_json_line(tmp_path):
    # A line that is valid JSON but not an object (bare scalar/array from a
    # partial or interleaved write) must be skipped, not crash on .get().
    history.record(tmp_path, "review", {"findings": 1})
    path = tmp_path / ".kicad-mcp" / "history.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write("42\n")
        f.write('"just a string"\n')
        f.write("[1, 2, 3]\n")
    entries = history.read(tmp_path, kind="review")
    assert len(entries) == 1
    assert entries[0]["findings"] == 1


def test_read_respects_limit(tmp_path):
    for i in range(5):
        history.record(tmp_path, "review", {"n": i})
    entries = history.read(tmp_path, limit=2)
    assert [e["n"] for e in entries] == [3, 4]
