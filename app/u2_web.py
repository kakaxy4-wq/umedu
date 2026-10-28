"""umedu 2.0: подготовка к ОГЭ/ЕГЭ с прогнозом балла. Четыре вкладки, выбор экзамена и тренажёр по номерам.

Раздел /u2 включается флагом CQ_UMEDU2=1; без него все адреса раздела отвечают 404, действующий сайт не меняется.
Данные — app/knowledge.py (знания по номерам, прогноз, план) поверх app/exam_model.py (номера и шкалы).
"""
import json
import random
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import auth, config, oge_drill
from . import exam_model as em
from . import knowledge as kn
from .content import inf_gen, math_gen, oge_gen, phys_gen
from .content.oge import OGE_NUMBERS
from .db import get_db
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
GENERATED = {"oge-inf-2026": set(oge_gen.GENERATORS), **{e: set(b.GENERATORS) for e, b in BANKS.items()}}
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
            "attempts": sum(s["n"] for s in states.values()), "states": states}


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
            items = kn.plan(c["exam"], c["states"], minutes[c["id"]], today, due=_due(c["exam"], c["states"], today, minutes[c["id"]]))
            for it in items:
                it["title"] = _task_info(c["exam"], it["n"])["title"]
            plans.append({"card": c, "minutes": sum(i["minutes"] for i in items), "steps": items})
    return _page(request, conn, user, "today", "u2/today.html", cards=cards, plans=plans,
                 total=sum(p["minutes"] for p in plans))


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
    return _page(request, conn, user, "subjects", "u2/subject.html", c=c, tasks=tasks)


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


@router.get("/me", response_class=HTMLResponse)
def u2_me(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    return _page(request, conn, user, "me", "u2/me.html", cards=_cards(conn, sid, config.today()),
                 minutes=_minutes(conn, sid), choices=MINUTE_CHOICES)


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


def _next_step(exam, states, today, after, minutes):
    """Следующий номер по плану на сегодня, кроме только что решённого."""
    for st in kn.plan(exam, states, minutes, today):
        if st["n"] != after:
            return st["n"]
    return None


def _train_ctx(conn, sid, enr, key, today):
    exam = em.load(enr["exam_id"])
    states = kn.load_states(conn, sid, exam["id"])
    st = kn.decay(states.get(key), today)
    return {"c": _card(enr, states, today), "t": _task_info(exam, key), "p": st["p"], "tries": st.get("n", 0),
            "bank": FIPI_BANK.get(exam["exam"]), "generated": key in GENERATED.get(exam["id"], ())}


@router.get("/train/{exam_id}/{raw}", response_class=HTMLResponse)
def u2_train(exam_id: str, raw: str, request: Request, seed: int = 0, conn=Depends(get_db),
             user=Depends(auth.current_user)):
    sid, today = need_sid(conn, user), config.today()
    enr = _enrolled(conn, sid, exam_id)
    key = _task_key(em.load(exam_id), raw)
    ctx = _train_ctx(conn, sid, enr, key, today)
    if ctx["generated"]:
        if not 0 < seed < 10 ** 7:
            return back(f"/u2/train/{exam_id}/{key}?seed={random.randrange(1, 10 ** 6)}")
        v = _variant(exam_id, key, seed)
        ctx.update(seed=seed, variant=oge_gen.public(v), text=oge_drill.rich(v["text"]))
    return _page(request, conn, user, "today", "u2/train.html", res=None, **ctx)


def _variant(exam_id, key, seed):
    bank = BANKS.get(exam_id)
    return bank.make(key, seed) if bank else oge_gen.make(key, seed)


@router.post("/train/{exam_id}/{raw}", response_class=HTMLResponse)
def u2_train_submit(exam_id: str, raw: str, request: Request, seed: int = Form(0), answer: str = Form(""),
                    score: int = Form(-1), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    only_student(user)
    sid, today = user["id"], config.today()
    enr = _enrolled(conn, sid, exam_id)
    exam = em.load(exam_id)
    key = _task_key(exam, raw)
    before = _card(enr, kn.load_states(conn, sid, exam_id), today)
    if key in GENERATED.get(exam_id, ()):
        if not 0 < seed < 10 ** 7:
            raise HTTPException(400)
        if exam_id in BANKS:
            v = BANKS[exam_id].make(key, seed)
            res = {"ok": BANKS[exam_id].check(v, answer[:100]), "answer": v["answer"], "explain": v["explain"], "xp": 0}
        else:
            res = oge_drill.answer(conn, sid, key, seed, answer[:100])  # заодно — статистика и трофеи старого тренажёра
        got, given = (1.0 if res["ok"] else 0.0), answer.strip()[:100]
    else:
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
        v = _variant(exam_id, key, seed)
        ctx.update(seed=seed, variant=oge_gen.public(v), text=oge_drill.rich(v["text"]), given=answer[:100])
    after = ctx["c"]
    k = after["kind"]
    delta = {"from": before["fc"][k], "to": after["fc"][k], "primary": round(after["fc"]["primary"] - before["fc"]["primary"], 1)}
    nxt = _next_step(exam, after["states"], today, key, _minutes(conn, sid))
    return _page(request, conn, user, "today", "u2/train.html", res=res, delta=delta, next_key=nxt, **ctx)
