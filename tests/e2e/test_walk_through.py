"""The walk-through pages and dashboard cards (story 6.14)."""

from hotel.web.tour import STEPS
from tests.conftest import csrf_token


def test_the_dashboard_invites_new_accounts(signed_in):
    page = signed_in.get("/").get_data(as_text=True)
    assert "Take the tour" in page
    assert "Getting started" in page
    signed_in.post("/welcome/done", data={"csrf_token": csrf_token(signed_in, "/")})
    page = signed_in.get("/").get_data(as_text=True)
    assert "Take the tour" not in page
    assert "Getting started" in page  # the checklist stays until done or hidden
    signed_in.post("/welcome/checklist/dismiss", data={"csrf_token": csrf_token(signed_in, "/")})
    assert "Getting started" not in signed_in.get("/").get_data(as_text=True)


def test_the_tour_walks_through_every_step(signed_in):
    total = len(STEPS)  # managers see every step
    first = signed_in.get("/welcome/1").get_data(as_text=True)
    assert f"Step 1 of {total}" in first
    assert "Skip the tour" in first
    last = signed_in.get(f"/welcome/{total}").get_data(as_text=True)
    assert "Finish the tour" in last
    assert signed_in.get("/welcome/0").status_code == 404
    assert signed_in.get(f"/welcome/{total + 1}").status_code == 404


def test_receptionists_get_a_shorter_tour(client, hotel):
    from tests.conftest import MANAGER_PASSWORD, login

    login(client, "rita")
    own = "olive-grove-at-dusk-7"
    client.post(
        "/account/password",
        data={
            "current_password": MANAGER_PASSWORD,
            "password": own,
            "confirm": own,
            "csrf_token": csrf_token(client, "/account/password"),
        },
    )
    receptionist_steps = len([s for s in STEPS if not s.manager_only])
    page = client.get("/welcome/1").get_data(as_text=True)
    assert f"Step 1 of {receptionist_steps}" in page
    assert client.get(f"/welcome/{receptionist_steps + 1}").status_code == 404


def test_the_tour_can_be_restarted_from_help(signed_in):
    signed_in.post("/welcome/done", data={"csrf_token": csrf_token(signed_in, "/")})
    response = signed_in.post(
        "/welcome/restart", data={"csrf_token": csrf_token(signed_in, "/help/")}
    )
    assert response.headers["Location"] == "/welcome/1"
    assert "Take the tour" in signed_in.get("/").get_data(as_text=True)


def test_every_checklist_link_works(signed_in):
    page = signed_in.get("/").get_data(as_text=True)
    for path in ("/guests/new", "/reservations/new", "/rooms/new", "/staff/new", "/backups/"):
        assert f'href="{path}"' in page
        assert signed_in.get(path).status_code == 200
