"""Исполнитель «Робот» для задания 15 ОГЭ — команды как в КуМире, только на Python.

Поле задаёт сервер (app/content/robot.py): {"w", "h", "walls": [[x, y, "r"|"d"], ...], "start": [x, y],
"target": [[x, y], ...]}. Стена "r" — справа от клетки (x, y), "d" — снизу. x растёт вправо, y — вниз.
На экзамене поле бесконечное: за краем нарисованной части стен нет, но уход за край — ошибка
(значит, Робот ушёл бы бесконечно далеко).

Работает одинаково в браузере (Pyodide) и в обычном Python (тесты сайта).
"""
import builtins
import io
import json
import sys

import cq_runtime

MAX_STEPS = 20_000      # движения и проверки; больше — почти наверняка бесконечный цикл
MAX_OPS = 3_000         # сколько шагов отдаём странице для анимации


class RobotCrash(Exception):
    """Робот разбился о стену или ушёл за край поля."""


class _Robot:
    def __init__(self, field):
        self.w, self.h = field["w"], field["h"]
        self.walls = set()
        for x, y, side in field["walls"]:
            if side == "r":
                self.walls.add(((x, y), (x + 1, y)))
            else:
                self.walls.add(((x, y), (x, y + 1)))
        self.x, self.y = field["start"]
        self.painted = set()
        self.ops = []
        self.steps = 0

    def _blocked(self, dx, dy):
        a, b = (self.x, self.y), (self.x + dx, self.y + dy)
        return (a, b) in self.walls or (b, a) in self.walls

    def _tick(self):
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise RobotCrash("Робот сделал больше %d действий — похоже на бесконечный цикл. "
                             "Проверь условие в while: оно когда-нибудь станет ложным?" % MAX_STEPS)

    def _op(self, *op):
        if len(self.ops) < MAX_OPS:
            self.ops.append(list(op))

    def move(self, dx, dy, word):
        self._tick()
        if self._blocked(dx, dy):
            self._op("crash", self.x, self.y, dx, dy)
            raise RobotCrash("Робот врезался в стену, выполняя «%s()». Перед шагом проверь, свободно ли там." % word)
        nx, ny = self.x + dx, self.y + dy
        if not (0 <= nx < self.w and 0 <= ny < self.h):
            self._op("crash", self.x, self.y, dx, dy)
            raise RobotCrash("Робот ушёл далеко от стен, выполняя «%s()». На экзамене поле бесконечное — "
                             "Робот шёл бы вечно. Проверь, когда должен остановиться цикл." % word)
        self.x, self.y = nx, ny
        self._op("m", nx, ny)

    def free(self, dx, dy):
        self._tick()
        return not self._blocked(dx, dy)

    def paint(self):
        self._tick()
        self.painted.add((self.x, self.y))
        self._op("p", self.x, self.y)


_r = None


def вверх(): _r.move(0, -1, "вверх")
def вниз(): _r.move(0, 1, "вниз")
def влево(): _r.move(-1, 0, "влево")
def вправо(): _r.move(1, 0, "вправо")
def закрасить(): _r.paint()
def сверху_свободно(): return _r.free(0, -1)
def снизу_свободно(): return _r.free(0, 1)
def слева_свободно(): return _r.free(-1, 0)
def справа_свободно(): return _r.free(1, 0)
def сверху_стена(): return not _r.free(0, -1)
def снизу_стена(): return not _r.free(0, 1)
def слева_стена(): return not _r.free(-1, 0)
def справа_стена(): return not _r.free(1, 0)


def клетка_закрашена():
    _r._tick()
    return (_r.x, _r.y) in _r.painted


COMMANDS = {f.__name__: f for f in (вверх, вниз, влево, вправо, закрасить, сверху_свободно, снизу_свободно,
                                    слева_свободно, справа_свободно, сверху_стена, снизу_стена, слева_стена,
                                    справа_стена, клетка_закрашена)}


def run_field(code, field):
    """Выполняет программу на одном поле. Возвращает dict с итогом и шагами для анимации."""
    global _r
    _r = _Robot(field)
    ns = {"__name__": "__main__", "__builtins__": builtins}
    ns.update(COMMANDS)
    old_stdout, old_input = sys.stdout, builtins.input
    sys.stdout = cq_runtime._Capture()

    def no_input(prompt=""):
        raise EOFError("Роботу ничего не вводят: убери input() — длины стен программа узнаёт сама, проверками.")

    builtins.input = no_input
    error = None
    try:
        exec(compile(code, cq_runtime.FILENAME, "exec"), ns)
    except SystemExit:
        pass
    except RobotCrash as e:
        error = cq_runtime.format_error(e)
        error["type"] = "Авария"
        error["hint"] = str(e)
    except BaseException as e:  # noqa: BLE001 — показываем ученику любую ошибку
        error = cq_runtime.format_error(e)
        if isinstance(e, KeyboardInterrupt):
            error["hint"] = "Время вышло: программа работала слишком долго. Возможно, бесконечный цикл."
    finally:
        sys.stdout, builtins.input = old_stdout, old_input
    target = {tuple(c) for c in field["target"]}
    missing, extra = target - _r.painted, _r.painted - target
    return {"ok": error is None and not missing and not extra, "error": error,
            "missing": sorted(missing), "extra": sorted(extra), "ops": _r.ops,
            "steps": _r.steps, "end": [_r.x, _r.y]}


def run_all(code, fields_json):
    """Проверяет программу на всех полях. Анимация — у первого поля и у первого непройденного."""
    fields = json.loads(fields_json) if isinstance(fields_json, str) else fields_json
    results = []
    shown_fail = False
    for i, f in enumerate(fields):
        r = run_field(code, f)
        if i > 0 and (r["ok"] or shown_fail):
            r["ops"] = None
        if not r["ok"] and i > 0:
            shown_fail = True
        results.append(r)
        if r["error"] and r["error"]["type"] == "KeyboardInterrupt":
            break           # остановили по времени — на остальных полях будет то же самое
    return json.dumps({"passed": bool(results) and all(r["ok"] for r in results), "results": results},
                      ensure_ascii=False)
