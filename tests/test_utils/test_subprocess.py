from __future__ import annotations

import sys

import pytest

from kicad_mcp.utils.subprocess import (
    CommandError,
    CommandTimeout,
    format_command,
    run,
    run_json,
)


def test_run_captures_stdout():
    result = run(
        [sys.executable, "-c", "import sys; sys.stdout.write('hello')"],
        timeout=30,
    )
    assert result.ok
    assert result.returncode == 0
    assert result.stdout == "hello"


def test_run_json_parses():
    payload = run_json(
        [sys.executable, "-c", "import json,sys; sys.stdout.write(json.dumps({'a': 1}))"],
        timeout=30,
    )
    assert payload == {"a": 1}


def test_check_raises_on_nonzero():
    with pytest.raises(CommandError) as exc:
        run([sys.executable, "-c", "import sys; sys.exit(3)"], timeout=30, check=True)
    assert exc.value.result.returncode == 3


def test_timeout_raises():
    with pytest.raises(CommandTimeout):
        run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.3)


def test_missing_executable_raises_command_error():
    with pytest.raises(CommandError) as exc:
        run(["kicad-mcp-definitely-not-a-real-binary"], timeout=5)
    assert exc.value.result.returncode == 127


def test_format_command_quotes_spaces():
    rendered = format_command(["kicad-cli", "sch", "--output", "my reports/board.pdf"])
    assert "'my reports/board.pdf'" in rendered
