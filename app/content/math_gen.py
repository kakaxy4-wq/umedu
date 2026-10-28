"""Свои варианты по математике для umedu 2.0: ОГЭ (номера 6–10, 12–17, 19), ЕГЭ профиль (1–7, 9, 10, 12) и база.

Как и app/content/oge_gen.py: вариант задаётся парой (номер, сид), условие и ответ каждый раз строятся одинаково,
проверка — на сервере пересборкой. Условия написаны по образцу экзаменационных (кодификатор ФИПИ), не копии заданий
банка. Ответ считается точно (Fraction) и всегда конечная десятичная дробь — как в бланке ответов.
Номера с чертежами и графиками (ОГЭ 11, 18; ЕГЭ 8, 11) здесь не генерируются.
"""
import math
import random
import re
from fractions import Fraction as F


def fmt(x):
    """Fraction → «-2,75». Только для конечных десятичных дробей."""
    x = F(x)
    sign, x = ("-" if x < 0 else ""), abs(x)
    whole, rest = divmod(x.numerator, x.denominator)
    if not rest:
        return sign + str(whole)
    digits = ""
    for _ in range(8):
        rest *= 10
        d, rest = divmod(rest, x.denominator)
        digits += str(d)
        if not rest:
            return sign + str(whole) + "," + digits
    raise ValueError("бесконечная дробь")


def finite(x):
    d = F(x).denominator
    for p in (2, 5):
        while d % p == 0:
            d //= p
    return d == 1


def _num(s):
    s = re.sub(r"\s+", "", str(s)).replace(",", ".").replace("−", "-")
    try:
        return F(s)
    except (ValueError, ZeroDivisionError):
        return None


def _frac(x):
    """Дробь для условия: 3/4 → «3/4», 2 → «2»."""
    x = F(x)
    return str(x.numerator) if x.denominator == 1 else "%d/%d" % (x.numerator, x.denominator)


def _signed(k, var="x", first=False):
    """Слагаемое с правильным знаком: (−3, x) → « − 3x»."""
    if k == 0:
        return ""
    a = abs(k)
    body = ("" if a == 1 and var else fmt(a)) + var
    if first:
        return ("−" if k < 0 else "") + body
    return (" − " if k < 0 else " + ") + body


# ================================================================== ОГЭ
def o6(r):
    while True:
        kind = r.choice(["sum", "mix", "dec"])
        if kind == "sum":
            a, b = F(r.randint(1, 9), r.choice([2, 4, 5, 8])), F(r.randint(1, 9), r.choice([2, 4, 5, 10]))
            c = r.choice([2, 4, 5, 8, 10, 20])
            ans, text = (a + b) * c, "(%s + %s) · %d" % (_frac(a), _frac(b), c)
        elif kind == "mix":
            a, b = F(r.randint(1, 9), r.choice([3, 6, 9])), F(r.randint(1, 9), r.choice([3, 6, 9]))
            c = F(r.randint(1, 9), r.choice([2, 4, 5]))
            if a == b:
                continue
            ans, text = (a - b) / c, "(%s − %s) : %s" % (_frac(a), _frac(b), _frac(c))
        else:
            a, b, c = F(r.randint(11, 99), 10), F(r.randint(2, 9), 10), F(r.randint(1, 99), 10)
            ans, text = a * b - c, "%s · %s − %s" % (fmt(a), fmt(b), fmt(c))
        if finite(ans) and ans != 0 and len(fmt(ans)) <= 7:
            return {"text": "Найдите значение выражения **%s**." % text, "answer": fmt(ans),
                    "explain": "%s = %s." % (text, fmt(ans))}


def o7(r):
    m = r.randint(3, 9)
    good = r.randint(m * m + 1, (m + 1) ** 2 - 1)
    bad = set()
    while len(bad) < 3:
        x = r.choice([r.randint((m - 2) ** 2 + 1, m * m - 1), r.randint((m + 1) ** 2 + 1, (m + 2) ** 2 - 1)])
        if not math.isqrt(x) ** 2 == x:
            bad.add(x)
    opts = list(bad) + [good]
    r.shuffle(opts)
    right = opts.index(good) + 1
    return {"text": "Какое из чисел заключено между числами **%d** и **%d**?\n\n%s\n\nВ ответе запишите номер выбранного варианта."
                    % (m, m + 1, "\n".join("%d) √%d" % (i + 1, x) for i, x in enumerate(opts))),
            "answer": str(right),
            "explain": "Возведём в квадрат: %d² = %d, %d² = %d. Между ними только %d — это вариант %d."
                       % (m, m * m, m + 1, (m + 1) ** 2, good, right)}


