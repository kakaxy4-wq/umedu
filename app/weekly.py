"""Недельная сводка преподавателю: что каждый ученик сделал за 7 дней и на что обратить внимание.

Видна всегда на странице /teacher/weekly. В Telegram уходит сама по воскресеньям в 19:00 (по CQ_TIMEZONE),
если в .env заданы CQ_TELEGRAM_TOKEN и CQ_TELEGRAM_CHAT_ID; отправка отмечается в settings, чтобы не повторяться
после перезапуска. Расписание — фоновая задача приложения (systemd-таймер не нужен).
"""
import asyncio
import logging
from datetime import timedelta

from . import config, forecast, game, notify, students, subjects
from .db import connect, get_setting, set_setting

log = logging.getLogger("codequest.weekly")

SEND_WEEKDAY = 6        # воскресенье
SEND_HOUR = 19
CHECK_EVERY = 600       # секунд


def _count(conn, sql, *args):
    return conn.execute(sql, args).fetchone()[0]


def student_week(conn, st, since):
    sid = st["id"]
    ru_n = _count(conn, "SELECT COUNT(*) FROM ru_attempts WHERE student_id = ? AND created_at >= ?", sid, since)
    ru_ok = _count(conn, "SELECT COALESCE(SUM(ok), 0) FROM ru_attempts WHERE student_id = ? AND created_at >= ?", sid, since)
    days = {r[0] for t in ("xp_events", "task_attempts", "ru_attempts", "robot_attempts")
            for r in conn.execute("SELECT DISTINCT substr(created_at, 1, 10) FROM %s WHERE student_id = ? "
                                  "AND created_at >= ?" % t, (sid, since))}
    return {
        "student": st,
        "xp": _count(conn, "SELECT COALESCE(SUM(amount), 0) FROM xp_events WHERE student_id = ? AND created_at >= ?", sid, since),
        "days": len(days),
        "tasks": _count(conn, "SELECT COUNT(*) FROM xp_events WHERE student_id = ? AND kind = 'task' AND created_at >= ?", sid, since),
        "attempts": _count(conn, "SELECT COUNT(*) FROM task_attempts WHERE student_id = ? AND created_at >= ?", sid, since),
        "robot": _count(conn, "SELECT COUNT(*) FROM xp_events WHERE student_id = ? AND kind = 'robot' AND created_at >= ?", sid, since),
        "lessons": [r[0] for r in conn.execute("SELECT num FROM lesson_state WHERE student_id = ? AND done_at >= ? ORDER BY num",
                                               (sid, since))],
        "checks": [(r["check_id"], r["right_count"], r["total"]) for r in conn.execute(
            "SELECT check_id, right_count, total FROM check_results WHERE student_id = ? AND finished_at >= ?", (sid, since))],
        "homework": _count(conn, "SELECT COUNT(*) FROM submissions WHERE student_id = ? AND created_at >= ?", sid, since),
        "ru": (ru_n, round(100 * ru_ok / ru_n) if ru_n else 0),
        "upto": game.unlocked_upto(conn, sid),
        "plans": _count(conn, "SELECT COUNT(*) FROM xp_events WHERE student_id = ? AND kind = 'drop' AND ref LIKE 'today:%' "
                              "AND created_at >= ?", sid, since),
        "oge": _count(conn, "SELECT COUNT(*) FROM oge_drill WHERE student_id = ? AND created_at >= ?", sid, since),
        "fc": _forecast(conn, st),
    }


def _forecast(conn, st):
    """Прогноз ОГЭ — только если у ученика Python и сайт уже видел хоть один номер."""
    if "python" not in subjects.of(st):
        return None
    from .main import oge_progress          # main импортирует weekly — поэтому здесь, а не наверху
    fc = forecast.forecast(oge_progress(conn, st["id"]))
    return fc if fc["known"] else None


