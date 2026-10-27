"""Генераторы вариантов: бесконечное прорешивание номеров, где условие строится из данных, а ответ вычисляется.

Задача-вариант определяется строкой «g-<экзамен><номер>-<сид>» (например g-o18-4821): по ней задача всегда
восстанавливается одинаково, поэтому её можно открыть по ссылке, проверить на сервере и учесть в прогрессе.
Данные — школьные (массы как в таблице для ОГЭ/ЕГЭ: Cl — 35,5, Cu — 64).
"""
import random
import re

MASS = {"H": 1, "He": 4, "Li": 7, "Be": 9, "B": 11, "C": 12, "N": 14, "O": 16, "F": 19, "Ne": 20, "Na": 23,
        "Mg": 24, "Al": 27, "Si": 28, "P": 31, "S": 32, "Cl": 35.5, "Ar": 40, "K": 39, "Ca": 40, "Cr": 52,
        "Mn": 55, "Fe": 56, "Cu": 64, "Zn": 65, "Br": 80, "Ag": 108, "I": 127, "Ba": 137}

# элементы главных подгрупп: символ, Z, период, группа (номер A-группы)
MAIN = [("Li", 3, 2, 1), ("Be", 4, 2, 2), ("B", 5, 2, 3), ("C", 6, 2, 4), ("N", 7, 2, 5), ("O", 8, 2, 6), ("F", 9, 2, 7),
        ("Na", 11, 3, 1), ("Mg", 12, 3, 2), ("Al", 13, 3, 3), ("Si", 14, 3, 4), ("P", 15, 3, 5), ("S", 16, 3, 6),
        ("Cl", 17, 3, 7), ("K", 19, 4, 1), ("Ca", 20, 4, 2), ("Ga", 31, 4, 3), ("Ge", 32, 4, 4), ("As", 33, 4, 5),
        ("Se", 34, 4, 6), ("Br", 35, 4, 7), ("Rb", 37, 5, 1), ("Sr", 38, 5, 2), ("I", 53, 5, 7)]
BY_SYM = {e[0]: e for e in MAIN}
# электроотрицательность по Полингу — для рядов «усиление неметаллических свойств»
EN = {"Li": 1.0, "Be": 1.6, "B": 2.0, "C": 2.5, "N": 3.0, "O": 3.5, "F": 4.0, "Na": 0.9, "Mg": 1.3, "Al": 1.6,
      "Si": 1.9, "P": 2.2, "S": 2.6, "Cl": 3.2, "K": 0.8, "Ca": 1.0, "Ga": 1.8, "Ge": 2.0, "As": 2.2, "Se": 2.6,
      "Br": 3.0, "Rb": 0.8, "Sr": 1.0, "I": 2.7}

_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*)|(\()|(\))(\d*)")


def molar_mass(formula):
    """M по формуле со скобками: Ca(OH)2, Al2(SO4)3."""
    stack = [0.0]
    for el, n, op, cl, k in _TOKEN.findall(formula):
        if el:
            stack[-1] += MASS[el] * (int(n) if n else 1)
        elif op:
            stack.append(0.0)
        elif cl:
            inner = stack.pop() * (int(k) if k else 1)
            stack[-1] += inner
    return stack[0]


def count_atoms(formula, element):
    total, mult = 0, [1]
    tokens = _TOKEN.findall(formula)
    # разворачиваем скобки: проходим справа налево, чтобы знать множитель скобки
    for el, n, op, cl, k in reversed(tokens):
        if cl:
            mult.append(mult[-1] * (int(k) if k else 1))
        elif op:
            mult.pop()
        elif el == element:
            total += (int(n) if n else 1) * mult[-1]
    return total


def _fmt(x, digits=0):
    s = ("%." + str(digits) + "f") % x
    return s.replace(".", ",")


def _ans(x, digits=0):
    return ("%." + str(digits) + "f") % x


def _plural(n, one, few, many):
    n10, n100 = n % 10, n % 100
    return "%d %s" % (n, one if n10 == 1 and n100 != 11 else (few if 2 <= n10 <= 4 and not 12 <= n100 <= 14 else many))


# ================================================================ ОГЭ
def o2(rng):
    sym, z, period, group = rng.choice([e for e in MAIN if e[1] <= 20])
    electrons = lambda n: _plural(n, "электрон", "электрона", "электронов")  # noqa: E731
    if rng.random() < 0.5:
        return ("Атом химического элемента имеет %s, на внешнем слое — %s.\n"
                "Запишите номер группы и номер периода, в которых находится этот элемент (сначала группа, потом период)."
                % (_plural(period, "электронный слой", "электронных слоя", "электронных слоёв"), electrons(group)),
                "%d%d" % (group, period), "seq",
                "Число слоёв = номер периода, число внешних электронов = номер группы. Это %s." % sym)
    return ("В атоме химического элемента %s.\nЗапишите номер периода, в котором находится элемент, "
            "и число электронов на внешнем слое его атома." % electrons(z), "%d%d" % (period, group), "seq",
            "Это %s: %d-й период, на внешнем слое %s." % (sym, period, electrons(group)))


def _row(rng, n=3):
    """Три элемента одного периода (2–3) или одной группы — для рядов по радиусу и свойствам."""
    if rng.random() < 0.5:
        period = rng.choice([2, 3])
        els = rng.sample([e for e in MAIN if e[2] == period], n)
    else:
        group = rng.choice([1, 2, 5, 6, 7])
        els = rng.sample([e for e in MAIN if e[3] == group], min(n, len([e for e in MAIN if e[3] == group])))
    return els


def _radius_key(e):
    # радиус растёт вниз по группе и справа налево в периоде
    return (e[2], -e[3])


def o3(rng):
    els = _row(rng)
    while len(els) < 3:
        els = _row(rng)
    kind = rng.choice(["radius", "nonmetal", "metal"])
    if kind == "radius":
        order = sorted(els, key=_radius_key)
        q = "в порядке увеличения радиуса их атомов"
    elif kind == "nonmetal":
        order = sorted(els, key=lambda e: EN[e[0]])
        q = "в порядке усиления их неметаллических свойств"
    else:
        order = sorted(els, key=lambda e: -EN[e[0]])
        q = "в порядке усиления их металлических свойств"
    if len({EN[e[0]] for e in els}) < 3 and kind != "radius":
        return o3(rng)
    text = "Расположите химические элементы %s:\n%s" % (q, "  ".join("%d) %s" % (i + 1, e[0]) for i, e in enumerate(els)))
    ans = "".join(str(els.index(e) + 1) for e in order)
    return text, ans, "seq", "Радиус растёт вниз по группе и справа налево в периоде; неметаллические свойства — наоборот."


OX = [("N", [("NH3", -3), ("N2", 0), ("N2O", 1), ("NO", 2), ("N2O3", 3), ("NO2", 4), ("HNO3", 5), ("KNO2", 3), ("NH4Cl", -3)]),
      ("S", [("H2S", -2), ("S", 0), ("SO2", 4), ("Na2SO3", 4), ("SO3", 6), ("H2SO4", 6), ("FeS", -2), ("K2SO4", 6)]),
      ("Cl", [("HCl", -1), ("Cl2", 0), ("NaClO", 1), ("KClO3", 5), ("HClO4", 7), ("Cl2O7", 7), ("KCl", -1)]),
      ("Mn", [("MnO2", 4), ("KMnO4", 7), ("MnSO4", 2), ("K2MnO4", 6), ("MnCl2", 2)]),
      ("Cr", [("Cr2O3", 3), ("K2Cr2O7", 6), ("CrCl3", 3), ("K2CrO4", 6), ("CrO3", 6), ("CrO", 2)]),
      ("P", [("PH3", -3), ("P2O5", 5), ("H3PO4", 5), ("P2O3", 3), ("Ca3P2", -3), ("H3PO3", 3)]),
      ("C", [("CH4", -4), ("CO", 2), ("CO2", 4), ("CaCO3", 4), ("Al4C3", -4), ("H2CO3", 4)])]
NAMES_EL = {"N": "азота", "S": "серы", "Cl": "хлора", "Mn": "марганца", "Cr": "хрома", "P": "фосфора", "C": "углерода"}


def _sgn(v):
    return "0" if v == 0 else ("+%d" % v if v > 0 else "−%d" % -v)


def o4(rng):
    el, items = rng.choice(OX)
    by_state = {}
    for f, v in items:
        by_state.setdefault(v, []).append(f)
    states = rng.sample(sorted(by_state), min(4, len(by_state)))
    if len(states) < 3:
        return o4(rng)
    chosen_states = rng.sample(states, 3)
    formulas = [rng.choice(by_state[v]) for v in chosen_states]
    options = sorted(states)
    letters = "АБВ"
    text = ("Установите соответствие между формулой вещества и степенью окисления %s в нём.\n%s\n%s\n"
            "Запишите цифры под буквами А, Б, В." % (NAMES_EL[el],
                                                    "   ".join("%s) %s" % (letters[i], f) for i, f in enumerate(formulas)),
                                                    "   ".join("%d) %s" % (i + 1, _sgn(v)) for i, v in enumerate(options))))
    ans = "".join(str(options.index(v) + 1) for v in chosen_states)
    return text, ans, "seq", "Сумма степеней окисления в молекуле равна нулю: водород +1, кислород −2, металлы IA +1, IIA +2."


IONS = [("NaCl", 2), ("KNO3", 2), ("HCl", 2), ("NaOH", 2), ("HNO3", 2), ("KBr", 2), ("CaCl2", 3), ("Na2SO4", 3),
        ("K2CO3", 3), ("Ba(OH)2", 3), ("MgCl2", 3), ("Ba(NO3)2", 3), ("AlCl3", 4), ("Na3PO4", 4), ("FeCl3", 4),
        ("K3PO4", 4), ("Al2(SO4)3", 5), ("Fe2(SO4)3", 5)]


def o13(rng):
    n = rng.choice([2, 3, 4])
    good = rng.sample([f for f, k in IONS if k == n], 2)
    bad = rng.sample([f for f, k in IONS if k != n], 3)
    items = good + bad
    rng.shuffle(items)
    text = "Выберите два вещества, при полной диссоциации 1 моль которых образуется %d моль ионов.\n%s" % (
        n, "  ".join("%d) %s" % (i + 1, f) for i, f in enumerate(items)))
    ans = "".join(sorted(str(items.index(f) + 1) for f in good))
    return text, ans, "set", "Посчитай ионы: катионы металла (или H⁺) плюс анионы кислотного остатка (или OH⁻)."


FRACTION = ["SO3", "SO2", "H2SO4", "CuO", "Fe2O3", "CaCO3", "NH4NO3", "KNO3", "NaOH", "MgO", "Al2O3", "CO2", "H2O",
            "NaCl", "CaCl2", "Na2CO3", "Ca(OH)2", "CuSO4", "Fe3O4", "NH3", "HNO3", "P2O5", "Mg(OH)2", "Al(OH)3"]


def o18(rng):
    for _ in range(50):
        f = rng.choice(FRACTION)
        els = sorted({el for el, *_ in _TOKEN.findall(f) if el})
        el = rng.choice(els)
        w = 100 * MASS[el] * count_atoms(f, el) / molar_mass(f)
        if abs(w - round(w)) < 0.4:              # без спорного округления
            return ("Вычислите массовую долю элемента %s в веществе %s. Ответ запишите в процентах с точностью до целых."
                    % (el, f), str(round(w)), "num",
                    "M(%s) = %s г/моль; w(%s) = %s · %d / %s ≈ %d %%." % (
                        f, _fmt(molar_mass(f), 1 if molar_mass(f) % 1 else 0), el, _fmt(MASS[el], 1 if MASS[el] % 1 else 0),
                        count_atoms(f, el), _fmt(molar_mass(f), 1 if molar_mass(f) % 1 else 0), round(w)))
    return o18(rng)


# ================================================================ ЕГЭ
def _unpaired(group):
    return {1: 1, 2: 0, 3: 1, 4: 2, 5: 3, 6: 2, 7: 1}[group]


def e1(rng):
    for _ in range(100):
        row = rng.sample(MAIN, 5)
        k = rng.choice([0, 1, 2, 3])
        good = [e for e in row if _unpaired(e[3]) == k]
        if len(good) == 2:
            text = ("Для заданий используйте ряд элементов: %s\nОпределите, атомы каких двух элементов в основном состоянии "
                    "%s." % ("  ".join("%d) %s" % (i + 1, e[0]) for i, e in enumerate(row)),
                             {0: "не имеют неспаренных электронов", 1: "имеют один неспаренный электрон",
                              2: "имеют два неспаренных электрона", 3: "имеют три неспаренных электрона"}[k]))
            ans = "".join(sorted(str(row.index(e) + 1) for e in good))
            return text, ans, "set", "Неспаренные электроны по группам: I — 1, II — 0, III — 1, IV — 2, V — 3, VI — 2, VII — 1."
    return e1(rng)


def e2(rng):
    period = rng.choice([2, 3, 4])
    row = rng.sample([e for e in MAIN if e[2] == period], 5)
    trio = sorted(rng.sample(row, 3), key=lambda e: e[3])
    if len({EN[e[0]] for e in trio}) < 3:
        return e2(rng)
    kind = rng.choice(["en", "radius"])
    if kind == "en":
        order, q = sorted(trio, key=lambda e: EN[e[0]]), "в порядке увеличения электроотрицательности"
    else:
        order, q = sorted(trio, key=lambda e: -e[3]), "в порядке увеличения радиуса атомов"
    text = ("Ряд элементов: %s\nИз указанных выберите элементы %s и расположите их %s."
            % ("  ".join("%d) %s" % (i + 1, e[0]) for i, e in enumerate(row)), ", ".join(e[0] for e in trio), q))
    ans = "".join(str(row.index(e) + 1) for e in order)
    return text, ans, "seq", "В периоде слева направо радиус уменьшается, электроотрицательность растёт."


def e3(rng):
    pool = [e for e in MAIN if e[0] not in ("F", "O")]
    for _ in range(100):
        row = rng.sample(pool, 5)
        k = rng.choice([4, 5, 6, 7])
        good = [e for e in row if e[3] == k]
        if len(good) == 2:
            text = ("Ряд элементов: %s\nВыберите два элемента, высшая степень окисления которых равна +%d."
                    % ("  ".join("%d) %s" % (i + 1, e[0]) for i, e in enumerate(row)), k))
            return text, "".join(sorted(str(row.index(e) + 1) for e in good)), "set", \
                "Высшая степень окисления элемента главной подгруппы равна номеру группы (кроме фтора и кислорода)."
    return e3(rng)


SALTS = [("NaCl", "хлорида натрия"), ("KNO3", "нитрата калия"), ("CuSO4", "сульфата меди(II)"), ("NaOH", "гидроксида натрия"),
         ("Na2CO3", "карбоната натрия"), ("KCl", "хлорида калия"), ("glucose", "глюкозы")]
# Предельная массовая доля (%) насыщенного раствора при 20 °C — задачи не должны требовать невозможный раствор
W_MAX = {"NaCl": 26, "KNO3": 24, "CuSO4": 17, "NaOH": 50, "Na2CO3": 17, "KCl": 25, "glucose": 45}


def e26(rng):
    for _ in range(200):
        out = _e26(rng)
        if out:
            return out
    raise RuntimeError("e26")


def _e26(rng):
    """Вариант или None, если для выбранного вещества такой раствор невозможен (выше насыщенного)."""
    kind = rng.choice(["mass", "dilute", "mix", "add"])
    formula, name = rng.choice(SALTS)
    ok = lambda *ws: max(ws) <= W_MAX[formula]  # noqa: E731
    if kind == "mass":
        m, w = rng.choice([150, 200, 250, 300, 400, 500]), rng.choice([4, 5, 8, 10, 12, 15, 20])
        if (m * w) % 100 or not ok(w):
            return None
        return ("Сколько граммов %s нужно для приготовления %d г раствора с массовой долей %d %%? Ответ — с точностью до целых."
                % (name, m, w), _ans(m * w / 100), "num", "m = %d · 0,%02d = %s г." % (m, w, _fmt(m * w / 100)))
    if kind == "dilute":
        m, w, add = rng.choice([100, 150, 200, 250]), rng.choice([10, 15, 20, 25]), rng.choice([50, 100, 150, 200, 250])
        res = 100 * m * w / 100 / (m + add)
        if not ok(w):
            return None
        return ("К %d г раствора %s с массовой долей %d %% добавили %d г воды. Вычислите массовую долю вещества в полученном "
                "растворе (%%). Ответ — с точностью до десятых." % (m, name, w, add), _ans(res, 1), "num",
                "Вещества %s г, раствора %d г: %s %%." % (_fmt(m * w / 100), m + add, _fmt(res, 1)))
    if kind == "mix":
        m1, w1, m2, w2 = rng.choice([100, 200, 150]), rng.choice([10, 20]), rng.choice([50, 100, 300]), rng.choice([5, 15, 30])
        res = 100 * (m1 * w1 + m2 * w2) / 100 / (m1 + m2)
        if not ok(w1, w2):
            return None
        return ("Смешали %d г раствора %s с массовой долей %d %% и %d г раствора того же вещества с массовой долей %d %%. "
                "Вычислите массовую долю вещества в полученном растворе (%%). Ответ — с точностью до десятых."
                % (m1, name, w1, m2, w2), _ans(res, 1), "num",
                "Вещества %s + %s г, раствора %d г → %s %%." % (_fmt(m1 * w1 / 100), _fmt(m2 * w2 / 100), m1 + m2, _fmt(res, 1)))
    water, w = rng.choice([180, 270, 360, 450, 160, 240]), rng.choice([10, 20, 25, 40])
    x = water * w / (100 - w)
    if abs(x - round(x, 1)) > 1e-9 or not ok(w):
        return None
    return ("Сколько граммов %s нужно растворить в %d г воды, чтобы получить раствор с массовой долей %d %%? "
            "Ответ — с точностью до десятых." % (name, water, w), _ans(x, 1), "num",
            "x / (x + %d) = 0,%02d → x = %s г." % (water, w, _fmt(x, 1)))


