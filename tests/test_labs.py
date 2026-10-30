"""Лаборатория опытов: модель, проверка ответов, доступ, бюджет JS, снимок меню КодКвеста и ХимЛаба."""
import json
import re
import subprocess
from datetime import date
from pathlib import Path

import pytest

from app import config, labs
from test_app import client, login, login_as, sid_of  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js" / "labs"

# Меню, которое было до лаборатории. Новые ссылки сюда попасть не должны.
CODEQUEST_NAV = (
    ("/", "Главная"),
    ("/today", "План на сегодня"),
    ("/map", "Карта курса"),
    ("/homework", "Домашка"),
    ("/daily", "Задача дня"),
    ("/oge", "ОГЭ"),
    ("/trainer", "Арена"),
    ("/bots", "Битва ботов"),
    ("/playground", "Песочница"),
    ("/cheatsheet", "Шпаргалка"),
    ("/achievements", "Бойцы и награды"),
    ("/season", "Пасс сезона"),
    ("/shop", "Магазин подарков"),
    ("/certificates", "Сертификаты"),
    ("/checks", "Проверки"),
    ("/portfolio", "Портфолио"),
    ("/account", "Аккаунт и данные"),
)
CHEM_NAV = (
    ("/chem", "Главная"),
    ("/chem/map", "Карта экзамена"),
    ("/chem/hw", "Домашние задания"),
    ("/chem/mock", "Пробник"),
    ("/checks", "Тесты"),
    ("/chem/lab", "Лаборатория"),
    ("/chem/table", "Таблица Менделеева"),
    ("/chem/me", "Мой профиль"),
)


def _on(monkeypatch):
    monkeypatch.setattr(config, "UMEDU2", True)


def _scripts(html):
    return re.findall(r"<script\b([^>]*)>", html, flags=re.I)


def test_ohm_series_parallel_against_analytics():
    ohm = labs.outputs(labs.get("ohm"), {"U": 6, "R": 10, "sw": 1})
    assert ohm["I"] == pytest.approx(6 / 10) and ohm["V"] == pytest.approx(6)
    opened = labs.outputs(labs.get("ohm"), {"U": 6, "R": 10, "sw": 0})
    assert opened["I"] == 0 and opened["V"] == 0
    series = labs.outputs(labs.get("series"), {"U": 12, "R1": 4, "R2": 8, "sw": 1})
    assert series["I"] == pytest.approx(12 / (4 + 8))
    assert series["U1"] == pytest.approx(4) and series["U2"] == pytest.approx(8)
    assert series["U1"] + series["U2"] == pytest.approx(12)
    parallel = labs.outputs(labs.get("parallel"), {"U": 12, "R1": 6, "R2": 12, "sw": 1})
    assert parallel["I1"] == pytest.approx(2) and parallel["I2"] == pytest.approx(1)
    req = 1 / (1 / 6 + 1 / 12)
    assert parallel["I"] == pytest.approx(12 / req) and parallel["I"] == pytest.approx(3)


def test_hooke_density_heat_analytics():
    hooke = labs.outputs(labs.get("hooke"), {"m": 200, "k": 50})
    assert hooke["F"] == pytest.approx(2) and hooke["x"] == pytest.approx(4)
    density = labs.outputs(labs.get("density"), {"rho": 2700, "V": 100})
    assert density["m"] == pytest.approx(270)
    heat = labs.outputs(labs.get("heat"), {"m": 0.2, "P": 210, "tau": 40})
    assert heat["Q"] == pytest.approx(8400) and heat["T"] == pytest.approx(30)


def test_meter_noise_stays_inside_division():
    for lab in labs.all_labs():
        controls = labs.clamp_controls(lab, {c["id"]: c["value"] for c in lab["controls"]})
        ideal = labs.outputs(lab, controls)
        for meter in lab["meters"]:
            limit = labs.band(meter) + 1e-6
            division = float(meter.get("division") or 0)
            for seed in range(1, 25):
                got = labs.meter_reading(lab, meter["id"], controls, seed)
                assert abs(got - ideal[meter["id"]]) <= limit, (lab["id"], meter["id"], seed, got)
                if division:
                    assert abs(got / division - round(got / division)) < 1e-6


