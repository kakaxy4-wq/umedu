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
    start = client.get("/u2/start").text
    assert "ОГЭ · 9 класс" in start and "ЕГЭ · 11 класс" in start and start.count("u2-card u2-pick") == 21

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


def test_diag_seeds_start_without_attempts(client, monkeypatch):  # noqa: F811
    from app import knowledge as kn
    from app.db import connect
    from test_app import sid_of
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    r = client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4}, follow_redirects=False)
    assert r.headers["location"] == "/u2/diag/oge-math-2026"                 # новый экзамен — сначала самооценка
    page = client.get("/u2/diag/oge-math-2026").text
    assert "Геометрия" in page and 'name="s2"' in page
    client.post("/u2/train/oge-math-2026/18", data={"csrf": csrf, "score": 1})  # по №18 уже есть попытка
    # практика — «почти всегда», алгебра — пропущена, геометрия — «не умею»
    client.post("/u2/diag/oge-math-2026", data={"csrf": csrf, "s0": 3, "s2": 0})
    states = kn.load_states(connect(), sid_of(), "oge-math-2026")
    assert states[1]["p"] == 0.85 and states[1]["n"] == 0
    assert 6 not in states                                                    # пропущенный раздел не тронут
    assert states[16]["p"] == 0.1 and states[18]["n"] == 1 and states[18]["p"] > 0.1   # попытку не затирает
    r = client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 5}, follow_redirects=False)
    assert r.headers["location"] == "/u2/today"                              # смена цели — без повторной оценки


def test_task_ranges_label():
    import app.main  # noqa: F401 — u2_web подключается из main
    from app.u2_web import _ranges
    assert _ranges([1, 2, 3, 4, 5]) == "1–5"
    assert _ranges([15, 16, 17, 18, 19, 23, 24, 25]) == "15–19, 23–25"
    assert _ranges([1, 2, 4]) == "1, 2, 4" and _ranges([7]) == "7"


def test_daily_minutes_setting(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    assert "Сегодня · 30 минут" in client.get("/u2/today").text
    client.post("/u2/me/minutes", data={"csrf": csrf, "minutes": 60})
    import re
    total = int(re.search(r"Сегодня · (\d+) минут", client.get("/u2/today").text).group(1))
    assert 50 < total <= 60                                                  # план заполняет новое время, не больше
    assert 'value="60" aria-pressed="true"' in client.get("/u2/me").text
    assert client.post("/u2/me/minutes", data={"csrf": csrf, "minutes": 7}).status_code == 400


def test_forecast_history_and_chart(client, monkeypatch):  # noqa: F811
    from datetime import timedelta
    from app import knowledge as kn
    from app.db import connect
    from test_app import sid_of
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    assert "График появится со второго дня" in client.get("/u2/progress").text
    client.post("/u2/train/oge-math-2026/1", data={"csrf": csrf, "score": 1})
    client.post("/u2/train/oge-math-2026/2", data={"csrf": csrf, "score": 1})
    conn, sid, today = connect(), sid_of(), config.today()
    hist = kn.history(conn, sid, "oge-math-2026", today=today)
    assert len(hist) == 1 and hist[0]["day"] == today.isoformat()              # одна строка в день
    with conn:
        for k in range(1, 6):
            kn.record(conn, sid, "oge-math-2026", k + 2, 1, today - timedelta(days=9))
        kn.log_forecast(conn, sid, "oge-math-2026", today - timedelta(days=9))
    hist = kn.history(conn, sid, "oge-math-2026", today=today)
    assert [h["day"] for h in hist] == sorted(h["day"] for h in hist) and len(hist) == 2
    page = client.get("/u2/progress").text
    assert "<polyline" in page and "u2-chart-band" in page


def test_schedule_prefills_exam_date(client, monkeypatch):  # noqa: F811
    """Расписание 2027 покрывает все экзамены каталога; на выборе дата подставлена, сохранённая — побеждает."""
    from datetime import date
    from app import exam_model as em
    from app.u2_web import SCHEDULE, _dates
    for exam_id in em.all_ids():
        ds = _dates(exam_id)
        assert ds and ds == sorted(ds), exam_id
        lo, hi = SCHEDULE["periods"][em.load(exam_id)["exam"]]["main"]
        assert all(lo <= d <= hi for d in ds), exam_id                     # внутри основного периода
        assert all(date.fromisoformat(d).weekday() != 6 for d in ds), exam_id   # не воскресенье
    assert set(SCHEDULE["dates"]) == {i.rsplit("-", 1)[0] for i in em.all_ids()}
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    start = client.get("/u2/start").text
    assert 'value="2027-06-02"' in start and "проекту расписания 2027" in start and "скажут в школе" in start
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4, "exam_date": "2027-06-28"})
    start = client.get("/u2/start").text
    assert 'value="2027-06-28"' in start and 'value="2027-06-02"' not in start


