"""Интерактивные модели: оглавление и страницы просмотра.

Раздел живёт только на umedu (CQ_UMEDU2=1 и не сайт химии). КодКвест и ХимЛаб этих адресов не отдают.
Сами программы — отдельные файлы в /static/models, в общий бандл сайта они не входят.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import auth, config
from .content import models as catalog
from .db import get_db
from .main import need_sid, render
from .u2_web import TABS


def _enabled():
    if not config.UMEDU2 or config.CHEM_SITE:
        raise HTTPException(404)


router = APIRouter(prefix="/u2/models", dependencies=[Depends(_enabled)])


def _page(request, conn, user, name, **ctx):
    return render(request, name, conn, user, tab="today", tabs=TABS, **ctx)


@router.get("", response_class=HTMLResponse)
def models_index(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    need_sid(conn, user)
    return _page(request, conn, user, "u2/models_index.html", sections=catalog.SECTIONS)


@router.get("/microcosmos", response_class=HTMLResponse)
def models_micro(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    need_sid(conn, user)
    return _page(request, conn, user, "u2/models_micro.html")


@router.get("/phet", response_class=HTMLResponse)
def models_phet(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    need_sid(conn, user)
    groups = []
    for key, title in catalog.SUBJECTS:
        items = []
        for item in catalog.PHET:
            if item["subject"] == key:
                items.append({**item, "src": catalog.phet_src(item)})
        groups.append({"id": key, "title": title, "items": items})
    return _page(request, conn, user, "u2/models_phet.html", groups=groups, credit=catalog.PHET_CREDIT)


@router.get("/molecules", response_class=HTMLResponse)
def models_molecules(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    need_sid(conn, user)
    items = [{**item, "src": catalog.molecule_src(item)} for item in catalog.MOLECULES]
    return _page(request, conn, user, "u2/models_mol.html", items=items)


@router.get("/optics", response_class=HTMLResponse)
def models_optics(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    need_sid(conn, user)
    items = [{**item, "src": catalog.ray_src(item)} for item in catalog.OPTICS]
    return _page(request, conn, user, "u2/models_optics.html", items=items)


@router.get("/circuits", response_class=HTMLResponse)
def models_circuits(request: Request, conn=Depends(get_db), user=Depends(auth.current_user)):
    need_sid(conn, user)
    items = [{**item, "src": catalog.circuit_src(item)} for item in catalog.CIRCUITS]
    return _page(request, conn, user, "u2/models_circuits.html", items=items)
