"""Какие номера umedu 2.0 решаются на сайте и как русский тренажёр садится на номер экзамена.

Старый сайт (/ru, /oge) этот модуль не вызывает: маршруты остаются за флагом /u2.
"""
from .content import inf_gen, math_gen, oge_gen, oge_u2, phys_gen
from .content.ru import ITEMS, RULES, check_basis, check_comma, check_spell

# (вид тренажёра, список правил или None — все правила этого вида)
RU = {
    "oge-rus-2026": {
        2: ("basis", None), 3: ("basis", None),
        4: ("comma", None), 5: ("comma", None),
        6: ("spell", None), 7: ("spell", None),
    },
    "ege-rus-2026": {
        9: ("spell", ["alt_lag", "alt_rast", "alt_kas", "alt_gor_zar", "alt_i_a", "o_yo", "tsy"]),
        10: ("spell", ["pre_pri", "pref_zs"]),
        11: ("spell", ["chik", "ek_ik"]),
        12: ("spell", ["tsya"]),
        13: ("spell", ["ne", "ne_ni"]),
        14: ("spell", ["nar_oa", "nar_sh", "ne"]),
        15: ("spell", ["nn_adj", "nn_part"]),
        16: ("comma", ["odn", "slozh"]),
        17: ("comma", ["prich", "deepr", "sravn", "pril"]),
        18: ("comma", ["vvod", "obr", "mezhd"]),
    },
}

# короткие генераторы по экзаменам, которые банк u2 уже знает, плюс №11 и №14 информатики
SHORT = {
    "oge-math-2026": set(math_gen.OGE.GENERATORS),
    "ege-math-profile-2026": set(math_gen.EGE_PROFILE.GENERATORS),
    "ege-math-base-2026": set(math_gen.EGE_BASE.GENERATORS),
    "ege-inf-2026": set(inf_gen.EGE.GENERATORS),
    "oge-phys-2026": set(phys_gen.OGE.GENERATORS),
    "ege-phys-2026": set(phys_gen.EGE.GENERATORS),
    "oge-inf-2026": set(oge_gen.GENERATORS) | set(oge_u2.GENERATORS),
}


def onsite(exam_id):
    """Номера, которые ученик решает на сайте. None — экзамен по-прежнему со самопроверкой в плане."""
    if exam_id == "oge-math-2026":
        return set(SHORT[exam_id])
    if exam_id == "oge-inf-2026":
        return set(SHORT[exam_id]) | {15, 16}
    if exam_id == "oge-rus-2026":
        return set(RU[exam_id])
    return None


def mode_of(exam_id, key):
    if exam_id == "oge-inf-2026" and key == 15:
        return "robot"
    if exam_id == "oge-inf-2026" and key == 16:
        return "code"
    if key in RU.get(exam_id, {}):
        return "ru"
    if key in SHORT.get(exam_id, ()):
        return "gen"
    return "self"


def ru_pool(exam_id, num):
    kind, rules = RU[exam_id][num]
    return [i for i in ITEMS.values() if i["kind"] == kind and (not rules or i["rule"] in rules)]


def ru_item(exam_id, num, seed):
    pool = ru_pool(exam_id, num)
    return pool[int(seed) % len(pool)]


def rule_hint(item):
    text = RULES[item["rule"]][1]
    dot = text.find(".")
    return text[:dot + 1] if dot > 0 else text


def check_ru(item, given):
    """Проверка без записи в старый журнал /ru. Возвращает (верно, подробности для экрана)."""
    if item["kind"] == "comma":
        ok, extra, missed = check_comma(item, given if isinstance(given, list) else [])
        return ok, {"extra": extra, "missed": missed, "gaps": item["gaps"], "text": item["text"]}
    if item["kind"] == "basis":
        ok, s, p = check_basis(item, given if isinstance(given, dict) else {})
        return ok, {"s": item["s"], "p": item["p"], "words": item["words"], "got_s": s, "got_p": p}
    ok = check_spell(item, str(given))
    return ok, {"answer": item["answer"], "text": item["text"]}
