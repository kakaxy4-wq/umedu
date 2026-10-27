"""Проверка задач преподавателем: задачи банка и образцы генераторов помечаются «верно» или «есть ошибка».

Ключи: id задачи банка («o1a») или «gen:<экзамен>:<номер>» для генератора. Задача или генератор с замечанием
скрыты от учеников (карта, ДЗ по теме, пробник), пока замечание не снято.
"""
from .content import chem_exam, chem_gen
from .content.chem_tasks import TASKS, for_number

SAMPLES = 3


def gen_key(exam, num):
    return "gen:%s:%d" % (exam, num)


def sample_ids(exam, num):
    """Постоянные образцы генератора: всегда одни и те же условия, чтобы преподаватель смотрел то же, что и в прошлый раз."""
    return ["g-%s%d-%d" % (exam[0], num, k) for k in range(1, SAMPLES + 1)]


def reviews(conn):
    return {r["item"]: dict(r) for r in conn.execute("SELECT * FROM chem_reviews")}


def set_review(conn, item, status, comment, now):
    if status == "clear":
        conn.execute("DELETE FROM chem_reviews WHERE item = ?", (item,))
        return
    conn.execute("INSERT INTO chem_reviews (item, status, comment, updated_at) VALUES (?, ?, ?, ?) "
                 "ON CONFLICT(item) DO UPDATE SET status = excluded.status, comment = excluded.comment, "
                 "updated_at = excluded.updated_at", (item, status, comment[:2000], now))


def hidden(conn):
    """(скрытые задачи банка, скрытые генераторы как пары (экзамен, номер))."""
    bank, gens = set(), set()
    for item, r in reviews(conn).items():
        if r["status"] != "issue":
            continue
        if item.startswith("gen:"):
            _, exam, num = item.split(":")
            gens.add((exam, int(num)))
        else:
            bank.add(item)
    return bank, gens


def visible_bank(conn, exam, num, hidden_bank=None):
    hb = hidden(conn)[0] if hidden_bank is None else hidden_bank
    return [t for t in for_number(exam, num) if t["id"] not in hb]


def generator_on(conn, exam, num, hidden_gens=None):
    hg = hidden(conn)[1] if hidden_gens is None else hidden_gens
    return chem_gen.has_generator(exam, num) and (exam, num) not in hg


def items(exam):
    """Всё, что нужно проверить по экзамену: по номерам — задачи банка и образцы генератора."""
    out = []
    for num, (title, pts) in chem_exam.EXAMS[exam]["numbers"].items():
        row = {"num": num, "title": title, "points": pts, "bank": for_number(exam, num), "gen": None}
        if chem_gen.has_generator(exam, num):
            row["gen"] = {"key": gen_key(exam, num), "samples": [chem_gen.task(i) for i in sample_ids(exam, num)]}
        out.append(row)
    return out


def total_items():
    return len(TASKS) + len(chem_gen.GENERATORS)
