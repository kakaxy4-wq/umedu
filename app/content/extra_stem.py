"""Расчётные и короткие задания по физике, информатике, биологии и географии.

Числа подбираются так, чтобы ответ был целым. data хранит исходные величины.
"""
import math


def _out(text, answer, explain, steps, data):
    return {"text": text, "answer": str(answer), "explain": explain, "steps": steps, "data": data}


def _digits_change(pairs):
    """pairs: список (вопрос, код 1/2/3)."""
    return "".join(code for _, code in pairs)


# ------------------------------------------------------------------ физика: направления величин
def _mech_analysis(r):
    items = [
        ("Силу тяги оставили прежней, а массу автомобиля увеличили. Что верно про ускорение?",
         "ускорение уменьшилось",
         ["ускорение выросло", "ускорение не зависит от массы", "скорость сразу стала равной силе"]),
        ("Массу оставили прежней, а силу тяги увеличили. Что верно про ускорение?",
         "ускорение увеличилось",
         ["ускорение уменьшилось", "ускорение не изменилось", "масса стала больше"]),
        ("На тело действует постоянная сила, масса не меняется. Что можно сказать об ускорении?",
         "ускорение не меняется",
         ["ускорение обязательно растёт", "ускорение обязательно падает", "сила равна нулю"]),
    ]
    prompt, right, wrongs = r.choice(items)
    opts = [right, *wrongs]
    r.shuffle(opts)
    ans = opts.index(right) + 1
    lines = "\n".join("%d) %s" % (i + 1, o) for i, o in enumerate(opts))
    text = "%s\n\n%s\n\nНомер верного варианта." % (prompt, lines)
    return _out(text, ans, "По второму закону Ньютона a = F/m. Верно: %s." % right,
                ["Сравни, что изменилось: сила или масса.", "Остаётся: %s." % right, "Номер %d." % ans],
                {"kind": "index", "options": opts, "right": right})


def _mech_change(r):
    cases = [
        ("массу увеличивают, сила тяги та же", "12",
         "Масса растёт. a = F/m, при той же силе ускорение меньше."),
        ("массу уменьшают, сила тяги та же", "21",
         "Масса падает. При той же силе ускорение растёт."),
        ("силу тяги увеличивают, масса та же", "11",
         "Сила больше, масса та же, поэтому ускорение больше."),
    ]
    what, ans, why = r.choice(cases)
    text = ("Автомобиль: %s. Как меняются масса и ускорение?\n\n"
            "1 — увеличивается, 2 — уменьшается, 3 — не изменяется.\n"
            "Две цифры подряд: сначала масса, потом ускорение." % what)
    return _out(text, ans, why,
                ["Сначала реши про массу.", "Потом про ускорение: a = F/m.", "Ответ %s." % ans],
                {"kind": "digits", "answer": ans})


def _series_change(r):
    up = r.choice([True, False])
    ans = "12" if up else "21"
    word = "увеличивают" if up else "уменьшают"
    why = ("Общее сопротивление %s, ток I = U/R меняется в обратную сторону."
           % ("растёт" if up else "падает"))
    text = ("Два резистора соединены последовательно, напряжение источника постоянно. Сопротивление одного резистора "
            "%s. Как меняются общее сопротивление и сила тока в цепи?\n\n"
            "1 — увеличивается, 2 — уменьшается, 3 — не изменяется.\n"
            "Две цифры: сначала общее сопротивление, потом сила тока." % word)
    return _out(text, ans, why,
                ["При последовательном соединении сопротивления складываются.", why, "Ответ %s." % ans],
                {"kind": "digits", "answer": ans})


def _gas_change(r):
    hot = r.choice([True, False])
    ans = "11" if hot else "22"
    word = "нагревают" if hot else "охлаждают"
    why = ("Температура %s. В жёстком сосуде давление идеального газа меняется так же."
           % ("растёт" if hot else "падает"))
    text = ("Идеальный газ %s в закрытом жёстком сосуде: объём не меняется. Как меняются температура и "
            "давление?\n\n1 — увеличивается, 2 — уменьшается, 3 — не изменяется.\n"
            "Две цифры: сначала температура, потом давление." % word)
    return _out(text, ans, why,
                ["Сосуд жёсткий, объём постоянен.", why, "Ответ %s." % ans],
                {"kind": "digits", "answer": ans})


def _gas_isobar(r):
    expand = r.choice([True, False])
    ans = "11" if expand else "22"
    word = "расширяется" if expand else "сжимается"
    why = ("При постоянном давлении объём и температура идеального газа меняются в одну сторону. Ответ %s." % ans)
    text = ("Идеальный газ %s при постоянном давлении. Как меняются объём и температура?\n\n"
            "1 — увеличивается, 2 — уменьшается, 3 — не изменяется.\n"
            "Две цифры: сначала объём, потом температура." % word)
    return _out(text, ans, why, ["Давление в условии постоянно.", why], {"kind": "digits", "answer": ans})


