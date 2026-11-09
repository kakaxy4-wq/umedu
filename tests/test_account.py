"""Удаление аккаунта, автоудаление через год и ник в галерее — только с согласием."""
import re
import sqlite3
import sys
from datetime import timedelta
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
    from fastapi.testclient import TestClient
    import manage
    from app import auth
    from app.db import connect, init_db
    from app.main import app
    auth._failed.clear()
    init_db()
    conn = connect()
    manage.create_user(conn, "teacher", "teacher", "Папа", "secret123")
    manage.create_user(conn, "student", "student", "Миша", "secret123")
    conn.close()
    with TestClient(app) as c:
        yield c


def _csrf(page):
    return re.search(r'name="csrf" content="([^"]+)"', page).group(1)


def _fam_csrf(page):
    return re.search(r'name="csrf" value="([^"]+)"', page).group(1)


def _login(client, username, password="secret123"):
    client.cookies.clear()
    r = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
    assert r.status_code == 303, r.text
    return _csrf(client.get("/").text)


def _age_student(conn, sid, when):
    from app import account
    with conn:
        conn.execute("UPDATE users SET created_at = ?, last_seen_at = ? WHERE id = ?", (when, when, sid))
        for table, col in account.ACTIVITY:
            conn.execute("UPDATE %s SET %s = ? WHERE student_id = ?" % (table, col), (when, sid))


def _project(client, csrf, title, public=True):
    data = {"title": title, "code": "print(1)", "description": "работа", "csrf": csrf}
    if public:
        data["public"] = "1"
    assert client.post("/portfolio/save", data=data, follow_redirects=False).status_code == 303


def test_student_deletes_account_and_public_page(client, tmp_path):
    """Ученик с 14 лет удаляет аккаунт из кабинета и с публичной страницы. Файлы и прогресс пропадают,
    копия базы — нет."""
    from app import account, config
    from app.db import connect
    import manage
    csrf = _login(client, "student")
    page = client.get("/account").text
    assert "Удалить аккаунт" in page and 'name="gallery"' in page
    _project(client, csrf, "Ракета")
    conn = connect()
    sid = conn.execute("SELECT id FROM users WHERE username = 'student'").fetchone()[0]
    upload = config.UPLOAD_DIR / "note.txt"
    upload.write_text("секрет домашки", encoding="utf-8")
    backup = tmp_path / "backups"
    backup.mkdir()
    (backup / "codequest-old.db").write_text("копия с данными", encoding="utf-8")
    with conn:
        conn.execute("UPDATE projects SET file_path = 'note.txt' WHERE student_id = ?", (sid,))
        conn.execute("INSERT INTO skill_attempt (student_id, exam_id, task_key, score, day) VALUES (?, ?, '1', 1, ?)",
                     (sid, "oge-inf-2026", config.today().isoformat()))
        conn.execute("INSERT INTO events (user_id, role, kind, route, created_at) VALUES (?, 'student', 'view', '/x', ?)",
                     (sid, config.now().isoformat()))
        conn.execute("INSERT INTO exam_enroll (student_id, exam_id, created_at) VALUES (?, 'oge-inf-2026', ?)",
                     (sid, config.now().isoformat()))
    # без галочки и с чужим паролем аккаунт на месте
    keep = {"password": "secret123", "csrf": csrf}
    assert "галочку" in client.post("/account/delete", data=keep).text
    assert "Неверный пароль" in client.post("/account/delete", data=dict(keep, confirm="1", password="nope")).text
    assert conn.execute("SELECT 1 FROM users WHERE id = ?", (sid,)).fetchone()
    # преподаватель этой формой не удаляется
    client.cookies.clear()
    ghost = client.post("/delete-account", data={"who": "student", "username": "teacher", "password": "secret123",
                                                 "confirm": "1"})
    assert "Неверный логин" in ghost.text
    assert conn.execute("SELECT 1 FROM users WHERE username = 'teacher'").fetchone()
    # публичная страница объясняет, что удаляем и что оставляем, и удаляет без кабинета
    client.cookies.clear()
    public = client.get("/delete-account")
    assert public.status_code == 200
    assert "без приложения" in public.text and "30 дней" in public.text and "180" in public.text
    assert "/privacy" in public.text
    manage.create_user(conn, "student", "solo", "Соло", "secret123")
    gone = client.post("/delete-account", data={"who": "student", "username": "solo", "password": "secret123",
                                                "confirm": "1"})
    assert "Аккаунт удалён" in gone.text
    assert not conn.execute("SELECT 1 FROM users WHERE username = 'solo'").fetchone()
    # свой кабинет
    csrf = _login(client, "student")
    done = client.post("/account/delete", data={"password": "secret123", "confirm": "1", "csrf": csrf})
    assert "Аккаунт удалён" in done.text
    assert not conn.execute("SELECT 1 FROM users WHERE id = ?", (sid,)).fetchone()
    assert not conn.execute("SELECT 1 FROM projects WHERE student_id = ?", (sid,)).fetchone()
    assert not conn.execute("SELECT 1 FROM skill_attempt WHERE student_id = ?", (sid,)).fetchone()
    assert not conn.execute("SELECT 1 FROM events WHERE user_id = ?", (sid,)).fetchone()
    assert not conn.execute("SELECT 1 FROM exam_enroll WHERE student_id = ?", (sid,)).fetchone()
    assert not upload.exists()
    assert (backup / "codequest-old.db").read_text(encoding="utf-8") == "копия с данными"
    assert client.get("/", follow_redirects=False).headers["location"] == "/login"
    assert client.get("/gallery").status_code == 200


