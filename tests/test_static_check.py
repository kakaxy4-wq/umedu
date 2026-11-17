"""Статика после выкладки и честное сообщение, если Python в браузере не загрузился."""
from pathlib import Path

from test_app import client  # noqa: F401

from app.static_check import assets_in, problems
from app.vendor_assets import VENDOR_FILES, missing


class R:
    def __init__(self, status, text="", headers=None, url=""):
        self.status = status
        self.text = text
        self.headers = headers or {}
        self.url = url


def test_healthz_stays_200_and_names_vendor(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["vendor"] in ("ok", "missing")
    if body["vendor"] == "missing":
        assert "vendor/pyodide/pyodide.js" in body["vendor_missing"]
        assert set(body["vendor_missing"]) <= set(VENDOR_FILES)


def test_missing_matches_disk():
    assert missing() == [name for name in VENDOR_FILES if not (Path("app/static") / name).is_file()]


def test_wasm_is_served_as_wasm(client, tmp_path, monkeypatch):
    from app.main import APP_DIR
    folder = APP_DIR / "static" / "vendor" / "pyodide"
    folder.mkdir(parents=True, exist_ok=True)
    wasm = folder / "_mime_probe.wasm"
    wasm.write_bytes(b"\0asm")
    try:
        res = client.get("/static/vendor/pyodide/_mime_probe.wasm")
        assert res.status_code == 200
        assert res.headers["content-type"].split(";")[0].strip() == "application/wasm"
    finally:
        wasm.unlink()


def test_page_assets_and_vendor_and_wasm_type():
    html = '<link rel="stylesheet" href="/static/css/app.css?v=1"><script src="/static/js/app.js"></script>'
    css = 'src: url("/static/vendor/fonts/golos-text-cyrillic-wght-normal.woff2")'
    js = 'const BASE = "/static/vendor/pyodide/";'
    pages = {
        "http://site/": R(200, html, url="http://site/"),
        "http://site/login": R(200, html, url="http://site/login"),
        "http://site/task/hello": R(303, "", url="http://site/login"),
        "http://site/u2/lab": R(404, "", url="http://site/u2/lab"),
        "http://site/chem/lab": R(404, "", url="http://site/chem/lab"),
    }

    def fetch(url):
        if url in pages:
            return pages[url]
        path = url.replace("http://site", "")
        if path == "/static/css/app.css":
            return R(200, css, url=url)
        if path == "/static/js/app.js":
            return R(200, js, url=url)
        if path.endswith(".wasm"):
            return R(200, "", {"content-type": "text/plain"}, url)
        if path == "/static/vendor/pyodide/pyodide.js":
            return R(404, "", url=url)
        return R(200, "", {"content-type": "application/octet-stream"}, url)

    bad = problems("http://site", fetch)
    assert any(line.startswith("/static/vendor/pyodide/pyodide.js → 404") for line in bad)
    assert any("application/wasm" in line and line.startswith("/static/vendor/pyodide/pyodide.asm.wasm") for line in bad)
    assert not any("/u2/lab" in line or "/chem/lab" in line for line in bad)
    assert "/static/vendor/fonts/golos-text-cyrillic-wght-normal.woff2" not in " ".join(bad)


def test_required_page_down_is_a_problem():
    def fetch(url):
        return R(500, "", url=url)

    bad = problems("http://site/", fetch)
    assert any(line.startswith("http://site/") and "500" in line for line in bad)
    assert any("/login" in line for line in bad)


def test_assets_ignore_foreign_and_query():
    text = '<a href="https://example.com/static/x.js"></a><script src="/static/js/app.js?v=3"></script>'
    assert assets_in(text, "http://site/login") == {"/static/js/app.js"}


def test_runner_does_not_blame_the_network_for_a_missing_file():
    runner = Path("app/static/js/runner.js").read_text(encoding="utf-8")
    worker = Path("app/static/js/py-worker.js").read_text(encoding="utf-8")
    assert "Запуск кода временно не работает — мы уже чиним. Твой код сохранён." in runner
    assert "Не получилось загрузить Python в браузере. Проверь интернет" not in runner
    assert "reason === 'network'" in runner
    assert "navigator.onLine" in worker
    assert "err.reason = 'server'" in worker
    assert "application/wasm" in worker
