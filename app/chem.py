"""Кабинет репетитора по химии: ученики сами регистрируются по коду-приглашению, преподаватель ведёт занятия,
посещаемость, оплату наличными за каждое занятие и домашние задания.

Персональных данных не храним: у ученика только имя или ник, логин, класс. Никаких фамилий, телефонов, почты.
Баланс ученика = все оплаты − цена занятий, за которые берутся деньги (проведено; пропуск — если отмечено «оплачивается»).
"""
import json
from datetime import datetime, timedelta

from . import auth, config, game, students
from .db import get_setting, set_setting

GRADES = {9: "9 класс · ОГЭ", 11: "11 класс · ЕГЭ"}
STATUSES = {
    "planned": ("🕒", "запланировано"),
    "done": ("✅", "проведено"),
    "missed": ("🚫", "пропуск"),
    "cancelled": ("↩️", "отменено"),
}
XP_HW = 10


# ------------------------------------------------------------------ регистрация по приглашению
def invite_code(conn):
    code = get_setting(conn, "invite_code")
    if not code:
        code = students.generate_password()
        with conn:
            set_setting(conn, "invite_code", code)
    return code


def new_invite_code(conn):
    """Новый код — старый перестаёт работать. Вызывать внутри `with conn:`."""
    code = students.generate_password()
    set_setting(conn, "invite_code", code)
    return code


def signup(conn, code, name, grade, login, password):
    """Регистрация ученика. Возвращает (id, None) или (None, текст ошибки). Вызывать внутри `with conn:`."""
    name, login = name.strip()[:40], login.strip().lower()
    if not code or code.strip().lower() != invite_code(conn):
        return None, "Неверный код приглашения — спроси его у преподавателя."
    if not name:
        return None, "Напиши имя или ник — так к тебе будут обращаться."
    if grade not in GRADES:
        return None, "Выбери класс."
    if not students.valid_login(login):
        return None, "Логин — латинские буквы, цифры, точка, дефис или _, от 2 до 32 символов."
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (login,)).fetchone():
        return None, "Такой логин уже занят — придумай другой."
    if len(password) < 6:
        return None, "Пароль — хотя бы 6 символов. Можно взять предложенный: его легко запомнить."
    if conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student' AND active = 1").fetchone()[0] >= students.MAX_STUDENTS:
        return None, "Сейчас мест нет — напиши преподавателю."
    sid = conn.execute(
        "INSERT INTO users (username, password_hash, role, display_name, subjects, grade, calm) "
        "VALUES (?, ?, 'student', ?, 'chemistry', ?, 1)", (login, auth.hash_password(password), name, grade)).lastrowid
    check_id = "chem%d_entry" % grade
    conn.execute("INSERT OR IGNORE INTO check_state (student_id, id, opened_at) VALUES (?, ?, ?)",
                 (sid, check_id, game.now_iso()))
    game.add_notice(conn, sid, "🧪", "Добро пожаловать! Начни с входного тестирования — оно покажет, с чего начать.", big=True)
    game.tell_teacher(conn, sid, "🆕 Новый ученик: %s, %s" % (name, GRADES[grade]), "/teacher/students")
    return sid, None


# ------------------------------------------------------------------ занятия и оплата
def _charged_sql():
    return "(status = 'done' OR (status = 'missed' AND charged = 1))"


def balance(conn, sid):
    paid = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM chem_payments WHERE student_id = ?", (sid,)).fetchone()[0]
    cost = conn.execute("SELECT COALESCE(SUM(price), 0) FROM chem_lessons WHERE student_id = ? AND " + _charged_sql(),
                        (sid,)).fetchone()[0]
    return {"paid": paid, "cost": cost, "balance": paid - cost}


def lessons(conn, sid=None, since=None, until=None, limit=200):
    sql, args = ("SELECT l.*, u.display_name AS who, u.grade, (SELECT p.plan != '' FROM chem_lesson_plans p "
                 "WHERE p.lesson_id = l.id) AS has_plan, substr(l.starts_at, 1, 10) > ? AS future "
                 "FROM chem_lessons l JOIN users u ON u.id = l.student_id WHERE 1 = 1"), [config.today().isoformat()]
    if sid:
        sql += " AND l.student_id = ?"
        args.append(sid)
    else:                                 # общее расписание — без учеников в архиве
        sql += " AND u.active = 1"
    if since:
        sql += " AND l.starts_at >= ?"
        args.append(since)
    if until:
        sql += " AND l.starts_at < ?"
        args.append(until)
    sql += " ORDER BY l.starts_at" + (" DESC" if sid and not since else "") + " LIMIT %d" % limit
    return conn.execute(sql, args).fetchall()