def test_minor_deleted_only_by_parent(client, monkeypatch):
    """Ребёнка младше 14 лет не удаляет ни он сам, ни публичная форма с его паролем. Удаляет родитель."""
    from app import config, family, students
    from app.db import connect
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    students._signups.clear()
    client.cookies.clear()
    form = {"pname": "Мама", "plogin": "mama", "ppassword": "dlinnyi-parol", "name": "Петя", "grade": 7,
            "login": "petya", "password": "kot-luna-27", "consent": "1"}
    assert client.post("/family/new-child", data=form, follow_redirects=False).status_code == 303
    conn = connect()
    kid = conn.execute("SELECT * FROM users WHERE username = 'petya'").fetchone()
    assert kid["minor"] == 1
    pid = conn.execute("SELECT id FROM parents WHERE username = 'mama'").fetchone()[0]
    # второй родитель: ребёнка не сносим вместе с первым, пока есть другой
    with conn:
        other, err = family.signup(conn, "Папа", "papa", "dlinnyi-parol", True)
        assert not err
        assert family.link(conn, other, kid["id"]) is None
    csrf = _login(client, "petya", "kot-luna-27")
    account = client.get("/account").text
    assert 'name="gallery"' not in account
    assert "родитель" in account.lower()
    assert client.post("/account/gallery", data={"gallery": "1", "csrf": csrf}).status_code == 403
    blocked = client.post("/account/delete", data={"password": "kot-luna-27", "confirm": "1", "csrf": csrf})
    assert "меньше 14" in blocked.text
    assert conn.execute("SELECT 1 FROM users WHERE username = 'petya'").fetchone()
    client.cookies.clear()
    denied = client.post("/delete-account", data={"who": "student", "username": "petya", "password": "kot-luna-27",
                                                  "confirm": "1"})
    assert "младше 14" in denied.text
    assert conn.execute("SELECT 1 FROM users WHERE username = 'petya'").fetchone()
    # родитель удаляет свой кабинет — Петя остаётся, потому что есть второй родитель
    client.post("/family/login", data={"username": "mama", "password": "dlinnyi-parol"})
    page = client.get("/family/delete").text
    assert "Петя" not in page and "другого родителя" in page
    assert "галочку" in client.post("/family/delete", data={"password": "dlinnyi-parol", "csrf": _fam_csrf(page)}).text
    done = client.post("/family/delete", data={"password": "dlinnyi-parol", "confirm": "1", "csrf": _fam_csrf(page)})
    assert "удалён" in done.text
    assert not conn.execute("SELECT 1 FROM parents WHERE username = 'mama'").fetchone()
    assert conn.execute("SELECT 1 FROM users WHERE username = 'petya'").fetchone()
    assert conn.execute("SELECT 1 FROM parent_children WHERE parent_id = ? AND student_id = ?",
                        (other, kid["id"])).fetchone()
    # оставшийся родитель удаляет ребёнка
    client.cookies.clear()
    client.post("/family/login", data={"username": "papa", "password": "dlinnyi-parol"})
    page = client.get("/family/child/%d/delete" % kid["id"]).text
    assert "Петя" in page and "без восстановления" in page
    bad = client.post("/family/child/%d/delete" % kid["id"],
                      data={"password": "wrong-pass", "confirm": "1", "csrf": _fam_csrf(page)})
    assert "Неверный пароль" in bad.text
    ok = client.post("/family/child/%d/delete" % kid["id"],
                     data={"password": "dlinnyi-parol", "confirm": "1", "csrf": _fam_csrf(page)})
    assert "Петя" in ok.text and "удалён" in ok.text
    assert not conn.execute("SELECT 1 FROM users WHERE username = 'petya'").fetchone()
    assert not conn.execute("SELECT 1 FROM parent_children WHERE student_id = ?", (kid["id"],)).fetchone()
    assert conn.execute("SELECT 1 FROM parents WHERE id = ?", (other,)).fetchone()