def build(conn, today=None):
    today = today or config.today()
    since = (today - timedelta(days=6)).isoformat()
    alerts = students.alerts(conn)
    rows = []
    for st in students.list_students(conn):
        w = student_week(conn, st, since)
        w["alerts"] = [a for a in alerts if a["student_id"] == st["id"]]
        rows.append(w)
    rows.sort(key=lambda w: -w["xp"])
    return {"from": today - timedelta(days=6), "to": today, "rows": rows}


def _plural(n, one, few, many):
    n10, n100 = n % 10, n % 100
    word = one if n10 == 1 and n100 != 11 else (few if 2 <= n10 <= 4 and not 12 <= n100 <= 14 else many)
    return "%d %s" % (n, word)


def text(summary):
    """Сводка простым текстом для Telegram (лимит сообщения — 4096 символов)."""
    lines = ["📊 КодКвест: неделя %s — %s" % (summary["from"].strftime("%d.%m"), summary["to"].strftime("%d.%m"))]
    if not summary["rows"]:
        lines.append("Активных учеников нет.")
    for w in summary["rows"]:
        st = w["student"]
        lines.append("")
        if not w["days"]:
            lines.append("😴 %s — на этой неделе не занимался(ась) на сайте" % st["display_name"])
        else:
            lines.append("👤 %s — +%d 🏆, %s из 7" % (st["display_name"], w["xp"], _plural(w["days"], "день", "дня", "дней")))
            parts = []
            if w["lessons"]:
                parts.append("уроки " + ", ".join(map(str, w["lessons"])) + " проведены")
            if w["tasks"]:
                parts.append("решено задач: %d (попыток %d)" % (w["tasks"], w["attempts"]))
            if w["plans"]:
                parts.append("план дня выполнен: %s" % _plural(w["plans"], "раз", "раза", "раз"))
            if w["oge"]:
                parts.append("тренажёр ОГЭ: %s" % _plural(w["oge"], "вариант", "варианта", "вариантов"))
            if w["robot"]:
                parts.append("Робот ОГЭ: %d" % w["robot"])
            if w["ru"][0]:
                parts.append("русский: %d ответов, верно %d%%" % w["ru"])
            if w["homework"]:
                parts.append("домашек сдано: %d" % w["homework"])
            for cid, right, total in w["checks"]:
                parts.append("проверка %s: %d/%d" % (cid, right, total))
            for p in parts:
                lines.append("   • " + p)
        lines.append("   сейчас открыт урок %d" % w["upto"])
        if w["fc"]:
            lines.append("   🎯 прогноз ОГЭ: %d из %d — «%d»" % (w["fc"]["points"], w["fc"]["max"], w["fc"]["grade"]))
        for a in w["alerts"][:3]:
            lines.append("   %s %s" % (a["emoji"], a["text"]))
    if config.BASE_URL:
        lines += ["", config.BASE_URL + "/teacher/weekly"]
    out = "\n".join(lines)
    return out if len(out) <= 4000 else out[:3990] + "\n…"


def configured():
    return bool(config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID)


def week_key(day):
    y, w, _ = day.isocalendar()
    return "%d-W%02d" % (y, w)


def due(now, last_sent):
    return now.weekday() == SEND_WEEKDAY and now.hour >= SEND_HOUR and last_sent != week_key(now.date())


def send_if_due():
    """Отправляет сводку, если пора и на этой неделе ещё не отправляли. Возвращает True, если отправила."""
    if not configured():
        return False
    conn = connect()
    try:
        now = config.now()
        if not due(now, get_setting(conn, "weekly_sent")):
            return False
        with conn:
            set_setting(conn, "weekly_sent", week_key(now.date()))
        notify.send_now(text(build(conn)))
        return True
    finally:
        conn.close()


async def scheduler():
    from . import parent_bot              # parent_bot импортирует weekly
    while True:
        for job in (send_if_due, parent_bot.send_if_due):
            try:
                await asyncio.to_thread(job)
            except Exception:  # сводка не должна ронять сайт
                log.exception("weekly summary failed")
        await asyncio.sleep(CHECK_EVERY)
