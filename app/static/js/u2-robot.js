// Робот ОГЭ №15 внутри /u2. Поле и проверка — те же, что в тренажёре, журнал — skill_attempt.
(function () {
  "use strict";
  var root = document.getElementById("robot-app");
  if (!root || !window.CQRunner) return;
  var NS = "http://www.w3.org/2000/svg";
  var runner = CQRunner.runner;
  var fields = JSON.parse(document.getElementById("robot-fields").textContent);
  var starter = JSON.parse(document.getElementById("robot-starter").textContent);
  var csrf = (document.querySelector('meta[name="csrf"]') || {}).content || "";
  var hinted = false;
  var current = 0;
  var $ = function (sel) { return root.querySelector(sel); };
  var svgBox = $(".robot-svg");
  var tabs = $(".robot-tabs");
  var status = $("[data-robot-status]");
  var resultBox = $("[data-robot-result]");
  var ta = $("[data-robot-code]");
  var runBtn = $("[data-robot-run]");
  var checkBtn = $("[data-robot-check]");

  function svg(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (parent) parent.append(n);
    return n;
  }

  function draw(f) {
    var s = Math.max(16, Math.min(32, Math.floor((svgBox.clientWidth || 320) / f.w)));
    var W = f.w * s, H = f.h * s;
    var g = svg("svg", { viewBox: "-2 -2 " + (W + 4) + " " + (H + 4), width: "100%", class: "robot-grid" });
    var x, y;
    for (x = 0; x <= f.w; x++) svg("line", { x1: x * s, y1: 0, x2: x * s, y2: H, class: "rg-line" }, g);
    for (y = 0; y <= f.h; y++) svg("line", { x1: 0, y1: y * s, x2: W, y2: y * s, class: "rg-line" }, g);
    f.target.forEach(function (c) {
      svg("rect", { x: c[0] * s + 4, y: c[1] * s + 4, width: s - 8, height: s - 8, class: "rg-goal" }, g);
    });
    f.walls.forEach(function (w) {
      if (w[2] === "r") svg("line", { x1: (w[0] + 1) * s, y1: w[1] * s, x2: (w[0] + 1) * s, y2: (w[1] + 1) * s, class: "rg-wall" }, g);
      else svg("line", { x1: w[0] * s, y1: (w[1] + 1) * s, x2: (w[0] + 1) * s, y2: (w[1] + 1) * s, class: "rg-wall" }, g);
    });
    var robot = svg("g", { class: "rg-robot" }, g);
    svg("rect", { x: 3, y: 3, width: s - 6, height: s - 6, rx: s / 4 }, robot);
    svg("circle", { cx: s * 0.36, cy: s * 0.42, r: Math.max(1.5, s / 12), class: "rg-eye" }, robot);
    svg("circle", { cx: s * 0.64, cy: s * 0.42, r: Math.max(1.5, s / 12), class: "rg-eye" }, robot);
    robot.setAttribute("transform", "translate(" + f.start[0] * s + "," + f.start[1] * s + ")");
    svgBox.replaceChildren(g);
  }

  function renderTabs() {
    tabs.replaceChildren();
    fields.forEach(function (_, i) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "robot-tab" + (i === current ? " active" : "");
      b.textContent = i === 0 ? "Пример" : "Поле " + (i + 1);
      b.addEventListener("click", function () { current = i; renderTabs(); draw(fields[i]); });
      tabs.append(b);
    });
  }

  async function ready() {
    status.textContent = "Загружаю Python…";
    try { await runner.start(); status.textContent = ""; return true; }
    catch (e) { status.textContent = "Не получилось загрузить Python. Обнови страницу."; return false; }
  }

  async function report(passed, code) {
    var r = await fetch("/u2/api/play/" + root.dataset.exam + "/" + root.dataset.num, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      credentials: "same-origin",
      body: JSON.stringify({ seed: +root.dataset.seed, passed: passed, hint: hinted ? 1 : 0, code: code }),
    });
    if (!r.ok) return null;
    return r.json();
  }

  function say(ok, text) {
    resultBox.hidden = false;
    resultBox.className = "robot-result " + (ok ? "ok" : "bad");
    resultBox.textContent = text;
  }

  runBtn.addEventListener("click", async function () {
    if (!(await ready())) return;
    status.textContent = "Робот работает…";
    var res = await runner.robot(ta.value, [fields[current]]);
    status.textContent = "";
    var row = res.results && res.results[0];
    say(row && row.ok, row && row.ok ? "На этом поле верно. Проверь на всех полях." : "На этом поле не сошлось.");
  });

  checkBtn.addEventListener("click", async function () {
    if (!(await ready())) return;
    status.textContent = "Проверяю…";
    var code = ta.value;
    var res = await runner.robot(code, fields);
    status.textContent = "";
    var passed = !!res.passed;
    var data = await report(passed, code);
    if (!data) return;
    if (data.pending) {
      hinted = true;
      say(false, "Пока не на всех полях. Подсказка: " + data.hint);
      return;
    }
    say(data.ok, data.ok ? "Верно на всех полях. Записано в №15." : "Неверно. Попытка записана.");
    if (data.solution && data.solution.py) {
      var ans = document.querySelector("[data-robot-answer]");
      ans.hidden = false;
      ans.querySelector("[data-robot-sol-py]").textContent = data.solution.py;
    }
  });

  $("[data-robot-reset]").addEventListener("click", function () { ta.value = starter; });
  renderTabs();
  draw(fields[0]);
})();
