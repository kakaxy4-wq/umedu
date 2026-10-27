"""Кабинет ученика по Python: план дня, уроки, задачи, домашки, проверки, игра.

Маршруты вынесены из main.py; общие функции берутся оттуда. Подключается в конце main.py.
"""
import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from . import auth, certificates, config, game, season, students, subjects, theme, today
from .db import get_db
from .content.cheatsheet import CHEATSHEET
from .content.checks import CHECKS, CHECK_BY_ID, SKIP, grade
from .content.guides import has_guide
from .content.lessons import LESSONS, LESSON_BY_NUM, MODULES, MODULE_BY_NUM
from .content.quizzes import QUIZ_BY_ID
from .content.tasks import TASK_BY_ID, tasks_for_lesson
from .main import (FILE_EXT, back, cert_signer, check_states, is_teacher, need_sid, only_student, render,
    save_upload, subject_id, upload_path)

router = APIRouter()


@router.get("/today", response_class=HTMLResponse)
def today_page(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    return render(request, "student/today.html", conn, user, plan=today.plan(conn, sid))


@router.post("/today/claim")
def today_claim(conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = need_sid(conn, user)
    if is_teacher(user):
        raise HTTPException(403)
    with conn:
        today.claim(conn, sid)
    return back("/today")


@router.get("/homework")
def homework_go(conn=Depends(get_db), user=Depends(auth.current_user)):
    """Пункт меню «Домашка»: к ДЗ, которое сейчас надо делать, — самое раннее проведённое занятие без сданной или
    принятой домашки, а если такого нет — к домашке текущего урока."""
    sid = need_sid(conn, user)
    sent = {r[0] for r in conn.execute("SELECT DISTINCT lesson FROM submissions WHERE student_id = ? AND status != 'returned'",
                                       (sid,))}
    for r in conn.execute("SELECT num FROM lesson_state WHERE student_id = ? AND done_at IS NOT NULL ORDER BY num", (sid,)):
        if r[0] not in sent and LESSON_BY_NUM.get(r[0], {}).get("homework"):
            return back("/lesson/%d#homework" % r[0])
    return back("/lesson/%d#homework" % game.unlocked_upto(conn, sid))


@router.get("/map", response_class=HTMLResponse)
def lesson_map(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    lessons = game.lesson_list_with_state(conn, sid)
    modules = [{**m, "items": [lessons[n - 1] for n in m["lessons"]]} for m in MODULES]
    return render(request, "student/map.html", conn, user, modules=modules)


@router.get("/lesson/{num}", response_class=HTMLResponse)
def lesson_page(num: int, request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    lesson = LESSON_BY_NUM.get(num)
    if not lesson:
        raise HTTPException(404)
    sid = subject_id(conn, user)
    if not is_teacher(user) and num > game.unlocked_upto(conn, sid):
        return render(request, "student/locked.html", conn, user, lesson=lesson)
    solved = game.solved_task_ids(conn, sid) if sid else set()
    subs = conn.execute("SELECT * FROM submissions WHERE student_id = ? AND lesson = ? ORDER BY id DESC",
                        (sid, num)).fetchall() if sid else []
    state = conn.execute("SELECT * FROM lesson_state WHERE student_id = ? AND num = ?", (sid, num)).fetchone() if sid else None
    pace = None
    if sid and game.self_paced(conn, sid) and num == game.unlocked_upto(conn, sid) and not (state and state["done_at"]):
        lesson_tasks = tasks_for_lesson(num)
        pace = {"need": game.self_pace_need(num), "have": len([t for t in lesson_tasks if t["id"] in solved]),
                "last": num == len(LESSONS)}
    return render(request, "student/lesson.html", conn, user, lesson=lesson, module=MODULE_BY_NUM[lesson["module"]],
                  pace=pace,
                  tasks=tasks_for_lesson(num), solved=solved, subs=subs, state=state, guide=has_guide(num),
                  prev_num=num - 1 if num > 1 else None, next_num=num + 1 if num < len(LESSONS) else None)


@router.post("/lesson/{num}/self-done")
def lesson_self_done(num: int, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    """«Урок изучен» в самостоятельном темпе — только для уроков без задач."""
    sid = only_student(user)
    with conn:
        ok = game.self_pace_advance(conn, sid, num, by_button=True)
    return back("/lesson/%d" % (num + 1 if ok and num < len(LESSONS) else num))


@router.post("/lesson/{num}/submit")
async def submit_homework(num: int, request: Request, code: str = Form(""), comment: str = Form(""),
                          star: str = Form(""), upload: UploadFile = File(None),
                          conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = only_student(user)
    if num not in LESSON_BY_NUM or num > game.unlocked_upto(conn, sid):
        raise HTTPException(404)
    if not code.strip() and not comment.strip() and not (upload and upload.filename):
        return back("/lesson/%d#homework" % num)
    file_name, file_path = await save_upload(upload, FILE_EXT)
    with conn:
        conn.execute("INSERT INTO submissions (student_id, lesson, code, comment, file_name, file_path, star, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (sid, num, code[:100_000], comment[:5000], file_name, file_path, 1 if star else 0, game.now_iso()))
        game.add_notice(conn, sid, "📬", "Домашка к уроку %d отправлена! Жди проверки." % num)
        game.sync_achievements(conn, sid)
    game.tell_teacher(conn, sid, "📬 Сдана домашка к уроку %d «%s»%s" % (num, LESSON_BY_NUM[num]["title"],
                                                                        " ⭐" if star else ""), "/teacher/reviews")
    return back("/lesson/%d#homework" % num)


@router.get("/files/sub/{sub_id}")
def submission_file(sub_id: int, conn=Depends(get_db), user=Depends(auth.current_user)):
    row = conn.execute("SELECT student_id, file_name, file_path FROM submissions WHERE id = ?", (sub_id,)).fetchone()
    if not row or not row["file_path"] or (not is_teacher(user) and row["student_id"] != user["id"]):
        raise HTTPException(404)
    return FileResponse(upload_path(row["file_path"]), filename=row["file_name"])


# ------------------------------------------------------------------ задачи
@router.get("/task/{task_id}", response_class=HTMLResponse)
def task_page(task_id: str, request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    task = TASK_BY_ID.get(task_id)
    if not task:
        raise HTTPException(404)
    sid = subject_id(conn, user)
    if not is_teacher(user) and task["lesson"] > game.unlocked_upto(conn, sid):
        return render(request, "student/locked.html", conn, user, lesson=LESSON_BY_NUM[task["lesson"]])
    last = conn.execute("SELECT code FROM task_attempts WHERE student_id = ? AND task_id = ? ORDER BY id DESC LIMIT 1",
                        (sid, task_id)).fetchone() if sid else None
    solved = bool(sid) and task_id in game.solved_task_ids(conn, sid)
    fails = conn.execute("SELECT COUNT(*) FROM task_attempts WHERE student_id = ? AND task_id = ? AND passed = 0",
                         (sid, task_id)).fetchone()[0] if sid else 0
    siblings = tasks_for_lesson(task["lesson"])
    idx = [t["id"] for t in siblings].index(task_id)
    next_task = siblings[idx + 1] if idx + 1 < len(siblings) else None
    return render(request, "student/task.html", conn, user, task=task, lesson=LESSON_BY_NUM[task["lesson"]],
                  code=last["code"] if last else task["starter"], solved=solved, fails=fails,
                  show_solution=solved or is_teacher(user), next_task=next_task,
                  tests_public=[{k: v for k, v in t.items()} for t in task["tests"]])


@router.post("/api/task/{task_id}/attempt")
async def task_attempt(task_id: str, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    task = TASK_BY_ID.get(task_id)
    if not task:
        raise HTTPException(404)
    data = await request.json()
    code = str(data.get("code", ""))[:100_000]
    passed = bool(data.get("passed"))
    result = {"first": False, "xp": 0, "notices": []}
    if user["role"] == "student":
        sid = user["id"]
        if task["lesson"] > game.unlocked_upto(conn, sid):
            raise HTTPException(404)
        already = task_id in game.solved_task_ids(conn, sid)
        with conn:
            conn.execute("INSERT INTO task_attempts (student_id, task_id, code, passed, created_at) VALUES (?, ?, ?, ?, ?)",
                         (sid, task_id, code, 1 if passed else 0, game.now_iso()))
            if passed and not already:
                game.award(conn, sid, task["xp"], "Задача «%s»" % task["title"], "task", task_id)
                game.daily_task_solved(conn, sid, task_id)
                season.maybe_drop(conn, sid, "задача «%s»" % task["title"])
                game.self_pace_advance(conn, sid, task["lesson"])
                result.update({"first": True, "xp": task["xp"]})
        result["notices"] = game.pop_notices(conn, sid)
    if passed:
        result["solution"] = task["solution"]
    return result


# ------------------------------------------------------------------ задача дня
@router.get("/daily", response_class=HTMLResponse)
def daily_page(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    d = game.get_daily(conn, sid)
    if d["kind"] == "task":
        return back("/task/%s" % d["ref"])
    quiz = QUIZ_BY_ID[d["ref"]]
    numeric = bool(re.fullmatch(r"-?\d+([.,]\d+)?", quiz["answer"].strip()))
    history = conn.execute("SELECT * FROM daily WHERE student_id = ? AND finished_at IS NOT NULL ORDER BY day DESC LIMIT 14",
                           (sid,)).fetchall()
    return render(request, "student/daily.html", conn, user, d=d, quiz=quiz, history=history, numeric=numeric)


@router.post("/api/daily/answer")
async def daily_answer(request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = only_student(user)
    data = await request.json()
    res = game.answer_daily_quiz(conn, sid, str(data.get("answer", ""))[:2000])
    res["notices"] = game.pop_notices(conn, sid)
    return res


def check_report(conn, sid, check, result):
    """Разбор сданной проверки; для итогового теста — ещё и «было» по темам из входного."""
    report = grade(check, json.loads(result["answers"]))
    report["result"] = result
    if result["started_at"]:
        secs = (datetime.fromisoformat(result["finished_at"]) - datetime.fromisoformat(result["started_at"])).total_seconds()
        report["minutes"] = max(1, round(secs / 60))
    base_id = check.get("compare_with")
    base = conn.execute("SELECT * FROM check_results WHERE student_id = ? AND check_id = ?",
                        (sid, base_id)).fetchone() if base_id else None
    if base:
        before = {t["topic"]: t for t in grade(CHECK_BY_ID[base_id], json.loads(base["answers"]))["topics"]}
        for t in report["topics"]:
            t["before"] = before.get(t["topic"])
        report["before_right"] = base["right_count"]
    return report


@router.get("/checks", response_class=HTMLResponse)
def checks_page(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    states, results = check_states(conn, sid)
    st = students.get_student(conn, sid)
    mine = subjects.of(st)
    return render(request, "student/checks.html", conn, user,
                  checks=[c for c in CHECKS if c["subject"] in mine and c.get("grade") in (None, st.get("grade"))],
                  states=states, results=results)


@router.get("/check/{cid}", response_class=HTMLResponse)
def check_page(cid: str, request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    check = CHECK_BY_ID.get(cid)
    if not check:
        raise HTTPException(404)
    sid = subject_id(conn, user)
    state = conn.execute("SELECT * FROM check_state WHERE student_id = ? AND id = ?", (sid, cid)).fetchone() if sid else None
    result = conn.execute("SELECT * FROM check_results WHERE student_id = ? AND check_id = ?",
                          (sid, cid)).fetchone() if sid else None
    is_open = bool(state and state["opened_at"])
    if result:
        return render(request, "student/check.html", conn, user, check=check, mode="result",
                      report=check_report(conn, sid, check, result))
    if is_teacher(user):
        return render(request, "student/check.html", conn, user, check=check, mode="preview", is_open=is_open)
    if not is_open:
        return render(request, "student/check.html", conn, user, check=check, mode="locked")
    started_at = state["started_at"]
    if not started_at:
        started_at = game.now_iso()
        with conn:
            conn.execute("UPDATE check_state SET started_at = ? WHERE student_id = ? AND id = ?", (started_at, sid, cid))
    return render(request, "student/check.html", conn, user, check=check, mode="form", started_at=started_at)


@router.post("/check/{cid}/submit")
async def check_submit(cid: str, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    check = CHECK_BY_ID.get(cid)
    if not check:
        raise HTTPException(404)
    sid = only_student(user)
    state = conn.execute("SELECT * FROM check_state WHERE student_id = ? AND id = ?", (sid, cid)).fetchone()
    if not (state and state["opened_at"]):
        raise HTTPException(400, "Проверка ещё не открыта")
    form = await request.form()
    answers = {}
    for q in check["questions"]:
        if q["skippable"] and form.get("s_" + q["id"]):
            answers[q["id"]] = SKIP
        else:
            answers[q["id"]] = str(form.get("a_" + q["id"], ""))[:2000]
    report = grade(check, answers)
    with conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO check_results (student_id, check_id, answers, right_count, total, skipped, started_at, "
            "finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, cid, json.dumps(answers, ensure_ascii=False), report["right"], report["total"], report["skipped"],
             state["started_at"], game.now_iso()))
        rewarded = conn.execute("SELECT 1 FROM xp_events WHERE student_id = ? AND kind = 'check' AND ref = ?",
                                (sid, cid)).fetchone()
        if cur.rowcount and not rewarded:
            game.award(conn, sid, game.XP_CHECK, "Проверка «%s»" % check["title"], "check", cid)
    if cur.rowcount:
        game.tell_teacher(conn, sid, "📝 %s: %d из %d%s" % (check["title"], report["right"], report["total"],
                                                          ", пропущено %d" % report["skipped"] if report["skipped"] else ""),
                          "/teacher/checks?student=%d" % sid)
    return back("/check/%s" % cid)


# ------------------------------------------------------------------ пасс сезона
@router.get("/season", response_class=HTMLResponse)
def season_page(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    return render(request, "student/season.html", conn, user, ov=season.overview(conn, sid),
                  coll=season.collection(conn, sid), st=students.get_student(conn, sid), rarities=season.RARITIES)


@router.post("/season/claim")
def season_claim(tier: int = Form(...), track: str = Form(...), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = only_student(user)
    with conn:
        msg = season.claim(conn, sid, tier, track)
        if msg is None:
            raise HTTPException(400, "Эту награду пока нельзя забрать")
        if not msg.startswith(theme.T["drop"]):          # о дропе уведомление уже есть
            game.add_notice(conn, sid, "🎁", "Награда пасса: " + msg, big=True)
    return back("/season#t%d" % tier)


@router.post("/season/equip")
def season_equip(kind: str = Form(...), value: str = Form(""), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = only_student(user)
    with conn:
        season.equip(conn, sid, kind, value)
    return back("/season#collection")


@router.get("/certificates", response_class=HTMLResponse)
def certificates_page(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    return render(request, "student/certificates.html", conn, user, certs=certificates.earned(conn, sid),
                  holder=certificates.holder_name(conn, sid), signer=cert_signer(conn))


def _certificate_response(request, conn, user, sid, kind, ref, back_url):
    cert = certificates.find(conn, sid, kind, ref)
    if not cert:
        raise HTTPException(404, "Такого сертификата пока нет")
    return render(request, "certificate.html", conn, user, sid=sid, cert=cert, holder=certificates.holder_name(conn, sid),
                  teacher_name=cert_signer(conn), year=(cert["date"] or game.now_iso())[:4], back_url=back_url)


@router.get("/certificate/{kind}/{ref}", response_class=HTMLResponse)
def certificate_page(kind: str, ref: str, request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    return _certificate_response(request, conn, user, need_sid(conn, user), kind, ref, "/certificates")


# ------------------------------------------------------------------ умножайка
@router.get("/trainer", response_class=HTMLResponse)
def trainer_page(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    runs = conn.execute("SELECT * FROM trainer_runs WHERE student_id = ? ORDER BY id DESC LIMIT 10", (sid,)).fetchall()
    return render(request, "student/trainer.html", conn, user, modes=game.TRAINER_MODES,
                  best=game.trainer_best(conn, sid), runs=runs, cap=config.TRAINER_DAILY_XP_CAP)


@router.post("/api/trainer")
async def trainer_api(request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    data = await request.json()
    if user["role"] != "student":
        return {"xp": 0, "record": False, "best": 0, "notices": []}
    sid = user["id"]
    try:
        res = game.trainer_result(conn, sid, str(data.get("mode")), data.get("correct", 0), data.get("wrong", 0))
    except (ValueError, TypeError):
        raise HTTPException(400)
    res["notices"] = game.pop_notices(conn, sid)
    return res


# ------------------------------------------------------------------ песочница
STARTERS = {
    "empty": ("Пустой файл", ""),
    "turtle": ("Черепашка", 'import turtle\nt = turtle.Turtle()\nt.speed(0)\nt.color("purple")\nfor i in range(36):\n    t.circle(80)\n    t.left(10)\n'),
    "guess": ("Угадай число", LESSON_BY_NUM[8]["examples"][0]["code"]),
    "trainer": ("Своя умножайка", LESSON_BY_NUM[8]["examples"][1]["code"]),
}


@router.get("/playground", response_class=HTMLResponse)
def playground(request: Request, s: int = 0, starter: str = "", conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    snippets = conn.execute("SELECT id, title, updated_at FROM snippets WHERE student_id = ? ORDER BY updated_at DESC",
                            (sid,)).fetchall()
    current = conn.execute("SELECT * FROM snippets WHERE id = ? AND student_id = ?", (s, sid)).fetchone() if s else None
    code = current["code"] if current else STARTERS.get(starter, STARTERS["turtle"])[1]
    return render(request, "student/playground.html", conn, user, snippets=snippets, current=current,
                  code=code, starters=STARTERS)


@router.post("/api/snippets")
async def save_snippet(request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    """Песочница ученика. Преподаватель тоже может сохранить сюда программу — например, заготовки к уроку."""
    sid = need_sid(conn, user)
    data = await request.json()
    title = (str(data.get("title") or "").strip() or "Без названия")[:80]
    code = str(data.get("code", ""))[:100_000]
    snippet_id = int(data.get("id") or 0)
    with conn:
        if snippet_id and conn.execute("SELECT 1 FROM snippets WHERE id = ? AND student_id = ?", (snippet_id, sid)).fetchone():
            conn.execute("UPDATE snippets SET title = ?, code = ?, updated_at = ? WHERE id = ?",
                         (title, code, game.now_iso(), snippet_id))
        else:
            snippet_id = conn.execute("INSERT INTO snippets (student_id, title, code, updated_at) VALUES (?, ?, ?, ?)",
                                      (sid, title, code, game.now_iso())).lastrowid
        if user["role"] == "student":
            game.sync_achievements(conn, sid)
    return {"id": snippet_id, "notices": game.pop_notices(conn, sid) if user["role"] == "student" else []}


@router.post("/snippets/{snippet_id}/delete")
def delete_snippet(snippet_id: int, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = need_sid(conn, user)
    with conn:
        conn.execute("DELETE FROM snippets WHERE id = ? AND student_id = ?", (snippet_id, sid))
    return back("/playground")


# ------------------------------------------------------------------ достижения, магазин, шпаргалка
@router.get("/achievements", response_class=HTMLResponse)
def achievements_page(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    have = game.unlocked_achievements(conn, sid)
    board = students.leaderboard(conn) if students.leaderboard_enabled(conn) else []
    return render(request, "student/achievements.html", conn, user, achievements=game.ACHIEVEMENTS, have=have,
                  levels=game.LEVELS, brawlers=game.BRAWLERS, hero_need=game.HERO_NEED, ru_heroes=game.RU_HEROES,
                  board=board if len(board) > 1 else [])


@router.get("/shop", response_class=HTMLResponse)
def shop(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    sid = need_sid(conn, user)
    rewards = conn.execute("SELECT * FROM rewards WHERE active = 1 ORDER BY cost").fetchall()
    purchases = conn.execute("SELECT * FROM purchases WHERE student_id = ? ORDER BY id DESC LIMIT 20", (sid,)).fetchall()
    return render(request, "student/shop.html", conn, user, rewards=rewards, purchases=purchases)


@router.post("/shop/{rid}/buy")
def buy(rid: int, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    if user["role"] != "student":
        return back("/shop")
    sid = user["id"]
    reward = conn.execute("SELECT * FROM rewards WHERE id = ? AND active = 1", (rid,)).fetchone()
    if not reward:
        raise HTTPException(404)
    with conn:
        if game.coins(conn, sid) < reward["cost"]:
            game.add_notice(conn, sid, "🪙", "Пока не хватает гемов на «%s»" % reward["title"])
            return back("/shop")
        conn.execute("INSERT INTO purchases (student_id, reward_id, title, cost, created_at) VALUES (?, ?, ?, ?, ?)",
                     (sid, rid, reward["title"], reward["cost"], game.now_iso()))
        game.add_notice(conn, sid, reward["emoji"], "Запрос на «%s» отправлен преподавателю!" % reward["title"])
    game.tell_teacher(conn, sid, "🛍️ Запрошена награда: %s %s (%d 💎)" % (reward["emoji"], reward["title"], reward["cost"]),
                      "/teacher/rewards")
    return back("/shop")


@router.get("/cheatsheet", response_class=HTMLResponse)
def cheatsheet(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    upto = 999 if is_teacher(user) else game.unlocked_upto(conn, user["id"])
    sections = [s for s in CHEATSHEET if s["lesson"] <= upto]
    locked = len(CHEATSHEET) - len(sections)
    return render(request, "student/cheatsheet.html", conn, user, sections=sections, locked=locked)
