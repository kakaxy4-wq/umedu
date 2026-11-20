"""Редизайн umedu: шаг на сегодня, класс ребёнка, успехи родителя, редактор кода, вход родителя."""
import re

from app import config
from test_app import client, login  # noqa: F401


def test_today_leads_with_an_onsite_step(client, monkeypatch):
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "ege-phys-2026", "goal": 70})
    page = client.get("/u2/today").text
    assert "Следующий шаг" in page and "Начать задание" in page and "Решается прямо здесь" in page
    assert "u2-nav" in page and "u2-tab" in page


def test_parent_sees_primary_answers(client, monkeypatch):
    from app import students
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    students._signups.clear()
    client.cookies.clear()
    form = {"pname": "Мама", "plogin": "mama-ux", "ppassword": "dlinnyi-parol", "name": "Лена",
            "grade": 4, "login": "lena4", "password": "kot-luna-27", "consent": "1"}
    assert client.post("/family/new-child", data=form, follow_redirects=False).status_code == 303
    client.cookies.clear()
    client.post("/login", data={"username": "lena4", "password": "kot-luna-27"}, follow_redirects=False)
    page = client.get("/u2/today").text
    csrf = re.search(r'name="csrf" content="([^"]+)"', page).group(1)
    # m4-02 is 47×23 in the grade-4 plan; the exact id is not required if any answer is stored.
    from app.db import connect
    sid = connect().execute("SELECT id FROM users WHERE username = 'lena4'").fetchone()[0]
    task = re.search(r'href="/u2/p/math/(m4-[^"]+)"', page)
    assert task, page
    from app import primary
    right = primary.BY_ID[task.group(1)]["accept"][0]
    client.post("/u2/p/math/%s" % task.group(1), data={"csrf": csrf, "answer": right})
    client.cookies.clear()
    assert client.post("/family/login", data={"username": "mama-ux", "password": "dlinnyi-parol"},
                       follow_redirects=False).status_code == 303
    home = client.get("/family/child/%d" % sid).text
    assert "Последние успехи" in home and "Пока пусто" not in home
    assert "Верно" in home and "Пока не так" not in home
    assert "Ещё нет решённых заданий за неделю" not in home


def test_code_task_loads_editor(client, monkeypatch):
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-inf-2026", "goal": 4})
    page = client.get("/u2/train/oge-inf-2026/16?seed=4").text
    assert "codemirror.js" in page and "Копировать" in client.get("/static/js/runner.js").text
    assert "отрицательные числа" not in client.get("/static/py/cq_runtime.py").text


def test_grade_lock_matches_server(client, monkeypatch):
    """Ученик 14+ с привязанным родителем не видит кнопки класса: сервер всё равно ответил бы 403."""
    from app import family
    from app.db import connect
    from test_app import sid_of
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    sid = sid_of()
    conn = connect()
    with conn:
        pid, err = family.signup(conn, "Мама", "mama-link", "dlinnyi-parol", True)
        assert err is None
        assert family.link(conn, pid, sid) is None
    page = client.get("/u2/me").text
    assert "Меняет родитель" in page and 'action="/u2/me/grade"' not in page
    assert client.post("/u2/me/grade", data={"csrf": csrf, "grade": 9}).status_code == 403


def test_forecast_waits_for_attempts_and_code_card_is_hidden(client, monkeypatch):
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "ege-phys-2026", "goal": 70})
    page = client.get("/u2/today").text
    assert "Прогноза пока нет" in page and "первичный" not in page
    code = client.get("/u2/train/oge-inf-2026/16?seed=4")
    assert code.status_code == 404  # экзамен не выбран
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-inf-2026", "goal": 4})
    html = client.get("/u2/train/oge-inf-2026/16?seed=4").text
    assert 'id="u2-solution" hidden' in html
    css = client.get("/static/css/u2.css").text
    assert ".u2-card[hidden]" in css and "cb-bar .btn" in css


def test_join_script_is_external(client, monkeypatch):
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    html = client.get("/join").text
    assert 'src="/static/js/join.js' in html
    assert "<script>" not in html
    js = client.get("/static/js/join.js").text
    assert "join-password" in js and "join-show" in js


def test_join_show_password_button(client, monkeypatch):
    """Кнопка «Показать» меняет type у поля. Нужен Chrome; без него тест не падает вслепую."""
    import socket
    import threading
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    pytest = __import__("pytest")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright не установлен")
    port = 8771
    ready = threading.Event()

    def serve():
        import uvicorn
        from app.main import app
        ready.set()
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    ready.wait(2)
    import time
    time.sleep(0.4)
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(channel="chrome", headless=True)
            except Exception:
                pytest.skip("Chrome недоступен")
            page = browser.new_page()
            page.goto("http://127.0.0.1:%d/join" % port, wait_until="domcontentloaded")
            field = page.locator("#join-password")
            assert field.get_attribute("type") == "password"
            page.locator("#join-show").click()
            assert field.get_attribute("type") == "text"
            assert page.locator("#join-show").inner_text() == "Скрыть"
            browser.close()
    except OSError:
        pytest.skip("сервер регистрации не поднялся")


def test_join_hides_password_and_parent_can_sign_up(client, monkeypatch):
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    join = client.get("/join").text
    assert 'type="password"' in join and "Мы придумали пароль" in join and 'id="join-show"' in join
    login_page = client.get("/family/login").text
    assert 'href="/family/new-child"' in login_page and "Создать кабинет" in login_page
    monkeypatch.setattr(config, "OPEN_SIGNUP", False)
    assert "от преподавателя" in client.get("/family/login").text
