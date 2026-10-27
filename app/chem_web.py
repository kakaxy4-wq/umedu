"""Страницы экземпляра по химии (CQ_SUBJECTS=chemistry): регистрация по приглашению, кабинет ученика,
кабинет преподавателя (расписание, посещаемость, оплата, ДЗ). Подключается в конце main.py.
"""
import csv
import io
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from . import auth, chem, config, game, students
from .db import get_db, get_setting, set_setting
from .main import FILE_EXT, IMAGE_EXT, back, need_sid, only_student, render, save_upload, target_student, upload_path

router = APIRouter()
HW_EXT = IMAGE_EXT | {".pdf", ".heic", ".docx", ".txt"}


def _site_only():
    if not config.CHEM_SITE:
        raise HTTPException(404)


def _int(value, default=0, lo=-10**9, hi=10**9):
    """Целое из формы: пробелы (и неразрывные) между разрядами допустимы; вне [lo, hi] — default."""
    try:
        v = int(str(value).strip().replace(" ", "").replace("\u00a0", "").replace("\u202f", ""))
    except (TypeError, ValueError):
        return default
    return v if lo <= v <= hi else default


def _date(value):
    """Дата ГГГГ-ММ-ДД из формы или None."""
    value = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(value).isoformat() if value else None
    except ValueError:
        raise HTTPException(400, "Не понял дату")


def _month(value):
    value = str(value or "")
    try:
        d = date.fromisoformat(value + "-01")
        if 2000 <= d.year <= 2100:
            return value
    except ValueError:
        pass
    return config.today().strftime("%Y-%m")


async def _json(request):
    """Тело запроса — JSON-объект, иначе 400."""
    try:
        data = await request.json()
    except ValueError:
        raise HTTPException(400)
    if not isinstance(data, dict):
        raise HTTPException(400)
    return data


def _csv_cell(v):
    """Ячейка CSV без формул Excel (=, +, -, @ в начале)."""
    v = "" if v is None else v
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


# ------------------------------------------------------------------ ученик
@router.get("/chem", response_class=HTMLResponse)
def chem_home(request: Request, welcome: int = 0, conn=Depends(get_db), user=Depends(auth.current_user)):
    _site_only()
    if user["role"] == "teacher":
        return back("/chem/teacher")
    sid = user["id"]
    card = chem.student_card(conn, sid)
    hw = chem.hw_list(conn, sid)
    from .main import check_states
    states, results = check_states(conn, sid)
    entry_id = "chem%d_entry" % (card["student"]["grade"] or 9)
    return render(request, "chem/home.html", conn, user, card=card, hw=hw[:6], welcome=welcome,
                  entry_id=entry_id, entry_done=entry_id in results, grades=chem.GRADES,
                  upcoming=chem.lessons(conn, sid, since=config.now().isoformat(timespec="minutes")[:16], limit=5),
                  sheets=conn.execute("SELECT f.*, l.starts_at, l.topic FROM chem_lesson_files f JOIN chem_lessons l "
                                      "ON l.id = f.lesson_id WHERE f.student_id = ? ORDER BY l.starts_at DESC, f.id LIMIT 12",
                                      (sid,)).fetchall())