def o8(r):
    kind = r.choice(["pow", "root"])
    if kind == "pow":
        a = r.choice([2, 3, 5, 10])
        x, y, z = r.randint(2, 6), r.randint(2, 6), r.randint(2, 9)
        while not 0 < x + y - z <= (4 if a > 3 else 7):
            x, y, z = r.randint(2, 6), r.randint(2, 6), r.randint(2, 9)
        ans = F(a) ** (x + y - z)
        text = "%d^%d · %d^%d : %d^%d" % (a, x, a, y, a, z)
        expl = "При умножении показатели складываются, при делении вычитаются: %d^(%d + %d − %d) = %d^%d = %s." % (
            a, x, y, z, a, x + y - z, fmt(ans))
    else:
        p, k = r.choice([2, 3, 5, 6, 7]), r.randint(2, 6)      # √(pk²) · √p = pk — корень извлекается нацело
        ans = F(p * k)
        text = "√%d · √%d" % (p * k * k, p)
        expl = "√%d · √%d = √(%d · %d) = √%d = %s." % (p * k * k, p, p * k * k, p, p * p * k * k, fmt(ans))
    return {"text": "Найдите значение выражения **%s**." % text, "answer": fmt(ans), "explain": expl}


def o9(r):
    if r.random() < 0.5:
        while True:
            a, c = r.randint(2, 9), r.randint(-9, 9)
            b, d = r.randint(-20, 20), r.randint(-20, 20)
            if a != c and c != 0:
                x = F(d - b, a - c)
                if finite(x) and x != 0 and len(fmt(x)) <= 5:
                    break
        eq = "%s%s = %s%s" % (_signed(a, first=True), _signed(b, ""), _signed(c, first=True), _signed(d, ""))
        return {"text": "Найдите корень уравнения **%s**." % eq, "answer": fmt(x),
                "explain": "Переносим: (%d − %d)x = %d − %d, x = %s." % (a, c, d, b, fmt(x))}
    while True:
        x1, x2 = r.randint(-9, 9), r.randint(-9, 9)
        if x1 != x2 and x1 + x2 != 0 and x1 * x2 != 0:
            break
    want = r.choice(["больший", "меньший"])
    ans = max(x1, x2) if want == "больший" else min(x1, x2)
    eq = "x²%s%s = 0" % (_signed(-(x1 + x2)), _signed(x1 * x2, ""))
    return {"text": "Решите уравнение **%s**. Если уравнение имеет более одного корня, в ответ запишите %s из корней."
                    % (eq, want),
            "answer": str(ans),
            "explain": "По теореме Виета корни %d и %d (сумма %d, произведение %d). %s — %d." % (
                min(x1, x2), max(x1, x2), x1 + x2, x1 * x2, want.capitalize(), ans)}


_PROB = [("В фирме такси в наличии {n} легковых автомобилей; {k} из них чёрного цвета, остальные — других цветов. "
          "По вызову выехала машина, случайно выбранная из имеющихся. Найдите вероятность того, что к заказчику приедет "
          "машина не чёрного цвета.", True),
         ("В лотерее {n} билетов, из них {k} выигрышных. Найдите вероятность выиграть, купив один билет.", False),
         ("В коробке {n} одинаковых на ощупь шариков, {k} из них красные. Наугад достают один шарик. Найдите вероятность "
          "того, что он окажется не красным.", True),
         ("На экзамене {n} билетов, Серёжа не выучил {k} из них. Найдите вероятность того, что ему попадётся выученный "
          "билет.", True),
         ("Из {n} пирожков в тарелке {k} с капустой, остальные с вишней. Маша наугад берёт один пирожок. Найдите "
          "вероятность того, что он окажется с капустой.", False)]


def o10(r):
    text, other = r.choice(_PROB)
    n = r.choice([20, 25, 40, 50, 80, 100, 125, 200, 250, 400, 500, 1000])
    k = r.randint(1, n - 1)
    p = F(n - k if other else k, n)
    return {"text": text.format(n=n, k=k), "answer": fmt(p),
            "explain": "Вероятность = число подходящих исходов : число всех = %d : %d = %s." % (
                (n - k) if other else k, n, fmt(p))}


