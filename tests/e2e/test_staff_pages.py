import re

import pytest

from hotel.domain.actor import Actor
from hotel.domain.enums import Role
from tests.conftest import csrf_token, login

TEMP = "temporary-pass-4521"


def _post(client, path, **data):
    return client.post(path, data={"csrf_token": csrf_token(client, "/"), **data})


@pytest.fixture
def rita(services, manager):
    return services.users.create_user(
        Actor(manager),
        username="rita",
        full_name="Rita",
        role=Role.RECEPTIONIST,
        temporary_password=TEMP,
    )


def test_staff_list_and_create(signed_in):
    assert "mona" in signed_in.get("/staff/").get_data(as_text=True)
    response = _post(
        signed_in,
        "/staff/new",
        username="sami",
        full_name="Sami Gharbi",
        role="RECEPTIONIST",
        password=TEMP,
        confirm=TEMP,
    )
    assert response.status_code == 302
    page = signed_in.get("/staff/").get_data(as_text=True)
    assert "sami" in page
    assert "Temporary password" in page


def test_create_form_shows_errors_next_to_fields(signed_in):
    response = _post(
        signed_in,
        "/staff/new",
        username="sami",
        full_name="Sami",
        role="RECEPTIONIST",
        password=TEMP,
        confirm="different",
    )
    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert "The two passwords are different." in page
    response = _post(
        signed_in,
        "/staff/new",
        username="x",
        full_name="",
        role="KING",
        password=TEMP,
        confirm=TEMP,
    )
    assert "Choose a role." in response.get_data(as_text=True)
    response = _post(
        signed_in,
        "/staff/new",
        username="mona",
        full_name="Dup",
        role="MANAGER",
        password=TEMP,
        confirm=TEMP,
    )
    assert "already used" in response.get_data(as_text=True)


def test_edit_deactivate_reset_unlock(signed_in, rita, services):
    page = signed_in.get(f"/staff/{rita.id}").get_data(as_text=True)
    version = re.search(r'name="version" value="(\d+)"', page).group(1)
    response = _post(
        signed_in, f"/staff/{rita.id}", version=version, full_name="Rita T.", role="RECEPTIONIST"
    )
    assert response.status_code == 302
    stale = _post(
        signed_in, f"/staff/{rita.id}", version=version, full_name="Old", role="RECEPTIONIST"
    )
    assert "Someone else changed this record" in stale.get_data(as_text=True)

    page = signed_in.get(f"/staff/{rita.id}").get_data(as_text=True)
    version = re.search(r'name="version" value="(\d+)"', page).group(1)
    _post(signed_in, f"/staff/{rita.id}/active", version=version)
    assert "Deactivated" in signed_in.get("/staff/").get_data(as_text=True)

    bad = _post(signed_in, f"/staff/{rita.id}/password", password="short", confirm="short")
    assert bad.status_code == 302
    _post(signed_in, f"/staff/{rita.id}/password", password=TEMP + "x", confirm=TEMP + "x")
    _post(signed_in, f"/staff/{rita.id}/unlock")
    assert services.users.get_user(Actor.system(), rita.id).must_change_password


def test_manager_cannot_deactivate_self_through_the_page(signed_in, manager):
    _post(signed_in, f"/staff/{manager.id}/active", version=str(manager.version + 1))
    page = signed_in.get(f"/staff/{manager.id}").get_data(as_text=True)
    assert "can&#39;t deactivate your own account" in page


def test_receptionist_gets_403_on_every_staff_page(client, rita, services):
    services.users.change_own_password(
        Actor(rita), current_password=TEMP, new_password="jasmine tea at noon"
    )
    login(client, "rita", "jasmine tea at noon")
    for path in ("/staff/", "/staff/new", f"/staff/{rita.id}", "/audit/"):
        assert client.get(path).status_code == 403, path
    assert _post(client, f"/staff/{rita.id}/unlock").status_code == 403


def test_temporary_password_forces_a_change_first(client, rita):
    login(client, "rita", TEMP)
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/account/password"
    page = client.get("/account/password").get_data(as_text=True)
    assert "temporary password" in page

    mismatch = _post(
        client,
        "/account/password",
        current_password=TEMP,
        password="jasmine tea at noon",
        confirm="something else",
    )
    assert mismatch.status_code == 400
    wrong = _post(
        client,
        "/account/password",
        current_password="nope",
        password="jasmine tea at noon",
        confirm="jasmine tea at noon",
    )
    assert "not correct" in wrong.get_data(as_text=True)
    done = _post(
        client,
        "/account/password",
        current_password=TEMP,
        password="jasmine tea at noon",
        confirm="jasmine tea at noon",
    )
    assert done.status_code == 302
    assert client.get("/").status_code == 200  # still signed in, free to continue
