"""ОГЭ по информатике: тренажёр номеров, пробник, исполнитель «Робот», битва ботов.

Маршруты вынесены из main.py; общие функции берутся оттуда. Подключается в конце main.py.
"""
import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import auth, forecast, game, oge_drill, season, students
from .content import bots as bots_content, oge16_gen, oge_gen, robot as robot_content
from .content.lessons import LESSON_BY_NUM
from .db import get_db
from .content.oge import FIPI_DEMO_URL, FIPI_GUIDE_URL, OGE_NUMBERS
from .main import _mock_items, back, is_teacher, need_sid, oge_progress, render, robot_solved

router = APIRouter()


# ------------------------------------------------------------------ ОГЭ, часть 1: тренажёр вариантов и пробник
MOCK_MINUTES = 30


@router.get("/oge/mock", response_class=HTMLResponse)
def oge_mock(request: Request, k: int = 0, t: int = 0, conn=Depends(get_db), user=Depends(auth.current_user)):
    need_sid(conn, user)
    if not (0 < k < 10 ** 6 and t > 0):
        return back("/oge/mock?k=%d&t=%d" % (random.randrange(1, 10 ** 6), int(datetime.now(timezone.utc).timestamp())))
    started = datetime.fromtimestamp(t, timezone.utc).isoformat()
    return render(request, "student/oge_mock.html", conn, user, key=k, t=t, started=started, minutes=MOCK_MINUTES,
                  items=_mock_items(k), results=None)