@router.get("/chem/hw", response_class=HTMLResponse)
def chem_hw_list(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    _site_only()
    sid = need_sid(conn, user)
    return render(request, "chem/hw_list.html", conn, user, hw=chem.hw_list(conn, sid))


@router.get("/chem/hw/{hw_id}", response_class=HTMLResponse)
def chem_hw_page(hw_id: int, request: Request, err: str = "", conn=Depends(get_db), user=Depends(auth.current_user)):
    _site_only()
    hw = chem.hw_get(conn, hw_id)
    if not hw or (user["role"] != "teacher" and hw["student_id"] != user["id"]):
        raise HTTPException(404)
    return render(request, "chem/hw.html", conn, user, hw=hw, sid=hw["student_id"], tasks=chem.hw_tasks(conn, hw), err=err,
                  files=chem.hw_files(conn, hw_id))


@router.post("/chem/hw/{hw_id}/submit")
async def chem_hw_submit(hw_id: int, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _site_only()
    sid = only_student(user)
    hw = chem.hw_get(conn, hw_id)
    if not hw or hw["student_id"] != sid or hw["status"] == "checked":
        raise HTTPException(404)
    form = await request.form()
    answer = str(form.get("answer") or "")
    uploads = [u for u in form.getlist("files") + form.getlist("file") if getattr(u, "filename", "")]
    had_files = bool(hw["file_path"]) or bool(chem.hw_files(conn, hw_id)["student"])
    if not answer.strip() and not uploads and not had_files and hw["task_ids"] in ("", "[]"):
        return back("/chem/hw/%d?err=empty" % hw_id)
    saved = [await save_upload(u, HW_EXT) for u in uploads]
    with conn:
        for original, stored in saved:
            chem.hw_add_file(conn, hw_id, "student", original, stored)
        chem.hw_submit(conn, hw_id, answer)
    return back("/chem/hw/%d" % hw_id)


@router.post("/chem/hw-file/{file_id}/delete")
def chem_hw_file_delete(file_id: int, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    """Ученик убирает своё фото, приложенное по ошибке, пока ДЗ не проверено."""
    sid = only_student(user)
    row = conn.execute("SELECT f.*, h.student_id, h.status FROM chem_hw_files f JOIN chem_hw h ON h.id = f.hw_id "
                       "WHERE f.id = ?", (file_id,)).fetchone()
    if not row or row["student_id"] != sid or row["author"] != "student" or row["status"] == "checked":
        raise HTTPException(404)
    with conn:
        conn.execute("DELETE FROM chem_hw_files WHERE id = ?", (file_id,))
    try:
        upload_path(row["file_path"]).unlink()
    except (HTTPException, OSError):
        pass
    return back("/chem/hw/%d" % row["hw_id"])


@router.get("/chem/me", response_class=HTMLResponse)
def chem_me(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    _site_only()
    only_student(user)
    return render(request, "chem/me.html", conn, user, st=students.get_student(conn, user["id"]),
                  done=request.query_params.get("ok"), err=request.query_params.get("err"))


@router.post("/chem/me/password")
def chem_me_password(old: str = Form(""), new: str = Form(""), new2: str = Form(""), conn=Depends(get_db),
                     user=Depends(auth.check_csrf)):
    sid = only_student(user)
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (sid,)).fetchone()
    if not auth.verify_password(old, row["password_hash"]):
        return back("/chem/me?err=old")
    if len(new) < 6 or len(new) > 100:
        return back("/chem/me?err=short")
    if new != new2:
        return back("/chem/me?err=same")
    with conn:
        students.set_password(conn, sid, new)
    return back("/chem/me?ok=1")


@router.get("/chem/hw-file/{file_id}")
def chem_hw_file2(file_id: int, conn=Depends(get_db), user=Depends(auth.current_user)):
    row = conn.execute("SELECT f.*, h.student_id FROM chem_hw_files f JOIN chem_hw h ON h.id = f.hw_id WHERE f.id = ?",
                       (file_id,)).fetchone()
    if not row or (user["role"] != "teacher" and row["student_id"] != user["id"]):
        raise HTTPException(404)
    return FileResponse(upload_path(row["file_path"]), filename=row["file_name"])


@router.get("/chem/hw/{hw_id}/file")
def chem_hw_file(hw_id: int, conn=Depends(get_db), user=Depends(auth.current_user)):
    hw = chem.hw_get(conn, hw_id)
    if not hw or not hw["file_path"] or (user["role"] != "teacher" and hw["student_id"] != user["id"]):
        raise HTTPException(404)
    return FileResponse(upload_path(hw["file_path"]), filename=hw["file_name"])


# ------------------------------------------------------------------ преподаватель: пульт и расписание
def _topics_all():
    from .content.chem_topics import TOPIC_BY_ID
    return list(TOPIC_BY_ID.values())


def _teacher(user):
    if user["role"] != "teacher":
        raise HTTPException(403)


@router.get("/chem/teacher", response_class=HTMLResponse)
def chem_teacher_home(request: Request, demo: int = 0, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    _site_only()
    today = config.today()
    since, _ = chem.day_bounds(today)
    week = chem.lessons(conn, since=since, until=(today + timedelta(days=7)).isoformat())
    overdue = conn.execute("SELECT l.*, u.display_name AS who FROM chem_lessons l JOIN users u ON u.id = l.student_id "
                           "WHERE l.status = 'planned' AND u.active = 1 AND l.starts_at < ? ORDER BY l.starts_at",
                           (config.now().isoformat(timespec="minutes")[:16],)).fetchall()
    late = {r["id"] for r in overdue}
    week = [r for r in week if r["id"] not in late]
    roster = [chem.student_card(conn, s["id"]) for s in students.list_students(conn)]
    return render(request, "chem/teacher_home.html", conn, user, week=week, overdue=overdue, today=today.isoformat(),
                  debtors=chem.debtors(conn), hw_wait=chem.hw_list(conn, status="submitted"), roster=roster,
                  invite=chem.invite_code(conn), base_url=config.BASE_URL or str(request.base_url).rstrip("/"),
                  statuses=chem.STATUSES, grades=chem.GRADES, demo=demo, files=chem.lesson_files(conn),
                  topics_all=_topics_all(),
                  demo_exists=bool(conn.execute("SELECT 1 FROM users WHERE username = ?", (chem.DEMO_LOGIN,)).fetchone()))


@router.post("/chem/teacher/invite")
def chem_invite_new(conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _teacher(user)
    with conn:
        chem.new_invite_code(conn)
    return back("/chem/teacher#invite")


@router.post("/chem/teacher/lessons")
def chem_lessons_add(student_id: int = Form(...), day: str = Form(...), time: str = Form(...), price: str = Form(""),
                     minutes: int = Form(60), weeks: int = Form(1), topic: str = Form(""), next: str = Form(""),
                     conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _teacher(user)
    st = students.get_student(conn, student_id)
    if not st:
        raise HTTPException(404)
    try:
        starts = datetime.fromisoformat("%s %s" % (day, time)).isoformat(timespec="minutes")
    except ValueError:
        raise HTTPException(400, "Не понял дату или время")
    price_val = _int(price, st["price"] or 0, 0, 1_000_000) if price.strip() else (st["price"] or 0)
    if not 15 <= minutes <= 300:
        raise HTTPException(400, "Длительность занятия — от 15 до 300 минут")
    with conn:
        chem.add_lessons(conn, student_id, starts, price_val, minutes, weeks, topic.strip()[:200])
    return back(next if next.startswith("/chem/") else "/chem/teacher")


@router.post("/chem/teacher/lesson/{lesson_id}")
def chem_lesson_set(lesson_id: int, status: str = Form(...), charged: str = Form(""), topic: str = Form(None),
                    next: str = Form(""), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _teacher(user)
    with conn:
        if status == "delete":
            conn.execute("DELETE FROM chem_lessons WHERE id = ? AND status = 'planned'", (lesson_id,))
        elif status == "delete_series":
            chem.delete_series(conn, lesson_id)
        elif not chem.set_lesson(conn, lesson_id, status, charged=(bool(charged) if status == "missed" else None),
                                 topic=topic.strip()[:200] if topic is not None else None):
            raise HTTPException(400, "Будущее занятие нельзя отметить проведённым или пропущенным")
    return back(next if next.startswith("/chem/") else "/chem/teacher")


@router.get("/chem/teacher/lesson/{lesson_id}/plan", response_class=HTMLResponse)
def chem_lesson_plan(lesson_id: int, request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    _site_only()
    lesson = conn.execute("SELECT * FROM chem_lessons WHERE id = ?", (lesson_id,)).fetchone()
    if not lesson:
        raise HTTPException(404)
    sid = lesson["student_id"]
    st = students.get_student(conn, sid)
    plan = chem.lesson_plan(conn, lesson_id)
    covered = chem.covered_topics(conn, sid, exclude=lesson_id)   # пройдено на других занятиях
    topics = chem_topics.for_grade(st["grade"])
    fresh = [t for t in topics if t["title"] not in covered]
    done = [t for t in topics if t["title"] in covered]
    return render(request, "chem/lesson_plan.html", conn, user, lesson=lesson, st=st, plan=plan, fresh=fresh, done=done,
                  covered=covered, elsewhere=chem.other_plans(conn, sid, lesson_id), statuses=chem.STATUSES,
                  topic_by_id=chem_topics.TOPIC_BY_ID, tasks=chem.plan_tasks(conn, sid, plan["topic_ids"]),
                  history=[h for h in chem.lessons(conn, sid, until=lesson["starts_at"], limit=30) if h["status"] == "done"],
                  saved=request.query_params.get("saved"), hw_given=request.query_params.get("hw"))


@router.post("/chem/teacher/lesson/{lesson_id}/plan")
async def chem_lesson_plan_save(lesson_id: int, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _teacher(user)
    lesson = conn.execute("SELECT * FROM chem_lessons WHERE id = ?", (lesson_id,)).fetchone()
    if not lesson:
        raise HTTPException(404)
    form = await request.form()
    topic_ids = [t for t in form.getlist("topics") if t in chem_topics.TOPIC_BY_ID]
    text = str(form.get("plan") or "").replace("\r\n", "\n").strip()[:8000]
    if form.get("action") == "draft":
        text = chem.draft_plan(conn, lesson["student_id"], topic_ids, lesson["minutes"])
    with conn:
        chem.save_lesson_plan(conn, lesson_id, topic_ids, text)
    return back("/chem/teacher/lesson/%d/plan?saved=1" % lesson_id)


@router.get("/chem/teacher/schedule", response_class=HTMLResponse)
def chem_schedule(request: Request, start: str = "", conn=Depends(get_db), user=Depends(auth.teacher_required)):
    _site_only()
    try:
        first = date.fromisoformat(start) if start else config.today()
    except ValueError:
        first = config.today()
    if not 2000 <= first.year <= 2100:
        first = config.today()
    first = first - timedelta(days=first.weekday())
    days = [first + timedelta(days=i) for i in range(7)]
    rows = chem.lessons(conn, since=first.isoformat(), until=(first + timedelta(days=7)).isoformat())
    by_day = {d.isoformat(): [r for r in rows if r["starts_at"][:10] == d.isoformat()] for d in days}
    return render(request, "chem/schedule.html", conn, user, days=days, by_day=by_day, statuses=chem.STATUSES,
                  prev=(first - timedelta(days=7)).isoformat(), nxt=(first + timedelta(days=7)).isoformat(),
                  all_st=students.list_students(conn), today=config.today().isoformat(),
                  files=chem.lesson_files(conn), topics_all=_topics_all())


# ------------------------------------------------------------------ преподаватель: ученик
@router.get("/chem/teacher/student/{sid}", response_class=HTMLResponse)
def chem_student(sid: int, request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    _site_only()
    st = students.get_student(conn, sid)
    if not st:
        raise HTTPException(404)
    from .main import check_states, select_student
    select_student(conn, user, sid)
    states, results = check_states(conn, sid)
    parent_url = ((config.BASE_URL or str(request.base_url).rstrip("/")) + "/parent/" + st["parent_token"]) \
        if st["parent_token"] else ""
    return render(request, "chem/teacher_student.html", conn, user, sid=sid, st=st, card=chem.student_card(conn, sid),
                  lessons=chem.lessons(conn, sid, since=config.now().isoformat(timespec="minutes")[:16], limit=40),
                  history=chem.lessons(conn, sid, until=config.now().isoformat(timespec="minutes")[:16], limit=60),
                  pays=chem.payments(conn, sid), hw=chem.hw_list(conn, sid),
                  statuses=chem.STATUSES, grades=chem.GRADES, parent_url=parent_url, results=results,
                  today=config.today().isoformat(), files=chem.lesson_files(conn, sid),
                  topics_all=chem_topics.for_grade(st["grade"]), covered=chem.covered_topics(conn, sid),
                  textbooks=chem.TEXTBOOKS, last_textbook=get_setting(conn, "last_textbook", ""), hwerr=request.query_params.get("hwerr"),
                  mocks=chem_mock.list_for(conn, sid))


@router.post("/chem/teacher/student/{sid}/settings")
def chem_student_settings(sid: int, name: str = Form(""), grade: int = Form(0), price: str = Form("0"),
                          notes: str = Form(""), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, sid)
    with conn:
        if name.strip():
            conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (name.strip()[:40], sid))
        if grade in chem.GRADES:
            conn.execute("UPDATE users SET grade = ? WHERE id = ?", (grade, sid))
        conn.execute("UPDATE users SET price = ?, notes = ? WHERE id = ?", (_int(price, 0, 0, 1_000_000), notes[:2000], sid))
    return back("/chem/teacher/student/%d" % sid)


@router.post("/chem/teacher/student/{sid}/payment")
def chem_payment_add(sid: int, amount: str = Form(...), paid_at: str = Form(""), note: str = Form(""),
                     conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, sid)
    value = _int(amount, 0, 0, 10_000_000)
    if value <= 0:
        raise HTTPException(400, "Сумма — положительное число рублей")
    with conn:
        chem.add_payment(conn, sid, value, _date(paid_at), note[:200])
    return back("/chem/teacher/student/%d#money" % sid)


@router.post("/chem/teacher/payment/{pay_id}/delete")
def chem_payment_delete(pay_id: int, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _teacher(user)
    row = conn.execute("SELECT student_id FROM chem_payments WHERE id = ?", (pay_id,)).fetchone()
    if not row:
        raise HTTPException(404)
    with conn:
        conn.execute("DELETE FROM chem_payments WHERE id = ?", (pay_id,))
    return back("/chem/teacher/student/%d#money" % row["student_id"])


@router.post("/chem/teacher/student/{sid}/hw")
async def chem_hw_give(sid: int, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, sid)
    form = await request.form()
    f = lambda k: str(form.get(k) or "").strip()  # noqa: E731
    kind = f("kind") or "text"
    text = f("text")
    title = f("title")
    if kind == "book":
        text = chem.book_text(f("book"), f("paragraph"), f("pages"), f("exercises"), text)
        title = title or ("Учебник: " + f("paragraph") if f("paragraph") else "Учебник")
        if f("book"):
            with conn:
                set_setting(conn, "last_textbook", f("book"))
    uploads = [u for u in form.getlist("files") if getattr(u, "filename", "")]
    if not title and not text and not uploads:
        return back("/chem/teacher/student/%d?hwerr=empty#hw" % sid)
    saved = [await save_upload(u, HW_EXT) for u in uploads]
    with conn:
        hw_id = chem.hw_give(conn, sid, title or "Домашнее задание", text, _date(f("due_at")),
                             max_score=_int(f("max_score"), None, 1, 1000) if f("max_score") else None)
        for original, stored in saved:
            chem.hw_add_file(conn, hw_id, "teacher", original, stored)
    return back("/chem/teacher/student/%d#hw" % sid)


@router.get("/chem/teacher/hw", response_class=HTMLResponse)
def chem_teacher_hw(request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    _site_only()
    wait = chem.hw_list(conn, status="submitted")
    auto = {}
    for h in wait:
        ts = chem.hw_tasks(conn, h)
        if ts:
            auto[h["id"]] = (sum(x["best"] or 0 for x in ts), sum(x["points"] for x in ts), len(ts),
                             len([x for x in ts if x["best"] and x["best"] >= x["points"]]))
    return render(request, "chem/teacher_hw.html", conn, user, wait=wait, auto=auto,
                  files={h["id"]: chem.hw_files(conn, h["id"]) for h in wait},
                  given=chem.hw_list(conn, status="given"))


@router.post("/chem/teacher/hw/{hw_id}/check")
def chem_hw_check(hw_id: int, score: str = Form(""), max_score: str = Form(""), comment: str = Form(""),
                  action: str = Form("accept"), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _teacher(user)
    hw = chem.hw_get(conn, hw_id)
    if not hw:
        raise HTTPException(404)
    mx = _int(max_score, None, 1, 1000) if max_score.strip() else hw["max_score"]
    sc = _int(score, None, 0, mx or 1000) if score.strip() else None
    if score.strip() and sc is None:
        raise HTTPException(400, "Оценка — число от 0 до %d" % (mx or 1000))
    with conn:
        chem.hw_check(conn, hw_id, sc, mx, comment.strip(),
                      returned=action == "return")
    return back("/chem/teacher/hw")


# ------------------------------------------------------------------ деньги: отчёт и выгрузка
def _money_rows(conn, month):
    return conn.execute("SELECT p.*, u.display_name AS who FROM chem_payments p JOIN users u ON u.id = p.student_id "
                        "WHERE substr(p.paid_at, 1, 7) = ? ORDER BY p.paid_at, p.id", (month,)).fetchall()


@router.get("/chem/teacher/money", response_class=HTMLResponse)
def chem_money(request: Request, month: str = "", conn=Depends(get_db), user=Depends(auth.teacher_required)):
    _site_only()
    month = _month(month)
    rows = _money_rows(conn, month)
    done = conn.execute("SELECT COUNT(*), COALESCE(SUM(price), 0) FROM chem_lessons WHERE substr(starts_at, 1, 7) = ? "
                        "AND (status = 'done' OR (status = 'missed' AND charged = 1))", (month,)).fetchone()
    first = date.fromisoformat(month + "-01")
    prev = (first - timedelta(days=1)).strftime("%Y-%m")
    nxt = (first + timedelta(days=32)).strftime("%Y-%m")
    return render(request, "chem/money.html", conn, user, rows=rows, month=month, total=sum(r["amount"] for r in rows),
                  lessons_n=done[0], lessons_sum=done[1], prev=prev, nxt=nxt, debtors=chem.debtors(conn))


@router.get("/chem/teacher/money.csv")
def chem_money_csv(month: str = "", conn=Depends(get_db), user=Depends(auth.teacher_required)):
    month = _month(month)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Дата", "Ученик", "Сумма, ₽", "Комментарий"])
    for r in _money_rows(conn, month):
        w.writerow([_csv_cell(r["paid_at"]), _csv_cell(r["who"]), r["amount"], _csv_cell(r["note"])])
    data = "﻿" + buf.getvalue()               # BOM — чтобы Excel открыл кириллицу
    return Response(data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="oplaty-%s.csv"' % month})


# ------------------------------------------------------------------ карта экзамена и задачи
from .content import chem_exam, chem_gen  # noqa: E402
from .content.chem_tasks import TASK_BY_ID as CHEM_TASKS, TASKS as CHEM_TASK_LIST, for_number, grade_answer  # noqa: E402

XP_PER_POINT = 5


def get_task(task_id):
    """Задача банка или сгенерированный вариант (g-o18-123)."""
    return CHEM_TASKS.get(task_id) or chem_gen.task(task_id)


def best_points(conn, sid):
    """task_id → лучший балл ученика."""
    return {r[0]: r[1] for r in conn.execute(
        "SELECT task_id, MAX(points) FROM chem_attempts WHERE student_id = ? GROUP BY task_id", (sid,))}


def _num_of(task_id):
    t = CHEM_TASKS.get(task_id)
    if t:
        return t["exam"], t["num"]
    m = chem_gen._ID.match(task_id)
    return (("oge" if m.group(1) == "o" else "ege"), int(m.group(2))) if m else (None, None)


def exam_progress(conn, sid, exam):
    """По каждому номеру: задачи банка, варианты, сколько решено, и прогноз баллов части с кратким ответом.
    Ученику не показываются задачи и генераторы, к которым у преподавателя есть замечание."""
    from .chem_review import hidden
    hb, hg = hidden(conn) if sid else (set(), set())
    best = best_points(conn, sid) if sid else {}
    last = {r[0]: r[1] for r in conn.execute("SELECT task_id, MAX(created_at) FROM chem_attempts WHERE student_id = ? "
                                             "GROUP BY task_id", (sid,))} if sid else {}
    by_num = {}
    for tid, pts_got in best.items():
        ex_, num = _num_of(tid)
        if ex_ == exam:
            by_num.setdefault(num, []).append((tid, pts_got))
    ex = chem_exam.EXAMS[exam]
    rows, forecast, short_max = [], 0.0, 0
    for num, (title, pts) in ex["numbers"].items():
        tasks = [x for x in for_number(exam, num) if x["id"] not in hb]
        long = num in ex["long"]
        tried = by_num.get(num, [])
        recent = sorted(tried, key=lambda x: last.get(x[0], ""))[-8:]   # 8 последних по времени: и банк, и варианты
        share = (sum(p for _, p in recent) / (pts * len(recent))) if recent and not long else 0
        if not long:
            short_max += pts
            forecast += share * pts
        rows.append({"num": num, "title": title, "points": pts, "long": long, "tasks": tasks,
                     "solved": sum(1 for _, p in tried if p >= pts), "tried": len(tried), "share": round(share * 100),
                     "best": best, "gen": chem_gen.has_generator(exam, num) and (exam, num) not in hg})
    return {"exam": exam, "ex": ex, "rows": rows, "forecast": round(forecast, 1), "short_max": short_max}


@router.get("/chem/map", response_class=HTMLResponse)
def chem_map(request: Request, exam: str = "", conn=Depends(get_db), user=Depends(auth.current_user)):
    _site_only()
    if user["role"] == "teacher":
        exam = exam if exam in chem_exam.EXAMS else "oge"
        sid = None
    else:
        sid = user["id"]
        exam = chem_exam.exam_for_grade(students.get_student(conn, sid)["grade"])
    return render(request, "chem/map.html", conn, user, pr=exam_progress(conn, sid, exam), exams=chem_exam.EXAMS,
                  total=len(CHEM_TASK_LIST), generators=len([k for k in chem_gen.GENERATORS if k[0] == exam]))


@router.get("/chem/variant")
def chem_variant(exam: str, num: int, conn=Depends(get_db), user=Depends(auth.current_user)):
    """Новый вариант номера — редирект на страницу задачи-варианта."""
    if not chem_gen.has_generator(exam, num) or (user["role"] == "student" and not chem_review.generator_on(conn, exam, num)):
        raise HTTPException(404)
    return back("/chem/task/" + chem_gen.new_id(exam, num))


@router.get("/chem/task/{task_id}", response_class=HTMLResponse)
def chem_task(task_id: str, request: Request, hw: int = 0, conn=Depends(get_db), user=Depends(auth.current_user)):
    _site_only()
    task = get_task(task_id)
    if not task:
        raise HTTPException(404)
    if user["role"] == "student" and _hidden_for_student(conn, task):
        raise HTTPException(404)
    ex = chem_exam.EXAMS[task["exam"]]
    best = best_points(conn, user["id"]).get(task_id) if user["role"] == "student" else None
    nxt = None
    if not task.get("generated"):
        siblings = for_number(task["exam"], task["num"])
        idx = [x["id"] for x in siblings].index(task_id)
        nxt = siblings[idx + 1] if idx + 1 < len(siblings) else None
        if not nxt:
            later = [x for x in CHEM_TASK_LIST if x["exam"] == task["exam"] and x["num"] > task["num"]]
            nxt = min(later, key=lambda x: x["num"]) if later else None    # ближайший следующий номер
    title, pts = ex["numbers"][task["num"]]
    public = {k: task[k] for k in ("id", "exam", "num", "text", "mode")}
    return render(request, "chem/task.html", conn, user, task=public, ex=ex, title=title, pts=pts, best=best,
                  next_task=nxt, generated=bool(task.get("generated")), has_gen=chem_gen.has_generator(task["exam"], task["num"]),
                  show_answer=user["role"] == "teacher" or (best is not None and best >= pts),
                  answer=task["answer"], why=task["why"], hw_id=hw)


def _hidden_for_student(conn, task):
    """Задача банка или генератор с замечанием преподавателя — ученику недоступны."""
    hb, hg = chem_review.hidden(conn)
    return task["id"] in hb or (task.get("generated") and (task["exam"], task["num"]) in hg)


@router.post("/api/chem/task/{task_id}")
async def chem_task_answer(task_id: str, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    task = get_task(task_id)
    if not task or task["mode"] == "long":
        raise HTTPException(404)
    if user["role"] == "student" and _hidden_for_student(conn, task):
        raise HTTPException(404)
    data = await _json(request)
    given = str(data.get("answer", ""))[:40]
    hw_id = _int(data.get("hw"), None, 1) if user["role"] == "student" else None
    if hw_id and not conn.execute("SELECT 1 FROM chem_hw WHERE id = ? AND student_id = ?", (hw_id, user["id"])).fetchone():
        hw_id = None
    pts = chem_exam.points(task["exam"], task["num"])
    got = grade_answer(task, given)
    result = {"points": got, "max": pts, "notices": []}
    if user["role"] == "student":
        sid = user["id"]
        before = best_points(conn, sid).get(task_id, -1)
        tries = conn.execute("SELECT COUNT(*) FROM chem_attempts WHERE student_id = ? AND task_id = ?",
                             (sid, task_id)).fetchone()[0]
        # ответ показан после 3 неверных попыток — дальнейшие ответы в зачёт (прогноз, ДЗ, опыт) не идут
        shown = before < pts and tries >= 3
        counted = 0 if shown else got
        with conn:
            conn.execute("INSERT INTO chem_attempts (student_id, task_id, answer, points, max_points, hw_id, created_at) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)", (sid, task_id, given, counted, pts, hw_id, game.now_iso()))
            if counted == pts and before < pts:
                game.award(conn, sid, XP_PER_POINT * pts, "Задача %s №%d" % (chem_exam.EXAMS[task["exam"]]["title"],
                                                                             task["num"]), "chem", task_id)
        result["notices"] = game.pop_notices(conn, sid)
        result["after_reveal"] = shown
        reveal = got == pts or tries + 1 >= 3
    else:
        reveal = True
    if reveal:
        result.update({"answer": task["answer"], "why": task["why"]})
    return result


@router.get("/api/chem/task/{task_id}/sample")
def chem_task_sample(task_id: str, conn=Depends(get_db), user=Depends(auth.current_user)):
    task = get_task(task_id)
    if not task or task["mode"] != "long" or (user["role"] == "student" and _hidden_for_student(conn, task)):
        raise HTTPException(404)
    return {"why": task["why"]}


# ------------------------------------------------------------------ таблица Менделеева
@router.get("/chem/table", response_class=HTMLResponse)
def chem_table(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    _site_only()
    from .content.elements import CATEGORIES, CATEGORY_HINTS, ELEMENTS, STATE_HINTS
    return render(request, "chem/table.html", conn, user, elements=ELEMENTS, categories=CATEGORIES,
                  category_hints=CATEGORY_HINTS, state_hints=STATE_HINTS)


@router.post("/chem/teacher/demo")
def chem_demo_student(grade: int = Form(9), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _teacher(user)
    with conn:
        chem.demo_student(conn, grade)
    return back("/chem/teacher?demo=1#demo")


# ------------------------------------------------------------------ ДЗ по теме и листочки с занятий
from .content import chem_topics  # noqa: E402

PHOTO_EXT = IMAGE_EXT | {".pdf", ".heic"}


@router.post("/chem/teacher/student/{sid}/hw-topic")
def chem_hw_topic(sid: int, topic: str = Form(...), due_at: str = Form(""), next: str = Form(""), conn=Depends(get_db),
                  user=Depends(auth.check_csrf)):
    sid = target_student(conn, user, sid)
    t = chem_topics.TOPIC_BY_ID.get(topic)
    if not t:
        raise HTTPException(404)
    with conn:
        hw_id = chem.hw_from_topic(conn, sid, t, _date(due_at))
    if not hw_id:
        raise HTTPException(400, "Для этой темы в банке пока нет задач — задай ДЗ текстом")
    return back(next + ("&" if "?" in next else "?") + "hw=%d" % hw_id if next.startswith("/chem/teacher/lesson/")
                else "/chem/teacher/student/%d#hw" % sid)


@router.post("/chem/teacher/lesson/{lesson_id}/file")
async def chem_lesson_file_add(lesson_id: int, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _teacher(user)
    lesson = conn.execute("SELECT * FROM chem_lessons WHERE id = ?", (lesson_id,)).fetchone()
    if not lesson:
        raise HTTPException(404)
    form = await request.form()
    nxt = str(form.get("next") or "")
    saved = 0
    for upload in form.getlist("files"):
        if not getattr(upload, "filename", ""):
            continue
        original, stored = await save_upload(upload, PHOTO_EXT)
        with conn:
            conn.execute("INSERT INTO chem_lesson_files (lesson_id, student_id, file_name, file_path, created_at) "
                         "VALUES (?, ?, ?, ?, ?)", (lesson_id, lesson["student_id"], original, stored, game.now_iso()))
        saved += 1
    if saved:
        with conn:
            game.add_notice(conn, lesson["student_id"], "📷", "Добавлен листочек с занятия %s.%s"
                            % (lesson["starts_at"][8:10], lesson["starts_at"][5:7]))
    return back(nxt if nxt.startswith("/chem/") else "/chem/teacher/student/%d#lessons" % lesson["student_id"])


@router.post("/chem/teacher/lesson-file/{file_id}/delete")
def chem_lesson_file_delete(file_id: int, next: str = Form(""), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _teacher(user)
    row = conn.execute("SELECT * FROM chem_lesson_files WHERE id = ?", (file_id,)).fetchone()
    if not row:
        raise HTTPException(404)
    with conn:
        conn.execute("DELETE FROM chem_lesson_files WHERE id = ?", (file_id,))
    return back(next if next.startswith("/chem/") else "/chem/teacher/student/%d#lessons" % row["student_id"])


@router.get("/chem/lesson-file/{file_id}")
def chem_lesson_file(file_id: int, conn=Depends(get_db), user=Depends(auth.current_user)):
    row = conn.execute("SELECT * FROM chem_lesson_files WHERE id = ?", (file_id,)).fetchone()
    if not row or (user["role"] != "teacher" and row["student_id"] != user["id"]):
        raise HTTPException(404)
    return FileResponse(upload_path(row["file_path"]), filename=row["file_name"])


@router.get("/parent/{token}/lesson-file/{file_id}")
def chem_parent_lesson_file(token: str, file_id: int, conn=Depends(get_db)):
    st = students.by_parent_token(conn, token)
    row = conn.execute("SELECT * FROM chem_lesson_files WHERE id = ?", (file_id,)).fetchone()
    if not st or not row or row["student_id"] != st["id"]:
        raise HTTPException(404)
    return FileResponse(upload_path(row["file_path"]), filename=row["file_name"])



# ------------------------------------------------------------------ лаборатория
LAB_MODULES = [
    {"id": "atom", "emoji": "⚛️", "title": "Атом изнутри", "ready": True, "nums": "ОГЭ 2–3 · ЕГЭ 1–3",
     "about": "3D-модель атома, электронно-графическая формула со спинами, возбуждённое состояние, ионы, игра «Собери атом»."},
    {"id": "molecules", "emoji": "🧬", "title": "Молекулы и решётки 3D", "ready": False, "nums": "ОГЭ 5 · ЕГЭ 4, 11",
     "about": "Крутить молекулы, гибридизация, σ- и π-связи, полярность, кристаллические решётки."},
    {"id": "atlas", "emoji": "🧪", "title": "Атлас качественных реакций", "ready": False, "nums": "ОГЭ 17 · ЕГЭ 6, 24",
     "about": "Таблица растворимости с настоящими цветами осадков, ионные уравнения, режим «детектив»."},
    {"id": "video", "emoji": "🎬", "title": "Эффектные опыты", "ready": True, "nums": "ОГЭ 12, 17, 23 · ЕГЭ 24",
     "about": "Видео опытов с уравнениями, признаками и вопросом «что наблюдаем?»."},
    {"id": "sim", "emoji": "🎛️", "title": "Симуляции частиц", "ready": False, "nums": "ЕГЭ 18, 20, 22, 23",
     "about": "Скорость реакции, равновесие и принцип Ле Шателье, электролиз — ползунками."},
]
LAB_XP = 5
LAB_DAILY = 5


@router.get("/chem/lab", response_class=HTMLResponse)
def chem_lab(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    _site_only()
    return render(request, "chem/lab.html", conn, user, modules=LAB_MODULES)


@router.get("/chem/lab/atom", response_class=HTMLResponse)
def chem_lab_atom(request: Request, z: int = 6, conn=Depends(get_db), user=Depends(auth.current_user)):
    _site_only()
    from .content.elements import ELEMENTS
    data = [{"z": e["z"], "sym": e["sym"], "name": e["name"], "mass": e["mass"], "period": e["period"],
             "main": e["group"] in (1, 2) or e["group"] >= 13} for e in ELEMENTS if e["z"] <= 54]
    return render(request, "chem/lab_atom.html", conn, user, elements=data, z=z if 1 <= z <= 54 else 6)


@router.get("/chem/lab/video", response_class=HTMLResponse)
def chem_lab_video(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    _site_only()
    from .content import chem_videos
    items = [{**it, "options": chem_videos.options(it["id"]), "reagents": chem_videos.reagents(it)}
             for it in chem_videos.available()]
    solved = set()
    if user["role"] == "student":
        solved = {r[0][len("video-"):] for r in conn.execute(
            "SELECT ref FROM xp_events WHERE student_id = ? AND kind = 'lab' AND ref LIKE 'video-%'", (user["id"],))}
    return render(request, "chem/lab_video.html", conn, user, items=items, solved=solved,
                  total=len(chem_videos.ITEMS))


@router.post("/api/chem/lab/video")
async def chem_lab_video_answer(request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    from .content import chem_videos
    data = await _json(request)
    item_id = str(data.get("id", ""))
    if item_id not in chem_videos.BY_ID:
        raise HTTPException(404)
    try:
        index = int(data.get("answer"))
    except (TypeError, ValueError):
        raise HTTPException(400)
    item = chem_videos.BY_ID[item_id]
    ok = chem_videos.check(item_id, index)
    from .chem_format import formula_html
    result = {"correct": ok, "right": chem_videos.options(item_id).index(item["observe"]), "title": item["title"],
              "equation_html": str(formula_html(item["equation"])), "nums": item["nums"], "notices": []}
    if not ok and user["role"] == "student":
        # ошибку запоминаем: после перезагрузки страницы верный ответ на этот опыт опыта уже не даст
        with conn:
            if not conn.execute("SELECT 1 FROM xp_events WHERE student_id = ? AND kind = 'lab_miss' AND ref = ?",
                                (user["id"], "video-" + item_id)).fetchone():
                conn.execute("INSERT INTO xp_events (student_id, amount, reason, kind, ref, created_at) VALUES (?, 0, ?, "
                             "'lab_miss', ?, ?)", (user["id"], "Опыт «%s»: ошибка" % item["title"], "video-" + item_id,
                                                   game.now_iso()))
    if ok and user["role"] == "student":
        sid = user["id"]
        ref = "video-" + item_id
        done = conn.execute("SELECT 1 FROM xp_events WHERE student_id = ? AND kind IN ('lab', 'lab_miss') AND ref = ?",
                            (sid, ref)).fetchone()
        n_today = conn.execute("SELECT COUNT(*) FROM xp_events WHERE student_id = ? AND kind = 'lab' AND created_at >= ?",
                               (sid, config.today().isoformat())).fetchone()[0]
        with conn:
            if not done and n_today < LAB_DAILY:
                game.award(conn, sid, LAB_XP, "Лаборатория: опыт «%s»" % item["title"], "lab", ref)
        result["notices"] = game.pop_notices(conn, sid)
    return result


@router.post("/api/chem/lab/atom")
async def chem_lab_atom_done(request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    data = await _json(request)
    z = _int(data.get("z"), 0)
    if user["role"] != "student" or not 1 <= z <= 54:
        return {"notices": []}
    sid = user["id"]
    today = config.today().isoformat()
    done = conn.execute("SELECT 1 FROM xp_events WHERE student_id = ? AND kind = 'lab' AND ref = ?", (sid, "atom-%d" % z)).fetchone()
    n_today = conn.execute("SELECT COUNT(*) FROM xp_events WHERE student_id = ? AND kind = 'lab' AND created_at >= ?",
                           (sid, today)).fetchone()[0]
    with conn:
        if not done and n_today < LAB_DAILY:
            game.award(conn, sid, LAB_XP, "Лаборатория: собран атом №%d" % z, "lab", "atom-%d" % z)
    return {"notices": game.pop_notices(conn, sid)}


# ------------------------------------------------------------------ пробный вариант ОГЭ/ЕГЭ
from . import chem_mock, chem_review  # noqa: E402


def _mock_for(conn, mock_id, user):
    m = chem_mock.get(conn, mock_id)
    if not m or (user["role"] != "teacher" and m["student_id"] != user["id"]):
        raise HTTPException(404)
    return m


def _mock_files(conn, mock_id):
    return conn.execute("SELECT * FROM chem_mock_files WHERE mock_id = ? ORDER BY id", (mock_id,)).fetchall()


@router.get("/chem/mock", response_class=HTMLResponse)
def chem_mock_list(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    _site_only()
    if user["role"] == "teacher":
        return back("/chem/teacher/mocks")
    sid = user["id"]
    exam = chem_exam.exam_for_grade(students.get_student(conn, sid)["grade"])
    mocks = chem_mock.list_for(conn, sid)
    return render(request, "chem/mock_list.html", conn, user, mocks=mocks, ex=chem_exam.EXAMS[exam],
                  busy=any(m["status"] in ("given", "running") for m in mocks))


@router.post("/chem/mock/new")
def chem_mock_new(conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _site_only()
    sid = only_student(user)
    if conn.execute("SELECT 1 FROM chem_mocks WHERE student_id = ? AND status IN ('given', 'running')", (sid,)).fetchone():
        return back("/chem/mock")
    exam = chem_exam.exam_for_grade(students.get_student(conn, sid)["grade"])
    with conn:
        mid = chem_mock.create(conn, sid, exam)
    return back("/chem/mock/%d" % mid)


@router.get("/chem/mock/{mock_id}", response_class=HTMLResponse)
def chem_mock_page(mock_id: int, request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    _site_only()
    m = _mock_for(conn, mock_id, user)
    if m["status"] == "running" and chem_mock.expired(m):
        with conn:
            _finish_mock(conn, m)
        m = chem_mock.get(conn, mock_id)
    done = m["status"] in ("finished", "checked")
    st = students.get_student(conn, m["student_id"])
    return render(request, "chem/mock.html", conn, user, m=m, rows=chem_mock.rows(m, reveal=done or user["role"] == "teacher"),
                  short_max=chem_mock.short_max(m), long_max=chem_mock.long_max(m), files=_mock_files(conn, mock_id),
                  left=chem_mock.time_left(m), who=st["display_name"] if st else "")


@router.post("/chem/mock/{mock_id}/start")
def chem_mock_start(mock_id: int, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = only_student(user)
    m = _mock_for(conn, mock_id, user)
    busy = conn.execute("SELECT id FROM chem_mocks WHERE student_id = ? AND status = 'running' AND id != ?",
                        (sid, mock_id)).fetchone()
    if busy and m["status"] == "given":
        return back("/chem/mock/%d" % busy[0])
    with conn:
        chem_mock.start(conn, m)
    return back("/chem/mock/%d" % mock_id)


@router.post("/api/chem/mock/{mock_id}/save")
async def chem_mock_save(mock_id: int, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    only_student(user)
    m = _mock_for(conn, mock_id, user)
    data = await _json(request)
    with conn:
        ok = chem_mock.save_answers(conn, m, data.get("answers") or {})
    return {"saved": ok, "left": chem_mock.time_left(m)}


async def _save_mock_files(conn, mock_id, uploads):
    for up in uploads or []:
        if not up or not up.filename:
            continue
        name, path = await save_upload(up, HW_EXT)
        conn.execute("INSERT INTO chem_mock_files (mock_id, file_name, file_path, created_at) VALUES (?, ?, ?, ?)",
                     (mock_id, name, path, game.now_iso()))


def _finish_mock(conn, m):
    """Сдать пробник и начислить опыт за часть 1 (один раз). Вызывать внутри `with conn:`."""
    score = chem_mock.finish(conn, m)
    if score and not game.awarded(conn, m["student_id"], "chem", "mock-%d" % m["id"]):
        game.award(conn, m["student_id"], chem_mock.XP_PER_POINT * score,
                   "пробник %s, часть 1: %d из %d" % (m["ex"]["title"], score, chem_mock.short_max(m)), "chem", "mock-%d" % m["id"])


@router.post("/chem/mock/{mock_id}/finish")
async def chem_mock_finish(mock_id: int, request: Request, files: list[UploadFile] = File(None),
                           conn=Depends(get_db), user=Depends(auth.check_csrf)):
    sid = only_student(user)
    m = _mock_for(conn, mock_id, user)
    form = await request.form()
    answers = {k[2:]: v for k, v in form.items() if k.startswith("a_") and isinstance(v, str)}
    was_open = m["status"] in ("given", "running")
    with conn:
        chem_mock.save_answers(conn, m, answers)
        _finish_mock(conn, m)
        if was_open:
            await _save_mock_files(conn, mock_id, files)
    return back("/chem/mock/%d" % mock_id)


@router.post("/chem/mock/{mock_id}/files")
async def chem_mock_add_files(mock_id: int, files: list[UploadFile] = File(None), conn=Depends(get_db),
                              user=Depends(auth.check_csrf)):
    only_student(user)
    m = _mock_for(conn, mock_id, user)
    if m["status"] != "finished":
        raise HTTPException(400, "Пробник уже проверен")
    with conn:
        await _save_mock_files(conn, mock_id, files)
    return back("/chem/mock/%d#files" % mock_id)


@router.get("/chem/mock-file/{file_id}")
def chem_mock_file(file_id: int, conn=Depends(get_db), user=Depends(auth.current_user)):
    row = conn.execute("SELECT f.*, m.student_id FROM chem_mock_files f JOIN chem_mocks m ON m.id = f.mock_id WHERE f.id = ?",
                       (file_id,)).fetchone()
    if not row or (user["role"] != "teacher" and row["student_id"] != user["id"]):
        raise HTTPException(404)
    return FileResponse(upload_path(row["file_path"]), filename=row["file_name"])


@router.post("/chem/teacher/student/{sid}/mock")
def chem_mock_give(sid: int, due_at: str = Form(""), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _site_only()
    _teacher(user)
    st = students.get_student(conn, sid)
    if not st:
        raise HTTPException(404)
    if conn.execute("SELECT 1 FROM chem_mocks WHERE student_id = ? AND status IN ('given', 'running')", (sid,)).fetchone():
        return back("/chem/teacher/student/%d#mocks" % sid)      # уже есть незавершённый — второй не выдаём
    with conn:
        chem_mock.create(conn, sid, chem_exam.exam_for_grade(st["grade"]), created_by="teacher", due_at=_date(due_at))
    return back("/chem/teacher/student/%d#mocks" % sid)


@router.get("/chem/teacher/mocks", response_class=HTMLResponse)
def chem_teacher_mocks(request: Request, conn=Depends(get_db), user=Depends(auth.teacher_required)):
    _site_only()
    rows = conn.execute("SELECT m.id FROM chem_mocks m ORDER BY CASE m.status WHEN 'finished' THEN 0 ELSE 1 END, m.id DESC "
                        "LIMIT 200").fetchall()
    mocks = []
    for r in rows:
        m = chem_mock.get(conn, r[0])
        st = students.get_student(conn, m["student_id"])
        m["who"] = st["display_name"] if st else "?"
        mocks.append(m)
    return render(request, "chem/teacher_mocks.html", conn, user, mocks=mocks)


@router.post("/chem/teacher/mock/{mock_id}/grade")
async def chem_mock_grade(mock_id: int, request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _teacher(user)
    m = _mock_for(conn, mock_id, user)
    if m["status"] not in ("finished", "checked"):
        raise HTTPException(400, "Пробник ещё не сдан")
    form = await request.form()
    long_points = {k[2:]: v for k, v in form.items() if k.startswith("l_")}
    with conn:
        chem_mock.grade_long(conn, m, long_points, str(form.get("comment", "")))
        got = sum(chem_mock.get(conn, mock_id)["long_points"].values())
        # опыт — только за прирост сверх уже начисленного за эту часть (повторная оценка не начисляет заново)
        paid = game.awarded(conn, m["student_id"], "chem", "mock-long-%d-%%" % mock_id)
        if chem_mock.XP_PER_POINT * got > paid:
            game.award(conn, m["student_id"], chem_mock.XP_PER_POINT * got - paid,
                       "Пробник %s: развёрнутая часть" % m["ex"]["title"], "chem", "mock-long-%d-%d" % (mock_id, got))
    return back("/chem/mock/%d" % mock_id)


# ------------------------------------------------------------------ проверка задач преподавателем
@router.get("/chem/teacher/review", response_class=HTMLResponse)
def chem_review_page(request: Request, exam: str = "oge", show: str = "all", conn=Depends(get_db),
                     user=Depends(auth.teacher_required)):
    _site_only()
    exam = exam if exam in chem_exam.EXAMS else "oge"
    revs = chem_review.reviews(conn)
    issues = [(k, r) for k, r in sorted(revs.items()) if r["status"] == "issue"]
    return render(request, "chem/review.html", conn, user, exam=exam, show=show, exams=chem_exam.EXAMS,
                  rows=chem_review.items(exam), revs=revs, done=len(revs), total=chem_review.total_items(),
                  issues=issues)


@router.post("/api/chem/review")
async def chem_review_set(request: Request, conn=Depends(get_db), user=Depends(auth.check_csrf)):
    _teacher(user)
    data = await _json(request)
    item = str(data.get("item", ""))
    status = str(data.get("status", ""))
    if status not in ("ok", "issue", "clear"):
        raise HTTPException(400)
    valid = item in CHEM_TASKS or (item.startswith("gen:") and len(item.split(":")) == 3
                                   and chem_gen.has_generator(item.split(":")[1], _int(item.split(":")[2])))
    if not valid:
        raise HTTPException(404)
    with conn:
        chem_review.set_review(conn, item, status, str(data.get("comment", "")), game.now_iso())
    return {"ok": True, "done": conn.execute("SELECT COUNT(*) FROM chem_reviews").fetchone()[0]}
