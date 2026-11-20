// №16 внутри /u2: проверка тестов — в браузере, как на старом тренажёре. Журнал — на сервере.
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", function () {
    var box = document.querySelector(".codebox[data-u2-code]");
    if (!box) return;
    var hinted = false;
    var csrf = (document.querySelector('meta[name="csrf"]') || {}).content || "";
    box.addEventListener("cq:checked", async function (e) {
      var passed = !!(e.detail.res && e.detail.res.passed);
      var code = e.detail.code || "";
      var r;
      try {
        r = await fetch("/u2/api/play/" + box.dataset.exam + "/" + box.dataset.num, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          credentials: "same-origin",
          body: JSON.stringify({ seed: +box.dataset.seed, passed: passed, hint: hinted ? 1 : 0, code: code }),
        });
      } catch (err) { return; }
      if (!r.ok) return;
      var data = await r.json();
      var note = document.createElement("p");
      note.className = "u2-hint";
      if (data.pending) {
        hinted = true;
        note.textContent = "Пока не то. Подсказка: " + data.hint;
      } else {
        note.textContent = data.ok ? "Верно. Записано в №16." : "Неверно. Попытка записана.";
        if (data.solution && data.solution.py) {
          var sol = document.getElementById("u2-solution");
          sol.hidden = false;
          sol.querySelector("pre").textContent = data.solution.py;
        }
      }
      box.append(note);
    });
  });
})();
