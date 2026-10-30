"""ОГЭ по информатике №16: бесконечные варианты задачи на программирование.

Вариант = сид. Генератор собирает условие (что считать × какие числа × как вводятся), эталонное решение и тесты:
два открытых примера и четыре скрытых, ответы к ним считает программа. Проверка — в браузере, как у задач курса
(static/py/cq_runtime.py); попытки пишутся в oge_drill с num = 16.
"""
import random

NUM = 16
PREFIX = "oge16-"
LESSON = 8                 # открывается вместе с задачами №16 в курсе
MAX_VALUE = 30000


def _filters(r):
    """(мн. ч. «чисел, …», ед. ч. «число, …», условие на Python, проверка)."""
    kind = r.choice(["mult", "end", "even", "two", "mult_end", "mult_not", "digitsum", "first"])
    if kind == "mult":
        k = r.randint(3, 9)
        return "чисел, кратных %d" % k, "число, кратное %d" % k, "x %% %d == 0" % k, lambda x: x % k == 0
    if kind == "end":
        d = r.randint(1, 9)
        return ("чисел, оканчивающихся на %d" % d, "число, оканчивающееся на %d" % d, "x %% 10 == %d" % d,
                lambda x: x % 10 == d)
    if kind == "even":
        return "чётных чисел", "чётное число", "x % 2 == 0", lambda x: x % 2 == 0
    if kind == "two":
        return "двузначных чисел", "двузначное число", "10 <= x <= 99", lambda x: 10 <= x <= 99
    if kind == "mult_end":
        k, d = r.choice([3, 7, 9]), r.randint(1, 9)
        return ("чисел, кратных %d и оканчивающихся на %d" % (k, d), "число, кратное %d и оканчивающееся на %d" % (k, d),
                "x %% %d == 0 and x %% 10 == %d" % (k, d), lambda x: x % k == 0 and x % 10 == d)
    if kind == "digitsum":
        s = r.randint(5, 18)
        return ("чисел, сумма цифр которых равна %d" % s, "число, сумма цифр которого равна %d" % s,
                "sum(int(c) for c in str(x)) == %d" % s, lambda x, s=s: sum(map(int, str(x))) == s)
    if kind == "first":
        d = r.randint(1, 9)
        return ("чисел, которые начинаются с цифры %d" % d, "число, которое начинается с цифры %d" % d,
                "str(x)[0] == '%d'" % d, lambda x, d=d: str(x).startswith(str(d)))
    a, b = r.choice([(3, 9), (2, 4), (5, 10), (3, 6), (2, 6), (4, 8)])
    return ("чисел, кратных %d, но не кратных %d" % (a, b), "число, кратное %d, но не кратное %d" % (a, b),
            "x %% %d == 0 and x %% %d != 0" % (a, b), lambda x: x % a == 0 and x % b != 0)


# что считать: (условие задачи, инициализация, условие обновления, обновление, вывод, функция ответа, нужно ли совпадение)
AGGS = {
    "count": ("количество {pl}", "cnt = 0", "{c}", "cnt += 1", "cnt", lambda xs: len(xs), False),
    "sum": ("сумму {pl}", "s = 0", "{c}", "s += x", "s", lambda xs: sum(xs), False),
    "max": ("наибольшее {sg}", "m = 0", "{c} and x > m", "m = x", "m", lambda xs: max(xs), True),
    "min": ("наименьшее {sg}", "m = %d" % (MAX_VALUE + 1), "{c} and x < m", "m = x", "m", lambda xs: min(xs), True),
    "avg": ("среднее арифметическое {pl}. Результат округли до ближайшего целого", "s, cnt = 0, 0", "{c}",
            "s += x; cnt += 1", "round(s / cnt)", lambda xs: round(sum(xs) / len(xs)), True),
    "pair": ("количество {pl} и наибольшее из них", "cnt, m = 0, 0", "{c}", "cnt += 1; m = x if x > m else m",
             "cnt, m", lambda xs: "%d %d" % (len(xs), max(xs)), True),
}

