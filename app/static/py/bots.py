"""«Битва ботов»: пошаговая игра «Сбор кристаллов» для ботов на Python.

Бот — функция ход(я, враг, кристаллы, стены), которая каждый ход возвращает команду:
    "вверх", "вниз", "влево", "вправо", "стоп"            — шаг
    "огонь вверх", "огонь вниз", "огонь влево", "огонь вправо" — выстрел по прямой на ДАЛЬНОСТЬ клеток
я, враг — словари {"x", "y", "жизни", "кристаллы", "жив"}; кристаллы — список (x, y); стены — множество (x, y).
Помощники: расстояние(a, b), шаг_к(я, цель, стены), линия_огня(я, цель, стены) → направление или None.

Ход считается одновременно: сначала выстрелы (по позициям в начале хода), потом шаги, потом подбор кристаллов.
Подстреленный (3 попадания) роняет все кристаллы и через 3 хода появляется на своей базе. 3 хода без выстрелов
и попаданий — +1 жизнь (до 3).
Победа — 7 кристаллов в конце хода (у обоих — у кого больше), иначе через 120 ходов — у кого больше.

Работает одинаково в браузере (Pyodide) и в обычном Python (тесты сайта).
"""
import builtins
import json
import random
import sys

import cq_runtime

W, H = 11, 9
WALLS = {(4, 4), (6, 4), (3, 2), (7, 2), (3, 6), (7, 6), (5, 1), (5, 7), (2, 4), (8, 4)}
BASES = {"blue": (1, 4), "red": (9, 4)}
SPAWNS = [(5, 4), (5, 2), (5, 6)]
HP = 3
RANGE = 3
WIN_GEMS = 7
MAX_TURNS = 120
RESPAWN = 3
REGEN_AFTER = 3          # ходов без выстрелов и попаданий — и +1 жизнь
SPAWN_EVERY = 3
MAX_GEMS_ON_FIELD = 4
MAX_FRAMES = 130

DIRS = {"вверх": (0, -1), "вниз": (0, 1), "влево": (-1, 0), "вправо": (1, 0)}


# ------------------------------------------------------------------ помощники для ботов
def расстояние(a, b):
    ax, ay = (a["x"], a["y"]) if isinstance(a, dict) else a
    bx, by = (b["x"], b["y"]) if isinstance(b, dict) else b
    return abs(ax - bx) + abs(ay - by)


def _xy(p):
    return (p["x"], p["y"]) if isinstance(p, dict) else tuple(p)


def шаг_к(я, цель, стены):
    """Направление первого шага кратчайшего пути от я к цели в обход стен (или "стоп")."""
    start, goal = _xy(я), _xy(цель)
    if start == goal:
        return "стоп"
    prev = {start: None}
    queue = [start]
    for cur in queue:
        if cur == goal:
            break
        for name, (dx, dy) in DIRS.items():
            nxt = (cur[0] + dx, cur[1] + dy)
            if 0 <= nxt[0] < W and 0 <= nxt[1] < H and nxt not in стены and nxt not in prev:
                prev[nxt] = (cur, name)
                queue.append(nxt)
    if goal not in prev:
        return "стоп"
    node, first = goal, "стоп"
    while prev[node] is not None:
        node, first = prev[node]
    return first


def линия_огня(я, цель, стены):
    """Если цель на одной прямой в пределах ДАЛЬНОСТИ и стен между нет — направление выстрела, иначе None."""
    (x, y), (tx, ty) = _xy(я), _xy(цель)
    for name, (dx, dy) in DIRS.items():
        cx, cy = x, y
        for _ in range(RANGE):
            cx, cy = cx + dx, cy + dy
            if (cx, cy) in стены or not (0 <= cx < W and 0 <= cy < H):
                break
            if (cx, cy) == (tx, ty):
                return name
    return None


HELPERS = {"расстояние": расстояние, "шаг_к": шаг_к, "линия_огня": линия_огня, "ДАЛЬНОСТЬ": RANGE,
           "ШИРИНА": W, "ВЫСОТА": H}

