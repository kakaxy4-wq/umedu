"""umedu 2.0: подготовка к ОГЭ/ЕГЭ с прогнозом балла. Каркас интерфейса — четыре вкладки и выбор экзамена.

Раздел /u2 включается флагом CQ_UMEDU2=1; без него все адреса раздела отвечают 404, действующий сайт не меняется.
Данные — app/knowledge.py (знания по номерам, прогноз, план) поверх app/exam_model.py (номера и шкалы).
"""
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import auth, config
from . import exam_model as em
from . import knowledge as kn
from .db import get_db
from .main import back, need_sid, only_student, render


def _enabled():
    if not config.UMEDU2:
        raise HTTPException(404)


router = APIRouter(prefix="/u2", dependencies=[Depends(_enabled)])

DAILY_MINUTES = 30
REVIEW_AFTER_DAYS = 14        # номер, к которому не возвращались столько дней, попадает в план как повторение
REVIEW_MIN_P = 0.6
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
    minutes = kn.split_minutes({c["id"]: c["gap"] for c in cards}, DAILY_MINUTES)
    plans = []
    for c in cards:
        if minutes.get(c["id"]):
            items = kn.plan(c["exam"], c["states"], minutes[c["id"]], today, due=_due(c["exam"], c["states"], today, minutes[c["id"]]))
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
    sid = need_sid(conn, user)
    return _page(request, conn, user, "progress", "u2/progress.html", cards=_cards(conn, sid, config.today()))


@router.get("/me", response_class=HTMLResponse)
def u2_me(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    return _page(request, conn, user, "me", "u2/me.html", cards=_cards(conn, sid, config.today()))


# ------------------------------------------------------------------ выбор экзамена (онбординг; диагностика — следующий шаг)
def _catalog():
    out = []
    for exam_id in em.all_ids():
        ex = em.load(exam_id)
        out.append({"id": exam_id, "title": f'{ex["exam"]} · {ex["subject"]}', "kind": _kind(ex), "range": _goal_range(ex),
                    "min": ex["scale"].get("min_university")})
    return sorted(out, key=lambda e: (e["title"][:3] != "ОГЭ", e["title"]))


@router.get("/start", response_class=HTMLResponse)
def u2_start(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    mine = {e["exam_id"] for e in kn.exams_of(conn, sid)}
    return _page(request, conn, user, "me", "u2/start.html", catalog=_catalog(), mine=mine)


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
    return back("/u2/today")
