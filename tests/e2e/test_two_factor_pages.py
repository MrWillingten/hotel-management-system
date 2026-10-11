"""Two-factor sign-in through the pages (story 6.1)."""

import re
from datetime import timedelta

from hotel import cli
from hotel.domain.totp import GRACE, totp
from tests.conftest import MANAGER_PASSWORD, csrf_token, enrol_two_factor, login, login_with_code

STEP = timedelta(seconds=30)
_SECRET = re.compile(r'<code class="code-block" dir="ltr">([A-Z2-7 ]+)</code>')
RITA_OWN = "olive-grove-at-dusk-7"
_RECOVERY = re.compile(r"<li><code>([A-Z0-9-]{14})</code></li>")


def _enrol_through_the_pages(client, clock) -> tuple[str, list[str]]:
    page = client.get("/account/two-factor").get_data(as_text=True)
    assert 'class="qr__image"' in page
    assert "<svg" in page
    secret = _SECRET.search(page).group(1).replace(" ", "")
    response = client.post(
        "/account/two-factor/confirm",
        data={
            "code": totp(secret, clock.now()),
            "csrf_token": csrf_token(client, "/account/two-factor"),
        },
    )
    assert response.status_code == 200
    assert "Set it up before" not in response.get_data(as_text=True)
    codes = _RECOVERY.findall(response.get_data(as_text=True))
    return secret, codes


def test_a_manager_enrols_then_signs_in_with_a_code(signed_in, clock):
    _secret, codes = _enrol_through_the_pages(signed_in, clock)
    assert len(codes) == 10
    page = signed_in.get("/account/two-factor").get_data(as_text=True)
    assert "Unused recovery codes: 10" in page
    assert "Turn off two-factor sign-in" not in page  # managers must keep it
    signed_in.post("/logout", data={"csrf_token": csrf_token(signed_in, "/")})

    clock.advance(STEP)
    response = login(signed_in)
    assert response.headers["Location"] == "/login/code"
    assert signed_in.get("/").status_code == 302  # no session yet
    wrong = signed_in.post(
        "/login/code", data={"code": "000000", "csrf_token": csrf_token(signed_in, "/login/code")}
    )
    assert wrong.status_code == 401
    assert "This code is not correct" in wrong.get_data(as_text=True)
    response = signed_in.post(
        "/login/code",
        data={"code": codes[0], "csrf_token": csrf_token(signed_in, "/login/code")},
    )
    assert response.status_code == 302
    assert "Welcome, Mona Ben Salah." in signed_in.get("/").get_data(as_text=True)


def test_a_wrong_enrolment_code_is_explained(signed_in):
    response = signed_in.post(
        "/account/two-factor/confirm",
        data={"code": "12", "csrf_token": csrf_token(signed_in, "/account/two-factor")},
    )
    assert response.status_code == 400
    assert "Check the phone&#39;s time" in response.get_data(as_text=True)


def test_the_code_page_needs_a_password_first(client, manager):
    response = client.get("/login/code")
    assert response.headers["Location"] == "/login"


def test_an_expired_code_step_sends_back_to_the_password(client, manager, services, clock):
    secret = enrol_two_factor(services, manager)
    clock.advance(timedelta(minutes=6))
    login(client)
    clock.advance(timedelta(minutes=6))
    response = client.post(
        "/login/code",
        data={"code": totp(secret, clock.now()), "csrf_token": csrf_token(client, "/login/code")},
    )
    assert response.headers["Location"] == "/login"
    assert "took too long" in client.get("/login").get_data(as_text=True)


def test_next_is_kept_across_the_code_step(client, manager, services, clock):
    secret = enrol_two_factor(services, manager)
    clock.advance(STEP)
    login(client, next="/guests/")
    response = client.post(
        "/login/code",
        data={"code": totp(secret, clock.now()), "csrf_token": csrf_token(client, "/login/code")},
    )
    assert response.headers["Location"] == "/guests/"


def test_managers_are_reminded_then_blocked_after_the_grace_period(signed_in, clock):
    page = signed_in.get("/").get_data(as_text=True)
    assert "Set it up before" in page
    clock.advance(GRACE)
    login(signed_in)  # the old session has expired by now
    response = signed_in.get("/guests/")
    assert response.headers["Location"] == "/account/two-factor"
    page = signed_in.get("/account/two-factor").get_data(as_text=True)
    assert "Set it up now to continue." in page
    secret, _ = _enrol_through_the_pages(signed_in, clock)
    assert signed_in.get("/guests/").status_code == 200
    assert "Set it up before" not in signed_in.get("/").get_data(as_text=True)
    assert secret