def _lens_change(r):
    away = r.choice([True, False])
    ans = "32" if away else "31"
    word = "отодвигают" if away else "придвигают ближе к фокусу, но оставляют дальше фокуса"
    why = ("Оптическая сила не зависит от предмета. Расстояние до изображения %s."
           % ("уменьшается" if away else "увеличивается"))
    text = ("Предмет %s от собирающей линзы. Фокусное расстояние не меняется, предмет дальше фокуса. "
            "Как меняются оптическая сила линзы и расстояние от линзы до действительного изображения?\n\n"
            "1 — увеличивается, 2 — уменьшается, 3 — не изменяется.\n"
            "Две цифры: сначала оптическая сила, потом расстояние до изображения." % word)
    return _out(text, ans, why, ["D = 1/F зависит только от линзы.", why, "Ответ %s." % ans],
                {"kind": "digits", "answer": ans})


def _nuclear_change(r):
    alpha = r.choice([True, False])
    if alpha:
        ans, why = "22", "α-частица уносит A = 4 и Z = 2, оба числа уменьшаются."
        name = "α-распад"
    else:
        ans, why = "21", "β-распад не меняет массовое число, зарядовое растёт на 1."
        name = "β-распад"
    text = ("Ядро испытало %s. Как изменились массовое число и зарядовое число?\n\n"
            "1 — увеличилось, 2 — уменьшилось, 3 — не изменилось.\n"
            "Две цифры: сначала массовое число, потом зарядовое." % name)
    return _out(text, ans, why, [why, "Ответ %s." % ans], {"kind": "digits", "answer": ans})


def _device(r):
    pairs = [("массу тела", "весы"), ("силу тока", "амперметр"), ("напряжение", "вольтметр"),
             ("температуру", "термометр"), ("промежуток времени", "секундомер")]
    what, right = r.choice(pairs)
    names = [p[1] for p in pairs]
    r.shuffle(names)
    ans = names.index(right) + 1
    lines = "\n".join("%d) %s" % (i + 1, n) for i, n in enumerate(names))
    text = ("Каким прибором измеряют %s?\n\n%s\n\nВ ответе номер варианта." % (what, lines))
    return _out(text, ans, "Нужен прибор «%s», это вариант %d." % (right, ans),
                ["Вспомни, что показывает каждый прибор.", "Подходит «%s»." % right, "Номер %d." % ans],
                {"kind": "index", "options": names, "right": right})


def _scale(r):
    step = r.choice([1, 2, 5])
    marks = r.randint(2, 9)
    ans = step * marks
    text = ("Цена деления шкалы %d единица. Стрелка стоит на %d делениях от нуля. Каково показание?"
            % (step, marks))
    return _out(text, ans, "Показание = цена деления · число делений = %d · %d = %d." % (step, marks, ans),
                ["Цена деления — сколько единиц в одном промежутке.", "%d · %d = %d." % (step, marks, ans)],
                {"kind": "scale", "step": step, "marks": marks})


def _plan_exp(r):
    right = "силу тока и напряжение"
    wrongs = ["массу и длину", "температуру и время", "объём и плотность"]
    opts = [right, *wrongs]
    r.shuffle(opts)
    ans = opts.index(right) + 1
    lines = "\n".join("%d) %s" % (i + 1, o) for i, o in enumerate(opts))
    text = ("Нужно найти сопротивление резистора, подключённого к источнику. Какие две величины достаточно измерить?\n\n"
            "%s\n\nНомер варианта." % lines)
    return _out(text, ans, "По закону Ома R = U/I. Это вариант %d." % ans,
                ["Сопротивление связано с током и напряжением.", "R = U/I.", "Вариант %d." % ans],
                {"kind": "index", "options": opts, "right": right})


def _qualitative(r):
    items = [
        ("Почему высоко в горах вода закипает при температуре ниже 100 °C?",
         "атмосферное давление меньше, чем у подножия",
         ["вода в горах химически другая", "в горах нет силы тяжести", "молекулы воды тяжелее"]),
        ("Почему зимой на морозе металлическая ручка кажется холоднее деревянной?",
         "металл лучше проводит тепло и быстрее забирает его у руки",
         ["у металла всегда отрицательная температура", "дерево нагрето внутри", "металл тяжелее, поэтому холоднее"]),
        ("Лодка плавает. Что можно сказать о силе Архимеда и весе лодки?",
         "они равны",
         ["сила Архимеда больше веса", "вес больше силы Архимеда", "сила Архимеда равна нулю"]),
    ]
    prompt, right, wrongs = r.choice(items)
    opts = [right, *wrongs]
    r.shuffle(opts)
    ans = opts.index(right) + 1
    lines = "\n".join("%d) %s" % (i + 1, o) for i, o in enumerate(opts))
    text = "%s\n\n%s\n\nНомер верного варианта." % (prompt, lines)
    return _out(text, ans, "Верно: %s." % right,
                ["Отбрось варианты, которые противоречат известному закону.", "Остаётся: %s." % right,
                 "Номер %d." % ans],
                {"kind": "index", "options": opts, "right": right})


