"""Sign-in, sessions and access control, through real HTTP requests."""

import pytest

from hotel.web.security import AUTH_COOKIE, is_safe_redirect_target
from tests.conftest import MANAGER_PASSWORD, csrf_token, login


def _auth_cookie(client):
    return client.get_cookie(AUTH_COOKIE)


def test_anonymous_users_are_sent_to_the_login_page(client, manager):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login?next=/"


def test_login_page_explains_setup_when_no_account_exists(client):
    page = client.get("/login").get_data(as_text=True)
    assert "python -m hotel create-manager" in page


def test_successful_login(client, manager):
    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    cookie = _auth_cookie(client)
    assert cookie.http_only
    assert cookie.same_site == "Lax"
    page = client.get("/").get_data(as_text=True)
    assert "Mona Ben Salah" in page
    assert "Welcome, Mona Ben Salah." in page


def test_wrong_password_shows_a_generic_error(client, manager):
    response = login(client, password="not the password")
    assert response.status_code == 401
    page = response.get_data(as_text=True)
    assert "Invalid username or password" in page
    assert 'value="mona"' in page  # the username is kept...
    assert "not the password" not in page  # ...the password never is
    assert _auth_cookie(client) is None


def test_login_without_csrf_token_is_rejected(client, manager):
    response = client.post("/login", data={"username": "mona", "password": MANAGER_PASSWORD})
    assert response.status_code == 400
    assert "Form expired" in response.get_data(as_text=True)


def test_next_parameter_is_followed_only_for_local_paths(client, manager):
    assert login(client, next="/?tab=1").headers["Location"] == "/?tab=1"
    client.post("/logout", data={"csrf_token": csrf_token(client, "/")})
    assert login(client, next="https://evil.example/").headers["Location"] == "/"


@pytest.mark.parametrize(
    ("target", "safe"),
    [
        ("/", True),
        ("/reservations?page=2", True),
        ("//evil.example", False),
        ("https://evil.example", False),
        ("/\\evil.example", False),
        ("javascript:alert(1)", False),
        ("/\nSet-Cookie:x", False),
        ("", False),
        (None, False),
    ],
)
def test_safe_redirect_targets(target, safe):
    assert is_safe_redirect_target(target) is safe


def test_logout_ends_the_server_session(client, manager, services):
    login(client)
    token = _auth_cookie(client).value
    response = client.post("/logout", data={"csrf_token": csrf_token(client, "/")})
    assert response.status_code == 302
    assert _auth_cookie(client) is None
    assert services.auth.authenticate_session(token) is None
    assert client.get("/").status_code == 302


def test_logout_requires_post_and_csrf(signed_in):
    assert signed_in.get("/logout").status_code == 405
    assert signed_in.post("/logout").status_code == 400
    assert signed_in.get("/").status_code == 200  # still signed in


def test_a_new_login_never_reuses_the_previous_session(client, manager, services):
    login(client)
    first = _auth_cookie(client).value
    login(client)
    second = _auth_cookie(client).value
    assert first != second
    assert services.auth.authenticate_session(first) is None


def test_an_invalid_session_cookie_is_cleared(client, manager):
    client.set_cookie(AUTH_COOKIE, "forged-or-expired-token")
    response = client.get("/")
    assert response.status_code == 302
    assert _auth_cookie(client) is None


def test_user_data_is_escaped_in_pages(client, services):
    services.auth.create_first_manager("mona", "<script>alert(1)</script>", MANAGER_PASSWORD)
    login(client)
    page = client.get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