def test_receptionists_choose_and_can_turn_it_off(client, hotel, clock):
    login(client, "rita")
    client.post(
        "/account/password",
        data={
            "current_password": MANAGER_PASSWORD,
            "password": RITA_OWN,
            "confirm": RITA_OWN,
            "csrf_token": csrf_token(client, "/account/password"),
        },
    )
    assert "Set it up before" not in client.get("/").get_data(as_text=True)
    secret, _ = _enrol_through_the_pages(client, clock)
    clock.advance(STEP)
    response = client.post(
        "/account/two-factor/disable",
        data={
            "code": totp(secret, clock.now()),
            "csrf_token": csrf_token(client, "/account/two-factor"),
        },
    )
    assert response.headers["Location"] == "/account/two-factor"
    assert "Two-factor sign-in is off." in client.get("/account/two-factor").get_data(as_text=True)


def test_recovery_codes_can_be_renewed(signed_in, clock):
    secret, old = _enrol_through_the_pages(signed_in, clock)
    clock.advance(STEP)
    wrong = signed_in.post(
        "/account/two-factor/recovery-codes",
        data={"code": "000000", "csrf_token": csrf_token(signed_in, "/account/two-factor")},
    )
    assert wrong.status_code == 400
    response = signed_in.post(
        "/account/two-factor/recovery-codes",
        data={
            "code": totp(secret, clock.now()),
            "csrf_token": csrf_token(signed_in, "/account/two-factor"),
        },
    )
    new = _RECOVERY.findall(response.get_data(as_text=True))
    assert len(new) == 10
    assert not set(new) & set(old)


def test_managers_cannot_turn_it_off_by_posting_directly(signed_in, clock, services):
    _enrol_through_the_pages(signed_in, clock)
    response = signed_in.post(
        "/account/two-factor/disable",
        data={"code": "123456", "csrf_token": csrf_token(signed_in, "/account/two-factor")},
    )
    assert response.headers["Location"] == "/account/two-factor"
    assert "Managers must keep two-factor sign-in." in signed_in.get(
        "/account/two-factor"
    ).get_data(as_text=True)


def test_renewing_codes_without_enrolment_is_refused(signed_in):
    response = signed_in.post(
        "/account/two-factor/recovery-codes",
        data={"code": "123456", "csrf_token": csrf_token(signed_in, "/account/two-factor")},
    )
    assert response.headers["Location"] == "/account/two-factor"


def test_confirming_twice_just_shows_the_status(signed_in, clock):
    _enrol_through_the_pages(signed_in, clock)
    response = signed_in.post(
        "/account/two-factor/confirm",
        data={"code": "123456", "csrf_token": csrf_token(signed_in, "/account/two-factor")},
    )
    assert response.headers["Location"] == "/account/two-factor"


def test_cli_reset_totp(monkeypatch, tmp_path, capsys):
    from hotel.bootstrap import build_services
    from hotel.config import Settings
    from hotel.domain.actor import Actor

    monkeypatch.setenv("HOTEL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HOTEL_ENV", "testing")
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": MANAGER_PASSWORD)
    assert cli.main(["create-manager", "--username", "mona", "--full-name", "Mona"]) == 0
    assert cli.main(["reset-totp", "nobody"]) == 1
    assert cli.main(["reset-totp", "mona"]) == 0
    assert "nothing to reset" in capsys.readouterr().out
    services = build_services(Settings.from_env())
    user = services.users.list_users(Actor.system())[0]
    enrol_two_factor(services, user)
    assert cli.main(["reset-totp", "Mona"]) == 0
    out = capsys.readouterr().out
    assert "reset for 'mona'" in out
    assert "at the next sign-in" in out
    assert services.auth.login("mona", MANAGER_PASSWORD, ip="127.0.0.1").token


def test_login_with_code_helper_matches_the_pages(client, manager, services, clock):
    secret = enrol_two_factor(services, manager)
    clock.advance(STEP)
    assert login_with_code(client, secret, clock.now()).headers["Location"] == "/"