def add_lessons(conn, sid, starts_at, price, minutes=60, weeks=1, topic=""):
    """Занятие (или серия по неделям). Вызывать внутри `with conn:`. Возвращает число созданных."""
    from .content import chem_topics
    start = datetime.fromisoformat(starts_at)
    by_title = {t["title"]: t["id"] for t in chem_topics.TOPIC_BY_ID.values()}
    for i in range(max(1, min(weeks, 40))):
        # тема — только у первого занятия серии (дальше темы выбираются в «📝 План»)
        cur = conn.execute("INSERT INTO chem_lessons (student_id, starts_at, minutes, price, topic, created_at) "
                           "VALUES (?, ?, ?, ?, ?, ?)",
                           (sid, (start + timedelta(weeks=i)).isoformat(timespec="minutes"), minutes, price,
                            topic if i == 0 else "", game.now_iso()))
        if i == 0 and topic in by_title:
            conn.execute("INSERT INTO chem_lesson_plans (lesson_id, topic_ids, plan, updated_at) VALUES (?, ?, '', ?)",
                         (cur.lastrowid, json.dumps([by_title[topic]]), game.now_iso()))
    return max(1, min(weeks, 40))


def set_lesson(conn, lesson_id, status, charged=None, topic=None, note=None):
    if status not in STATUSES:
        return False
    row = conn.execute("SELECT * FROM chem_lessons WHERE id = ?", (lesson_id,)).fetchone()
    if not row:
        return False
    if status in ("done", "missed") and row["starts_at"][:10] > config.today().isoformat():
        return False                      # будущее занятие нельзя отметить проведённым или пропущенным
    charged = (1 if status == "done" else 0) if charged is None else int(bool(charged))
    conn.execute("UPDATE chem_lessons SET status = ?, charged = ?, topic = COALESCE(?, topic), note = COALESCE(?, note) "
                 "WHERE id = ?", (status, charged, topic, note, lesson_id))
    if status == "done" and row["status"] != "done" and not game.awarded(conn, row["student_id"], "lesson", str(lesson_id)):
        game.award(conn, row["student_id"], 15, "занятие %s.%s" % (row["starts_at"][8:10], row["starts_at"][5:7]),
                   "lesson", str(lesson_id))
    return True


def delete_series(conn, lesson_id):
    """Удалить запланированное занятие и все следующие запланированные этого ученика в тот же день недели и час."""
    row = conn.execute("SELECT * FROM chem_lessons WHERE id = ?", (lesson_id,)).fetchone()
    if not row:
        return 0
    wd = datetime.fromisoformat(row["starts_at"]).weekday()
    ids = [r["id"] for r in conn.execute(
        "SELECT id, starts_at FROM chem_lessons WHERE student_id = ? AND status = 'planned' AND starts_at >= ? "
        "AND substr(starts_at, 12, 5) = ?", (row["student_id"], row["starts_at"], row["starts_at"][11:16]))
        if datetime.fromisoformat(r["starts_at"]).weekday() == wd]
    conn.executemany("DELETE FROM chem_lessons WHERE id = ?", [(i,) for i in ids])
    return len(ids)


def add_payment(conn, sid, amount, paid_at=None, note=""):
    conn.execute("INSERT INTO chem_payments (student_id, amount, paid_at, note, created_at) VALUES (?, ?, ?, ?, ?)",
                 (sid, amount, paid_at or config.today().isoformat(), note[:200], game.now_iso()))


def payments(conn, sid, limit=100):
    return conn.execute("SELECT * FROM chem_payments WHERE student_id = ? ORDER BY paid_at DESC, id DESC LIMIT ?",
                        (sid, limit)).fetchall()


def debtors(conn):
    out = []
    for st in students.list_students(conn, include_archived=True):   # долг не пропадает и после архива
        b = balance(conn, st["id"])
        if b["balance"] < 0:
            out.append({"student": st, **b})
    return out


