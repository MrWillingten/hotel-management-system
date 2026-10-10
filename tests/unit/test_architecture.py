"""The layering rules from the design, checked automatically.

    web -> services -> domain <- persistence

The domain must stay pure Python, and services must never know about HTTP.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "hotel"

FORBIDDEN = {
    "domain": (
        "flask",
        "flask_babel",
        "flask_wtf",
        "werkzeug",
        "waitress",
        "sqlite3",
        "hotel.persistence",
        "hotel.services",
        "hotel.web",
        "hotel.bootstrap",
    ),
    "services": ("flask", "flask_babel", "flask_wtf", "werkzeug", "waitress", "hotel.web"),
    "persistence": ("flask", "flask_babel", "flask_wtf", "werkzeug", "hotel.services", "hotel.web"),
}


def _imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_does_not_import_forbidden_modules(layer):
    violations = []
    for path in (SRC / layer).rglob("*.py"):
        for name in _imports(path):
            if any(name == bad or name.startswith(bad + ".") for bad in FORBIDDEN[layer]):
                violations.append(f"{path.relative_to(SRC)} imports {name}")
    assert not violations, "\n".join(violations)
