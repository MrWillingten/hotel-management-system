"""The Windows executable's entry point and its helpers (story 6.4)."""

import importlib.util
import sys
from pathlib import Path

import pytest

from hotel import cli, config

LAUNCHER = Path(__file__).resolve().parents[2] / "packaging" / "windows" / "launcher.py"


@pytest.fixture
def launcher(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("HOTEL_DATA_DIR", raising=False)
    monkeypatch.setenv("HOTEL_ENV", "testing")
    spec = importlib.util.spec_from_file_location("hotel_launcher", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_command_hint_names_the_program_people_have(monkeypatch):
    assert config.cli_command() == "python -m hotel"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert config.cli_command() == "hotel.exe"


def test_arguments_are_passed_to_the_usual_commands(launcher, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "main", lambda argv: calls.append(argv) or 0)
    monkeypatch.setattr(sys, "argv", ["hotel.exe", "backup"])
    assert launcher.main() == 0
    assert calls == [["backup"]]
    import os

    assert os.environ["HOTEL_DATA_DIR"] == str(tmp_path / "HotelMedina")


def test_first_double_click_creates_the_manager_then_starts(launcher, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "main", lambda argv: calls.append(argv) or 0)
    monkeypatch.setattr(sys, "argv", ["hotel.exe"])
    assert launcher.main() == 0
    assert calls == [["create-manager"], ["run", "--open-browser"]]


def test_errors_stay_on_screen_after_a_double_click(launcher, monkeypatch):
    monkeypatch.setattr(cli, "main", lambda argv: 1)
    monkeypatch.setattr(sys, "argv", ["hotel.exe"])
    pauses = []
    monkeypatch.setattr("builtins.input", lambda prompt="": pauses.append(prompt))
    assert launcher.main() == 1
    assert pauses == ["Press Enter to close this window."]


@pytest.mark.parametrize(
    ("host", "shown"),
    [
        ("127.0.0.1", "127.0.0.1"),
        ("0.0.0.0", "127.0.0.1"),
        ("::", "127.0.0.1"),
        ("hotel.lan", "hotel.lan"),
    ],
)
def test_open_browser_points_at_a_reachable_address(monkeypatch, host, shown):
    started = []

    class FakeTimer:
        def __init__(self, delay, function, args):
            started.append(args[0])

        def start(self):
            pass

    monkeypatch.setattr("threading.Timer", FakeTimer)
    cli._open_browser_soon(host, 8000)
    assert started == [f"http://{shown}:8000/"]