def _ohm_num(r):
    u, res = r.choice([(6, 2), (12, 3), (12, 4), (18, 6), (24, 8), (9, 3)])
    ans = u // res
    text = ("На резистор сопротивлением %d Ом подано напряжение %d В. Какова сила тока в амперах?" % (res, u))
    return _out(text, ans, "I = U/R = %d/%d = %d А." % (u, res, ans),
                ["Закон Ома для участка цепи.", "%d разделить на %d." % (u, res)],
                {"kind": "ohm", "u": u, "r": res})


def _heat_num(r):
    c, m, dt = 500, r.choice([2, 4]), r.choice([5, 10])
    ans = c * m * dt
    text = ("Удельная теплоёмкость вещества %d Дж/(кг·°C), масса %d кг. На сколько джоулей возрастёт внутренняя "
            "энергия при нагреве на %d °C без изменения агрегатного состояния?" % (c, m, dt))
    return _out(text, ans, "Q = cmΔt = %d · %d · %d = %d Дж." % (c, m, dt, ans),
                ["Количество теплоты при нагреве — cmΔt.", "%d · %d · %d." % (c, m, dt)],
                {"kind": "heat", "c": c, "m": m, "dt": dt})


def _speed_num(r):
    s, t = r.choice([(100, 5), (150, 10), (240, 8), (90, 3), (120, 4)])
    ans = s // t
    text = ("Тело прошло %d м равномерно за %d с. Какова скорость в м/с?" % (s, t))
    return _out(text, ans, "v = s/t = %d/%d = %d м/с." % (s, t, ans),
                ["Равномерное движение: скорость — путь делить на время.", "%d / %d." % (s, t)],
                {"kind": "speed", "s": s, "t": t})


def _parallel_num(r):
    pairs = [(6, 3, 2), (12, 6, 4), (4, 4, 2), (12, 4, 3), (6, 6, 3)]
    a, b, ans = r.choice(pairs)
    text = ("Резисторы %d Ом и %d Ом соединены параллельно. Каково их общее сопротивление в омах?" % (a, b))
    return _out(text, ans, "1/R = 1/%d + 1/%d, R = %d Ом." % (a, b, ans),
                ["При параллельном соединении складывают обратные сопротивления.", "Получается %d Ом." % ans],
                {"kind": "parallel", "a": a, "b": b, "ans": ans})


def _weight(r):
    m = r.choice([2, 3, 5, 8])
    ans = m * 10
    text = ("Масса тела %d кг. Считай g = 10 Н/кг. Каков вес покоящегося тела в ньютонах?" % m)
    return _out(text, ans, "P = mg = %d · 10 = %d Н." % (m, ans),
                ["Вес покоящегося тела равен mg.", "%d · 10." % m],
                {"kind": "weight", "m": m})


def _text_phys(r):
    return r.choice([_ohm_num, _heat_num, _speed_num, _weight])(r)


# ------------------------------------------------------------------ информатика
def _graph(r):
    n = 4
    # список рёбер без петель и кратных
    possible = [(i, j) for i in range(n) for j in range(i + 1, n)]
    edges = r.sample(possible, r.randint(3, 5))
    v = r.randrange(n)
    deg = sum(1 for a, b in edges if a == v or b == v)
    names = "АБВГ"
    lines = ", ".join("%s—%s" % (names[a], names[b]) for a, b in edges)
    text = ("Неориентированный граф без кратных рёбер. Вершины А, Б, В, Г. Рёбра: %s. "
            "Какова степень вершины %s?" % (lines, names[v]))
    return _out(text, deg, "К вершине %s подходит %d ребра." % (names[v], deg),
                ["Степень — число рёбер, выходящих из вершины.", "У %s их %d." % (names[v], deg)],
                {"kind": "graph", "edges": edges, "v": v})


def _db(r):
    names = ["Аня", "Боря", "Вера", "Глеб", "Даша", "Егор"]
    rows = [(name, r.randint(3, 5), r.randint(3, 5)) for name in names]
    subj = r.choice([0, 1])
    need = r.choice([4, 5])
    ans = sum(1 for row in rows if row[1 + subj] >= need)
    label = "математике" if subj == 0 else "русскому"
    lines = "\n".join("%s — математика %d, русский %d" % row for row in rows)
    text = ("Таблица оценок.\n\n%s\n\nСколько учеников имеют по %s оценку не ниже %d?" % (lines, label, need))
    return _out(text, ans, "Таких строк %d." % ans,
                ["Смотри только столбец «%s»." % label, "Считай оценки ≥ %d." % need],
                {"kind": "db", "rows": rows, "subj": subj, "need": need})


def _prefix(r):
    # А=0, Б=10, В=11 — префиксный код. Длина сообщения из слова.
    word = "".join(r.choice("АБВ") for _ in range(r.randint(4, 7)))
    bits = {"А": 1, "Б": 2, "В": 2}
    ans = sum(bits[ch] for ch in word)
    text = ("Префиксный код: А — 0, Б — 10, В — 11. Сколько бит займёт слово %s?" % word)
    return _out(text, ans, "Длины букв: %s. Сумма %d." % ("+".join(str(bits[ch]) for ch in word), ans),
                ["Посчитай биты каждой буквы.", "Сложи их."],
                {"kind": "prefix", "word": word})


