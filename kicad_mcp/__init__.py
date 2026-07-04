"""kicad-mcp: an MCP server for creating, reviewing, and exporting KiCad designs.

Two pillars (see PLAN.md):
  1. Automation — project/schematic/board tooling driven by Claude.
  2. Review engine — a rule engine encoding the Hartley and Phil's Lab catalogs.

This package is built in phases (PLAN.md §8). Phase 0 = skeleton, config, backend
factory. Phase 1 = headless foundation (read + verify + export with KiCad closed).
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