def o12(r):
    kind = r.choice(["temp", "area", "speed"])
    if kind == "temp":
        c = r.choice(range(-40, 101, 5))
        f = F(9, 5) * c + 32
        return {"text": "Перевести значение температуры по шкале Цельсия в шкалу Фаренгейта позволяет формула "
                        "**F = 1,8C + 32**, где C — градусы Цельсия, F — градусы Фаренгейта. Какая температура по шкале "
                        "Фаренгейта соответствует %d° по шкале Цельсия?" % c,
                "answer": fmt(f), "explain": "F = 1,8 · %d + 32 = %s." % (c, fmt(f))}
    if kind == "area":
        d1, d2 = r.randint(3, 30), r.randint(3, 30)
        s = F(d1 * d2, 2)
        return {"text": "Площадь ромба можно вычислить по формуле **S = d₁d₂/2**, где d₁ и d₂ — его диагонали. "
                        "Найдите диагональ d₁, если диагональ d₂ равна %d, а площадь ромба равна %s." % (d2, fmt(s)),
                "answer": str(d1), "explain": "d₁ = 2S : d₂ = 2 · %s : %d = %d." % (fmt(s), d2, d1)}
    t, v = r.randint(2, 9), r.randint(4, 25)
    a = r.choice([1, 2, 3, 4, 5])
    s = v * t + F(a * t * t, 2)
    return {"text": "Путь при равноускоренном движении вычисляется по формуле **s = vt + at²/2**. Найдите s (в метрах), "
                    "если v = %d м/с, t = %d с, a = %d м/с²." % (v, t, a),
            "answer": fmt(s), "explain": "s = %d · %d + %d · %d² / 2 = %s." % (v, t, a, t, fmt(s))}


def o13(r):
    while True:
        a, c = r.randint(-9, 9), r.randint(-9, 9)
        b, d = r.randint(-20, 20), r.randint(-20, 20)
        if a != c and a != 0 and c != 0:
            x0 = F(d - b, a - c)
            if x0.denominator == 1 and x0 != 0:
                break
    x0 = int(x0)
    sign = r.choice(["≥", "≤"])
    # ax + b ≥ cx + d  ⇔  (a − c)x ≥ d − b
    ge = (sign == "≥") == (a - c > 0)                  # после деления на (a − c): x ≥ x0 или x ≤ x0
    right = "[%d; +∞)" % x0 if ge else "(−∞; %d]" % x0
    opts = ["[%d; +∞)" % x0, "(−∞; %d]" % x0, "[%d; +∞)" % -x0, "(−∞; %d]" % -x0]
    r.shuffle(opts)
    ineq = "%s%s %s %s%s" % (_signed(a, first=True), _signed(b, ""), sign, _signed(c, first=True), _signed(d, ""))
    return {"text": "Укажите решение неравенства **%s**.\n\n%s\n\nВ ответе запишите номер выбранного варианта."
                    % (ineq, "\n".join("%d) %s" % (i + 1, o) for i, o in enumerate(opts))),
            "answer": str(opts.index(right) + 1),
            "explain": "(%d)x %s %d. %s x %s %d — это %s." % (
                a - c, sign, d - b, "Делим на отрицательное число — знак меняется:" if a - c < 0 else "Делим:",
                "≥" if ge else "≤", x0, right)}


def o14(r):
    a, d, n = r.randint(2, 20), r.randint(2, 9), r.randint(5, 15)
    if r.random() < 0.5:
        return {"text": "Улитка в первую минуту проползла %d см, а в каждую следующую — на %d см больше, чем в "
                        "предыдущую. Сколько сантиметров проползла улитка за %d-ю минуту?" % (a, d, n),
                "answer": str(a + d * (n - 1)), "explain": "aₙ = a₁ + (n − 1)d = %d + %d · %d = %d." % (
                    a, n - 1, d, a + d * (n - 1))}
    total = n * (2 * a + d * (n - 1)) // 2
    return {"text": "Бригада в первый день уложила %d м дороги, а каждый следующий день — на %d м больше, чем в предыдущий. "
                    "Сколько метров дороги уложила бригада за первые %d дней?" % (a, d, n),
            "answer": str(total), "explain": "Sₙ = (2a₁ + (n − 1)d) · n / 2 = (2 · %d + %d · %d) · %d / 2 = %d." % (
                a, n - 1, d, n, total)}


