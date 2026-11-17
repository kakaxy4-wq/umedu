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
    missing = []
    for exam_id in em.all_ids():
        for key in em.points(em.load(exam_id)):
            if u2_onsite.mode_of(exam_id, key) == "self":
                missing.append((exam_id, key))
            assert key in u2_onsite.onsite(exam_id)
    assert missing == []


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
        ROOT / "app" / "templates" / "student" / "oge.html",
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
        rel = str(path.relative_to(ROOT))
        if rel.startswith("app/templates/chem/") or rel.startswith("app/templates/guides/"):
            continue
        text = path.read_text(encoding="utf-8")
        urls = [u for u in URL.findall(text) if not ALLOW_URL.match(u)]
        if urls and rel not in ALLOW_URL_FILES:
            found.append((rel, urls))
    assert found == []
