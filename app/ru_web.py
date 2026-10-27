"""Русский язык: запятые, орфограммы, основа, диктанты, повторение ошибок.

Маршруты вынесены из main.py; общие функции берутся оттуда. Подключается в конце main.py.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import auth, game, russian, students, subjects
from .db import bump_counter, get_db
from .content.checks import CHECK_BY_ID
from .content.ru import RULES as RU_RULES
from .main import check_states, need_sid, render

router = APIRouter()


@router.post("/api/run")
def api_run(conn=Depends(get_db), user=Depends(auth.check_csrf)):
    if user["role"] != "student":
        return {"notices": []}
    sid = user["id"]
    with conn:
        bump_counter(conn, sid, "runs")
        game.sync_achievements(conn, sid)
    return {"notices": game.pop_notices(conn, sid)}


# ------------------------------------------------------------------ русский язык
def ru_sid(conn, user):
    sid = need_sid(conn, user)
    if user["role"] == "student" and "russian" not in subjects.of(students.get_student(conn, sid)):
        raise HTTPException(404, "Русский язык не подключён — попроси преподавателя")
    return sid


@router.get("/ru", response_class=HTMLResponse)
def ru_home(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = ru_sid(conn, user)
    states, results = check_states(conn, sid)
    return render(request, "ru/home.html", conn, user, ov=russian.overview(conn, sid),
                  entry=CHECK_BY_ID["ru_entry"], entry_state=states.get("ru_entry"), entry_result=results.get("ru_entry"))


@router.get("/ru/commas", response_class=HTMLResponse)
def ru_commas(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    ru_sid(conn, user)
    return render(request, "ru/trainer.html", conn, user, mode="comma")


@router.get("/ru/spell", response_class=HTMLResponse)
def ru_spell(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    ru_sid(conn, user)
    return render(request, "ru/trainer.html", conn, user, mode="spell")


@router.get("/ru/basis", response_class=HTMLResponse)
def ru_basis(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    ru_sid(conn, user)
    return render(request, "ru/trainer.html", conn, user, mode="basis")


@router.get("/ru/dict", response_class=HTMLResponse)
def ru_dict(request: Request, id: str = "", conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = ru_sid(conn, user)
    d = russian.DICT_ITEMS.get(id) or russian.dict_pick(conn, sid)
    return render(request, "ru/trainer.html", conn, user, mode="dict", dict_data=russian.dict_public(d),
                  dict_title=d["title"])


@router.post("/api/ru/dict")
async def ru_dict_answer(request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = ru_sid(conn, user)
    data = await request.json()
    did = str(data.get("id", ""))
    if did not in russian.DICT_ITEMS:
        raise HTTPException(404)
    res = russian.dict_answer(conn, sid, did, data.get("letters"), data.get("commas"), record=user["role"] == "student")
    res["notices"] = game.pop_notices(conn, sid) if user["role"] == "student" else []
    return res


@router.get("/ru/practice/{rule}", response_class=HTMLResponse)
def ru_practice(rule: str, request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    ru_sid(conn, user)
    if rule not in RU_RULES:
        raise HTTPException(404)
    return render(request, "ru/trainer.html", conn, user, mode="rule", rule=rule, rule_title=RU_RULES[rule][0],
                  rule_text=RU_RULES[rule][1])


@router.get("/ru/review", response_class=HTMLResponse)
def ru_review(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    ru_sid(conn, user)
    return render(request, "ru/trainer.html", conn, user, mode="review")


@router.get("/ru/rules", response_class=HTMLResponse)
def ru_rules(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = ru_sid(conn, user)
    return render(request, "ru/rules.html", conn, user, ov=russian.overview(conn, sid))


@router.get("/api/ru/next")
def ru_next(kind: str = "comma", rule: str = "", skip: str = "", conn=Depends(get_db),
            user=Depends(auth.current_user)):
    sid = ru_sid(conn, user)
    if kind == "rule":
        item = russian.pick_rule(conn, sid, rule, exclude=set(skip.split(",")))
        return {"item": russian.public(item) if item else None}
    if kind == "review":
        due = russian.due_items(conn, sid)
        return {"item": russian.public(due[0]) if due else None, "left": len(due)}
    if kind not in ("comma", "spell", "basis"):
        raise HTTPException(400)
    item, is_due = russian.pick(conn, sid, kind)
    return {"item": russian.public(item), "due": is_due}


@router.get("/api/ru/batch")
def ru_batch(conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = ru_sid(conn, user)
    return {"items": [russian.public(i) for i in russian.batch(conn, sid, "spell")]}


@router.post("/api/ru/answer")
async def ru_answer(request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = ru_sid(conn, user)
    data = await request.json()
    mode = data.get("mode") if data.get("mode") in ("comma", "spell", "arena", "review", "basis", "rule") else "comma"
    try:
        res = russian.answer(conn, sid, str(data.get("id", "")), data.get("answer"), mode,
                             record=user["role"] == "student")
    except KeyError:
        raise HTTPException(404)
    res["notices"] = game.pop_notices(conn, sid) if user["role"] == "student" else []
    return res
