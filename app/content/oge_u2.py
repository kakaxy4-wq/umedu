"""Генераторы ОГЭ по информатике, которые нужны только umedu 2.0: №11 и №14.

В старый тренажёр /oge/drill они не входят: там по-прежнему номера из oge_gen.GENERATORS.
№11 — поиск по короткому тексту (на экзамене ищут в файлах, здесь тот же навык на абзаце).
№14 — небольшая таблица и формула, ответ считает программа.
"""
import random
import re

from .solve_steps import ensure

_NAMES = ["Аня", "Боря", "Вера", "Глеб", "Даша", "Егор", "Зоя", "Кирилл"]
_FEMALE = {"Аня", "Вера", "Даша", "Зоя"}
# именительный ед. / родительный ед. (2–4) / родительный мн. — в винительном для «купил»
_GOODS = {
    "тетрадь": ("тетрадь", "тетради", "тетрадей"),
    "яблоко": ("яблоко", "яблока", "яблок"),
    "марка": ("марку", "марки", "марок"),
    "открытка": ("открытку", "открытки", "открыток"),
    "карандаш": ("карандаш", "карандаша", "карандашей"),
}
_SHOPS = ["Север", "Юг", "Мост"]


def _bought(name):
    return "купила" if name in _FEMALE else "купил"


def _noun(n, forms):
    n_abs = abs(int(n))
    tail, hundred = n_abs % 10, n_abs % 100
    if tail == 1 and hundred != 11:
        return forms[0]
    if 2 <= tail <= 4 and not 12 <= hundred <= 14:
        return forms[1]
    return forms[2]


def _finish(v, num, seed):
    v.update({"num": num, "seed": seed})
    ensure(v)
    return v


def g11(r):
    """Абзац из шаблонных фраз. Вопрос: сколько раз имя, какое число после имени или наибольшее число."""
    sentences = []
    bag = []                                              # (имя, число, товар) в порядке текста
    for _ in range(r.randint(6, 9)):
        name, n, forms = r.choice(_NAMES), r.randint(3, 40), r.choice(list(_GOODS.values()))
        word = _noun(n, forms)
        sentences.append("%s %s %d %s." % (name, _bought(name), n, word))
        bag.append((name, n, word))
    text_body = " ".join(sentences)
    kind = r.choice(["count", "after", "max"])
    if kind == "count":
        name = r.choice(_NAMES)
        ans = sum(1 for w in re.findall(r"[А-Яа-яЁё]+|\d+", text_body) if w == name)
        ask = "Сколько раз в тексте встречается имя «%s»?" % name
        expl = "Имя «%s» встречается %d раз." % (name, ans)
        steps = ["Ищи имя как отдельное слово, не внутри другого.",
                 "Пройди текст слева направо и отметь каждое «%s»." % name,
                 "Всего %d." % ans]
        data = {"kind": "count", "name": name, "body": text_body}
    elif kind == "after":
        # первое вхождение имени, у которого есть покупка — оно всегда есть, раз имя из bag
        name = r.choice([b[0] for b in bag])
        ans = next(n for who, n, _ in bag if who == name)
        verb = _bought(name)
        ask = "Какое число %s человек при первом упоминании имени «%s»?" % (verb, name)
        expl = "Первая покупка %s — %d." % (name, ans)
        steps = ["Найди первое «%s» в тексте." % name, "Число стоит сразу после слова «%s»." % verb, "Это %d." % ans]
        data = {"kind": "after", "name": name, "body": text_body}
    else:
        ans = max(n for _, n, _ in bag)
        ask = "Какое наибольшее число записано в тексте?"
        expl = "Самое большое из чисел — %d." % ans
        steps = ["Выпиши все числа из текста.", "Сравни их.", "Наибольшее — %d." % ans]
        data = {"kind": "max", "body": text_body}
    text = "Прочитай текст и ответь на вопрос. Ответ — число.\n\n%s\n\n%s" % (text_body, ask)
    return {"text": text, "answer": str(ans), "explain": expl, "steps": steps, "data": data}


