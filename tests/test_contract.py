"""contract.lock = SHA-256 openapi/v1.yaml. Копия схемы и лок живут и в репозитории umedu-android."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YAML = ROOT / "openapi" / "v1.yaml"
LOCK = ROOT / "contract.lock"


def _digest():
    data = YAML.read_bytes()
    assert b"\r\n" not in data
    return hashlib.sha256(data).hexdigest()


def _lock():
    """Строки вида `sha256 <хеш>` и `file <путь>`."""
    pairs = (line.split(None, 1) for line in LOCK.read_text(encoding="utf-8").splitlines() if line.strip())
    return {k: v.strip() for k, v in pairs}


def test_lock_matches_yaml():
    lock = _lock()
    assert lock["file"] == "openapi/v1.yaml"
    assert lock["sha256"] == _digest()


def test_yaml_has_only_live_paths():
    """В схеме нет пути, на который сервер не отвечает."""
    import app.main  # noqa: F401 — роутер api_v1 подключается из main
    from app.api_v1 import router
    lines = YAML.read_text(encoding="utf-8").splitlines()
    paths = {line.strip().rstrip(":") for line in lines if line.startswith("  /")}
    assert paths == {"/api/v1/config", "/api/v1/catalog"}
    served = {r.path for r in router.routes}
    assert paths <= served
