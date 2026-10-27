"""Пробный вариант ОГЭ/ЕГЭ: по одному заданию на каждый номер, таймер как на экзамене.

Часть с кратким ответом проверяется сразу (правила ФИПИ — chem_tasks.grade_answer), развёрнутую часть ученик решает на
бумаге и прикладывает фото, баллы ставит преподаватель. Ответы сохраняются на сервере по ходу работы.
"""
import json
import random
from datetime import datetime, timedelta

from . import chem_review, config
from .content import chem_exam, chem_gen
from .content.chem_tasks import TASK_BY_ID, grade_answer

GRACE_SECONDS = 120          # запас на сеть после окончания времени
XP_PER_POINT = 5


def _now():
    return config.now()


def get_task(task_id):
    return TASK_BY_ID.get(task_id) or chem_gen.task(task_id)


def build_tasks(conn, exam, rng=random):
    """Номер → id задания: свежий вариант генератора, если генератор не скрыт, иначе задача банка."""
    hb, hg = chem_review.hidden(conn)
    tasks = []
    for num in chem_exam.EXAMS[exam]["numbers"]:
        if chem_review.generator_on(conn, exam, num, hg):
            tid = chem_gen.new_id(exam, num, rng)
        else:
            bank = chem_review.visible_bank(conn, exam, num, hb)
            if not bank:
                continue
            tid = rng.choice(bank)["id"]
        tasks.append({"num": num, "id": tid})
    return tasks


def create(conn, sid, exam, created_by="student", due_at=None):
    return conn.execute("INSERT INTO chem_mocks (student_id, exam, tasks, created_by, due_at, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (sid, exam, json.dumps(build_tasks(conn, exam)), created_by, due_at,
                         _now().isoformat(timespec="seconds"))).lastrowid


def get(conn, mock_id):
    row = conn.execute("SELECT * FROM chem_mocks WHERE id = ?", (mock_id,)).fetchone()
    if not row:
        return None
    m = dict(row)
    for k in ("tasks", "answers", "points", "long_points"):
        m[k] = json.loads(m[k] or ("[]" if k == "tasks" else "{}"))
    m["ex"] = chem_exam.EXAMS[m["exam"]]
    return m


def list_for(conn, sid):
    return [get(conn, r[0]) for r in conn.execute(
        "SELECT id FROM chem_mocks WHERE student_id = ? ORDER BY id DESC", (sid,))]


def start(conn, m):
    if m["status"] != "given":
        return
    now = _now()
    conn.execute("UPDATE chem_mocks SET status = 'running', started_at = ?, deadline_at = ? WHERE id = ?",
                 (now.isoformat(timespec="seconds"),
                  (now + timedelta(minutes=m["ex"]["minutes"])).isoformat(timespec="seconds"), m["id"]))


def time_left(m):
    if not m.get("deadline_at"):
        return None
    return (datetime.fromisoformat(m["deadline_at"]) - _now()).total_seconds()


def expired(m):
    left = time_left(m)
    return left is not None and left < -GRACE_SECONDS


def save_answers(conn, m, answers):
    """Сохраняет ответы части 1 (только номера этого варианта, только пока идёт время). Возвращает False после срока."""
    if m["status"] != "running" or expired(m):
        return False
    short = {str(t["num"]) for t in m["tasks"] if t["num"] not in m["ex"]["long"]}
    clean = {k: str(v)[:40] for k, v in (answers or {}).items() if str(k) in short}
    m["answers"].update(clean)
    conn.execute("UPDATE chem_mocks SET answers = ? WHERE id = ?", (json.dumps(m["answers"], ensure_ascii=False), m["id"]))
    return True


def short_max(m):
    return sum(chem_exam.points(m["exam"], t["num"]) for t in m["tasks"] if t["num"] not in m["ex"]["long"])


def long_max(m):
    return sum(chem_exam.points(m["exam"], t["num"]) for t in m["tasks"] if t["num"] in m["ex"]["long"])


def finish(conn, m):
    """Проверяет часть 1, записывает попытки (идут в прогноз на карте) и возвращает баллы части 1."""
    if m["status"] != "running":
        return None
    points = {}
    now = _now().isoformat(timespec="seconds")
    for t in m["tasks"]:
        if t["num"] in m["ex"]["long"]:
            continue
        task = get_task(t["id"])
        given = m["answers"].get(str(t["num"]), "")
        got = grade_answer(task, given) if task else 0
        points[str(t["num"])] = got
        if given.strip():
            conn.execute("INSERT INTO chem_attempts (student_id, task_id, answer, points, max_points, created_at) "
                         "VALUES (?, ?, ?, ?, ?, ?)",
                         (m["student_id"], t["id"], given, got, chem_exam.points(m["exam"], t["num"]), now))
    score = sum(points.values())
    status = "finished" if long_max(m) else "checked"
    conn.execute("UPDATE chem_mocks SET status = ?, points = ?, score = ?, finished_at = ? WHERE id = ?",
                 (status, json.dumps(points), score, now, m["id"]))
    return score


def grade_long(conn, m, long_points, comment):
    """Преподаватель ставит баллы за развёрнутые номера (не больше максимума номера)."""
    clean = {}
    for t in m["tasks"]:
        if t["num"] in m["ex"]["long"]:
            mx = chem_exam.points(m["exam"], t["num"])
            try:
                v = int(long_points.get(str(t["num"]), 0))
            except (TypeError, ValueError):
                v = 0
            clean[str(t["num"])] = max(0, min(mx, v))
    score = sum(m["points"].values()) + sum(clean.values())
    conn.execute("UPDATE chem_mocks SET long_points = ?, score = ?, comment = ?, status = 'checked', checked_at = ? "
                 "WHERE id = ?", (json.dumps(clean), score, comment[:3000], _now().isoformat(timespec="seconds"), m["id"]))
    return score


def rows(m, reveal):
    """Строки результата: номер, задание, ответ, верный ответ (если reveal), баллы."""
    out = []
    for t in m["tasks"]:
        task = get_task(t["id"])
        num = t["num"]
        long = num in m["ex"]["long"]
        out.append({"num": num, "id": t["id"], "task": task, "long": long, "max": chem_exam.points(m["exam"], num),
                    "title": m["ex"]["numbers"][num][0],
                    "given": m["answers"].get(str(num), ""),
                    "got": (m["long_points"] if long else m["points"]).get(str(num)),
                    "right": task["answer"] if (task and reveal and not long) else None,
                    "why": task["why"] if (task and reveal) else None})
    return out