def test_gallery_nickname_only_with_consent(client, monkeypatch):
    """Без согласия проект в галерее и на /p/… без автора. С 14 лет галочку ставит ученик, младше — только родитель."""
    from app import account, config, students
    from app.db import connect
    csrf = _login(client, "student")
    _project(client, csrf, "Ракета")
    conn = connect()
    row = conn.execute("SELECT slug FROM projects WHERE title = 'Ракета'").fetchone()
    client.cookies.clear()
    gallery = client.get("/gallery").text
    project = client.get("/p/%s" % row["slug"]).text
    assert "Ракета" in gallery and "автор" not in gallery and "Миша" not in gallery
    assert "Ракета" in project and "Миша" not in project
    # старая редакция согласия ник не показывает
    sid = conn.execute("SELECT id FROM users WHERE username = 'student'").fetchone()[0]
    with conn:
        conn.execute("UPDATE users SET gallery_ok = 1, gallery_consent_version = '1999-01-01', "
                     "gallery_consent_by = 'ученик', gallery_consent_at = '1999-01-01T00:00:00' WHERE id = ?", (sid,))
    assert "Миша" not in client.get("/gallery").text
    # ученик включает сам
    csrf = _login(client, "student")
    home = client.get("/account").text
    box = re.search(r'<input type="checkbox" name="gallery"[^>]*>', home)
    assert box and "checked" not in box.group(0)
    assert "10.1" in home and "/consent#gallery" in home
    client.post("/account/gallery", data={"gallery": "1", "csrf": csrf})
    saved = conn.execute("SELECT gallery_ok, gallery_consent_at, gallery_consent_version, gallery_consent_by "
                         "FROM users WHERE id = ?", (sid,)).fetchone()
    assert saved["gallery_ok"] == 1
    assert saved["gallery_consent_version"] == account.GALLERY_CONSENT_VERSION
    assert saved["gallery_consent_by"] == "ученик"
    assert saved["gallery_consent_at"][:10] == config.today().isoformat()
    monkeypatch.setattr(config, "UMEDU2", True)
    assert 'name="gallery"' in client.get("/u2/me").text and "Показывать мой ник" in client.get("/u2/me").text
    client.cookies.clear()
    assert "автор: Миша" in client.get("/gallery").text
    assert "автор: Миша" in client.get("/p/%s" % row["slug"]).text
    # отзыв — автора снова нет, запись согласия стёрта
    csrf = _login(client, "student")
    client.post("/account/gallery", data={"csrf": csrf})
    saved = conn.execute("SELECT gallery_ok, gallery_consent_at, gallery_consent_version, gallery_consent_by "
                         "FROM users WHERE id = ?", (sid,)).fetchone()
    assert saved["gallery_ok"] == 0 and not saved["gallery_consent_at"]
    assert saved["gallery_consent_version"] == "" and saved["gallery_consent_by"] == ""
    client.cookies.clear()
    assert "Миша" not in client.get("/gallery").text
    # родитель ученика с 14 лет галочку не ставит
    from app import family
    with conn:
        pid, err = family.signup(conn, "Мама", "mama", "dlinnyi-parol", True)
        assert family.link(conn, pid, sid) is None
    client.post("/family/login", data={"username": "mama", "password": "dlinnyi-parol"})
    fam_csrf = _fam_csrf(client.get("/family").text)
    assert client.post("/family/child/%d/gallery" % sid, data={"gallery": "1", "csrf": fam_csrf}).status_code == 403
    assert client.get("/family/child/%d/delete" % sid).status_code == 403
    assert conn.execute("SELECT gallery_ok FROM users WHERE id = ?", (sid,)).fetchone()[0] == 0
    # младше 14: галочки нет ни в кабинете ученика, ни на /u2/me; ставит родитель
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "OPEN_SIGNUP", True)
    monkeypatch.setattr(config, "UMEDU2", True)
    students._signups.clear()
    client.cookies.clear()
    child = {"pname": "Бабушка", "plogin": "baba", "ppassword": "dlinnyi-parol", "name": "Оля", "grade": 7,
             "login": "olya", "password": "kot-luna-27", "consent": "1"}
    assert client.post("/family/new-child", data=child, follow_redirects=False).status_code == 303
    kid = conn.execute("SELECT id FROM users WHERE username = 'olya'").fetchone()[0]
    kcsrf = _login(client, "olya", "kot-luna-27")
    _project(client, kcsrf, "Кораблик")
    assert 'name="gallery"' not in client.get("/account").text
    me = client.get("/u2/me").text
    assert 'name="gallery"' not in me and "родитель" in me.lower()
    client.cookies.clear()
    assert "Оля" not in client.get("/gallery").text
    client.post("/family/login", data={"username": "baba", "password": "dlinnyi-parol"})
    card = client.get("/family/child/%d" % kid).text
    assert 'name="gallery"' in card and "10.1" in card
    client.post("/family/child/%d/gallery" % kid, data={"gallery": "1", "csrf": _fam_csrf(card)})
    grant = conn.execute("SELECT gallery_consent_by, gallery_consent_version, gallery_ok FROM users WHERE id = ?",
                         (kid,)).fetchone()
    assert grant["gallery_ok"] == 1 and grant["gallery_consent_by"] == "родитель"
    assert grant["gallery_consent_version"] == account.GALLERY_CONSENT_VERSION
    client.cookies.clear()
    assert "автор: Оля" in client.get("/gallery").text
    slug = conn.execute("SELECT slug FROM projects WHERE title = 'Кораблик'").fetchone()[0]
    assert "автор: Оля" in client.get("/p/%s" % slug).text
    client.post("/family/login", data={"username": "baba", "password": "dlinnyi-parol"})
    client.post("/family/child/%d/gallery" % kid, data={"csrf": _fam_csrf(client.get("/family/child/%d" % kid).text)})
    client.cookies.clear()
    assert "Оля" not in client.get("/p/%s" % slug).text
    # политика и согласие рассказывают про галерею и удаление
    privacy = client.get("/privacy").text
    consent = client.get("/consent").text
    assert "/delete-account" in privacy and "10.1" in privacy and 'href="/consent#gallery"' in privacy
    assert 'id="gallery"' in consent and "10.1" in consent and "/delete-account" in consent
    assert "30 дней" in privacy and "180" in privacy


