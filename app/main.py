"""КодКвест — личный кабинет ученика курса Python. Несколько учеников, один преподаватель.

Чей кабинет показываем — «субъект» (sid):
  ученик видит только себя — sid берётся из сессии и никогда из запроса;
  преподаватель смотрит кабинет выбранного ученика (переключатель в шапке), а действия над учеником
  (провести урок, выдать трофеи…) принимают student_id явно из формы.
"""
import asyncio
import json
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from markupsafe import Markup, escape
from starlette.concurrency import run_in_threadpool

from . import art, auth, config, events, game, levels, oge_drill, russian, season, students, subjects, theme, today, weekly

from .content.checks import CHECK_BY_ID, CHECKS, grade
from .content.glossary import add_abbr
from .content.lessons import LESSON_BY_NUM
from .content.oge import OGE_NUMBERS, OGE_TASKS
from .content.quizzes import QUIZ_BY_ID
from .content import oge_gen
from .content import robot as robot_content
from .content.tasks import TASK_BY_ID
from .db import get_db, get_setting, init_db

APP_DIR = Path(__file__).resolve().parent
STATIC_VERSION = secrets.token_hex(4)


@asynccontextmanager
async def lifespan(_app):
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    task = asyncio.create_task(weekly.scheduler()) if os.environ.get("CQ_WEEKLY", "1") == "1" else None
    yield
    if task:
        task.cancel()


app = FastAPI(title=config.SITE_NAME, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
FILE_EXT = IMAGE_EXT | {".py", ".txt", ".zip", ".pdf", ".json", ".md", ".exe", ".mp4", ".webm"}

CSP = ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data: blob:; connect-src 'self'; worker-src 'self'; media-src 'self'; "
       "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


# страницы курса Python и игры «КодКвеста» — на сайте химии их нет
PYTHON_ONLY = ("/today", "/lesson/", "/homework", "/task/", "/api/task/", "/api/run", "/daily", "/api/daily/", "/oge", "/api/robot/", "/bots",
               "/api/bots/", "/season", "/ru", "/api/ru/", "/certificate", "/certificates", "/trainer", "/api/trainer", "/playground",
               "/api/snippets", "/snippets/", "/achievements", "/shop", "/cheatsheet", "/portfolio", "/p/", "/gallery",
               "/files/sub/", "/files/project/", "/teacher/weekly", "/teacher/lessons", "/teacher/lesson/", "/teacher/guide/",
               "/teacher/reviews", "/teacher/review/", "/teacher/rewards", "/teacher/purchase/", "/teacher/solutions",
               "/teacher/attempts/", "/teacher/journal", "/teacher/xp", "/teacher/leaderboard", "/teacher/certificates",
               "/teacher/cert-name", "/teacher/analytics", "/family", "/privacy")


@app.middleware("http")
async def chem_site_only(request: Request, call_next):
    if config.CHEM_SITE:
        path = request.url.path
        if any(path == p.rstrip("/") or path.startswith(p if p.endswith("/") else p + "/") or path == p for p in PYTHON_ONLY):
            return Response("Not Found", status_code=404)
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    await run_in_threadpool(events.record, request, response.status_code)
    # Изоляция страницы нужна, чтобы Python в браузере мог ждать input() и останавливаться кнопкой «Стоп»
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers.setdefault("Content-Security-Policy", CSP)
    if request.url.path.startswith("/static/vendor/"):
        response.headers["Cache-Control"] = "public, max-age=2592000, immutable"
    if request.url.path.startswith(("/parent/", "/family", "/teacher/students", "/teacher/student/")):
        # страница родителя и карточки доступа — не кэшировать и не индексировать
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


class NoStudent(Exception):
    """Преподаватель открыл кабинет ученика, а учеников ещё нет."""


@app.exception_handler(auth.LoginRequired)
async def _login_redirect(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "login"}, status_code=401)
    if request.url.path == "/" and theme.THEME == "public":
        return RedirectResponse("/welcome", status_code=303)
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def _http_error(request: Request, exc):
    """Ошибки форм и страниц — понятной страницей с кнопкой «Назад», а не JSON; API отвечает JSON, как раньше."""
    if request.url.path.startswith("/api/") or "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))
    detail = exc.detail if isinstance(exc.detail, str) else ""
    if exc.status_code == 404 and detail in ("", "Not Found"):
        detail = "Возможно, ссылка устарела или страница доступна другому пользователю."
    elif detail in ("", "Bad Request", "Forbidden", "Method Not Allowed"):
        detail = "Что-то пошло не так. Вернись назад и попробуй ещё раз."
    return templates.TemplateResponse(request, "error.html", {
        "request": request, "user": None, "site_name": config.SITE_NAME, "brand": config.BRAND_EMOJI,
        "v": STATIC_VERSION, "nav": request.url.path, "chem_site": config.CHEM_SITE, "status": exc.status_code,
        "message": detail}, status_code=exc.status_code)


