"""Знания ученика и прогноз umedu 2.0 — чистые функции поверх модели экзамена (app/exam_model.py).

По каждой паре (ученик, номер экзамена) храним p — вероятность решить номер на экзамене, число попыток и дату
последней. Для развёрнутых номеров и критериев p — доля баллов, которую ученик в среднем получает.

- update: после попытки p сдвигается к результату (экспоненциальное сглаживание). Шаг больше на первых попытках,
  чтобы прогноз быстро «нащупал» уровень, и меньше потом, чтобы одна ошибка не обрушила его.
- decay: без практики p возвращается к стартовому значению с полураспадом HALF_LIFE_DAYS.
- forecast: ожидаемый первичный балл = Σ p × баллы; вилка — ±1,28σ (≈80%), σ сужается с числом попыток.
- plan: жадно берём номер с наибольшим ожидаемым приростом баллов за минуту.
"""
import math
from datetime import date

from . import exam_model as em

PRIOR = 0.3                   # p номера, по которому ничего не знаем
HALF_LIFE_DAYS = 30
ALPHA_MIN, ALPHA_FIRST = 0.15, 0.5
LEARN_RATE = 0.25             # какую долю разрыва (1 − p) закрывает одна тренировка номера
MINUTES = {"extended": 15, "file": 20, "program": 15}   # остальные типы ответа — 3 минуты на вариант
Z80 = 1.28


def task_minutes(task):
    return task.get("minutes") or MINUTES.get(task["answer"], 3)


def update(state, score, today=None):
    """state = {'p', 'n', 'last'} или None; score — доля полученных баллов за попытку (0…1)."""
    st = decay(state, today) if state else {"p": PRIOR, "n": 0}
    alpha = max(ALPHA_MIN, ALPHA_FIRST / (1 + st["n"]))
    p = st["p"] + alpha * (min(max(score, 0.0), 1.0) - st["p"])
    return {"p": round(p, 4), "n": st["n"] + 1, "last": (today or date.today()).isoformat()}


def decay(state, today=None):
    """p с учётом забывания на сегодня. Без даты последней попытки — как есть."""
    if not state or not state.get("last"):
        return dict(state or {"p": PRIOR, "n": 0})
    days = ((today or date.today()) - date.fromisoformat(state["last"])).days
    k = 0.5 ** (max(days, 0) / HALF_LIFE_DAYS)
    return {**state, "p": round(PRIOR + (state["p"] - PRIOR) * k, 4)}


def _p(states, key, today):
    return decay(states.get(key), today)


def forecast(exam, states, today=None):
    """Прогноз: ожидаемый первичный балл, вилка и перевод по шкале (отметка или тестовый балл)."""
    mean, var, expected = 0.0, 0.0, {}
    for key, pts in em.points(exam).items():
        st = _p(states, key, today)
        p = st["p"]
        expected[key] = p * pts
        mean += p * pts
        # неопределённость самого p: пока попыток мало, разброс шире биномиального
        var += pts * pts * (p * (1 - p) + 0.25 / (1 + st.get("n", 0)))
    sd = math.sqrt(var)
    lo, hi = max(0, math.floor(mean - Z80 * sd)), min(exam["max_points"], math.ceil(mean + Z80 * sd))
    # условия (геометрия, грамотность) проверяем на ожидаемых баллах по номерам
    scaled = {k: em.result(exam, _scaled(expected, v)) for k, v in (("mid", mean), ("low", lo), ("high", hi))}
    key = "grade" if exam["scale"]["kind"] == "grade" else "test"
    return {"primary": round(mean, 1), "low": lo, "high": hi,
            key: scaled["mid"][key], key + "_low": scaled["low"][key], key + "_high": scaled["high"][key]}


def _scaled(expected, total):
    """Раскладывает total по номерам пропорционально ожидаемым баллам (с округлением, сумма = total)."""
    total = int(round(total))
    s = sum(expected.values())
    if s <= 0 or total <= 0:
        return {}
    raw = {k: v * total / s for k, v in expected.items()}
    out = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - out[k], reverse=True)[:total - sum(out.values())]:
        out[k] += 1
    return out


def gain_per_minute(exam, task, states, today=None):
    p = _p(states, task["n"], today)["p"]
    return (1 - p) * task["points"] * LEARN_RATE / task_minutes(task)


def plan(exam, states, minutes=30, today=None, due=()):
    """План на день: сначала повторения с подошедшим сроком (due — номера), затем номера с наибольшим
    ожидаемым приростом баллов за минуту. Возвращает [{'n', 'minutes', 'gain', 'why'}]."""
    by_n = {t["n"]: t for t in em.tasks(exam)}
    out, left = [], minutes
    for n in due:
        t = by_n.get(n)
        if t and task_minutes(t) <= left:
            out.append({"n": n, "minutes": task_minutes(t), "gain": 0.0, "why": "повторение"})
            left -= task_minutes(t)
    ranked = sorted((t for t in by_n.values() if t["n"] not in due), key=lambda t: -gain_per_minute(exam, t, states, today))
    for t in ranked:
        m = task_minutes(t)
        if m <= left:
            g = gain_per_minute(exam, t, states, today) * m
            out.append({"n": t["n"], "minutes": m, "gain": round(g, 2), "why": "больше всего баллов за минуту"})
            left -= m
        if left < 3:
            break
    return out


def split_minutes(gaps, minutes):
    """Делит время между предметами пропорционально разрыву «цель − прогноз» (не меньше 0).
    gaps = {предмет: разрыв}; при нулевых разрывах — поровну. Минуты кратны 5."""
    if not gaps:
        return {}
    g = {k: max(v, 0) for k, v in gaps.items()}
    s = sum(g.values())
    share = {k: (v / s if s else 1 / len(g)) for k, v in g.items()}
    out = {k: int(minutes * v // 5 * 5) for k, v in share.items()}
    for k in sorted(share, key=lambda k: -share[k]):
        if sum(out.values()) + 5 > minutes:
            break
        out[k] += 5
    return out
