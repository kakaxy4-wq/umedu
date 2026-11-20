"""Номера, которые раньше отправляли в банк ФИПИ, решаются на сайте.

Проверка ответа не доверяет строке из генератора вслепую: для расчётов тест пересчитывает
результат из data, для выбора — что номер варианта указывает на верную формулировку.
"""
import re
from pathlib import Path

import pytest

from test_app import client  # noqa: F401

from app import exam_model as em
from app import u2_onsite
from app.content import onsite_extra
from app.content.extra_math import recompute as math_value

ROOT = Path(__file__).resolve().parent.parent

# Ссылки, которые ученик видит не как задание: политика, исходный код, лицензии моделей.
ALLOW_URL_FILES = {
    "app/templates/privacy.html",
    "app/templates/login.html",
    "app/templates/landing.html",
    "app/templates/u2/models_phet.html",
    "app/templates/u2/models_circuits.html",
    "app/templates/u2/models_micro.html",
    "app/templates/u2/models_mol.html",
    "app/templates/u2/models_optics.html",
    "app/templates/student/oge.html",
}

GO_ELSEWHERE = re.compile(
    r"открыт\w* банк|своего сборника|своих источник|зайди на сайт|порешай|"
    r"найди в учебнике|в учебнике|из учебника|решу огэ|решу егэ|fipi\.ru|"
    r"за пределами сайта|вне сайта|отметь, сколько баллов|отметь выполнен",
    re.I,
)
URL = re.compile(r"https?://[^\s\"'<>]+", re.I)
ALLOW_URL = re.compile(r"^https?://(www\.)?w3\.org/", re.I)


def test_no_self_check_numbers_left():
    """Самопроверки с уходом на ФИПИ нет. Номер без честного задания — «скоро», не в плане."""
    soon = []
    for exam_id in em.all_ids():
        for key in em.points(em.load(exam_id)):
            mode = u2_onsite.mode_of(exam_id, key)
            assert mode != "self", (exam_id, key)
            if mode == "soon":
                soon.append((exam_id, key))
                assert key not in u2_onsite.onsite(exam_id)
            else:
                assert key in u2_onsite.onsite(exam_id)
    assert ("ege-eng-2026", 1) in soon and ("oge-math-2026", 22) in soon
    assert ("ege-math-profile-2026", 17) in soon


def test_extra_answers_recomputed():
    for (exam_id, key), fn in onsite_extra.FUNCS.items():
        assert (exam_id, key) in onsite_extra.ABOUT
        for seed in (1, 2, 7, 40):
            v = onsite_extra.make(exam_id, key, seed)
            assert v == onsite_extra.make(exam_id, key, seed)
            assert onsite_extra.check(v, v["answer"])
            assert not onsite_extra.check(v, v["answer"] + "нет")
            assert "fipi" not in v["text"].lower() and "http://" not in v["text"] and "https://" not in v["text"]
            data = v.get("data") or {}
            if data.get("kind") == "choice":
                n = int(v["answer"])
                assert data["options"][n - 1] == data["right"]
            else:
                again = onsite_extra.value_of(v)
                assert str(again) == str(v["answer"]) or _same_number(again, v["answer"])
            if exam_id.startswith(("oge-math", "ege-math")) and data.get("kind") not in ("choice", None):
                assert str(math_value(data)) == str(v["answer"]) or _same_number(math_value(data), v["answer"])


def _same_number(a, b):
    from app.content.math_gen import _num
    x, y = _num(a), _num(b)
    return x is not None and x == y


def test_replaced_task_page_checks_answer(client, monkeypatch):
    from app import config
    from test_app import login
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "ege-hist-2026", "goal": 60})
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-math-2026", "goal": 4})
    page = client.get("/u2/train/ege-hist-2026/1?seed=3").text
    assert "открытого банка" not in page and "fipi.ru" not in page and 'name="answer"' in page
    right = onsite_extra.make("ege-hist-2026", 1, 3)["answer"]
    assert "Верно" in client.post("/u2/train/ege-hist-2026/1",
                                  data={"csrf": csrf, "seed": 3, "answer": right}).text
    bad = client.post("/u2/train/oge-math-2026/20", data={"csrf": csrf, "seed": 8, "answer": "999999"}).text
    assert "Пока не то" in bad and "Верно" not in bad.split("Пока не то")[0]


