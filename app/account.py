"""Удаление аккаунта и согласие на ник в галерее.

Удаление полное, не архив: строка ученика или родителя и всё, что на неё ссылается
(ответы, прогресс, проекты, файлы, согласия, сессии). Каскад в схеме это делает сам.

Дольше аккаунта специально остаются только:
- резервные копии базы (manage.py backup, последние 30 штук, по политике — до 30 дней);
- журналы веб-сервера (IP, время, адрес страницы, User-Agent) — их ведёт journald, не приложение;
- журнал действий (events) этого человека удаляется вместе с аккаунтом, а пока аккаунт жив — не дольше 180 дней.

Неактивный ученик удаляется через год после последнего входа или занятия.
Кабинет родителя без детей — через год после последнего входа родителя.
"""
import asyncio
import logging
import os
from datetime import date, timedelta

from . import auth, config, students
from .db import connect, get_setting, set_setting

log = logging.getLogger("codequest.account")

# Редакция текста /consent#gallery. Меняется вместе с этим текстом, отдельно от CONSENT_VERSION:
# старая галочка после смены текста больше не показывает ник, пока её не поставят снова.
GALLERY_CONSENT_VERSION = "2026-10-30"
BY_STUDENT = "ученик"
BY_PARENT = "родитель"
INACTIVE_DAYS = 365

# Откуда берём «последнее занятие». Имена таблиц — константа, не ввод пользователя.
ACTIVITY = (
    ("xp_events", "created_at"),
    ("task_attempts", "created_at"),
    ("skill_attempt", "day"),
    ("ru_attempts", "created_at"),
    ("oge_drill", "created_at"),
    ("robot_attempts", "created_at"),
    ("submissions", "created_at"),
    ("projects", "updated_at"),
    ("check_results", "finished_at"),
    ("lesson_state", "opened_at"),
    ("lesson_state", "done_at"),
    ("check_state", "opened_at"),
    ("check_state", "started_at"),
    ("daily", "day"),
    ("trainer_runs", "created_at"),
    ("bot_fights", "created_at"),
    ("certificates", "issued_at"),
    ("forecast_log", "day"),
    ("exam_enroll", "created_at"),
    ("chem_attempts", "created_at"),
    ("chem_lessons", "starts_at"),
    ("chem_hw", "created_at"),
    ("notices", "created_at"),
    ("snippets", "updated_at"),
)

_FILE_SQL = (
    "SELECT image_path FROM projects WHERE student_id = ? AND image_path IS NOT NULL AND image_path != ''",
    "SELECT file_path FROM projects WHERE student_id = ? AND file_path IS NOT NULL AND file_path != ''",
    "SELECT file_path FROM submissions WHERE student_id = ? AND file_path IS NOT NULL AND file_path != ''",
    "SELECT file_path FROM chem_hw WHERE student_id = ? AND file_path IS NOT NULL AND file_path != ''",
    "SELECT file_path FROM chem_lesson_files WHERE student_id = ? AND file_path IS NOT NULL AND file_path != ''",
    "SELECT f.file_path FROM chem_hw_files f JOIN chem_hw h ON h.id = f.hw_id "
    "WHERE h.student_id = ? AND f.file_path IS NOT NULL AND f.file_path != ''",
    "SELECT f.file_path FROM chem_mock_files f JOIN chem_mocks m ON m.id = f.mock_id "
    "WHERE m.student_id = ? AND f.file_path IS NOT NULL AND f.file_path != ''",
)

_PUBLIC = (
    "SELECT p.*, CASE WHEN u.gallery_ok = 1 AND u.gallery_consent_version = ? "
    "THEN u.display_name ELSE '' END AS author "
    "FROM projects p JOIN users u ON u.id = p.student_id "
    "WHERE p.public = 1 AND u.active = 1"
)


def purge_enabled():
    return os.environ.get("CQ_PURGE_INACTIVE", "1") != "0"


def granted(st):
    """Согласие на ник действует: галочка включена и текст согласия той же редакции."""
    return bool(st and st["gallery_ok"] and st["gallery_consent_version"] == GALLERY_CONSENT_VERSION)


def set_gallery(conn, sid, on, by):
    """Записать или снять согласие. Вызывать для ученика. by — «ученик» или «родитель»."""
    if by not in (BY_STUDENT, BY_PARENT):
        raise ValueError(by)
    with conn:
        if on:
            conn.execute(
                "UPDATE users SET gallery_ok = 1, gallery_consent_at = ?, gallery_consent_version = ?, "
                "gallery_consent_by = ? WHERE id = ? AND role = 'student'",
                (config.now().isoformat(timespec="seconds"), GALLERY_CONSENT_VERSION, by, sid))
        else:
            conn.execute(
                "UPDATE users SET gallery_ok = 0, gallery_consent_at = NULL, gallery_consent_version = '', "
                "gallery_consent_by = '' WHERE id = ? AND role = 'student'", (sid,))


def public_projects(conn):
    return conn.execute(_PUBLIC + " ORDER BY p.updated_at DESC", (GALLERY_CONSENT_VERSION,)).fetchall()


def public_project(conn, slug):
    return conn.execute(_PUBLIC + " AND p.slug = ?", (GALLERY_CONSENT_VERSION, slug)).fetchone()


def password_ok(stored, password):
    return bool(stored and password and auth.verify_password(password, stored))


def student_login(conn, login):
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? AND role = 'student' AND active = 1",
        (login.strip().lower(),)).fetchone()
    return dict(row) if row else None


def parent_login(conn, login):
    row = conn.execute("SELECT * FROM parents WHERE username = ? AND active = 1",
                       (login.strip().lower(),)).fetchone()
    return dict(row) if row else None


