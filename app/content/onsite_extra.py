"""Задания на сайте вместо самопроверки по банку ФИПИ.

Раньше эти номера показывали текст «реши в открытом банке или в своём сборнике и отметь баллы».
Теперь условие и проверка живут здесь. Ключ номера не меняется: старые попытки в skill_attempt
остаются на том же экзамене и том же номере.
"""
import random
import re

from .extra_math import ABOUT as MATH_ABOUT
from .extra_math import MATH
from .extra_quiz import ABOUT as QUIZ_ABOUT
from .extra_quiz import QUIZ
from .extra_stem import ABOUT as STEM_ABOUT
from .extra_stem import STEM
from .extra_stem import recompute as stem_value
from .math_gen import _minus, _num, _tidy
from .solve_steps import ensure

FUNCS = {}
FUNCS.update(QUIZ)
FUNCS.update(STEM)
FUNCS.update(MATH)

ABOUT = {}
ABOUT.update(QUIZ_ABOUT)
ABOUT.update(STEM_ABOUT)
ABOUT.update(MATH_ABOUT)

OLD_TEXT = ("Реши задание из открытого банка ФИПИ или своего сборника, сверь с ответом и отметь, "
            "сколько баллов получил бы на экзамене.")


def has(exam_id, key):
    return (exam_id, key) in FUNCS


def keys_for(exam_id):
    return {key for exam, key in FUNCS if exam == exam_id}


def make(exam_id, key, seed):
    r = random.Random("%s-%s-%s" % (exam_id, key, seed))
    v = FUNCS[(exam_id, key)](r)
    v["text"] = _tidy(_minus(v["text"]))
    v["explain"] = _tidy(_minus(v.get("explain") or ""))
    if v.get("steps"):
        v["steps"] = [_tidy(_minus(s)) for s in v["steps"]]
    ensure(v)
    v.update({"num": key, "seed": seed, "source": "extra"})
    return v


def _norm(s):
    return re.sub(r"\s+", "", str(s)).lower().replace("ё", "е").replace("−", "-")


def check(v, given):
    ans, got = str(v["answer"]).strip(), str(given).strip()
    a, b = _num(ans), _num(got)
    if a is not None and b is not None:
        return a == b
    return _norm(got) == _norm(ans)


def value_of(v):
    """Число или строка, которую тест сверяет второй функцией. None — вопрос на выбор факта."""
    data = v.get("data") or {}
    kind = data.get("kind")
    if kind == "choice":
        return None
    if kind in ("digits", "fixed", "index"):
        return stem_value(data)
    try:
        from .extra_math import recompute as math_value
        return math_value(data)
    except KeyError:
        return stem_value(data)
