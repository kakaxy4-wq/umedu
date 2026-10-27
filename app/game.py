"""Игровая механика: опыт, уровни, монеты, серии, достижения, задача дня, умножайка.

Всё считается для конкретного ученика: первым аргументом после conn идёт sid — id ученика.
"""
import hashlib
import random
import re
from datetime import date, timedelta

from . import art, config, notify
from .content.lessons import LESSONS, MODULES
from .content.quizzes import QUIZZES, QUIZ_BY_ID, normalize_answer
from .content.tasks import TASKS, TASK_BY_ID
from .db import counter

# Ранги растянуты на весь курс (34 урока): 10.10.2026 первое же занятие дало 3 ранга — слишком быстро.
LEVELS = [
    (0, "Бронза I", "🥉"),
    (200, "Бронза II", "🥉"),
    (450, "Серебро", "🥈"),
    (800, "Золото", "🥇"),
    (1250, "Алмаз", "💎"),
    (1800, "Мифик", "🔮"),
    (2500, "Легенда", "👑"),
    (3300, "Мастер", "🏆"),
    (4200, "Грандмастер", "🐍"),
    (5200, "Гуру Python", "🌟"),
]

# Гемы 💎 — валюта настоящих подарков. Не трофеи: они даются только за реальную учёбу, поэтому
# «пицца» не прилетает за вечер дропов и тренажёров. Сколько гемов за одно событие каждого вида:
GEMS = {"lesson": 10, "homework": 10, "check": 10, "streak": 5}

# Коллекция бойцов Python: открываются трофеями, заработанными в Python (русский — своя коллекция ниже).
# Порог — как у рангов. (номер, эмодзи, имя, редкость, суперспособность)
BRAWLERS = [
    (1, "🐍", "Питоша", "Стартовый", "«Привет, мир!» — оглушает врагов первой программой"),
    (2, "🐢", "Тёртл", "Редкий", "Рисует щит-многоугольник вокруг команды"),
    (3, "🔁", "Цикломёт", "Редкий", "Стреляет range(100) раз подряд"),
    (4, "🎲", "Рандомщик", "Сверхредкий", "random.choice — никто не знает, куда прилетит"),
    (5, "🧙", "Функционер", "Сверхредкий", "def super(): — вызывает ульту из любой точки карты"),
    (6, "🕵️", "Шифро", "Эпический", "Шифр Цезаря: враги не понимают, что происходит"),
    (7, "🗝️", "Словарник", "Эпический", "Находит любой предмет по ключу за O(1)"),
    (8, "🎮", "Пиксель", "Мифический", "Игровой цикл 60 FPS — двигается быстрее всех"),
    (9, "🤖", "Бот-Бро", "Мифический", "Призывает Telegram-бота, который отвечает за него"),
    (10, "🐉", "Мастер Кода", "Легендарный", "Пишет код, который пишет код"),
]
HERO_NEED = [need for need, _, _ in LEVELS]          # трофеи Python для бойца №1…10

# Герои русского языка — открываются трофеями за русский. (нужно трофеев, эмодзи, имя, редкость, сила)
RU_HEROES = [
    (20, "✍️", "Запятайка", "Стартовый", "Ставит запятую быстрее, чем враг дочитает фразу"),
    (80, "📚", "Буквоед", "Редкий", "Съедает опечатки — от них не остаётся и следа"),
    (180, "🥷", "Эн-Эн", "Сверхредкий", "Удар двойной, как НН в слове «деревянный»"),
    (320, "🌱", "Корнелиус", "Эпический", "Проверяет корень и всегда знает, где А, а где О"),
    (500, "🦖", "Синтакс-Рекс", "Мифический", "Одной чертой — подлежащее, двумя — сказуемое"),
    (750, "👑", "Грамотей", "Легендарный", "Пишет диктант без единой ошибки"),
]