@pytest.mark.parametrize("lab_id,answer", [
    ("ohm", "0,6"), ("series", "8"), ("parallel", "3"), ("hooke", "4"), ("density", "270"), ("heat", "30"),
])
def test_reading_check_accepts_instrument_and_rejects_nonsense(lab_id, answer):
    lab = labs.get(lab_id)
    assert labs.check_reading(lab, answer)["ok"]
    assert labs.check_reading(lab, answer.replace(",", "."))["ok"]
    bad = labs.check_reading(lab, "99999")
    assert not bad["ok"] and bad["explain"]
    assert not labs.check_reading(lab, "не знаю")["ok"]


def test_transfer_numbers_exist_and_are_not_fipi_copies():
    from app import exam_model as em
    for lab in labs.all_labs():
        assert labs.check_predict(lab, lab["predict"]["answer"])["ok"]
        assert not labs.check_predict(lab, "no-such")["ok"]
        for t in lab["transfer"]:
            exam = em.load(t["exam"])
            assert t["task"] in em.points(exam), (lab["id"], t)
            assert labs.parse_num(str(t["answer"])) == pytest.approx(t["answer"])
            assert "fipi" not in t["text"].lower()
        public = json.loads(labs.client_json(lab, 7))
        assert "answer" not in json.dumps(public, ensure_ascii=False)
        assert "why" not in public
        assert "explain" not in json.dumps(public)


def test_js_model_matches_python():
    cases = []
    samples = {
        "ohm": {"U": 6, "R": 10, "sw": 1},
        "series": {"U": 12, "R1": 4, "R2": 8, "sw": 1},
        "parallel": {"U": 12, "R1": 6, "R2": 12, "sw": 1},
        "hooke": {"m": 200, "k": 50},
        "density": {"rho": 2700, "V": 100},
        "heat": {"m": 0.2, "P": 210, "tau": 40},
    }
    for lab_id, controls in samples.items():
        lab = labs.get(lab_id)
        controls = labs.clamp_controls(lab, controls)
        expect = labs.outputs(lab, controls)
        cases.append({
            "id": lab_id, "outputs": lab["outputs"], "constants": lab.get("constants") or {},
            "controls": controls, "meters": lab["meters"], "seed": 3, "expect": expect,
            "reading": {m["id"]: labs.meter_reading(lab, m["id"], controls, 3) for m in lab["meters"]},
        })
    blob = ROOT / "tests" / "_lab_cases.json"
    blob.write_text(json.dumps(cases), encoding="utf-8")
    script = r"""
const fs = require("fs");
const vm = require("vm");
const sandbox = { console };
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("app/static/js/labs/engine.js", "utf8"), sandbox);
const E = sandbox.LabEngine || (sandbox.globalThis && sandbox.globalThis.LabEngine);
if (!E) { console.error("LabEngine не поднялся"); process.exit(1); }
const cases = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
for (const c of cases) {
  const out = E.evalOutputs(c.outputs, c.constants, c.controls);
  for (const k of Object.keys(c.expect)) {
    if (Math.abs(out[k] - c.expect[k]) > 1e-6) {
      console.error("формула", c.id, k, out[k], c.expect[k]); process.exit(1);
    }
  }
  for (const m of c.meters) {
    const got = E.meterReading(out[m.id], m, c.seed, c.controls);
    if (Math.abs(got - c.reading[m.id]) > 1e-6) {
      console.error("прибор", c.id, m.id, got, c.reading[m.id]); process.exit(1);
    }
  }
}
"""
    run = subprocess.run(["node", "-e", script, str(blob)], cwd=ROOT, capture_output=True, text=True)
    blob.unlink(missing_ok=True)
    assert run.returncode == 0, run.stderr or run.stdout


def test_scene_js_budget_and_no_eval():
    engine = (JS / "engine.js").read_text(encoding="utf-8")
    assert "eval(" not in engine and "new Function" not in engine
    subprocess.run(["node", "--check", str(JS / "engine.js")], check=True)
    for path in sorted(JS.glob("*.js")):
        subprocess.run(["node", "--check", str(path)], check=True)
        if path.name == "engine.js":
            continue
        assert path.stat().st_size <= 40 * 1024, path.name
        assert "http://" not in path.read_text(encoding="utf-8")
        assert "https://" not in path.read_text(encoding="utf-8")


