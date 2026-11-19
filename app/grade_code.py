"""Проверка программ ученика на сервере.

Браузер присылает флаг passed после прогона в Pyodide. Ему не верим: тот же код
прогоняем здесь, в отдельном процессе, чтобы бесконечный цикл не завис на запросе.
"""
import json
import subprocess
import sys
from pathlib import Path

PY_DIR = str(Path(__file__).resolve().parent / "static" / "py")
TIMEOUT = 3

_RUNNER = """
import json, sys
sys.path.insert(0, sys.argv[1])
kind = sys.argv[2]
payload = json.load(sys.stdin)
if kind == "py":
    import cq_runtime
    print(cq_runtime.check(payload["code"], payload["tests"]))
elif kind == "robot":
    import robot
    print(robot.run_all(payload["code"], payload["fields"]))
else:
    sys.exit(2)
"""


def _passed(kind, payload):
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _RUNNER, PY_DIR, kind],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False
    if proc.returncode != 0 or not proc.stdout.strip():
        return False
    try:
        return bool(json.loads(proc.stdout).get("passed"))
    except json.JSONDecodeError:
        return False


def python_passes(code, tests):
    return _passed("py", {"code": code or "", "tests": tests})


def robot_passes(code, fields):
    return _passed("robot", {"code": code or "", "fields": fields})