# ------------------------------------------------------------------ боссы сайта (по возрастанию сложности)
BOSSES = [
    {"id": 'dummy', "name": 'Манекен', "emoji": '🪵', "xp": 15,
     "about": 'Стоит на базе и ничего не делает. Дойди до кристаллов и собери 7.',
     "code": "def ход(я, враг, кристаллы, стены):\n    return 'стоп'\n"},
    {"id": 'turret', "name": 'Турель', "emoji": '🗼', "xp": 20,
     "about": 'Стоит у центра и стреляет во всех на линии огня. Кристаллы не собирает — успей раньше неё.',
     "code": "def ход(я, враг, кристаллы, стены):\n    if враг['жив']:\n        л = линия_огня(я, враг, стены)\n        if л:\n            return 'огонь ' + л\n    return шаг_к(я, (6, 3), стены)\n"},
    {"id": 'runner', "name": 'Бегун', "emoji": '🏃', "xp": 25,
     "about": 'Бежит к ближайшему кристаллу и собирает быстро. Не стреляет — а вот тебе придётся.',
     "code": "def ход(я, враг, кристаллы, стены):\n    if not кристаллы:\n        return 'стоп'\n    цель = min(кристаллы, key=lambda к: расстояние(я, к))\n    return шаг_к(я, цель, стены)\n"},
    {"id": 'hunter', "name": 'Охотник', "emoji": '🐺', "xp": 30,
     "about": 'Собирает кристаллы и стреляет, когда ты на линии огня. После выстрела ход перезаряжается.',
     "code": "перезарядка = False\n\n\ndef ход(я, враг, кристаллы, стены):\n    global перезарядка\n    if враг['жив'] and not перезарядка:\n        л = линия_огня(я, враг, стены)\n        if л:\n            перезарядка = True\n            return 'огонь ' + л\n    перезарядка = False\n    if кристаллы:\n        цель = min(кристаллы, key=lambda к: расстояние(я, к))\n        return шаг_к(я, цель, стены)\n    return шаг_к(я, враг, стены) if враг['жив'] else 'стоп'\n"},
    {"id": 'champion', "name": 'Чемпион', "emoji": '👑', "xp": 50,
     "about": 'Стреляет без перезарядки, а с 5 кристаллами или одной жизнью уходит на базу. В лоб не победить — не подставляйся под линию огня.',
     "code": "def ход(я, враг, кристаллы, стены):\n    if враг['жив']:\n        л = линия_огня(я, враг, стены)\n        if л:\n            return 'огонь ' + л\n    if я['кристаллы'] >= 5 or я['жизни'] == 1:\n        return шаг_к(я, (9, 4), стены)\n    if враг['жив'] and враг['кристаллы'] > я['кристаллы'] and расстояние(я, враг) <= 6:\n        return шаг_к(я, враг, стены)\n    if кристаллы:\n        цель = min(кристаллы, key=lambda к: расстояние(я, к) - (2 if расстояние(враг, к) > расстояние(я, к) else 0))\n        return шаг_к(я, цель, стены)\n    return 'стоп'\n"},
]
BOSS_BY_ID = {b["id"]: b for b in BOSSES}


class BotError(Exception):
    pass


def _load(code):
    ns = {"__name__": "__bot__", "__builtins__": builtins}
    ns.update(HELPERS)
    exec(compile(code, cq_runtime.FILENAME, "exec"), ns)
    fn = ns.get("ход")
    if not callable(fn):
        raise BotError("В программе нет функции ход(я, враг, кристаллы, стены). Начни с: def ход(я, враг, кристаллы, стены):")
    return fn


def _view(p):
    return {"x": p["x"], "y": p["y"], "жизни": p["hp"], "кристаллы": p["gems"], "жив": p["dead"] == 0}


