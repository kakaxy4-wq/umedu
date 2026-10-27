"""Ученики: создание, доступы, архив, ссылка для родителей, рейтинг недели, «кому нужна помощь»."""
import re
import secrets
import time
from datetime import datetime, timedelta

from . import auth, config, game, russian, subjects
from .content.checks import CHECK_BY_ID
from .content.lessons import LESSON_BY_NUM
from .content.tasks import TASK_BY_ID

MAX_STUDENTS = config.MAX_STUDENTS  # задаётся экземпляром (CQ_MAX_STUDENTS)

_TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                     ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
                      "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))
# Пароль ученик должен запомнить: два знакомых слова латиницей и число — «kot-luna-27».
# Слова — простые, без букв, которые дети путают в транслите (ё, щ, ы, ь). Вариантов ~ 80 · 80 · 90 ≈ 576 000;
# от перебора защищает ограничение попыток входа (auth.MAX_FAILS за 15 минут с одного адреса).
_WORDS = (
    "kot", "pes", "lis", "volk", "mish", "zayac", "yozh", "sova", "kit", "slon", "tigr", "lev", "bober", "panda",
    "koala", "kenguru", "zhiraf", "orel", "ptica", "ryba", "akula", "delfin", "krab", "kon", "korova", "utka",
    "gus", "drakon", "robot", "raketa", "luna", "solnce", "zvezda", "kometa", "planeta", "oblako", "raduga",
    "veter", "sneg", "dozhd", "grom", "more", "reka", "gora", "les", "pole", "sad", "dom", "most", "zamok",
    "korabl", "poezd", "mashina", "samolet", "velosiped", "myach", "kubik", "piksel", "kod", "piton", "cherepaha",
    "arbuz", "banan", "limon", "yabloko", "vishnya", "pirog", "blin", "sup", "chay", "kakao", "sok", "zefir",
    "karandash", "kniga", "gitara", "baraban", "fonar", "klyuch", "kompas",
)


def generate_password():
    first, second = secrets.choice(_WORDS), secrets.choice(_WORDS)
    while second == first:
        second = secrets.choice(_WORDS)
    return "%s-%s-%d" % (first, second, secrets.randbelow(90) + 10)


def suggest_login(conn, name):
    base = "".join(_TRANSLIT.get(ch, ch) for ch in name.lower())
    base = re.sub(r"[^a-z0-9]", "", base)[:16] or "student"
    login, n = base, 2
    while conn.execute("SELECT 1 FROM users WHERE username = ?", (login,)).fetchone():
        login, n = "%s%d" % (base, n), n + 1
    return login


def valid_login(login):
    return bool(re.fullmatch(r"[a-z0-9_.-]{2,32}", login))


def create_student(conn, username, display_name, password, full_name="", grade=None):
    """Новый ученик: открыт урок 1 и входное тестирование. Вызывать внутри `with conn:`."""
    now = game.now_iso()
    sid = conn.execute(
        "INSERT INTO users (username, password_hash, role, display_name, full_name) VALUES (?, ?, 'student', ?, ?)",
        (username.lower(), auth.hash_password(password), display_name, full_name)).lastrowid
    if config.CHEM_SITE:
        grade = grade if grade in (9, 11) else 9
        conn.execute("UPDATE users SET subjects = 'chemistry', calm = 1, grade = ? WHERE id = ?", (grade, sid))
        conn.execute("INSERT OR IGNORE INTO check_state (student_id, id, opened_at) VALUES (?, ?, ?)",
                     (sid, "chem%d_entry" % grade, now))
        return sid
    conn.execute("INSERT OR IGNORE INTO lesson_state (student_id, num, opened_at) VALUES (?, 1, ?)", (sid, now))
    conn.execute("INSERT OR IGNORE INTO check_state (student_id, id, opened_at) VALUES (?, 'entry', ?)", (sid, now))
    return sid


# ------------------------------------------------------------------ открытая регистрация (CQ_SIGNUP=open)
GRADES = {7: "7 и младше", 8: "8 класс", 9: "9 класс", 10: "10 и старше"}
SIGNUPS_PER_HOUR = 5                      # с одного адреса — от ботов и «мультиаккаунтов»
_signups = {}                             # ip -> [время регистрации]


def signup_limited(ip):
    now = time.time()
    _signups[ip] = [t for t in _signups.get(ip, []) if now - t < 3600]
    return len(_signups[ip]) >= SIGNUPS_PER_HOUR


