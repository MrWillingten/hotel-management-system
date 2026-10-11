"""The evidence documents name real tests (story 6.6).

docs/asvs.md and docs/test-evidence.md cite tests as `path::name`; renaming
or deleting a test without updating them would leave false evidence.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_REFERENCE = re.compile(r"`((?:unit|integration|e2e)/[\w/]+\.py)(?:::(\w+))?`|`::(\w+)`")


@pytest.mark.parametrize("document", ["asvs.md", "test-evidence.md"])
def test_every_cited_test_exists(document):
    text = (ROOT / "docs" / document).read_text(encoding="utf-8")
    missing, current = [], None
    for match in _REFERENCE.finditer(text):
        current = match.group(1) or current  # "`::name`" continues the previous file
        name = match.group(2) or match.group(3)
        path = ROOT / "tests" / current
        if not path.exists():
            missing.append(current)
        elif name and f"def {name}(" not in path.read_text(encoding="utf-8"):
            missing.append(f"{current}::{name}")
    assert not missing, f"{document} cites tests that do not exist: {missing}"
