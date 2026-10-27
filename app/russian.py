"""Русский язык: выдача заданий, проверка, повторение ошибок, статистика по правилам.

Проверка ответа — только на сервере (в браузер правильные запятые и буквы не отдаются до ответа).
Повторение: ошибка → карточка в очереди на завтра; верный ответ при повторении → следующий интервал
1 → 3 → 7 → 14 дней; после 14 — правило считается закреплённым, карточка уходит из очереди.
"""
import json
import random
from datetime import timedelta

from . import config, game
from .content.ru import (DICT_ITEMS, ITEMS, RULES, SECTIONS, check_basis, check_comma, check_dictation, check_spell,
                         spelled)

INTERVALS = [1, 3, 7, 14]
XP_COMMA = 2          # верное предложение в тренажёре запятых
XP_SPELL = 1          # верное слово на арене
XP_REVIEW = 2         # верный ответ при повторении ошибки
DAILY_XP_CAP = 40     # трофеев за русский в день (как у Арены — чтобы не «фармили»)
XP_DICT = (6, 3)      # диктант без ошибок / с одной-двумя; за каждый диктант — раз в день


def today():
    return config.today().isoformat()


def public(item):
    """То, что можно показать до ответа."""
    if item["kind"] == "comma":
        return {"id": item["id"], "kind": "comma", "words": item["words"], "end": item["end"]}
    if item["kind"] == "basis":
        return {"id": item["id"], "kind": "basis", "words": item["words"]}
    return {"id": item["id"], "kind": "spell", "text": item["text"], "options": item["options"]}


def due_items(conn, sid, kind=None):
    rows = conn.execute("SELECT item_id FROM ru_review WHERE student_id = ? AND due <= ? ORDER BY due, item_id",
                        (sid, today())).fetchall()
    return [ITEMS[r[0]] for r in rows if r[0] in ITEMS and (kind is None or ITEMS[r[0]]["kind"] == kind)]


def rule_stats(conn, sid):
    """По каждому правилу: попыток и доля верных за последние 30 дней."""
    since = (config.today() - timedelta(days=30)).isoformat()
    out = {}
    for r in conn.execute("SELECT rule, COUNT(*) AS n, SUM(ok) AS ok FROM ru_attempts WHERE student_id = ? "
                          "AND created_at >= ? GROUP BY rule", (sid, since)):
        out[r["rule"]] = {"n": r["n"], "ok": r["ok"] or 0, "pct": round(100 * (r["ok"] or 0) / r["n"])}
    return out


def pick(conn, sid, kind, exclude=()):
    """Следующее задание: сначала то, что пора повторить, потом — чаще из правил, где больше ошибок."""
    due = [i for i in due_items(conn, sid, kind) if i["id"] not in exclude]
    if due:
        return due[0], True
    recent = {r[0] for r in conn.execute("SELECT item_id FROM ru_attempts WHERE student_id = ? ORDER BY id DESC LIMIT 12",
                                         (sid,))}
    stats = rule_stats(conn, sid)
    pool = [i for i in ITEMS.values() if i["kind"] == kind and i["id"] not in recent and i["id"] not in exclude]
    if not pool:
        pool = [i for i in ITEMS.values() if i["kind"] == kind and i["id"] not in exclude] or \
               [i for i in ITEMS.values() if i["kind"] == kind]

    def weight(item):
        s = stats.get(item["rule"])
        err = 0.5 if not s else 1 - s["pct"] / 100   # новое правило — средний приоритет
        return 0.3 + err
    return random.choices(pool, weights=[weight(i) for i in pool])[0], False


def pick_rule(conn, sid, rule, exclude=()):
    """Задание по одному правилу (кнопка «Потренировать» на странице правил): сначала повторения этого правила."""
    due = [i for i in due_items(conn, sid) if i["rule"] == rule and i["id"] not in exclude]
    if due:
        return due[0]
    pool = [i for i in ITEMS.values() if i["rule"] == rule and i["id"] not in exclude]
    return random.choice(pool) if pool else None


def batch(conn, sid, kind, n=40):
    """Пачка слов для арены: повторения в начале, остальное — случайно с упором на слабые правила."""
    chosen, seen = [], set()
    for _ in range(n):
        item, _ = pick(conn, sid, kind, exclude=seen)
        if item["id"] in seen:
            break
        seen.add(item["id"])
        chosen.append(item)
    return chosen


