"""«К уроку»: Meet-ссылка, слабые номера, доска без утечки ответа, домашка у ученика (путь Гоши)."""
import re

from test_app import add_student, client, login_as  # noqa: F401

MEET = "https://meet.google.com/abc-defg-hij"


def _teacher_with_group(client):
    """Репетитор через открытую регистрацию + ученик в его группе; возвращает (csrf, sid, пароль ученика)."""
    from app import config
    from app.db import connect
    client.cookies.clear()
    r = client.post("/signup-teacher", data={"name": "Мария Петровна", "login": "qa-lesson-t",
                                             "password": "urok-6", "consent": "1", "website": ""},
                    follow_redirects=False)
    assert r.status_code == 303, r.text[:200]
    csrf = re.search(r'name="csrf" content="([^"]+)"', client.get("/teacher/students").text).group(1)
    client.post("/teacher/students", data={"display_name": "Гоша", "username": "gosha", "csrf": csrf})
    conn = connect()
    sid = conn.execute("SELECT id FROM users WHERE username = 'gosha'").fetchone()[0]
    # Гоша — девятиклассник на ОГЭ математике
    conn.execute("UPDATE users SET grade = 9 WHERE id = ?", (sid,))
    conn.execute("INSERT OR IGNORE INTO exam_enroll (student_id, exam_id, goal, exam_date, created_at) "
                 "VALUES (?, 'oge-math-2026', 4, NULL, '2026-01-01T00:00:00')", (sid,))
    conn.commit()
    return client, csrf, sid


def test_meet_link_saved_and_shown(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    client, csrf, sid = _teacher_with_group(client)
    page = client.get("/teacher/lesson").text
    assert "К уроку" in page and "Ссылка на Meet" in page
    client.post("/teacher/lesson/meet", data={"url": MEET, "csrf": csrf})
    page = client.get("/teacher/lesson").text
    assert 'href="%s"' % MEET in page and "Начать урок" in page
    # не-https ссылка отклоняется, прежняя остаётся
    r = client.post("/teacher/lesson/meet", data={"url": "ftp://nope", "csrf": csrf}, follow_redirects=False)
    assert r.status_code == 303
    assert 'href="%s"' % MEET in client.get("/teacher/lesson").text


def test_weak_spots_and_assign_flow(client, monkeypatch):
    from app import config, knowledge as kn
    from app.db import connect
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    monkeypatch.setattr(config, "UMEDU2", True)
    client, csrf, sid = _teacher_with_group(client)
    conn = connect()
    # две попытки: №20 слабо, №21 уверенно
    with conn:
        kn.record(conn, sid, "oge-math-2026", 20, 0.0)
        kn.record(conn, sid, "oge-math-2026", 20, 0.2)
        kn.record(conn, sid, "oge-math-2026", 21, 1.0)
    page = client.get("/teacher/lesson").text
    assert "№20" in page and "№21" not in page, "слабым должен быть только №20"
    # доска без ответа в HTML; с reveal — ответ есть
    board = client.get("/teacher/board/%d?exam=oge-math-2026&n=20&seed=777" % sid).text
    assert "вариант 777" in board
    v20 = __import__("app.u2_web", fromlist=["_variant"])._variant("oge-math-2026", 20, 777)
    assert '<section class="board-answer">' not in board and "Ответ:" not in board, \
        "блока ответа в закрытой доске не должно"
    revealed = client.get("/teacher/board/%d?exam=oge-math-2026&n=20&seed=777&reveal=1" % sid).text
    assert '<section class="board-answer">' in revealed and v20["answer"] in revealed
    # задать домой → у Гоши на «Сегодня»
    r_assign = client.post("/teacher/lesson/assign", data={"sid": sid, "exam": "oge-math-2026", "n": 20,
                                                           "note": "Разобрали вместе", "csrf": csrf},
                           follow_redirects=False)
    assert r_assign.status_code == 303, (r_assign.status_code, r_assign.text[:300])
    conn2 = connect()
    assert conn2.execute("SELECT COUNT(*) FROM teacher_task WHERE student_id = ?", (sid,)).fetchone()[0] == 1
    pw = re.search(r"<dt>Пароль</dt><dd>([^<]+)</dd>", client.get("/teacher/students").text)
    # войдём Гошей через смену пароля преподавателем — проще: логин через карточку уже показанную не сохранить, зададим пароль
    from app import auth as _auth
    with conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (_auth.hash_password("gosha-6"), sid))
    client.cookies.clear()
    assert client.post("/login", data={"username": "gosha", "password": "gosha-6"},
                       follow_redirects=False).status_code == 303
    today = client.get("/u2/today").text
    assert "От преподавателя" in today and "/u2/train/oge-math-2026/20" in today
    # Гоша решает верно — задание исчезает
    with conn:
        kn.record(conn, sid, "oge-math-2026", 20, 1.0)
    today = client.get("/u2/today").text
    assert "От преподавателя" not in today


def test_board_isolated_between_teachers(client, monkeypatch):
    from app import config
    from app.db import connect
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    client, csrf, sid = _teacher_with_group(client)
    # второй преподаватель — чужой ученик для доски и заданий
    client.cookies.clear()
    client.post("/signup-teacher", data={"name": "Другой", "login": "qa-lesson-t2", "password": "urok-6",
                                         "consent": "1", "website": ""}, follow_redirects=False)
    csrf2 = re.search(r'name="csrf" content="([^"]+)"', client.get("/teacher/students").text).group(1)
    assert client.get("/teacher/board/%d?exam=oge-math-2026&n=20&seed=1" % sid).status_code == 404
    r = client.post("/teacher/lesson/assign", data={"sid": sid, "exam": "oge-math-2026", "n": 20, "csrf": csrf2},
                    follow_redirects=False)
    assert r.status_code == 404
    # и на его «К уроку» нет ни секции Гоши, ни ссылки на его доску
    other = client.get("/teacher/lesson").text
    assert 'id="s%d"' % sid not in other and ("/teacher/board/%d" % sid) not in other