def test_catalog_marks_first_six():
    text = (ROOT / "docs" / "labs" / "CATALOG.md").read_text(encoding="utf-8")
    head, tail = text.split("## Дальше", 1)
    first = re.findall(r"`([a-z0-9-]+)`", head)
    rest = re.findall(r"^### \d+\. .+", tail, flags=re.M)
    assert first[:6] == ["ohm", "series", "parallel", "hooke", "density", "heat"]
    assert len(rest) == 9
    for chunk in re.split(r"\n### ", text)[1:]:
        if chunk.startswith("Химия") or "перенести позже" in chunk[:80]:
            continue
        for label in ("Вопрос", "Крутит", "Измеряет", "Закон", "Ловушка", "Экзамен", "Сложность"):
            assert label in chunk, (label, chunk[:40])
    assert "Собери атом" in text and "app/chem" in text


def test_offer_is_one_lab_every_three_days():
    sag = {"oge-phys-2026": [(9, 0.2), (6, 0.5)]}
    day = date(2026, 10, 1)
    first = labs.pick_offer(sag, {}, day)
    assert first["id"] == "ohm" and first["task"] == 9
    assert labs.pick_offer(sag, {"ohm": day}, day)["id"] == "ohm"
    assert labs.pick_offer(sag, {"ohm": day}, date(2026, 10, 2)) is None
    assert labs.pick_offer(sag, {"ohm": day}, date(2026, 10, 3)) is None
    assert labs.pick_offer(sag, {"ohm": day}, date(2026, 10, 4))["id"] == "ohm"
    only6 = {"oge-phys-2026": [(6, 0.2)]}
    assert labs.pick_offer(only6, {}, day)["id"] == "hooke"


def test_hidden_without_flag_and_needs_login(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "UMEDU2", False)
    login(client, "student")
    assert client.get("/u2/lab").status_code == 404
    assert client.get("/u2/lab/ohm").status_code == 404
    _on(monkeypatch)
    client.cookies.clear()
    assert client.get("/u2/lab/ohm", follow_redirects=False).status_code == 303


def test_page_has_no_inline_script_and_hides_answers(client, monkeypatch):  # noqa: F811
    _on(monkeypatch)
    login(client, "student")
    res = client.get("/u2/lab/ohm")
    assert res.status_code == 200
    assert "script-src 'self'" in res.headers["content-security-policy"]
    html = res.text
    assert "закон Ома" in html and "Как сила тока" in html
    assert "4,5 / 15" not in html and "I = U / R = 6 / 10" not in html
    for attrs in _scripts(html):
        assert "src=" in attrs or "application/json" in attrs, attrs
    assert "onclick=" not in html and "javascript:" not in html
    assert 'src="/static/js/labs/engine.js' in html and 'src="/static/js/labs/circuit.js' in html
    listed = client.get("/u2/lab").text
    assert listed.count('href="/u2/lab/') == 6
    assert "4,5 / 15" not in listed


def test_check_csrf_predict_and_reading(client, monkeypatch):  # noqa: F811
    _on(monkeypatch)
    csrf = login(client, "student")
    assert client.post("/u2/lab/ohm/check", data={"kind": "predict", "predict": "twice"}).status_code == 403
    bad = client.post("/u2/lab/ohm/check", data={"csrf": csrf, "kind": "predict", "predict": "same"})
    body = bad.json()
    assert bad.status_code == 200 and body["ok"] is False and "Сопротивление то же" in body["why"]
    good = client.post("/u2/lab/ohm/check", data={"csrf": csrf, "kind": "predict", "predict": "twice"})
    assert good.json()["ok"] is True
    reading = client.post("/u2/lab/ohm/check", data={"csrf": csrf, "kind": "reading", "value": "0,58"},
                          headers={"X-CSRF-Token": csrf})
    assert reading.json()["ok"] is True
    assert client.post("/u2/lab/ohm/check", data={"csrf": csrf, "kind": "reading", "value": "9"}).json()["ok"] is False
    assert client.post("/u2/lab/nope/check", data={"csrf": csrf, "kind": "predict", "predict": "twice"}).status_code == 404
    teacher = login(client, "teacher")
    assert client.get("/u2/lab/ohm").status_code == 200
    assert client.post("/u2/lab/ohm/check", data={"csrf": teacher, "kind": "predict", "predict": "twice"}).status_code == 403


