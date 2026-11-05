"""Короткие шаги решения для генераторов umedu 2.0.

Если генератор уже вернул 2–4 шага, оставляем их. Иначе первый шаг — подсказка без ответа,
второй — готовый разбор из explain.
"""


def ensure(v):
    steps = [s.strip() for s in v.get("steps") or [] if str(s).strip()]
    if 2 <= len(steps) <= 4:
        v["steps"] = steps
        return v
    expl = (v.get("explain") or "").strip()
    hint = "Выпиши данные из условия и выбери, что нужно найти."
    v["steps"] = [hint, expl or "Посчитай и запиши число."]
    return v
