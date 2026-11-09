"""Лаборатория опытов umedu 2.0: описание в JSON, модель на сервере.

Цикл опыта (вопрос → предсказание → измерение → сравнение → закон → перенос) рисует браузер.
Проверяет ответы только сервер: те же формулы, что в JSON. Шум прибора и цена деления — чтобы
ученик снимал показание, а не подставлял идеальное число; допуск проверки покрывает этот шум.

Химию сюда не кладём: «Собери атом» и видео ХимЛаба остаются в app/chem*.py.
"""
import json
import math
import re
from pathlib import Path

OFFER_DAYS = 3                    # «Сегодня» предлагает опыт не чаще раза в 3 дня
ORDER = ("ohm", "series", "parallel", "hooke", "density", "heat")
LABS_DIR = Path(__file__).resolve().parent / "content" / "labs"

_NUM = re.compile(r"-?\d+(?:[.,]\d+)?")


class EvalError(ValueError):
    pass


def _labs():
    found = {}
    for path in LABS_DIR.glob("*.json"):
        lab = json.loads(path.read_text(encoding="utf-8"))
        if lab.get("id") != path.stem:
            raise ValueError("id опыта не совпадает с именем файла: %s" % path.name)
        found[lab["id"]] = lab
    missing = [i for i in ORDER if i not in found]
    if missing:
        raise ValueError("нет JSON опытов: %s" % ", ".join(missing))
    return found


LABS = _labs()


def all_labs():
    return [LABS[i] for i in ORDER]


def get(lab_id):
    lab = LABS.get(lab_id)
    if not lab:
        raise KeyError(lab_id)
    return lab


def canon(x):
    """Одинаковая запись числа в ключе шума — и в Python, и в JS."""
    n = round(float(x), 6)
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    return ("%.6f" % n).rstrip("0").rstrip(".")


def fnv(text):
    """FNV-1a, 32 бита. Та же схема в app/static/js/labs/engine.js."""
    h = 2166136261
    for b in text.encode():
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def quantize(value, division):
    """К ближайшему делению. Для положительных чисел совпадает с Math.round в JS."""
    if not division:
        return float(value)
    steps = float(value) / float(division)
    rounded = math.floor(steps + 0.5) if steps >= 0 else math.ceil(steps - 0.5)
    return rounded * float(division)


def eval_expr(src, names):
    """Четыре действия, скобки, имена из names. Без вызовов и степени — формулы опытов простые."""
    s = src.replace(" ", "")
    i = 0

    def peek():
        return s[i] if i < len(s) else ""

    def parse_expr():
        nonlocal i
        v = parse_term()
        while i < len(s) and s[i] in "+-":
            op = s[i]
            i += 1
            r = parse_term()
            v = v + r if op == "+" else v - r
        return v

    def parse_term():
        nonlocal i
        v = parse_factor()
        while i < len(s) and s[i] in "*/":
            op = s[i]
            i += 1
            r = parse_factor()
            if op == "/" and r == 0:
                raise EvalError("деление на ноль")
            v = v * r if op == "*" else v / r
        return v

    def parse_factor():
        nonlocal i
        if peek() == "+":
            i += 1
            return parse_factor()
        if peek() == "-":
            i += 1
            return -parse_factor()
        if peek() == "(":
            i += 1
            v = parse_expr()
            if peek() != ")":
                raise EvalError("нет скобки")
            i += 1
            return v
        if peek().isdigit() or peek() == ".":
            j = i
            while i < len(s) and (s[i].isdigit() or s[i] == "."):
                i += 1
            return float(s[j:i])
        if peek().isalpha() or peek() == "_":
            j = i
            while i < len(s) and (s[i].isalnum() or s[i] == "_"):
                i += 1
            name = s[j:i]
            if name not in names:
                raise EvalError("неизвестно: %s" % name)
            return float(names[name])
        raise EvalError("синтаксис: %s" % src)

    value = parse_expr()
    if i != len(s):
        raise EvalError("лишнее в формуле: %s" % src)
    return value


def clamp_controls(lab, raw):
    """Ползунок не выходит за диапазон, переключатель — только 0 или 1, выбор — из списка."""
    out = {}
    raw = raw or {}
    for c in lab["controls"]:
        try:
            val = float(raw.get(c["id"], c["value"]))
        except (TypeError, ValueError):
            val = float(c["value"])
        kind = c.get("type") or "range"
        if kind == "choice":
            allowed = [float(o["value"]) for o in c["options"]]
            if not any(abs(val - a) < 1e-9 for a in allowed):
                val = float(c["value"])
        elif kind == "switch":
            val = 1.0 if val >= 0.5 else 0.0
        else:
            lo, hi = float(c["min"]), float(c["max"])
            step = float(c.get("step") or 0)
            val = min(max(val, lo), hi)
            if step:
                val = round(round((val - lo) / step) * step + lo, 6)
                val = min(max(val, lo), hi)
        out[c["id"]] = float(val)
    return out


def outputs(lab, controls):
    """Идеальные величины модели. Порядок ключей в JSON — порядок вычисления."""
    names = {k: float(v) for k, v in (lab.get("constants") or {}).items()}
    names.update(controls)
    out = {}
    for key, expr in lab["outputs"].items():
        out[key] = eval_expr(expr, names)
        names[key] = out[key]
    return out


