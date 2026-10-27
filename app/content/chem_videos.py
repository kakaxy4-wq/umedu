"""Видео опытов для «Лаборатории → Эффектные опыты».

Описание опытов — в tools/video-prompts.json (там же промпты для генерации). На сайте показываются только те опыты,
для которых лежит файл app/static/video/chem/<id>.mp4 — новое видео появляется само, как только его положили.
Ответ «что наблюдаем?» проверяется на сервере: варианты — признаки других опытов той же группы, без совпадений по цвету.
"""
import json
import random
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIR = _ROOT / "app" / "static" / "video" / "chem"
ITEMS = json.loads((_ROOT / "tools" / "video-prompts.json").read_text(encoding="utf-8"))["items"]
BY_ID = {it["id"]: it for it in ITEMS}

# ключ признака: два варианта с одним ключом считаются «одинаковыми по смыслу» и вместе не показываются
_KEYS = ["голуб", "бур", "серо", "бел", "жёлт", "газ", "растворение", "изменений", "малинов", "красн", "фиолет",
         "кирпич", "зелён", "синее", "синий", "серебр", "обесцвеч", "запах", "налёт"]


def _key(text):
    t = text.lower()
    for k in _KEYS:
        if k in t:
            return k
    return t


def _group(item_id):
    return "flame" if item_id.startswith("flame_") else "lab"


# Что смешиваем и при каких условиях — там, где левой части уравнения мало: индикаторы, пламя, органика,
# порядок добавления. Без наблюдения, чтобы не подсказать ответ.
REAGENTS = {
    "phenolphthalein_naoh_hcl": "NaOH + фенолфталеин, затем по каплям HCl → ?",
    "litmus_acid": "HCl + лакмус → ?",
    "methyl_orange_acid": "метилоранж в HCl и в NaOH → ?",
    "cu_hcl_no_reaction": "Cu + HCl → ?",
    "ammonia_test": "NH4Cl + NaOH, нагревание; у отверстия пробирки — влажная красная лакмусовая бумажка → ?",
    "zn_oh2_amphoteric": "ZnSO4 + NaOH: сначала немного, затем избыток → ?",
    "cu_hno3_conc": "Cu + HNO3 (конц.) → ?",
    "mg_burning": "Mg, поджигаем на воздухе → ?",
    "iodine_starch": "крахмальный клейстер + раствор иода → ?",
    "silver_mirror": "CH3CHO + аммиачный раствор оксида серебра, нагревание → ?",
    "cu_oh2_glycerol": "свежий Cu(OH)2 + глицерин → ?",
    "bromine_water_decolor": "этилен C2H4 через бромную воду → ?",
    "flame_sodium": "соль натрия в пламени горелки → ?",
    "flame_potassium": "соль калия в пламени горелки → ?",
    "flame_lithium": "соль лития в пламени горелки → ?",
    "flame_calcium": "соль кальция в пламени горелки → ?",
    "flame_copper": "соль меди(II) в пламени горелки → ?",
    "flame_barium": "соль бария в пламени горелки → ?",
}


def reagents(item):
    """Что смешиваем — без названия опыта, чтобы не подсказать ответ."""
    if item["id"] in REAGENTS:
        return REAGENTS[item["id"]]
    eq = item["equation"]
    if "=" in eq:
        return eq.split(";")[0].split("=")[0].strip() + " → ?"
    return ""


def available():
    return [it for it in ITEMS if (VIDEO_DIR / ("%s.mp4" % it["id"])).exists()]


def _kind(observe):
    o = observe.lower()
    if "пламя" in o:
        return "flame"
    if o.startswith("образование") and "осадк" in o:
        return "precipitate"
    return "other"


def options(item_id):
    """4 варианта ответа: верный признак + 3 признака других опытов той же группы. Порядок постоянный для опыта."""
    item = BY_ID[item_id]
    right = item["observe"]
    pool, seen = [], {_key(right)}
    for it in ITEMS:
        if it["id"] == item_id or _group(it["id"]) != _group(item_id):
            continue
        k = _key(it["observe"])
        if k not in seen:
            seen.add(k)
            pool.append(it["observe"])
    rng = random.Random(item_id)
    # отвлекающие варианты — того же рода (осадок к осадку, газ к газу), иначе ответ угадывается по форме
    same = [o for o in pool if _kind(o) == _kind(right)]
    other = [o for o in pool if _kind(o) != _kind(right)]
    picked = rng.sample(same, min(3, len(same)))
    picked += rng.sample(other, min(3 - len(picked), len(other)))
    opts = picked + [right]
    rng.shuffle(opts)
    return opts


def check(item_id, index):
    opts = options(item_id)
    return 0 <= index < len(opts) and opts[index] == BY_ID[item_id]["observe"]
