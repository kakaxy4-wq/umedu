"""Сайт по химии (CQ_SUBJECTS=chemistry): регистрация, кабинет преподавателя, оплата, ДЗ, задачи, таблица."""
import re

import pytest

from test_app import client, login_as  # noqa: F401 — общая фикстура с тестовой базой


@pytest.fixture()
def chem(client, monkeypatch):  # noqa: F811
    from app import config
    monkeypatch.setattr(config, "CHEM_SITE", True)
    monkeypatch.setattr(config, "SUBJECTS", ["chemistry"])
    monkeypatch.setattr(config, "GAME", "light")
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "BRAND_EMOJI", "🧪")
    return client


def _signup(c, code, grade=11, login="masha11", name="Маша"):
    c.cookies.clear()
    return c.post("/join", data={"code": code, "name": name, "grade": grade, "login": login, "password": "lisa-gora-42"},
                  follow_redirects=False)


def test_grading_rules_and_content():
    from app.content import chem_exam
    from app.content.chem_tasks import TASKS, TASK_BY_ID, grade_answer, formula_html
    from app.content.checks import CHECK_BY_ID
    from app.content.elements import ELEMENTS
    assert chem_exam.EXAMS["oge"]["max"] == 38 and chem_exam.EXAMS["ege"]["max"] == 56
    assert len({x["id"] for x in TASKS}) == len(TASKS)
    for x in TASKS:
        assert x["num"] in chem_exam.EXAMS[x["exam"]]["numbers"], x["id"]
        assert (x["mode"] == "long") == (x["num"] in chem_exam.EXAMS[x["exam"]]["long"]), x["id"]
        if x["mode"] != "long":
            assert grade_answer(x, x["answer"]) == chem_exam.points(x["exam"], x["num"]), x["id"]
    assert grade_answer(TASK_BY_ID["o1a"], "42") == 1 and grade_answer(TASK_BY_ID["o1a"], "243") == 0   # порядок не важен
    assert grade_answer(TASK_BY_ID["e8a"], "1234") == 1 and grade_answer(TASK_BY_ID["e8a"], "1243") == 0  # 2-балльное
    assert grade_answer(TASK_BY_ID["e28a"], "22,4") == 1 and grade_answer(TASK_BY_ID["e28a"], "22") == 0
    assert grade_answer(TASK_BY_ID["e8a"], "") == 0
    html = formula_html("2H2SO4 и Fe(OH)2, SO4²⁻, Fe(II), VIA, X, 25 °C")
    assert '2<span class="f" title="серная кислота" tabindex="0">H<sub>2</sub>SO<sub>4</sub></span>' in html
    assert "Fe(OH)<sub>2</sub>" in html and 'title="сульфат-ион"' in html
    assert html.endswith(", Fe(II), VIA, X, 25 °C")                       # не формулы — без изменений
    assert CHECK_BY_ID["chem9_entry"]["grade"] == 9 and CHECK_BY_ID["chem11_entry"]["subject"] == "chemistry"
    el = {e["sym"]: e for e in ELEMENTS}
    assert (el["Fe"]["period"], el["Fe"]["group"]) == (4, 8) and (el["Og"]["period"], el["Og"]["group"]) == (7, 18)
    assert (el["Al"]["group"], el["La"]["row"], el["Cl"]["mass"], el["K"]["shells"]) == (13, 9, "35,5", [2, 8, 8, 1])


