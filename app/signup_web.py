"""Регистрация ученика: по коду приглашения (ХимЛаб, CQ_SIGNUP=1) или открытая (CQ_SIGNUP=open).

Маршруты вынесены из main.py и chem_web.py; общие функции берутся из main. Подключается в конце main.py.
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import auth, chem, config, students
from .db import get_db
from .main import back, render

router = APIRouter()


def _ip(request):
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "?")


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
    return render(request, "join.html", conn, None, grades=students.GRADES, suggested=students.generate_password(),
                  form={})


@router.post("/join", response_class=HTMLResponse)
def join(request: Request, code: str = Form(""), name: str = Form(""), grade: int = Form(0), login: str = Form(""),
         password: str = Form(""), consent: str = Form(""), website: str = Form(""), conn=Depends(get_db)):
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
        return render(request, "join.html", conn, None, grades=students.GRADES, suggested=password,
                      form={"name": name, "grade": grade, "login": login, "consent": consent}, error=error)
    if website:                            # скрытое поле: человек его не видит, бот заполняет
        return again("Не получилось. Обнови страницу и попробуй ещё раз.")
    if students.signup_limited(ip):
        return again("С этого адреса уже много регистраций. Попробуй через час.")
    with conn:
        sid, error = students.signup(conn, name, grade, login, password, bool(consent), ip)
    if error:
        return again(error)
    return _done(conn, sid, "/")
