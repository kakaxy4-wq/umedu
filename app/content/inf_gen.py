"""Свои варианты ЕГЭ по информатике для umedu 2.0: номера 2, 5, 7, 8, 11–16, 23 — формат, устойчивый в КИМ.

Устроено как app/content/math_gen.py (Bank: make / public / check). Условия написаны по образцу экзаменационных,
не копии банка ФИПИ. Ответ всегда считается программно — перебором, динамикой или прямым вычислением.
"""
import itertools
import math
from fractions import Fraction as F
from functools import lru_cache

from .math_gen import Bank


def _cnt(n, one, few, many):
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def e7(r):
    if r.random() < 0.5:
        w, h = r.choice([(64, 128), (128, 128), (128, 256), (256, 256), (320, 256), (640, 512), (1024, 512)])
        bits = r.randint(2, 8)
        kb = w * h * bits // 8192
        while w * h * bits % 8192:
            bits += 1
            kb = w * h * bits // 8192
        return {"text": "Для хранения произвольного растрового изображения размером %d×%d пикселей отведено %d Кбайт памяти "
                        "без учёта размера заголовка файла. Для кодирования цвета каждого пикселя используется одинаковое "
                        "количество бит, коды пикселей записываются в файл один за другим без промежутков. Какое "
                        "максимальное количество цветов можно использовать в изображении?" % (w, h, kb),
                "answer": str(2 ** bits),
                "explain": "%d Кбайт = %d бит; на пиксель %d · 8192 : (%d · %d) = %d бит, значит, 2^%d = %d цветов."
                           % (kb, kb * 8192, kb, w, h, bits, bits, 2 ** bits)}
    size = r.choice([12, 16, 20, 24, 30, 36, 40, 48, 60, 64, 80, 90])
    while True:
        fq, rs = r.choice(_CHANGES), r.choice(_CHANGES)       # во сколько раз изменились частота и разрешение
        new = size * fq * rs
        if (fq, rs) != (1, 1) and new.denominator == 1:
            break
    return {"text": "Музыкальный фрагмент был оцифрован и записан в виде файла без использования сжатия данных. Размер "
                    "файла — %d Мбайт. Затем тот же фрагмент был оцифрован повторно с частотой дискретизации %s и "
                    "разрешением %s, чем в первый раз; сжатие данных не производилось. Укажите размер в Мбайт файла, "
                    "полученного при повторной записи." % (size, _how(fq, "прежней"), _how(rs, "прежним")),
            "answer": str(int(new)),
            "explain": "Размер пропорционален частоте и разрешению: %d · %s · %s = %d Мбайт."
                       % (size, _ratio(fq), _ratio(rs), int(new))}


_CHANGES = [F(1), F(2), F(3), F(4), F(1, 2), F(1, 3), F(1, 4)]


def _how(x, same):
    if x == 1:
        return same
    k = x.numerator if x > 1 else x.denominator
    return "в %d %s %s" % (k, _cnt(k, "раз", "раза", "раз"), "выше" if x > 1 else "ниже")


def _ratio(x):
    return str(x.numerator) if x.denominator == 1 else "1/%d" % x.denominator


def e8(r):
    letters = r.sample("АВГДЕИКЛМНОПРСТ", r.randint(4, 6))
    n = r.randint(4, 6)
    x = r.choice(letters)
    kind = r.choice(["exact", "notfirst", "noadj"])
    words = itertools.product(letters, repeat=n)
    if kind == "exact":
        k = r.randint(1, 2)
        ans = sum(1 for w in words if w.count(x) == k)
        cond = "буква %s встречается ровно %d %s" % (x, k, _cnt(k, "раз", "раза", "раз"))
        expl = "Выбираем места для %s: C(%d, %d), остальные %d мест — любая из %d букв: C(%d, %d) · %d^%d = %d." % (
            x, n, k, n - k, len(letters) - 1, n, k, len(letters) - 1, n - k, ans)
    elif kind == "notfirst":
        ans = sum(1 for w in words if w[0] != x)
        cond = "слово не начинается с буквы %s" % x
        expl = "На первое место — %d букв, на остальные %d — любая из %d: %d · %d^%d = %d." % (
            len(letters) - 1, n - 1, len(letters), len(letters) - 1, len(letters), n - 1, ans)
    else:
        ans = sum(1 for w in words if all(not (w[i] == x == w[i + 1]) for i in range(n - 1)))
        cond = "две буквы %s не стоят рядом" % x
        expl = "Перебор всех %d^%d слов (или динамика по последней букве) даёт %d." % (len(letters), n, ans)
    return {"text": "Вася составляет %d-буквенные слова, в которых есть только буквы %s, причём каждая буква может "
                    "встречаться в слове любое количество раз или не встречаться совсем. Словом считается любая "
                    "последовательность букв, не обязательно осмысленная. Сколько существует таких слов, в которых "
                    "%s?" % (n, ", ".join(letters), cond),
            "answer": str(ans), "explain": expl}


