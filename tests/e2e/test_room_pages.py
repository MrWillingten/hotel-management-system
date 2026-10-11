import re

from hotel.domain.actor import Actor
from hotel.domain.money import Money
from tests.conftest import csrf_token

TEMP = "temporary-pass-4521"
NEW = "jasmine tea at noon"


def _post(client, path, **data):
    return client.post(path, data={"csrf_token": csrf_token(client, "/"), **data})


def _setup_room(services, manager):
    boss = Actor(manager)
    deluxe = services.rooms.create_category(boss, name="Deluxe")
    return deluxe, services.rooms.create_room(
        boss, number="204", category_id=deluxe.id, capacity=2, nightly_rate=Money(180_000)
    )


def test_empty_room_list_explains_what_to_do(signed_in):
    assert "Create a room category first" in signed_in.get("/rooms/").get_data(as_text=True)


def test_manager_creates_categories_and_rooms(signed_in):
    assert (
        _post(signed_in, "/rooms/categories", name="Deluxe", description="Sea view").status_code
        == 302
    )
    page = signed_in.get("/rooms/categories").get_data(as_text=True)
    category_id = re.search(r'name="id" value="(\d+)"', page).group(1)
    duplicate = _post(signed_in, "/rooms/categories", name="deluxe")
    assert duplicate.status_code == 400

    bad = _post(
        signed_in,
        "/rooms/new",
        number="!!",
        category_id=category_id,
        capacity="2",
        nightly_rate="abc",
    )
    assert bad.status_code == 400
    response = _post(
        signed_in,
        "/rooms/new",
        number="204",
        category_id=category_id,
        capacity="2",
        nightly_rate="180,5",
        notes="",
    )
    assert response.status_code == 302
    listing = signed_in.get("/rooms/").get_data(as_text=True)
    assert "204" in listing
    assert "180.500 DT" in listing
    assert signed_in.get(f"/rooms/?category={category_id}").status_code == 200
    assert signed_in.get("/rooms/?category=abc").status_code == 200


def test_edit_room_and_rename_category(signed_in, services, manager):
    deluxe, room = _setup_room(services, manager)
    page = signed_in.get(f"/rooms/{room.id}/edit").get_data(as_text=True)
    assert 'value="204"' in page
    response = _post(
        signed_in,
        f"/rooms/{room.id}/edit",
        version=room.version,
        number="204",
        category_id=deluxe.id,
        capacity="3",
        nightly_rate="200",
        notes="",
    )
    assert response.status_code == 302
    assert "Out of service" in signed_in.get("/rooms/").get_data(as_text=True)
    stale = _post(
        signed_in,
        f"/rooms/{room.id}/edit",
        version=room.version,
        number="204",
        category_id=deluxe.id,
        capacity="3",
        nightly_rate="200",
        in_service="on",
    )
    assert stale.status_code == 400
    renamed = _post(
        signed_in,
        "/rooms/categories",
        id=deluxe.id,
        version=deluxe.version,
        name="Deluxe+",
        description="",
    )
    assert renamed.status_code == 302


def test_maintenance_through_the_pages(signed_in, services, manager):
    _, room = _setup_room(services, manager)
    bad = _post(
        signed_in,
        f"/rooms/{room.id}/maintenance",
        first_night="2026-07-08",
        reopens_on="2026-07-08",
        reason="Paint",
    )
    assert bad.status_code == 400
    ok = _post(
        signed_in,
        f"/rooms/{room.id}/maintenance",
        first_night="2026-07-08",
        reopens_on="2026-07-11",
        reason="Paint",
    )
    assert ok.status_code == 302
    page = signed_in.get(f"/rooms/{room.id}").get_data(as_text=True)
    assert "Paint" in page
    assert "Maintenance" in signed_in.get("/rooms/").get_data(as_text=True)
    clash = _post(
        signed_in,
        f"/rooms/{room.id}/maintenance",
        first_night="2026-07-09",
        reopens_on="2026-07-12",
        reason="Again",
    )
    assert clash.status_code == 400
    assert "already closed" in clash.get_data(as_text=True)
    maintenance_id = services.rooms.maintenance_for_room(Actor(manager), room.id)[0].id
    _post(signed_in, f"/rooms/maintenance/{maintenance_id}/cancel", room_id=room.id)
    _post(signed_in, f"/rooms/maintenance/{maintenance_id}/cancel", room_id=room.id)
    assert services.rooms.maintenance_for_room(Actor(manager), room.id) == []


def test_receptionist_access(client, services, manager):
    from hotel.domain.enums import Role
    from tests.conftest import login

    _, room = _setup_room(services, manager)
    rita = services.users.create_user(
        Actor(manager),
        username="rita",
        full_name="Rita",
        role=Role.RECEPTIONIST,
        temporary_password=TEMP,
    )
    services.users.change_own_password(Actor(rita), current_password=TEMP, new_password=NEW)
    login(client, "rita", NEW)
    assert client.get("/rooms/").status_code == 200
    detail = client.get(f"/rooms/{room.id}").get_data(as_text=True)
    assert "Close for maintenance" not in detail
    for path in ("/rooms/new", f"/rooms/{room.id}/edit", "/rooms/categories"):
        assert client.get(path).status_code == 403, path
    assert client.get("/rooms/999").status_code == 404


def test_seasonal_rates_page(signed_in, services, hotel):
    from tests.conftest import csrf_token

    category_id = hotel.rooms["204"].category_id
    page = signed_in.get("/rooms/rates").get_data(as_text=True)
    assert "No rate period" in page
    data = {
        "csrf_token": csrf_token(signed_in, "/rooms/rates"),
        "name": "Summer",
        "category_id": category_id,
        "first_night": "2026-07-10",
        "last_night": "2026-07-20",
        "nightly_rate": "250",
    }
    assert signed_in.post("/rooms/rates", data=data).status_code == 302
    assert "Summer" in signed_in.get("/rooms/rates").get_data(as_text=True)
    clash = signed_in.post(
        "/rooms/rates", data={**data, "csrf_token": csrf_token(signed_in, "/rooms/rates")}
    )
    assert clash.status_code == 400
    [period] = services.rooms.rate_periods(hotel.boss)
    response = signed_in.post(
        f"/rooms/rates/{period.id}/delete",
        data={"csrf_token": csrf_token(signed_in, "/rooms/rates")},
    )
    assert "keep their prices" in signed_in.get(response.headers["Location"]).get_data(as_text=True)
