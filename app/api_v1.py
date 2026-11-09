"""Публичный API приложения. Этап 1: чтение (конфиг, каталог). Этап 2: условие номера и проверка попытки
без учётки. Этап 3: онбординг гостем, запись попыток и прогноз.

Гость — строка users с guest = 1 без пароля (войти на сайт им нельзя), знания считает тот же
app/knowledge.py, что и на сайте. Попытку проверяет тот же движок, что тренажёр: вариант пересобирается
из (exam_id, номер, seed). С токеном сессии попытка пишется; ключ идемпотентности хранится в
api_attempt_keys — повтор с тем же ключом возвращает сохранённый ответ и второй раз попытку не пишет.
"""
import hashlib
import secrets
import sqlite3
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from . import exam_model as em
from . import knowledge as kn
from . import config
from .db import get_db

router = APIRouter(prefix="/api/v1")

SCHEMA_VERSION = 1
NOTICE_PAUSED = "Эта часть на паузе. Ответы, которые ты уже дал, на месте"
TRAIN_PAUSED = "Тренажёр на паузе. Ответы, которые ты уже дал, на месте"
GUESTS_PAUSED = "Онбординг гостей на паузе. Уже созданные сессии работают"
SESSION_NOT_FOUND = "Сессия не найдена — создай новую (POST /api/v1/sessions)"

# live — у предмета есть номера, где сервер сам выдаёт вариант и проверяет ответ (u2_web.GENERATED).
# Остальные soon: там пока только самопроверка по банку ФИПИ. Баллы — из app/content/exams, не из памяти.
# Обязательные: русский и математика ОГЭ; на ЕГЭ русский (математику выбирают — базу или профиль).
_TRACKS = (("oge", "ОГЭ"), ("ege", "ЕГЭ"))
_REQUIRED = {"oge-rus-2026", "oge-math-2026", "ege-rus-2026"}


class FlagSet(BaseModel):
    trainer: bool = True
    trial: bool = True
    crash_reports: bool = True
    guests: bool = True


class Notice(BaseModel):
    kind: str
    text: str


class ConfigOut(BaseModel):
    schema_version: int = SCHEMA_VERSION
    hard_min_build: int
    flags: FlagSet
    notice: Notice | None = None


class SubjectOut(BaseModel):
    id: str
    exam_id: str
    title: str
    status: str
    required: bool
    max_points: int = Field(gt=0)


class ExamTrackOut(BaseModel):
    id: str
    title: str
    year: int
    subjects: list[SubjectOut]


class CatalogOut(BaseModel):
    schema_version: int = SCHEMA_VERSION
    tracks: list[ExamTrackOut]


class TaskOut(BaseModel):
    schema_version: int = SCHEMA_VERSION
    exam_id: str
    n: int
    seed: int
    text: str
    table: list[list[str]] | None = None
    code: str | None = None
    svg: str | None = None


class AttemptIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    exam_id: str
    n: int
    seed: int = Field(gt=0, lt=10 ** 7)
    answer: str = Field(min_length=1, max_length=100)


class AttemptOut(BaseModel):
    schema_version: int = SCHEMA_VERSION
    idempotency_key: str
    ok: bool
    answer: str
    explain: str = ""
    steps: list[str] = []


class SessionIn(BaseModel):
    device_id: str = Field(min_length=8, max_length=128)


class SessionOut(BaseModel):
    schema_version: int = SCHEMA_VERSION
    token: str
    created: bool                     # False — device_id уже был: это тот же гость, прогресс на месте


class ForecastOut(BaseModel):
    schema_version: int = SCHEMA_VERSION
    exam_id: str
    primary: float
    low: int
    high: int
    grade: int | None = None
    grade_low: int | None = None
    grade_high: int | None = None
    test: int | None = None
    test_low: int | None = None
    test_high: int | None = None


def _flag(name, default=True):
    raw = getattr(config, name, default)
    if isinstance(raw, str):
        return raw not in ("0", "false", "False")
    return bool(raw)


def _subject(exam_id, generated):
    exam = em.load(exam_id)
    return SubjectOut(
        id=exam_id.split("-", 1)[1].rsplit("-", 1)[0],   # oge-math-2026 → math, ege-math-base-2026 → math-base
        exam_id=exam_id,
        title=exam["subject"],
        status="live" if generated.get(exam_id) else "soon",
        required=exam_id in _REQUIRED,
        max_points=exam["max_points"],
    )


