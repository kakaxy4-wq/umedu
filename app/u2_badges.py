"""Достижения umedu 2.0. Игра здесь — серия дней и значки, без монет и лавки.

Значок, однажды полученный, остаётся: серия считается по всем дням в журнале попыток,
а не только по текущей. Пробник и опыт отмечаются в момент, когда ученик их сделал.
"""
from datetime import date

from . import knowledge as kn

BADGES = (
    ("first_task", "Первый номер", "Решил первый номер"),
    ("streak_3", "Три дня подряд", "Занимался 3 дня без пропуска"),
    ("streak_7", "Неделя подряд", "Занимался 7 дней без пропуска"),
    ("streak_30", "Месяц подряд", "Занимался 30 дней без пропуска"),
    ("first_mastered", "Номер освоен", "Три верных ответа подряд по одному номеру"),
    ("first_mock", "Первый пробник", "Сдал первый мини-пробник"),
    ("first_lab", "Первый опыт", "Открыл опыт в лаборатории"),
)


def list_for(conn, sid):
    have = {r["code"]: r["earned_at"] for r in conn.execute(
        "SELECT code, earned_at FROM u2_badge WHERE student_id = ?", (sid,))}
    return [{"code": code, "title": title, "text": text, "earned": code in have, "at": have.get(code)}
            for code, title, text in BADGES]


def sync(conn, sid, today, mock=False, lab=False):
    """Записывает значки, которые уже следуют из журнала. Повторный вызов ничего не дублирует."""
    today = today or date.today()
    have = {r[0] for r in conn.execute("SELECT code FROM u2_badge WHERE student_id = ?", (sid,))}
    want = set()
    days = {date.fromisoformat(d) for (d,) in conn.execute(
        "SELECT DISTINCT day FROM skill_attempt WHERE student_id = ?", (sid,))}
    if days:
        want.add("first_task")
    best = _best_streak(days)
    if best >= 3:
        want.add("streak_3")
    if best >= 7:
        want.add("streak_7")
    if best >= 30:
        want.add("streak_30")
    if "first_mastered" not in have and _mastered(conn, sid):
        want.add("first_mastered")
    if mock:
        want.add("first_mock")
    if lab:
        want.add("first_lab")
    fresh = want - have
    if not fresh:
        return []
    with conn:
        for code in sorted(fresh):
            conn.execute("INSERT OR IGNORE INTO u2_badge (student_id, code, earned_at) VALUES (?, ?, ?)",
                         (sid, code, today.isoformat()))
    return sorted(fresh)


def _best_streak(days):
    if not days:
        return 0
    ordered = sorted(days)
    best = cur = 1
    for prev, nxt in zip(ordered, ordered[1:]):
        gap = (nxt - prev).days
        if gap == 1:
            cur += 1
            best = max(best, cur)
        elif gap > 1:
            cur = 1
    return best


def _mastered(conn, sid):
    exams = [r[0] for r in conn.execute("SELECT exam_id FROM exam_enroll WHERE student_id = ?", (sid,))]
    for exam_id in exams:
        if any(s["streak"] >= kn.MASTERED_STREAK for s in kn.streaks(conn, sid, exam_id).values()):
            return True
    return False
