"""Числовые задания для номеров математики, которые раньше отмечались баллами вручную.

Условие собирается из чисел, ответ считается здесь же. В data лежат исходные числа,
чтобы тест пересчитал ответ отдельно от текста.
"""
import math


def _out(text, answer, explain, steps, data):
    return {"text": text, "answer": str(answer), "explain": explain, "steps": steps, "data": data}


def _quad(r):
    p, q = r.randint(1, 9), r.randint(1, 9)
    s, prod = p + q, p * q
    ask = r.choice(["sum", "big", "small"])
    ans = {"sum": s, "big": max(p, q), "small": min(p, q)}[ask]
    what = {"sum": "сумму корней", "big": "больший корень", "small": "меньший корень"}[ask]
    named = {"sum": "Сумма корней", "big": "Больший корень", "small": "Меньший корень"}[ask]
    text = ("Решите уравнение x² − %dx + %d = 0. В ответ запишите %s." % (s, prod, what))
    expl = "Корни %d и %d: (%d) + (%d) = %d, (%d) · (%d) = %d. %s — %d." % (
        p, q, p, q, s, p, q, prod, named, ans)
    return _out(text, ans, expl,
                ["Уравнение x² − sx + p = 0, корни в сумме дают s и в произведении p.",
                 "Подходят %d и %d." % (p, q), "%s: %d." % (named, ans)],
                {"kind": "quad", "p": p, "q": q, "ask": ask})


def _work(r):
    pairs = [(6, 3), (4, 12), (6, 6), (8, 8), (5, 20), (10, 15), (4, 4), (12, 6), (9, 18), (10, 10)]
    a, b = r.choice(pairs)
    ans = a * b // (a + b)
    text = ("Первый мастер красит забор за %d ч, второй — за %d ч. За сколько часов они покрасят тот же забор "
            "вместе, если начнут одновременно? Ответ дай целым числом часов." % (a, b))
    expl = "За час вместе 1/%d + 1/%d = %d/%d забора, значит всё займёт %d ч." % (a, b, a + b, a * b, ans)
    return _out(text, ans, expl,
                ["За один час первый делает 1/%d забора, второй — 1/%d." % (a, b),
                 "Вместе за час: %d/%d." % (a + b, a * b), "Всё вместе: %d ч." % ans],
                {"kind": "work", "a": a, "b": b})


def _motion(r):
    v, t = r.choice([40, 50, 60, 80]), r.choice([2, 3, 4, 5])
    ans = v * t
    text = ("Велосипедист едет с постоянной скоростью %d км/ч. Какой путь в километрах он проедет за %d ч?"
            % (v, t))
    expl = "s = vt = %d · %d = %d км." % (v, t, ans)
    return _out(text, ans, expl, ["Скорость постоянная, путь — скорость умножить на время.",
                                  "%d · %d = %d." % (v, t, ans)],
                {"kind": "motion", "v": v, "t": t})


def _ineq(r):
    lo, hi = sorted(r.sample(range(0, 12), 2))
    if hi == lo:
        hi = lo + 2
    if hi == lo + 1:
        hi = lo + 2
    nums = list(range(lo + 1, hi))
    ans = max(nums)
    text = ("Найдите наибольшее целое решение неравенства (x − %d)(x − %d) < 0." % (lo, hi))
    expl = "Произведение отрицательно между корнями: %d < x < %d. Наибольшее целое — %d." % (lo, hi, ans)
    return _out(text, ans, expl,
                ["Корни %d и %d. Между ними произведение меньше нуля." % (lo, hi),
                 "Целые: %s." % ", ".join(map(str, nums)), "Наибольшее — %d." % ans],
                {"kind": "ineq", "lo": lo, "hi": hi})


def _angles(r):
    a = r.choice([35, 40, 45, 50, 55, 60, 70])
    b = r.choice([30, 40, 45, 50, 60, 65])
    if a + b >= 170:
        b = 40
    ans = 180 - a - b
    text = ("В треугольнике два угла равны %d° и %d°. Найдите третий угол. Ответ дайте в градусах." % (a, b))
    expl = "Сумма углов треугольника 180°. Третий угол %d°." % ans
    return _out(text, ans, expl, ["Сумма углов любого треугольника — 180°.",
                                  "180 − %d − %d = %d." % (a, b, ans)],
                {"kind": "angles", "a": a, "b": b})