THERMO = [("C + O2 = CO2", "C", 394, "углерода"), ("2H2 + O2 = 2H2O", "H2", 572, "водорода"),
          ("CH4 + 2O2 = CO2 + 2H2O", "CH4", 802, "метана"), ("S + O2 = SO2", "S", 297, "серы"),
          ("2Mg + O2 = 2MgO", "Mg", 1204, "магния"), ("4P + 5O2 = 2P2O5", "P", 3010, "фосфора")]
COEF = {"C": 1, "H2": 2, "CH4": 1, "S": 1, "Mg": 2, "P": 4}


def e27(rng):
    eq, sub, q, name = rng.choice(THERMO)
    k = COEF[sub]
    n = rng.choice([0.25, 0.5, 1, 1.5, 2, 3])
    mass = n * molar_mass(sub)
    heat = q * n / k
    if abs(heat - round(heat)) > 1e-9 or abs(mass - round(mass)) > 1e-9:
        return e27(rng)
    if rng.random() < 0.5:
        return ("По термохимическому уравнению %s + %d кДж вычислите количество теплоты (кДж), которое выделится при "
                "сгорании %d г %s. Ответ — с точностью до целых." % (eq, q, mass, name), _ans(heat), "num",
                "n = %d / %s = %s моль; Q = %d · %s / %d = %d кДж." % (mass, _fmt(molar_mass(sub)), _fmt(n, 2).rstrip("0").rstrip(","), q,
                                                                     _fmt(n, 2).rstrip("0").rstrip(","), k, round(heat)))
    return ("По термохимическому уравнению %s + %d кДж вычислите массу %s (г), при сгорании которой выделилось %d кДж "
            "теплоты. Ответ — с точностью до целых." % (eq, q, name, round(heat)), _ans(mass), "num",
            "n = %d · %d / %d = %s моль; m = %d г." % (round(heat), k, q, _fmt(n, 2).rstrip("0").rstrip(","), round(mass)))


def _trim(x, nd=4):
    """Число без округления промежуточных шагов: 37,5 / 0,375 (без лишних нулей)."""
    return _fmt(x, nd).rstrip("0").rstrip(",")


def e28(rng):
    kind = rng.choice(["impurity", "yield"])
    if kind == "impurity":
        m, imp = rng.choice([50, 100, 125, 200, 250]), rng.choice([10, 20, 25, 40])
        pure = m * (100 - imp) / 100
        n = pure / 100
        res = n * 56
        return ("Какую массу оксида кальция (г) можно получить при полном разложении %d г известняка, содержащего %d %% "
                "примесей? Ответ — с точностью до десятых." % (m, imp), _ans(res, 1), "num",
                "CaCO3 = CaO + CO2. Чистого CaCO3 %s г, n = %s / 100 = %s моль; m(CaO) = %s · 56 = %s г." % (
                    _trim(pure), _trim(pure), _trim(n), _trim(n), _fmt(res, 1)))
    m, y = rng.choice([4.6, 9.2, 13.8, 23]), rng.choice([60, 75, 80, 90])
    n = m / 23
    res = n * 0.5 * 22.4 * y / 100
    return ("При взаимодействии %s г натрия с избытком воды выделился водород, выход которого составил %d %% от "
            "теоретического. Вычислите объём водорода (л, н. у.). Ответ — с точностью до сотых."
            % (_fmt(m, 1).replace(",0", ""), y), _ans(res, 2), "num",
            "2Na + 2H2O = 2NaOH + H2. n(Na) = %s моль, n(H2) = %s моль; V = %s · 22,4 · 0,%02d = %s л." % (
                _fmt(n, 1), _fmt(n / 2, 2), _fmt(n / 2, 2), y, _fmt(res, 2)))


GENERATORS = {("oge", 2): o2, ("oge", 3): o3, ("oge", 4): o4, ("oge", 13): o13, ("oge", 18): o18,
              ("ege", 1): e1, ("ege", 2): e2, ("ege", 3): e3, ("ege", 26): e26, ("ege", 27): e27, ("ege", 28): e28}
# ================================================================ ещё генераторы: классификация, электролиз, гидролиз, равновесие
CLASSES = {
    "основный оксид": ["Na2O", "CaO", "MgO", "BaO", "K2O", "CuO", "FeO", "Li2O"],
    "кислотный оксид": ["SO3", "SO2", "CO2", "P2O5", "N2O5", "SiO2", "CrO3"],
    "амфотерный оксид": ["ZnO", "Al2O3", "BeO", "Cr2O3", "Fe2O3"],
    "несолеобразующий оксид": ["CO", "NO", "N2O"],
    "кислота": ["HNO3", "H2SO4", "HCl", "H3PO4", "H2S", "H2SiO3"],
    "щёлочь": ["NaOH", "KOH", "Ba(OH)2", "LiOH", "Ca(OH)2"],
    "нерастворимое основание": ["Cu(OH)2", "Fe(OH)2", "Mg(OH)2", "Ni(OH)2"],
    "амфотерный гидроксид": ["Al(OH)3", "Zn(OH)2", "Be(OH)2", "Cr(OH)3"],
    "средняя соль": ["NaCl", "K2SO4", "CaCO3", "Na3PO4", "Cu(NO3)2", "BaSO4"],
    "кислая соль": ["NaHCO3", "KHSO4", "NaH2PO4", "Ca(HCO3)2", "K2HPO4"],
    "основная соль": ["(CuOH)2CO3", "MgOHCl", "AlOHCl2", "FeOHSO4"],
}


def _class_pick(rng, wanted, n_items):
    chosen = [rng.choice(CLASSES[c]) for c in wanted]
    others = [f for c, fs in CLASSES.items() if c not in wanted for f in fs]
    items = chosen + rng.sample(others, n_items - len(chosen))
    rng.shuffle(items)
    return chosen, items


def o7(rng):
    pairs = [("основный оксид", "кислоту"), ("кислотный оксид", "щёлочь"), ("амфотерный оксид", "среднюю соль"),
             ("кислую соль", "кислотный оксид"), ("нерастворимое основание", "кислоту"), ("амфотерный гидроксид", "кислую соль")]
    a, b = rng.choice(pairs)
    key = {"кислоту": "кислота", "щёлочь": "щёлочь", "среднюю соль": "средняя соль", "кислую соль": "кислая соль"}
    ka, kb = key.get(a, a), key.get(b, b)
    chosen, items = _class_pick(rng, [ka, kb], 5)
    text = ("Из предложенного перечня выберите %s и %s.\n%s\nЗапишите номера: сначала %s, затем %s."
            % (a, b, "  ".join("%d) %s" % (i + 1, f) for i, f in enumerate(items)), a, b))
    return text, "%d%d" % (items.index(chosen[0]) + 1, items.index(chosen[1]) + 1), "seq", \
        "%s — %s; %s — %s." % (chosen[0], ka, chosen[1], kb)


def e5(rng):
    trio = rng.sample(["кислотный оксид", "амфотерный оксид", "основный оксид", "кислая соль", "основная соль",
                       "амфотерный гидроксид", "щёлочь", "несолеобразующий оксид"], 3)
    chosen, items = _class_pick(rng, trio, 7)
    text = ("Среди веществ выберите: А) %s; Б) %s; В) %s.\n%s\nЗапишите номера под буквами А, Б, В."
            % (trio[0], trio[1], trio[2], "  ".join("%d) %s" % (i + 1, f) for i, f in enumerate(items))))
    return text, "".join(str(items.index(c) + 1) for c in chosen), "seq", \
        "; ".join("%s — %s" % (c, t) for c, t in zip(chosen, trio)) + "."


ANODE = {"KCl": "Cl2", "NaBr": "Br2", "CuCl2": "Cl2", "AgNO3": "O2", "K2SO4": "O2", "ZnSO4": "O2", "FeCl2": "Cl2",
         "NaI": "I2", "Cu(NO3)2": "O2", "CaCl2": "Cl2", "MgSO4": "O2", "Na2SO4": "O2", "KBr": "Br2", "BaCl2": "Cl2"}
CATHODE = {"KCl": "водород", "NaBr": "водород", "CuCl2": "металл", "AgNO3": "металл", "K2SO4": "водород",
           "ZnSO4": "металл и водород", "FeCl2": "металл и водород", "NaI": "водород", "Cu(NO3)2": "металл",
           "CaCl2": "водород", "MgSO4": "водород", "Na2SO4": "водород", "KBr": "водород", "BaCl2": "водород"}


def e20(rng):
    if rng.random() < 0.5:
        options = ["H2", "O2", "Cl2", "Br2", "I2"]
        table, where, why = ANODE, "на инертном аноде", "Галогенид-ионы (кроме F⁻) окисляются; при кислородсодержащих анионах окисляется вода — выделяется O2."
    else:
        options = ["водород", "металл", "металл и водород"]
        table, where, why = CATHODE, "на катоде", ("Металлы до Al — на катоде водород; от Mn до H — металл и водород; "
                                                    "после водорода — только металл.")
    for _ in range(100):
        salts = rng.sample(sorted(table), 4)
        if len({table[s] for s in salts}) >= 2:
            break
    letters = "АБВГ"
    text = ("Установите соответствие между формулой соли и продуктом, который образуется %s при электролизе её водного раствора.\n%s\n%s"
            % (where, "   ".join("%s) %s" % (letters[i], s) for i, s in enumerate(salts)),
               "   ".join("%d) %s" % (i + 1, o) for i, o in enumerate(options))))
    return text, "".join(str(options.index(table[s]) + 1) for s in salts), "seq", why


MEDIUM = {"кислая": ["NH4Cl", "ZnCl2", "AlCl3", "CuSO4", "FeCl3", "NH4NO3", "Fe(NO3)3", "ZnSO4"],
          "щелочная": ["Na2CO3", "K2CO3", "Na2S", "CH3COONa", "K2SiO3", "Na3PO4", "K2SO3", "NaNO2"],
          "нейтральная": ["NaCl", "KNO3", "Na2SO4", "KCl", "BaCl2", "Ca(NO3)2", "KBr", "NaNO3"]}


def e21(rng):
    options = ["кислая", "щелочная", "нейтральная"]
    kinds = [rng.choice(options) for _ in range(4)]
    if len(set(kinds)) < 2:
        return e21(rng)
    salts = []
    for k in kinds:
        f = rng.choice([x for x in MEDIUM[k] if x not in salts])
        salts.append(f)
    letters = "АБВГ"
    text = ("Установите соответствие между формулой соли и средой её водного раствора.\n%s\n%s"
            % ("   ".join("%s) %s" % (letters[i], s) for i, s in enumerate(salts)),
               "   ".join("%d) %s" % (i + 1, o) for i, o in enumerate(options))))
    return text, "".join(str(options.index(k) + 1) for k in kinds), "seq", \
        "Соль слабого основания и сильной кислоты — кислая среда; сильного основания и слабой кислоты — щелочная; сильных — нейтральная."


EQUIL = [("H2(г) + I2(г) ⇄ 2HI(г)", ("H2", 1), ("I2", 1), ("HI", 2)),
         ("2SO2(г) + O2(г) ⇄ 2SO3(г)", ("SO2", 2), ("O2", 1), ("SO3", 2)),
         ("N2(г) + 3H2(г) ⇄ 2NH3(г)", ("N2", 1), ("H2", 3), ("NH3", 2)),
         ("CO(г) + Cl2(г) ⇄ COCl2(г)", ("CO", 1), ("Cl2", 1), ("COCl2", 1))]


def e23(rng):
    eq, (a, ka), (b, kb), (p, kp) = rng.choice(EQUIL)
    x = rng.choice([0.1, 0.2, 0.3])                       # «шаг» реакции, моль/л
    a0 = round(rng.choice([0.4, 0.5, 0.6, 0.7, 0.8, 0.9]), 1)
    b0 = round(rng.choice([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2]), 1)
    a1, b1, p1 = round(a0 - ka * x, 2), round(b0 - kb * x, 2), round(kp * x, 2)
    if min(a1, b1) <= 0:
        return e23(rng)
    ask = rng.choice(["start", "eq"])
    if ask == "eq":
        given = "Исходные концентрации: %s — %s моль/л, %s — %s моль/л; равновесная концентрация %s — %s моль/л." % (
            a, _fmt(a0, 1), b, _fmt(b0, 1), p, _fmt(p1, 1))
        q = "Определите равновесные концентрации %s (X) и %s (Y)." % (a, b)
        xv, yv = a1, b1
    else:
        given = "Равновесные концентрации: %s — %s моль/л, %s — %s моль/л, %s — %s моль/л." % (
            a, _fmt(a1, 1), b, _fmt(b1, 1), p, _fmt(p1, 1))
        q = "Определите исходные концентрации %s (X) и %s (Y)." % (a, b)
        xv, yv = a0, b0
    values = sorted({round(v / 10, 1) for v in range(1, 13)})
    pool = [v for v in values if v not in (xv, yv)]
    opts = sorted(set(rng.sample(pool, 4) + [xv, yv]))
    if len(opts) < 6 or xv == yv:
        return e23(rng)
    text = ("В реактор постоянного объёма поместили %s и %s (продукта %s в начале не было). Установилось равновесие %s\n%s\n%s\n%s"
            % (a, b, p, eq, given, q, "  ".join("%d) %s" % (i + 1, _fmt(v, 1)) for i, v in enumerate(opts))))
    why = "Изменения концентраций пропорциональны коэффициентам: прореагировало %s моль/л %s и %s моль/л %s." % (
        _fmt(ka * x, 1), a, _fmt(kb * x, 1), b)
    return text, "%d%d" % (opts.index(xv) + 1, opts.index(yv) + 1), "seq", why


GENERATORS.update({("oge", 7): o7, ("ege", 5): e5, ("ege", 20): e20, ("ege", 21): e21, ("ege", 23): e23})



# ================================================================ связь, решётки, типы реакций, признаки, ионы, ОВР
def _numbered(items):
    return "  ".join("%d) %s" % (i + 1, f) for i, f in enumerate(items))


def _lines(items):
    return "\n".join("%d) %s" % (i + 1, f) for i, f in enumerate(items))


def _pick_two(rng, good_pool, bad_pool, n_bad=3):
    good = rng.sample(good_pool, 2)
    bad = rng.sample([b for b in bad_pool if b not in good], n_bad)
    items = good + bad
    rng.shuffle(items)
    return items, "".join(sorted(str(items.index(g) + 1) for g in good)), good


# Вещества с одним типом связи (без «смешанных» вроде NH4Cl, KNO3 — в ОГЭ они спорные)
BOND = {
    "ионной связью": ["NaCl", "KBr", "CaO", "MgF2", "K2S", "LiCl", "BaCl2", "Na2O", "CaF2", "KI"],
    "ковалентной полярной связью": ["HCl", "H2O", "NH3", "CO2", "H2S", "SO2", "CH4", "PCl3", "HBr", "SiO2"],
    "ковалентной неполярной связью": ["O2", "N2", "Cl2", "H2", "Br2", "I2", "F2"],
    "металлической связью": ["Na", "Fe", "Cu", "Al", "Mg", "Zn", "K", "Ca"],
}
LATTICE = {
    "молекулярную": ["H2O", "CO2", "I2", "O2", "HCl", "NH3", "CH4", "N2", "Cl2", "H2S"],
    "ионную": ["NaCl", "KF", "CaO", "MgO", "KNO3", "Na2SO4", "BaCl2", "K2CO3"],
    "атомную": ["SiO2", "Si", "SiC", "B", "Ge"],
    "металлическую": ["Fe", "Cu", "Na", "Al", "Zn", "Mg"],
}