@router.post("/oge/mock", response_class=HTMLResponse)
async def oge_mock_submit(request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = need_sid(conn, user)
    form = await request.form()
    try:
        k, t = int(form.get("k", 0)), int(form.get("t", 0))
    except ValueError:
        raise HTTPException(400)
    if not 0 < k < 10 ** 6:
        raise HTTPException(400)
    results, xp = [], 0
    for it in _mock_items(k):
        given = str(form.get("a%d" % it["num"], ""))[:100].strip()
        res = oge_drill.answer(conn, sid, it["num"], it["seed"], given, record=user["role"] == "student") if given \
            else {"ok": False, "answer": it["v"]["answer"], "explain": it["v"]["explain"], "xp": 0}
        xp += res["xp"]
        results.append({"num": it["num"], "title": it["title"], "given": given, **res})
    now = int(datetime.now(timezone.utc).timestamp())
    spent = (now - t) // 60 if 0 < now - t < 6 * 3600 else None
    return render(request, "student/oge_mock.html", conn, user, results=results, xp=xp, spent=spent,
                  score=sum(r["ok"] for r in results))


@router.get("/oge/code16", response_class=HTMLResponse)
def oge_code16(request: Request, seed: int = 0, conn=Depends(get_db), user=Depends(auth.current_user)):
    """№16: бесконечные варианты задачи на программирование, проверка в браузере на скрытых тестах."""
    sid = need_sid(conn, user)
    if not 0 < seed < 10 ** 7:
        return back("/oge/code16?seed=%d" % random.randrange(1, 10 ** 6))
    if not is_teacher(user) and oge16_gen.LESSON > game.unlocked_upto(conn, sid):
        return render(request, "student/locked.html", conn, user, lesson=LESSON_BY_NUM[oge16_gen.LESSON])
    v = oge16_gen.make(seed)
    solved = bool(conn.execute("SELECT 1 FROM oge_drill WHERE student_id = ? AND num = 16 AND seed = ? AND ok = 1",
                               (sid, seed)).fetchone())
    return render(request, "student/oge_code.html", conn, user, task=v, solved=solved,
                  st=oge_drill.stats(conn, sid).get(16), examples=[t for t in v["tests"] if not t["hidden"]])


@router.get("/oge/drill/{num}", response_class=HTMLResponse)
def oge_drill_page(num: int, request: Request, seed: int = 0, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    if num not in oge_gen.GENERATORS:
        raise HTTPException(404)
    if not 0 < seed < 10 ** 7:
        return back("/oge/drill/%d?seed=%d" % (num, random.randrange(1, 10 ** 6)))
    v = oge_gen.make(num, seed)
    return render(request, "student/oge_drill.html", conn, user, num=num, seed=seed, variant=oge_gen.public(v),
                  text=oge_drill.rich(v["text"]), title=OGE_NUMBERS[num][0], st=oge_drill.stats(conn, sid).get(num),
                  res=None, given="")


@router.post("/oge/drill/{num}", response_class=HTMLResponse)
def oge_drill_answer(num: int, request: Request, seed: int = Form(...), answer: str = Form(""), conn=Depends(get_db),
                     user=Depends(auth.check_csrf)):
    sid = need_sid(conn, user)
    if num not in oge_gen.GENERATORS or not 0 < seed < 10 ** 7:
        raise HTTPException(404)
    res = oge_drill.answer(conn, sid, num, seed, answer[:100], record=user["role"] == "student")
    v = oge_gen.make(num, seed)
    return render(request, "student/oge_drill.html", conn, user, num=num, seed=seed, variant=oge_gen.public(v),
                  text=oge_drill.rich(v["text"]), title=OGE_NUMBERS[num][0], st=oge_drill.stats(conn, sid).get(num),
                  res=res, given=answer[:100])


def robot_open(conn, user, sid):
    return is_teacher(user) or game.unlocked_upto(conn, sid) >= robot_content.LESSON


@router.get("/oge/robot", response_class=HTMLResponse)
def robot_list(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    return render(request, "student/robot_list.html", conn, user, tasks=robot_content.TASKS,
                  solved=robot_solved(conn, sid), is_open=robot_open(conn, user, sid), lesson=robot_content.LESSON,
                  help=robot_content.COMMANDS_HELP)


@router.get("/oge/robot/{task_id}", response_class=HTMLResponse)
def robot_page(task_id: str, request: Request, exam: int = 0, conn=Depends(get_db), user=Depends(auth.current_user)):
    if task_id == "exam":                  # «Как на экзамене»: случайная задача, сначала нерешённые
        sid = need_sid(conn, user)
        done = robot_solved(conn, sid)
        pool = [t for t in robot_content.TASKS if t["id"] not in done] or robot_content.TASKS
        return back("/oge/robot/%s?exam=1" % random.choice(pool)["id"])
    task = robot_content.TASK_BY_ID.get(task_id)
    if not task:
        raise HTTPException(404)
    sid = need_sid(conn, user)
    if not robot_open(conn, user, sid):
        return back("/oge/robot")
    last = conn.execute("SELECT code FROM robot_attempts WHERE student_id = ? AND task_id = ? ORDER BY id DESC LIMIT 1",
                        (sid, task_id)).fetchone()
    solved = task_id in robot_solved(conn, sid)
    ids = [t["id"] for t in robot_content.TASKS]
    nxt = ids[ids.index(task_id) + 1] if ids.index(task_id) + 1 < len(ids) else None
    exam = bool(exam)
    # На экзамене поля каждый раз новые и программа пишется с чистого листа; эталон не показываем до решения.
    fields = robot_content.fields_for(task, random.randrange(10 ** 6) if exam else None)
    code = robot_content.EXAM_STARTER if exam else (last["code"] if last else task["starter"])
    return render(request, "student/robot.html", conn, user, task=robot_content.public(task),
                  fields=fields, code=code, exam=exam, starter=robot_content.EXAM_STARTER if exam else task["starter"],
                  solved=solved, xp=robot_content.XP, help=robot_content.COMMANDS_HELP,
                  next_task=robot_content.TASK_BY_ID.get(nxt) if nxt else None,
                  answer=task if (solved or is_teacher(user)) and not exam else None)


@router.post("/api/robot/{task_id}/attempt")
async def robot_attempt(task_id: str, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    task = robot_content.TASK_BY_ID.get(task_id)
    if not task:
        raise HTTPException(404)
    data = await request.json()
    code = str(data.get("code", ""))[:50_000]
    passed = bool(data.get("passed"))
    result = {"first": False, "xp": 0, "notices": []}
    if user["role"] == "student":
        sid = user["id"]
        if not robot_open(conn, user, sid):
            raise HTTPException(404)
        already = task_id in robot_solved(conn, sid)
        with conn:
            conn.execute("INSERT INTO robot_attempts (student_id, task_id, code, passed, created_at) VALUES (?, ?, ?, ?, ?)",
                         (sid, task_id, code, 1 if passed else 0, game.now_iso()))
            if passed and not already:
                game.award(conn, sid, robot_content.XP, "Робот: «%s»" % task["title"], "robot", task_id)
                season.maybe_drop(conn, sid, "Робот: «%s»" % task["title"])
                result.update({"first": True, "xp": robot_content.XP})
        result["notices"] = game.pop_notices(conn, sid)
    if passed:
        result["solution"] = task["solution"]
        result["kumir"] = task["kumir"]
    return result


@router.get("/oge", response_class=HTMLResponse)
def oge_page(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    everyone = []
    if is_teacher(user):
        everyone = [(s, oge_progress(conn, s["id"])) for s in students.list_students(conn)]
    progress = oge_progress(conn, sid)
    return render(request, "student/oge.html", conn, user, numbers=OGE_NUMBERS, progress=progress,
                  fc=forecast.forecast(progress),
                  upto=999 if is_teacher(user) else game.unlocked_upto(conn, sid), solved=game.solved_task_ids(conn, sid),
                  everyone=everyone, demo_url=FIPI_DEMO_URL, guide_url=FIPI_GUIDE_URL)


# ------------------------------------------------------------------ битва ботов
def bots_beaten(conn, sid):
    return {r[0] for r in conn.execute("SELECT DISTINCT boss FROM bot_fights WHERE student_id = ? AND won = 1", (sid,))}


def bots_open(conn, user, sid):
    return is_teacher(user) or game.unlocked_upto(conn, sid) >= bots_content.LESSON


@router.get("/bots", response_class=HTMLResponse)
def bots_page(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    beaten = bots_beaten(conn, sid)
    ladder, prev_won = [], True
    for b in bots_content.BOSSES:
        ladder.append(dict(b, beaten=b["id"] in beaten, available=prev_won or is_teacher(user)))
        prev_won = b["id"] in beaten
    last = conn.execute("SELECT code FROM bot_fights WHERE student_id = ? ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    current = next((b for b in ladder if b["available"] and not b["beaten"]), ladder[-1])
    return render(request, "student/bots.html", conn, user, ladder=ladder, current=current,
                  is_open=bots_open(conn, user, sid), lesson=bots_content.LESSON,
                  code=last["code"] if last else bots_content.STARTER, starter=bots_content.STARTER,
                  help=bots_content.HELP)


@router.post("/api/bots/{boss}/result")
async def bots_result(boss: str, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    b = bots_content.BOSS_BY_ID.get(boss)
    if not b:
        raise HTTPException(404)
    data = await request.json()
    code = str(data.get("code", ""))[:50_000]
    won = bool(data.get("won"))
    result = {"first": False, "xp": 0, "notices": []}
    if user["role"] == "student":
        sid = user["id"]
        if not bots_open(conn, user, sid):
            raise HTTPException(404)
        already = boss in bots_beaten(conn, sid)
        with conn:
            conn.execute("INSERT INTO bot_fights (student_id, boss, code, won, created_at) VALUES (?, ?, ?, ?, ?)",
                         (sid, boss, code, 1 if won else 0, game.now_iso()))
            if won and not already:
                game.award(conn, sid, b["xp"], "Битва ботов: победа над «%s»" % b["name"], "bots", boss)
                result.update({"first": True, "xp": b["xp"]})
        result["notices"] = game.pop_notices(conn, sid)
    return result