@app.exception_handler(NoStudent)
async def _no_student(request: Request, exc):
    return RedirectResponse("/teacher/students", status_code=303)


# ------------------------------------------------------------------ шаблоны
def inline_md(text):
    """Мини-разметка: `код` и **жирный**. Остальное экранируется."""
    s = str(escape(text or ""))
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    if config.CHEM_SITE:                      # сайт по химии: формулы с индексами вместо глоссария Python
        from .chem_format import formula_html
        return Markup(formula_html(s))
    return Markup(add_abbr(s))


templates.env.filters["md"] = inline_md
templates.env.filters["abbr"] = lambda html: Markup(add_abbr(str(html)))
templates.env.filters["tojson_attr"] = lambda v: json.dumps(v, ensure_ascii=False)
templates.env.globals["brawler_img"] = art.brawler_img
templates.env.globals["ruhero_img"] = art.ruhero_img
templates.env.globals["world_img"] = art.world_img
templates.env.globals["rank_img"] = art.rank_img
templates.env.globals["T"] = theme.T
templates.env.globals["wordmark"] = theme.wordmark
templates.env.globals["fam_csrf"] = lambda fam: Markup('<input type="hidden" name="csrf" value="%s">' % fam["csrf"])
templates.env.globals["chest_img"] = art.chest_img
templates.env.globals["season_banner"] = art.season_banner


def ico(name, emoji, cls="ico-img"):
    """Иконка раздела картинкой, если она есть, иначе эмодзи."""
    url = art.icon_img(name)
    return Markup('<img src="%s" alt="" class="%s">' % (url, cls)) if url else emoji


templates.env.globals["ico"] = ico


def fmt_dt(value, with_time=True):
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
              "сентября", "октября", "ноября", "декабря"]
    s = "%d %s" % (dt.day, months[dt.month - 1])
    if with_time and (dt.hour or dt.minute):
        s += ", %02d:%02d" % (dt.hour, dt.minute)
    return s


def fmt_ago(value):
    if not value:
        return "входа ещё не было"
    d = students._days_since(value)
    if d is None:
        return value
    return "сегодня" if d == 0 else "вчера" if d == 1 else "%d дн. назад" % d


templates.env.filters["dt"] = fmt_dt


from .chem_format import chem_text  # noqa: E402

templates.env.filters["chem"] = chem_text
templates.env.filters["ago"] = fmt_ago


def subject_id(conn, user):
    """Чей кабинет показываем. Ученик — всегда свой; преподаватель — выбранного ученика."""
    if not user:
        return None
    if user["role"] == "student":
        return user["id"]
    sid = user.get("current_student_id")
    if sid and students.get_student(conn, sid):
        return sid
    first = conn.execute("SELECT id FROM users WHERE role = 'student' AND active = 1 ORDER BY id LIMIT 1").fetchone()
    return first[0] if first else None


def need_sid(conn, user):
    sid = subject_id(conn, user)
    if not sid:
        raise NoStudent()
    return sid


def target_student(conn, user, student_id=0):
    """Ученик, над которым преподаватель выполняет действие: явно из формы, иначе — выбранный."""
    auth.teacher_required(user)
    sid = student_id or subject_id(conn, user)
    if not sid or not students.get_student(conn, sid):
        raise HTTPException(400, "Такого ученика нет")
    return sid


def render(request, name, conn, user=None, **ctx):
    ctx.update({
        "request": request,
        "user": user,
        "site_name": config.SITE_NAME,
        "v": STATIC_VERSION,
        "nav": request.url.path,
        "chem_site": config.CHEM_SITE,
        "brand": config.BRAND_EMOJI,
        "game_full": config.GAME == "full",
        "signup": config.SIGNUP,
        "open_signup": config.OPEN_SIGNUP,
        "public_site": theme.THEME == "public",
        "source_url": config.SOURCE_URL,
        "logo": theme.LOGO,
    })
    if user:
        sid = ctx.pop("sid", None) or subject_id(conn, user)
        ctx["sid"] = sid
        ctx["subject"] = students.get_student(conn, sid) if sid else None
        ctx.setdefault("me", game.stats(conn, sid) if sid else None)
        ctx["student_name"] = ctx["subject"]["display_name"] if ctx["subject"] else ""
        ctx["subj"] = subjects.of(ctx["subject"]) if ctx["subject"] else []
        ctx["subjects_all"] = subjects.SUBJECTS
        ctx["lvl"] = levels.LEVELS[levels.of(ctx["subject"])] if ctx["subject"] else None
        ctx["levels_all"] = levels.LEVELS
        ctx["calm"] = config.GAME != "full" or bool(ctx["subject"] and ctx["subject"].get("calm"))
        ctx["subj_of"] = subjects.of
        if "russian" in ctx["subj"]:
            ctx["ru_due"] = len(russian.due_items(conn, sid))
        ctx["notices"] = game.pop_notices(conn, sid) if user["role"] == "student" else []
        if user["role"] == "teacher":
            ctx["all_students"] = students.list_students(conn)
            ctx["pending_hw"] = conn.execute("SELECT COUNT(*) FROM submissions WHERE status = 'pending'").fetchone()[0]
            ctx["pending_buy"] = conn.execute("SELECT COUNT(*) FROM purchases WHERE status = 'requested'").fetchone()[0]
            ctx["pending_reviews"] = ctx["pending_hw"] + ctx["pending_buy"]
            if config.CHEM_SITE:
                ctx["pending_chem"] = conn.execute("SELECT COUNT(*) FROM chem_hw WHERE status = 'submitted'").fetchone()[0]
        else:
            students.touch(conn, user["id"])
    return templates.TemplateResponse(request, name, ctx)


