# Лицензии интерактивных моделей

Раздел «Интерактивные модели» есть только на umedu, за флагом `CQ_UMEDU2`.
КодКвест и ХимЛаб эти страницы не показывают. Файлы лежат в `app/static/models`
и не входят в общий бандл сайта.

## Microcosmos

- Что это: трёхмерная капля пруда (инфузории, водоросль, цианобактерия, органоиды).
- Автор: Felipe Reigosa.
- Исходники: https://github.com/felipereigosa/microcosmos
- Лицензия: GPL-3.0. Текст: `app/static/models/microcosmos/LICENSE`.
- Что изменено: тексты карточек и подписи интерфейса переведены на русский.
  Перевод исходника `info.js` лежит рядом со сборкой. Список правок: `CHANGES.txt`.
- Страница: `/u2/models/microcosmos`, сама модель — `/static/models/microcosmos/microcosmos.html`.
- Музыка `music.mp3` в копию не входит. Это «Dreams Become Real», Kevin MacLeod
  (incompetech.com), лицензия CC BY 4.0. Если файл положить рядом со страницей модели,
  кнопка звука появится сама, подпись автора уже есть в кнопке.

## PhET

- Что это: 15 симуляций по физике, химии, биологии и математике, русские версии `*_ru.html`.
- Правообладатель: PhET Interactive Simulations, University of Colorado Boulder.
- Сайт: https://phet.colorado.edu
- Как встроено: только официальный iframe на `phet.colorado.edu`. Файлы симуляций не копируются.
- Лицензия симуляций с 2026 года: CC BY-NC. Некоммерческое использование в школе этому не противоречит,
  но свою копию мы не делаем.
- Обязательная атрибуция на странице: «PhET Interactive Simulations, University of Colorado Boulder».

## 3Dmol.js и модели молекул

- Просмотрщик: 3Dmol.js 2.5.5.
- Правообладатель: University of Pittsburgh и участники проекта.
- Исходники: https://github.com/3dmol/3Dmol.js
- Лицензия: BSD-3-Clause. Текст: `app/static/models/molecules/LICENSE`.
  В сборке также отмечены куски GLmol, Three.js и jQuery, см. `3Dmol-min.js.LICENSE.txt`.
- Скрипт лежит у нас: `app/static/models/molecules/3Dmol-min.js`. С чужого CDN он не грузится.
- Малые молекулы: трёхмерные структуры PubChem (вода, метан, этилен, ацетилен, бензол, этанол, глюкоза).
- ДНК: структура 1BNA, RCSB PDB. Белок: структура 1CRN (крамбин), RCSB PDB.
- Решётка NaCl: учебная модель ячейки каменной соли, файл `nacl.xyz`, собрана для этой страницы.

## Ray Optics Simulation

- Что это: геометрическая оптика, лучи, линзы, зеркала.
- Автор: Yi-Ting Tu и участники проекта.
- Исходники: https://github.com/ricktu288/ray-optics
- Лицензия: Apache-2.0. Текст: `app/static/models/ray-optics/LICENSE`.
- Как встроено: своя копия сборки симулятора, русские строки и пять учебных сцен.
  Целиком галерея проекта не копировалась. Заметки: `NOTICE.txt`.
- Официальная русская версия, с которой сверена сборка: https://phydemo.app/ray-optics/ru/

## CircuitJS1

- Что это: симулятор электрических цепей.
- Авторы: Paul Falstad и Iain Sharp.
- Исходники: https://github.com/pfalstad/circuitjs1
- Лицензия: GPL-2.0-or-later. Текст GPL-2.0: `app/static/models/circuitjs/COPYING.txt`.
  В заголовках исходников сказано: версия 2 или, по выбору, любая более новая.
- Как встроено: своя копия сборки (`npm run build`), включая `locale_ru.txt`.
  Скрипт Dropbox из страницы убран. Заметки: `NOTICE.txt`.
- Шрифт значков поставляется вместе со сборкой, лицензия значков — `circuitjs/font/webfontlicense.html`.
