"""Аналитика для преподавателя: кто занимается, где бросают, что не получается.

Дни активности считаются по всем следам — events, трофеи, попытки задач, тренажёр ОГЭ, русский, —
поэтому история видна и до появления таблицы events (27.10.2026).
"""
from collections import Counter, defaultdict
from datetime import timedelta

from . import config, events
from .content.ru import RULES
from .content.tasks import TASK_BY_ID

WINDOW = 28
_TRACES = (("events", "user_id"), ("xp_events", "student_id"), ("task_attempts", "student_id"),
           ("oge_drill", "student_id"), ("ru_attempts", "student_id"))


def _students(conn):
    return [dict(r) for r in conn.execute(
        "SELECT id, display_name, last_seen_at, created_at FROM users WHERE role = 'student' AND active = 1 "
        "ORDER BY display_name COLLATE NOCASE")]


def active_days(conn, since=None):
    """{student_id: set(дат 'YYYY-MM-DD')} по всем следам активности."""
    days = defaultdict(set)
    for table, col in _TRACES:
        sql = "SELECT %s, substr(created_at, 1, 10) FROM %s" % (col, table)
        args = ()
        if table == "events":
            sql += " WHERE role = 'student'"
        if since:
            sql += (" AND" if "WHERE" in sql else " WHERE") + " created_at >= ?"
            args = (since,)
        for sid, day in conn.execute(sql + " GROUP BY 1, 2", args):
            days[sid].add(day)
    return days


def _first_hits(conn):
    """Шаги воронки: у кого из учеников было хоть раз."""
    q = lambda sql: {r[0] for r in conn.execute(sql)}            # noqa: E731
    return {
        "solved": q("SELECT DISTINCT student_id FROM task_attempts WHERE passed = 1"),
        "today": q("SELECT DISTINCT student_id FROM xp_events WHERE kind = 'drop' AND ref LIKE 'today:%'"),
        "oge": q("SELECT DISTINCT student_id FROM oge_drill"),
        "ru": q("SELECT DISTINCT student_id FROM ru_attempts"),
    }


