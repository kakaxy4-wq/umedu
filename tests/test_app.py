import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "static" / "py"))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CQ_DATA_DIR", str(tmp_path))
    from app import config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "up")
    monkeypatch.setattr(config, "COOKIE_SECURE", False)
    from app import season
    monkeypatch.setattr(season, "DROP_CHANCE", 0)          # случайные старр-дропы ломали бы подсчёт трофеев в тестах
    from fastapi.testclient import TestClient
    import manage
    from app.db import connect, init_db
    from app.main import app
    from app import auth
    auth._failed.clear()
    init_db()
    conn = connect()
    manage.create_user(conn, "teacher", "teacher", "Папа", "secret123")
    manage.create_user(conn, "student", "student", "Миша", "secret123")
    conn.close()
    with TestClient(app) as c:
        yield c


def login(client, who):
    client.cookies.clear()
    r = client.post("/login", data={"username": who, "password": "secret123"}, follow_redirects=False)
    assert r.status_code == 303
    page = client.get("/" if who == "student" else "/teacher").text
    return re.search(r'name="csrf" content="([^"]+)"', page).group(1)


def sid_of(login="student"):
    from app.db import connect
    return connect().execute("SELECT id FROM users WHERE username = ?", (login,)).fetchone()[0]


def stats(login="student"):
    from app import game
    from app.db import connect
    return game.stats(connect(), sid_of(login))


# ------------------------------------------------------------------ контент
def test_all_task_solutions_pass_and_starters_fail():
    import cq_runtime
    from app.content.tasks import TASKS
    for t in TASKS:
        res = json.loads(cq_runtime.check(t["solution"], t["tests"]))
        assert res["passed"], (t["id"], res)
        assert not json.loads(cq_runtime.check(t["starter"], t["tests"]))["passed"], t["id"]


def test_content_consistency():
    from app.content.lessons import LESSONS, MODULES
    from app.content.quizzes import QUIZZES
    from app.content.tasks import TASKS
    assert [l["num"] for l in LESSONS] == list(range(1, 35))
    assert sorted(n for m in MODULES for n in m["lessons"]) == list(range(1, 35))
    assert len({t["id"] for t in TASKS}) == len(TASKS)
    assert all(q["answer"] for q in QUIZZES)
    for l in LESSONS:
        for key in ("title", "intro", "plan", "homework", "learn", "wow"):
            assert l[key], (l["num"], key)


def test_browser_examples_run_without_errors():
    """Примеры уроков, которые запускаются в браузере, не должны падать (input подставляем)."""
    import cq_runtime
    from app.content.lessons import LESSONS
    for l in LESSONS:
        for ex in l["examples"]:
            if ex.get("local"):
                continue
            feeds = ["Миша\n13\n" + "\n".join(str(i) for i in range(1, 101)),
                     "\n".join(str(i) for i in range(1, 101)),
                     "камень\n" * 5, "налево\n", "п\nи\nт\nо\nн\n"]
            errs = [cq_runtime._exec_captured(ex["code"], f)[2] for f in feeds]
            if "Найди и исправь" in ex["title"]:
                assert all(errs)
                continue
            assert any(e is None or e["type"] == "EOFError" for e in errs), (l["num"], ex["title"], errs[0])


def test_friendly_errors():
    import cq_runtime
    _, _, err = cq_runtime._exec_captured('print("a" + 1)', "")
    assert "текст и число" in err["hint"]
    _, _, err = cq_runtime._exec_captured("if True\n    pass", "")
    assert "двоеточие" in err["hint"]
    _, _, err = cq_runtime._exec_captured("x = int('abc')", "")
    assert "int()" in err["hint"]


# ------------------------------------------------------------------ доступ
def test_login_required_and_roles(client):
    assert client.get("/", follow_redirects=False).headers["location"] == "/login"
    assert client.post("/api/run").status_code == 401
    csrf = login(client, "student")
    assert client.get("/teacher").status_code == 403
    r = client.post("/teacher/xp", data={"amount": 500, "reason": "хак", "csrf": csrf})
    assert r.status_code == 403
    assert stats()["xp"] == 0


def test_bad_password_and_rate_limit(client):
    for _ in range(10):
        r = client.post("/login", data={"username": "student", "password": "nope"})
        assert "Неверный" in r.text
    r = client.post("/login", data={"username": "student", "password": "secret123"})
    assert "Слишком много" in r.text


def test_csrf_required(client):
    login(client, "student")
    assert client.post("/api/run").status_code == 403
    assert client.post("/api/run", headers={"X-CSRF-Token": "wrong"}).status_code == 403


def test_security_headers(client):
    r = client.get("/login")
    assert r.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert r.headers["Cross-Origin-Embedder-Policy"] == "require-corp"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]


# ------------------------------------------------------------------ игровая механика
def test_task_xp_once_and_achievements(client):
    csrf = login(client, "student")
    h = {"X-CSRF-Token": csrf}
    for _ in range(3):
        client.post("/api/task/hello/attempt", json={"code": "x", "passed": False}, headers=h)
    r = client.post("/api/task/hello/attempt", json={"code": 'print("Привет, мир!")', "passed": True}, headers=h).json()
    assert r["first"] and r["xp"] == 10 and "Привет" in r["solution"]
    r2 = client.post("/api/task/hello/attempt", json={"code": "", "passed": True}, headers=h).json()
    assert not r2["first"]
    s = stats()
    assert s["tasks_solved"] == 1 and s["bug_fixes"] == 1
    from app.db import connect
    from app import game
    have = game.unlocked_achievements(connect(), sid_of())
    assert "task_1" in have and "bug_hunter" in have
    assert s["xp"] == 10 + 10 + 15  # задача + «Первая победа» + «Победил баг»


def test_solution_hidden_until_solved(client):
    login(client, "student")
    page = client.get("/task/greet").text
    assert 'name + "!")' not in page.split('id="solution"')[1].split("</div>")[1]


def test_locked_lessons_for_student(client):
    csrf_s = login(client, "student")
    assert "ещё закрыт" in client.get("/lesson/5").text
    assert "ещё закрыт" in client.get("/task/caesar").text
    r = client.post("/lesson/5/submit", data={"code": "x", "csrf": csrf_s})
    assert r.status_code == 404
    csrf_t = login(client, "teacher")
    client.post("/teacher/lesson/5/open", data={"csrf": csrf_t})
    login(client, "student")
    assert "ещё закрыт" not in client.get("/lesson/5").text
    assert "Функции" in client.get("/lesson/5").text


def test_lesson_done_awards_once(client):
    csrf = login(client, "teacher")
    client.post("/teacher/lesson/1/done", data={"csrf": csrf})
    client.post("/teacher/lesson/1/done", data={"csrf": csrf})
    assert stats()["xp"] == 20
    assert client.post("/teacher/lesson/9/done", data={"csrf": csrf}).status_code == 400


def test_homework_flow(client):
    csrf = login(client, "student")
    r = client.post("/lesson/1/submit", data={"code": "print(1)", "comment": "готово", "star": "1", "csrf": csrf},
                    files={"upload": ("pic.png", b"\x89PNG....", "image/png")}, follow_redirects=False)
    assert r.status_code == 303
    r = client.post("/lesson/1/submit", data={"code": "x", "csrf": csrf},
                    files={"upload": ("evil.html", b"<script>", "text/html")})
    assert r.status_code == 400
    csrf_t = login(client, "teacher")
    assert "готово" in client.get("/teacher/reviews").text
    client.post("/teacher/review/1", data={"action": "approve", "xp": 10, "star_ok": "1", "comment": "Супер", "csrf": csrf_t})
    s = stats()
    assert s["hw_approved"] == 1 and s["hw_stars"] == 1
    assert s["xp"] == 15 + 10  # домашка с ⭐ + достижение «Первая домашка»
    assert client.get("/files/sub/1").status_code == 200
    client.cookies.clear()
    assert client.get("/files/sub/1", follow_redirects=False).status_code == 303


def test_shop_flow(client):
    csrf_t = login(client, "teacher")
    client.post("/teacher/xp", data={"amount": 500, "reason": "бонус", "csrf": csrf_t})
    assert stats()["coins"] == 0                               # трофеи — не гемы: подарки только за учёбу
    client.post("/teacher/lesson/5/open", data={"csrf": csrf_t})
    for n in range(1, 6):
        client.post("/teacher/lesson/%d/done" % n, data={"csrf": csrf_t})
    assert stats()["coins"] == 50                              # 5 занятий × 10 💎
    csrf = login(client, "student")
    assert "Как получить гемы" in client.get("/shop").text
    client.post("/shop/1/buy", data={"csrf": csrf})            # «Десерт на выбор» — 40 💎
    assert stats()["coins"] == 10
    client.post("/shop/1/buy", data={"csrf": csrf})            # не хватает
    assert stats()["coins"] == 10
    csrf_t = login(client, "teacher")
    client.post("/teacher/purchase/1", data={"action": "decline", "csrf": csrf_t})
    s = stats()
    assert s["coins"] == 50 and s["xp"] == 600


def test_daily_quiz(client):
    csrf = login(client, "student")
    from app import game
    from app.content.quizzes import QUIZ_BY_ID
    from app.db import connect
    d = game.get_daily(connect(), sid_of())
    assert d["kind"] == "quiz" and QUIZ_BY_ID[d["ref"]]["lesson"] <= 1
    answer = QUIZ_BY_ID[d["ref"]]["answer"]
    r = client.post("/api/daily/answer", json={"answer": "  " + answer + "\n"}, headers={"X-CSRF-Token": csrf}).json()
    assert r["correct"] and r["finished"]
    r = client.post("/api/daily/answer", json={"answer": answer}, headers={"X-CSRF-Token": csrf}).json()
    assert r["finished"]
    s = stats()
    assert s["streak"] == 1 and s["xp"] == 15 + 5  # задача дня + достижение


def test_streak_calc(client):
    from datetime import timedelta
    from app import config, game
    from app.db import connect
    conn = connect()
    today = config.today()
    with conn:
        for i in range(1, 8):
            conn.execute("INSERT INTO daily (student_id, day, kind, ref, finished_at, solved) "
                         "VALUES (?, ?, 'quiz', 'q1', 'x', 1)", (sid_of(), (today - timedelta(days=i)).isoformat()))
    assert game.streaks(conn, sid_of()) == (7, 7)
    with conn:
        conn.execute("DELETE FROM daily WHERE day = ?", ((today - timedelta(days=1)).isoformat(),))
    assert game.streaks(conn, sid_of()) == (0, 6)


def test_trainer_daily_cap(client):
    csrf = login(client, "student")
    h = {"X-CSRF-Token": csrf}
    total = 0
    for _ in range(3):
        total += client.post("/api/trainer", json={"mode": "table", "correct": 40, "wrong": 1}, headers=h).json()["xp"]
    assert total == 30
    r = client.post("/api/trainer", json={"mode": "nope", "correct": 1, "wrong": 0}, headers=h)
    assert r.status_code == 400
    r = client.post("/api/trainer", json={"mode": "bin", "correct": 99999, "wrong": 0}, headers=h).json()
    assert r["best"] == 150


