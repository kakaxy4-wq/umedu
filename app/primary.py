"""Начальная школа в umedu: 3 и 4 класс.

Работает только при CQ_UMEDU2 и не на сайте химии. ОГЭ, Python, игры и модели
этому ученику не показываем. Ответы лежат в primary_attempt и не входят в прогноз экзамена.
"""
import ast
import re
from datetime import timedelta

from . import config, game
from .content.primary_gen import count_solved as _gen_count
from .content.primary_gen import has_kinds as _gen_has
from .content.primary_gen import make_random as _gen_random
from .content.primary_gen import task_by_id as _gen_task
from .content.primary_tasks import TASKS

# Ошибка — повтор завтра; верный ответ по расписанию — через 1, 3, 7, 14 дней, потом «выучено».
# Как в «Русском» у старших (russian.INTERVALS).
REVIEW_INTERVALS = [1, 3, 7, 14]

SUBJECTS = (
    {"id": "math", "title": "Математика", "emoji": "🔢"},
    {"id": "russian", "title": "Русский язык", "emoji": "📖"},
    {"id": "world", "title": "Окружающий мир", "emoji": "🌍"},
)
SUBJECT_BY_ID = {s["id"]: s for s in SUBJECTS}
BY_ID = {t["id"]: t for t in TASKS}

# Страницы средних классов и игр. /u2/subjects не прячем: это не /u2/subject/.
_HIDE = re.compile(
    r"^/(?:oge|bots|season|shop|playground|trainer|lesson|task|homework|today|checks|map|"
    r"achievements|ru|certificate|certificates|portfolio|gallery|cheatsheet|robot|daily|"
    r"snippets)(?:/|$)"
    r"|^/api/(?:robot|bots|ru|trainer|task|run|daily)(?:/|$)"
    r"|^/u2/(?:models|lab|mock|start|train|diag|how|mistakes)(?:/|$)"
    r"|^/u2/subject/"
)


def hidden_path(path):
    return bool(_HIDE.match(path or ""))


def norm(text):
    s = str(text or "").strip().lower().replace("ё", "е")
    s = s.replace("\u00a0", " ").replace("−", "-").replace("–", "-").replace("—", "-")
    for ch in ",.;:!?«»\"'()°":
        s = s.replace(ch, " ")
    return re.sub(r"\s+", " ", s).strip()


def check(task, given):
    g = norm(given)
    return bool(g) and any(g == norm(a) for a in task["accept"])


def tasks_for(grade, subject=None):
    return [t for t in TASKS if t["grade"] == grade and (subject is None or t["subject"] == subject)]


def public(task):
    numeric = not task["choices"] and all(re.fullmatch(r"\d+", a) for a in task["accept"])
    return {"id": task["id"], "grade": task["grade"], "subject": task["subject"], "topic": task["topic"],
            "prompt": task["prompt"], "choices": task["choices"], "numeric": numeric,
            "hint": task.get("hint", ""),
            "letter": not task["choices"] and not numeric and all(len(a) == 1 for a in task["accept"])}


def get_task(task_id):
    """Статичное задание или сгенерированное (id вида gen-...). Неизвестный id — None."""
    return BY_ID.get(task_id) or _gen_task(task_id)


def _solved(conn, sid):
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT task_id FROM primary_attempt WHERE student_id = ? AND ok = 1", (sid,))}


def _due_review(conn, sid, grade):
    """Задания, пришедшие по расписанию повторения (due <= сегодня), старшие — первыми."""
    today = config.today().isoformat()
    out = []
    for r in conn.execute("SELECT task_id FROM primary_review WHERE student_id = ? AND due <= ? "
                          "ORDER BY due, task_id", (sid, today)):
        t = get_task(r["task_id"])
        if t and t["grade"] == grade:
            out.append(t)
    return out


DAY_GOAL = 3


def _pick_subject(conn, sid, grade, subj, done, due):
    """Одно задание предмета: повторение по расписанию, потом новое (генератор/статика), иначе повтор."""
    pool = tasks_for(grade, subj["id"])
    fresh = [t for t in pool if t["id"] not in done]
    rev = next((t for t in due if t["subject"] == subj["id"]), None)
    if rev:
        return rev, "повтори"
    gen_task = None
    if _gen_has(grade, subj["id"]):
        pool_ids = {t["id"] for t in pool}
        gen_done = _gen_count(done, grade, subj["id"])
        static_done = len([d for d in done if d in pool_ids])
        if gen_done < static_done or not fresh:
            gen_task = _gen_random(grade, subj["id"], done)
    if gen_task:
        return gen_task, "новое"
    if fresh:
        return fresh[0], "новое"
    return pool[0], "повтори"