def report(conn):
    today = config.today()
    since = (today - timedelta(days=WINDOW - 1)).isoformat()
    week = (today - timedelta(days=6)).isoformat()
    fortnight = (today - timedelta(days=13)).isoformat()
    studs = _students(conn)
    ids = {s["id"] for s in studs}
    all_days = active_days(conn)
    n = len(studs)

    # --- активность по дням
    chart = []
    for i in range(WINDOW - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        chart.append({"day": d, "students": sum(1 for sid in ids if d in all_days.get(sid, ()))})
    peak = max([c["students"] for c in chart] + [1])

    def active_in(sid, start):
        return len([d for d in all_days.get(sid, ()) if d >= start])

    summary = {
        "students": n,
        "today": sum(1 for sid in ids if today.isoformat() in all_days.get(sid, ())),
        "week": sum(1 for sid in ids if active_in(sid, week)),
        "month": sum(1 for sid in ids if active_in(sid, since)),
        "avg_days_week": round(sum(active_in(sid, week) for sid in ids) / n, 1) if n else 0,
    }

    # --- воронка
    hits = _first_hits(conn)
    seen = {sid for sid in ids if all_days.get(sid)} | {s["id"] for s in studs if s["last_seen_at"]}
    steps = [
        ("Учётка создана", ids),
        ("Заходили на сайт", seen),
        ("Решили первую задачу", hits["solved"] & ids),
        ("Забирали сундук плана дня", hits["today"] & ids),
        ("Занимались 3+ разных дня", {sid for sid in ids if len(all_days.get(sid, ())) >= 3}),
        ("Держат ритм: 3+ дня из последних 14", {sid for sid in ids if active_in(sid, fortnight) >= 3}),
    ]
    funnel = [{"title": t, "count": len(s), "pct": round(100 * len(s) / n) if n else 0} for t, s in steps]

    # --- где уходят: последняя открытая страница дня
    exits = Counter()
    last_page = {}
    rows = conn.execute("SELECT user_id, substr(created_at, 1, 10) AS day, route, created_at FROM events "
                        "WHERE role = 'student' AND kind = 'view' AND created_at >= ? ORDER BY created_at", (since,))
    last_of_day = {}
    for r in rows:
        if r["user_id"] in ids:
            last_of_day[(r["user_id"], r["day"])] = r["route"]
            last_page[r["user_id"]] = (r["route"], r["created_at"])
    exits.update(last_of_day.values())
    total_exits = sum(exits.values())
    exit_rows = [{"route": route, "section": events.section(route)[0], "what": events.section(route)[1], "count": c,
                  "pct": round(100 * c / total_exits)} for route, c in exits.most_common(8)]

    # --- разделы за неделю
    sec_views, sec_users = Counter(), defaultdict(set)
    for r in conn.execute("SELECT user_id, route FROM events WHERE role = 'student' AND created_at >= ?", (week,)):
        if r["user_id"] in ids:
            sec = events.section(r["route"])[0]
            sec_views[sec] += 1
            sec_users[sec].add(r["user_id"])
    sections = [{"section": s, "events": c, "students": len(sec_users[s])} for s, c in sec_views.most_common()]

    # --- задачи, на которых застревают: пробовал, но так и не решил
    stuck = defaultdict(lambda: {"students": set(), "fails": 0})
    solved = {(r[0], r[1]) for r in conn.execute("SELECT DISTINCT student_id, task_id FROM task_attempts WHERE passed = 1")}
    for r in conn.execute("SELECT student_id, task_id, COUNT(*) FROM task_attempts WHERE passed = 0 GROUP BY 1, 2"):
        if r[0] in ids and (r[0], r[1]) not in solved and r[1] in TASK_BY_ID:
            stuck[r[1]]["students"].add(r[0])
            stuck[r[1]]["fails"] += r[2]
    stuck_rows = sorted(({"task": TASK_BY_ID[t], "students": len(v["students"]), "fails": v["fails"]}
                         for t, v in stuck.items()), key=lambda x: (-x["students"], -x["fails"]))[:8]

    # --- слабые места: номера ОГЭ и правила русского за 4 недели (от 5 ответов)
    oge = [{"num": r[0], "n": r[1], "pct": round(100 * r[2] / r[1])} for r in conn.execute(
        "SELECT num, COUNT(*), SUM(ok) FROM oge_drill WHERE created_at >= ? GROUP BY num HAVING COUNT(*) >= 5 "
        "ORDER BY 1.0 * SUM(ok) / COUNT(*) LIMIT 5", (since,))]
    ru = [{"rule": RULES.get(r[0], (r[0],))[0], "n": r[1], "pct": round(100 * r[2] / r[1])} for r in conn.execute(
        "SELECT rule, COUNT(*), SUM(ok) FROM ru_attempts WHERE created_at >= ? GROUP BY rule HAVING COUNT(*) >= 5 "
        "ORDER BY 1.0 * SUM(ok) / COUNT(*) LIMIT 5", (since,))]

    # --- по ученикам
    solved_week = Counter(r[0] for r in conn.execute(
        "SELECT student_id, task_id FROM task_attempts WHERE passed = 1 AND created_at >= ? GROUP BY 1, 2", (week,)))
    people = []
    for s in studs:
        sid = s["id"]
        page = last_page.get(sid)
        days = sorted(all_days.get(sid, ()))
        people.append({"st": s, "week": active_in(sid, week), "month": active_in(sid, since),
                       "last_day": days[-1] if days else None, "solved_week": solved_week.get(sid, 0),
                       "last_page": events.section(page[0])[1] if page else None})
    people.sort(key=lambda p: (p["week"], p["month"]))                # сначала те, кто выпадает

    return {"summary": summary, "chart": chart, "peak": peak, "funnel": funnel, "exits": exit_rows,
            "sections": sections, "stuck": stuck_rows, "oge": oge, "ru": ru, "people": people,
            "has_events": bool(conn.execute("SELECT 1 FROM events LIMIT 1").fetchone()), "window": WINDOW}
