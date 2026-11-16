"""Каталог интерактивных моделей umedu. Страницы только при CQ_UMEDU2, не на ХимЛабе.

Чужие программы сюда не вшиты: адреса, подписи и темы экзамена. Файлы моделей — в app/static/models.
"""

PHET_CREDIT = "PhET Interactive Simulations, University of Colorado Boulder"

SUBJECTS = (
    ("phys", "Физика"),
    ("chem", "Химия"),
    ("bio", "Биология"),
    ("math", "Математика"),
)

# Русские сборки PhET. Ссылки проверены: каждая *_ru.html отвечает 200.
# Симуляции не копируем (с 2026 лицензия CC BY-NC) — только официальный iframe.
PHET = (
    {"id": "ohms-law", "subject": "phys", "title": "Закон Ома",
     "text": "Как ток зависит от напряжения и сопротивления.",
     "topic": "Физика, постоянный ток. ОГЭ №9, ЕГЭ №11."},
    {"id": "circuit-construction-kit-dc", "subject": "phys", "title": "Конструктор цепей",
     "text": "Собери цепь: последовательное и параллельное соединение.",
     "topic": "Физика, постоянный ток. ОГЭ №9 и №14, ЕГЭ №14 и №20."},
    {"id": "hookes-law", "subject": "phys", "title": "Закон Гука",
     "text": "Сила упругости и удлинение пружины.",
     "topic": "Физика, силы. ОГЭ №6, ЕГЭ №4."},
    {"id": "bending-light", "subject": "phys", "title": "Преломление света",
     "text": "Луч на границе двух сред и закон Снеллиуса.",
     "topic": "Физика, геометрическая оптика. ОГЭ и ЕГЭ."},
    {"id": "geometric-optics", "subject": "phys", "title": "Линзы",
     "text": "Собирающая и рассеивающая линза, где получается изображение.",
     "topic": "Физика, геометрическая оптика. ЕГЭ."},
    {"id": "projectile-motion", "subject": "phys", "title": "Бросок под углом",
     "text": "Траектория тела: скорость, угол и дальность.",
     "topic": "Физика, кинематика. ОГЭ №1, ЕГЭ №1."},
    {"id": "build-an-atom", "subject": "chem", "title": "Собери атом",
     "text": "Протоны, нейтроны и электроны: заряд иона и массовое число.",
     "topic": "Химия, строение атома. ОГЭ и ЕГЭ."},
    {"id": "balancing-chemical-equations", "subject": "chem", "title": "Уравнивание реакций",
     "text": "Подбери коэффициенты, чтобы атомов слева и справа было поровну.",
     "topic": "Химия, химические реакции. ОГЭ №16, ЕГЭ №21."},
    {"id": "ph-scale", "subject": "chem", "title": "Шкала pH",
     "text": "Как кислотность зависит от концентрации ионов.",
     "topic": "Химия, растворы. ЕГЭ."},
    {"id": "molecule-shapes", "subject": "chem", "title": "Форма молекул",
     "text": "Электронные пары отталкиваются — от этого форма молекулы.",
     "topic": "Химия, химическая связь. ЕГЭ."},
    {"id": "neuron", "subject": "bio", "title": "Нейрон",
     "text": "Нервный импульс бежит по аксону и передаётся через синапс.",
     "topic": "Биология, нервная система. ЕГЭ."},
    {"id": "gene-expression-essentials", "subject": "bio", "title": "От гена к белку",
     "text": "Транскрипция и трансляция: как с ДНК читается белок.",
     "topic": "Биология, молекулярная биология. ЕГЭ."},
    {"id": "diffusion", "subject": "bio", "title": "Диффузия",
     "text": "Молекулы идут из области, где их больше, туда, где меньше.",
     "topic": "Биология, клетка и мембрана. ОГЭ и ЕГЭ."},
    {"id": "graphing-quadratics", "subject": "math", "title": "Квадратичная функция",
     "text": "Как коэффициенты двигают параболу.",
     "topic": "Математика, функции. ОГЭ №11, ЕГЭ профиль."},
    {"id": "trig-tour", "subject": "math", "title": "Синус и косинус",
     "text": "Точка на окружности и знаки синуса и косинуса по четвертям.",
     "topic": "Математика, тригонометрия. ЕГЭ профиль."},
)