INPUT_N = ("Программа получает на вход количество чисел в последовательности, а затем сами числа — каждое с новой строки. "
           "В последовательности всегда имеется {need}. Количество чисел не превышает 1000. "
           "Введённые числа не превышают %d." % MAX_VALUE)
INPUT_ZERO = ("Программа получает на вход натуральные числа, количество введённых чисел неизвестно, последовательность "
              "чисел заканчивается числом 0 (0 — признак окончания ввода, не входит в последовательность). "
              "В последовательности всегда имеется {need}. Количество чисел, не считая 0, не превышает 1000. "
              "Введённые числа не превышают %d." % MAX_VALUE)


def _numbers(r, pred, length, hi, need_match, no_match=False):
    def pick(want):
        for _ in range(200):
            x = r.randint(1, hi)
            if pred(x) == want:
                return x
        return r.choice([x for x in range(1, hi + 1) if pred(x) == want])   # редкие числа (двузначные среди 30 000)
    xs = []
    for _ in range(length):
        xs.append(pick(not no_match and r.random() < 0.4))
    if need_match and not any(pred(x) for x in xs):
        xs[r.randrange(length)] = pick(True)
    return xs


def make(seed):
    r = random.Random(seed * 7919 + NUM)
    pl, sg, cond, pred = _filters(r)
    agg = r.choice(list(AGGS))
    what, init, upd_cond, upd, out, func, need_match = AGGS[agg]
    zero = r.random() < 0.5
    need = "хотя бы одно " + sg if need_match else "хотя бы одно число"
    what = what.format(pl=pl, sg=sg)
    tail = ("два числа через пробел: сначала количество, потом максимум" if agg == "pair" else "одно число — %s" % what)
    text = ("Напишите программу, которая в последовательности натуральных чисел определяет %s.\n\n%s\n\n"
            "Программа должна вывести %s." % (what, (INPUT_ZERO if zero else INPUT_N).format(need=need), tail))
    c = upd_cond.format(c=cond)
    if zero:
        solution = "%s\nx = int(input())\nwhile x != 0:\n    if %s:\n        %s\n    x = int(input())\nprint(%s)" % (
            init, c, upd, out)
    else:
        solution = "n = int(input())\n%s\nfor i in range(n):\n    x = int(input())\n    if %s:\n        %s\nprint(%s)" % (
            init, c, upd, out)

    tests = []
    plan = [(r.randint(4, 6), 300, False), (r.randint(5, 8), 300, False), (r.randint(10, 20), MAX_VALUE, False),
            (r.randint(30, 60), MAX_VALUE, False), (1, 300, False), (r.randint(3, 6), 300, not need_match)]
    for i, (length, hi, no_match) in enumerate(plan):
        xs = _numbers(r, pred, length, hi, need_match, no_match)
        stdin = "\n".join(map(str, ([] if zero else [len(xs)]) + xs + ([0] if zero else [])))
        tests.append({"stdin": stdin, "stdout": str(func([x for x in xs if pred(x)])), "hidden": i >= 2})
    hint = ("Заведи переменную до цикла, внутри цикла проверяй условие `%s`. %s" % (
        cond, "Цикл `while x != 0` — ввод заканчивается нулём." if zero else "Сначала прочитай n, потом n чисел в цикле `for`."))
    steps = [hint, "Проверь программу на обоих примерах из условия: вывод должен совпасть.",
             "Отдельно проверь короткий список: одно подходящее число и несколько неподходящих."]
    return {"id": "%s%d" % (PREFIX, seed), "seed": seed, "oge": NUM, "lesson": LESSON, "level": 2,
            "title": "ОГЭ №16: %s" % what, "text": text, "starter": "", "tests": tests, "hint": hint,
            "solution": solution, "steps": steps}


def seed_of(task_id):
    """«oge16-123» → 123; иначе None."""
    if not task_id.startswith(PREFIX):
        return None
    tail = task_id[len(PREFIX):]
    return int(tail) if tail.isdigit() and 0 < int(tail) < 10 ** 7 else None
