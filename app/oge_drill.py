"""Тренажёр первой части ОГЭ: попытки, трофеи, статистика по номерам. Варианты — app/content/oge_gen.py."""
import html
import re
from datetime import timedelta

from markupsafe import Markup

from . import config, game
from .content import oge_gen

MASTER_STREAK = 3       # три верных варианта подряд — номер «освоен»


def rich(text):
    """Условие → список абзацев-HTML: переносы строк, **жирный**. Абзац "{code}" — место для программы (шаблон
    подставит её блоком кода)."""
    out = []
    for para in text.split("\n\n"):
        if para == "{code}":
            out.append(None)
            continue
        p = html.escape(para)
        p = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", p).replace("\n", "<br>")
        out.append(Markup(p))
    return out


def _earned_today(conn, sid):
    return conn.execute("SELECT COALESCE(SUM(amount), 0) FROM xp_events WHERE student_id = ? AND kind = 'oge_drill' "
                        "AND created_at >= ?", (sid, config.today().isoformat())).fetchone()[0]


def answer(conn, sid, num, seed, given, record=True):
    v = oge_gen.make(num, seed)
    ok = oge_gen.check(v, given)
    res = {"ok": ok, "answer": v["answer"], "explain": v["explain"], "xp": 0}
    if not record:
        return res
    with conn:
        tried = conn.execute("SELECT 1 FROM oge_drill WHERE student_id = ? AND num = ? AND seed = ?",
                             (sid, num, seed)).fetchone()
        conn.execute("INSERT INTO oge_drill (student_id, num, seed, ok, answer, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (sid, num, seed, 1 if ok else 0, str(given)[:100], game.now_iso()))
        if ok and not tried:          # трофеи — только за вариант, решённый с первой попытки
            xp = max(0, min(oge_gen.XP, oge_gen.DAILY_XP_CAP - _earned_today(conn, sid)))
            if xp:
                game.award(conn, sid, xp, "ОГЭ №%d: тренажёр" % num, "oge_drill", "%d-%d" % (num, seed), quiet=True)
                res["xp"] = xp
    return res


def code_attempt(conn, sid, seed, passed, code):
    """№16: решение проверено в браузере. Трофеи — за вариант, решённый с первой попытки, в общем дневном лимите."""
    res = {"first": False, "xp": 0}
    with conn:
        tried = conn.execute("SELECT 1 FROM oge_drill WHERE student_id = ? AND num = 16 AND seed = ?", (sid, seed)).fetchone()
        conn.execute("INSERT INTO oge_drill (student_id, num, seed, ok, answer, created_at) VALUES (?, 16, ?, ?, ?, ?)",
                     (sid, seed, 1 if passed else 0, code[:100], game.now_iso()))
        if passed and not tried:
            xp = max(0, min(oge_gen.XP, oge_gen.DAILY_XP_CAP - _earned_today(conn, sid)))
            if xp:
                game.award(conn, sid, xp, "ОГЭ №16: тренажёр", "oge_drill", "16-%d" % seed, quiet=True)
            res.update({"first": True, "xp": xp})
    return res


def stats(conn, sid):
    """По номеру: попыток и верных за 30 дней, освоен ли (последние три разных варианта — верно с первого раза)."""
    since = (config.today() - timedelta(days=30)).isoformat()
    out = {}
    for r in conn.execute("SELECT num, COUNT(*) AS n, SUM(ok) AS ok FROM oge_drill WHERE student_id = ? AND created_at >= ? "
                          "GROUP BY num", (sid, since)):
        out[r["num"]] = {"n": r["n"], "ok": r["ok"] or 0, "mastered": False}
    for num in out:
        firsts = conn.execute("SELECT ok FROM oge_drill WHERE id IN (SELECT MIN(id) FROM oge_drill WHERE student_id = ? "
                              "AND num = ? GROUP BY seed) ORDER BY id DESC LIMIT ?", (sid, num, MASTER_STREAK)).fetchall()
        out[num]["mastered"] = len(firsts) == MASTER_STREAK and all(f["ok"] for f in firsts)
    return out
