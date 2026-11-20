"""Рантайм КодКвеста: запуск кода ученика, понятные ошибки по-русски, автопроверка задач.

Работает одинаково в браузере (Pyodide) и в обычном Python (для тестов сайта).
"""
import builtins
import io
import json
import math
import re
import sys
import traceback

import turtle as _turtle

FILENAME = "main.py"
MAX_OUTPUT = 100_000


# ---------------------------------------------------------------- ошибки по-русски
def _explain(exc):
    """Короткая подсказка на русском для частых ошибок новичков."""
    name = type(exc).__name__
    msg = str(exc)
    if isinstance(exc, KeyboardInterrupt):
        return "Программа остановлена. Если ты её не останавливал — возможно, получился бесконечный цикл."
    if isinstance(exc, IndentationError):
        if "expected an indented block" in msg:
            return "После строки с двоеточием (if, for, while, def…) нужен отступ — 4 пробела в начале следующей строки."
        if "unexpected indent" in msg:
            return "Лишний отступ: эта строка сдвинута вправо, хотя не должна."
        if "unindent does not match" in msg:
            return "Отступы не совпадают: проверь, что строки внутри одного блока начинаются на одном уровне."
        return "Проблема с отступами (пробелами в начале строк)."
    if isinstance(exc, SyntaxError):
        if "was never closed" in msg or "EOF" in msg:
            return "Не закрыта скобка или кавычка. Посчитай: каждой ( нужна ), каждой \" нужна \"."
        if "unterminated string" in msg:
            return "Строка не закрыта: не хватает кавычки в конце."
        if "invalid character" in msg:
            return "В коде есть странный символ — может, русская буква или «ёлочки» вместо обычных кавычек?"
        if "expected ':'" in msg:
            return "Забыто двоеточие ':' в конце строки с if / for / while / def / else."
        if "'=' " in msg or "Maybe you meant '==' " in msg or "cannot assign" in msg:
            return "Для сравнения нужно '==', а один '=' — это присваивание."
        if "invalid syntax" in msg:
            return "Python не понял строку. Проверь скобки, кавычки, двоеточия и запятые."
        return "Ошибка в записи кода — Python не может его прочитать."
    if isinstance(exc, NameError):
        m = re.search(r"name '(\w+)' is not defined", msg)
        if m:
            n = m.group(1)
            hints = {"prnt": "print", "pirnt": "print", "Print": "print", "imput": "input", "Input": "input",
                     "ture": "True", "true": "True", "false": "False", "Range": "range", "lenght": "len"}
            if n in hints:
                return "Python не знает слово '%s'. Наверное, ты имел в виду '%s'." % (n, hints[n])
            return ("Python не знает имя '%s'. Возможно, опечатка, переменная ещё не создана, "
                    "или забыты кавычки вокруг текста." % n)
        return "Используется имя, которое Python не знает."
    if isinstance(exc, ZeroDivisionError):
        return "Деление на ноль! Так нельзя даже в Python."
    if isinstance(exc, TypeError):
        if "can only concatenate str" in msg or "unsupported operand type(s) for +: 'int' and 'str'" in msg:
            return "Нельзя сложить текст и число. Преобразуй: str(число) — в текст, int(текст) — в число."
        if "not supported between instances of 'str' and 'int'" in msg:
            return "Сравниваешь текст с числом. Наверное, забыл int() вокруг input()."
        if "takes" in msg and "positional argument" in msg:
            return "Функции передано не то количество аргументов, которое она ожидает."
        if "not callable" in msg:
            return "Пытаешься вызвать как функцию (со скобками) то, что функцией не является."
        if "object is not subscriptable" in msg:
            return "Квадратные скобки [] можно использовать только у списков, строк и словарей."
        if "object is not iterable" in msg:
            return "По этому значению нельзя пройти циклом for. Может, нужен range(...)?"
        return "Операция с неподходящим типом данных (например, текст вместо числа)."
    if isinstance(exc, ValueError):
        if "invalid literal for int()" in msg:
            return "int() не может превратить этот текст в число. Проверь, что ввод — именно целое число."
        if "could not convert string to float" in msg:
            return "float() не может превратить этот текст в число."
        return "Неподходящее значение."
    if isinstance(exc, IndexError):
        return "Номер элемента вне списка/строки. Помни: нумерация с 0, а последний индекс — len(...) - 1."
    if isinstance(exc, KeyError):
        return "В словаре нет такого ключа: %s." % msg
    if isinstance(exc, AttributeError):
        return "У этого объекта нет такого метода или свойства. Проверь написание после точки."
    if isinstance(exc, RecursionError):
        return "Функция вызывает сама себя бесконечно."
    if isinstance(exc, EOFError):
        return "Программа ждёт ввода (input), но данные закончились."
    if isinstance(exc, ModuleNotFoundError):
        return "Такой библиотеки нет в браузерном Python. pygame и подобное запускай на компьютере (Thonny/VS Code)."
    if isinstance(exc, AssertionError):
        return "Проверка assert не прошла."
    if isinstance(exc, _turtle.TurtleGraphicsError):
        return str(exc)
    return "Ошибка %s." % name