def _earned_today(conn, sid):
    return conn.execute("SELECT COALESCE(SUM(amount), 0) FROM xp_events WHERE student_id = ? AND kind = 'ru' "
                        "AND created_at >= ?", (sid, today())).fetchone()[0]


def answer(conn, sid, item_id, given, mode, record=True):
    """Проверить ответ, записать попытку, обновить повторение, начислить трофеи. Вызывать вне транзакции.
    record=False — только проверить (преподаватель пробует тренажёр, статистика ученика не трогается)."""
    item = ITEMS.get(item_id)
    if not item:
        raise KeyError(item_id)
    if item["kind"] == "comma":
        ok, extra, missed = check_comma(item, given if isinstance(given, list) else [])
        result = {"ok": ok, "extra": extra, "missed": missed, "gaps": item["gaps"], "text": item["text"]}
        stored = json.dumps(sorted({int(g) for g in given if str(g).isdigit()}) if isinstance(given, list) else [])
    elif item["kind"] == "basis":
        ok, s, p = check_basis(item, given)
        result = {"ok": ok, "s": item["s"], "p": item["p"], "words": item["words"], "text": item["text"]}
        stored = json.dumps({"s": s, "p": p})
    else:
        ok = check_spell(item, str(given))
        result = {"ok": ok, "answer": item["answer"], "text": spelled(item)}
        stored = str(given)[:20]
    title, text = RULES[item["rule"]]
    result.update({"kind": item["kind"], "rule": item["rule"], "rule_title": title, "rule_text": text, "xp": 0})
    if not record:
        return result
    now = game.now_iso()
    with conn:
        conn.execute("INSERT INTO ru_attempts (student_id, item_id, rule, ok, answer, mode, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)", (sid, item_id, item["rule"], 1 if ok else 0, stored, mode, now))
        row = conn.execute("SELECT box, due FROM ru_review WHERE student_id = ? AND item_id = ?", (sid, item_id)).fetchone()
        if not ok:
            due = (config.today() + timedelta(days=1)).isoformat()
            conn.execute("INSERT INTO ru_review (student_id, item_id, box, due) VALUES (?, ?, 0, ?) "
                         "ON CONFLICT(student_id, item_id) DO UPDATE SET box = 0, due = excluded.due", (sid, item_id, due))
            result["review"] = "added"
        elif row and row["due"] <= today():
            box = row["box"] + 1
            if box >= len(INTERVALS):
                conn.execute("DELETE FROM ru_review WHERE student_id = ? AND item_id = ?", (sid, item_id))
                result["review"] = "mastered"
            else:
                due = (config.today() + timedelta(days=INTERVALS[box])).isoformat()
                conn.execute("UPDATE ru_review SET box = ?, due = ? WHERE student_id = ? AND item_id = ?",
                             (box, due, sid, item_id))
                result["review"] = "next:%d" % INTERVALS[box]
        if ok:
            base = XP_REVIEW if mode == "review" else (XP_SPELL if item["kind"] == "spell" else XP_COMMA)
            xp = max(0, min(base, DAILY_XP_CAP - _earned_today(conn, sid)))
            if xp:
                game.award(conn, sid, xp, "Русский: %s" % title, "ru", item_id, quiet=True)
                result["xp"] = xp
        result["cap_reached"] = _earned_today(conn, sid) >= DAILY_XP_CAP
    return result


def overview(conn, sid):
    stats = rule_stats(conn, sid)
    rules = []
    for rid, (title, text) in RULES.items():
        s = stats.get(rid)
        rules.append({"id": rid, "title": title, "text": text, "stats": s})
    weak = sorted([r for r in rules if r["stats"] and r["stats"]["n"] >= 3], key=lambda r: r["stats"]["pct"])[:3]
    waiting = conn.execute("SELECT COUNT(*) FROM ru_review WHERE student_id = ?", (sid,)).fetchone()[0]
    week = conn.execute("SELECT COUNT(*), COALESCE(SUM(ok), 0) FROM ru_attempts WHERE student_id = ? AND created_at >= ?",
                        (sid, (config.today() - timedelta(days=6)).isoformat())).fetchone()
    by_id = {r["id"]: r for r in rules}
    sections = [(title, [by_id[r] for r in ids]) for title, ids in SECTIONS]
    return {"rules": rules, "sections": sections, "weak": weak, "due": len(due_items(conn, sid)), "waiting": waiting,
            "week_n": week[0], "week_ok": week[1], "earned_today": _earned_today(conn, sid), "cap": DAILY_XP_CAP}