def back(path):
    return RedirectResponse(path, status_code=303)


def is_teacher(user):
    return bool(user) and user["role"] == "teacher"


def only_student(user):
    if user["role"] != "student":
        raise HTTPException(403, "Это делает ученик в своём кабинете")
    return user["id"]


async def save_upload(upload: UploadFile, allowed):
    if not upload or not upload.filename:
        return None, None
    ext = Path(upload.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, "Такой тип файла нельзя загрузить: %s" % ext)
    name = secrets.token_hex(12) + ext
    dest = config.UPLOAD_DIR / name
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    with open(dest, "wb") as f:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(400, "Файл больше %d МБ" % config.MAX_UPLOAD_MB)
            f.write(chunk)
    original = re.sub(r"[^\w.\- ]", "_", Path(upload.filename).name)[:100]
    return original, name


def upload_path(name):
    path = (config.UPLOAD_DIR / name).resolve()
    if config.UPLOAD_DIR.resolve() not in path.parents or not path.exists():
        raise HTTPException(404)
    return path


# ------------------------------------------------------------------ вход
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, conn=Depends(get_db)):
    if auth.load_user(request, conn):
        return back("/")
    return render(request, "login.html", conn, error=None)


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), conn=Depends(get_db)):
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "?")
    if auth.too_many_fails(ip):
        return render(request, "login.html", conn, error="Слишком много попыток. Подожди 15 минут.")
    row = conn.execute("SELECT id, password_hash, active FROM users WHERE username = ?",
                       (username.strip().lower(),)).fetchone()
    if not row or not auth.verify_password(password, row["password_hash"]):
        auth.register_fail(ip)
        return render(request, "login.html", conn, error="Неверный логин или пароль")
    if not row["active"]:
        return render(request, "login.html", conn, error="Аккаунт в архиве. Напиши преподавателю.")
    token = auth.create_session(conn, row["id"])
    resp = back("/")
    auth.set_cookie(resp, token)
    return resp


