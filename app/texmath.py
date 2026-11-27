"""Формулы из теории «Разобраться» ($…$ и $$…$$) — в MathML, без библиотек и без JavaScript.

Понимаем подмножество TeX, которое встречается в школьной теории: дроби, степени и индексы, корни, векторы,
греческие буквы, знаки сравнения и логики, функции sin/cos/log. Весь текст экранируется: из формулы нельзя
вставить разметку. Если формула не разбирается, её показывают как есть, моноширинным текстом.
"""
import re
from html import escape

SYMBOLS = {
    # отношения и операции
    "cdot": ("mo", "·"), "times": ("mo", "×"), "div": ("mo", "÷"), "pm": ("mo", "±"), "mp": ("mo", "∓"),
    "le": ("mo", "≤"), "leq": ("mo", "≤"), "ge": ("mo", "≥"), "geq": ("mo", "≥"), "ne": ("mo", "≠"), "neq": ("mo", "≠"),
    "approx": ("mo", "≈"), "equiv": ("mo", "≡"), "sim": ("mo", "∼"), "to": ("mo", "→"), "rightarrow": ("mo", "→"),
    "Rightarrow": ("mo", "⇒"), "Leftrightarrow": ("mo", "⇔"), "Longleftrightarrow": ("mo", "⟺"), "leftarrow": ("mo", "←"),
    "in": ("mo", "∈"), "notin": ("mo", "∉"), "subset": ("mo", "⊂"), "subseteq": ("mo", "⊆"), "cap": ("mo", "∩"),
    "cup": ("mo", "∪"), "land": ("mo", "∧"), "wedge": ("mo", "∧"), "lor": ("mo", "∨"), "vee": ("mo", "∨"),
    "neg": ("mo", "¬"), "lnot": ("mo", "¬"), "oplus": ("mo", "⊕"), "mid": ("mo", "∣"), "angle": ("mo", "∠"),
    "perp": ("mo", "⊥"), "parallel": ("mo", "∥"), "triangle": ("mo", "△"), "circ": ("mo", "∘"), "deg": ("mo", "°"),
    "ldots": ("mo", "…"), "dots": ("mo", "…"), "cdots": ("mo", "⋯"), "infty": ("mi", "∞"), "emptyset": ("mi", "∅"),
    "lceil": ("mo", "⌈"), "rceil": ("mo", "⌉"), "lfloor": ("mo", "⌊"), "rfloor": ("mo", "⌋"),
    "langle": ("mo", "⟨"), "rangle": ("mo", "⟩"), "{": ("mo", "{"), "}": ("mo", "}"), "%": ("mo", "%"),
    "$": ("mo", "$"), "#": ("mo", "#"), "&": ("mo", "&"), "_": ("mo", "_"), "|": ("mo", "‖"), "backslash": ("mo", "\\"),
    # греческие
    "alpha": ("mi", "α"), "beta": ("mi", "β"), "gamma": ("mi", "γ"), "delta": ("mi", "δ"), "epsilon": ("mi", "ε"),
    "varepsilon": ("mi", "ε"), "lambda": ("mi", "λ"), "mu": ("mi", "μ"), "pi": ("mi", "π"), "rho": ("mi", "ρ"),
    "sigma": ("mi", "σ"), "tau": ("mi", "τ"), "phi": ("mi", "ϕ"), "varphi": ("mi", "φ"), "omega": ("mi", "ω"),
    "theta": ("mi", "θ"), "Delta": ("mi", "Δ"), "Omega": ("mi", "Ω"), "Sigma": ("mi", "Σ"), "Pi": ("mi", "Π"),
}
FUNCS = {"sin", "cos", "tg", "ctg", "tan", "cot", "log", "lg", "ln", "min", "max", "arcsin", "arccos", "arctg", "exp", "lim",
         "gcd", "mod"}
SPACES = {",": "0.17em", ":": "0.22em", ";": "0.28em", " ": "0.25em", "quad": "1em", "qquad": "2em", "!": "0"}
IGNORE = {"displaystyle", "limits", "nolimits", "big", "Big", "bigl", "bigr", "Bigl", "Bigr", "middle"}
ACCENTS = {"vec": "→", "overrightarrow": "→", "bar": "‾", "overline": "‾", "hat": "^", "widehat": "^", "tilde": "~"}
TEXTS = {"text", "textrm", "mathrm", "operatorname", "textbf", "mathbf", "mbox"}

_TOKEN = re.compile(r"\\([A-Za-z]+|.)|(\d+(?:[.,]\d+)*)|(\s+)|(.)", re.S)


class TexError(ValueError):
    pass


def _tokens(src):
    out = []
    for m in _TOKEN.finditer(src):
        cmd, num, space, ch = m.groups()
        if cmd is not None:
            out.append(("cmd", cmd))
        elif num is not None:
            out.append(("num", num))
        elif space is not None:
            continue
        else:
            out.append(("ch", ch))
    return out


def _el(tag, text, **attrs):
    a = "".join(f' {k}="{escape(v)}"' for k, v in attrs.items())
    return f"<{tag}{a}>{escape(text)}</{tag}>"


def _row(items):
    return items[0] if len(items) == 1 else "<mrow>" + "".join(items) + "</mrow>"


