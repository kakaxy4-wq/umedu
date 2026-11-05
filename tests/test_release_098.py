"""umedu 0.98: восьмиклассник через родителя попадает в /u2, без даты экзамена ничего не падает.

КодКвест (семейная тема, без CQ_UMEDU2) и ХимЛаб остаются на своих страницах.
"""
import re
from datetime import date, timedelta

from app import config
from test_app import client, login, sid_of  # noqa: F401


def _badge(html, title):
    m = re.search(r'<li class="(on|off)">\s*<b>%s</b>' % re.escape(title), html)
    assert m, title
    return m.group(1)


def _diag(client, csrf, exam):
    page = client.get("/u2/diag/%s" % exam).text
    data = {"csrf": csrf}
    for name in set(re.findall(r'name="(s\d+)"', page)):
        data[name] = "0"
    r = client.post("/u2/diag/%s" % exam, data=data, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/u2/today", exam


def test_eighth_grader_path(client, monkeypatch):  # noqa: F811
    """Родитель заводит ребёнка 8 класса, ребёнок входит в /u2, берёт ОГЭ без даты, 15 минут, номер и опыт."""
    from app import students
    from app.content.math_gen import OGE
    from app.db import connect
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    students._signups.clear()
    client.cookies.clear()
    form = {"pname": "Мама", "plogin": "mama8", "ppassword": "dlinnyi-parol", "name": "Сын", "grade": 8,
            "login": "syn8", "password": "kot-luna-27", "consent": "1"}
    r = client.post("/family/new-child", data=form, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/family"
    row = connect().execute("SELECT * FROM users WHERE username = 'syn8'").fetchone()
    assert row["grade"] == 8 and row["minor"] == 1 and "родитель #" in row["consent"]

    client.cookies.clear()
    r = client.post("/login", data={"username": "syn8", "password": "kot-luna-27"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/u2/today"
    assert client.get("/", follow_redirects=False).headers["location"] == "/u2/today"
    start = client.get("/u2/start").text
    vals = re.findall(r'<input type="date" name="exam_date" value="([^"]*)"', start)
    assert vals and set(vals) == {""}
    assert "дату можно не указывать" in start
    csrf = re.search(r'name="csrf" content="([^"]+)"', start).group(1)

    for exam in ("oge-math-2026", "oge-rus-2026", "oge-phys-2026"):
        r = client.post("/u2/start", data={"csrf": csrf, "exam_id": exam, "goal": 4, "exam_date": ""},
                        follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/u2/diag/%s" % exam
        _diag(client, csrf, exam)
    dates = connect().execute("SELECT exam_date FROM exam_enroll WHERE student_id = ?", (row["id"],)).fetchall()
    assert len(dates) == 3 and all(d[0] is None for d in dates)

    r = client.post("/u2/me/minutes", data={"csrf": csrf, "minutes": 15}, follow_redirects=False)
    assert r.headers["location"] == "/u2/me"
    me = client.get("/u2/me").text
    assert 'value="15"' in me and 'aria-pressed="true"' in me
    assert _badge(me, "Первый номер") == "off" and "Монет и лавки здесь нет" in me

    today = client.get("/u2/today").text
    assert "ОГЭ · Математика" in today and "ОГЭ · Русский" in today and "ОГЭ · Физика" in today
    total = int(re.search(r"Сегодня · (\d+) минут", today).group(1))
    assert 0 < total <= 15, total
    assert "дн. до экзамена" not in today and 'href="/u2/train/' in today
    assert client.get("/u2/subject/oge-math-2026").status_code == 200
    assert "u2-proj" not in client.get("/u2/subject/oge-phys-2026").text
    assert client.get("/u2/progress").status_code == 200

    ans = OGE.make(1, 11)["answer"]
    res = client.post("/u2/train/oge-math-2026/1", data={"csrf": csrf, "seed": 11, "answer": ans}).text
    assert "Верно" in res
    lab = client.get("/u2/lab").text
    assert "Электрическая цепь" in lab or "закон Ома" in lab
    ohm = client.get("/u2/lab/ohm").text
    assert "закон Ома" in ohm and "<script src=" in ohm and "cdn" not in ohm.lower()
    me = client.get("/u2/me").text
    assert _badge(me, "Первый номер") == "on" and _badge(me, "Первый опыт") == "on"
    assert _badge(me, "Первый пробник") == "off"


def test_badges_streak_mastery_and_mock(client, monkeypatch):  # noqa: F811
    from app.content.math_gen import OGE
    from app.db import connect
    day = {"d": date(2026, 11, 5)}
    monkeypatch.setattr(config, "today", lambda: day["d"])
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4, "exam_date": ""})
    assert "u2-proj" not in client.get("/u2/subject/oge-math-2026").text
    for seed in (1, 2, 3):
        ans = OGE.make(1, seed)["answer"]
        assert "Верно" in client.post("/u2/train/oge-math-2026/1",
                                      data={"csrf": csrf, "seed": seed, "answer": ans}).text
    assert client.post("/u2/mock/oge-math-2026", data={"csrf": csrf, "seed": 4}).status_code == 200
    sid = sid_of()
    with connect() as conn:
        for i in range(1, 30):
            conn.execute("INSERT INTO skill_attempt (student_id, exam_id, task_key, score, day) "
                         "VALUES (?, 'oge-math-2026', '1', 1, ?)",
                         (sid, (day["d"] - timedelta(days=i)).isoformat()))
    me = client.get("/u2/me").text
    assert _badge(me, "Первый номер") == "on"
    assert _badge(me, "Номер освоен") == "on"
    assert _badge(me, "Первый пробник") == "on"
    assert _badge(me, "Три дня подряд") == "on"
    assert _badge(me, "Неделя подряд") == "on"
    assert _badge(me, "Месяц подряд") == "on"
    assert 'href="/shop"' not in me


def test_login_targets_by_site(client, monkeypatch):  # noqa: F811
    """Без флага ученик КодКвеста остаётся на /. ХимЛаб не уводит в /u2 даже с флагом. Преподаватель — на пульт."""
    r = client.post("/login", data={"username": "student", "password": "secret123"}, follow_redirects=False)
    assert r.headers["location"] == "/"
    assert 'href="/map"' in client.get("/").text
    client.cookies.clear()
    monkeypatch.setattr(config, "UMEDU2", True)
    r = client.post("/login", data={"username": "teacher", "password": "secret123"}, follow_redirects=False)
    assert r.headers["location"] == "/teacher"
    client.cookies.clear()
    monkeypatch.setattr(config, "CHEM_SITE", True)
    r = client.post("/login", data={"username": "student", "password": "secret123"}, follow_redirects=False)
    assert r.headers["location"] == "/chem"


def test_open_signup_lands_in_u2(client, monkeypatch):  # noqa: F811
    from app import students
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    students._signups.clear()
    client.cookies.clear()
    form = {"name": "Аня", "grade": 9, "login": "anya14", "password": "kot-luna-27", "consent": "1", "age14": "1"}
    r = client.post("/join", data=form, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/u2/today"


def test_public_hides_python_and_games(client, monkeypatch):  # noqa: F811
    from app import theme
    from app.db import connect
    monkeypatch.setattr(theme, "THEME", "public")
    with connect() as conn:
        conn.execute("UPDATE users SET subjects = 'python,russian' WHERE username = 'student'")
    login(client, "student")
    home = client.get("/").text
    nav = re.search(r'<nav class="sidenav">(.*)</nav>', home, re.S).group(1)
    for href in ("/map", "/homework", "/daily", "/oge", "/trainer", "/bots", "/playground", "/cheatsheet",
                 "/achievements", "/season", "/shop", "/today"):
        assert 'href="%s"' % href not in nav, href
    assert 'href="/ru"' in nav and "Русский язык" in nav
    assert "На арену" not in home and "Пасс" not in home and "сундук" not in home
    assert "Арена букв" in home
    assert "План на 15–30 минут" in home


def test_public_landing_explains_umedu2(client, monkeypatch):  # noqa: F811
    from app import theme
    monkeypatch.setattr(theme, "THEME", "public")
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    monkeypatch.setattr(config, "CONTACT", "https://t.me/example")
    page = client.get("/welcome").text
    assert "Подготовка к ОГЭ" in page and "ЕГЭ" in page and "Прогноз балла" in page
    assert "15" in page and "30" in page and 'href="/join"' in page and 'href="/family/new-child"' in page
    assert "/login" in page and "t.me/example" in page
    text = re.sub(r"<[^>]+>", " ", page)
    assert "Python" not in text and "Арена" not in text and "сундук" not in text and "отзыв" not in text.lower()
    assert "пилот" not in text
    for word in theme.FOREIGN_BRANDS:
        assert word not in text.lower()
