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
from datetime import date, timedelta

from . import exam_model as em

PRIOR = 0.3                   # p номера, по которому ничего не знаем
HALF_LIFE_DAYS = 30
ALPHA_MIN, ALPHA_FIRST = 0.15, 0.5
LEARN_RATE = 0.25             # какую долю разрыва (1 − p) закрывает одна тренировка номера
MINUTES = {"extended": 15, "file": 20, "program": 15, "essay": 30, "experiment": 20}   # остальные — 3 минуты
MAX_REPS = 3                  # сколько раз один номер может стоять в плане на день
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
    ожидаемым приростом баллов за минуту. Отдача убывает: после каждой запланированной тренировки p номера
    условно растёт на LEARN_RATE · (1 − p), так что слабый номер может встать в план несколько раз (до MAX_REPS),
    но только пока он выгоднее остальных. Возвращает [{'n', 'minutes', 'gain', 'why', 'times'}] в порядке
    первого появления номера."""
    by_n = {t["n"]: t for t in em.tasks(exam)}
    out, left = {}, minutes
    for n in due:
        t = by_n.get(n)
        if t and task_minutes(t) <= left:
            out[n] = {"n": n, "minutes": task_minutes(t), "gain": 0.0, "why": "повторение", "times": 1}
            left -= task_minutes(t)
    p = {n: _p(states, n, today)["p"] for n in by_n}
    while left >= 3:
        best, best_g = None, 0.0
        for t in by_n.values():
            m = task_minutes(t)
            if t["n"] in due or m > left or out.get(t["n"], {}).get("times", 0) >= MAX_REPS:
                continue
            g = (1 - p[t["n"]]) * t["points"] * LEARN_RATE / m
            if g > best_g:
                best, best_g = t, g
        if not best:
            break
        n, m = best["n"], task_minutes(best)
        it = out.setdefault(n, {"n": n, "minutes": 0, "gain": 0.0, "why": "больше всего баллов за минуту", "times": 0})
        it["minutes"] += m
        it["gain"] = round(it["gain"] + best_g * m, 2)
        it["times"] += 1
        p[n] += LEARN_RATE * (1 - p[n])
        left -= m
    return list(out.values())


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


# --- хранение (таблицы exam_enroll, skill_state в app/db.py) ---

def enroll(conn, sid, exam_id, goal=None, exam_date=None):
    em.load(exam_id)                                   # неизвестный экзамен — ошибка сразу, а не мусор в базе
    conn.execute("INSERT INTO exam_enroll (student_id, exam_id, goal, exam_date, created_at) VALUES (?, ?, ?, ?, ?) "
                 "ON CONFLICT(student_id, exam_id) DO UPDATE SET goal = excluded.goal, exam_date = excluded.exam_date",
                 (sid, exam_id, goal, exam_date, date.today().isoformat()))


def exams_of(conn, sid):
    return [dict(r) for r in conn.execute("SELECT exam_id, goal, exam_date FROM exam_enroll WHERE student_id = ? "
                                          "ORDER BY created_at, exam_id", (sid,))]


def load_states(conn, sid, exam_id):
    rows = conn.execute("SELECT task_key, p, n, last FROM skill_state WHERE student_id = ? AND exam_id = ?", (sid, exam_id))
    return {(int(k) if k.isdigit() else k): {"p": p, "n": n, "last": last} for k, p, n, last in rows}


def log_forecast(conn, sid, exam_id, today=None):
    """Пересчитывает прогноз и записывает его за сегодня (одна строка в день, последняя попытка дня побеждает)."""
    today = today or date.today()
    exam = em.load(exam_id)
    fc = forecast(exam, load_states(conn, sid, exam_id), today)
    key = "grade" if exam["scale"]["kind"] == "grade" else "test"
    conn.execute("INSERT INTO forecast_log (student_id, exam_id, day, primary_mean, low, high, result) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(student_id, exam_id, day) DO UPDATE SET "
                 "primary_mean = excluded.primary_mean, low = excluded.low, high = excluded.high, result = excluded.result",
                 (sid, exam_id, today.isoformat(), fc["primary"], fc["low"], fc["high"], fc[key]))
    return fc


def history(conn, sid, exam_id, days=90, today=None):
    since = ((today or date.today()) - timedelta(days=days)).isoformat()
    return [dict(r) for r in conn.execute(
        "SELECT day, primary_mean, low, high, result FROM forecast_log WHERE student_id = ? AND exam_id = ? AND day >= ? "
        "ORDER BY day", (sid, exam_id, since))]


def seed(conn, sid, exam_id, key, p, today=None):
    """Стартовое p по самооценке ученика. Попыткой не считается (n = 0 — вилка прогноза остаётся широкой) и не
    затирает номер, по которому уже были попытки."""
    conn.execute("INSERT INTO skill_state (student_id, exam_id, task_key, p, n, last) VALUES (?, ?, ?, ?, 0, ?) "
                 "ON CONFLICT(student_id, exam_id, task_key) DO UPDATE SET p = excluded.p, last = excluded.last "
                 "WHERE skill_state.n = 0",
                 (sid, exam_id, str(key), round(min(max(p, 0.0), 1.0), 4), (today or date.today()).isoformat()))


def record(conn, sid, exam_id, key, score, today=None):
    """Записывает попытку по номеру (или критерию) и возвращает новое состояние."""
    exam = em.load(exam_id)
    if key not in em.points(exam):
        raise KeyError(f"{exam_id}: нет номера {key!r}")
    st = update(load_states(conn, sid, exam_id).get(key), score, today)
    conn.execute("INSERT INTO skill_state (student_id, exam_id, task_key, p, n, last) VALUES (?, ?, ?, ?, ?, ?) "
                 "ON CONFLICT(student_id, exam_id, task_key) DO UPDATE SET p = excluded.p, n = excluded.n, last = excluded.last",
                 (sid, exam_id, str(key), st["p"], st["n"], st["last"]))
    return st
