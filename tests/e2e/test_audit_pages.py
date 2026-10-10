from hotel import cli
from hotel.persistence.db import connect


def test_manager_sees_the_audit_log(signed_in):
    response = signed_in.get("/audit/")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Integrity verified" in page
    assert "auth.login" in page


def test_audit_filters_and_bad_input(signed_in):
    assert signed_in.get("/audit/?action=auth.&since=2026-07-01&page=1").status_code == 200
    response = signed_in.get("/audit/?since=not-a-date&user=abc&page=zz")
    assert response.status_code == 200
    assert "auth.login" in response.get_data(as_text=True)


def test_broken_chain_is_shown(signed_in, settings):
    conn = connect(settings.database_path)
    conn.execute("DROP TRIGGER audit_log_no_update")
    conn.execute("UPDATE audit_log SET username = 'mallory' WHERE id = 1")
    conn.close()
    assert "Integrity check failed at entry #1" in signed_in.get("/audit/").get_data(as_text=True)


def test_anonymous_users_cannot_open_the_audit_log(client, manager):
    assert client.get("/audit/").status_code == 302


def test_cli_audit_verify(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOTEL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HOTEL_ENV", "testing")
    assert cli.main(["audit", "verify"]) == 0
    assert "intact" in capsys.readouterr().out
    conn = connect(tmp_path / "hotel.db")
    conn.execute(
        "INSERT INTO audit_log (at, action, prev_hash, hash) VALUES ('x', 'forged', ?, ?)",
        ("1" * 64, "2" * 64),
    )
    conn.close()
    assert cli.main(["audit", "verify"]) == 1
    assert "AUDIT LOG ALTERED" in capsys.readouterr().err
