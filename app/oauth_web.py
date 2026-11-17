"""Кнопка «Войти с Яндекс ID»: код авторизации, state в сессии, привязка по подтверждённой почте.

Новый аккаунт не создаётся в callback. Сначала та же проверка, что у регистрации по почте:
дата рождения, младше 14 — отказ (аккаунт заводит родитель), плюс согласие, как на /join.
Уже существующий пользователь с этой почтой входит в свой аккаунт, вторая строка users не появляется.
"""
import hmac
import logging
import secrets
import sqlite3
import time
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import auth, config, oauth_providers, students
from .api_v1 import _age
from .db import get_db
from .family import CONSENT_VERSION
from .main import after_login, back, render

router = APIRouter()
log = logging.getLogger("codequest.oauth")

COOKIE = "cq_oauth"
STATE_MINUTES = 10

STATE_MSG = "Ссылка входа устарела или открыта в другом окне. Нажмите «Войти с Яндекс ID» ещё раз."
DENY_MSG = "Вы отменили вход через Яндекс ID. Можно войти по логину и паролю."
FAIL_MSG = "Не удалось войти через Яндекс ID. Попробуйте ещё раз чуть позже."
NO_EMAIL_MSG = "Яндекс не подтвердил почту этого аккаунта. Укажите почту в Яндекс ID и попробуйте снова."
ARCHIVE_MSG = "Аккаунт в архиве. Напиши преподавателю."
MINOR_MSG = "Самому зарегистрироваться можно с 14 лет. Если тебе меньше — пусть родитель заведёт тебе аккаунт."
CONSENT_MSG = "Отметь согласие на обработку данных — без него зарегистрироваться нельзя."
TAKEN_MSG = "Эта почта или логин уже заняты"
FULL_MSG = "Сейчас все места заняты — загляни через пару дней."
FUTURE_MSG = "Дата рождения из будущего"
DATE_MSG = "Укажите дату рождения."
BOT_MSG = "Не получилось. Обнови страницу и попробуй ещё раз."
RATE_MSG = "С этого адреса уже много регистраций. Попробуй через час."


def _provider(name):
    p = oauth_providers.get(name)
    if p is None or not p.enabled():
        raise HTTPException(404)
    return p


def _now():
    return config.now().replace(microsecond=0)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def _redirect_uri(request, provider_id):
    base = (config.BASE_URL or str(request.base_url)).rstrip("/")
    return "%s/auth/%s/callback" % (base, provider_id)


def _ip(request):
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "?")


def _set_cookie(resp, value):
    resp.set_cookie(COOKIE, value, max_age=STATE_MINUTES * 60, httponly=True, path="/auth",
                    secure=config.COOKIE_SECURE, samesite="lax")


def _clear_cookie(resp):
    resp.delete_cookie(COOKIE, path="/auth", secure=config.COOKIE_SECURE, samesite="lax")


def _same(a, b):
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    if not a or not b or len(a) > 200 or len(b) > 200 or len(a) != len(b):
        return False
    return hmac.compare_digest(a, b)


def _purge(conn):
    now = _iso(_now())
    conn.execute("DELETE FROM oauth_states WHERE expires_at <= ?", (now,))
    conn.execute("DELETE FROM oauth_pending WHERE expires_at <= ?", (now,))


def _save_state(conn, state, provider):
    exp = _iso(_now() + timedelta(minutes=STATE_MINUTES))
    with conn:
        _purge(conn)
        conn.execute("INSERT INTO oauth_states (state_hash, provider, expires_at) VALUES (?, ?, ?)",
                     (auth._token_hash(state), provider, exp))


def _consume_state(conn, provider, query_state, cookie_state):
    """state из URL должен совпасть с cookie этой сессии и с одноразовой строкой в базе.

    Чужой state cookie не стирает: в соседней вкладке может быть живой вход.
    Возвращает ok / mismatch / replay.
    """
    if not _same(query_state, cookie_state):
        return "mismatch"
    now = _iso(_now())
    h = auth._token_hash(query_state)
    row = conn.execute("SELECT 1 FROM oauth_states WHERE state_hash = ? AND provider = ? AND expires_at > ?",
                       (h, provider, now)).fetchone()
    with conn:
        conn.execute("DELETE FROM oauth_states WHERE state_hash = ?", (h,))
    return "ok" if row else "replay"


