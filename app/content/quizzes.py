"""Квизы «Что выведет код?» — для задачи дня.

Правильный ответ не хранится вручную: он вычисляется запуском кода при старте,
поэтому ошибиться в ответе невозможно.
"""
import contextlib
import io

_RAW = [
    # (урок, код, пояснение)
    (1, 'print(2 + 3 * 4)', "Сначала умножение, потом сложение — как в математике."),
    (1, 'print("2" + "3")', "Строки склеиваются, а не складываются."),
    (1, 'print("ха" * 3)', "Строку можно умножить на число — она повторится."),
    (1, 'x = 5\nx = x + 2\nprint(x)', "x = x + 2 берёт старое значение и прибавляет 2."),
    (2, 'print(17 // 5, 17 % 5)', "// — целая часть от деления, % — остаток."),
    (2, 'print(7 / 2)', "Обычное деление / всегда даёт дробное число (float)."),
    (2, 'print(10 % 3 + 10 // 3)', "10 % 3 = 1, 10 // 3 = 3."),
    (2, 'a = 3\nb = a\na = 10\nprint(b)', "b получила значение 3 и не меняется, когда меняется a."),
    (2, 'print(type(3.0).__name__)', "3.0 — дробное число, тип float."),
    (4, 'for i in range(3):\n    print(i)', "range(3) — это 0, 1, 2. Тройка не входит!"),
    (4, 'total = 0\nfor i in range(1, 5):\n    total += i\nprint(total)', "1 + 2 + 3 + 4."),
    (4, 'for i in range(10, 0, -3):\n    print(i, end=" ")', "Начинаем с 10 и шагаем по -3, пока больше 0."),
    (4, 'count = 0\nfor i in range(3):\n    for j in range(4):\n        count += 1\nprint(count)', "Вложенный цикл: 3 раза по 4."),
    (5, 'def f(x):\n    return x * x\nprint(f(3) + f(2))', "9 + 4."),
    (5, 'def hello(name="мир"):\n    return "Привет, " + name\nprint(hello())', "Если аргумент не передан, берётся значение по умолчанию."),
    (5, 'def f(a, b):\n    return a - b\nprint(f(b=1, a=10))', "Аргументы переданы по имени — порядок не важен."),
    (7, 'x = 7\nif x > 5:\n    print("A")\nelif x > 3:\n    print("B")\nelse:\n    print("C")', "Срабатывает первое подходящее условие, остальные пропускаются."),
    (7, 'print(3 > 2 and 2 > 5)', "and — истина, только если оба условия истинны."),
    (7, 'print(not (5 == 5) or 1 < 2)', "not True — это False, но 1 < 2 — True, а or нужно хотя бы одно."),
    (7, 'x = 0\nif x:\n    print("да")\nelse:\n    print("нет")', "Ноль в условии считается ложью."),
    (8, 'n = 1\nwhile n < 50:\n    n *= 2\nprint(n)', "1, 2, 4, 8, 16, 32, 64 — останавливаемся, когда стало ≥ 50."),
    (8, 'i = 0\nwhile True:\n    i += 3\n    if i > 10:\n        break\nprint(i)', "break выходит из цикла."),
    (8, 'n = 1234\ns = 0\nwhile n > 0:\n    s += n % 10\n    n //= 10\nprint(s)', "Сумма цифр числа."),
    (9, 'beats = {"камень": "ножницы", "ножницы": "бумага"}\nprint(beats["камень"])', "По ключу «камень» лежит «ножницы»."),
    (10, 'a = [3, 1, 2]\na.append(5)\nprint(len(a), a[-1])', "После append в списке 4 элемента, последний — 5."),
    (10, 'lst = ["a", "b", "c", "d"]\nprint(lst[1], lst[-2])', "Индексы с 0; -2 — второй с конца."),
    (10, 'print(3 in [1, 2, 3], "x" in ["xy"])', "in ищет элемент целиком: «x» не равно «xy»."),
    (10, 'a = [1, 2]\nb = a\nb.append(3)\nprint(a)', "a и b — один и тот же список!"),
    (13, 's = "Python"\nprint(s[0] + s[-1])', "Первая и последняя буквы."),
    (13, 'print("кот"[::-1])', "Срез [::-1] переворачивает строку."),
    (13, 'print("привет мир".title())', "title() делает каждое слово с большой буквы."),
    (13, 'print("a,b,,c".split(","))', "Между двумя запятыми — пустая строка."),
    (13, 's = "программирование"\nprint(s[3:7])', "Срез с 3 по 6 включительно (7 не входит)."),
    (14, 'print(ord("A"), chr(66))', "У каждого символа есть номер в таблице Unicode."),
    (15, 'print(sorted([3, 1, 2], reverse=True))', "Сортировка по убыванию."),
    (15, 'print(sum([1, 2, 3]) / len([1, 2, 3]))', "Среднее арифметическое — это float."),
    (15, 'for i, x in enumerate(["a", "b"], 1):\n    print(i, x)', "enumerate нумерует элементы, начиная с указанного числа."),
    (15, 'print([x * 2 for x in range(4)])', "Генератор списка: каждый x умножаем на 2."),
    (15, 'print(len(set([1, 1, 2, 3, 3, 3])))', "Множество хранит только уникальные значения."),
    (16, 'd = {"a": 1}\nd["b"] = 2\nd["a"] += 10\nprint(d)', "Можно добавлять ключи и менять значения."),
    (16, 'd = {"x": 1}\nprint(d.get("y", 0))', "get возвращает значение по умолчанию, если ключа нет."),
    (16, 'd = {"a": 3, "b": 1}\nfor k, v in d.items():\n    print(k * v, end=" ")', "Строка, умноженная на число, повторяется."),
    (17, 'import json\nprint(json.loads("[1, 2, 3]")[1])', "JSON превращается в обычный список Python."),
    (4, 'points = 0\nfor shot in [2, 3, 2, 1]:\n    points += shot\nprint(points)', "Складываем очки всех бросков: 2 + 3 + 2 + 1."),
    (7, 'trophies = 4\ntrophies -= 6\nif trophies < 0:\n    trophies = 0\nprint(trophies)', "Трофеев не бывает меньше нуля."),
    (10, 'team = ["Питоша", "Тёртл"]\nteam.append("Шифро")\nprint(team[-1], len(team))', "append добавляет бойца в конец команды."),
    (16, 'score = {"Ракеты": 0, "Тигры": 0}\nscore["Ракеты"] += 3\nscore["Тигры"] += 2\nscore["Ракеты"] += 2\nprint(score["Ракеты"] - score["Тигры"])', "Ракеты 5, Тигры 2."),
    (23, 'class A:\n    def __init__(self):\n        self.n = 1\n    def inc(self):\n        self.n += 1\na = A()\na.inc()\na.inc()\nprint(a.n)', "Каждый inc увеличивает поле n объекта."),
    (23, 'class Animal:\n    def sound(self):\n        return "..."\nclass Cat(Animal):\n    def sound(self):\n        return "мяу"\nprint(Cat().sound(), Animal().sound())', "Наследник переопределил метод."),
]


def _run(code):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(code, {})
    return buf.getvalue().rstrip()


QUIZZES = []
for i, (lesson, code, why) in enumerate(_RAW, 1):
    QUIZZES.append({"id": "q%d" % i, "lesson": lesson, "code": code, "why": why, "answer": _run(code)})

QUIZ_BY_ID = {q["id"]: q for q in QUIZZES}


def normalize_answer(text):
    """Сравниваем ответы без учёта лишних пробелов по краям строк и пустых строк в конце."""
    lines = [ln.strip() for ln in str(text).replace("\r\n", "\n").strip().split("\n")]
    return "\n".join(" ".join(ln.split()) for ln in lines)
