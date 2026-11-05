"""umedu 2.0: подготовка к ОГЭ/ЕГЭ с прогнозом балла. Четыре вкладки, выбор экзамена и тренажёр по номерам.

Раздел /u2 включается флагом CQ_UMEDU2=1; без него все адреса раздела отвечают 404, действующий сайт не меняется.
Данные — app/knowledge.py (знания по номерам, прогноз, план) поверх app/exam_model.py (номера и шкалы).
"""
import json
import random
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import account, auth, config, oge_drill, russian
from . import exam_model as em
from . import knowledge as kn
from .content import inf_gen, math_gen, oge_gen, oge_u2, oge16_gen, phys_gen
from .content import robot as robot_content
from .content.oge import OGE_NUMBERS
from .content.ru import RULES as RU_RULES
from . import u2_onsite
from .db import get_db
from . import students
from .main import back, need_sid, only_student, render


def _enabled():
    if not config.UMEDU2:
        raise HTTPException(404)


router = APIRouter(prefix="/u2", dependencies=[Depends(_enabled)])

DAILY_MINUTES = 30            # по умолчанию; ученик меняет во вкладке «Я»
MINUTE_CHOICES = (15, 30, 45, 60, 90)
REVIEW_AFTER_DAYS = 14        # номер, к которому не возвращались столько дней, попадает в план как повторение
REVIEW_MIN_P = 0.6
FIPI_BANK = {"ОГЭ": "https://fipi.ru/oge/otkrytyy-bank-zadaniy-oge", "ЕГЭ": "https://fipi.ru/ege/otkrytyy-bank-zadaniy-ege"}
# номера, для которых сайт сам выдаёт варианты и проверяет ответ; остальные — самопроверка по банку ФИПИ
BANKS = {"oge-math-2026": math_gen.OGE, "ege-math-profile-2026": math_gen.EGE_PROFILE, "ege-inf-2026": inf_gen.EGE,
         "ege-math-base-2026": math_gen.EGE_BASE, "oge-phys-2026": phys_gen.OGE, "ege-phys-2026": phys_gen.EGE}
GENERATED = dict(u2_onsite.SHORT)
TITLES = {"oge-inf-2026": {n: t[0] for n, t in OGE_NUMBERS.items()}, **{e: b.TITLES for e, b in BANKS.items()}}
TABS = [("today", "Сегодня"), ("subjects", "Предметы"), ("progress", "Прогресс"), ("me", "Я")]


def _kind(exam):
    return "grade" if exam["scale"]["kind"] == "grade" else "test"


def _goal_range(exam):
    return (3, 5) if _kind(exam) == "grade" else (0, 100)


def _card(enr, states, today):
    """Всё, что вкладкам нужно знать об одном экзамене ученика."""
    exam = em.load(enr["exam_id"])
    fc = kn.forecast(exam, states, today)
    key = _kind(exam)
    lo, hi = _goal_range(exam)
    gap = (enr["goal"] - fc[key]) / (hi - lo) if enr["goal"] is not None else 0
    days = (date.fromisoformat(enr["exam_date"]) - today).days if enr["exam_date"] else None
    groups = []
    for g in exam.get("groups") or [{"name": p["name"], "tasks": [t["n"] for t in p["tasks"]]} for p in exam["parts"]]:
        ps = [kn.decay(states.get(n), today)["p"] for n in g["tasks"]]
        groups.append({"name": g["name"], "p": sum(ps) / len(ps), "tasks": g["tasks"]})
    return {"id": exam["id"], "title": f'{exam["exam"]} · {exam["subject"]}', "exam": exam, "kind": key,
            "goal": enr["goal"], "exam_date": enr["exam_date"], "days": days, "fc": fc, "gap": gap, "groups": groups,
            "attempts": sum(s["n"] for s in states.values()), "states": states, "mock": bool(GENERATED.get(exam["id"]))}


def _cards(conn, sid, today):
    return [_card(e, kn.load_states(conn, sid, e["exam_id"]), today) for e in kn.exams_of(conn, sid)]


def _due(exam, states, today, minutes):
    """Повторения: освоенные номера (p ≥ REVIEW_MIN_P), к которым давно не возвращались, — самые давние первыми.
    Занимают не больше половины времени, иначе на новое не остаётся."""
    old = sorted(((date.fromisoformat(s["last"]), k) for k, s in states.items()
                  if isinstance(k, int) and s.get("last") and s["p"] >= REVIEW_MIN_P
                  and (today - date.fromisoformat(s["last"])).days >= REVIEW_AFTER_DAYS))
    by_n = {t["n"]: t for t in em.tasks(exam)}
    out, left = [], minutes // 2
    for _, k in old:
        m = kn.task_minutes(by_n[k])
        if m <= left:
            out.append(k)
            left -= m
    return out


