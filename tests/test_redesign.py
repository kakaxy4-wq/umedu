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
    client.post("/u2/p/math/%s" % task.group(1), data={"csrf": csrf, "answer": "1"})
    client.cookies.clear()
    assert client.post("/family/login", data={"username": "mama-ux", "password": "dlinnyi-parol"},
                       follow_redirects=False).status_code == 303
    home = client.get("/family/child/%d" % sid).text
    assert "Последние успехи" in home and "Пока пусто" not in home
    assert "Верно" in home or "Пока не так" in home
    assert "Ещё нет решённых заданий за неделю" not in home


def test_code_task_loads_editor(client, monkeypatch):
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-inf-2026", "goal": 4})
    page = client.get("/u2/train/oge-inf-2026/16?seed=4").text
    assert "codemirror.js" in page and "Копировать" in client.get("/static/js/runner.js").text
    assert "отрицательные числа" not in client.get("/static/py/cq_runtime.py").text


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
