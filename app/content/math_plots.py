"""Свои варианты ОГЭ по математике с рисунками: №1–5 (один сюжет на пять вопросов), №11, №18.

Сюжеты авторские: дачный участок, квартира-«вагон», тарифы «Берёзка» и «Сосна», веломастерская.
Числа случайные, ответ считается по ним заново. Рисунки — SVG без скриптов.
"""


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _svg(inner, w, h, label):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" role="img" aria-label="%s">%s</svg>'
            % (w, h, _esc(label), inner))


def _pack(text, answer, explain, steps, data, svg=None, table=None):
    v = {"text": text, "answer": str(answer), "explain": explain, "steps": steps, "data": data}
    if svg:
        v["svg"] = svg
    if table:
        v["table"] = table
    return v


# ================================================================== №1–5, четыре сюжета
def story(seed):
    import random
    r = random.Random("oge-math-story-%s" % seed)
    return r.choice([_plot, _flat, _tariff, _bike])(r)


def _plot(r):
    L, W = r.choice(range(20, 41, 2)), r.choice(range(14, 27, 2))
    hx, hy = r.choice(range(4, max(6, L // 3), 2)), r.choice(range(4, max(6, W // 3), 2))
    bx = r.randint(2, max(2, L - hx - 2))
    by = r.randint(2, max(2, W - hy - 2))
    price = r.choice([120, 150, 180, 200, 250])
    area, house, bed = L * W, hx * hy, bx * by
    lawn, peri = area - house - bed, 2 * (L + W)
    # план: дом в левом нижнем углу, грядка в правом верхнем, между ними зазор
    sc = 8
    pad = 28
    pw, ph = L * sc + pad * 2, W * sc + pad * 2

    def box(x, y, w, h, fill):
        return '<rect x="%d" y="%d" width="%d" height="%d" fill="%s" stroke="#14112A" stroke-width="1.5"/>' % (
            pad + x * sc, pad + (W - y - h) * sc, w * sc, h * sc, fill)

    svg = _svg(
        '<rect x="1" y="1" width="%d" height="%d" fill="#F4F2FF"/>' % (pw - 2, ph - 2)
        + box(0, 0, L, W, "#E7F6D8")
        + box(0, 0, hx, hy, "#D9C7FF")
        + box(L - bx, W - by, bx, by, "#C6FF1A")
        + '<text x="%d" y="18" font-size="13" fill="#14112A">%d м</text>' % (pw // 2, L)
        + '<text x="6" y="%d" font-size="13" fill="#14112A">%d м</text>' % (ph // 2, W),
        pw, ph, "План участка: дом, грядка и газон")
    intro = ("Прямоугольный участок у реки: длина %d м, ширина %d м. В левом нижнем углу стоит дом %d×%d м, "
             "в правом верхнем — грядка %d×%d м (они не пересекаются). Остальное — газон. Метр забора стоит %d руб."
             % (L, W, hx, hy, bx, by, price))
    raw = {"kind": "plot", "L": L, "W": W, "hx": hx, "hy": hy, "bx": bx, "by": by, "price": price}
    qs = {
        1: (area, "Найди площадь всего участка в квадратных метрах.",
            "%d · %d = %d." % (L, W, area),
            ["Площадь прямоугольника — длина на ширину.", "S = %d · %d = %d." % (L, W, area)]),
        2: (peri, "Сколько метров забора нужно, чтобы огородить участок по периметру?",
            "2 · (%d + %d) = %d." % (L, W, peri),
            ["Периметр прямоугольника — сумма всех сторон, их две пары.", "P = 2 · (%d + %d) = %d." % (L, W, peri)]),
        3: (house, "Найди площадь дома в квадратных метрах.",
            "%d · %d = %d." % (hx, hy, house),
            ["Дом тоже прямоугольник.", "S = %d · %d = %d." % (hx, hy, house)]),
        4: (lawn, "Найди площадь газона в квадратных метрах.",
            "%d − %d − %d = %d." % (area, house, bed, lawn),
            ["Из площади участка вычти дом и грядку.", "%d − %d − %d = %d." % (area, house, bed, lawn)]),
        5: (peri * price, "Сколько рублей стоит забор вокруг всего участка?",
            "%d · %d = %d." % (peri, price, peri * price),
            ["Сначала периметр, потом умножь на цену метра.", "P = %d м, стоимость %d · %d = %d." % (peri, peri, price, peri * price)]),
    }
    return {"intro": intro, "svg": svg, "raw": raw, "qs": qs, "table": None}


def _flat(r):
    depth = r.choice([3, 4, 5, 6])
    kitchen = r.choice([2, 3, 4])
    room = kitchen + r.choice([1, 2, 3])
    bed = r.choice([3, 4, 5])
    price = r.choice([450, 500, 600, 700, 800])
    total = kitchen + room + bed
    raw = {"kind": "flat", "depth": depth, "kitchen": kitchen, "room": room, "bed": bed, "price": price}
    sc, pad = 28, 36
    pw, ph = total * sc + pad * 2, depth * sc + 70

    def room_box(x, w, fill, name):
        return ('<rect x="%d" y="28" width="%d" height="%d" fill="%s" stroke="#14112A" stroke-width="1.5"/>'
                '<text x="%d" y="%d" font-size="12" fill="#14112A">%s</text>'
                % (pad + x * sc, w * sc, depth * sc, fill, pad + x * sc + 6, 28 + depth * sc // 2, _esc(name)))

    svg = _svg(
        '<rect width="%d" height="%d" fill="#F4F2FF"/>' % (pw, ph)
        + room_box(0, kitchen, "#FFE0C2", "кухня")
        + room_box(kitchen, room, "#E4DBFF", "комната")
        + room_box(kitchen + room, bed, "#D7F7C8", "спальня")
        + '<text x="%d" y="%d" font-size="13" fill="#14112A">глубина %d м</text>' % (8, ph - 10, depth),
        pw, ph, "План квартиры из трёх комнат в ряд")
    intro = ("Квартира-«вагон»: три комнаты в ряд, глубина у всех %d м. Ширина кухни %d м, комнаты %d м, "
             "спальни %d м. Ламинат стоит %d руб. за квадратный метр."
             % (depth, kitchen, room, bed, price))
    ka, ra, ba, ta = kitchen * depth, room * depth, bed * depth, total * depth
    qs = {
        1: (ka, "Найди площадь кухни в квадратных метрах.", "%d · %d = %d." % (kitchen, depth, ka),
            ["Площадь комнаты — ширина на глубину.", "%d · %d = %d." % (kitchen, depth, ka)]),
        2: (ba, "Найди площадь спальни в квадратных метрах.", "%d · %d = %d." % (bed, depth, ba),
            ["У спальни та же глубина.", "%d · %d = %d." % (bed, depth, ba)]),
        3: (ta, "Найди площадь всей квартиры в квадратных метрах.", "%d · %d = %d." % (total, depth, ta),
            ["Сложи ширины и умножь на глубину.", "(%d + %d + %d) · %d = %d." % (kitchen, room, bed, depth, ta)]),
        4: (ra - ka, "На сколько квадратных метров комната больше кухни?",
            "%d − %d = %d." % (ra, ka, ra - ka),
            ["Вычти площадь кухни из площади комнаты.", "%d − %d = %d." % (ra, ka, ra - ka)]),
        5: (ta * price, "Сколько рублей стоит ламинат на всю квартиру?",
            "%d · %d = %d." % (ta, price, ta * price),
            ["Площадь всей квартиры умножь на цену метра.", "%d · %d = %d." % (ta, price, ta * price)]),
    }
    return {"intro": intro, "svg": svg, "raw": raw, "qs": qs, "table": None}


def _tariff(r):
    t = r.choice([10, 12, 15, 20, 24, 30, 40])          # с этого числа ГБ «Сосна» дешевле, строго после t
    step = r.choice([2, 4, 5])
    a_fee = r.choice([180, 200, 240, 300])
    b_gb = r.choice([3, 4, 5, 6])
    a_gb = b_gb + step
    b_fee = a_fee + t * step
    n = r.choice([x for x in (5, 8, 16, 25, 36, 48, 50) if x != t])
    names = ("Берёзка", "Сосна")
    cost = lambda fee, gb: fee + gb * n
    ca, cb = cost(a_fee, a_gb), cost(b_fee, b_gb)
    raw = {"kind": "tariff", "t": t, "a_fee": a_fee, "a_gb": a_gb, "b_fee": b_fee, "b_gb": b_gb, "n": n}
    table = [["Тариф", "Плата в месяц, руб.", "Цена 1 ГБ сверх 0, руб."],
             [names[0], str(a_fee), str(a_gb)], [names[1], str(b_fee), str(b_gb)]]
    intro = ("Два тарифа домашнего интернета. Плата за месяц плюс цена каждого гигабайта. В этом месяце "
             "нужно %d ГБ." % n)
    diff = abs(ca - cb)
    year = min(ca, cb) * 12
    qs = {
        1: (ca, "Сколько рублей стоит месяц на тарифе «Берёзка» при %d ГБ?" % n,
            "%d + %d · %d = %d." % (a_fee, a_gb, n, ca),
            ["Сложи абонентскую плату и плату за гигабайты.", "%d + %d · %d = %d." % (a_fee, a_gb, n, ca)]),
        2: (cb, "Сколько рублей стоит месяц на тарифе «Сосна» при %d ГБ?" % n,
            "%d + %d · %d = %d." % (b_fee, b_gb, n, cb),
            ["Та же схема для второго тарифа.", "%d + %d · %d = %d." % (b_fee, b_gb, n, cb)]),
        3: (diff, "На сколько рублей один тариф дешевле другого при %d ГБ?" % n,
            "|%d − %d| = %d." % (ca, cb, diff),
            ["Посчитай оба тарифа и вычти меньший из большего.", "|%d − %d| = %d." % (ca, cb, diff)]),
        4: (t + 1, "Начиная с какого числа гигабайт тариф «Сосна» становится строго дешевле «Берёзки»?",
            "Разница плат %d руб., каждый гигабайт экономит %d руб. Порог %d, строго дешевле с %d."
            % (b_fee - a_fee, step, t, t + 1),
            ["«Сосна» дороже на старте, но дешевле за каждый гигабайт.",
             "Она догоняет «Берёзку» при %d ГБ и становится дешевле со следующего: %d." % (t, t + 1)]),
        5: (year, "Сколько рублей стоят 12 месяцев на более дешёвом из двух тарифов при %d ГБ каждый месяц?" % n,
            "min(%d, %d) · 12 = %d." % (ca, cb, year),
            ["Возьми меньшую месячную цену и умножь на 12.", "%d · 12 = %d." % (min(ca, cb), year)]),
    }
    return {"intro": intro, "svg": None, "raw": raw, "qs": qs, "table": table}


def _bike(r):
    d = r.choice([40, 46, 50, 54, 60, 66])
    t = r.choice([2, 3, 4, 5])
    d2 = r.choice([x for x in (40, 50, 60, 70) if x != d])
    t2 = r.choice([2, 3, 4, 5])
    price = r.choice([350, 420, 480, 560, 640])
    stock = r.choice([6, 8, 10, 12, 16])
    outer, outer2 = d + 2 * t, d2 + 2 * t2
    raw = {"kind": "bike", "d": d, "t": t, "d2": d2, "t2": t2, "price": price, "stock": stock}

    def wheel(cx, diam, label):
        rad = 28 + diam // 8
        return ('<circle cx="%d" cy="78" r="%d" fill="none" stroke="#14112A" stroke-width="6"/>'
                '<circle cx="%d" cy="78" r="%d" fill="none" stroke="#7B2FF7" stroke-width="3"/>'
                '<text x="%d" y="150" font-size="12" text-anchor="middle" fill="#14112A">%s</text>'
                % (cx, rad, cx, max(8, rad - 10), cx, _esc(label)))

    svg = _svg('<rect width="320" height="168" fill="#F4F2FF"/>' + wheel(90, d, "обод %d см" % d)
               + wheel(230, d2, "обод %d см" % d2), 320, 168, "Два колеса: обод и покрышка")
    intro = ("В веломастерской «Спица» покрышка надевается на обод. У первого колеса диаметр обода %d см, "
             "толщина покрышки %d см. У второго обод %d см и покрышка %d см. Одна покрышка стоит %d руб., "
             "на складе %d покрышек." % (d, t, d2, t2, price, stock))
    qs = {
        1: (outer, "Найди внешний диаметр первого колеса в сантиметрах.",
            "%d + 2 · %d = %d." % (d, t, outer),
            ["Покрышка добавляет толщину с двух сторон.", "%d + 2 · %d = %d." % (d, t, outer)]),
        2: (2 * t, "На сколько сантиметров внешний диаметр первого колеса больше диаметра его обода?",
            "2 · %d = %d." % (t, 2 * t),
            ["Прибавка — две толщины покрышки.", "2 · %d = %d." % (t, 2 * t)]),
        3: (abs(outer - outer2), "На сколько сантиметров отличаются внешние диаметры двух колёс?",
            "|%d − %d| = %d." % (outer, outer2, abs(outer - outer2)),
            ["Посчитай оба внешних диаметра и вычти.", "|%d − %d| = %d." % (outer, outer2, abs(outer - outer2))]),
        4: (price * 2, "Сколько рублей стоят две покрышки?",
            "2 · %d = %d." % (price, price * 2),
            ["Цена одной покрышки умножь на два.", "2 · %d = %d." % (price, price * 2)]),
        5: (stock // 2, "На сколько велосипедов (по две покрышки) хватит склада?",
            "%d : 2 = %d." % (stock, stock // 2),
            ["Раздели число покрышек на 2.", "%d : 2 = %d." % (stock, stock // 2)]),
    }
    return {"intro": intro, "svg": svg, "raw": raw, "qs": qs, "table": None}


def question(seed, num):
    st = story(seed)
    ans, ask, expl, steps = st["qs"][num]
    data = dict(st["raw"], q=num)
    text = st["intro"] + "\n\n" + ask
    return _pack(text, ans, expl, steps, data, svg=st["svg"], table=st["table"])


def o1(r, seed):
    return question(seed, 1)


def o2(r, seed):
    return question(seed, 2)


def o3(r, seed):
    return question(seed, 3)


def o4(r, seed):
    return question(seed, 4)


def o5(r, seed):
    return question(seed, 5)


for _fn in (o1, o2, o3, o4, o5):
    _fn.wants_seed = True


# ================================================================== №11 графики
def _map(x, y, x0, y0, s, ymin, ymax):
    # x в [-4, 4], y в [ymin, ymax] → пиксели
    px = x0 + (x + 4) / 8 * s
    py = y0 + (ymax - y) / (ymax - ymin) * s
    return px, py


def _poly(samples, x0, y0, s, ymin, ymax):
    pts = []
    for x, y in samples:
        if y is None or y < ymin or y > ymax:
            if pts:
                pts.append(None)
            continue
        px, py = _map(x, y, x0, y0, s, ymin, ymax)
        pts.append((px, py))
    out = ""
    chunk = []
    for p in pts + [None]:
        if p is None:
            if len(chunk) >= 2:
                out += '<polyline fill="none" stroke="#7B2FF7" stroke-width="2" points="%s"/>' % " ".join(
                    "%.1f,%.1f" % q for q in chunk)
            chunk = []
        else:
            chunk.append(p)
    return out


def _samples(kind, params):
    pts = []
    if kind == "line":
        k, b = params
        for i in range(17):
            x = -4 + i * 0.5
            pts.append((x, k * x + b))
    elif kind == "para":
        a = params[0]
        for i in range(17):
            x = -4 + i * 0.5
            pts.append((x, a * x * x))
    else:
        k = params[0]
        for i in range(17):
            x = -4 + i * 0.5
            pts.append((x, None if x == 0 else k / x))
    return pts


def _formula(kind, params):
    if kind == "line":
        k, b = params
        body = "x" if k == 1 else ("−x" if k == -1 else "%dx" % k if k > 0 else "−%dx" % -k)
        if b:
            body += " + %d" % b if b > 0 else " − %d" % -b
        return "y = " + body
    if kind == "para":
        a = params[0]
        return "y = x²" if a == 1 else ("y = −x²" if a == -1 else "y = %dx²" % a)
    k = params[0]
    return "y = %d/x" % k if k > 0 else "y = −%d/x" % -k


def o11(r):
    specs = [("line", (r.choice([1, 2, -1, -2]), r.choice([-2, -1, 1, 2]))),
             ("para", (r.choice([1, -1]),)),
             ("hyp", (r.choice([2, 4, -2, -4]),))]
    order = [0, 1, 2]
    r.shuffle(order)                                  # порядок графиков на рисунке
    letters = "АБВ"
    ymin, ymax = -6, 6
    s, gap = 108, 16
    w, h = 3 * s + 4 * gap, s + 36
    parts = ['<rect width="%d" height="%d" fill="#F4F2FF"/>' % (w, h)]
    for i, idx in enumerate(order):
        x0, y0 = gap + i * (s + gap), 8
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#fff" stroke="#E4E2F0"/>' % (x0, y0, s, s))
        # оси
        ax, ay = _map(0, 0, x0, y0, s, ymin, ymax)
        parts.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#14112A" stroke-width="1"/>' % (x0, ay, x0 + s, ay))
        parts.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#14112A" stroke-width="1"/>' % (ax, y0, ax, y0 + s))
        parts.append(_poly(_samples(*specs[idx]), x0, y0, s, ymin, ymax))
        parts.append('<text x="%d" y="%d" font-size="13" font-weight="700" fill="#14112A">%d</text>' % (
            x0 + s / 2 - 4, h - 6, i + 1))
    lines = []
    digits = []
    for j, idx in enumerate(range(3)):
        graph = order.index(idx) + 1
        digits.append(str(graph))
        lines.append("%s) %s" % (letters[j], _formula(*specs[idx])))
    ans = "".join(digits)
    text = ("На рисунке три графика, они пронумерованы. Установи соответствие между формулой и графиком.\n\n%s\n\n"
            "В ответе запиши три цифры подряд: номер графика для А, для Б и для В." % "\n".join(lines))
    steps = ["Посмотри, прямая это, парабола или гипербола: у гиперболы две ветви и разрыв в нуле, у параболы — ветви "
             "от одной точки.",
             "Знак коэффициента говорит, куда смотрит график: плюс — вверх или вправо-вверх, минус — наоборот.",
             "Формулы: %s. Графики идут как %s, ответ %s." % (", ".join(lines), "".join(str(i + 1) for i in range(3)), ans)]
    return _pack(text, ans, "А — график %s, Б — %s, В — %s." % tuple(ans), steps,
                 {"kind": "graphs", "specs": [{"kind": k, "params": list(p)} for k, p in specs], "order": order},
                 svg=_svg("".join(parts), w, h, "Три графика функций"))


# ================================================================== №18 клетчатая бумага
def _shoelace(pts):
    s = 0
    for i, (x, y) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x * y2 - x2 * y
    return abs(s) / 2


def o18(r):
    kind = r.choice(["rect", "tri", "trap"])
    if kind == "rect":
        a, b = r.randint(2, 14), r.randint(2, 10)
        pts, area = [(0, 0), (a, 0), (a, b), (0, b)], a * b
        name = "прямоугольник"
    elif kind == "tri":
        a, b = r.choice(range(2, 16, 2)), r.randint(2, 12)
        pts, area = [(0, 0), (a, 0), (0, b)], a * b / 2
        name = "прямоугольный треугольник"
    else:
        h = r.choice([2, 4, 6])
        a = r.randint(2, 8)
        b = r.randint(a + 2, a + 10)
        pts, area = [(0, 0), (b, 0), (a, h), (0, h)], (a + b) * h / 2
        name = "трапеция"
    assert area == int(area) and area == _shoelace(pts)
    area = int(area)
    cell = 22
    m = 18
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w, h = (max(xs) + 2) * cell + m, (max(ys) + 2) * cell + m
    lines = []
    for i in range(max(xs) + 3):
        lines.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#D9D6EA" stroke-width="1"/>' % (
            m + i * cell, m, m + i * cell, m + (max(ys) + 2) * cell))
    for j in range(max(ys) + 3):
        lines.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#D9D6EA" stroke-width="1"/>' % (
            m, m + j * cell, m + (max(xs) + 2) * cell, m + j * cell))
    poly = " ".join("%d,%d" % (m + x * cell, m + (max(ys) - y) * cell) for x, y in pts)
    svg = _svg("".join(lines) + '<polygon points="%s" fill="#C6FF1A" fill-opacity="0.85" stroke="#14112A" stroke-width="2"/>' % poly,
               w, h, "Фигура на клетчатой бумаге, сторона клетки 1 см")
    verts = ", ".join("(%d; %d)" % p for p in pts)
    text = ("На клетчатой бумаге со стороной клетки 1 см нарисован %s. Вершины стоят в узлах сетки: %s. "
            "Найди площадь. Ответ дай в квадратных сантиметрах." % (name, verts))
    steps = ["Считай клетки по основанию и высоте. У прямоугольного треугольника площадь — половина произведения катетов, "
             "у трапеции — полусумма оснований на высоту.",
             "Основания и высота читаются по клеткам.",
             "Площадь равна %d." % area]
    return _pack(text, area, "Площадь %s равна %d." % (name, area), steps,
                 {"kind": "grid", "shape": kind, "pts": [list(p) for p in pts]})

