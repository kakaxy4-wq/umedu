"""Модель экзамена umedu 2.0: номера, баллы, шкала. Новый экзамен — JSON-файл в app/content/exams, а не код.

Файл описывает части и номера (балл и тип ответа), шкалу перевода первичных баллов — в отметку (ОГЭ) или в тестовый
балл (ЕГЭ) — и дополнительные условия, например «2 балла за геометрию для тройки» в ОГЭ по математике.
Флаг verified.* = false значит: эту часть ещё надо сверить с документами ФИПИ/Рособрнадзора текущего года.
Условие с отметкой g проверяется для g и всех отметок выше; не выполнено — отметка снижается, пока условия не сойдутся.
"""
import json
from functools import lru_cache
from pathlib import Path

EXAMS_DIR = Path(__file__).resolve().parent / "content" / "exams"


@lru_cache(maxsize=None)
def load(exam_id):
    return json.loads((EXAMS_DIR / f"{exam_id}.json").read_text(encoding="utf-8"))


def all_ids():
    return sorted(p.stem for p in EXAMS_DIR.glob("*.json"))


def tasks(exam):
    return [t for part in exam["parts"] for t in part["tasks"]]


def points(exam):
    """{номер или критерий: максимальный балл}. Критерии — баллы за работу в целом, не за номер
    (грамотность ГК и точность ФК в ОГЭ по русскому считаются по изложению и сочинению вместе)."""
    return {**{t["n"]: t["points"] for t in tasks(exam)}, **{c["id"]: c["points"] for c in exam.get("criteria", [])}}


def conditions_met(exam, by_task, grade):
    """Выполнены ли доп. условия для отметки grade при баллах по номерам by_task."""
    return all(sum(by_task.get(n, 0) for n in c["tasks"]) >= c["min_points"]
               for c in exam.get("conditions", []) if c["grade"] <= grade)


def result(exam, by_task):
    """Первичный балл и итог: {'primary', 'grade'} для ОГЭ или {'primary', 'test'} для ЕГЭ."""
    primary = sum(min(by_task.get(n, 0), mx) for n, mx in points(exam).items())
    sc = exam["scale"]
    if sc["kind"] == "test":
        return {"primary": primary, "test": sc["table"][primary]}
    grade = max([2] + [int(g) for g, need in sc["from"].items() if primary >= need])
    while grade > 2 and not conditions_met(exam, by_task, grade):
        grade -= 1
    return {"primary": primary, "grade": grade}
