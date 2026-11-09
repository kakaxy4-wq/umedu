"""Календарь учебного дня — те же фикстуры, что в android/core/model."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.school_day import answer_canon, due_on, school_day, streak_after

MOSCOW = ZoneInfo("Europe/Moscow")
VLAD = ZoneInfo("Asia/Vladivostok")
BERLIN = ZoneInfo("Europe/Berlin")


def test_0359_is_yesterday_0400_is_today():
    day = date(2026, 10, 29)
    before = datetime(2026, 10, 29, 3, 59, tzinfo=MOSCOW)
    on_time = datetime(2026, 10, 29, 4, 0, tzinfo=MOSCOW)
    assert school_day(before, MOSCOW) == date(2026, 10, 28)
    assert school_day(on_time, MOSCOW) == day


def test_session_at_0020_closes_yesterday():
    instant = datetime(2026, 10, 29, 0, 20, tzinfo=MOSCOW)
    assert school_day(instant, MOSCOW) == date(2026, 10, 28)


def test_zone_change_moscow_2200_to_vladivostok():
    instant = datetime(2026, 10, 29, 22, 0, tzinfo=MOSCOW)
    assert school_day(instant, MOSCOW) == date(2026, 10, 29)
    assert school_day(instant, VLAD) == date(2026, 10, 30)


def test_leap_day_2028_plus_one_is_march_first():
    assert due_on(date(2028, 2, 29), 1) == date(2028, 3, 1)
    assert due_on(date(2028, 2, 29), 1) != date(2029, 2, 28)
    assert due_on(date(2028, 2, 29), 1) != date(2028, 2, 29)


def test_berlin_dst_spring_forward():
    # 2026-03-29 02:00 Europe/Berlin не существует: стрелки на час вперёд.
    before = datetime(2026, 3, 29, 1, 30, tzinfo=BERLIN)
    after = datetime(2026, 3, 29, 3, 30, tzinfo=BERLIN)
    assert school_day(before, BERLIN) == date(2026, 3, 28)
    assert school_day(after, BERLIN) == date(2026, 3, 28)
    morning = datetime(2026, 3, 29, 4, 0, tzinfo=BERLIN)
    assert school_day(morning, BERLIN) == date(2026, 3, 29)


def test_skip_one_day_breaks_streak():
    today = date(2026, 10, 29)
    out = streak_after(date(2026, 10, 27), today, previous_streak=5)
    assert out["streak"] == 0 and not out["comeback"]


def test_skip_three_days_is_comeback_half_minutes():
    today = date(2026, 10, 29)
    out = streak_after(date(2026, 10, 25), today, previous_streak=12)
    assert out["comeback"] is True
    assert out["minutes_factor"] == 0.5
    assert out["streak"] == 1


def test_consecutive_days_grow_streak():
    out = streak_after(date(2026, 10, 28), date(2026, 10, 29), previous_streak=4)
    assert out == {"streak": 5, "comeback": False, "minutes_factor": 1.0}


def test_answer_canon_keeps_comma():
    assert answer_canon("  3,14  ") == "3,14"
    assert answer_canon("3,14") == "3,14"
    assert "," in answer_canon("3,14")
    assert answer_canon("") == ""