def _diag(r):
    triples = [(3, 4, 5), (5, 12, 13), (6, 8, 10), (8, 15, 17), (7, 24, 25), (9, 12, 15), (20, 21, 29)]
    a, b, c = r.choice(triples)
    k = r.choice([1, 2])
    a, b, c = a * k, b * k, c * k
    text = ("Прямоугольник со сторонами %d см и %d см. Найдите диагональ в сантиметрах." % (a, b))
    expl = "По теореме Пифагора диагональ √(%d² + %d²) = %d см." % (a, b, c)
    return _out(text, c, expl, ["Диагональ прямоугольника — гипотенуза прямоугольного треугольника.",
                                "%d² + %d² = %d²." % (a, b, c), "Диагональ %d см." % c],
                {"kind": "diag", "a": a, "b": b, "c": c})


def _inscribed(r):
    central = r.choice([40, 50, 60, 70, 80, 100, 120, 140])
    ans = central // 2
    text = ("Центральный угол окружности равен %d°. Вписанный угол опирается на ту же дугу. "
            "Чему равен вписанный угол? Ответ дайте в градусах." % central)
    expl = "Вписанный угол равен половине центрального, опирающегося на ту же дугу: %d°." % ans
    return _out(text, ans, expl, ["Вписанный угол измеряется половиной дуги, на которую опирается.",
                                  "Центральный на ту же дугу — %d°, значит вписанный %d°." % (central, ans)],
                {"kind": "inscribed", "central": central})


def _percent(r):
    price = r.choice(list(range(200, 1001, 50)))
    p = r.choice([10, 20, 25, 50])
    ans = price * (100 + p) // 100
    text = ("Куртка стоила %d руб. Цену подняли на %d%%. Сколько рублей стала стоить куртка?" % (price, p))
    expl = "%d · %d/100 = %d." % (price, 100 + p, ans)
    return _out(text, ans, expl, ["Надбавка %d%% — это множитель %d/100." % (p, 100 + p),
                                  "%d · %d / 100 = %d." % (price, 100 + p, ans)],
                {"kind": "percent", "price": price, "p": p})


def _table_sum(r):
    days = ["Пн", "Вт", "Ср", "Чт", "Пт"]
    vals = [r.randint(2, 20) for _ in days]
    ans = sum(vals)
    rows = "\n".join("%s — %d" % (d, v) for d, v in zip(days, vals))
    text = ("В таблице число проданных тетрадей по дням.\n\n%s\n\nСколько тетрадей продали за все эти дни?" % rows)
    expl = "Сумма %s = %d." % (" + ".join(map(str, vals)), ans)
    return _out(text, ans, expl, ["Сложи числа по всем дням.", expl],
                {"kind": "table-sum", "vals": vals})


def _pick_row(r):
    """Самый дешёвый вариант, у которого память не меньше порога. Ответ — номер строки."""
    need = r.choice([64, 128])
    rows = []
    for mem in (32, 64, 128, 256):
        price = {32: r.randint(8, 12), 64: r.randint(11, 16), 128: r.randint(15, 22), 256: r.randint(20, 30)}[mem]
        rows.append((mem, price * 1000))
    r.shuffle(rows)
    ok = [(i, mem, price) for i, (mem, price) in enumerate(rows) if mem >= need]
    ans = min(ok, key=lambda t: (t[2], t[0]))[0] + 1
    lines = "\n".join("%d) %d ГБ, %d руб." % (i + 1, mem, price) for i, (mem, price) in enumerate(rows))
    text = ("Нужен телефон с памятью не меньше %d ГБ, как можно дешевле. Какой номер строки подходит?\n\n%s"
            % (need, lines))
    expl = "Подходят строки с памятью ≥ %d ГБ. Самая дешёвая из них — строка %d." % (need, ans)
    return _out(text, ans, expl,
                ["Оставь строки, где память не меньше %d ГБ." % need, "Из них выбери меньшую цену.",
                 "Это строка %d." % ans],
                {"kind": "pick-row", "need": need, "rows": rows})


def _deriv(r):
    a = r.randint(1, 6)
    x0 = r.randint(1, 8)
    ans = 2 * a * x0
    text = ("Функция f(x) = %dx². Найдите значение производной f′(%d)." % (a, x0))
    expl = "f′(x) = %dx, f′(%d) = %d." % (2 * a, x0, ans)
    return _out(text, ans, expl, ["Производная x² — это 2x, коэффициент остаётся.",
                                  "f′(x) = %dx." % (2 * a), "Подставь x = %d: %d." % (x0, ans)],
                {"kind": "deriv", "a": a, "x0": x0})