def _fail(request, conn, message):
    resp = render(request, "login.html", conn, error=message)
    _clear_cookie(resp)
    return resp


def _find_by_email(conn, email):
    row = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
    if row:
        return row
    return conn.execute(
        "SELECT * FROM users WHERE lower(username) = ? AND (email IS NULL OR email = '')", (email,)).fetchone()


def _find_linked(conn, ident):
    return conn.execute(
        "SELECT u.* FROM oauth_identities i JOIN users u ON u.id = i.user_id "
        "WHERE i.provider = ? AND i.subject = ?", (ident.provider, ident.subject)).fetchone()


def _attach(conn, user_id, provider, subject, email):
    now = _iso(_now())
    conn.execute(
        "INSERT INTO oauth_identities (provider, subject, user_id, email, created_at) VALUES (?, ?, ?, ?, ?)",
        (provider, subject, user_id, email, now))
    conn.execute("UPDATE users SET email = ? WHERE id = ? AND (email IS NULL OR email = '')", (email, user_id))


def _enter(request, conn, user):
    if not user["active"]:
        return _fail(request, conn, ARCHIVE_MSG)
    token = auth.create_session(conn, user["id"])
    resp = back(after_login(user))
    auth.set_cookie(resp, token)
    _clear_cookie(resp)
    return resp


def _reload(conn, uid):
    return conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def _places_full(conn):
    n = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student' AND active = 1 AND guest = 0").fetchone()[0]
    return n >= students.MAX_STUDENTS


@router.get("/auth/{provider}")
def oauth_start(provider: str, request: Request, conn=Depends(get_db)):
    p = _provider(provider)
    user = auth.load_user(request, conn)
    if user:
        return back(after_login(user))
    state = secrets.token_urlsafe(32)
    _save_state(conn, state, p.id)
    resp = RedirectResponse(p.authorize_url(state, _redirect_uri(request, p.id)), status_code=302)
    _set_cookie(resp, state)
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _provider_message(error):
    if error == "access_denied":
        return DENY_MSG
    return FAIL_MSG


