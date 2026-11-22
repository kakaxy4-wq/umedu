"""«К уроку»: экран внешнего репетитора, который занимается раз в неделю.

Сценарий: преподаватель в возрасте, ноутбук, Telegram нет, созвоны в Google Meet.
Заходит на сайт по закладке раз в неделю перед уроком:
ссылка на Meet уже сохранена, видна неделя ученика и его слабые номера,
задание можно показать крупно («доска» — для показа экрана в Meet) и
попросить повторить дома. Задание преподавателя появляется в «Сегодня»
ученика и живёт до первой верной попытки, максимум неделю.
"""
from datetime import timedelta

from . import config
from .db import connect

MEET_URL_KEY = "meet_url"
TASK_TTL_DAYS = 7


# ------------------------------------------------------------------ настройки кабинета
def pref(conn, teacher_id, key, default=""):
    row = conn.execute("SELECT value FROM teacher_pref WHERE teacher_id = ? AND key = ?", (teacher_id, key)).fetchone()
    return row["value"] if row else default


def set_pref(conn, teacher_id, key, value):
    conn.execute("INSERT INTO teacher_pref (teacher_id, key, value) VALUES (?, ?, ?) "
                 "ON CONFLICT(teacher_id, key) DO UPDATE SET value = excluded.value",
                 (teacher_id, key, value))


def valid_meet_url(url):
    u = (url or "").strip()
    return u if u.startswith("https://") and len(u) <= 300 and " " not in u else None


# ------------------------------------------------------------------ слабые номера
WEAK_P = 0.6   # ниже — номер «сыпется»: одна верная попытка даёт ~0.65, уверенное владение — выше


def weak_spots(conn, sid, exam_id, top=3):
    """Номера с попытками и низкой вероятностью успеха. Уверенные (p ≥ WEAK_P) не показываем."""
    return [dict(r) for r in conn.execute(
        "SELECT task_key, p, n FROM skill_state WHERE student_id = ? AND exam_id = ? AND n > 0 AND p < ? "
        "ORDER BY p, n DESC LIMIT ?", (sid, exam_id, WEAK_P, top))]


# ------------------------------------------------------------------ задания от преподавателя
def assign(conn, teacher_id, student_id, exam_id, task_key, note=""):
    conn.execute(
        "INSERT INTO teacher_task (teacher_id, student_id, exam_id, task_key, note, day) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (teacher_id, student_id, exam_id, int(task_key), note[:200] or "", config.today().isoformat()))


def open_for_student(conn, sid, today=None):
    """Живые задания: не решено верно со дня выдачи и выдано не позже недели назад."""
    today = today or config.today()
    rows = conn.execute(
        "SELECT t.id, t.exam_id, t.task_key, t.note, t.day FROM teacher_task t WHERE t.student_id = ? "
        "AND t.day <= ? AND t.day >= ? AND NOT EXISTS ("
        "  SELECT 1 FROM skill_attempt a WHERE a.student_id = t.student_id AND a.exam_id = t.exam_id "
        "  AND a.task_key = t.task_key AND a.day >= t.day AND a.score >= 0.5) "
        "ORDER BY t.day DESC, t.id DESC",
        (sid, today.isoformat(), (today - timedelta(days=TASK_TTL_DAYS)).isoformat())).fetchall()
    return [dict(r) for r in rows]
