"""Шаблоны службы и env стенда, dry-run скриптов. На диск за пределами репозитория ничего не пишется."""
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ["deploy/stage_lib.sh", "deploy/add_stage.sh", "deploy/update_stage.sh"]


def _bash(code, *args):
    return subprocess.check_output(["bash", "-c", code, "bash", *args], cwd=ROOT, text=True)


def test_bash_and_shellcheck():
    for name in SCRIPTS:
        subprocess.check_call(["bash", "-n", name], cwd=ROOT)
    if shutil.which("shellcheck"):
        subprocess.check_call(["shellcheck", "--severity=warning", "-x", *SCRIPTS], cwd=ROOT)


def test_env_and_unit_templates():
    env = _bash('source deploy/stage_lib.sh; stage_render_env "$@"', "stage", "stage.umedu.ru")
    for line in (
        "CQ_STAGE=1",
        "CQ_THEME=public",
        "CQ_UMEDU2=1",
        "CQ_SIGNUP=open",
        "CQ_PARENT_BOT=0",
        "CQ_PURGE_INACTIVE=0",
        'CQ_SITE_NAME="umedu · стенд"',
        "CQ_BASE_URL=https://stage.umedu.ru",
        "CQ_DATA_DIR=/var/lib/codequest-stage",
    ):
        assert line in env
    unit = _bash('source deploy/stage_lib.sh; stage_render_unit "$@"', "stage", "8091")
    assert "WorkingDirectory=/opt/codequest-stage" in unit
    assert "EnvironmentFile=/etc/codequest/stage.env" in unit
    assert "User=codequest" in unit
    assert "--port 8091" in unit
    nginx = _bash('source deploy/stage_lib.sh; stage_render_nginx "$@"', "stage.umedu.ru", "8091")
    assert "server_name stage.umedu.ru;" in nginx
    assert "proxy_pass http://host.docker.internal:8091;" in nginx
    assert "$host" in nginx
    compose = _bash(
        'source deploy/stage_lib.sh; stage_render_compose "$@"',
        "stage", "stage.umedu.ru", "traefik", "websecure", "letsencrypt")
    assert "traefik.enable=true" in compose
    assert "Host(`stage.umedu.ru`)" in compose
    assert "traefik.docker.network=traefik" in compose


def test_dry_run_prints_plan_and_writes_nothing():
    proc = subprocess.run(
        ["bash", "deploy/add_stage.sh", "--dry-run", "stage", "stage.umedu.ru", "8091", "main"],
        cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "DNS" in out and "deploy_key" in out and "8091" in out
    assert "CQ_STAGE=1" in out and "CQ_SIGNUP=open" in out
    assert "/opt/codequest-stage" in out
    assert not Path("/opt/codequest-stage").exists()
    assert not Path("/etc/codequest/stage.env").exists()
    update = subprocess.run(["bash", "deploy/update_stage.sh", "--dry-run", "main"],
                            cwd=ROOT, capture_output=True, text=True)
    assert update.returncode == 0, update.stderr
    assert "pytest" in update.stdout and "healthz" in update.stdout and "не запускаю" in update.stdout


def test_add_stage_rejects_bad_args_and_non_root():
    bad = subprocess.run(
        ["bash", "deploy/add_stage.sh", "--dry-run", "Stage", "stage.umedu.ru", "80", "main"],
        cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode != 0
    real = subprocess.run(
        ["bash", "deploy/add_stage.sh", "stage", "stage.umedu.ru", "8091", "main"],
        cwd=ROOT, capture_output=True, text=True)
    assert real.returncode != 0
    assert "root" in real.stderr
    assert not Path("/etc/codequest/stage.env").exists()


def test_scripts_have_no_private_markers():
    blob = "\n".join(Path(ROOT, name).read_text(encoding="utf-8") for name in SCRIPTS)
    blob += "\n" + Path(ROOT, "docs/STAGE.md").read_text(encoding="utf-8")
    assert "familysrv" not in blob and "/opt/kaxy4" not in blob and "private/" not in blob.lower()
    ips = set(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", blob))
    assert ips <= {"0.0.0.0"}
