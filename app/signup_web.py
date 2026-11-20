"""Регистрация ученика: по коду приглашения (ХимЛаб, CQ_SIGNUP=1) или открытая (CQ_SIGNUP=open).

Маршруты вынесены из main.py и chem_web.py; общие функции берутся из main. Подключается в конце main.py.
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import auth, chem, config, students
from .db import get_db
from .main import back, only_student, render

router = APIRouter()


def _ip(request):
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "?")


@router.get("/signup-teacher", response_class=HTMLResponse)
def signup_teacher_page(request: Request, conn=Depends(get_db)):
    """Регистрация репетитора. Как и регистрация учеников, открыта только при CQ_SIGNUP=open (issue #13)."""
    if not config.OPEN_SIGNUP:
        raise HTTPException(404)
    return render(request, "signup_teacher.html", conn, None, suggested=students.generate_password(), form={}, error=None)


@router.post("/signup-teacher", response_class=HTMLResponse)
def signup_teacher(request: Request, name: str = Form(""), login: str = Form(""), password: str = Form(""),
                   consent: str = Form(""), website: str = Form(""), conn=Depends(get_db)):
    ip = _ip(request)
    if not config.OPEN_SIGNUP:
        raise HTTPException(404)

    def again(error):
        return render(request, "signup_teacher.html", conn, None, suggested=students.generate_password(),
                      form={"name": name, "login": login}, error=error)

    if website:
        return again("Не получилось. Обновите страницу и попробуйте ещё раз.")
    if students.signup_limited(ip):
        return again("С этого адреса уже много регистраций. Попробуй через час.")
    name = name.strip()[:60]
    login = login.strip().lower()
    if not name:
        return again("Напишите, как к вам обращаться.")
    if not students.valid_login(login):
        return again("Логин — латиница, цифры, точка, дефис, 2–32 символа.")
    if len(password) < 6:
        return again("Пароль — хотя бы 6 символов.")
    if not consent:
        return again("Отметьте согласие на обработку данных.")
    error = None
    tid = code = None
    with conn:
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (login,)).fetchone():
            error = "Такой логин уже занят."
        else:
            tid = conn.execute(
                "INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, 'teacher', ?)",
                (login, auth.hash_password(password), name)).lastrowid
            code = students.make_invite_code(conn, tid)
    if error:
        return again(error)
    return _done(conn, tid, "/teacher/students")


@router.get("/account/join-teacher", response_class=HTMLResponse)
def join_teacher_page(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    only_student(user)
    return render(request, "account/join_teacher.html", conn, user, ok=None, error=None, code="")


@router.post("/account/join-teacher", response_class=HTMLResponse)
def join_teacher(request: Request, code: str = Form(""), conn=Depends(get_db), user=Depends(auth.check_csrf)):
    only_student(user)
    code = code.strip().upper()[:16]
    teacher_id = students.teacher_by_invite(conn, code)
    if not teacher_id:
        return render(request, "account/join_teacher.html", conn, user, ok=None,
                      error="Код не найден. Проверьте буквы — их даёт преподаватель.", code=code)
    with conn:
        students.attach_student_to_teacher(conn, user["id"], teacher_id)
    return render(request, "account/join_teacher.html", conn, user,
                  ok="Готово: вы в группе. Преподаватель видит ваш прогресс в своём кабинете.", error=None, code=code)


def _done(conn, sid, to):
    token = auth.create_session(conn, sid)
    resp = back(to)
    auth.set_cookie(resp, token)
    return resp


@router.get("/join", response_class=HTMLResponse)
def join_page(request: Request, code: str = "", conn=Depends(get_db)):
    if config.CHEM_SITE and config.SIGNUP:
        return render(request, "chem/join.html", conn, None, code=code, grades=chem.GRADES,
                      suggested=students.generate_password(), form={})
    if not config.OPEN_SIGNUP:
        raise HTTPException(404)
    return render(request, "join.html", conn, None, grades=students.signup_grades(), suggested=students.generate_password(),
                  form={})


@router.post("/join", response_class=HTMLResponse)
def join(request: Request, code: str = Form(""), name: str = Form(""), grade: int = Form(0), login: str = Form(""),
         password: str = Form(""), consent: str = Form(""), age14: str = Form(""), website: str = Form(""),
         invite_code: str = Form(""), conn=Depends(get_db)):
    ip = _ip(request)
    if config.CHEM_SITE and config.SIGNUP:
        def again(error):
            return render(request, "chem/join.html", conn, None, code=code, grades=chem.GRADES, suggested=password,
                          form={"name": name, "grade": grade, "login": login}, error=error)
        if auth.too_many_fails(ip):
            return again("Слишком много попыток. Подожди 15 минут.")
        with conn:
            sid, error = chem.signup(conn, code, name, grade, login, password)
        if error:
            if "код" in error:
                auth.register_fail(ip)
            return again(error)
        return _done(conn, sid, "/chem?welcome=1")
    if not config.OPEN_SIGNUP:
        raise HTTPException(404)

    def again(error):
        return render(request, "join.html", conn, None, grades=students.signup_grades(), suggested=password,
                      form={"name": name, "grade": grade, "login": login, "consent": consent, "age14": age14,
                            "invite_code": invite_code}, error=error)
    if website:                            # скрытое поле: человек его не видит, бот заполняет
        return again("Не получилось. Обнови страницу и попробуй ещё раз.")
    if students.signup_limited(ip):
        return again("С этого адреса уже много регистраций. Попробуй через час.")
    with conn:
        sid, error = students.signup(conn, name, grade, login, password, bool(consent), ip, age14=bool(age14), invite_code=invite_code)
    if error:
        return again(error)
    return _done(conn, sid, "/u2/today" if config.UMEDU2 and not config.CHEM_SITE else "/")