def signup(conn, name, grade, login, password, consent, ip="?"):
    """Ученик регистрируется сам: самостоятельный темп, отметка согласия. Возвращает (id, None) или (None, ошибка).
    Вызывать внутри `with conn:`."""
    from .family import CONSENT_VERSION
    name, login = name.strip()[:40], login.strip().lower()
    if not name:
        return None, "Напиши имя или ник — так к тебе будут обращаться."
    if grade not in GRADES:
        return None, "Выбери класс."
    if not valid_login(login):
        return None, "Логин — латинские буквы, цифры, точка, дефис или _, от 2 до 32 символов."
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (login,)).fetchone():
        return None, "Такой логин уже занят — придумай другой."
    if len(password) < 6:
        return None, "Пароль — хотя бы 6 символов. Можно взять предложенный: его легко запомнить."
    if not consent:
        return None, "Отметь согласие на обработку данных — без него зарегистрироваться нельзя."
    if conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student' AND active = 1").fetchone()[0] >= MAX_STUDENTS:
        return None, "Сейчас все места заняты — загляни через пару дней."
    sid = create_student(conn, login, name, password)
    chosen = [s for s in config.SUBJECTS if s in ("python", "russian")] or ["python"]
    conn.execute("UPDATE users SET grade = ?, self_paced = 1, consent = ?, subjects = ? WHERE id = ?",
                 (grade, "%s · %s" % (CONSENT_VERSION, game.now_iso()), subjects.serialize(chosen), sid))
    for cid in ["oge1"] + (["ru_entry"] if "russian" in chosen else []):
        conn.execute("INSERT OR IGNORE INTO check_state (student_id, id, opened_at) VALUES (?, ?, ?)",
                     (sid, cid, game.now_iso()))
    _signups.setdefault(ip, []).append(time.time())
    game.add_notice(conn, sid, "👋", "Привет! Начни с плана на сегодня — 10–15 минут, в конце сундук.", big=True)
    game.tell_teacher(conn, sid, "🆕 Зарегистрировался сам: %s, %s" % (name, GRADES[grade]), "/teacher/students")
    return sid, None


def get_student(conn, sid, include_archived=True):
    row = conn.execute("SELECT * FROM users WHERE id = ? AND role = 'student'", (sid,)).fetchone()
    if not row or (not include_archived and not row["active"]):
        return None
    return dict(row)


def list_students(conn, include_archived=False):
    sql = "SELECT * FROM users WHERE role = 'student'" + ("" if include_archived else " AND active = 1")
    return [dict(r) for r in conn.execute(sql + " ORDER BY active DESC, display_name COLLATE NOCASE")]


def set_password(conn, sid, password):
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (auth.hash_password(password), sid))
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (sid,))  # старые входы больше не действуют


def set_active(conn, sid, active):
    conn.execute("UPDATE users SET active = ? WHERE id = ? AND role = 'student'", (1 if active else 0, sid))
    if not active:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (sid,))
        conn.execute("UPDATE users SET parent_token = NULL WHERE id = ?", (sid,))


def new_parent_token(conn, sid):
    token = secrets.token_urlsafe(24)
    conn.execute("UPDATE users SET parent_token = ? WHERE id = ? AND role = 'student'", (token, sid))
    return token


def by_parent_token(conn, token):
    if not token or len(token) < 20:
        return None
    row = conn.execute("SELECT * FROM users WHERE parent_token = ? AND role = 'student' AND active = 1",
                       (token,)).fetchone()
    return dict(row) if row else None


def touch(conn, sid):
    """Отмечаем, когда ученик последний раз заходил (не чаще раза в 5 минут — не пишем в базу на каждый клик)."""
    now = config.now()
    row = conn.execute("SELECT last_seen_at FROM users WHERE id = ?", (sid,)).fetchone()
    if row and row[0]:
        try:
            if now - datetime.fromisoformat(row[0]) < timedelta(minutes=5):
                return
        except ValueError:
            pass
    with conn:
        conn.execute("UPDATE users SET last_seen_at = ? WHERE id = ?", (now.isoformat(timespec="seconds"), sid))


# ------------------------------------------------------------------ рейтинг недели
def week_start():
    today = config.today()
    return today - timedelta(days=today.weekday())


def leaderboard(conn):
    """Трофеи за текущую неделю (с понедельника). Неделя, а не всё время — чтобы новичок мог побороться."""
    start = week_start().isoformat()
    rows = conn.execute(
        "SELECT u.id, u.display_name, u.badge, u.title, "
        "COALESCE(SUM(CASE WHEN x.created_at >= ? THEN x.amount END), 0) AS week, "
        "COALESCE(SUM(x.amount), 0) AS total FROM users u LEFT JOIN xp_events x ON x.student_id = u.id "
        "WHERE u.role = 'student' AND u.active = 1 GROUP BY u.id ORDER BY week DESC, total DESC, u.id",
        (start,)).fetchall()
    out, place, prev = [], 0, None
    for i, r in enumerate(rows, 1):
        if r["week"] != prev:
            place, prev = i, r["week"]
        out.append({"id": r["id"], "name": r["display_name"], "badge": r["badge"], "title": r["title"],
                    "week": r["week"], "total": r["total"],
                    "level": game.level_info(r["total"]), "place": place})
    return out


