"""The /health page used by Docker's HEALTHCHECK (story 6.2)."""


def test_health_is_public_and_says_little(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert response.headers["Cache-Control"] == "no-store"


def test_health_reports_a_broken_database(client, settings):
    settings.database_path.unlink()
    settings.database_path.mkdir()  # a folder where the database should be: cannot open
    response = client.get("/health")
    assert response.status_code == 503
    assert response.get_json() == {"status": "unavailable"}
