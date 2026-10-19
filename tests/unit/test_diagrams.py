"""The committed class diagrams match the code (docs/diagrams/class_diagrams.py)."""

import importlib.util
import sys
from pathlib import Path

DIAGRAMS = Path(__file__).resolve().parents[2] / "docs" / "diagrams"


def test_class_diagrams_are_up_to_date():
    spec = importlib.util.spec_from_file_location("class_diagrams", DIAGRAMS / "class_diagrams.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["class_diagrams"] = module  # dataclasses look their module up there
    spec.loader.exec_module(module)
    classes = module.read_classes("", "domain", "services", "persistence", "web")
    classes.update(module.read_classes("persistence/repositories"))
    generated = {
        "classes-domain-stays.dot": module.domain_stays_and_money(classes),
        "classes-domain-accounts.dot": module.domain_accounts_and_support(classes),
        "classes-architecture.dot": module.architecture(classes),
    }
    stale = [
        name
        for name, text in generated.items()
        if (DIAGRAMS / name).read_text(encoding="utf-8") != text
    ]
    assert not stale, f"Run `make -C docs/diagrams` to refresh: {stale}"
