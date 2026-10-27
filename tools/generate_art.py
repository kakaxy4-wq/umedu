"""Генерация арта КодКвеста через z.ai (glm-image) по манифесту tools/art-prompts.json.

    ZAI_API_KEY=... python tools/generate_art.py --ids brawler_01_pitosha --variants 2 --out ../art/raw

Промпт = prompt айтема + look его группы + style + avoid (порядок важен: модель сильнее
взвешивает начало). Кандидаты не затираются: <id>_1.png, <id>_2.png… — лучший выбирается руками.
Дальше: вырезка пурпурного фона и WebP — скрипты скилла art-gen (cutout_bg.py, to_webp.py).
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

IMAGE_ENDPOINT = "https://api.z.ai/api/paas/v4/images/generations"
IMAGE_MODEL = "glm-image"
MANIFEST = Path(__file__).with_name("art-prompts.json")


def build_prompt(manifest, item):
    look = manifest["looks"].get(item["kind"], "")
    return ", ".join(p for p in (item["prompt"], look, manifest["style"], manifest["avoid"]) if p)


def generate_one(prompt, size, api_key):
    payload = json.dumps({"model": IMAGE_MODEL, "prompt": prompt, "size": size}).encode()
    req = urllib.request.Request(IMAGE_ENDPOINT, data=payload, method="POST",
                                 headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode())
    item = data["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    with urllib.request.urlopen(item["url"], timeout=120) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="", help="через запятую; пусто — все")
    ap.add_argument("--variants", type=int, default=1)
    ap.add_argument("--size", default="1024x1024")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        sys.exit("ZAI_API_KEY не задан в окружении")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    wanted = {i.strip() for i in args.ids.split(",") if i.strip()}
    items = [i for i in manifest["items"] if not wanted or i["id"] in wanted]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for item in items:
        prompt = build_prompt(manifest, item)
        for _ in range(args.variants):
            n = 1
            while (out / ("%s_%d.png" % (item["id"], n))).exists():
                n += 1
            dest = out / ("%s_%d.png" % (item["id"], n))
            t0 = time.time()
            try:
                dest.write_bytes(generate_one(prompt, args.size, api_key))
                print("ok   %s  %.0fs" % (dest.name, time.time() - t0), flush=True)
            except urllib.error.HTTPError as e:
                print("FAIL %s  HTTP %s: %s" % (dest.name, e.code, e.read().decode(errors="replace")[:300]), flush=True)
            except Exception as e:  # сеть/таймаут — идём дальше, кандидата можно догенерировать
                print("FAIL %s  %s" % (dest.name, e), flush=True)


if __name__ == "__main__":
    main()
