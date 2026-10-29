"""Публичный API приложения. Этап 1: только чтение, записи в users нет.

Каталог и флаги собираются из кода и JSON экзаменов, не из живых учеников.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from . import exam_model as em
from . import config

router = APIRouter(prefix="/api/v1")

SCHEMA_VERSION = 1
NOTICE_PAUSED = "Эта часть на паузе. Ответы, которые ты уже дал, на месте"

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