def test_task_copy_has_no_go_elsewhere():
    roots = [
        ROOT / "app" / "templates" / "u2" / "train.html",
        ROOT / "app" / "templates" / "u2" / "lab.html",
        ROOT / "app" / "templates" / "u2" / "mistakes.html",
        ROOT / "app" / "templates" / "student" / "lesson.html",
        ROOT / "app" / "templates" / "student" / "task.html",
    ]
    blobs = []
    for path in roots:
        blobs.append((str(path.relative_to(ROOT)), path.read_text(encoding="utf-8")))
    from app.content.lessons import LESSONS
    from app.content.tasks import TASKS
    from app.content.primary_tasks import TASKS as PRIMARY
    for lesson in LESSONS:
        blobs.append(("lesson-%s" % lesson["num"], " ".join([
            lesson.get("intro") or "", lesson.get("homework") or "", lesson.get("star") or ""])))
    for task in list(TASKS) + list(PRIMARY):
        blobs.append((task["id"], " ".join(str(task.get(k) or "") for k in ("text", "hint", "title"))))
    bad = []
    for name, text in blobs:
        if GO_ELSEWHERE.search(text):
            bad.append((name, "фраза", GO_ELSEWHERE.search(text).group(0)))
        for url in URL.findall(text):
            if not ALLOW_URL.match(url):
                bad.append((name, "ссылка", url))
    assert bad == []


def test_student_templates_urls_are_allowlisted():
    """Внешние адреса в шаблонах ученика — только из явного списка (не условия заданий)."""
    found = []
    base = ROOT / "app" / "templates"
    for path in base.rglob("*.html"):
        rel = path.relative_to(ROOT).as_posix()  # прямые слэши и на Windows — иначе guides/ не исключить
        if rel.startswith("app/templates/chem/") or rel.startswith("app/templates/guides/"):
            continue
        text = path.read_text(encoding="utf-8")
        urls = [u for u in URL.findall(text) if not ALLOW_URL.match(u)]
        if urls and rel not in ALLOW_URL_FILES:
            found.append((rel, urls))
    assert found == []


_SERVICE = (
    "как единственная норма", "как единственный смысл", "для угля всегда",
    "wrongly", "Solve for", "Article 1", "сердце в колене", "любой камень",
    "посадник всегда", "по действующей норме", "как минимальный возраст",
    "дёшево, часто", "для вопроса выберем",
    "в значении императива", "химический элемент только", "при двух основах", "надо сужать",
    "платочный мама", "мамин из платка",
)
_LATIN = re.compile(r"[A-Za-z]{4,}")
_LATIN_OK = {"true", "false", "none", "html", "href"}
_ROMAN = re.compile(r"^[IVXLCDM]+$")


def test_russian_variants_have_no_service_or_latin():
    bad = []
    for (exam_id, key) in onsite_extra.FUNCS:
        if exam_id.endswith("eng-2026"):
            continue
        for seed in (1, 2, 3):
            v = onsite_extra.make(exam_id, key, seed)
            blob = v["text"] + " " + " ".join((v.get("data") or {}).get("options") or [])
            for phrase in _SERVICE:
                if phrase.lower() in blob.lower():
                    bad.append((exam_id, key, phrase))
            if exam_id.split("-")[1] in ("rus", "hist", "soc", "lit", "bio", "geo"):
                words = [w for w in _LATIN.findall(blob) if w.lower() not in _LATIN_OK and not _ROMAN.match(w)]
                if words:
                    bad.append((exam_id, key, words[:4]))
    assert bad == []


def test_units_and_paren_are_accepted():
    v = {"answer": "30", "data": {"kind": "digits"}}
    assert onsite_extra.check(v, "30 м/с") and onsite_extra.check(v, "30м/с")
    v2 = {"answer": "3"}
    assert onsite_extra.check(v2, "3)") and onsite_extra.check(v2, "3.")


def test_practice_does_not_move_forecast_and_twins_differ():
    assert onsite_extra.is_practice("ege-rus-2026", 27)
    assert not onsite_extra.is_practice("ege-rus-2026", 4)
    a = onsite_extra.make("ege-phys-2026", 5, 1)["text"]
    b = onsite_extra.make("ege-phys-2026", 6, 1)["text"]
    assert a != b
    assert onsite_extra.make("ege-phys-2026", 9, 1)["text"] != onsite_extra.make("ege-phys-2026", 10, 1)["text"]
    same = [key for key in onsite_extra.FUNCS if not onsite_extra.varies(*key)]
    assert same == []


def test_practice_attempt_keeps_forecast(client, monkeypatch):
    from app import config, knowledge as kn
    from app.db import connect
    from test_app import login, sid_of
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "ege-rus-2026", "goal": 70})
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "ege-eng-2026", "goal": 70})
    before = kn.forecast(em.load("ege-rus-2026"), kn.load_states(connect(), sid_of(), "ege-rus-2026"))
    page = client.get("/u2/train/ege-rus-2026/27?seed=2").text
    assert "на прогноз балла не влияет" in page and "fipi" not in page.lower()
    right = onsite_extra.make("ege-rus-2026", 27, 2)["answer"]
    client.post("/u2/train/ege-rus-2026/27", data={"csrf": csrf, "seed": 2, "answer": right})
    after = kn.forecast(em.load("ege-rus-2026"), kn.load_states(connect(), sid_of(), "ege-rus-2026"))
    assert before["test"] == after["test"]
    assert 27 not in kn.load_states(connect(), sid_of(), "ege-rus-2026")
    hidden = client.get("/u2/train/ege-eng-2026/1").text
    assert "Скоро" in hidden and "fipi" not in hidden.lower()


