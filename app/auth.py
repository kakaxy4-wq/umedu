import hashlib
import hmac
import secrets
import time
from datetime import timedelta

from fastapi import Depends, HTTPException, Request

from . import config
from .db import get_db

COOKIE = "cq_session"
SESSION_DAYS = 30
_ITER = 240_000

# простая защита от перебора паролей: ip -> [времена неудачных попыток]
_failed = {}
MAX_FAILS = 10
FAIL_WINDOW = 15 * 60


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITER).hex()
    return "pbkdf2$%d$%s$%s" % (_ITER, salt, digest)


def verify_password(password, stored):
    try:
        _, iters, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters)).hex()
        return hmac.compare_digest(check, digest)
    except ValueError:
        return False


def _token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def too_many_fails(ip):
    now = time.time()
    attempts = [t for t in _failed.get(ip, []) if now - t < FAIL_WINDOW]
    _failed[ip] = attempts
    return len(attempts) >= MAX_FAILS


def register_fail(ip):
    _failed.setdefault(ip, []).append(time.time())


def create_session(conn, user_id):
    token = secrets.token_urlsafe(32)
    expires = (config.now() + timedelta(days=SESSION_DAYS)).isoformat()
    with conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (config.now().isoformat(),))
        conn.execute("INSERT INTO sessions (token_hash, user_id, csrf, expires_at) VALUES (?, ?, ?, ?)",
                     (_token_hash(token), user_id, secrets.token_urlsafe(24), expires))
    return token


def delete_session(conn, token):
    with conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def set_cookie(response, token):
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True,
                        secure=config.COOKIE_SECURE, samesite="lax")


def load_user(request: Request, conn):
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = conn.execute(
        "SELECT u.id, u.username, u.role, u.display_name, u.current_student_id, s.csrf FROM sessions s "
        "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ? AND u.active = 1",
        (_token_hash(token), config.now().isoformat())).fetchone()
    return dict(row) if row else None


class LoginRequired(Exception):
    pass


def current_user(request: Request, conn=Depends(get_db)):
    user = load_user(request, conn)
    if user is None:
        raise LoginRequired()
    request.state.user = user
    return user


def teacher_required(user=Depends(current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Только для преподавателя")
    return user


async def check_csrf(request: Request, user=Depends(current_user)):
    """Проверка CSRF-токена для POST: из формы (csrf) или заголовка X-CSRF-Token."""
    if request.method != "POST":
        return user
    token = request.headers.get("x-csrf-token")
    if not token:
        form = await request.form()
        token = form.get("csrf")
    if not token or not hmac.compare_digest(str(token), user["csrf"]):
        raise HTTPException(status_code=403, detail="Устаревшая форма. Обнови страницу и попробуй ещё раз.")
    return user
