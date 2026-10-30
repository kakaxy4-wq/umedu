"""Пакет D: план дня решается на сайте, генераторы сходятся с пересчётом, русский мост и снимок меню."""
import re
import xml.etree.ElementTree as ET
from datetime import date

from app import config, exam_model as em
from app import knowledge as kn
from app.content import math_gen, oge16_gen, oge_gen, oge_u2, phys_gen
from app.content import ru
from app.content.math_plots import _shoelace
from app.content.phys_choice import CHANGES, DEVICES, PHENOMENA, UNITS
from app import u2_onsite
from test_app import client, login  # noqa: F401


def _svg_ok(svg):
    ET.fromstring(svg)
    low = svg.lower()
    assert "<script" not in low and "javascript:" not in low
    assert not re.search(r"\son[a-z]+=", low)


def _math_expected(data):
    q = data["q"]
    if data["kind"] == "plot":
        area, peri = data["L"] * data["W"], 2 * (data["L"] + data["W"])
        house, bed = data["hx"] * data["hy"], data["bx"] * data["by"]
        vals = [area, peri, house, area - house - bed, peri * data["price"]]
    elif data["kind"] == "flat":
        ka, ba = data["kitchen"] * data["depth"], data["bed"] * data["depth"]
        ra = data["room"] * data["depth"]
        total = (data["kitchen"] + data["room"] + data["bed"]) * data["depth"]
        vals = [ka, ba, total, ra - ka, total * data["price"]]
    elif data["kind"] == "tariff":
        ca = data["a_fee"] + data["a_gb"] * data["n"]
        cb = data["b_fee"] + data["b_gb"] * data["n"]
        vals = [ca, cb, abs(ca - cb), data["t"] + 1, min(ca, cb) * 12]
    else:
        outer, outer2 = data["d"] + 2 * data["t"], data["d2"] + 2 * data["t2"]
        vals = [outer, 2 * data["t"], abs(outer - outer2), data["price"] * 2, data["stock"] // 2]
    return str(vals[q - 1])


def _phys_expected(data):
    kind = data["kind"]
    if kind == "units":
        units = dict(UNITS)
        return "".join(str(data["shown"].index(units[q]) + 1) for q in data["quants"])
    if kind == "device":
        return str(data["options"].index(dict(DEVICES)[data["what"]]) + 1)
    if kind == "phenomenon":
        return str(data["options"].index(dict(PHENOMENA)[data["situation"]]) + 1)
    if kind == "lift":
        pe = data["m"] * 10 * data["h"]
        good = {"Потенциальная энергия тела увеличилась на %d Дж." % pe,
                "Кинетическая энергия тела при подъёме не изменилась."}
        return "".join(str(i + 1) for i, s in enumerate(data["statements"]) if s in good)
    if kind == "explain":
        right = {"boat": "Сила Архимеда равна весу бруска.",
                 "fuse": "Ток в цепи стал больше допустимого.",
                 "swing": "Скорость маятника больше всего в нижней точке."}[data["topic"]]
        return str(data["options"].index(right) + 1)
    if kind == "process":
        table = {"isobar": {"объём газа": "увеличивается", "давление газа": "не изменяется"},
                 "isochor": {"давление газа": "увеличивается", "объём газа": "не изменяется"},
                 "heat_ice": {"внутренняя энергия": "увеличивается", "температура": "не изменяется"}}
        return "".join(CHANGES[table[data["group"]][n]] for n in data["names"])
    if kind == "table":
        return str(data["v0"] + data["a"] * data["ask"])
    if kind == "scale":
        return str(data["start"] + data["n"] * data["step"])
    if data["ask"] == "r":
        return str(data["u1"] // data["i1"])
    return str(data["i2"] // data["i1"])


def _inf11(data):
    body = data["body"]
    if data["kind"] == "count":
        return str(len(re.findall(r"(?<![А-Яа-яЁё])%s(?![А-Яа-яЁё])" % re.escape(data["name"]), body)))
    if data["kind"] == "after":
        return re.search(re.escape(data["name"]) + r" купил (\d+)", body).group(1)
    return str(max(int(x) for x in re.findall(r"\d+", body)))


def _inf14(data):
    rows = [tuple(r) for r in data["rows"]]
    if data["kind"] == "sum":
        return str(sum(c for _, shop, c in rows if shop == data["shop"]))
    if data["kind"] == "count":
        return str(sum(1 for *_, c in rows if c >= data["limit"]))
    return str(max(c for good, _, c in rows if good == data["good"]))


def test_new_generators_200_seeds_and_recompute():
    banks = [(math_gen.OGE, {1, 2, 3, 4, 5, 11, 18}), (phys_gen.OGE, {1, 2, 3, 4, 5, 12, 13, 14, 15, 16})]
    for bank, nums in banks:
        for num in nums:
            texts = set()
            for seed in range(1, 201):
                v = bank.make(num, seed)
                assert bank.check(v, v["answer"]) and not bank.check(v, v["answer"] + "9")
                assert 2 <= len(v["steps"]) <= 4
                texts.add((v["text"], str(v.get("table")), v.get("svg")))
                if num <= 5 and bank.prefix == "oge-math":
                    assert v["answer"] == _math_expected(v["data"])
                elif bank.prefix == "oge-phys":
                    assert v["answer"] == _phys_expected(v["data"])
                elif num == 11:
                    order = v["data"]["order"]
                    assert v["answer"] == "".join(str(order.index(i) + 1) for i in range(3))
                elif num == 18:
                    assert int(v["answer"]) == int(_shoelace(v["data"]["pts"]))
                if v.get("svg"):
                    _svg_ok(v["svg"])
                    pub = oge_gen.public(v)
                    assert "svg" in pub and "data" not in pub and "answer" not in pub
            assert len(texts) >= 80, (bank.prefix, num, len(texts))
    for num in (11, 14):
        texts = set()
        for seed in range(1, 201):
            v = oge_u2.make(num, seed)
            assert oge_gen.check(v, v["answer"]) and not oge_gen.check(v, "zzz")
            assert 2 <= len(v["steps"]) <= 4
            texts.add((v["text"], str(v.get("table"))))
            got = _inf11(v["data"]) if num == 11 else _inf14(v["data"])
            assert v["answer"] == got, (num, seed, v["answer"], got)
            if v.get("svg"):
                _svg_ok(v["svg"])
        assert len(texts) >= 150, (num, len(texts))
    # один сид — один сюжет на все пять вопросов
    a = math_gen.OGE.make(1, 7)["data"]
    b = math_gen.OGE.make(5, 7)["data"]
    assert {k: a[k] for k in a if k != "q"} == {k: b[k] for k in b if k != "q"}
    kinds = {math_gen.OGE.make(1, s)["data"]["kind"] for s in range(1, 80)}
    assert kinds == {"plot", "flat", "tariff", "bike"}


def test_steps_on_old_generators_and_no_ascii_hyphen_space():
    for bank in (math_gen.OGE, math_gen.EGE_PROFILE, math_gen.EGE_BASE, phys_gen.OGE, phys_gen.EGE):
        for num in bank.GENERATORS:
            v = bank.make(num, 3)
            assert 2 <= len(v["steps"]) <= 4
            assert " -" not in v["text"] + v["explain"]


def test_russian_issue_counts():
    from collections import Counter
    spell = Counter(i["rule"] for i in ru.SPELL_ITEMS)
    commas = Counter(i["rule"] for i in ru.COMMA_ITEMS)
    basis = Counter(i["rule"] for i in ru.BASIS_ITEMS)
    assert spell["alt_lag"] >= 8 and spell["alt_rast"] >= 8 and spell["alt_kas"] >= 8
    assert spell["alt_gor_zar"] >= 8 and spell["alt_i_a"] >= 8
    assert commas["sravn"] >= 8 and commas["pril"] >= 8 and commas["mezhd"] >= 8
    assert basis["basis_sost"] >= 12 and basis["basis_odno"] >= 12


def test_day_plan_only_onsite_when_lagging(client, monkeypatch):  # noqa: F811
    from app.u2_web import _sections
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    for exam_id, goal in (("oge-math-2026", 4), ("oge-inf-2026", 4), ("oge-rus-2026", 4)):
        client.post("/u2/start", data={"csrf": csrf, "exam_id": exam_id, "goal": goal})
        data = {"csrf": csrf}
        for i, _sec in enumerate(_sections(em.load(exam_id))):
            data["s%d" % i] = "0"                                 # «не умею» по каждому разделу
        client.post("/u2/diag/%s" % exam_id, data=data)
    client.post("/u2/me/minutes", data={"csrf": csrf, "minutes": 90})
    page = client.get("/u2/today").text
    hrefs = re.findall(r'href="/u2/train/(oge-(?:math|inf|rus)-2026)/(\d+)"', page)
    assert hrefs and all(int(n) in u2_onsite.onsite(exam) for exam, n in hrefs)
    assert "fipi.ru" not in page
    assert "u2-tab" in page


def test_russian_bridge_records_skill(client, monkeypatch):  # noqa: F811
    from app.db import connect
    from test_app import sid_of
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-rus-2026", "goal": 4})
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "ege-rus-2026", "goal": 70})
    page = client.get("/u2/train/oge-rus-2026/4?seed=3").text
    assert "u2-tab" in page and "sidenav" not in page and "u2-ru" in page
    item = u2_onsite.ru_item("oge-rus-2026", 4, 3)
    h = {"X-CSRF-Token": csrf}
    bad = client.post("/u2/api/ru/oge-rus-2026/4", json={"id": item["id"], "seed": 3, "answer": [0], "hint": 0},
                      headers=h).json()
    # ловушка без запятых может случайно совпасть с [0]; тогда это верный ответ и он запишется
    if bad.get("pending"):
        assert connect().execute("SELECT COUNT(*) FROM skill_attempt WHERE exam_id = 'oge-rus-2026'").fetchone()[0] == 0
        client.post("/u2/api/ru/oge-rus-2026/4", json={"id": item["id"], "seed": 3, "answer": item["gaps"], "hint": 1},
                    headers=h)
    states = kn.load_states(connect(), sid_of(), "oge-rus-2026")
    assert states[4]["n"] == 1
    # ЕГЭ: слово по правилу корней попадает в №9
    word = u2_onsite.ru_item("ege-rus-2026", 9, 5)
    assert word["kind"] == "spell" and word["rule"].startswith("alt_") or word["rule"] in ("o_yo", "tsy")
    ok = client.post("/u2/api/ru/ege-rus-2026/9", json={"id": word["id"], "seed": 5, "answer": word["answer"]},
                     headers=h).json()
    assert ok["ok"] and kn.load_states(connect(), sid_of(), "ege-rus-2026")[9]["n"] == 1


def test_robot_and_code_open_inside_u2(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-inf-2026", "goal": 4})
    robot = client.get("/u2/train/oge-inf-2026/15?seed=4").text
    code = client.get("/u2/train/oge-inf-2026/16?seed=4").text
    assert "robot-app" in robot and "u2-tab" in robot and "sidenav" not in robot
    assert "codebox" in code and "u2-code" in code and oge16_gen.make(4)["solution"] not in code
    h = {"X-CSRF-Token": csrf}
    pending = client.post("/u2/api/play/oge-inf-2026/15", json={"seed": 4, "passed": False, "code": "вверх()"},
                          headers=h).json()
    assert pending["pending"] and "hint" in pending
    done = client.post("/u2/api/play/oge-inf-2026/15", json={"seed": 4, "passed": True, "hint": 1, "code": "ok"},
                       headers=h).json()
    assert done["ok"] and "solution" in done


def test_menu_snapshot_codequest_and_chemlab(client, monkeypatch):  # noqa: F811
    """Главная КодКвеста и /chem ХимЛаба: меню и ключевые ссылки не разъехались."""
    login(client, "student")
    nav = re.search(r'<nav class="sidenav">(.*)</nav>', client.get("/").text, re.S).group(1)
    assert re.findall(r'href="([^"]+)"', nav) == [
        "/", "/today", "/map", "/homework", "/daily", "/oge", "/trainer", "/bots", "/playground", "/cheatsheet",
        "/achievements", "/season", "/shop", "/certificates", "/checks", "/portfolio", "/account"]
    from app import config as cfg
    monkeypatch.setattr(cfg, "CHEM_SITE", True)
    monkeypatch.setattr(cfg, "SUBJECTS", ["chemistry"])
    monkeypatch.setattr(cfg, "GAME", "light")
    monkeypatch.setattr(cfg, "SIGNUP", True)
    login(client, "student")
    home = client.get("/chem").text
    nav = re.search(r'<nav class="sidenav">(.*)</nav>', home, re.S).group(1)
    assert re.findall(r'href="([^"]+)"', nav) == [
        "/chem", "/chem/map", "/chem/hw", "/chem/mock", "/checks", "/chem/lab", "/chem/table", "/chem/me", "/account"]


def test_plan_filter_does_not_change_other_exams():
    """Без only= план считает все номера, как раньше."""
    ex = em.load("oge-rus-2026")
    D = date(2026, 10, 30)
    states = {n: {"p": 0.1, "n": 0, "last": D.isoformat()} for n in range(1, 14)}
    plain = [s["n"] for s in kn.plan(ex, states, 30, D)]
    assert 1 in plain                                              # изложение по-прежнему в модели
    only = [s["n"] for s in kn.plan(ex, states, 30, D, only=u2_onsite.onsite("oge-rus-2026"))]
    assert only and set(only) <= {2, 3, 4, 5, 6, 7}