def _logic_count(r):
    n = r.randint(20, 90)
    flags = [n % 2 == 0, n % 3 == 0, n > 50, sum(int(ch) for ch in str(n)) % 2 == 0]
    names = ["число чётное", "число делится на 3", "число больше 50", "сумма цифр чётная"]
    ans = sum(1 for f in flags if f)
    lines = "\n".join("%d) %s" % (i + 1, name) for i, name in enumerate(names))
    text = ("Дано число %d. Сколько из утверждений верны?\n\n%s" % (n, lines))
    expl = "Верны: %s. Всего %d." % (", ".join(name for name, ok in zip(names, flags) if ok) or "ни одно", ans)
    return _out(text, ans, expl, ["Проверь каждое утверждение отдельно.", expl],
                {"kind": "logic", "n": n})


def _area(r):
    base = r.choice([6, 8, 10, 12, 14, 16])
    height = r.randint(3, 12)
    ans = base * height // 2
    text = ("Основание треугольника %d см, высота к этому основанию %d см. Найдите площадь в квадратных сантиметрах."
            % (base, height))
    expl = "S = ah/2 = %d · %d / 2 = %d." % (base, height, ans)
    return _out(text, ans, expl, ["Площадь треугольника — половина произведения основания на высоту.", expl],
                {"kind": "area", "base": base, "height": height})


def _largest_sq(r):
    n = r.choice([10, 17, 26, 37, 50, 65, 80, 101])
    ans = int(math.isqrt(n - 1))
    text = ("Найдите наибольшее целое число x, для которого x² < %d." % n)
    expl = "%d² = %d < %d, а %d² = %d уже не меньше %d." % (ans, ans * ans, n, ans + 1, (ans + 1) ** 2, n)
    return _out(text, ans, expl, ["Ищи наибольший квадрат, который строго меньше %d." % n, expl],
                {"kind": "largest-sq", "n": n})