def format_error(exc):
    """Возвращает dict: тип, сообщение, строка, подсказка, укороченный traceback."""
    tb = traceback.extract_tb(exc.__traceback__)
    user_frames = [f for f in tb if f.filename == FILENAME]
    line = None
    if isinstance(exc, SyntaxError) and exc.filename == FILENAME:
        line = exc.lineno
    elif user_frames:
        line = user_frames[-1].lineno
    lines = ["Traceback (most recent call last):"]
    for f in user_frames:
        lines.append('  File "%s", line %d, in %s' % (f.filename, f.lineno, f.name))
        if f.line:
            lines.append("    " + f.line.strip())
    if isinstance(exc, SyntaxError):
        lines = ['  File "%s", line %s' % (FILENAME, exc.lineno)]
        if exc.text:
            lines.append("    " + exc.text.rstrip())
    lines.append("%s: %s" % (type(exc).__name__, exc) if str(exc) else type(exc).__name__)
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "line": line,
        "hint": _explain(exc),
        "traceback": "\n".join(lines),
    }


# ---------------------------------------------------------------- запуск
def prepare():
    """Сбрасывает состояние перед запуском (черепашка, модуль __main__)."""
    _turtle._reset()


def run(code):
    """Интерактивный запуск (ввод/вывод уже подключены браузером). Возвращает JSON."""
    prepare()
    ns = {"__name__": "__main__", "__builtins__": builtins}
    error = None
    try:
        exec(compile(code, FILENAME, "exec"), ns)
    except SystemExit:
        pass
    except BaseException as e:  # noqa: BLE001 — показываем ученику любую ошибку
        error = format_error(e)
    finally:
        try:
            sys.stdout.flush()
        except Exception:
            pass
        _turtle._flush()
    return json.dumps({"error": error}, ensure_ascii=False)


class _Capture(io.StringIO):
    def write(self, s):
        if self.tell() > MAX_OUTPUT:
            raise RuntimeError("Слишком много вывода — возможно, бесконечный цикл с print.")
        return super().write(s)


def _exec_captured(code, stdin_text):
    """Выполняет код с подставленным вводом. Возвращает (namespace, stdout, error|None)."""
    prepare()
    lines = stdin_text.split("\n") if stdin_text else []
    if lines and lines[-1] == "":
        lines.pop()
    feed = iter(lines)

    def fake_input(prompt=""):
        try:
            return next(feed)
        except StopIteration:
            raise EOFError("input() вызван больше раз, чем есть входных данных") from None

    out = _Capture()
    ns = {"__name__": "__main__", "__builtins__": builtins}
    old_input, old_stdout = builtins.input, sys.stdout
    builtins.input = fake_input
    sys.stdout = out
    error = None
    try:
        exec(compile(code, FILENAME, "exec"), ns)
    except SystemExit:
        pass
    except BaseException as e:  # noqa: BLE001
        if isinstance(e, KeyboardInterrupt):
            error = format_error(e)
            error["hint"] = "Время вышло: программа работала слишком долго. Возможно, бесконечный цикл."
        else:
            error = format_error(e)
    finally:
        builtins.input = old_input
        sys.stdout = old_stdout
    return ns, out.getvalue(), error