def test_purge_inactive_dry_run_then_apply(client):
    """Год без входа и занятий: dry-run никого не трогает, --apply удаляет учеников и пустой кабинет родителя.
    Преподавателя и тех, у кого есть недавнее занятие или ребёнок, не трогает."""
    from app import account, config, family
    from app.db import connect
    import manage
    conn = connect()
    today = config.today()
    old = (today - timedelta(days=400)).isoformat()
    year = (today - timedelta(days=365)).isoformat()
    almost = (today - timedelta(days=364)).isoformat()
    misha = conn.execute("SELECT id FROM users WHERE username = 'student'").fetchone()[0]
    teacher = conn.execute("SELECT id FROM users WHERE username = 'teacher'").fetchone()[0]
    manage.create_user(conn, "student", "year", "Год", "secret123")
    manage.create_user(conn, "student", "almost", "Почти", "secret123")
    manage.create_user(conn, "student", "kid", "Малыш", "secret123")
    year_id = conn.execute("SELECT id FROM users WHERE username = 'year'").fetchone()[0]
    almost_id = conn.execute("SELECT id FROM users WHERE username = 'almost'").fetchone()[0]
    kid_id = conn.execute("SELECT id FROM users WHERE username = 'kid'").fetchone()[0]
    _age_student(conn, misha, old)
    _age_student(conn, year_id, year)
    _age_student(conn, almost_id, almost)
    _age_student(conn, kid_id, old)
    with conn:
        conn.execute("UPDATE users SET minor = 1, created_at = ?, last_seen_at = ? WHERE id = ?", (old, old, kid_id))
        conn.execute("UPDATE users SET created_at = ?, last_seen_at = ? WHERE id = ?", (old, old, teacher))
        pid, err = family.signup(conn, "Старая", "oldparent", "dlinnyi-parol", True)
        assert not err
        conn.execute("UPDATE parents SET created_at = ?, consent_at = ?, last_seen_at = NULL WHERE id = ?", (old, old, pid))
        fresh, err = family.signup(conn, "Живая", "fresh", "dlinnyi-parol", True)
        assert not err
        assert family.link(conn, fresh, kid_id) is None
    plan = account.purge_inactive(conn, dry_run=True)
    assert plan["dry_run"] is True
    students = {s["username"] for s in plan["students"]}
    parents = {p["username"] for p in plan["parents"]}
    assert students == {"student", "year", "kid"}
    assert "almost" not in students and "teacher" not in students
    assert parents == {"oldparent"}
    assert "fresh" not in parents
    assert conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0] == 4
    # команда без --apply тоже ничего не стирает
    manage.cmd_purge(apply=False)
    assert conn.execute("SELECT 1 FROM users WHERE username = 'student'").fetchone()
    done = account.purge_inactive(conn, dry_run=False)
    assert done["dry_run"] is False
    left = {r[0] for r in conn.execute("SELECT username FROM users")}
    assert left == {"teacher", "almost"}
    assert not conn.execute("SELECT 1 FROM parents WHERE username = 'oldparent'").fetchone()
    assert conn.execute("SELECT 1 FROM parents WHERE username = 'fresh'").fetchone()
    assert not conn.execute("SELECT 1 FROM users WHERE username = 'kid'").fetchone()
    again = account.purge_inactive(conn, dry_run=True)
    assert again["students"] == [] and again["parents"] == []