# ------------------------------------------------------------------ домашние задания
def hw_list(conn, sid=None, status=None):
    sql, args = "SELECT h.*, u.display_name AS who FROM chem_hw h JOIN users u ON u.id = h.student_id WHERE 1 = 1", []
    if sid:
        sql += " AND h.student_id = ?"
        args.append(sid)
    if status:
        sql += " AND h.status = ?"
        args.append(status)
    return conn.execute(sql + " ORDER BY h.id DESC", args).fetchall()


def hw_get(conn, hw_id):
    return conn.execute("SELECT * FROM chem_hw WHERE id = ?", (hw_id,)).fetchone()


def hw_give(conn, sid, title, text="", due_at=None, task_ids=(), max_score=None):
    hw_id = conn.execute("INSERT INTO chem_hw (student_id, title, text, task_ids, due_at, max_score, created_at) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (sid, title[:120], text[:4000], json.dumps(list(task_ids)), due_at or None, max_score,
                          game.now_iso())).lastrowid
    game.add_notice(conn, sid, "📚", "Новое домашнее задание: «%s»" % title[:80], big=True)
    return hw_id


def hw_submit(conn, hw_id, answer, file_name=None, file_path=None):
    conn.execute("UPDATE chem_hw SET status = 'submitted', answer = ?, file_name = COALESCE(?, file_name), "
                 "file_path = COALESCE(?, file_path), submitted_at = ? WHERE id = ?",
                 (answer[:8000], file_name, file_path, game.now_iso(), hw_id))
    hw = hw_get(conn, hw_id)
    game.tell_teacher(conn, hw["student_id"], "📬 Сдано ДЗ «%s»" % hw["title"], "/chem/teacher/hw")


def hw_check(conn, hw_id, score, max_score, comment, returned=False):
    hw = hw_get(conn, hw_id)
    status = "given" if returned else "checked"
    conn.execute("UPDATE chem_hw SET status = ?, score = ?, max_score = ?, comment = ?, checked_at = ? WHERE id = ?",
                 (status, score, max_score, comment[:2000], game.now_iso(), hw_id))
    if returned:
        game.add_notice(conn, hw["student_id"], "🔧", "ДЗ «%s» вернули на доработку" % hw["title"], big=True)
    elif hw["status"] != "checked" and not game.awarded(conn, hw["student_id"], "homework", str(hw_id)):
        game.award(conn, hw["student_id"], XP_HW, "ДЗ «%s»" % hw["title"], "homework", str(hw_id))


# ------------------------------------------------------------------ сводки
def student_card(conn, sid):
    st = students.get_student(conn, sid)
    now = config.now().isoformat(timespec="minutes")[:16]
    nxt = conn.execute("SELECT * FROM chem_lessons WHERE student_id = ? AND status = 'planned' AND starts_at >= ? "
                       "ORDER BY starts_at LIMIT 1", (sid, now)).fetchone()
    return {"student": st, "balance": balance(conn, sid), "next": nxt,
            "hw_open": conn.execute("SELECT COUNT(*) FROM chem_hw WHERE student_id = ? AND status = 'given'",
                                    (sid,)).fetchone()[0],
            "hw_wait": conn.execute("SELECT COUNT(*) FROM chem_hw WHERE student_id = ? AND status = 'submitted'",
                                    (sid,)).fetchone()[0],
            "visits": conn.execute("SELECT COUNT(*) FROM chem_lessons WHERE student_id = ? AND status = 'done'",
                                   (sid,)).fetchone()[0],
            "missed": conn.execute("SELECT COUNT(*) FROM chem_lessons WHERE student_id = ? AND status = 'missed'",
                                   (sid,)).fetchone()[0]}


def day_bounds(day):
    return day.isoformat(), (day + timedelta(days=1)).isoformat()


# ------------------------------------------------------------------ тестовый ученик для преподавателя
DEMO_LOGIN = "тест"
DEMO_PASSWORD = "тест"