XP_LESSON_DONE = 20
XP_CHECK = 30  # за прохождение проверки, от баллов не зависит
XP_HOMEWORK = 10
XP_HOMEWORK_STAR = 5
XP_DAILY_FIRST = 15
XP_DAILY_SECOND = 8
XP_DAILY_TASK_BONUS = 10
XP_STREAK_WEEK = 30

TRAINER_MODES = {
    "table": "Таблица умножения",
    "big": "Умножение до 20×20",
    "squares": "Квадраты",
    "pow2": "Степени двойки",
    "divmod": "// и %",
    "bin": "Двоичная система",
    "mix": "Микс",
}


def now_iso():
    return config.now().isoformat(timespec="seconds")


def student_name(conn, sid):
    row = conn.execute("SELECT display_name FROM users WHERE id = ?", (sid,)).fetchone()
    return row[0] if row else "?"


def tell_teacher(conn, sid, text, path=""):
    """Уведомление преподавателю с именем ученика — при нескольких учениках без имени непонятно, кто это."""
    notify.teacher("%s · %s" % (student_name(conn, sid), text), path)


# ------------------------------------------------------------------ уровни
def level_info(xp):
    idx = 0
    for i, (need, _, _) in enumerate(LEVELS):
        if xp >= need:
            idx = i
    need, title, emoji = LEVELS[idx]
    nxt = LEVELS[idx + 1][0] if idx + 1 < len(LEVELS) else None
    progress = 100 if nxt is None else int(100 * (xp - need) / (nxt - need))
    return {"num": idx + 1, "title": title, "emoji": emoji, "xp": xp, "from": need, "next": nxt,
            "progress": progress, "to_next": (nxt - xp) if nxt else 0}


def total_xp(conn, sid):
    return conn.execute("SELECT COALESCE(SUM(amount), 0) FROM xp_events WHERE student_id = ?", (sid,)).fetchone()[0]


def ru_xp(conn, sid):
    return conn.execute("SELECT COALESCE(SUM(amount), 0) FROM xp_events WHERE student_id = ? AND kind = 'ru'",
                        (sid,)).fetchone()[0]


def py_xp(conn, sid):
    return total_xp(conn, sid) - ru_xp(conn, sid)


def gems_earned(conn, sid):
    rows = conn.execute("SELECT kind, COUNT(*) FROM xp_events WHERE student_id = ? AND kind IN (%s) GROUP BY kind"
                        % ",".join("?" * len(GEMS)), (sid, *GEMS)).fetchall()
    return sum(GEMS[k] * n for k, n in rows)


def coins(conn, sid):
    spent = conn.execute("SELECT COALESCE(SUM(cost), 0) FROM purchases WHERE student_id = ? AND status != 'declined'",
                         (sid,)).fetchone()[0]
    return gems_earned(conn, sid) - spent


def heroes(conn, sid):
    """Открытые бойцы Python и герои русского: номера/пороги, которых ученик достиг."""
    py, ru = py_xp(conn, sid), ru_xp(conn, sid)
    return {"py": py, "ru": ru, "py_got": sum(1 for n in HERO_NEED if py >= n),
            "ru_got": sum(1 for h in RU_HEROES if ru >= h[0])}


def add_notice(conn, sid, emoji, text, big=False):
    conn.execute("INSERT INTO notices (student_id, emoji, text, big, created_at) VALUES (?, ?, ?, ?, ?)",
                 (sid, emoji, text, 1 if big else 0, now_iso()))


def pop_notices(conn, sid):
    rows = [dict(r) for r in conn.execute(
        "SELECT id, emoji, text, big FROM notices WHERE student_id = ? AND seen = 0 ORDER BY id", (sid,))]
    if rows:
        with conn:
            conn.execute("UPDATE notices SET seen = 1 WHERE student_id = ? AND id <= ?", (sid, rows[-1]["id"]))
    return rows