def test_math_generators_selfcheck():
    """Каждый вариант по математике: эталон проходит свою проверку, ответ — конечная десятичная дробь или цифры,
    условие без «-5» вместо «−5»; одна пара (номер, сид) — один и тот же вариант."""
    from app.content import inf_gen, phys_gen
    from app.content import math_gen as mg
    for bank in (mg.OGE, mg.EGE_PROFILE, mg.EGE_BASE, inf_gen.EGE, phys_gen.OGE, phys_gen.EGE):
        for num in bank.GENERATORS:
            for seed in range(1, 150):
                v = bank.make(num, seed)
                assert bank.check(v, v["answer"]) and not bank.check(v, v["answer"] + "1"), (bank.prefix, num, seed)
                assert mg._num(v["answer"]) is not None
                assert " -" not in v["text"] + v["explain"], (bank.prefix, num, seed)
            assert bank.make(num, 5) == bank.make(num, 5)
    assert mg.OGE.check(mg.OGE.make(10, 3), mg.OGE.make(10, 3)["answer"].replace(",", "."))   # точка тоже годится
    assert mg.fmt(mg.F(-11, 4)) == "-2,75" and not mg.finite(mg.F(1, 3))
    v = mg.EGE_BASE.make(19, 4)                                 # №19: подходит любое число с нужными свойствами
    rule = v["accept"]
    others = [x for x in range(100, 1000) if x % rule["k"] == 0 and sum(map(int, str(x))) == rule["s"]]
    assert all(mg.EGE_BASE.check(v, str(x)) for x in others) and not mg.EGE_BASE.check(v, "1000")


def test_math_trainer(client, monkeypatch):  # noqa: F811
    from app import knowledge as kn
    from app.content import math_gen as mg
    from app.db import connect
    from test_app import sid_of
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    assert "seed=" in client.get("/u2/train/oge-math-2026/9", follow_redirects=False).headers["location"]
    page = client.get("/u2/train/oge-math-2026/9?seed=11").text
    assert 'name="answer"' in page and "Уравнения" in page
    v = mg.OGE.make(9, 11)
    res = client.post("/u2/train/oge-math-2026/9", data={"csrf": csrf, "seed": 11, "answer": "999999"}).text
    assert "Неверно" in res and v["answer"].replace("-", "−") in res.replace("-", "−")
    assert kn.load_states(connect(), sid_of(), "oge-math-2026")[9]["n"] == 1
    page = client.get("/u2/train/oge-math-2026/18").text                     # клетчатая бумага — самопроверка
    assert 'name="score"' in page


def test_subject_mentions_regional_scale(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "ege-rus-2026", "goal": 80})
    assert "Регион может утвердить свою шкалу" in client.get("/u2/subject/oge-math-2026").text
    assert "Регион может" not in client.get("/u2/subject/ege-rus-2026").text   # шкала ЕГЭ единая