def _two_digit(r):
    k = r.choice([3, 4, 5, 6, 7, 8, 9])
    ans = len([x for x in range(10, 100) if x % k == 0])
    text = ("Сколько двузначных натуральных чисел делится на %d?" % k)
    expl = "От %d до %d включительно, шаг %d: всего %d чисел." % (
        (10 + k - 1) // k * k, (99 // k) * k, k, ans)
    return _out(text, ans, expl, ["Первое двузначное, кратное %d, и последнее, не больше 99." % k, expl],
                {"kind": "two-digit", "k": k})


def _vertex(r):
    h = r.randint(-4, 5)
    text = ("Функция задана таблицей значений y = −(x − %d)² + 3. При каком x значение y наибольшее?" % h)
    # show a few points so it is a reading task, answer is the vertex
    xs = list(range(h - 2, h + 3))
    rows = "\n".join("x = %d, y = %d" % (x, -((x - h) ** 2) + 3) for x in xs)
    text = ("Значения функции:\n\n%s\n\nПри каком x значение y наибольшее?" % rows)
    expl = "Наибольшее y в вершине: x = %d, y = 3." % h
    return _out(text, h, expl, ["Сравни y в таблице.", "Максимум при x = %d." % h],
                {"kind": "vertex", "h": h})


def _exp(r):
    triples = [(2, 8, 3), (2, 16, 4), (2, 32, 5), (3, 27, 3), (3, 81, 4), (5, 25, 2), (5, 125, 3), (10, 100, 2)]
    base, val, exp = r.choice(triples)
    ans = exp - 1
    text = ("Решите уравнение %d^(x + 1) = %d. В ответ запишите корень." % (base, val))
    expl = "%d^%d = %d, значит x + 1 = %d и x = %d." % (base, exp, val, exp, ans)
    return _out(text, ans, expl, ["Представь правую часть степенью с тем же основанием.", expl],
                {"kind": "exp", "base": base, "exp": exp})


def _box_scale(r):
    k = r.choice([2, 3])
    ans = k ** 3
    a, b, c = r.randint(2, 6), r.randint(2, 6), r.randint(2, 6)
    text = ("Прямоугольный параллелепипед имеет рёбра %d, %d и %d. Все рёбра увеличили в %d раза. "
            "Во сколько раз увеличился объём?" % (a, b, c, k))
    expl = "Объём умножается на куб коэффициента: %d³ = %d. Исходные рёбра на ответ не влияют." % (k, ans)
    return _out(text, ans, expl, ["Каждое измерение умножается на %d." % k, "Объём — на %d³ = %d." % (k, ans)],
                {"kind": "box", "k": k})


def _count_between(r):
    lo, hi = sorted(r.sample(range(-2, 8), 2))
    if hi < lo + 2:
        hi = lo + 2
    left, right = lo - r.randint(1, 3), hi + r.randint(1, 3)
    ans = sum(1 for x in range(left, right + 1) if lo <= x <= hi)
    text = ("Сколько целых чисел x одновременно удовлетворяют неравенству %d ≤ x ≤ %d и лежат на отрезке от %d до %d "
            "включительно?" % (lo, hi, left, right))
    expl = "Пересечение отрезков — от %d до %d, целых чисел %d." % (max(lo, left), min(hi, right), ans)
    return _out(text, ans, expl, ["Возьми пересечение двух отрезков.", "Посчитай целые точки.", expl],
                {"kind": "between", "lo": lo, "hi": hi, "left": left, "right": right})


def _deposit(r):
    s = r.choice([5000, 10000, 20000])
    p = r.choice([10, 20])
    ans = s * (100 + p) // 100 * (100 + p) // 100
    text = ("Вклад %d руб. под %d%% годовых с ежегодной капитализацией. Сколько рублей будет на счёте через 2 года?"
            % (s, p))
    expl = "Каждый год сумма умножается на %d/100. Через два года %d руб." % (100 + p, ans)
    return _out(text, ans, expl, ["После первого года: %d · %d/100." % (s, 100 + p),
                                  "После второго — ещё раз умножить на тот же множитель.", "Получается %d." % ans],
                {"kind": "deposit", "s": s, "p": p})


def _similar(r):
    k = r.choice([2, 3, 4])
    ans = k * k
    text = ("Два треугольника подобны, коэффициент подобия равен %d. Во сколько раз площадь большего больше площади "
            "меньшего?" % k)
    expl = "Площади относятся как квадрат коэффициента: %d² = %d." % (k, ans)
    return _out(text, ans, expl, ["У подобных фигур отношение площадей — квадрат отношения сторон.", expl],
                {"kind": "similar", "k": k})


def _abs_sum(r):
    # |x| + |x - 2| минимум равен 2, достигается на [0, 2]. Наименьшее целое a, при котором есть решение |x|+|x-2| = a
    text = ("Найдите наименьшее целое число a, при котором уравнение |x| + |x − 2| = a имеет хотя бы одно решение.")
    expl = "Выражение |x| + |x − 2| равно 2 на всём отрезке от 0 до 2 и больше 2 вне его. Наименьшее такое a — 2."
    return _out(text, 2, expl,
                ["На отрезке между 0 и 2 сумма модулей постоянна.", "Посчитай её в точке 0: |0| + |−2| = 2.",
                 "Меньше 2 выражение не бывает."],
                {"kind": "abs-sum"})


def _lcm_below(r):
    pairs = [(4, 6), (6, 8), (6, 9), (5, 7), (8, 12), (9, 12)]
    a, b = r.choice(pairs)
    n = r.randint(80, 180)
    g = math.gcd(a, b)
    step = a * b // g
    ans = (n - 1) // step * step
    text = ("Найдите наибольшее натуральное число, меньшее %d, которое делится и на %d, и на %d." % (n, a, b))
    expl = "НОК(%d, %d) = %d. Наибольшее кратное, меньшее %d, — %d." % (a, b, step, n, ans)
    return _out(text, ans, expl, ["Число должно делиться на оба, значит на их НОК.", "НОК = %d." % step, expl],
                {"kind": "lcm", "a": a, "b": b, "n": n})


def recompute(data):
    """Тот же ответ из data, без текста условия. Им пользуется тест."""
    k = data["kind"]
    if k == "quad":
        p, q = data["p"], data["q"]
        return {"sum": p + q, "big": max(p, q), "small": min(p, q)}[data["ask"]]
    if k == "work":
        a, b = data["a"], data["b"]
        return a * b // (a + b)
    if k == "motion":
        return data["v"] * data["t"]
    if k == "ineq":
        return max(range(data["lo"] + 1, data["hi"]))
    if k == "angles":
        return 180 - data["a"] - data["b"]
    if k == "diag":
        return data["c"]
    if k == "inscribed":
        return data["central"] // 2
    if k == "percent":
        return data["price"] * (100 + data["p"]) // 100
    if k == "table-sum":
        return sum(data["vals"])
    if k == "pick-row":
        ok = [(i, price) for i, (mem, price) in enumerate(data["rows"]) if mem >= data["need"]]
        return min(ok, key=lambda t: (t[1], t[0]))[0] + 1
    if k == "deriv":
        return 2 * data["a"] * data["x0"]
    if k == "logic":
        n = data["n"]
        return sum([n % 2 == 0, n % 3 == 0, n > 50, sum(int(ch) for ch in str(n)) % 2 == 0])
    if k == "area":
        return data["base"] * data["height"] // 2
    if k == "largest-sq":
        return int(math.isqrt(data["n"] - 1))
    if k == "two-digit":
        return len([x for x in range(10, 100) if x % data["k"] == 0])
    if k == "vertex":
        return data["h"]
    if k == "exp":
        return data["exp"] - 1
    if k == "box":
        return data["k"] ** 3
    if k == "between":
        lo, hi, left, right = data["lo"], data["hi"], data["left"], data["right"]
        return sum(1 for x in range(left, right + 1) if lo <= x <= hi)
    if k == "deposit":
        s, p = data["s"], data["p"]
        return s * (100 + p) // 100 * (100 + p) // 100
    if k == "similar":
        return data["k"] ** 2
    if k == "abs-sum":
        return 2
    if k == "lcm":
        step = data["a"] * data["b"] // math.gcd(data["a"], data["b"])
        return (data["n"] - 1) // step * step
    raise KeyError(k)


MATH = {
    ("oge-math-2026", 20): _quad,
    ("oge-math-2026", 21): lambda r: r.choice([_work, _motion])(r),
    ("oge-math-2026", 22): _ineq,
    ("oge-math-2026", 23): _angles,
    ("oge-math-2026", 24): _diag,
    ("oge-math-2026", 25): _inscribed,
    ("ege-math-base-2026", 2): lambda r: r.choice([_percent, _motion, _work])(r),
    ("ege-math-base-2026", 3): _table_sum,
    ("ege-math-base-2026", 6): _pick_row,
    ("ege-math-base-2026", 7): _deriv,
    ("ege-math-base-2026", 8): _logic_count,
    ("ege-math-base-2026", 9): lambda r: r.choice([_area, _diag])(r),
    ("ege-math-base-2026", 18): _largest_sq,
    ("ege-math-base-2026", 21): _two_digit,
    ("ege-math-profile-2026", 8): _deriv,
    ("ege-math-profile-2026", 11): _vertex,
    ("ege-math-profile-2026", 13): _exp,
    ("ege-math-profile-2026", 14): _box_scale,
    ("ege-math-profile-2026", 15): _count_between,
    ("ege-math-profile-2026", 16): _deposit,
    ("ege-math-profile-2026", 17): lambda r: r.choice([_similar, _angles, _diag])(r),
    ("ege-math-profile-2026", 18): _abs_sum,
    ("ege-math-profile-2026", 19): _lcm_below,
}

ABOUT = {
    ("oge-math-2026", 20): "Квадратное уравнение с целыми корнями: сумма или один из корней.",
    ("oge-math-2026", 21): "Текстовая задача: совместная работа или путь при постоянной скорости.",
    ("oge-math-2026", 22): "Квадратное неравенство: наибольшее целое решение.",
    ("oge-math-2026", 23): "Треугольник: третий угол по сумме 180°.",
    ("oge-math-2026", 24): "Диагональ прямоугольника по теореме Пифагора.",
    ("oge-math-2026", 25): "Вписанный угол — половина центрального на ту же дугу.",
    ("ege-math-base-2026", 2): "Текстовая задача: процент, путь или совместная работа.",
    ("ege-math-base-2026", 3): "Сумма по таблице.",
    ("ege-math-base-2026", 6): "Выбор строки таблицы по двум условиям.",
    ("ege-math-base-2026", 7): "Значение производной квадратичной функции.",
    ("ege-math-base-2026", 8): "Сколько утверждений о числе верны.",
    ("ege-math-base-2026", 9): "Площадь треугольника или диагональ прямоугольника.",
    ("ege-math-base-2026", 18): "Наибольшее целое, квадрат которого меньше данного числа.",
    ("ege-math-base-2026", 21): "Сколько двузначных чисел делится на заданное.",
    ("ege-math-profile-2026", 8): "Производная f(x) = ax² в точке.",
    ("ege-math-profile-2026", 11): "По таблице значений найти x, где y наибольшее.",
    ("ege-math-profile-2026", 13): "Показательное уравнение, корень целый.",
    ("ege-math-profile-2026", 14): "Во сколько раз растёт объём, если рёбра увеличили в k раз.",
    ("ege-math-profile-2026", 15): "Сколько целых в пересечении двух отрезков.",
    ("ege-math-profile-2026", 16): "Вклад на два года с ежегодной капитализацией.",
    ("ege-math-profile-2026", 17): "Подобие, угол треугольника или диагональ.",
    ("ege-math-profile-2026", 18): "Наименьшее целое a, при котором |x| + |x − 2| = a имеет решение.",
    ("ege-math-profile-2026", 19): "Наибольшее число меньше N, делящееся на два заданных.",
}
