// Движок лаборатории: шаги цикла, ползунки, приборы, таблица, график, сцена на canvas.
// Формулы те же, что в JSON и в app/labs.py. Зависимостей нет.
(function (root) {
  var scenes = {};

  function scene(name, draw) { scenes[name] = draw; }

  function canon(x) {
    var n = Math.round(Number(x) * 1000000) / 1000000;
    if (Math.abs(n - Math.round(n)) < 1e-9) return String(Math.round(n));
    return n.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
  }

  function fnv(text) {
    var h = 2166136261;
    for (var i = 0; i < text.length; i++) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h >>> 0;
  }

  function quantize(value, division) {
    if (!division) return value;
    var steps = value / division;
    var rounded = steps >= 0 ? Math.floor(steps + 0.5) : Math.ceil(steps - 0.5);
    return rounded * division;
  }

  function evalExpr(src, names) {
    var s = String(src).replace(/ /g, "");
    var i = 0;
    function peek() { return i < s.length ? s.charAt(i) : ""; }
    function parseExpr() {
      var v = parseTerm();
      while (i < s.length && (peek() === "+" || peek() === "-")) {
        var op = s.charAt(i++);
        var r = parseTerm();
        v = op === "+" ? v + r : v - r;
      }
      return v;
    }
    function parseTerm() {
      var v = parseFactor();
      while (i < s.length && (peek() === "*" || peek() === "/")) {
        var op = s.charAt(i++);
        var r = parseFactor();
        if (op === "/" && r === 0) throw new Error("деление на ноль");
        v = op === "*" ? v * r : v / r;
      }
      return v;
    }
    function parseFactor() {
      if (peek() === "+") { i++; return parseFactor(); }
      if (peek() === "-") { i++; return -parseFactor(); }
      if (peek() === "(") {
        i++;
        var v = parseExpr();
        if (peek() !== ")") throw new Error("скобка");
        i++;
        return v;
      }
      if ((peek() >= "0" && peek() <= "9") || peek() === ".") {
        var j = i;
        while (i < s.length && ((s.charAt(i) >= "0" && s.charAt(i) <= "9") || s.charAt(i) === ".")) i++;
        return parseFloat(s.slice(j, i));
      }
      if (/[A-Za-z_]/.test(peek())) {
        var k = i;
        while (i < s.length && /[A-Za-z0-9_]/.test(s.charAt(i))) i++;
        var name = s.slice(k, i);
        if (!Object.prototype.hasOwnProperty.call(names, name)) throw new Error(name);
        return +names[name];
      }
      throw new Error("формула");
    }
    var value = parseExpr();
    if (i !== s.length) throw new Error("формула");
    return value;
  }

  function evalOutputs(outputs, constants, controls) {
    var names = {};
    Object.keys(constants || {}).forEach(function (k) { names[k] = +constants[k]; });
    Object.keys(controls).forEach(function (k) { names[k] = +controls[k]; });
    var out = {};
    Object.keys(outputs).forEach(function (k) {
      out[k] = evalExpr(outputs[k], names);
      names[k] = out[k];
    });
    return out;
  }

  function meterReading(trueValue, meter, seed, controls) {
    var keys = Object.keys(controls).sort();
    var key = seed + "|" + meter.id + "|" + keys.map(function (k) {
      return k + "=" + canon(controls[k]);
    }).join("|");
    var unit = fnv(key) / 4294967295;
    var wobble = (unit * 2 - 1) * (+meter.noise || 0);
    return quantize(+trueValue + wobble, +meter.division || 0);
  }

  function digits(division) {
    if (!division || division >= 1) return 0;
    return Math.min(4, Math.ceil(-Math.log10(division) - 1e-9));
  }

  function fmt(x, division) {
    if (!isFinite(x)) return "—";
    var d = digits(division);
    var s = (+x).toFixed(d);
    if (d === 0) return s.replace(".", ",");
    return s.replace(".", ",");
  }

  function boot() {
    var node = document.getElementById("lab-config");
    if (!node) return;
    var cfg = JSON.parse(node.textContent);
    var state = {};
    cfg.controls.forEach(function (c) { state[c.id] = +c.value; });
    var rows = [];
    var view = { controls: state, out: {}, shown: {}, time: 0, cfg: cfg };
    var raf = 0;
    root.__labFrames = 0;

    function colors() {
      var s = getComputedStyle(document.documentElement);
      function v(name, fb) { return (s.getPropertyValue(name) || "").trim() || fb; }
      return {
        text: v("--text", "#14112A"), muted: v("--muted", "#6B6688"), line: v("--line", "#E4E2F0"),
        card: v("--card", "#FFFFFF"), bg: v("--bg", "#F6F5FB"), ultra: v("--ultra", "#3A2BFF"),
        lime: v("--lime", "#C6FF1A"), good: v("--good", "#19B36B"), weak: v("--weak", "#FF5A4E"),
        ink: v("--ink", "#14112A")
      };
    }

    function fit(canvas) {
      var dpr = Math.min(root.devicePixelRatio || 1, 2);
      var w = canvas.clientWidth || 320;
      var h = canvas.clientHeight || 220;
      var pw = Math.max(1, Math.round(w * dpr));
      var ph = Math.max(1, Math.round(h * dpr));
      if (canvas.width !== pw || canvas.height !== ph) {
        canvas.width = pw;
        canvas.height = ph;
      }
      var g = canvas.getContext("2d");
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      return { g: g, w: w, h: h };
    }

    function compute() {
      var out = evalOutputs(cfg.outputs, cfg.constants, state);
      var shown = {};
      cfg.meters.forEach(function (m) {
        shown[m.id] = meterReading(out[m.id], m, cfg.seed, state);
      });
      view.out = out;
      view.shown = shown;
      return shown;
    }

    function paintMeters(shown) {
      cfg.meters.forEach(function (m) {
        var el = document.querySelector('[data-meter="' + m.id + '"]');
        if (el) el.textContent = fmt(shown[m.id], m.division) + " " + m.unit;
      });
    }

    function draw() {
      var canvas = document.getElementById("lab-scene");
      if (!canvas) return;
      var box = fit(canvas);
      view.w = box.w;
      view.h = box.h;
      view.colors = colors();
      view.controls = state;
      try {
        if (scenes[cfg.scene]) scenes[cfg.scene](box.g, view);
      } catch (err) {
        box.g.fillStyle = view.colors.weak;
        box.g.font = "14px sans-serif";
        box.g.fillText(String(err && err.message || err).slice(0, 90), 12, 28);
      }
      root.__labFrames += 1;
    }

    function loop(t) {
      view.time = t / 1000;
      compute();
      draw();
      raf = root.requestAnimationFrame(loop);
    }

    function startLoop() {
      if (raf) return;
      compute();
      paintMeters(view.shown);
      raf = root.requestAnimationFrame(loop);
    }

    function stopLoop() {
      if (raf) root.cancelAnimationFrame(raf);
      raf = 0;
    }

    function labelOf(control, value) {
      if (control.type === "switch") return value >= 0.5 ? "замкнут" : "разомкнут";
      if (control.type === "choice") {
        var opt = (control.options || []).filter(function (o) { return Math.abs(+o.value - value) < 1e-6; })[0];
        return opt ? opt.label : canon(value);
      }
      return fmt(value, control.step && control.step < 1 ? control.step : 0) + (control.unit ? " " + control.unit : "");
    }

    function buildControls() {
      var host = document.getElementById("lab-controls");
      cfg.controls.forEach(function (c) {
        var wrap = document.createElement("label");
        wrap.className = "lab-ctl";
        var title = document.createElement("span");
        title.textContent = c.label;
        wrap.appendChild(title);
        if ((c.type || "range") === "switch") {
          var btn = document.createElement("button");
          btn.type = "button";
          btn.className = "u2-btn ghost lab-switch";
          btn.setAttribute("data-ctl", c.id);
          var paint = function () {
            var on = state[c.id] >= 0.5;
            btn.textContent = on ? "Замкнут" : "Разомкнут";
            btn.setAttribute("aria-pressed", on ? "true" : "false");
          };
          btn.addEventListener("click", function () {
            state[c.id] = state[c.id] >= 0.5 ? 0 : 1;
            paint();
            refresh();
          });
          paint();
          wrap.appendChild(btn);
        } else if (c.type === "choice") {
          var sel = document.createElement("select");
          sel.setAttribute("data-ctl", c.id);
          c.options.forEach(function (o) {
            var opt = document.createElement("option");
            opt.value = String(o.value);
            opt.textContent = o.label;
            if (Math.abs(+o.value - state[c.id]) < 1e-6) opt.selected = true;
            sel.appendChild(opt);
          });
          sel.addEventListener("change", function () {
            state[c.id] = +sel.value;
            refresh();
          });
          wrap.appendChild(sel);
        } else {
          var row = document.createElement("span");
          row.className = "lab-slider";
          var input = document.createElement("input");
          input.type = "range";
          input.min = String(c.min);
          input.max = String(c.max);
          input.step = String(c.step || 1);
          input.value = String(c.value);
          input.setAttribute("data-ctl", c.id);
          input.setAttribute("aria-label", c.label);
          var out = document.createElement("b");
          var paint = function () {
            var text = labelOf(c, state[c.id]);
            out.textContent = text;
            input.setAttribute("aria-valuetext", text);
          };
          input.addEventListener("input", function () {
            state[c.id] = +input.value;
            paint();
            refresh();
          });
          paint();
          row.appendChild(input);
          row.appendChild(out);
          wrap.appendChild(row);
        }
        host.appendChild(wrap);
      });
    }

    function buildMeters() {
      var host = document.getElementById("lab-meters");
      cfg.meters.forEach(function (m) {
        var box = document.createElement("div");
        box.className = "lab-meter";
        var span = document.createElement("span");
        span.textContent = m.label;
        var b = document.createElement("b");
        b.setAttribute("data-meter", m.id);
        box.appendChild(span);
        box.appendChild(b);
        host.appendChild(box);
      });
    }

    function buildTableHead() {
      var tr = document.createElement("tr");
      cfg.controls.forEach(function (c) {
        var th = document.createElement("th");
        th.textContent = c.type === "switch" ? "Ключ" : (c.unit ? c.id + ", " + c.unit : c.id);
        tr.appendChild(th);
      });
      cfg.meters.forEach(function (m) {
        var thm = document.createElement("th");
        thm.textContent = m.unit ? m.id + ", " + m.unit : m.id;
        tr.appendChild(thm);
      });
      document.querySelector("#lab-table thead").appendChild(tr);
    }

    function distinctX() {
      var key = cfg.graph.x;
      var seen = {};
      rows.forEach(function (r) { seen[canon(r.controls[key])] = 1; });
      return Object.keys(seen).length;
    }

    function ready() {
      return rows.length >= cfg.min_points && distinctX() >= cfg.min_distinct;
    }

    function needText() {
      var el = document.getElementById("lab-need");
      if (ready()) {
        el.textContent = "Точек достаточно — можно сравнивать с предсказанием.";
        return;
      }
      var left = Math.max(0, cfg.min_points - rows.length);
      var dx = Math.max(0, cfg.min_distinct - distinctX());
      el.textContent = "Запиши ещё " + (left || "пару") + " показаний" +
        (dx ? " при разных значениях («" + cfg.graph.xlabel + "»)." : ".");
    }

    function addRow() {
      var shown = compute();
      var copy = {};
      var show = {};
      Object.keys(state).forEach(function (k) { copy[k] = state[k]; });
      Object.keys(shown).forEach(function (k) { show[k] = shown[k]; });
      rows.push({ controls: copy, shown: show });
      var tr = document.createElement("tr");
      cfg.controls.forEach(function (c) {
        var td = document.createElement("td");
        td.textContent = labelOf(c, copy[c.id]);
        tr.appendChild(td);
      });
      cfg.meters.forEach(function (m) {
        var td = document.createElement("td");
        td.textContent = fmt(show[m.id], m.division);
        tr.appendChild(td);
      });
      document.querySelector("#lab-table tbody").appendChild(tr);
      drawGraph();
      document.getElementById("lab-to-compare").disabled = !ready();
      needText();
    }

    function drawGraph() {
      var svg = document.getElementById("lab-graph");
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      var ns = "http://www.w3.org/2000/svg";
      function el(name, attrs) {
        var n = document.createElementNS(ns, name);
        Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
        svg.appendChild(n);
        return n;
      }
      el("rect", { x: 0, y: 0, width: 320, height: 180, rx: 12, fill: "none" });
      var xk = cfg.graph.x;
      var yk = cfg.graph.y;
      var meter = cfg.meters.filter(function (m) { return m.id === yk; })[0] || {};
      var pts = rows.map(function (r) { return [r.controls[xk], r.shown[yk]]; });
      el("line", { x1: 48, y1: 148, x2: 304, y2: 148, stroke: "currentColor", "stroke-width": 1.5 });
      el("line", { x1: 48, y1: 18, x2: 48, y2: 148, stroke: "currentColor", "stroke-width": 1.5 });
      var lx = el("text", { x: 176, y: 170, "text-anchor": "middle", fill: "currentColor" });
      lx.textContent = cfg.graph.xlabel;
      var ly = el("text", { x: 16, y: 86, fill: "currentColor", transform: "rotate(-90 16 86)" });
      ly.textContent = cfg.graph.ylabel;
      if (!pts.length) return;
      var xs = pts.map(function (p) { return p[0]; });
      var ys = pts.map(function (p) { return p[1]; });
      var minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs);
      var minY = Math.min.apply(null, ys.concat([0])), maxY = Math.max.apply(null, ys.concat([meter.max || 0]));
      if (maxX === minX) maxX = minX + 1;
      if (maxY === minY) maxY = minY + 1;
      function X(x) { return 48 + (x - minX) / (maxX - minX) * 246; }
      function Y(y) { return 148 - (y - minY) / (maxY - minY) * 120; }
      var sorted = pts.slice().sort(function (a, b) { return a[0] - b[0]; });
      el("polyline", {
        fill: "none", stroke: "currentColor", "stroke-width": 2,
        points: sorted.map(function (p) { return X(p[0]).toFixed(1) + "," + Y(p[1]).toFixed(1); }).join(" ")
      });
      pts.forEach(function (p) {
        el("circle", { cx: X(p[0]).toFixed(1), cy: Y(p[1]).toFixed(1), r: 4, fill: "currentColor" });
      });
    }

    function refresh() {
      paintMeters(compute());
      if (!raf) draw();
    }

    function go(step) {
      document.querySelectorAll("[data-step]").forEach(function (el) {
        el.hidden = el.getAttribute("data-step") !== step;
      });
      document.querySelectorAll("[data-crumb]").forEach(function (el) {
        var on = el.getAttribute("data-crumb") === step;
        el.classList.toggle("on", on);
        if (on) el.setAttribute("aria-current", "step");
        else el.removeAttribute("aria-current");
      });
      if (step === "experiment") startLoop();
      else stopLoop();
      if (step === "law") {
        var note = document.getElementById("lab-from-data");
        if (note) note.textContent = dataSentence();
      }
    }

    function dataSentence() {
      if (rows.length < 2) return "";
      var x = cfg.graph.x, y = cfg.graph.y;
      var sorted = rows.slice().sort(function (a, b) { return a.controls[x] - b.controls[x]; });
      var a = sorted[0], b = sorted[sorted.length - 1];
      if (a.controls[x] === b.controls[x]) return "В таблице мало разных значений — сними ещё точки.";
      var dy = b.shown[y] - a.shown[y];
      if (dy > 0) return "По твоим точкам «" + cfg.graph.ylabel + "» растёт вместе с «" + cfg.graph.xlabel + "».";
      if (dy < 0) return "По твоим точкам «" + cfg.graph.ylabel + "» уменьшается, когда растёт «" + cfg.graph.xlabel + "».";
      return "По твоим точкам «" + cfg.graph.ylabel + "» почти не менялась.";
    }

    function post(data) {
      var body = new URLSearchParams();
      Object.keys(data).forEach(function (k) { body.set(k, data[k]); });
      var token = document.querySelector('meta[name="csrf"]').getAttribute("content");
      return fetch("/u2/lab/" + cfg.id + "/check", {
        method: "POST",
        headers: { "X-CSRF-Token": token, "Accept": "application/json" },
        body: body
      }).then(function (r) {
        return r.json().then(function (j) {
          if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "Не удалось проверить");
          return j;
        });
      });
    }

    buildControls();
    buildMeters();
    buildTableHead();
    needText();
    drawGraph();
    refresh();

    document.getElementById("lab-record").addEventListener("click", addRow);
    document.getElementById("lab-check").addEventListener("click", function () {
      var input = document.getElementById("lab-value");
      var out = document.getElementById("lab-check-out");
      post({ kind: "reading", value: input.value }).then(function (res) {
        out.textContent = (res.ok ? "Сходится. " : "Пока не так. ") + res.explain;
        if (res.ok) document.getElementById("lab-to-law").disabled = false;
      }).catch(function (err) {
        out.textContent = err.message || "Не получилось отправить. Попробуй ещё раз.";
      });
    });
    document.querySelector(".lab-run").addEventListener("click", function (ev) {
      var btn = ev.target.closest("[data-next]");
      if (!btn || btn.disabled) return;
      var next = btn.getAttribute("data-next");
      if (next === "experiment") {
        var chosen = document.querySelector('input[name="predict"]:checked');
        var err = document.getElementById("lab-predict-err");
        if (!chosen) {
          err.textContent = "Сначала выбери вариант.";
          return;
        }
        err.textContent = "";
        post({ kind: "predict", predict: chosen.value }).then(function (res) {
          document.getElementById("lab-pred-text").textContent = res.ok
            ? "Предсказание совпало с тем, как устроен закон."
            : "Предсказание не совпало — поэтому и ставим опыт.";
          document.getElementById("lab-pred-why").textContent = res.why || "";
          go("experiment");
        }).catch(function (e) {
          err.textContent = e.message || "Не удалось записать предсказание.";
        });
        return;
      }
      go(next);
    });
    root.addEventListener("resize", function () { if (raf) draw(); });
  }

  root.LabEngine = {
    scene: scene,
    canon: canon,
    fnv: fnv,
    quantize: quantize,
    evalExpr: evalExpr,
    evalOutputs: evalOutputs,
    meterReading: meterReading
  };

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", boot);
  }
})(typeof window !== "undefined" ? window : globalThis);
