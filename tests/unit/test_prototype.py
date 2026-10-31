"""The CP2 procedural prototype (prototype/): the brief's scenarios and its money parsing."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "prototype"))

import hotel_prototype as proto
import scenarios


@pytest.mark.parametrize("scenario", scenarios.SCENARIOS, ids=lambda s: s.__name__)
def test_brief_scenarios(scenario):
    scenario()


@pytest.mark.parametrize(
    ("text", "millimes"), [("150", 150_000), ("12.5", 12_500), ("0.005", 5), ("7.250", 7_250)]
)
def test_amounts_are_read_as_text_not_floats(text, millimes):
    assert proto.dinars(text) == millimes


@pytest.mark.parametrize("text", ["", "abc", "1.2345", "-5", "1,5"])
def test_wrong_amounts_are_refused(text):
    with pytest.raises(ValueError, match="not an amount"):
        proto.dinars(text)


def test_the_menu_books_and_bills(monkeypatch, capsys):
    answers = iter(
        [
            "1",
            "nobody",
            "y",
            "Amira",
            "Ben Salah",
            "CIN",
            "07123456",
            "",
            "",
            "3",
            "1",
            "2027-07-01",
            "2027-07-04",
            "101",
            "2",
            "10",
            "1",
            "3",
            "1",
            "2027-07-02",
            "2027-07-03",
            "101",
            "1",
            "0",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    proto.main()
    out = capsys.readouterr().out
    assert "Registered guest #1." in out
    assert "Booked: reservation #1 (R-2027-00001)." in out
    assert "450.000 DT" in out
    assert "Refused: Room 101 is not free for these dates." in out
