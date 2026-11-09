"""Публичный API приложения. Этап 1: чтение (конфиг, каталог), записи в users нет.
Этап 2: условие номера и проверка попытки без учётки.

Попытку проверяет тот же движок, что тренажёр сайта: вариант пересобирается из (exam_id, номер, seed),
поэтому повтор с тем же ключом идемпотентности даёт тот же вердикт. Ученика на этапе 2 ещё нет
(онбординг гостем — этап 3), так что попытка ничего не пишет в базу.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import exam_model as em
from . import config

router = APIRouter(prefix="/api/v1")

SCHEMA_VERSION = 1
NOTICE_PAUSED = "Эта часть на паузе. Ответы, которые ты уже дал, на месте"
TRAIN_PAUSED = "Тренажёр на паузе. Ответы, которые ты уже дал, на месте"

# live — у предмета есть номера, где сервер сам выдаёт вариант и проверяет ответ (u2_web.GENERATED).
# Остальные soon: там пока только самопроверка по банку ФИПИ. Баллы — из app/content/exams, не из памяти.
# Обязательные: русский и математика ОГЭ; на ЕГЭ русский (математику выбирают — базу или профиль).
_TRACKS = (("oge", "ОГЭ"), ("ege", "ЕГЭ"))
_REQUIRED = {"oge-rus-2026", "oge-math-2026", "ege-rus-2026"}


class FlagSet(BaseModel):
    trainer: bool = True
    trial: bool = True
    crash_reports: bool = True


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


@router.post("/attempts", response_model=AttemptOut)
def post_attempt(body: AttemptIn):
    """Проверка попытки: ответ до 100 символов, как на сайте. В базу не пишется — очередь и её ключи на клиенте."""
    _trainer_gate()
    v, bank, oge_gen = _engine(body.exam_id, body.n, body.seed)
    ok = bank.check(v, body.answer) if bank else oge_gen.check(v, body.answer)
    return AttemptOut(schema_version=SCHEMA_VERSION, idempotency_key=body.idempotency_key, ok=ok,
                      answer=str(v.get("answer", "")), explain=v.get("explain") or "",
                      steps=[str(s) for s in v.get("steps") or []])
