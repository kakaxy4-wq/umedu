"""«Разобраться»: теория перед номером, правило двух ошибок, безопасный рендер markdown и формул."""
import re

import pytest

from app import config, texmath, theory
from test_app import client, login  # noqa: F401 — общая фикстура с тестовой базой

OFFER_SHOWN = re.compile(r"data-th-offer>")
OFFER_HIDDEN = re.compile(r"data-th-offer hidden>")


# ---------------------------------------------------------------- контент

def test_all_theory_files_parse_and_fit_exams():
    items = theory.all_items()
    assert len(items) >= 80
    for (exam_id, key), it in items.items():
        assert theory.valid_for_exam(it), it["slug"]
        assert it["status"] in ("verified", "draft"), it["slug"]
        for part in ("rule", "example", "mistakes"):
            assert len(str(it[part])) > 200, (it["slug"], part)
        assert 2 <= it["minutes"] <= 6, it["slug"]               # «как семечки»: шаг — пара минут


def test_theory_content_is_clean():
    for it in theory.all_items().values():
        html = "".join(str(it[p]) for p in ("rule", "example", "mistakes", "deep"))
        assert "th-tex" not in html, it["slug"]                   # каждая формула разобралась в MathML
        assert "<details" not in html and "&lt;details" not in html, it["slug"]
        assert "генератор" not in html.lower(), it["slug"]        # внутренняя кухня сайта ученику не видна
        if "-rus-" in it["slug"]:                               # служебные номера слов тренажёра русского
            assert not re.search(r"позици[яи] \d", html), it["slug"]
        for ans in re.findall(r'<p class="th-answer">(.*?)</p>', html):
            assert not re.sub(r"<[^>]+>", "", ans).rstrip().endswith("."), (it["slug"], ans)


def test_oge_rus_2_and_3_use_different_examples():
    a, b = theory.get("oge-rus-2026", 2), theory.get("oge-rus-2026", 3)
    ex = lambda it: re.search(r"«([^»]+)»", re.sub(r"<[^>]+>", "", str(it["example"]))).group(1)
    assert ex(a) != ex(b)


def test_only_verified_theory_is_shown(tmp_path, monkeypatch):
    (tmp_path / "oge-math-01.md").write_text(_md(status="draft"), encoding="utf-8")
    (tmp_path / "oge-math-02.md").write_text(_md(kim=2), encoding="utf-8")
    monkeypatch.setattr(theory, "ROOT", tmp_path)
    theory._all.cache_clear()
    try:
        assert theory.get("oge-math-2026", 1) is None and not theory.has("oge-math-2026", 1)
        assert theory.get("oge-math-2026", 2)["topic"] == "Тест"
        assert theory.keys_for("oge-math-2026") == {2}
    finally:
        theory._all.cache_clear()


# ---------------------------------------------------------------- безопасность рендера

XSS = [
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    "[ссылка](javascript:alert(1))",
    "**<svg onload=alert(1)>**",
    "`<script>x</script>`",
    r"$\text{<script>alert(1)</script>}$",
    r"$x<y>z$",
    r"$\operatorname{<b>}$",
    r"$\unknown{<i>}$",
    '| <b onmouseover="x">a</b> | b |\n|---|---|\n| <script> | "x" |',
    "```<script>\n</code><script>alert(1)</script>\n```",
    "$$\\frac{<a href='javascript:x'>}{2}$$",
]


ALLOWED_TAGS = {"p", "strong", "em", "code", "pre", "br", "ul", "ol", "li", "div", "span", "h1", "h2", "h3", "h4",
                "table", "thead", "tbody", "tr", "th", "td", "math", "mrow", "mi", "mn", "mo", "mtext", "mfrac", "msup",
                "msub", "msubsup", "msqrt", "mroot", "mover", "munder", "mspace"}
ALLOWED_ATTRS = {"class", "aria-label", "display", "stretchy", "accent", "width", "mathvariant", "linethickness", "start",
                 "data-lang", "form"}


@pytest.mark.parametrize("src", XSS)
def test_markdown_escapes_html(src):
    html = "".join(theory.blocks(src))
    for tag, attrs in re.findall(r"<([a-zA-Z][\w-]*)([^>]*)>", html):
        assert tag in ALLOWED_TAGS, (tag, html)
        for name in re.findall(r"([\w-]+)=", attrs):
            assert name in ALLOWED_ATTRS, (name, html)
    assert "<script" not in html and "javascript:" not in re.sub(r">[^<]*<", "><", html)


def test_markdown_basics():
    html = "".join(theory.blocks("**Шаг 1.** Делим.\n\nОтвет: 1,5\n\n- раз\n- два\n\n1. первый\n2. второй"))
    assert '<span class="th-step-n" aria-label="Шаг 1">1</span><p>Делим.</p>' in html
    assert '<p class="th-answer">Ответ: 1,5</p>' in html
    assert "<ul><li>раз</li><li>два</li></ul>" in html and "<ol><li>первый</li>" in html
    table = "".join(theory.blocks("| a | b |\n|---|---|\n| 1 | $x^2$ |"))
    assert "<th>a</th>" in table and "<msup><mi>x</mi><mn>2</mn></msup>" in table