def test_chem_site_signup_lessons_money_hw(chem):
    from app import chem as chem_mod
    from app.db import connect
    t = login_as(chem, "teacher")
    assert chem.get("/teacher", follow_redirects=False).headers["location"] == "/chem/teacher"
    page = chem.get("/chem/teacher").text
    code = connect().execute("SELECT value FROM settings WHERE key = 'invite_code'").fetchone()[0]
    assert code in page and "/join?code=" in page
    # регистрация: неверный код, затем верный
    assert "Неверный код" in _signup(chem, "nope").text
    r = _signup(chem, code)
    assert r.status_code == 303 and r.headers["location"].startswith("/chem")
    sid = connect().execute("SELECT id FROM users WHERE username = 'masha11'").fetchone()[0]
    row = connect().execute("SELECT grade, subjects, calm, full_name FROM users WHERE id = ?", (sid,)).fetchone()
    assert (row["grade"], row["subjects"], row["calm"], row["full_name"]) == (11, "chemistry", 1, "")
    assert "занят" in _signup(chem, code).text                          # логин уже есть
    s_csrf = login_as(chem, "masha11", "lisa-gora-42")
    home = chem.get("/chem").text
    assert "Входное тестирование" in home and "/check/chem11_entry" in home
    checks = chem.get("/checks").text
    assert "chem11_entry" in checks and "chem9_entry" not in checks and "Python" not in checks
    assert "ЕГЭ" in chem.get("/chem/map").text
    # задачи: ответ проверяет сервер, ответ показывается после решения
    page = chem.get("/chem/task/e8a").text
    assert "1235" not in page
    h = {"X-CSRF-Token": s_csrf}
    r = chem.post("/api/chem/task/e8a", json={"answer": "1234"}, headers=h).json()
    assert (r["points"], r["max"]) == (1, 2) and "answer" not in r
    r = chem.post("/api/chem/task/e8a", json={"answer": "1235"}, headers=h).json()
    assert r["points"] == 2 and r["answer"] == "1235"
    assert "лучший результат: 2/2" in chem.get("/chem/task/e8a").text
    assert chem.get("/chem/table").text.count('class="pt-el') == 118
    table = chem.get("/chem/table").text
    assert "Что означают подписи" in table and "Группа 17 (VIIA)" in table and "Семейство:" in table
    # преподаватель: занятия, оплата, баланс
    t = login_as(chem, "teacher")
    chem.post("/chem/teacher/student/%d/settings" % sid, data={"name": "Маша", "grade": 11, "price": "1500", "csrf": t})
    chem.post("/chem/teacher/lessons", data={"student_id": sid, "day": "2025-10-10", "time": "16:00", "price": "",
                                            "weeks": 2, "csrf": t})
    lessons = connect().execute("SELECT id, price, starts_at FROM chem_lessons WHERE student_id = ? ORDER BY starts_at",
                                (sid,)).fetchall()
    assert [(l["price"], l["starts_at"]) for l in lessons] == [(1500, "2025-10-10T16:00"), (1500, "2025-10-17T16:00")]
    chem.post("/chem/teacher/lesson/%d" % lessons[0]["id"], data={"status": "done", "csrf": t})
    chem.post("/chem/teacher/lesson/%d" % lessons[1]["id"], data={"status": "missed", "csrf": t})   # без оплаты
    conn = connect()
    assert chem_mod.balance(conn, sid)["balance"] == -1500
    chem.post("/chem/teacher/student/%d/payment" % sid, data={"amount": "1 000", "paid_at": "2025-10-10", "csrf": t})
    assert chem_mod.balance(conn, sid)["balance"] == -500
    assert "500 ₽" in chem.get("/chem/teacher").text
    money = chem.get("/chem/teacher/money?month=2025-10").text
    assert "1 000 ₽" in money
    csv = chem.get("/chem/teacher/money.csv?month=2025-10")
    assert csv.text.startswith("﻿Дата;") and "Маша;1000" in csv.text
    # ДЗ
    chem.post("/chem/teacher/student/%d/hw" % sid, data={"title": "ОВР", "text": "3 реакции", "csrf": t})
    hw_id = conn.execute("SELECT id FROM chem_hw WHERE student_id = ?", (sid,)).fetchone()[0]
    s_csrf = login_as(chem, "masha11", "lisa-gora-42")
    chem.post("/chem/hw/%d/submit" % hw_id, data={"answer": "решение", "csrf": s_csrf})
    assert conn.execute("SELECT status FROM chem_hw WHERE id = ?", (hw_id,)).fetchone()[0] == "submitted"
    t = login_as(chem, "teacher")
    assert "решение" in chem.get("/chem/teacher/hw").text
    chem.post("/chem/teacher/hw/%d/check" % hw_id, data={"score": "2", "max_score": "3", "comment": "хорошо", "csrf": t})
    assert conn.execute("SELECT status, score FROM chem_hw WHERE id = ?", (hw_id,)).fetchone()[:] == ("checked", 2)
    # родительская ссылка: занятия, оплата, ДЗ — без пароля
    chem.post("/teacher/student/%d/parent-link" % sid, data={"action": "new", "csrf": t})
    token = conn.execute("SELECT parent_token FROM users WHERE id = ?", (sid,)).fetchone()[0]
    chem.cookies.clear()
    parent = chem.get("/parent/%s" % token).text
    assert "−500" in parent or "-500" in parent
    assert "ОВР" in parent and "проведено" in parent


def test_python_site_unchanged_by_chem_code(client):  # noqa: F811
    assert client.get("/join").status_code == 404
    t = login_as(client, "teacher")
    assert client.get("/chem/teacher").status_code == 404
    assert "chem9_entry" not in client.get("/teacher/checks").text


def test_demo_student_and_manual_grade(chem):
    from app.db import connect
    t = login_as(chem, "teacher")
    chem.post("/chem/teacher/demo", data={"grade": 11, "csrf": t})
    chem.post("/chem/teacher/demo", data={"grade": 11, "csrf": t})          # повторно — без дубля
    rows = connect().execute("SELECT grade FROM users WHERE username = 'тест'").fetchall()
    assert [r[0] for r in rows] == [11]
    assert "логин <b>тест</b>" in chem.get("/chem/teacher").text
    r = chem.post("/teacher/students", data={"display_name": "Петя", "username": "petya", "grade": 11, "price": "1400",
                                             "csrf": t})
    assert r.status_code == 200
    row = connect().execute("SELECT grade, price, subjects FROM users WHERE username = 'petya'").fetchone()
    assert (row["grade"], row["price"], row["subjects"]) == (11, 1400, "chemistry")
    assert 'name="grade" value="9"' in chem.get("/teacher/students").text
    chem.cookies.clear()
    r = chem.post("/login", data={"username": "Тест", "password": "тест"}, follow_redirects=False)
    assert r.status_code == 303
    page = chem.get("/chem/task/e8a").text
    assert '<span class="f" title="хлорид железа(III)" tabindex="0">FeCl<sub>3</sub></span>' in page


