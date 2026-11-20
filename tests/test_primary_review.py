"""Интервальное повторение 3–4 класса: ошибка — завтра, верный ответ по расписанию 1–3–7–14."""
import pytest

from test_app import client  # noqa: F401  (фикстура TestClient с временной базой)


@pytest.fixture()
def kid(client, monkeypatch):
    from app import config, students
    from app.db import connect
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "CHEM_SITE", False)
    conn = connect()
    with conn:
        sid = students.create_student(conn, "qa-review-3", "Тест Повторение", "parol-6", grade=3)
        conn.execute("UPDATE users SET grade = 3, subjects = 'primary', minor = 1 WHERE id = ?", (sid,))
    return conn, sid


def _task(conn, task_id):
    from app.primary import get_task
    return get_task(task_id)


def _review_row(conn, sid, task_id):
    return conn.execute("SELECT box, due FROM primary_review WHERE student_id = ? AND task_id = ?",
                        (sid, task_id)).fetchone()


def test_wrong_then_intervals_then_mastered(kid):
    from datetime import timedelta

    from app import config
    from app.primary import answer, record, today_plan
    conn, sid = kid
    task = _task(conn, "m3-01")

    # ошибка: завтра, ящик 0, пометка ученику
    with conn:
        ok, nxt, note = answer(conn, sid, task, "41")
    assert ok is False and note == "Повторим завтра."
    row = _review_row(conn, sid, "m3-01")
    assert row["box"] == 0 and row["due"] == (config.today() + timedelta(days=1)).isoformat()

    # ещё раз неверно — ящик остаётся 0, срок снова завтра
    with conn:
        answer(conn, sid, task, "41")
    assert _review_row(conn, sid, "m3-01")["box"] == 0

    # в задание приходит на день раньше срока — расписание не двигается
    with conn:
        ok, nxt, note = answer(conn, sid, task, "42")
    assert ok is True and note is None
    assert _review_row(conn, sid, "m3-01")["box"] == 0

    # «прошло время» — верный ответ: ящик 1, следующий повтор через 3 дня
    conn.execute("UPDATE primary_review SET due = date('now', '-1 day') WHERE student_id = ?", (sid,))
    with conn:
        ok, nxt, note = answer(conn, sid, task, "42")
    assert ok is True and note == "Повторим через 3 дн."
    assert _review_row(conn, sid, "m3-01")["box"] == 1

    # цепочка до «выучено»: +7, +14, затем строка удаляется
    for expected in ("Повторим через 7 дн.", "Повторим через 14 дн.", "Выучено — больше не повторяем."):
        conn.execute("UPDATE primary_review SET due = date('now', '-1 day') WHERE student_id = ?", (sid,))
        with conn:
            ok, nxt, note = answer(conn, sid, task, "42")
        assert note == expected, note
    assert _review_row(conn, sid, "m3-01") is None


def test_plan_prioritizes_due_review(kid):
    from datetime import date, timedelta

    from app.primary import answer, record, today_plan
    conn, sid = kid
    day = date.today() + timedelta(days=200)
    # ошибка по окружающему миру: в плане предмет должен прийти «повтори»
    w3 = _task(conn, "w3-01")
    with conn:
        answer(conn, sid, w3, "неверно")
    row = _review_row(conn, sid, "w3-01")
    assert row["box"] == 0
    # срок ещё завтра — план показывает новое
    world = [x for x in today_plan(conn, sid, 3, day)["items"] if x["subject"] == "world"][0]
    assert world["why"] == "новое"
    # срок наступил — план показывает то же задание «повтори»
    conn.execute("UPDATE primary_review SET due = date('now', '-1 day') WHERE student_id = ?", (sid,))
    world = [x for x in today_plan(conn, sid, 3, day)["items"] if x["subject"] == "world"][0]
    assert world["id"] == "w3-01" and world["why"] == "повтори"


def test_review_of_other_grade_not_shown(kid):
    from app.primary import record, today_plan
    conn, sid = kid
    m4 = _task(conn, "m4-01")
    with conn:
        record(conn, sid, m4, False, "неверно")  # попытка «в 4 классе»
    conn.execute("UPDATE primary_review SET due = '2000-01-01' WHERE student_id = ?", (sid,))
    math = [x for x in today_plan(conn, sid, 3)["items"] if x["subject"] == "math"][0]
    assert math["id"] != "m4-01", "задание другого класса не должно приходить в план 3 класса"


def test_correct_fresh_task_creates_no_review(kid):
    from app.primary import answer, record, today_plan
    conn, sid = kid
    with conn:
        answer(conn, sid, _task(conn, "m3-02"), "72")  # верно с первого раза, не в повторении
    assert _review_row(conn, sid, "m3-02") is None
    # и ничего не сломалось в плане
    assert len(today_plan(conn, sid, 3)["items"]) == 3