def test_transfer_records_skill_attempt(client, monkeypatch):  # noqa: F811
    from app.db import connect
    _on(monkeypatch)
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-phys-2026", "goal": 4})
    page = client.get("/u2/lab/ohm").text
    assert "ОГЭ №9" in page and "ОГЭ №15" in page and "ЕГЭ №11" not in page
    res = client.post("/u2/lab/ohm/transfer", data={"csrf": csrf, "a0": "0,3", "a1": "7"})
    assert res.status_code == 200
    assert res.text.count("Верно") == 1 and "Неверно" in res.text and "20 Ом" in res.text
    rows = connect().execute(
        "SELECT task_key, score, given FROM skill_attempt WHERE student_id = ? AND exam_id = ? ORDER BY id",
        (sid_of(), "oge-phys-2026")).fetchall()
    assert [(r["task_key"], r["score"], r["given"]) for r in rows] == [("9", 1.0, "0,3"), ("15", 0.0, "7")]
    assert client.post("/u2/lab/ohm/transfer", data={"a0": "0,3", "a1": "20"}).status_code == 403
    assert client.post("/u2/lab/density/transfer", data={"csrf": csrf, "a0": "1"}).status_code == 200


def test_today_suggests_sagging_lab_then_waits(client, monkeypatch):  # noqa: F811
    from app import knowledge as kn
    from app.db import connect
    _on(monkeypatch)
    day = {"d": date(2026, 10, 1)}
    monkeypatch.setattr(config, "today", lambda: day["d"])
    csrf = login(client, "student")
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-phys-2026", "goal": 4})
    with connect() as conn:
        kn.record(conn, sid_of(), "oge-phys-2026", 9, 0.0, day["d"])
    page = client.get("/u2/today").text
    assert 'data-lab-offer="ohm"' in page and "/u2/lab/ohm" in page
    day["d"] = date(2026, 10, 2)
    rested = client.get("/u2/today").text
    assert "data-lab-offer" not in rested and 'href="/u2/lab"' in rested
    day["d"] = date(2026, 10, 4)
    assert 'data-lab-offer="ohm"' in client.get("/u2/today").text


def test_codequest_home_nav_snapshot(client):  # noqa: F811
    login(client, "student")
    html = client.get("/").text
    for href, label in CODEQUEST_NAV:
        assert f'href="{href}"' in html, href
        assert label in html
    assert 'href="/u2' not in html and 'href="/chem' not in html
    assert "Лаборатория опытов" not in html


def test_chemlab_home_nav_snapshot(client, monkeypatch):  # noqa: F811
    from app.db import connect
    monkeypatch.setattr(config, "CHEM_SITE", True)
    monkeypatch.setattr(config, "SUBJECTS", ["chemistry"])
    monkeypatch.setattr(config, "GAME", "light")
    monkeypatch.setattr(config, "SIGNUP", True)
    monkeypatch.setattr(config, "BRAND_EMOJI", "🧪")
    login_as(client, "teacher")
    code = connect().execute("SELECT value FROM settings WHERE key = 'invite_code'").fetchone()
    if not code:
        client.get("/chem/teacher")
        code = connect().execute("SELECT value FROM settings WHERE key = 'invite_code'").fetchone()
    else:
        client.get("/chem/teacher")
    client.cookies.clear()
    joined = client.post("/join", data={"code": code[0], "name": "Лена", "grade": 9, "login": "lena9",
                                        "password": "lisa-gora-42"}, follow_redirects=False)
    assert joined.status_code == 303
    home = client.get("/chem").text
    for href, label in CHEM_NAV:
        assert f'href="{href}"' in home, href
        assert label in home
    assert 'href="/u2' not in home and 'href="/map"' not in home and 'href="/today"' not in home
    lab = client.get("/chem/lab").text
    assert "Атом изнутри" in lab and "Собери атом" in lab and "Эффектные опыты" in lab
