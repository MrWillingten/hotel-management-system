"""Themes and languages."""

import pytest

from hotel.web.preferences import LANG_COOKIE, THEME_COOKIE
from tests.conftest import csrf_token


def _post(client, path, **data):
    return client.post(path, data={"csrf_token": csrf_token(client), "next": "/login", **data})


def test_default_theme_follows_the_system(client):
    page = client.get("/login").get_data(as_text=True)
    assert "data-theme" not in page.split(">", 2)[1]
    assert 'content="light dark"' in page


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_choosing_a_theme(client, theme):
    response = _post(client, "/preferences/theme", theme=theme)
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
    assert client.get_cookie(THEME_COOKIE).value == theme
    assert f'data-theme="{theme}"' in client.get("/login").get_data(as_text=True)


def test_unknown_values_are_refused(client):
    assert _post(client, "/preferences/theme", theme="neon").status_code == 400
    assert _post(client, "/preferences/language", language="../../etc").status_code == 400
    assert client.get_cookie(THEME_COOKIE) is None


def test_preferences_never_redirect_off_site(client):
    response = client.post(
        "/preferences/theme",
        data={"csrf_token": csrf_token(client), "theme": "dark", "next": "https://evil.example"},
    )
    assert response.headers["Location"] == "/"


def test_arabic_switches_the_page_to_right_to_left(client):
    _post(client, "/preferences/language", language="ar")
    assert client.get_cookie(LANG_COOKIE).value == "ar"
    page = client.get("/login").get_data(as_text=True)
    assert '<html lang="ar" dir="rtl"' in page
    assert "تسجيل الدخول" in page


def test_french(client):
    _post(client, "/preferences/language", language="fr")
    page = client.get("/login").get_data(as_text=True)
    assert '<html lang="fr" dir="ltr"' in page
    assert "Se connecter" in page


def test_browser_language_is_used_when_nothing_was_chosen(client):
    page = client.get("/login", headers={"Accept-Language": "fr-FR,fr;q=0.9"}).get_data(
        as_text=True
    )
    assert 'lang="fr"' in page


def test_translated_error_messages(client, manager):
    _post(client, "/preferences/language", language="fr")
    response = client.post(
        "/login",
        data={"username": "mona", "password": "wrong password!", "csrf_token": csrf_token(client)},
    )
    assert "Nom d&#39;utilisateur ou mot de passe incorrect" in response.get_data(as_text=True)


def test_dashboard_in_every_language(signed_in):
    for language, expected in (
        ("en", "Dashboard"),
        ("fr", "Tableau de bord"),
        ("ar", "لوحة القيادة"),
    ):
        signed_in.post(
            "/preferences/language",
            data={"csrf_token": csrf_token(signed_in, "/"), "language": language, "next": "/"},
        )
        response = signed_in.get("/")
        assert response.status_code == 200
        assert expected in response.get_data(as_text=True)


@pytest.mark.parametrize(
    ("hour", "greeting"),
    [
        (2, "Good evening"),
        (5, "Good morning"),
        (11, "Good morning"),
        (12, "Good afternoon"),
        (17, "Good afternoon"),
        (18, "Good evening"),
        (23, "Good evening"),
    ],
)
def test_greeting_follows_the_hotel_clock(app, hour, greeting):
    from hotel.web.blueprints.dashboard import _greeting

    with app.test_request_context():
        assert _greeting(hour) == greeting
