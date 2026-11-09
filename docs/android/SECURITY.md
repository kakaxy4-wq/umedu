# Часть 5. Безопасность и зависимости

Код открыт. То, что спрятано только внутри APK, спрятанным не считается.

Защищаем: почту, имя, идентификаторы VK ID и Яндекс ID, ответы и прогноз, ссылку родителя. Честность прогноза: балл двигает только сервер.

Не обещаем: защиту от накрутки серии в скачанной пачке; защиту от своего APK; защиту данных от root на Android 8.

## Закрыто в коде этапа 1

- HTTPS only, `usesCleartextTraffic=false`, в trust-anchors только `system`. Пиннинга нет.
- User-Agent `umedu-android/{version}`, без идентификатора устройства.
- Облачный бэкап выключен (`allowBackup=false` и data extraction rules).
- В release-графе нет play-services / firebase / crashlytics / ads / appmetrica / mytracker / appsflyer / facebook — ловит `tests/test_android_gates.py`.
- Крошка падения: `app/crash_report.py` режет всё кроме белого списка. Тест подсовывает черновик ответа.

Access в памяти, refresh в Tink — этап 4. SQLCipher, Play Integrity, FLAG_SECURE — не делаем.

## Зависимости v1 (версии — в `android/gradle/libs.versions.toml`)

| Компонент | Где | Лицензия | Что уходит |
|---|---|---|---|
| Kotlin, coroutines, serialization | приложение | Apache-2.0 | ничего |
| AndroidX core, activity, lifecycle, compose, material3 | приложение | Apache-2.0 | ничего |
| OkHttp | приложение | Apache-2.0 | HTTPS к umedu.ru |
| JUnit | тесты | EPL-2.0 | в APK нет |
| FastAPI, Uvicorn, Pydantic, Jinja2 | сервер | MIT / BSD-3 | VPS в РФ |
| SQLite | сервер | Public Domain | диск VPS |

GPL-2.0-only запрещена. Hilt, Room, Coil, Tink, WorkManager — в граф, когда появится код этапа 2–4, и сразу строка в этой таблице.

Рекомендации владельцу, ещё не закрытые фактом: дампы VPS 30 дней в РФ; пользовательский CA в release не принимать; в Telegram до публичного приложения — ссылка на кабинет без балла.