@app.post("/logout")
def logout(request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    token = request.cookies.get(auth.COOKIE)
    if token:
        auth.delete_session(conn, token)
    resp = back("/login")
    resp.delete_cookie(auth.COOKIE)
    return resp


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ------------------------------------------------------------------ ученик: главная
def pending_check(conn, sid):
    """Открытая, но ещё не сданная проверка — её показываем ученику на главной."""
    states, results = check_states(conn, sid)
    return next((c for c in CHECKS if c["id"] in states and states[c["id"]]["opened_at"] and c["id"] not in results), None)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    if is_teacher(user):
        return back("/teacher")
    if config.CHEM_SITE:
        return back("/chem")
    sid = user["id"]
    lessons = game.lesson_list_with_state(conn, sid)
    upto = game.unlocked_upto(conn, sid)
    current = LESSON_BY_NUM.get(upto)
    daily = game.get_daily(conn, sid)
    daily_item = QUIZ_BY_ID.get(daily["ref"]) if daily["kind"] == "quiz" else TASK_BY_ID.get(daily["ref"])
    recent = conn.execute("SELECT * FROM xp_events WHERE student_id = ? ORDER BY id DESC LIMIT 6", (sid,)).fetchall()
    returned = conn.execute("SELECT * FROM submissions WHERE student_id = ? AND status = 'returned' AND id IN "
                            "(SELECT MAX(id) FROM submissions WHERE student_id = ? GROUP BY lesson)", (sid, sid)).fetchall()
    have = game.unlocked_achievements(conn, sid)
    next_ach = [a for a in game.ACHIEVEMENTS if a[0] not in have][:3]
    board = students.leaderboard(conn) if students.leaderboard_enabled(conn) else []
    ru_ov = russian.overview(conn, sid) if "russian" in subjects.of(students.get_student(conn, sid)) else None
    return render(request, "student/home.html", conn, user, ru_ov=ru_ov, pass_ov=season.overview(conn, sid),
                  plan=today.plan(conn, sid),
                  lessons=lessons, current=current, current_state=lessons[upto - 1] if current else None,
                  daily=daily, daily_item=daily_item, recent=recent, returned=returned,
                  next_lesson_at=students.get_student(conn, sid)["next_lesson_at"], next_ach=next_ach,
                  trainer_best=game.trainer_best(conn, sid), pending_check=pending_check(conn, sid),
                  board=board if len(board) > 1 else [])


# ------------------------------------------------------------------ проверки: входной тест, срезы, итоговый
def check_states(conn, sid):
    states = {r["id"]: r for r in conn.execute("SELECT * FROM check_state WHERE student_id = ?", (sid,))}
    results = {r["check_id"]: r for r in conn.execute("SELECT * FROM check_results WHERE student_id = ?", (sid,))}
    return states, results


# ------------------------------------------------------------------ ОГЭ: номера экзамена и прогресс по ним
def oge_progress(conn, sid):
    """По каждому номеру ОГЭ: решённые задачи в формате номера и верные ответы последнего пробника."""
    solved = game.solved_task_ids(conn, sid)
    trial = conn.execute("SELECT answers FROM check_results WHERE student_id = ? AND check_id = 'oge1'", (sid,)).fetchone()
    trial_topics = {}
    if trial:
        for item in grade(CHECK_BY_ID["oge1"], json.loads(trial["answers"]))["items"]:
            num = int(item["q"]["topic"].split()[0].lstrip("№"))
            ok, total = trial_topics.get(num, (0, 0))
            trial_topics[num] = (ok + item["ok"], total + 1)
    out = {}
    drill = oge_drill.stats(conn, sid)
    for num in OGE_NUMBERS:
        tasks = [t for t in OGE_TASKS if t["oge"] == num]
        out[num] = {"tasks": tasks, "solved": len([t for t in tasks if t["id"] in solved]), "trial": trial_topics.get(num),
                    "drill": drill.get(num) if num in oge_gen.GENERATORS else None, "has_drill": num in oge_gen.GENERATORS}
    out[15]["robot"] = (len(robot_solved(conn, sid)), len(robot_content.TASKS))
    return out


def _mock_items(key):
    """Пробник: по варианту каждого номера, сиды выводятся из ключа пробника."""
    out = []
    for num in sorted(oge_gen.GENERATORS):
        v = oge_gen.make(num, (key * 31 + num) % 10 ** 6 + 1)
        out.append({"num": num, "seed": v["seed"], "v": v, "variant": oge_gen.public(v), "title": OGE_NUMBERS[num][0],
                    "text": oge_drill.rich(v["text"])})
    return out


# ------------------------------------------------------------------ ОГЭ №15: исполнитель «Робот»
def robot_solved(conn, sid):
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT task_id FROM robot_attempts WHERE student_id = ? AND passed = 1", (sid,))}


# ------------------------------------------------------------------ сертификаты для печати
def cert_signer(conn):
    row = conn.execute("SELECT display_name FROM users WHERE role = 'teacher' ORDER BY id LIMIT 1").fetchone()
    return get_setting(conn, "cert_teacher") or (row["display_name"] if row else "")


class FamilyLogin(Exception):
    """Страница кабинета родителя без входа."""


@app.exception_handler(FamilyLogin)
async def _family_login_redirect(request: Request, exc):
    return back("/family/login")


# ------------------------------------------------------------------ преподаватель: ученики
def select_student(conn, user, sid):
    if students.get_student(conn, sid):
        with conn:
            conn.execute("UPDATE users SET current_student_id = ? WHERE id = ?", (sid, user["id"]))
        user["current_student_id"] = sid


# ------------------------------------------------------------------ экземпляр по химии (CQ_SUBJECTS=chemistry)
# Разделы сайта — в отдельных модулях; им нужны общие функции выше, поэтому подключаем в конце.
from .student_web import router as student_router  # noqa: E402
from .oge_web import router as oge_router  # noqa: E402
from .ru_web import router as russian_router  # noqa: E402
from .portfolio_web import router as portfolio_router  # noqa: E402
from .family_web import router as family_router  # noqa: E402
from .teacher_web import router as teacher_router  # noqa: E402
from .signup_web import router as signup_router  # noqa: E402
app.include_router(student_router)
app.include_router(oge_router)
app.include_router(russian_router)
app.include_router(portfolio_router)
app.include_router(family_router)
app.include_router(teacher_router)
app.include_router(signup_router)
from .chem_web import router as chem_router  # noqa: E402 — после всех общих функций, которыми он пользуется

app.include_router(chem_router)