def catalog_payload():
    from .u2_web import GENERATED   # здесь, а не сверху: u2_web тянет main, а main подключает этот роутер
    ids = sorted(em.all_ids())
    tracks = []
    for track_id, title in _TRACKS:
        mine = [e for e in ids if e.startswith(track_id + "-")]
        subjects = sorted((_subject(e, GENERATED) for e in mine), key=lambda s: (s.status != "live", s.title))
        tracks.append(ExamTrackOut(id=track_id, title=title, year=int(mine[0].rsplit("-", 1)[1]), subjects=subjects))
    return CatalogOut(tracks=tracks)


def config_payload():
    notice = None
    if config.API_NOTICE_KIND:
        notice = Notice(kind=config.API_NOTICE_KIND, text=config.API_NOTICE_TEXT or NOTICE_PAUSED)
    return ConfigOut(
        hard_min_build=config.API_HARD_MIN_BUILD,
        flags=FlagSet(
            trainer=_flag("API_FLAG_TRAINER"),
            trial=_flag("API_FLAG_TRIAL"),
            crash_reports=_flag("API_FLAG_CRASH_REPORTS"),
            guests=_flag("API_FLAG_GUESTS"),
        ),
        notice=notice,
    )


@router.get("/config", response_model=ConfigOut)
def get_config():
    return config_payload()


@router.get("/catalog", response_model=CatalogOut)
def get_catalog():
    return catalog_payload()


def _trainer_gate():
    if not _flag("API_FLAG_TRAINER"):
        raise HTTPException(503, TRAIN_PAUSED)


def _engine(exam_id, n, seed):
    """Вариант и банк проверки — тот же движок, что тренажёр сайта. Чужой экзамен или номер — 404."""
    from .content import oge_gen
    from .u2_web import BANKS, GENERATED, _variant   # локально: u2_web тянет main, а main подключает этот роутер
    if exam_id not in GENERATED or n not in GENERATED[exam_id]:
        raise HTTPException(404)
    return _variant(exam_id, n, seed), BANKS.get(exam_id), oge_gen


@router.get("/tasks/{exam_id}/{n}", response_model=TaskOut, response_model_exclude_none=True)
def get_task(exam_id: str, n: int, seed: int = Query(gt=0, lt=10 ** 7)):
    """Условие номера по варианту: без ответа, разбора и шагов — их даёт только попытка."""
    _trainer_gate()
    v, _, _ = _engine(exam_id, n, seed)
    return TaskOut(exam_id=exam_id, n=n, seed=seed, text=v["text"],
                   table=v.get("table"), code=v.get("code"), svg=v.get("svg"))


# --- этап 3: онбординг гостем, запись попыток, прогноз ---

_sessions = {}                            # ip -> [время создания сессии]


def _session_limited(ip):
    now = time.time()
    _sessions[ip] = [t for t in _sessions.get(ip, []) if now - t < 3600]
    return len(_sessions[ip]) >= config.API_SESSIONS_PER_HOUR


def _token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _bearer(authorization):
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization[7:].strip()


def _guest_id(conn, token):
    row = conn.execute("SELECT s.user_id FROM api_sessions s JOIN users u ON u.id = s.user_id "
                       "WHERE s.token_hash = ? AND u.active = 1", (_token_hash(token),)).fetchone()
    return row[0] if row else None


@router.post("/sessions", response_model=SessionOut)
def post_session(body: SessionIn, request: Request, conn=Depends(get_db)):
    """Онбординг гостем: токен без учётки, знаний ноль. Повтор с тем же device_id выдаёт новый токен
    тому же гостю — прогресс сохраняется. Лимит — CQ_API_SESSIONS_PER_HOUR с адреса."""
    if not _flag("API_FLAG_GUESTS"):
        raise HTTPException(503, GUESTS_PAUSED)
    ip = request.client.host if request.client else "?"
    if _session_limited(ip):
        raise HTTPException(429, "Слишком много сессий с одного адреса — попробуй позже")
    _sessions.setdefault(ip, []).append(time.time())
    device_hash = _token_hash(body.device_id)
    now = config.now().isoformat(timespec="seconds")
    token = None
    with conn:
        prev = conn.execute("SELECT user_id FROM api_sessions WHERE device_hash = ?", (device_hash,)).fetchone()
        if prev:
            uid, created = prev[0], False
            conn.execute("DELETE FROM api_sessions WHERE device_hash = ?", (device_hash,))
        else:
            uid = None
            for _ in range(3):             # коллизия случайного имени практически невозможна, но дёшево повторить
                try:
                    uid = conn.execute(
                        "INSERT INTO users (username, password_hash, role, display_name, guest, created_at) "
                        "VALUES (?, ?, 'student', 'Гость', 1, ?)",
                        ("api-" + secrets.token_hex(8), secrets.token_hex(16), now)).lastrowid
                    break
                except sqlite3.IntegrityError:
                    continue
            if uid is None:
                raise HTTPException(500, "Не получилось создать гостя")
            created = True
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO api_sessions (token_hash, user_id, device_hash, created_at, last_seen_at) "
                     "VALUES (?, ?, ?, ?, ?)", (_token_hash(token), uid, device_hash, now, now))
    return SessionOut(schema_version=SCHEMA_VERSION, token=token, created=created)