def _norm(text):
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _short(text, limit=300):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "…"


def _equal(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-6)
        except TypeError:
            return False
    return a == b


def check(code, tests_json):
    """Проверяет решение. tests_json — JSON со списком тестов:

    {"stdin": "...", "stdout": "..."}            — сравнение вывода (опц. "contains": true)
    {"call": "f(2)", "expect": "4"}              — вызов функции из решения
    {"assert": "...python...", "msg": "..."}      — произвольная проверка (доступны _out и turtle)
    Для call/assert можно задать общий ввод полем "stdin" у теста.
    """
    tests = json.loads(tests_json) if isinstance(tests_json, str) else tests_json
    results = []
    shared = {}  # кэш выполнения для call/assert с одинаковым вводом

    for i, t in enumerate(tests, 1):
        name = t.get("name") or "Тест %d" % i
        hidden = bool(t.get("hidden"))
        res = {"name": name, "ok": False, "detail": "", "hidden": hidden}
        if "stdout" in t:
            ns, out, err = _exec_captured(code, t.get("stdin", ""))
            if err:
                res["detail"] = "Ошибка: %s — %s" % (err["type"], err["hint"])
                res["error"] = err
            else:
                exp, got = _norm(t["stdout"]), _norm(out)
                if t.get("contains"):
                    ok = exp.lower() in got.lower()
                else:
                    ok = exp == got
                res["ok"] = ok
                if not ok:
                    res["detail"] = "Ввод: %s\nОжидался вывод:\n%s\nПолучено:\n%s" % (
                        _short(t.get("stdin", "") or "(пусто)"), _short(exp), _short(got or "(ничего)"))
        else:
            key = t.get("stdin", "")
            if key not in shared:
                shared[key] = _exec_captured(code, key)
            ns, out, err = shared[key]
            if err:
                res["detail"] = "Ошибка при запуске: %s — %s" % (err["type"], err["hint"])
                res["error"] = err
            elif "call" in t:
                try:
                    old_stdout = sys.stdout
                    sys.stdout = _Capture()
                    try:
                        got = eval(t["call"], ns)
                    finally:
                        sys.stdout = old_stdout
                    exp = eval(t["expect"], {})
                    res["ok"] = _equal(got, exp)
                    if not res["ok"]:
                        res["detail"] = "%s → ожидалось %s, получено %s" % (t["call"], t["expect"], _short(repr(got)))
                except BaseException as e:  # noqa: BLE001
                    err = format_error(e)
                    res["detail"] = "%s → ошибка %s: %s" % (t["call"], err["type"], err["hint"])
            elif "assert" in t:
                env = dict(ns)
                env.update({"_out": out, "_norm": _norm, "_code": code, "turtle": _turtle, "math": math})
                try:
                    exec(t["assert"], env)
                    res["ok"] = True
                except AssertionError:
                    res["detail"] = t.get("msg", "Проверка не прошла")
                except BaseException as e:  # noqa: BLE001
                    err = format_error(e)
                    res["detail"] = t.get("msg") or ("Ошибка проверки: %s" % err["hint"])
        if hidden and not res["ok"]:
            res["detail"] = "Скрытый тест не пройден. Проверь крайние случаи (0, отрицательные числа, пустой ввод…)."
        results.append(res)

    _turtle._ops = []  # при проверке рисунок не анимируем
    return json.dumps({"passed": all(r["ok"] for r in results) and bool(results), "results": results},
                      ensure_ascii=False)