def _day_rows(conn, sid, grade, today):
    """Три задания дня фиксируются при первом заходе и не подменяются новыми."""
    day = today.isoformat()
    rows = list(conn.execute(
        "SELECT slot, task_id FROM primary_day WHERE student_id = ? AND day = ? ORDER BY slot", (sid, day)))
    if len(rows) == DAY_GOAL:
        tasks = [get_task(r[1]) for r in rows]
        if all(t and t["grade"] == grade for t in tasks):
            return tasks
    done = _solved(conn, sid)
    due = _due_review(conn, sid, grade)
    picks = []
    for subj in SUBJECTS:
        pick, why = _pick_subject(conn, sid, grade, subj, done, due)
        picks.append(pick)
    conn.execute("DELETE FROM primary_day WHERE student_id = ? AND day = ?", (sid, day))
    for slot, task in enumerate(picks):
        conn.execute("INSERT INTO primary_day (student_id, day, slot, task_id) VALUES (?, ?, ?, ?)",
                     (sid, day, slot, task["id"]))
    return picks


def _solved_on(conn, sid, today):
    prefix = today.isoformat()
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT task_id FROM primary_attempt WHERE student_id = ? AND ok = 1 AND created_at LIKE ?",
        (sid, prefix + "%"))}


def today_plan(conn, sid, grade, today=None):
    """Три карточки дня. Задания фиксируются на день: после трёх верных ответов
    день закрыт, новые задания не подставляются. Повторение по расписанию и
    генераторы учитываются при подборе, «готово» видно после верного ответа."""
    today = today or config.today()
    solved_today = _solved_on(conn, sid, today)
    due = _due_review(conn, sid, grade)
    out = []
    for task in _day_rows(conn, sid, grade, today):
        subj = SUBJECT_BY_ID[task["subject"]]
        done = task["id"] in solved_today
        why = "готово" if done else next(("повтори" for t in due if t["id"] == task["id"]), "новое")
        out.append({**public(task), "why": why, "done": done,
                    "subject_title": subj["title"], "emoji": subj["emoji"]})
    done_n = sum(1 for it in out if it["done"])
    return {"items": out, "done": done_n, "goal": DAY_GOAL, "finished": done_n >= DAY_GOAL}


def trailing_misses(conn, sid, task_id):
    n = 0
    for (ok,) in conn.execute(
            "SELECT ok FROM primary_attempt WHERE student_id = ? AND task_id = ? ORDER BY id DESC LIMIT 2",
            (sid, task_id)):
        if ok:
            break
        n += 1
    return n


def hint_for(task):
    """Подсказка без правильного ответа: его показываем только после второй ошибки."""
    answer = str(task["accept"][0])
    explain = task["explain"]
    if answer and answer in explain:
        return "Посмотри на числа в условии и проверь действие. Правильный ответ покажем после второй попытки."
    return explain


def groups(grade, subject, solved):
    out = []
    for t in tasks_for(grade, subject):
        item = {**public(t), "done": t["id"] in solved}
        if not out or out[-1]["topic"] != t["topic"]:
            out.append({"topic": t["topic"], "tasks": [item]})
        else:
            out[-1]["tasks"].append(item)
    return out


def summary(conn, sid, grade):
    solved = _solved(conn, sid)
    subjects = []
    for subj in SUBJECTS:
        pool = tasks_for(grade, subj["id"])
        subjects.append({**subj, "done": sum(1 for t in pool if t["id"] in solved), "total": len(pool)})
    recent = []
    for r in conn.execute(
            "SELECT task_id, ok FROM primary_attempt WHERE student_id = ? ORDER BY id DESC LIMIT 5", (sid,)):
        t = get_task(r["task_id"])
        if not t or t["grade"] != grade:
            continue
        recent.append({"prompt": t["prompt"], "ok": bool(r["ok"]), "topic": t["topic"],
                       "title": SUBJECT_BY_ID[t["subject"]]["title"]})
    return {"subjects": subjects, "recent": recent}