def e11(r):
    length, alpha = r.randint(8, 20), r.choice([10, 12, 18, 26, 33, 36, 52, 62])
    extra, users = r.randint(0, 20), r.choice([20, 25, 30, 40, 50, 60, 100])
    bits = math.ceil(math.log2(alpha))
    per = math.ceil(length * bits / 8) + extra
    return {"text": "При регистрации в компьютерной системе каждому пользователю выдаётся пароль из %d символов. Для "
                    "пароля используется алфавит из %d различных символов. В базе данных каждый символ кодируется "
                    "одинаковым и минимально возможным количеством бит, а пароль — минимально возможным целым "
                    "количеством байт. Кроме пароля, для каждого пользователя хранятся дополнительные сведения, под "
                    "которые отведено %d байт. Сколько байт нужно для хранения сведений о %d пользователях?"
                    % (length, alpha, extra, users),
            "answer": str(per * users),
            "explain": "На символ ⌈log₂ %d⌉ = %d бит; пароль %d · %d = %d бит → %d байт; на пользователя %d байт; "
                       "всего %d · %d = %d." % (alpha, bits, length, bits, length * bits, per - extra, per, per, users,
                                                 per * users)}


def _digits(x, q):
    out = []
    while x:
        x, d = divmod(x, q)
        out.append(d)
    return out or [0]


def e14(r):
    q = r.choice([3, 4, 5, 6, 7, 8, 9])
    p1, p2 = r.randint(40, 300), r.randint(5, 39)
    sub = r.randint(2, 60)
    val = q ** p1 + q ** p2 - sub
    d = r.choice([0, q - 1])
    ans = _digits(val, q).count(d)
    return {"text": "Значение арифметического выражения **%d^%d + %d^%d − %d** записали в системе счисления с основанием "
                    "%d. Сколько цифр %d содержится в этой записи?" % (q, p1, q, p2, sub, q, d),
            "answer": str(ans),
            "explain": "Переводим число в систему с основанием %d (например, циклом divmod) и считаем цифры %d: %d."
                       % (q, d, ans)}


