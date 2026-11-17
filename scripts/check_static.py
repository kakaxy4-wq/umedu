#!/usr/bin/env python3
"""После выкладки: все файлы /static со страниц и из списка vendor отвечают 200.

Запуск с корня репозитория, когда сайт уже слушает:

    python scripts/check_static.py http://127.0.0.1:8000
    python scripts/check_static.py https://umedu.ru

Код выхода 0 — всё на месте. Иначе в stderr список адресов, которые не 200
или у которых .wasm отдан не как application/wasm.

/ и /login обязаны открыться. /task/hello, /u2/lab и /chem/lab смотрим, только если
они отвечают 200: на КодКвесте нет /u2, на umedu нет химической лаборатории.
"""
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, ".")  # корень репозитория, чтобы импортировать app

from app.static_check import problems  # noqa: E402


class _Resp:
    def __init__(self, status, headers, text, url):
        self.status = status
        self.headers = headers
        self.text = text
        self.url = url


def _fetch(url):
    req = Request(url, headers={"User-Agent": "umedu-check-static"})
    try:
        with urlopen(req, timeout=20) as res:
            raw = res.read()
            text = raw.decode("utf-8", "replace") if not url.endswith(".wasm") else ""
            return _Resp(res.status, dict(res.headers.items()), text, res.geturl())
    except HTTPError as exc:
        return _Resp(exc.code, dict(exc.headers.items()) if exc.headers else {}, "", url)
    except URLError as exc:
        raise RuntimeError(exc.reason) from exc


def main(argv):
    if len(argv) != 2 or not argv[1].startswith("http"):
        print("Нужен адрес сайта: python scripts/check_static.py https://umedu.ru", file=sys.stderr)
        return 2
    bad = problems(argv[1], _fetch)
    if bad:
        print("Статика неполная, %d проблем:" % len(bad), file=sys.stderr)
        for line in bad:
            print("  " + line, file=sys.stderr)
        return 1
    print("Статика на месте: %s" % argv[1].rstrip("/"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
