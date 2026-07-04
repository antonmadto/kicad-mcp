"""Rule families. Importing this package registers every rule (PLAN.md §6).

Each family module decorates its rule classes with ``@register`` so the registry
can discover them. New families are added to ``_MODULES`` below.
"""

from importlib import import_module

# One module per rule family. Import triggers @register on each rule class.
_MODULES = (
    "stackup",
    "grounding",
    "return_path",
    "decoupling",
    "dfm",
    "transmission",
    "crosstalk",
    "smps",
    "subcircuits",
    "connectors",
)

for _name in _MODULES:
    import_module(f"{__name__}.{_name}")