def o5(rng):
    if rng.random() < 0.6:
        kind = rng.choice(sorted(BOND))
        others = [f for k, fs in BOND.items() if k != kind for f in fs]
        items, ans, good = _pick_two(rng, BOND[kind], others)
        return ("Из предложенного перечня выберите два вещества с %s.\n%s" % (kind, _numbered(items)), ans, "set",
                "Ионная — металл + неметалл; ковалентная полярная — разные неметаллы; неполярная — одинаковые атомы "
                "неметалла; металлическая — в металлах. Ответ: %s." % ", ".join(good))
    kind = rng.choice(sorted(LATTICE))
    others = [f for k, fs in LATTICE.items() if k != kind for f in fs]
    items, ans, good = _pick_two(rng, LATTICE[kind], others)
    return ("Из предложенного перечня выберите два вещества, которые имеют %s кристаллическую решётку.\n%s"
            % (kind, _numbered(items)), ans, "set",
            "Молекулярная — газы, летучие вещества, I2; ионная — соли, оксиды и гидроксиды активных металлов; атомная — "
            "алмаз, Si, SiO2, SiC, B; металлическая — металлы. Ответ: %s." % ", ".join(good))


# (уравнение, тип, ОВР?)
REACTIONS = [
    ("2Mg + O2 = 2MgO", "соединения", True), ("CaO + H2O = Ca(OH)2", "соединения", False),
    ("SO3 + H2O = H2SO4", "соединения", False), ("4P + 5O2 = 2P2O5", "соединения", True),
    ("N2 + 3H2 = 2NH3", "соединения", True), ("2Fe + 3Cl2 = 2FeCl3", "соединения", True),
    ("Na2O + CO2 = Na2CO3", "соединения", False),
    ("CaCO3 = CaO + CO2", "разложения", False), ("2H2O = 2H2 + O2", "разложения", True),
    ("2KClO3 = 2KCl + 3O2", "разложения", True), ("Cu(OH)2 = CuO + H2O", "разложения", False),
    ("NH4Cl = NH3 + HCl", "разложения", False), ("2Fe(OH)3 = Fe2O3 + 3H2O", "разложения", False),
    ("2HgO = 2Hg + O2", "разложения", True),
    ("Zn + 2HCl = ZnCl2 + H2", "замещения", True), ("Fe + CuSO4 = FeSO4 + Cu", "замещения", True),
    ("2Na + 2H2O = 2NaOH + H2", "замещения", True), ("CuO + H2 = Cu + H2O", "замещения", True),
    ("Cl2 + 2KBr = 2KCl + Br2", "замещения", True), ("2Al + Fe2O3 = Al2O3 + 2Fe", "замещения", True),
    ("Mg + H2SO4 = MgSO4 + H2", "замещения", True),
    ("NaOH + HCl = NaCl + H2O", "обмена", False), ("BaCl2 + Na2SO4 = BaSO4 + 2NaCl", "обмена", False),
    ("CuO + 2HNO3 = Cu(NO3)2 + H2O", "обмена", False), ("AgNO3 + KCl = AgCl + KNO3", "обмена", False),
    ("Fe(OH)3 + 3HCl = FeCl3 + 3H2O", "обмена", False), ("Na2CO3 + 2HCl = 2NaCl + H2O + CO2", "обмена", False),
]


def _reaction_types(rng, exam_word):
    if rng.random() < 0.7:
        kind = rng.choice(["соединения", "разложения", "замещения", "обмена"])
        items, ans, good = _pick_two(rng, [r[0] for r in REACTIONS if r[1] == kind],
                                     [r[0] for r in REACTIONS if r[1] != kind])
        return ("Из предложенного перечня выберите две реакции %s.\n%s" % (kind, _lines(items)), ans, "set",
                "Соединения: из нескольких веществ одно. Разложения: из одного несколько. Замещения: простое + сложное → "
                "простое + сложное. Обмена: два сложных обмениваются частями.")
    ovr = rng.random() < 0.5
    items, ans, good = _pick_two(rng, [r[0] for r in REACTIONS if r[2] == ovr], [r[0] for r in REACTIONS if r[2] != ovr])
    return ("Из предложенного перечня выберите две реакции, которые %sявляются окислительно-восстановительными.\n%s"
            % ("" if ovr else "не ", _lines(items)), ans, "set",
            "ОВР — меняются степени окисления: всегда, если участвует или образуется простое вещество. "
            "Реакции обмена ОВР не бывают.")


def o11(rng):
    return _reaction_types(rng, "ОГЭ")


def e17(rng):
    return _reaction_types(rng, "ЕГЭ")


SIGNS = ["выделение газа", "образование белого осадка", "образование голубого осадка", "образование бурого осадка",
         "растворение осадка"]
SIGN_PAIRS = [
    ("CuSO4 и NaOH", 2), ("CuCl2 и KOH", 2), ("Cu(NO3)2 и NaOH", 2),
    ("FeCl3 и NaOH", 3), ("Fe2(SO4)3 и KOH", 3), ("Fe(NO3)3 и NaOH", 3),
    ("BaCl2 и Na2SO4", 1), ("AgNO3 и NaCl", 1), ("CaCl2 и Na2CO3", 1), ("Ba(NO3)2 и H2SO4", 1),
    ("Na2CO3 и HCl", 0), ("Zn и H2SO4 (р-р)", 0), ("K2CO3 и HNO3", 0), ("Mg и HCl", 0),
    ("Cu(OH)2 и HCl", 4), ("Fe(OH)3 и H2SO4", 4), ("Mg(OH)2 и HNO3", 4),
]


def o12(rng):
    for _ in range(100):
        pairs = rng.sample(SIGN_PAIRS, 3)
        if len({p[1] for p in pairs}) >= 2:
            break
    letters = "АБВ"
    text = ("Установите соответствие между реагирующими веществами и признаком протекающей между ними реакции.\n%s\n%s\n"
            "Цифры в ответе могут повторяться." % ("\n".join("%s) %s" % (letters[i], p[0]) for i, p in enumerate(pairs)) + "\n",
                                                    "\n".join("%d) %s" % (i + 1, s) for i, s in enumerate(SIGNS))))
    return text, "".join(str(p[1] + 1) for p in pairs), "seq", "; ".join(
        "%s — %s" % (p[0], SIGNS[p[1]]) for p in pairs) + "."


# сокращённое ионное уравнение → пары, которым оно соответствует, и пары-ловушки (другое уравнение или нет реакции)
IONIC = [
    ("Ba²⁺ + SO4²⁻ = BaSO4↓", ["BaCl2 и Na2SO4", "Ba(NO3)2 и K2SO4", "BaCl2 и H2SO4"],
     ["Ba(OH)2 и H2SO4", "BaCO3 и H2SO4", "BaCl2 и Na2CO3", "Ba(NO3)2 и NaCl"]),
    ("H⁺ + OH⁻ = H2O", ["HCl и NaOH", "HNO3 и KOH", "H2SO4 и NaOH"],
     ["HCl и Cu(OH)2", "H2SO4 и Ba(OH)2", "H2SiO3 и NaOH", "HCl и Fe(OH)3"]),
    ("Ag⁺ + Cl⁻ = AgCl↓", ["AgNO3 и NaCl", "AgNO3 и HCl", "AgNO3 и KCl"],
     ["AgNO3 и KNO3", "Ag и HCl", "AgNO3 и NaBr"]),
    ("CO3²⁻ + 2H⁺ = H2O + CO2↑", ["Na2CO3 и HCl", "K2CO3 и HNO3", "Na2CO3 и H2SO4"],
     ["CaCO3 и HCl", "Na2CO3 и NaOH", "Na2SO4 и HCl"]),
    ("Cu²⁺ + 2OH⁻ = Cu(OH)2↓", ["CuSO4 и NaOH", "CuCl2 и KOH", "Cu(NO3)2 и NaOH"],
     ["CuO и NaOH", "CuSO4 и Ba(OH)2", "Cu(OH)2 и HCl"]),
    ("Fe³⁺ + 3OH⁻ = Fe(OH)3↓", ["FeCl3 и NaOH", "Fe(NO3)3 и KOH"],
     ["Fe2(SO4)3 и Ba(OH)2", "FeCl2 и NaOH", "Fe2O3 и NaOH"]),
]


def o14(rng):
    eq, good, bad = rng.choice(IONIC)
    foreign = [g for e, gs, _ in IONIC if e != eq for g in gs]
    items, ans, chosen = _pick_two(rng, good, bad + rng.sample(foreign, 2))
    return ("Выберите две пары веществ, взаимодействию которых в растворе соответствует сокращённое ионное уравнение\n"
            "%s\n%s" % (eq, _lines(items)), ans, "set",
            "Подходят пары растворимых сильных электролитов, где других осадков, газов и воды не образуется: %s. "
            "Нерастворимые вещества (осадки, оксиды) в ионном уравнении пишут целиком." % ", ".join(chosen))


def _state_label(el, v):
    return "%s(%s)" % (el, _sgn(v))


def _ox_schemes(rng, n, allow_same=False):
    el, items = rng.choice([o for o in OX if len({v for _, v in o[1]}) >= 3])
    states = sorted({v for _, v in items})
    out = []
    for _ in range(200):
        a, b = rng.choice(states), rng.choice(states)
        if a == b and not allow_same:
            continue
        if (a, b) in [(x, y) for x, y, _ in out]:
            continue
        role = 0 if b < a else (1 if b > a else 2)        # 0 — окислитель, 1 — восстановитель, 2 — не меняется
        out.append((a, b, role))
        if len(out) == n:
            break
    return el, out


def o15(rng):
    for _ in range(50):
        el, schemes = _ox_schemes(rng, 3)
        if len({r for _, _, r in schemes}) == 2:
            break
    letters = "АБВ"
    text = ("Установите соответствие между схемой изменения степени окисления %s и свойством, которое этот элемент проявляет.\n%s\n\n"
            "1) окислитель\n2) восстановитель\nЦифры в ответе могут повторяться." % (
                NAMES_EL[el], "\n".join("%s) %s → %s" % (letters[i], _state_label(el, a), _state_label(el, b))
                                        for i, (a, b, _) in enumerate(schemes))))
    return text, "".join(str(r + 1) for _, _, r in schemes), "seq", \
        "Степень окисления понижается — элемент принимает электроны, он окислитель; повышается — отдаёт, восстановитель."


def e19(rng):
    """Схемы через формулы веществ: HCl → Cl2, SO2 → SO3, HCl → KCl (без изменения степени окисления)."""
    for _ in range(100):
        el, items = rng.choice(OX)
        by_state = {}
        for f, v in items:
            by_state.setdefault(v, []).append(f)
        schemes = []
        for _ in range(3):
            a = rng.choice(sorted(by_state))
            same = len(by_state[a]) > 1 and rng.random() < 0.3
            b = a if same else rng.choice([v for v in by_state if v != a])
            fa = rng.choice(by_state[a])
            fb = rng.choice([f for f in by_state[b] if f != fa])
            schemes.append((fa, fb, 0 if b < a else (1 if b > a else 2), a, b))
        if len({(x[0], x[1]) for x in schemes}) == 3 and len({x[2] for x in schemes}) >= 2:
            break
    letters = "АБВ"
    text = ("Установите соответствие между схемой превращения и свойством, которое проявляет в ней атом %s.\n%s\n\n"
            "1) окислитель\n2) восстановитель\n3) не проявляет окислительно-восстановительных свойств\n"
            "Цифры в ответе могут повторяться." % (
                NAMES_EL[el], "\n".join("%s) %s → %s" % (letters[i], x[0], x[1]) for i, x in enumerate(schemes))))
    why = "; ".join("%s → %s: %s → %s" % (x[0], x[1], _sgn(x[3]), _sgn(x[4])) for x in schemes)
    return text, "".join(str(x[2] + 1) for x in schemes), "seq", \
        why + ". Понижение степени окисления — окислитель, повышение — восстановитель, без изменения — не проявляет."


# различение пар веществ: 1 — реактив различает, 0 — нет, None — спорно (такой реактив с этой парой не даём)
REAGENTS = ["AgNO3", "BaCl2", "HCl", "NaOH", "Na2SO4"]
DISTINGUISH = [
    ("NaCl и NaNO3", {"AgNO3": 1, "BaCl2": 0, "HCl": 0, "NaOH": 0, "Na2SO4": 0}, "AgNO3 — белый осадок AgCl только с NaCl"),
    ("Na2SO4 и NaNO3", {"AgNO3": None, "BaCl2": 1, "HCl": 0, "NaOH": 0, "Na2SO4": 0}, "BaCl2 — белый осадок BaSO4"),
    ("Na2CO3 и Na2SO4", {"AgNO3": None, "BaCl2": 0, "HCl": 1, "NaOH": 0, "Na2SO4": 0}, "HCl — газ CO2 только с карбонатом"),
    ("NH4Cl и KCl", {"AgNO3": 0, "BaCl2": 0, "HCl": 0, "NaOH": 1, "Na2SO4": 0}, "NaOH — при нагревании запах аммиака"),
    ("HCl и HNO3", {"AgNO3": 1, "BaCl2": 0, "HCl": 0, "NaOH": 0, "Na2SO4": 0}, "AgNO3 — белый осадок с HCl"),
    ("MgCl2 и BaCl2", {"AgNO3": 0, "BaCl2": 0, "HCl": 0, "NaOH": 1, "Na2SO4": 1},
     "NaOH — белый осадок Mg(OH)2; Na2SO4 — белый осадок BaSO4"),
    ("CuCl2 и NaCl", {"AgNO3": 0, "BaCl2": 0, "HCl": 0, "NaOH": 1, "Na2SO4": 0}, "NaOH — голубой осадок Cu(OH)2"),
    ("Na2CO3 и NaOH", {"AgNO3": None, "BaCl2": 1, "HCl": 1, "NaOH": 0, "Na2SO4": 0},
     "HCl — газ с карбонатом; BaCl2 — осадок BaCO3"),
    ("H2SO4 и HNO3", {"AgNO3": None, "BaCl2": 1, "HCl": 0, "NaOH": 0, "Na2SO4": 0}, "BaCl2 — белый осадок BaSO4"),
    ("FeCl2 и FeCl3", {"AgNO3": 0, "BaCl2": 0, "HCl": 0, "NaOH": 1, "Na2SO4": 0},
     "NaOH — серо-зелёный осадок Fe(OH)2 и бурый Fe(OH)3"),
    ("K2SO4 и KCl", {"AgNO3": None, "BaCl2": 1, "HCl": 0, "NaOH": 0, "Na2SO4": 0}, "BaCl2 — белый осадок BaSO4"),
    ("Ba(NO3)2 и KNO3", {"AgNO3": 0, "BaCl2": 0, "HCl": 0, "NaOH": 0, "Na2SO4": 1}, "Na2SO4 — белый осадок BaSO4"),
]


def _distinguish(rng, n_pairs):
    letters = "АБВГ"
    for _ in range(500):
        reagents = rng.sample(REAGENTS, 4)
        pairs = rng.sample(DISTINGUISH, n_pairs)
        ok = True
        answer = ""
        for name, table, _ in pairs:
            vals = [table[r] for r in reagents]
            if None in vals or vals.count(1) != 1:
                ok = False
                break
            answer += str(vals.index(1) + 1)
        if ok:
            text = ("Установите соответствие между двумя веществами и реактивом, с помощью которого их можно различить.\n"
                    "%s\n\n%s\nЦифры в ответе могут повторяться." % (
                        "\n".join("%s) %s" % (letters[i], p[0]) for i, p in enumerate(pairs)),
                        "\n".join("%d) %s" % (i + 1, r) for i, r in enumerate(reagents))))
            return text, answer, "seq", "; ".join("%s: %s" % (p[0], p[2]) for p in pairs) + "."
    raise RuntimeError("no distinguishing set")


def o17(rng):
    return _distinguish(rng, 3)


def e24(rng):
    return _distinguish(rng, 4)


def e4(rng):
    molecular = LATTICE["молекулярную"]
    non_molecular = LATTICE["ионную"] + LATTICE["атомную"] + LATTICE["металлическую"]
    if rng.random() < 0.5:
        items, ans, good = _pick_two(rng, molecular, non_molecular)
        q = "молекулярного строения"
    else:
        items, ans, good = _pick_two(rng, non_molecular, molecular)
        q = "немолекулярного строения"
    return ("Из предложенного перечня выберите два вещества %s.\n%s" % (q, _numbered(items)), ans, "set",
            "Молекулярное строение — вещества из отдельных молекул (газы, жидкости, I2, сахар). Немолекулярное — ионные "
            "(соли, оксиды металлов), атомные (Si, SiO2, SiC, B) и металлы. Ответ: %s." % ", ".join(good))


