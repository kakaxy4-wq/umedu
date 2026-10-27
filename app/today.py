"""«План на сегодня» — ритуал на 10–15 минут вместо россыпи разделов (как ежедневная сессия у LogicLike).

3–4 шага из того, что уже есть на сайте: задача дня, повторение ошибок по русскому (или 5 заданий), 3 варианта
ОГЭ по самому слабому номеру, одна новая задача текущего урока. Шаг считается сделанным по реальным событиям в
базе за сегодня — отдельного учёта нет. Весь план — сундук (дроп) один раз в день.
"""
from . import config, game, oge_drill, russian, season, subjects, students
from .content.tasks import TASKS
from .forecast import EASY_FIRST as OGE_START_ORDER

RU_MIN = 5            # заданий по русскому, если повторять нечего
OGE_MIN = 3           # вариантов ОГЭ


def _today():
    return config.today().isoformat()


def _count(conn, sql, *args):
    return conn.execute(sql, args).fetchone()[0]


def _oge_pick(conn, sid):
    """Номер для тренировки: начатый и не освоенный с худшей точностью, иначе следующий по порядку."""
    st = oge_drill.stats(conn, sid)
    started = [(v["ok"] / v["n"], n) for n, v in st.items() if v["n"] and not v["mastered"]]
    if started:
        return min(started)[1]
    for n in OGE_START_ORDER:
        if not st.get(n, {}).get("mastered"):
            return n
    return OGE_START_ORDER[0]


def plan(conn, sid):
    day = _today()
    subj = subjects.of(students.get_student(conn, sid))
    steps = []
    if "python" in subj:
        daily = game.get_daily(conn, sid)
        steps.append({"key": "daily", "emoji": "☀️", "title": "Задача дня", "href": "/daily" if daily["kind"] == "quiz"
                      else "/task/%s" % daily["ref"], "done": bool(daily.get("finished_at")),
                      "note": "серия 🔥 не прервётся"})
    if "russian" in subj:
        due = len(russian.due_items(conn, sid))
        done_today = _count(conn, "SELECT COUNT(*) FROM ru_attempts WHERE student_id = ? AND created_at >= ?", sid, day)
        if due:
            steps.append({"key": "ru", "emoji": "🔁", "title": "Русский: повторить ошибки", "href": "/ru/review",
                          "done": False, "note": "на сегодня — %d" % due})
        else:
            steps.append({"key": "ru", "emoji": "✍️", "title": "Русский: %d заданий" % RU_MIN, "href": "/ru/commas",
                          "done": done_today >= RU_MIN, "note": "сделано %d из %d" % (min(done_today, RU_MIN), RU_MIN)})
    if "python" in subj:
        num = _oge_pick(conn, sid)
        n = _count(conn, "SELECT COUNT(*) FROM oge_drill WHERE student_id = ? AND created_at >= ?", sid, day)
        steps.append({"key": "oge", "emoji": "🎯", "title": "ОГЭ №%d: %d варианта" % (num, OGE_MIN),
                      "href": "/oge/drill/%d" % num, "done": n >= OGE_MIN,
                      "note": "сделано %d из %d" % (min(n, OGE_MIN), OGE_MIN)})
        upto = game.unlocked_upto(conn, sid)
        solved = game.solved_task_ids(conn, sid)
        fresh = [t for t in TASKS if t["lesson"] <= upto and t["id"] not in solved]
        new_today = _count(conn, "SELECT COUNT(*) FROM xp_events WHERE student_id = ? AND kind = 'task' AND created_at >= ?",
                           sid, day)
        if fresh or new_today:
            t = fresh[0] if fresh else None
            steps.append({"key": "task", "emoji": "🐍", "title": "Новая задача" + (": «%s»" % t["title"] if t and not new_today else ""),
                          "href": "/task/%s" % t["id"] if t else "/map", "done": bool(new_today),
                          "note": "из открытых уроков"})
    done = sum(1 for s in steps if s["done"])
    claimed = bool(conn.execute("SELECT 1 FROM xp_events WHERE student_id = ? AND kind = 'drop' AND ref = ?",
                                (sid, "today:" + day)).fetchone())
    return {"steps": steps, "done": done, "total": len(steps), "complete": bool(steps) and done == len(steps),
            "claimed": claimed}


def claim(conn, sid):
    """Сундук за весь план — один раз в день. Вызывать внутри `with conn:`."""
    p = plan(conn, sid)
    if not p["complete"] or p["claimed"]:
        return None
    return season.roll_drop(conn, sid, "план на сегодня", ref="today:" + _today())