def g14(r):
    """10–16 строк покупок. Сумма по магазину, количество дороже порога или максимум цены."""
    n = r.randint(10, 16)
    rows = []
    for i in range(n):
        rows.append((r.choice(list(_GOODS)), r.choice(_SHOPS), r.randint(20, 400)))
    kind = r.choice(["sum", "count", "max"])
    header = ["Товар", "Магазин", "Цена, руб."]
    table = [header] + [[a, b, str(c)] for a, b, c in rows]
    if kind == "sum":
        shop = r.choice(_SHOPS)
        ans = sum(c for _, b, c in rows if b == shop)
        ask = "Чему равна сумма цен товаров из магазина «%s»? Ответ дай в рублях." % shop
        expl = "Складываем цены, где магазин «%s»: %d." % (shop, ans)
        steps = ["Оставь строки магазина «%s»." % shop, "Сложи числа в столбце «Цена».", "Сумма %d." % ans]
        data = {"kind": "sum", "shop": shop, "rows": rows}
    elif kind == "count":
        limit = r.choice([100, 150, 200, 250])
        ans = sum(1 for _, _, c in rows if c >= limit)
        ask = "Сколько товаров стоят не меньше %d руб.?" % limit
        expl = "Таких строк %d." % ans
        steps = ["Смотри только столбец цены.", "Считай строки, где цена ≥ %d." % limit, "Их %d." % ans]
        data = {"kind": "count", "limit": limit, "rows": rows}
    else:
        good = r.choice(list(_GOODS))
        prices = [c for a, _, c in rows if a == good]
        if not prices:                                    # редкий промах — добавим строку
            rows.append((good, r.choice(_SHOPS), r.randint(20, 400)))
            table.append([good, rows[-1][1], str(rows[-1][2])])
            prices = [rows[-1][2]]
        ans = max(prices)
        ask = "Какова наибольшая цена товара «%s»? Ответ дай в рублях." % good
        expl = "Максимум в строках «%s» — %d." % (good, ans)
        steps = ["Оставь строки с товаром «%s»." % good, "Выбери наибольшую цену.", "Это %d." % ans]
        data = {"kind": "max", "good": good, "rows": rows}
    text = "В таблице покупки за неделю. %s" % ask
    return {"text": text, "answer": str(ans), "explain": expl, "steps": steps, "data": data, "table": table}


def g13(r):
    """Структура презентации или размер текста. На экзамене это файл, здесь тот же счёт."""
    kind = r.choice(["bullets", "bytes", "slides"])
    if kind == "bullets":
        n, k = r.randint(3, 12), r.randint(2, 6)
        ans = n * k
        text = ("Презентация: один титульный слайд без пунктов и %d слайдов с текстом. На каждом текстовом слайде "
                "ровно %d пункта. Сколько пунктов во всей презентации?" % (n, k))
        expl = "%d · %d = %d. Титульный слайд пунктов не добавляет." % (n, k, ans)
        steps = ["Титульный слайд в сумму пунктов не входит.", "Умножь число текстовых слайдов на число пунктов.",
                 "Получается %d." % ans]
        data = {"kind": "bullets", "n": n, "k": k}
    elif kind == "bytes":
        chars, b = r.choice([80, 100, 120, 150, 200, 250]), r.choice([1, 2])
        ans = chars * b
        text = ("Текст документа без служебного заголовка — %d символов. Каждый символ кодируется %d байтами. "
                "Каков размер текста в байтах?" % (chars, b))
        expl = "%d · %d = %d байт." % (chars, b, ans)
        steps = ["Заголовка файла в условии нет.", "Умножь число символов на число байт на символ.", expl]
        data = {"kind": "bytes", "chars": chars, "b": b}
    else:
        content = r.randint(4, 16)
        ans = content + 1
        text = ("В презентации есть титульный слайд и ещё %d слайдов с содержанием. Сколько слайдов всего?" % content)
        expl = "1 + %d = %d." % (content, ans)
        steps = ["Титульный слайд тоже считается.", "Прибавь его к остальным.", expl]
        data = {"kind": "slides", "content": content}
    return {"text": text, "answer": str(ans), "explain": expl, "steps": steps, "data": data}


GENERATORS = {11: g11, 13: g13, 14: g14}


def make(num, seed):
    v = GENERATORS[num](random.Random("oge-inf-u2-%d-%d" % (num, seed)))
    return _finish(v, num, seed)


def public(v):
    return {k: v[k] for k in ("num", "seed", "text", "table", "code", "svg") if k in v}
