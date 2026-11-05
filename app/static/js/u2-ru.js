// Тренажёр русского внутри /u2: запятые, основа, орфограмма. Ответ уходит на сервер.
(function () {
  "use strict";
  var root = document.querySelector("[data-u2-ru]");
  if (!root) return;
  var item = JSON.parse(document.getElementById("u2-ru-item").textContent);
  var seed = +root.getAttribute("data-seed");
  var exam = root.getAttribute("data-exam");
  var num = root.getAttribute("data-num");
  var hinted = false;
  var csrf = (document.querySelector('meta[name="csrf"]') || {}).content || "";

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    if (tag === "button") e.type = "button";
    return e;
  }

  function renderComma() {
    var line = el("div", "ru-sentence");
    item.words.forEach(function (w, i) {
      line.append(el("span", "ru-word", w + (i === item.words.length - 1 ? (item.end || "") : "")));
      if (i < item.words.length - 1) {
        var gap = el("button", "ru-gap");
        gap.dataset.gap = String(i);
        gap.addEventListener("click", function () { gap.classList.toggle("on"); });
        line.append(gap);
      }
    });
    root.append(line);
  }

  function renderBasis() {
    var line = el("div", "ru-sentence ru-basis");
    item.words.forEach(function (w, i) {
      var b = el("button", "ru-bword", w);
      b.dataset.word = String(i);
      b.addEventListener("click", function () {
        if (b.classList.contains("ru-u-s")) { b.classList.remove("ru-u-s"); b.classList.add("ru-u-p"); }
        else if (b.classList.contains("ru-u-p")) b.classList.remove("ru-u-p");
        else b.classList.add("ru-u-s");
      });
      line.append(b);
    });
    root.append(line);
  }

  function renderSpell() {
    var line = el("div", "ru-word-big");
    var parts = item.text.split("_");
    if (item.text.indexOf("(не)") === 0) {
      line.append(el("span", "ru-blank", "не"));
      line.append(document.createTextNode(item.text.slice(4)));
    } else {
      parts.forEach(function (p, i) {
        line.append(document.createTextNode(p));
        if (i < parts.length - 1) line.append(el("span", "ru-blank", "?"));
      });
    }
    root.append(line);
    var opts = el("div", "ru-options");
    item.options.forEach(function (o) {
      var b = el("button", "u2-btn ghost ru-opt", o);
      b.addEventListener("click", function () {
        opts.querySelectorAll(".ru-opt").forEach(function (x) { x.classList.remove("on"); });
        b.classList.add("on");
      });
      opts.append(b);
    });
    root.append(opts);
  }

  function answer() {
    if (item.kind === "comma") {
      return Array.prototype.map.call(root.querySelectorAll(".ru-gap.on"), function (g) { return +g.dataset.gap; });
    }
    if (item.kind === "basis") {
      var s = [], p = [];
      root.querySelectorAll(".ru-bword").forEach(function (b) {
        if (b.classList.contains("ru-u-s")) s.push(+b.dataset.word);
        if (b.classList.contains("ru-u-p")) p.push(+b.dataset.word);
      });
      return { s: s, p: p };
    }
    var on = root.querySelector(".ru-opt.on");
    return on ? on.textContent : "";
  }

  function show(data) {
    var box = root.querySelector(".u2-ru-result");
    box.hidden = false;
    box.className = "u2-ru-result " + (data.ok ? "ok" : "bad");
    box.replaceChildren();
    if (data.pending) {
      hinted = true;
      box.append(el("p", "", "Пока не то. Подсказка: " + (data.hint || "")));
      return;
    }
    box.append(el("p", "", data.ok ? "Верно. Записано в этот номер." : "Неверно. Записано в этот номер."));
    if (!data.ok && data.text) box.append(el("p", "", "Правильно: " + data.text));
    if (data.rule_text) box.append(el("p", "u2-hint", data.rule_title + ". " + data.rule_text));
    var next = el("a", "u2-btn", "Ещё вариант");
    next.href = "/u2/train/" + exam + "/" + num;
    box.append(next);
  }

  async function submit() {
    if (item.kind === "spell" && !answer()) return;
    var r = await fetch("/u2/api/ru/" + exam + "/" + num, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      credentials: "same-origin",
      body: JSON.stringify({ id: item.id, seed: seed, answer: answer(), hint: hinted ? 1 : 0 }),
    });
    if (!r.ok) { show({ ok: false, pending: true, hint: "Не получилось отправить. Обнови страницу." }); return; }
    show(await r.json());
  }

  if (item.kind === "comma") renderComma();
  else if (item.kind === "basis") renderBasis();
  else renderSpell();
  var actions = el("div", "u2-actions");
  var btn = el("button", "u2-btn", "Проверить");
  btn.addEventListener("click", submit);
  actions.append(btn);
  root.append(actions, el("div", "u2-ru-result"));
  root.querySelector(".u2-ru-result").hidden = true;
})();