def _executor(r):
    b = r.choice([2, 3, 4])
    prog = r.choice(["1121", "1211", "211", "1112"])
    x = r.randint(1, 5)
    start = x
    for cmd in prog:
        x = x + 1 if cmd == "1" else x * b
    text = ("Исполнитель умеет: 1 — прибавь 1; 2 — умножь на %d. Программа %s выполняется над числом %d. "
            "Какое число получится?" % (b, prog, start))
    return _out(text, x, "По шагам получается %d." % x,
                ["Выполняй команды слева направо.", "1 — это +1, 2 — это ·%d." % b, "Результат %d." % x],
                {"kind": "exec", "b": b, "prog": prog, "start": start})


def _sheet(r):
    n = r.randint(6, 10)
    prices = [r.randint(10, 40) for _ in range(n)]
    limit = r.choice([15, 20, 25, 30])
    ans = sum(p for p in prices if p >= limit)
    text = ("В столбце цены: %s. Чему равна сумма тех цен, которые не меньше %d?"
            % (", ".join(map(str, prices)), limit))
    return _out(text, ans, "Подходящие числа в сумме дают %d." % ans,
                ["Оставь числа ≥ %d." % limit, "Сложи их."],
                {"kind": "sheet", "prices": prices, "limit": limit})


def _search(r):
    word = r.choice(["кот", "дом", "лес", "мир"])
    bag = [r.choice([word, "сад", "река", "мост", word, "луг"]) for _ in range(r.randint(8, 12))]
    ans = bag.count(word)
    text = ("Сколько раз слово «%s» встречается отдельным словом в строке: %s?"
            % (word, " ".join(bag)))
    return _out(text, ans, "Слово «%s» встречается %d раз." % (word, ans),
                ["Дели строку по пробелам.", "Считай точные совпадения."],
                {"kind": "search", "bag": bag, "word": word})


def _seq(r):
    nums = [r.randint(1, 40) for _ in range(r.randint(8, 12))]
    evens = [x for x in nums if x % 2 == 0]
    ans = max(evens) if evens else 0
    if not evens:
        nums[0] = 2
        ans = 2
    text = ("Дана последовательность: %s. Найди наибольшее чётное число в ней." % ", ".join(map(str, nums)))
    return _out(text, ans, "Наибольшее чётное — %d." % ans,
                ["Оставь чётные.", "Выбери максимум."],
                {"kind": "seq", "nums": nums})


def _path_sum(r):
    # сетка 2x2, из левого верхнего в правый нижний, только вправо и вниз, максимальная сумма
    a, b = r.randint(1, 9), r.randint(1, 9)
    c, d = r.randint(1, 9), r.randint(1, 9)
    # клетки:
    # a b
    # c d
    # пути: a-b-d и a-c-d
    ans = a + d + max(b, c)
    text = ("В таблице чисел\n\n%d %d\n%d %d\n\nнужно пройти из левой верхней клетки в правую нижнюю, двигаясь только "
            "вправо или вниз, и набрать наибольшую сумму. Какова эта сумма?" % (a, b, c, d))
    return _out(text, ans, "Два пути: через %d и через %d. Большая сумма %d." % (b, c, ans),
                ["Пути два: верхний ряд потом вниз или сначала вниз потом вправо.",
                 "Суммы %d и %d." % (a + b + d, a + c + d), "Большая — %d." % ans],
                {"kind": "grid", "a": a, "b": b, "c": c, "d": d})


def _game_win(n, moves=(1, 2)):
    win = [False] * (n + 1)
    for i in range(1, n + 1):
        win[i] = any(i >= m and not win[i - m] for m in moves)
    return win


def _game(r, ask):
    n = r.randint(4, 15)
    win = _game_win(n)
    if ask == "one":
        text = ("В куче %d камней. За ход можно взять 1 или 2 камня. Выигрывает взявший последний. "
                "Есть ли у игрока, который ходит первым, ход в заведомо выигрышную для него позицию? "
                "Ответь 1, если да, и 2, если нет." % n)
        # есть ли ход в проигрышную для соперника
        ans = 1 if win[n] else 2
        data = {"kind": "game-one", "n": n}
    elif ask == "strat":
        moves = r.choice([(1, 2), (1, 3), (2, 3)])
        limit = r.choice([10, 12, 15])
        win = _game_win(limit, moves)
        ans = next(i for i in range(1, limit + 1) if not win[i])
        text = ("Берут %d или %d камня, последний ход выигрывает. Какое наименьшее число камней от 1 до %d "
                "проигрышно для первого игрока, если второй не ошибается?" % (moves[0], moves[1], limit))
        data = {"kind": "game-strat", "moves": list(moves), "limit": limit}
        n = None
    else:
        text = ("Кучa из %d камней, ходы «взять 1» или «взять 2», побеждает взявший последний. "
                "Сколько камней нужно взять первым ходом, чтобы победить при точной игре соперника? "
                "Если победа невозможна, запиши 0." % n)
        win = _game_win(n)
        if not win[n]:
            ans = 0
        else:
            ans = next(m for m in (1, 2) if n >= m and not win[n - m])
        data = {"kind": "game-tree", "n": n}
    expl = "Проигрышные позиции — кратные 3: с них любой ход отдаёт сопернику победу."
    return _out(text, ans, expl, ["Позиция 0 — уже проигрыш того, кто должен ходить.", "Проигрышны числа, кратные 3.",
                                  "Ответ %s." % ans], data)


