"""Дерево навыков (Skill Tree): единый реестр того, что ученик осваивает.

Каждый навык — атомарная единица обучения (урок Python, номер ОГЭ, правило русского,
критерий ЕГЭ). У навыка есть предмет, экзамен, ключ в БД (task_key / lesson num),
вес и список пререквизитов. Реестр — единый источник правды для «плана на сегодня»,
прогноза и дашборда: добавление новой темы = запись здесь, а не правка маршрутов.

Это основа масштабирования контента (учи.ru / LogicLike уровень): контент описывается
данными, а не кодом.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Skill:
    id: str                 # уникальный ключ, например "py:lesson:5", "oge-inf:12", "ru:odn"
    title: str
    subject: str            # python | russian | oge-inf | oge-math | ...
    exam_id: str | None     # ключ экзамена в skill_state/exam_enroll, или None для Python
    key: str                # task_key в skill_state или номер урока
    kind: str               # lesson | oge-number | ru-rule | ege-criterion
    weight: int = 1         # вклад в прогноз балла
    prereqs: tuple[str, ...] = field(default_factory=tuple)


# ---------- Python (34 урока) ----------
_PYTHON_TITLES = {
    1: "Вывод и ввод", 2: "Арифметика", 3: "Условия", 4: "Циклы", 5: "Списки",
    6: "Строки", 7: "Функции", 8: "Словари", 9: "Множества", 10: "Файлы",
}
SKILLS: dict[str, Skill] = {}
for _n in range(1, 35):
    SKILLS[f"py:lesson:{_n}"] = Skill(
        id=f"py:lesson:{_n}",
        title=_PYTHON_TITLES.get(_n, f"Урок {_n}"),
        subject="python",
        exam_id=None,
        key=str(_n),
        kind="lesson",
        weight=1,
        prereqs=(f"py:lesson:{_n-1}",) if _n > 1 else (),
    )

# ---------- ОГЭ информатика (номера) ----------
_OGE_INF_TITLES = {
    1: "Объём текста", 2: "Декодирование", 3: "Истинность высказывания",
    4: "Кратчайший путь", 5: "Исполнитель (команды)", 6: "Анализ программы",
    7: "Адрес файла", 8: "Запросы к поиску", 9: "Количество путей",
    10: "Системы счисления", 11: "Поиск в тексте", 12: "Маски файлов",
    14: "Таблицы и формулы", 15: "Исполнитель «Робот»", 16: "Программирование",
}
for _n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16):
    SKILLS[f"oge-inf:{_n}"] = Skill(
        id=f"oge-inf:{_n}",
        title=_OGE_INF_TITLES.get(_n, f"Номер {_n}"),
        subject="oge-inf",
        exam_id="oge-inf-2026",
        key=str(_n),
        kind="oge-number",
        weight=2 if _n in (15, 16) else 1,
    )

# ---------- Русский: правила ----------
_RU_RULE_TITLES = None  # заполняется лениво из content.ru


def _ru_rules():
    global _RU_RULE_TITLES
    if _RU_RULE_TITLES is not None:
        return _RU_RULE_TITLES
    try:
        from .content.ru import RULES
        _RU_RULE_TITLES = RULES
    except Exception:
        _RU_RULE_TITLES = {}
    return _RU_RULE_TITLES


for _rid in ("odn", "obr", "vvod", "prich", "deepr", "sravn", "slozh", "pril", "mezhd"):
    SKILLS[f"ru:{_rid}"] = Skill(
        id=f"ru:{_rid}", title=_rid, subject="russian", exam_id="oge-rus-2026",
        key=_rid, kind="ru-rule", weight=1)


def all_skills() -> list[Skill]:
    # гарантируем, что правила русского подгружены
    for rid, (title, _text) in _ru_rules().items():
        sid = f"ru:{rid}"
        if sid not in SKILLS:
            SKILLS[sid] = Skill(id=sid, title=title, subject="russian",
                                exam_id="oge-rus-2026", key=rid, kind="ru-rule", weight=1)
    return list(SKILLS.values())


def skills_for_subject(subject: str) -> list[Skill]:
    return [s for s in all_skills() if s.subject == subject]


def skills_for_exam(exam_id: str) -> list[Skill]:
    return [s for s in all_skills() if s.exam_id == exam_id]


def prereqs_of(skill_id: str) -> tuple[str, ...]:
    s = SKILLS.get(skill_id)
    return s.prereqs if s else ()


def progress_summary(conn, student_id: str, exam_id: str) -> dict:
    """Сводка мастерства по навыкам экзамена: {skill_id: {p, n, mastered}}."""
    rows = conn.execute(
        "SELECT task_key, p, n FROM skill_state WHERE student_id = ? AND exam_id = ?",
        (student_id, exam_id)).fetchall()
    state = {r["task_key"]: (r["p"], r["n"]) for r in rows}
    out = {}
    for sk in skills_for_exam(exam_id):
        p, n = state.get(sk.key, (0.5, 0))
        out[sk.id] = {"title": sk.title, "p": round(float(p), 3), "n": int(n),
                      "mastered": int(n) >= 5 and float(p) >= 0.75, "weight": sk.weight}
    return out


def next_skills(conn, student_id: str, exam_id: str, limit: int = 3) -> list[Skill]:
    """Навыки, которые стоит подтянуть: низкое мастерство, пререквизиты выполнены."""
    summ = progress_summary(conn, student_id, exam_id)
    done = {sid for sid, info in summ.items() if info["mastered"]}
    candidates = []
    for sk in skills_for_exam(exam_id):
        info = summ.get(sk.id, {})
        if info.get("mastered"):
            continue
        if any(pr not in done for pr in sk.prereqs):
            continue
        candidates.append((info.get("p", 0.5), sk))
    candidates.sort(key=lambda x: x[0])
    return [sk for _, sk in candidates[:limit]]
