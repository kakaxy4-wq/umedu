"""Прогноз балла ОГЭ по информатике — то, что родитель 8–9 класса хочет видеть в первую очередь.

Считаем честно и только по тому, что сайт видел: тренажёр вариантов (№1–10, 12), Робот (№15), задачи в формате
номера (№16 и др.), пробник первой части. Для номера — вероятность решить его на экзамене p; ожидаемый балл = Σ p ×
баллы номера. Номера, которые на сайте не тренировались (11, 13, 14 делаются на занятии на компьютере), в прогноз
не входят и показываются отдельно: «ещё до N баллов».

Баллы и шкала — по демоверсии ФИПИ (16 заданий, 21 первичный балл; «3» с 5, «4» с 11, «5» с 17). Если ФИПИ поменяет
шкалу — правится только здесь.
"""

POINTS = {**{n: 1 for n in range(1, 13)}, 13: 2, 14: 3, 15: 2, 16: 2}
MAX_POINTS = sum(POINTS.values())
GRADE_FROM = [(17, 5), (11, 4), (5, 3), (0, 2)]
MASTERED_P = 0.95
# номера, которые решаются без программирования, — с них ОГЭ можно начинать с первых уроков
EASY_FIRST = [4, 7, 9, 2, 8, 12, 1, 3, 10, 5, 6]


def grade(points):
    return next(g for need, g in GRADE_FROM if points >= need)


def number_p(info):
    """Вероятность решить номер на экзамене по данным сайта; None — данных нет."""
    d = info.get("drill")
    if d and d["n"]:
        if d["mastered"]:
            return MASTERED_P
        return min(0.9, (d["ok"] + 1) / (d["n"] + 3))          # сглаживание: 0 из 0 → 1/3, без скачков от одной попытки
    robot = info.get("robot")
    if robot and robot[0]:
        return min(0.9, 0.2 + 0.7 * robot[0] / robot[1])
    if info.get("tasks") and info.get("solved"):
        return min(0.85, 0.2 + 0.65 * info["solved"] / len(info["tasks"]))
    trial = info.get("trial")
    if trial and trial[1]:
        return 0.9 * trial[0] / trial[1]
    return None


def forecast(progress):
    """progress — результат main.oge_progress: {номер: {...}}. Возвращает прогноз и что подтянуть."""
    known, unknown, expected = {}, [], 0.0
    for num, pts in POINTS.items():
        p = number_p(progress.get(num, {}))
        if p is None:
            unknown.append(num)
        else:
            known[num] = p
            expected += p * pts
    points = int(expected + 0.5)
    # что даст больше всего баллов: тренируемые номера с наибольшей недостачей, сначала те, что есть в тренажёре
    order = {n: i for i, n in enumerate(EASY_FIRST)}
    gaps = sorted((-(1 - known.get(n, 0)) * POINTS[n], order.get(n, 99), n) for n in POINTS
                  if progress.get(n, {}).get("has_drill") and known.get(n, 0) < MASTERED_P)
    return {
        "points": points, "max": MAX_POINTS, "grade": grade(points) if known else None,
        "known": {n: int(p * 100 + 0.5) for n, p in known.items()},
        "unknown": unknown, "unknown_points": sum(POINTS[n] for n in unknown),
        "next": [n for *_, n in gaps][:3],
        "enough_data": len(known) >= 4,
    }
