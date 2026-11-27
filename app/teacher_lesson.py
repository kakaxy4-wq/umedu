"""«К уроку»: экран внешнего репетитора, который занимается раз в неделю.

Сценарий: преподаватель в возрасте, ноутбук, Telegram нет, созвоны в Google Meet.
Заходит на сайт по закладке раз в неделю перед уроком:
ссылка на Meet уже сохранена, видна неделя ученика и его слабые номера,
задание можно показать крупно («доска» — для показа экрана в Meet) и
попросить повторить дома. Задание преподавателя появляется в «Сегодня»
ученика и живёт до первой верной попытки, максимум неделю.
"""
from datetime import timedelta
from urllib.parse import urlsplit

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


# Сервисы видеосвязи, на которые ведёт большая кнопка «Начать урок». Только https, без логина и порта в адресе:
# кнопка открывается из кабинета в один клик, поэтому чужой сайт под видом созвона туда попасть не должен.
MEET_HOSTS = {
    "meet.google.com": "Google Meet",
    "telemost.yandex.ru": "Яндекс Телемосте", "telemost.360.yandex.ru": "Яндекс Телемосте",
    "zoom.us": "Zoom",                                  # и поддомены us02web.zoom.us и т. п.
    "teams.microsoft.com": "Microsoft Teams", "teams.live.com": "Microsoft Teams",
}


def _meet_host(host):
    host = (host or "").lower().rstrip(".")
    if host in MEET_HOSTS:
        return host
    if host.endswith(".zoom.us") and host.count(".") <= 3:
        return "zoom.us"
    return None


def valid_meet_url(url):
    """Ссылка на созвон из MEET_HOSTS или None."""
    u = (url or "").strip()
    if not u.startswith("https://") or len(u) > 300 or any(ch.isspace() for ch in u):
        return None
    try:
        parts = urlsplit(u)
        port = parts.port
    except ValueError:
        return None
    if parts.username or parts.password or port is not None or not _meet_host(parts.hostname):
        return None
    if parts.path in ("", "/"):            # голая главная страница — не ссылка на комнату
        return None
    return u


def meet_service(url):
    """Название сервиса для кнопки: «Начать урок в Zoom»."""
    if not valid_meet_url(url):
        return None
    return MEET_HOSTS[_meet_host(urlsplit(url.strip()).hostname)]


# ------------------------------------------------------------------ слабые номера
WEAK_P = 0.6   # ниже — номер «сыпется»: одна верная попытка даёт ~0.65, уверенное владение — выше


def weak_spots(conn, sid, exam_id, top=3):
    """Номера с попытками и низкой вероятностью успеха. Уверенные (p ≥ WEAK_P) не показываем."""
    return [dict(r) for r in conn.execute(
        "SELECT task_key, p, n FROM skill_state WHERE student_id = ? AND exam_id = ? AND n > 0 AND p < ? "
        "ORDER BY p, n DESC LIMIT ?", (sid, exam_id, WEAK_P, top))]


# ------------------------------------------------------------------ задания от преподавателя
def assign(conn, teacher_id, student_id, exam_id, task_key, note=""):
    """Задать номер домой. Повторное нажатие, пока прежнее задание живо (или задано сегодня), ничего не добавляет
    и возвращает False.
    Дубли отсекаем одним INSERT … WHERE NOT EXISTS (двойной клик не проскочит между проверкой и записью),
    а не UNIQUE-индексом: на проде уже могут лежать одинаковые строки, индекс на них не создастся."""
    today = config.today()
    cur = conn.execute(
        "INSERT INTO teacher_task (teacher_id, student_id, exam_id, task_key, note, day) "
        "SELECT ?, ?, ?, ?, ?, ? WHERE NOT EXISTS ("
        "  SELECT 1 FROM teacher_task t WHERE t.student_id = ? AND t.exam_id = ? AND t.task_key = ? "
        "  AND t.day <= ? AND t.day >= ? AND (t.day = ? OR NOT EXISTS ("
        "    SELECT 1 FROM skill_attempt a WHERE a.student_id = t.student_id AND a.exam_id = t.exam_id "
        "    AND a.task_key = t.task_key AND a.day >= t.day AND a.score >= 0.5)))",
        (teacher_id, student_id, exam_id, int(task_key), note[:200] or "", today.isoformat(),
         student_id, exam_id, int(task_key), today.isoformat(), (today - timedelta(days=TASK_TTL_DAYS)).isoformat(),
         today.isoformat()))
    return cur.rowcount == 1


def open_count(conn, sid, exam_id, today=None):
    """Сколько живых заданий по этому экзамену (одинаковые номера, заданные дважды до исправления, — один раз)."""
    return len({t["task_key"] for t in open_for_student(conn, sid, today) if t["exam_id"] == exam_id})


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
