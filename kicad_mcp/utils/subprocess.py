"""Hardened subprocess execution for kicad-cli and other external tools.

Security rule (PLAN.md §3, CLAUDE.md): every external command is run in **list
form with ``shell=False``**, which makes shell injection structurally impossible
— no argument is ever interpreted by a shell. ``shlex.quote`` is applied only in
:func:`format_command`, the human-readable rendering used for logs and error
messages, honoring the "quote every subprocess arg" rule for display.
"""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CommandError(RuntimeError):
    """A command exited non-zero (only raised when ``check=True``)."""

    def __init__(self, result: CommandResult) -> None:
        self.result = result
        super().__init__(
            f"Command failed (exit {result.returncode}): {format_command(result.args)}\n"
            f"stderr: {result.stderr.strip()}"
        )


class CommandTimeout(RuntimeError):
    """A command exceeded its timeout."""

    def __init__(self, args: Sequence[str], timeout: float) -> None:
        self.args = list(args)
        self.timeout = timeout
        super().__init__(f"Command timed out after {timeout}s: {format_command(args)}")


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    args: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def format_command(args: Sequence[str | Path]) -> str:
    """Render a command as a copy-pasteable, shell-quoted string (for logs)."""
    return " ".join(shlex.quote(str(a)) for a in args)


def run(
    args: Sequence[str | Path],
    *,
    timeout: float,
    check: bool = False,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    """Run a command (``shell=False``) and capture stdout/stderr as text.

    Raises :class:`CommandTimeout` on timeout and, if ``check`` is set,
    :class:`CommandError` on a non-zero exit.
    """
    argv = [str(a) for a in args]
    try:
        proc = subprocess.run(  # noqa: S603 — list form, shell=False, args are ours
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CommandTimeout(argv, timeout) from exc
    except FileNotFoundError as exc:
        raise CommandError(
            CommandResult(127, "", f"executable not found: {argv[0]}", tuple(argv))
        ) from exc

    result = CommandResult(proc.returncode, proc.stdout or "", proc.stderr or "", tuple(argv))
    if check and not result.ok:
        raise CommandError(result)
    return result


def run_json(
    args: Sequence[str | Path],
    *,
    timeout: float,
    cwd: str | Path | None = None,
) -> Any:
    """Run a command that emits JSON on stdout and return the parsed object."""
    import json

    result = run(args, timeout=timeout, check=True, cwd=cwd)
    return json.loads(result.stdout)
