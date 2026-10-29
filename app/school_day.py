"""Учебный день и серия. Граница 04:00 в поясе ученика.

Та же функция должна жить в приложении (`:core:model`), без второй формулы прогноза:
due_on считает только сервер, клиент показывает присланную дату.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SCHOOL_DAY_START = time(4, 0)
DEFAULT_TZ = "Europe/Moscow"


def _zone(tz):
    return tz if isinstance(tz, ZoneInfo) else ZoneInfo(tz or DEFAULT_TZ)


def school_day(instant, tz=DEFAULT_TZ):
    """Календарная дата учебного дня для момента `instant`.

    До 04:00 локального времени день ещё вчерашний. Смена пояса считается
    по тому поясу, который передали, а не по поясу исходного datetime.
    """
    zone = _zone(tz)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=zone)
    local = instant.astimezone(zone)
    if local.time() < SCHOOL_DAY_START:
        return local.date() - timedelta(days=1)
    return local.date()


def due_on(answered_on, interval_days):
    """Дата повтора: учебный день ответа плюс интервал в учебных днях, не плюс 24 часа.

    Интервалы (+1, +3, +7) задаёт сервер. Клиент их не хранит.
    """
    if interval_days < 0:
        raise ValueError("interval_days")
    return answered_on + timedelta(days=interval_days)


def streak_after(last_school_day, today, previous_streak=0):
    """Серия после занятия в учебный день `today`.

    Пропуск одного учебного дня рвёт серию. Пропуск трёх и больше —
    возвращение: серия с единицы, план на сегодня короче вдвое.
    """
    if last_school_day is None:
        return {"streak": 1, "comeback": False, "minutes_factor": 1.0}
    missed = (today - last_school_day).days - 1
    if missed < 0:
        return {"streak": max(previous_streak, 1), "comeback": False, "minutes_factor": 1.0}
    if missed == 0:
        return {"streak": previous_streak + 1, "comeback": False, "minutes_factor": 1.0}
    if missed >= 3:
        return {"streak": 1, "comeback": True, "minutes_factor": 0.5}
    return {"streak": 0, "comeback": False, "minutes_factor": 1.0}


def answer_canon(raw):
    """Канон сырого ответа: края обрезаем, запятую не превращаем в точку."""
    if raw is None:
        return ""
    return str(raw).strip()
