"""Сертификаты для печати: за пройденный мир, новый ранг, окончание курса и грамоты от преподавателя.

Автоматические сертификаты не хранятся в базе — они вычисляются из прогресса, а дата берётся
из момента, когда условие выполнилось. Грамоты преподаватель создаёт сам (таблица certificates).
"""
from .content.lessons import LESSONS, MODULES
from .game import LEVELS


def _world_certs(conn, sid):
    done = {r["num"]: r["done_at"] for r in conn.execute(
        "SELECT num, done_at FROM lesson_state WHERE student_id = ? AND done_at IS NOT NULL", (sid,))}
    certs = []
    for m in MODULES:
        nums = list(m["lessons"])
        if all(n in done for n in nums):
            titles = [l["title"] for l in LESSONS if l["module"] == m["num"]]
            certs.append({"kind": "world", "ref": str(m["num"]), "emoji": m["emoji"],
                          "title": "Мир %d пройден" % m["num"],
                          "heading": "Сертификат",
                          "reason": "за прохождение мира «%s» курса программирования на Python" % m["title"],
                          "details": " · ".join(titles), "date": max(done[n] for n in nums)})
    if LESSONS and all(l["num"] in done for l in LESSONS):
        certs.append({"kind": "course", "ref": "python", "emoji": "🎓", "title": "Курс окончен",
                      "heading": "Сертификат",
                      "reason": "об окончании годового курса программирования на Python",
                      "details": "%d занятий · %d миров · от первой строчки кода до собственного проекта"
                                 % (len(LESSONS), len(MODULES)),
                      "date": max(done.values())})
    return certs


def _rank_certs(conn, sid):
    """Ранг засчитывается в момент, когда сумма трофеев впервые перешагнула порог."""
    certs, total, idx = [], 0, 1
    for e in conn.execute("SELECT amount, created_at FROM xp_events WHERE student_id = ? ORDER BY id", (sid,)):
        total += e["amount"]
        while idx < len(LEVELS) and total >= LEVELS[idx][0]:
            need, title, emoji = LEVELS[idx]
            certs.append({"kind": "rank", "ref": str(idx + 1), "emoji": emoji, "title": "Ранг «%s»" % title,
                          "heading": "Сертификат",
                          "reason": "за достижение ранга «%s» — %d трофеев, заработанных решением задач, "
                                    "домашними заданиями и упорством" % (title, need),
                          "details": "", "date": e["created_at"]})
            idx += 1
    return certs


def _custom_certs(conn, sid):
    return [{"kind": "custom", "ref": str(r["id"]), "emoji": r["emoji"], "title": r["title"],
             "heading": "Грамота", "reason": r["reason"], "details": "", "date": r["issued_at"], "id": r["id"]}
            for r in conn.execute("SELECT * FROM certificates WHERE student_id = ? ORDER BY issued_at, id", (sid,))]


def earned(conn, sid):
    certs = _world_certs(conn, sid) + _rank_certs(conn, sid) + _custom_certs(conn, sid)
    return sorted(certs, key=lambda c: c["date"] or "", reverse=True)


def find(conn, sid, kind, ref):
    return next((c for c in earned(conn, sid) if c["kind"] == kind and c["ref"] == ref), None)


def holder_name(conn, sid):
    row = conn.execute("SELECT full_name, display_name FROM users WHERE id = ?", (sid,)).fetchone()
    return (row["full_name"] or row["display_name"]) if row else "Ученик"