def leaderboard_enabled(conn):
    from .db import get_setting
    return get_setting(conn, "leaderboard", "1") == "1"


# ------------------------------------------------------------------ сводка и «кому нужна помощь»
def _days_since(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=config.now().tzinfo)
    return (config.now() - dt).days


def overview(conn, sid):
    s = game.stats(conn, sid)
    st = get_student(conn, sid)
    week = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM xp_events WHERE student_id = ? AND created_at >= ?",
                        (sid, week_start().isoformat())).fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM submissions WHERE student_id = ? AND status = 'pending'", (sid,)).fetchone()[0]
    return {"student": st, "stats": s, "week": week, "pending": pending, "upto": game.unlocked_upto(conn, sid),
            "seen_days": _days_since(st["last_seen_at"]) if st else None}


def alerts(conn):
    """Сигналы преподавателю по всем активным ученикам — самое важное, когда учеников больше одного."""
    out = []
    for st in list_students(conn):
        sid, name = st["id"], st["display_name"]

        def add(level, emoji, text, link):
            out.append({"student_id": sid, "name": name, "level": level, "emoji": emoji, "text": text, "link": link})

        seen = _days_since(st["last_seen_at"])
        if seen is None:
            add(1, "👋", "первого входа на сайт ещё не было — проверь, что карточка доступа дошла", "/teacher/student/%d" % sid)
        elif seen >= 5:
            add(2, "💤", "%d дн. без входа на сайт" % seen, "/teacher/student/%d" % sid)
        for r in conn.execute("SELECT lesson, created_at FROM submissions WHERE student_id = ? AND status = 'pending'", (sid,)):
            d = _days_since(r["created_at"]) or 0
            if d >= 2:
                add(3, "📬", "домашка к уроку %d ждёт твоей проверки %d дн." % (r["lesson"], d), "/teacher/reviews")
        for r in conn.execute(
                "SELECT task_id, COUNT(*) AS fails, MAX(created_at) AS last FROM task_attempts WHERE student_id = ? "
                "GROUP BY task_id HAVING SUM(passed) = 0 AND COUNT(*) >= 5", (sid,)):
            if (_days_since(r["last"]) or 0) <= 7 and r["task_id"] in TASK_BY_ID:
                add(2, "🧱", "задача «%s»: %d неудачных попыток, решения пока нет" % (TASK_BY_ID[r["task_id"]]["title"], r["fails"]),
                    "/teacher/attempts/%s?student=%d" % (r["task_id"], sid))
        submitted = {r[0] for r in conn.execute("SELECT DISTINCT lesson FROM submissions WHERE student_id = ?", (sid,))}
        for r in conn.execute("SELECT num, done_at FROM lesson_state WHERE student_id = ? AND done_at IS NOT NULL", (sid,)):
            if r["num"] not in submitted and (_days_since(r["done_at"]) or 0) >= 7 and LESSON_BY_NUM.get(r["num"], {}).get("homework"):
                add(1, "📝", "домашка к уроку %d не сдана" % r["num"], "/teacher/student/%d" % sid)
        results = {r[0] for r in conn.execute("SELECT check_id FROM check_results WHERE student_id = ?", (sid,))}
        for r in conn.execute("SELECT id, opened_at FROM check_state WHERE student_id = ? AND opened_at IS NOT NULL", (sid,)):
            if r["id"] not in results and (_days_since(r["opened_at"]) or 0) >= 7 and r["id"] in CHECK_BY_ID:
                add(1, "🧭", "«%s» не пройдено — открыто %d дн. назад" % (CHECK_BY_ID[r["id"]]["title"], _days_since(r["opened_at"])),
                    "/teacher/checks?student=%d" % sid)
        for r in conn.execute("SELECT title FROM purchases WHERE student_id = ? AND status = 'requested'", (sid,)):
            add(3, "🎁", "ждёт награду «%s»" % r["title"], "/teacher/rewards")
        if "russian" in subjects.of(st):
            for rid, s in russian.rule_stats(conn, sid).items():
                if s["n"] >= 6 and s["pct"] < 60 and rid in russian.RULES:
                    add(1, "📖", "русский: «%s» — верно %d%% из %d ответов за месяц" % (russian.RULES[rid][0], s["pct"], s["n"]),
                        "/teacher/student/%d#russian" % sid)
            piled = len(russian.due_items(conn, sid))
            if piled >= 15:
                add(1, "🔁", "русский: %d ошибок ждут повторения — напомни про «Мои ошибки»" % piled,
                    "/teacher/student/%d#russian" % sid)
    return sorted(out, key=lambda a: (-a["level"], a["name"]))