def test_old_database_gets_new_columns(tmp_path, monkeypatch):
    """Колонки добавляются к уже существующей базе при старте, старые строки не пропадают."""
    from app import config
    from app.db import connect, init_db
    db = tmp_path / "old.db"
    raw = sqlite3.connect(db)
    raw.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, "
                "role TEXT, display_name TEXT, consent TEXT NOT NULL DEFAULT '')")
    raw.execute("INSERT INTO users (username, password_hash, role, display_name, consent) VALUES (?, ?, ?, ?, ?)",
                ("kid", "x", "student", "Петя", "2026-10-29 · 2026-10-29T12:00:00 · родитель #3"))
    raw.execute("INSERT INTO users (username, password_hash, role, display_name, consent) VALUES (?, ?, ?, ?, ?)",
                ("self", "x", "student", "Аня", "2026-10-29 · 2026-10-29T12:00:00"))
    raw.commit()
    raw.close()
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "up")
    init_db()
    conn = connect()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    assert {"minor", "gallery_ok", "gallery_consent_at", "gallery_consent_version", "gallery_consent_by"} <= cols
    kid = conn.execute("SELECT display_name, minor, gallery_ok FROM users WHERE username = 'kid'").fetchone()
    assert kid["display_name"] == "Петя" and kid["minor"] == 1 and kid["gallery_ok"] == 0
    assert conn.execute("SELECT minor FROM users WHERE username = 'self'").fetchone()["minor"] == 0
    assert "last_seen_at" in {r[1] for r in conn.execute("PRAGMA table_info(parents)")}
    conn.close()
