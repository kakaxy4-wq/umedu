"""Отрисовка химических формул в тексте: H2SO4 → H₂SO₄ (нижние индексы), подсказка-название при наведении.

Формулы в задачах и ДЗ пишутся обычными цифрами; заряды ионов — надстрочными знаками (SO4²⁻, Fe³⁺),
их удобно вставлять из окна ввода формул. Работает с уже экранированным HTML и не трогает содержимое тегов.
Формулой считается слово из химических символов с цифрой или зарядом — либо известное вещество из словаря:
так «VIA», «Fe(II)» или буквы-обозначения «X», «Y» остаются как есть.
"""
import re

from markupsafe import Markup, escape

from .content.chem_names import NAMES

_EL = r"[A-Z][a-z]?"
_GROUP = r"\((?:[A-Z][a-z]?\d*)+\)\d*"
_SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_TOKEN = re.compile(r"(?<![A-Za-zА-Яа-яЁё])((?:%s|%s)(?:%s\d*|%s|\d+)*)([%s]*[⁺⁻]?)" % (_EL, _GROUP, _EL, _GROUP, _SUP))
_TAG = re.compile(r"(<[^>]+>)")
_DIGITS = re.compile(r"(\d+)")


def _render(m):
    body, charge = m.group(1), m.group(2)
    key = body + charge
    if not (any(ch.isdigit() for ch in body) or charge or (key in NAMES and len(body) > 1)):
        return m.group(0)
    inner = _DIGITS.sub(r"<sub>\1</sub>", body) + charge
    name = NAMES.get(key)
    return '<span class="f"%s>%s</span>' % (' title="%s" tabindex="0"' % name if name else "", inner)


def formula_html(html):
    """Обрабатывает уже экранированный HTML: формулы вне тегов → <span class="f">."""
    return "".join(part if part.startswith("<") else _TOKEN.sub(_render, part) for part in _TAG.split(html))


def chem_text(text):
    """Фильтр шаблонов: экранирование + формулы + переносы строк."""
    if isinstance(text, Markup):
        return Markup(formula_html(str(text)))
    # варианты в одну строку «1) …   2) …» / «А) …   Б) …» — каждый с новой строки, иначе сливаются
    html = _OPTION_GAP.sub("\n", str(escape(text or "")))
    return Markup(formula_html(html).replace("\n", "<br>"))


_OPTION_GAP = re.compile(r"[ \t]{2,}(?=(?:\d{1,2}|[А-ЕA-E])\)\s)")