def test_texmath():
    assert texmath.to_mathml(r"\frac12") == "<math><mfrac><mn>1</mn><mn>2</mn></mfrac></math>"
    assert "<msqrt>" in texmath.to_mathml(r"\sqrt{x}") and "<mroot>" in texmath.to_mathml(r"\sqrt[3]{8}")
    assert "<mn>1,5</mn>" in texmath.to_mathml("1,5") and "<mo>≤</mo>" in texmath.to_mathml(r"x\le 2")
    assert 'display="block"' in texmath.to_mathml("x", display=True)
    assert texmath.render(r"\frac{1}") .startswith('<code class="th-tex">')     # битая формула — как есть
    assert texmath.render("{" * 100 + "x" + "}" * 100).startswith('<code class="th-tex">')
    assert "&lt;" in texmath.render(r"\text{<b>}")
    assert texmath.to_mathml("-3") == '<math><mrow><mo form="prefix">−</mo><mn>3</mn></mrow></math>'
    assert '<mo>−</mo>' in texmath.to_mathml("a-3") and 'form="prefix"' in texmath.to_mathml("(-x)")


# ---------------------------------------------------------------- шаг на сайте

def _md(status="verified", kim=1, body_extra=""):
    filler = "Слово " * 60
    return (f"---\nexam: ОГЭ\nsubject: математика\nkim_number: {kim}\ntopic: Тест\nsource: ФИПИ\nstatus: {status}\n---\n\n"
            f"# Разобраться: №{kim}\n\n## Правило\n\n{filler}{body_extra}\n\n## Разобранный пример\n\n{filler}\n\nОтвет: 1\n\n"
            f"## Типичные ошибки\n\n- {filler}\n\n## Углубиться\n\n<details>\n<summary>{body_extra or 'Глубже'}</summary>\n\n"
            f"{filler}\n\n</details>\n")


def _enroll(client, exam_id, goal=4):
    monkey_csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": monkey_csrf, "exam_id": exam_id, "goal": goal})
    return monkey_csrf


def test_step_before_number_and_page(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "UMEDU2", True)
    _enroll(client, "oge-math-2026")
    page = client.get("/u2/train/oge-math-2026/9?seed=11").text
    assert "Шаг 1 из 2" in page and 'href="/u2/learn/oge-math-2026/9"' in page
    assert 'name="answer"' in page                                   # задание не прячем: шаг можно пропустить
    learn = client.get("/u2/learn/oge-math-2026/9")
    assert learn.status_code == 200
    for word in ("Правило", "Разобранный пример", "Типичные ошибки", "Углубиться", "<math", "Проверено",
                 'href="/u2/train/oge-math-2026/9"', "<details"):
        assert word in learn.text, word
    page = client.get("/u2/train/oge-math-2026/9?seed=11").text
    assert "Шаг 1 из 2" not in page and 'class="th-chip"' in page   # шаг пройден — остаётся ссылка «Теория»


def test_number_without_theory_works_without_step(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "UMEDU2", True)
    _enroll(client, "oge-math-2026")
    assert not theory.has("oge-math-2026", 20)
    page = client.get("/u2/train/oge-math-2026/20?seed=5")
    assert page.status_code == 200 and "th-step-card" not in page.text and "data-th-offer" not in page.text
    assert client.get("/u2/learn/oge-math-2026/20").status_code == 404
    assert client.get("/u2/learn/oge-math-2026/999").status_code == 404
    assert client.get("/u2/learn/ege-inf-2026/2").status_code == 404     # экзамен не выбран


def test_two_wrong_in_a_row_offers_theory(client, monkeypatch):  # noqa: F811
    from app.content import math_gen as mg
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = _enroll(client, "oge-math-2026")
    url = "/u2/train/oge-math-2026/9"
    res = client.post(url, data={"csrf": csrf, "seed": 11, "answer": "999999"}).text
    assert "Пока не то" in res and OFFER_HIDDEN.search(res)          # одна ошибка — рано
    res = client.post(url, data={"csrf": csrf, "seed": 11, "answer": "999999", "hint": 1}).text
    assert "Неверно" in res and OFFER_SHOWN.search(res) and "Вернуться к теории" in res
    learn = client.get("/u2/learn/oge-math-2026/9").text
    assert "Две ошибки подряд" in learn                              # страница теории знает, зачем ученик пришёл
    res = client.post(url, data={"csrf": csrf, "seed": 12, "answer": "999999"}).text
    assert OFFER_HIDDEN.search(res)                                  # теория открыта — счёт заново
    res = client.post(url, data={"csrf": csrf, "seed": 12, "answer": mg.OGE.make(9, 12)["answer"], "hint": 1}).text
    assert "Верно" in res and OFFER_HIDDEN.search(res)
    res = client.post(url, data={"csrf": csrf, "seed": 13, "answer": "999999"}).text
    assert OFFER_HIDDEN.search(res)                                  # верный ответ обнулил счётчик