def demo_student(conn, grade):
    """Тестовый ученик «тест / тест» — посмотреть сайт глазами ученика. Повторный вызов меняет класс и пароль
    обратно на «тест». Вызывать внутри `with conn:`. Возвращает id."""
    grade = grade if grade in GRADES else 9
    row = conn.execute("SELECT id FROM users WHERE username = ?", (DEMO_LOGIN,)).fetchone()
    if row:
        sid = row["id"]
        conn.execute("UPDATE users SET password_hash = ?, grade = ?, active = 1, role = 'student' WHERE id = ?",
                     (auth.hash_password(DEMO_PASSWORD), grade, sid))
    else:
        sid = conn.execute(
            "INSERT INTO users (username, password_hash, role, display_name, subjects, grade, calm, notes) "
            "VALUES (?, ?, 'student', 'Тестовый ученик', 'chemistry', ?, 1, 'Тестовый — для просмотра сайта глазами ученика')",
            (DEMO_LOGIN, auth.hash_password(DEMO_PASSWORD), grade)).lastrowid
    conn.execute("INSERT OR IGNORE INTO check_state (student_id, id, opened_at) VALUES (?, ?, ?)",
                 (sid, "chem%d_entry" % grade, game.now_iso()))
    return sid


# ------------------------------------------------------------------ темы, ДЗ по теме, листочки с занятий
def _plan_topics(conn, sid, status, exclude=0):
    """{название темы: дата} по планам занятий ученика с данным статусом (самое раннее занятие)."""
    from .content import chem_topics
    out = {}
    for r in conn.execute("SELECT l.starts_at, p.topic_ids FROM chem_lesson_plans p JOIN chem_lessons l ON l.id = p.lesson_id "
                          "WHERE l.student_id = ? AND l.status = ? AND l.id != ? ORDER BY l.starts_at", (sid, status, exclude)):
        for tid in json.loads(r["topic_ids"] or "[]"):
            t = chem_topics.TOPIC_BY_ID.get(tid)
            if t:
                out.setdefault(t["title"], r["starts_at"][:10])
    return out


def covered_topics(conn, sid, exclude=0):
    """Пройденные темы {название: дата первого проведённого занятия}: темы из планов занятий, отмеченных «Был»,
    и (по-старому) тема занятия, если она совпадает с названием темы программы."""
    from .content import chem_topics
    titles = {t["title"] for t in chem_topics.TOPIC_BY_ID.values()}
    out = _plan_topics(conn, sid, "done", exclude)
    for r in conn.execute("SELECT topic, MIN(starts_at) FROM chem_lessons WHERE student_id = ? AND status = 'done' "
                          "AND topic != '' AND id != ? GROUP BY topic", (sid, exclude)):
        if r[0] in titles and (r[0] not in out or r[1][:10] < out[r[0]]):
            out[r[0]] = r[1][:10]
    return out


def lesson_plan(conn, lesson_id):
    row = conn.execute("SELECT * FROM chem_lesson_plans WHERE lesson_id = ?", (lesson_id,)).fetchone()
    return {"topic_ids": json.loads(row["topic_ids"]), "plan": row["plan"], "updated_at": row["updated_at"]} if row \
        else {"topic_ids": [], "plan": "", "updated_at": ""}


def other_plans(conn, sid, lesson_id):
    """{id темы: дата} — темы, уже запланированные на другие предстоящие занятия ученика."""
    out = {}
    for r in conn.execute("SELECT l.starts_at, p.topic_ids FROM chem_lesson_plans p JOIN chem_lessons l ON l.id = p.lesson_id "
                          "WHERE l.student_id = ? AND l.status = 'planned' AND l.id != ? ORDER BY l.starts_at",
                          (sid, lesson_id)):
        for tid in json.loads(r["topic_ids"] or "[]"):
            out.setdefault(tid, r["starts_at"][:10])
    return out


def save_lesson_plan(conn, lesson_id, topic_ids, plan):
    """Темы и план занятия; тема занятия (видна в расписании) — названия выбранных тем. Вызывать внутри `with conn:`."""
    from .content import chem_topics
    grade = conn.execute("SELECT u.grade FROM chem_lessons l JOIN users u ON u.id = l.student_id WHERE l.id = ?",
                         (lesson_id,)).fetchone()[0]
    own = {t["id"] for t in chem_topics.for_grade(grade)}
    topic_ids = [t for t in dict.fromkeys(topic_ids) if t in own]
    had = lesson_plan(conn, lesson_id)["topic_ids"]
    conn.execute("INSERT INTO chem_lesson_plans (lesson_id, topic_ids, plan, updated_at) VALUES (?, ?, ?, ?) "
                 "ON CONFLICT(lesson_id) DO UPDATE SET topic_ids = excluded.topic_ids, plan = excluded.plan, "
                 "updated_at = excluded.updated_at", (lesson_id, json.dumps(topic_ids), plan, game.now_iso()))
    if topic_ids:
        title = "; ".join(chem_topics.TOPIC_BY_ID[t]["title"] for t in topic_ids)
        conn.execute("UPDATE chem_lessons SET topic = ? WHERE id = ?", (title[:200], lesson_id))
    elif had:                             # темы из плана сняты — снимаем и тему занятия
        conn.execute("UPDATE chem_lessons SET topic = '' WHERE id = ?", (lesson_id,))


