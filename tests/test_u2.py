"""Раздел umedu 2.0 (/u2): за флагом, выбор экзамена ведёт на «Сегодня», вкладки показывают прогноз."""
from app import config
from test_app import client, login  # noqa: F401 — общая фикстура с тестовой базой

TABS = ("/u2/today", "/u2/subjects", "/u2/progress", "/u2/me")


def test_hidden_without_flag(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "UMEDU2", False)
    login(client, "student")
    for path in TABS + ("/u2/start",):
        assert client.get(path).status_code == 404


def test_enroll_and_tabs(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    r = client.get("/u2/today", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/u2/start"      # без экзамена — сначала выбор
    assert "ОГЭ · Математика" in client.get("/u2/start").text

    r = client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4, "exam_date": "2027-05-20"},
                    follow_redirects=False)
    assert r.status_code == 303
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "ege-math-profile-2026", "goal": 80})

    today = client.get("/u2/today").text
    assert "ОГЭ · Математика" in today and "ЕГЭ · Математика" in today and "№" in today
    for path in TABS:
        page = client.get(path)
        assert page.status_code == 200 and 'aria-current="page"' in page.text, path
    subj = client.get("/u2/subject/oge-math-2026").text
    assert "Геометрия" in subj and "02-20" in subj
    assert client.get("/u2/subject/oge-rus-2026").status_code == 404           # экзамен не выбран
    assert "цель «4»" in client.get("/u2/me").text


def test_enroll_validation(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    bad = [{"exam_id": "no-such", "goal": 4}, {"exam_id": "oge-math-2026", "goal": 7},
           {"exam_id": "ege-rus-2026", "goal": 101}, {"exam_id": "oge-math-2026", "goal": 4, "exam_date": "завтра"}]
    for data in bad:
        assert client.post("/u2/start", data={"csrf": csrf, **data}).status_code == 400, data
    assert client.post("/u2/start", data={"exam_id": "oge-math-2026", "goal": 4}).status_code in (400, 403)  # без csrf


def test_trainer_generated_and_self_check(client, monkeypatch):  # noqa: F811
    from app import knowledge as kn
    from app.content import oge_gen
    from app.db import connect
    from test_app import sid_of
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-inf-2026", "goal": 5})
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-rus-2026", "goal": 4})

    r = client.get("/u2/train/oge-inf-2026/1", follow_redirects=False)
    assert r.status_code == 303 and "seed=" in r.headers["location"]          # генерируемый номер — свой вариант
    page = client.get("/u2/train/oge-inf-2026/1?seed=42").text
    assert 'name="answer"' in page
    right = oge_gen.make(1, 42)["answer"]
    res = client.post("/u2/train/oge-inf-2026/1", data={"csrf": csrf, "seed": 42, "answer": right}).text
    assert "Верно" in res and "Дальше по плану" in res
    sid = sid_of()
    assert kn.load_states(connect(), sid, "oge-inf-2026")[1]["n"] == 1

    page = client.get("/u2/train/oge-rus-2026/13").text                     # сочинение — самопроверка по баллам
    assert "fipi.ru/oge" in page and 'name="score" value="7"' in page
    assert "Записано: 5 из 7" in client.post("/u2/train/oge-rus-2026/13", data={"csrf": csrf, "score": 5}).text
    assert abs(kn.load_states(connect(), sid, "oge-rus-2026")[13]["p"] - (0.3 + 0.5 * (5 / 7 - 0.3))) < 1e-3
    client.post("/u2/train/oge-rus-2026/ГК", data={"csrf": csrf, "score": 9})
    assert kn.load_states(connect(), sid, "oge-rus-2026")["ГК"]["n"] == 1

    assert client.post("/u2/train/oge-rus-2026/13", data={"csrf": csrf, "score": 8}).status_code == 400
    assert client.get("/u2/train/oge-rus-2026/99").status_code == 404
    assert client.get("/u2/train/ege-inf-2026/1").status_code == 404          # экзамен не выбран