def test_portfolio_public_and_private(client):
    csrf = login(client, "student")
    client.post("/portfolio/save", data={"title": "Секрет", "code": "print(1)", "csrf": csrf})
    client.post("/portfolio/save", data={"title": "Открытка", "code": "print(2)", "public": "1", "csrf": csrf},
                files={"image": ("a.png", b"\x89PNG", "image/png")})
    from app.db import connect
    rows = {r["title"]: dict(r) for r in connect().execute("SELECT * FROM projects")}
    client.cookies.clear()
    assert client.get("/p/%s" % rows["Секрет"]["slug"]).status_code == 404
    page = client.get("/p/%s" % rows["Открытка"]["slug"])
    assert page.status_code == 200 and "print(2)" in page.text
    assert client.get("/files/project/%d/image" % rows["Открытка"]["id"]).status_code == 200
    assert client.get("/files/project/%d/image" % rows["Секрет"]["id"]).status_code == 404
    assert "Открытка" in client.get("/gallery").text and "Секрет" not in client.get("/gallery").text


def test_all_pages_render(client):
    login(client, "teacher")
    from app.content.tasks import TASKS
    for path in ["/teacher", "/teacher/lessons", "/teacher/reviews", "/teacher/rewards", "/teacher/solutions",
                 "/teacher/journal", "/teacher/attempts/hello", "/teacher/students", "/teacher/students?archived=1",
                 "/teacher/student/%d" % sid_of(), "/teacher/checks", "/certificates", "/checks", "/oge", "/ru", "/ru/rules", "/map", "/daily", "/trainer", "/playground",
                 "/achievements", "/shop", "/cheatsheet", "/portfolio", "/portfolio/new", "/gallery"] + \
            ["/lesson/%d" % n for n in range(1, 35)] + ["/task/%s" % t["id"] for t in TASKS]:
        r = client.get(path)
        assert r.status_code == 200, path
    login(client, "student")
    for path in ["/", "/map", "/daily", "/trainer", "/playground", "/achievements", "/shop", "/cheatsheet",
                 "/portfolio", "/lesson/1", "/task/hello", "/playground?starter=guess"]:
        assert client.get(path).status_code == 200, path


def test_level_up_notice(client):
    csrf_t = login(client, "teacher")
    client.post("/teacher/xp", data={"amount": 460, "reason": "тест", "csrf": csrf_t})
    from app.db import connect
    texts = [r["text"] for r in connect().execute("SELECT text FROM notices")]
    assert any("Новый ранг: «Серебро»" in t for t in texts), texts
    assert any("Открыт боец Python" in t and "Цикломёт" in t for t in texts), texts


# ------------------------------------------------------------------ проверки
def test_checks_content_is_consistent():
    from app.content.checks import CHECKS, CHECK_BY_ID
    ids = [q["id"] for c in CHECKS for q in c["questions"]]
    assert len(ids) == len(set(ids))
    for c in CHECKS:
        for q in c["questions"]:
            assert q["answer"] != "", q["id"]
            if q["kind"] == "choice":
                assert q["answer"] in q["options"] and len(set(q["options"])) == len(q["options"]), q["id"]
    # итоговый — те же вопросы, что входной, иначе сравнение «было → стало» бессмысленно
    entry, final = CHECK_BY_ID["entry"], CHECK_BY_ID["final"]
    assert [(q["topic"], q["text"], q["code"]) for q in entry["questions"]] == \
           [(q["topic"], q["text"], q["code"]) for q in final["questions"]]


def test_check_flow(client):
    from app.content.checks import CHECK_BY_ID
    entry = CHECK_BY_ID["entry"]
    csrf = login(client, "student")
    assert "Входное тестирование" in client.get("/").text          # баннер на главной
    assert "ещё не открыли" in client.get("/check/w1").text         # срез закрыт
    assert client.post("/check/w1/submit", data={"csrf": csrf}).status_code == 400

    page = client.get("/check/entry").text
    assert "Пропустить часть" in page and "Сдать проверку" in page
    data = {"csrf": csrf}
    for q in entry["questions"]:
        if q["skippable"]:
            data["s_" + q["id"]] = "1"                               # Python-часть пропущена
        else:
            data["a_" + q["id"]] = " " + q["answer"].upper() + " "     # регистр и пробелы не важны
    wrong = entry["questions"][0]
    data["a_" + wrong["id"]] = "100500"
    xp_before = stats()["xp"]
    r = client.post("/check/entry/submit", data=data, follow_redirects=False)
    assert r.status_code == 303
    python_part = [q for q in entry["questions"] if q["skippable"]]
    page = client.get("/check/entry").text
    assert "%d <small>из %d" % (len(entry["questions"]) - len(python_part) - 1, len(entry["questions"])) in page
    assert stats()["xp"] == xp_before + 30
    # повторная отправка ничего не меняет
    client.post("/check/entry/submit", data=data)
    assert stats()["xp"] == xp_before + 30

    tcsrf = login(client, "teacher")
    assert "✅" in client.get("/check/final").text                   # предпросмотр с ответами
    client.post("/teacher/check/final/open", data={"csrf": tcsrf})
    client.post("/teacher/check/entry/reset", data={"csrf": tcsrf})

    csrf = login(client, "student")
    data["csrf"] = csrf
    client.post("/check/entry/submit", data=data)
    assert stats()["xp"] == xp_before + 30                           # за пересдачу трофеи не дают
    final = {"csrf": csrf}
    for q in CHECK_BY_ID["final"]["questions"]:
        final["a_" + q["id"]] = q["answer"]
    client.post("/check/final/submit", data=final)
    page = client.get("/check/final").text
    assert "В начале года было" in page and "рост на" in page


# ------------------------------------------------------------------ сертификаты
def test_certificates(client):
    from app import game
    from app.db import connect
    login(client, "student")
    assert "Пока сертификатов нет" in client.get("/certificates").text
    assert client.get("/certificate/rank/2").status_code == 404

    tcsrf = login(client, "teacher")
    for n in range(1, 7):                                            # мир 1 — уроки 1–6
        client.post("/teacher/lesson/%d/open" % n, data={"csrf": tcsrf})
        client.post("/teacher/lesson/%d/done" % n, data={"csrf": tcsrf})
    conn = connect()
    with conn:
        game.award(conn, sid_of(), 300, "тест", "manual")                       # плюс бонусы за достижения — не меньше Серебра
    client.post("/teacher/certificates", data={"csrf": tcsrf, "emoji": "🏅", "title": "Лучшая игра",
                                               "reason": "за самую весёлую игру", "issued_at": "2026-05-20"})
    client.post("/teacher/cert-name", data={"csrf": tcsrf, "name": "Михаил Петров", "signer": "П. Петров"})

    login(client, "student")
    page = client.get("/certificates").text
    for title in ("Мир 1 пройден", "Ранг «Бронза II»", "Ранг «Серебро»", "Лучшая игра"):
        assert title in page, title
    assert "Ранг «Гуру Python»" not in page
    cert = client.get("/certificate/world/1").text
    assert "Михаил Петров" in cert and "П. Петров" in cert and "Первые шаги и черепашка" in cert
    custom = client.get("/certificate/custom/1").text
    assert "Грамота" in custom and "20 мая 2026" in custom


# ------------------------------------------------------------------ сокращения
def test_abbr_markup():
    from app.content.glossary import add_abbr
    html = add_abbr("Данные в JSON, ещё раз JSON. <code>JSON</code> <svg><text>JSON</text></svg>")
    assert html.count("<abbr") == 1 and "<code>JSON</code>" in html and "<text>JSON</text>" in html


# ------------------------------------------------------------------ подготовка к уроку
def test_lesson_guide(client):
    from app.content.guides import CARDS, has_guide
    assert has_guide(1) and CARDS[1]
    login(client, "student")
    assert client.get("/teacher/guide/1").status_code == 403
    login(client, "teacher")
    page = client.get("/teacher/guide/1").text
    assert "Подготовка к уроку 1" in page and "<svg" in page and "шахматной доске" in page
    assert "/teacher/guide/1" in client.get("/lesson/1").text
    cards = client.get("/teacher/guide/1/cards").text
    assert cards.count('class="fcard"') == len(CARDS[1])
    assert "План по шагам" in page and "Занятие проведено" in page
    assert "Словарик сокращений" in page and "Малая электронная счётная машина" in page
    assert "<abbr" not in page.split("<svg")[1].split("</svg>")[0]      # в рисунки подсказки не вставляем
    for num in range(1, 35):                                          # 1–9 полные, 10–34 черновики
        page = client.get("/teacher/guide/%d" % num)
        assert page.status_code == 200, num
        assert ("Черновик." in page.text) == (num > 9), num
        assert "Рассказ и вау-момент" not in page.text and "Связь с экзаменом" not in page.text
    for num in range(1, 10):
        assert client.get("/teacher/guide/%d/cards" % num).text.count('class="fcard"') == len(CARDS[num])
    assert client.get("/teacher/guide/10/cards").status_code == 404          # карточек-заглушек нет


# ------------------------------------------------------------------ несколько учеников
def add_student(client, name, login):
    """Создаёт ученика через интерфейс преподавателя и возвращает пароль с карточки доступа."""
    csrf = login_as(client, "teacher")
    r = client.post("/teacher/students", data={"display_name": name, "username": login, "csrf": csrf})
    assert r.status_code == 200 and "Карточка доступа" in r.text, r.text[:300]
    return re.search(r"<dt>Пароль</dt><dd>([^<]+)</dd>", r.text).group(1)


def login_as(client, who, password="secret123"):
    client.cookies.clear()
    r = client.post("/login", data={"username": who, "password": password}, follow_redirects=False)
    assert r.status_code == 303, who
    page = client.get("/" if who != "teacher" else "/teacher/students").text
    return re.search(r'name="csrf" (?:content|value)="([^"]+)"', page).group(1)


def test_teacher_creates_student_with_access_card(client):
    password = add_student(client, "Аня", "anya")
    assert re.fullmatch(r"[a-z]+-[a-z]+-\d\d", password)                   # запоминается: «kot-luna-27»
    from app.db import connect
    row = connect().execute("SELECT password_hash FROM users WHERE username = 'anya'").fetchone()
    assert password not in row[0]                                         # хранится только хеш
    csrf = login_as(client, "anya", password)
    page = client.get("/").text
    assert "Привет, Аня" in page and "Входное тестирование" in page    # урок 1 и входной тест открыты
    assert "ещё закрыт" in client.get("/lesson/2").text
    # логин по-русски превращается в латиницу, занятый — с цифрой
    csrf_t = login_as(client, "teacher")
    r = client.post("/teacher/students", data={"display_name": "Аня", "csrf": csrf_t})
    assert "<dd>anya2</dd>" in r.text
    r = client.post("/teacher/students", data={"display_name": "X", "username": "anya", "csrf": csrf_t})
    assert r.status_code == 400


