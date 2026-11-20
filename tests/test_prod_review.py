"""Проверка прода: меню umedu, отвязка младше 14, старые адреса, проверка кода на сервере, заголовки."""
import re
from pathlib import Path

from app import config
from test_app import client, login  # noqa: F401

JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js"


def _child(client, grade="4"):
    from app import students
    students._signups.clear()
    client.cookies.clear()
    form = {"pname": "Мама", "plogin": "mama4", "ppassword": "dlinnyi-parol", "name": "Петя",
            "grade": grade, "login": "petya4", "password": "kot-luna-27", "consent": "1"}
    r = client.post("/family/new-child", data=form, follow_redirects=False)
    assert r.status_code == 303, r.text
    client.cookies.clear()
    client.post("/login", data={"username": "petya4", "password": "kot-luna-27"}, follow_redirects=False)
    return form


def test_junior_menu_only_real_pages(client, monkeypatch):
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "CHEM_SITE", False)
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    _child(client)
    for path in ("/account", "/for-parents"):
        nav = re.search(r'<nav class="sidenav">(.*)</nav>', client.get(path).text, re.S).group(1)
        hrefs = re.findall(r'href="([^"]+)"', nav)
        assert hrefs
        for gone in ("/certificates", "/checks", "/portfolio", "/achievements", "/season", "/shop", "/oge", "/map"):
            assert gone not in hrefs, (path, gone)
        assert "/u2/today" in hrefs and "/account" in hrefs
    page = client.get("/for-parents").text
    assert "прогноз балла ОГЭ" not in page and "Отвязать" not in page
    assert "уроки" in page


def test_minor_cannot_unlink_parent(client, monkeypatch):
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    _child(client)
    page = client.get("/for-parents").text
    csrf = re.search(r'name="csrf" content="([^"]+)"', page).group(1)
    from app.db import connect
    pid = connect().execute("SELECT id FROM parents WHERE username = 'mama4'").fetchone()[0]
    r = client.post("/for-parents", data={"csrf": csrf, "action": "unlink", "parent_id": pid})
    assert r.status_code == 403
    assert "Мама" in client.get("/for-parents").text


def test_umedu_legacy_redirects_senior_not_primary_or_codequest(client, monkeypatch):
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "CHEM_SITE", False)
    login(client, "student")
    r = client.get("/oge", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/u2/today"
    assert client.get("/playground", follow_redirects=False).headers["location"] == "/u2/today"
    login(client, "teacher")
    assert client.get("/teacher").status_code == 200
    monkeypatch.setattr(config, "UMEDU2", False)
    login(client, "student")
    assert client.get("/oge").status_code == 200 and "ОГЭ" in client.get("/oge").text


def test_passed_needs_nonempty_code(client):
    """Код на сервере не запускаем. Пустую отправку не засчитываем, непустую — как сообщил браузер."""
    csrf = login(client, "student")
    h = {"X-CSRF-Token": csrf}
    empty = client.post("/api/task/hello/attempt", json={"code": "   ", "passed": True}, headers=h).json()
    assert empty["passed"] is False and empty["xp"] == 0
    claimed = client.post("/api/task/hello/attempt", json={"code": "print(1)", "passed": True}, headers=h).json()
    assert claimed["passed"] is True and claimed["xp"] == 10


def test_head_static_and_page_keep_length(client, caplog):
    """HEAD на файл и на страницу: пустое тело, длина как у GET, без исключения ASGI."""
    import logging
    from pathlib import Path
    caplog.set_level(logging.ERROR)
    static = client.head("/static/js/app.js")
    size = (Path(__file__).resolve().parents[1] / "app" / "static" / "js" / "app.js").stat().st_size
    assert static.status_code == 200 and static.content == b""
    assert static.headers["content-length"] == str(size)
    assert static.headers["content-type"].startswith("text/javascript")
    page = client.head("/login")
    full = client.get("/login")
    assert page.status_code == 200 and page.content == b""
    assert page.headers["content-length"] == full.headers["content-length"]
    assert int(page.headers["content-length"]) == len(full.content)
    assert "Content-Length" not in caplog.text and "Exception in ASGI" not in caplog.text


def test_head_robots_favicon_sitemap_and_hsts(client, monkeypatch):
    head = client.head("/login")
    assert head.status_code == 200 and head.content == b""
    family = client.get("/robots.txt")
    assert family.status_code == 200 and "Disallow: /" in family.text and "Allow: /" not in family.text
    assert "<url>" not in client.get("/sitemap.xml").text
    monkeypatch.setattr(config, "CHEM_SITE", True)
    assert "Disallow: /" in client.get("/robots.txt").text
    monkeypatch.setattr(config, "CHEM_SITE", False)
    monkeypatch.setattr(config, "UMEDU2", True)
    robots = client.get("/robots.txt")
    assert robots.status_code == 200 and "Disallow: /account" in robots.text and "Allow: /" in robots.text
    assert client.get("/favicon.ico").status_code == 200
    site = client.get("/sitemap.xml")
    assert site.status_code == 200 and "/login" in site.text and "/account" not in site.text
    assert "strict-transport-security" not in {k.lower() for k in client.get("/login").headers}
    https = client.get("/login", headers={"X-Forwarded-Proto": "https"})
    assert https.headers["strict-transport-security"] == "max-age=31536000"


def test_u2_csrf_is_json_and_gallery_is_not_python(client, monkeypatch):
    monkeypatch.setattr(config, "UMEDU2", True)
    login(client, "student")
    r = client.post("/u2/api/play/oge-inf-2026/16", json={"seed": 1, "passed": True})
    assert r.status_code == 403 and r.headers["content-type"].startswith("application/json")
    assert "detail" in r.json()
    monkeypatch.setattr(config, "UMEDU2", True)
    page = client.get("/gallery").text
    assert "курсе Python" not in page
    monkeypatch.setattr(config, "UMEDU2", False)
    assert "курсе Python" in client.get("/gallery").text


def test_physics_plan_has_no_fipi_self_checks(client, monkeypatch):
    from app import u2_onsite
    from app.content import onsite_extra, phys_gen
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "ege-phys-2026", "goal": 70})
    page = client.get("/u2/today").text
    assert "fipi.ru" not in page and "сборник" not in page and "открытого банка" not in page
    hrefs = [int(n) for n in re.findall(r'href="/u2/train/ege-phys-2026/(\d+)"', page)]
    allowed = (set(phys_gen.EGE.GENERATORS) | onsite_extra.keys_for("ege-phys-2026")
               ) - onsite_extra.practice_keys("ege-phys-2026")
    assert hrefs and set(hrefs) <= allowed
    for n in hrefs:
        assert u2_onsite.mode_of("ege-phys-2026", n) != "soon"
    self_page = client.get("/u2/train/ege-phys-2026/5?seed=3").text
    assert "fipi.ru" not in self_page and 'name="answer"' in self_page and "target=\"_blank\"" not in self_page
    lab = client.get("/u2/lab/ohm").text
    assert "fipi.ru" not in lab
    assert "ХимЛабе" not in client.get("/u2/lab").text


