"""Свои варианты ЕГЭ по информатике для umedu 2.0: номера 7, 8, 11, 14, 16, 23 — формат, устойчивый в КИМ.

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


EGE = Bank("ege-inf", {7: e7, 8: e8, 11: e11, 14: e14, 16: e16, 23: e23},
           {7: "Кодирование изображений и звука", 8: "Комбинаторика", 11: "Объём информации",
            14: "Системы счисления", 16: "Рекурсия", 23: "Исполнитель: число программ"})