class _Parser:
    def __init__(self, src):
        self.t = _tokens(src)
        self.i = 0
        self.depth = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        if tok[0] is None:
            raise TexError("неожиданный конец формулы")
        self.i += 1
        return tok

    def expr(self, stop=None):
        items = []
        while True:
            kind, val = self.peek()
            if kind is None:
                if stop:
                    raise TexError("нет закрывающей скобки")
                break
            if kind == "ch" and val == stop:
                self.i += 1
                break
            if kind == "cmd" and val == "right" and stop == "right":
                break
            if kind == "ch" and val in "+-" and self._prefix_slot(items):
                self.i += 1                         # унарный минус: «−3», «(−∞; −3]» — без пробелов бинарного знака
                items.append(self.scripts(_el("mo", "−" if val == "-" else "+", form="prefix")))
                continue
            atom = self.atom()
            if atom is None:
                continue
            items.append(self.scripts(atom))
        return items

    @staticmethod
    def _prefix_slot(items):
        if not items:
            return True
        last = items[-1]
        return last.startswith("<mo") and not re.search(r">[)\]|⌉⌋⟩]</mo>$", last)

    def group(self):
        """Аргумент команды: {…} или один знак."""
        kind, val = self.peek()
        if kind == "ch" and val == "{":
            self.i += 1
            self.depth += 1
            if self.depth > 40:
                raise TexError("слишком глубокая вложенность")
            items = self.expr("}")
            self.depth -= 1
            return _row(items) if items else "<mrow></mrow>"
        if kind == "num" and len(val) > 1:      # \frac12: в TeX аргумент без скобок — одна цифра
            self.t[self.i] = ("num", val[1:])
            return _el("mn", val[0])
        atom = self.atom()
        if atom is None:
            raise TexError("пустой аргумент")
        return atom

    def raw_group(self):
        kind, val = self.take()
        if not (kind == "ch" and val == "{"):
            return val
        depth, buf = 1, []
        while True:
            kind, val = self.take()
            if kind == "ch" and val == "{":
                depth += 1
            elif kind == "ch" and val == "}":
                depth -= 1
                if depth == 0:
                    return "".join(buf)
            buf.append("\\" + val if kind == "cmd" else val)
            if kind == "cmd" and val.isalpha():
                buf.append(" ")

    def scripts(self, base):
        sub = sup = None
        while True:
            kind, val = self.peek()
            if kind == "ch" and val in "^_":
                self.i += 1
                arg = self.group()
                if val == "^":
                    sup = arg
                else:
                    sub = arg
                continue
            if kind == "ch" and val == "'":
                self.i += 1
                sup = _el("mo", "′")
                continue
            break
        if sub and sup:
            return f"<msubsup>{base}{sub}{sup}</msubsup>"
        if sup:
            return f"<msup>{base}{sup}</msup>"
        if sub:
            return f"<msub>{base}{sub}</msub>"
        return base

    def atom(self):
        kind, val = self.take()
        if kind == "num":
            return _el("mn", val.replace(".", ","))
        if kind == "ch":
            if val == "{":
                self.i -= 1
                return self.group()
            if val == "}":
                raise TexError("лишняя закрывающая скобка")
            if val in "^_":
                raise TexError(f"знак {val} без основания")
            if val.isalpha():
                return _el("mi", val)
            if val == "~":
                return '<mspace width="0.25em"></mspace>'
            if val == "-":
                return _el("mo", "−")
            if val == "*":
                return _el("mo", "·")
            if val in "()[]|":
                return _el("mo", val, stretchy="false")
            return _el("mo", val)
        return self.command(val)

    def command(self, name):
        if name in ("frac", "dfrac", "tfrac", "cfrac"):
            num, den = self.group(), self.group()
            return f"<mfrac>{num}{den}</mfrac>"
        if name == "binom":
            n, k = self.group(), self.group()
            return f'<mrow><mo>(</mo><mfrac linethickness="0">{n}{k}</mfrac><mo>)</mo></mrow>'
        if name == "sqrt":
            kind, val = self.peek()
            if kind == "ch" and val == "[":
                self.i += 1
                idx = _row(self.expr("]") or ["<mrow></mrow>"])
                return f"<mroot>{self.group()}{idx}</mroot>"
            return f"<msqrt>{self.group()}</msqrt>"
        if name in ACCENTS:
            return f'<mover accent="true">{self.group()}{_el("mo", ACCENTS[name])}</mover>'
        if name in ("underline",):
            return f'<munder>{self.group()}{_el("mo", "_")}</munder>'
        if name in TEXTS:
            text = self.raw_group()
            if name in ("operatorname", "mathrm"):
                return _el("mi", text.strip(), mathvariant="normal")
            return _el("mtext", text)
        if name in FUNCS:
            return _el("mi", name)
        if name in SPACES:
            return f'<mspace width="{SPACES[name]}"></mspace>'
        if name in IGNORE:
            return None
        if name in ("left", "right"):
            kind, val = self.take()
            if val == ".":
                return None
            if kind == "cmd":
                return _el(*SYMBOLS.get(val, ("mo", val)))
            return _el("mo", val)
        if name in SYMBOLS:
            tag, text = SYMBOLS[name]
            return _el(tag, text)
        raise TexError(f"неизвестная команда \\{name}")


def to_mathml(src, display=False):
    """MathML для формулы. Неизвестная разметка — TexError."""
    if len(src) > 4000:
        raise TexError("слишком длинная формула")
    items = _Parser(src).expr()
    body = _row(items) if items else "<mrow></mrow>"
    mode = ' display="block"' if display else ""
    return f'<math{mode}>{body}</math>'


def render(src, display=False):
    """Безопасный HTML: MathML или экранированный исходник, если формула не разобралась."""
    try:
        return to_mathml(src, display)
    except (TexError, IndexError, RecursionError):
        return f'<code class="th-tex">{escape(src)}</code>'
