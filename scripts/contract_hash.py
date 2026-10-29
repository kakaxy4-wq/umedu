"""SHA-256 openapi/v1.yaml → stdout. Тот же хеш лежит в contract.lock."""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YAML = ROOT / "openapi" / "v1.yaml"


def digest(path=YAML):
    data = path.read_bytes()
    if b"\r\n" in data:
        raise SystemExit("openapi/v1.yaml must use LF")
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    sys.stdout.write(digest() + "\n")
