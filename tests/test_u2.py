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
                assert mg._num(v["answer"]) is not None or v["accept"]["kind"] == "text"
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


def test_progress_by_numbers(client, monkeypatch):  # noqa: F811
    """«Прогресс → По номерам»: 3 верных подряд — освоено, ошибка после них — проседает; попытки пишутся в журнал
    вместе с вариантом и ответом ученика."""
    from app.content import math_gen as mg
    from app.db import connect
    from test_app import sid_of
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    for seed in (1, 2, 3):
        client.post("/u2/train/oge-math-2026/6", data={"csrf": csrf, "seed": seed, "answer": mg.OGE.make(6, seed)["answer"]})
    client.post("/u2/train/oge-math-2026/7", data={"csrf": csrf, "seed": 5, "answer": "999999"})
    client.post("/u2/train/oge-math-2026/8", data={"csrf": csrf, "seed": 5, "answer": mg.OGE.make(8, 5)["answer"]})
    page = client.get("/u2/progress").text
    done = page.split("Освоено")[1]
    sag = page.split("Проседает")[1].split("В работе")[0]
    work = page.split("В работе")[1].split("Освоено")[0]
    assert "№6" in done and "№7" in sag and "последняя попытка неверная" in sag and "№8" in work
    assert "подряд: 1 из 3" in work and "Ещё не решал ни разу" in page
    client.post("/u2/train/oge-math-2026/6", data={"csrf": csrf, "seed": 9, "answer": "999999"})
    page = client.get("/u2/progress").text
    assert "№6" in page.split("Проседает")[1].split("В работе")[0] and "Освоено" not in page
    rows = connect().execute("SELECT task_key, score, seed, given FROM skill_attempt WHERE student_id = ? ORDER BY id",
                             (sid_of(),)).fetchall()
    assert [tuple(r) for r in rows][-2:] == [("8", 1.0, 5, mg.OGE.make(8, 5)["answer"]), ("6", 0.0, 9, "999999")]


def test_mock_exam(client, monkeypatch):  # noqa: F811
    """Мини-пробник: набор номеров на 25 минут из своих генераторов, сдача целиком, разбор только ошибок; каждая
    задача — попытка в журнале и пересчёт прогноза. Для экзамена без генераторов пробника нет."""
    from app import u2_web
    from app.db import connect
    from app import exam_model as em
    from test_app import sid_of
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    assert "seed=" in client.get("/u2/mock/oge-math-2026", follow_redirects=False).headers["location"]
    exam = em.load("oge-math-2026")
    items = u2_web._mock_items(exam, 7)
    assert len(items) >= 5 and len({n for n, _ in items}) == len(items)
    assert sum(3 for _ in items) <= u2_web.MOCK_MINUTES
    page = client.get("/u2/mock/oge-math-2026?seed=7").text
    assert all(f'name="a{n}"' in page for n, _ in items) and "Сдать" in page
    first, rest = items[0], items[1:]
    data = {"csrf": csrf, "seed": 7, f"a{first[0]}": u2_web._variant("oge-math-2026", *first)["answer"]}
    data.update({f"a{n}": "999999" for n, _ in rest[:-1]})                # последний оставлен пустым — тоже ошибка
    res = client.post("/u2/mock/oge-math-2026", data=data).text
    assert f"1 из {len(items)} верно" in res and res.count("Решить похожий") == len(items) - 1
    rows = connect().execute("SELECT task_key, score, seed FROM skill_attempt WHERE student_id = ? ORDER BY id",
                             (sid_of(),)).fetchall()
    assert [(int(k), s) for k, _, s in rows] == items and [r[1] for r in rows].count(1.0) == 1
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-rus-2026", "goal": 4})
    assert client.get("/u2/mock/oge-rus-2026?seed=3").status_code == 404
    assert "мини-пробник" in client.get("/u2/today").text.lower()


def test_teacher_class_view(client, monkeypatch):  # noqa: F811
    """Учитель видит учеников по экзаменам: прогноз, цель, слабые номера, попытки за неделю; ученику экран закрыт."""
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    assert client.get("/u2/class").status_code == 403
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 5})
    for seed in (1, 2):
        client.post("/u2/train/oge-math-2026/9", data={"csrf": csrf, "seed": seed, "answer": "999999"})
    login(client, "teacher")
    assert "/u2/class" in client.get("/teacher").text
    page = client.get("/u2/class").text
    assert "ОГЭ · Математика" in page and "№9" in page and "u2-behind" in page
    row = page.split("№9")[0].rsplit("<tr>", 1)[1]
    assert "/teacher/student/" in row
    assert ">2<" in page.split("№9")[1].split("</tr>")[0]            # попыток за 7 дней