def o15(r):
    kind = r.choice(["sum", "iso", "ext"])
    if kind == "sum":
        a, b = r.randint(20, 90), r.randint(20, 70)
        return {"text": "В треугольнике ABC угол A равен %d°, угол B равен %d°. Найдите угол C. Ответ дайте в градусах."
                        % (a, b), "answer": str(180 - a - b),
                "explain": "Сумма углов треугольника 180°: 180 − %d − %d = %d." % (a, b, 180 - a - b)}
    if kind == "iso":
        top = r.randrange(20, 160, 2)
        return {"text": "В равнобедренном треугольнике ABC с основанием AC угол B равен %d°. Найдите угол A. Ответ дайте "
                        "в градусах." % top, "answer": str((180 - top) // 2),
                "explain": "Углы при основании равны: (180 − %d) : 2 = %d." % (top, (180 - top) // 2)}
    a, b = r.randint(20, 80), r.randint(20, 80)
    return {"text": "В треугольнике ABC угол A равен %d°, угол B равен %d°. Найдите внешний угол при вершине C. Ответ "
                    "дайте в градусах." % (a, b), "answer": str(a + b),
            "explain": "Внешний угол равен сумме двух внутренних, не смежных с ним: %d + %d = %d." % (a, b, a + b)}


_TRIPLES = [(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (6, 8, 10), (9, 12, 15), (20, 21, 29), (12, 16, 20)]


def o16(r):
    kind = r.choice(["inscribed", "circum", "tangent"])
    if kind == "inscribed":
        c = r.randrange(20, 180, 2)
        return {"text": "Точка O — центр окружности, на которой лежат точки A, B и C. Известно, что центральный угол AOB "
                        "равен %d°, а точка C лежит на большей дуге AB. Найдите вписанный угол ACB. Ответ дайте в градусах."
                        % min(c, 360 - c), "answer": str(min(c, 360 - c) // 2),
                "explain": "Вписанный угол равен половине центрального, опирающегося на ту же дугу: %d : 2 = %d." % (
                    min(c, 360 - c), min(c, 360 - c) // 2)}
    a, b, c = r.choice(_TRIPLES)
    k = r.randint(1, 3)
    if kind == "circum":
        return {"text": "Катеты прямоугольного треугольника равны %d и %d. Найдите радиус окружности, описанной около "
                        "этого треугольника." % (a * k, b * k), "answer": fmt(F(c * k, 2)),
                "explain": "Центр описанной окружности — середина гипотенузы. Гипотенуза √(%d² + %d²) = %d, радиус %s." % (
                    a * k, b * k, c * k, fmt(F(c * k, 2)))}
    return {"text": "Отрезок AB касается окружности с центром O в точке B. Найдите AO, если AB = %d, а радиус окружности "
                    "равен %d." % (b * k, a * k), "answer": str(c * k),
            "explain": "Радиус в точку касания перпендикулярен касательной: AO = √(%d² + %d²) = %d." % (b * k, a * k, c * k)}


def o17(r):
    kind = r.choice(["trap", "rhomb", "par"])
    if kind == "trap":
        a, b, h = r.randint(2, 20), r.randint(2, 20), r.randint(2, 15)
        s = F((a + b) * h, 2)
        return {"text": "Основания трапеции равны %d и %d, а высота равна %d. Найдите площадь трапеции." % (a, b, h),
                "answer": fmt(s), "explain": "S = (a + b) · h / 2 = (%d + %d) · %d / 2 = %s." % (a, b, h, fmt(s))}
    if kind == "rhomb":
        d1, d2 = r.randint(2, 30), r.randint(2, 30)
        return {"text": "Диагонали ромба равны %d и %d. Найдите его площадь." % (d1, d2), "answer": fmt(F(d1 * d2, 2)),
                "explain": "S = d₁d₂ / 2 = %d · %d / 2 = %s." % (d1, d2, fmt(F(d1 * d2, 2)))}
    a, b = r.randint(3, 20), r.randint(3, 20)
    ang = r.choice([30, 150])
    s = F(a * b, 2)
    return {"text": "Стороны параллелограмма равны %d и %d, а один из его углов равен %d°. Найдите площадь "
                    "параллелограмма." % (a, b, ang), "answer": fmt(s),
            "explain": "S = ab · sin %d° = %d · %d · 1/2 = %s." % (ang, a, b, fmt(s))}


_TRUE = ["Вертикальные углы равны.", "Сумма углов любого треугольника равна 180 градусам.",
         "Диагонали прямоугольника равны.", "Диагонали ромба перпендикулярны.",
         "В любой треугольник можно вписать окружность.", "Площадь квадрата равна квадрату его стороны.",
         "Центр описанной около прямоугольного треугольника окружности лежит на середине гипотенузы.",
         "Касательная к окружности перпендикулярна радиусу, проведённому в точку касания.",
         "Если две стороны и угол между ними одного треугольника соответственно равны двум сторонам и углу между ними "
         "другого треугольника, то такие треугольники равны.",
         "Средняя линия трапеции параллельна её основаниям.", "Все углы прямоугольника прямые.",
         "Через любые две различные точки проходит ровно одна прямая.",
         "В равнобедренном треугольнике углы при основании равны.",
         "Вписанный угол равен половине центрального угла, опирающегося на ту же дугу."]
_FALSE = ["Диагонали любого параллелограмма равны.", "Сумма углов любого треугольника равна 360 градусам.",
          "Любой ромб является квадратом.", "Площадь трапеции равна произведению её оснований.",
          "Диагонали любой трапеции точкой пересечения делятся пополам.",
          "Если угол острый, то смежный с ним угол тоже острый.",
          "В любом прямоугольнике диагонали перпендикулярны.", "Около любого ромба можно описать окружность.",
          "Тангенс любого острого угла меньше единицы.", "Все высоты треугольника пересекаются в центре вписанной окружности.",
          "Площадь круга равна произведению радиуса на число π.", "Любые два равнобедренных треугольника подобны.",
          "Гипотенуза прямоугольного треугольника равна сумме его катетов.",
          "Смежные углы всегда равны."]


def o19(r):
    t = r.choice(_TRUE)
    opts = [t] + r.sample(_FALSE, 2)
    r.shuffle(opts)
    return {"text": "Какое из следующих утверждений верно?\n\n%s\n\nВ ответе запишите номер выбранного утверждения."
                    % "\n".join("%d) %s" % (i + 1, s) for i, s in enumerate(opts)),
            "answer": str(opts.index(t) + 1), "explain": "Верно: «%s» Остальные два утверждения ложны." % t}


# ================================================================== ЕГЭ, профильный уровень
def p1(r):
    a, b, c = r.choice(_TRIPLES)
    k = r.randint(1, 4)
    kind = r.choice(["sin", "cos", "tg"])
    if kind == "sin":
        return {"text": "В треугольнике ABC угол C равен 90°, AB = %d, sin A = %s. Найдите BC." % (c * k, _frac(F(a, c))),
                "answer": str(a * k),
                "explain": "sin A = BC / AB, BC = %d · %s = %d." % (c * k, _frac(F(a, c)), a * k)}
    if kind == "cos":
        return {"text": "В треугольнике ABC угол C равен 90°, AB = %d, cos A = %s. Найдите AC." % (c * k, _frac(F(b, c))),
                "answer": str(b * k), "explain": "cos A = AC / AB, AC = %d · %s = %d." % (c * k, _frac(F(b, c)), b * k)}
    return {"text": "В треугольнике ABC угол C равен 90°, AC = %d, tg A = %s. Найдите BC." % (b * k, _frac(F(a, b))),
            "answer": str(a * k), "explain": "tg A = BC / AC, BC = %d · %s = %d." % (b * k, _frac(F(a, b)), a * k)}


def p2(r):
    while True:
        x1, y1, x2, y2 = (r.randint(-9, 9) for _ in range(4))
        if (x1, y1) != (0, 0) and (x2, y2) != (0, 0):
            break
    if r.random() < 0.5:
        ans = x1 * x2 + y1 * y2
        return {"text": "Даны векторы a(%d; %d) и b(%d; %d). Найдите скалярное произведение a · b." % (x1, y1, x2, y2),
                "answer": str(ans), "explain": "a · b = %d · %d + %d · %d = %d." % (x1, x2, y1, y2, ans)}
    a, b, c = r.choice(_TRIPLES[:5])
    sx, sy = r.choice([1, -1]), r.choice([1, -1])
    ux, uy = sx * a - x2, sy * b - y2
    return {"text": "Даны векторы a(%d; %d) и b(%d; %d). Найдите длину вектора a + b." % (ux, uy, x2, y2),
            "answer": str(c), "explain": "a + b = (%d; %d), |a + b| = √(%d² + %d²) = %d." % (sx * a, sy * b, a, b, c)}


def p3(r):
    kind = r.choice(["cube", "box", "cyl"])
    if kind == "cube":
        k = r.randint(2, 5)
        return {"text": "Во сколько раз увеличится объём куба, если все его рёбра увеличить в %d раза?" % k
                if k < 5 else "Во сколько раз увеличится объём куба, если все его рёбра увеличить в %d раз?" % k,
                "answer": str(k ** 3), "explain": "Объём пропорционален кубу ребра: %d³ = %d." % (k, k ** 3)}
    if kind == "box":
        a, b, c = r.randint(2, 12), r.randint(2, 12), r.randint(2, 12)
        return {"text": "Найдите площадь поверхности прямоугольного параллелепипеда с рёбрами %d, %d и %d." % (a, b, c),
                "answer": str(2 * (a * b + b * c + a * c)),
                "explain": "S = 2(ab + bc + ac) = 2(%d + %d + %d) = %d." % (a * b, b * c, a * c, 2 * (a * b + b * c + a * c))}
    v, k = r.randint(2, 30), r.choice([2, 3, 4])
    return {"text": "Объём цилиндра равен %d. Радиус основания увеличили в %d раза, высоту оставили прежней. Найдите объём "
                    "нового цилиндра." % (v, k), "answer": str(v * k * k),
            "explain": "V = πr²h — объём растёт как квадрат радиуса: %d · %d² = %d." % (v, k, v * k * k)}


def p4(r):
    return o10(r)


def p5(r):
    kind = r.choice(["shots", "two"])
    if kind == "shots":
        p = F(r.choice([6, 7, 8, 9]), 10)
        hit, miss = r.randint(1, 3), r.randint(1, 2)
        ans = p ** hit * (1 - p) ** miss
        return {"text": "Биатлонист %d раз стреляет по мишеням. Вероятность попадания при одном выстреле равна %s. Найдите "
                        "вероятность того, что биатлонист первые %d раз попал в мишени, а последние %d промахнулся."
                        % (hit + miss, fmt(p), hit, miss), "answer": fmt(ans),
                "explain": "Выстрелы независимы: %s^%d · %s^%d = %s." % (fmt(p), hit, fmt(1 - p), miss, fmt(ans))}
    p, q = F(r.randint(1, 9), 10), F(r.randint(1, 9), 10)
    ans = 1 - (1 - p) * (1 - q)
    return {"text": "В магазине два независимо работающих платёжных терминала. Вероятность того, что терминал неисправен, "
                    "равна %s для первого и %s для второго. Найдите вероятность того, что хотя бы один терминал исправен."
                    % (fmt(1 - p), fmt(1 - q)), "answer": fmt(ans),
            "explain": "Противоположное событие — оба неисправны: %s · %s. Ответ: 1 − %s = %s." % (
                fmt(1 - p), fmt(1 - q), fmt((1 - p) * (1 - q)), fmt(ans))}


def p6(r):
    kind = r.choice(["log", "exp", "root"])
    if kind == "log":
        base, b, a = r.choice([2, 3, 5]), r.randint(1, 4), r.randint(-9, 9)
        while base ** b > 130:
            b -= 1
        x = base ** b - a
        return {"text": "Найдите корень уравнения **log%s(x%s) = %d**." % (_sub(base), _signed(a, ""), b),
                "answer": str(x), "explain": "x%s = %d^%d = %d, x = %d." % (_signed(a, ""), base, b, base ** b, x)}
    if kind == "exp":
        base, b, a = r.choice([2, 3, 5]), r.randint(1, 4), r.choice([i for i in range(-9, 10) if i])
        return {"text": "Найдите корень уравнения **%d^(x%s) = %d**." % (base, _signed(-a, ""), base ** b),
                "answer": str(a + b), "explain": "%d = %d^%d, значит x − %d = %d, x = %d." % (base ** b, base, b, a, b, a + b)
                if a >= 0 else "%d = %d^%d, значит x + %d = %d, x = %d." % (base ** b, base, b, -a, b, a + b)}
    b, a = r.randint(2, 12), r.randint(-20, 20)
    return {"text": "Найдите корень уравнения **√(x%s) = %d**." % (_signed(a, ""), b), "answer": str(b * b - a),
            "explain": "x%s = %d² = %d, x = %d." % (_signed(a, ""), b, b * b, b * b - a)}


def _sub(n):
    return "".join("₀₁₂₃₄₅₆₇₈₉"[int(c)] for c in str(n))


def p7(r):
    kind = r.choice(["log", "pow"])
    if kind == "log":
        a = r.choice([2, 3, 5, 7])
        m, n = r.randint(2, 6), r.randint(2, 5)
        ans = m * n
        return {"text": "Найдите значение выражения **%d · log%s(%d^%d)**." % (n, _sub(a), a, m),
                "answer": str(m * n), "explain": "log%s(%d^%d) = %d, %d · %d = %d." % (_sub(a), a, m, m, n, m, ans)}
    a = r.choice([2, 3, 5])
    x, y = r.randint(2, 9), r.randint(2, 9)
    while not 0 <= 2 * x - y <= 6:
        x, y = r.randint(2, 9), r.randint(2, 9)
    return {"text": "Найдите значение выражения **(%d^%d)² : %d^%d**." % (a, x, a, y), "answer": str(a ** (2 * x - y)),
            "explain": "(%d^%d)² = %d^%d, %d^%d : %d^%d = %d^%d = %d." % (a, x, a, 2 * x, a, 2 * x, a, y, a, 2 * x - y,
                                                                       a ** (2 * x - y))}


def p9(r):
    while True:
        t1, t2 = r.randint(1, 3), r.randint(2, 8)
        if t2 > t1:
            break
    v, h = 5 * (t1 + t2), 5 * t1 * t2
    return {"text": "Камень брошен вертикально вверх. Пока он не упал, высота, на которой он находится, описывается "
                    "формулой **h(t) = %dt − 5t²**, где h — высота в метрах, t — время в секундах с момента броска. "
                    "Сколько секунд камень находился на высоте не менее %d метров?" % (v, h),
            "answer": str(t2 - t1),
            "explain": "%dt − 5t² ≥ %d ⇔ t² − %dt + %d ≤ 0 ⇔ %d ≤ t ≤ %d. Длительность %d с." % (
                v, h, t1 + t2, t1 * t2, t1, t2, t2 - t1)}


def p10(r):
    if r.random() < 0.5:
        while True:
            b, x = r.randint(4, 40), r.randint(6, 60)          # вместе за b минут, вторая — за x
            if x > b and (b * x) % (x - b) == 0:
                a = b * x // (x - b)
                if a != x and a <= 120:
                    break
        return {"text": "Первая труба наполняет бак за %d минут, а обе трубы вместе — за %d минут. За сколько минут "
                        "наполняет этот бак одна вторая труба?" % (a, b), "answer": str(x),
                "explain": "Производительность второй: 1/%d − 1/%d = 1/%d. Значит, %d минут." % (b, a, x, x)}
    while True:
        v, c = r.randint(8, 30), r.randint(1, 5)
        s = r.choice([16, 24, 30, 36, 40, 45, 48, 60, 72, 80, 90])
        dt = F(s, v - c) - F(s, v + c)
        if v > c and dt.denominator == 1 and dt > 0:
            break
    return {"text": "Лодка прошла %d км против течения реки и вернулась обратно, затратив на путь против течения на %d ч "
                    "больше, чем на обратный путь. Скорость течения %d км/ч. Найдите собственную скорость лодки в км/ч."
                    % (s, int(dt), c), "answer": str(v),
            "explain": "%d/(v − %d) − %d/(v + %d) = %d. Подходит v = %d: %s − %s = %d." % (
                s, c, s, c, int(dt), v, fmt(F(s, v - c)) if finite(F(s, v - c)) else _frac(F(s, v - c)),
                fmt(F(s, v + c)) if finite(F(s, v + c)) else _frac(F(s, v + c)), int(dt))}


def p12(r):
    while True:
        p, q = r.randint(-6, 6), r.randint(-6, 6)
        if p < q and (p + q) % 2 == 0:
            break
    b, c, d = -3 * (p + q) // 2, 3 * p * q, r.randint(-20, 20)
    want = r.choice(["минимума", "максимума"])
    poly = "x³%s%s%s" % (_signed(b, "x²"), _signed(c, "x"), _signed(d, ""))
    return {"text": "Найдите точку %s функции **y = %s**." % (want, poly), "answer": str(q if want == "минимума" else p),
            "explain": "y′ = 3x²%s%s = 3(x − %d)(x − %d). Производная меняет знак с «+» на «−» в точке %d (максимум) и с "
                       "«−» на «+» в точке %d (минимум)." % (_signed(2 * b, "x"), _signed(c, ""), p, q, p, q)}


def _minus(t):
    """Отрицательные числа в условии и разборе: «3 − -5» → «3 + 5», «2 · -5» → «2 · (−5)», «-4» → «−4»."""
    t = re.sub(r"− -(?=\d)", "+ ", t)
    t = re.sub(r"\+ -(?=\d)", "− ", t)
    t = re.sub(r"([·:]) -([\d,]+)", r"\1 (−\2)", t)
    return re.sub(r"(?<!\w)-(?=\d)", "−", t)


class Bank:
    """Генераторы одного экзамена: make / public / check, как у oge_gen."""

    def __init__(self, prefix, gens, titles):
        self.prefix, self.GENERATORS, self.TITLES = prefix, gens, titles

    def make(self, num, seed):
        v = self.GENERATORS[num](random.Random("%s-%d-%d" % (self.prefix, num, seed)))
        v.update({"num": num, "seed": seed, "text": _minus(v["text"]), "explain": _minus(v["explain"])})
        return v

    @staticmethod
    def public(v):
        return {k: v[k] for k in ("num", "seed", "text", "table", "code") if k in v}

    @staticmethod
    def check(v, given):
        a = _num(given)
        if a is None:
            return False
        if "accept" in v:                     # верных ответов несколько — проверяем условие, а не эталон
            return _accepts(v["accept"], a)
        return a == _num(v["answer"])


def _accepts(rule, a):
    if rule["kind"] == "digits":              # трёхзначное, кратное k, сумма цифр s
        if a.denominator != 1 or not 100 <= a <= 999:
            return False
        x = int(a)
        return x % rule["k"] == 0 and sum(map(int, str(x))) == rule["s"]
    raise ValueError(rule["kind"])


# ================================================================== ЕГЭ, базовый уровень
def b15(r):
    kind = r.choice(["up", "down", "find"])
    price = r.choice(range(200, 5001, 50))
    p = r.choice([5, 10, 15, 20, 25, 30, 40, 50])
    if kind == "up":
        new = F(price) * (100 + p) / 100
        return {"text": "Тетрадь в магазине стоила %d руб. В сентябре цена выросла на %d%%. Сколько рублей стала стоить "
                        "тетрадь после повышения цены?" % (price, p), "answer": fmt(new),
                "explain": "%d · (1 + %d/100) = %d · %s = %s." % (price, p, price, fmt(F(100 + p, 100)), fmt(new))}
    if kind == "down":
        new = F(price) * (100 - p) / 100
        return {"text": "Куртка стоила %d руб. На распродаже цену снизили на %d%%. Сколько рублей стала стоить куртка?"
                        % (price, p), "answer": fmt(new),
                "explain": "%d · (1 − %d/100) = %d · %s = %s." % (price, p, price, fmt(F(100 - p, 100)), fmt(new))}
    new = F(price) * (100 - p) / 100
    return {"text": "Футболка стоила %d руб. После снижения цены она стала стоить %s руб. На сколько процентов была "
                    "снижена цена футболки?" % (price, fmt(new)), "answer": str(p),
            "explain": "Снижение %s руб.; %s : %d · 100%% = %d%%." % (fmt(price - new), fmt(price - new), price, p)}


def b19(r):
    while True:
        k, s = r.choice([3, 4, 5, 6, 9, 11, 12, 15, 25]), r.randint(5, 24)
        ok = [x for x in range(100, 1000) if x % k == 0 and sum(map(int, str(x))) == s]
        if ok:
            break
    return {"text": "Приведите пример трёхзначного натурального числа, которое делится на %d и сумма цифр которого "
                    "равна %d. В ответе укажите какое-нибудь одно такое число." % (k, s),
            "answer": str(ok[0]), "accept": {"kind": "digits", "k": k, "s": s},
            "explain": "Подходит, например, %d: %d : %d = %d, сумма цифр %s = %d. Всего таких чисел — %d."
                       % (ok[0], ok[0], k, ok[0] // k, " + ".join(str(ok[0])), s, len(ok))}


def b20(r):
    return o14(r) if r.random() < 0.5 else p10(r)


OGE = Bank("oge-math", {6: o6, 7: o7, 8: o8, 9: o9, 10: o10, 12: o12, 13: o13, 14: o14, 15: o15, 16: o16, 17: o17,
                        19: o19},
           {6: "Действия с дробями", 7: "Числа и координатная прямая", 8: "Степени и корни", 9: "Уравнения",
            10: "Вероятность", 11: "Графики функций", 12: "Расчёты по формулам", 13: "Неравенства",
            14: "Прогрессии в задачах", 15: "Треугольники", 16: "Окружность", 17: "Площади фигур",
            18: "Фигуры на клетчатой бумаге", 19: "Верные утверждения"})
EGE_PROFILE = Bank("ege-math-profile", {1: p1, 2: p2, 3: p3, 4: p4, 5: p5, 6: p6, 7: p7, 9: p9, 10: p10, 12: p12},
                   {1: "Планиметрия", 2: "Векторы", 3: "Стереометрия", 4: "Простая вероятность",
                    5: "Вероятности сложных событий", 6: "Простейшие уравнения", 7: "Вычисления и преобразования",
                    8: "Производная и первообразная", 9: "Задача с прикладным содержанием", 10: "Текстовая задача",
                    11: "Графики функций", 12: "Наибольшее и наименьшее значение функции"})


def b17(r):
    return p6(r) if r.random() < 0.5 else o9(r)


def b_geo(r):
    return r.choice([o15, o16, o17])(r)


# названия номеров базового уровня — в модели экзамена (спецификация ФИПИ 2026)
EGE_BASE = Bank("ege-math-base", {1: o6, 4: o12, 5: o10, 10: b_geo, 11: p3, 12: b_geo, 13: p3, 14: o6, 15: b15, 16: o8,
                                  17: b17, 19: b19, 20: b20}, {})