def test_variants_topics_homework_and_lesson_sheets(chem):
    import io as _io
    from app.content import chem_gen
    from app.content.chem_tasks import grade_answer
    from app.db import connect
    tid = chem_gen.new_id("oge", 18)
    assert chem_gen.task(tid) == chem_gen.task(tid)                      # вариант восстанавливается по id
    t = login_as(chem, "teacher")
    chem.post("/chem/teacher/demo", data={"grade": 9, "csrf": t})
    sid = connect().execute("SELECT id FROM users WHERE username = 'тест'").fetchone()[0]
    r = chem.get("/chem/variant?exam=oge&num=18", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/chem/task/g-o18-")
    assert chem.get("/chem/variant?exam=ege&num=99", follow_redirects=False).status_code == 404
    # программа и ДЗ по теме
    page = chem.get("/chem/teacher/student/%d" % sid).text
    assert "Программа" in page and "Расчёты по уравнению реакции" in page and 'list="chem-topics"' in page
    chem.post("/chem/teacher/student/%d/hw-topic" % sid, data={"topic": "o21", "csrf": t})
    hw = connect().execute("SELECT id, task_ids, title FROM chem_hw WHERE student_id = ?", (sid,)).fetchone()
    assert hw["title"].startswith("Молярная масса") and "g-o18-" in hw["task_ids"]
    # занятие по теме → тема пройдена; листочек
    chem.post("/chem/teacher/lessons", data={"student_id": sid, "day": "2025-10-09", "time": "15:00",
                                            "topic": "Молярная масса. Массовая доля элемента", "csrf": t})
    lid = connect().execute("SELECT id FROM chem_lessons WHERE student_id = ?", (sid,)).fetchone()[0]
    chem.post("/chem/teacher/lesson/%d" % lid, data={"status": "done", "csrf": t})
    assert "✅ Молярная масса" in chem.get("/chem/teacher/student/%d" % sid).text
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    chem.post("/chem/teacher/lesson/%d/file" % lid, data={"csrf": t},
              files=[("files", ("list1.png", _io.BytesIO(png), "image/png")), ("files", ("list2.jpg", _io.BytesIO(png), "image/jpeg"))])
    fids = [r[0] for r in connect().execute("SELECT id FROM chem_lesson_files WHERE lesson_id = ?", (lid,))]
    assert len(fids) == 2
    # ученик: ДЗ с задачами, вариант решается, листочек виден
    s = login_as(chem, "тест", "тест")
    page = chem.get("/chem/hw/%d" % hw["id"]).text
    assert "Задачи с автопроверкой" in page and "?hw=%d" % hw["id"] in page
    gid = [x for x in __import__("json").loads(hw["task_ids"]) if x.startswith("g-")][0]
    ans = chem_gen.task(gid)["answer"]
    r = chem.post("/api/chem/task/%s" % gid, json={"answer": ans, "hw": hw["id"]}, headers={"X-CSRF-Token": s}).json()
    assert r["points"] == 1
    assert "1 из 1" in chem.get("/chem/hw/%d" % hw["id"]).text
    assert "Листочки с занятий" in chem.get("/chem").text
    assert chem.get("/chem/lesson-file/%d" % fids[0]).status_code == 200
    assert "🎲 Новый вариант" in chem.get("/chem/map").text


def test_hw_submit_rules_and_friendly_errors(chem):
    from app import chem as chem_mod
    from app.db import connect
    t = login_as(chem, "teacher")
    chem.post("/chem/teacher/demo", data={"grade": 9, "csrf": t})
    sid = connect().execute("SELECT id FROM users WHERE username = 'тест'").fetchone()[0]
    chem.post("/chem/teacher/student/%d/hw-topic" % sid, data={"topic": "o01", "csrf": t})
    chem.post("/chem/teacher/student/%d/hw" % sid, data={"title": "Текстом", "text": "Опиши опыт", "csrf": t})
    rows = connect().execute("SELECT id, task_ids FROM chem_hw WHERE student_id = ? ORDER BY id", (sid,)).fetchall()
    topic_hw, text_hw = rows[0]["id"], rows[1]["id"]
    s = login_as(chem, "тест", "тест")
    r = chem.post("/chem/hw/%d/submit" % text_hw, data={"answer": "  ", "csrf": s}, follow_redirects=False)
    assert r.headers["location"] == "/chem/hw/%d?err=empty" % text_hw
    assert "пустое ДЗ не отправить" in chem.get(r.headers["location"]).text
    chem.post("/chem/hw/%d/submit" % topic_hw, data={"answer": "", "csrf": s})          # ДЗ с задачами — можно без текста
    assert chem_mod.hw_get(connect(), topic_hw)["status"] == "submitted"
    page = chem.get("/chem/hw/999")
    assert page.status_code == 404 and "Такой страницы нет" in page.text and "detail" not in page.text
    assert chem.get("/api/chem/task/nope/sample").json() == {"detail": "Not Found"}


def test_lab_pages(chem):
    t = login_as(chem, "teacher")
    assert "Атом изнутри" in chem.get("/chem/lab").text
    page = chem.get("/chem/lab/atom?z=16").text
    assert 'id="lab-elements"' in page and "/static/js/lab.js" in page and 'data-z="16"' in page
    chem.post("/chem/teacher/demo", data={"grade": 11, "csrf": t})
    s = login_as(chem, "тест", "тест")
    h = {"X-CSRF-Token": s}
    r = chem.post("/api/chem/lab/atom", json={"z": 6}, headers=h).json()
    assert any("Лаборатория" in n["text"] for n in r["notices"])
    r = chem.post("/api/chem/lab/atom", json={"z": 6}, headers=h).json()       # тот же элемент — без повтора
    assert not r["notices"]


def test_hw_kinds_book_photo_drawing(chem):
    import io as _io
    from app.db import connect
    t = login_as(chem, "teacher")
    chem.post("/chem/teacher/demo", data={"grade": 9, "csrf": t})
    sid = connect().execute("SELECT id FROM users WHERE username = 'тест'").fetchone()[0]
    chem.post("/chem/teacher/student/%d/hw" % sid, data={"kind": "book", "book": "Габриелян О. С. и др. Химия. 9 класс",
                                                       "paragraph": "§ 12", "pages": "45–49", "exercises": "№ 2, 4", "csrf": t})
    hw = connect().execute("SELECT * FROM chem_hw WHERE student_id = ? ORDER BY id DESC", (sid,)).fetchone()
    assert hw["title"] == "Учебник: § 12" and "Страницы: 45–49" in hw["text"] and "№ 2, 4" in hw["text"]
    assert "Габриелян О. С. и др. Химия. 9 класс" in chem.get("/chem/teacher/student/%d" % sid).text   # запомнил учебник
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    chem.post("/chem/teacher/student/%d/hw" % sid, data={"kind": "text", "title": "", "csrf": t},
              files=[("files", ("рисунок-1.png", _io.BytesIO(png), "image/png"))])
    hw2 = connect().execute("SELECT * FROM chem_hw WHERE student_id = ? ORDER BY id DESC", (sid,)).fetchone()
    assert hw2["title"] == "Домашнее задание"
    r = chem.post("/chem/teacher/student/%d/hw" % sid, data={"kind": "text", "csrf": t}, follow_redirects=False)
    assert "hwerr=empty" in r.headers["location"]
    s = login_as(chem, "тест", "тест")
    page = chem.get("/chem/hw/%d" % hw2["id"]).text
    assert "/chem/hw-file/" in page and "data-drawpad" in page
    chem.post("/chem/hw/%d/submit" % hw2["id"], data={"answer": "", "csrf": s},
              files=[("files", ("a.png", _io.BytesIO(png), "image/png")), ("files", ("b.png", _io.BytesIO(png), "image/png"))])
    assert connect().execute("SELECT COUNT(*) FROM chem_hw_files WHERE hw_id = ? AND author = 'student'", (hw2["id"],)).fetchone()[0] == 2
    fid = connect().execute("SELECT id FROM chem_hw_files WHERE hw_id = ? AND author = 'teacher'", (hw2["id"],)).fetchone()[0]
    assert chem.get("/chem/hw-file/%d" % fid).status_code == 200
    t = login_as(chem, "teacher")
    assert page.count("/chem/hw-file/") >= 1 and "Решение" in chem.get("/chem/teacher/hw").text


def test_all_generators_are_consistent():
    """Каждый генератор на сотнях сидов: вариант восстанавливается по id, ответ — номера из списка, даёт полный балл."""
    import re as _re
    from app.content import chem_exam, chem_gen
    from app.content.chem_tasks import grade_answer
    assert len(chem_gen.GENERATORS) >= 28
    for (exam, num), _gen in chem_gen.GENERATORS.items():
        long = num in chem_exam.EXAMS[exam]["long"]
        for seed in range(1, 300):
            tid = "g-%s%d-%d" % (exam[0], num, seed)
            t = chem_gen.task(tid)
            assert t == chem_gen.task(tid), tid
            assert (t["mode"] == "long") == long, tid
            assert t["text"] and t["answer"] and t["why"], tid
            if t["mode"] in ("set", "seq"):
                options = {int(x) for x in _re.findall(r"^(\d)\)", t["text"], _re.M)} | \
                          {int(x) for x in _re.findall(r"(?:^|\s)(\d)\) ", t["text"])}
                if options:                                       # в ОГЭ 2 ответ — сами числа, без списка
                    assert set(int(c) for c in t["answer"]) <= options, (tid, t["answer"], t["text"])
            if t["mode"] == "set":
                assert len(set(t["answer"])) == len(t["answer"]) == 2, tid
            if not long:
                assert grade_answer(t, t["answer"]) == chem_exam.points(exam, num), tid


def test_generator_chemistry_spot_checks():
    """Химия в данных генераторов: пулы не пересекаются, ионные пары и реактивы различения — без двусмысленности."""
    from app.content import chem_gen as g
    for pools in (g.BOND, g.LATTICE, g.CLASSES):
        flat = [f for fs in pools.values() for f in fs]
        assert len(flat) == len(set(flat)), pools
    eqs = [r[0] for r in g.REACTIONS]
    assert len(eqs) == len(set(eqs))
    assert all(r[2] for r in g.REACTIONS if r[1] == "замещения") and not any(r[2] for r in g.REACTIONS if r[1] == "обмена")
    goods = [p for _, gs, _ in g.IONIC for p in gs]
    assert len(goods) == len(set(goods))
    for _, gs, bad in g.IONIC:
        assert not set(gs) & set(bad)
    for name, table, _ in g.DISTINGUISH:
        assert set(table) == set(g.REAGENTS), name
        assert 1 in table.values(), name
    assert g.molar_mass("Cu(OH)2") == 98 and g.molar_mass("BaSO4") == 233 and g.molar_mass("AgCl") == 143.5


def _atoms(side):
    """Атомы одной части уравнения: «2Fe + 3Cl2» → {Fe: 2, Cl: 6}."""
    import re as _re
    from app.content.chem_gen import count_atoms
    total = {}
    for term in side.split(" + "):
        term = _re.sub(r"\((конц\.|разб\.|тв|г|р-р|кат\.)\)|[↓↑]", "", term).strip().replace("[", "(").replace("]", ")")
        m = _re.match(r"^(\d*)(.+)$", term)
        k = int(m.group(1) or 1)
        formula = m.group(2)
        for el in set(_re.findall(r"[A-Z][a-z]?", formula)):
            total[el] = total.get(el, 0) + k * count_atoms(formula, el)
    return total


def test_generator_equations_are_balanced():
    import re as _re
    from app.content import chem_gen as g
    equations = [r[0] for r in g.REACTIONS] + [p[3] for p in g.PRECIPITATE] + [r[1] for r in g.REDOX] + \
        [e for c in g.CHAINS for e in c[1]] + g.EXPERIMENT_EQUATIONS + [r[1] for r in g.REDOX_EGE] + \
        [x[1] for x in g.IONIC_FULL] + [e for _, es in g.DESCRIPTIONS_31 for e in es] + [e for *_, es in g.CHAINS_32 for e in es]
    for chain, eqs, _ in g.CHAINS:                                   # уравнения идут по звеньям цепочки
        links = chain.split(" → ")
        for i, e in enumerate(eqs):
            left, right = e.split(" = ")
            assert links[i] in left and links[i + 1] in right.replace("↓", "").replace("↑", ""), (chain, e)
    for eq in equations:
        left, right = _re.split(r" = | ⇄ ", eq)
        assert _atoms(left) == _atoms(right), eq
    # схема без коэффициентов — те же вещества, что в уравнении
    for scheme, eq, *_ in g.REDOX + g.REDOX_EGE:
        strip = lambda side: sorted(_re.sub(r"^\d+", "", t.strip()) for t in side.split(" + "))  # noqa: E731
        s_left, s_right = scheme.replace("(конц.)", "").replace("(разб.)", "").split(" → ")
        e_left, e_right = eq.split(" = ")
        assert strip(s_left) == strip(e_left) and strip(s_right) == strip(e_right), scheme


def test_reactivity_table_is_consistent():
    from app.content import chem_gen as g
    for x, (_, yes, no) in g.REACTIVITY.items():
        assert not set(yes) & set(no), x
        assert len(yes) >= 2 and len(no) >= 3, x
    # симметрия там, где обе стороны есть в таблице: «HCl реагирует с Fe» ⇔ «Fe реагирует с HCl»
    assert "Fe" in g.REACTIVITY["HCl"][1] and "HCl" in g.REACTIVITY["Fe"][1]
    assert "NaOH" in g.REACTIVITY["CO2"][1] and "CO2" in g.REACTIVITY["NaOH"][1]
    assert "CuSO4" in g.REACTIVITY["NaOH"][1] and "NaOH" in g.REACTIVITY["CuSO4"][1]
    assert "CaO" in g.REACTIVITY["CO2"][1] and "CO2" in g.REACTIVITY["CaO"][1]
    for a in g.REACTIVITY:
        for b in g.REACTIVITY:
            base_b = b.split(" ")[0]
            base_a = a.split(" ")[0]
            if base_b in g.REACTIVITY[a][1] + g.REACTIVITY[a][2] and base_a in g.REACTIVITY[b][1] + g.REACTIVITY[b][2]:
                assert (base_b in g.REACTIVITY[a][1]) == (base_a in g.REACTIVITY[b][1]), (a, b)


def test_ege_generator_data():
    from app.content import chem_gen as g
    for table in (g.ORG_PROPS_12, g.ORG_PROPS_13):
        for q, yes, no in table:
            assert not set(yes) & set(no) and len(yes) >= 2 and len(no) >= 3, q
    names = [n for ns in g.ORG_CLASSES.values() for n in ns]
    assert len(names) == len(set(names))
    apps = [a for _, a in g.APPLICATIONS]
    assert len(apps) == len(set(apps))
    # Ле Шателье: N2 + 3H2 — давление вправо, нагрев влево; H2 + I2 — давление не смещает
    sh = dict(g._shifts(g.EQUILIBRIA[1]))
    assert sh["повышение давления"] == 0 and sh["повышение температуры"] == 1 and sh["увеличение концентрации NH3"] == 1
    assert dict(g._shifts(g.EQUILIBRIA[2]))["повышение давления"] == 2
    assert dict(g._shifts(g.EQUILIBRIA[7]))["добавление твёрдого CaCO3"] == 2


def test_organic_generator_data():
    from app.content import chem_gen as g
    names = [n for ns in g.ISOMERS.values() for n in ns]
    assert len(names) == len(set(names))
    for table, decoys in ((g.REACTIONS_14, g.DECOYS_14), (g.REACTIONS_15, g.DECOYS_15)):
        reactants = [r for r, _ in table]
        assert len(reactants) == len(set(reactants))
        # ловушки — не продукты ни одной реакции своей таблицы, кроме явно повторяющихся по смыслу
        assert not ({p for _, p in table} & set(decoys)) or table is g.REACTIONS_15


def test_ege_calculations():
    """Числа в ЕГЭ 34 и данные ЕГЭ 33 пересчитываются независимо."""
    from app.content import chem_gen as g
    assert round(0.2 * 64, 2) == 12.8 and round((20 - 12.8) / 80, 3) == 0.09 and round(0.29 * 160, 1) == 46.4
    assert round(10.6 / (200 + 4.4) * 100, 2) == 5.19
    assert round(27.75 / (25 + 200 - 11) * 100, 2) == 12.97
    for formula, _, _ in g.ORGANIC_33:
        assert g.molar_mass(formula) == 12 * g.count_atoms(formula, "C") + g.count_atoms(formula, "H") + \
            16 * g.count_atoms(formula, "O")
    for name, _, _, short in g.IONIC_FULL:
        assert "=" in short, name


def test_lab_videos(chem):
    from app.content import chem_videos
    ids = [it["id"] for it in chem_videos.available()]
    assert {"cu_oh2_precipitate", "fe_oh2_precipitate", "baso4_precipitate"} <= set(ids)
    for it in chem_videos.ITEMS:                     # варианты: 4 разных, верный ровно один, без двойников по цвету
        opts = chem_videos.options(it["id"])
        assert len(opts) == len(set(opts)) == 4 and opts.count(it["observe"]) == 1, it["id"]
        assert len({chem_videos._key(o) for o in opts}) == 4, (it["id"], opts)
        assert opts == chem_videos.options(it["id"])
        rg = chem_videos.reagents(it)                  # без реагентов (индикатор, пламя) на вопрос не ответить
        assert rg.endswith("→ ?") and len(rg) > 8 and it["observe"] not in rg, (it["id"], rg)
    assert "фенолфталеин" in chem_videos.reagents(chem_videos.BY_ID["phenolphthalein_naoh_hcl"])
    t = login_as(chem, "teacher")
    assert "Эффектные опыты" in chem.get("/chem/lab").text
    chem.post("/chem/teacher/demo", data={"grade": 9, "csrf": t})
    s = login_as(chem, "тест", "тест")
    page = chem.get("/chem/lab/video").text
    assert "/static/video/chem/cu_oh2_precipitate.mp4" in page and 'data-video-quiz="baso4_precipitate"' in page
    assert "Голубой осадок" not in page                                         # название не подсказывает ответ
    h = {"X-CSRF-Token": s}
    right = chem_videos.options("cu_oh2_precipitate").index("образование голубого осадка")
    r = chem.post("/api/chem/lab/video", json={"id": "cu_oh2_precipitate", "answer": (right + 1) % 4}, headers=h).json()
    assert not r["correct"] and r["right"] == right and not r["notices"] and "<sub>4</sub>" in r["equation_html"]
    r = chem.post("/api/chem/lab/video", json={"id": "cu_oh2_precipitate", "answer": right}, headers=h).json()
    assert r["correct"] and not r["notices"]                  # после ошибки (и перезагрузки) опыт за этот ролик не даётся
    right2 = chem_videos.options("baso4_precipitate").index("образование белого осадка")
    r = chem.post("/api/chem/lab/video", json={"id": "baso4_precipitate", "answer": right2}, headers=h).json()
    assert r["correct"] and any("Лаборатория" in n["text"] for n in r["notices"])
    r = chem.post("/api/chem/lab/video", json={"id": "baso4_precipitate", "answer": right2}, headers=h).json()
    assert r["correct"] and not r["notices"]                                    # опыт за повтор не даётся
    assert chem.post("/api/chem/lab/video", json={"id": "nope", "answer": 0}, headers=h).status_code == 404
    assert chem.get("/static/video/chem/baso4_precipitate.mp4").status_code == 200


def test_mock_exam_flow(chem):
    import io as _io
    from datetime import timedelta
    from app import chem_mock, config
    from app.content import chem_exam
    from app.db import connect
    t = login_as(chem, "teacher")
    chem.post("/chem/teacher/demo", data={"grade": 9, "csrf": t})
    sid = connect().execute("SELECT id FROM users WHERE username = 'тест'").fetchone()[0]
    # преподаватель выдаёт пробник
    chem.post("/chem/teacher/student/%d/mock" % sid, data={"due_at": "2026-10-20", "csrf": t})
    assert "Пробные варианты" in chem.get("/chem/teacher/student/%d" % sid).text
    s = login_as(chem, "тест", "тест")
    page = chem.get("/chem/mock").text
    assert "выдан преподавателем" in page and "Начать новый пробник" not in page          # один незавершённый за раз
    mid = connect().execute("SELECT id FROM chem_mocks WHERE student_id = ?", (sid,)).fetchone()[0]
    m = chem_mock.get(connect(), mid)
    assert [x["num"] for x in m["tasks"]] == list(range(1, 24))                         # все 23 номера ОГЭ
    assert "Начать" in chem.get("/chem/mock/%d" % mid).text
    chem.post("/chem/mock/%d/start" % mid, data={"csrf": s})
    page = chem.get("/chem/mock/%d" % mid).text
    assert 'data-mock-timer="' in page and 'name="a_1"' in page and 'name="a_22"' not in page   # 22 — развёрнутый
    # ответы: все верные в части 1, кроме №1
    m = chem_mock.get(connect(), mid)
    right = {str(x["num"]): chem_mock.get_task(x["id"])["answer"] for x in m["tasks"] if x["num"] not in m["ex"]["long"]}
    answers = dict(right, **{"1": "00"})
    h = {"X-CSRF-Token": s}
    r = chem.post("/api/chem/mock/%d/save" % mid, json={"answers": {"1": "00", "999": "x"}}, headers=h).json()
    assert r["saved"]
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    chem.post("/chem/mock/%d/finish" % mid, data=dict({"a_" + k: v for k, v in answers.items()}, csrf=s),
              files=[("files", ("long1.png", _io.BytesIO(png), "image/png"))])
    m = chem_mock.get(connect(), mid)
    short_max = chem_mock.short_max(m)
    assert m["status"] == "finished" and m["score"] == short_max - 1 and short_max == 24
    assert "999" not in m["answers"]
    page = chem.get("/chem/mock/%d" % mid).text
    assert "ждёт проверки преподавателем" in page and "long1.png" in page
    assert chem.post("/api/chem/mock/%d/save" % mid, json={"answers": {"1": "5"}}, headers=h).json()["saved"] is False
    # попытки пошли в прогноз карты
    assert connect().execute("SELECT COUNT(*) FROM chem_attempts WHERE student_id = ?", (sid,)).fetchone()[0] >= 18
    # преподаватель ставит баллы за развёрнутую часть (с ограничением по максимуму номера)
    login_as(chem, "teacher")
    t = login_as(chem, "teacher")
    assert "ждёт проверки" in chem.get("/chem/teacher/mocks").text
    chem.post("/chem/teacher/mock/%d/grade" % mid, data={"l_20": 3, "l_21": 2, "l_22": 9, "l_23": 4, "comment": "Хорошо", "csrf": t})
    m = chem_mock.get(connect(), mid)
    assert m["status"] == "checked" and m["long_points"] == {"20": 3, "21": 2, "22": 3, "23": 4}
    assert m["score"] == 23 + 12 and m["ex"]["max"] == 38
    # чужой ученик не видит пробник
    _signup(chem, connect().execute("SELECT value FROM settings WHERE key = 'invite_code'").fetchone()[0], 9, "petya9", "Петя")
    assert chem.get("/chem/mock/%d" % mid).status_code == 404
    fid = connect().execute("SELECT id FROM chem_mock_files WHERE mock_id = ?", (mid,)).fetchone()[0]
    assert chem.get("/chem/mock-file/%d" % fid).status_code == 404


def test_mock_time_limit(chem):
    from datetime import timedelta
    from app import chem_mock, config
    from app.db import connect
    t = login_as(chem, "teacher")
    chem.post("/chem/teacher/demo", data={"grade": 11, "csrf": t})
    s = login_as(chem, "тест", "тест")
    chem.post("/chem/mock/new", data={"csrf": s})
    conn = connect()
    mid = conn.execute("SELECT id FROM chem_mocks ORDER BY id DESC").fetchone()[0]
    assert len(chem_mock.get(conn, mid)["tasks"]) == 34
    chem.post("/chem/mock/%d/start" % mid, data={"csrf": s})
    past = (config.now() - timedelta(minutes=5)).isoformat(timespec="seconds")
    with conn:
        conn.execute("UPDATE chem_mocks SET deadline_at = ? WHERE id = ?", (past, mid))
    assert chem.post("/api/chem/mock/%d/save" % mid, json={"answers": {"1": "12"}}, headers={"X-CSRF-Token": s}).json()["saved"] is False
    chem.get("/chem/mock/%d" % mid)                                   # открыл после срока — пробник сдаётся сам
    assert chem_mock.get(connect(), mid)["status"] == "finished"


def test_task_review_hides_from_students(chem):
    from app import chem_review
    from app.db import connect
    t = login_as(chem, "teacher")
    page = chem.get("/chem/teacher/review?exam=oge").text
    assert "Проверка задач" in page and "g-o5-1" in page and "o1a" in page
    h = {"X-CSRF-Token": t}
    assert chem.post("/api/chem/review", json={"item": "o1a", "status": "issue", "comment": "ответ 24 спорный"}, headers=h).json()["ok"]
    chem.post("/api/chem/review", json={"item": "gen:oge:5", "status": "issue", "comment": "SiO2 лучше убрать"}, headers=h)
    chem.post("/api/chem/review", json={"item": "o1b", "status": "ok"}, headers=h)
    assert chem.post("/api/chem/review", json={"item": "zzz", "status": "ok"}, headers=h).status_code == 404
    assert chem.post("/api/chem/review", json={"item": "gen:oge:99", "status": "ok"}, headers=h).status_code == 404
    page = chem.get("/chem/teacher/review?exam=oge&show=issue").text
    assert "o1a: ответ 24 спорный" in page and "gen:oge:5: SiO2 лучше убрать" in page
    assert chem_review.hidden(connect()) == ({"o1a"}, {("oge", 5)})
    chem.post("/chem/teacher/demo", data={"grade": 9, "csrf": t})
    s = login_as(chem, "тест", "тест")
    page = chem.get("/chem/map").text
    assert "/chem/task/o1a" not in page and "/chem/task/o1b" in page and "exam=oge&num=5" not in page
    assert chem.get("/chem/task/o1a").status_code == 404
    chem.post("/chem/mock/new", data={"csrf": s})
    from app import chem_mock
    m = chem_mock.get(connect(), connect().execute("SELECT id FROM chem_mocks ORDER BY id DESC").fetchone()[0])
    by_num = {x["num"]: x["id"] for x in m["tasks"]}
    assert not by_num[5].startswith("g-") and by_num[1] != "o1a"                   # вместо скрытого — банк
    t = login_as(chem, "teacher")
    chem.post("/api/chem/review", json={"item": "o1a", "status": "clear"}, headers={"X-CSRF-Token": t})
    assert chem_review.hidden(connect())[0] == set()


def test_lesson_plan_topics_and_history(chem):
    from app import chem as chem_mod
    from app.db import connect
    t = login_as(chem, "teacher")
    chem.post("/chem/teacher/demo", data={"grade": 9, "csrf": t})
    sid = connect().execute("SELECT id FROM users WHERE username = 'тест'").fetchone()[0]
    for day in ("2025-10-09", "2025-10-16"):
        chem.post("/chem/teacher/lessons", data={"student_id": sid, "day": day, "time": "16:00", "minutes": 60, "csrf": t})
    l1, l2 = [r[0] for r in connect().execute("SELECT id FROM chem_lessons WHERE student_id = ? AND starts_at >= '2025-10-09' "
                                              "ORDER BY starts_at", (sid,))]
    page = chem.get("/chem/teacher/lesson/%d/plan" % l1).text
    assert "Ещё не проходили" in page and "Расчёты по уравнению реакции" in page
    # черновик по двум темам: минуты, опорные пункты, номера
    r = chem.post("/chem/teacher/lesson/%d/plan" % l1, data={"topics": ["o16", "o17", "zzz"], "action": "draft", "plan": "", "csrf": t},
                  follow_redirects=False)
    assert r.status_code == 303
    plan = chem_mod.lesson_plan(connect(), l1)
    assert plan["topic_ids"] == ["o16", "o17"]
    assert "10 мин — разминка" in plan["plan"] and "20 мин — Электролитическая диссоциация" in plan["plan"]
    assert "№13 ОГЭ" in plan["plan"] and "10 мин — итог" in plan["plan"]
    topic = connect().execute("SELECT topic FROM chem_lessons WHERE id = ?", (l1,)).fetchone()[0]
    assert topic == "Электролитическая диссоциация; Реакции ионного обмена. Ионные уравнения"
    # правка текста сохраняется как есть
    chem.post("/chem/teacher/lesson/%d/plan" % l1, data={"topics": ["o16", "o17"], "action": "save", "plan": "мой план", "csrf": t})
    assert chem_mod.lesson_plan(connect(), l1)["plan"] == "мой план"
    page = chem.get("/chem/teacher/lesson/%d/plan" % l1).text
    assert "мой план" in page and "/chem/task/" in page and "Задачи для разбора" in page
    # на втором занятии видно, что темы уже в плане на 09.10; пока не проведено — не пройдены
    page = chem.get("/chem/teacher/lesson/%d/plan" % l2).text
    assert "в плане на 09.10" in page and "пройдено 09.10" not in page
    assert chem_mod.covered_topics(connect(), sid) == {}
    chem.post("/chem/teacher/lesson/%d" % l1, data={"status": "done", "csrf": t})
    covered = chem_mod.covered_topics(connect(), sid)
    assert covered == {"Электролитическая диссоциация": "2025-10-09", "Реакции ионного обмена. Ионные уравнения": "2025-10-09"}
    page = chem.get("/chem/teacher/lesson/%d/plan" % l2).text
    assert "пройдено 09.10" in page and "Уже пройдено" in page
    page = chem.get("/chem/teacher/student/%d" % sid).text
    assert "пройдено 2 из" in page and "· 09.10.25" in page and "/chem/teacher/lesson/%d/plan" % l1 in page
    # ученику план недоступен
    s = login_as(chem, "тест", "тест")
    assert chem.get("/chem/teacher/lesson/%d/plan" % l1, follow_redirects=False).status_code in (303, 403, 404)
    assert chem.post("/chem/teacher/lesson/%d/plan" % l1, data={"topics": ["o01"], "plan": "x", "csrf": s}).status_code in (403, 404)
    assert chem_mod.lesson_plan(connect(), l1)["plan"] == "мой план"


def test_qa_fixes_lessons_xp_and_inputs(chem):
    from app import chem as chem_mod, game
    from app.db import connect
    t = login_as(chem, "teacher")
    chem.post("/chem/teacher/demo", data={"grade": 9, "csrf": t})
    sid = connect().execute("SELECT id FROM users WHERE username = 'тест'").fetchone()[0]
    # будущее занятие не отметить «Был»; прошедшее — опыт один раз, даже если снять отметку и поставить снова
    chem.post("/chem/teacher/lessons", data={"student_id": sid, "day": "2099-01-05", "time": "16:00", "weeks": 4,
                                            "topic": "Соли", "csrf": t})
    fut = [r[0] for r in connect().execute("SELECT id FROM chem_lessons WHERE starts_at LIKE '2099-%' ORDER BY starts_at")]
    assert len(fut) == 4
    assert [r[0] for r in connect().execute("SELECT topic FROM chem_lessons WHERE starts_at LIKE '2099-%' ORDER BY starts_at")] \
        == ["Соли", "", "", ""]
    assert chem_mod.lesson_plan(connect(), fut[0])["topic_ids"] == ["o10"]
    assert chem.post("/chem/teacher/lesson/%d" % fut[0], data={"status": "done", "csrf": t}).status_code == 400
    # удалить серию со второго занятия
    chem.post("/chem/teacher/lesson/%d" % fut[1], data={"status": "delete_series", "csrf": t})
    assert connect().execute("SELECT COUNT(*) FROM chem_lessons WHERE starts_at LIKE '2099-%'").fetchone()[0] == 1
    chem.post("/chem/teacher/lessons", data={"student_id": sid, "day": "2025-01-05", "time": "16:00", "csrf": t})
    lid = connect().execute("SELECT id FROM chem_lessons WHERE starts_at LIKE '2025-01-05%'").fetchone()[0]
    for st in ("done", "planned", "done", "planned", "done"):
        chem.post("/chem/teacher/lesson/%d" % lid, data={"status": st, "csrf": t})
    assert game.awarded(connect(), sid, "lesson", str(lid)) == 15
    # плохие данные — 400, а не 500
    assert chem.post("/chem/teacher/lessons", data={"student_id": sid, "day": "2025-01-06", "time": "16:00",
                                                   "minutes": -60, "csrf": t}).status_code == 400
    assert chem.get("/chem/teacher/money?month=2026-13").status_code == 200
    assert chem.get("/chem/teacher/schedule?start=0001-01-01").status_code == 200
    assert chem.post("/chem/teacher/student/%d/payment" % sid, data={"amount": "1 000", "paid_at": "x", "csrf": t}).status_code == 400
    chem.post("/chem/teacher/student/%d/payment" % sid, data={"amount": "1 000", "paid_at": "2025-01-06", "note": "=1+1", "csrf": t})
    assert "'=1+1" in chem.get("/chem/teacher/money.csv?month=2025-01").text
    assert chem.post("/api/chem/review", content="[1]", headers={"X-CSRF-Token": t, "Content-Type": "application/json"}).status_code == 400
    # ДЗ по теме только с письменными номерами — условие задачи в тексте
    chem.post("/chem/teacher/student/%d/hw-topic" % sid, data={"topic": "o22", "csrf": t})
    text = connect().execute("SELECT text FROM chem_hw WHERE student_id = ? ORDER BY id DESC", (sid,)).fetchone()[0]
    assert "Письменно, №22 ОГЭ" in text and "ответ проверяется сразу" not in text


def test_qa_fixes_student_side(chem):
    from app import game
    from app.content import chem_gen
    from app.db import connect
    t = login_as(chem, "teacher")
    chem.post("/chem/teacher/demo", data={"grade": 9, "csrf": t})
    sid = connect().execute("SELECT id FROM users WHERE username = 'тест'").fetchone()[0]
    s = login_as(chem, "тест", "тест")
    h = {"X-CSRF-Token": s}
    # страницы курса Python на сайте химии закрыты
    for path in ("/achievements", "/shop", "/trainer", "/playground", "/cheatsheet", "/daily"):
        assert chem.get(path, follow_redirects=False).status_code == 404, path
    assert chem.get("/checks").status_code == 200
    # после показа ответа (3 неверные попытки) верный ответ не засчитывается
    tid = chem_gen.new_id("oge", 3)
    task = chem_gen.task(tid)
    for _ in range(3):
        chem.post("/api/chem/task/" + tid, json={"answer": "0"}, headers=h)
    r = chem.post("/api/chem/task/" + tid, json={"answer": task["answer"]}, headers=h).json()
    assert r["after_reveal"] and game.awarded(connect(), sid, "chem", tid) == 0
    assert connect().execute("SELECT MAX(points) FROM chem_attempts WHERE task_id = ?", (tid,)).fetchone()[0] == 0
    # уведомления — про опыт, не про трофеи
    tid2 = chem_gen.new_id("oge", 3)
    r = chem.post("/api/chem/task/" + tid2, json={"answer": chem_gen.task(tid2)["answer"]}, headers=h).json()
    assert any("опыта" in n["text"] for n in r["notices"]) and not any("трофе" in n["text"] for n in r["notices"])
    # плохой JSON — 400
    assert chem.post("/api/chem/task/" + tid2, content="[1]", headers={**h, "Content-Type": "application/json"}).status_code == 400



def test_answer_formats_and_profile(chem):
    from app.content.chem_tasks import grade_answer
    from app.db import connect
    assert grade_answer({"exam": "oge", "num": 1, "mode": "set", "answer": "24"}, "2,4") == 1
    assert grade_answer({"exam": "oge", "num": 10, "mode": "seq", "answer": "312"}, "3-1-2") == 2
    assert grade_answer({"exam": "oge", "num": 18, "mode": "num", "answer": "60"}, "60 %") == 1
    assert grade_answer({"exam": "oge", "num": 18, "mode": "num", "answer": "60"}, "6O") == 0
    t = login_as(chem, "teacher")
    chem.post("/chem/teacher/demo", data={"grade": 9, "csrf": t})
    s = login_as(chem, "тест", "тест")
    assert "Сменить пароль" in chem.get("/chem/me").text
    assert "err=old" in chem.post("/chem/me/password", data={"old": "x", "new": "новый-пароль", "new2": "новый-пароль", "csrf": s},
                                  follow_redirects=False).headers["location"]
    chem.post("/chem/me/password", data={"old": "тест", "new": "новый-пароль", "new2": "новый-пароль", "csrf": s})
    assert login_as(chem, "тест", "новый-пароль")
    assert chem.get("/chem/me").status_code == 200
    t = login_as(chem, "teacher")
    assert chem.get("/chem/me", follow_redirects=False).status_code in (303, 403, 404)
