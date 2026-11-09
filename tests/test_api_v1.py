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


# ---- этап 2: условие номера и проверка попытки без учётки ----

EXAM = "oge-math-2026"


def _first_number():
    from app.u2_web import GENERATED
    return sorted(GENERATED[EXAM])[0]


def _variant(n, seed):
    from app.u2_web import _variant
    return _variant(EXAM, n, seed)


def test_task_is_condition_without_answer(client):  # noqa: F811
    n = _first_number()
    r = client.get(f"/api/v1/tasks/{EXAM}/{n}?seed=123456")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == 1
    assert (body["exam_id"], body["n"], body["seed"]) == (EXAM, n, 123456)
    assert body["text"]
    assert set(body) <= {"schema_version", "exam_id", "n", "seed", "text", "table", "code", "svg"}
    assert not any(k in body for k in ("answer", "explain", "steps"))


def test_attempt_right_and_wrong(client):  # noqa: F811
    n = _first_number()
    answer = str(_variant(n, 123456)["answer"])
    payload = {"idempotency_key": "k" * 16, "exam_id": EXAM, "n": n, "seed": 123456}
    ok = client.post("/api/v1/attempts", json={**payload, "answer": answer})
    assert ok.status_code == 200
    body = ok.json()
    assert body["ok"] is True and body["answer"] == answer and body["idempotency_key"] == "k" * 16
    wrong = client.post("/api/v1/attempts", json={**payload, "answer": "999999"})
    assert wrong.status_code == 200
    assert wrong.json()["ok"] is False and wrong.json()["answer"] == answer


def test_same_key_same_verdict(client):  # noqa: F811
    """Один ключ идемпотентности — одна попытка: проверка детерминирована по (exam_id, n, seed)."""
    payload = {"idempotency_key": "retry-key-1", "exam_id": EXAM, "n": _first_number(),
               "seed": 424242, "answer": "0"}
    assert client.post("/api/v1/attempts", json=payload).json() \
        == client.post("/api/v1/attempts", json=payload).json()


def test_attempt_writes_nothing(client):  # noqa: F811
    from app.db import connect
    conn = connect()
    n = _first_number()
    payload = {"idempotency_key": "k" * 16, "exam_id": EXAM, "n": n, "seed": 123456, "answer": "1"}

    def state():
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        return users, tables

    before = state()
    assert client.get(f"/api/v1/tasks/{EXAM}/{n}?seed=123456").status_code == 200
    assert client.post("/api/v1/attempts", json=payload).status_code == 200
    assert state() == before


def test_unknown_exam_and_number_are_404(client):  # noqa: F811
    assert client.get("/api/v1/tasks/oge-rus-2026/1?seed=1").status_code == 404   # русский пока только самопроверка
    assert client.get(f"/api/v1/tasks/{EXAM}/99?seed=1").status_code == 404
    assert client.get("/api/v1/tasks/nope-2026/1?seed=1").status_code == 404
    r = client.post("/api/v1/attempts", json={"idempotency_key": "k" * 12, "exam_id": "oge-rus-2026",
                                              "n": 1, "seed": 1, "answer": "1"})
    assert r.status_code == 404


def test_seed_and_answer_bounds(client):  # noqa: F811
    assert client.get(f"/api/v1/tasks/{EXAM}/1?seed=0").status_code == 422
    assert client.get(f"/api/v1/tasks/{EXAM}/1?seed=10000000").status_code == 422
    base = {"idempotency_key": "k" * 12, "exam_id": EXAM, "n": 1}
    assert client.post("/api/v1/attempts", json={**base, "seed": 0, "answer": "1"}).status_code == 422
    assert client.post("/api/v1/attempts", json={**base, "seed": 1, "answer": "1" * 101}).status_code == 422
    assert client.post("/api/v1/attempts", json={**base, "seed": 1, "answer": ""}).status_code == 422
    assert client.post("/api/v1/attempts", json={**base, "seed": 1, "answer": "1"}).status_code == 200


def test_trainer_flag_pauses_stage2(client, monkeypatch):  # noqa: F811
    from app import config
    monkeypatch.setattr(config, "API_FLAG_TRAINER", False)
    assert client.get(f"/api/v1/tasks/{EXAM}/1?seed=1").status_code == 503
    r = client.post("/api/v1/attempts", json={"idempotency_key": "k" * 12, "exam_id": EXAM,
                                              "n": 1, "seed": 1, "answer": "1"})
    assert r.status_code == 503
