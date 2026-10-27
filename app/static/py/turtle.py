"""Черепашка для браузера.

Повторяет основные команды стандартного модуля turtle, но ничего не рисует сама:
она записывает команды рисования (линии, заливки, текст) и передаёт их в браузер,
где они анимируются на <canvas>. Записанные команды также используются
автопроверкой задач (функции _segments, _fills, _texts, _dots).
"""
import math

_ops = []          # команды для браузера, ещё не отправленные
_log = []          # полный журнал команд текущего запуска (для автопроверки)
_turtles = []
_screen = None
_default = None
_colormode = 1.0
_emit = None       # функция отправки в браузер (задаётся рантаймом в Pyodide)
_FLUSH_EVERY = 300


def _send(op):
    _log.append(op)
    _ops.append(op)
    if len(_ops) >= _FLUSH_EVERY:
        _flush()


def _flush():
    global _ops
    if _ops and _emit is not None:
        _emit(_ops)
    _ops = []


def _reset():
    """Вызывается рантаймом перед каждым запуском программы."""
    global _ops, _log, _turtles, _screen, _default, _colormode
    _ops = []
    _log = []
    _turtles = []
    _screen = None
    _default = None
    _colormode = 1.0


class TurtleGraphicsError(Exception):
    pass


Terminator = TurtleGraphicsError


def _color_to_css(args):
    if len(args) == 1:
        c = args[0]
    else:
        c = tuple(args)
    if isinstance(c, str):
        c = c.strip()
        if c.startswith("#"):
            return c
        return c.replace(" ", "").lower()
    if isinstance(c, (tuple, list)) and len(c) == 3:
        if _colormode == 1.0:
            if not all(0 <= v <= 1 for v in c):
                raise TurtleGraphicsError(
                    "Цвет %r вне диапазона 0..1. Для чисел 0..255 сначала вызови colormode(255)" % (c,))
            r, g, b = (int(round(v * 255)) for v in c)
        else:
            if not all(0 <= v <= 255 for v in c):
                raise TurtleGraphicsError("Цвет %r вне диапазона 0..255" % (c,))
            r, g, b = (int(v) for v in c)
        return "rgb(%d,%d,%d)" % (r, g, b)
    raise TurtleGraphicsError("Не понимаю цвет: %r" % (c,))


def colormode(mode=None):
    global _colormode
    if mode is None:
        return _colormode
    if mode not in (1, 1.0, 255):
        raise TurtleGraphicsError("colormode может быть только 1.0 или 255")
    _colormode = 1.0 if mode in (1, 1.0) else 255


class Vec2D(tuple):
    def __new__(cls, x, y):
        return tuple.__new__(cls, (x, y))

    def __add__(self, other):
        return Vec2D(self[0] + other[0], self[1] + other[1])

    def __sub__(self, other):
        return Vec2D(self[0] - other[0], self[1] - other[1])

    def __abs__(self):
        return math.hypot(self[0], self[1])

    def __repr__(self):
        return "(%.2f,%.2f)" % self


class _Screen:
    def __init__(self):
        self._bg = "white"

    def bgcolor(self, *args):
        if not args:
            return self._bg
        self._bg = _color_to_css(args)
        _send({"t": "bg", "c": self._bg})

    def bgpic(self, *a, **k):
        pass

    def setup(self, width=None, height=None, *a, **k):
        _send({"t": "setup", "w": width, "h": height})

    def screensize(self, *a, **k):
        pass

    def title(self, *a, **k):
        pass

    def tracer(self, n=None, delay=None):
        if n is not None:
            _send({"t": "tracer", "n": n})
        return 1

    def update(self):
        pass

    def delay(self, *a, **k):
        return 0

    def colormode(self, mode=None):
        return colormode(mode)

    def onclick(self, *a, **k):
        pass

    onscreenclick = onclick

    def onkey(self, *a, **k):
        pass

    onkeypress = onkey
    onkeyrelease = onkey

    def ontimer(self, *a, **k):
        pass

    def listen(self, *a, **k):
        pass

    def mainloop(self):
        pass

    def done(self):
        pass

    def exitonclick(self):
        pass

    def bye(self):
        pass

    def clear(self):
        _send({"t": "clearall"})

    clearscreen = clear
    reset = clear
    resetscreen = clear

    def window_width(self):
        return 700

    def window_height(self):
        return 500

    def turtles(self):
        return list(_turtles)

    def register_shape(self, *a, **k):
        pass

    addshape = register_shape

    def textinput(self, title, prompt):
        return input(prompt)

    def numinput(self, title, prompt, default=None, minval=None, maxval=None):
        return float(input(prompt))


