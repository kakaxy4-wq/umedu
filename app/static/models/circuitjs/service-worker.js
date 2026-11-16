/* Пустой worker: сборка CircuitJS регистрирует service-worker.js.
   Файла из dist.sh здесь нет, поэтому регистрация не должна падать 404.
   Запросы не перехватываем. */
self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (event) { event.waitUntil(self.clients.claim()); });
