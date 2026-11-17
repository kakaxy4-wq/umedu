/* Галерея молекул на своём 3Dmol.js. Вращение и масштаб — мышь и палец, это умеет сам просмотрщик. */
(function () {
  var box = document.getElementById("mol-view");
  var note = document.getElementById("model-note");
  var buttons = document.querySelectorAll("[data-mol]");
  var lib = window.$3Dmol || window["3Dmol"];
  if (!box || !lib || !lib.createViewer || !buttons.length) return;
  box.style.position = "relative";
  box.style.overflow = "hidden";
  var viewer = lib.createViewer(box, { backgroundColor: "#F7F6FC" });
  viewer.resize();

  function draw(text, fmt, style) {
    viewer.clear();
    viewer.addModel(text, fmt);
    if (style === "cartoon") viewer.setStyle({}, { cartoon: { color: "spectrum" } });
    else if (style === "ball") viewer.setStyle({}, { sphere: { scale: 0.28 } });
    else viewer.setStyle({}, { stick: { radius: 0.15 }, sphere: { scale: 0.25 } });
    viewer.zoomTo();
    viewer.render();
  }

  function show(btn) {
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute("aria-pressed", buttons[i] === btn ? "true" : "false");
    }
    if (note) note.textContent = btn.getAttribute("data-note") || "";
    fetch(btn.getAttribute("data-url")).then(function (res) {
      if (!res.ok) throw new Error("model");
      return res.text();
    }).then(function (text) {
      draw(text, btn.getAttribute("data-fmt"), btn.getAttribute("data-style"));
    }).catch(function () {
      if (note) note.textContent = "Модель не открылась. Обнови страницу.";
    });
  }

  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener("click", function (event) { show(event.currentTarget); });
  }
  window.addEventListener("resize", function () { viewer.resize(); });
  show(buttons[0]);
})();