def Screen():
    global _screen
    if _screen is None:
        _screen = _Screen()
    return _screen


class Turtle:
    def __init__(self, shape="classic", visible=True, **kwargs):
        self._id = len(_turtles)
        _turtles.append(self)
        self._x = 0.0
        self._y = 0.0
        self._heading = 0.0  # градусы, 0 = вправо, против часовой стрелки
        self._down = True
        self._pencolor = "black"
        self._fillcolor = "black"
        self._width = 1
        self._speed = 3
        self._visible = visible
        self._filling = False
        self._fill_pts = []
        self._shape = shape
        _send({"t": "new", "id": self._id, "v": visible, "shape": shape})

    # --- служебное ---
    def _move_to(self, x, y):
        x0, y0 = self._x, self._y
        self._x, self._y = float(x), float(y)
        if self._down:
            _send({"t": "line", "id": self._id, "x1": x0, "y1": y0, "x2": self._x, "y2": self._y,
                   "c": self._pencolor, "w": self._width, "s": self._speed})
        else:
            _send({"t": "move", "id": self._id, "x": self._x, "y": self._y, "s": self._speed})
        if self._filling:
            self._fill_pts.append((self._x, self._y))

    def _turn_to(self, heading):
        self._heading = heading % 360.0
        _send({"t": "turn", "id": self._id, "h": self._heading, "s": self._speed})

    # --- движение ---
    def forward(self, distance):
        rad = math.radians(self._heading)
        self._move_to(self._x + distance * math.cos(rad), self._y + distance * math.sin(rad))

    fd = forward

    def back(self, distance):
        self.forward(-distance)

    bk = back
    backward = back

    def right(self, angle):
        self._turn_to(self._heading - angle)

    rt = right

    def left(self, angle):
        self._turn_to(self._heading + angle)

    lt = left

    def goto(self, x, y=None):
        if y is None:
            x, y = x
        self._move_to(x, y)

    setpos = goto
    setposition = goto

    def setx(self, x):
        self._move_to(x, self._y)

    def sety(self, y):
        self._move_to(self._x, y)

    def setheading(self, angle):
        self._turn_to(angle)

    seth = setheading

    def home(self):
        self._move_to(0, 0)
        self._turn_to(0)

    def circle(self, radius, extent=None, steps=None):
        if extent is None:
            extent = 360
        if steps is None:
            frac = abs(extent) / 360.0
            steps = 1 + int(min(11 + abs(radius) / 6.0, 59.0) * frac)
        w = 1.0 * extent / steps
        w2 = 0.5 * w
        length = 2.0 * radius * math.sin(math.radians(w2))
        if radius < 0:
            length, w, w2 = -length, -w, -w2
        self._turn_to(self._heading + w2)
        for _ in range(steps):
            self.forward(length)
            self._turn_to(self._heading + w)
        self._turn_to(self._heading - w2)

    def dot(self, size=None, *color):
        if size is None:
            size = max(self._width + 4, self._width * 2)
        c = _color_to_css(color) if color else self._pencolor
        _send({"t": "dot", "id": self._id, "x": self._x, "y": self._y, "r": size / 2.0, "c": c})

    def stamp(self):
        _send({"t": "dot", "id": self._id, "x": self._x, "y": self._y, "r": 5, "c": self._fillcolor})
        return 0

    def write(self, arg, move=False, align="left", font=("Arial", 8, "normal")):
        font = tuple(font) + ("Arial", 8, "normal")[len(font):]
        _send({"t": "text", "id": self._id, "x": self._x, "y": self._y, "text": str(arg),
               "align": align, "font": [str(font[0]), int(font[1]), str(font[2])], "c": self._pencolor})

    # --- перо ---
    def penup(self):
        self._down = False

    pu = penup
    up = penup

    def pendown(self):
        self._down = True

    pd = pendown
    down = pendown

    def isdown(self):
        return self._down

    def pensize(self, width=None):
        if width is None:
            return self._width
        self._width = width

    width = pensize

    def speed(self, speed=None):
        names = {"fastest": 0, "fast": 10, "normal": 6, "slow": 3, "slowest": 1}
        if speed is None:
            return self._speed
        if isinstance(speed, str):
            speed = names.get(speed, 6)
        speed = int(round(speed))
        if not 0.5 < speed < 10.5:
            speed = 0
        self._speed = speed

    def pencolor(self, *args):
        if not args:
            return self._pencolor
        self._pencolor = _color_to_css(args)

    def fillcolor(self, *args):
        if not args:
            return self._fillcolor
        self._fillcolor = _color_to_css(args)

    def color(self, *args):
        if not args:
            return self._pencolor, self._fillcolor
        if len(args) == 2 and not all(isinstance(a, (int, float)) for a in args):
            self._pencolor = _color_to_css((args[0],))
            self._fillcolor = _color_to_css((args[1],))
        else:
            self._pencolor = self._fillcolor = _color_to_css(args)

    def begin_fill(self):
        self._filling = True
        self._fill_pts = [(self._x, self._y)]
        _send({"t": "fill_begin", "id": self._id})

    def end_fill(self):
        if self._filling and len(self._fill_pts) > 2:
            _send({"t": "fill", "id": self._id, "pts": self._fill_pts, "c": self._fillcolor})
        self._filling = False
        self._fill_pts = []

    def filling(self):
        return self._filling

    # --- видимость и прочее ---
    def hideturtle(self):
        self._visible = False
        _send({"t": "vis", "id": self._id, "v": False})

    ht = hideturtle

    def showturtle(self):
        self._visible = True
        _send({"t": "vis", "id": self._id, "v": True})

    st = showturtle

    def isvisible(self):
        return self._visible

    def shape(self, name=None):
        if name is None:
            return self._shape
        self._shape = name
        _send({"t": "shape", "id": self._id, "shape": name})

    def shapesize(self, *a, **k):
        pass

    turtlesize = shapesize

    def position(self):
        return Vec2D(self._x, self._y)

    pos = position

    def xcor(self):
        return self._x

    def ycor(self):
        return self._y

    def heading(self):
        return self._heading

    def towards(self, x, y=None):
        if y is None:
            x, y = x
        return math.degrees(math.atan2(y - self._y, x - self._x)) % 360.0

    def distance(self, x, y=None):
        if y is None:
            x, y = x
        return math.hypot(x - self._x, y - self._y)

    def clear(self):
        _send({"t": "clear", "id": self._id})

    def reset(self):
        self.clear()
        self.penup()
        self.home()
        self.pendown()

    def getscreen(self):
        return Screen()

    def onclick(self, *a, **k):
        pass

    def ondrag(self, *a, **k):
        pass

    def tilt(self, *a, **k):
        pass

    def degrees(self, *a, **k):
        pass

    def hideturtle_all(self):
        pass


