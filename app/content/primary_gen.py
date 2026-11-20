"""Генераторы заданий по математике для 3–4 классов.

Вариант кодируется в id: gen-<вид>-<параметры>. Один и тот же id всегда даёт
одно и то же задание — попытка в primary_attempt пишется по этому же id, поэтому
схема базы не меняется. Обучение: у каждого задания короткая подсказка `hint`
(до решения) и полный разбор `explain` (после ответа).
"""

TOPICS = {
    "mul": "Таблица умножения",
    "div": "Деление",
    "ord": "Порядок действий",
    "add4": "Многозначные числа",
    "sub4": "Многозначные числа",
    "mul2": "Умножение и деление",
    "rem": "Умножение и деление",
}

KINDS_BY_GRADE = {
    3: ("mul", "div", "ord"),
    4: ("add4", "sub4", "mul2", "rem"),
}


def _int(s):
    if not s.isdigit():
        raise ValueError(s)
    return int(s)


def _row(kind, grade, prompt, accept, hint, explain):
    return {"id": None, "grade": grade, "subject": "math", "topic": TOPICS[kind],
            "prompt": prompt, "accept": [str(accept)], "choices": [],
            "explain": explain, "hint": hint}


def _mul(*parts):
    if len(parts) != 2:
        return None
    a, b = _int(parts[0]), _int(parts[1])
    if not (2 <= a <= 9 and 2 <= b <= 9):
        return None
    t = _row("mul", 3, "Сколько будет %d × %d? Напиши число." % (a, b), a * b,
             "Умножение — это несколько раз по столько: %d × %d — по %d взять %d раз. Числа можно менять местами: %d × %d = %d × %d." % (a, b, b, a, a, b, b, a),
             "%d × %d = %d." % (a, b, a * b))
    t["id"] = "gen-mul-%d-%d" % (a, b)
    return t


def _div(*parts):
    if len(parts) != 2:
        return None
    a, b = _int(parts[0]), _int(parts[1])
    if b < 2 or a < b * 2 or a % b != 0 or a // b > 9:
        return None
    q = a // b
    t = _row("div", 3, "Сколько будет %d ÷ %d? Напиши число." % (a, b),
             q,
             "Деление обратно умножению: подбери число, которое при умножении на делитель даст делимое.",
             "%d ÷ %d = %d, потому что %d × %d = %d." % (a, b, q, b, q, a))
    t["id"] = "gen-div-%d-%d" % (a, b)
    return t


def _ord(*parts):
    if len(parts) != 3:
        return None
    a, b, c = _int(parts[0]), _int(parts[1]), _int(parts[2])
    if not (2 <= b <= 9 and 2 <= c <= 9):
        return None
    d = a - b * c
    if not (1 <= d <= 30):
        return None
    t = _row("ord", 3, "Сколько будет %d − %d × %d? Напиши число." % (a, b, c), d,
             "Порядок действий: сначала умножение и деление, потом сложение и вычитание.",
             "Сначала умножение: %d × %d = %d. Потом вычитание: %d − %d = %d." % (b, c, b * c, a, b * c, d))
    t["id"] = "gen-ord-%d-%d-%d" % (a, b, c)
    return t


def _add4(*parts):
    if len(parts) != 2:
        return None
    a, b = _int(parts[0]), _int(parts[1])
    if not (1000 <= a <= 9999 and 1000 <= b <= 9999) or a + b > 9999:
        return None
    t = _row("add4", 4, "Сколько будет %d + %d? Напиши число." % (a, b), a + b,
             "Складывай по разрядам: единицы к единицам, десятки к десяткам. Не забудь перенос через десяток.",
             "%d + %d = %d. Проверка: %d − %d = %d — сходится." % (a, b, a + b, a + b, b, a))
    t["id"] = "gen-add4-%d-%d" % (a, b)
    return t


def _sub4(*parts):
    if len(parts) != 2:
        return None
    a, b = _int(parts[0]), _int(parts[1])
    if not (2000 <= a <= 9999 and 1000 <= b < a):
        return None
    t = _row("sub4", 4, "Сколько будет %d − %d? Напиши число." % (a, b), a - b,
             "Вычитай по разрядам. Если в разряде не хватает — занимай десяток у старшего.",
             "%d − %d = %d. Проверка: %d + %d = %d — сходится." % (a, b, a - b, a - b, b, a))
    t["id"] = "gen-sub4-%d-%d" % (a, b)
    return t


def _mul2(*parts):
    if len(parts) != 2:
        return None
    a, b = _int(parts[0]), _int(parts[1])
    if not (12 <= a <= 99 and 2 <= b <= 9):
        return None
    t = _row("mul2", 4, "Сколько будет %d × %d? Напиши число." % (a, b), a * b,
             "Умножай по разрядам: единицы, потом десятки, потом сложи результаты.",
             "%d × %d: %d × %d = %d, %d × %d = %d, вместе %d + %d = %d." % (
                 a, b, a // 10 * 10, b, a // 10 * 10 * b, a % 10, b, a % 10 * b,
                 a // 10 * 10 * b, a % 10 * b, a * b))
    t["id"] = "gen-mul2-%d-%d" % (a, b)
    return t


def _rem(*parts):
    if len(parts) != 2:
        return None
    a, b = _int(parts[0]), _int(parts[1])
    if not (20 <= a <= 99 and 3 <= b <= 9):
        return None
    q, r = divmod(a, b)
    if r == 0:
        return None
    t = _row("rem", 4, "Чему равен остаток от деления %d на %d? Напиши число." % (a, b), r,
             "Раздели с остатком: подбери наибольшее число, которое умножить на %d и не превысить %d. Остаток всегда меньше делителя." % (b, a),
             "%d = %d × %d + %d. Остаток — %d, он меньше делителя %d." % (a, b, q, r, r, b))
    t["id"] = "gen-rem-%d-%d" % (a, b)
    return t


GEN = {"mul": _mul, "div": _div, "ord": _ord, "add4": _add4, "sub4": _sub4, "mul2": _mul2, "rem": _rem}


def task_by_id(task_id):
    """Собирает задание из id. Неизвестный или некорректный id — None (маршрут даст 404)."""
    if not task_id or not task_id.startswith("gen-"):
        return None
    parts = task_id.split("-")
    if len(parts) < 3 or parts[1] not in GEN:
        return None
    try:
        task = GEN[parts[1]](*parts[2:])
    except (ValueError, TypeError):
        return None
    return task if task and task["id"] == task_id else None


def make_random(grade, exclude=(), tries=12):
    """Случайный нес решённый вариант. exclude — уже решённые и текущий id."""
    import random
    kinds = KINDS_BY_GRADE.get(grade)
    if not kinds:
        return None
    for _ in range(tries):
        kind = random.choice(kinds)
        if kind == "mul":
            task = _mul(str(random.randint(2, 9)), str(random.randint(2, 9)))
        elif kind == "div":
            b = random.randint(2, 9)
            task = _div(str(b * random.randint(2, 9)), str(b))
        elif kind == "ord":
            b, c = random.randint(2, 9), random.randint(2, 9)
            task = _ord(str(b * c + random.randint(1, 30)), str(b), str(c))
        elif kind == "add4":
            task = _add4(str(random.randint(1000, 8999)), str(random.randint(1000, 9999)))
        elif kind == "sub4":
            a = random.randint(2000, 9999)
            task = _sub4(str(a), str(random.randint(1000, a - 1)))
        elif kind == "mul2":
            task = _mul2(str(random.randint(12, 99)), str(random.randint(2, 9)))
        else:
            a = random.randint(20, 99)
            task = _rem(str(a), str(random.randint(3, 9)))
        if task and task["id"] not in exclude:
            return task
    return None