def subject_view(conn, sid, grade, subject_id):
    subj = SUBJECT_BY_ID.get(subject_id)
    if not subj:
        return None
    solved = _solved(conn, sid)
    pool = tasks_for(grade, subject_id)
    return {"subject": subj, "groups": groups(grade, subject_id, solved),
            "done": sum(1 for t in pool if t["id"] in solved), "total": len(pool)}


def answer(conn, sid, task, given):
    """Пишет попытку и двигает расписание повторения.

    Возвращает (верно, следующее задание или None, пометка ученику или None).
    Вызывать внутри `with conn`.
    """
    ok = check(task, given)
    note = record(conn, sid, task, ok, given)
    nxt = next_open(task["grade"], task["subject"], task["id"], _solved(conn, sid))
    return ok, nxt, note


def record(conn, sid, task, ok, given):
    """Пишет попытку и ведёт расписание повторения. Возвращает пометку ученику или None."""
    conn.execute(
        "INSERT INTO primary_attempt (student_id, task_id, ok, given, created_at) VALUES (?, ?, ?, ?, ?)",
        (sid, task["id"], 1 if ok else 0, str(given or "")[:200], game.now_iso()))
    row = conn.execute("SELECT box, due FROM primary_review WHERE student_id = ? AND task_id = ?",
                       (sid, task["id"])).fetchone()
    if not ok:
        due = (config.today() + timedelta(days=1)).isoformat()
        conn.execute("INSERT INTO primary_review (student_id, task_id, box, due) VALUES (?, ?, 0, ?) "
                     "ON CONFLICT(student_id, task_id) DO UPDATE SET box = 0, due = excluded.due",
                     (sid, task["id"], due))
        return "Повторим завтра."
    if row and row["due"] <= config.today().isoformat():
        box = row["box"] + 1
        if box >= len(REVIEW_INTERVALS):
            conn.execute("DELETE FROM primary_review WHERE student_id = ? AND task_id = ?", (sid, task["id"]))
            return "Выучено — больше не повторяем."
        due = (config.today() + timedelta(days=REVIEW_INTERVALS[box])).isoformat()
        conn.execute("UPDATE primary_review SET box = ?, due = ? WHERE student_id = ? AND task_id = ?",
                     (box, due, sid, task["id"]))
        return "Повторим через %d дн." % REVIEW_INTERVALS[box]
    return None


def next_open(grade, subject, current_id, solved):
    if current_id.startswith("gen-"):
        nxt = _gen_random(grade, subject, set(solved) | {current_id}, tries=6)
        if nxt:
            return nxt
        for t in tasks_for(grade, subject):
            if t["id"] not in solved:
                return t
        return None
    pool = tasks_for(grade, subject)
    ids = [t["id"] for t in pool]
    if current_id not in ids:
        return None
    rest = pool[ids.index(current_id) + 1:]
    for t in rest:
        if t["id"] not in solved:
            return t
    return rest[0] if rest else None


def counts():
    out = {}
    for t in TASKS:
        key = (t["grade"], t["subject"])
        out[key] = out.get(key, 0) + 1
    return out


def _arith(expr):
    tree = ast.parse(expr, mode="eval")
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub, ast.Mult,
               ast.FloorDiv, ast.Div, ast.USub, ast.UAdd)
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise ValueError(expr)
    return eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, {})


def _validate():
    if len(BY_ID) != len(TASKS):
        raise RuntimeError("повторяется id задания начальной школы")
    for t in TASKS:
        if t["grade"] not in (3, 4) or t["subject"] not in SUBJECT_BY_ID:
            raise RuntimeError(t["id"])
        if not t["prompt"] or not t["explain"] or not t["accept"]:
            raise RuntimeError(t["id"])
        if t["choices"] and t["accept"][0] not in t["choices"]:
            raise RuntimeError("ответ не среди кнопок: " + t["id"])
        if len({norm(c) for c in t["choices"]}) != len(t["choices"]):
            raise RuntimeError("кнопки совпадают: " + t["id"])
        if not check(t, t["accept"][0]) or check(t, "___нет___"):
            raise RuntimeError("проверка ответа сломана: " + t["id"])
        if "expr" in t and str(_arith(t["expr"])) != t["accept"][0]:
            raise RuntimeError("пример не сходится: %s (%s)" % (t["id"], t["expr"]))
    for grade in (3, 4):
        for subj in SUBJECT_BY_ID:
            n = counts()[(grade, subj)]
            if not 20 <= n <= 40:
                raise RuntimeError("число заданий %s %s: %s" % (grade, subj, n))


_validate()
