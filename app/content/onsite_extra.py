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


_UNITS = (
    "м/с²", "м/с2", "км/ч", "м/с", "дж", "ом", "кг", "см", "мм", "кдж",
    "н", "а", "в", "г", "м", "%",
)


def _strip_units(text):
    """«30 м/с» и «3)» — тот же ответ, что 30 и 3. Буквенный ответ не режем."""
    s = str(text).strip().replace("ё", "е").replace("−", "-")
    s = re.sub(r"^(\d+)\s*[).]$", r"\1", s)
    compact = re.sub(r"\s+", "", s).lower()
    for _ in range(3):
        m = re.match(r"^(-?\d+(?:[.,]\d+)?)(.*)$", compact)
        if not m or not m.group(2):
            break
        rest = m.group(2)
        if rest not in _UNITS:
            break
        compact = m.group(1)
    return compact


def _norm(s):
    return re.sub(r"\s+", "", str(s)).lower().replace("ё", "е").replace("−", "-")


def check(v, given):
    ans, got = str(v["answer"]).strip(), str(given).strip()
    a, b = _num(_strip_units(ans)), _num(_strip_units(got))
    if a is not None and b is not None:
        return a == b
    return _norm(got) == _norm(ans)


def _wanted(exam, keys):
    return {(exam, k) for k in keys}


# Развёрнутый ответ и сочинение: попытка пишется, прогноз по номеру не двигается.
_PRACTICE_WANTED = set()
_PRACTICE_WANTED |= _wanted("ege-rus-2026", [27])
_PRACTICE_WANTED |= _wanted("oge-rus-2026", [1, 13, "ГК", "ФК"])
_PRACTICE_WANTED |= _wanted("ege-eng-2026", [37, 38, "У1", "У2", "У3", "У4"])
_PRACTICE_WANTED |= _wanted("oge-eng-2026", [35, "У1", "У2", "У3"])
_PRACTICE_WANTED |= _wanted("ege-hist-2026", [17])
_PRACTICE_WANTED |= _wanted("oge-hist-2026", [18, 19, 20, 21, 22, 23, 24])
_PRACTICE_WANTED |= _wanted("ege-bio-2026", [22, 23, 25, 26, 27, 28])
_PRACTICE_WANTED |= _wanted("ege-phys-2026", [21, 22, 23, 24, 25, 26])
_PRACTICE_WANTED |= _wanted("oge-phys-2026", [17, 18, 19, 20, 21, 22])
_PRACTICE_WANTED |= _wanted("oge-math-2026", [20, 21, 23, 25])
_PRACTICE_WANTED |= _wanted("ege-math-profile-2026", [13, 14, 15, 16, 18, 19])
PRACTICE = {key for key in _PRACTICE_WANTED if key in FUNCS}


def is_practice(exam_id, key):
    return (exam_id, key) in PRACTICE


def practice_keys(exam_id):
    return {key for exam, key in PRACTICE if exam == exam_id}


def varies(exam_id, key):
    """Разные сиды дают разные условия. Иначе номер не ставим в план дважды подряд."""
    if not has(exam_id, key):
        return False
    texts = {make(exam_id, key, s)["text"] for s in range(1, 9)}
    return len(texts) > 1


def status_of(exam_id, key):
    if has(exam_id, key):
        return "тренировка" if is_practice(exam_id, key) else "соответствует"
    return "скрыт"


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