def _split(cards, total):
    """Минуты по экзаменам: пропорционально разрыву с целью, но каждому, где цель не достигнута, — хотя бы 5 минут,
    иначе экзамен с маленьким разрывом выпадает из плана совсем."""
    out = kn.split_minutes({c["id"]: c["gap"] for c in cards}, total)
    for c in cards:
        if c["gap"] > 0 and not out.get(c["id"]):
            richest = max(out, key=out.get)
            if out[richest] > 5:
                out[richest] -= 5
                out[c["id"]] = 5
    return out


def _minutes(conn, sid):
    row = conn.execute("SELECT daily_minutes FROM u2_prefs WHERE student_id = ?", (sid,)).fetchone()
    return row[0] if row else DAILY_MINUTES


def _page(request, conn, user, tab, name, **ctx):
    return render(request, name, conn, user, tab=tab, tabs=TABS, **ctx)


@router.get("")
def u2_home():
    return back("/u2/today")


@router.get("/today", response_class=HTMLResponse)
def u2_today(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid, today = need_sid(conn, user), config.today()
    cards = _cards(conn, sid, today)
    if not cards:
        return back("/u2/start")
    minutes = _split(cards, _minutes(conn, sid))
    plans = []
    for c in cards:
        if minutes.get(c["id"]):
            due = _due(c["exam"], c["states"], today, minutes[c["id"]])
            items = _plan(c["exam"], c["states"], minutes[c["id"]], today, due)
            for it in items:
                it["title"] = _task_info(c["exam"], it["n"])["title"]
            plans.append({"card": c, "minutes": sum(i["minutes"] for i in items), "steps": items})
    return _page(request, conn, user, "today", "u2/today.html", cards=cards, plans=plans,
                 total=sum(p["minutes"] for p in plans), act=kn.activity(conn, sid, today), intro=_intro(cards, plans))


def _intro(cards, plans):
    """Первые шаги: экзамен выбран → самооценка по разделам → первое задание. Отметки — по данным, без флагов;
    когда сделано всё, карточки нет."""
    if any(c["attempts"] for c in cards):
        return None
    first = cards[0]
    step = next((s for p in plans for s in p["steps"]), None)
    return [{"done": True, "text": "Выбрать экзамен и цель", "href": "/u2/me"},
            {"done": bool(first["states"]), "text": "Оценить себя по разделам — 1 минута, прогноз станет точнее",
             "href": f"/u2/diag/{first['id']}"},
            {"done": False, "text": "Решить первое задание из плана" + (f": №{step['n']}" if step else ""),
             "href": f"/u2/train/{plans[0]['card']['id']}/{step['n']}" if step else f"/u2/subject/{first['id']}"}]


@router.get("/subjects", response_class=HTMLResponse)
def u2_subjects(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    return _page(request, conn, user, "subjects", "u2/subjects.html", cards=_cards(conn, sid, config.today()))


@router.get("/subject/{exam_id}", response_class=HTMLResponse)
def u2_subject(exam_id: str, request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid, today = need_sid(conn, user), config.today()
    enr = next((e for e in kn.exams_of(conn, sid) if e["exam_id"] == exam_id), None)
    if not enr:
        raise HTTPException(404)
    c = _card(enr, kn.load_states(conn, sid, exam_id), today)
    tasks = [{**t, "p": kn.decay(c["states"].get(t["n"]), today)["p"], "n_try": c["states"].get(t["n"], {}).get("n", 0)}
             for t in em.tasks(c["exam"])]
    path = None
    if c["goal"] is not None and c["gap"] > 0:
        path = kn.path_to_goal(c["exam"], c["states"], c["goal"], today)
        for s in path["steps"]:
            s.update(_task_info(c["exam"], s["n"]))
    return _page(request, conn, user, "subjects", "u2/subject.html", c=c, tasks=tasks, proj=_projection(conn, sid, c, today),
                 path=path)


PACE_DAYS = 14


def _projection(conn, sid, c, today):
    """Прогноз к дате экзамена: в нынешнем темпе (минуты за последние PACE_DAYS дней) и по выбранному плану."""
    if not c["exam_date"] or c["days"] is None or c["days"] <= 0:
        return None
    by_n = {t["n"]: t for t in em.tasks(c["exam"])}
    since = (today - timedelta(days=PACE_DAYS)).isoformat()
    done = conn.execute("SELECT task_key FROM skill_attempt WHERE student_id = ? AND exam_id = ? AND day > ?",
                        (sid, c["id"], since)).fetchall()
    pace = sum(kn.task_minutes(by_n[int(k)]) if k.isdigit() and int(k) in by_n else 3 for (k,) in done) / PACE_DAYS
    planned = _split(_cards(conn, sid, today), _minutes(conn, sid)).get(c["id"]) or 0
    until = date.fromisoformat(c["exam_date"])
    k = c["kind"]
    out = {"pace": round(pace), "planned": planned, "now": kn.project(c["exam"], c["states"], today, until, pace)[k],
           "plan": kn.project(c["exam"], c["states"], today, until, planned)[k]}
    return out


@router.get("/progress", response_class=HTMLResponse)
def u2_progress(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid, today = need_sid(conn, user), config.today()
    cards = _cards(conn, sid, today)
    for c in cards:
        c["chart"] = _chart(kn.history(conn, sid, c["id"], today=today), c["exam"]["max_points"])
        c["mastery"] = _mastery(c["exam"], c["states"], kn.streaks(conn, sid, c["id"]), today)
    return _page(request, conn, user, "progress", "u2/progress.html", cards=cards)


SAG_P = 0.5                   # ниже — номер «проседает», даже если последняя попытка верная


def _mastery(exam, states, streaks, today):
    """Номера по группам: освоено (MASTERED_STREAK верных подряд и не забыто), проседает (последняя попытка
    неверная, низкое p или освоенное забывается), в работе — остальные решённые хоть раз; не начатые — числом."""
    out = {"mastered": [], "sagging": [], "working": [], "untouched": 0}
    for key in em.points(exam):
        st, sk = states.get(key), streaks.get(key)
        if not st or not st["n"] or not sk:
            out["untouched"] += 1
            continue
        p = kn.decay(st, today)["p"]
        item = {**_task_info(exam, key), "p": p, "streak": sk["streak"]}
        if sk["streak"] >= kn.MASTERED_STREAK:
            if p >= REVIEW_MIN_P:
                out["mastered"].append(item)
                continue
            item["why"] = "давно не повторял"
        elif sk["last"] < 1:
            item["why"] = "последняя попытка неверная"
        elif p < SAG_P:
            item["why"] = "пока мало верных"
        else:
            out["working"].append(item)
            continue
        out["sagging"].append(item)
    out["sagging"].sort(key=lambda i: i["p"])
    return out


def _chart(rows, max_points, w=300, h=90):
    """Координаты для SVG: вилка первичного балла (многоугольник) и середина (линия) по дням. Нужно ≥ 2 дней."""
    if len(rows) < 2:
        return None
    d0 = date.fromisoformat(rows[0]["day"])
    span = max((date.fromisoformat(rows[-1]["day"]) - d0).days, 1)
    x = [round((date.fromisoformat(r["day"]) - d0).days / span * w, 1) for r in rows]
    y = lambda v: round(h - v / max_points * h, 1)  # noqa: E731
    top = " ".join(f"{a},{y(r['high'])}" for a, r in zip(x, rows))
    bottom = " ".join(f"{a},{y(r['low'])}" for a, r in reversed(list(zip(x, rows))))
    return {"w": w, "h": h, "band": f"{top} {bottom}", "line": " ".join(f"{a},{y(r['primary_mean'])}" for a, r in zip(x, rows)),
            "first": rows[0], "last": rows[-1], "days": span}


MISTAKES_SHOWN = 20


@router.get("/mistakes", response_class=HTMLResponse)
def u2_mistakes(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    """Последние ошибки в генерируемых номерах: условие пересобираем по сиду, рядом — свой ответ, верный и разбор.
    Номер, который уже решён верно позже ошибки, помечаем «исправлено»."""
    sid = need_sid(conn, user)
    exams = {e["exam_id"] for e in kn.exams_of(conn, sid)}
    rows = conn.execute("SELECT id, exam_id, task_key, seed, given, day FROM skill_attempt WHERE student_id = ? "
                        "AND score < 1 AND seed IS NOT NULL ORDER BY id DESC LIMIT ?", (sid, MISTAKES_SHOWN * 2)).fetchall()
    items = []
    for r in rows:
        key = int(r["task_key"]) if r["task_key"].isdigit() else r["task_key"]
        if r["exam_id"] not in exams or key not in GENERATED.get(r["exam_id"], ()):
            continue
        exam = em.load(r["exam_id"])
        v = _variant(r["exam_id"], key, r["seed"])
        fixed = conn.execute("SELECT 1 FROM skill_attempt WHERE student_id = ? AND exam_id = ? AND task_key = ? AND id > ? "
                             "AND score >= 1", (sid, r["exam_id"], r["task_key"], r["id"])).fetchone()
        items.append({"exam_id": r["exam_id"], "exam": f'{exam["exam"]} · {exam["subject"]}', "t": _task_info(exam, key),
                      "variant": oge_gen.public(v), "text": oge_drill.rich(v["text"]), "given": r["given"],
                      "answer": v["answer"], "explain": v["explain"], "day": r["day"], "fixed": bool(fixed)})
        if len(items) == MISTAKES_SHOWN:
            break
    return _page(request, conn, user, "progress", "u2/mistakes.html", items=items)


@router.get("/how", response_class=HTMLResponse)
def u2_how(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    """«Как считается прогноз» простыми словами. Числа берём из knowledge, чтобы текст не разошёлся с расчётом."""
    pct = lambda x: round(x * 100)  # noqa: E731
    k = {"prior": pct(kn.PRIOR), "first": pct(kn.ALPHA_FIRST), "min": pct(kn.ALPHA_MIN), "half": kn.HALF_LIFE_DAYS,
         "review": REVIEW_AFTER_DAYS, "learn": pct(kn.LEARN_RATE), "reps": kn.MAX_REPS, "streak": kn.MASTERED_STREAK}
    example, st = [], None
    for i, score in enumerate((1, 1, 0, 1), 1):
        st = kn.update(st, score)
        example.append({"label": "%d-я попытка: %s" % (i, "верно" if score else "ошибка"), "p": pct(st["p"])})
    return _page(request, conn, user, None, "u2/how.html", k=k, example=example)


@router.get("/me", response_class=HTMLResponse)
def u2_me(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    st = students.get_student(conn, sid)
    return _page(request, conn, user, "me", "u2/me.html", cards=_cards(conn, sid, config.today()),
                 minutes=_minutes(conn, sid), choices=MINUTE_CHOICES,
                 gallery_on=account.granted(st) if st else False)


@router.post("/me/minutes")
def u2_me_minutes(minutes: int = Form(...), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    only_student(user)
    if minutes not in MINUTE_CHOICES:
        raise HTTPException(400, "Выбери время из списка")
    with conn:
        conn.execute("INSERT INTO u2_prefs (student_id, daily_minutes) VALUES (?, ?) "
                     "ON CONFLICT(student_id) DO UPDATE SET daily_minutes = excluded.daily_minutes", (user["id"], minutes))
    return back("/u2/me")


# ------------------------------------------------------------------ выбор экзамена и стартовая самооценка
# даты экзаменов ближайшего года (app/content/schedule-*.json); ключ — id экзамена без года модели: «oge-inf»
SCHEDULE = json.loads((Path(__file__).parent / "content" / "schedule-2027.json").read_text(encoding="utf-8"))
MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября",
          "декабря")


def _dates(exam_id):
    return SCHEDULE["dates"].get(exam_id.rsplit("-", 1)[0], [])


def _ru_day(d):
    d = date.fromisoformat(d)
    return f"{d.day} {MONTHS[d.month - 1]}"


def _catalog():
    out = []
    for exam_id in em.all_ids():
        ex = em.load(exam_id)
        out.append({"id": exam_id, "exam": ex["exam"], "subject": ex["subject"], "title": f'{ex["exam"]} · {ex["subject"]}',
                    "kind": _kind(ex), "range": _goal_range(ex),
                    "min": ex["scale"].get("min_university"), "dates": _dates(exam_id),
                    "days": ", ".join(_ru_day(d) for d in _dates(exam_id)),
                    "note": SCHEDULE.get("notes", {}).get(exam_id.rsplit("-", 1)[0])})
    return sorted(out, key=lambda e: (e["exam"] != "ОГЭ", e["subject"]))


@router.get("/start", response_class=HTMLResponse)
def u2_start(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    mine = {e["exam_id"]: e for e in kn.exams_of(conn, sid)}
    return _page(request, conn, user, "me", "u2/start.html", catalog=_catalog(), mine=mine, schedule=SCHEDULE)


@router.post("/start")
def u2_start_submit(exam_id: str = Form(...), goal: int = Form(...), exam_date: str = Form(""),
                    conn=Depends(get_db), user=Depends(auth.check_csrf)):
    only_student(user)
    if exam_id not in em.all_ids():
        raise HTTPException(400, "Такого экзамена нет")
    lo, hi = _goal_range(em.load(exam_id))
    if not lo <= goal <= hi:
        raise HTTPException(400, f"Цель — от {lo} до {hi}")
    if exam_date:
        try:
            date.fromisoformat(exam_date)
        except ValueError:
            raise HTTPException(400, "Дата экзамена в формате ГГГГ-ММ-ДД")
    with conn:
        kn.enroll(conn, user["id"], exam_id, goal, exam_date or None)
    if kn.load_states(conn, user["id"], exam_id):
        return back("/u2/today")                       # экзамен уже был — только обновили цель
    return back(f"/u2/diag/{exam_id}")


# самооценка раздела → стартовая вероятность решить его номера
LEVELS = [("не умею", 0.1), ("иногда", 0.35), ("обычно", 0.6), ("почти всегда", 0.85)]


def _sections(exam):
    """Разделы для самооценки: группы экзамена (или части), плюс критерии работы в целом (ГК, устная часть)."""
    groups = exam.get("groups") or [{"name": p["name"], "tasks": [t["n"] for t in p["tasks"]]} for p in exam["parts"]]
    crit = [{"name": c["name"], "tasks": [c["id"]]} for c in exam.get("criteria", [])]
    return [{"name": g["name"], "tasks": g["tasks"], "label": _ranges(g["tasks"])} for g in groups] + crit


def _ranges(nums):
    """[1, 2, 3, 5, 7, 8, 9] → «1–3, 5, 7–9»."""
    out, nums = [], sorted(nums)
    start = prev = nums[0]
    for n in nums[1:] + [None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        out.append(str(start) if start == prev else f"{start}–{prev}" if prev > start + 1 else f"{start}, {prev}")
        start = prev = n
    return ", ".join(out)


@router.get("/diag/{exam_id}", response_class=HTMLResponse)
def u2_diag(exam_id: str, request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    enr = _enrolled(conn, sid, exam_id)
    exam = em.load(exam_id)
    return _page(request, conn, user, "today", "u2/diag.html", c=_card(enr, {}, config.today()),
                 sections=_sections(exam), levels=LEVELS)


@router.post("/diag/{exam_id}")
async def u2_diag_submit(exam_id: str, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    only_student(user)
    _enrolled(conn, user["id"], exam_id)
    form = await request.form()
    today = config.today()
    with conn:
        for i, sec in enumerate(_sections(em.load(exam_id))):
            raw = str(form.get(f"s{i}", ""))
            if raw.isdigit() and int(raw) < len(LEVELS):
                for key in sec["tasks"]:
                    kn.seed(conn, user["id"], exam_id, key, LEVELS[int(raw)][1], today)
        kn.log_forecast(conn, user["id"], exam_id, today)
    return back("/u2/today")


# ------------------------------------------------------------------ тренажёр: номер → попытка → запись в модель знаний
def _enrolled(conn, sid, exam_id):
    enr = next((e for e in kn.exams_of(conn, sid) if e["exam_id"] == exam_id), None)
    if not enr:
        raise HTTPException(404)
    return enr


def _task_key(exam, raw):
    key = int(raw) if raw.isdigit() else raw
    if key not in em.points(exam):
        raise HTTPException(404)
    return key


def _task_info(exam, key):
    """Название, баллы и раздел номера (или критерия ГК/ФК)."""
    crit = {c["id"]: c for c in exam.get("criteria", [])}
    group = next((g["name"] for g in exam.get("groups", []) if key in g["tasks"]), None)
    if key in crit:
        return {"key": key, "label": key, "title": crit[key].get("name", "Критерий"), "points": crit[key]["points"],
                "group": group}
    task = next(t for t in em.tasks(exam) if t["n"] == key)
    part = next(p["name"] for p in exam["parts"] if task in p["tasks"])
    return {"key": key, "label": f"№{key}", "title": task.get("title") or TITLES.get(exam["id"], {}).get(key) or group or part,
            "points": task["points"], "group": group or part}


def _plan(exam, states, minutes, today, due=()):
    """План дня только из номеров, которые решаются на сайте, — для экзаменов, где это уже возможно."""
    only = u2_onsite.onsite(exam["id"])
    if only is not None:
        due = [n for n in due if n in only]
    return kn.plan(exam, states, minutes, today, due=due, only=only)


def _next_step(exam, states, today, after, minutes):
    """Следующий номер по плану на сегодня, кроме только что решённого."""
    for st in _plan(exam, states, minutes, today):
        if st["n"] != after:
            return st["n"]
    return None


def _train_ctx(conn, sid, enr, key, today):
    exam = em.load(enr["exam_id"])
    states = kn.load_states(conn, sid, exam["id"])
    st = kn.decay(states.get(key), today)
    mode = u2_onsite.mode_of(exam["id"], key)
    return {"c": _card(enr, states, today), "t": _task_info(exam, key), "p": st["p"], "tries": st.get("n", 0),
            "bank": FIPI_BANK.get(exam["exam"]), "generated": mode == "gen", "mode": mode}


@router.get("/train/{exam_id}/{raw}", response_class=HTMLResponse)
def u2_train(exam_id: str, raw: str, request: Request, seed: int = 0, conn=Depends(get_db),
             user=Depends(auth.current_user)):
    sid, today = need_sid(conn, user), config.today()
    enr = _enrolled(conn, sid, exam_id)
    key = _task_key(em.load(exam_id), raw)
    ctx = _train_ctx(conn, sid, enr, key, today)
    if ctx["mode"] != "self":
        if not 0 < seed < 10 ** 7:
            return back(f"/u2/train/{exam_id}/{key}?seed={_fresh_seed()}")
        ctx.update(_play_ctx(exam_id, key, seed))
    return _page(request, conn, user, "today", "u2/train.html", res=None, **ctx)


MAX_ATTEMPTS_PER_DAY = 1000  # живой ученик столько не решит; защита журнала попыток от накрутки скриптом


def _budget(conn, sid, today, n=1):
    done = conn.execute("SELECT COUNT(*) FROM skill_attempt WHERE student_id = ? AND day = ?",
                        (sid, today.isoformat())).fetchone()[0]
    if done + n > MAX_ATTEMPTS_PER_DAY:
        raise HTTPException(429, "На сегодня заданий достаточно — продолжим завтра.")


def _variant(exam_id, key, seed):
    if exam_id == "oge-inf-2026" and key in oge_u2.GENERATORS:
        return oge_u2.make(key, seed)
    bank = BANKS.get(exam_id)
    return bank.make(key, seed) if bank else oge_gen.make(key, seed)


def _fresh_seed():
    return random.randrange(1, 10 ** 6)


def _play_ctx(exam_id, key, seed):
    """Условие номера, которое можно показать до ответа."""
    mode = u2_onsite.mode_of(exam_id, key)
    if mode == "gen":
        v = _variant(exam_id, key, seed)
        return {"seed": seed, "variant": oge_gen.public(v), "text": oge_drill.rich(v["text"])}
    if mode == "ru":
        item = u2_onsite.ru_item(exam_id, key, seed)
        return {"seed": seed, "ru": russian.public(item)}
    if mode == "robot":
        task = robot_content.TASKS[seed % len(robot_content.TASKS)]
        return {"seed": seed, "robot": robot_content.public(task), "fields": robot_content.fields_for(task, seed),
                "help": robot_content.COMMANDS_HELP, "starter": task["starter"]}
    v = oge16_gen.make(seed)
    return {"seed": seed, "code": {"text": v["text"], "examples": [t for t in v["tests"] if not t["hidden"]],
                                   "tests": v["tests"], "id": v["id"]}}


def _steps_view(v):
    return [oge_drill.rich(s) for s in v.get("steps") or []]


@router.post("/train/{exam_id}/{raw}", response_class=HTMLResponse)
def u2_train_submit(exam_id: str, raw: str, request: Request, seed: int = Form(0), answer: str = Form(""),
                    score: int = Form(-1), hint: int = Form(0), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    only_student(user)
    sid, today = user["id"], config.today()
    enr = _enrolled(conn, sid, exam_id)
    exam = em.load(exam_id)
    key = _task_key(exam, raw)
    before = _card(enr, kn.load_states(conn, sid, exam_id), today)
    if key in GENERATED.get(exam_id, ()):
        if not 0 < seed < 10 ** 7:
            raise HTTPException(400)
        v = _variant(exam_id, key, seed)
        ok = BANKS[exam_id].check(v, answer[:100]) if exam_id in BANKS else oge_gen.check(v, answer[:100])
        if not ok and hint != 1:
            ctx = _train_ctx(conn, sid, enr, key, today)
            ctx.update(_play_ctx(exam_id, key, seed), given=answer[:100])
            return _page(request, conn, user, "today", "u2/train.html",
                         res={"ok": False, "pending": True, "hint": oge_drill.rich(v["steps"][0])}, **ctx)
        _budget(conn, sid, today)
        if exam_id not in BANKS and key in oge_gen.GENERATORS:
            oge_drill.answer(conn, sid, key, seed, answer[:100])   # трофеи старого тренажёра
        got, given = (1.0 if ok else 0.0), answer.strip()[:100]
        res = {"ok": ok, "answer": v["answer"], "explain": v["explain"], "steps": _steps_view(v), "xp": 0}
    else:
        _budget(conn, sid, today)
        mx = em.points(exam)[key]
        if not 0 <= score <= mx:
            raise HTTPException(400, f"Баллы — от 0 до {mx}")
        got = score / mx
        res = {"ok": score == mx, "score": score, "max": mx}
        seed, given = None, None
    with conn:
        kn.record(conn, sid, exam_id, key, got, today, seed=seed, given=given)
        kn.log_forecast(conn, sid, exam_id, today)
    ctx = _train_ctx(conn, sid, enr, key, today)
    if ctx["generated"]:
        ctx.update(_play_ctx(exam_id, key, seed), given=answer[:100])
    after = ctx["c"]
    k = after["kind"]
    delta = {"from": before["fc"][k], "to": after["fc"][k], "primary": round(after["fc"]["primary"] - before["fc"]["primary"], 1)}
    nxt = _next_step(exam, after["states"], today, key, _minutes(conn, sid))
    return _page(request, conn, user, "today", "u2/train.html", res=res, delta=delta, next_key=nxt, **ctx)


@router.post("/api/ru/{exam_id}/{raw}")
async def u2_ru_answer(exam_id: str, raw: str, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    """Ответ в тренажёре русского внутри /u2. Первая ошибка — подсказка и не пишется в журнал."""
    only_student(user)
    sid, today = user["id"], config.today()
    _enrolled(conn, sid, exam_id)
    exam = em.load(exam_id)
    key = _task_key(exam, raw)
    if u2_onsite.mode_of(exam_id, key) != "ru":
        raise HTTPException(404)
    data = await request.json()
    try:
        seed = int(data.get("seed", 0))
    except (TypeError, ValueError):
        raise HTTPException(400)
    if not 0 < seed < 10 ** 7:
        raise HTTPException(400)
    item = u2_onsite.ru_item(exam_id, key, seed)
    if str(data.get("id", "")) != item["id"]:
        raise HTTPException(400)
    ok, detail = u2_onsite.check_ru(item, data.get("answer"))
    title, rule = RU_RULES[item["rule"]]
    if not ok and int(data.get("hint") or 0) != 1:
        return {"ok": False, "pending": True, "hint": u2_onsite.rule_hint(item), "rule_title": title}
    _budget(conn, sid, today)
    given = json.dumps(data.get("answer"), ensure_ascii=False)[:100]
    with conn:
        kn.record(conn, sid, exam_id, key, 1.0 if ok else 0.0, today, seed=seed, given=given)
        kn.log_forecast(conn, sid, exam_id, today)
    return {"ok": ok, "pending": False, "rule_title": title, "rule_text": rule, **detail}


@router.post("/api/play/{exam_id}/{raw}")
async def u2_play(exam_id: str, raw: str, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    """Робот и №16: проверка в браузере, как в старых тренажёрах. В журнал — со второй ошибки или с верного ответа."""
    only_student(user)
    sid, today = user["id"], config.today()
    _enrolled(conn, sid, exam_id)
    exam = em.load(exam_id)
    key = _task_key(exam, raw)
    mode = u2_onsite.mode_of(exam_id, key)
    if mode not in ("robot", "code"):
        raise HTTPException(404)
    data = await request.json()
    try:
        seed = int(data.get("seed", 0))
    except (TypeError, ValueError):
        raise HTTPException(400)
    if not 0 < seed < 10 ** 7:
        raise HTTPException(400)
    passed = bool(data.get("passed"))
    if mode == "robot":
        task = robot_content.TASKS[seed % len(robot_content.TASKS)]
        hint, steps = task["hint"], [task["hint"], "Проверь программу на короткой стене и на длинной.",
                                     "Крась клетку в том же цикле, где идёшь вдоль стены."]
        solution = {"py": task["solution"], "ku": task["kumir"]}
    else:
        v = oge16_gen.make(seed)
        hint, steps, solution = v["steps"][0], v["steps"], {"py": v["solution"]}
    if not passed and int(data.get("hint") or 0) != 1:
        return {"ok": False, "pending": True, "hint": hint}
    _budget(conn, sid, today)
    with conn:
        kn.record(conn, sid, exam_id, key, 1.0 if passed else 0.0, today, seed=seed, given=str(data.get("code", ""))[:100])
        kn.log_forecast(conn, sid, exam_id, today)
    return {"ok": passed, "pending": False, "steps": steps, "solution": solution}


# ================================================================== мини-пробник
MOCK_MINUTES = 25


def _mock_items(exam, seed):
    """Набор пробника: генерируемые номера из разных частей экзамена на MOCK_MINUTES минут. Пара (экзамен, сид)
    всегда даёт тот же набор и те же варианты — проверка на сервере пересборкой, как в тренажёре."""
    r = random.Random(f"mock-{exam['id']}-{seed}")
    by_n = {t["n"]: t for t in em.tasks(exam)}
    nums = sorted(GENERATED.get(exam["id"], ()))
    r.shuffle(nums)
    picked, left = [], MOCK_MINUTES
    for n in nums:
        m = kn.task_minutes(by_n[n])
        if m <= left:
            picked.append((n, r.randrange(1, 10 ** 6)))
            left -= m
    return sorted(picked)


def _mock_ctx(exam, seed):
    items = []
    for n, s in _mock_items(exam, seed):
        v = _variant(exam["id"], n, s)
        items.append({"t": _task_info(exam, n), "seed": s, "v": v, "variant": oge_gen.public(v),
                      "text": oge_drill.rich(v["text"])})
    return items


def _check(exam_id, v, given):
    bank = BANKS.get(exam_id)
    return bank.check(v, given) if bank else oge_gen.check(v, given)


@router.get("/mock/{exam_id}", response_class=HTMLResponse)
def u2_mock(exam_id: str, request: Request, seed: int = 0, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid, today = need_sid(conn, user), config.today()
    enr = _enrolled(conn, sid, exam_id)
    exam = em.load(exam_id)
    if not GENERATED.get(exam_id):
        raise HTTPException(404)
    if not 0 < seed < 10 ** 7:
        return back(f"/u2/mock/{exam_id}?seed={random.randrange(1, 10 ** 6)}")
    c = _card(enr, kn.load_states(conn, sid, exam_id), today)
    return _page(request, conn, user, "today", "u2/mock.html", c=c, seed=seed, items=_mock_ctx(exam, seed),
                 minutes=MOCK_MINUTES, result=None)


@router.post("/mock/{exam_id}", response_class=HTMLResponse)
async def u2_mock_submit(exam_id: str, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid, today = only_student(user), config.today()
    enr = _enrolled(conn, sid, exam_id)
    exam = em.load(exam_id)
    form = await request.form()
    try:
        seed = int(form.get("seed", 0))
    except ValueError:
        raise HTTPException(400)
    if not GENERATED.get(exam_id) or not 0 < seed < 10 ** 7:
        raise HTTPException(400)
    before = _card(enr, kn.load_states(conn, sid, exam_id), today)
    items = _mock_ctx(exam, seed)
    _budget(conn, sid, today, len(items))
    with conn:
        for it in items:
            it["given"] = str(form.get("a%s" % it["t"]["key"], "")).strip()[:100]
            it["ok"] = bool(it["given"]) and _check(exam_id, it["v"], it["given"])
            it["answer"], it["explain"] = it["v"]["answer"], it["v"]["explain"]
            kn.record(conn, sid, exam_id, it["t"]["key"], 1.0 if it["ok"] else 0.0, today, seed=it["seed"],
                      given=it["given"])
        kn.log_forecast(conn, sid, exam_id, today)
    c = _card(enr, kn.load_states(conn, sid, exam_id), today)
    k = c["kind"]
    delta = {"from": before["fc"][k], "to": c["fc"][k], "primary": round(c["fc"]["primary"] - before["fc"]["primary"], 1)}
    result = {"right": sum(it["ok"] for it in items), "total": len(items),
              "points": sum(it["t"]["points"] for it in items if it["ok"]), "max_points": sum(it["t"]["points"] for it in items)}
    return _page(request, conn, user, "today", "u2/mock.html", c=c, seed=seed, items=items, minutes=MOCK_MINUTES,
                 result=result, delta=delta)


# ================================================================== учитель: класс по экзаменам
WEAK_SHOWN = 3


def _class_row(conn, st, enr, today):
    states = kn.load_states(conn, st["id"], enr["exam_id"])
    c = _card(enr, states, today)
    tried = [(kn.decay(s, today)["p"], k) for k, s in states.items() if s["n"]]
    weak = [{"key": k, "label": _task_info(c["exam"], k)["label"], "p": p} for p, k in sorted(tried)[:WEAK_SHOWN]
            if p < REVIEW_MIN_P]
    since = (today - timedelta(days=7)).isoformat()
    week = conn.execute("SELECT COUNT(*) FROM skill_attempt WHERE student_id = ? AND exam_id = ? AND day >= ?",
                        (st["id"], enr["exam_id"], since)).fetchone()[0]
    last = max((s["last"] for s in states.values() if s["n"] and s.get("last")), default=None)
    return {"sid": st["id"], "name": st["display_name"], "c": c, "weak": weak, "week": week, "last": last}


@router.get("/class", response_class=HTMLResponse)
def u2_class(request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    """Все ученики по экзаменам: прогноз, цель, разрыв, слабые номера, активность за неделю. Выше — у кого разрыв
    с целью больше."""
    today, exams = config.today(), {}
    for st in students.list_students(conn):
        for enr in kn.exams_of(conn, st["id"]):
            row = _class_row(conn, st, enr, today)
            ex = exams.setdefault(enr["exam_id"], {"title": row["c"]["title"], "kind": row["c"]["kind"], "rows": []})
            ex["rows"].append(row)
    for ex in exams.values():
        ex["rows"].sort(key=lambda r: (-r["c"]["gap"], r["name"]))
    return render(request, "u2/class.html", conn, user, tab=None, tabs=[], exams=list(exams.values()))