@router.post("/attempts", response_model=AttemptOut)
def post_attempt(body: AttemptIn, conn=Depends(get_db), authorization: str | None = Header(default=None)):
    """Проверка попытки: ответ до 100 символов, как на сайте. Без токена — ничего не пишется (этап 2).
    С токеном сессии гостя попытка пишется (kn.record), а ключ идемпотентности — в api_attempt_keys:
    повтор с тем же ключом возвращает сохранённый ответ, второй раз попытка не засчитывается."""
    _trainer_gate()
    v, bank, oge_gen = _engine(body.exam_id, body.n, body.seed)
    ok = bank.check(v, body.answer) if bank else oge_gen.check(v, body.answer)
    out = AttemptOut(schema_version=SCHEMA_VERSION, idempotency_key=body.idempotency_key, ok=ok,
                     answer=str(v.get("answer", "")), explain=v.get("explain") or "",
                     steps=[str(s) for s in v.get("steps") or []])
    token = _bearer(authorization)
    if token is None:
        return out
    uid = _guest_id(conn, token)
    if uid is None:
        raise HTTPException(401, SESSION_NOT_FOUND)
    fingerprint = (body.exam_id, str(body.n), body.seed, body.answer)
    row = conn.execute("SELECT exam_id, task_key, seed, answer, response FROM api_attempt_keys "
                       "WHERE idempotency_key = ?", (body.idempotency_key,)).fetchone()
    if row:
        if (row["exam_id"], row["task_key"], row["seed"], row["answer"]) != fingerprint:
            raise HTTPException(422, "Ключ идемпотентности уже использован с другим запросом")
        return AttemptOut.model_validate_json(row["response"])
    now = config.now().isoformat(timespec="seconds")
    with conn:
        try:
            conn.execute("INSERT INTO api_attempt_keys (idempotency_key, user_id, exam_id, task_key, seed, "
                         "answer, response, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (body.idempotency_key, uid, body.exam_id, str(body.n), body.seed, body.answer,
                          out.model_dump_json(), now))
        except sqlite3.IntegrityError:     # гонка: тот же ключ пришёл дважды — побеждает первый
            row = conn.execute("SELECT response FROM api_attempt_keys WHERE idempotency_key = ?",
                               (body.idempotency_key,)).fetchone()
            return AttemptOut.model_validate_json(row["response"])
        try:
            kn.record(conn, uid, body.exam_id, body.n, 1.0 if ok else 0.0, seed=body.seed, given=body.answer)
        except KeyError:
            raise HTTPException(404)
        conn.execute("UPDATE api_sessions SET last_seen_at = ? WHERE token_hash = ?", (now, _token_hash(token)))
    return out


@router.get("/forecast/{exam_id}", response_model=ForecastOut, response_model_exclude_none=True)
def get_forecast(exam_id: str, conn=Depends(get_db), authorization: str | None = Header(default=None)):
    """Прогноз балла по попыткам гостя — тот же расчёт, что на сайте (kn.forecast): ожидаемый первичный
    балл, вилка 80% и отметка или тестовый балл. Без сессии — 401, чужой exam_id — 404."""
    _trainer_gate()
    token = _bearer(authorization)
    if token is None:
        raise HTTPException(401, "Нужна сессия гостя (POST /api/v1/sessions)")
    uid = _guest_id(conn, token)
    if uid is None:
        raise HTTPException(401, SESSION_NOT_FOUND)
    try:
        exam = em.load(exam_id)
    except FileNotFoundError:
        raise HTTPException(404)
    return ForecastOut(schema_version=SCHEMA_VERSION, exam_id=exam_id,
                       **kn.forecast(exam, kn.load_states(conn, uid, exam_id)))