def plan_tasks(conn, sid, topic_ids, per_topic=2):
    """Задачи для разбора на занятии: по теме — задача банка или вариант генератора по её номерам."""
    from .chem_review import generator_on, hidden, visible_bank
    from .content import chem_exam, chem_gen, chem_topics
    st = students.get_student(conn, sid)
    exam = chem_exam.exam_for_grade(st["grade"])
    hb, hg = hidden(conn)
    out = {}
    for tid in topic_ids:
        picked = []
        for num in chem_topics.TOPIC_BY_ID[tid]["nums"]:
            if num in chem_exam.EXAMS[exam]["long"]:
                picked.append({"num": num, "id": None, "long": True})
                continue
            bank = visible_bank(conn, exam, num, hb)
            if bank:
                picked.append({"num": num, "id": bank[0]["id"], "long": False})
            elif generator_on(conn, exam, num, hg):
                picked.append({"num": num, "id": chem_gen.new_id(exam, num), "long": False})
        out[tid] = picked[:per_topic]
    return out


def draft_plan(conn, sid, topic_ids, minutes=60):
    """Черновик плана занятия по выбранным темам с разбивкой по минутам."""
    from .content import chem_exam, chem_topics
    st = students.get_student(conn, sid)
    exam = chem_exam.EXAMS[chem_exam.exam_for_grade(st["grade"])]["title"]
    topics = [chem_topics.TOPIC_BY_ID[t] for t in topic_ids if t in chem_topics.TOPIC_BY_ID]
    minutes = max(30, minutes or 60)
    warm, final = (5, 5) if minutes < 50 else (10, 10)
    body = minutes - warm - final
    lines = ["%d мин — разминка: проверка ДЗ, вопросы с прошлого занятия" % warm]
    if not topics:
        lines.append("%d мин — новая тема / разбор ошибок" % body)
    tasks = plan_tasks(conn, sid, [t["id"] for t in topics]) if topics else {}
    for i, t in enumerate(topics):
        share = body // len(topics) + (body % len(topics) if i == 0 else 0)
        lines.append("")
        lines.append("%d мин — %s" % (share, t["title"]))
        lines += ["  • %s" % p for p in chem_topics.POINTS.get(t["id"], [])]
        nums = [x["num"] for x in tasks.get(t["id"], [])]
        if nums:
            lines.append("  • Разобрать: %s %s" % (", ".join("№%d" % n for n in nums), exam))
    lines += ["", "%d мин — итог: что запомнили, ДЗ по темам занятия" % final]
    return "\n".join(lines)


def hw_from_topic(conn, sid, topic, due_at=None):
    """ДЗ по теме: задачи банка по её номерам + по два варианта генератора; письменные номера — в тексте.
    Вызывать внутри `with conn:`. Возвращает id ДЗ или None, если для темы нет задач."""
    from .chem_review import generator_on, hidden, visible_bank
    from .content import chem_exam, chem_gen
    st = students.get_student(conn, sid)
    hb, hg = hidden(conn)
    exam = chem_exam.exam_for_grade(st["grade"])
    ids, written = [], []
    for num in topic["nums"]:
        if num in chem_exam.EXAMS[exam]["long"]:
            written.append(num)
            continue
        ids += [x["id"] for x in visible_bank(conn, exam, num, hb)]
        if generator_on(conn, exam, num, hg):
            ids += [chem_gen.new_id(exam, num) for _ in range(2)]
    ids = ids[:10]
    if not ids and not written:
        return None
    parts = []
    if ids:
        parts.append("Реши задачи ниже — ответ проверяется сразу. Когда закончишь, нажми «Отправить преподавателю».")
    for num in written:
        bank = visible_bank(conn, exam, num, hb)
        if bank:   # условие письменной задачи — прямо в тексте ДЗ
            parts.append("Письменно, №%d %s (реши в тетради и приложи фото):\n%s"
                         % (num, chem_exam.EXAMS[exam]["title"], bank[(sid + len(parts)) % len(bank)]["text"]))
        else:
            parts.append("Письменно: задание №%d %s — реши в тетради и приложи фото." % (num, chem_exam.EXAMS[exam]["title"]))
    return hw_give(conn, sid, topic["title"], "\n\n".join(parts), due_at, task_ids=ids)


