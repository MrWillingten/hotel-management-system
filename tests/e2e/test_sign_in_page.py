"""The premium sign-in page (story 6.12): markup and safety of the decoration."""

from pathlib import Path

from hotel.bootstrap import build_services
from hotel.config import Settings
from hotel.web import create_app

CSS = Path(__file__).resolve().parents[2] / "src" / "hotel" / "web" / "static" / "css" / "app.css"


def test_the_hotel_name_is_written_as_a_signature(client):
    page = client.get("/login").get_data(as_text=True)
    assert 'class="signature"' in page
    assert ">Hotel Medina</text>" in page
    assert 'aria-hidden="true"' in page  # decoration only; the title says it too
    assert "<script" not in page


def _login_page(tmp_path, clock, name):
    settings = Settings(environment="testing", data_dir=tmp_path, hotel_name=name, scrypt_n=2**10)
    app = create_app(settings, services=build_services(settings, clock=clock))
    return app.test_client().get("/login").get_data(as_text=True)


def test_a_long_hotel_name_is_squeezed_to_fit(tmp_path, clock):
    assert 'textLength="740"' in _login_page(tmp_path, clock, "Grand Hôtel des Thermes")


def test_a_short_hotel_name_keeps_its_natural_width(tmp_path, clock):
    assert 'textLength="504"' in _login_page(tmp_path, clock, "Dar Sidi")  # 8 letters x 63


def test_the_code_page_shares_the_signature(client, manager, services, clock):
    from datetime import timedelta

    from tests.conftest import enrol_two_factor, login

    enrol_two_factor(services, manager)
    clock.advance(timedelta(seconds=30))
    login(client)
    assert 'class="signature"' in client.get("/login/code").get_data(as_text=True)


def test_motion_stops_for_people_who_ask_for_less():
    css = CSS.read_text(encoding="utf-8")
    reduced = css[css.rindex("@media (prefers-reduced-motion: reduce)") :]
    for selector in (".signature__text", ".auth-panel"):
        assert selector in reduced
    assert "great-vibes-latin-400.woff2" in css
    assert (CSS.parent.parent / "fonts" / "great-vibes-latin-400.woff2").exists()
    assert (CSS.parent.parent / "fonts" / "OFL-great-vibes.txt").exists()
