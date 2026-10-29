"""GET /api/v1/config и /catalog — чтение, без записей, без поломки сайта."""
from app import exam_model as em
from app.api_v1 import catalog_payload
from test_app import client  # noqa: F401


def test_config_and_catalog_are_public(client):  # noqa: F811
    cfg = client.get("/api/v1/config")
    assert cfg.status_code == 200
    body = cfg.json()
    assert body["schema_version"] == 1
    assert body["hard_min_build"] >= 1
    assert body["flags"]["trainer"] is True
    assert "notice" in body
    cat = client.get("/api/v1/catalog")
    assert cat.status_code == 200
    tracks = {t["id"]: t for t in cat.json()["tracks"]}
    assert tracks["oge"]["year"] == 2026 and tracks["ege"]["year"] == 2026
    oge = {s["id"]: s for s in tracks["oge"]["subjects"]}
    assert oge["math"]["status"] == "live" and oge["math"]["required"] is True
    assert oge["inf"]["status"] == "live" and oge["phys"]["status"] == "live"
    assert oge["rus"]["status"] == "soon" and oge["rus"]["required"] is True   # пока только самопроверка
    assert oge["hist"]["status"] == "soon" and oge["hist"]["required"] is False
    ege = {s["id"]: s for s in tracks["ege"]["subjects"]}
    assert {"math-base", "math-profile", "inf", "phys"} <= {k for k, s in ege.items() if s["status"] == "live"}
    assert ege["rus"]["status"] == "soon" and ege["rus"]["required"] is True


def test_live_means_server_checks_answers():
    from app.u2_web import GENERATED
    for track in catalog_payload().tracks:
        for subj in track.subjects:
            assert (subj.status == "live") == bool(GENERATED.get(subj.exam_id)), subj.exam_id


def test_catalog_max_points_match_exam_json():
    payload = catalog_payload()
    for track in payload.tracks:
        for subj in track.subjects:
            assert subj.max_points == em.load(subj.exam_id)["max_points"]


def test_catalog_does_not_write_users(client):  # noqa: F811
    from app.db import connect
    conn = connect()
    before = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert client.get("/api/v1/catalog").status_code == 200
    assert client.get("/api/v1/config").status_code == 200
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == before


def test_old_site_still_opens(client):  # noqa: F811
    login = client.get("/login")
    assert login.status_code == 200
    assert "html" in login.headers.get("content-type", "")


def test_notice_from_env(client, monkeypatch):  # noqa: F811
    from app import config
    monkeypatch.setattr(config, "API_NOTICE_KIND", "paused")
    monkeypatch.setattr(config, "API_NOTICE_TEXT", "Эта часть на паузе. Ответы, которые ты уже дал, на месте")
    monkeypatch.setattr(config, "API_FLAG_TRAINER", False)
    body = client.get("/api/v1/config").json()
    assert body["flags"]["trainer"] is False
    assert body["notice"]["kind"] == "paused"
    assert "на месте" in body["notice"]["text"]
