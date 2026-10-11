from hotel import cli
from tests.conftest import csrf_token


def test_backup_page(signed_in):
    assert "No backups yet." in signed_in.get("/backups/").get_data(as_text=True)
    response = signed_in.post("/backups/", data={"csrf_token": csrf_token(signed_in, "/")})
    assert response.status_code == 302
    page = signed_in.get("/backups/").get_data(as_text=True)
    assert "-manual.db" in page
    assert "Manual" in page


def test_cli_backup_and_restore(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOTEL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HOTEL_ENV", "testing")
    assert cli.main(["backup"]) == 0
    written = capsys.readouterr().out.split("Backup written to ")[1].strip()
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")
    assert cli.main(["restore", written]) == 1
    assert "Cancelled" in capsys.readouterr().out
    assert cli.main(["restore", written, "--yes"]) == 0
    assert "Restored" in capsys.readouterr().out
    assert cli.main(["restore", str(tmp_path / "missing.db"), "--yes"]) == 1
    assert "Restore refused" in capsys.readouterr().err


def test_cli_seed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOTEL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HOTEL_ENV", "testing")
    assert cli.main(["seed"]) == 2
    assert cli.main(["seed", "--demo"]) == 0
    out = capsys.readouterr().out
    assert "17 rooms" in out
    assert "demo.manager" in out
    assert cli.main(["seed", "--demo"]) == 1
    assert "already has rooms" in capsys.readouterr().err


def test_demo_banner(client, services):
    from hotel.demo import seed_demo

    assert "DEMO DATA" not in client.get("/login").get_data(as_text=True)
    seed_demo(services, guests=1)
    assert "DEMO DATA" in client.get("/login").get_data(as_text=True)