def test_quantity_change_answers_match_the_story():
    """Эталон «две цифры» должен совпадать с тем, что написано в условии. Все ветки, не один сид."""
    rules = (
        ("β-распад", "31"),
        ("α-распад", "22"),
        ("силу тяги увеличивают, масса та же", "31"),
        ("массу увеличивают, сила тяги та же", "12"),
        ("массу уменьшают, сила тяги та же", "21"),
        ("Идеальный газ нагревают", "11"),
        ("Идеальный газ охлаждают", "22"),
        ("Идеальный газ расширяется", "11"),
        ("Идеальный газ сжимается", "22"),
        ("резистора увеличивают", "12"),
        ("резистора уменьшают", "21"),
    )
    seen = set()
    for (exam_id, key), _fn in onsite_extra.FUNCS.items():
        if "phys" not in exam_id:
            continue
        for seed in range(1, 41):
            v = onsite_extra.make(exam_id, key, seed)
            if (v.get("data") or {}).get("kind") != "digits":
                continue
            for phrase, expect in rules:
                if phrase in v["text"]:
                    seen.add(phrase)
                    assert v["answer"] == expect, (exam_id, key, seed, phrase, v["answer"], v["explain"])
                    assert expect in v["explain"] or expect in "".join(v["steps"])
    assert seen == {phrase for phrase, _expect in rules}


def test_mock_skips_practice_numbers(client, monkeypatch):
    from app import config, knowledge as kn
    from app.db import connect
    from test_app import login, sid_of
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "ege-rus-2026", "goal": 70})
    page = client.get("/u2/mock/ege-rus-2026?seed=3").text
    assert "/27" not in page and "№27" not in page
    before = kn.load_states(connect(), sid_of(), "ege-rus-2026")
    client.post("/u2/mock/ege-rus-2026", data={"csrf": csrf, "seed": 3})
    after = kn.load_states(connect(), sid_of(), "ege-rus-2026")
    assert 27 not in after
    assert before.get(4, {}).get("n", 0) <= after.get(4, {}).get("n", 0)


def test_goal_path_skips_hidden_and_puts_practice_last(client, monkeypatch):
    from app import config
    from test_app import login
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = login(client, "student")
    assert client.post("/u2/start", data={"csrf": csrf, "exam_id": "ege-lit-2026", "goal": 40}).status_code == 400
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "ege-rus-2026", "goal": 70})
    page = client.get("/u2/subject/ege-rus-2026").text
    assert "Скоро" not in page.split("Путь к цели")[-1].split("Дальше — тренировка")[0]
    assert "Дальше — тренировка" in page and "№27" in page.split("Дальше — тренировка")[-1]


def kim_status_markdown():
    lines = ["# Номер → тема КИМ → статус", "",
             "Источник правды для заданий umedu. Сомнение в теме номера — статус «скрыт».",
             "«генератор» — задание было на сайте до замены банка.",
             "«соответствует» — новое задание по теме номера, влияет на прогноз.",
             "«тренировка» — срез навыка, прогноз не меняет.",
             "«скрыт» — страницы задания нет в плане.", ""]
    for exam_id in em.all_ids():
        ex = em.load(exam_id)
        lines.append("## %s" % exam_id)
        lines.append("")
        lines.append("| № | Тема | Баллы | Статус |")
        lines.append("|---|---|---|---|")
        titles, points = {}, {}
        for t in em.tasks(ex):
            titles[t["n"]] = t.get("title") or "—"
            points[t["n"]] = t.get("points")
        for c in ex.get("criteria") or []:
            titles[c["id"]] = c.get("name") or "критерий"
            points[c["id"]] = c.get("points")
        for key in em.points(ex):
            mode = u2_onsite.mode_of(exam_id, key)
            if mode == "soon":
                label = "скрыт"
            elif onsite_extra.is_practice(exam_id, key):
                label = "тренировка"
            elif onsite_extra.has(exam_id, key):
                label = "соответствует"
            else:
                label = "генератор"
            lines.append("| %s | %s | %s | %s |" % (key, titles.get(key) or "—", points.get(key, ""), label))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def test_inf20_losing_position_is_not_trivial():
    """ЕГЭ информатика №20: ответ не «1» и разбор называет ходы этого варианта."""
    for seed in range(1, 41):
        v = onsite_extra.make("ege-inf-2026", 20, seed)
        assert int(v["answer"]) > 1, (seed, v["text"], v["answer"])
        moves = (v.get("data") or {}).get("moves")
        assert moves and all(str(m) in v["explain"] for m in moves)
        assert "кратные 3" not in v["explain"] or moves == [1, 2]


def test_kim_status_table_is_committed():
    path = ROOT / "docs" / "kim-status-table.md"
    assert path.read_text(encoding="utf-8") == kim_status_markdown()