@router.get("/auth/{provider}/callback", response_class=HTMLResponse)
def oauth_callback(provider: str, request: Request, code: str = "", state: str = "", error: str = "",
                   conn=Depends(get_db)):
    p = _provider(provider)
    consumed = _consume_state(conn, p.id, state, request.cookies.get(COOKIE))
    if consumed != "ok":
        resp = render(request, "login.html", conn, error=STATE_MSG)
        if consumed == "replay":
            _clear_cookie(resp)
        return resp
    if error or not code:
        return _fail(request, conn, _provider_message(error))
    try:
        ident = p.fetch_identity(code, _redirect_uri(request, p.id))
    except oauth_providers.ProviderError:
        log.warning("oauth %s: провайдер не отдал профиль", p.id)
        return _fail(request, conn, FAIL_MSG)
    except Exception:
        log.warning("oauth %s: сбой обмена кода", p.id)
        return _fail(request, conn, FAIL_MSG)
    linked = _find_linked(conn, ident)
    if linked:
        return _enter(request, conn, linked)
    if not ident.email:
        return _fail(request, conn, NO_EMAIL_MSG)
    existing = _find_by_email(conn, ident.email)
    if existing:
        try:
            with conn:
                _attach(conn, existing["id"], ident.provider, ident.subject, ident.email)
                if existing["guest"]:
                    conn.execute("UPDATE users SET guest = 0 WHERE id = ?", (existing["id"],))
        except sqlite3.IntegrityError:
            log.warning("oauth %s: почта уже привязана к другому входу", p.id)
            return _fail(request, conn, FAIL_MSG)
        return _enter(request, conn, _reload(conn, existing["id"]))
    token = secrets.token_urlsafe(32)
    exp = _iso(_now() + timedelta(minutes=STATE_MINUTES))
    with conn:
        _purge(conn)
        conn.execute(
            "INSERT INTO oauth_pending (token_hash, provider, subject, email, display_name, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (auth._token_hash(token), ident.provider, ident.subject, ident.email, ident.display_name, exp))
    resp = RedirectResponse("/auth/%s/complete" % ident.provider, status_code=303)
    _set_cookie(resp, token)
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _load_pending(conn, provider, token):
    if not isinstance(token, str) or not token or len(token) > 200:
        return None
    row = conn.execute(
        "SELECT * FROM oauth_pending WHERE token_hash = ? AND provider = ? AND expires_at > ?",
        (auth._token_hash(token), provider, _iso(_now()))).fetchone()
    if not row:
        return None
    return {"provider": row["provider"], "subject": row["subject"], "email": row["email"],
            "display_name": row["display_name"], "token_hash": row["token_hash"]}


def _complete_page(request, conn, provider, pending, error, birth_date="", consent=""):
    return render(request, "oauth_complete.html", conn, error=error, provider=provider, email=pending["email"],
                  display_name=pending["display_name"], form={"birth_date": birth_date, "consent": consent})


@router.get("/auth/{provider}/complete", response_class=HTMLResponse)
def oauth_complete_page(provider: str, request: Request, conn=Depends(get_db)):
    p = _provider(provider)
    pending = _load_pending(conn, p.id, request.cookies.get(COOKIE))
    if not pending:
        return _fail(request, conn, STATE_MSG)
    return _complete_page(request, conn, p.id, pending, None)


@router.post("/auth/{provider}/complete", response_class=HTMLResponse)
def oauth_complete(provider: str, request: Request, birth_date: str = Form(""), consent: str = Form(""),
                   website: str = Form(""), conn=Depends(get_db)):
    """Новый аккаунт. Возраст — как у регистрации по почте: младше 14 не создаём."""
    p = _provider(provider)
    pending = _load_pending(conn, p.id, request.cookies.get(COOKIE))
    if not pending:
        return _fail(request, conn, STATE_MSG)

    def again(message):
        return _complete_page(request, conn, p.id, pending, message, birth_date, consent)

    if website:
        return again(BOT_MSG)
    try:
        born = date.fromisoformat(birth_date)
    except ValueError:
        return again(DATE_MSG)
    if born > config.today():
        return again(FUTURE_MSG)
    # Уже существующий аккаунт с этой почтой (успел появиться, пока форма была открыта) — это вход, не регистрация.
    existing = _find_by_email(conn, pending["email"])
    password_hash = None
    if existing is None:
        if _age(born) < 14:
            return again(MINOR_MSG)
        if consent != "1":
            return again(CONSENT_MSG)
        if students.signup_limited(_ip(request)):
            return again(RATE_MSG)
        if _places_full(conn):
            return again(FULL_MSG)
        password_hash = auth.hash_password(secrets.token_urlsafe(32))
    try:
        with conn:
            deleted = conn.execute("DELETE FROM oauth_pending WHERE token_hash = ? AND expires_at > ?",
                                   (pending["token_hash"], _iso(_now()))).rowcount
            if not deleted:
                raise LookupError()
            if existing is None:
                now = _iso(_now())
                uid = conn.execute(
                    "INSERT INTO users (username, password_hash, role, display_name, email, guest, created_at, "
                    "consent, self_paced, minor) VALUES (?, ?, 'student', ?, ?, 0, ?, ?, 1, 0)",
                    (pending["email"], password_hash, pending["display_name"], pending["email"], now,
                     "%s · %s" % (CONSENT_VERSION, now))).lastrowid
            else:
                uid = existing["id"]
                if existing["guest"]:
                    conn.execute("UPDATE users SET guest = 0 WHERE id = ?", (uid,))
            _attach(conn, uid, pending["provider"], pending["subject"], pending["email"])
    except LookupError:
        return _fail(request, conn, STATE_MSG)
    except sqlite3.IntegrityError:
        return _fail(request, conn, TAKEN_MSG)
    if existing is None:
        students._signups.setdefault(_ip(request), []).append(time.time())
    return _enter(request, conn, _reload(conn, uid))