def _critical(r):
    a = r.randint(2, 6)
    b = r.randint(2, 6)
    c = r.randint(2, 6)
    d = r.randint(2, 6)
    ans = a + max(b, c) + d
    text = ("Четыре дела. А занимает %d ч и ни от чего не зависит. Б (%d ч) и В (%d ч) можно начать только после А, "
            "они идут независимо. Г (%d ч) начинается, когда закончены и Б, и В. За сколько часов закончится всё, "
            "если независимые дела идут одновременно?" % (a, b, c, d))
    return _out(text, ans, "Длинная ветка: %d + max(%d, %d) + %d = %d." % (a, b, c, d, ans),
                ["А обязательно первое.", "Б и В идут параллельно, ждём более долгое.", "Потом Г."],
                {"kind": "crit", "a": a, "b": b, "c": c, "d": d})


def _runs(r):
    letter = r.choice("ABC")
    parts = []
    longest = 0
    for _ in range(r.randint(4, 7)):
        ch = r.choice("ABC")
        k = r.randint(1, 4)
        parts.append(ch * k)
        if ch == letter:
            longest = max(longest, k)
    s = "".join(parts)
    # пересчитать честно
    best = cur = 0
    for ch in s:
        if ch == letter:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    text = ("В строке %s найди длину самой длинной непрерывной цепочки буквы %s." % (s, letter))
    return _out(text, best, "Самая длинная цепочка «%s» имеет длину %d." % (letter, best),
                ["Иди по строке слева направо.", "Сбрасывай счётчик, когда буква меняется."],
                {"kind": "runs", "s": s, "letter": letter})


def _div_count(r):
    a, b = r.randint(20, 60), r.randint(80, 140)
    k = r.choice([3, 4, 6, 7])
    ban = r.choice([2, 5])
    ans = sum(1 for x in range(a, b + 1) if x % k == 0 and x % ban != 0)
    text = ("Сколько целых чисел от %d до %d включительно делятся на %d и при этом не делятся на %d?"
            % (a, b, k, ban))
    return _out(text, ans, "Таких чисел %d." % ans,
                ["Перебери отрезок.", "Оставь кратные %d и вычеркни кратные %d." % (k, ban)],
                {"kind": "divc", "a": a, "b": b, "k": k, "ban": ban})


def _fit(r):
    cap = r.choice([50, 60, 80])
    sizes = sorted(r.randint(5, 30) for _ in range(8))
    used = n = 0
    for sz in sizes:
        if used + sz <= cap:
            used += sz
            n += 1
    text = ("На диск помещается %d МБ. Файлы, МБ: %s. Их записывают начиная с самых маленьких, пока хватает места. "
            "Сколько файлов поместится?" % (cap, ", ".join(map(str, sizes))))
    return _out(text, n, "Жадно с маленьких: помещается %d файлов, занято %d МБ." % (n, used),
                ["Отсортируй по возрастанию.", "Складывай, пока сумма не превысит %d." % cap],
                {"kind": "fit", "cap": cap, "sizes": sizes})


def _pairs(r):
    k = r.choice([3, 4, 5])
    nums = [r.randint(1, 20) for _ in range(6)]
    ans = 0
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if (nums[i] + nums[j]) % k == 0:
                ans += 1
    text = ("Числа: %s. Сколько неупорядоченных пар имеют сумму, делящуюся на %d? Пару образуют два разных элемента, "
            "порядок не важен." % (", ".join(map(str, nums)), k))
    return _out(text, ans, "Таких пар %d." % ans,
                ["Перебери все пары индексов i < j.", "Проверь остаток суммы."],
                {"kind": "pairs", "nums": nums, "k": k})


def _doc(r):
    kind = r.choice(["bullets", "bytes", "slides"])
    if kind == "bullets":
        n, k = r.randint(3, 12), r.randint(2, 6)
        ans = n * k
        text = ("Презентация: титульный слайд без пунктов и %d слайдов с текстом. На каждом текстовом слайде ровно "
                "%d пункта. Сколько пунктов во всей презентации?" % (n, k))
        expl = "%d · %d = %d. Титульный слайд пунктов не добавляет." % (n, k, ans)
        data = {"kind": "bullets", "n": n, "k": k}
    elif kind == "bytes":
        chars, b = r.choice([80, 100, 120, 150, 200]), r.choice([1, 2])
        ans = chars * b
        text = ("Текст без служебного заголовка состоит из %d символов. Каждый символ кодируется %d байтами. "
                "Каков размер текста в байтах?" % (chars, b))
        expl = "%d · %d = %d байт." % (chars, b, ans)
        data = {"kind": "bytes", "chars": chars, "b": b}
    else:
        content = r.randint(4, 16)
        ans = content + 1
        text = ("В презентации есть титульный слайд и ещё %d слайдов с содержанием. Сколько слайдов всего?" % content)
        expl = "1 + %d = %d." % (content, ans)
        data = {"kind": "slides", "content": content}
    return _out(text, ans, expl, ["Выпиши, что сказано про титульный слайд и про остальные.", expl], data)


