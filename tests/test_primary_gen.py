"""Генераторы заданий начальной школы: вариант в id, подсказка до решения, разбор после."""
import random

from test_app import client  # noqa: F401  (фикстура TestClient с временной базой)

from app.content import primary_gen
from app.primary import check, get_task, next_open, public


def _all_variants():
    """По несколько случайных вариантов каждого вида для 3 и 4 класса."""
    out = []
    for grade in (3, 4):
        for seed in range(40):
            random.seed(grade * 1000 + seed)
            t = primary_gen.make_random(grade)
            assert t, (grade, seed)
            out.append(t)
        for seed in range(40):
            random.seed(500000 + grade * 1000 + seed)
            t = primary_gen.make_random(grade, "russian")
            assert t, (grade, seed)
            out.append(t)
    return out


def _int(s):
    return int(s)


def test_task_by_id_deterministic_and_consistent():
    for t in _all_variants():
        again = primary_gen.task_by_id(t["id"])
        assert again == t, t["id"]
        assert t["prompt"] and t["explain"] and t["hint"], t["id"]
        assert check(t, t["accept"][0]), t["id"]
        assert not check(t, "___нет___"), t["id"]
        assert public(t)["hint"] == t["hint"], t["id"]


def test_arithmetic_independent():
    for t in _all_variants():
        parts = t["id"].split("-")
        kind, nums = parts[1], [_int(p) for p in parts[2:] if p.isdigit()]
        if kind == "rud":
            continue  # словарные слова проверяются отдельным тестом
        a = nums[0]
        if kind == "mul":
            assert t["accept"][0] == str(a * nums[1])
        elif kind == "div":
            assert a % nums[1] == 0 and t["accept"][0] == str(a // nums[1])
        elif kind == "ord":
            assert t["accept"][0] == str(a - nums[1] * nums[2])
        elif kind == "add4":
            assert t["accept"][0] == str(a + nums[1])
        elif kind == "sub4":
            assert t["accept"][0] == str(a - nums[1])
        elif kind == "mul2":
            assert t["accept"][0] == str(a * nums[1])
        elif kind == "rem":
            r = a % nums[1]
            assert t["accept"][0] == str(r) and 0 < r < nums[1]


def test_bad_ids_return_none():
    for bad in ["gen-", "gen-mul", "gen-mul-x-y", "gen-mul-6", "gen-nope-1-2", "gen-div-7-0",
                "gen-mul-99-99", "gen-rem-6-9", "gen-ord-3-2-9", "gen-add4-9999-9999", "m3-01", ""]:
        assert primary_gen.task_by_id(bad) is None, bad
    assert get_task("m3-01")["id"] == "m3-01"          # статика на месте
    assert get_task("gen-mul-6-7")["accept"][0] == "42"


def test_hint_is_teaching_not_answer():
    import re
    from app.primary import norm
    for t in _all_variants():
        assert t["hint"], t["id"]
        assert norm(t["hint"]) != norm(t["explain"]), t["id"]
        if not str(t["accept"][0]).isdigit():
            continue  # у выбора буквы обе кнопки и так видны, проверяем только числа
        # ответ не упоминается в подсказке как отдельное число (45 содержит «5», но 5 — не ответ)
        hit = re.search(r"(?<!\d)%s(?!\d)" % re.escape(str(t["accept"][0])), t["hint"])
        assert not hit, "подсказка не должна раскрывать ответ: " + t["id"]


def test_russian_words():
    from app.primary import norm
    for grade, words in primary_gen.RU_WORDS.items():
        assert len(words) >= 30, grade
        ids = [primary_gen._rud(w)["id"] for w, i, b in words]
        assert len(set(ids)) == len(ids), "слова повторяются: %s" % grade
        for word, idx, bad in words:
            t = primary_gen.task_by_id("gen-rud-%s" % word)
            assert t and t["id"] == "gen-rud-%s" % word
            assert t["grade"] == grade and t["subject"] == "russian"
            masked = word[:idx] + "?" + word[idx + 1:]
            assert masked in t["prompt"], word
            assert t["choices"] == [word[idx], bad] and word[idx] != bad
            assert check(t, word[idx]) and not check(t, bad)
            assert word[idx] not in bad  # ловушка не совпадает с ответом
            assert t["hint"] and t["explain"] and word.capitalize() in t["explain"]
            assert norm(t["hint"]) != norm(t["explain"])
    for bad_id in ["gen-rud-неттакого", "gen-rud-б?рег", "gen-rud-", "gen-rud-берег-лишний"]:
        assert primary_gen.task_by_id(bad_id) is None, bad_id


def test_russian_in_plan_balance(client, monkeypatch):
    from app import config, students
    from app.db import connect
    from app.primary import get_task, record, today_plan
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "CHEM_SITE", False)
    conn = connect()
    with conn:
        sid = students.create_student(conn, "qa-gen-ru", "Тест Русский", "parol-6", grade=3)
        conn.execute("UPDATE users SET grade = 3, subjects = 'primary', minor = 1 WHERE id = ?", (sid,))
    from datetime import date, timedelta
    seen_gen = seen_static = 0
    start = date.today() + timedelta(days=500)
    for i in range(30):
        day = today_plan(conn, sid, 3, start + timedelta(days=i))
        ru = [x for x in day["items"] if x["subject"] == "russian"][0]
        if ru["id"].startswith("gen-rud-"):
            seen_gen += 1
            assert ru["choices"], "у словарных слов кнопки"
        else:
            seen_static += 1
        task = get_task(ru["id"])
        with conn:
            record(conn, sid, task, True, task["accept"][0])
    assert seen_gen >= 5 and seen_static >= 5, "чередование генератора и статики по русскому"


def test_today_plan_alternates_gen_and_static(client, monkeypatch):
    from datetime import date, timedelta

    from app import config, students
    from app.db import connect
    from app.primary import get_task, record, today_plan

    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "CHEM_SITE", False)
    conn = connect()
    with conn:
        sid = students.create_student(conn, "qa-gen-3", "Тест Третий", "parol-6", grade=3)
        conn.execute("UPDATE users SET grade = 3, subjects = 'primary', minor = 1 WHERE id = ?", (sid,))
    seen_gen, seen_static = 0, 0
    start = date.today() + timedelta(days=400)
    for i in range(40):
        day = today_plan(conn, sid, 3, start + timedelta(days=i))
        math = [x for x in day["items"] if x["subject"] == "math"][0]
        if math["id"].startswith("gen-"):
            seen_gen += 1
            assert math["hint"], "у генератора есть подсказка"
        else:
            seen_static += 1
        task = get_task(math["id"])
        with conn:
            record(conn, sid, task, True, task["accept"][0])
    assert seen_gen >= 5 and seen_static >= 5, "чередование генератора и статики по дням"


def test_next_open_for_gen_returns_other_variant():
    solved = set()
    first = primary_gen.make_random(3)
    solved.add(first["id"])
    for _ in range(20):
        nxt = next_open(3, "math", first["id"], solved)
        assert nxt is not None
        assert nxt["id"] != first["id"] and nxt["id"] not in solved
        if nxt["id"].startswith("gen-"):
            assert primary_gen.task_by_id(nxt["id"])["id"] == nxt["id"]
            return
        solved.add(nxt["id"])
