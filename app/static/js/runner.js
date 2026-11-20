/* Запуск Python в браузере: PyRunner (воркер), TurtleCanvas (черепашка), CodeBox (редактор + консоль). */
(function () {
  'use strict';
  const V = document.documentElement.dataset.v || '1';

  // ------------------------------------------------------------------ PyRunner
  class PyRunner {
    constructor() {
      this.ready = null;
      this.job = null;
      this.waitingInput = false;
    }

    get isolated() {
      return !!(self.crossOriginIsolated && typeof SharedArrayBuffer !== 'undefined');
    }

    start() {
      if (this.ready) return this.ready;
      this.worker = new Worker('/static/js/py-worker.js?v=' + V);
      const init = { type: 'init', version: V };
      if (this.isolated) {
        this.inputSab = new SharedArrayBuffer(8 + 65536);
        this.ctrl = new Int32Array(this.inputSab, 0, 2);
        this.data = new Uint8Array(this.inputSab, 8);
        this.intSab = new SharedArrayBuffer(1);
        this.interrupt = new Uint8Array(this.intSab);
        init.inputBuffer = this.inputSab;
        init.interruptBuffer = this.intSab;
      }
      this.ready = new Promise((resolve, reject) => {
        this._readyResolve = resolve;
        this._readyReject = reject;
      });
      this.worker.onmessage = (e) => this._onMessage(e.data);
      this.worker.onerror = (e) => {
        this._readyReject && this._readyReject(new Error(e.message || 'Не удалось запустить Python'));
        this._finish({ error: { type: 'Error', hint: 'Python не загрузился. Обнови страницу.', traceback: String(e.message || '') } });
      };
      this.worker.postMessage(init);
      return this.ready;
    }

    _onMessage(msg) {
      const h = this.job ? this.job.handlers : {};
      switch (msg.type) {
        case 'ready': this.interactive = msg.interactive; this._readyResolve(); break;
        case 'stdout': h.onStdout && h.onStdout(msg.text); break;
        case 'stderr': h.onStderr && h.onStderr(msg.text); break;
        case 'turtle': h.onTurtle && h.onTurtle(msg.ops); break;
        case 'input': this.waitingInput = true; h.onInput && h.onInput(); break;
        case 'done':
        case 'checked': this._finish(msg.result); break;
        case 'fatal':
          if (!this.job) { this._readyReject && this._readyReject(new Error(msg.error)); break; }
          this._finish({ error: { type: 'Error', hint: 'Внутренняя ошибка запуска.', traceback: msg.error } });
          break;
      }
    }

    _finish(result) {
      const job = this.job;
      this.job = null;
      this.waitingInput = false;
      if (job) {
        clearTimeout(job.timer);
        clearTimeout(job.killTimer);
        job.resolve(result);
      }
    }

    async _exec(msg, handlers, timeoutMs) {
      await this.start();
      if (this.job) this.stop();
      if (this.interrupt) this.interrupt[0] = 0;
      return new Promise((resolve) => {
        this.job = { resolve, handlers: handlers || {} };
        if (timeoutMs) this.job.timer = setTimeout(() => this.stop(true), timeoutMs);
        this.worker.postMessage(msg);
      });
    }

    run(code, handlers, stdin) {
      return this._exec({ type: 'run', code, stdin: stdin || '' }, handlers, 0);
    }

    check(code, tests) {
      return this._exec({ type: 'check', code, tests }, {}, 10000);
    }

    bots(code, boss) {
      return this._exec({ type: 'bots', code, boss }, {}, 20000);
    }

    robot(code, fields) {
      return this._exec({ type: 'robot', code, fields: JSON.stringify(fields) }, {}, 15000);
    }

    provideInput(text) {
      if (!this.ctrl) return;
      let bytes = new TextEncoder().encode(text);
      if (bytes.length > 65000) bytes = bytes.slice(0, 65000);
      this.data.set(bytes);
      Atomics.store(this.ctrl, 1, bytes.length);
      Atomics.store(this.ctrl, 0, 1);
      Atomics.notify(this.ctrl, 0);
      this.waitingInput = false;
    }

    stop(timeout) {
      if (!this.job) return;
      const job = this.job;
      if (this.isolated && this.interrupt) {
        this.interrupt[0] = 2;  // SIGINT → KeyboardInterrupt
        if (this.waitingInput) {
          Atomics.store(this.ctrl, 1, -1);
          Atomics.store(this.ctrl, 0, 1);
          Atomics.notify(this.ctrl, 0);
        }
        // если Python не реагирует (долгая операция внутри), перезапускаем воркер
        job.killTimer = setTimeout(() => { if (this.job === job) this._kill(timeout); }, 1500);
      } else {
        this._kill(timeout);
      }
    }

    _kill(timeout) {
      this.worker.terminate();
      this.ready = null;
      this._finish({
        error: { type: 'KeyboardInterrupt', hint: timeout ? 'Время вышло: программа работала слишком долго. Возможно, бесконечный цикл.' : 'Программа остановлена.' },
        passed: false, results: [{ name: 'Время', ok: false, detail: 'Программа работала слишком долго. Возможно, бесконечный цикл или лишний input().' }]
      });
    }
  }

  const runner = new PyRunner();

  // ------------------------------------------------------------------ TurtleCanvas
  class TurtleCanvas {
    constructor(container) {
      this.W = 700; this.H = 500;
      this.wrap = container;
      this.canvas = document.createElement('canvas');
      this.overlay = document.createElement('canvas');
      this.wrap.append(this.canvas, this.overlay);
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      for (const c of [this.canvas, this.overlay]) {
        c.width = this.W * dpr; c.height = this.H * dpr;
        c.getContext('2d').setTransform(dpr, 0, 0, dpr, 0, 0);
      }
      this.ctx = this.canvas.getContext('2d');
      this.octx = this.overlay.getContext('2d');
      this.reset();
    }

    reset() {
      this.queue = [];
      this.cur = null;
      this.turtles = {};
      this.fillLines = {};
      this.instant = false;
      this.canvas.style.background = 'white';
      this.ctx.clearRect(0, 0, this.W, this.H);
      this.octx.clearRect(0, 0, this.W, this.H);
      cancelAnimationFrame(this.raf);
      this.raf = null;
    }

    finishNow() { this.instant = true; this._kick(); }

    push(ops) {
      for (const op of ops) this.queue.push(op);
      this._kick();
    }

    _kick() { if (!this.raf) this.raf = requestAnimationFrame(() => this._frame()); }

    cx(x) { return this.W / 2 + x; }
    cy(y) { return this.H / 2 - y; }

    _t(id) {
      if (!this.turtles[id]) this.turtles[id] = { x: 0, y: 0, h: 0, v: true, shape: 'classic' };
      return this.turtles[id];
    }

    _frame() {
      this.raf = null;
      let budget = 1;  // доля «времени кадра»
      let guard = 0;
      while (this.queue.length && budget > 0 && guard++ < 5000) {
        const op = this.queue[0];
        const speed = op.s === undefined ? 0 : op.s;
        if (this.instant || speed === 0 || !('s' in op)) {
          this._apply(op, 1);
          this.queue.shift();
          if (!this.instant && 's' in op && speed !== 0) budget -= 0.05;
          continue;
        }
        // скорость 1..10 → пикселей и градусов за кадр
        const pxPerFrame = speed * 5;
        const degPerFrame = speed * 12;
        const t = this._t(op.id);
        if (op.t === 'line' || op.t === 'move') {
          const x2 = op.t === 'line' ? op.x2 : op.x, y2 = op.t === 'line' ? op.y2 : op.y;
          const dist = Math.hypot(x2 - t.x, y2 - t.y);
          const can = pxPerFrame * budget;
          if (dist <= can || dist < 0.5) {
            this._apply(op, 1);
            this.queue.shift();
            budget -= dist / pxPerFrame;
          } else {
            const k = can / dist;
            const nx = t.x + (x2 - t.x) * k, ny = t.y + (y2 - t.y) * k;
            if (op.t === 'line') this._stroke(t.x, t.y, nx, ny, op.c, op.w);
            t.x = nx; t.y = ny;
            budget = 0;
          }
        } else if (op.t === 'turn') {
          let diff = ((op.h - t.h) % 360 + 540) % 360 - 180;
          const can = degPerFrame * budget;
          if (Math.abs(diff) <= can) {
            this._apply(op, 1);
            this.queue.shift();
            budget -= Math.abs(diff) / degPerFrame;
          } else {
            t.h += Math.sign(diff) * can;
            budget = 0;
          }
        } else {
          this._apply(op, 1);
          this.queue.shift();
        }
      }
      this._drawCursors();
      if (this.queue.length) this._kick();
    }

    _stroke(x1, y1, x2, y2, c, w) {
      const ctx = this.ctx;
      ctx.strokeStyle = c; ctx.lineWidth = w || 1; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      ctx.beginPath(); ctx.moveTo(this.cx(x1), this.cy(y1)); ctx.lineTo(this.cx(x2), this.cy(y2)); ctx.stroke();
    }

    _apply(op) {
      const ctx = this.ctx;
      switch (op.t) {
        case 'new': { const t = this._t(op.id); t.v = op.v; t.shape = op.shape; break; }
        case 'line': {
          const t = this._t(op.id);
          this._stroke(t.x, t.y, op.x2, op.y2, op.c, op.w);
          if (this.fillLines[op.id]) this.fillLines[op.id].push(op);
          t.x = op.x2; t.y = op.y2; break;
        }
        case 'move': { const t = this._t(op.id); t.x = op.x; t.y = op.y; break; }
        case 'turn': this._t(op.id).h = op.h; break;
        case 'bg': this.canvas.style.background = op.c; break;
        case 'tracer': if (op.n === 0) this.instant = true; break;
        case 'vis': this._t(op.id).v = op.v; break;
        case 'shape': this._t(op.id).shape = op.shape; break;
        case 'fill_begin': this.fillLines[op.id] = []; break;
        case 'fill': {
          ctx.fillStyle = op.c;
          ctx.beginPath();
          op.pts.forEach((p, i) => i ? ctx.lineTo(this.cx(p[0]), this.cy(p[1])) : ctx.moveTo(this.cx(p[0]), this.cy(p[1])));
          ctx.closePath(); ctx.fill();
          for (const l of this.fillLines[op.id] || []) this._stroke(l.x1, l.y1, l.x2, l.y2, l.c, l.w);
          delete this.fillLines[op.id];
          break;
        }
        case 'dot':
          ctx.fillStyle = op.c; ctx.beginPath();
          ctx.arc(this.cx(op.x), this.cy(op.y), Math.max(0.5, op.r), 0, Math.PI * 2); ctx.fill(); break;
        case 'text': {
          const [fam, size, style] = op.font;
          const weight = /bold/.test(style) ? 'bold ' : '';
          const italic = /italic/.test(style) ? 'italic ' : '';
          ctx.font = italic + weight + Math.round(size * 1.33) + 'px ' + JSON.stringify(fam) + ', sans-serif';
          ctx.fillStyle = op.c;
          ctx.textAlign = op.align === 'center' ? 'center' : op.align === 'right' ? 'right' : 'left';
          ctx.textBaseline = 'alphabetic';
          ctx.fillText(op.text, this.cx(op.x), this.cy(op.y));
          break;
        }
        case 'clear':
        case 'clearall':
          ctx.clearRect(0, 0, this.W, this.H);
          if (op.t === 'clearall') this.canvas.style.background = 'white';
          break;
      }
    }

    _drawCursors() {
      const o = this.octx;
      o.clearRect(0, 0, this.W, this.H);
      for (const id in this.turtles) {
        const t = this.turtles[id];
        if (!t.v) continue;
        o.save();
        o.translate(this.cx(t.x), this.cy(t.y));
        o.rotate(-t.h * Math.PI / 180);
        if (t.shape === 'turtle') {
          o.scale(-1, 1);
          o.font = '22px sans-serif'; o.textAlign = 'center'; o.textBaseline = 'middle';
          o.fillText('🐢', 0, 0);
        } else if (t.shape === 'circle') {
          o.fillStyle = '#222'; o.beginPath(); o.arc(0, 0, 6, 0, Math.PI * 2); o.fill();
        } else {
          o.fillStyle = '#222'; o.strokeStyle = '#fff'; o.lineWidth = 1;
          o.beginPath(); o.moveTo(9, 0); o.lineTo(-6, 6); o.lineTo(-3, 0); o.lineTo(-6, -6); o.closePath();
          o.fill(); o.stroke();
        }
        o.restore();
      }
    }
  }

  // ------------------------------------------------------------------ CodeBox
  const PY_LOADING = 'Загружаю Python… (первый раз — около 10 МБ, потом быстрее)';

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    // Кнопки редактора — не кнопки отправки: внутри формы домашки «Запустить» отправляло ДЗ (10.10.2026).
    if (tag === 'button') e.type = 'button';
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  class CodeBox {
    constructor(root) {
      this.root = root;
      this.mode = root.dataset.mode || 'run';      // run | task | playground
      this.textarea = root.querySelector('textarea');
      this.initial = this.textarea.value;
      this.local = root.dataset.local === '1';
      this._build();
    }

    _build() {
      const r = this.root;
      const bar = el('div', 'cb-bar');
      this.runBtn = el('button', 'btn btn-run', '▶ Запустить');
      this.stopBtn = el('button', 'btn btn-stop', '■ Стоп');
      this.stopBtn.hidden = true;
      this.resetBtn = el('button', 'btn btn-ghost', '↺ Сначала');
      this.resetBtn.title = 'Вернуть исходный код';
      this.status = el('span', 'cb-status');
      if (this.local) {
        this.runBtn.disabled = true;
        this.runBtn.textContent = '💻 Запускай на компьютере';
        this.runBtn.title = 'Этот код использует библиотеки, которых нет в браузере (pygame, requests, telebot…)';
      }
      bar.append(this.runBtn, this.stopBtn);
      if (this.mode === 'task') {
        this.checkBtn = el('button', 'btn btn-check', '✔ Проверить');
        bar.append(this.checkBtn);
      }
      bar.append(this.resetBtn, this.status);
      if (this.mode !== 'playground') {
        const copy = el('button', 'btn btn-ghost', '⧉');
        copy.title = 'Скопировать код';
        copy.onclick = () => navigator.clipboard && navigator.clipboard.writeText(this.getCode()).then(() => this._status('Скопировано'));
        bar.append(copy);
      }
      r.insertBefore(bar, this.textarea);

      this.panels = el('div', 'cb-panels');
      this.consoleWrap = el('div', 'cb-console');
      this.consoleWrap.hidden = true;
      this.out = el('pre', 'cb-out');
      this.inputRow = el('form', 'cb-input');
      this.inputRow.hidden = true;
      this.inputField = el('input');
      this.inputField.placeholder = 'Введи ответ и нажми Enter';
      this.inputField.autocomplete = 'off';
      const send = el('button', 'btn btn-small', 'Ввод ⏎');
      send.type = 'submit';
      this.inputRow.append(this.inputField, send);
      this.consoleWrap.append(this.out, this.inputRow);
      this.turtleWrap = el('div', 'cb-turtle');
      this.turtleWrap.hidden = true;
      this.errorBox = el('div', 'cb-error');
      this.errorBox.hidden = true;
      this.results = el('div', 'cb-results');
      this.results.hidden = true;
      this.panels.append(this.errorBox, this.results, this.turtleWrap, this.consoleWrap);
      r.append(this.panels);

      if (!runner.isolated && !this.local) {
        this.stdinBox = el('textarea', 'cb-stdin');
        this.stdinBox.placeholder = 'Данные для input() — каждая строка отдельно (браузер не поддерживает живой ввод)';
        this.stdinBox.rows = 2;
        r.insertBefore(this.stdinBox, this.panels);
      }

      if (window.CodeMirror) {
        this.cm = CodeMirror.fromTextArea(this.textarea, {
          mode: 'python', lineNumbers: true, indentUnit: 4, tabSize: 4, matchBrackets: true,
          autoCloseBrackets: true, viewportMargin: Infinity, lineWrapping: false,
          extraKeys: {
            Tab: (cm) => cm.somethingSelected() ? cm.indentSelection('add') : cm.replaceSelection('    ', 'end'),
            'Shift-Tab': (cm) => cm.indentSelection('subtract'),
            'Ctrl-Enter': () => this.run(), 'Cmd-Enter': () => this.run(),
          },
        });
        this.cm.on('change', () => this._clearMark());
        // редактор, созданный в скрытом блоке, нужно перерисовать, когда блок покажется
        if ('IntersectionObserver' in window) {
          new IntersectionObserver((entries) => { if (entries.some((e) => e.isIntersecting)) this.cm.refresh(); })
            .observe(this.cm.getWrapperElement());
        }
      } else {
        this.textarea.classList.add('cb-plain');
        this.textarea.addEventListener('keydown', (e) => {
          if (e.key === 'Tab') { e.preventDefault(); document.execCommand('insertText', false, '    '); }
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) this.run();
        });
      }

      this.runBtn.onclick = () => this.run();
      this.stopBtn.onclick = () => runner.stop();
      this.resetBtn.onclick = () => { if (confirm('Вернуть исходный код? Твои изменения пропадут.')) this.setCode(this.initial); };
      if (this.checkBtn) this.checkBtn.onclick = () => this.check();
      this.inputRow.onsubmit = (e) => {
        e.preventDefault();
        const v = this.inputField.value;
        this._write(v + '\n', 'in');
        this.inputField.value = '';
        this.inputRow.hidden = true;
        runner.provideInput(v);
      };
    }

    getCode() { return this.cm ? this.cm.getValue() : this.textarea.value; }
    setCode(code) { if (this.cm) this.cm.setValue(code); else this.textarea.value = code; }

    _status(text) { this.status.textContent = text || ''; }

    _write(text, cls) {
      this.consoleWrap.hidden = false;
      if (this.out.textContent.length > 200000) return;
      const span = document.createElement('span');
      if (cls) span.className = cls;
      span.textContent = text;
      this.out.append(span);
      this.out.scrollTop = this.out.scrollHeight;
    }

    _clearMark() {
      if (this.mark) { this.cm.removeLineClass(this.mark, 'background', 'cm-error-line'); this.mark = null; }
    }

    _showError(err) {
      if (!err) { this.errorBox.hidden = true; return; }
      this.errorBox.hidden = false;
      this.errorBox.replaceChildren();
      const h = el('div', 'cb-error-hint');
      h.append(el('b', '', '🐞 ' + (err.type || 'Ошибка') + (err.line ? ' в строке ' + err.line : '')), el('div', '', err.hint || ''));
      this.errorBox.append(h);
      if (err.traceback) {
        const d = el('details');
        d.append(el('summary', '', 'Что написал Python'), el('pre', '', err.traceback));
        this.errorBox.append(d);
      }
      if (this.cm && err.line) {
        this._clearMark();
        this.mark = this.cm.addLineClass(err.line - 1, 'background', 'cm-error-line');
        this.cm.scrollIntoView({ line: err.line - 1, ch: 0 }, 80);
      }
    }

    _ensureTurtle() {
      if (!this.turtle) this.turtle = new TurtleCanvas(this.turtleWrap);
      this.turtleWrap.hidden = false;
      return this.turtle;
    }

    _busy(on) {
      this.runBtn.hidden = on;
      this.stopBtn.hidden = !on;
      if (this.checkBtn) this.checkBtn.disabled = on;
    }

    async _prepare() {
      if (!runner.ready) this._status(PY_LOADING);
      try { await runner.start(); } catch (e) {
        this._status('');
        this._showError({ type: 'Ошибка загрузки', hint: 'Не получилось загрузить Python в браузере. Проверь интернет и обнови страницу.', traceback: String(e.message || e) });
        return false;
      }
      this._status('');
      return true;
    }

    async run() {
      if (this.local || this.running) return;
      this.running = true;
      this._busy(true);
      this.out.textContent = '';
      this.consoleWrap.hidden = true;
      this.results.hidden = true;
      this._showError(null);
      if (this.turtle) this.turtle.reset();
      this.turtleWrap.hidden = true;
      if (!(await this._prepare())) { this.running = false; this._busy(false); return; }
      this._status('Работает…');
      const code = this.getCode();
      window.CQ && document.querySelector('meta[name="csrf"]') && CQ.api('/api/run', {}).then(CQ.handleNotices).catch(() => {});
      const res = await runner.run(code, {
        onStdout: (t) => this._write(t),
        onStderr: (t) => this._write(t, 'err'),
        onTurtle: (ops) => this._ensureTurtle().push(ops),
        onInput: () => {
          this.consoleWrap.hidden = false;
          this.inputRow.hidden = false;
          this.inputField.focus({ preventScroll: true });
        },
      }, this.stdinBox ? this.stdinBox.value : '');
      this.inputRow.hidden = true;
      this.running = false;
      this._busy(false);
      if (res && res.error) {
        this._showError(res.error);
        this._status('');
      } else {
        this._status((this.out.textContent || !this.turtleWrap.hidden) ? '✓ Готово' : '✓ Готово (программа ничего не вывела)');
      }
      this.root.dispatchEvent(new CustomEvent('cq:ran', { detail: res }));
    }

    async check() {
      if (this.running) return;
      const tests = JSON.parse(this.root.dataset.tests || '[]');
      this.running = true;
      this._busy(true);
      this._showError(null);
      this.results.hidden = true;
      if (!(await this._prepare())) { this.running = false; this._busy(false); return; }
      this._status('Проверяю…');
      const code = this.getCode();
      const res = await runner.check(code, tests);
      this.running = false;
      this._busy(false);
      this._status('');
      this._renderResults(res);
      this.root.dispatchEvent(new CustomEvent('cq:checked', { detail: { res, code } }));
    }

    _renderResults(res) {
      this.results.hidden = false;
      this.results.replaceChildren();
      const ok = res.passed;
      const head = el('div', 'cb-results-head ' + (ok ? 'ok' : 'bad'), ok ? '🎉 Все тесты пройдены!' : '😕 Пока не всё. Посмотри, что не так:');
      this.results.append(head);
      const list = el('ul', 'cb-tests');
      for (const r of res.results || []) {
        const li = el('li', r.ok ? 'ok' : 'bad');
        li.append(el('span', 'mark', r.ok ? '✅' : '❌'), el('span', 'name', r.name + (r.hidden ? ' (скрытый)' : '')));
        if (!r.ok && r.detail) li.append(el('pre', 'detail', r.detail));
        list.append(li);
      }
      this.results.append(list);
      const firstErr = (res.results || []).find((r) => r.error);
      if (firstErr && firstErr.error.line && this.cm) {
        this._clearMark();
        this.mark = this.cm.addLineClass(firstErr.error.line - 1, 'background', 'cm-error-line');
      }
    }
  }

  function initCodeBoxes(scope) {
    const boxes = [];
    (scope || document).querySelectorAll('.codebox:not([data-ready])').forEach((root) => {
      root.dataset.ready = '1';
      const box = new CodeBox(root);
      root.codebox = box;
      boxes.push(box);
    });
    // Прогрев Python, когда страница загрузилась и браузер свободен
    if (boxes.some((b) => !b.local)) {
      const warm = () => runner.start().catch(() => {});
      ('requestIdleCallback' in window) ? requestIdleCallback(warm, { timeout: 3000 }) : setTimeout(warm, 1500);
    }
    return boxes;
  }

  window.CQRunner = { runner, CodeBox, TurtleCanvas, initCodeBoxes };
  document.addEventListener('DOMContentLoaded', () => initCodeBoxes());
})();