# скорость реакции: (уравнение, есть ли газ-реагент, есть ли твёрдый реагент, есть ли реагент в растворе)
RATE = [
    ("Zn(тв) + 2HCl(р-р) = ZnCl2 + H2", False, True, True),
    ("CaCO3(тв) + 2HCl(р-р) = CaCl2 + H2O + CO2", False, True, True),
    ("2SO2(г) + O2(г) ⇄ 2SO3(г)", True, False, False),
    ("N2(г) + 3H2(г) ⇄ 2NH3(г)", True, False, False),
    ("C(тв) + O2(г) = CO2(г)", True, True, False),
    ("Fe(тв) + H2SO4(р-р) = FeSO4 + H2", False, True, True),
    ("2H2(г) + O2(г) = 2H2O(г)", True, False, False),
]


def e18(rng):
    eq, gas, solid, solution = rng.choice(RATE)
    up, down = ["повышение температуры"], ["понижение температуры"]
    if gas:
        up += ["повышение давления", "увеличение концентрации кислорода" if "O2(г)" in eq else "уменьшение объёма сосуда"]
        down += ["понижение давления", "увеличение объёма сосуда"]
    if solid:
        up += ["измельчение твёрдого вещества"]
    if solution:
        up += ["увеличение концентрации кислоты"]
        down += ["разбавление раствора кислоты водой"]
    up = sorted(set(up))
    if len(up) < 2:
        return e18(rng)
    items, ans, good = _pick_two(rng, up, down + ["использование ингибитора"], n_bad=min(3, len(down) + 1))
    return ("Из предложенного перечня выберите два внешних воздействия, которые приводят к увеличению скорости реакции\n"
            "%s\n%s" % (eq, _lines(items)), ans, "set",
            "Скорость растёт при нагревании, увеличении концентрации (для газов — давления), измельчении твёрдого вещества. "
            "Ответ: %s." % ", ".join(good))


# ОГЭ 22 — расчёт по уравнению (развёрнутый ответ: решение на бумаге, сверка с образцом)
PRECIPITATE = [
    ("BaCl2", "Na2SO4", "BaSO4", "BaCl2 + Na2SO4 = BaSO4↓ + 2NaCl", "хлорида бария", "сульфата натрия"),
    ("AgNO3", "NaCl", "AgCl", "AgNO3 + NaCl = AgCl↓ + NaNO3", "нитрата серебра", "хлорида натрия"),
    ("CuSO4", "NaOH", "Cu(OH)2", "CuSO4 + 2NaOH = Cu(OH)2↓ + Na2SO4", "сульфата меди(II)", "гидроксида натрия"),
    ("CaCl2", "Na2CO3", "CaCO3", "CaCl2 + Na2CO3 = CaCO3↓ + 2NaCl", "хлорида кальция", "карбоната натрия"),
    ("FeCl3", "NaOH", "Fe(OH)3", "FeCl3 + 3NaOH = Fe(OH)3↓ + 3NaCl", "хлорида железа(III)", "гидроксида натрия"),
    ("Na2SO4", "BaCl2", "BaSO4", "Na2SO4 + BaCl2 = BaSO4↓ + 2NaCl", "сульфата натрия", "хлорида бария"),
]


def o22(rng):
    for _ in range(200):
        sub, reag, prod, eq, sub_name, reag_name = rng.choice(PRECIPITATE)
        n = rng.choice([0.02, 0.04, 0.05, 0.1, 0.15, 0.2, 0.25])
        w = rng.choice([4, 5, 8, 10, 12, 15, 20])
        m_sub = n * molar_mass(sub)
        m_sol = m_sub * 100 / w
        m_prod = n * molar_mass(prod)
        if abs(m_sol - round(m_sol, 1)) > 1e-9 or m_sol > 600 or abs(m_prod * 100 - round(m_prod * 100)) > 1e-6:
            continue
        mm = lambda f: _fmt(molar_mass(f), 1 if molar_mass(f) % 1 else 0)  # noqa: E731
        why = ("1) %s\n2) m(%s) = %s · %d / 100 = %s г; n(%s) = %s / %s = %s моль\n"
               "3) n(%s) = n(%s) = %s моль; m(%s) = %s · %s = %s г\nОтвет: %s г." % (
                   eq, sub, _fmt(m_sol, 1).replace(",0", ""), w, _fmt(m_sub, 2).rstrip("0").rstrip(","), sub,
                   _fmt(m_sub, 2).rstrip("0").rstrip(","), mm(sub), _fmt(n, 2).rstrip("0").rstrip(","), prod, sub,
                   _fmt(n, 2).rstrip("0").rstrip(","), prod, _fmt(n, 2).rstrip("0").rstrip(","), mm(prod), _fmt(m_prod, 2).rstrip("0").rstrip(","),
                   _fmt(m_prod, 2).rstrip("0").rstrip(",")))
        text = ("К %s г раствора %s с массовой долей %d %% добавили избыток раствора %s. Вычислите массу выпавшего осадка. "
                "Запишите уравнение реакции и подробное решение." % (_fmt(m_sol, 1).replace(",0", ""), sub_name, w, reag_name))
        return text, _ans(m_prod, 2), "long", why
    return o22(rng)


GENERATORS.update({("oge", 5): o5, ("oge", 11): o11, ("oge", 12): o12, ("oge", 14): o14, ("oge", 15): o15,
                   ("oge", 17): o17, ("oge", 22): o22, ("ege", 4): e4, ("ege", 17): e17, ("ege", 18): e18,
                   ("ege", 19): e19, ("ege", 24): e24})



# ================================================================ ОГЭ 1, 6, 8, 9, 10, 16, 19, 20
# ОГЭ 1: о веществе как о простом веществе или как о химическом элементе
SUBSTANCE_ELEMENT = {
    "кислороде": (
        ["Кислород поддерживает горение.", "Кислород — газ без цвета и запаха.", "Кислород плохо растворяется в воде.",
         "Кислородом дышат живые организмы.", "Кислород в лаборатории получают разложением перманганата калия."],
        ["Кислород входит в состав воды.", "Кислород — элемент VIA-группы.", "Кислород входит в состав углекислого газа.",
         "Массовая доля кислорода в земной коре — около 49 %.", "В молекуле озона три атома кислорода."]),
    "железе": (
        ["Железо притягивается магнитом.", "Железо — серебристо-серый металл.", "Железо ржавеет во влажном воздухе.",
         "Железо проводит электрический ток.", "Железо плавится при 1539 °C."],
        ["Железо входит в состав гемоглобина.", "В оксиде железа(III) железо имеет степень окисления +3.",
         "Железо находится в 4-м периоде.", "Железо входит в состав магнитного железняка Fe3O4.",
         "В организме взрослого человека около 4 г железа."]),
    "азоте": (
        ["Азот — основная часть воздуха по объёму.", "Азот — газ без цвета и запаха.",
         "Жидким азотом быстро замораживают продукты.", "Азот при обычных условиях малоактивен."],
        ["Азот входит в состав белков.", "Азот входит в состав аммиака.", "Азот — элемент VA-группы.",
         "Азот входит в состав нитратов, которые используют как удобрения."]),
    "кальции": (
        ["Кальций — серебристо-белый металл.", "Кальций хранят под слоем керосина.",
         "Кальций энергично реагирует с водой.", "Кальций проводит электрический ток."],
        ["Кальций входит в состав костей и зубов.", "Кальций входит в состав мела CaCO3.",
         "Суточная потребность человека в кальции — около 1 г.", "Кальций — элемент 4-го периода."]),
    "водороде": (
        ["Водород — самый лёгкий газ.", "Водород горит в кислороде.", "Водород плохо растворяется в воде.",
         "Водород рассматривают как экологичное топливо."],
        ["Водород входит в состав воды.", "Водород входит в состав всех кислот.",
         "Водород — первый элемент Периодической системы.", "Водород входит в состав метана."]),
    "хлоре": (
        ["Хлор — жёлто-зелёный газ с резким запахом.", "Хлор ядовит.", "Хлором обеззараживают воду.",
         "Хлор тяжелее воздуха."],
        ["Хлор входит в состав поваренной соли.", "Хлор входит в состав соляной кислоты.",
         "Хлор — элемент VIIA-группы.", "Ионы хлора есть в желудочном соке."]),
}


def o1(rng):
    name = rng.choice(sorted(SUBSTANCE_ELEMENT))
    simple, element = SUBSTANCE_ELEMENT[name]
    if rng.random() < 0.5:
        items, ans, good = _pick_two(rng, simple, element)
        q, other = "как о простом веществе", "химическом элементе"
    else:
        items, ans, good = _pick_two(rng, element, simple)
        q, other = "как о химическом элементе", "простом веществе"
    return ("Выберите два высказывания, в которых говорится о %s %s.\n%s" % (name, q, _lines(items)), ans, "set",
            "Простое вещество — это то, что можно потрогать, смешать, сжечь: цвет, запах, плавление, реакции. Элемент — "
            "вид атомов: «входит в состав», место в таблице, степень окисления. Остальные высказывания — о %s." % other)


# ОГЭ 6: утверждения, верные для обоих элементов — истинность вычисляется по положению в ПС
METALS = {"Li", "Be", "Na", "Mg", "Al", "K", "Ca", "Ga", "Rb", "Sr"}
NONMETALS = {"B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Se", "Br", "I"}
OXIDE = {1: "R2O", 2: "RO", 3: "R2O3", 4: "RO2", 5: "R2O5", 6: "RO3", 7: "R2O7"}


def _o6_statements(a, b):
    (sa, _, pa, ga), (sb, _, pb, gb) = a, b
    st = [("В их атомах по %s." % _plural(pa, "электронный слой", "электронных слоя", "электронных слоёв"), pa == pb),
          ("На внешнем слое их атомов по %s." % _plural(ga, "электрону", "электрона", "электронов").replace(
              "1 электрону", "одному электрону"), ga == gb),
          ("Их атомы содержат одинаковое число протонов.", False)]
    kind_a = "металлам" if sa in METALS else "неметаллам"
    st.append(("Они относятся к %s." % kind_a, (sa in METALS) == (sb in METALS)))
    if sa not in ("O", "F"):
        st.append(("Они образуют высшие оксиды состава %s." % OXIDE[ga], ga == gb and sb not in ("O", "F")))
        st.append(("Их высшая степень окисления равна +%d." % ga, ga == gb and sb not in ("O", "F")))
    volatile = lambda e: e[0] in NONMETALS and e[3] >= 4  # noqa: E731
    st.append(("Они образуют летучие водородные соединения.", volatile(a) and volatile(b)))
    st.append(("Их атомы имеют одинаковый радиус.", False))
    return st


def o6(rng):
    pool = [e for e in MAIN if e[0] in METALS | NONMETALS]
    names = {e[0]: e for e in pool}
    for _ in range(500):
        a = rng.choice(pool)
        same = [e for e in pool if e != a and (e[2] == a[2] or e[3] == a[3])]
        b = rng.choice(same)
        st = _o6_statements(a, b)
        true = [x for x, v in st if v]
        false = [x for x, v in st if not v]
        if len(true) >= 2 and len(false) >= 3:
            items, ans, good = _pick_two(rng, true, false)
            return ("Выберите два утверждения, верных и для %s, и для %s.\n%s" % (a[0], b[0], _lines(items)), ans, "set",
                    "%s: %d-й период, %s группа (A); %s: %d-й период, %s группа (A). Число слоёв = период, внешних "
                    "электронов = номер группы, высший оксид и степень окисления — по группе (кроме O и F)."
                    % (a[0], a[2], ["", "I", "II", "III", "IV", "V", "VI", "VII"][a[3]],
                       b[0], b[2], ["", "I", "II", "III", "IV", "V", "VI", "VII"][b[3]]))
    raise RuntimeError("o6")


# ОГЭ 8 и 10: с чем реагирует вещество. Для каждого — кто точно реагирует (да) и точно нет; спорного здесь нет.
REACTIVITY = {
    "HCl": ("соляная кислота",
            ["Zn", "Fe", "Mg", "CuO", "MgO", "CaO", "NaOH", "KOH", "Ca(OH)2", "Cu(OH)2", "AgNO3", "Na2CO3"],
            ["Cu", "Ag", "CO2", "SO2", "SiO2", "P2O5", "HNO3", "H2SO4", "BaCl2", "NaCl", "Na2SO4", "KNO3", "FeCl3",
             "CuSO4", "O2", "S"]),
    "H2SO4 (разб.)": ("разбавленная серная кислота",
                      ["Zn", "Fe", "Mg", "CuO", "MgO", "CaO", "NaOH", "KOH", "Cu(OH)2", "BaCl2", "Na2CO3"],
                      ["Cu", "Ag", "CO2", "SO2", "SiO2", "P2O5", "HCl", "HNO3", "NaCl", "Na2SO4", "KNO3", "FeCl3",
                       "CuSO4", "O2", "S"]),
    "NaOH": ("раствор гидроксида натрия",
             ["CO2", "SO2", "P2O5", "HCl", "HNO3", "H2SO4", "FeCl3", "CuSO4", "Zn", "AgNO3"],
             ["Fe", "Mg", "Cu", "Ag", "CuO", "MgO", "CaO", "KOH", "Ca(OH)2", "Cu(OH)2", "BaCl2", "NaCl", "Na2SO4",
              "KNO3", "Na2CO3", "O2"]),
    "CaO": ("оксид кальция",
            ["H2O", "CO2", "SO2", "SiO2", "P2O5", "HCl", "HNO3", "H2SO4"],
            ["Zn", "Fe", "Mg", "Cu", "Ag", "CuO", "MgO", "NaOH", "KOH", "Ca(OH)2", "Cu(OH)2", "NaCl", "Na2SO4",
             "KNO3", "O2", "BaCl2"]),
    "CO2": ("оксид углерода(IV)",
            ["NaOH", "KOH", "Ca(OH)2", "CaO", "H2O", "Mg"],
            ["HCl", "HNO3", "H2SO4", "SO2", "SiO2", "P2O5", "Cu", "Ag", "Fe", "Zn", "CuO", "NaCl", "Na2SO4", "KNO3",
             "O2", "S", "BaCl2", "FeCl3", "CuSO4", "AgNO3"]),
    "CuSO4": ("раствор сульфата меди(II)",
              ["Fe", "Zn", "Mg", "NaOH", "KOH", "Ca(OH)2", "BaCl2"],
              ["Cu", "Ag", "HCl", "HNO3", "H2SO4", "NaCl", "Na2SO4", "KNO3", "CO2", "SO2", "SiO2", "O2", "CuO", "MgO",
               "FeCl3"]),
    "Fe": ("железо",
           ["HCl", "H2SO4", "CuSO4", "O2", "S", "AgNO3"],
           ["NaOH", "KOH", "Ca(OH)2", "MgO", "CaO", "CO2", "SO2", "SiO2", "NaCl", "Na2SO4", "KNO3", "BaCl2", "Zn",
            "Mg", "Cu", "Ag", "Na2CO3"]),
}


def o8(rng):
    x = rng.choice(sorted(REACTIVITY))
    name, yes, no = REACTIVITY[x]
    items, ans, good = _pick_two(rng, yes, no)
    return ("Выберите два вещества, с которыми реагирует %s.\n%s" % (name, _numbered(items)), ans, "set",
            "%s реагирует с %s. Металлы после водорода (Cu, Ag) не вытесняют его из кислот; основные оксиды и основания "
            "реагируют с кислотами и кислотными оксидами; соли — если выпадает осадок, выделяется газ или металл "
            "активнее." % (name[0].upper() + name[1:], " и ".join(good)))


def o10(rng):
    return _match_reagents(rng, 3, 4)


def e7(rng):
    return _match_reagents(rng, 4, 5)


def _match_reagents(rng, n_subs, n_opts):
    """Для каждого вещества — своя пара реагентов, с обоими из которых оно реагирует; пара не подходит другим веществам.
    Используются только реагенты, про которые для всех трёх веществ точно известно «да» или «нет»."""
    from itertools import combinations
    for _ in range(500):
        subs = rng.sample(sorted(REACTIVITY), n_subs)
        known = set.intersection(*[set(REACTIVITY[x][1]) | set(REACTIVITY[x][2]) for x in subs])
        yes = {x: set(REACTIVITY[x][1]) for x in subs}
        fits = lambda pair, x: all(r in yes[x] for r in pair)  # noqa: E731
        options, ok = [], True
        for x in subs:
            cands = [pr for pr in combinations(sorted(yes[x] & known), 2)
                     if not any(fits(pr, y) for y in subs if y != x) and pr not in options]
            if not cands:
                ok = False
                break
            options.append(rng.choice(cands))
        decoys = [pr for pr in combinations(sorted(known), 2) if not any(fits(pr, y) for y in subs)]
        if not ok or len(decoys) < n_opts - n_subs:
            continue
        options += rng.sample(decoys, n_opts - n_subs)
        rng.shuffle(options)
        answer = ""
        for x in subs:
            good = [i for i, o in enumerate(options) if fits(o, x)]
            assert len(good) == 1
            answer += str(good[0] + 1)
        letters = "АБВГ"
        text = ("Установите соответствие между веществом и реагентами, с каждым из которых оно может взаимодействовать.\n"
                "%s\n\n%s\nЦифры в ответе могут повторяться." % (
                    "\n".join("%s) %s" % (letters[i], x) for i, x in enumerate(subs)),
                    "\n".join("%d) %s, %s" % (i + 1, o[0], o[1]) for i, o in enumerate(options))))
        why = "; ".join("%s — с %s" % (x, ", ".join(options[int(c) - 1])) for x, c in zip(subs, answer))
        return text, answer, "seq", why + ". В остальных парах хотя бы одно вещество с ним не реагирует."
    raise RuntimeError("match_reagents")