# ------------------------------------------------------------------ биология и география: расчёты
def _bio_table(r):
    years = [2019, 2020, 2021, 2022, 2023]
    vals = [r.randint(10, 40) for _ in years]
    # гарантируем единственный максимум
    top = vals.index(max(vals))
    vals[top] = max(vals) + 3
    ans = years[vals.index(max(vals))]
    lines = "\n".join("%d год — %d особей" % (y, v) for y, v in zip(years, vals))
    text = ("Численность колонии по годам:\n\n%s\n\nВ каком году особей было больше всего? Запиши год." % lines)
    return _out(text, ans, "Максимум %d особей в %d году." % (max(vals), ans),
                ["Сравни числа.", "Год с наибольшим числом — %d." % ans],
                {"kind": "bio-table", "years": years, "vals": vals})


def _bio_energy(r):
    start = r.choice([1000, 2000, 5000])
    levels = r.choice([1, 2])
    ans = start // (10 ** levels)
    text = ("В условии задачи действует правило: на следующий трофический уровень переходит 10%% энергии. "
            "На уровне продуцентов %d кДж. Сколько кДж дойдёт до уровня, который на %d %s выше?"
            % (start, levels, "ступень" if levels == 1 else "ступени"))
    return _out(text, ans, "Каждая ступень делит энергию на 10: %d." % ans,
                ["Один переход — деление на 10.", "Повтори %d раз." % levels],
                {"kind": "energy", "start": start, "levels": levels})


def _bio_cross(r):
    dominant = r.choice([True, False])
    ans = 3 if dominant else 1
    trait = "жёлтые" if dominant else "зелёные"
    text = ("У гороха жёлтая окраска семян доминирует над зелёной. Скрестили две гетерозиготы. Сколько из каждых "
            "четырёх потомков в среднем имеют %s семена? Запиши число." % trait)
    return _out(text, ans, "Расщепление 3:1. %s — %d из 4." % (trait.capitalize(), ans),
                ["Aa × Aa даёт три доминантных фенотипа и один рецессивный.", "Ответ %d." % ans],
                {"kind": "fixed", "answer": str(ans)})


def _geo_scale(r):
    cm = r.randint(2, 8)
    # 1:100000 → 1 см = 1 км
    ans = cm
    text = ("Масштаб карты 1:100 000. Отрезок на карте %d см. Каково расстояние на местности в километрах?" % cm)
    return _out(text, ans, "1:100 000 означает 1 см = 1 км, значит %d см = %d км." % (cm, ans),
                ["В 1 см карты — 100 000 см местности, это 1 км.", "%d см — это %d км." % (cm, ans)],
                {"kind": "scale-map", "cm": cm})


def _geo_growth(r):
    born, died = r.randint(10, 18), r.randint(6, 14)
    ans = born - died
    text = ("На 1000 жителей за год родилось %d человек и умерло %d. Чему равен естественный прирост на 1000 жителей? "
            "Если убыль — запиши отрицательное число." % (born, died))
    return _out(text, ans, "Прирост = родившиеся − умершие = %d." % ans,
                ["Естественный прирост — разность рождаемости и смертности.", "%d − %d = %d." % (born, died, ans)],
                {"kind": "growth", "born": born, "died": died})


def _geo_years(r):
    reserve, use = r.choice([(300, 10), (480, 12), (250, 5), (600, 20), (360, 15)])
    ans = reserve // use
    text = ("Запасы ресурса %d млн т, ежегодная добыча %d млн т и не меняется. На сколько лет хватит запаса?"
            % (reserve, use))
    return _out(text, ans, "%d / %d = %d лет." % (reserve, use, ans),
                ["Раздели запас на годовую добычу.", "%d / %d." % (reserve, use)],
                {"kind": "years", "reserve": reserve, "use": use})


