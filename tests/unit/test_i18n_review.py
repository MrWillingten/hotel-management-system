"""The translation review script (story 5.5), run on a copy of the catalogues."""

import csv
import importlib.util
import shutil
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "i18n_review.py"


@pytest.fixture
def review(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("i18n_review", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    copy = tmp_path / "translations"
    shutil.copytree(module.TRANSLATIONS, copy)
    monkeypatch.setattr(module, "TRANSLATIONS", copy)
    return module


def _rows(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_placeholders(review):
    assert review.placeholders("Room %(number)s: 20%% off %(name)s") == [
        "%%",
        "%(name)s",
        "%(number)s",
    ]


def test_export_then_import_a_correction(review, tmp_path):
    sheet = tmp_path / "review.csv"
    assert review.main(["export", str(sheet)]) == 0
    rows = _rows(sheet)
    assert {"english", "french", "arabic", "french_correction", "arabic_correction"} <= set(rows[0])
    row = next(r for r in rows if r["english"] == "Room %(number)s is ready for the next guest.")
    row["french_correction"] = "La chambre %(number)s est prête."
    _write(sheet, rows)
    assert review.main(["import", str(sheet)]) == 0
    assert review._catalog("fr").get(row["english"]).string == "La chambre %(number)s est prête."


def test_a_broken_placeholder_changes_nothing(review, tmp_path, capsys):
    sheet = tmp_path / "review.csv"
    review.main(["export", str(sheet)])
    rows = _rows(sheet)
    row = next(r for r in rows if r["english"] == "Room %(number)s is ready for the next guest.")
    before = review._catalog("ar").get(row["english"]).string
    row["arabic_correction"] = "الغرفة %(numero)s جاهزة."  # misspelt placeholder
    _write(sheet, rows)
    assert review.main(["import", str(sheet)]) == 1
    assert "do not match" in capsys.readouterr().out
    assert review._catalog("ar").get(row["english"]).string == before


def test_usage(review):
    assert review.main([]) == 2