def awarded(conn, sid, kind, ref):
    """Сколько опыта уже начислено за (kind, ref); ref может быть шаблоном LIKE с %."""
    return conn.execute("SELECT COALESCE(SUM(amount), 0) FROM xp_events WHERE student_id = ? AND kind = ? AND ref LIKE ?",
                        (sid, kind, ref)).fetchone()[0]


def award(conn, sid, amount, reason, kind, ref=None, quiet=False):
    """Начисляет опыт и проверяет достижения. Вызывать внутри `with conn:`."""
    before = total_xp(conn, sid)
    h_before = heroes(conn, sid) if not config.CHEM_SITE else None
    gem_before = gems_earned(conn, sid) if kind in GEMS else None
    conn.execute("INSERT INTO xp_events (student_id, amount, reason, kind, ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                 (sid, amount, reason, kind, ref, now_iso()))
    if not quiet and amount:
        if config.CHEM_SITE:
            add_notice(conn, sid, "✨", "%+d опыта — %s" % (amount, reason))
        else:
            add_notice(conn, sid, "🏆", "%+d трофеев — %s" % (amount, reason))
    sync_achievements(conn, sid)
    _check_level_up(conn, sid, before)
    if h_before:
        _check_heroes(conn, sid, h_before)
    if gem_before is not None and not config.CHEM_SITE:
        add_notice(conn, sid, "💎", "+%d 💎 — гемы для настоящих подарков" % (gems_earned(conn, sid) - gem_before))


def _brawler_for(level_num):
    for lvl, emoji, name, _rarity, _sup in BRAWLERS:
        if lvl == level_num:
            return emoji, name
    return "", ""


def _check_level_up(conn, sid, before):
    old, new = level_info(before), level_info(total_xp(conn, sid))
    if new["num"] > old["num"]:
        if config.CHEM_SITE:
            add_notice(conn, sid, "⭐", "Новый уровень: %d!" % new["num"], big=True)
            tell_teacher(conn, sid, "⭐ Новый уровень: %d" % new["num"])
            return
        add_notice(conn, sid, art.rank_img(new["num"]) or new["emoji"], "Новый ранг: «%s»!" % new["title"], big=True)
        tell_teacher(conn, sid, "🆙 Новый ранг: %s %s" % (new["emoji"], new["title"]))


def _check_heroes(conn, sid, before):
    """Новый боец — только из «своего» предмета: за русский открываются герои русского, а не Питоша."""
    calm = conn.execute("SELECT calm FROM users WHERE id = ?", (sid,)).fetchone()
    if calm and calm[0]:
        return
    after = heroes(conn, sid)
    for n in range(before["py_got"] + 1, after["py_got"] + 1):
        emoji, name = _brawler_for(n)
        add_notice(conn, sid, emoji, "Открыт боец Python: %s %s! Загляни в коллекцию" % (emoji, name), big=True)
    for n in range(before["ru_got"], after["ru_got"]):
        _need, emoji, name, _r, _s = RU_HEROES[n]
        add_notice(conn, sid, emoji, "Открыт герой русского: %s %s!" % (emoji, name), big=True)


# ------------------------------------------------------------------ статистика
def solved_task_ids(conn, sid):
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT task_id FROM task_attempts WHERE student_id = ? AND passed = 1", (sid,))}


def unlocked_upto(conn, sid):
    row = conn.execute("SELECT unlocked FROM users WHERE id = ?", (sid,)).fetchone()
    return int(row[0]) if row else 1


def done_lessons(conn, sid):
    return {r[0] for r in conn.execute(
        "SELECT num FROM lesson_state WHERE student_id = ? AND done_at IS NOT NULL", (sid,))}


def streaks(conn, sid):
    if config.CHEM_SITE:   # химия: дни, когда ученик решал задачи
        sql = "SELECT DISTINCT substr(created_at, 1, 10) FROM chem_attempts WHERE student_id = ?"
    else:
        sql = "SELECT day FROM daily WHERE student_id = ? AND finished_at IS NOT NULL"
    days = sorted(date.fromisoformat(r[0]) for r in conn.execute(sql, (sid,)))
    best = cur = 0
    prev = None
    for d in days:
        cur = cur + 1 if prev and d - prev == timedelta(days=1) else 1
        best = max(best, cur)
        prev = d
    today = config.today()
    current = cur if prev and (today - prev).days <= 1 else 0
    return current, best


def bug_fixes(conn, sid):
    """Сколько задач решено после 3+ неудачных попыток."""
    n = 0
    for tid in solved_task_ids(conn, sid):
        rows = conn.execute("SELECT passed FROM task_attempts WHERE student_id = ? AND task_id = ? ORDER BY id",
                            (sid, tid)).fetchall()
        fails = 0
        for r in rows:
            if r[0]:
                break
            fails += 1
        if fails >= 3:
            n += 1
    return n


def trainer_best(conn, sid):
    return {r[0]: r[1] for r in conn.execute(
        "SELECT mode, MAX(correct) FROM trainer_runs WHERE student_id = ? GROUP BY mode", (sid,))}


def _count(conn, sql, sid):
    return conn.execute(sql, (sid,)).fetchone()[0]


def stats(conn, sid):
    solved = solved_task_ids(conn, sid)
    cur_streak, best_streak = streaks(conn, sid)
    done = done_lessons(conn, sid)
    xp = total_xp(conn, sid)
    best = trainer_best(conn, sid)
    return {
        "xp": xp,
        "coins": coins(conn, sid),
        "heroes": heroes(conn, sid),
        "level": level_info(xp),
        "tasks_solved": len(solved),
        "tasks_total": len(TASKS),
        "turtle_solved": len([t for t in solved if TASK_BY_ID.get(t, {}).get("turtle")]),
        "bug_fixes": bug_fixes(conn, sid),
        "runs": counter(conn, sid, "runs"),
        "streak": cur_streak,
        "best_streak": best_streak,
        "daily_done": _count(conn, "SELECT COUNT(*) FROM daily WHERE student_id = ? AND finished_at IS NOT NULL", sid),
        "quiz_correct": _count(conn, "SELECT COUNT(*) FROM daily WHERE student_id = ? AND kind = 'quiz' AND solved = 1", sid),
        "hw_submitted": _count(conn, "SELECT COUNT(DISTINCT lesson) FROM submissions WHERE student_id = ?", sid),
        "hw_approved": _count(conn, "SELECT COUNT(DISTINCT lesson) FROM submissions WHERE student_id = ? "
                                    "AND status = 'approved'", sid),
        "hw_stars": _count(conn, "SELECT COUNT(*) FROM submissions WHERE student_id = ? AND status = 'approved' "
                                 "AND star = 1", sid),
        "lessons_done": len(done),
        "done": done,
        "modules_done": {m["num"] for m in MODULES if all(n in done for n in m["lessons"])},
        "projects": _count(conn, "SELECT COUNT(*) FROM projects WHERE student_id = ?", sid),
        "public_projects": _count(conn, "SELECT COUNT(*) FROM projects WHERE student_id = ? AND public = 1", sid),
        "snippets": _count(conn, "SELECT COUNT(*) FROM snippets WHERE student_id = ?", sid),
        "purchases": _count(conn, "SELECT COUNT(*) FROM purchases WHERE student_id = ? AND status = 'given'", sid),
        "trainer_runs": _count(conn, "SELECT COUNT(*) FROM trainer_runs WHERE student_id = ?", sid),
        "trainer_best": max(best.values()) if best else 0,
        "trainer_bin": best.get("bin", 0),
    }


# ------------------------------------------------------------------ достижения
# (код, эмодзи, название, описание, бонус XP, условие)
ACHIEVEMENTS = [
    ("first_run", "👋", "Привет, мир!", "Запусти свою первую программу", 5, lambda s: s["runs"] >= 1),
    ("runs_100", "⚡", "Неутомимый", "Запусти код 100 раз", 20, lambda s: s["runs"] >= 100),
    ("runs_500", "🚂", "Машина кода", "Запусти код 500 раз", 50, lambda s: s["runs"] >= 500),
    ("task_1", "🥇", "Первая победа", "Реши первую задачу", 10, lambda s: s["tasks_solved"] >= 1),
    ("task_10", "🧠", "Решатель", "Реши 10 задач", 25, lambda s: s["tasks_solved"] >= 10),
    ("task_30", "🌪️", "Мозговой штурм", "Реши 30 задач", 50, lambda s: s["tasks_solved"] >= 30),
    ("task_all", "💎", "Перфекционист", "Реши все задачи курса", 150, lambda s: s["tasks_solved"] >= s["tasks_total"]),
    ("turtle_3", "🎨", "Художник кода", "Реши 3 задачи с черепашкой", 15, lambda s: s["turtle_solved"] >= 3),
    ("bug_hunter", "🐞", "Победил баг", "Реши задачу после трёх неудачных попыток", 15, lambda s: s["bug_fixes"] >= 1),
    ("bug_master", "🦟", "Гроза багов", "Пять раз доведи упрямую задачу до победы", 30, lambda s: s["bug_fixes"] >= 5),
    ("daily_1", "☀️", "Задача дня", "Выполни первую задачу дня", 5, lambda s: s["daily_done"] >= 1),
    ("streak_3", "🔥", "Разогрев", "3 дня подряд с задачей дня", 15, lambda s: s["best_streak"] >= 3),
    ("streak_7", "🔥", "Неделя без пропусков", "7 дней подряд", 40, lambda s: s["best_streak"] >= 7),
    ("streak_30", "🌋", "Железная воля", "30 дней подряд", 150, lambda s: s["best_streak"] >= 30),
    ("quiz_10", "🔮", "Ясновидец", "10 раз правильно предскажи вывод программы", 25, lambda s: s["quiz_correct"] >= 10),
    ("hw_1", "📬", "Первая домашка", "Сдай первое домашнее задание", 10, lambda s: s["hw_submitted"] >= 1),
    ("hw_10", "📚", "Ответственный", "10 принятых домашних заданий", 40, lambda s: s["hw_approved"] >= 10),
    ("hw_star_5", "⭐", "Звёздочка", "5 принятых заданий со звёздочкой", 40, lambda s: s["hw_stars"] >= 5),
    ("lesson_10", "🎒", "Постоянный ученик", "10 проведённых занятий", 20, lambda s: s["lessons_done"] >= 10),
    ("module_1", "🐢", "Художник", "Пройди модуль «Первые шаги и черепашка»", 30, lambda s: 1 in s["modules_done"]),
    ("module_2", "📜", "Сценарист", "Пройди модуль «Логика и консольные игры»", 30, lambda s: 2 in s["modules_done"]),
    ("module_3", "🗝️", "Хранитель данных", "Пройди модуль «Строки, списки, словари, файлы»", 30, lambda s: 3 in s["modules_done"]),
    ("module_4", "🎮", "Геймдизайнер", "Пройди модуль «Игры на pygame»", 50, lambda s: 4 in s["modules_done"]),
    ("module_5", "🤖", "Ботовод", "Пройди модуль «Python в реальном мире»", 30, lambda s: 5 in s["modules_done"]),
    ("module_6", "🎓", "Выпускник", "Защити финальный проект", 100, lambda s: 6 in s["modules_done"]),
    ("project_1", "🗂️", "Портфолио открыто", "Добавь первый проект в портфолио", 10, lambda s: s["projects"] >= 1),
    ("project_public", "📣", "На публику", "Сделай проект публичным и поделись ссылкой", 10, lambda s: s["public_projects"] >= 1),
    ("project_5", "🏛️", "Коллекционер", "5 проектов в портфолио", 30, lambda s: s["projects"] >= 5),
    ("sandbox_5", "🧪", "Экспериментатор", "Сохрани 5 программ в песочнице", 10, lambda s: s["snippets"] >= 5),
    ("trainer_1", "🏀", "Первый матч", "Сыграй первый матч на Арене", 5, lambda s: s["trainer_runs"] >= 1),
    ("trainer_10", "🏃", "Спринтер", "10 матчей на Арене", 15, lambda s: s["trainer_runs"] >= 10),
    ("trainer_30", "🧮", "Калькулятор в голове", "30 верных ответов за один матч на Арене", 30, lambda s: s["trainer_best"] >= 30),
    ("trainer_bin", "0️⃣", "Двоичный мозг", "15 верных ответов в режиме «Двоичная система»", 30, lambda s: s["trainer_bin"] >= 15),
    ("shop_1", "🛍️", "Первая покупка", "Получи первую награду из магазина", 0, lambda s: s["purchases"] >= 1),
    ("level_5", "💎", "Алмазный ранг", "Достигни ранга «Алмаз»", 0, lambda s: s["level"]["num"] >= 5),
    ("level_10", "🌟", "Гуру Python", "Достигни максимального ранга", 0, lambda s: s["level"]["num"] >= 10),
]
ACH_BY_CODE = {a[0]: a for a in ACHIEVEMENTS}


def unlocked_achievements(conn, sid):
    return {r[0]: r[1] for r in conn.execute(
        "SELECT code, unlocked_at FROM achievements WHERE student_id = ?", (sid,))}


def sync_achievements(conn, sid):
    """Открывает заработанные достижения (несколько проходов: бонус может открыть следующее)."""
    for _ in range(5):
        have = unlocked_achievements(conn, sid)
        s = stats(conn, sid)
        new = [a for a in ACHIEVEMENTS if a[0] not in have and a[5](s)]
        if not new:
            return
        for code, emoji, title, desc, bonus, _cond in new:
            conn.execute("INSERT INTO achievements (student_id, code, unlocked_at) VALUES (?, ?, ?)", (sid, code, now_iso()))
            add_notice(conn, sid, emoji, "Достижение «%s»! %s" % (title, ("+%d 🏆" % bonus) if bonus else ""), big=True)
            if bonus:
                conn.execute("INSERT INTO xp_events (student_id, amount, reason, kind, ref, created_at) "
                             "VALUES (?, ?, ?, 'achievement', ?, ?)",
                             (sid, bonus, "Достижение «%s»" % title, code, now_iso()))
            tell_teacher(conn, sid, "🏅 Достижение: %s %s — %s" % (emoji, title, desc))


# ------------------------------------------------------------------ задача дня
def _seeded(day, salt=""):
    return random.Random(int(hashlib.sha256((day.isoformat() + salt).encode()).hexdigest(), 16))


def get_daily(conn, sid):
    day = config.today()
    row = conn.execute("SELECT * FROM daily WHERE student_id = ? AND day = ?", (sid, day.isoformat())).fetchone()
    if row:
        return dict(row)
    upto = unlocked_upto(conn, sid)
    used = {r[0] for r in conn.execute("SELECT ref FROM daily WHERE student_id = ? AND kind = 'quiz'", (sid,))}
    rnd = _seeded(day, str(sid))
    fresh = [q for q in QUIZZES if q["lesson"] <= upto and q["id"] not in used]
    if fresh:
        kind, ref = "quiz", rnd.choice(fresh)["id"]
    else:
        solved = solved_task_ids(conn, sid)
        open_tasks = [t for t in TASKS if t["lesson"] <= upto and t["id"] not in solved]
        if open_tasks:
            kind, ref = "task", rnd.choice(open_tasks)["id"]
        else:
            pool = [q for q in QUIZZES if q["lesson"] <= upto] or QUIZZES
            kind, ref = "quiz", rnd.choice(pool)["id"]
    with conn:
        conn.execute("INSERT OR IGNORE INTO daily (student_id, day, kind, ref) VALUES (?, ?, ?, ?)",
                     (sid, day.isoformat(), kind, ref))
    return dict(conn.execute("SELECT * FROM daily WHERE student_id = ? AND day = ?", (sid, day.isoformat())).fetchone())


def _finish_daily(conn, sid, day_row, solved, xp, reason):
    conn.execute("UPDATE daily SET finished_at = ?, solved = ? WHERE student_id = ? AND day = ?",
                 (now_iso(), 1 if solved else 0, sid, day_row["day"]))
    if xp:
        award(conn, sid, xp, reason, "daily", day_row["day"])
    cur, _ = streaks(conn, sid)
    if cur and cur % 7 == 0:
        award(conn, sid, XP_STREAK_WEEK, "%d дней подряд! 🔥" % cur, "streak", day_row["day"])
    else:
        sync_achievements(conn, sid)


def answer_daily_quiz(conn, sid, answer):
    d = get_daily(conn, sid)
    if d["kind"] != "quiz" or d["finished_at"]:
        return {"finished": True, "correct": bool(d["solved"])}
    quiz = QUIZ_BY_ID[d["ref"]]
    given = normalize_answer(answer)
    if re.fullmatch(r"-?\d+,\d+", given):  # «3,5» с экранной клавиатуры — это 3.5
        given = given.replace(",", ".")
    correct = given == normalize_answer(quiz["answer"])
    attempts = d["attempts"] + 1
    with conn:
        conn.execute("UPDATE daily SET attempts = ? WHERE student_id = ? AND day = ?", (attempts, sid, d["day"]))
        if correct:
            _finish_daily(conn, sid, d, True, XP_DAILY_FIRST if attempts == 1 else XP_DAILY_SECOND, "Задача дня")
        elif attempts >= 2:
            _finish_daily(conn, sid, d, False, 0, "")
    finished = correct or attempts >= 2
    res = {"correct": correct, "finished": finished, "attempts_left": max(0, 2 - attempts)}
    if finished:
        res.update({"answer": quiz["answer"], "why": quiz["why"]})
    return res


def daily_task_solved(conn, sid, task_id):
    """Вызывается при решении задачи: если это задача дня — засчитываем."""
    d = get_daily(conn, sid)
    if d["kind"] == "task" and d["ref"] == task_id and not d["finished_at"]:
        _finish_daily(conn, sid, d, True, XP_DAILY_TASK_BONUS, "Задача дня (бонус)")


# ------------------------------------------------------------------ умножайка
def trainer_result(conn, sid, mode, correct, wrong):
    if mode not in TRAINER_MODES:
        raise ValueError("unknown mode")
    correct = max(0, min(int(correct), 150))
    wrong = max(0, min(int(wrong), 150))
    prev_best = trainer_best(conn, sid).get(mode, 0)
    today_start = config.today().isoformat()
    earned_today = conn.execute("SELECT COALESCE(SUM(xp), 0) FROM trainer_runs WHERE student_id = ? AND created_at >= ?",
                                (sid, today_start)).fetchone()[0]
    xp = max(0, min(correct // 2, config.TRAINER_DAILY_XP_CAP - earned_today))
    with conn:
        conn.execute("INSERT INTO trainer_runs (student_id, mode, correct, wrong, xp, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (sid, mode, correct, wrong, xp, now_iso()))
        if xp:
            award(conn, sid, xp, "Арена: %s" % TRAINER_MODES[mode], "trainer", mode, quiet=True)
        else:
            sync_achievements(conn, sid)
        record = correct > prev_best and correct > 0
        if record and prev_best:
            add_notice(conn, sid, "🏁", "Новый рекорд в режиме «%s»: %d!" % (TRAINER_MODES[mode], correct), big=True)
    return {"xp": xp, "record": record, "best": max(prev_best, correct),
            "cap_reached": earned_today + xp >= config.TRAINER_DAILY_XP_CAP}


def open_lesson(conn, sid, num, notice=True):
    """Открыть урок num (и все предыдущие). Вызывать внутри `with conn:`."""
    if num > unlocked_upto(conn, sid):
        conn.execute("UPDATE users SET unlocked = ? WHERE id = ?", (num, sid))
    for n in range(1, num + 1):
        conn.execute("INSERT OR IGNORE INTO lesson_state (student_id, num, opened_at) VALUES (?, ?, ?)", (sid, n, now_iso()))
    if notice:
        lesson = next(l for l in LESSONS if l["num"] == num)
        add_notice(conn, sid, lesson["emoji"], "Открыт урок %d: «%s»!" % (num, lesson["title"]), big=True)


def mark_lesson_done(conn, sid, num, how="Занятие"):
    """Отметка «урок пройден» + XP_LESSON_DONE (один раз). Вызывать внутри `with conn:`."""
    lesson = next(l for l in LESSONS if l["num"] == num)
    conn.execute("INSERT OR IGNORE INTO lesson_state (student_id, num, opened_at) VALUES (?, ?, ?)", (sid, num, now_iso()))
    row = conn.execute("SELECT done_at FROM lesson_state WHERE student_id = ? AND num = ?", (sid, num)).fetchone()
    if row["done_at"]:
        return False
    conn.execute("UPDATE lesson_state SET done_at = ? WHERE student_id = ? AND num = ?", (now_iso(), sid, num))
    award(conn, sid, XP_LESSON_DONE, "%s %d «%s»" % (how, num, lesson["title"]), "lesson", str(num))
    return True


# Самостоятельный темп (users.self_paced): без преподавателя урок считается пройденным, когда решено SELF_PACE_SHARE
# его задач, — и сразу открывается следующий. У уроков без задач (pygame, проекты) — кнопка «Урок изучен».
SELF_PACE_SHARE = 0.6


def self_paced(conn, sid):
    row = conn.execute("SELECT self_paced FROM users WHERE id = ?", (sid,)).fetchone()
    return bool(row and row[0])


def self_pace_need(num):
    tasks = [t for t in TASKS if t["lesson"] == num]
    return max(1, int(len(tasks) * SELF_PACE_SHARE + 0.999)) if tasks else 0


def self_pace_advance(conn, sid, num, by_button=False):
    """Пройти урок num в самостоятельном темпе, если условие выполнено; открыть следующий. Внутри `with conn:`."""
    if not self_paced(conn, sid) or num != unlocked_upto(conn, sid):
        return False
    need = self_pace_need(num)
    if need:
        solved = solved_task_ids(conn, sid)
        if len([t for t in TASKS if t["lesson"] == num and t["id"] in solved]) < need:
            return False
    elif not by_button:
        return False
    mark_lesson_done(conn, sid, num, "Урок пройден сам:")
    if num < len(LESSONS):
        open_lesson(conn, sid, num + 1)
    return True


def lesson_list_with_state(conn, sid):
    upto = unlocked_upto(conn, sid)
    done = done_lessons(conn, sid)
    solved = solved_task_ids(conn, sid)
    subs = {r["lesson"]: r["status"] for r in conn.execute(
        "SELECT lesson, status FROM submissions WHERE id IN "
        "(SELECT MAX(id) FROM submissions WHERE student_id = ? GROUP BY lesson)", (sid,))}
    out = []
    for lesson in LESSONS:
        tasks = [t for t in TASKS if t["lesson"] == lesson["num"]]
        out.append({**lesson,
                    "open": lesson["num"] <= upto,
                    "done": lesson["num"] in done,
                    "current": lesson["num"] == upto,
                    "tasks_total": len(tasks),
                    "tasks_solved": len([t for t in tasks if t["id"] in solved]),
                    "hw_status": subs.get(lesson["num"])})
    return out
