"""Shared helpers for tool modules: project resolution and output confinement."""

from __future__ import annotations

from pathlib import Path

from kicad_mcp.context import AppContext
from kicad_mcp.projects import Project, resolve_project
from kicad_mcp.utils.paths import validate_within_roots


def resolve(ctx: AppContext, project: str) -> Project:
    """Resolve a project path/dir within the configured roots."""
    return resolve_project(project, ctx.config.project_roots)


def confine_output(ctx: AppContext, output: str | Path) -> Path:
    """Validate an export target stays inside the project roots, and ensure its
    parent directory exists."""
    resolved = validate_within_roots(output, ctx.config.project_roots)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved
