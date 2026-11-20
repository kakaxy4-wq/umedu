"""Генераторы заданий для 3–4 классов: математика и русский язык (словарные слова).

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
    "rud": "Словарные слова",
}

# Словарные слова по ФГОС НОО: (слово, позиция опасной буквы, буква-ловушка).
# Букву нельзя проверить ударением — только запомнить, поэтому формат «вставь букву».
RU_WORDS = {
    3: [("берег", 1, "а"), ("восток", 1, "а"), ("город", 1, "а"), ("девочка", 1, "и"),
        ("дежурный", 1, "и"), ("завтрак", 1, "о"), ("капуста", 1, "о"), ("карандаш", 1, "о"),
        ("картина", 1, "о"), ("квартира", 1, "о"), ("комната", 1, "а"), ("компьютер", 1, "а"),
        ("космос", 1, "а"), ("лимон", 1, "е"), ("морковь", 4, "а"), ("обед", 2, "и"),
        ("овощи", 2, "а"), ("огород", 2, "а"), ("орех", 2, "и"), ("посуда", 1, "а"),
        ("понедельник", 3, "и"), ("праздник", 2, "о"), ("ракета", 1, "о"), ("растение", 1, "о"),
        ("рисунок", 1, "е"), ("родина", 1, "а"), ("сапоги", 1, "о"), ("сахар", 1, "о"),
        ("сентябрь", 1, "и"), ("сирень", 1, "е"), ("тарелка", 1, "о"), ("трактор", 2, "о"),
        ("урожай", 2, "а"), ("яблоко", 2, "о")],
    4: [("агроном", 1, "о"), ("аллея", 1, "и"), ("багаж", 1, "о"), ("бассейн", 1, "о"),
        ("билет", 1, "о"), ("болото", 1, "а"), ("вагон", 1, "о"), ("вокзал", 1, "а"),
        ("герой", 1, "о"), ("горизонт", 2, "о"), ("календарь", 1, "о"), ("коллекция", 1, "а"),
        ("коридор", 1, "а"), ("костюм", 3, "и"), ("лагерь", 1, "и"), ("лестница", 1, "и"),
        ("лопата", 1, "а"), ("медаль", 1, "и"), ("метель", 1, "и"), ("мечта", 1, "и"),
        ("надежда", 3, "и"), ("обложка", 3, "а"), ("остров", 4, "а"), ("пассажир", 1, "о"),
        ("песок", 1, "и"), ("пирог", 1, "е"), ("платок", 2, "о"), ("победа", 1, "а"),
        ("погода", 1, "а"), ("салют", 1, "о"), ("свитер", 1, "е"), ("соловей", 1, "а"),
        ("столица", 2, "а"), ("топор", 1, "а"), ("тетрадь", 1, "и"), ("шоссе", 1, "а"),
        ("экскурсия", 1, "и")],
}
RU_BY_WORD = {w: (w, i, bad) for grade, words in RU_WORDS.items() for (w, i, bad) in words}
RU_WORD_GRADE = {w: grade for grade, words in RU_WORDS.items() for (w, i, bad) in words}

KINDS_BY_SUBJECT = {
    (3, "math"): ("mul", "div", "ord"),
    (4, "math"): ("add4", "sub4", "mul2", "rem"),
    (3, "russian"): ("rud",),
    (4, "russian"): ("rud",),
}


def _int(s):
    if not s.isdigit():
        raise ValueError(s)
    return int(s)


def _row(kind, grade, prompt, accept, hint, explain, subject="math"):
    return {"id": None, "grade": grade, "subject": subject, "topic": TOPICS[kind],
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


def _rud(*parts):
    """Словарное слово: вставь букву, которую нельзя проверить ударением."""
    if len(parts) != 1:
        return None
    word = parts[0]
    if word not in RU_BY_WORD:
        return None
    grade = RU_WORD_GRADE[word]
    idx, bad = RU_BY_WORD[word][1], RU_BY_WORD[word][2]
    letter = word[idx]
    if letter == bad:
        return None
    t = _row("rud", grade, "Вставь пропущенную букву: %s?%s. Нажми на правильную букву." % (word[:idx], word[idx + 1:]),
             letter,
             "Словарное слово: букву нельзя проверить ударением. Сомневаешься — вспомни, как слово писали в учебнике, и запомни.",
             "%s — словарное слово: пишем «%s» (%s). Его написание надо запомнить." % (word.capitalize(), letter, word.replace(letter, "«%s»" % letter, 1)),
             subject="russian")
    t["choices"] = [letter, bad]
    t["id"] = "gen-rud-%s" % word
    return t


GEN = {"mul": _mul, "div": _div, "ord": _ord, "add4": _add4, "sub4": _sub4, "mul2": _mul2,
       "rem": _rem, "rud": _rud}


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


def has_kinds(grade, subject):
    return (grade, subject) in KINDS_BY_SUBJECT


def count_solved(done, grade, subject):
    """Сколько решённых id относятся к генераторам предмета (для баланса в плане дня)."""
    prefixes = tuple("gen-%s-" % k for k in KINDS_BY_SUBJECT.get((grade, subject), ()))
    return sum(1 for d in done if d.startswith(prefixes))


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


def make_random(grade, subject="math", exclude=(), tries=12):
    """Случайный нерешённый вариант предмета. exclude — уже решённые и текущий id."""
    import random
    kinds = KINDS_BY_SUBJECT.get((grade, subject))
    if not kinds:
        return None
    for _ in range(tries):
        kind = random.choice(kinds)
        if kind == "rud":
            task = _rud(random.choice(RU_WORDS[grade])[0])
        elif kind == "mul":
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
