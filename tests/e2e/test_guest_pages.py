import re

from tests.conftest import csrf_token


def _post(client, path, **data):
    return client.post(path, data={"csrf_token": csrf_token(client, "/"), **data})


AMIRA = {
    "first_name": "Amira",
    "last_name": "Ben Salah",
    "id_doc_type": "CIN",
    "id_doc_number": "09123456",
    "nationality": "TN",
    "phone": "+216 20 123 456",
    "email": "amira@example.tn",
    "notes": "",
}


def test_register_search_and_view(signed_in):
    assert "No guests registered yet." in signed_in.get("/guests/").get_data(as_text=True)
    form = signed_in.get("/guests/new").get_data(as_text=True)
    assert "Tunisia" in form  # country names come from the locale
    response = _post(signed_in, "/guests/new", **AMIRA)
    assert response.status_code == 302
    guest_url = response.headers["Location"]
    listing = signed_in.get("/guests/?q=amira").get_data(as_text=True)
    assert "Ben Salah, Amira" in listing
    assert "09123456" not in listing  # masked
    assert "••••456" in listing
    detail = signed_in.get(guest_url).get_data(as_text=True)
    assert "Tunisia" in detail
    assert "09123456" not in detail
    revealed = _post(signed_in, guest_url + "/document")
    assert "09123456" in revealed.get_data(as_text=True)
    assert "recorded in the audit log" in revealed.get_data(as_text=True)


def test_validation_and_duplicates(signed_in):
    bad = _post(signed_in, "/guests/new", **{**AMIRA, "id_doc_number": "123", "email": "nope"})
    assert bad.status_code == 400
    page = bad.get_data(as_text=True)
    assert "exactly 8 digits" in page
    assert "valid e-mail" in page

    _post(signed_in, "/guests/new", **AMIRA)
    same_doc = _post(signed_in, "/guests/new", **{**AMIRA, "first_name": "Other"})
    assert "already registered" in same_doc.get_data(as_text=True)
    assert "Is it one of these guests?" in same_doc.get_data(as_text=True)

    probable = _post(
        signed_in, "/guests/new", **{**AMIRA, "id_doc_type": "PASSPORT", "id_doc_number": "ZZ55555"}
    )
    assert probable.status_code == 400
    assert "register anyway" in probable.get_data(as_text=True)
    confirmed = _post(
        signed_in,
        "/guests/new",
        confirm_duplicate="on",
        **{**AMIRA, "id_doc_type": "PASSPORT", "id_doc_number": "ZZ55555"},
    )
    assert confirmed.status_code == 302


def test_edit_and_flags(signed_in):
    guest_url = _post(signed_in, "/guests/new", **AMIRA).headers["Location"]
    page = signed_in.get(guest_url + "/edit").get_data(as_text=True)
    assert 'value="Amira"' in page
    version = re.search(r'name="version" value="(\d+)"', page).group(1)
    saved = _post(
        signed_in, guest_url + "/edit", version=version, **{**AMIRA, "email": "new@example.tn"}
    )
    assert saved.status_code == 302
    stale = _post(signed_in, guest_url + "/edit", version=version, **AMIRA)
    assert stale.status_code == 409 or "Someone else changed" in stale.get_data(as_text=True)

    version = re.search(
        r'name="version" value="(\d+)"', signed_in.get(guest_url).get_data(as_text=True)
    ).group(1)
    missing_reason = _post(signed_in, guest_url + "/flags", version=version, do_not_rent="on")
    assert missing_reason.status_code == 400
    flagged = _post(
        signed_in,
        guest_url + "/flags",
        version=version,
        is_vip="on",
        do_not_rent="on",
        reason="Damaged furniture",
    )
    assert flagged.status_code == 302
    detail = signed_in.get(guest_url).get_data(as_text=True)
    assert "Damaged furniture" in detail
    assert "VIP" in detail


def test_unknown_guest_is_404(signed_in):
    assert signed_in.get("/guests/999").status_code == 404


def test_anonymise_page_needs_confirmation(signed_in, services, hotel, clock):
    from datetime import timedelta

    from tests.conftest import csrf_token, login

    clock.advance(timedelta(days=800))
    login(signed_in)  # the session expired while the clock moved
    page = signed_in.get("/guests/anonymise").get_data(as_text=True)
    assert "Karim Haddad" in page
    data = {"csrf_token": csrf_token(signed_in, "/guests/anonymise"), "guest_id": [hotel.karim.id]}
    response = signed_in.post("/guests/anonymise", data=data)
    assert "Tick the box" in signed_in.get(response.headers["Location"]).get_data(as_text=True)
    data["confirm"] = "on"
    data["csrf_token"] = csrf_token(signed_in, "/guests/anonymise")
    response = signed_in.post("/guests/anonymise", data=data)
    assert "Guests anonymised: 1." in signed_in.get(response.headers["Location"]).get_data(
        as_text=True
    )
    assert services.guests.get(hotel.boss, hotel.karim.id).is_anonymised
    page = signed_in.get(f"/guests/{hotel.karim.id}").get_data(as_text=True)
    assert "Anonymised guest" in page
    assert "Edit guest" not in page
    assert "Save flags" not in page
