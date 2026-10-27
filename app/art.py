"""Картинки бойцов и миров. Если файла нет — шаблоны показывают эмодзи, поэтому набор можно
докладывать по одной картинке. Исходники и промпты — tools/art-prompts.json, конвейер — скилл art-gen.
"""
from pathlib import Path

IMG_DIR = Path(__file__).resolve().parent / "static" / "img"


def _url(kind, num):
    name = "%s-%d.webp" % (kind, num)
    return "/static/img/%s/%s" % (kind, name) if (IMG_DIR / kind / name).exists() else None


BRAWLER_IMG = {n: _url("brawler", n) for n in range(1, 11)}
WORLD_IMG = {n: _url("world", n) for n in range(1, 7)}
RU_HERO_IMG = {n: _url("ruhero", n) for n in range(1, 7)}     # герои русского; пока нет файлов — эмодзи


def brawler_img(level_num):
    return BRAWLER_IMG.get(level_num)


def ruhero_img(num):
    return RU_HERO_IMG.get(num)


def world_img(num):
    return WORLD_IMG.get(num)


# Наборы с GPU-аренды 11.10.2026 (SDXL): эмблемы рангов, сундуки дропов, иконки разделов, баннеры сезонов.
# Тот же принцип: нет файла — остаётся эмодзи.
def _named(kind, name):
    return "/static/img/%s/%s.webp" % (kind, name) if (IMG_DIR / kind / ("%s.webp" % name)).exists() else None


RANK_IMG = {n: _url("rank", n) for n in range(1, 11)}
CHEST_BY_RARITY = {"Редкий": "rare", "Сверхредкий": "superrare", "Эпический": "epic", "Мифический": "mythic",
                   "Легендарный": "legendary"}
SEASON_BY_MONTH = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
                   6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}


def rank_img(num):
    return RANK_IMG.get(num)


def chest_img(rarity):
    return _named("chest", CHEST_BY_RARITY.get(rarity, rarity))


def icon_img(name):
    return _named("icon", name)


def season_banner(month):
    return _named("banner", "season-" + SEASON_BY_MONTH[month])