# ОГЭ 9: реагенты → продукты; семьи реакций с похожими продуктами
PRODUCT_FAMILIES = [
    ([("Fe + HCl", "FeCl2 + H2"), ("Fe2O3 + HCl", "FeCl3 + H2O"), ("Fe(OH)2 + HCl", "FeCl2 + H2O"),
      ("Fe + Cl2", "FeCl3"), ("Fe(OH)3 + HCl", "FeCl3 + H2O")], ["FeCl3 + H2", "FeCl2", "FeCl2 + Cl2"]),
    ([("Cu + HNO3 (конц.)", "Cu(NO3)2 + NO2 + H2O"), ("Cu + HNO3 (разб.)", "Cu(NO3)2 + NO + H2O"),
      ("CuO + HNO3", "Cu(NO3)2 + H2O"), ("Cu + H2SO4 (конц.)", "CuSO4 + SO2 + H2O"), ("CuO + H2SO4", "CuSO4 + H2O")],
     ["Cu(NO3)2 + H2", "CuSO4 + H2", "Cu(NO3)2 + NH3"]),
    ([("S + O2", "SO2"), ("SO2 + O2 (кат.)", "SO3"), ("SO3 + H2O", "H2SO4"), ("SO2 + H2O", "H2SO3"),
      ("H2S + O2 (избыток)", "SO2 + H2O")], ["SO3 + H2O", "H2SO4 + H2", "S + H2O"]),
    ([("CO2 + NaOH (избыток)", "Na2CO3 + H2O"), ("CO2 (избыток) + NaOH", "NaHCO3"), ("NaHCO3 + NaOH", "Na2CO3 + H2O"),
      ("Na2CO3 + HCl (избыток)", "NaCl + H2O + CO2"), ("Na2O + CO2", "Na2CO3")], ["NaHCO3 + H2O", "Na2O + CO2", "NaCl + H2CO3"]),
    ([("Al + HCl", "AlCl3 + H2"), ("Al2O3 + HCl", "AlCl3 + H2O"), ("Al(OH)3 + NaOH (р-р)", "Na[Al(OH)4]"),
      ("Al + O2", "Al2O3"), ("Al(OH)3 + HCl", "AlCl3 + H2O")], ["Al2O3 + H2", "AlCl3", "Al(OH)3 + NaCl"]),
]


def o9(rng):
    for _ in range(500):
        fam, decoys = rng.choice(PRODUCT_FAMILIES)
        chosen = rng.sample(fam, 3)
        products = sorted({p for _, p in chosen})
        extra = [p for _, p in fam if p not in products] + [d for d in decoys if d not in products]
        options = products + rng.sample(extra, 4 - len(products))
        if len(set(options)) != 4:
            continue
        rng.shuffle(options)
        letters = "АБВ"
        text = ("Установите соответствие между реагирующими веществами и продуктами их взаимодействия.\n%s\n\n%s\n"
                "Цифры в ответе могут повторяться." % ("\n".join("%s) %s" % (letters[i], r) for i, (r, _) in enumerate(chosen)),
                                                       _lines(options)))
        return text, "".join(str(options.index(p) + 1) for _, p in chosen), "seq", \
            "; ".join("%s → %s" % (r, p) for r, p in chosen) + "."
    raise RuntimeError("o9")


# ОГЭ 16: безопасность и разделение смесей
SAFETY_TRUE = [
    "Смесь речного песка и воды можно разделить фильтрованием.",
    "Поваренную соль из раствора выделяют выпариванием.",
    "Железные опилки из смеси с серой можно извлечь магнитом.",
    "Смесь воды и растительного масла разделяют с помощью делительной воронки.",
    "Чистую воду из раствора соли получают перегонкой (дистилляцией).",
    "Пробирку при нагревании держат пробиркодержателем.",
    "Запах вещества определяют, направляя воздух от сосуда к себе движением руки.",
    "При разбавлении концентрированной серной кислоты кислоту вливают в воду, а не наоборот.",
    "Опыты с концентрированными кислотами и щелочами проводят в защитных очках.",
    "Горящий спирт тушат, накрыв пламя песком или плотной тканью.",
]
SAFETY_FALSE = [
    "Нагревая жидкость в пробирке, её отверстие направляют на себя.",
    "Смесь спирта и воды разделяют фильтрованием.",
    "Поваренную соль из раствора можно отделить фильтрованием.",
    "Вещества в лаборатории можно пробовать на вкус, если они не ядовиты.",
    "При разбавлении серной кислоты воду вливают в кислоту.",
    "С концентрированными кислотами можно работать без защитных очков.",
    "Смесь сахара и поваренной соли можно разделить с помощью магнита.",
    "Горящий бензин тушат водой.",
    "Смесь железных и медных опилок разделяют растворением в воде.",
    "Неиспользованный реактив возвращают обратно в склянку.",
]


def o16(rng):
    items, ans, good = _pick_two(rng, SAFETY_TRUE, SAFETY_FALSE)
    return ("Выберите два верных суждения.\n%s" % _lines(items), ans, "set",
            "Верно: %s Остальные суждения нарушают правила безопасности или способ разделения не подходит "
            "(фильтр задерживает только нерастворимое, магнит притягивает только железо)." % " ".join(good))


# ОГЭ 19: химия в жизни — расчёты с данными
FERTILIZERS = [("NH4NO3", "аммиачной селитры"), ("CO(NH2)2", "карбамида (мочевины)"), ("(NH4)2SO4", "сульфата аммония")]
FOODS = [("молока", 120), ("кефира", 120), ("творога", 160), ("сыра", 1000), ("капусты", 50), ("миндаля", 260)]


def o19(rng):
    kind = rng.choice(["fert", "solution", "food"])
    if kind == "fert":
        for _ in range(200):
            f, name = rng.choice(FERTILIZERS)
            n_mass = rng.choice([7, 14, 21, 28, 35, 42, 56, 70])
            m = n_mass * molar_mass(f) / (14 * count_atoms(f, "N"))
            if abs(m - round(m)) < 1e-9:
                w = 100 * 14 * count_atoms(f, "N") / molar_mass(f)
                return ("Для подкормки грядки нужно внести %d г азота. Сколько граммов %s %s нужно взять? "
                        "Ответ — целое число." % (n_mass, name, f), _ans(m), "num",
                        "M(%s) = %s г/моль, в ней %s; w(N) = %s %%. m = %d / %s = %d г." % (
                            f, _fmt(molar_mass(f)), _plural(count_atoms(f, "N"), "атом азота", "атома азота", "атомов азота"),
                            _fmt(w, 1).replace(",0", ""), n_mass, _fmt(w / 100, 3).rstrip("0"), round(m)))
    if kind == "solution":
        m, w = rng.choice([(200, 0.9), (500, 0.9), (1000, 0.9), (250, 2), (300, 3), (150, 6), (400, 0.5)])
        what = "поваренной соли в физиологическом растворе" if w == 0.9 else "соли в растворе для полоскания горла"
        res = m * w / 100
        return ("Сколько граммов %s массой %d г, если массовая доля соли %s %%? Ответ — с точностью до десятых."
                % (what, m, _fmt(w, 1).replace(",0", "")), _ans(res, 1), "num",
                "m(соли) = %d · %s / 100 = %s г." % (m, _fmt(w, 1).replace(",0", ""), _fmt(res, 1)))
    for _ in range(200):
        food, c = rng.choice(FOODS)
        eaten = rng.choice([50, 100, 150, 200, 250, 300])
        mg = eaten * c / 100
        pct = mg / 1000 * 100
        if abs(pct - round(pct)) < 1e-9 and pct <= 100:
            return ("В 100 г %s содержится %d мг кальция, суточная потребность подростка — 1000 мг. Какой процент "
                    "суточной потребности покроют %d г %s? Ответ — целое число." % (food, c, eaten, food), _ans(pct), "num",
                    "%d г × %d мг / 100 г = %d мг; %d / 1000 = %d %%." % (eaten, c, round(mg), round(mg), round(pct)))
    return o19(rng)


# ОГЭ 20: электронный баланс (развёрнутый ответ). Уравнения проверяет тест на сохранение атомов.
REDOX = [
    ("Cu + HNO3(конц.) → Cu(NO3)2 + NO2 + H2O", "Cu + 4HNO3 = Cu(NO3)2 + 2NO2 + 2H2O",
     ["Cu⁰ − 2e → Cu⁺² | 1", "N⁺⁵ + 1e → N⁺⁴ | 2"], "азот +5 (HNO3)", "медь 0"),
    ("Cu + HNO3(разб.) → Cu(NO3)2 + NO + H2O", "3Cu + 8HNO3 = 3Cu(NO3)2 + 2NO + 4H2O",
     ["Cu⁰ − 2e → Cu⁺² | 3", "N⁺⁵ + 3e → N⁺² | 2"], "азот +5 (HNO3)", "медь 0"),
    ("H2S + HNO3 → S + NO + H2O", "3H2S + 2HNO3 = 3S + 2NO + 4H2O",
     ["S⁻² − 2e → S⁰ | 3", "N⁺⁵ + 3e → N⁺² | 2"], "азот +5 (HNO3)", "сера −2 (H2S)"),
    ("Zn + H2SO4(конц.) → ZnSO4 + H2S + H2O", "4Zn + 5H2SO4 = 4ZnSO4 + H2S + 4H2O",
     ["Zn⁰ − 2e → Zn⁺² | 4", "S⁺⁶ + 8e → S⁻² | 1"], "сера +6 (H2SO4)", "цинк 0"),
    ("Cu + H2SO4(конц.) → CuSO4 + SO2 + H2O", "Cu + 2H2SO4 = CuSO4 + SO2 + 2H2O",
     ["Cu⁰ − 2e → Cu⁺² | 1", "S⁺⁶ + 2e → S⁺⁴ | 1"], "сера +6 (H2SO4)", "медь 0"),
    ("NH3 + O2 → NO + H2O", "4NH3 + 5O2 = 4NO + 6H2O",
     ["N⁻³ − 5e → N⁺² | 4", "O2⁰ + 4e → 2O⁻² | 5"], "кислород 0 (O2)", "азот −3 (NH3)"),
    ("MnO2 + HCl → MnCl2 + Cl2 + H2O", "MnO2 + 4HCl = MnCl2 + Cl2 + 2H2O",
     ["Mn⁺⁴ + 2e → Mn⁺² | 1", "2Cl⁻ − 2e → Cl2⁰ | 1"], "марганец +4 (MnO2)", "хлор −1 (HCl)"),
    ("Fe2O3 + CO → Fe + CO2", "Fe2O3 + 3CO = 2Fe + 3CO2",
     ["Fe⁺³ + 3e → Fe⁰ | 2", "C⁺² − 2e → C⁺⁴ | 3"], "железо +3 (Fe2O3)", "углерод +2 (CO)"),
    ("P + HNO3(конц.) → H3PO4 + NO2 + H2O", "P + 5HNO3 = H3PO4 + 5NO2 + H2O",
     ["P⁰ − 5e → P⁺⁵ | 1", "N⁺⁵ + 1e → N⁺⁴ | 5"], "азот +5 (HNO3)", "фосфор 0"),
    ("S + HNO3(конц.) → H2SO4 + NO2 + H2O", "S + 6HNO3 = H2SO4 + 6NO2 + 2H2O",
     ["S⁰ − 6e → S⁺⁶ | 1", "N⁺⁵ + 1e → N⁺⁴ | 6"], "азот +5 (HNO3)", "сера 0"),
    ("C + H2SO4(конц.) → CO2 + SO2 + H2O", "C + 2H2SO4 = CO2 + 2SO2 + 2H2O",
     ["C⁰ − 4e → C⁺⁴ | 1", "S⁺⁶ + 2e → S⁺⁴ | 2"], "сера +6 (H2SO4)", "углерод 0"),
    ("Ag + HNO3(конц.) → AgNO3 + NO2 + H2O", "Ag + 2HNO3 = AgNO3 + NO2 + H2O",
     ["Ag⁰ − 1e → Ag⁺¹ | 1", "N⁺⁵ + 1e → N⁺⁴ | 1"], "азот +5 (HNO3)", "серебро 0"),
    ("Mg + HNO3(разб.) → Mg(NO3)2 + N2O + H2O", "4Mg + 10HNO3 = 4Mg(NO3)2 + N2O + 5H2O",
     ["Mg⁰ − 2e → Mg⁺² | 4", "2N⁺⁵ + 8e → 2N⁺¹ | 1"], "азот +5 (HNO3)", "магний 0"),
    ("KClO3 → KCl + O2", "2KClO3 = 2KCl + 3O2",
     ["Cl⁺⁵ + 6e → Cl⁻¹ | 2", "2O⁻² − 4e → O2⁰ | 3"], "хлор +5 (KClO3)", "кислород −2 (KClO3)"),
]


def o20(rng):
    scheme, eq, balance, ox, red = rng.choice(REDOX)
    text = ("Используя метод электронного баланса, расставьте коэффициенты в уравнении реакции, схема которой\n%s\n"
            "Определите окислитель и восстановитель." % scheme)
    why = "%s\n%s\nОкислитель — %s, восстановитель — %s.\nКритерии: баланс — 1 балл, окислитель и восстановитель — " \
          "1 балл, коэффициенты — 1 балл." % ("\n".join(balance), eq, ox, red)
    return text, eq, "long", why


GENERATORS.update({("oge", 1): o1, ("oge", 6): o6, ("oge", 8): o8, ("oge", 9): o9, ("oge", 10): o10,
                   ("oge", 16): o16, ("oge", 19): o19, ("oge", 20): o20})



# ОГЭ 21: цепочки превращений (третье превращение — с сокращённым ионным уравнением)
CHAINS = [
    ("Cu → CuO → CuCl2 → Cu(OH)2", ["2Cu + O2 = 2CuO", "CuO + 2HCl = CuCl2 + H2O", "CuCl2 + 2NaOH = Cu(OH)2↓ + 2NaCl"],
     "Cu²⁺ + 2OH⁻ = Cu(OH)2↓"),
    ("Ca → Ca(OH)2 → CaCO3 → CaCl2", ["Ca + 2H2O = Ca(OH)2 + H2↑", "Ca(OH)2 + CO2 = CaCO3↓ + H2O",
                                      "CaCO3 + 2HCl = CaCl2 + H2O + CO2↑"], "CaCO3 + 2H⁺ = Ca²⁺ + H2O + CO2↑"),
    ("P → P2O5 → Na3PO4 → Ca3(PO4)2", ["4P + 5O2 = 2P2O5", "P2O5 + 6NaOH = 2Na3PO4 + 3H2O",
                                        "2Na3PO4 + 3CaCl2 = Ca3(PO4)2↓ + 6NaCl"], "3Ca²⁺ + 2PO4³⁻ = Ca3(PO4)2↓"),
    ("Mg → MgO → MgCl2 → Mg(OH)2", ["2Mg + O2 = 2MgO", "MgO + 2HCl = MgCl2 + H2O", "MgCl2 + 2NaOH = Mg(OH)2↓ + 2NaCl"],
     "Mg²⁺ + 2OH⁻ = Mg(OH)2↓"),
    ("S → SO2 → Na2SO3 → BaSO3", ["S + O2 = SO2", "SO2 + 2NaOH = Na2SO3 + H2O", "Na2SO3 + BaCl2 = BaSO3↓ + 2NaCl"],
     "Ba²⁺ + SO3²⁻ = BaSO3↓"),
    ("Fe → FeCl3 → Fe(OH)3 → Fe2(SO4)3", ["2Fe + 3Cl2 = 2FeCl3", "FeCl3 + 3NaOH = Fe(OH)3↓ + 3NaCl",
                                           "2Fe(OH)3 + 3H2SO4 = Fe2(SO4)3 + 6H2O"], "Fe(OH)3 + 3H⁺ = Fe³⁺ + 3H2O"),
    ("Zn → ZnO → ZnCl2 → Zn(NO3)2", ["2Zn + O2 = 2ZnO", "ZnO + 2HCl = ZnCl2 + H2O",
                                      "ZnCl2 + 2AgNO3 = Zn(NO3)2 + 2AgCl↓"], "Ag⁺ + Cl⁻ = AgCl↓"),
    ("C → CO2 → Na2CO3 → CaCO3", ["C + O2 = CO2", "CO2 + 2NaOH = Na2CO3 + H2O", "Na2CO3 + CaCl2 = CaCO3↓ + 2NaCl"],
     "Ca²⁺ + CO3²⁻ = CaCO3↓"),
    ("Na → NaOH → Na2SO4 → BaSO4", ["2Na + 2H2O = 2NaOH + H2↑", "2NaOH + H2SO4 = Na2SO4 + 2H2O",
                                     "Na2SO4 + BaCl2 = BaSO4↓ + 2NaCl"], "Ba²⁺ + SO4²⁻ = BaSO4↓"),
]


