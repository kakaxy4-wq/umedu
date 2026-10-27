"""Тема сайта: слова, по которым узнаётся чужая игра.

Семейный сайт (CQ_THEME=family, по умолчанию) говорит как Brawl Stars — так интереснее детям владельца. Публичный
(CQ_THEME=public) — похоже, но своими словами: механики (ранги, трофеи, сундуки, пасс) общие для жанра, а фирменные
названия чужие. Новое «фирменное» слово — только сюда, в обе темы; тест test_public_theme_has_no_foreign_brands
следит, чтобы в коде и шаблонах их не было мимо этого файла.
"""
from . import config

TERMS = {
    "family": {
        "drop": "Старр-дроп",            # именительный, ед. ч.
        "drops": "Старр-дропы",          # именительный, мн. ч. (заголовки)
        "drops_gen": "старр-дропов",     # родительный, мн. ч.
        "notes_hint": "Любит баскетбол и Brawl Stars. Быстро схватывает циклы, путается в индексах.",
    },
    "public": {
        "drop": "Звёздный дроп",
        "drops": "Звёздные дропы",
        "drops_gen": "звёздных дропов",
        "notes_hint": "Любит баскетбол и игры. Быстро схватывает циклы, путается в индексах.",
    },
}

# слова, которых не должно быть в публичной теме (проверяет тест)
FOREIGN_BRANDS = ("старр", "brawl", "бравл", "supercell")

THEME = config.THEME if config.THEME in TERMS else "family"
T = TERMS[THEME]

# Знак бренда (брендбук umedu — docs/BRAND.md). У семейного сайта знака нет: там эмодзи CQ_BRAND_EMOJI.
LOGO = "/static/img/brand/umedu-mark.svg" if THEME == "public" else ""


def wordmark(name):
    """«umedu» в фирменных цветах: ume — фиолетовый, du — оранжевый. Другое имя — как есть."""
    from markupsafe import Markup, escape
    if name.lower() == "umedu":
        return Markup('<span class="wordmark"><b>ume</b><i>du</i></span>')
    return escape(name)