def test_students_are_isolated(client):
    """Главное правило: ученик видит и меняет только своё."""
    pw = add_student(client, "Аня", "anya")
    a = login_as(client, "anya", pw)
    h = {"X-CSRF-Token": a}
    client.post("/api/task/hello/attempt", json={"code": "print(1)", "passed": True}, headers=h)
    client.post("/api/run", headers=h)
    client.post("/api/snippets", json={"title": "Анин код", "code": "print('a')"}, headers=h)
    client.post("/portfolio/save", data={"title": "Анин проект", "code": "x", "csrf": a},
                files={"image": ("a.png", b"\x89PNG", "image/png")})
    client.post("/lesson/1/submit", data={"code": "print(1)", "csrf": a},
                files={"upload": ("hw.txt", b"anya", "text/plain")})
    from app.db import connect
    conn = connect()
    anya_snip = conn.execute("SELECT id FROM snippets WHERE title = 'Анин код'").fetchone()[0]
    anya_proj = conn.execute("SELECT id FROM projects WHERE title = 'Анин проект'").fetchone()[0]
    anya_sub = conn.execute("SELECT id FROM submissions").fetchone()[0]
    assert stats("anya")["xp"] > 0 and stats("anya")["tasks_solved"] == 1

    m = login_as(client, "student")
    assert stats("student")["xp"] == 0 and stats("student")["tasks_solved"] == 0
    for path in ["/playground", "/portfolio", "/lesson/1", "/achievements"]:
        assert "Анин" not in client.get(path).text, path
    assert "Анин код" not in client.get("/playground?s=%d" % anya_snip).text
    assert client.get("/portfolio/%d/edit" % anya_proj).status_code == 404
    assert client.get("/files/sub/%d" % anya_sub).status_code == 404
    assert client.get("/files/project/%d/image" % anya_proj).status_code == 404
    client.post("/snippets/%d/delete" % anya_snip, data={"csrf": m})
    client.post("/portfolio/%d/delete" % anya_proj, data={"csrf": m})
    client.post("/portfolio/save", data={"pid": anya_proj, "title": "взлом", "csrf": m})
    assert conn.execute("SELECT COUNT(*) FROM snippets WHERE id = ?", (anya_snip,)).fetchone()[0] == 1
    assert conn.execute("SELECT title FROM projects WHERE id = ?", (anya_proj,)).fetchone()[0] == "Анин проект"
    # ученик не может подставить чужой student_id в действия преподавателя
    assert client.post("/teacher/xp", data={"amount": 100, "reason": "x", "student_id": sid_of("anya"),
                                            "csrf": m}).status_code == 403
    # трофеи, уведомления и задача дня у каждого свои
    assert not any("Анин" in n["text"] for n in conn.execute("SELECT text FROM notices WHERE student_id = ?",
                                                                (sid_of(),)).fetchall())

    t = login_as(client, "teacher")
    client.post("/teacher/review/%d" % anya_sub, data={"action": "approve", "xp": 10, "csrf": t})
    assert stats("anya")["hw_approved"] == 1 and stats("student")["hw_approved"] == 0
    assert "Аня" in client.get("/teacher/reviews").text


def test_teacher_actions_target_the_right_student(client):
    pw = add_student(client, "Аня", "anya")
    t = login_as(client, "teacher")
    anya, misha = sid_of("anya"), sid_of("student")
    client.post("/teacher/lesson/1/done", data={"student_id": anya, "csrf": t})
    client.post("/teacher/lesson/2/open", data={"student_id": anya, "csrf": t})
    client.post("/teacher/xp", data={"amount": 7, "reason": "молодец", "student_id": misha, "csrf": t})
    client.post("/teacher/check/w1/open", data={"student_id": anya, "csrf": t})
    assert stats("anya")["xp"] == 20 and stats("anya")["lessons_done"] == 1
    assert stats("student")["xp"] == 7 and stats("student")["lessons_done"] == 0
    login_as(client, "student")
    assert "ещё закрыт" in client.get("/lesson/2").text
    assert "ещё не открыли" in client.get("/check/w1").text
    login_as(client, "anya", pw)
    assert "ещё закрыт" not in client.get("/lesson/2").text
    # «Проведено» по ошибке можно отменить — +20 списываются
    t = login_as(client, "teacher")
    client.post("/teacher/lesson/1/undone", data={"student_id": anya, "csrf": t})
    assert stats("anya")["xp"] == 0 and stats("anya")["lessons_done"] == 0
    # переключатель ученика: кабинет и журнал показывают выбранного
    client.post("/teacher/select", data={"student_id": misha, "next": "/teacher/journal", "csrf": t})
    assert "молодец" in client.get("/teacher/journal").text
    client.post("/teacher/select", data={"student_id": anya, "next": "//evil.example", "csrf": t},
                follow_redirects=False)
    assert "молодец" not in client.get("/teacher/journal").text


def test_archive_and_password_reset(client):
    pw = add_student(client, "Аня", "anya")
    login_as(client, "anya", pw)
    t = login_as(client, "teacher")
    anya = sid_of("anya")
    r = client.post("/teacher/student/%d/password" % anya, data={"csrf": t})
    new_pw = re.search(r"<dt>Пароль</dt><dd>([^<]+)</dd>", r.text).group(1)
    assert new_pw != pw
    client.cookies.clear()
    assert "Неверный" in client.post("/login", data={"username": "anya", "password": pw}).text
    login_as(client, "anya", new_pw)
    t = login_as(client, "teacher")
    client.post("/teacher/student/%d/archive" % anya, data={"active": 0, "csrf": t})
    assert "Аня" not in client.get("/teacher/students").text.split("<h2>")[1]
    client.cookies.clear()
    assert "в архиве" in client.post("/login", data={"username": "anya", "password": new_pw}).text
    t = login_as(client, "teacher")
    client.post("/teacher/student/%d/archive" % anya, data={"active": 1, "csrf": t})
    login_as(client, "anya", new_pw)


def test_parent_link(client):
    t = login_as(client, "teacher")
    misha = sid_of("student")
    client.post("/teacher/lesson/1/done", data={"student_id": misha, "csrf": t})
    client.post("/teacher/student/%d/parent-link" % misha, data={"action": "new", "csrf": t})
    from app.db import connect
    token = connect().execute("SELECT parent_token FROM users WHERE id = ?", (misha,)).fetchone()[0]
    client.cookies.clear()
    r = client.get("/parent/%s" % token)
    assert r.status_code == 200 and "Миша" in r.text and "Привет, Python" in r.text
    assert "Прогноз ОГЭ" in r.text and "Занимался на сайте за 2 недели" in r.text
    assert r.headers["Cache-Control"] == "no-store" and "noindex" in r.headers["X-Robots-Tag"]
    assert "csrf" not in r.text                                          # без входа — никаких форм
    assert client.get("/parent/%s/certificate/rank/2" % token).status_code == 404
    assert client.get("/parent/wrong-token-wrong-token-xx").status_code == 404
    t = login_as(client, "teacher")
    client.post("/teacher/student/%d/parent-link" % misha, data={"action": "new", "csrf": t})
    client.cookies.clear()
    assert client.get("/parent/%s" % token).status_code == 404           # старая ссылка больше не работает


def test_weekly_leaderboard(client):
    pw = add_student(client, "Аня", "anya")
    t = login_as(client, "teacher")
    client.post("/teacher/xp", data={"amount": 50, "reason": "a", "student_id": sid_of("anya"), "csrf": t})
    client.post("/teacher/xp", data={"amount": 30, "reason": "m", "student_id": sid_of("student"), "csrf": t})
    from app import students
    from app.db import connect
    board = students.leaderboard(connect())
    assert [r["name"] for r in board] == ["Аня", "Миша"] and board[0]["place"] == 1
    login_as(client, "student")
    page = client.get("/").text
    assert "Рейтинг недели" in page and "Аня" in page
    t = login_as(client, "teacher")
    client.post("/teacher/leaderboard", data={"csrf": t})                # выключить
    login_as(client, "student")
    assert "Рейтинг недели" not in client.get("/").text


def test_alerts_for_teacher(client):
    from app.db import connect
    conn = connect()
    with conn:
        for _ in range(5):
            conn.execute("INSERT INTO task_attempts (student_id, task_id, code, passed, created_at) "
                         "VALUES (?, 'pizza', 'x', 0, datetime('now'))", (sid_of(),))
    login_as(client, "teacher")
    page = client.get("/teacher").text
    assert "Кому нужна помощь" in page and "задача «Сколько заказать пиццы?»: 5 неудачных попыток" in page


def test_migration_from_single_student_db(tmp_path, monkeypatch):
    """Рабочая база v1 (один ученик, общие таблицы) переезжает в v2 без потерь."""
    import sqlite3
    from app import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "old.db")
    old = sqlite3.connect(tmp_path / "old.db")
    old.executescript(V1_SCHEMA)
    old.executescript("""
        INSERT INTO users (id, username, password_hash, role, display_name) VALUES (1, 't', 'x', 'teacher', 'Саша');
        INSERT INTO users (id, username, password_hash, role, display_name) VALUES (2, 'vg', 'x', 'student', 'Ученик');
        INSERT INTO settings VALUES ('unlocked', '3'), ('student_name', 'Аня'), ('cert_name', 'Анна С.'),
                                    ('next_lesson_at', '2026-10-10T18:00');
        INSERT INTO lesson_state (num, opened_at, done_at) VALUES (1, 'a', 'b'), (2, 'a', NULL);
        INSERT INTO xp_events (amount, reason, kind, created_at) VALUES (20, 'урок', 'lesson', '2026-10-01');
        INSERT INTO achievements VALUES ('first_run', 'x');
        INSERT INTO counters VALUES ('runs', 4);
        INSERT INTO check_state (id, opened_at) VALUES ('entry', 'x');
        INSERT INTO snippets (title, code, updated_at) VALUES ('s', 'c', 'u');
        INSERT INTO rewards (emoji, title, cost) VALUES ('🎁', 'приз', 10);
        INSERT INTO purchases (reward_id, title, cost, created_at) VALUES (1, 'приз', 10, 'x');
    """)
    old.commit()
    old.close()
    from app import game
    from app.db import connect, init_db
    init_db()
    init_db()                                                            # повторный запуск ничего не ломает
    conn = connect()
    st = conn.execute("SELECT * FROM users WHERE id = 2").fetchone()
    assert st["display_name"] == "Аня" and st["full_name"] == "Анна С." and st["unlocked"] == 3
    assert st["next_lesson_at"] == "2026-10-10T18:00"
    s = game.stats(conn, 2)
    assert s["xp"] == 20 and s["lessons_done"] == 1 and s["runs"] == 4 and s["snippets"] == 1 and s["coins"] == 0
    assert conn.execute("SELECT COUNT(*) FROM check_state WHERE student_id = 2 AND id = 'entry'").fetchone()[0] == 1
    assert "student_id" in [r[1] for r in conn.execute("PRAGMA table_info(xp_events)")]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("SELECT value FROM settings WHERE key = 'unlocked'").fetchone() is None