# ------------------------------------------------------------------ удаление
def _file_names(conn, sid):
    names = []
    for sql in _FILE_SQL:
        names.extend(r[0] for r in conn.execute(sql, (sid,)))
    return names


def _unlink(name):
    if not name:
        return
    root = config.UPLOAD_DIR.resolve()
    path = (root / name).resolve()
    if path == root or root not in path.parents or not path.is_file():
        return
    try:
        path.unlink()
    except OSError:
        log.warning("файл загрузки не удалился")


def delete_student(conn, sid):
    """Полностью удалить ученика. False, если это не ученик. Преподавателя не трогает."""
    row = conn.execute("SELECT role FROM users WHERE id = ?", (sid,)).fetchone()
    if not row or row["role"] != "student":
        return False
    files = _file_names(conn, sid)
    with conn:
        conn.execute("UPDATE users SET current_student_id = NULL WHERE current_student_id = ?", (sid,))
        deleted = conn.execute("DELETE FROM users WHERE id = ? AND role = 'student'", (sid,)).rowcount
    if not deleted:
        return False
    for name in files:
        _unlink(name)
    return True


def exclusive_minors(conn, pid):
    """Дети младше 14, которых удаляем вместе с этим родителем: другого родителя у них нет."""
    rows = conn.execute(
        "SELECT u.* FROM parent_children c JOIN users u ON u.id = c.student_id "
        "WHERE c.parent_id = ? AND u.minor = 1 AND u.role = 'student'", (pid,)).fetchall()
    out = []
    for row in rows:
        others = conn.execute(
            "SELECT COUNT(*) FROM parent_children WHERE student_id = ? AND parent_id != ?",
            (row["id"], pid)).fetchone()[0]
        if not others:
            out.append(dict(row))
    return out


def delete_parent(conn, pid):
    """Удалить кабинет родителя. Детей младше 14 без другого родителя удаляет тоже.
    Возвращает список удалённых детей или None, если родителя нет."""
    if not conn.execute("SELECT 1 FROM parents WHERE id = ?", (pid,)).fetchone():
        return None
    kids = exclusive_minors(conn, pid)
    for st in kids:
        delete_student(conn, st["id"])
    with conn:
        conn.execute("DELETE FROM parents WHERE id = ?", (pid,))
    return kids


# ------------------------------------------------------------------ год без занятий
def as_date(value):
    if not value:
        return None
    text = str(value).strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _latest(dates):
    found = [d for d in dates if d]
    return max(found) if found else None


def student_last_activity(conn, st):
    dates = [as_date(st["created_at"]), as_date(st["last_seen_at"])]
    sid = st["id"]
    for table, col in ACTIVITY:
        row = conn.execute("SELECT MAX(%s) FROM %s WHERE student_id = ?" % (col, table), (sid,)).fetchone()
        dates.append(as_date(row[0] if row else None))
    return _latest(dates)


def parent_last_activity(parent):
    return _latest([as_date(parent["created_at"]), as_date(parent["last_seen_at"]), as_date(parent["consent_at"])])


def _inactive(last, today):
    # Дату не разобрали — не удаляем: лучше оставить аккаунт, чем стереть живого ученика.
    return bool(last) and (today - last).days >= INACTIVE_DAYS


def _plan(conn, today):
    students_out = []
    for st in students.list_students(conn, include_archived=True):
        last = student_last_activity(conn, st)
        if _inactive(last, today):
            students_out.append({"id": st["id"], "username": st["username"], "display_name": st["display_name"],
                                 "last": last.isoformat(), "minor": st["minor"]})
    going = {s["id"] for s in students_out}
    parents_out = []
    for p in conn.execute("SELECT * FROM parents").fetchall():
        linked = [r[0] for r in conn.execute("SELECT student_id FROM parent_children WHERE parent_id = ?", (p["id"],))]
        if any(sid not in going for sid in linked):
            continue
        last = parent_last_activity(p)
        if _inactive(last, today):
            parents_out.append({"id": p["id"], "username": p["username"], "display_name": p["display_name"],
                                "last": last.isoformat() if last else ""})
    return students_out, parents_out


def purge_inactive(conn, dry_run=True, today=None):
    """Удалить неактивных. По умолчанию только план: база не меняется, пока dry_run=False.

    Возвращает {'dry_run', 'students', 'parents'} — кого удалили или удалили бы.
    """
    today = today or config.today()
    planned_students, planned_parents = _plan(conn, today)
    if dry_run:
        return {"dry_run": True, "students": planned_students, "parents": planned_parents}
    for st in planned_students:
        delete_student(conn, st["id"])
    for p in planned_parents:
        if conn.execute("SELECT 1 FROM parents WHERE id = ?", (p["id"],)).fetchone():
            delete_parent(conn, p["id"])
    return {"dry_run": False, "students": planned_students, "parents": planned_parents}


def run_scheduled():
    """Один проход в сутки. Повторный запуск в тот же день ничего не делает."""
    if not purge_enabled():
        return None
    conn = connect()
    try:
        today = config.today().isoformat()
        if get_setting(conn, "purge_inactive_on") == today:
            return None
        report = purge_inactive(conn, dry_run=False)
        with conn:
            set_setting(conn, "purge_inactive_on", today)
        log.info("неактивные аккаунты удалены: учеников %d, родителей %d",
                 len(report["students"]), len(report["parents"]))
        return report
    finally:
        conn.close()


async def scheduler():
    """Раз в час проверяем, не пора ли снять неактивных. Первый раз — не сразу, чтобы не мешать старту."""
    await asyncio.sleep(3600)
    while True:
        try:
            await asyncio.to_thread(run_scheduled)
        except Exception:
            log.exception("не удалось удалить неактивные аккаунты")
        await asyncio.sleep(3600)
