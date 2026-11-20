"""Тренировочная попытка без явной даты пишется московским «сегодня» (не UTC).

Между 00:00 и 03:00 МСК UTC-дата ещё «вчера»: попытки после полуночи выпадали
из «Сегодня» (test_api_v1::test_today_activity_after_attempt краснел на CI ровно
в этом окне). Правильное поведение — config.today() везде.
"""
from datetime import date, timedelta

from test_app import client  # noqa: F401  (фикстура TestClient с временной базой)


def test_record_defaults_to_msk_today(client, monkeypatch):
    from app import config, knowledge as kn

    from app import students
    from app.db import connect as _connect
    conn = _connect()
    with conn:
        sid = students.create_student(conn, "qa-day-fix", "Тест Дни", "parol-6")
    # «UTC-сегодня» = вчерашний день по МСК: до фикса record() писал date.today() (UTC) и
    # попытка после полуночи по МСК выпадала из «Сегодня»
    fake_today = date.today() - timedelta(days=1)
    monkeypatch.setattr(kn.config, "today", lambda: fake_today)
    with conn:
        kn.record(conn, sid, "oge-inf-2026", 1, 1.0, today=None, seed=777, given="777",
                  update_state=False)
    rows = conn.execute("SELECT day FROM skill_attempt WHERE student_id = ?", (sid,)).fetchall()
    assert rows, "попытка записана"
    assert date.fromisoformat(rows[0][0]) == fake_today, "день попытки — московское сегодня"
