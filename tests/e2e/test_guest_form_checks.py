"""Real checks on guest details through the form (story 6.15)."""

from tests.conftest import csrf_token


def _register(client, **fields):
    data = {
        "first_name": "Lina",
        "last_name": "Trabelsi",
        "id_doc_type": "PASSPORT",
        "id_doc_number": "TN1234567",
        "nationality": "",
        "phone": "",
        "email": "",
        "notes": "",
        "csrf_token": csrf_token(client, "/guests/new"),
        **fields,
    }
    return client.post("/guests/new", data=data)


def test_nationality_is_typed_with_suggestions_in_the_interface_language(signed_in):
    page = signed_in.get("/guests/new").get_data(as_text=True)
    assert 'list="countries"' in page
    assert '<option value="Tunisia">' in page
    signed_in.post(
        "/preferences/language", data={"language": "fr", "csrf_token": csrf_token(signed_in, "/")}
    )
    assert '<option value="Tunisie">' in signed_in.get("/guests/new").get_data(as_text=True)


def test_a_country_name_in_any_language_is_stored_as_its_code(signed_in, services, hotel):
    for typed, code in (("Tunisie", "TN"), ("تونس", "TN"), ("germany", "DE"), ("fr", "FR")):
        response = _register(
            signed_in,
            first_name="Lina",
            last_name=f"Trabelsi{chr(65 + len(typed))}",
            id_doc_number=f"TN{1000000 + len(typed) * 7 + ord(code[0])}",
            nationality=typed,
        )
        assert response.status_code == 302, typed
        guest_id = int(response.headers["Location"].rsplit("/", 1)[1])
        assert services.guests.get(hotel.boss, guest_id).nationality == code


def test_the_edit_form_shows_the_country_name_and_a_spaced_number(signed_in, hotel):
    page = signed_in.get(f"/guests/{hotel.amira.id}/edit").get_data(as_text=True)
    assert 'value="+216 20 123 456"' in page
    detail = signed_in.get(f"/guests/{hotel.amira.id}").get_data(as_text=True)
    assert "+216 20 123 456" in detail


def test_impossible_details_are_refused_with_reasons(signed_in):
    response = _register(
        signed_in,
        id_doc_number="ABCDEFG",
        nationality="Narnia",
        phone="12 345 678",
        email="lina..t@example",
    )
    assert response.status_code == 400
    page = response.get_data(as_text=True)
    for field in ("id_doc_number", "nationality", "phone", "email"):
        assert f'id="f-{field}-error"' in page, field
    assert 'value="Narnia"' in page  # what was typed is kept for correction


def test_browser_hints_are_present(signed_in):
    page = signed_in.get("/guests/new").get_data(as_text=True)
    assert 'type="tel"' in page
    assert 'inputmode="tel"' in page
    assert 'type="email"' in page
