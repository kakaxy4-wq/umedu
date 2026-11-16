/* Переключает готовую сцену в одном iframe. Без встроенного кода на странице. */
(function () {
  var frame = document.getElementById("model-frame");
  var note = document.getElementById("model-note");
  var buttons = document.querySelectorAll("[data-src]");
  if (!frame || !buttons.length) return;

  function show(btn) {
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute("aria-pressed", buttons[i] === btn ? "true" : "false");
    }
    var title = btn.getAttribute("data-title") || "Модель";
    frame.title = title;
    frame.src = btn.getAttribute("data-src");
    if (note) note.textContent = btn.getAttribute("data-note") || "";
  }

  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener("click", function (event) { show(event.currentTarget); });
  }
  show(buttons[0]);
})();