def o21(rng):
    chain, eqs, ionic = rng.choice(CHAINS)
    text = ("Дана схема превращений: %s\nНапишите молекулярные уравнения реакций, с помощью которых можно осуществить "
            "указанные превращения. Для третьего превращения составьте сокращённое ионное уравнение реакции." % chain)
    why = "%s\n   %s\nВозможны и другие верные реагенты. Критерии: по 1 баллу за каждое верное уравнение (ионное — " \
          "в составе третьего)." % ("\n".join("%d) %s" % (i + 1, e) for i, e in enumerate(eqs)), ionic)
    return text, chain, "long", why


# ОГЭ 23: реальный эксперимент — две реакции из набора реактивов
EXPERIMENTS = [
    ("Дан раствор хлорида меди(II), а также набор реактивов: цинк, растворы гидроксида натрия, нитрата калия, "
     "сульфата натрия и соляная кислота. Предложите две реакции, характеризующие свойства хлорида меди(II): "
     "одну — реакцию ионного обмена, другую — окислительно-восстановительную.",
     "1) CuCl2 + 2NaOH = Cu(OH)2↓ + 2NaCl — голубой осадок; Cu²⁺ + 2OH⁻ = Cu(OH)2↓\n"
     "2) CuCl2 + Zn = ZnCl2 + Cu — красный налёт меди на цинке, окраска раствора бледнеет"),
    ("Дан раствор карбоната натрия, а также набор реактивов: соляная кислота, растворы хлорида кальция, хлорида натрия, "
     "нитрата калия и фенолфталеин. Докажите двумя реакциями ионного обмена, что в растворе есть карбонат-ионы.",
     "1) Na2CO3 + 2HCl = 2NaCl + H2O + CO2↑ — выделяется газ без цвета и запаха; CO3²⁻ + 2H⁺ = H2O + CO2↑\n"
     "2) Na2CO3 + CaCl2 = CaCO3↓ + 2NaCl — белый осадок; Ca²⁺ + CO3²⁻ = CaCO3↓"),
    ("Дан раствор хлорида бария, а также набор реактивов: разбавленная серная кислота, растворы карбоната натрия, "
     "гидроксида натрия, нитрата калия и медь. Докажите двумя реакциями ионного обмена, что в растворе есть ионы бария.",
     "1) BaCl2 + H2SO4 = BaSO4↓ + 2HCl — белый осадок; Ba²⁺ + SO4²⁻ = BaSO4↓\n"
     "2) BaCl2 + Na2CO3 = BaCO3↓ + 2NaCl — белый осадок; Ba²⁺ + CO3²⁻ = BaCO3↓"),
    ("Дан раствор серной кислоты, а также набор реактивов: цинк, медь, растворы хлорида бария, хлорида натрия и нитрата "
     "калия. Предложите две реакции, характеризующие свойства серной кислоты: одну — окислительно-восстановительную, "
     "другую — реакцию ионного обмена.",
     "1) Zn + H2SO4 = ZnSO4 + H2↑ — цинк растворяется, выделяется газ\n"
     "2) H2SO4 + BaCl2 = BaSO4↓ + 2HCl — белый осадок; Ba²⁺ + SO4²⁻ = BaSO4↓"),
    ("Дан раствор гидроксида натрия, а также набор реактивов: растворы сульфата меди(II), хлорида натрия, нитрата калия, "
     "фенолфталеин и соляная кислота. Докажите, что в растворе есть щёлочь, и проведите реакцию, в которой образуется осадок.",
     "1) Фенолфталеин окрашивается в малиновый цвет — среда щелочная; NaOH + HCl = NaCl + H2O — малиновая окраска "
     "исчезает; H⁺ + OH⁻ = H2O\n"
     "2) 2NaOH + CuSO4 = Cu(OH)2↓ + Na2SO4 — голубой осадок; Cu²⁺ + 2OH⁻ = Cu(OH)2↓"),
]
EXPERIMENT_EQUATIONS = ["CuCl2 + 2NaOH = Cu(OH)2↓ + 2NaCl", "CuCl2 + Zn = ZnCl2 + Cu", "Na2CO3 + 2HCl = 2NaCl + H2O + CO2↑",
                        "Na2CO3 + CaCl2 = CaCO3↓ + 2NaCl", "BaCl2 + H2SO4 = BaSO4↓ + 2HCl",
                        "BaCl2 + Na2CO3 = BaCO3↓ + 2NaCl", "Zn + H2SO4 = ZnSO4 + H2↑", "NaOH + HCl = NaCl + H2O",
                        "2NaOH + CuSO4 = Cu(OH)2↓ + Na2SO4"]


def o23(rng):
    task, solution = rng.choice(EXPERIMENTS)
    text = (task + "\nЗапишите молекулярные уравнения реакций, опишите признаки их протекания. Для реакций ионного обмена "
                   "составьте сокращённые ионные уравнения. Опыты проводят по правилам техники безопасности.")
    why = solution + "\nКритерии: уравнения — до 2 баллов, признаки — до 2 баллов, ионное уравнение — 1 балл."
    return text, solution.split("\n")[0], "long", why


GENERATORS.update({("oge", 21): o21, ("oge", 23): o23})



# ================================================================ ЕГЭ 9, 10, 12, 13, 22, 25, 29
# ЕГЭ 22: смещение равновесия. (уравнение, экзо?, газов слева, газов справа, газообразные реагенты, продукты, твёрдые)
EQUILIBRIA = [
    ("2SO2(г) + O2(г) ⇄ 2SO3(г) + Q", True, 3, 2, ["SO2", "O2"], ["SO3"], []),
    ("N2(г) + 3H2(г) ⇄ 2NH3(г) + Q", True, 4, 2, ["N2", "H2"], ["NH3"], []),
    ("H2(г) + I2(г) ⇄ 2HI(г) − Q", False, 2, 2, ["H2", "I2"], ["HI"], []),
    ("N2(г) + O2(г) ⇄ 2NO(г) − Q", False, 2, 2, ["N2", "O2"], ["NO"], []),
    ("CO(г) + Cl2(г) ⇄ COCl2(г) + Q", True, 2, 1, ["CO", "Cl2"], ["COCl2"], []),
    ("2NO(г) + O2(г) ⇄ 2NO2(г) + Q", True, 3, 2, ["NO", "O2"], ["NO2"], []),
    ("C(тв) + CO2(г) ⇄ 2CO(г) − Q", False, 1, 2, ["CO2"], ["CO"], ["C"]),
    ("CaCO3(тв) ⇄ CaO(тв) + CO2(г) − Q", False, 0, 1, [], ["CO2"], ["CaCO3", "CaO"]),
    ("N2O4(г) ⇄ 2NO2(г) − Q", False, 1, 2, ["N2O4"], ["NO2"], []),
    ("CO(г) + H2O(г) ⇄ CO2(г) + H2(г) + Q", True, 2, 2, ["CO", "H2O"], ["CO2", "H2"], []),
]
SHIFT = ["вправо", "влево", "не смещается"]


def _shifts(eq):
    _, exo, left, right, reag, prod, solid = eq
    acts = [("повышение температуры", 1 if exo else 0), ("понижение температуры", 0 if exo else 1),
            ("использование катализатора", 2)]
    dp = 2 if left == right else (0 if right < left else 1)
    acts += [("повышение давления", dp), ("понижение давления", {0: 1, 1: 0, 2: 2}[dp])]
    acts += [("увеличение концентрации %s" % r, 0) for r in reag]
    acts += [("уменьшение концентрации %s" % r, 1) for r in reag]
    acts += [("увеличение концентрации %s" % p, 1) for p in prod]
    acts += [("уменьшение концентрации %s" % p, 0) for p in prod]
    acts += [("добавление твёрдого %s" % x, 2) for x in solid]
    return acts


def e22(rng):
    for _ in range(200):
        eq = rng.choice(EQUILIBRIA)
        acts = rng.sample(_shifts(eq), 4)
        if len({a[1] for a in acts}) >= 2:
            break
    letters = "АБВГ"
    text = ("Установите соответствие между воздействием на равновесную систему\n%s\nи направлением смещения "
            "химического равновесия.\n%s\n\n%s\nЦифры в ответе могут повторяться." % (
                eq[0], "\n".join("%s) %s" % (letters[i], a[0]) for i, a in enumerate(acts)), _lines(SHIFT)))
    return text, "".join(str(a[1] + 1) for a in acts), "seq", (
        "Нагревание смещает в сторону эндотермической реакции; давление — в сторону меньшего числа молей газов "
        "(здесь %d → %d); добавление вещества смещает в сторону его расхода; катализатор и твёрдые вещества "
        "равновесие не смещают." % (eq[2], eq[3]))


# ЕГЭ 10: классы органических веществ
ORG_CLASSES = {
    "алканы": ["метан", "пропан", "2-метилбутан", "гексан"],
    "алкены": ["этилен", "пропен", "бутен-2", "2-метилпропен"],
    "алкины": ["ацетилен", "пропин", "бутин-1"],
    "арены": ["бензол", "толуол", "этилбензол"],
    "спирты": ["этанол", "пропанол-2", "этиленгликоль", "глицерин"],
    "фенолы": ["фенол", "4-метилфенол"],
    "альдегиды": ["формальдегид", "этаналь", "пропаналь"],
    "кетоны": ["ацетон", "бутанон"],
    "карбоновые кислоты": ["уксусная кислота", "муравьиная кислота", "пропионовая кислота", "бензойная кислота"],
    "сложные эфиры": ["метилацетат", "этилформиат", "этилацетат"],
    "простые эфиры": ["диметиловый эфир", "диэтиловый эфир"],
    "амины": ["метиламин", "диметиламин", "анилин"],
    "аминокислоты": ["глицин", "аланин"],
}


def e10(rng):
    classes = rng.sample(sorted(ORG_CLASSES), 4)
    chosen = classes[:3]
    names = [rng.choice(ORG_CLASSES[c]) for c in chosen]
    options = classes[:]
    rng.shuffle(options)
    letters = "АБВ"
    text = ("Установите соответствие между названием вещества и классом (группой) органических соединений, к которому "
            "оно принадлежит.\n%s\n\n%s" % ("\n".join("%s) %s" % (letters[i], n) for i, n in enumerate(names)),
                                            _lines(options)))
    return text, "".join(str(options.index(c) + 1) for c in chosen), "seq", \
        "; ".join("%s — %s" % (n, c) for n, c in zip(names, chosen)) + "."


# ЕГЭ 12–13: свойства органических веществ. (вопрос, кто «да», кто точно «нет»)
ORG_PROPS_12 = [
    ("обесцвечивают бромную воду", ["этилен", "пропен", "ацетилен", "бутадиен-1,3", "фенол", "анилин"],
     ["метан", "этан", "бензол", "этанол", "уксусная кислота", "циклогексан", "толуол"]),
    ("вступают в реакцию «серебряного зеркала»", ["формальдегид", "этаналь", "глюкоза", "муравьиная кислота"],
     ["ацетон", "этанол", "сахароза", "уксусная кислота", "фенол", "глицерин"]),
    ("реагируют с металлическим натрием", ["этанол", "фенол", "уксусная кислота", "глицерин"],
     ["бензол", "гексан", "диэтиловый эфир", "этилацетат", "ацетон"]),
    ("реагируют с раствором гидроксида натрия", ["фенол", "уксусная кислота", "этилацетат", "глицин"],
     ["этанол", "бензол", "гексан", "глицерин", "ацетон", "диэтиловый эфир"]),
]
ORG_PROPS_13 = [
    ("подвергаются гидролизу", ["сахароза", "крахмал", "целлюлоза", "тристеарат глицерина", "этилацетат"],
     ["глюкоза", "фруктоза", "глицерин", "этанол", "уксусная кислота"]),
    ("образуют ярко-синий раствор с гидроксидом меди(II) при комнатной температуре",
     ["глицерин", "этиленгликоль", "глюкоза", "сахароза"], ["этанол", "метанол", "ацетон", "бензол", "этилацетат"]),
    ("проявляют амфотерные свойства", ["глицин", "аланин"],
     ["метиламин", "уксусная кислота", "анилин", "этанол", "фенол"]),
    ("проявляют основные свойства", ["метиламин", "диметиламин", "анилин"],
     ["фенол", "уксусная кислота", "глицерин", "бензол", "этанол"]),
]


def _org_props(rng, table):
    q, yes, no = rng.choice(table)
    items, ans, good = _pick_two(rng, yes, no)
    return ("Из предложенного перечня выберите два вещества, которые %s.\n%s" % (q, _lines(items)), ans, "set",
            "%s: %s." % (q[0].upper() + q[1:], ", ".join(good)))


def e12(rng):
    return _org_props(rng, ORG_PROPS_12)


def e13(rng):
    return _org_props(rng, ORG_PROPS_13)


# ЕГЭ 9: вещества X и Y в схеме превращений (вариантов ответа ровно по одному)
SCHEMES_9 = [
    ("Fe —X→ FeCl3 —Y→ Fe(OH)3", ["HCl", "Cl2", "NaOH", "H2O", "NaCl"], "23",
     "Соляная кислота окисляет железо только до +2, хлор — до +3; гидроксид осаждают щёлочью."),
    ("Cu —X→ CuSO4 —Y→ Cu(OH)2", ["H2SO4 (разб.)", "H2SO4 (конц.)", "NaOH", "Na2SO4", "H2O"], "23",
     "Медь стоит после водорода — растворяется только в концентрированной серной кислоте; гидроксид — действием щёлочи."),
    ("Al —X→ AlCl3 —Y→ Al(OH)3", ["HCl", "NaCl", "NaOH (избыток)", "NH3 (водный р-р)", "H2O"], "14",
     "Избыток щёлочи растворяет амфотерный Al(OH)3, поэтому осаждают раствором аммиака."),
    ("S —X→ SO2 —Y→ Na2SO3", ["O2", "H2O", "NaOH", "Na2SO4", "H2SO4"], "13",
     "Сера сгорает до SO2; кислотный оксид со щёлочью даёт сульфит."),
    ("Ca —X→ Ca(OH)2 —Y→ CaCO3", ["H2O", "O2", "CO2", "NaCl", "HCl"], "13",
     "Кальций реагирует с водой; известковая вода мутнеет от CO2."),
    ("Na2CO3 —X→ NaCl —Y→ AgCl", ["HCl", "NaOH", "AgNO3", "Ag", "H2O"], "13",
     "Карбонат разлагается кислотой; хлорид-ион осаждают нитратом серебра."),
]


def e9(rng):
    scheme, opts, ans, why = rng.choice(SCHEMES_9)
    order = list(range(5))
    rng.shuffle(order)
    shown = [opts[i] for i in order]
    new_ans = "".join(str(order.index(int(c) - 1) + 1) for c in ans)
    text = ("Задана схема превращений веществ: %s\nОпределите, какие из указанных веществ являются веществами X и Y.\n%s\n"
            "Запишите номера: сначала X, затем Y." % (scheme, _lines(shown)))
    return text, new_ans, "seq", why


# ЕГЭ 25: применение веществ (у каждого вещества здесь одно характерное применение, без пересечений)
APPLICATIONS = [
    ("аммиак", "производство азотных удобрений"), ("хлор", "обеззараживание питьевой воды"),
    ("кремний", "изготовление полупроводников и солнечных батарей"), ("ацетилен", "сварка и резка металлов"),
    ("гидрокарбонат натрия", "разрыхлитель теста"), ("полиэтилен", "упаковочная плёнка"),
    ("жидкий азот", "быстрая заморозка"), ("метан", "бытовой газ для плит"),
    ("карбонат кальция", "производство извести и цемента"), ("оксид кремния(IV)", "производство стекла"),
]


