"""Юниты чистки неактивных: команда существует, сухой прогон идёт до удаления, таймер ежедневный."""
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"


def test_purge_units_call_existing_command():
    svc = (DEPLOY / "codequest-purge@.service").read_text(encoding="utf-8")
    manage = (DEPLOY.parent / "manage.py").read_text(encoding="utf-8")
    assert '"purge-inactive"' in manage and '"--apply" in' in manage
    pre = [l for l in svc.splitlines() if l.startswith("ExecStartPre=")]
    run = [l for l in svc.splitlines() if l.startswith("ExecStart=")]
    assert pre and pre[0].endswith("manage.py purge-inactive")          # сухой прогон
    assert run and run[0].endswith("manage.py purge-inactive --apply")
    assert "EnvironmentFile=/etc/codequest/%i.env" in svc


def test_purge_timer_daily():
    timer = (DEPLOY / "codequest-purge@.timer").read_text(encoding="utf-8")
    assert "OnCalendar=*-*-* 04:40:00" in timer and "Persistent=true" in timer
