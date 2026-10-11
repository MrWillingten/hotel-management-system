"""The in-app Help page (story 6.10)."""

from hotel.web.help import TOPICS
from tests.conftest import MANAGER_PASSWORD, csrf_token, login

OWN = "olive-grove-at-dusk-7"


def test_managers_see_every_topic(signed_in):
    page = signed_in.get("/help/").get_data(as_text=True)
    for topic in TOPICS:
        assert f'id="{topic.anchor}"' in page
    assert "Night audit" in page
    assert 'href="/help/"' in page  # in the menu


def test_receptionists_see_only_what_they_can_use(client, hotel):
    login(client, "rita")
    client.post(
        "/account/password",
        data={
            "current_password": MANAGER_PASSWORD,
            "password": OWN,
            "confirm": OWN,
            "csrf_token": csrf_token(client, "/account/password"),
        },
    )
    page = client.get("/help/").get_data(as_text=True)
    assert 'id="booking"' in page
    for topic in TOPICS:
        if topic.manager_only:
            assert f'id="{topic.anchor}"' not in page


def test_help_is_translated(signed_in):
    signed_in.post(
        "/preferences/language", data={"language": "ar", "csrf_token": csrf_token(signed_in, "/")}
    )
    page = signed_in.get("/help/").get_data(as_text=True)
    assert "المواضيع" in page
    assert 'dir="rtl"' in page


def test_help_needs_an_account(client):
    assert client.get("/help/").headers["Location"].startswith("/login")


def test_every_topic_link_opens_a_page(signed_in):
    from flask import url_for

    app = signed_in.application
    with app.test_request_context():
        urls = [url_for(t.endpoint) for t in TOPICS if t.endpoint]
    for url in urls:
        assert signed_in.get(url, follow_redirects=True).status_code == 200, url