def e25(rng):
    pick = rng.sample(APPLICATIONS, 4)
    chosen = pick[:3]
    options = [a for _, a in pick]
    rng.shuffle(options)
    letters = "АБВ"
    text = ("Установите соответствие между веществом и областью его применения.\n%s\n\n%s" % (
        "\n".join("%s) %s" % (letters[i], s) for i, (s, _) in enumerate(chosen)), _lines(options)))
    return text, "".join(str(options.index(a) + 1) for _, a in chosen), "seq", \
        "; ".join("%s — %s" % (s, a) for s, a in chosen) + "."


# ЕГЭ 29: ОВР уровня ЕГЭ — электронный баланс (развёрнутый ответ, 2 балла)
REDOX_EGE = [
    ("KMnO4 + HCl → KCl + MnCl2 + Cl2 + H2O", "2KMnO4 + 16HCl = 2KCl + 2MnCl2 + 5Cl2 + 8H2O",
     ["Mn⁺⁷ + 5e → Mn⁺² | 2", "2Cl⁻ − 2e → Cl2⁰ | 5"], "марганец +7 (KMnO4)", "хлор −1 (HCl)"),
    ("K2Cr2O7 + HCl → KCl + CrCl3 + Cl2 + H2O", "K2Cr2O7 + 14HCl = 2KCl + 2CrCl3 + 3Cl2 + 7H2O",
     ["2Cr⁺⁶ + 6e → 2Cr⁺³ | 1", "2Cl⁻ − 2e → Cl2⁰ | 3"], "хром +6 (K2Cr2O7)", "хлор −1 (HCl)"),
    ("KMnO4 + Na2SO3 + H2SO4 → MnSO4 + Na2SO4 + K2SO4 + H2O",
     "2KMnO4 + 5Na2SO3 + 3H2SO4 = 2MnSO4 + 5Na2SO4 + K2SO4 + 3H2O",
     ["Mn⁺⁷ + 5e → Mn⁺² | 2", "S⁺⁴ − 2e → S⁺⁶ | 5"], "марганец +7 (KMnO4)", "сера +4 (Na2SO3)"),
    ("KMnO4 + Na2SO3 + H2O → MnO2 + Na2SO4 + KOH", "2KMnO4 + 3Na2SO3 + H2O = 2MnO2 + 3Na2SO4 + 2KOH",
     ["Mn⁺⁷ + 3e → Mn⁺⁴ | 2", "S⁺⁴ − 2e → S⁺⁶ | 3"], "марганец +7 (KMnO4)", "сера +4 (Na2SO3)"),
    ("KMnO4 + Na2SO3 + KOH → K2MnO4 + Na2SO4 + H2O", "2KMnO4 + Na2SO3 + 2KOH = 2K2MnO4 + Na2SO4 + H2O",
     ["Mn⁺⁷ + 1e → Mn⁺⁶ | 2", "S⁺⁴ − 2e → S⁺⁶ | 1"], "марганец +7 (KMnO4)", "сера +4 (Na2SO3)"),
    ("K2Cr2O7 + Na2SO3 + H2SO4 → Cr2(SO4)3 + Na2SO4 + K2SO4 + H2O",
     "K2Cr2O7 + 3Na2SO3 + 4H2SO4 = Cr2(SO4)3 + 3Na2SO4 + K2SO4 + 4H2O",
     ["2Cr⁺⁶ + 6e → 2Cr⁺³ | 1", "S⁺⁴ − 2e → S⁺⁶ | 3"], "хром +6 (K2Cr2O7)", "сера +4 (Na2SO3)"),
    ("Al + HNO3(разб.) → Al(NO3)3 + NH4NO3 + H2O", "8Al + 30HNO3 = 8Al(NO3)3 + 3NH4NO3 + 9H2O",
     ["Al⁰ − 3e → Al⁺³ | 8", "N⁺⁵ + 8e → N⁻³ | 3"], "азот +5 (HNO3)", "алюминий 0"),
    ("FeCl3 + KI → FeCl2 + KCl + I2", "2FeCl3 + 2KI = 2FeCl2 + 2KCl + I2",
     ["Fe⁺³ + 1e → Fe⁺² | 2", "2I⁻ − 2e → I2⁰ | 1"], "железо +3 (FeCl3)", "иод −1 (KI)"),
    ("H2O2 + KI + H2SO4 → I2 + K2SO4 + H2O", "H2O2 + 2KI + H2SO4 = I2 + K2SO4 + 2H2O",
     ["2O⁻¹ + 2e → 2O⁻² | 1", "2I⁻ − 2e → I2⁰ | 1"], "кислород −1 (H2O2)", "иод −1 (KI)"),
]


def e29(rng):
    scheme, eq, balance, ox, red = rng.choice(REDOX_EGE)
    text = ("Используя метод электронного баланса, составьте уравнение реакции\n%s\nУкажите окислитель и "
            "восстановитель." % scheme)
    why = "%s\n%s\nОкислитель — %s, восстановитель — %s.\nКритерии ЕГЭ: уравнение с коэффициентами — 1 балл, " \
          "электронный баланс с окислителем и восстановителем — 1 балл." % ("\n".join(balance), eq, ox, red)
    return text, eq, "long", why


GENERATORS.update({("ege", 9): e9, ("ege", 10): e10, ("ege", 12): e12, ("ege", 13): e13, ("ege", 22): e22,
                   ("ege", 25): e25, ("ege", 29): e29})



# ================================================================ ЕГЭ 8, 11, 14, 15, 16
def e8(rng):
    """Реагенты → продукты: 4 реакции одной семьи, 6 вариантов."""
    for _ in range(500):
        fam, decoys = rng.choice(PRODUCT_FAMILIES)
        chosen = rng.sample(fam, 4)
        products = sorted({p for _, p in chosen})
        extra = [p for _, p in fam if p not in products] + [d for d in decoys if d not in products]
        if len(products) + len(extra) < 6:
            continue
        options = products + rng.sample(extra, 6 - len(products))
        rng.shuffle(options)
        letters = "АБВГ"
        text = ("Установите соответствие между исходными веществами и продуктами реакции.\n%s\n\n%s\n"
                "Цифры в ответе могут повторяться." % ("\n".join("%s) %s" % (letters[i], r) for i, (r, _) in enumerate(chosen)),
                                                       _lines(options)))
        return text, "".join(str(options.index(p) + 1) for _, p in chosen), "seq", \
            "; ".join("%s → %s" % (r, p) for r, p in chosen) + "."
    raise RuntimeError("e8")


# ЕГЭ 11: изомеры — группы веществ с одинаковой молекулярной формулой
ISOMERS = {
    "C4H8": ["бутен-1", "бутен-2", "2-метилпропен", "циклобутан", "метилциклопропан"],
    "C4H10": ["бутан", "2-метилпропан"],
    "C4H6": ["бутин-1", "бутин-2", "бутадиен-1,3"],
    "C5H12": ["пентан", "2-метилбутан", "2,2-диметилпропан"],
    "C6H12": ["гексен-1", "циклогексан", "метилциклопентан"],
    "C3H8O": ["пропанол-1", "пропанол-2", "метилэтиловый эфир"],
    "C3H6O2": ["пропионовая кислота", "метилацетат", "этилформиат"],
    "C2H6O": ["этанол", "диметиловый эфир"],
    "C3H6O": ["пропаналь", "ацетон"],
}


def e11(rng):
    formula = rng.choice([f for f, ns in ISOMERS.items() if len(ns) >= 3])
    target = rng.choice(ISOMERS[formula])
    good = [n for n in ISOMERS[formula] if n != target]
    others = [n for f, ns in ISOMERS.items() if f != formula for n in ns]
    items, ans, chosen = _pick_two(rng, good, others)
    return ("Из предложенного перечня выберите два вещества, которые являются структурными изомерами вещества %s.\n%s"
            % (target, _lines(items)), ans, "set",
            "Изомеры — одинаковая молекулярная формула, разное строение. У %s формула %s; такая же у: %s."
            % (target, formula, ", ".join(chosen)))


# ЕГЭ 14 и 15: органический продукт реакции
REACTIONS_14 = [
    ("пропен + HBr", "2-бромпропан"), ("пропен + H2O (H⁺)", "пропанол-2"), ("пропен + Br2", "1,2-дибромпропан"),
    ("пропен + H2 (Ni)", "пропан"), ("пропин + H2O (Hg²⁺)", "ацетон"), ("ацетилен + H2O (Hg²⁺)", "этаналь"),
    ("бензол + Cl2 (FeCl3)", "хлорбензол"), ("бензол + HNO3 (H2SO4 конц.)", "нитробензол"),
    ("этан + Cl2 (свет)", "хлорэтан"), ("метан + Cl2 (свет)", "хлорметан"),
    ("толуол + KMnO4 (H⁺, t)", "бензойная кислота"), ("хлорэтан + KOH (водный р-р)", "этанол"),
    ("хлорэтан + KOH (спиртовой р-р)", "этилен"), ("этилен + HCl", "хлорэтан"),
]
REACTIONS_15 = [
    ("этанол + Na", "этилат натрия"), ("этанол + CuO (t)", "этаналь"),
    ("этанол + H2SO4 (конц., t > 140 °C)", "этилен"), ("этанол + HBr", "бромэтан"),
    ("уксусная кислота + NaOH", "ацетат натрия"), ("уксусная кислота + этанол (H⁺)", "этилацетат"),
    ("этаналь + H2 (Ni)", "этанол"), ("этаналь + Cu(OH)2 (t)", "уксусная кислота"),
    ("фенол + NaOH", "фенолят натрия"), ("фенол + Br2 (водный р-р)", "2,4,6-трибромфенол"),
    ("метанол + CuO (t)", "формальдегид"), ("пропанол-2 + CuO (t)", "ацетон"), ("глюкоза + H2 (Ni)", "сорбит"),
]
DECOYS_14 = ["1-бромпропан", "пропанол-1", "пропаналь", "1,1-дибромпропан", "бензиловый спирт", "этан"]
DECOYS_15 = ["диэтиловый эфир", "этанол", "метилацетат", "фенол", "пропаналь", "глюконовая кислота"]


def _org_products(rng, table, decoys, intro):
    for _ in range(200):
        chosen = rng.sample(table, 4)
        products = sorted({p for _, p in chosen})
        pool = [p for _, p in table if p not in products] + [d for d in decoys if d not in products]
        options = products + rng.sample(pool, 6 - len(products))
        if len(set(options)) != 6:
            continue
        rng.shuffle(options)
        letters = "АБВГ"
        text = ("Установите соответствие между %s и органическим продуктом, который преимущественно образуется.\n%s\n\n%s\n"
                "Цифры в ответе могут повторяться." % (intro, "\n".join("%s) %s" % (letters[i], r) for i, (r, _) in enumerate(chosen)),
                                                       _lines(options)))
        return text, "".join(str(options.index(p) + 1) for _, p in chosen), "seq", \
            "; ".join("%s → %s" % (r, p) for r, p in chosen) + "."
    raise RuntimeError("org_products")


def e14(rng):
    return _org_products(rng, REACTIONS_14, DECOYS_14, "реагирующими веществами")


def e15(rng):
    return _org_products(rng, REACTIONS_15, DECOYS_15, "реагирующими веществами")


# ЕГЭ 16: органические цепочки с X и Y
SCHEMES_16 = [
    ("этилен —X→ этанол —Y→ этаналь", ["H2O (H⁺)", "CuO (t)", "H2", "NaOH", "Cl2"], "12",
     "Гидратация этилена даёт этанол; оксид меди(II) при нагревании окисляет спирт до альдегида."),
    ("ацетилен —X→ этаналь —Y→ этанол", ["H2O (Hg²⁺)", "H2 (Ni)", "O2", "NaOH", "Br2"], "12",
     "Реакция Кучерова даёт этаналь; водород на никеле восстанавливает альдегид до спирта."),
    ("метан —X→ хлорметан —Y→ метанол", ["Cl2 (свет)", "HCl", "NaOH (водный р-р)", "Na", "H2"], "13",
     "Радикальное хлорирование на свету; водная щёлочь замещает хлор на OH."),
    ("бензол —X→ нитробензол —Y→ анилин", ["HNO3 (H2SO4 конц.)", "NaNO3", "H2 (кат.)", "NaOH", "O2"], "13",
     "Нитрование нитрующей смесью; восстановление нитрогруппы до аминогруппы."),
    ("этанол —X→ этилен —Y→ 1,2-дибромэтан", ["H2SO4 (конц., t > 140 °C)", "NaOH", "Br2", "HBr", "H2"], "13",
     "Внутримолекулярная дегидратация даёт этилен; бром присоединяется к двойной связи (HBr дал бы бромэтан)."),
    ("уксусная кислота —X→ ацетат натрия —Y→ метан", ["NaOH", "Na2SO4", "HCl", "H2", "CO2"], "11",
     "Нейтрализация щёлочью, затем сплавление ацетата с NaOH (декарбоксилирование) даёт метан."),
]


def e16(rng):
    scheme, opts, ans, why = rng.choice(SCHEMES_16)
    order = list(range(5))
    rng.shuffle(order)
    shown = [opts[i] for i in order]
    new_ans = "".join(str(order.index(int(c) - 1) + 1) for c in ans)
    text = ("Задана схема превращений веществ: %s\nОпределите, какие из указанных веществ являются веществами X и Y.\n%s\n"
            "Запишите номера: сначала X, затем Y. Цифры могут повторяться." % (scheme, _lines(shown)))
    return text, new_ans, "seq", why


GENERATORS.update({("ege", 7): e7, ("ege", 8): e8, ("ege", 11): e11, ("ege", 14): e14, ("ege", 15): e15,
                   ("ege", 16): e16})



# ================================================================ ЕГЭ 6, 30–34
# ЕГЭ 6: вещества X и Y по наблюдениям. Для каждого наблюдения — кто точно даёт, кто точно нет (остальные не показываем)
SALTS_6 = ["Na2SO4", "K2SO4", "(NH4)2SO4", "NH4Cl", "NH4NO3", "NaCl", "KCl", "KNO3", "NaNO3", "Na2CO3", "K2CO3",
           "NaHCO3", "KBr", "KI", "Na3PO4"]
OBSERVATIONS_6 = [
    ("добавили раствор хлорида бария — выпал белый осадок, нерастворимый в кислотах",
     {"Na2SO4", "K2SO4", "(NH4)2SO4"},
     {"NH4Cl", "NH4NO3", "NaCl", "KCl", "KNO3", "NaNO3", "Na2CO3", "K2CO3", "NaHCO3", "KBr", "KI", "Na3PO4"}),
    ("добавили раствор гидроксида натрия и нагрели — выделился газ с резким запахом",
     {"NH4Cl", "NH4NO3", "(NH4)2SO4"}, set(SALTS_6) - {"NH4Cl", "NH4NO3", "(NH4)2SO4"}),
    ("добавили соляную кислоту — выделился газ без запаха, от которого мутнеет известковая вода",
     {"Na2CO3", "K2CO3", "NaHCO3"}, set(SALTS_6) - {"Na2CO3", "K2CO3", "NaHCO3"}),
    ("добавили раствор нитрата серебра — выпал белый творожистый осадок",
     {"NaCl", "KCl", "NH4Cl"}, {"KNO3", "NaNO3", "NH4NO3"}),
]


def e6(rng):
    for _ in range(2000):
        (o1, y1, n1), (o2, y2, n2) = rng.sample(OBSERVATIONS_6, 2)
        x, y = rng.choice(sorted(y1)), rng.choice(sorted(y2))
        if x == y or x in y2 or y in y1:
            continue
        rest = [z for z in SALTS_6 if z not in (x, y) and z in n1 and z in n2]
        if len(rest) < 3:
            continue
        items = [x, y] + rng.sample(rest, 3)
        rng.shuffle(items)
        text = ("В пробирку с раствором вещества X %s. В пробирку с раствором вещества Y %s.\n"
                "Из предложенного перечня выберите вещества X и Y.\n%s\nЗапишите номера: сначала X, затем Y."
                % (o1, o2, _lines(items)))
        return text, "%d%d" % (items.index(x) + 1, items.index(y) + 1), "seq", \
            "X — %s, Y — %s. Сульфат-ион узнают по BaSO4 (не растворяется в кислотах), ион аммония — по аммиаку со " \
            "щёлочью, карбонат — по CO2 с кислотой, хлорид — по белому творожистому AgCl." % (x, y)
    raise RuntimeError("e6")