def recompute(data):
    k = data["kind"]
    if k == "digits":
        return data["answer"]
    if k == "fixed":
        return data["answer"]
    if k == "index":
        return data["options"].index(data["right"]) + 1
    if k == "scale":
        return data["step"] * data["marks"]
    if k == "ohm":
        return data["u"] // data["r"]
    if k == "heat":
        return data["c"] * data["m"] * data["dt"]
    if k == "speed":
        return data["s"] // data["t"]
    if k == "parallel":
        return data["a"] * data["b"] // (data["a"] + data["b"])
    if k == "weight":
        return data["m"] * 10
    if k == "graph":
        v = data["v"]
        return sum(1 for a, b in data["edges"] if a == v or b == v)
    if k == "db":
        return sum(1 for row in data["rows"] if row[1 + data["subj"]] >= data["need"])
    if k == "prefix":
        bits = {"А": 1, "Б": 2, "В": 2}
        return sum(bits[ch] for ch in data["word"])
    if k == "exec":
        x = data["start"]
        for cmd in data["prog"]:
            x = x + 1 if cmd == "1" else x * data["b"]
        return x
    if k == "sheet":
        return sum(p for p in data["prices"] if p >= data["limit"])
    if k == "search":
        return data["bag"].count(data["word"])
    if k == "seq":
        return max(x for x in data["nums"] if x % 2 == 0)
    if k == "grid":
        a, b, c, d = data["a"], data["b"], data["c"], data["d"]
        return a + d + max(b, c)
    if k == "game-one":
        return 1 if _game_win(data["n"])[data["n"]] else 2
    if k == "game-strat":
        win = _game_win(data["limit"], tuple(data["moves"]))
        return next(i for i in range(1, data["limit"] + 1) if not win[i])
    if k == "game-tree":
        win = _game_win(data["n"])
        n = data["n"]
        if not win[n]:
            return 0
        return next(m for m in (1, 2) if not win[n - m])
    if k == "crit":
        return data["a"] + max(data["b"], data["c"]) + data["d"]
    if k == "runs":
        best = cur = 0
        for ch in data["s"]:
            if ch == data["letter"]:
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
        return best
    if k == "divc":
        return sum(1 for x in range(data["a"], data["b"] + 1) if x % data["k"] == 0 and x % data["ban"] != 0)
    if k == "fit":
        used = n = 0
        for sz in sorted(data["sizes"]):
            if used + sz <= data["cap"]:
                used += sz
                n += 1
        return n
    if k == "pairs":
        nums, mod = data["nums"], data["k"]
        return sum(1 for i in range(len(nums)) for j in range(i + 1, len(nums)) if (nums[i] + nums[j]) % mod == 0)
    if k == "bullets":
        return data["n"] * data["k"]
    if k == "bytes":
        return data["chars"] * data["b"]
    if k == "slides":
        return data["content"] + 1
    if k == "bio-table":
        vals = data["vals"]
        return data["years"][vals.index(max(vals))]
    if k == "energy":
        return data["start"] // (10 ** data["levels"])
    if k == "scale-map":
        return data["cm"]
    if k == "growth":
        return data["born"] - data["died"]
    if k == "years":
        return data["reserve"] // data["use"]
    raise KeyError(k)


def _bind(keys, fn):
    return {key: fn for key in keys}


STEM = {}
STEM.update(_bind([("ege-phys-2026", 5)], _mech_analysis))
STEM.update(_bind([("ege-phys-2026", 6)], _mech_change))
STEM.update(_bind([("ege-phys-2026", 14)], _series_change))
STEM.update(_bind([("ege-phys-2026", 9)], _gas_change))
STEM.update(_bind([("ege-phys-2026", 10)], _gas_isobar))
STEM.update(_bind([("ege-phys-2026", 17)], _nuclear_change))
STEM.update(_bind([
    ("ege-phys-2026", 18), ("ege-phys-2026", 21), ("oge-phys-2026", 19),
], _qualitative))
STEM.update(_bind([("ege-phys-2026", 19)], _scale))
STEM.update(_bind([("ege-phys-2026", 20), ("oge-phys-2026", 17)], _plan_exp))
STEM.update(_bind([
    ("oge-phys-2026", 18), ("oge-phys-2026", 20), ("oge-phys-2026", 21), ("oge-phys-2026", 22),
], _text_phys))
STEM[("ege-phys-2026", 22)] = _speed_num
STEM[("ege-phys-2026", 23)] = _weight
STEM[("ege-phys-2026", 24)] = _ohm_num
STEM[("ege-phys-2026", 25)] = _heat_num
STEM[("ege-phys-2026", 26)] = _qualitative
# часть «изменение величин» по механике уже закрыта _ohm_change; для оптики — отдельно
STEM[("ege-phys-2026", 15)] = _lens_change

STEM.update({
    ("ege-inf-2026", 1): _graph,
    ("ege-inf-2026", 3): _db,
    ("ege-inf-2026", 4): _prefix,
    ("ege-inf-2026", 6): _executor,
    ("ege-inf-2026", 9): _sheet,
    ("ege-inf-2026", 10): _search,
    ("ege-inf-2026", 17): _seq,
    ("ege-inf-2026", 18): _path_sum,
    ("ege-inf-2026", 19): lambda r: _game(r, "one"),
    ("ege-inf-2026", 20): lambda r: _game(r, "strat"),
    ("ege-inf-2026", 21): lambda r: _game(r, "tree"),
    ("ege-inf-2026", 22): _critical,
    ("ege-inf-2026", 24): _runs,
    ("ege-inf-2026", 25): _div_count,
    ("ege-inf-2026", 26): _fit,
    ("ege-inf-2026", 27): _pairs,
    ("oge-bio-2026", 4): _bio_table,
    ("oge-bio-2026", 25): _bio_table,
    ("oge-bio-2026", 26): _bio_energy,
    ("ege-bio-2026", 3): _bio_energy,
    ("ege-bio-2026", 4): _bio_cross,
    ("ege-bio-2026", 21): _bio_table,
    ("ege-bio-2026", 28): _bio_cross,
    ("oge-geo-2026", 9): _geo_growth,
    ("ege-geo-2026", 15): _geo_years,
    ("ege-geo-2026", 16): _geo_growth,
    ("oge-geo-2026", 6): _geo_scale,
    ("ege-geo-2026", 1): _geo_scale,
})

