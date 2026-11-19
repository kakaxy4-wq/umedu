"""3 и 4 класс на umedu: свой набор заданий, без ОГЭ, Python и моделей.

КодКвест без CQ_UMEDU2 и ХимЛаб эти классы не предлагают.
"""
import re

from app import config
from test_app import _fam_csrf, client, login  # noqa: F401


def test_grades_follow_umedu_flag(monkeypatch):
    from app import students
    monkeypatch.setattr(config, "UMEDU2", False)
    monkeypatch.setattr(config, "CHEM_SITE", False)
    assert 3 not in students.signup_grades() and not students.is_primary_grade(3)
    monkeypatch.setattr(config, "UMEDU2", True)
    assert [students.signup_grades()[g] for g in (3, 4)] == ["3 класс", "4 класс"]
    assert students.is_primary_grade(3) and students.is_primary_grade(4)
    assert not students.is_primary_grade(8)
    monkeypatch.setattr(config, "CHEM_SITE", True)
    assert 3 not in students.signup_grades() and not students.is_primary_grade(3)


def test_tasks_are_checkable_and_in_range():
    from app.content.primary_tasks import TASKS
    from app import primary
    topics = {}
    assert len({t["id"] for t in TASKS}) == len(TASKS)
    for t in TASKS:
        assert primary.check(t, t["accept"][0]), t["id"]
        assert primary.check(t, "  %s. " % t["accept"][0]), t["id"]
        assert not primary.check(t, ""), t["id"]
        assert not primary.check(t, "не-тот-ответ"), t["id"]
        if t["choices"]:
            wrong = next(c for c in t["choices"] if primary.norm(c) != primary.norm(t["accept"][0]))
            assert not primary.check(t, wrong), t["id"]
        topics.setdefault((t["grade"], t["subject"]), set()).add(t["topic"])
    for grade in (3, 4):
        for subject in ("math", "russian", "world"):
            n = primary.counts()[(grade, subject)]
            assert 20 <= n <= 40, (grade, subject, n)
    assert "Падежи" not in topics[(3, "russian")]
    assert "Падежи" in topics[(4, "russian")]
    assert {"Таблица умножения", "Деление", "Периметр и площадь"} <= topics[(3, "math")]
    assert "Доли" in topics[(4, "math")]
    assert primary.norm("  Ёлка. ") == "елка"
    assert primary.check(primary.BY_ID["m3-01"], "42")
    assert not primary.check(primary.BY_ID["m3-01"], "41")
    assert primary.hidden_path("/shop") and primary.hidden_path("/oge") and primary.hidden_path("/u2/models")
    assert primary.hidden_path("/u2/lab") and primary.hidden_path("/u2/start") and primary.hidden_path("/lesson/1")
    assert not primary.hidden_path("/u2/today")
    assert not primary.hidden_path("/u2/subjects")
    assert not primary.hidden_path("/u2/p/math/m3-01")


def _child(client, grade, login_name, name):
    from app import students
    students._signups.clear()
    client.cookies.clear()
    form = {"pname": "Мама", "plogin": "mama%s" % grade, "ppassword": "dlinnyi-parol", "name": name,
            "grade": grade, "login": login_name, "password": "kot-luna-27", "consent": "1"}
    r = client.post("/family/new-child", data=form, follow_redirects=False)
    assert r.status_code == 303, r.text
    return form


def test_primary_student_path(client, monkeypatch):  # noqa: F811
    from app.db import connect
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "CHEM_SITE", False)
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    _child(client, 3, "petya3", "Петя")
    row = connect().execute("SELECT * FROM users WHERE username = 'petya3'").fetchone()
    assert row["grade"] == 3 and row["subjects"] == "primary" and row["minor"] == 1
    assert not connect().execute("SELECT 1 FROM check_state WHERE student_id = ? AND id = 'oge1'", (row["id"],)).fetchone()
    assert not connect().execute("SELECT 1 FROM lesson_state WHERE student_id = ?", (row["id"],)).fetchone()
    page = client.get("/family/new-child").text
    assert "3 класс" in page and "4 класс" in page
    card = client.get("/family/child/%d" % row["id"]).text
    assert "Начальная школа" in card and "Гуру Python" not in card and "Прогноз ОГЭ" not in card
    assert "3 класс" in card
    client.post("/family/child/%d/grade" % row["id"], data={"grade": 4, "csrf": _fam_csrf(card)}, follow_redirects=False)
    assert connect().execute("SELECT grade FROM users WHERE username = 'petya3'").fetchone()[0] == 4
    client.post("/family/child/%d/grade" % row["id"], data={"grade": 3, "csrf": _fam_csrf(card)}, follow_redirects=False)

    client.cookies.clear()
    r = client.post("/login", data={"username": "petya3", "password": "kot-luna-27"}, follow_redirects=False)
    assert r.headers["location"] == "/u2/today"
    today = client.get("/u2/today").text
    assert "Сегодня, 3 класс" in today and "6 × 7" in today and "ОГЭ" not in today
    assert "Интерактивные модели" not in today and "html.u2.junior" not in today and 'class="u2 junior"' in today
    assert "Уроки" in today and "Успехи" in today
    for path in ("/shop", "/oge", "/bots", "/lesson/1", "/u2/models", "/u2/lab", "/u2/start", "/u2/train/oge-math-2026/1"):
        assert client.get(path).status_code == 404, path
    csrf = re.search(r'name="csrf" content="([^"]+)"', today).group(1)
    task = client.get("/u2/p/math/m3-01").text
    assert "42" not in task.split("<body", 1)[1] and "6 × 7" in task
    assert 'action="/u2/p/math/m3-01"' in task
    assert client.get("/u2/p/math/m4-01").status_code == 404
    bad = client.post("/u2/p/math/m3-01", data={"csrf": csrf, "answer": "41"}).text
    assert "Пока не так" in bad and "42" in bad
    good = client.post("/u2/p/math/m3-01", data={"csrf": csrf, "answer": "42"}).text
    assert "Верно" in good and "6 × 7 = 42" in good
    assert [r[0] for r in connect().execute(
        "SELECT ok FROM primary_attempt WHERE student_id = ? ORDER BY id", (row["id"],))] == [0, 1]
    prog = client.get("/u2/progress").text
    assert "1 из 26" in prog
    me = client.get("/u2/me").text
    assert 'value="3"' in me and 'aria-pressed="true"' in me
    client.post("/u2/me/grade", data={"csrf": csrf, "grade": 4}, follow_redirects=False)
    assert "47 × 23" in client.get("/u2/today").text and "6 × 7" not in client.get("/u2/today").text
    assert client.get("/u2/p/math/m3-01").status_code == 404
    client.post("/u2/me/grade", data={"csrf": csrf, "grade": 8}, follow_redirects=False)
    start = client.get("/u2/start").text
    assert "ОГЭ · 9 класс" in start
    assert client.get("/u2/models").status_code == 200
    assert client.post("/u2/me/grade", data={"csrf": csrf, "grade": 5}).status_code == 400
    assert connect().execute("SELECT grade FROM users WHERE id = ?", (row["id"],)).fetchone()[0] == 8

    client.cookies.clear()
    login(client, "student")
    assert "ОГЭ" in client.get("/u2/start").text
    assert client.get("/u2/models").status_code == 200
