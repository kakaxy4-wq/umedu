"""Тренажёр первой части ОГЭ: бесконечные варианты номеров 1–10 и 12.

Вариант задаётся парой (номер, сид): по ним генератор каждый раз строит одно и то же условие и ответ, поэтому в браузер
уходит только условие, а проверка — на сервере пересборкой варианта. Условия написаны по образцу экзаменационных
(спецификация ФИПИ 2026), не копии. Ответ считается программно (перебор, Дейкстра, подсчёт путей), а не задаётся руками.

Каждый генератор возвращает: text — условие (абзацы через \\n\\n), answer — эталон, explain — короткий разбор;
по желанию table — таблица (список строк, первая — заголовок), code — фрагмент программы, check — своя проверка
ответа (когда верных ответов несколько, как в №5).
"""
import heapq
import random
import re
from fnmatch import fnmatchcase

XP = 2                  # за верный ответ на новый вариант
DAILY_XP_CAP = 20


def _pl(n, one, few, many):
    """1 байт, 2 байта, 5 байт."""
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def _norm(s):
    return re.sub(r"\s+", "", str(s)).upper().replace("Ё", "Е")


# ------------------------------------------------------------------ №1 — объём текста
_ANIMALS = ["кот", "лев", "енот", "тигр", "слон", "волк", "зебра", "жираф", "барсук", "бегемот", "носорог", "антилопа",
            "крокодил", "дикобраз", "орангутан", "муравьед"]
_BIRDS = ["чиж", "грач", "сова", "дрозд", "синица", "ворона", "соловей", "воробей", "снегирь", "трясогузка", "журавль",
          "попугай", "пеликан", "фламинго", "куропатка"]


