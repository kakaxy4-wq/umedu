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


# ---- этап 3: онбординг гостем, запись попыток, прогноз ----


def _session(client, device="device-abc12345"):
    r = client.post("/api/v1/sessions", json={"device_id": device})
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == 1 and body["token"] and body["created"] is True
    return body["token"]


def _attempt(client, token, n, seed, answer, key="k" * 16):
    return client.post("/api/v1/attempts", json={"idempotency_key": key, "exam_id": EXAM, "n": n,
                                                 "seed": seed, "answer": answer},
                       headers={"Authorization": "Bearer " + token})


def test_session_is_guest_without_password(client):  # noqa: F811
    from app.db import connect
    token = _session(client)
    row = connect().execute("SELECT username, role, guest, display_name FROM users WHERE guest = 1").fetchone()
    assert row["username"].startswith("api-") and row["role"] == "student"
    assert row["display_name"] == "Гость"
    # гость не виден преподавателю в списках учеников
    from app import students
    conn = connect()
    names = [s["username"] for s in students.list_students(conn, include_archived=True)]
    assert row["username"] not in names


def test_same_device_returns_same_guest(client):  # noqa: F811
    first = client.post("/api/v1/sessions", json={"device_id": "device-abc12345"}).json()
    again = client.post("/api/v1/sessions", json={"device_id": "device-abc12345"}).json()
    assert first["created"] is True and again["created"] is False
    assert again["token"] != first["token"]                    # токен обновился
    from app.db import connect
    conn = connect()
    assert conn.execute("SELECT COUNT(*) FROM users WHERE guest = 1").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM api_sessions").fetchone()[0] == 1
    # старый токен больше не работает, новый — работает
    r = client.get(f"/api/v1/forecast/{EXAM}", headers={"Authorization": "Bearer " + first["token"]})
    assert r.status_code == 401
    assert client.get(f"/api/v1/forecast/{EXAM}", headers={"Authorization": "Bearer " + again["token"]}).status_code == 200


def test_session_bad_input(client):  # noqa: F811
    assert client.post("/api/v1/sessions", json={"device_id": "коротко"}).status_code == 422
    assert client.post("/api/v1/sessions", json={}).status_code == 422


def test_attempt_with_session_is_recorded(client):  # noqa: F811
    from app.db import connect
    token = _session(client)
    n, seed = _first_number(), 123456
    answer = str(_variant(n, seed)["answer"])
    r = _attempt(client, token, n, seed, answer)
    assert r.status_code == 200 and r.json()["ok"] is True
    conn = connect()
    rows = conn.execute("SELECT student_id, exam_id, task_key, score, seed, given FROM skill_attempt").fetchall()
    assert len(rows) == 1 and rows[0]["exam_id"] == EXAM and int(rows[0]["task_key"]) == n
    assert rows[0]["score"] == 1.0 and rows[0]["given"] == answer
    st = conn.execute("SELECT p, n FROM skill_state").fetchone()
    assert st["n"] == 1 and st["p"] > 0.3        # p сдвинулся от старта к успеху
    # ошибка тоже пишется
    r = _attempt(client, token, n, seed + 1, "999999", key="k" * 15)
    assert r.json()["ok"] is False
    conn = connect()
    assert conn.execute("SELECT COUNT(*) FROM skill_attempt").fetchone()[0] == 2


def test_same_key_recorded_once(client):  # noqa: F811
    """Один ключ — одна попытка: повтор с тем же ключом возвращает тот же ответ и не пишет вторую попытку."""
    from app.db import connect
    token = _session(client)
    n, seed = _first_number(), 424242
    payload_answer = str(_variant(n, seed)["answer"])
    first = _attempt(client, token, n, seed, payload_answer, key="retry-key-1")
    again = _attempt(client, token, n, seed, payload_answer, key="retry-key-1")
    assert again.status_code == 200 and again.json() == first.json()
    assert connect().execute("SELECT COUNT(*) FROM skill_attempt").fetchone()[0] == 1
    assert connect().execute("SELECT COUNT(*) FROM api_attempt_keys").fetchone()[0] == 1