def hw_tasks(conn, hw):
    """Задачи ДЗ с лучшим результатом ученика."""
    from .content import chem_exam, chem_gen
    from .content.chem_tasks import TASK_BY_ID
    from .chem_review import hidden
    hb, hg = hidden(conn)
    ids = json.loads(hw["task_ids"] or "[]")
    best = {r[0]: r[1] for r in conn.execute(
        "SELECT task_id, MAX(points) FROM chem_attempts WHERE student_id = ? GROUP BY task_id", (hw["student_id"],))}
    out = []
    for tid in ids:
        t = TASK_BY_ID.get(tid) or chem_gen.task(tid)
        if not t or tid in hb or (t.get("generated") and (t["exam"], t["num"]) in hg):
            continue                      # нет такой задачи или преподаватель отметил в ней ошибку
        pts = chem_exam.points(t["exam"], t["num"])
        out.append({"id": tid, "exam": t["exam"], "num": t["num"], "points": pts, "best": best.get(tid),
                    "generated": bool(t.get("generated")), "title": chem_exam.EXAMS[t["exam"]]["numbers"][t["num"]][0]})
    return out


def lesson_files(conn, sid=None, lesson_ids=None):
    sql, args = "SELECT * FROM chem_lesson_files WHERE 1 = 1", []
    if sid:
        sql += " AND student_id = ?"
        args.append(sid)
    rows = conn.execute(sql + " ORDER BY id", args).fetchall()
    by_lesson = {}
    for r in rows:
        if lesson_ids is None or r["lesson_id"] in lesson_ids:
            by_lesson.setdefault(r["lesson_id"], []).append(r)
    return by_lesson



# ------------------------------------------------------------------ ДЗ: учебник и файлы (фото, рисунки от руки)
TEXTBOOKS = [
    "Габриелян О. С. и др. Химия. 8 класс", "Габриелян О. С. и др. Химия. 9 класс",
    "Рудзитис Г. Е., Фельдман Ф. Г. Химия. 8 класс", "Рудзитис Г. Е., Фельдман Ф. Г. Химия. 9 класс",
    "Еремин В. В., Кузьменко Н. Е. и др. Химия. 9 класс",
    "Габриелян О. С. и др. Химия. 10 класс", "Габриелян О. С. и др. Химия. 11 класс",
    "Рудзитис Г. Е., Фельдман Ф. Г. Химия. 10 класс", "Рудзитис Г. Е., Фельдман Ф. Г. Химия. 11 класс",
    "Еремин В. В. и др. Химия. 10 класс (углублённый)", "Еремин В. В. и др. Химия. 11 класс (углублённый)",
]


def book_text(book, paragraph, pages, exercises, extra=""):
    """Текст ДЗ по учебнику из отдельных полей формы."""
    lines = []
    if book:
        lines.append("📖 Учебник: " + book)
    if paragraph:
        lines.append("Параграф: " + paragraph)
    if pages:
        lines.append("Страницы: " + pages)
    if exercises:
        lines.append("Задания после параграфа: " + exercises)
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def hw_add_file(conn, hw_id, author, file_name, file_path):
    conn.execute("INSERT INTO chem_hw_files (hw_id, author, file_name, file_path, created_at) VALUES (?, ?, ?, ?, ?)",
                 (hw_id, author, file_name, file_path, game.now_iso()))


def hw_files(conn, hw_id):
    rows = conn.execute("SELECT * FROM chem_hw_files WHERE hw_id = ? ORDER BY id", (hw_id,)).fetchall()
    return {"teacher": [r for r in rows if r["author"] == "teacher"], "student": [r for r in rows if r["author"] == "student"]}