def _parse(cmd):
    if not isinstance(cmd, str):
        return None
    cmd = cmd.strip().lower()
    if cmd == "стоп":
        return ("stay", None)
    if cmd in DIRS:
        return ("move", cmd)
    if cmd.startswith("огонь ") and cmd[6:].strip() in DIRS:
        return ("shoot", cmd[6:].strip())
    return None


def battle(code_blue, code_red, seed=1):
    """Бой двух ботов. Возвращает dict: winner (blue|red|draw), frames, счёт, ошибки (только синего, с подсказкой)."""
    rng = random.Random(seed)
    fns, errors = {}, {}
    for side, code in (("blue", code_blue), ("red", code_red)):
        try:
            fns[side] = _load(code)
        except BotError as e:
            errors[side] = {"type": "Ошибка", "hint": str(e), "line": None, "turn": 0}
        except BaseException as e:  # noqa: BLE001
            errors[side] = dict(cq_runtime.format_error(e), turn=0)
    if errors:
        winner = "draw" if len(errors) == 2 else ("red" if "blue" in errors else "blue")
        return {"winner": winner, "frames": [], "score": {"blue": 0, "red": 0}, "turns": 0, "errors": errors,
                "walls": sorted(WALLS), "w": W, "h": H}

    pl = {s: {"x": BASES[s][0], "y": BASES[s][1], "hp": HP, "gems": 0, "dead": 0, "calm": 0} for s in BASES}
    gems = []
    frames = []
    winner = None
    old_stdout, old_input = sys.stdout, builtins.input
    sys.stdout = cq_runtime._Capture()
    builtins.input = lambda prompt="": "0"
    try:
        for turn in range(1, MAX_TURNS + 1):
            if turn % SPAWN_EVERY == 1 and len(gems) < MAX_GEMS_ON_FIELD:
                gems.append(rng.choice(SPAWNS))
            acts = {}
            for side, other in (("blue", "red"), ("red", "blue")):
                p = pl[side]
                if p["dead"]:
                    acts[side] = ("stay", None)
                    continue
                try:
                    cmd = fns[side](_view(p), _view(pl[other]), list(gems), set(WALLS))
                except BaseException as e:  # noqa: BLE001 — ошибка бота: он стоит этот ход
                    if isinstance(e, KeyboardInterrupt):
                        raise
                    if side not in errors:
                        errors[side] = dict(cq_runtime.format_error(e), turn=turn)
                    cmd = "стоп"
                act = _parse(cmd)
                if act is None:
                    if side not in errors:
                        errors[side] = {"type": "Неизвестная команда", "turn": turn, "line": None,
                                        "hint": "ход вернул %r. Нужно: 'вверх', 'вниз', 'влево', 'вправо', 'стоп' "
                                                "или 'огонь вверх' и т. п." % (cmd,)}
                    act = ("stay", None)
                acts[side] = act
            # выстрелы — по позициям в начале хода
            shots = []
            hits = {"blue": 0, "red": 0}
            for side, other in (("blue", "red"), ("red", "blue")):
                kind, d = acts[side]
                if kind != "shoot":
                    continue
                dx, dy = DIRS[d]
                x, y = pl[side]["x"], pl[side]["y"]
                length, hit = 0, False
                for _ in range(RANGE):
                    nx, ny = x + dx, y + dy
                    if (nx, ny) in WALLS or not (0 <= nx < W and 0 <= ny < H):
                        break
                    x, y, length = nx, ny, length + 1
                    o = pl[other]
                    if not o["dead"] and (o["x"], o["y"]) == (x, y):
                        hit = True
                        hits[other] += 1
                        break
                shots.append([side, pl[side]["x"], pl[side]["y"], dx, dy, length, hit])
            # шаги
            want = {}
            for side in pl:
                kind, d = acts[side]
                p = pl[side]
                want[side] = (p["x"], p["y"])
                if kind == "move":
                    dx, dy = DIRS[d]
                    nx, ny = p["x"] + dx, p["y"] + dy
                    if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in WALLS:
                        want[side] = (nx, ny)
            # столкновения: в одну клетку — проходит один по жребию; «сквозь» друг друга — оба стоят;
            # в клетку стоящего — нельзя
            alive = {side: not pl[side]["dead"] for side in pl}
            cur = {side: (pl[side]["x"], pl[side]["y"]) for side in pl}
            if alive["blue"] and alive["red"]:
                if want["blue"] == want["red"] and want["blue"] != cur["blue"] and want["red"] != cur["red"]:
                    loser = rng.choice(("blue", "red"))
                    want[loser] = cur[loser]
                elif want["blue"] == cur["red"] and want["red"] == cur["blue"]:
                    want = dict(cur)
                for side, other in (("blue", "red"), ("red", "blue")):
                    if want[side] == cur[other] and want[other] == cur[other]:
                        want[side] = cur[side]
            for side in pl:
                if alive[side]:
                    pl[side]["x"], pl[side]["y"] = want[side]
            # попадания и подбор
            for side in pl:
                p = pl[side]
                if p["dead"]:
                    p["dead"] -= 1
                    if p["dead"] == 0:
                        p["x"], p["y"], p["hp"] = BASES[side][0], BASES[side][1], HP
                    continue
                p["hp"] -= hits[side]
                p["calm"] = 0 if hits[side] or acts[side][0] == "shoot" else p["calm"] + 1
                if p["calm"] >= REGEN_AFTER and p["hp"] < HP:
                    p["hp"], p["calm"] = p["hp"] + 1, 0
                if p["hp"] <= 0:
                    gems.extend([(p["x"], p["y"])] * p["gems"])
                    p["gems"], p["hp"], p["dead"] = 0, 0, RESPAWN
                    continue
                here = (p["x"], p["y"])
                if here in gems:
                    n = gems.count(here)
                    gems = [g for g in gems if g != here]
                    p["gems"] += n
            if len(frames) < MAX_FRAMES:
                frames.append({"t": turn, "p": {s: [pl[s]["x"], pl[s]["y"], pl[s]["hp"], pl[s]["gems"], pl[s]["dead"]] for s in pl},
                               "g": [list(g) for g in gems], "s": shots})
            bg, rg = pl["blue"]["gems"], pl["red"]["gems"]
            if bg >= WIN_GEMS or rg >= WIN_GEMS:
                winner = "blue" if bg > rg else ("red" if rg > bg else None)
                if winner:
                    break
        else:
            turn = MAX_TURNS
    finally:
        sys.stdout, builtins.input = old_stdout, old_input
    if winner is None:
        bg, rg = pl["blue"]["gems"], pl["red"]["gems"]
        winner = "blue" if bg > rg else ("red" if rg > bg else "draw")
    return {"winner": winner, "frames": frames, "score": {s: pl[s]["gems"] for s in pl}, "turns": turn,
            "errors": errors, "walls": sorted(WALLS), "w": W, "h": H}


def fight_boss(code, boss_id, seeds=(1, 2, 3)):
    """Матч из трёх боёв против босса сайта. Победа в матче — 2 боя из 3. JSON для страницы."""
    boss = BOSS_BY_ID[boss_id]
    games = [battle(code, boss["code"], seed) for seed in seeds]
    wins = sum(g["winner"] == "blue" for g in games)
    losses = sum(g["winner"] == "red" for g in games)
    shown = next((g for g in games if g["winner"] != "blue"), games[0])
    for g in games:
        if g is not shown:
            g["frames"] = []
    return json.dumps({"boss": boss_id, "won": wins >= 2, "wins": wins, "losses": losses,
                       "games": [{"winner": g["winner"], "score": g["score"], "turns": g["turns"]} for g in games],
                       "shown": games.index(shown), "battle": shown,
                       "error": shown["errors"].get("blue") or next((g["errors"]["blue"] for g in games
                                                                     if "blue" in g["errors"]), None)},
                      ensure_ascii=False)
