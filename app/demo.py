"""Демо-класс стенда: ученики, родитель и попытки за две недели.

Команда `python manage.py seed_demo` вызывает seed_demo. Без CQ_STAGE=1 функция
сразу отказывается и в базу ничего не пишет — на проде, КодКвесте и ХимЛабе её запускать нельзя.
Повторный запуск на стенде тоже ничего не меняет: пароли и попытки остаются как после первого раза.
"""
import json
from datetime import timedelta
from pathlib import Path

from . import auth, config, family, students
from . import knowledge as kn
from .db import get_setting, set_setting

EXAM_ID = "oge-math-2026"
MARKER = "demo_seeded"
CLASS_NAME = "9 класс"
ORG_NAME = "Стенд"
# номера с коротким ответом: попытки крутятся по кругу, чтобы в классе были и сильные, и слабые
TASKS = (6, 7, 8, 9, 10)
# логин → (имя, пароль). Пароли фиксированные и только для стенда, их же пишет документация.
STUDENTS = {
    "demo": ("Аня", "demo-anya"),
    "demo-misha": ("Миша", "demo-misha"),
    "demo-kate": ("Катя", "demo-kate"),
}
PARENT = ("demo-parent", "Родитель демо", "demo-parent")
TEACHER = ("teacher", "Преподаватель", "demo-teacher")
# доля верных ответов: у Кати разрыв с целью большой, она вверху списка класса
RATES = {"demo": 0.8, "demo-misha": 0.5, "demo-kate": 0.2}
GOALS = {"demo": 4, "demo-misha": 4, "demo-kate": 5}


class DemoRefused(RuntimeError):
    """Стенд не включён: базу не трогаем."""


def seed_demo(conn):
    """Создаёт демо-класс или сообщает, что он уже есть. Возвращает словарь для печати."""
    if not config.STAGE:
        raise DemoRefused("seed_demo только для тестового стенда (CQ_STAGE=1). База не изменена.")
    if get_setting(conn, MARKER) == "1":
        return _report(conn, created=False)
    with conn:
        teacher_id = _ensure_teacher(conn)
        ids = {login: _ensure_student(conn, login) for login in STUDENTS}
        _ensure_class(conn, teacher_id, list(ids.values()))
        _ensure_parent(conn, ids["demo"])
        _ensure_token(conn, ids["demo"])
        if conn.execute("SELECT COUNT(*) FROM skill_attempt WHERE student_id = ?", (ids["demo"],)).fetchone()[0] == 0:
            _attempts(conn, ids)
        set_setting(conn, MARKER, "1")
    return _report(conn, created=True)


def _ensure_teacher(conn):
    row = conn.execute("SELECT id FROM users WHERE role = 'teacher' ORDER BY id LIMIT 1").fetchone()
    if row:
        return row["id"]
    login, name, password = TEACHER
    return conn.execute(
        "INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, 'teacher', ?)",
        (login, auth.hash_password(password), name)).lastrowid


def _ensure_student(conn, login):
    row = conn.execute("SELECT id FROM users WHERE username = ?", (login,)).fetchone()
    if row:
        return row["id"]
    name, password = STUDENTS[login]
    sid = students.create_student(conn, login, name, password)
    conn.execute("UPDATE users SET grade = 9 WHERE id = ?", (sid,))
    return sid


def _ensure_class(conn, teacher_id, sids):
    now = config.now().isoformat(timespec="seconds")
    row = conn.execute("SELECT id FROM class WHERE teacher_id = ? AND name = ?", (teacher_id, CLASS_NAME)).fetchone()
    if row:
        class_id = row["id"]
    else:
        org = conn.execute("SELECT id FROM org WHERE name = ?", (ORG_NAME,)).fetchone()
        org_id = org["id"] if org else conn.execute(
            "INSERT INTO org (name, created_at) VALUES (?, ?)", (ORG_NAME, now)).lastrowid
        class_id = conn.execute(
            "INSERT INTO class (org_id, name, teacher_id, created_at) VALUES (?, ?, ?, ?)",
            (org_id, CLASS_NAME, teacher_id, now)).lastrowid
    for sid in sids:
        conn.execute(
            "INSERT INTO class_member (class_id, student_id, joined_at) VALUES (?, ?, ?) "
            "ON CONFLICT(class_id, student_id) DO NOTHING",
            (class_id, sid, now))
    return class_id


def _ensure_parent(conn, sid):
    login, name, password = PARENT
    row = conn.execute("SELECT id FROM parents WHERE username = ?", (login,)).fetchone()
    if row:
        pid = row["id"]
    else:
        pid, err = family.signup(conn, name, login, password, True)
        if err:
            raise RuntimeError(err)
    err = family.link(conn, pid, sid)
    if err:
        raise RuntimeError(err)
    return pid


def _ensure_token(conn, sid):
    row = conn.execute("SELECT parent_token FROM users WHERE id = ?", (sid,)).fetchone()
    if row["parent_token"]:
        return row["parent_token"]
    return students.new_parent_token(conn, sid)


def _exam_date():
    path = Path(__file__).resolve().parent / "content" / "schedule-2027.json"
    dates = json.loads(path.read_text(encoding="utf-8"))["dates"].get("oge-math") or []
    return dates[0] if dates else "2027-06-02"


def _attempts(conn, ids):
    """По одной попытке в каждый из последних 14 дней — график прогресса и лента родителя не пустые."""
    today, exam_date = config.today(), _exam_date()
    for login, sid in ids.items():
        kn.enroll(conn, sid, EXAM_ID, GOALS[login], exam_date)
        full = int(RATES[login] * 10)
        for offset in range(14):
            day = today - timedelta(days=13 - offset)
            score = 1.0 if (offset % 10) < full else 0.0
            kn.record(conn, sid, EXAM_ID, TASKS[offset % len(TASKS)], score, day)
            kn.log_forecast(conn, sid, EXAM_ID, day)
            conn.execute(
                "INSERT INTO xp_events (student_id, amount, reason, kind, ref, created_at) VALUES (?, 10, ?, 'task', 'demo', ?)",
                (sid, "Демо: задание", day.isoformat() + "T12:00:00"))


def _report(conn, created):
    span = conn.execute("SELECT MIN(day), MAX(day), COUNT(*) FROM skill_attempt").fetchone()
    teacher = conn.execute("SELECT username FROM users WHERE role = 'teacher' ORDER BY id LIMIT 1").fetchone()
    return {
        "created": created,
        "teacher": teacher["username"] if teacher else "",
        "students": list(STUDENTS),
        "parent": PARENT[0],
        "passwords": {
            TEACHER[0]: TEACHER[2],
            **{login: password for login, (_name, password) in STUDENTS.items()},
            PARENT[0]: PARENT[2],
        },
        "first_day": span[0],
        "last_day": span[1],
        "attempts": span[2],
        "members": conn.execute("SELECT COUNT(*) FROM class_member").fetchone()[0],
    }
