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


# ---------------------------------------------------------------- неблокеры ревью PR #65

def test_meet_url_only_video_hosts():
    from app.teacher_lesson import meet_service, valid_meet_url
    ok = {"https://meet.google.com/abc-defg-hij": "Google Meet",
          "https://telemost.yandex.ru/j/12345678901234": "Яндекс Телемосте",
          "https://telemost.360.yandex.ru/j/12345678901234": "Яндекс Телемосте",
          "https://us02web.zoom.us/j/8123456789?pwd=abc": "Zoom", "https://zoom.us/j/8123456789": "Zoom",
          "https://teams.microsoft.com/l/meetup-join/19%3a": "Microsoft Teams",
          "https://teams.live.com/meet/9381234": "Microsoft Teams"}
    for url, name in ok.items():
        assert valid_meet_url(url) == url and meet_service(url) == name, url
    bad = ["http://meet.google.com/abc", "https://evil.example/meet.google.com", "https://meet.google.com.evil.ru/abc",
           "https://meet.google.com@evil.ru/abc", "https://user:pw@meet.google.com/abc", "https://meet.google.com:8443/abc",
           "https://meet.google.com", "https://meet.google.com/", "https://evilzoom.us/j/1", "https://a.b.c.zoom.us/j/1",
           "https://meet.google.com/abc def", "javascript:alert(1)", "", None, "https://meet.google.com/" + "a" * 300]
    for url in bad:
        assert valid_meet_url(url) is None and meet_service(url) is None, url


def test_meet_button_names_the_service(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    client, csrf, sid = _teacher_with_group(client)
    client.post("/teacher/lesson/meet", data={"url": "https://telemost.yandex.ru/j/1234567", "csrf": csrf})
    page = client.get("/teacher/lesson").text
    assert "Начать урок в Яндекс Телемосте" in page
    r = client.post("/teacher/lesson/meet", data={"url": "https://evil.example/j/1", "csrf": csrf}, follow_redirects=False)
    assert r.headers["location"].endswith("bad=1")
    assert "Начать урок в Яндекс Телемосте" in client.get("/teacher/lesson").text   # прежняя ссылка осталась
    assert "request.url.path.endswith" not in open("app/templates/teacher/lesson.html", encoding="utf-8").read()


def test_assign_is_idempotent_and_counted_per_exam(client, monkeypatch):
    from app import config, knowledge as kn
    from app import teacher_lesson as tl
    from app.db import connect
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    monkeypatch.setattr(config, "UMEDU2", True)
    client, csrf, sid = _teacher_with_group(client)
    conn = connect()
    with conn:
        conn.execute("INSERT INTO exam_enroll (student_id, exam_id, goal, exam_date, created_at) "
                     "VALUES (?, 'ege-math-profile-2026', 70, NULL, '2026-01-01T00:00:00')", (sid,))
        kn.record(conn, sid, "oge-math-2026", 20, 0.0)
        kn.record(conn, sid, "ege-math-profile-2026", 1, 0.0)
    for _ in range(3):                                                    # тройной клик — одно задание
        r = client.post("/teacher/lesson/assign", data={"sid": sid, "exam": "oge-math-2026", "n": 20, "csrf": csrf},
                        follow_redirects=False)
        assert r.status_code == 303
    count = lambda: connect().execute("SELECT COUNT(*) FROM teacher_task WHERE student_id = ?", (sid,)).fetchone()[0]
    assert count() == 1
    page = client.get("/teacher/lesson").text
    assert page.count("дома уже задано: 1") == 1                          # у профиля ЕГЭ домашки нет
    client.post("/teacher/lesson/assign", data={"sid": sid, "exam": "ege-math-profile-2026", "n": 1, "csrf": csrf})
    assert count() == 2 and client.get("/teacher/lesson").text.count("дома уже задано: 1") == 2
    # старые дубли на проде (до исправления) не ломают счётчик
    with conn:
        conn.execute("INSERT INTO teacher_task (teacher_id, student_id, exam_id, task_key, note, day) "
                     "SELECT teacher_id, student_id, exam_id, task_key, note, day FROM teacher_task WHERE task_key = 20")
    assert tl.open_count(conn, sid, "oge-math-2026") == 1
    # решено верно — в тот же день повтор всё равно дубль, на следующий день можно задать снова
    from datetime import timedelta
    with conn:
        kn.record(conn, sid, "oge-math-2026", 20, 1.0)
        assert tl.assign(conn, 1, sid, "oge-math-2026", 20) is False
    tomorrow = config.today() + timedelta(days=1)
    monkeypatch.setattr(config, "today", lambda: tomorrow)
    with conn:
        assert tl.assign(conn, 1, sid, "oge-math-2026", 20) is True
        assert tl.assign(conn, 1, sid, "oge-math-2026", 20) is False


def test_archived_and_guest_students_hidden_from_board(client, monkeypatch):
    from app import config
    from app.db import connect
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    client, csrf, sid = _teacher_with_group(client)
    assert client.get("/teacher/board/%d?exam=oge-math-2026&n=20&seed=1" % sid).status_code == 200
    for col in ("active = 0", "guest = 1"):
        conn = connect()
        with conn:
            conn.execute("UPDATE users SET active = 1, guest = 0 WHERE id = ?", (sid,))
            conn.execute("UPDATE users SET %s WHERE id = ?" % col, (sid,))
        assert client.get("/teacher/board/%d?exam=oge-math-2026&n=20&seed=1" % sid).status_code == 404, col
        r = client.post("/teacher/lesson/assign", data={"sid": sid, "exam": "oge-math-2026", "n": 20, "csrf": csrf},
                        follow_redirects=False)
        assert r.status_code == 404, col


def test_picker_timeout_text_matches_wait():
    src = open("app/static/js/models/picker.js", encoding="utf-8").read()
    assert "var WAIT_MS = 30000;" in src and "дольше 30 секунд" in src and "дольше минуты" not in src
