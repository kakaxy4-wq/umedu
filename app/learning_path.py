"""Траектория обучения (Learning Path): обогащает «план на сегодня» навыками из реестра.

Цель — единая структура (учи.ru / LogicLike уровень): каждый шаг плана знает,
какой навык он развивает, и может показать прогресс по нему.
"""
from __future__ import annotations

from . import skills, today


def _skill_for_step(step: dict, conn, sid) -> str | None:
    key = step.get("key")
    if key == "oge":
        # извлекаем номер из заголовка "ОГЭ №N: ..."
        title = step.get("title", "")
        import re
        m = re.search(r"№(\d+)", title)
        if m:
            return "oge-inf:%s" % m.group(1)
    if key == "task":
        # урок берётся из href /task/... — маппинг на py:lesson делает вызывающий при необходимости
        return step.get("skill_id")
    if key == "ru":
        return None  # правило определяется на стороне /ru
    return step.get("skill_id")


def enriched_plan(conn, sid):
    p = today.plan(conn, sid)
    steps = []
    for st in p.get("steps", []):
        st = dict(st)
        st.setdefault("skill_id", _skill_for_step(st, conn, sid))
        # мастерство по навыку, если есть
        sk_id = st.get("skill_id")
        if sk_id:
            sk = skills.SKILLS.get(sk_id)
            if sk and sk.exam_id:
                summ = skills.progress_summary(conn, sid, sk.exam_id)
                info = summ.get(sk_id)
                if info:
                    st["skill_p"] = info["p"]
                    st["skill_mastered"] = info["mastered"]
        steps.append(st)
    p = dict(p)
    p["steps"] = steps
    return p