def test_same_key_other_request_is_422(client):  # noqa: F811
    token = _session(client)
    n = _first_number()
    assert _attempt(client, token, n, 1, "1", key="retry-key-2").status_code == 200
    r = _attempt(client, token, n, 2, "1", key="retry-key-2")     # другой seed
    assert r.status_code == 422


def test_forecast_empty_and_after_attempts(client):  # noqa: F811
    token = _session(client)
    r = client.get(f"/api/v1/forecast/{EXAM}", headers={"Authorization": "Bearer " + token})
    assert r.status_code == 200
    body = r.json()
    assert body["exam_id"] == EXAM and body["low"] <= body["primary"] <= body["high"]
    assert "grade" in body and "test" not in body            # ОГЭ — шкала отметок
    n, seed = _first_number(), 123456
    answer = str(_variant(n, seed)["answer"])
    assert _attempt(client, token, n, seed, answer).status_code == 200
    after = client.get(f"/api/v1/forecast/{EXAM}", headers={"Authorization": "Bearer " + token}).json()
    assert after["primary"] > body["primary"]                # верная попытка поднимает прогноз


def test_forecast_requires_session(client):  # noqa: F811
    assert client.get(f"/api/v1/forecast/{EXAM}").status_code == 401
    assert client.get(f"/api/v1/forecast/{EXAM}", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/v1/forecast/nope-2026", headers={"Authorization": "Bearer " + _session(client)}).status_code == 404


def test_attempts_bad_token_is_401(client):  # noqa: F811
    n = _first_number()
    r = client.post("/api/v1/attempts", json={"idempotency_key": "k" * 12, "exam_id": EXAM, "n": n,
                                              "seed": 1, "answer": "1"}, headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_anonymous_attempt_still_writes_nothing(client):  # noqa: F811
    from app.db import connect
    conn = connect()
    n = _first_number()
    payload = {"idempotency_key": "k" * 16, "exam_id": EXAM, "n": n, "seed": 123456, "answer": "1"}

    def state():
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        skill = conn.execute("SELECT COUNT(*) FROM skill_attempt").fetchone()[0]
        keys = conn.execute("SELECT COUNT(*) FROM api_attempt_keys").fetchone()[0]
        return users, skill, keys

    before = state()
    assert client.post("/api/v1/attempts", json=payload).status_code == 200
    assert state() == before


def test_guests_flag_pauses_onboarding(client, monkeypatch):  # noqa: F811
    from app import config
    monkeypatch.setattr(config, "API_FLAG_GUESTS", False)
    assert client.get("/api/v1/config").json()["flags"]["guests"] is False
    assert client.post("/api/v1/sessions", json={"device_id": "device-abc12345"}).status_code == 503


def test_session_rate_limit(client, monkeypatch):  # noqa: F811
    from app import api_v1
    monkeypatch.setattr(api_v1.config, "API_SESSIONS_PER_HOUR", 2)
    api_v1._sessions.clear()
    assert client.post("/api/v1/sessions", json={"device_id": "device-11111111"}).status_code == 200
    assert client.post("/api/v1/sessions", json={"device_id": "device-22222222"}).status_code == 200
    assert client.post("/api/v1/sessions", json={"device_id": "device-33333333"}).status_code == 429


def test_teacher_lists_and_quota_ignore_guests(client):  # noqa: F811
    from app.db import connect
    from app import students
    token = _session(client)
    assert _attempt(client, token, _first_number(), 1, "1").status_code == 200
    conn = connect()
    assert conn.execute("SELECT COUNT(*) FROM users WHERE guest = 1").fetchone()[0] == 1
    assert all(not s.get("guest") for s in students.list_students(conn, include_archived=True))
    # лимит мест не занят гостем: место ещё есть
    assert conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student' AND active = 1 AND guest = 0").fetchone()[0] <= students.MAX_STUDENTS
