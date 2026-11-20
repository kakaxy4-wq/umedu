"""Версия релиза: в /healthz и в подвале страниц; перекрывается CQ_VERSION."""
from test_app import client  # noqa: F401  (фикстура TestClient с временной базой)


def test_version_in_healthz_and_footer(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "VERSION", "9.9-test")
    r = client.get("/healthz")
    assert r.json()["version"] == "9.9-test"
    page = client.get("/login").text
    assert "umedu 9.9-test" in page


def test_default_version(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "VERSION", "1.0")
    assert client.get("/healthz").json()["version"] == "1.0"