Pen = Turtle
RawTurtle = Turtle
RawPen = Turtle


def getturtle():
    global _default
    if _default is None:
        _default = Turtle()
    return _default


getpen = getturtle


def _make_func(name):
    def f(*args, **kwargs):
        return getattr(getturtle(), name)(*args, **kwargs)
    f.__name__ = name
    return f


_TURTLE_METHODS = [
    "forward", "fd", "back", "bk", "backward", "right", "rt", "left", "lt", "goto", "setpos",
    "setposition", "setx", "sety", "setheading", "seth", "home", "circle", "dot", "stamp", "write",
    "penup", "pu", "up", "pendown", "pd", "down", "isdown", "pensize", "width", "speed", "pencolor",
    "fillcolor", "color", "begin_fill", "end_fill", "filling", "hideturtle", "ht", "showturtle", "st",
    "isvisible", "shape", "shapesize", "turtlesize", "position", "pos", "xcor", "ycor", "heading",
    "towards", "distance", "clear", "reset", "tilt", "degrees",
]
for _name in _TURTLE_METHODS:
    globals()[_name] = _make_func(_name)


def _make_screen_func(name):
    def f(*args, **kwargs):
        return getattr(Screen(), name)(*args, **kwargs)
    f.__name__ = name
    return f


for _name in ["bgcolor", "bgpic", "setup", "screensize", "title", "tracer", "update", "delay",
              "onclick", "onscreenclick", "onkey", "onkeypress", "onkeyrelease", "ontimer", "listen",
              "mainloop", "done", "exitonclick", "bye", "clearscreen", "resetscreen",
              "window_width", "window_height", "turtles", "register_shape", "addshape",
              "textinput", "numinput"]:
    globals()[_name] = _make_screen_func(_name)


