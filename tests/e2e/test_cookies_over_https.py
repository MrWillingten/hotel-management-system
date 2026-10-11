"""Cookie hardening behind HTTPS and on sign-out (story 6.6, ASVS V3.3.1 / V14.3.1)."""

import pytest

from hotel.bootstrap import build_services
from hotel.config import Settings
from hotel.web import create_app
from tests.conftest import MANAGER_PASSWORD, csrf_token, login


@pytest.fixture
def https_client(tmp_path, clock):
    settings = Settings(environment="testing", data_dir=tmp_path, https=True, scrypt_n=2**10)
    services = build_services(settings, clock=clock)
    services.auth.create_first_manager("mona", "Mona Ben Salah", MANAGER_PASSWORD)
    client = create_app(settings, services=services).test_client()
    # Requests arrive as https://, or the client would not send back Secure cookies.
    client.environ_base["wsgi.url_scheme"] = "https"
    return client


def test_every_cookie_gets_the_host_prefix_behind_https(https_client):
    response = login(https_client)
    assert response.status_code == 302
    session_cookie = https_client.get_cookie("__Host-hotel_session")
    assert session_cookie is not None
    assert session_cookie.secure
    assert session_cookie.path == "/"
    assert session_cookie.domain in ("", "localhost")
    assert https_client.get_cookie("hotel_session") is None
    assert https_client.get_cookie("__Host-hotel_ui").secure
    assert https_client.get("/").status_code == 200  # the prefixed cookie is read back
    https_client.post(
        "/preferences/language",
        data={"language": "fr", "csrf_token": csrf_token(https_client, "/")},
    )
    assert https_client.get_cookie("__Host-hotel_lang").value == "fr"
    assert "Tableau de bord" in https_client.get("/").get_data(as_text=True)


def test_plain_http_keeps_unprefixed_names(signed_in):
    assert signed_in.get_cookie("hotel_session") is not None


def test_signing_out_clears_cached_pages(signed_in):
    response = signed_in.post("/logout", data={"csrf_token": csrf_token(signed_in, "/")})
    assert response.headers["Clear-Site-Data"] == '"cache", "storage"'


def test_the_blocklist_holds_thousands_of_long_common_passwords(services):
    from hotel.bootstrap import load_common_passwords

    common = load_common_passwords()
    assert len(common) >= 3000  # ASVS V6.2.4: at least the top 3000 matching the policy
    assert all(len(word) >= 12 for word in common)
    assert "password1234" in common