def test_two_wrong_in_russian_trainer_api(client, monkeypatch):  # noqa: F811
    from app import u2_onsite
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = _enroll(client, "oge-rus-2026")
    item = u2_onsite.ru_item("oge-rus-2026", 2, 7)
    body = {"id": item["id"], "seed": 7, "answer": {}, "hint": 0}
    hdr = {"X-CSRF-Token": csrf}
    first = client.post("/u2/api/ru/oge-rus-2026/2", json=body, headers=hdr).json()
    assert first["pending"] and "theory" not in first
    second = client.post("/u2/api/ru/oge-rus-2026/2", json={**body, "hint": 1}, headers=hdr).json()
    assert second["theory"] == "/u2/learn/oge-rus-2026/2"
    page = client.get("/u2/train/oge-rus-2026/2?seed=7").text
    assert "data-th-offer" in page                                    # карточку покажет u2.js по ответу API


def test_learn_page_escapes_file_content(client, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(config, "UMEDU2", True)
    evil = "<script>alert(1)</script><img src=x onerror=alert(2)>"
    (tmp_path / "oge-math-01.md").write_text(_md(body_extra=evil), encoding="utf-8")
    monkeypatch.setattr(theory, "ROOT", tmp_path)
    theory._all.cache_clear()
    try:
        _enroll(client, "oge-math-2026")
        html = client.get("/u2/learn/oge-math-2026/1").text
        assert "Тест" in html and "<script>alert" not in html and "<img src=x" not in html
        assert "&lt;script&gt;" in html
    finally:
        theory._all.cache_clear()


# ---------------------------------------------------------------- теория в плане дня

def test_fit_plan_counts_unread_theory():
    items = [{"n": 9, "minutes": 6, "times": 2}, {"n": 10, "minutes": 3, "times": 1}, {"n": 20, "minutes": 4, "times": 1},
             {"n": 11, "minutes": 3, "times": 1}]
    th9, th10 = theory.get("oge-math-2026", 9)["minutes"], theory.get("oge-math-2026", 10)["minutes"]
    fresh = theory.fit_plan("oge-math-2026", items, 15, set())
    assert sum(i["minutes"] for i in fresh) <= 15
    assert fresh[0]["theory"] == th9 and fresh[0]["minutes"] == 6 + th9
    assert all(i["theory"] == 0 for i in fresh if i["n"] == 20)           # №20 без теории — без надбавки
    seen = theory.fit_plan("oge-math-2026", items, 15, {"9", "10", "11"})
    assert all(i["theory"] == 0 for i in seen)
    assert [i["n"] for i in seen] == [9, 10, 20] and sum(i["minutes"] for i in seen) == 13   # №11 уже не влез
    tight = theory.fit_plan("oge-math-2026", items, 3 + th9, set())       # «× 2» теряет повтор, но номер остаётся
    assert tight[0]["n"] == 9 and tight[0]["times"] == 1 and tight[0]["minutes"] == 3 + th9
    assert theory.fit_plan("oge-math-2026", items, 2, set()) == []
    assert th10 >= 2


def test_today_plan_fits_15_minutes_with_theory(client, monkeypatch):  # noqa: F811
    import re
    monkeypatch.setattr(config, "UMEDU2", True)
    csrf = _enroll(client, "oge-math-2026")
    client.post("/u2/me/minutes", data={"csrf": csrf, "minutes": 90})
    page = client.get("/u2/today").text
    total = int(re.search(r"Сегодня · (\d+) минут", page).group(1))
    assert 0 < total <= 15
    assert "сначала теория" in page                                       # непрочитанная теория в бюджете дня
    first = re.search(r'href="/u2/train/oge-math-2026/(\d+)"', page).group(1)
    for n in range(1, 26):                                                 # прочитал всю теорию — надбавки нет
        if theory.has("oge-math-2026", n):
            client.get(f"/u2/learn/oge-math-2026/{n}")
    page = client.get("/u2/today").text
    assert "сначала теория" not in page and first
    assert 0 < int(re.search(r"Сегодня · (\d+) минут", page).group(1)) <= 15


def test_subject_page_marks_theory(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "UMEDU2", True)
    _enroll(client, "oge-math-2026")
    total = len(theory.keys_for("oge-math-2026"))
    page = client.get("/u2/subject/oge-math-2026").text
    assert f"<b>0 из {total}</b>" in page and page.count("th-cell-new") == total and "th-cell-seen" not in page
    client.get("/u2/learn/oge-math-2026/9")
    page = client.get("/u2/subject/oge-math-2026").text
    assert f"<b>1 из {total}</b>" in page and page.count("th-cell-seen") == 1 and "теория разобрана" in page
    assert page.count("th-cell-new") == total - 1