def meter_reading(lab, meter_id, controls, seed=1):
    """Показание прибора: модель + устойчивый шум + округление до цены деления."""
    meter = next(m for m in lab["meters"] if m["id"] == meter_id)
    true = outputs(lab, controls)[meter_id]
    key = "%s|%s|" % (seed, meter_id) + "|".join(
        "%s=%s" % (k, canon(controls[k])) for k in sorted(controls))
    unit = fnv(key) / 4294967295
    wobble = (unit * 2 - 1) * float(meter.get("noise") or 0)
    return quantize(true + wobble, float(meter.get("division") or 0))


def band(meter):
    """Насколько показание может отличаться от идеального: шум и полделения."""
    return float(meter.get("noise") or 0) + float(meter.get("division") or 0) / 2


def parse_num(text):
    if text is None:
        return None
    raw = str(text).replace(" ", "").replace("\u2212", "-").replace("\u2013", "-")
    m = _NUM.search(raw)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def fmt_ru(x, digits=2):
    if x is None or x != x:  # NaN
        return "—"
    s = ("%.*f" % (digits, x)).rstrip("0").rstrip(".")
    if s in ("", "-0"):
        s = "0"
    return s.replace(".", ",")


def check_predict(lab, option_id):
    pred = lab["predict"]
    ok = option_id == pred["answer"]
    return {"ok": ok, "why": pred["why"]}


def check_reading(lab, text):
    grade = lab["grade"]
    controls = clamp_controls(lab, grade.get("controls") or {})
    ideal = outputs(lab, controls)[grade["meter"]]
    meter = next(m for m in lab["meters"] if m["id"] == grade["meter"])
    tol = max(float(grade.get("tol") or 0), band(meter))
    got = parse_num(text)
    if got is None:
        return {"ok": False, "explain": "Нужно число. Дробную часть пиши через запятую."}
    ok = abs(got - ideal) <= tol + 1e-9
    return {"ok": ok, "explain": grade["explain"]}


def visible_transfer(lab, enrolled):
    """2–3 задания тех экзаменов, которые ученик уже выбрал. Чужой экзамен не подсовываем."""
    return [t for t in lab["transfer"] if t["exam"] in enrolled][:3]


def transfer_public(lab, enrolled):
    out = []
    for t in visible_transfer(lab, enrolled):
        name = "ОГЭ" if str(t["exam"]).startswith("oge") else "ЕГЭ"
        out.append({"label": "%s №%s" % (name, t["task"]), "text": t["text"]})
    return out


def grade_transfer(items, answers):
    graded = []
    for i, t in enumerate(items):
        given = (answers[i] if i < len(answers) else "") or ""
        given = str(given).strip()[:100]
        got = parse_num(given)
        ideal = float(t["answer"])
        tol = float(t.get("tol") or 0)
        ok = got is not None and abs(got - ideal) <= tol + 1e-9
        graded.append({"ok": ok, "given": given, "explain": t["explain"], "exam": t["exam"], "task": t["task"],
                       "text": t["text"]})
    return graded


def exams_label(lab):
    bits = []
    for link in lab["exams"]:
        name = "ОГЭ" if link["id"].startswith("oge") else "ЕГЭ"
        bits.append(name + " " + ", ".join(str(n) for n in link["tasks"]))
    return " · ".join(bits)


def client_config(lab, seed):
    """То, что нужно сцене. Верные ответы предсказания и переноса сюда не входят."""
    meters = []
    for m in lab["meters"]:
        meters.append({k: m[k] for k in ("id", "label", "unit", "division", "noise", "max") if k in m})
    return {
        "id": lab["id"],
        "scene": lab["scene"],
        "layout": lab.get("layout") or lab["id"],
        "seed": int(seed),
        "constants": lab.get("constants") or {},
        "controls": lab["controls"],
        "meters": meters,
        "outputs": lab["outputs"],
        "graph": lab["graph"],
        "min_points": int(lab.get("min_points") or 4),
        "min_distinct": int(lab.get("min_distinct") or 3),
    }


def client_json(lab, seed):
    return json.dumps(client_config(lab, seed), ensure_ascii=False).replace("<", "\\u003c")


def _linked(lab, sagging):
    """Самый слабый проседающий номер, к которому привязан опыт. (p, номер, экзамен) или None."""
    found = None
    for link in lab["exams"]:
        for n, p in sagging.get(link["id"], ()):
            if n not in link["tasks"]:
                continue
            cand = (p, n, link["id"])
            if found is None or cand < found:
                found = cand
    return found


def pick_offer(sagging, offered, today):
    """Один опыт к самому слабому номеру. В день показа карточка остаётся той же.
    Следующие OFFER_DAYS − 1 дней нового предложения нет, даже если проседает другой номер."""
    today_ids = [lab_id for lab_id, day in offered.items() if day == today]
    recent = any(day != today and (today - day).days < OFFER_DAYS for day in offered.values())
    if recent and not today_ids:
        return None
    if today_ids:
        lab = LABS.get(today_ids[0])
        if not lab:
            return None
        hit = _linked(lab, sagging)
        if not hit:
            return None
        p, n, exam_id = hit
        return _offer_card(lab, n, exam_id, p)
    best = None
    for lab in all_labs():
        hit = _linked(lab, sagging)
        if not hit:
            continue
        p, n, exam_id = hit
        cand = (p, ORDER.index(lab["id"]), n, exam_id, lab["id"])
        if best is None or cand < best:
            best = cand
    if not best:
        return None
    p, _rank, n, exam_id, lab_id = best
    return _offer_card(LABS[lab_id], n, exam_id, p)


def _offer_card(lab, n, exam_id, p):
    return {"id": lab["id"], "title": lab["title"], "question": lab["question"], "task": n,
            "exam_id": exam_id, "p": p}
