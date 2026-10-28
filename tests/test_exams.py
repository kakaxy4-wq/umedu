"""Контракты файлов экзаменов: баллы совпадают со спецификацией, шкала монотонна, номера идут подряд."""
import pytest

from app import exam_model as em
from app import forecast


@pytest.mark.parametrize("exam_id", em.all_ids())
def test_exam_file_contract(exam_id):
    ex = em.load(exam_id)
    nums = [t["n"] for t in em.tasks(ex)]
    assert nums == list(range(1, len(nums) + 1)), "номера идут подряд с 1"
    assert sum(em.points(ex).values()) == ex["max_points"], "сумма баллов = максимум по спецификации"
    assert ex["id"] == exam_id and ex["duration_min"] > 0
    sc = ex["scale"]
    if sc["kind"] == "test":
        table = sc["table"]
        assert len(table) == ex["max_points"] + 1 and table[0] == 0 and table[-1] == 100
        assert all(a <= b for a, b in zip(table, table[1:])), "шкала монотонна"
    else:
        need = [sc["from"][g] for g in ("3", "4", "5")]
        assert 0 < need[0] < need[1] < need[2] <= ex["max_points"], "пороги отметок растут"
    keys = set(em.points(ex))
    for c in ex.get("conditions", []):
        assert set(c["tasks"]) <= keys and c["min_points"] > 0
    for g in ex.get("groups", []):
        assert set(g["tasks"]) <= set(nums)


def test_groups_cover_every_task_once():
    ex = em.load("oge-math-2026")
    grouped = sorted(n for g in ex["groups"] for n in g["tasks"])
    assert grouped == list(range(1, 26))


def test_oge_inf_matches_current_forecast():
    ex = em.load("oge-inf-2026")
    assert em.points(ex) == forecast.POINTS
    for p in range(ex["max_points"] + 1):
        assert em.result(ex, _spread(ex, p))["grade"] == forecast.grade(p)


def test_oge_math_geometry_rule():
    ex = em.load("oge-math-2026")
    algebra_only = {n: 1 for n in range(1, 15)}                       # 14 баллов, геометрии нет
    assert em.result(ex, algebra_only) == {"primary": 14, "grade": 2}
    with_geo = {**algebra_only, 15: 1, 16: 1}
    assert em.result(ex, with_geo) == {"primary": 16, "grade": 4}
    assert em.result(ex, {n: 1 for n in range(1, 8)}) == {"primary": 7, "grade": 2}


def test_oge_rus_literacy_rule():
    ex = em.load("oge-rus-2026")
    base = {1: 6, **{n: 1 for n in range(2, 13)}, 13: 7, "ФК": 2}          # 26 баллов без грамотности
    assert em.result(ex, {**base, "ГК": 9}) == {"primary": 35, "grade": 5}
    assert em.result(ex, {**base, "ГК": 8}) == {"primary": 34, "grade": 4}    # 33+, но ГК < 9 → «4»
    assert em.result(ex, {**base, "ГК": 5})["grade"] == 3                     # ГК < 6 → «3»
    assert em.result(ex, {n: 1 for n in range(2, 13)})["grade"] == 2          # 11 баллов — ниже порога 15


def test_ege_minimums_match_scale():
    """Пороги «аттестат» и «вуз» — реальные значения шкалы (их достигает какой-то первичный балл)."""
    for exam_id in em.all_ids():
        sc = em.load(exam_id)["scale"]
        if sc["kind"] == "test":
            assert sc["min_certificate"] in sc["table"] and sc["min_university"] >= sc["min_certificate"]


def test_ege_profile_scale_and_caps():
    ex = em.load("ege-math-profile-2026")
    assert em.result(ex, {}) == {"primary": 0, "test": 0}
    assert em.result(ex, {n: 1 for n in range(1, 6)})["test"] == ex["scale"]["min_certificate"]
    full = {n: 9 for n in range(1, 20)}                                # лишние баллы за номер не засчитываются
    assert em.result(ex, full) == {"primary": 32, "test": 100}


def _spread(ex, total):
    """Раскладывает total первичных баллов по номерам подряд."""
    out = {}
    for n, mx in em.points(ex).items():
        take = min(mx, total)
        if take:
            out[n] = take
        total -= take
    return out


# письмо Рособрнадзора от 25.02.2026 № 02-20, приложение 1: максимум, пороги «3»/«4»/«5», профильный класс
OGE_LETTER_2026 = {
    "oge-phys-2026": (39, 10, 20, 30, 26), "oge-bio-2026": (47, 13, 26, 38, 33), "oge-geo-2026": (31, 12, 19, 26, 23),
    "oge-soc-2026": (37, 14, 24, 32, 29), "oge-hist-2026": (37, 11, 21, 30, 26), "oge-lit-2026": (40, 16, 25, 33, 27),
    "oge-eng-2026": (68, 29, 46, 58, 55), "oge-inf-2026": (21, 5, 11, 17, 15),
}


@pytest.mark.parametrize("exam_id", sorted(OGE_LETTER_2026))
def test_oge_scales_match_letter(exam_id):
    ex = em.load(exam_id)
    mx, g3, g4, g5, prof = OGE_LETTER_2026[exam_id]
    assert (ex["max_points"], ex["scale"]["from"]["3"], ex["scale"]["from"]["4"], ex["scale"]["from"]["5"]) == (mx, g3, g4, g5)
    assert ex["profile_min"] == prof


def test_oge_eng_oral_part():
    ex = em.load("oge-eng-2026")
    written = sum(t["points"] for t in em.tasks(ex))
    oral = sum(c["points"] for c in ex["criteria"])
    assert (written, oral) == (53, 15)                                    # спецификация ФИПИ 2026, раздел 11