# ЕГЭ 30: ионные уравнения (развёрнутый ответ)
IONIC_FULL = [
    ("хлоридом бария и сульфатом натрия", "BaCl2 + Na2SO4 = BaSO4↓ + 2NaCl",
     "Ba²⁺ + 2Cl⁻ + 2Na⁺ + SO4²⁻ = BaSO4↓ + 2Na⁺ + 2Cl⁻", "Ba²⁺ + SO4²⁻ = BaSO4↓"),
    ("нитратом серебра и хлоридом калия", "AgNO3 + KCl = AgCl↓ + KNO3",
     "Ag⁺ + NO3⁻ + K⁺ + Cl⁻ = AgCl↓ + K⁺ + NO3⁻", "Ag⁺ + Cl⁻ = AgCl↓"),
    ("карбонатом натрия и соляной кислотой", "Na2CO3 + 2HCl = 2NaCl + H2O + CO2↑",
     "2Na⁺ + CO3²⁻ + 2H⁺ + 2Cl⁻ = 2Na⁺ + 2Cl⁻ + H2O + CO2↑", "CO3²⁻ + 2H⁺ = H2O + CO2↑"),
    ("сульфатом меди(II) и гидроксидом натрия", "CuSO4 + 2NaOH = Cu(OH)2↓ + Na2SO4",
     "Cu²⁺ + SO4²⁻ + 2Na⁺ + 2OH⁻ = Cu(OH)2↓ + 2Na⁺ + SO4²⁻", "Cu²⁺ + 2OH⁻ = Cu(OH)2↓"),
    ("хлоридом железа(III) и гидроксидом натрия", "FeCl3 + 3NaOH = Fe(OH)3↓ + 3NaCl",
     "Fe³⁺ + 3Cl⁻ + 3Na⁺ + 3OH⁻ = Fe(OH)3↓ + 3Na⁺ + 3Cl⁻", "Fe³⁺ + 3OH⁻ = Fe(OH)3↓"),
    ("гидрокарбонатом натрия и соляной кислотой", "NaHCO3 + HCl = NaCl + H2O + CO2↑",
     "Na⁺ + HCO3⁻ + H⁺ + Cl⁻ = Na⁺ + Cl⁻ + H2O + CO2↑", "HCO3⁻ + H⁺ = H2O + CO2↑"),
    ("гидроксидом меди(II) и азотной кислотой", "Cu(OH)2 + 2HNO3 = Cu(NO3)2 + 2H2O",
     "Cu(OH)2 + 2H⁺ + 2NO3⁻ = Cu²⁺ + 2NO3⁻ + 2H2O", "Cu(OH)2 + 2H⁺ = Cu²⁺ + 2H2O"),
    ("гидроксидом бария и серной кислотой", "Ba(OH)2 + H2SO4 = BaSO4↓ + 2H2O",
     "Ba²⁺ + 2OH⁻ + 2H⁺ + SO4²⁻ = BaSO4↓ + 2H2O", "Ba²⁺ + 2OH⁻ + 2H⁺ + SO4²⁻ = BaSO4↓ + 2H2O (сокращать нечего)"),
    ("хлоридом аммония и гидроксидом натрия (при нагревании)", "NH4Cl + NaOH = NaCl + NH3↑ + H2O",
     "NH4⁺ + Cl⁻ + Na⁺ + OH⁻ = Na⁺ + Cl⁻ + NH3↑ + H2O", "NH4⁺ + OH⁻ = NH3↑ + H2O"),
]


def e30(rng):
    pair, mol, full, short = rng.choice(IONIC_FULL)
    text = "Запишите молекулярное, полное и сокращённое ионное уравнения реакции между %s." % pair
    why = ("%s\n%s\n%s\nНерастворимые вещества, газы и вода записываются в молекулярном виде.\n"
           "Критерии: молекулярное уравнение — 1 балл, полное и сокращённое ионные — 1 балл." % (mol, full, short))
    return text, mol, "long", why


# ЕГЭ 31: описание опытов, 4 реакции. check — те же уравнения для проверки сохранения атомов
DESCRIPTIONS_31 = [
    ("Железо сожгли в хлоре. Полученную соль растворили в воде и добавили раствор гидроксида натрия. Выпавший бурый "
     "осадок отфильтровали и прокалили. Полученное вещество сплавили с карбонатом натрия.",
     ["2Fe + 3Cl2 = 2FeCl3", "FeCl3 + 3NaOH = Fe(OH)3↓ + 3NaCl", "2Fe(OH)3 = Fe2O3 + 3H2O",
      "Fe2O3 + Na2CO3 = 2NaFeO2 + CO2↑"]),
    ("Медь растворили в концентрированной азотной кислоте. Раствор выпарили, остаток прокалили. Твёрдый продукт нагрели "
     "в токе водорода, а полученный металл сожгли в хлоре.",
     ["Cu + 4HNO3 = Cu(NO3)2 + 2NO2↑ + 2H2O", "2Cu(NO3)2 = 2CuO + 4NO2↑ + O2↑", "CuO + H2 = Cu + H2O",
      "Cu + Cl2 = CuCl2"]),
    ("Алюминий растворили в растворе гидроксида натрия. Через полученный раствор пропустили избыток углекислого газа. "
     "Выпавший осадок отфильтровали и прокалили. Полученное вещество сплавили с карбонатом натрия.",
     ["2Al + 2NaOH + 6H2O = 2Na[Al(OH)4] + 3H2↑", "Na[Al(OH)4] + CO2 = Al(OH)3↓ + NaHCO3", "2Al(OH)3 = Al2O3 + 3H2O",
      "Al2O3 + Na2CO3 = 2NaAlO2 + CO2↑"]),
    ("Серу сплавили с железом. Продукт обработали соляной кислотой. Выделившийся газ пропустили через раствор сульфата "
     "меди(II). Образовавшийся чёрный осадок обожгли на воздухе.",
     ["Fe + S = FeS", "FeS + 2HCl = FeCl2 + H2S↑", "H2S + CuSO4 = CuS↓ + H2SO4", "2CuS + 3O2 = 2CuO + 2SO2"]),
]


def e31(rng):
    desc, eqs = rng.choice(DESCRIPTIONS_31)
    why = "%s\nКритерии: по 1 баллу за каждое верное уравнение." % "\n".join("%d) %s" % (i + 1, e) for i, e in enumerate(eqs))
    return desc + "\nНапишите уравнения четырёх описанных реакций.", eqs[0], "long", why


# ЕГЭ 32: органические цепочки. text — структурные формулы, check — молекулярные для проверки атомов
CHAINS_32 = [
    ("CH4 → C2H2 → CH3CHO → CH3COOH → CH3COOC2H5 → CH3COONa",
     ["2CH4 → HC≡CH + 3H2 (1500 °C)", "HC≡CH + H2O → CH3–CHO (Hg²⁺, H⁺)",
      "CH3–CHO + 2Cu(OH)2 → CH3–COOH + Cu2O↓ + 2H2O (t)", "CH3–COOH + C2H5OH ⇄ CH3–COO–C2H5 + H2O (H2SO4 конц., t)",
      "CH3–COO–C2H5 + NaOH → CH3–COONa + C2H5OH (t)"],
     ["2CH4 = C2H2 + 3H2", "C2H2 + H2O = C2H4O", "C2H4O + 2Cu(OH)2 = C2H4O2 + Cu2O + 2H2O",
      "C2H4O2 + C2H6O = C4H8O2 + H2O", "C4H8O2 + NaOH = C2H3O2Na + C2H6O"]),
    ("C2H5OH → C2H4 → C2H4Br2 → C2H2 → C6H6 → C6H5NO2",
     ["CH3–CH2–OH → CH2=CH2 + H2O (H2SO4 конц., t > 140 °C)", "CH2=CH2 + Br2 → CH2Br–CH2Br",
      "CH2Br–CH2Br + 2KOH → HC≡CH + 2KBr + 2H2O (спиртовой р-р, t)", "3HC≡CH → C6H6 (C акт., 600 °C)",
      "C6H6 + HNO3 → C6H5–NO2 + H2O (H2SO4 конц.)"],
     ["C2H6O = C2H4 + H2O", "C2H4 + Br2 = C2H4Br2", "C2H4Br2 + 2KOH = C2H2 + 2KBr + 2H2O", "3C2H2 = C6H6",
      "C6H6 + HNO3 = C6H5NO2 + H2O"]),
    ("CH4 → CH3Cl → CH3OH → HCHO → HCOOH → HCOOCH3",
     ["CH4 + Cl2 → CH3Cl + HCl (свет)", "CH3Cl + NaOH → CH3OH + NaCl (водный р-р)",
      "CH3OH + CuO → HCHO + Cu + H2O (t)", "HCHO + 2Cu(OH)2 → HCOOH + Cu2O↓ + 2H2O (t)",
      "HCOOH + CH3OH ⇄ HCOO–CH3 + H2O (H2SO4 конц., t)"],
     ["CH4 + Cl2 = CH3Cl + HCl", "CH3Cl + NaOH = CH4O + NaCl", "CH4O + CuO = CH2O + Cu + H2O",
      "CH2O + 2Cu(OH)2 = CH2O2 + Cu2O + 2H2O", "CH2O2 + CH4O = C2H4O2 + H2O"]),
]


def e32(rng):
    chain, eqs, _ = rng.choice(CHAINS_32)
    text = ("Напишите уравнения реакций, с помощью которых можно осуществить превращения:\n%s\n"
            "При написании уравнений используйте структурные формулы органических веществ." % chain)
    why = "%s\nКритерии: по 1 баллу за каждое верное уравнение с условиями." % "\n".join(
        "%d) %s" % (i + 1, e) for i, e in enumerate(eqs))
    return text, chain, "long", why


# ЕГЭ 33: формула по продуктам сгорания; строение — по свойству (пропаналь и ацетон — одна формула)
ORGANIC_33 = [
    ("C2H6O", "CH3–CH2–OH (этанол)", "реагирует с натрием с выделением водорода и не реагирует с раствором щёлочи"),
    ("C3H8O", "CH3–CH2–CH2–OH (пропанол-1)", "при окислении оксидом меди(II) образует альдегид"),
    ("C2H4O2", "CH3–COOH (уксусная кислота)", "реагирует с гидрокарбонатом натрия с выделением газа"),
    ("C3H6O", "CH3–CH2–CHO (пропаналь)", "даёт реакцию «серебряного зеркала»"),
    ("C3H6O", "CH3–CO–CH3 (ацетон)", "образуется при окислении пропанола-2 оксидом меди(II)"),
    ("C3H6O2", "CH3–COO–CH3 (метилацетат)", "при щелочном гидролизе образует метанол"),
    ("C7H8", "C6H5–CH3 (толуол)", "является гомологом бензола и окисляется перманганатом калия до бензойной кислоты"),
]


def e33(rng):
    for _ in range(100):
        formula, struct, prop = rng.choice(ORGANIC_33)
        n = rng.choice([0.05, 0.1, 0.15, 0.2, 0.25])
        M = molar_mass(formula)
        c, h = count_atoms(formula, "C"), count_atoms(formula, "H")
        o = count_atoms(formula, "O")
        m, m_co2, m_h2o = n * M, n * c * 44, n * h / 2 * 18
        if any(abs(x * 100 - round(x * 100)) > 1e-6 for x in (m, m_co2, m_h2o)):
            continue
        f2 = lambda x: _fmt(x, 2).rstrip("0").rstrip(",")  # noqa: E731
        mC, mH = n * c * 12, n * h
        mO = m - mC - mH
        text = ("При сгорании %s г органического вещества получили %s г углекислого газа и %s г воды. Плотность паров "
                "вещества по водороду равна %s. Известно, что вещество %s.\nНа основании этих данных: 1) проведите "
                "вычисления и установите молекулярную формулу вещества; 2) составьте его структурную формулу; "
                "3) напишите уравнение реакции, подтверждающей указанное свойство." % (
                    f2(m), f2(m_co2), f2(m_h2o), f2(M / 2), prop))
        why = ("n(CO2) = %s / 44 = %s моль → n(C) = %s моль, m(C) = %s г\n"
               "n(H2O) = %s / 18 = %s моль → n(H) = %s моль, m(H) = %s г\n"
               "m(O) = %s − %s − %s = %s\n"
               "%s; M = 2 · %s = %s г/моль → %s\nСтроение: %s.\n"
               "Критерии: вычисления — 1, молекулярная формула — 1, структура и уравнение — 1."
               % (f2(m_co2), f2(n * c), f2(n * c), f2(mC), f2(m_h2o), f2(n * h / 2), f2(n * h), f2(mH),
                  f2(m), f2(mC), f2(mH),
                  ("%s г → n(O) = %s моль" % (f2(mO), f2(n * o))) if o else "0 — кислорода в веществе нет",
                  ("C : H : O = %d : %d : %d" % (c, h, o)) if o else ("C : H = %d : %d" % (c, h)),
                  f2(M / 2), f2(M), formula, struct))
        return text, formula, "long", why
    return e33(rng)


# ЕГЭ 34: комбинированные расчёты (числа проверены вручную и в тестах)
PROBLEMS_34 = [
    ("Смесь меди и оксида меди(II) массой 20 г обработали избытком концентрированной серной кислоты. Выделилось 4,48 л "
     "(н. у.) газа. Вычислите массовую долю оксида меди(II) в смеси и массу образовавшегося сульфата меди(II).",
     "Cu + 2H2SO4(конц.) = CuSO4 + SO2↑ + 2H2O; CuO + H2SO4 = CuSO4 + H2O\nn(SO2) = 0,2 моль = n(Cu); m(Cu) = 12,8 г; "
     "m(CuO) = 7,2 г; w(CuO) = 36 %\nn(CuSO4) = 0,2 + 0,09 = 0,29 моль; m = 46,4 г\nОтвет: 36 %, 46,4 г."),
    ("Смесь цинка и меди массой 20 г обработали избытком соляной кислоты, выделилось 4,48 л водорода (н. у.). "
     "Вычислите массовую долю меди в смеси и массу образовавшегося хлорида цинка.",
     "Zn + 2HCl = ZnCl2 + H2↑ (медь с соляной кислотой не реагирует)\nn(H2) = 0,2 моль = n(Zn); m(Zn) = 13 г; "
     "m(Cu) = 7 г; w(Cu) = 35 %\nm(ZnCl2) = 0,2 · 136 = 27,2 г\nОтвет: 35 %, 27,2 г."),
    ("Через 200 г раствора гидроксида натрия с массовой долей 8 % пропустили 2,24 л углекислого газа (н. у.). "
     "Вычислите массовую долю карбоната натрия в полученном растворе.",
     "n(NaOH) = 200 · 0,08 / 40 = 0,4 моль; n(CO2) = 0,1 моль — щёлочь в избытке, образуется средняя соль\n"
     "2NaOH + CO2 = Na2CO3 + H2O; n(Na2CO3) = 0,1 моль, m = 10,6 г\nm(р-ра) = 200 + 0,1 · 44 = 204,4 г; "
     "w(Na2CO3) = 10,6 / 204,4 ≈ 5,19 %\nОтвет: 5,19 %."),
    ("Карбонат кальция массой 25 г растворили в 200 г соляной кислоты с массовой долей 14,6 %. Вычислите массовую долю "
     "хлорида кальция в полученном растворе.",
     "CaCO3 + 2HCl = CaCl2 + H2O + CO2↑\nn(CaCO3) = 0,25 моль; n(HCl) = 29,2 / 36,5 = 0,8 моль — кислота в избытке\n"
     "m(CaCl2) = 0,25 · 111 = 27,75 г; m(CO2) = 0,25 · 44 = 11 г\nm(р-ра) = 25 + 200 − 11 = 214 г; "
     "w(CaCl2) = 27,75 / 214 ≈ 12,97 %\nОтвет: 12,97 %."),
]


def e34(rng):
    text, sol = rng.choice(PROBLEMS_34)
    return (text + "\nВ ответе запишите уравнения реакций и приведите все необходимые вычисления.", sol.split("\n")[-1],
            "long", sol + "\nКритерии: уравнения — 1, количества веществ — 1, промежуточные расчёты — 1, ответ — 1.")


GENERATORS.update({("ege", 6): e6, ("ege", 30): e30, ("ege", 31): e31, ("ege", 32): e32, ("ege", 33): e33,
                   ("ege", 34): e34})


_ID = re.compile(r"^g-(o|e)(\d+)-(\d{1,9})$")


def has_generator(exam, num):
    return (exam, num) in GENERATORS


def new_id(exam, num, rng=random):
    return "g-%s%d-%d" % (exam[0], num, rng.randint(1, 10 ** 9 - 1))


def task(task_id):
    """Задача по id варианта или None."""
    m = _ID.match(task_id or "")
    if not m:
        return None
    exam = "oge" if m.group(1) == "o" else "ege"
    num = int(m.group(2))
    gen = GENERATORS.get((exam, num))
    if not gen:
        return None
    text, answer, mode, why = gen(random.Random(int(m.group(3)) * 1000 + num))
    return {"id": task_id, "exam": exam, "num": num, "text": text, "answer": answer, "mode": mode, "why": why,
            "generated": True}