RAY = "/static/models/ray-optics/simulator/index.html?ru#"
OPTICS = (
    {"id": "convex-lens", "title": "Собирающая линза",
     "text": "Лучи после линзы сходятся. Где они пересекутся — там действительное изображение.",
     "topic": "Физика, линзы. ОГЭ и ЕГЭ, геометрическая оптика."},
    {"id": "concave-lens", "title": "Рассеивающая линза",
     "text": "Лучи после линзы расходятся. Продолжения назад сходятся в мнимом изображении.",
     "topic": "Физика, линзы. ОГЭ и ЕГЭ."},
    {"id": "parabolic-mirror", "title": "Зеркало",
     "text": "Сравни угол падения и угол отражения. У параболы лучи, параллельные оси, сходятся в фокусе.",
     "topic": "Физика, отражение. ОГЭ и ЕГЭ."},
    {"id": "prisms", "title": "Призма",
     "text": "На границе стекло–воздух луч меняет направление. Это преломление.",
     "topic": "Физика, преломление. ОГЭ и ЕГЭ."},
    {"id": "internal-reflection", "title": "Полное отражение",
     "text": "Из стекла в воздух луч при большом угле не выходит наружу, а отражается целиком.",
     "topic": "Физика, полное внутреннее отражение. ЕГЭ."},
)

# Схемы собраны в формате CircuitJS и сжаты так же, как кнопка «Export as link» (lz-string).
# Числа простые, чтобы сверить с законом: наведи на резистор — видны ток и напряжение.
CIRCUIT = "/static/models/circuitjs/circuitjs.html?lang=ru&ctz="
CIRCUITS = (
    {"id": "ohm", "title": "Закон Ома",
     "text": "Источник 6 В и один резистор 10 Ом. Какой ток? Нажми на резистор.",
     "topic": "Физика, закон Ома. ОГЭ №9, ЕГЭ №11.",
     "ctz": "CQAgjCCsB0AMCiBaAbOW0DMBOMAWWWyGGukkA7GVLFHNQFABu45qGATDWK+OwBwgaNfCGR10Q8dEj0ATi1Rh+IDMgFKBXCfQDuKtbwGqjnQbv0muPDkPoBzBStPc2kdmaA"},
    {"id": "series", "title": "Последовательно",
     "text": "12 В, резисторы 4 Ом и 8 Ом один за другим. Где напряжение больше — на каком сопротивлении?",
     "topic": "Физика, последовательное соединение. ОГЭ №9 и №14.",
     "ctz": "CQAgjCCsB0AMCiBaAbOW0DMBOMAWWWyGGukkA7GVLFHNQFABu4YATCMamGy+zTfnCs66fiOiR6AJ16zW5dtz4hccaSHmKeuDFuUAONQHcVu2TvacQseiYscMXHlZsBzWVaUdk+6-SA"},
    {"id": "parallel", "title": "Параллельно",
     "text": "12 В, ветви 6 Ом и 12 Ом. В какой ветви ток больше? Сложи токи ветвей.",
     "topic": "Физика, параллельное соединение. ОГЭ №9 и №14, ЕГЭ №14.",
     "ctz": "CQAgjCCsB0AMCiBaAbOW0DMBOMAWWWyGGukkA7GVLFHNQFABu4uuIxqebhINN+4AEx10fEdEj0A7i26pBADgUgesaSEXKeuDIJWo1AJw1L9J5R14hkcesZ17tu9hgNDbMzS9QPvvdVx+XpZqAOayfoGuympAA"},
    {"id": "switch", "title": "Ключ",
     "text": "Цепь замкнута: 6 В и 10 Ом. Щёлкни по ключу. Что стало с током?",
     "topic": "Физика, электрическая цепь. ОГЭ №9.",
     "ctz": "CQAgjCCsB0AMCiBaAbOW0DMBOMAWWWyGGukkA7GVLFHNQFABu4yNxqYr4ATABwg0a+EMjrpBY6JHoBnFjTB8Q3ctx78aAMwCGAGxkBTEDv0H6AJ2Wr1IXBjWKNaOPQDut+zbtr2Atx58MDi5fWHoAc3kQX042ZA16IA"},
    {"id": "divider", "title": "Делитель",
     "text": "9 В, сверху 10 Ом, снизу 20 Ом. Какое напряжение на нижнем резисторе?",
     "topic": "Физика, последовательное соединение. ОГЭ №14, ЕГЭ №14.",
     "ctz": "CQAgjCCsB0AMCiBaAbOW0DMBOMAWWWyGGukkA7GVLFHNQFABu4uuIGkATC24SDTXwgsddANHRI9AE49hqDJxp8aYMTPZL5mmh240lcegHcd7LnL396Ac0sW8bDAA42sekA"},
)