def test_how_forecast_page(client, monkeypatch):  # noqa: F811
    """«Как считается прогноз»: числа из knowledge (не вписаны в текст руками), пример посчитан тем же update."""
    from app import knowledge as kn
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    page = client.get("/u2/how").text
    assert f"шанс\n    {round(kn.PRIOR * 100)} %" in page and f"за {kn.HALF_LIFE_DAYS} дней" in page
    p = round(kn.update(kn.update(None, 1), 1)["p"] * 100)
    assert f"2-я попытка: верно → шанс {p} %" in page
    assert 'href="/u2/how"' in client.get("/u2/subject/oge-math-2026").text
    today = client.get("/u2/today").text
    assert 'href="/u2/how"' not in today                         # карточка — сама ссылка, вложенной не будет


def test_my_mistakes(client, monkeypatch):  # noqa: F811
    """«Мои ошибки»: неверный вариант пересобирается по сиду (условие, свой ответ, верный, разбор), после верного
    решения того же номера помечается «исправлено»; самопроверка без сида сюда не попадает."""
    from app.content import math_gen as mg
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    assert "Ошибок пока нет" in client.get("/u2/mistakes").text
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    client.post("/u2/train/oge-math-2026/9", data={"csrf": csrf, "seed": 21, "answer": "424242"})
    client.post("/u2/train/oge-math-2026/18", data={"csrf": csrf, "score": 0})
    v = mg.OGE.make(9, 21)
    page = client.get("/u2/mistakes").text
    assert "424242" in page and v["answer"].replace("-", "−") in page.replace("-", "−") and "№18" not in page
    assert "ошибка</span>" in page and "/u2/train/oge-math-2026/9" in page
    client.post("/u2/train/oge-math-2026/9", data={"csrf": csrf, "seed": 22, "answer": mg.OGE.make(9, 22)["answer"]})
    assert "исправлено" in client.get("/u2/mistakes").text


def test_day_streak_and_week(client, monkeypatch):  # noqa: F811
    """Серия — дни подряд с попытками; сегодняшний день её не обрывает, пока не прошёл. Неделя — пн–вс."""
    from datetime import date, timedelta
    from app import knowledge as kn
    from app.db import connect
    from test_app import sid_of
    login(client, "student")
    conn, sid = connect(), sid_of()
    wed = date(2026, 10, 28)                                       # среда
    for d in (wed - timedelta(days=k) for k in (1, 2, 3, 6)):      # вт, пн, вс прошлой недели, чт прошлой недели
        conn.execute("INSERT INTO skill_attempt (student_id, exam_id, task_key, score, day) VALUES (?, 'oge-math-2026', "
                     "'6', 1, ?)", (sid, d.isoformat()))
    conn.commit()
    a = kn.activity(conn, sid, wed)
    assert a["streak"] == 3 and not a["today"] and a["week"] == [True, True, False, False, False, False, False]
    assert kn.activity(conn, sid, wed + timedelta(days=1))["streak"] == 0       # пропущена среда — серия прервалась
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "today", lambda: wed)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    page = client.get("/u2/today").text
    assert "3</b> дня подряд" in page and "серия продолжится" in page and "2 из 5" in page


def test_projection_to_exam_date(client, monkeypatch):  # noqa: F811
    """Прогноз к экзамену: без занятий — только забывание; больше минут в день — не хуже; на странице предмета
    оба варианта, если дата экзамена известна."""
    from datetime import date
    from app import exam_model as em
    from app import knowledge as kn
    ex, today, until = em.load("oge-math-2026"), date(2026, 10, 29), date(2027, 6, 1)
    states = {n: {"p": 0.9, "n": 5, "last": today.isoformat()} for n in range(1, 10)}
    idle = kn.project(ex, states, today, until, 0)
    assert idle == kn.forecast(ex, states, until) and idle["primary"] < kn.forecast(ex, states, today)["primary"]
    runs = [kn.project(ex, states, today, until, m)["primary"] for m in (5, 15, 45)]
    assert idle["primary"] < runs[0] <= runs[1] <= runs[2]
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4, "exam_date": "2027-06-01"})
    page = client.get("/u2/subject/oge-math-2026").text
    assert "К дню экзамена" in page and "Если не заниматься" in page and "По плану — 30 мин в день" in page


def test_path_to_goal(client, monkeypatch):  # noqa: F811
    """Путь к цели: освоив номера из списка до 90 %, ученик по прогнозу выходит на цель; без последнего — нет."""
    from datetime import date
    from app import exam_model as em
    from app import knowledge as kn
    ex, today = em.load("oge-math-2026"), date(2026, 10, 29)
    path = kn.path_to_goal(ex, {}, 4, today)
    assert path["reached"] and path["steps"]
    done = {s["n"]: {"p": kn.MASTER_P, "n": 1, "last": today.isoformat()} for s in path["steps"]}
    assert kn.forecast(ex, done, today)["grade"] >= 4
    del done[path["steps"][-1]["n"]]
    assert kn.forecast(ex, done, today)["grade"] < 4
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    page = client.get("/u2/subject/oge-math-2026").text
    assert "Путь к цели «4»" in page and f"Хватит освоить {len(path['steps'])}" in page


