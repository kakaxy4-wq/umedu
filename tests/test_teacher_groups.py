"""Несколько преподавателей на одном сайте: регистрация, код группы, изоляция (issue #13)."""
import re

from test_app import add_student, client, login_as  # noqa: F401

TEACHER = re.compile(r"Код приглашения|Ваш код|[A-Z0-9]{8}")


def _signup_teacher(client, login, name="Репетитор"):
    """Открытая регистрация преподавателя; возвращает (код приглашения, пароль)."""
    r = client.get("/signup-teacher")
    assert r.status_code == 200 and "Кабинет репетитора" in r.text
    password = "urok-6-simv"
    r = client.post("/signup-teacher", data={"name": name, "login": login, "password": password,
                                             "consent": "1", "website": ""}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/teacher/students", r.text[:200]
    from app.db import connect
    row = connect().execute("SELECT invite_code FROM users WHERE username = ?", (login,)).fetchone()
    assert row and re.fullmatch(r"[A-Z0-9]{6,8}", row[0] or ""), row
    return row[0], password


def test_teacher_signup_and_gate(client, monkeypatch):
    from app import config
    # гейт закрыт — 404
    monkeypatch.setattr(config, "OPEN_SIGNUP", False)
    assert client.get("/signup-teacher").status_code == 404
    assert client.post("/signup-teacher", data={"name": "x", "login": "t-x", "password": "abcdef",
                                                "consent": "1"}).status_code == 404
    # открыта — работает
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    code, password = _signup_teacher(client, "t-anna")
    assert code
    client.cookies.clear()
    assert client.post("/login", data={"username": "t-anna", "password": password},
                       follow_redirects=False).status_code == 303
    # дубль логина
    r = client.post("/signup-teacher", data={"name": "Кто-то", "login": "t-anna", "password": "abcdef",
                                             "consent": "1", "website": ""})
    assert "уже занят" in r.text


def test_join_by_code_and_isolation(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    code_a, _ = _signup_teacher(client, "t-a", "Учитель A")
    code_b, _ = _signup_teacher(client, "t-b", "Учитель B")

    # ученик A (создан учителем A через обычный интерфейс)
    client.cookies.clear()
    assert client.post("/login", data={"username": "t-a", "password": "urok-6-simv"},
                       follow_redirects=False).status_code == 303
    csrf = re.search(r'name="csrf" content="([^"]+)"', client.get("/teacher/students").text).group(1)
    client.post("/teacher/students", data={"display_name": "Ученик A", "username": "ua-student", "csrf": csrf})
    client.cookies.clear()
    assert client.post("/login", data={"username": "t-b", "password": "urok-6-simv"},
                       follow_redirects=False).status_code == 303
    csrf_b = re.search(r'name="csrf" content="([^"]+)"', client.get("/teacher/students").text).group(1)
    client.post("/teacher/students", data={"display_name": "Ученик B", "username": "ub-student", "csrf": csrf_b})

    # самостоятельный ученик присоединяется к группе A по коду
    client.cookies.clear()
    pw_a = add_student(client, "Самостоятельный", "solo-join")
    client.cookies.clear()
    client.post("/login", data={"username": "solo-join", "password": pw_a}, follow_redirects=False)
    page = client.get("/account/join-teacher").text
    assert "Присоединиться к группе" in page
    csrf_solo = re.search(r'name="csrf" content="([^"]+)"', page).group(1)
    bad = client.post("/account/join-teacher", data={"code": "ZZZZ9999", "csrf": csrf_solo}).text
    assert "Код не найден" in bad
    ok = client.post("/account/join-teacher", data={"code": code_a.lower(), "csrf": csrf_solo}).text
    assert "вы в группе" in ok

    # изоляция: A видит своего и присоединившегося, но не ученика B; B — наоборот
    client.cookies.clear()
    client.post("/login", data={"username": "t-a", "password": "urok-6-simv"}, follow_redirects=False)
    # в списках-ссылках ростера (лидерборд страницы общий — проверяем именно карточки учеников)
    roster_a = client.get("/teacher/students").text
    assert "<b>Ученик A</b></a>" in roster_a and "<b>Самостоятельный</b></a>" in roster_a and "<b>Ученик B</b></a>" not in roster_a
    client.cookies.clear()
    client.post("/login", data={"username": "t-b", "password": "urok-6-simv"}, follow_redirects=False)
    roster_b = client.get("/teacher/students").text
    assert "<b>Ученик B</b></a>" in roster_b and "<b>Ученик A</b></a>" not in roster_b and "<b>Самостоятельный</b></a>" not in roster_b


def test_join_page_shows_teacher_link(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    assert "/signup-teacher" in client.get("/join").text