# схема v1 — как была в рабочей базе до перехода на нескольких учеников
V1_SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'teacher')), display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE lesson_state (num INTEGER PRIMARY KEY, opened_at TEXT, done_at TEXT, teacher_note TEXT NOT NULL DEFAULT '');
CREATE TABLE xp_events (id INTEGER PRIMARY KEY, amount INTEGER NOT NULL, reason TEXT NOT NULL, kind TEXT NOT NULL,
    ref TEXT, created_at TEXT NOT NULL);
CREATE TABLE task_attempts (id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, code TEXT NOT NULL, passed INTEGER NOT NULL,
    created_at TEXT NOT NULL);
CREATE INDEX idx_attempts_task ON task_attempts(task_id);
CREATE TABLE submissions (id INTEGER PRIMARY KEY, lesson INTEGER NOT NULL, code TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT '', file_name TEXT, file_path TEXT, star INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending', teacher_comment TEXT NOT NULL DEFAULT '', xp_awarded INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, reviewed_at TEXT);
CREATE TABLE achievements (code TEXT PRIMARY KEY, unlocked_at TEXT NOT NULL);
CREATE TABLE notices (id INTEGER PRIMARY KEY, emoji TEXT NOT NULL, text TEXT NOT NULL, big INTEGER NOT NULL DEFAULT 0,
    seen INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE rewards (id INTEGER PRIMARY KEY, emoji TEXT NOT NULL, title TEXT NOT NULL, cost INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE purchases (id INTEGER PRIMARY KEY, reward_id INTEGER NOT NULL REFERENCES rewards(id), title TEXT NOT NULL,
    cost INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'requested', created_at TEXT NOT NULL, resolved_at TEXT);
CREATE TABLE projects (id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '', code TEXT NOT NULL DEFAULT '', image_path TEXT, file_name TEXT, file_path TEXT,
    public INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE snippets (id INTEGER PRIMARY KEY, title TEXT NOT NULL, code TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE daily (day TEXT PRIMARY KEY, kind TEXT NOT NULL, ref TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    solved INTEGER NOT NULL DEFAULT 0, finished_at TEXT);
CREATE TABLE trainer_runs (id INTEGER PRIMARY KEY, mode TEXT NOT NULL, correct INTEGER NOT NULL, wrong INTEGER NOT NULL,
    xp INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE counters (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
CREATE TABLE check_state (id TEXT PRIMARY KEY, opened_at TEXT, started_at TEXT);
CREATE TABLE check_results (check_id TEXT PRIMARY KEY, answers TEXT NOT NULL, right_count INTEGER NOT NULL,
    total INTEGER NOT NULL, skipped INTEGER NOT NULL, started_at TEXT, finished_at TEXT NOT NULL);
CREATE TABLE certificates (id INTEGER PRIMARY KEY, emoji TEXT NOT NULL, title TEXT NOT NULL, reason TEXT NOT NULL,
    issued_at TEXT NOT NULL);
"""


# ------------------------------------------------------------------ ОГЭ
def test_oge_tasks_and_trial(client):
    from app.content.checks import CHECK_BY_ID
    from app.content.oge import OGE_NUMBERS, OGE_TASKS
    from app.content.tasks import TASK_BY_ID
    assert sorted(OGE_NUMBERS) == list(range(1, 17))
    assert all(TASK_BY_ID[t["id"]]["oge"] in OGE_NUMBERS for t in OGE_TASKS)
    trial = CHECK_BY_ID["oge1"]
    assert trial["minutes"] == 30 and all(q["topic"].startswith("№") for q in trial["questions"])

    t = login_as(client, "teacher")
    client.post("/teacher/lesson/7/open", data={"student_id": sid_of(), "csrf": t})
    client.post("/teacher/check/oge1/open", data={"student_id": sid_of(), "csrf": t})
    s = login_as(client, "student")
    page = client.get("/lesson/7").text
    assert "ОГЭ №3" in page and "ОГЭ №6" in page
    assert "как на ОГЭ №6" in client.get("/task/oge6_runs").text
    oge = client.get("/oge").text
    assert "Анализ программы с условием" in oge and "🔒" in oge          # задачи из уроков 13–15 ещё закрыты
    form = client.get("/check/oge1").text
    assert 'class="check-timer"' in form
    data = {"csrf": s}
    for q in trial["questions"]:
        data["a_" + q["id"]] = q["answer"]
    data["a_" + trial["questions"][-1]["id"]] = "0"                    # №10 — одна ошибка
    client.post("/check/oge1/submit", data=data)
    oge = client.get("/oge").text
    assert "в пробнике 1/2" in oge and "в пробнике 2/2" in oge
    login_as(client, "teacher")
    assert "Пробник ОГЭ" in client.get("/teacher/checks").text and client.get("/oge").status_code == 200



# ------------------------------------------------------------------ удобство на телефоне
def test_numeric_answers_get_onscreen_keypad(client):
    from app.content.checks import CHECK_BY_ID, grade
    entry = CHECK_BY_ID["entry"]
    numeric = [q for q in entry["questions"] if q["numeric"]]
    assert numeric and all(q["kind"] != "choice" for q in numeric)
    assert not CHECK_BY_ID["oge1"]["questions"][1]["numeric"]          # «ББВАГА» — обычное поле
    login(client, "student")
    page = client.get("/check/entry").text
    assert page.count('class="numpad"') == len(numeric) and 'inputmode="none"' in page
    assert "Ответы сохраняются на этом устройстве" in page
    q = next(q for q in CHECK_BY_ID["w1"]["questions"] if q["answer"] == "3.5")
    assert grade(CHECK_BY_ID["w1"], {q["id"]: "3,5"})["items"][[i["q"]["id"] for i in grade(CHECK_BY_ID["w1"], {})["items"]].index(q["id"])]["ok"]


# ------------------------------------------------------------------ русский язык
def test_russian_content_is_consistent():
    from app.content import ru
    from app.content.checks import CHECK_BY_ID
    assert len(ru.COMMA_ITEMS) >= 30 and len(ru.SPELL_ITEMS) >= 50
    assert all(i["rule"] in ru.RULES for i in ru.ITEMS.values())
    assert all(i["answer"] in i["options"] and "_" in i["text"] or i["text"].startswith("(не)") for i in ru.SPELL_ITEMS)
    assert all("_" not in ru.spelled(i) and "(" not in ru.spelled(i) for i in ru.SPELL_ITEMS)
    assert any(not i["gaps"] for i in ru.COMMA_ITEMS)                    # есть «ловушки» без запятых
    assert CHECK_BY_ID["ru_entry"]["subject"] == "russian"
    assert len(ru.ITEMS) == len(ru.COMMA_ITEMS) + len(ru.SPELL_ITEMS) + len(ru.BASIS_ITEMS)   # id не повторяются
    assert sorted(r for _, ids in ru.SECTIONS for r in ids) == sorted(ru.RULES)            # каждое правило в разделе
    assert all(any(i["rule"] == r for i in ru.ITEMS.values()) for r in ru.RULES)          # и у каждого есть задания
    for b in ru.BASIS_ITEMS:
        assert (b["s"] or b["p"]) and not set(b["s"]) & set(b["p"]), b["id"]
        assert not any(w[0] in "*=" for w in b["words"]), b["id"]
        assert ru.check_basis(b, {"s": b["s"], "p": b["p"]})[0] and not ru.check_basis(b, {"s": b["p"], "p": b["s"]})[0]


def test_russian_trainer_flow(client):
    from app.content import ru
    from app.db import connect
    sid = sid_of()
    login(client, "student")
    assert client.get("/ru").status_code == 404                           # не подключён
    assert "ru_entry" not in client.get("/checks").text
    t = login_as(client, "teacher")
    assert "/teacher/student/%d/subjects" % sid in client.get("/teacher").text     # переключатель прямо на пульте
    r = client.post("/teacher/student/%d/subjects" % sid, data={"python": "1", "russian": "1", "csrf": t,
                                                               "next": "/teacher"}, follow_redirects=False)
    assert r.headers["location"] == "/teacher"
    # преподаватель может попробовать — в статистику не пишется
    r = client.post("/api/ru/answer", json={"id": "c01", "answer": [2], "mode": "comma"}, headers={"X-CSRF-Token": t}).json()
    assert r["ok"] and r["xp"] == 0
    assert connect().execute("SELECT COUNT(*) FROM ru_attempts").fetchone()[0] == 0

    s = login_as(client, "student")
    h = {"X-CSRF-Token": s}
    home = client.get("/").text
    assert "Русский язык" in home and "/ru/commas" in home
    assert "Русский: входной срез" in client.get("/checks").text
    for path in ("/ru", "/ru/commas", "/ru/spell", "/ru/review", "/ru/rules"):
        assert client.get(path).status_code == 200, path
    item = client.get("/api/ru/next?kind=comma").json()["item"]
    assert "gaps" not in item and item["kind"] == "comma"                 # ответ не уходит в браузер
    # верно: +2 трофея; лишняя запятая — ошибка и повторение завтра
    r = client.post("/api/ru/answer", json={"id": "c01", "answer": [2], "mode": "comma"}, headers=h).json()
    assert r["ok"] and r["xp"] == 2
    r = client.post("/api/ru/answer", json={"id": "c05", "answer": [1], "mode": "comma"}, headers=h).json()
    assert not r["ok"] and r["extra"] == [1] and r["review"] == "added"
    r = client.post("/api/ru/answer", json={"id": "s01", "answer": "н", "mode": "arena"}, headers=h).json()
    assert not r["ok"] and r["text"] == "деревянный стол"
    conn = connect()
    assert conn.execute("SELECT COUNT(*) FROM ru_review WHERE student_id = ?", (sid,)).fetchone()[0] == 2
    # «завтра» наступило: повторение по интервалам 1 → 3 → 7 → 14, потом карточка уходит
    with conn:
        conn.execute("UPDATE ru_review SET due = '2000-01-01'")
    assert client.get("/api/ru/next?kind=review").json()["left"] == 2
    for step in ("next:3", "next:7", "next:14", "mastered"):
        r = client.post("/api/ru/answer", json={"id": "c05", "answer": [], "mode": "review"}, headers=h).json()
        assert r["ok"] and r["review"] == step, (step, r)
        with conn:
            conn.execute("UPDATE ru_review SET due = '2000-01-01' WHERE item_id = 'c05'")
    assert conn.execute("SELECT COUNT(*) FROM ru_review WHERE item_id = 'c05'").fetchone()[0] == 0
    batch = client.get("/api/ru/batch").json()["items"]
    assert batch[0]["id"] == "s01" and len({i["id"] for i in batch}) == len(batch)   # повторение — первым
    # дневной потолок трофеев
    for _ in range(40):
        client.post("/api/ru/answer", json={"id": "s02", "answer": "н", "mode": "arena"}, headers=h)
    from app import russian
    assert russian._earned_today(conn, sid) == russian.DAILY_XP_CAP


def test_russian_basis_practice_and_teacher_view(client):
    from app.db import connect
    sid = sid_of()
    t = login_as(client, "teacher")
    client.post("/teacher/student/%d/subjects" % sid, data={"python": "1", "russian": "1", "csrf": t})
    s = login_as(client, "student")
    h = {"X-CSRF-Token": s}
    for path in ("/ru/basis", "/ru/practice/basis", "/ru/practice/nn_adj"):
        assert client.get(path).status_code == 200, path
    assert client.get("/ru/practice/nope").status_code == 404
    assert "/ru/practice/odn" in client.get("/ru/rules").text
    item = client.get("/api/ru/next?kind=basis").json()["item"]
    assert item["kind"] == "basis" and "s" not in item and "p" not in item         # ответ не уходит в браузер
    # «Я не знаю ответа»: подлежащее — «Я», сказуемое — «не знаю»
    r = client.post("/api/ru/answer", json={"id": "b03", "answer": {"s": [0], "p": [1, 2]}, "mode": "basis"}, headers=h).json()
    assert r["ok"] and r["xp"] == 2
    r = client.post("/api/ru/answer", json={"id": "b13", "answer": {"s": [0], "p": [1, 4]}, "mode": "basis"}, headers=h).json()
    assert not r["ok"] and r["p"] == [1]                                     # деепричастие — не сказуемое
    r = client.post("/api/ru/answer", json={"id": "b03", "answer": "мусор", "mode": "basis"}, headers=h).json()
    assert not r["ok"]
    # тренировка правила: только задания этого правила, повторы пропускаются
    ids = set()
    for _ in range(6):
        it = client.get("/api/ru/next?kind=rule&rule=chik&skip=" + ",".join(ids)).json()["item"]
        assert it["id"] in {"s90", "s91", "s92", "s93", "s94", "s95"}
        ids.add(it["id"])
    assert len(ids) == 6
    assert client.get("/api/ru/next?kind=rule&rule=chik&skip=" + ",".join(ids)).json()["item"] is None
    # много ошибок в одном правиле → сигнал преподавателю и блок в профиле
    for _ in range(6):
        client.post("/api/ru/answer", json={"id": "s91", "answer": "ч", "mode": "rule"}, headers=h)
    login_as(client, "teacher")
    assert "русский: «Суффиксы -ЧИК- и -ЩИК-»" in client.get("/teacher").text
    page = client.get("/teacher/student/%d" % sid).text
    assert 'id="russian"' in page and "каменщик" in page and "Трудные правила" in page
    assert connect().execute("SELECT COUNT(*) FROM ru_attempts WHERE mode = 'rule'").fetchone()[0] == 6


def test_russian_dictation(client):
    from app.content import ru
    from app.db import connect
    for d in ru.DICT_ITEMS.values():                                       # разметка диктантов цела
        assert d["letters"] and d["need"] and set(d["need"]) <= set(d["can"])
        assert all(g["rule"] in ru.RULES and g["answer"] in g["options"] for g in d["letters"])
        assert all(r in ru.RULES for r in d["need"].values()) and "[" not in d["text"] and "^" not in d["text"]
        assert ru.check_dictation(d, [g["answer"] for g in d["letters"]], list(d["need"]))["errors"] == 0
    sid = sid_of()
    t = login_as(client, "teacher")
    client.post("/teacher/student/%d/subjects" % sid, data={"python": "1", "russian": "1", "csrf": t})
    s = login_as(client, "student")
    h = {"X-CSRF-Token": s}
    page = client.get("/ru/dict?id=d01").text
    assert "Диктант: «Перед дождём»" in page and "деревянной" not in page             # ответы не в странице
    d = ru.DICT_ITEMS["d01"]
    letters = [g["answer"] for g in d["letters"]]
    letters[0] = "н"                                                                    # «деревяной» — ошибка
    r = client.post("/api/ru/dict", json={"id": "d01", "letters": letters, "commas": list(d["need"])[1:] + [0]},
                    headers=h).json()
    assert r["errors"] == 3 and r["extra"] == [0] and len(r["missing"]) == 1 and r["xp"] == 0
    assert "Н и НН в прилагательных" in r["rules"] and r["text"].startswith("Мы сидели в деревянной")
    r = client.post("/api/ru/dict", json={"id": "d01", "letters": [g["answer"] for g in d["letters"]],
                                          "commas": list(d["need"])}, headers=h).json()
    assert r["errors"] == 0 and r["xp"] == 6
    r = client.post("/api/ru/dict", json={"id": "d01", "letters": [g["answer"] for g in d["letters"]],
                                          "commas": list(d["need"])}, headers=h).json()
    assert r["xp"] == 0                                                                 # тот же диктант — раз в день
    conn = connect()
    assert conn.execute("SELECT COUNT(*) FROM ru_attempts WHERE mode = 'dict' AND ok = 0").fetchone()[0] == 2
    assert "d01" not in client.get("/ru/dict", follow_redirects=True).text.split('id="ru-dict"')[1][:60]   # следующий — другой
    assert client.post("/api/ru/dict", json={"id": "nope"}, headers=h).status_code == 404


def test_oge_generators_are_consistent():
    """Контракт генератора номера ОГЭ (CONTRIBUTING.md): новый генератор должен пройти этот тест."""
    from app.content import oge_gen as g
    for num in g.GENERATORS:
        shown = set()
        for seed in range(1, 200):
            v = g.make(num, seed)
            assert v["text"].strip() and str(v["answer"]).strip() and v.get("explain", "").strip(), (num, seed)
            shown.add((v["text"], str(v.get("table")), v.get("code")))
            assert g.check(v, v["answer"]) and not g.check(v, "zzz"), (num, seed)
            w = g.make(num, seed)                                                     # вариант воспроизводится по сиду
            assert (w["text"], w["answer"], w.get("table")) == (v["text"], v["answer"], v.get("table"))
            assert "answer" not in g.public(v) and "explain" not in g.public(v)
        assert len(shown) >= 150, (num, len(shown))                                  # варианты правда разные
    v = g.make(5, 3)
    assert not g.check(v, v["answer"] + "1111")                                        # не больше 5 команд
    for seed in range(1, 50):
        v = g.make(2, seed)
        codes = dict(zip(v["table"][0][1:], v["table"][1][1:]))
        assert "".join(codes[c] for c in v["answer"]) in v["text"]                       # сообщение кодирует ответ


def test_oge_drill_flow(client):
    from app.content import oge_gen as g
    from app.db import connect
    sid = sid_of()
    s = login_as(client, "student")
    r = client.get("/oge/drill/4", follow_redirects=False)
    assert r.status_code == 303 and "/oge/drill/4?seed=" in r.headers["location"]
    assert client.get("/oge/drill/11").status_code == 404                               # №11 — только на занятии
    page = client.get("/oge/drill/4?seed=42").text
    v = g.make(4, 42)
    assert "кратчайшего пути" in page and v["explain"] not in page                    # ответ не уходит в браузер
    r = client.post("/oge/drill/4", data={"seed": 42, "answer": "999", "csrf": s}).text
    assert "Неверно" in r and v["explain"] in r
    r = client.post("/oge/drill/4", data={"seed": 42, "answer": v["answer"], "csrf": s}).text
    assert "Верно!" in r and "+2 🏆" not in r                                          # со второй попытки — без трофеев
    for seed in (7, 8, 9):
        r = client.post("/oge/drill/4", data={"seed": seed, "answer": g.make(4, seed)["answer"], "csrf": s}).text
        assert "+2 🏆" in r
    oge = client.get("/oge").text
    assert "/oge/drill/12" in oge and "освоено" in oge
    assert connect().execute("SELECT COUNT(*) FROM oge_drill WHERE student_id = ?", (sid,)).fetchone()[0] == 5
    page = client.get("/oge/drill/6?seed=5").text
    assert "oge-code" in page and "print(" in page, page[page.find("<main"):][:3000]   # №6: программа блоком кода


def test_oge_mock(client):
    from app import main
    s = login_as(client, "student")
    r = client.get("/oge/mock", follow_redirects=False)
    assert r.status_code == 303 and "/oge/mock?k=" in r.headers["location"]
    page = client.get("/oge/mock?k=77&t=1700000000").text
    items = main._mock_items(77)
    assert len(items) == 11 and page.count('name="a') == 11 and 'class="check-timer"' in page
    assert items[3]["v"]["explain"] not in page                                         # ответы не в странице
    data = {"csrf": s, "k": "77", "t": "1700000000"}
    for it in items[:5]:
        data["a%d" % it["num"]] = it["v"]["answer"]
    data["a%d" % items[5]["num"]] = "неверно"
    res = client.post("/oge/mock", data=data).text
    assert "5 из 11" in res and "Потренировать №%d" % items[5]["num"] in res and "+10 🏆" in res
    assert "/oge/mock" in client.get("/oge").text


def test_robot_solutions_work_on_every_field():
    import robot
    from app.content import robot as rc
    for t in rc.TASKS:
        for seed in range(15):
            fields = rc.fields_for(t, seed)
            assert len(fields) >= 4 and all(f["target"] for f in fields), t["id"]
            assert json.loads(robot.run_all(t["solution"], fields))["passed"], (t["id"], seed)
            assert not json.loads(robot.run_all(t["starter"], fields))["passed"], t["id"]
    # авария, уход за край и бесконечный цикл — понятные ошибки, а не зависание
    f = rc.fields_for(rc.TASK_BY_ID["under"], 1)[:1]
    assert "врезался" in json.loads(robot.run_all("вверх()", f))["results"][0]["error"]["hint"]
    assert "далеко" in json.loads(robot.run_all("while True:\n    вправо()", f))["results"][0]["error"]["hint"]
    f = rc.fields_for(rc.TASK_BY_ID["corner"], 1)[:1]
    assert "бесконечный" in json.loads(robot.run_all("while справа_свободно():\n    pass", f))["results"][0]["error"]["hint"]
    # решение «на глазок» под одно поле не проходит остальные
    r = json.loads(robot.run_all("for i in range(5):\n    закрасить()\n    вправо()", rc.fields_for(rc.TASK_BY_ID["under"], 1)))
    assert not r["passed"] and r["results"][1]["extra"]


def test_robot_trainer_flow(client):
    sid = sid_of()
    s = login_as(client, "student")
    assert "Робот откроется" in client.get("/oge/robot").text            # нужен урок с while
    assert client.get("/oge/robot/under", follow_redirects=False).status_code == 303
    t = login_as(client, "teacher")
    assert client.get("/oge/robot/gap").status_code == 200                 # преподаватель видит всё
    for n in range(2, 9):
        client.post("/teacher/lesson/%d/open" % n, data={"csrf": t})
    s = login_as(client, "student")
    page = client.get("/oge/robot/under").text
    assert "robot-fields" in page and "Эталонное решение" in page and "нц пока" not in page   # ответ — только после решения
    h = {"X-CSRF-Token": s}
    assert client.post("/api/robot/under/attempt", json={"code": "x", "passed": False}, headers=h).json()["xp"] == 0
    r = client.post("/api/robot/under/attempt", json={"code": "ok", "passed": True}, headers=h).json()
    assert r["first"] and r["xp"] == 15 and "нц пока" in r["kumir"]
    assert client.post("/api/robot/under/attempt", json={"code": "ok", "passed": True}, headers=h).json()["xp"] == 0
    from app.content import robot as rc
    assert "решено 1 из %d" % len(rc.TASKS) in client.get("/oge").text
    assert "/oge/robot/corner" in client.get("/oge/robot").text
    from app import game
    from app.db import connect
    assert game.stats(connect(), sid)["tasks_solved"] == 0                 # Робот не путается с задачами курса
    # «как на экзамене»: случайная нерешённая задача, без подсказки и эталона, код с чистого листа, поля каждый раз новые
    for _ in range(10):
        loc = client.get("/oge/robot/exam", follow_redirects=False).headers["location"]
        assert loc.endswith("?exam=1") and "/under?" not in loc
    page = client.get("/oge/robot/under?exam=1").text
    assert 'data-exam="1"' in page and "💡 Подсказка" not in page and "нц пока" not in page   # under уже решена
    assert "Как на экзамене: без подсказок" in page and "📝 Сдать" in page
    assert "/oge/robot/under?exam=1" in client.get("/oge/robot/under").text

def test_levels_recommendation_and_profile(client):
    from app import levels
    assert levels.recommend(None, None) is None
    assert levels.recommend(9, None)["level"] == "junior"
    assert levels.recommend(14, (9, None)) == {"level": "pro", "start": 1, "why": levels.recommend(14, (9, None))["why"]}
    r = levels.recommend(12, (9, 8))
    assert r["level"] == "pro" and r["start"] == 7
    assert levels.recommend(14, (3, 1))["level"] == "base"                 # слабая логика — не торопимся
    sid = sid_of()
    t = login_as(client, "teacher")
    page = client.get("/teacher/student/%d" % sid).text
    assert "Уровень и темп" in page and "Укажи возраст" in page
    assert client.post("/teacher/student/%d/level" % sid, data={"level": "boss", "csrf": t}).status_code == 400
    client.post("/teacher/student/%d/level" % sid, data={"level": "base", "age": "14", "csrf": t})
    page = client.get("/teacher/student/%d" % sid).text
    assert "Сайт предлагает: 🎓 Про" in page and "возраст 14" in page
    client.post("/teacher/student/%d/level" % sid, data={"level": "pro", "age": "14", "start": "4", "csrf": t})
    from app import game
    from app.db import connect
    row = connect().execute("SELECT level, age FROM users WHERE id = ?", (sid,)).fetchone()
    assert (row["level"], row["age"]) == ("pro", 14) and game.unlocked_upto(connect(), sid) == 4
    assert "🎓 Про" in client.get("/teacher").text and "🎓 Про" in client.get("/teacher/students").text


def test_calm_mode_and_pro_pace(client):
    sid = sid_of()
    t = login_as(client, "teacher")
    client.post("/teacher/student/%d/level" % sid, data={"level": "pro", "age": "15", "calm_set": "1", "calm": "1", "csrf": t})
    assert "⏩ Сразу уроки 2–3" not in client.get("/teacher").text      # урок 1 ещё не проведён
    client.post("/teacher/lesson/1/done", data={"csrf": t})
    assert "⏩ Сразу уроки 2–3" in client.get("/teacher").text
    # «Принять рекомендацию» без галочки не сбрасывает спокойный вид
    client.post("/teacher/student/%d/level" % sid, data={"level": "pro", "age": "15", "csrf": t})
    s = login_as(client, "student")
    home = client.get("/").text
    assert 'data-calm="1"' in home and "Награды и рейтинг" in home and "/static/img/brawler/" not in home
    ach = client.get("/achievements").text
    assert "Бойцы Python" not in ach and "<h1>🏅 Награды</h1>" in ach
    from app import game
    from app.db import connect
    conn = connect()
    with conn:
        game.award(conn, sid, 500, "тест", "test")
    texts = [n["text"] for n in conn.execute("SELECT text FROM notices WHERE student_id = ?", (sid,))]
    assert any(x.startswith("Новый ранг") for x in texts) and not any("боец" in x for x in texts)
    t = login_as(client, "teacher")
    client.post("/teacher/student/%d/level" % sid, data={"level": "pro", "calm_set": "1", "csrf": t})
    s = login_as(client, "student")
    assert "Бойцы Python" in client.get("/achievements").text


def test_weekly_summary(client, monkeypatch):
    from datetime import datetime
    from app import config, game, notify, weekly
    from app.db import connect
    sid = sid_of()
    conn = connect()
    with conn:
        game.award(conn, sid, 30, "Задача «тест»", "task", "t1")
        conn.execute("INSERT INTO oge_drill (student_id, num, seed, ok, answer, created_at) VALUES (?, 4, 1, 1, '', ?)",
                     (sid, game.now_iso()))
    s = weekly.build(conn)
    row = next(r for r in s["rows"] if r["student"]["id"] == sid)
    assert row["xp"] >= 30 and row["tasks"] == 1 and row["days"] == 1
    txt = weekly.text(s)
    assert "+%d 🏆" % row["xp"] in txt and "1 день из 7" in txt and "решено задач: 1" in txt
    assert "тренажёр ОГЭ: 1 вариант" in txt and "прогноз ОГЭ: 1 из 21" in txt
    # расписание: воскресенье после 19:00, раз в неделю
    sun = datetime(2026, 10, 11, 19, 5, tzinfo=config.TZ)
    assert weekly.due(sun, None) and not weekly.due(sun, weekly.week_key(sun.date()))
    assert not weekly.due(sun.replace(hour=18), None) and not weekly.due(datetime(2026, 10, 10, 20, tzinfo=config.TZ), None)
    sent = []
    monkeypatch.setattr(notify, "send_now", lambda text: sent.append(text) or True)
    monkeypatch.setattr(config, "now", lambda: sun)
    assert not weekly.send_if_due()                                       # Telegram не настроен — ничего
    monkeypatch.setattr(config, "TELEGRAM_TOKEN", "x")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "1")
    assert weekly.send_if_due() and not weekly.send_if_due() and len(sent) == 1
    # страница и кнопка
    t = login_as(client, "teacher")
    page = client.get("/teacher/weekly").text
    assert "Сводка недели" in page and "Отправить сейчас" in page
    r = client.post("/teacher/weekly/send", data={"csrf": t}, follow_redirects=False)
    assert r.headers["location"] == "/teacher/weekly?sent=1" and len(sent) == 2
    s = login_as(client, "student")
    assert client.get("/teacher/weekly", follow_redirects=False).status_code in (303, 403)


def test_season_pass(client, monkeypatch):
    import random
    from app import game, season
    monkeypatch.setattr(season, "DROP_CHANCE", 0.35)
    from app.db import connect
    sid = sid_of()
    conn = connect()
    ov = season.overview(conn, sid)
    assert ov["tier"] == 0 and not ov["premium"] and len(ov["rows"]) == 20
    with conn:
        game.award(conn, sid, 100, "тест", "task", "t1")                 # 100 трофеев → 2 ступени по 40
        game.award(conn, sid, 500, "пасс не крутит сам себя", "pass")
    ov = season.overview(conn, sid)
    assert ov["tier"] == 2 and ov["to_next"] == 20 and ov["ready"] == 2
    s = login_as(client, "student")
    page = client.get("/season").text
    assert "Пасс сезона" in page and page.count('action="/season/claim"') == 2   # премиум закрыт
    assert client.post("/season/claim", data={"tier": 3, "track": "free", "csrf": s}).status_code == 400
    assert client.post("/season/claim", data={"tier": 1, "track": "premium", "csrf": s}).status_code == 400
    client.post("/season/claim", data={"tier": 2, "track": "free", "csrf": s})          # значок 🐣
    assert client.post("/season/claim", data={"tier": 2, "track": "free", "csrf": s}).status_code == 400  # дважды нельзя
    assert "🐣" in client.get("/").text
    with conn:
        assert season.claim(conn, sid, 1, "free", random.Random(1)).startswith("Старр-дроп")
    assert conn.execute("SELECT COUNT(*) FROM xp_events WHERE student_id = ? AND kind = 'drop'", (sid,)).fetchone()[0] == 1
    # премиум вручную от преподавателя
    t = login_as(client, "teacher")
    client.post("/teacher/student/%d/premium" % sid, data={"on": "1", "csrf": t})
    assert season.overview(conn, sid)["premium"]
    s = login_as(client, "student")
    client.post("/season/claim", data={"tier": 1, "track": "premium", "csrf": s})          # значок 🎧
    client.post("/season/equip", data={"kind": "badge", "value": "🐣", "csrf": s})
    assert connect().execute("SELECT badge FROM users WHERE id = ?", (sid,)).fetchone()[0] == "🐣"
    client.post("/season/equip", data={"kind": "badge", "value": "👑", "csrf": s})          # чужой значок — нельзя
    assert connect().execute("SELECT badge FROM users WHERE id = ?", (sid,)).fetchone()[0] == "🐣"
    # старр-дропы за решения: не больше 3 в день
    with conn:
        got = [season.maybe_drop(conn, sid, "тест", random.Random(i)) for i in range(40)]
    assert sum(1 for g in got if g) == season.DROPS_PER_DAY
    # испытания считаются
    ch = {c["id"]: c for c in season.challenges(conn, sid, season.season_of())}
    assert ch["tasks"]["have"] == 1 and ch["days"]["have"] == 1


def test_fresh_database_has_all_user_columns(tmp_path, monkeypatch):
    from app import config, db
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "fresh.db")
    db.init_db()
    have = db._columns(db.connect(), "users")
    assert all(name in have for name, _ in db.USER_COLUMNS)


BOT_CAREFUL = """
ХОДЫ = {'вверх': (0, -1), 'вниз': (0, 1), 'влево': (-1, 0), 'вправо': (1, 0)}

def опасно(клетка, враг, стены):
    return враг['жив'] and линия_огня(враг, клетка, стены) is not None

def ход(я, враг, кристаллы, стены):
    if враг['жив']:
        л = линия_огня(я, враг, стены)
        if л:
            return 'огонь ' + л
    цели = [к for к in кристаллы if not опасно(к, враг, стены)] or кристаллы
    if not цели:
        return 'стоп'
    цель = min(цели, key=lambda к: расстояние(я, к))
    шаг = шаг_к(я, цель, стены)
    if шаг == 'стоп':
        return 'стоп'
    dx, dy = ХОДЫ[шаг]
    куда = (я['x'] + dx, я['y'] + dy)
    if опасно(куда, враг, стены) and куда != tuple(цель):
        for имя, (dx, dy) in ХОДЫ.items():
            к = (я['x'] + dx, я['y'] + dy)
            if к not in стены and 0 <= к[0] < ШИРИНА and 0 <= к[1] < ВЫСОТА and not опасно(к, враг, стены):
                return имя
        return 'стоп'
    return шаг
"""


def test_bots_engine_and_ladder():
    import bots
    from app.content import bots as meta
    assert [(b["id"], b["name"], b["xp"], b["about"]) for b in meta.BOSSES] ==         [(b["id"], b["name"], b["xp"], b["about"]) for b in bots.BOSSES]
    # заготовка сама не побеждает; подсказка из неё — побеждает Манекена, но не Охотника
    assert not json.loads(bots.fight_boss(meta.STARTER, "dummy"))["won"]
    first = "def ход(я, враг, кристаллы, стены):\n    if кристаллы:\n        return шаг_к(я, кристаллы[0], стены)\n    return 'стоп'\n"
    assert json.loads(bots.fight_boss(first, "dummy"))["won"]
    assert not json.loads(bots.fight_boss(first, "hunter"))["won"]
    # каждого босса можно победить осторожной тактикой
    for b in bots.BOSSES:
        assert json.loads(bots.fight_boss(BOT_CAREFUL, b["id"]))["won"], b["id"]
    # бой детерминирован и укладывается в лимиты
    a, b = bots.battle(BOT_CAREFUL, bots.BOSSES[3]["code"], 5), bots.battle(BOT_CAREFUL, bots.BOSSES[3]["code"], 5)
    assert a["frames"] == b["frames"] and len(a["frames"]) <= bots.MAX_FRAMES
    # понятные ошибки вместо падения
    r = json.loads(bots.fight_boss("x = 1", "dummy"))
    assert not r["won"] and "нет функции ход" in r["error"]["hint"]
    r = json.loads(bots.fight_boss("def ход(я, враг, к, с):\n    return 1 / 0", "dummy"))
    assert not r["won"] and r["error"]["turn"] == 1 and r["error"]["line"] == 2
    r = json.loads(bots.fight_boss("def ход(я, враг, к, с):\n    return 'прыжок'", "dummy"))
    assert "прыжок" in r["error"]["hint"]
    assert bots.шаг_к({"x": 1, "y": 4}, (3, 4), bots.WALLS) in ("вверх", "вниз")      # в обход стены (2, 4)
    assert bots.линия_огня({"x": 3, "y": 4}, {"x": 5, "y": 4}, bots.WALLS) is None      # стена (4, 4) закрывает


def test_bots_page_and_results(client):
    sid = sid_of()
    s = login_as(client, "student")
    assert "откроется с урока 10" in client.get("/bots").text
    t = login_as(client, "teacher")
    for n in range(2, 11):
        client.post("/teacher/lesson/%d/open" % n, data={"csrf": t})
    s = login_as(client, "student")
    page = client.get("/bots").text
    assert 'data-boss="dummy"' in page and page.count("disabled title=") == 4     # открыт только первый
    h = {"X-CSRF-Token": s}
    assert client.post("/api/bots/dummy/result", json={"code": "x", "won": False}, headers=h).json()["xp"] == 0
    r = client.post("/api/bots/dummy/result", json={"code": "ok", "won": True}, headers=h).json()
    assert r["first"] and r["xp"] == 15
    assert client.post("/api/bots/dummy/result", json={"code": "ok", "won": True}, headers=h).json()["xp"] == 0
    page = client.get("/bots").text
    assert page.count("disabled title=") == 3 and "✅ побеждён" in page
    assert client.post("/api/bots/nobody/result", json={"won": True}, headers=h).status_code == 404


# ------------------------------------------------------------------ экономика 10.10: гемы, герои по предметам, дропы
def test_economy_gems_heroes_and_drops(client):
    import random
    from app import game, season
    from app.db import connect, init_db
    sid = sid_of()
    conn = connect()
    with conn:
        game.award(conn, sid, 40, "русский", "ru")
    h = game.heroes(conn, sid)
    assert h["ru"] == 40 and h["ru_got"] == 1 and h["py_got"] == 1          # Запятайка за русский, Python не сдвинулся
    texts = [n["text"] for n in conn.execute("SELECT text FROM notices WHERE student_id = ?", (sid,))]
    assert any("герой русского" in t and "Запятайка" in t for t in texts) and not any("боец Python" in t for t in texts)
    assert game.coins(conn, sid) == 0
    with conn:                                                               # гемы — только за учёбу
        game.award(conn, sid, 10, "дз", "homework", "1")
        game.award(conn, sid, 30, "проверка", "check", "w1")
        game.award(conn, sid, 15, "дроп", "drop")
    assert game.coins(conn, sid) == 20
    # дроп даёт значок своей редкости, пока они не кончились, и трофеев немного
    with conn:
        d = season.roll_drop(conn, sid, "тест", random.Random(3))
    assert d["amount"] <= 40 and d["badge"] in season.DROP_BADGES[d["rarity"]]
    assert d["badge"] in season.collection(conn, sid)["badges"]
    with conn:
        for i in range(60):
            season.roll_drop(conn, sid, "тест", random.Random(i))
    badges = season.collection(conn, sid)["badges"]
    assert len(badges) == len(set(badges))                                   # без повторов
    # цены магазина переведены на гемы один раз, свои цены преподавателя не трогаем
    with conn:
        conn.execute("UPDATE rewards SET cost = 300 WHERE title = 'Пицца на ужин'")
        conn.execute("DELETE FROM settings WHERE key = 'economy_v2'")
        conn.execute("UPDATE rewards SET cost = 999 WHERE title = 'Новая игра'")
    init_db()
    costs = dict(conn.execute("SELECT title, cost FROM rewards").fetchall())
    assert costs["Пицца на ужин"] == 160 and costs["Новая игра"] == 999 and costs["Десерт на выбор"] == 40
    assert len(costs) == len(set(costs))
    # страница коллекции: два блока, бойцы кликабельные
    t = login_as(client, "teacher")
    client.post("/teacher/student/%d/subjects" % sid, data={"python": "1", "russian": "1", "csrf": t})
    login_as(client, "student")
    ach = client.get("/achievements").text
    assert "Бойцы Python" in ach and "Герои русского языка" in ach and 'data-hero-name="Запятайка"' in ach
    page = client.get("/").text
    assert page.index("🐍 Python") < page.index("📖 Русский язык") < page.index("🏆 Награды")   # меню блоками


def test_homework_link_and_form(client):
    t = login(client, "teacher")
    client.post("/teacher/lesson/2/open", data={"csrf": t})
    for n in (1, 2):
        client.post("/teacher/lesson/%d/done" % n, data={"csrf": t})
    s = login(client, "student")
    r = client.get("/homework", follow_redirects=False)
    assert r.headers["location"] == "/lesson/1#homework"                     # самое раннее несданное ДЗ
    page = client.get("/lesson/1").text
    assert "только по кнопке «📬 Сдать на проверку»" in page and 'data-confirm="Сдать домашку' in page
    client.post("/lesson/1/submit", data={"code": "print(1)", "comment": "", "csrf": s})
    assert client.get("/homework", follow_redirects=False).headers["location"] == "/lesson/2#homework"


def test_art_sets_present():
    """Картинки с GPU-аренды: у каждого ранга эмблема, у каждой редкости дропа сундук, у каждого сезона баннер."""
    from app import art, season
    assert all(art.rank_img(n) for n in range(1, 11))
    assert all(art.chest_img(name) for name, *_ in season.RARITIES)
    assert all(art.season_banner(m) for m in range(1, 13))
    assert art.icon_img("ru_basis") and art.icon_img("нет-такой") is None


def test_public_theme_has_no_foreign_brands():
    """Фирменные слова чужой игры живут только в app/theme.py: публичная тема их не содержит, а код и шаблоны
    берут их из темы. Уроки и задачи (класс Brawler в задаче про ООП) — учебный текст, их не проверяем."""
    import pathlib
    from app import theme
    pub = " ".join(theme.TERMS["public"].values()).lower()
    assert not [w for w in theme.FOREIGN_BRANDS if w in pub]
    assert set(theme.TERMS["public"]) == set(theme.TERMS["family"])
    root = pathlib.Path(theme.__file__).parent
    bad = []
    for p in list(root.glob("*.py")) + list((root / "templates").rglob("*.html")) + list((root / "static" / "js").glob("*.js")):
        if p.name == "theme.py" or "guides" in p.parts:
            continue
        low = p.read_text(encoding="utf-8").lower()
        bad += ["%s: %s" % (p.name, w) for w in ("старр", "brawl stars", "supercell") if w in low]
    assert not bad, bad


def test_forecast_math():
    from app import forecast
    assert forecast.MAX_POINTS == 21
    assert forecast.grade(4) == 2 and forecast.grade(5) == 3 and forecast.grade(11) == 4 and forecast.grade(17) == 5
    empty = forecast.forecast({n: {} for n in range(1, 17)})
    assert empty["grade"] is None and empty["points"] == 0 and len(empty["unknown"]) == 16
    prog = {n: {"has_drill": n in (1, 2, 4), "drill": {"n": 3, "ok": 3, "mastered": True}} if n in (1, 2) else {"has_drill": n == 4}
            for n in range(1, 17)}
    fc = forecast.forecast(prog)
    assert fc["known"] == {1: 95, 2: 95} and fc["points"] == 2 and fc["next"] == [4]


def test_today_plan_and_chest(client):
    from app import config, game, today
    from app.content import oge_gen as g
    from app.db import connect
    sid = sid_of()
    conn = connect()
    p = today.plan(conn, sid)
    assert [s["key"] for s in p["steps"]] == ["daily", "oge", "task"] and p["done"] == 0
    s = login_as(client, "student")
    page = client.get("/today").text
    assert "План на сегодня" in page and "/oge/drill/4" in page and 'action="/today/claim"' not in page
    assert "План на сегодня — 0 из 3" in client.get("/").text
    client.post("/today/claim", data={"csrf": s})
    assert not today.plan(conn, sid)["claimed"]                                       # план не выполнен — сундука нет
    for seed in (1, 2, 3):
        client.post("/oge/drill/4", data={"seed": seed, "answer": g.make(4, seed)["answer"], "csrf": s})
    with conn:
        conn.execute("UPDATE daily SET finished_at = ? WHERE student_id = ?", (game.now_iso(), sid))
        game.award(conn, sid, 5, "тест", "task", "hello")
    p = today.plan(conn, sid)
    assert p["complete"] and not p["claimed"]
    assert 'action="/today/claim"' in client.get("/today").text
    client.post("/today/claim", data={"csrf": s})
    client.post("/today/claim", data={"csrf": s})                                      # второй раз — ничего
    ref = "today:" + config.today().isoformat()
    assert connect().execute("SELECT COUNT(*) FROM xp_events WHERE student_id = ? AND kind = 'drop' AND ref = ?",
                             (sid, ref)).fetchone()[0] == 1
    assert today.plan(conn, sid)["claimed"]
    t = login_as(client, "teacher")
    assert client.post("/today/claim", data={"csrf": t}).status_code == 403
    assert "Прогноз ОГЭ" in client.get("/teacher/student/%d" % sid).text


def test_self_paced_lessons(client):
    from app import game
    from app.content.tasks import TASKS
    from app.db import connect
    sid = sid_of()
    conn = connect()
    s = login_as(client, "student")
    t1 = [t for t in TASKS if t["lesson"] == 1]
    need = game.self_pace_need(1)
    assert need == 3 and len(t1) == 4
    # без галочки задачи урок не двигают
    client.post("/api/task/%s/attempt" % t1[0]["id"], json={"code": "x", "passed": True}, headers={"X-CSRF-Token": s})
    assert game.unlocked_upto(conn, sid) == 1
    t = login_as(client, "teacher")
    page = client.get("/teacher/student/%d" % sid).text
    assert 'name="self_pace"' in page
    assert not game.self_paced(conn, sid)
    client.post("/teacher/student/%d/level" % sid, data={"csrf": t, "level": "base", "calm_set": "1", "self_pace": "1"})
    assert game.self_paced(conn, sid)
    s = login_as(client, "student")
    assert "Учусь сам" in client.get("/lesson/1").text
    for task in t1[1:3]:
        client.post("/api/task/%s/attempt" % task["id"], json={"code": "x", "passed": True}, headers={"X-CSRF-Token": s})
    assert game.unlocked_upto(conn, sid) == 2 and 1 in game.done_lessons(conn, sid)
    # урок без задач — по кнопке
    empty = next(n for n in range(1, 35) if not [x for x in TASKS if x["lesson"] == n])
    with conn:
        game.open_lesson(conn, sid, empty, notice=False)
    assert "Урок изучен" in client.get("/lesson/%d" % empty).text
    client.post("/lesson/%d/self-done" % empty, data={"csrf": s})
    assert game.unlocked_upto(conn, sid) == empty + 1 and empty in game.done_lessons(conn, sid)
    client.post("/lesson/%d/self-done" % (empty + 1), data={"csrf": s})                # у урока с задачами кнопка не работает
    if [x for x in TASKS if x["lesson"] == empty + 1]:
        assert game.unlocked_upto(conn, sid) == empty + 1


def test_landing_only_on_public_site(client, monkeypatch):
    from app import theme
    client.cookies.clear()
    r = client.get("/welcome", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"                    # семейный сайт — сразу вход
    assert client.get("/", follow_redirects=False).headers["location"] == "/login"
    monkeypatch.setattr(theme, "THEME", "public")
    assert client.get("/", follow_redirects=False).headers["location"] == "/welcome"
    page = client.get("/welcome").text
    assert "Подготовка к ОГЭ" in page and "Прогноз балла" in page and "/login" in page
    text = re.sub(r"<[^>]+>", " ", page).lower()                                         # видимый текст, без путей картинок
    assert not [w for w in theme.FOREIGN_BRANDS if w in text]


def _parent_token(client, sid):
    t = login_as(client, "teacher")
    client.post("/teacher/student/%d/parent-link" % sid, data={"action": "new", "csrf": t})
    from app.db import connect
    return connect().execute("SELECT parent_token FROM users WHERE id = ?", (sid,)).fetchone()[0]


def _fam_csrf(page):
    return re.search(r'name="csrf" value="([^"]+)"', page).group(1)


def test_family_cabinet(client):
    misha = sid_of("student")
    add_student(client, "Аня", "anya")
    anya = sid_of("anya")
    tok_m, tok_a = _parent_token(client, misha), _parent_token(client, anya)
    client.cookies.clear()
    page = client.get("/parent/%s" % tok_m).text
    assert "Завести кабинет" in page and "csrf" not in page
    assert "/privacy" in client.get("/parent/%s/account" % tok_m).text
    form = {"name": "Мама", "login": "mama", "password": "dlinnyi-parol"}
    r = client.post("/parent/%s/account" % tok_m, data=form)
    assert "согласия" in r.text and "cq_family" not in r.cookies                     # без галочки — нельзя
    r = client.post("/parent/%s/account" % tok_m, data=dict(form, password="short", consent="1"))
    assert "8 символов" in r.text
    r = client.post("/parent/%s/account" % tok_m, data=dict(form, consent="1"), follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/family"
    home = client.get("/family")
    assert "Миша" in home.text and "Аня" not in home.text and home.headers["Cache-Control"] == "no-store"
    from app.db import connect
    row = connect().execute("SELECT consent_at, consent_version FROM parents WHERE username = 'mama'").fetchone()
    assert row[0] and row[1]
    assert "Прогноз ОГЭ" in client.get("/family/child/%d" % misha).text
    assert client.get("/family/child/%d" % anya).status_code == 404                     # чужого ребёнка не видно
    # родитель не попадает в кабинеты ученика и преподавателя
    assert client.get("/", follow_redirects=False).status_code in (302, 303, 307)
    assert client.get("/teacher", follow_redirects=False).status_code in (302, 303, 307, 403)
    # второй ребёнок — по его ссылке, с CSRF
    page = client.get("/parent/%s" % tok_a).text
    assert "Добавить в мой кабинет" in page
    assert client.post("/parent/%s/link" % tok_a, data={"csrf": "bad"}).status_code == 403
    client.post("/parent/%s/link" % tok_a, data={"csrf": _fam_csrf(page)})
    assert "Аня" in client.get("/family").text
    # повторный вход по логину
    csrf = _fam_csrf(client.get("/family").text)
    client.post("/family/logout", data={"csrf": csrf})
    assert client.get("/family", follow_redirects=False).headers["location"] == "/family/login"
    assert "Неверный" in client.post("/family/login", data={"username": "mama", "password": "wrong-wrong"}).text
    client.post("/family/login", data={"username": "mama", "password": "dlinnyi-parol"})
    assert "Аня" in client.get("/family").text
    # преподаватель видит родителя и может отвязать
    t = login_as(client, "teacher")
    page = client.get("/teacher/student/%d" % anya).text
    assert "Кабинет родителя" in page and "mama" in page
    pid = connect().execute("SELECT id FROM parents WHERE username = 'mama'").fetchone()[0]
    client.post("/teacher/student/%d/parent-unlink" % anya, data={"parent_id": pid, "csrf": t})
    client.cookies.clear()
    client.post("/family/login", data={"username": "mama", "password": "dlinnyi-parol"})
    assert "Аня" not in client.get("/family").text and "Миша" in client.get("/family").text


def test_source_link(client, monkeypatch):
    from app import config
    assert "Исходный код" not in client.get("/login").text
    monkeypatch.setattr(config, "SOURCE_URL", "https://example.org/src")
    assert "https://example.org/src" in client.get("/login").text


def test_brand_only_on_public_site(client, monkeypatch):
    from app import theme
    page = client.get("/login").text
    assert "umedu-mark.svg" not in page and 'data-site="public"' not in page
    monkeypatch.setattr(theme, "LOGO", "/static/img/brand/umedu-mark.svg")
    import app.main as m
    monkeypatch.setattr(m.theme, "THEME", "public")
    monkeypatch.setattr(m.config, "SITE_NAME", "umedu")
    page = client.get("/login").text
    assert "umedu-mark.svg" in page and 'class="wordmark"' in page and 'data-site="public"' in page
    assert client.get("/static/img/brand/umedu-mark.svg").status_code == 200


def test_privacy_page(client):
    r = client.get("/privacy")
    assert r.status_code == 200 and "152-ФЗ" in r.text


def test_events_and_analytics(client, monkeypatch):
    from app import events
    from app.content.tasks import TASKS
    from app.db import connect
    conn = connect()
    client.cookies.clear()
    client.get("/login")                                                       # аноним — не пишем
    s = login_as(client, "student")
    client.get("/lesson/1")
    client.get("/lesson/99")                                                   # 404 — не пишем
    client.get("/static/css/app.css")
    t1 = [t for t in TASKS if t["lesson"] == 1]
    client.post("/api/task/%s/attempt" % t1[0]["id"], json={"code": "x", "passed": False}, headers={"X-CSRF-Token": s})
    client.post("/api/task/%s/attempt" % t1[1]["id"], json={"code": "x", "passed": True}, headers={"X-CSRF-Token": s})
    rows = conn.execute("SELECT role, kind, route, ref FROM events ORDER BY id").fetchall()
    routes = [(r["kind"], r["route"], r["ref"]) for r in rows]
    assert ("view", "/lesson/{num}", "1") in routes
    assert ("action", "/api/task/{task_id}/attempt", t1[0]["id"]) in routes
    assert not [r for r in routes if r[1].startswith(("/static", "/login")) or r[2] == "99"]
    assert {r["role"] for r in rows} == {"student"}
    # сломанная запись событий не ломает страницу
    real = events.connect
    monkeypatch.setattr(events, "connect", lambda: (_ for _ in ()).throw(RuntimeError("db busy")))
    assert client.get("/lesson/1").status_code == 200
    monkeypatch.setattr(events, "connect", real)
    # отчёт
    from app import analytics
    a = analytics.report(conn)
    assert a["summary"]["students"] == 1 and a["summary"]["today"] == 1
    steps = {f["title"]: f["count"] for f in a["funnel"]}
    assert steps["Заходили на сайт"] == 1 and steps["Решили первую задачу"] == 1 and steps["Забирали сундук плана дня"] == 0
    assert a["exits"] and a["exits"][0]["what"] == "урок"
    assert a["stuck"][0]["task"]["id"] == t1[0]["id"]
    assert a["people"][0]["last_page"] == "урок" and a["people"][0]["solved_week"] == 1
    login_as(client, "teacher")
    page = client.get("/teacher/analytics").text
    assert "Аналитика" in page and "Миша" in page and "Где уходят" in page and t1[0]["title"] in page
    login_as(client, "student")
    assert client.get("/teacher/analytics").status_code == 403