def teacher_view(conn, sid):
    """Для профиля ученика у преподавателя: слабые правила и последние ошибки с ответом ученика."""
    ov = overview(conn, sid)
    mistakes = []
    for r in conn.execute("SELECT item_id, answer, created_at FROM ru_attempts WHERE student_id = ? AND ok = 0 "
                          "ORDER BY id DESC LIMIT 12", (sid,)):
        item = ITEMS.get(r["item_id"])
        if not item:
            continue
        if item["kind"] == "spell":
            given = r["answer"] or "—"
        elif item["kind"] == "comma":
            gaps = set(json.loads(r["answer"] or "[]"))
            given = " ".join(w + ("," if i in gaps else "") for i, w in enumerate(item["words"])) + item["end"]
        else:
            given = "основа указана неверно"
        mistakes.append({"right": spelled(item) if item["kind"] == "spell" else item["text"], "given": given,
                         "rule": RULES[item["rule"]][0], "at": r["created_at"]})
    ov["mistakes"] = mistakes
    ov["struggling"] = [r for r in ov["rules"] if r["stats"] and r["stats"]["n"] >= 6 and r["stats"]["pct"] < 60]
    return ov


# ------------------------------------------------------------------ диктант
def dict_public(d):
    return {"id": d["id"], "title": d["title"], "can": d["can"],
            "words": [[p if isinstance(p, str) else {"g": p["g"], "options": d["letters"][p["g"]]["options"]}
                       for p in parts] for parts in d["words"]]}


def dict_pick(conn, sid):
    """Диктант, который ученик давно не писал (или не писал вовсе)."""
    last = {r["d"]: r["at"] for r in conn.execute(
        "SELECT substr(item_id, 1, instr(item_id, ':') - 1) AS d, MAX(created_at) AS at FROM ru_attempts "
        "WHERE student_id = ? AND mode = 'dict' GROUP BY d", (sid,))}
    return min(DICT_ITEMS.values(), key=lambda d: (last.get(d["id"], ""), random.random()))


def dict_answer(conn, sid, did, letters, commas, record=True):
    """Проверка диктанта. Каждый пропуск буквы и каждая нужная запятая пишутся попыткой по своему правилу —
    так ошибки диктанта попадают в «Что подтянуть» и в сигналы преподавателю. Лишние запятые — только в счёт ошибок."""
    d = DICT_ITEMS[did]
    res = check_dictation(d, letters, commas)
    res.update({"text": d["text"], "xp": 0,
                "rules": sorted({RULES[x["rule"]][0] for x in res["letters"] if not x["ok"]} |
                                {RULES[d["need"][i]][0] for i in res["missing"]})})
    if not record:
        return res
    now = game.now_iso()
    with conn:
        for i, x in enumerate(res["letters"]):
            given = letters[i] if isinstance(letters, list) and i < len(letters) else ""
            conn.execute("INSERT INTO ru_attempts (student_id, item_id, rule, ok, answer, mode, created_at) "
                         "VALUES (?, ?, ?, ?, ?, 'dict', ?)", (sid, "%s:L%d" % (did, i), x["rule"], 1 if x["ok"] else 0,
                                                               str(given)[:20], now))
        for i in res["need"]:
            conn.execute("INSERT INTO ru_attempts (student_id, item_id, rule, ok, answer, mode, created_at) "
                         "VALUES (?, ?, ?, ?, '', 'dict', ?)", (sid, "%s:C%d" % (did, i), d["need"][i],
                                                                0 if i in res["missing"] else 1, now))
        base = XP_DICT[0] if res["errors"] == 0 else (XP_DICT[1] if res["errors"] <= 2 else 0)
        ref = "dict:%s:%s" % (did, today())
        if base and not game.awarded(conn, sid, "ru", ref):
            xp = max(0, min(base, DAILY_XP_CAP - _earned_today(conn, sid)))
            if xp:
                game.award(conn, sid, xp, "Русский: диктант «%s»" % d["title"], "ru", ref, quiet=True)
                res["xp"] = xp
    return res