def test_first_steps(client, monkeypatch):  # noqa: F811
    """Первые шаги на «Сегодня»: отмечаются по данным и пропадают после первой попытки."""
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    page = client.get("/u2/today").text
    assert "Первые шаги" in page and 'href="/u2/diag/oge-math-2026"' in page and "Решить первое задание из плана: №" in page
    client.post("/u2/train/oge-math-2026/6", data={"csrf": csrf, "seed": 3, "answer": "1"})
    assert "Первые шаги" not in client.get("/u2/today").text


def test_parent_sees_u2_forecast(client, monkeypatch):  # noqa: F811
    """Родитель по ссылке видит прогноз umedu 2.0, цель и что подтянуть — только при включённом флаге."""
    from test_app import _parent_token, sid_of
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 5})
    client.post("/u2/train/oge-math-2026/9", data={"csrf": csrf, "seed": 4, "answer": "424242"})
    token = _parent_token(client, sid_of())
    client.cookies.clear()
    page = client.get("/parent/%s" % token).text
    assert "ОГЭ · Математика" in page and "цель «5»" in page and "Заданий за неделю: 1" in page and "№9" in page
    monkeypatch.setattr(config, "UMEDU2", False)
    assert "ОГЭ · Математика" not in client.get("/parent/%s" % token).text


def test_u2_access_rules(client, monkeypatch):  # noqa: F811
    """Доступ: чужой (невыбранный) экзамен — 404; преподаватель смотрит, но не пишет попытки; любой POST без
    CSRF — 403; аноним не видит раздел; кэш модели экзамена после обхода страниц не изменён."""
    import json
    from app import exam_model as em
    from app import u2_web
    monkeypatch.setattr(config, "UMEDU2", True)
    before = json.dumps(em.load("oge-math-2026"), sort_keys=True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4, "exam_date": "2027-06-01"})
    for url in ("/u2/subject/ege-inf-2026", "/u2/train/ege-inf-2026/7?seed=3", "/u2/mock/ege-inf-2026?seed=3",
                "/u2/diag/ege-inf-2026"):
        assert client.get(url).status_code == 404, url
    for url, data in (("/u2/train/ege-inf-2026/7", {"seed": 3, "answer": "1"}), ("/u2/mock/ege-inf-2026", {"seed": 3}),
                      ("/u2/diag/ege-inf-2026", {})):
        assert client.post(url, data={"csrf": csrf, **data}).status_code == 404, url
    # все POST раздела без токена
    posts = [r.path for r in u2_web.router.routes if "POST" in r.methods]
    assert len(posts) >= 5
    for path in posts:
        url = path.replace("{exam_id}", "oge-math-2026").replace("{raw}", "9")
        assert client.post(url, data={"seed": 3, "answer": "1", "minutes": 30, "exam_id": "oge-math-2026",
                                      "goal": 4}).status_code == 403, url
    for url in ("/u2/today", "/u2/progress", "/u2/mistakes", "/u2/subject/oge-math-2026", "/u2/how",
                "/u2/mock/oge-math-2026?seed=5", "/u2/train/oge-math-2026/9?seed=5"):
        assert client.get(url).status_code == 200, url
    # преподаватель: страницы ученика открываются, записи — нет
    t = login(client, "teacher")
    assert client.get("/u2/subject/oge-math-2026").status_code == 200
    for url, data in (("/u2/train/oge-math-2026/9", {"seed": 3, "answer": "1"}), ("/u2/mock/oge-math-2026", {"seed": 3}),
                      ("/u2/me/minutes", {"minutes": 30}), ("/u2/diag/oge-math-2026", {})):
        assert client.post(url, data={"csrf": t, **data}).status_code == 403, url
    client.cookies.clear()
    r = client.get("/u2/today", follow_redirects=False)
    assert r.status_code in (303, 307, 401) and "Сегодня" not in r.text
    assert json.dumps(em.load("oge-math-2026"), sort_keys=True) == before


def test_attempt_budget_per_day(client, monkeypatch):  # noqa: F811
    """Журнал попыток не накрутить скриптом: сверх дневного лимита — 429, попытка не записывается."""
    from app import u2_web
    from app.db import connect
    from test_app import sid_of
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(u2_web, "MAX_ATTEMPTS_PER_DAY", 2)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    codes = [client.post("/u2/train/oge-math-2026/9", data={"csrf": csrf, "seed": s, "answer": "1"}).status_code
             for s in (1, 2, 3)]
    assert codes == [200, 200, 429]
    assert client.post("/u2/mock/oge-math-2026", data={"csrf": csrf, "seed": 5}).status_code == 429
    assert connect().execute("SELECT COUNT(*) FROM skill_attempt WHERE student_id = ?", (sid_of(),)).fetchone()[0] == 2