MOLECULES = (
    {"id": "water", "title": "Вода", "fmt": "sdf", "style": "stick", "file": "water.sdf",
     "text": "H₂O, угловая молекула. Связи O–H полярные.",
     "topic": "Химия, химическая связь. 8–9 класс, ЕГЭ."},
    {"id": "methane", "title": "Метан", "fmt": "sdf", "style": "stick", "file": "methane.sdf",
     "text": "CH₄, тетраэдр. Простейший алкан.",
     "topic": "Химия, алканы. ОГЭ и ЕГЭ, органическая химия."},
    {"id": "ethylene", "title": "Этилен", "fmt": "sdf", "style": "stick", "file": "ethylene.sdf",
     "text": "C₂H₄, двойная связь C=C, молекула плоская.",
     "topic": "Химия, алкены. ЕГЭ."},
    {"id": "acetylene", "title": "Ацетилен", "fmt": "sdf", "style": "stick", "file": "acetylene.sdf",
     "text": "C₂H₂, тройная связь, молекула линейная.",
     "topic": "Химия, алкины. ЕГЭ."},
    {"id": "benzene", "title": "Бензол", "fmt": "sdf", "style": "stick", "file": "benzene.sdf",
     "text": "C₆H₆, плоское кольцо из шести атомов углерода.",
     "topic": "Химия, арены. ЕГЭ."},
    {"id": "ethanol", "title": "Этанол", "fmt": "sdf", "style": "stick", "file": "ethanol.sdf",
     "text": "C₂H₅OH, у углерода спирта есть группа OH.",
     "topic": "Химия, спирты. ОГЭ и ЕГЭ."},
    {"id": "glucose", "title": "Глюкоза", "fmt": "sdf", "style": "stick", "file": "glucose.sdf",
     "text": "C₆H₁₂O₆, углевод. В этой модели — одна из пространственных форм.",
     "topic": "Химия и биология, углеводы. ОГЭ и ЕГЭ."},
    {"id": "nacl", "title": "Решётка NaCl", "fmt": "xyz", "style": "ball", "file": "nacl.xyz",
     "text": "Ионы натрия и хлора чередуются в кубической решётке. Это не молекула, а кристалл.",
     "topic": "Химия, ионная связь и кристаллические решётки. ОГЭ и ЕГЭ."},
    {"id": "dna", "title": "Фрагмент ДНК", "fmt": "pdb", "style": "cartoon", "file": "1bna.pdb",
     "text": "Короткий кусок двойной спирали, структура 1BNA из банка PDB.",
     "topic": "Биология, нуклеиновые кислоты. ЕГЭ."},
    {"id": "protein", "title": "Белок крамбин", "fmt": "pdb", "style": "cartoon", "file": "1crn.pdb",
     "text": "Маленький белок из 46 аминокислот, структура 1CRN. Лента — ход цепи.",
     "topic": "Биология, белки. ЕГЭ."},
)

SECTIONS = (
    {"id": "phys", "title": "Физика", "cards": (
        {"href": "/u2/models/optics", "title": "Оптика", "chip": "лучи",
         "text": "Линза, зеркало и преломление. Готовые сцены, их можно двигать."},
        {"href": "/u2/models/circuits", "title": "Электрические цепи", "chip": "ток",
         "text": "Закон Ома, последовательное и параллельное соединение, ключ."},
        {"href": "/u2/models/phet#phys", "title": "Симуляции PhET", "chip": "физика",
         "text": "Закон Ома, цепи, Гук, свет, бросок под углом."},
    )},
    {"id": "chem", "title": "Химия", "cards": (
        {"href": "/u2/models/molecules", "title": "Молекулы в 3D", "chip": "атомы",
         "text": "Вода, углеводороды, глюкоза, решётка соли, ДНК и белок."},
        {"href": "/u2/models/phet#chem", "title": "Симуляции PhET", "chip": "химия",
         "text": "Атом, уравнивание реакций, pH и форма молекул."},
    )},
    {"id": "bio", "title": "Биология", "cards": (
        {"href": "/u2/models/microcosmos", "title": "Микрокосмос", "chip": "клетка",
         "text": "Капля пруда: инфузории, водоросль, цианобактерия и органоиды."},
        {"href": "/u2/models/phet#bio", "title": "Симуляции PhET", "chip": "биология",
         "text": "Нейрон, от гена к белку, диффузия."},
    )},
    {"id": "math", "title": "Математика", "cards": (
        {"href": "/u2/models/phet#math", "title": "Симуляции PhET", "chip": "графики",
         "text": "Парабола и синус с косинусом на окружности."},
    )},
)


def phet_src(item):
    return "https://phet.colorado.edu/sims/html/%s/latest/%s_ru.html" % (item["id"], item["id"])


def ray_src(item):
    return RAY + item["id"]


def circuit_src(item):
    return CIRCUIT + item["ctz"]


def molecule_src(item):
    return "/static/models/molecules/" + item["file"]
