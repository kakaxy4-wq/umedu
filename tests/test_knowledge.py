"""Модель знаний и прогноз: p растёт с практикой и затухает без неё, прогноз — вилка с условиями экзамена, план — по приросту."""
from datetime import date, timedelta

from app import exam_model as em
from app import knowledge as kn

D = date(2026, 10, 28)


def test_update_moves_towards_result_and_slows_down():
    st = kn.update(None, 1, D)
    assert st["n"] == 1 and st["p"] > kn.PRIOR + 0.3                       # первая попытка — крупный шаг
    for _ in range(20):
        st = kn.update(st, 1, D)
    assert st["p"] > 0.9
    after_miss = kn.update(st, 0, D)
    assert st["p"] - after_miss["p"] <= kn.ALPHA_MIN * st["p"] + 1e-3       # одна ошибка не обрушивает
    assert kn.update(None, 5, D)["p"] <= 1 and kn.update(None, -1, D)["p"] >= 0


def test_decay_returns_to_prior():
    st = {"p": 0.9, "n": 10, "last": D.isoformat()}
    assert kn.decay(st, D)["p"] == 0.9
    half = kn.decay(st, D + timedelta(days=kn.HALF_LIFE_DAYS))["p"]
    assert abs(half - (kn.PRIOR + 0.3)) < 1e-6
    assert kn.decay(st, D + timedelta(days=3650))["p"] < kn.PRIOR + 0.01


def test_forecast_band_narrows_with_practice():
    ex = em.load("ege-math-profile-2026")
    few = {n: {"p": 0.7, "n": 1, "last": D.isoformat()} for n in range(1, 20)}
    many = {n: {"p": 0.7, "n": 30, "last": D.isoformat()} for n in range(1, 20)}
    f1, f2 = kn.forecast(ex, few, D), kn.forecast(ex, many, D)
    assert f1["primary"] == f2["primary"]
    assert f2["high"] - f2["low"] < f1["high"] - f1["low"]
    assert f1["test_low"] <= f1["test"] <= f1["test_high"]
    assert 0 <= f1["low"] <= f1["primary"] <= f1["high"] <= ex["max_points"]


def test_forecast_respects_geometry_rule():
    ex = em.load("oge-math-2026")
    algebra = {n: {"p": 1.0, "n": 50, "last": D.isoformat()} for n in range(1, 15)}
    no_geo = {**algebra, **{n: {"p": 0.0, "n": 50, "last": D.isoformat()} for n in list(range(15, 20)) + [23, 24, 25]}}
    assert kn.forecast(ex, no_geo, D)["grade"] == 2                         # 14+ баллов, но геометрия = 0
    with_geo = {**no_geo, 15: {"p": 1.0, "n": 50, "last": D.isoformat()}, 16: {"p": 1.0, "n": 50, "last": D.isoformat()}}
    assert kn.forecast(ex, with_geo, D)["grade"] >= 3


def test_plan_prefers_cheap_weak_tasks_and_fits_time():
    ex = em.load("oge-math-2026")
    states = {n: {"p": 0.95, "n": 20, "last": D.isoformat()} for n in range(1, 26)}
    states[4] = {"p": 0.2, "n": 5, "last": D.isoformat()}
    pl = kn.plan(ex, states, 30, D)
    assert pl[0]["n"] == 4
    assert sum(x["minutes"] for x in pl) <= 30
    with_due = kn.plan(ex, states, 30, D, due=[17])
    assert with_due[0] == {"n": 17, "minutes": 3, "gain": 0.0, "why": "повторение"}


def test_split_minutes():
    assert kn.split_minutes({"математика": 20, "русский": 10}, 30) == {"математика": 20, "русский": 10}
    assert kn.split_minutes({"а": 0, "б": 0}, 30) == {"а": 15, "б": 15}
    out = kn.split_minutes({"а": 5, "б": -3}, 30)
    assert out == {"а": 30, "б": 0}
    assert sum(kn.split_minutes({"а": 1, "б": 1, "в": 1}, 30).values()) <= 30
