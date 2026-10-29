"""Крошка падения: белый список полей. Тело режется до отправки."""
import json
import re

ALLOWED = ("build", "exception", "frames", "route", "last_api_error")
MAX_BYTES = 8000
OWN_PACKAGE = "ru.umedu."
ROUTE_OK = re.compile(r"^[a-z]+(/\{[a-z_]+\})*$")


def sanitize(payload):
    """payload может содержать черновик ответа — его не должно остаться в JSON."""
    out = {}
    for key in ALLOWED:
        if key not in payload:
            continue
        value = payload[key]
        if key == "frames":
            value = [frame for frame in value if isinstance(frame, str) and OWN_PACKAGE in frame]
        if key == "route" and value and not ROUTE_OK.match(str(value).replace("{", "{").split("?")[0]):
            value = "unknown"
        out[key] = value
    raw = json.dumps(out, ensure_ascii=False)
    if len(raw.encode()) > MAX_BYTES:
        out["frames"] = out.get("frames", [])[:3]
        raw = json.dumps(out, ensure_ascii=False)
    return json.loads(raw)