def _payload(src, marker):
    """Объект, который уходит в запрос, а не поле ответа r.passed рядом."""
    window = src[src.index(marker):src.index(marker) + 700]
    found = re.search(r"JSON\.stringify\(\{([^}]*)\}", window) or re.search(r"/attempt',\s*\{([^}]*)\}", window)
    assert found, window[:160]
    return found.group(1)


def test_every_code_client_sends_passed_including_codequest(client, monkeypatch):
    """КодКвест без флага umedu и страницы u2 сообщают браузерный результат. Без passed сервер пишет 0."""
    monkeypatch.setattr(config, "UMEDU2", False)
    monkeypatch.setattr(config, "CHEM_SITE", False)
    app_js = (JS / "app.js").read_text(encoding="utf-8")
    code_js = (JS / "u2-code.js").read_text(encoding="utf-8")
    robot_js = (JS / "u2-robot.js").read_text(encoding="utf-8")
    assert "passed" in _payload(app_js, "'/api/task/'")
    assert "passed" in _payload(app_js, "'/api/robot/'")
    assert "passed" in _payload(code_js, "/u2/api/play/")
    assert "passed" in _payload(robot_js, "/u2/api/play/")
    for path in JS.glob("*.js"):
        src = path.read_text(encoding="utf-8")
        for m in re.finditer(r"/api/(?:task|robot)/|/u2/api/play/", src):
            assert "passed" in _payload(src, src[m.start():m.end()]), path.name
    from test_app import login_as, sid_of
    t = login_as(client, "teacher")
    for n in range(2, 9):
        client.post("/teacher/lesson/%d/open" % n, data={"csrf": t})
    s = login_as(client, "student")
    assert client.get("/oge/robot/under").status_code == 200
    h = {"X-CSRF-Token": s}
    from app.content.robot import TASK_BY_ID
    from app.db import connect
    sid = sid_of()
    missing = client.post("/api/robot/under/attempt",
                          json={"code": TASK_BY_ID["under"]["solution"], "seed": 1}, headers=h).json()
    assert missing["passed"] is False and missing["xp"] == 0
    row = connect().execute(
        "SELECT passed FROM robot_attempts WHERE student_id = ? AND task_id = 'under' ORDER BY id DESC LIMIT 1",
        (sid,)).fetchone()
    assert row[0] == 0
    ok = client.post("/api/robot/under/attempt",
                     json={"code": TASK_BY_ID["under"]["solution"], "seed": 1, "passed": True}, headers=h).json()
    assert ok["passed"] is True
    row = connect().execute(
        "SELECT passed FROM robot_attempts WHERE student_id = ? AND task_id = 'under' ORDER BY id DESC LIMIT 1",
        (sid,)).fetchone()
    assert row[0] == 1
