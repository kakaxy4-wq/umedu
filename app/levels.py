"""Уровни обучения: темп и подача курса под возраст и подготовку ученика.

Уровень выбирает преподаватель в профиле ученика; сайт предлагает его по возрасту и входному тестированию
(часть «Логика и математика» — мышление, часть «Python» — что уже знает). Решение всегда за человеком:
рекомендация объясняет, почему так, и её можно не принимать.

Пока уровень влияет на подсказки преподавателю (темп, с какого урока начать) и виден в профиле и на пульте.
Отдельные курсы «Юниор» и режим «Про» — карточки бэклога; когда появятся, они будут опираться на это поле.
"""
import json

from .content.checks import CHECK_BY_ID, ENTRY_PARTS, grade

LEVELS = {
    "junior": {"emoji": "🌱", "title": "Юниор", "ages": "8–10 лет",
               "pace": "Один урок за занятие, без спешки. Больше черепашки и игр, меньше текста; домашки короткие.",
               "about": "для младших: короче объяснения, больше рисования и игры"},
    "base": {"emoji": "🚀", "title": "Стандарт", "ages": "11–13 лет",
             "pace": "Урок за занятие. Если всё решено быстро — задачи «с подвохом» и задача дня вместо новой темы.",
             "about": "основной курс: 34 урока по порядку"},
    "pro": {"emoji": "🎓", "title": "Про", "ages": "14–16 лет",
            "pace": "Можно открывать по два урока за занятие: знакомые темы — быстро, через задачи, без долгих "
                    "объяснений. Больше задач в формате ОГЭ.",
            "about": "старшим и тем, кто уже программировал: быстрее темп, больше задач ОГЭ"},
}
DEFAULT = "base"

LOGIC_TOPICS = {q["topic"] for q in ENTRY_PARTS[0]["questions"]}
LOGIC_TOTAL = len(ENTRY_PARTS[0]["questions"])
PY_TOTAL = len(ENTRY_PARTS[1]["questions"])


def of(student):
    lvl = (student or {}).get("level") or DEFAULT
    return lvl if lvl in LEVELS else DEFAULT


def entry_scores(conn, sid):
    """(логика, python | None если часть пропущена) по входному тестированию или None, если его не сдавали."""
    row = conn.execute("SELECT answers FROM check_results WHERE student_id = ? AND check_id = 'entry'", (sid,)).fetchone()
    if not row:
        return None
    rep = grade(CHECK_BY_ID["entry"], json.loads(row["answers"]))
    logic = sum(i["ok"] for i in rep["items"] if i["q"]["topic"] in LOGIC_TOPICS)
    py_items = [i for i in rep["items"] if i["q"]["topic"] not in LOGIC_TOPICS]
    py = None if all(i["skipped"] for i in py_items) else sum(i["ok"] for i in py_items)
    return logic, py


def recommend(age, scores):
    """Рекомендация: {"level", "start", "why": [...]} или None, если не на что опереться."""
    if not age and not scores:
        return None
    why = []
    level, start = DEFAULT, 1
    if age:
        level = "junior" if age <= 10 else ("pro" if age >= 14 else "base")
        why.append("возраст %d — обычно это уровень «%s»" % (age, LEVELS[level]["title"]))
    if scores:
        logic, py = scores
        why.append("логика и математика: %d из %d" % (logic, LOGIC_TOTAL))
        if logic >= 8 and level == "base" and (py or 0) >= 5:
            level = "pro"
            why.append("сильная логика и уже знает Python — можно быстрее")
        elif logic <= 4:
            if level == "pro":
                level = "base"
            why.append("логике стоит уделить время: начинать спокойно, с разминок")
        if py is None:
            why.append("часть «Python» пропущена — начинать с первого урока")
        else:
            why.append("Python: %d из %d" % (py, PY_TOTAL))
            if py >= 7:
                start = 7
                why.append("основы уже знает: уроки 1–6 пройти быстро, за 1–2 занятия, и начать с урока 7")
            elif py >= 4:
                start = 4
                why.append("переменные и вывод знакомы: уроки 1–3 можно пройти за одно занятие")
    return {"level": level, "start": start, "why": why}
