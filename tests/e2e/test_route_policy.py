"""Deny by default: every route must declare who may use it."""

import pytest

from hotel.domain.errors import NotFoundError
from hotel.web.security import policy_of, public


def test_every_route_declares_an_access_policy(app):
    missing = [
        rule.rule
        for rule in app.url_map.iter_rules()
        if rule.endpoint != "static" and policy_of(app.view_functions[rule.endpoint]) is None
    ]
    assert not missing, f"Routes without @public/@login_required/@roles_required: {missing}"


def test_a_route_without_policy_is_refused(app, client):
    app.add_url_rule("/forgotten", "forgotten", lambda: "secret")
    response = client.get("/forgotten")
    assert response.status_code == 403
    assert "secret" not in response.get_data(as_text=True)


def test_a_policy_cannot_be_declared_twice():
    with pytest.raises(TypeError):
        public(public(lambda: None))


def test_security_headers_on_every_page(client, manager):
    for path in ("/login", "/does-not-exist"):
        headers = client.get(path).headers
        assert "default-src 'self'" in headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Referrer-Policy"] == "same-origin"
        assert headers["Cache-Control"] == "no-store"
        assert "Strict-Transport-Security" not in headers  # only behind HTTPS


def test_static_files_may_be_cached(client):
    response = client.get("/static/css/app.css")
    response.close()
    assert response.status_code == 200
    assert response.headers.get("Cache-Control") != "no-store"


def test_hsts_is_sent_when_served_over_https(tmp_path, clock):
    from hotel.bootstrap import build_services
    from hotel.config import Settings
    from hotel.web import create_app

    settings = Settings(environment="testing", data_dir=tmp_path, https=True, scrypt_n=2**10)
    app = create_app(settings, services=build_services(settings, clock=clock))
    headers = app.test_client().get("/login").headers
    assert headers["Strict-Transport-Security"].startswith("max-age=")


def test_error_pages_never_leak_internals(app, client):
    @public
    def explode():
        raise RuntimeError("database password is hunter2")

    app.add_url_rule("/explode", "explode", explode)
    response = client.get("/explode")
    page = response.get_data(as_text=True)
    assert response.status_code == 500
    assert "hunter2" not in page
    assert "Traceback" not in page
    assert "Incident reference" in page


def test_business_errors_become_friendly_pages(app, client):
    @public
    def missing():
        raise NotFoundError

    app.add_url_rule("/missing", "missing", missing)
    response = client.get("/missing")
    assert response.status_code == 404
    assert "We couldn&#39;t find what you were looking for." in response.get_data(as_text=True)


def test_unknown_page_is_a_404(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert "Page not found" in response.get_data(as_text=True)