ABOUT = {
    ("ege-phys-2026", 5): "Механика: при той же силе большая масса даёт меньшее ускорение.",
    ("ege-phys-2026", 6): "Механика: как меняются масса и ускорение.",
    ("ege-phys-2026", 9): "Нагрев газа в жёстком сосуде: температура и давление.",
    ("ege-phys-2026", 10): "То же: температура и давление идеального газа.",
    ("ege-phys-2026", 14): "Последовательное соединение: общее сопротивление и ток.",
    ("ege-phys-2026", 15): "Собирающая линза: оптическая сила и расстояние до изображения.",
    ("ege-phys-2026", 17): "α-распад: как меняются массовое и зарядовое числа.",
    ("ege-phys-2026", 18): "Качественный вопрос: кипение, теплопроводность или плавание.",
    ("ege-phys-2026", 19): "Показание прибора по цене деления.",
    ("ege-phys-2026", 20): "Какие две величины измерить, чтобы найти сопротивление.",
    ("ege-phys-2026", 21): "Качественный вопрос: кипение, теплопроводность или плавание.",
    ("ege-phys-2026", 22): "Короткий расчёт по формуле из условия.",
    ("ege-phys-2026", 23): "Короткий расчёт по формуле из условия.",
    ("ege-phys-2026", 24): "Короткий расчёт по формуле из условия.",
    ("ege-phys-2026", 25): "Короткий расчёт по формуле из условия.",
    ("ege-phys-2026", 26): "Короткий расчёт, закон назван в разборе.",
    ("oge-phys-2026", 17): "Какие величины измерить для сопротивления.",
    ("oge-phys-2026", 18): "Расчёт по тексту: Ом, теплота, скорость или вес.",
    ("oge-phys-2026", 19): "Качественный вопрос по известному явлению.",
    ("oge-phys-2026", 20): "Расчёт по формуле.",
    ("oge-phys-2026", 21): "Расчёт по формуле.",
    ("oge-phys-2026", 22): "Расчёт по формуле.",
    ("ege-inf-2026", 1): "Степень вершины в небольшом графе.",
    ("ege-inf-2026", 3): "Подсчёт строк таблицы по условию.",
    ("ege-inf-2026", 4): "Длина слова в префиксном коде.",
    ("ege-inf-2026", 6): "Результат программы исполнителя.",
    ("ege-inf-2026", 9): "Сумма чисел столбца по условию.",
    ("ege-inf-2026", 10): "Сколько раз слово встречается в строке.",
    ("ege-inf-2026", 17): "Наибольшее чётное в последовательности.",
    ("ege-inf-2026", 18): "Наибольшая сумма пути по таблице 2×2.",
    ("ege-inf-2026", 19): "Игра в камни: выигрышна ли позиция.",
    ("ege-inf-2026", 20): "Игра в камни: наименьшая проигрышная куча.",
    ("ege-inf-2026", 21): "Игра в камни: каким первым ходом победить.",
    ("ege-inf-2026", 22): "Длина критического пути из четырёх дел.",
    ("ege-inf-2026", 24): "Самая длинная цепочка одинаковых букв.",
    ("ege-inf-2026", 25): "Сколько чисел на отрезке с двумя условиями делимости.",
    ("ege-inf-2026", 26): "Сколько файлов влезет, если класть с маленьких.",
    ("ege-inf-2026", 27): "Сколько пар имеют сумму, кратную k.",
    ("oge-bio-2026", 4): "По таблице численности найти год максимума.",
    ("oge-bio-2026", 25): "По таблице найти год с наибольшим значением.",
    ("oge-bio-2026", 26): "Энергия по правилу 10%, правило названо в условии.",
    ("ege-bio-2026", 3): "Расчёт энергии по названному правилу 10%.",
    ("ege-bio-2026", 4): "Моногибридное скрещивание двух гетерозигот: 3 из 4.",
    ("ege-bio-2026", 21): "Год максимума по таблице.",
    ("ege-bio-2026", 28): "Моногибридное скрещивание: доля доминантного фенотипа.",
    ("oge-geo-2026", 6): "Расстояние по масштабу 1:100 000.",
    ("oge-geo-2026", 9): "Естественный прирост: родившиеся минус умершие.",
    ("ege-geo-2026", 1): "Расстояние по масштабу.",
    ("ege-geo-2026", 15): "На сколько лет хватит запаса при постоянной добыче.",
    ("ege-geo-2026", 16): "Естественный прирост населения.",
}
