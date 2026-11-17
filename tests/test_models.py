"""Интерактивные модели: страницы umedu отдают 200, на КодКвесте и в ХимЛабе раздела нет."""
import re

from app import config
from app.content import models as catalog
from test_app import client, login  # noqa: F401

PAGES = (
    "/u2/models",
    "/u2/models/microcosmos",
    "/u2/models/phet",
    "/u2/models/molecules",
    "/u2/models/optics",
    "/u2/models/circuits",
)
FILES = (
    "/static/models/microcosmos/microcosmos.html",
    "/static/models/microcosmos/info.js",
    "/static/models/microcosmos/LICENSE",
    "/static/models/molecules/3Dmol-min.js",
    "/static/models/molecules/LICENSE",
    "/static/models/molecules/water.sdf",
    "/static/models/molecules/nacl.xyz",
    "/static/models/molecules/1bna.pdb",
    "/static/models/molecules/1crn.pdb",
    "/static/models/ray-optics/simulator/index.html",
    "/static/models/ray-optics/simulator/main.js",
    "/static/models/ray-optics/LICENSE",
    "/static/models/ray-optics/locales/ru/simulator.json",
    "/static/models/ray-optics/gallery/convex-lens.json",
    "/static/models/circuitjs/circuitjs.html",
    "/static/models/circuitjs/iframe.html",
    "/static/models/circuitjs/COPYING.txt",
    "/static/models/circuitjs/circuitjs/locale/locale_ru.txt",
)


def _on(monkeypatch):
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "CHEM_SITE", False)


def test_catalog_phet_links_are_official_russian():
    assert 10 <= len(catalog.PHET) <= 15
    subjects = {item["subject"] for item in catalog.PHET}
    assert subjects == {"phys", "chem", "bio", "math"}
    for item in catalog.PHET:
        src = catalog.phet_src(item)
        assert src == "https://phet.colorado.edu/sims/html/%s/latest/%s_ru.html" % (item["id"], item["id"])
        assert item["text"] and item["topic"]
    assert len(catalog.OPTICS) >= 3 and len(catalog.CIRCUITS) >= 3
    assert len(catalog.MOLECULES) >= 8


def test_pages_and_files_return_200(client, monkeypatch):  # noqa: F811
    _on(monkeypatch)
    login(client, "student")
    for path in PAGES:
        res = client.get(path)
        assert res.status_code == 200, path
        assert "Интерактивные" in res.text or "Микрокосмос" in res.text or "PhET" in res.text or "Молекул" in res.text or "Оптика" in res.text or "цеп" in res.text
    for path in FILES:
        assert client.get(path).status_code == 200, path
    assert client.get("/static/models/microcosmos/music.mp3").status_code == 404


def test_pages_need_login_and_hide_without_flag(client, monkeypatch):  # noqa: F811
    login(client, "student")
    assert client.get("/u2/models").status_code == 404
    assert client.get("/static/models/microcosmos/microcosmos.html").status_code == 404
    home = client.get("/").text
    assert "Интерактивные модели" not in home and 'href="/u2/models"' not in home
    _on(monkeypatch)
    client.cookies.clear()
    assert client.get("/u2/models", follow_redirects=False).status_code == 303


def test_hidden_on_chemlab_even_with_flag(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "UMEDU2", True)
    monkeypatch.setattr(config, "CHEM_SITE", True)
    login(client, "student")
    assert client.get("/u2/models").status_code == 404
    assert client.get("/u2/models/phet").status_code == 404
    assert client.get("/static/models/circuitjs/circuitjs.html").status_code == 404


def test_lab_links_models_and_keeps_six_labs(client, monkeypatch):  # noqa: F811
    _on(monkeypatch)
    csrf = login(client, "student")
    lab = client.get("/u2/lab").text
    assert 'href="/u2/models"' in lab and "Интерактивные модели" in lab
    assert lab.count('href="/u2/lab/') == 6
    client.post("/u2/start", data={"csrf": csrf, "exam_id": "oge-phys-2026", "goal": 4})
    assert 'href="/u2/models"' in client.get("/u2/today").text


