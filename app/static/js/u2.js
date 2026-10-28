// umedu 2.0: тема оформления. Выбор хранится в браузере; без выбора — как в системе (prefers-color-scheme).
(function () {
  var KEY = "u2-theme";
  function get() { try { return localStorage.getItem(KEY) || ""; } catch (e) { return ""; } }
  function apply(t) {
    if (t) document.documentElement.setAttribute("data-theme", t);
    else document.documentElement.removeAttribute("data-theme");
  }
  apply(get());   // скрипт в <head> — тема ставится до отрисовки, без вспышки
  document.addEventListener("DOMContentLoaded", function () {
    var btns = document.querySelectorAll("[data-theme-set]");
    function mark() {
      var cur = get();
      btns.forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-theme-set") === cur ? "true" : "false"); });
    }
    btns.forEach(function (b) {
      b.addEventListener("click", function () {
        var t = b.getAttribute("data-theme-set");
        try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch (e) { /* приватный режим */ }
        apply(t);
        mark();
      });
    });
    mark();
  });
})();