def g1(r):
    kind, pool, tail = r.choice([("одного из животных", _ANIMALS, "дикие животные"), ("одной из птиц", _BIRDS, "птицы")])
    uniq = []
    while not uniq:                       # нужен хоть один «вычеркнутый» с длиной, которой больше ни у кого нет
        words = r.sample(pool, r.randint(6, 8))
        lens = [len(w) for w in words]
        uniq = [w for w in words if lens.count(len(w)) == 1]
    gone = r.choice(uniq)
    bits = r.choice([8, 16])
    enc = "КОИ-8 каждый символ кодируется 8 битами" if bits == 8 else "Unicode каждый символ кодируется 16 битами"
    diff = (len(gone) + 2) * bits // 8
    sent = ", ".join(words) + " — " + tail
    sent = sent[0].upper() + sent[1:]
    return {"text": "В кодировке %s. Ученик написал текст (в нём нет лишних пробелов):\n\n«%s».\n\n"
                    "Ученик вычеркнул из списка название %s. Заодно он вычеркнул ставшие лишними запятую и пробел — "
                    "два пробела не должны идти подряд. При этом размер нового предложения оказался на %d %s меньше, "
                    "чем размер исходного. Напишите в ответе вычеркнутое название." % (enc, sent, kind, diff,
                                                                         _pl(diff, "байт", "байта", "байт")),
            "answer": gone,
            "explain": "Вычеркнули слово, запятую и пробел. %d : %d (байт на символ) = %d символов, из них 2 — запятая и "
                       "пробел. Значит, в слове %d букв — это «%s»." % (diff, bits // 8, diff * 8 // bits, len(gone), gone)}


# ------------------------------------------------------------------ №2 — декодирование
_PREFIX_CODES = [["0", "10", "110", "1110", "1111"], ["00", "01", "10", "110", "111"], ["1", "01", "001", "0001", "0000"],
                 ["11", "10", "01", "001", "000"], ["0", "100", "101", "110", "111"], ["01", "00", "10", "110", "111"]]


def g2(r):
    letters = r.sample("АБВГДЕЖИКЛМНОПРСТ", 5)
    codes = r.choice(_PREFIX_CODES)[:]
    r.shuffle(codes)
    table = dict(zip(letters, codes))
    word = "".join(r.choice(letters) for _ in range(r.randint(5, 7)))
    bitstr = "".join(table[c] for c in word)
    return {"text": "Разведчик передал в штаб сообщение, зашифрованное кодом. Каждой букве соответствует своя "
                    "последовательность из нулей и единиц, и никакой код не является началом другого — поэтому сообщение "
                    "расшифровывается однозначно.\n\nСообщение: **%s**\n\nРасшифруйте его и запишите буквы в ответе." % bitstr,
            "table": [["Буква"] + letters, ["Код"] + [table[c] for c in letters]],
            "answer": word,
            "explain": "Идём слева направо и отрезаем код, который подходит: " + " · ".join(
                "%s=%s" % (table[c], c) for c in word) + "."}


# ------------------------------------------------------------------ №3 — истинность высказывания
def g3(r):
    a = r.randint(10, 90)
    k = r.choice([3, 4, 5, 6, 7])
    forms = [
        ("НЕ (X < %d) И (X делится на %d)" % (a, k), lambda x: not x < a and x % k == 0, True, "min"),
        ("НЕ (X > %d) И (X делится на %d)" % (a, k), lambda x: not x > a and x % k == 0, True, "max"),
        ("(X > %d) ИЛИ (X чётное)" % a, lambda x: x > a or x % 2 == 0, False, "max"),
        ("(X < %d) ИЛИ НЕ (X нечётное)" % a, lambda x: x < a or x % 2 == 0, False, "min"),
        ("(X > %d) И НЕ (X делится на %d)" % (a, k), lambda x: x > a and x % k != 0, True, "min"),
        ("НЕ (X > %d) И НЕ (X чётное)" % a, lambda x: not x > a and x % 2 == 1, True, "max"),
    ]
    expr, pred, truth, which = r.choice(forms)
    xs = [x for x in range(-1000, 1001) if pred(x) == truth]
    ans = min(xs) if which == "min" else max(xs)
    assert -1000 < ans < 1000
    return {"text": "Напишите %s целое число X, для которого %s высказывание:\n\n**%s**" % (
                "наименьшее" if which == "min" else "наибольшее", "истинно" if truth else "ложно", expr),
            "answer": str(ans),
            "explain": "При X = %d высказывание %s, а при всех %s X — нет. Удобно проверить перебором в цикле."
                       % (ans, "истинно" if truth else "ложно", "меньших" if which == "min" else "больших")
                       + (" Чтобы высказывание с ИЛИ было ложным, ложными должны быть обе его части." if not truth else "")}


# ------------------------------------------------------------------ №4 — кратчайший путь по таблице
def _dijkstra(n, w, s, t):
    dist, prev, pq = {s: 0}, {}, [(0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e9):
            continue
        for v in range(n):
            if w[u][v] and d + w[u][v] < dist.get(v, 1e9):
                dist[v], prev[v] = d + w[u][v], u
                heapq.heappush(pq, (dist[v], v))
    if t not in dist:
        return None, []
    path = [t]
    while path[-1] != s:
        path.append(prev[path[-1]])
    return dist[t], path[::-1]


def g4(r):
    names = "ABCDEF"
    n = 6
    while True:
        w = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if r.random() < 0.5:
                    w[i][j] = w[j][i] = r.randint(1, 9)
        d, path = _dijkstra(n, w, 0, n - 1)
        if d and len(path) >= 3 and (not w[0][n - 1] or w[0][n - 1] > d):
            break
    table = [[""] + list(names)] + [[names[i]] + [str(w[i][j]) if w[i][j] else "" for j in range(n)] for i in range(n)]
    return {"text": "Между населёнными пунктами A, B, C, D, E, F построены дороги, протяжённость которых (в километрах) "
                    "приведена в таблице. Определите длину кратчайшего пути между пунктами A и F. Передвигаться можно "
                    "только по дорогам, протяжённость которых указана в таблице.",
            "table": table, "answer": str(d),
            "explain": "Кратчайший путь: %s = %s = %d км." % (
                "–".join(names[i] for i in path), " + ".join(str(w[a][b]) for a, b in zip(path, path[1:])), d)}


# ------------------------------------------------------------------ №5 — исполнитель с двумя командами
def g5(r):
    while True:
        s, a, b = r.randint(1, 9), r.randint(1, 5), r.randint(2, 4)
        prog = "".join(r.choice("12") for _ in range(5))
        if "1" in prog and "2" in prog:
            break
    x, steps = s, []
    for c in prog:
        x = x + a if c == "1" else x * b
        steps.append(x)
    t = x

    def check(given):
        g = _norm(given)
        if not g or len(g) > 5 or set(g) - {"1", "2"}:
            return False
        v = s
        for c in g:
            v = v + a if c == "1" else v * b
        return v == t
    return {"text": "У исполнителя Альфа две команды, которым присвоены номера:\n\n**1. прибавь %d**\n**2. умножь на %d**\n\n"
                    "Первая увеличивает число на экране на %d, вторая — умножает его на %d. Составьте алгоритм получения "
                    "из числа %d числа %d, содержащий не более 5 команд. В ответе запишите только номера команд. Если таких "
                    "алгоритмов больше одного, запишите любой." % (a, b, a, b, s, t),
            "answer": prog, "check": check,
            "explain": "Например, %s: %d → %s. Удобно идти от конца: если %d не делится на %d, последней была команда 1."
                       % (prog, s, " → ".join(map(str, steps)), t, b)}


# ------------------------------------------------------------------ №6 — анализ программы с условием
def g6(r):
    A, B = r.randint(2, 9), r.randint(5, 12)
    forms = [("s > %d and t < %d" % (A, B), lambda s, t: s > A and t < B),
             ("s > %d or t > %d" % (A, B), lambda s, t: s > A or t > B),
             ("not (s < %d) and t > %d" % (A, B), lambda s, t: not s < A and t > B),
             ("s < %d or not (t > %d)" % (A, B), lambda s, t: s < A or not t > B)]
    cond, f = r.choice(forms)
    pairs = [(r.randint(-5, 15), r.randint(-5, 15)) for _ in range(9)]
    word = r.choice(["YES", "NO"])
    yes = sum(1 for s, t in pairs if f(s, t))
    ans = yes if word == "YES" else 9 - yes
    return {"text": "Дана программа:\n\n{code}\n\nБыло проведено 9 запусков программы, при которых в качестве значений переменных "
                    "s и t вводились следующие пары чисел:\n\n%s\n\nСколько было запусков, при которых программа "
                    "напечатала «%s»?" % (", ".join("(%d, %d)" % p for p in pairs), word),
            "code": "s = int(input())\nt = int(input())\nif %s:\n    print(\"YES\")\nelse:\n    print(\"NO\")" % cond,
            "answer": str(ans),
            "explain": "Условие истинно для пар: %s — «YES» напечатано %d %s, «NO» — %d." % (
                ", ".join("(%d, %d)" % p for p in pairs if f(*p)) or "ни одной", yes, _pl(yes, "раз", "раза", "раз"),
                9 - yes)}


# ------------------------------------------------------------------ №7 — адрес файла
def g7(r):
    proto = r.choice(["http", "https", "ftp"])
    host = r.choice(["school", "info", "study", "home", "exam", "site", "lib", "test"])
    tld = r.choice(["ru", "net", "org", "com"])
    fname = r.choice([x for x in ["data", "notes", "task", "list", "report", "photo", "plan", "book"] if x != host])
    ext = r.choice(["txt", "doc", "png", "htm", "xls", "pdf"])
    parts = [proto, "://", host, "." + tld, "/", fname, "." + ext]
    letters = list("АБВГДЕЖ")
    shuffled = parts[:]
    r.shuffle(shuffled)
    code = dict(zip(shuffled, letters))
    ans = "".join(code[p] for p in parts)
    return {"text": "Доступ к файлу **%s.%s**, находящемуся на сервере **%s.%s**, осуществляется по протоколу **%s**. "
                    "Фрагменты адреса файла закодированы буквами от А до Ж. Запишите последовательность этих букв, "
                    "кодирующую адрес указанного файла в сети Интернет." % (fname, ext, host, tld, proto),
            "table": [["Буква", "Фрагмент"]] + [[l, p] for p, l in zip(shuffled, letters)],
            "answer": ans,
            "explain": "Адрес: %s → %s." % ("".join(parts), " ".join("%s(%s)" % (code[p], p) for p in parts))}


# ------------------------------------------------------------------ №8 — запросы к поисковой системе
_PAIRS = [("Фрегат", "Эсминец"), ("Кошка", "Собака"), ("Физика", "Химия"), ("Пушкин", "Лермонтов"), ("Лиса", "Заяц"),
          ("Москва", "Казань"), ("Футбол", "Хоккей")]


def g8(r):
    x, y = r.choice(_PAIRS)
    ab = r.randint(100, 900)
    a, b = ab + r.randint(200, 2000), ab + r.randint(200, 2000)
    rows = [("%s | %s" % (x, y), a + b - ab), ("%s & %s" % (x, y), ab), (x, a), (y, b)]
    ask = r.randrange(4)
    shown = [[q, str(v) if i != ask else "?"] for i, (q, v) in enumerate(rows)]
    return {"text": "В языке запросов поискового сервера для обозначения логической операции «ИЛИ» используется символ "
                    "«|», а для операции «И» — «&». В таблице приведены запросы и количество найденных по ним страниц "
                    "некоторого сегмента сети Интернет. Какое количество страниц (в тысячах) будет найдено по запросу "
                    "«%s»? Считается, что все запросы выполнялись практически одновременно." % rows[ask][0],
            "table": [["Запрос", "Найдено страниц (в тысячах)"]] + shown,
            "answer": str(rows[ask][1]),
            "explain": "Круги Эйлера: |%s| = |%s| + |%s| − |%s & %s|, то есть %d = %d + %d − %d." % (
                rows[0][0], x, y, x, y, a + b - ab, a, b, ab)}


# ------------------------------------------------------------------ №9 — количество путей
def g9(r):
    names = "АБВГДЕЖИК"
    n = len(names)
    while True:
        edges = set()
        for i in range(n - 1):
            for j in r.sample(range(i + 1, min(n, i + 4)), min(r.randint(1, 2), min(n, i + 4) - i - 1)):
                edges.add((i, j))
        if not all(any(e[1] == j for e in edges) for j in range(1, n)):
            continue
        ways = [0] * n
        ways[0] = 1
        for j in range(1, n):
            ways[j] = sum(ways[i] for i, jj in edges if jj == j)
        if 6 <= ways[-1] <= 40:
            break
    out = {}
    for i, j in sorted(edges):
        out.setdefault(i, []).append(names[j])
    roads = "; ".join("из %s — в %s" % (names[i], ", ".join(v)) for i, v in out.items())
    return {"text": "Между городами %s проложены дороги с односторонним движением: %s. Сколько существует различных "
                    "путей из города А в город К?" % (", ".join(names), roads),
            "answer": str(ways[-1]),
            "explain": "Считаем для каждого города число путей в него — сумму по городам, откуда в него ведут дороги: "
                       + ", ".join("%s=%d" % (names[j], ways[j]) for j in range(n)) + "."}


# ------------------------------------------------------------------ №10 — системы счисления
def g10(r):
    vals = r.sample(range(40, 256), 3)
    sub = {2: "₂", 8: "₈", 16: "₁₆"}
    shown = [format(vals[0], "b") + sub[2], format(vals[1], "o") + sub[8], format(vals[2], "X") + sub[16]]
    order = [0, 1, 2]
    r.shuffle(order)
    which = r.choice(["максимальное", "минимальное"])
    ans = max(vals) if which == "максимальное" else min(vals)
    return {"text": "Среди приведённых ниже трёх чисел, записанных в различных системах счисления, найдите %s и "
                    "запишите его в ответе в десятичной системе счисления. В ответе запишите только число, основание "
                    "системы счисления указывать не нужно.\n\n**%s**" % (which, ", ".join(shown[i] for i in order)),
            "answer": str(ans),
            "explain": "Переводим: %s." % ", ".join("%s = %d" % (shown[i], vals[i]) for i in range(3))}


# ------------------------------------------------------------------ №12 — маски файлов
def g12(r):
    while True:
        exts = ["txt", "tex", "dat", "doc", "dot"]
        files = sorted({"".join(r.choice("abco") for _ in range(r.randint(3, 6))) + "." + r.choice(exts)
                        for _ in range(9)})
        base, ext = r.choice(files).split(".")
        chars = list(base)
        chars[r.randrange(len(chars))] = "?"
        cut = r.randint(1, len(chars) - 1)
        mask_base = "".join(chars[:cut]) + "*"
        mask_ext = ext if r.random() < 0.5 else ext[0] + "?" + ext[2]
        mask = mask_base + "." + mask_ext
        count = sum(fnmatchcase(f, mask) for f in files)
        if 2 <= count <= len(files) - 2:
            break
    return {"text": "Для групповых операций с файлами используются маски имён файлов: символ «?» означает ровно один "
                    "произвольный символ, «*» — любую последовательность символов произвольной длины, в том числе пустую. "
                    "Сколько файлов из списка ниже удовлетворяет маске **%s**?\n\n%s" % (mask, "\n".join(files)),
            "answer": str(count),
            "explain": "Подходят: %s." % ", ".join(f for f in files if fnmatchcase(f, mask))}


GENERATORS = {1: g1, 2: g2, 3: g3, 4: g4, 5: g5, 6: g6, 7: g7, 8: g8, 9: g9, 10: g10, 12: g12}


def make(num, seed):
    from .solve_steps import ensure
    v = GENERATORS[num](random.Random("%d-%d" % (num, seed)))
    v["text"] = re.sub(r"\s+([.,;:!?])", r"\1", v["text"])
    v["explain"] = re.sub(r"\s+([.,;:!?])", r"\1", v.get("explain") or "")
    if v.get("steps"):
        v["steps"] = [re.sub(r"\s+([.,;:!?])", r"\1", s) for s in v["steps"]]
    ensure(v)
    v.update({"num": num, "seed": seed})
    return v


def public(v):
    return {k: v[k] for k in ("num", "seed", "text", "table", "code", "svg") if k in v}


def check(v, given):
    if "check" in v:
        return v["check"](given)
    return _norm(given) == _norm(v["answer"])
