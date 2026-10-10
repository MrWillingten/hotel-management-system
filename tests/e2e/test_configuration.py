"""Start-up safety: settings, secret key, debug mode, command line."""

import os
import sys

import pytest

from hotel import cli
from hotel.config import ConfigurationError, Settings
from hotel.secret_key import WeakSecretKeyError, load_or_create_secret_key
from hotel.web import create_app


def test_settings_default_to_production():
    settings = Settings.from_env({})
    assert settings.environment == "production"
    assert not settings.debug
    assert settings.timezone == "Africa/Tunis"


def test_settings_from_environment(tmp_path):
    settings = Settings.from_env(
        {
            "HOTEL_ENV": "Development",
            "HOTEL_DATA_DIR": str(tmp_path),
            "HOTEL_NAME": "Dar Jasmine",
            "HOTEL_HTTPS": "yes",
            "HOTEL_TRUSTED_PROXIES": "1",
        }
    )
    assert settings.debug
    assert settings.data_dir == tmp_path
    assert settings.hotel_name == "Dar Jasmine"
    assert settings.https
    assert settings.database_path == tmp_path / "hotel.db"


@pytest.mark.parametrize(
    "environ",
    [
        {"HOTEL_ENV": "staging"},
        {"HOTEL_TIMEZONE": "Mars/Olympus"},
        {"HOTEL_TRUSTED_PROXIES": "lots"},
        {"HOTEL_TRUSTED_PROXIES": "9"},
    ],
)
def test_invalid_settings_are_refused(environ):
    with pytest.raises(ConfigurationError):
        Settings.from_env(environ)


def test_debug_mode_is_refused_in_production(tmp_path, monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "1")
    with pytest.raises(ConfigurationError, match="Debug mode is forbidden"):
        create_app(Settings(environment="production", data_dir=tmp_path))


def test_production_app_writes_a_log_file(tmp_path, monkeypatch):
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    app = create_app(Settings(environment="production", data_dir=tmp_path, trusted_proxies=1))
    assert not app.debug
    assert (tmp_path / "logs" / "hotel.log").exists()


def test_secret_key_is_generated_once_and_reused(tmp_path):
    path = tmp_path / "secret_key"
    key = load_or_create_secret_key(path)
    assert len(key) == 64
    assert load_or_create_secret_key(path) == key
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_weak_secret_key_is_refused(tmp_path):
    path = tmp_path / "secret_key"
    path.write_text("changeme", encoding="utf-8")
    with pytest.raises(WeakSecretKeyError):
        load_or_create_secret_key(path)


# ------------------------------------------------------------ command line
@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOTEL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HOTEL_ENV", "testing")
    return tmp_path


def test_cli_version(capsys):
    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out.startswith("hotel ")


def test_cli_init_db(cli_env, capsys):
    assert cli.main(["init-db"]) == 0
    assert (cli_env / "hotel.db").exists()
    assert "schema v" in capsys.readouterr().out


def test_cli_create_manager(cli_env, monkeypatch, capsys):
    answers = iter(
        [
            "short",
            "cognac-and-cedar-2026",
            "different-password!",
            "cognac-and-cedar-2026",
            "cognac-and-cedar-2026",
        ]
    )
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(answers))
    code = cli.main(["create-manager", "--username", "mona", "--full-name", "Mona Ben Salah"])
    captured = capsys.readouterr()
    assert code == 0
    assert "at least 12 characters" in captured.err
    assert "different" in captured.err
    assert "'mona' created" in captured.out
    # A second manager cannot be created this way.
    assert cli.main(["create-manager", "--username", "other", "--full-name", "Other"]) == 1


def test_cli_create_manager_reports_invalid_input(cli_env, monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "cognac-and-cedar-2026")
    assert cli.main(["create-manager", "--username", "x", "--full-name", "X"]) == 1
    assert "Username" in capsys.readouterr().err


def test_cli_reports_configuration_errors(monkeypatch, capsys):
    monkeypatch.setenv("HOTEL_ENV", "staging")
    assert cli.main(["init-db"]) == 2
    assert "Configuration error" in capsys.readouterr().err


def test_cli_run_uses_waitress_and_warns_on_network_addresses(cli_env, monkeypatch, capsys):
    served = {}
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    monkeypatch.setitem(sys.modules, "waitress", type(sys)("waitress"))
    sys.modules["waitress"].serve = lambda app, **kw: served.update(kw)
    assert cli.main(["run", "--host", "0.0.0.0", "--port", "8123"]) == 0
    assert served == {"host": "0.0.0.0", "port": 8123, "threads": 8}
    assert "WARNING" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("host", "loopback"),
    [
        ("127.0.0.1", True),
        ("localhost", True),
        ("::1", True),
        ("0.0.0.0", False),
        ("hotel.lan", False),
    ],
)
def test_loopback_detection(host, loopback):
    assert cli._is_loopback(host) is loopback