def e16(r):
    k, a, m = r.randint(2, 5), r.choice([1, 2, 3]), r.randint(15, 40)
    kind = r.choice(["sum", "half"])
    if kind == "half":
        m = r.randint(40, 300)

    @lru_cache(None)
    def f(n):
        if n < k:
            return n if kind == "sum" else 1
        if kind == "sum":
            return n + f(n - a)
        return f(n // 2) + n if n % 2 == 0 else f(n - 1) + 1

    if kind == "sum":
        rule = "F(n) = n при n < %d;\nF(n) = n + F(n − %d) при n ≥ %d." % (k, a, k)
    else:
        rule = ("F(n) = 1 при n < %d;\nF(n) = F(n / 2) + n, если n ≥ %d и n чётное;\n"
                "F(n) = F(n − 1) + 1, если n ≥ %d и n нечётное." % (k, k, k))
    ask = "Чему равно значение F(%d)?" % m
    return {"text": "Алгоритм вычисления значения функции F(n), где n — натуральное число, задан соотношениями:\n\n%s\n\n%s"
                    % (rule, ask), "answer": str(f(m)),
            "explain": "Считаем от малых n к большим (или рекурсией с запоминанием): F(%d) = %d." % (m, f(m))}


def e23(r):
    ops = r.choice([("Прибавить 1", "Умножить на 2"), ("Прибавить 1", "Прибавить 2"), ("Прибавить 1", "Умножить на 3"),
                    ("Прибавить 2", "Умножить на 2")])
    funcs = {"Прибавить 1": lambda x: x + 1, "Прибавить 2": lambda x: x + 2, "Умножить на 2": lambda x: x * 2,
             "Умножить на 3": lambda x: x * 3}
    while True:
        a, b = r.randint(1, 5), r.randint(18, 40)
        must, avoid = r.randint(a + 2, b - 3), r.randint(a + 2, b - 2)
        if must == avoid:
            continue

        @lru_cache(None)
        def ways(x, y, skip):
            if x == y:
                return 1
            if x > y or x == skip:
                return 0
            return sum(ways(funcs[o](x), y, skip) for o in ops)

        ans = ways(a, must, avoid) * ways(must, b, avoid)
        if 0 < ans < 100000:
            break
    return {"text": "Исполнитель преобразует число на экране. У исполнителя есть две команды:\n\n1. %s\n2. %s\n\n"
                    "Программа для исполнителя — это последовательность команд. Сколько существует программ, для которых "
                    "при исходном числе %d результатом является число %d, и при этом траектория вычислений содержит "
                    "число %d и не содержит числа %d?" % (ops[0], ops[1], a, b, must, avoid),
            "answer": str(ans),
            "explain": "Число программ = (из %d в %d, минуя %d) × (из %d в %d, минуя %d); считаем динамикой по числам: %d."
                       % (a, must, avoid, must, b, avoid, ans)}


def _imp(a, b):
    return (not a) or b


# выражение для №2: (вид, число переменных, функция от словаря переменных)
_LOGIC = [
    ("(x ∧ ¬y) ∨ (y ≡ z)", 3, lambda v: (v["x"] and not v["y"]) or (v["y"] == v["z"])),
    ("(x → y) ∧ ¬z", 3, lambda v: _imp(v["x"], v["y"]) and not v["z"]),
    ("¬x ∨ (y ∧ ¬z)", 3, lambda v: (not v["x"]) or (v["y"] and not v["z"])),
    ("(x ≡ ¬y) → z", 3, lambda v: _imp(v["x"] == (not v["y"]), v["z"])),
    ("(x ∨ y) ∧ (y → ¬z)", 3, lambda v: (v["x"] or v["y"]) and _imp(v["y"], not v["z"])),
    ("((x → y) ∧ (y → w)) ∨ (z ≡ x)", 4, lambda v: (_imp(v["x"], v["y"]) and _imp(v["y"], v["w"])) or v["z"] == v["x"]),
    ("¬(x → z) ∨ (y ≡ w) ∨ y", 4, lambda v: (not _imp(v["x"], v["z"])) or v["y"] == v["w"] or v["y"]),
    ("(x ∨ ¬y) ∧ ¬(z ≡ w)", 4, lambda v: (v["x"] or not v["y"]) and v["z"] != v["w"]),
    ("(x ∧ y) ∨ (¬z ∧ w) ∨ ¬x", 4, lambda v: (v["x"] and v["y"]) or ((not v["z"]) and v["w"]) or not v["x"]),
]


def e2(r):
    """Полные строки таблицы истинности со смешанными столбцами: показываем строки, пока соответствие
    «столбец → переменная» не станет единственным (проверяем перебором всех перестановок)."""
    while True:
        expr, k, f = r.choice(_LOGIC)
        names = "xyzw"[:k]
        val = r.choice([0, 1])
        rows = [bits for bits in itertools.product((0, 1), repeat=k) if f(dict(zip(names, bits))) == val]
        r.shuffle(rows)
        perm = list(names)
        r.shuffle(perm)
        shown = []
        for bits in rows:
            assign = dict(zip(names, bits))
            shown.append([assign[c] for c in perm])            # строка в порядке столбцов таблицы
            ok = [q for q in itertools.permutations(names)
                  if all(f(dict(zip(q, row))) == val for row in shown)]
            if len(ok) == 1:
                break
        if len(ok) == 1 and 2 <= len(shown) <= 6:
            break
    answer = "".join(perm)
    table = [["Перем. %d" % (i + 1) for i in range(k)] + ["F"]] + [[str(b) for b in row] + [str(val)] for row in shown]
    return {"text": "Логическая функция F задаётся выражением **%s**. Ниже — фрагмент таблицы истинности функции F, все "
                    "строки в нём различны. Определите, какому столбцу таблицы соответствует каждая из переменных %s.\n\n"
                    "В ответе напишите буквы %s в том порядке, в котором идут соответствующие им столбцы: сначала "
                    "буква, соответствующая первому столбцу, затем — второму и т. д." % (expr, ", ".join(names),
                                                                                       ", ".join(names)),
            "table": table, "answer": answer, "accept": {"kind": "text", "value": answer},
            "explain": "Перебираем все %d %s переменных по столбцам: только при порядке %s каждая строка даёт "
                       "F = %d." % (math.factorial(k), _cnt(math.factorial(k), "расстановку", "расстановки", "расстановок"),
                                    answer, val)}


def e5(r):
    while True:
        kind = r.choice(["parity", "evenodd"])
        x = r.randint(40, 400)
        if kind == "parity":
            def run(n):
                s = bin(n)[2:]
                for _ in range(2):
                    s += str(s.count("1") % 2)
                return int(s, 2)
            rule = ("1. Строится двоичная запись числа N.\n2. К этой записи справа дописывается остаток от деления суммы "
                    "её цифр на 2.\n3. К полученной записи справа дописывается остаток от деления суммы её цифр на 2.\n"
                    "4. Полученная запись — двоичная запись искомого числа R.")
        else:
            def run(n):
                s = bin(n)[2:]
                s = s + "10" if n % 2 == 0 else "1" + s + "01"
                return int(s, 2)
            rule = ("1. Строится двоичная запись числа N.\n2. Если N чётное, к записи справа дописывается 10; если N "
                    "нечётное, к записи слева дописывается 1, а справа — 01.\n3. Полученная запись — двоичная запись "
                    "искомого числа R.")
        res = [(run(n), n) for n in range(1, 1024)]          # R > N, поэтому для X ≤ 400 этого с запасом
        if r.random() < 0.5:
            ans = min(rr for rr, _ in res if rr > x)
            ask = "Укажите минимальное число R, которое превышает %d и может быть результатом работы алгоритма." % x
        else:
            ans = min(n for rr, n in res if rr > x)
            ask = "Укажите минимальное число N, после обработки которого получится число R, большее %d." % x
        break
    return {"text": "На вход алгоритма подаётся натуральное число N. Алгоритм строит по нему новое число R так:\n\n%s\n\n%s"
                    % (rule, ask), "answer": str(ans),
            "explain": "Перебираем N по возрастанию (циклом по N с переводом в двоичную запись) и находим первое "
                       "подходящее значение: %d." % ans}


def _edit(s, rules, steps=20000):
    """Исполнитель Редактор: ПОКА нашлось одно из образцов — заменяет первое вхождение первого найденного по порядку
    ЕСЛИ. Возвращает None, если за steps шагов не остановился."""
    for _ in range(steps):
        for pat, rep in rules:
            if pat in s:
                s = s.replace(pat, rep, 1)
                break
        else:
            return s
    return None


def e12(r):
    while True:
        a, b, c = r.sample("123456789", 3)
        if r.random() < 0.5:
            rules = [(a * 3, b), (b * 3, a)]
            start, n = a, r.randint(25, 90)
        else:
            rules = [(a + b, c), (c + b + b, b + a), (b * 4, a)]
            start, n = a + b, r.randint(20, 80)
        src = (a * n) if len(start) == 1 else (a + b * n)
        out = _edit(src, rules)
        if out:
            break
    lines = ["НАЧАЛО", "ПОКА " + " ИЛИ ".join("нашлось(%s)" % p for p, _ in rules)]
    for i, (p, q) in enumerate(rules):
        if i == len(rules) - 1:
            lines.append("    ИНАЧЕ заменить(%s, %s)" % (p, q))
        else:
            lines += ["    %sЕСЛИ нашлось(%s)" % ("ИНАЧЕ " if i else "", p), "        ТО заменить(%s, %s)" % (p, q)]
    code = "\n".join(lines + ["    КОНЕЦ ЕСЛИ", "КОНЕЦ ПОКА", "КОНЕЦ"])
    if len(start) == 1:
        given = "строка, состоящая из %d %s %s" % (n, _cnt(n, "цифры", "цифр", "цифр"), a)
    else:
        given = "строка из цифры %s и следующих за ней %d %s %s" % (a, n, _cnt(n, "цифры", "цифр", "цифр"), b)
    ask = r.choice(["result", "sum"])
    ans = out if ask == "result" else str(sum(map(int, out)))
    q = "Какая строка получится в результате применения программы?" if ask == "result" else \
        "Чему равна сумма цифр строки, получившейся в результате применения программы?"
    return {"text": "Исполнитель Редактор получает на вход строку цифр и преобразует её. Команда заменить(v, w) "
                    "заменяет в строке первое слева вхождение цепочки v на цепочку w; команда нашлось(v) проверяет, "
                    "встречается ли цепочка v в строке. На вход программе подана %s.\n\n{code}\n\n%s" % (given, q),
            "code": code, "answer": ans,
            "explain": "Выполняем программу (вручную по циклам замен или строкой s.replace(v, w, 1) в цикле): "
                       "получается %s%s." % (out, "" if ask == "result" else ", сумма цифр %s" % ans)}


def _ip(x):
    return ".".join(str(x >> s & 255) for s in (24, 16, 8, 0))


def _mask(k):
    return (0xFFFFFFFF << (32 - k)) & 0xFFFFFFFF if k else 0


def e13(r):
    ip = r.randint(1, 223) << 24 | r.randint(0, 255) << 16 | r.randint(0, 255) << 8 | r.randint(1, 254)
    kind = r.choice(["byte", "count", "ones"])
    if kind == "byte":
        k = r.choice([k for k in range(17, 31) if k % 8])
        idx = k // 8                                           # байт, где маска «рвётся»
        net = ip & _mask(k)
        ans = net >> (24 - 8 * idx) & 255
        return {"text": "Узел имеет IP-адрес %s и маску сети %s. Чему равен %s слева байт адреса сети? Ответ запишите "
                        "десятичным числом." % (_ip(ip), _ip(_mask(k)), ["первый", "второй", "третий", "четвёртый"][idx]),
                "answer": str(ans),
                "explain": "Адрес сети — поразрядная конъюнкция IP-адреса и маски: %d & %d = %d."
                           % (ip >> (24 - 8 * idx) & 255, _mask(k) >> (24 - 8 * idx) & 255, ans)}
    if kind == "count":
        k = r.randint(21, 28)
        net = ip & _mask(k)
        d = r.choice([2, 3])
        rem = r.randrange(d)
        ans = sum(1 for a in range(net, net + 2 ** (32 - k)) if bin(a).count("1") % d == rem)
        cond = "количество единиц в двоичной записи " + ("кратно %d" % d if rem == 0 else
                                                         "при делении на %d даёт остаток %d" % (d, rem))
        return {"text": "Сеть задана IP-адресом одного из её узлов %s и маской %s. Сколько в этой сети IP-адресов, "
                        "у которых %s? В ответе укажите только число." % (_ip(ip), _ip(_mask(k)), cond),
                "answer": str(ans),
                "explain": "Адрес сети %s, в сети 2^%d = %d %s; перебираем их и считаем подходящие: %d."
                           % (_ip(net), 32 - k, 2 ** (32 - k), _cnt(2 ** (32 - k), "адрес", "адреса", "адресов"), ans)}
    k0 = r.randint(18, 29)
    net = ip & _mask(k0)
    fits = [k for k in range(33) if ip & _mask(k) == net]
    most = r.random() < 0.5
    ans = max(fits) if most else min(fits)
    return {"text": "Для узла с IP-адресом %s адрес сети равен %s. Чему равно %s возможное количество единиц в "
                    "двоичной записи маски?" % (_ip(ip), _ip(net), "наибольшее" if most else "наименьшее"),
            "answer": str(ans),
            "explain": "Маска — k единиц, затем нули. Подходят k, при которых IP & маска = адрес сети: от %d до %d; "
                       "ответ %d." % (min(fits), max(fits), ans)}


def e15(r):
    kind = r.choice(["bits", "div", "seg"])
    if kind == "bits":
        while True:
            a, b = r.randint(5, 63), r.randint(5, 63)
            ans = min(x for x in range(64) if all(_imp(t & a != 0, _imp(t & b == 0, t & x != 0)) for t in range(64)))
            if ans:
                break
        return {"text": "Обозначим через m & n поразрядную конъюнкцию неотрицательных целых чисел m и n. Для какого "
                        "наименьшего неотрицательного целого числа А формула\n\n**(x & %d ≠ 0) → ((x & %d = 0) → "
                        "(x & А ≠ 0))**\n\nтождественно истинна, то есть принимает значение 1 при любом неотрицательном "
                        "целом x?" % (a, b), "answer": str(ans),
                "explain": "Формула ложна только при x & %d ≠ 0, x & %d = 0, x & А = 0. Значит, А должно содержать все "
                           "биты числа %d, которых нет в %d: А = %d & ¬%d = %d." % (a, b, a, b, a, b, ans)}
    if kind == "div":
        p, q = r.sample([2, 3, 4, 5, 6, 8, 9, 10, 12, 14, 15, 16, 18, 20, 21, 24], 2)
        ans = p * q // math.gcd(p, q)
        return {"text": "Обозначим через ДЕЛ(n, m) утверждение «натуральное число n делится без остатка на натуральное "
                        "число m». Для какого наибольшего натурального числа А формула\n\n**(ДЕЛ(x, %d) ∧ ДЕЛ(x, %d)) → "
                        "ДЕЛ(x, А)**\n\nтождественно истинна, то есть принимает значение 1 при любом натуральном x?"
                        % (p, q), "answer": str(ans),
                "explain": "Посылка истинна для чисел, кратных НОК(%d, %d) = %d; все они должны делиться на А. "
                           "Наибольшее такое А — сам НОК: %d." % (p, q, ans, ans)}
    while True:
        p1, q1 = r.randint(5, 40), r.randint(5, 40)
        p2, q2 = p1 + r.randint(10, 40), q1 + r.randint(10, 40)
        lo, hi = max(p1, q1), min(p2, q2)
        if hi - lo >= 2:
            break
    form = r.choice(["((x ∈ P) ∧ (x ∈ Q)) → (x ∈ A)", "¬(x ∈ A) → (¬(x ∈ P) ∨ ¬(x ∈ Q))",
                     "(x ∈ P) → ((x ∈ Q) → (x ∈ A))"])
    return {"text": "На числовой прямой даны два отрезка: P = [%d; %d] и Q = [%d; %d]. Укажите наименьшую возможную длину "
                    "такого отрезка A, что формула\n\n**%s**\n\nистинна при любом значении переменной x."
                    % (p1, p2, q1, q2, form), "answer": str(hi - lo),
            "explain": "Формула означает: «если x лежит и в P, и в Q, то x лежит в A». Значит, A должен "
                       "покрывать пересечение P ∩ Q = [%d; %d], его длина %d." % (lo, hi, hi - lo)}


EGE = Bank("ege-inf", {2: e2, 5: e5, 7: e7, 8: e8, 11: e11, 12: e12, 13: e13, 14: e14, 15: e15, 16: e16, 23: e23},
           {2: "Таблицы истинности", 5: "Алгоритм с двоичной записью", 7: "Кодирование изображений и звука",
            8: "Комбинаторика", 11: "Объём информации", 12: "Исполнитель Редактор", 13: "IP-адреса и маски",
            14: "Системы счисления", 15: "Логические формулы", 16: "Рекурсия", 23: "Исполнитель: число программ"})