def test_phet_page_attributes_and_does_not_loosen_the_rest(client, monkeypatch):  # noqa: F811
    _on(monkeypatch)
    login(client, "student")
    page = client.get("/u2/models/phet")
    assert page.status_code == 200
    html = page.text
    assert "PhET Interactive Simulations, University of Colorado Boulder" in html
    for item in catalog.PHET:
        assert catalog.phet_src(item) in html
    csp = page.headers["content-security-policy"]
    assert "frame-src 'self' https://phet.colorado.edu" in csp
    assert "frame-ancestors 'none'" in csp
    assert page.headers["cross-origin-embedder-policy"] == "unsafe-none"
    for attrs in re.findall(r"<script\b([^>]*)>", html, flags=re.I):
        assert "src=" in attrs, attrs
    login_page = client.get("/login")
    assert "phet.colorado.edu" not in login_page.headers["content-security-policy"]
    assert login_page.headers["cross-origin-embedder-policy"] == "require-corp"
    mol = client.get("/u2/models/molecules")
    assert "unsafe-eval" in mol.headers["content-security-policy"]
    assert 'src="/static/models/molecules/3Dmol-min.js' in mol.text


def test_attributions_are_on_the_pages(client, monkeypatch):  # noqa: F811
    _on(monkeypatch)
    login(client, "student")
    micro = client.get("/u2/models/microcosmos").text
    assert "Felipe Reigosa" in micro and "GPL-3.0" in micro
    assert "github.com/felipereigosa/microcosmos" in micro
    assert "Kevin MacLeod" in micro and "CC BY 4.0" in micro
    info = client.get("/static/models/microcosmos/info.js").text
    assert "Инфузория" in info and "Цианобактерия" in info
    optics = client.get("/u2/models/optics").text
    assert "Yi-Ting Tu" in optics and "Apache-2.0" in optics
    assert "github.com/ricktu288/ray-optics" in optics
    circuits = client.get("/u2/models/circuits").text
    assert "Paul Falstad" in circuits and "GPL-2.0" in circuits
    assert "Последовательно" in circuits and "Параллельно" in circuits and "Закон Ома" in circuits
    assert "whiteBackground=1" in circuits and "currentColor=%231a4fd8" in circuits
    assert "Как пользоваться" in circuits and "Редактировать" in circuits and "0,6 А" in circuits
    assert "ползунок" in circuits and "‖" in circuits
    optics_how = client.get("/u2/models/optics").text
    assert "Как пользоваться" in optics_how and "оранжевый" in optics_how
    phet_html = client.get("/u2/models/phet").text
    assert "Открыть в новой вкладке" in phet_html
    assert "phet.colorado.edu" in phet_html and "не копир" in phet_html
    assert 'data-external="phet"' in phet_html
    picker = client.get("/static/js/models/picker.js").text
    assert "postMessageOnLoad" in picker and "https://phet.colorado.edu" in picker
    micro_file = client.get("/static/models/microcosmos/microcosmos.html").text
    assert "#8ecae6" in micro_file and "new Yt(.06,.18,.28)" in micro_file
    assert ".0018,.0065,.0125" not in micro_file
    ray_page = client.get("/static/models/ray-optics/simulator/index.html").text
    assert "background-color: #F6F5FB" in ray_page
    assert "background-color: black" not in ray_page
    assert 'backgroundColor: "#F7F6FC"' in client.get("/static/js/models/molecules.js").text
    mol = client.get("/u2/models/molecules").text
    assert "3Dmol.js" in mol and "BSD-3-Clause" in mol
    assert "Вода" in mol and "Бензол" in mol and "Решётка NaCl" in mol
    assert "1BNA" in mol and "1CRN" in mol
    built = client.get("/static/models/circuitjs/circuitjs.html")
    assert "dropbox" not in built.text.lower()
    # Свою страницу модели можно вложить в iframe раздела. Чужие сайты по-прежнему не могут вложить umedu.
    assert "frame-ancestors 'self'" in built.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in client.get("/u2/models/circuits").headers["content-security-policy"]
    ray = client.get("/static/models/ray-optics/simulator/index.html").text
    assert "window.lang = lang" in ray
