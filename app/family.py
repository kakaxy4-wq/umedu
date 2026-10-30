"""Кабинет родителя со своим входом.

Родители живут в отдельных таблицах (parents, parent_sessions, parent_children), а не в users:
так им физически недоступны страницы ученика и преподавателя, и не нужна перестройка users.
Привязка к ребёнку — через секретную ссылку для родителей (/parent/<token>), которую выдаёт преподаватель.
"""
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, Request

from . import auth, config, students

COOKIE = "cq_family"
SESSION_DAYS = 60
CONSENT_VERSION = "2026-10-30"            # меняется вместе с текстом /privacy и /consent
# Согласие на ник в галерее — отдельное, редакция в app/account.py (GALLERY_CONSENT_VERSION).
MAX_CHILDREN = 6


def _now():
    return config.now().isoformat()


# ------------------------------------------------------------------ учётки и сессии
def signup(conn, name, login, password, consent):
    """Новая учётка родителя. Возвращает (id, None) или (None, текст ошибки). Вызывать внутри `with conn:`."""
    name, login = name.strip()[:60], login.strip().lower()
    if not name:
        return None, "Напишите, как к вам обращаться."
    if not students.valid_login(login):
        return None, "Логин — латинские буквы, цифры, точка, дефис или _, от 2 до 32 символов."
    if conn.execute("SELECT 1 FROM parents WHERE username = ?", (login,)).fetchone():
        return None, "Такой логин уже занят — придумайте другой."
    if len(password) < 8:
        return None, "Пароль — хотя бы 8 символов."
    if not consent:
        return None, "Без согласия на обработку данных кабинет завести нельзя."
    pid = conn.execute(
        "INSERT INTO parents (username, password_hash, display_name, consent_at, consent_version, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)", (login, auth.hash_password(password), name, _now(), CONSENT_VERSION, _now())).lastrowid
    return pid, None


def check_login(conn, login, password):
    row = conn.execute("SELECT id, password_hash FROM parents WHERE username = ? AND active = 1",
                       (login.strip().lower(),)).fetchone()
    return row["id"] if row and auth.verify_password(password, row["password_hash"]) else None


def create_session(conn, pid):
    token = secrets.token_urlsafe(32)
    with conn:
        conn.execute("DELETE FROM parent_sessions WHERE expires_at < ?", (_now(),))
        conn.execute("INSERT INTO parent_sessions (token_hash, parent_id, csrf, expires_at) VALUES (?, ?, ?, ?)",
                     (auth._token_hash(token), pid, secrets.token_urlsafe(24),
                      (config.now() + timedelta(days=SESSION_DAYS)).isoformat()))
    return token


def set_cookie(response, token):
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True,
                        secure=config.COOKIE_SECURE, samesite="lax")


def drop_session(conn, request, response):
    token = request.cookies.get(COOKIE)
    if token:
        with conn:
            conn.execute("DELETE FROM parent_sessions WHERE token_hash = ?", (auth._token_hash(token),))
    response.delete_cookie(COOKIE)


def load(request: Request, conn):
    """Родитель из cookie или None."""
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = conn.execute(
        "SELECT p.id, p.username, p.display_name, p.tg_chat_id, s.csrf FROM parent_sessions s JOIN parents p ON p.id = s.parent_id "
        "WHERE s.token_hash = ? AND s.expires_at > ? AND p.active = 1", (auth._token_hash(token), _now())).fetchone()
    return dict(row) if row else None


def touch(conn, pid):
    """Последний вход родителя — не чаще раза в 5 минут. Нужен, чтобы через год удалить пустой кабинет."""
    now = config.now()
    row = conn.execute("SELECT last_seen_at FROM parents WHERE id = ?", (pid,)).fetchone()
    if row and row[0]:
        try:
            seen = datetime.fromisoformat(row[0])
            if seen.tzinfo is None:
                seen = seen.replace(tzinfo=now.tzinfo)
            if now - seen < timedelta(minutes=5):
                return
        except ValueError:
            pass
    with conn:
        conn.execute("UPDATE parents SET last_seen_at = ? WHERE id = ?", (now.isoformat(timespec="seconds"), pid))


def check_csrf(parent, token):
    if not token or not hmac.compare_digest(str(token), parent["csrf"]):
        raise HTTPException(403, "Устаревшая форма. Обновите страницу и попробуйте ещё раз.")


# ------------------------------------------------------------------ дети
def link(conn, pid, sid):
    """Привязать ребёнка. Возвращает текст ошибки или None. Вызывать внутри `with conn:`."""
    if conn.execute("SELECT 1 FROM parent_children WHERE parent_id = ? AND student_id = ?", (pid, sid)).fetchone():
        return None
    if conn.execute("SELECT COUNT(*) FROM parent_children WHERE parent_id = ?", (pid,)).fetchone()[0] >= MAX_CHILDREN:
        return "К одному кабинету можно привязать не больше %d детей." % MAX_CHILDREN
    conn.execute("INSERT INTO parent_children (parent_id, student_id, created_at) VALUES (?, ?, ?)", (pid, sid, _now()))
    return None


def unlink(conn, pid, sid):
    conn.execute("DELETE FROM parent_children WHERE parent_id = ? AND student_id = ?", (pid, sid))


def children(conn, pid):
    return [dict(r) for r in conn.execute(
        "SELECT u.* FROM parent_children c JOIN users u ON u.id = c.student_id "
        "WHERE c.parent_id = ? AND u.active = 1 AND u.role = 'student' ORDER BY c.created_at", (pid,))]


def child(conn, pid, sid):
    """Ребёнок этого родителя или 404 — чужих детей не видно даже по прямой ссылке."""
    row = conn.execute(
        "SELECT u.* FROM parent_children c JOIN users u ON u.id = c.student_id "
        "WHERE c.parent_id = ? AND c.student_id = ? AND u.active = 1 AND u.role = 'student'", (pid, sid)).fetchone()
    if not row:
        raise HTTPException(404, "Такого ребёнка нет в вашем кабинете.")
    return dict(row)


def parents_of(conn, sid):
    """Для преподавателя: кто из родителей привязан к ученику."""
    return [dict(r) for r in conn.execute(
        "SELECT p.id, p.username, p.display_name, c.created_at FROM parent_children c JOIN parents p ON p.id = c.parent_id "
        "WHERE c.student_id = ? ORDER BY c.created_at", (sid,))]


def by_token(conn, token):
    st = students.by_parent_token(conn, token)
    if not st:
        raise HTTPException(404, "Ссылка устарела. Попросите у преподавателя новую.")
    return st
