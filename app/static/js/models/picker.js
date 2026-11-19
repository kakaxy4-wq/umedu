/* Переключает готовую сцену в одном iframe. Без встроенного кода на странице.
   Для PhET ждёт сообщение о загрузке: если сайт Колорадо молчит, показывает запасной текст. */
(function () {
  var frame = document.getElementById("model-frame");
  var note = document.getElementById("model-note");
  var buttons = document.querySelectorAll("[data-src]");
  if (!frame || !buttons.length) return;
  var external = frame.getAttribute("data-external") === "phet";
  var status = document.getElementById("phet-status");
  var ticket = 0;
  var timer = 0;
  var WAIT_MS = 12000;

  function withSignal(src) {
    if (src.indexOf("postMessageOnLoad") !== -1) return src;
    return src + (src.indexOf("?") === -1 ? "?" : "&") + "postMessageOnLoad";
  }

  function arm(my) {
    if (!status) return;
    status.hidden = false;
    status.className = "model-status";
    status.textContent = "Загружаем симуляцию…";
    clearTimeout(timer);
    timer = setTimeout(function () {
      if (my !== ticket || !status) return;
      status.className = "model-status is-bad";
      status.textContent = "Симуляция не открылась внутри страницы. Открой «Оптика», «Электрические цепи» или «Молекулы» — они на этом сайте.";
    }, WAIT_MS);
  }

  function loaded() {
    clearTimeout(timer);
    if (status) status.hidden = true;
  }

  function show(btn) {
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute("aria-pressed", buttons[i] === btn ? "true" : "false");
    }
    var title = btn.getAttribute("data-title") || "Модель";
    var src = btn.getAttribute("data-src") || "";
    frame.title = title;
    if (note) note.textContent = btn.getAttribute("data-note") || "";
    if (external) {
      var my = ++ticket;
      frame.src = withSignal(src);
      arm(my);
    } else {
      frame.src = src;
    }
  }

  if (external) {
    window.addEventListener("message", function (event) {
      if (event.origin !== "https://phet.colorado.edu") return;
      var data = event.data;
      if (typeof data === "string") {
        try { data = JSON.parse(data); } catch (err) { return; }
      }
      if (data && (data.type === "load" || data.type === "ready")) loaded();
    });
  }

  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener("click", function (event) { show(event.currentTarget); });
  }
  show(buttons[0]);
})();