# --- помощники для автопроверки ---
def _segments():
    """Список нарисованных линий: (x1, y1, x2, y2, цвет)."""
    return [(o["x1"], o["y1"], o["x2"], o["y2"], o["c"]) for o in _log if o["t"] == "line"
            and (o["x1"], o["y1"]) != (o["x2"], o["y2"])]


def _fills():
    return [(o["pts"], o["c"]) for o in _log if o["t"] == "fill"]


def _texts():
    return [o["text"] for o in _log if o["t"] == "text"]


def _dots():
    return [(o["x"], o["y"], o["r"], o["c"]) for o in _log if o["t"] == "dot"]


def _colors():
    return {s[4] for s in _segments()} | {f[1] for f in _fills()} | {d[3] for d in _dots()}


def _total_length():
    return sum(math.hypot(s[2] - s[0], s[3] - s[1]) for s in _segments())


def _bbox():
    pts = [(s[0], s[1]) for s in _segments()] + [(s[2], s[3]) for s in _segments()]
    if not pts:
        return (0, 0, 0, 0)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _polygon_sides(tol=0.5):
    """Длины сторон, если всё нарисованное — одна замкнутая ломаная. Иначе None."""
    segs = _segments()
    if not segs:
        return None
    for a, b in zip(segs, segs[1:]):
        if abs(a[2] - b[0]) > tol or abs(a[3] - b[1]) > tol:
            return None
    if abs(segs[0][0] - segs[-1][2]) > tol or abs(segs[0][1] - segs[-1][3]) > tol:
        return None
    # склеиваем соседние отрезки, лежащие на одной прямой
    sides = []
    prev_dir = None
    for s in segs:
        d = math.atan2(s[3] - s[1], s[2] - s[0])
        ln = math.hypot(s[2] - s[0], s[3] - s[1])
        if prev_dir is not None and abs(math.sin(d - prev_dir)) < 1e-6 and math.cos(d - prev_dir) > 0:
            sides[-1] += ln
        else:
            sides.append(ln)
        prev_dir = d
    if len(sides) > 1:
        first = math.atan2(segs[0][3] - segs[0][1], segs[0][2] - segs[0][0])
        last = math.atan2(segs[-1][3] - segs[-1][1], segs[-1][2] - segs[-1][0])
        if abs(math.sin(first - last)) < 1e-6 and math.cos(first - last) > 0:
            sides[0] += sides.pop()
    return sides


def _is_regular_polygon(n, side, tol=1.0):
    sides = _polygon_sides()
    return sides is not None and len(sides) == n and all(abs(s - side) <= tol for s in sides)
