/* Общий JS: запросы к API, уведомления, конфетти, страницы задач, задачи дня, умножайки, песочницы. */
(function () {
  'use strict';
  const csrf = () => (document.querySelector('meta[name="csrf"]') || {}).content || '';

  async function api(url, body) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf() },
      body: JSON.stringify(body || {}),
      credentials: 'same-origin',
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  // ------------------------------------------------------------------ уведомления и конфетти
  function toast(emoji, text, big) {
    let box = document.getElementById('toasts');
    if (!box) { box = document.createElement('div'); box.id = 'toasts'; document.body.append(box); }
    const t = document.createElement('div');
    t.className = 'toast' + (big ? ' big' : '');
    const e = document.createElement('span'); e.className = 'toast-emoji';
    if (/^\/static\/img\//.test(emoji)) { const im = new Image(); im.src = emoji; im.alt = ''; e.append(im); } else e.textContent = emoji;
    const s = document.createElement('span'); s.textContent = text;
    t.append(e, s);
    box.append(t);
    setTimeout(() => t.classList.add('show'), 20);
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 400); }, big ? 6000 : 3500);
    if (big) confetti();
  }

  function handleNotices(res) {
    (res && res.notices || []).forEach((n, i) => setTimeout(() => toast(n.emoji, n.text, !!n.big), i * 450));
    return res;
  }

  function confetti(count) {
    if (document.documentElement.dataset.calm) return;      // спокойный вид
    if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const c = document.createElement('canvas');
    c.className = 'confetti';
    c.width = innerWidth; c.height = innerHeight;
    document.body.append(c);
    const ctx = c.getContext('2d');
    const colors = ['#ff5d8f', '#ffd166', '#06d6a0', '#4cc9f0', '#9b5de5', '#f15bb5'];
    const parts = Array.from({ length: count || 140 }, () => ({
      x: innerWidth / 2 + (Math.random() - 0.5) * 200, y: innerHeight / 3,
      vx: (Math.random() - 0.5) * 14, vy: -Math.random() * 14 - 4,
      r: Math.random() * 6 + 4, c: colors[Math.floor(Math.random() * colors.length)],
      a: Math.random() * Math.PI, va: (Math.random() - 0.5) * 0.3,
    }));
    let frame = 0;
    (function tick() {
      ctx.clearRect(0, 0, c.width, c.height);
      for (const p of parts) {
        p.vy += 0.35; p.x += p.vx; p.y += p.vy; p.a += p.va; p.vx *= 0.99;
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.a); ctx.fillStyle = p.c;
        ctx.fillRect(-p.r / 2, -p.r / 4, p.r, p.r / 2); ctx.restore();
      }
      if (++frame < 160) requestAnimationFrame(tick); else c.remove();
    })();
  }

  // Своё окно подтверждения вместо системного confirm(): то тяжело выглядит на телефоне и пугает детей
  function ask(text, okText, cancelText) {
    return new Promise((resolve) => {
      const wrap = document.createElement('div');
      wrap.className = 'cq-modal';
      wrap.innerHTML = '<div class="cq-modal-card" role="dialog" aria-modal="true"><p></p>' +
        '<div class="row"><button type="button" class="btn" data-ok></button>' +
        '<button type="button" class="btn btn-ghost" data-cancel></button></div></div>';
      wrap.querySelector('p').textContent = text;
      wrap.querySelector('[data-ok]').textContent = okText || 'Да';
      wrap.querySelector('[data-cancel]').textContent = cancelText || 'Отмена';
      const done = (v) => { wrap.remove(); document.removeEventListener('keydown', onKey); resolve(v); };
      const onKey = (e) => { if (e.key === 'Escape') done(false); };
      wrap.addEventListener('click', (e) => { if (e.target === wrap) done(false); });
      wrap.querySelector('[data-ok]').addEventListener('click', () => done(true));
      wrap.querySelector('[data-cancel]').addEventListener('click', () => done(false));
      document.addEventListener('keydown', onKey);
      document.body.append(wrap);
      wrap.querySelector('[data-ok]').focus();
    });
  }

  window.CQ = { api, toast, confetti, handleNotices, ask };

  // ХимЛаб: пробник — таймер, автосохранение на сервер и в браузер
  function initMock() {
    const box = document.querySelector('[data-mock-timer]');
    const form = document.getElementById('mock-form');
    if (!box || !form) return;
    const id = box.dataset.mockId;
    const key = 'cq-mock-' + id;
    const end = Date.now() + Number(box.dataset.mockTimer) * 1000;
    const inputs = form.querySelectorAll('[data-mock-answer]');
    try {                                                  // восстановить из браузера то, что не успело уйти на сервер
      const local = JSON.parse(localStorage.getItem(key) || '{}');
      inputs.forEach((i) => { if (!i.value && local[i.dataset.mockAnswer]) i.value = local[i.dataset.mockAnswer]; });
    } catch (e) { /* хранилище недоступно — не страшно */ }
    const collect = () => { const a = {}; inputs.forEach((i) => { a[i.dataset.mockAnswer] = i.value.trim(); }); return a; };
    let dirty = false;
    inputs.forEach((i) => i.addEventListener('input', () => {
      dirty = true;
      try { localStorage.setItem(key, JSON.stringify(collect())); } catch (e) { /* ничего */ }
    }));
    const saved = box.querySelector('.mock-saved');
    async function save() {
      if (!dirty) return;
      dirty = false;
      try {
        const r = await api('/api/chem/mock/' + id + '/save', { answers: collect() });
        saved.textContent = r.saved ? '✓ сохранено ' + new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) : 'время вышло';
      } catch (e) { dirty = true; saved.textContent = 'нет связи — ответы сохранены в браузере'; }
    }
    setInterval(save, 30000);
    window.addEventListener('beforeunload', () => { if (dirty) navigator.sendBeacon && save(); });
    const left = box.querySelector('.mock-left');
    let submitted = false;
    const tick = () => {
      const s = Math.max(0, Math.round((end - Date.now()) / 1000));
      const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
      left.textContent = (h ? h + ':' : '') + String(m).padStart(2, '0') + ':' + String(sec).padStart(2, '0');
      box.classList.toggle('hurry', s < 600);
      if (s === 0 && !submitted) { submitted = true; form.removeAttribute('data-confirm'); form.requestSubmit ? form.requestSubmit() : form.submit(); }
    };
    tick(); setInterval(tick, 1000);
    form.addEventListener('submit', () => { try { localStorage.removeItem(key); } catch (e) { /* ничего */ } });
  }
  document.addEventListener('DOMContentLoaded', initMock);

  // ХимЛаб: проверка задач преподавателем
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-review-set]');
    if (!btn) return;
    const box = btn.closest('[data-review]');
    const status = btn.dataset.reviewSet;
    const comment = box.querySelector('.review-comment').value.trim();
    if (status === 'issue' && !comment) { box.querySelector('.review-comment').focus(); toast('✍️', 'Напиши, что не так — это поможет исправить'); return; }
    try {
      const r = await api('/api/chem/review', { item: box.dataset.review, status, comment });
      box.classList.remove('ok', 'issue');
      if (status !== 'clear') box.classList.add(status);
      box.querySelector('.review-state').textContent = status === 'ok' ? '✅ проверено' : (status === 'issue' ? '⚠️ скрыто от учеников' : '');
      const done = document.querySelector('[data-review-done]');
      if (done) done.textContent = r.done;
    } catch (err) { toast('⚠️', 'Не сохранилось — проверь интернет'); }
  });

  // ХимЛаб: видео опытов — «что наблюдаем?», ответ проверяет сервер
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-video-quiz] [data-answer]');
    if (!btn) return;
    const card = btn.closest('[data-video-quiz]');
    const buttons = card.querySelectorAll('[data-answer]');
    buttons.forEach((b) => { b.disabled = true; });
    try {
      const r = await api('/api/chem/lab/video', { id: card.dataset.videoQuiz, answer: Number(btn.dataset.answer) });
      buttons.forEach((b) => {
        if (Number(b.dataset.answer) === r.right) b.classList.add('answer-right');
        else if (b === btn) b.classList.add('answer-wrong');
      });
      const out = card.querySelector('.video-result');
      out.hidden = false;
      out.replaceChildren();
      const head = document.createElement('b');
      head.textContent = (r.correct ? '🎉 Верно! ' : '😕 Не совсем — правильный ответ выделен зелёным. ') + r.title;
      const eq = document.createElement('div');
      eq.className = 'chem-eq';
      eq.innerHTML = r.equation_html;   // формула с индексами — отрисована сервером из нашего же контента
      const nums = document.createElement('small');
      nums.className = 'muted';
      nums.textContent = 'Пригодится: ' + r.nums;
      out.append(head, eq, nums);
      handleNotices(r);
    } catch (err) {
      buttons.forEach((b) => { b.disabled = false; });
      toast('⚠️', 'Не удалось проверить — проверь интернет');
    }
  });

  // ------------------------------------------------------------------ общее
  function initCommon() {
    const data = document.getElementById('page-notices');
    if (data) handleNotices({ notices: JSON.parse(data.textContent) });

    document.querySelectorAll('form[data-confirm]').forEach((f) =>
      f.addEventListener('submit', async (e) => {
        if (!f.dataset.confirm) return;           // подтверждение сняли (например, пробник сдаётся сам по таймеру)
        e.preventDefault();
        const text = f.dataset.confirm, by = e.submitter;
        if (await ask(text, 'Да', 'Отмена')) {
          // requestSubmit: срабатывают остальные обработчики submit и передаётся нажатая кнопка (name/value)
          f.dataset.confirm = '';
          if (f.requestSubmit) f.requestSubmit(by && by.form === f ? by : undefined); else f.submit();
          f.dataset.confirm = text;
        }
      }));

    // подтверждение на отдельной кнопке: data-ask="текст", data-ask-if="#поле" — спрашивать, только если поле не пустое
    document.querySelectorAll('button[data-ask]').forEach((b) =>
      b.addEventListener('click', async (e) => {
        if (b.dataset.asked) { delete b.dataset.asked; return; }
        const field = b.dataset.askIf ? document.querySelector(b.dataset.askIf) : null;
        if (field && !field.value.trim()) return;
        e.preventDefault();
        if (await ask(b.dataset.ask, 'Да', 'Отмена')) { b.dataset.asked = '1'; b.click(); }
      }));

    // цифровая клавиатура на странице: системная на телефоне не выезжает (inputmode="none")
    document.querySelectorAll('.numpad').forEach((pad) => {
      const field = pad.parentElement.querySelector('[data-numpad]');
      if (!field) return;
      pad.addEventListener('click', (e) => {
        const b = e.target.closest('button[data-key]');
        if (!b || field.disabled) return;
        const k = b.dataset.key;
        if (k === 'back') field.value = field.value.slice(0, -1);
        else if (k === '−') field.value = field.value.startsWith('-') ? field.value.slice(1) : '-' + field.value;
        else if (k === ',') { if (!/[.,]/.test(field.value)) field.value += (field.value ? '' : '0') + ','; }
        else if (field.value.length < 12) field.value += k;
        field.dispatchEvent(new Event('input', { bubbles: true }));
      });
    });

    // меню ученика в шапке: закрываем по клику мимо и по Esc
    document.querySelectorAll('details.student-switch').forEach((d) => {
      document.addEventListener('click', (e) => { if (d.open && !d.contains(e.target)) d.open = false; });
      document.addEventListener('keydown', (e) => { if (e.key === 'Escape') d.open = false; });
    });

    // галочки-настройки: отправляем форму сразу при изменении
    document.querySelectorAll('[data-autosubmit]').forEach((el) =>
      el.addEventListener('change', () => el.form && el.form.submit()));

    document.querySelectorAll('[data-print]').forEach((b) => b.addEventListener('click', () => window.print()));

    // мягкий таймер проверки: считает от первого открытия, по истечении только подсвечивается
    document.querySelectorAll('.check-timer').forEach((box) => {
      const end = new Date(box.dataset.started).getTime() + Number(box.dataset.minutes) * 60000;
      const label = box.querySelector('b');
      const text = box.querySelector('span');
      const tick = () => {
        const left = Math.round((end - Date.now()) / 1000);
        if (left <= 0) {
          box.classList.add('over');
          label.textContent = '0:00';
          text.textContent = 'время вышло — проверь ответы и сдавай';
          return;
        }
        label.textContent = Math.floor(left / 60) + ':' + String(left % 60).padStart(2, '0');
        box.classList.toggle('soon', left < 300);
        setTimeout(tick, 1000);
      };
      tick();
    });

    // план по шагам на странице подготовки: галочки запоминаются в этом браузере
    document.querySelectorAll('[data-steps]').forEach((box) => {
      const key = 'cq-' + box.dataset.steps;
      let saved = {};
      try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch (e) { saved = {}; }
      const boxes = box.querySelectorAll('input[data-step]');
      const store = () => {
        const state = {};
        boxes.forEach((b) => { if (b.checked) state[b.dataset.step] = 1; });
        try { localStorage.setItem(key, JSON.stringify(state)); } catch (e) { /* приватный режим */ }
      };
      boxes.forEach((b) => { b.checked = !!saved[b.dataset.step]; b.addEventListener('change', store); });
      const reset = box.querySelector('[data-steps-reset]');
      if (reset) reset.addEventListener('click', () => { boxes.forEach((b) => { b.checked = false; }); store(); });
    });

    // сертификат и карточки: лист A4 ужимаем под ширину экрана, а на печать — в натуральную величину
    const sheet = document.querySelector('.sheet-fit');
    if (sheet) {
      const fit = () => { sheet.style.zoom = Math.min(1, (document.documentElement.clientWidth - 32) / sheet.offsetWidth); };
      fit();
      addEventListener('resize', () => { sheet.style.zoom = 1; fit(); });
      addEventListener('beforeprint', () => { sheet.style.zoom = 1; });
      addEventListener('afterprint', fit);
    }

    document.querySelectorAll('[data-copy]').forEach((b) => b.addEventListener('click', () => {
      const done = () => toast('🔗', 'Ссылка скопирована');
      if (navigator.clipboard) navigator.clipboard.writeText(b.dataset.copy).then(done, () => prompt('Скопируй ссылку:', b.dataset.copy));
      else prompt('Скопируй ссылку:', b.dataset.copy);
    }));

    document.querySelectorAll('[data-countdown]').forEach((elx) => {
      const target = new Date(elx.dataset.countdown);
      if (isNaN(target)) return;
      const upd = () => {
        let ms = target - new Date();
        if (ms <= 0) { elx.textContent = 'Уже сейчас! 🎉'; return; }
        const d = Math.floor(ms / 864e5); ms -= d * 864e5;
        const h = Math.floor(ms / 36e5); ms -= h * 36e5;
        const m = Math.floor(ms / 6e4);
        elx.textContent = (d ? d + ' д ' : '') + h + ' ч ' + m + ' мин';
      };
      upd(); setInterval(upd, 30000);
    });

    // блоки меню: помним, что ученик/преподаватель раскрыл или свернул (блок с текущей страницей раскрыт всегда)
    document.querySelectorAll('details.nav-group').forEach((d) => {
      const key = 'nav-' + d.dataset.key;
      try {
        const saved = localStorage.getItem(key);
        if (saved !== null && !d.dataset.active) d.open = saved === '1';
      } catch (e) { /* без хранилища — по умолчанию */ }
      d.addEventListener('toggle', () => { try { localStorage.setItem(key, d.open ? '1' : '0'); } catch (e) { /* нет */ } });
    });

    const nav = document.querySelector('.nav-toggle');
    if (nav) {
      nav.addEventListener('click', (e) => { e.stopPropagation(); document.body.classList.toggle('nav-open'); });
      // меню на телефоне закрывается касанием мимо него и клавишей Esc
      document.addEventListener('click', (e) => {
        if (document.body.classList.contains('nav-open') && !e.target.closest('.sidenav')) document.body.classList.remove('nav-open');
      });
      document.addEventListener('keydown', (e) => { if (e.key === 'Escape') document.body.classList.remove('nav-open'); });
    }
  }

  // ------------------------------------------------------------------ страница задачи
  function initTask() {
    const box = document.querySelector('.codebox[data-mode="task"]');
    if (!box) return;
    const taskId = box.dataset.task;
    box.addEventListener('cq:checked', async (e) => {
      const { res, code } = e.detail;
      try {
        const r = await api('/api/task/' + taskId + '/attempt', { code, passed: !!res.passed });
        handleNotices(r);
        if (res.passed) {
          if (!r.first) confetti(60);
          const sol = document.getElementById('solution');
          if (sol && r.solution) {
            sol.hidden = false;
            sol.querySelector('pre').textContent = r.solution;
          }
          const hb = document.getElementById('show-hint');
          if (hb) hb.hidden = true;
          const next = document.getElementById('next-task');
          if (next) next.hidden = false;
          const badge = document.getElementById('task-badge');
          if (badge) { badge.textContent = '✅ Решено'; badge.className = 'pill ok'; }
        } else {
          const fails = document.getElementById('fails');
          if (fails) {
            const n = Number(fails.dataset.n || 0) + 1;
            fails.dataset.n = n;
            if (n >= 2) document.getElementById('hint').hidden = false;
          }
        }
      } catch (err) { toast('⚠️', 'Не удалось сохранить попытку — проверь интернет'); }
    });
    const hb = document.getElementById('show-hint');
    if (hb) hb.addEventListener('click', () => { document.getElementById('hint').hidden = false; hb.hidden = true; });
  }

  // ------------------------------------------------------------------ задача дня
  function initDaily() {
    const form = document.getElementById('daily-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const answer = form.answer.value;
      const r = await api('/api/daily/answer', { answer });
      const out = document.getElementById('daily-result');
      out.hidden = false;
      out.className = 'daily-result ' + (r.correct ? 'ok' : 'bad');
      if (r.correct) {
        out.textContent = '🎉 Верно!';
        confetti();
      } else if (!r.finished) {
        out.textContent = '❌ Не совсем. Осталась ещё одна попытка — посмотри на код внимательнее.';
      } else {
        out.textContent = '😅 Не угадал. Правильный ответ ниже — запусти код и убедись.';
      }
      if (r.finished) {
        form.querySelector('button').disabled = true;
        const reveal = document.getElementById('daily-reveal');
        reveal.hidden = false;
        reveal.querySelector('pre').textContent = r.answer || '';
        reveal.querySelector('.why').textContent = r.why || '';
        document.querySelectorAll('.daily-code .codebox').forEach((b) => b.classList.remove('locked'));
      }
      handleNotices(r);
    });
  }

  // ------------------------------------------------------------------ умножайка
  const rnd = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
  const GEN = {
    table: () => { const a = rnd(2, 9), b = rnd(2, 9); return [a + ' × ' + b, a * b]; },
    big: () => { const a = rnd(3, 20), b = rnd(11, 20); return [a + ' × ' + b, a * b]; },
    squares: () => { const n = rnd(2, 30); return [n + '²', n * n]; },
    pow2: () => { const k = rnd(0, 16); return ['2^' + k, 2 ** k]; },
    divmod: () => {
      const a = rnd(10, 99), b = rnd(2, 9);
      return Math.random() < 0.5 ? [a + ' // ' + b, Math.floor(a / b)] : [a + ' % ' + b, a % b];
    },
    bin: () => {
      if (Math.random() < 0.5) { const n = rnd(1, 63); return [n.toString(2) + '₂ → в десятичную', n]; }
      const n = rnd(1, 31); return [n + ' → в двоичную', n.toString(2)];
    },
  };
  GEN.mix = () => { const keys = ['table', 'big', 'squares', 'pow2', 'divmod', 'bin']; return GEN[keys[rnd(0, keys.length - 1)]](); };

  function initTrainer() {
    const root = document.getElementById('trainer');
    if (!root) return;
    const DURATION = 60;
    const start = root.querySelector('.tr-start');
    const game = root.querySelector('.tr-game');
    const end = root.querySelector('.tr-end');
    const q = root.querySelector('.tr-q');
    const input = root.querySelector('.tr-input');
    const score = root.querySelector('.tr-score');
    const timer = root.querySelector('.tr-timer');
    const bar = root.querySelector('.tr-bar i');
    const flash = root.querySelector('.tr-flash');
    let mode, answer, correct, wrong, combo, t0, iv, points, threes, qStart;
    const pointsEl = root.querySelector('.tr-points');

    function next() {
      const [text, ans] = GEN[mode]();
      q.textContent = text + ' = ?';
      answer = String(ans);
      qStart = Date.now();
      input.value = '';
      input.focus();
    }

    function finish() {
      clearInterval(iv);
      game.hidden = true;
      end.hidden = false;
      end.querySelector('.tr-final').textContent = correct;
      end.querySelector('.tr-wrong').textContent = wrong;
      end.querySelector('.tr-final-points').textContent = points;
      end.querySelector('.tr-threes').textContent = threes;
      api('/api/trainer', { mode, correct, wrong }).then((r) => {
        const info = end.querySelector('.tr-info');
        info.textContent = (r.xp ? '+' + r.xp + ' 🏆. ' : (r.cap_reached ? 'Дневной лимит трофеев за Арену набран — но тренироваться всё равно полезно! ' : '')) +
          'Рекорд режима: ' + r.best + (r.record ? ' — НОВЫЙ РЕКОРД! 🏁' : '');
        const best = root.querySelector('[data-best="' + mode + '"]');
        if (best) best.textContent = r.best;
        if (r.record) confetti();
        handleNotices(r);
      }).catch(() => {});
    }

    root.querySelectorAll('[data-mode]').forEach((b) => b.addEventListener('click', () => {
      mode = b.dataset.mode;
      correct = 0; wrong = 0; combo = 0; points = 0; threes = 0;
      score.textContent = '0';
      pointsEl.textContent = '0';
      start.hidden = true; end.hidden = true; game.hidden = false;
      root.querySelector('.tr-mode').textContent = b.dataset.title;
      t0 = Date.now();
      iv = setInterval(() => {
        const left = Math.max(0, DURATION - (Date.now() - t0) / 1000);
        timer.textContent = Math.ceil(left);
        bar.style.width = (100 * left / DURATION) + '%';
        if (left <= 0) finish();
      }, 100);
      next();
    }));

    root.querySelector('.tr-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const v = input.value.trim().replace(/^0+(?=\d)/, '');
      if (!v) return;
      if (v === answer) {
        correct++; combo++;
        const three = Date.now() - qStart < 3000;
        points += three ? 3 : 2;
        if (three) threes++;
        score.textContent = correct;
        pointsEl.textContent = points;
        flash.textContent = (three ? '🏀 +3 трёхочковый!' : '🏀 +2') + (combo >= 5 ? ' 🔥×' + combo : '');
        flash.className = 'tr-flash ok';
      } else {
        wrong++; combo = 0;
        flash.textContent = '🧱 мимо! ' + answer;
        flash.className = 'tr-flash bad';
      }
      void flash.offsetWidth;
      flash.classList.add('show');
      next();
    });

    root.querySelectorAll('.tr-again').forEach((b) => b.addEventListener('click', () => { end.hidden = true; start.hidden = false; }));
  }

  // ------------------------------------------------------------------ песочница
  function initPlayground() {
    const root = document.getElementById('playground');
    if (!root) return;
    const box = root.querySelector('.codebox');
    const saveBtn = document.getElementById('save-snippet');
    const title = document.getElementById('snippet-title');
    saveBtn.addEventListener('click', async () => {
      const code = box.codebox.getCode();
      const r = await api('/api/snippets', { id: root.dataset.id || 0, title: title.value, code });
      if (!root.dataset.id || root.dataset.id === '0') {
        root.dataset.id = r.id;
        history.replaceState(null, '', '/playground?s=' + r.id);
      }
      toast('💾', 'Сохранено');
      handleNotices(r);
    });
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); saveBtn.click(); }
    });
  }

  // ------------------------------------------------------------------ домашка: код из редактора в форму
  function initHomework() {
    const form = document.getElementById('hw-form');
    if (!form) return;
    form.addEventListener('submit', () => {
      const box = form.querySelector('.codebox');
      if (box && box.codebox) form.querySelector('input[name="code"]').value = box.codebox.getCode();
    });
  }

  function initProjectForm() {
    const form = document.getElementById('project-form');
    if (!form) return;
    form.addEventListener('submit', () => {
      const box = form.querySelector('.codebox');
      if (box && box.codebox) form.querySelector('input[name="code"]').value = box.codebox.getCode();
    });
  }

  // ------------------------------------------------------------------ проверки: «пока не знаю» и сдача
  function initCheck() {
    // после сдачи черновик на устройстве больше не нужен
    document.querySelectorAll('[data-clear-check]').forEach((el) => {
      try { localStorage.removeItem('cq-check-' + el.dataset.clearCheck + '-' + el.dataset.user); } catch (e) { /* нет хранилища */ }
    });
    const form = document.querySelector('form.check-form');
    if (!form) return;
    const sync = (q) => {
      const skip = q.querySelector('.check-skip input');
      if (!skip) return;
      q.classList.toggle('skipped', skip.checked);
      q.querySelectorAll('input[name^="a_"], textarea').forEach((el) => { el.disabled = skip.checked; });
    };
    form.querySelectorAll('.check-q').forEach((q) => {
      const skip = q.querySelector('.check-skip input');
      if (skip) skip.addEventListener('change', () => sync(q));
    });
    form.querySelectorAll('[data-skip-part]').forEach((btn) => btn.addEventListener('click', () => {
      const part = btn.closest('.check-part');
      const boxes = [...part.querySelectorAll('.check-skip input')];
      const all = boxes.every((b) => b.checked);
      boxes.forEach((b) => { b.checked = !all; sync(b.closest('.check-q')); });
      btn.textContent = all ? '🤷 Пропустить часть' : '↩ Вернуть часть';
    }));
    // автосохранение: каждый ответ сразу пишем в браузер, при возвращении — восстанавливаем
    const key = 'cq-check-' + form.dataset.check + '-' + form.dataset.user;
    const note = form.querySelector('.autosave');
    const collect = () => {
      const data = {};
      form.querySelectorAll('input[name^="a_"], textarea[name^="a_"], input[name^="s_"]').forEach((el) => {
        if (el.type === 'radio') { if (el.checked) data[el.name] = el.value; }
        else if (el.type === 'checkbox') { if (el.checked) data[el.name] = '1'; }
        else if (el.value) data[el.name] = el.value;
      });
      return data;
    };
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch (e) { saved = {}; }
    Object.entries(saved).forEach(([name, value]) => {
      form.querySelectorAll('[name="' + CSS.escape(name) + '"]').forEach((el) => {
        if (el.type === 'radio') el.checked = el.value === value;
        else if (el.type === 'checkbox') el.checked = true;
        else el.value = value;
      });
    });
    form.querySelectorAll('.check-q').forEach(sync);
    if (Object.keys(saved).length && note) note.textContent = '💾 Восстановили твои ответы — продолжай с того места, где остановился.';
    const store = () => {
      try {
        localStorage.setItem(key, JSON.stringify(collect()));
        if (note) note.textContent = '💾 Сохранено в ' + new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
      } catch (e) { if (note) note.textContent = 'Не получилось сохранить на устройстве — не закрывай страницу до сдачи.'; }
    };
    form.addEventListener('input', store);
    form.addEventListener('change', store);
    form.querySelectorAll('[data-skip-part]').forEach((btn) => btn.addEventListener('click', () => setTimeout(store)));

    let confirmed = false;
    form.addEventListener('submit', async (e) => {
      if (confirmed) return;
      e.preventDefault();
      const empty = [...form.querySelectorAll('.check-q')].filter((q) => {
        const skip = q.querySelector('.check-skip input');
        if (skip && skip.checked) return false;
        const radios = q.querySelectorAll('input[type="radio"]');
        if (radios.length) return ![...radios].some((r) => r.checked);
        const field = q.querySelector('textarea, input[name^="a_"]');
        return !field || !field.value.trim();
      });
      const msg = empty.length
        ? 'Без ответа: ' + empty.length + '. Сдать так или вернуться и дописать?'
        : 'Всё заполнено. Сдаём? После сдачи ответы поменять нельзя.';
      const ok = await ask(msg, empty.length ? 'Сдать так' : 'Сдать', empty.length ? 'Дописать' : 'Ещё проверю');
      if (ok) { confirmed = true; form.requestSubmit ? form.requestSubmit() : form.submit(); }
      else if (empty.length) empty[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }


  // ------------------------------------------------------------------ русский: запятые, арена букв, повторение ошибок
  function initRu() {
    const root = document.querySelector('[data-ru-mode]');
    if (!root) return;
    const mode = root.dataset.ruMode;
    const card = root.querySelector('.ru-card');
    const q = root.querySelector('.ru-question');
    const opts = root.querySelector('.ru-options');
    const btnCheck = root.querySelector('[data-ru-check]');
    const btnNext = root.querySelector('[data-ru-next]');
    const res = root.querySelector('.ru-result');
    const score = root.querySelector('.ru-score');
    const summary = root.querySelector('.ru-summary');
    let item = null, chosen = new Set(), right = 0, total = 0, xp = 0, busy = false;
    let roles = [];                       // грамматическая основа: '' | 's' | 'p' для каждого слова
    const mistakes = [], seen = [];
    const RULE_ROUND = 10;                // «Потренировать правило» — 10 заданий подряд

    const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
    const updateScore = () => { score.textContent = total ? 'Верно ' + right + ' из ' + total + (xp ? ' · +' + xp + ' 🏆' : '') : ''; };

    function renderComma(it) {
      q.replaceChildren(); opts.replaceChildren(); chosen = new Set();
      const line = el('div', 'ru-sentence');
      it.words.forEach((w, i) => {
        line.append(el('span', 'ru-word', w + (i === it.words.length - 1 ? it.end : '')));
        if (i < it.words.length - 1) {
          const gap = el('button', 'ru-gap'); gap.type = 'button'; gap.dataset.gap = i;
          gap.setAttribute('aria-label', 'Запятая после «' + w + '»');
          gap.addEventListener('click', () => {
            if (gap.disabled) return;
            chosen.has(i) ? chosen.delete(i) : chosen.add(i);
            gap.classList.toggle('on', chosen.has(i));
          });
          line.append(gap);
        }
      });
      q.append(line);
      btnCheck.hidden = false; btnNext.hidden = true;
    }

    function renderBasis(it) {
      q.replaceChildren(); opts.replaceChildren(); roles = it.words.map(() => '');
      const line = el('div', 'ru-sentence ru-basis');
      it.words.forEach((w, i) => {
        const b = el('button', 'ru-bword', w); b.type = 'button'; b.dataset.word = i;
        b.addEventListener('click', () => {
          if (b.disabled) return;
          roles[i] = roles[i] === '' ? 's' : roles[i] === 's' ? 'p' : '';
          b.classList.toggle('ru-u-s', roles[i] === 's');
          b.classList.toggle('ru-u-p', roles[i] === 'p');
        });
        line.append(b);
      });
      q.append(line);
      q.append(el('p', 'muted small', 'Одно касание — подлежащее (одна черта), два — сказуемое (две черты), три — снять.'));
      btnCheck.hidden = false; btnNext.hidden = true;
    }

    function basisLine(r) {
      const line = el('div', 'ru-sentence ru-basis-answer');
      r.words.forEach((w, i) => {
        const cls = r.s.includes(i) ? 'ru-u-s' : r.p.includes(i) ? 'ru-u-p' : '';
        line.append(el('span', 'ru-bword ' + cls, w));
      });
      return line;
    }

    function renderSpell(it, onPick) {
      q.replaceChildren(); opts.replaceChildren();
      const line = el('div', 'ru-word-big');
      const parts = it.text.split('_');
      parts.forEach((p, i) => { line.append(document.createTextNode(p)); if (i < parts.length - 1) line.append(el('span', 'ru-blank', '?')); });
      q.append(line);
      it.options.forEach((o) => {
        const b = el('button', 'btn ru-opt', o); b.type = 'button';
        b.addEventListener('click', () => onPick(o, b));
        opts.append(b);
      });
      btnCheck.hidden = true; btnNext.hidden = true;
    }

    function explain(r, it) {
      res.hidden = false;
      res.className = 'ru-result ' + (r.ok ? 'ok' : 'bad');
      res.replaceChildren();
      res.append(el('b', '', r.ok ? '✅ Верно!' + (r.xp ? ' +' + r.xp + ' 🏆' : '') : '❌ Ошибка — разберёмся'));
      if (!r.ok && r.kind === 'basis') { res.append(el('p', 'ru-correct', 'Правильно:')); res.append(basisLine(r)); }
      else if (!r.ok) res.append(el('p', 'ru-correct', (r.gaps && !r.gaps.length ? 'Здесь запятые не нужны: ' : 'Правильно: ') + r.text));
      const rule = el('p', 'ru-rule-text'); rule.append(el('b', '', r.rule_title + '. ')); rule.append(document.createTextNode(r.rule_text));
      res.append(rule);
      if (r.review === 'added') res.append(el('p', 'muted small', '🔁 Добавлено в «Мои ошибки» — повторим завтра.'));
      if (r.review && r.review.startsWith('next:')) res.append(el('p', 'muted small', '🔁 Следующее повторение через ' + r.review.slice(5) + ' дн.'));
      if (r.review === 'mastered') res.append(el('p', 'muted small', '🏅 Запомнил! Больше не повторяем.'));
      if (r.cap_reached) res.append(el('p', 'muted small', 'Трофеи за русский на сегодня собраны — тренироваться можно дальше.'));
    }

    async function send(answer) {
      const r = await CQ.api('/api/ru/answer', { id: item.id, answer, mode: mode === 'spell' ? 'arena' : mode });
      total++; if (r.ok) right++; xp += r.xp || 0; updateScore();
      if (!r.ok) mistakes.push({ item, r });
      CQ.handleNotices(r);
      return r;
    }

    // ---------------- запятые и повторение: одно задание за раз, с разбором
    async function nextOne() {
      res.hidden = true;
      if (mode === 'rule' && total >= RULE_ROUND) return ruleSummary();
      let url = '/api/ru/next?kind=' + (mode === 'review' || mode === 'basis' ? mode : 'comma');
      if (mode === 'rule') url = '/api/ru/next?kind=rule&rule=' + encodeURIComponent(root.dataset.ruRule) + '&skip=' + seen.slice(-8).join(',');
      const r = await fetch(url, { credentials: 'same-origin' }).then((x) => x.json());
      item = r.item;
      if (!item) {
        if (mode === 'rule') return ruleSummary();
        card.hidden = true; summary.hidden = false;
        summary.replaceChildren(el('div', 'big-emoji', '🎉'), el('p', '', total ? 'На сегодня все ошибки повторены. Верно ' + right + ' из ' + total + '.' : 'Повторять пока нечего — ошибок на сегодня нет.'));
        const a = el('a', 'btn', 'К тренажёрам'); a.href = '/ru'; summary.append(a);
        return;
      }
      seen.push(item.id);
      card.hidden = false;
      if (item.kind === 'comma') renderComma(item);
      else if (item.kind === 'basis') renderBasis(item);
      else renderSpell(item, async (o, b) => {
        if (busy) return; busy = true;
        opts.querySelectorAll('button').forEach((x) => { x.disabled = true; });
        const rr = await send(o);
        b.classList.add(rr.ok ? 'right' : 'wrong');
        if (!rr.ok) opts.querySelectorAll('button').forEach((x) => { if (x.textContent === rr.answer) x.classList.add('right'); });
        explain(rr, item); btnNext.hidden = false; busy = false;
      });
    }

    function ruleSummary() {
      card.hidden = true; summary.hidden = false; summary.replaceChildren();
      const good = total && right / total >= 0.8;
      summary.append(el('div', 'big-emoji', good ? '🎯' : '💪'));
      summary.append(el('h2', '', 'Верно ' + right + ' из ' + total + (xp ? ' · +' + xp + ' 🏆' : '')));
      summary.append(el('p', 'muted', good ? 'Правило усвоено — можно браться за следующее.' : 'Ошибки уже в «Моих ошибках» — повторим завтра. Можно пройти ещё круг.'));
      const again = el('button', 'btn', 'Ещё круг'); again.type = 'button'; again.addEventListener('click', () => location.reload());
      const back = el('a', 'btn btn-ghost', 'К правилам'); back.href = '/ru/rules#' + root.dataset.ruRule;
      const row = el('div', 'row'); row.append(again, back); summary.append(row);
    }

    btnCheck.addEventListener('click', async () => {
      if (busy || !item) return; busy = true;
      if (item.kind === 'basis') {
        const s = [], p = [];
        roles.forEach((x, i) => { if (x === 's') s.push(i); if (x === 'p') p.push(i); });
        const rb = await send({ s, p });
        root.querySelectorAll('.ru-bword[data-word]').forEach((b) => {
          const i = Number(b.dataset.word); b.disabled = true;
          const want = rb.s.includes(i) ? 's' : rb.p.includes(i) ? 'p' : '';
          if (want !== roles[i]) b.classList.add('wrong');
          else if (want) b.classList.add('right');
        });
        explain(rb, item); btnCheck.hidden = true; btnNext.hidden = false; busy = false;
        return;
      }
      const r = await send([...chosen]);
      root.querySelectorAll('.ru-gap').forEach((g) => {
        const i = Number(g.dataset.gap); g.disabled = true;
        if (r.gaps.includes(i)) g.classList.add(chosen.has(i) ? 'right' : 'missed');
        else if (chosen.has(i)) g.classList.add('extra');
      });
      explain(r, item); btnCheck.hidden = true; btnNext.hidden = false; busy = false;
    });
    btnNext.addEventListener('click', () => (mode === 'spell' ? null : nextOne()));

    if (mode === 'dict') { initDict(); return; }
    if (mode !== 'spell') { nextOne(); return; }

    // ---------------- диктант: весь текст сразу, проверка в конце
    function initDict() {
      const d = JSON.parse(document.getElementById('ru-dict').textContent);
      const picked = [], commas = new Set();
      card.hidden = false; q.replaceChildren(); opts.replaceChildren();
      const line = el('div', 'ru-sentence ru-dict');
      d.words.forEach((parts, i) => {
        const w = el('span', 'ru-word');
        parts.forEach((p) => {
          if (typeof p === 'string') { w.append(document.createTextNode(p)); return; }
          picked[p.g] = '';
          const b = el('button', 'ru-letter', '?'); b.type = 'button'; b.dataset.g = p.g;
          b.addEventListener('click', () => {
            if (b.disabled) return;
            const k = p.options.indexOf(picked[p.g]);
            picked[p.g] = p.options[(k + 1) % p.options.length];
            b.textContent = picked[p.g]; b.classList.add('on');
          });
          w.append(b);
        });
        line.append(w);
        if (d.can.includes(i)) {
          const gap = el('button', 'ru-gap'); gap.type = 'button'; gap.dataset.gap = i;
          gap.addEventListener('click', () => {
            if (gap.disabled) return;
            commas.has(i) ? commas.delete(i) : commas.add(i);
            gap.classList.toggle('on', commas.has(i));
          });
          line.append(gap);
        } else if (i < d.words.length - 1) line.append(el('span', 'ru-sp'));   // конец предложения: просто пробел
      });
      q.append(line);
      btnCheck.hidden = false; btnNext.hidden = true;
      btnCheck.onclick = async (e) => {
        e.stopImmediatePropagation();
        if (busy) return;
        const empty = picked.filter((x) => !x).length;
        if (empty && !(await ask('Не вставлено букв: ' + empty + '. Проверить так?', 'Проверить', 'Дописать'))) return;
        busy = true;
        const r = await CQ.api('/api/ru/dict', { id: d.id, letters: picked, commas: [...commas] });
        CQ.handleNotices(r);
        root.querySelectorAll('.ru-letter').forEach((b) => {
          const x = r.letters[Number(b.dataset.g)]; b.disabled = true;
          if (!x.ok) { b.textContent = x.answer; b.classList.add('wrong'); } else b.classList.add('right');
        });
        root.querySelectorAll('.ru-gap').forEach((g) => {
          const i = Number(g.dataset.gap); g.disabled = true;
          if (r.need.includes(i)) g.classList.add(commas.has(i) ? 'right' : 'missed');
          else if (commas.has(i)) g.classList.add('extra');
        });
        res.hidden = false; res.replaceChildren();
        res.className = 'ru-result ' + (r.errors ? 'bad' : 'ok');
        res.append(el('b', '', r.errors ? '📝 Ошибок: ' + r.errors : '✅ Без ошибок!'));
        if (r.xp) res.append(el('span', '', ' +' + r.xp + ' 🏆'));
        if (r.extra.length) res.append(el('p', 'small', 'Лишних запятых: ' + r.extra.length + ' (зачёркнуты).'));
        if (r.rules.length) res.append(el('p', 'small', 'Повтори правила: ' + r.rules.join(', ') + '.'));
        res.append(el('p', 'ru-correct', r.text));
        const again = el('a', 'btn', 'Другой диктант →'); again.href = '/ru/dict';
        const rules = el('a', 'btn btn-ghost', 'К правилам'); rules.href = '/ru/rules';
        const row = el('div', 'row'); row.append(again, rules); res.append(row);
        btnCheck.hidden = true; busy = false;
      };
    }

    // ---------------- арена: 60 секунд, без разбора по ходу — разбор в конце
    const start = root.querySelector('[data-ru-start]');
    const timer = root.querySelector('.ru-timer');
    let queue = [], ends = 0, finished = false;
    function finish() {
      if (finished) return;
      finished = true;
      card.hidden = true; timer.hidden = true; summary.hidden = false; summary.replaceChildren();
      summary.append(el('h2', '', '⚡ ' + right + ' верных из ' + total + (xp ? ' · +' + xp + ' 🏆' : '')));
      if (mistakes.length) {
        summary.append(el('p', 'muted', 'Разбор ошибок — они уже в «Моих ошибках» на завтра:'));
        const ul = el('ul', 'ru-mistakes');
        mistakes.forEach(({ r }) => { const li = el('li'); li.append(el('b', '', r.text)); li.append(document.createTextNode(' — ' + r.rule_title + '. ' + r.rule_text)); ul.append(li); });
        summary.append(ul);
      } else if (total) summary.append(el('p', '', 'Ни одной ошибки! 🔥'));
      const again = el('button', 'btn', 'Ещё раз'); again.type = 'button'; again.addEventListener('click', () => location.reload());
      const back = el('a', 'btn btn-ghost', 'К тренажёрам'); back.href = '/ru';
      const row = el('div', 'row'); row.append(again, back); summary.append(row);
    }
    function showNext() {
      if (Date.now() >= ends) return finish();
      if (!queue.length) return finish();
      item = queue.shift();
      renderSpell(item, async (o, b) => {
        if (busy) return; busy = true;
        opts.querySelectorAll('button').forEach((x) => { x.disabled = true; });
        const r = await send(o);
        b.classList.add(r.ok ? 'right' : 'wrong');
        setTimeout(() => { busy = false; showNext(); }, r.ok ? 250 : 700);
      });
    }
    start.addEventListener('click', async () => {
      const r = await fetch('/api/ru/batch', { credentials: 'same-origin' }).then((x) => x.json());
      queue = r.items; ends = Date.now() + 60000;
      root.querySelector('.ru-arena-start').hidden = true; card.hidden = false; timer.hidden = false;
      const t = timer.querySelector('b');
      const tick = () => {
        if (finished) return;
        const left = Math.max(0, Math.ceil((ends - Date.now()) / 1000));
        t.textContent = left;
        if (left <= 0) finish(); else setTimeout(tick, 250);
      };
      tick(); showNext();
    });
  }

  // ------------------------------------------------------------------ бойцы: живая карточка
  // Клик по открытому бойцу — окно, где он «дышит», наклоняется за мышью или пальцем (3D) и по кнопке «Супер!»
  // показывает суперспособность: вспышка, тряска и искры его эмодзи.
  function initHeroes() {
    const cards = document.querySelectorAll('[data-hero]');
    if (!cards.length) return;
    const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
    let modal = null;
    function close() { if (modal) { modal.remove(); modal = null; } }
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
    cards.forEach((card) => card.addEventListener('click', () => {
      close();
      const d = card.dataset;
      modal = el('div', 'hero-modal');
      const box = el('div', 'hero-box ' + [...card.classList].filter((c) => c.startsWith('rarity-')).join(' '));
      const stage = el('div', 'hero-stage');
      const fig = el('div', 'hero-fig');
      if (d.heroImg) { const img = el('img'); img.src = d.heroImg; img.alt = d.heroName; fig.append(img); }
      else fig.append(el('span', 'hero-emoji', d.heroEmoji));
      fig.append(el('div', 'hero-shine'));
      stage.append(fig);
      const ult = el('button', 'btn hero-ult', '💥 Супер!'); ult.type = 'button';
      const shut = el('button', 'hero-close', '×'); shut.type = 'button'; shut.setAttribute('aria-label', 'Закрыть');
      box.append(shut, el('div', 'b-rarity', d.heroRarity), stage, el('h2', '', d.heroName), el('p', '', d.heroSup), ult);
      modal.append(box);
      document.body.append(modal);
      modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
      shut.addEventListener('click', close);
      // 3D-наклон за указателем
      const tilt = (x, y) => {
        const r = stage.getBoundingClientRect();
        const dx = (x - r.left) / r.width - 0.5, dy = (y - r.top) / r.height - 0.5;
        fig.style.setProperty('--rx', (-dy * 30).toFixed(1) + 'deg');
        fig.style.setProperty('--ry', (dx * 36).toFixed(1) + 'deg');
        fig.style.setProperty('--sx', (50 + dx * 80).toFixed(0) + '%');
      };
      stage.addEventListener('pointermove', (e) => tilt(e.clientX, e.clientY));
      stage.addEventListener('pointerleave', () => { fig.style.setProperty('--rx', '0deg'); fig.style.setProperty('--ry', '0deg'); });
      ult.addEventListener('click', () => {
        fig.classList.remove('ulting'); void fig.offsetWidth; fig.classList.add('ulting');
        box.classList.remove('flash'); void box.offsetWidth; box.classList.add('flash');
        for (let i = 0; i < 18; i++) {
          const p = el('span', 'hero-spark', d.heroEmoji);
          const a = (Math.PI * 2 * i) / 18, dist = 110 + Math.random() * 70;
          p.style.setProperty('--tx', Math.cos(a) * dist + 'px');
          p.style.setProperty('--ty', Math.sin(a) * dist + 'px');
          p.style.animationDelay = (Math.random() * 0.12).toFixed(2) + 's';
          stage.append(p);
          setTimeout(() => p.remove(), 1100);
        }
      });
    }));
  }

  // ------------------------------------------------------------------ исполнитель «Робот» (ОГЭ №15)
  function initRobot() {
    const root = document.getElementById('robot-app');
    if (!root || !window.CQRunner) return;
    const NS = 'http://www.w3.org/2000/svg';
    const runner = CQRunner.runner;
    const fields = JSON.parse(document.getElementById('robot-fields').textContent);
    const starter = JSON.parse(document.getElementById('robot-starter').textContent);
    const taskId = root.dataset.task;
    const exam = root.dataset.exam === '1';      // «как на экзамене»: одно поле на виду, итог проверки — только баллы
    const draftKey = 'cq-robot-' + (exam ? 'exam-' : '') + taskId + '-' + root.dataset.user;
    const $ = (sel) => root.querySelector(sel);
    const svgBox = $('.robot-svg');
    const tabs = $('.robot-tabs');
    const status = $('[data-robot-status]');
    const resultBox = $('[data-robot-result]');
    const goalBox = $('[data-robot-goal]');
    const speed = $('[data-robot-speed]');
    const runBtn = $('[data-robot-run]');
    const checkBtn = $('[data-robot-check]');
    const ta = $('[data-robot-code]');
    const DELAYS = [260, 140, 70, 30, 6];
    let current = 0;
    let results = null;
    let anim = 0;          // номер текущей анимации: новая отменяет старую
    let mark = null;

    try { const d = localStorage.getItem(draftKey); if (d) ta.value = d; } catch (e) { /* без черновика */ }
    let cm = null;
    if (window.CodeMirror) {
      cm = CodeMirror.fromTextArea(ta, { mode: 'python', lineNumbers: true, indentUnit: 4, tabSize: 4,
        matchBrackets: true, autoCloseBrackets: true, viewportMargin: Infinity,
        extraKeys: {
          Tab: (c) => c.somethingSelected() ? c.indentSelection('add') : c.replaceSelection('    ', 'end'),
          'Shift-Tab': (c) => c.indentSelection('subtract'),
          'Ctrl-Enter': () => run(), 'Cmd-Enter': () => run(),
        } });
    }
    const getCode = () => cm ? cm.getValue() : ta.value;
    const setCode = (v) => { if (cm) cm.setValue(v); else ta.value = v; };
    const saveDraft = () => { try { localStorage.setItem(draftKey, getCode()); } catch (e) { /* нет места */ } };
    if (cm) cm.on('change', () => { saveDraft(); clearMark(); }); else ta.addEventListener('input', saveDraft);
    function clearMark() { if (mark && cm) { cm.removeLineClass(mark, 'background', 'cm-error-line'); mark = null; } }

    // ---- рисование
    function svg(tag, attrs, parent) {
      const n = document.createElementNS(NS, tag);
      for (const k in attrs) n.setAttribute(k, attrs[k]);
      if (parent) parent.append(n);
      return n;
    }
    let view = null;   // {s, painted, robot, layer}
    function draw(f) {
      const s = Math.max(16, Math.min(38, Math.floor((svgBox.clientWidth - 4) / f.w)));
      const W = f.w * s, H = f.h * s;
      const g = svg('svg', { viewBox: '-2 -2 ' + (W + 4) + ' ' + (H + 4), width: W + 4, height: H + 4, class: 'robot-grid' });
      for (let x = 0; x <= f.w; x++) svg('line', { x1: x * s, y1: 0, x2: x * s, y2: H, class: 'rg-line' }, g);
      for (let y = 0; y <= f.h; y++) svg('line', { x1: 0, y1: y * s, x2: W, y2: y * s, class: 'rg-line' }, g);
      const paintLayer = svg('g', {}, g);
      if (goalBox.checked) {
        for (const [x, y] of f.target) svg('rect', { x: x * s + 4, y: y * s + 4, width: s - 8, height: s - 8, rx: 3, class: 'rg-goal' }, g);
      }
      for (const [x, y, side] of f.walls) {
        if (side === 'r') svg('line', { x1: (x + 1) * s, y1: y * s, x2: (x + 1) * s, y2: (y + 1) * s, class: 'rg-wall' }, g);
        else svg('line', { x1: x * s, y1: (y + 1) * s, x2: (x + 1) * s, y2: (y + 1) * s, class: 'rg-wall' }, g);
      }
      const robot = svg('g', { class: 'rg-robot' }, g);
      svg('rect', { x: 3, y: 3, width: s - 6, height: s - 6, rx: s / 4 }, robot);
      const eye = (cx) => svg('circle', { cx, cy: s * 0.42, r: Math.max(1.5, s / 12), class: 'rg-eye' }, robot);
      eye(s * 0.36); eye(s * 0.64);
      svgBox.replaceChildren(g);
      view = { s, f, paintLayer, robot, painted: new Set(), cells: {} };
      place(f.start[0], f.start[1]);
    }
    function place(x, y) { view.robot.setAttribute('transform', 'translate(' + x * view.s + ',' + y * view.s + ')'); view.x = x; view.y = y; }
    function paint(x, y) {
      const k = x + ',' + y;
      if (view.painted.has(k)) return;
      view.painted.add(k);
      const goal = view.f.target.some((c) => c[0] === x && c[1] === y);
      view.cells[k] = svg('rect', { x: x * view.s + 1, y: y * view.s + 1, width: view.s - 2, height: view.s - 2,
        class: goal || !goalBox.checked ? 'rg-paint' : 'rg-extra' }, view.paintLayer);
    }
    function crash(x, y, dx, dy) {
      const s = view.s;
      const cx = x * s + s / 2 + dx * s / 2, cy = y * s + s / 2 + dy * s / 2;
      svg('circle', { cx, cy, r: s / 3, class: 'rg-crash' }, svgBox.firstChild);
      view.robot.classList.add('crashed');
    }
    function showMissing(missing) {
      for (const [x, y] of missing || []) {
        svg('rect', { x: x * view.s + 2, y: y * view.s + 2, width: view.s - 4, height: view.s - 4, rx: 3, class: 'rg-missing' }, view.paintLayer);
      }
    }

    async function animate(ops, res) {
      const my = ++anim;
      draw(fields[current]);
      for (const op of ops || []) {
        if (my !== anim) return;
        if (op[0] === 'm') place(op[1], op[2]);
        else if (op[0] === 'p') paint(op[1], op[2]);
        else if (op[0] === 'crash') crash(op[1], op[2], op[3], op[4]);
        const d = DELAYS[(+speed.value || 3) - 1];
        if (d > 8 || Math.random() < 0.2) await new Promise((r) => setTimeout(r, d));
      }
      if (my === anim && res && !res.error) showMissing(res.missing);
    }

    // ---- вкладки полей
    function renderTabs() {
      tabs.replaceChildren();
      if (exam) { tabs.append(Object.assign(document.createElement('span'), { className: 'robot-tab active', textContent: 'Поле из условия' })); return; }
      fields.forEach((f, i) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'robot-tab' + (i === current ? ' active' : '');
        const r = results && results[i];
        b.textContent = (r ? (r.ok ? '✅ ' : '❌ ') : '') + (i === 0 ? 'Пример' : 'Поле ' + (i + 1));
        b.onclick = () => { current = i; renderTabs(); const rr = results && results[i]; if (rr && rr.ops) animate(rr.ops, rr); else { anim++; draw(fields[i]); } };
        tabs.append(b);
      });
    }

    function busy(on, text) {
      runBtn.disabled = checkBtn.disabled = on;
      status.textContent = text || '';
    }
    async function prepare() {
      if (!runner.ready) status.textContent = 'Загружаю Python… (первый раз — около 10 МБ)';
      try { await runner.start(); return true; } catch (e) {
        status.textContent = 'Не получилось загрузить Python. Обнови страницу.';
        return false;
      }
    }
    function errorText(r) {
      if (r.error) return '💥 ' + (r.error.hint || r.error.type) + (r.error.line ? ' (строка ' + r.error.line + ')' : '');
      const parts = [];
      if (r.missing && r.missing.length) parts.push('не закрашено клеток: ' + r.missing.length);
      if (r.extra && r.extra.length) parts.push('лишних закрашенных: ' + r.extra.length);
      return parts.length ? '🎨 ' + parts.join(', ') : '';
    }
    function markLine(r) {
      clearMark();
      if (cm && r && r.error && r.error.line) mark = cm.addLineClass(r.error.line - 1, 'background', 'cm-error-line');
    }

    async function run() {
      if (runBtn.disabled) return;
      busy(true);
      if (!(await prepare())) { busy(false); return; }
      busy(true, 'Робот работает…');
      const res = await runner.robot(getCode(), [fields[current]]);
      busy(false);
      const r = res.error ? { error: res.error, ok: false } : ((res.results || [])[0] || { ok: false });
      resultBox.hidden = false;
      resultBox.className = 'robot-result ' + (r.ok ? 'ok' : 'bad');
      resultBox.textContent = r.ok ? '✅ На этом поле всё верно. Теперь проверь на всех полях.' : (errorText(r) || 'Не всё закрашено как надо.');
      markLine(r);
      await animate(r.ops, r);
    }

    async function check() {
      if (checkBtn.disabled) return;
      busy(true);
      if (!(await prepare())) { busy(false); return; }
      busy(true, 'Проверяю на всех полях…');
      const code = getCode();
      const res = await runner.robot(code, fields);
      busy(false);
      results = res.error ? null : (res.results || null);   // res.error — программа не завершилась (тайм-аут)
      const passed = !!res.passed;
      resultBox.hidden = false;
      resultBox.replaceChildren();
      resultBox.className = 'robot-result ' + (passed ? 'ok' : 'bad');
      if (exam) {
        const h = document.createElement('b');
        h.textContent = passed ? '🎉 2 балла из 2: программа сработала на всех ' + fields.length + ' полях проверки.'
          : '0 баллов из 2: на каком-то поле проверки программа ошибается или зацикливается.';
        resultBox.append(h);
        if (!passed) resultBox.append(Object.assign(document.createElement('p'), { className: 'small',
          textContent: 'Какое поле — не скажем, как и на экзамене. Подумай о крайних случаях: стена длиной в одну клетку, ' +
            'проход шириной в одну клетку, очень длинная стена. Учебный режим покажет все поля.' }));
        results = null;
      }
      const head = document.createElement('b');
      head.textContent = passed ? '🎉 Программа работает на всех полях — как на экзамене!' :
        (results ? '😕 Не на всех полях. Посмотри на поля с ❌:' : '💥 ' + ((res.error && res.error.hint) || 'Ошибка запуска'));
      if (!exam) resultBox.append(head);
      if (results) {
        const ul = document.createElement('ul');
        results.forEach((r, i) => {
          if (r.ok) return;
          const li = document.createElement('li');
          li.textContent = (i === 0 ? 'Пример' : 'Поле ' + (i + 1)) + ': ' + errorText(r);
          ul.append(li);
        });
        if (ul.children.length) resultBox.append(ul);
        const firstBad = results.findIndex((r) => !r.ok);
        current = firstBad >= 0 ? firstBad : 0;
        renderTabs();
        markLine(results[current]);
        const rr = results[current];
        if (rr.ops) animate(rr.ops, rr); else { anim++; draw(fields[current]); }
      }
      try {
        const r = await api('/api/robot/' + taskId + '/attempt', { code, passed });
        handleNotices(r);
        if (passed) {
          if (!r.first) confetti(60);
          const badge = document.getElementById('robot-badge');
          if (badge) { badge.textContent = '✅ Решено'; badge.classList.add('ok'); }
          const ans = document.querySelector('[data-robot-answer]');
          if (ans && r.solution) {
            ans.hidden = false;
            ans.querySelector('[data-robot-sol-py]').textContent = r.solution;
            ans.querySelector('[data-robot-sol-ku]').textContent = r.kumir;
          }
        }
      } catch (e) { /* без сети попытка просто не запишется */ }
    }

    runBtn.addEventListener('click', run);
    checkBtn.addEventListener('click', check);
    $('[data-robot-reset]').addEventListener('click', async () => {
      if (await ask('Вернуть исходный код? Твои изменения пропадут.', 'Вернуть', 'Отмена')) setCode(starter);
    });
    goalBox.addEventListener('change', () => { anim++; draw(fields[current]); });
    let rt = 0;
    window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { anim++; draw(fields[current]); }, 200); });
    renderTabs();
    draw(fields[0]);
    const warm = () => runner.start().catch(() => {});
    ('requestIdleCallback' in window) ? requestIdleCallback(warm, { timeout: 3000 }) : setTimeout(warm, 1500);
  }

  // ------------------------------------------------------------------ битва ботов
  function initBots() {
    const root = document.getElementById('bots-app');
    if (!root || !window.CQRunner) return;
    const NS = 'http://www.w3.org/2000/svg';
    const runner = CQRunner.runner;
    const starter = JSON.parse(document.getElementById('bots-starter').textContent);
    const $ = (sel) => root.querySelector(sel);
    const draftKey = 'cq-bots-' + root.dataset.user;
    const box = $('.bots-svg');
    const status = $('[data-bots-status]');
    const resultBox = $('[data-bots-result]');
    const fightBtn = $('[data-bots-fight]');
    const speed = $('[data-bots-speed]');
    const ta = $('[data-bots-code]');
    const DELAYS = [420, 260, 150, 80, 25];
    const W = 11, H = 9;
    const WALLS = [[4, 4], [6, 4], [3, 2], [7, 2], [3, 6], [7, 6], [5, 1], [5, 7], [2, 4], [8, 4]];
    const BASES = { blue: [1, 4], red: [9, 4] };
    let boss = root.dataset.boss;
    const START = { t: 0, p: { blue: [1, 4, 3, 0, 0], red: [9, 4, 3, 0, 0] }, g: [], s: [] };
    let anim = 0;
    let mark = null;

    try { const d = localStorage.getItem(draftKey); if (d) ta.value = d; } catch (e) { /* без черновика */ }
    let cm = null;
    if (window.CodeMirror) {
      cm = CodeMirror.fromTextArea(ta, { mode: 'python', lineNumbers: true, indentUnit: 4, tabSize: 4,
        matchBrackets: true, autoCloseBrackets: true, viewportMargin: Infinity,
        extraKeys: {
          Tab: (c) => c.somethingSelected() ? c.indentSelection('add') : c.replaceSelection('    ', 'end'),
          'Shift-Tab': (c) => c.indentSelection('subtract'),
          'Ctrl-Enter': () => fight(), 'Cmd-Enter': () => fight(),
        } });
    }
    const getCode = () => cm ? cm.getValue() : ta.value;
    const setCode = (v) => { if (cm) cm.setValue(v); else ta.value = v; };
    const saveDraft = () => { try { localStorage.setItem(draftKey, getCode()); } catch (e) { /* нет места */ } };
    if (cm) cm.on('change', () => { saveDraft(); clearMark(); }); else ta.addEventListener('input', saveDraft);
    function clearMark() { if (mark && cm) { cm.removeLineClass(mark, 'background', 'cm-error-line'); mark = null; } }

    function svg(tag, attrs, parent, text) {
      const n = document.createElementNS(NS, tag);
      for (const k in attrs) n.setAttribute(k, attrs[k]);
      if (text != null) n.textContent = text;
      if (parent) parent.append(n);
      return n;
    }
    let s = 30;
    function drawFrame(f) {
      s = Math.max(22, Math.min(46, Math.floor((box.clientWidth - 4) / W)));
      const g = svg('svg', { viewBox: '-2 -2 ' + (W * s + 4) + ' ' + (H * s + 4), width: W * s + 4, height: H * s + 4, class: 'bots-grid' });
      svg('rect', { x: 0, y: 0, width: W * s, height: H * s, class: 'bg-field', rx: 8 }, g);
      for (const side in BASES) svg('rect', { x: BASES[side][0] * s + 2, y: BASES[side][1] * s + 2, width: s - 4, height: s - 4, rx: 6, class: 'bg-base ' + side }, g);
      for (const [x, y] of WALLS) svg('rect', { x: x * s + 1, y: y * s + 1, width: s - 2, height: s - 2, rx: 5, class: 'bg-wall' }, g);
      if (f) {
        const count = {};
        for (const [x, y] of f.g) count[x + ',' + y] = (count[x + ',' + y] || 0) + 1;
        for (const k in count) {
          const [x, y] = k.split(',').map(Number);
          svg('text', { x: x * s + s / 2, y: y * s + s * 0.68, 'font-size': s * 0.55, 'text-anchor': 'middle' }, g, '💎');
          if (count[k] > 1) svg('text', { x: x * s + s - 3, y: y * s + 11, 'font-size': 10, 'text-anchor': 'end', class: 'bg-count' }, g, '×' + count[k]);
        }
        for (const [side, x, y, dx, dy, len, hit] of f.s) {
          svg('line', { x1: x * s + s / 2, y1: y * s + s / 2, x2: (x + dx * len) * s + s / 2, y2: (y + dy * len) * s + s / 2, class: 'bg-shot ' + side + (hit ? ' hit' : '') }, g);
        }
        for (const side of ['blue', 'red']) {
          const [x, y, hp, gems, dead] = f.p[side];
          const bot = svg('g', { class: 'bg-bot ' + side + (dead ? ' dead' : ''), transform: 'translate(' + x * s + ',' + y * s + ')' }, g);
          svg('circle', { cx: s / 2, cy: s / 2, r: s * 0.38 }, bot);
          svg('text', { x: s / 2, y: s * 0.62, 'font-size': s * 0.4, 'text-anchor': 'middle' }, bot, dead ? '💀' : (side === 'blue' ? '🤖' : '👾'));
          for (let i = 0; i < 3; i++) svg('rect', { x: s * 0.18 + i * s * 0.22, y: 1, width: s * 0.18, height: 4, rx: 1, class: 'bg-hp' + (i < hp ? ' on' : '') }, bot);
          if (gems) svg('text', { x: s - 2, y: s - 2, 'font-size': 10, 'text-anchor': 'end', class: 'bg-count' }, bot, gems);
        }
        $('[data-score-blue]').textContent = f.p.blue[3];
        $('[data-score-red]').textContent = f.p.red[3];
        $('[data-turn]').textContent = 'ход ' + f.t;
      }
      box.replaceChildren(g);
    }

    async function play(frames) {
      const my = ++anim;
      for (const f of frames) {
        if (my !== anim) return;
        drawFrame(f);
        await new Promise((r) => setTimeout(r, DELAYS[(+speed.value || 3) - 1]));
      }
    }

    function selectBoss(btn) {
      if (btn.disabled) return;
      root.querySelectorAll('.bots-boss').forEach((b) => b.classList.toggle('active', b === btn));
      boss = btn.dataset.boss;
      $('[data-bots-about]').textContent = btn.dataset.about;
      $('[data-boss-name]').textContent = btn.querySelector('b').textContent;
      resultBox.hidden = true;
      anim++;
      drawFrame(START);
    }
    root.querySelectorAll('.bots-boss').forEach((b) => b.addEventListener('click', () => selectBoss(b)));

    async function fight() {
      if (fightBtn.disabled) return;
      fightBtn.disabled = true;
      if (!runner.ready) status.textContent = 'Загружаю Python… (первый раз — около 10 МБ)';
      try { await runner.start(); } catch (e) {
        status.textContent = 'Не получилось загрузить Python. Обнови страницу.';
        fightBtn.disabled = false;
        return;
      }
      status.textContent = 'Идёт матч из 3 боёв…';
      const code = getCode();
      const res = await runner.bots(code, boss);
      fightBtn.disabled = false;
      status.textContent = '';
      resultBox.hidden = false;
      resultBox.replaceChildren();
      clearMark();
      if (res.error && !res.battle) {        // программа не завершилась (тайм-аут)
        resultBox.className = 'robot-result bad';
        resultBox.textContent = '💥 ' + (res.error.hint || 'Ошибка запуска');
        return;
      }
      resultBox.className = 'robot-result ' + (res.won ? 'ok' : 'bad');
      const head = document.createElement('b');
      const score = ' (побед ' + res.wins + ', поражений ' + res.losses + ')';
      head.textContent = res.won ? '🏆 Победа в матче' + score + '!' :
        (res.wins > res.losses ? '💪 Почти! Нужно выиграть 2 боя из 3' : res.wins === res.losses ? '🤝 Ничья' : '😤 Поражение') +
        score + '. Посмотри показанный бой и подумай, что изменить.';
      resultBox.append(head);
      const ul = document.createElement('ul');
      res.games.forEach((g, i) => {
        const li = document.createElement('li');
        li.textContent = 'Бой ' + (i + 1) + ': ' + g.score.blue + ' : ' + g.score.red + ' 💎 — ' +
          (g.winner === 'blue' ? 'победа' : g.winner === 'red' ? 'поражение' : 'ничья') + (i === res.shown ? ' (показан)' : '');
        ul.append(li);
      });
      resultBox.append(ul);
      if (res.error) {
        const p = document.createElement('p');
        p.textContent = '🐞 ' + (res.error.type || 'Ошибка') + (res.error.turn ? ' на ходу ' + res.error.turn : '') +
          (res.error.line ? ', строка ' + res.error.line : '') + ': ' + (res.error.hint || '');
        resultBox.append(p);
        if (cm && res.error.line) mark = cm.addLineClass(res.error.line - 1, 'background', 'cm-error-line');
      }
      try {
        const r = await api('/api/bots/' + boss + '/result', { code, won: !!res.won });
        handleNotices(r);
        if (res.won) {
          const btn = root.querySelector('.bots-boss[data-boss="' + boss + '"]');
          if (btn) { btn.classList.add('beaten'); btn.querySelector('small').textContent = '✅ побеждён'; }
          const next = btn && btn.nextElementSibling;
          if (next && next.disabled) {
            next.disabled = false; next.removeAttribute('title');
            next.querySelector('.be').textContent = next.dataset.emoji;
          }
        }
      } catch (e) { /* без сети результат просто не запишется */ }
      await play(res.battle.frames || []);
    }

    fightBtn.addEventListener('click', fight);
    $('[data-bots-reset]').addEventListener('click', async () => {
      if (await ask('Вернуть заготовку? Твой код пропадёт.', 'Вернуть', 'Отмена')) setCode(starter);
    });
    let rt = 0;
    window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { anim++; drawFrame(START); }, 200); });
    drawFrame(START);
    const warm = () => runner.start().catch(() => {});
    ('requestIdleCallback' in window) ? requestIdleCallback(warm, { timeout: 3000 }) : setTimeout(warm, 1500);
  }

  // ------------------------------------------------------------------ химия: задача и таблица Менделеева
  function chemHtml(text) {
    const esc = (text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return esc.replace(/([A-Za-z\)\]])(\d+)/g, '$1<sub>$2</sub>').replace(/\n/g, '<br>');
  }

  function initChemTask() {
    const root = document.getElementById('chem-task');
    if (!root) return;
    const id = root.dataset.task;
    const form = root.querySelector('[data-chem-form]');
    const box = root.querySelector('[data-chem-result]');
    if (form) {
      const draftKey = 'cq-chem-answer-' + id;
      const field = form.querySelector('input');
      try { const d = localStorage.getItem(draftKey); if (d && !field.value) field.value = d; } catch (e) { /* без черновика */ }
      field.addEventListener('input', () => { try { localStorage.setItem(draftKey, field.value); } catch (e) { /* нет места */ } });
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        try { localStorage.removeItem(draftKey); } catch (err) { /* ничего */ }
        const input = form.querySelector('input');
        const btn = form.querySelector('button');
        btn.disabled = true;
        try {
          const r = await api('/api/chem/task/' + id, { answer: input.value, hw: +root.dataset.hw || null });
          handleNotices(r);
          box.hidden = false;
          const full = r.points === r.max;
          box.className = 'robot-result ' + (full ? 'ok' : 'bad');
          let html = full ? '🎉 Верно! ' + r.points + ' из ' + r.max + (r.max === 1 ? ' балла.' : ' баллов.') + (r.after_reveal ? ' Ответ уже был показан, поэтому в зачёт не идёт — возьми новый вариант.' : '') :
            (r.points ? '👍 Почти: ' + r.points + ' из ' + r.max + ' — одна ошибка.' : '😕 Пока неверно. Попробуй ещё раз.');
          if (r.answer !== undefined) {
            html += '<br><b>Ответ: ' + chemHtml(r.answer) + '</b>';
            if (r.why) html += '<br>' + chemHtml(r.why);
          }
          box.innerHTML = html;
          if (full) confetti(40);
        } catch (err) {
          box.hidden = false;
          box.className = 'robot-result bad';
          box.textContent = 'Не получилось отправить ответ. Проверь интернет.';
        }
        btn.disabled = false;
      });
    }
    const sampleBtn = root.querySelector('[data-chem-sample]');
    if (sampleBtn) {
      sampleBtn.addEventListener('click', async () => {
        const r = await fetch('/api/chem/task/' + id + '/sample', { credentials: 'same-origin' }).then((x) => x.json());
        const s = root.querySelector('.chem-sample');
        s.hidden = false;
        s.innerHTML = chemHtml(r.why);
        sampleBtn.hidden = true;
      });
    }
  }

  function initPeriodicTable() {
    const detail = document.querySelector('[data-pt-detail]');
    if (!detail) return;
    const set = (f, v) => { const el = detail.querySelector('[data-f="' + f + '"]'); if (el) el.textContent = v; };
    document.querySelectorAll('.pt-el').forEach((b) => b.addEventListener('click', () => {
      document.querySelectorAll('.pt-el.active').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      const d = b.dataset;
      set('z', d.z); set('sym', d.sym); set('name', d.name); set('mass', d.mass);
      set('period', d.period); set('group', d.group); set('cat', d.cat);
      set('shells', d.shells ? ' · электроны по слоям: ' + d.shells : '');
      set('state', d.state); set('config', d.config ? 'Электронная конфигурация: ' + d.config : '');
      set('en', d.en ? (d.config ? ' · ' : '') + 'электроотрицательность ' + d.en : '');
      detail.querySelector('[data-f="fact"]').innerHTML = chemHtml(d.fact || '');   // формулы в факте: O3, CaCO3
      const fig = detail.querySelector('[data-photo]');
      if (fig) {
        fig.hidden = !d.photo;
        if (d.photo) {
          fig.querySelector('img').src = d.photo;
          fig.querySelector('img').alt = d.name;
          const a = fig.querySelector('a');
          a.textContent = 'Фото: ' + d.credit;
          const note = fig.querySelector('[data-photo-note]');
          if (note) note.textContent = d.photoNote ? d.photoNote + '. ' : '';
          a.href = d.creditUrl;
        }
      }
      detail.className = 'card pt-detail cat-' + (b.className.match(/cat-(\w+)/) || ['', ''])[1];
      // на телефоне карточка выше таблицы и уходит с экрана — показываем её
      const r = detail.getBoundingClientRect();
      if (r.top < 0 || r.top > window.innerHeight * 0.5) detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }));
    const first = document.querySelector('.pt-el[data-sym="O"]');
    if (first) first.click();
  }

  // ------------------------------------------------------------------ подсказка-название у формулы (касание на телефоне)
  function initFormulaTips() {
    let tip = null;
    const hide = () => { if (tip) { tip.remove(); tip = null; } };
    document.addEventListener('click', (e) => {
      const f = e.target.closest && e.target.closest('.f[title]');
      hide();
      if (!f) return;
      tip = document.createElement('div');
      tip.className = 'f-tip';
      tip.textContent = f.getAttribute('title');
      document.body.append(tip);
      const r = f.getBoundingClientRect();
      tip.style.left = Math.max(8, Math.min(window.scrollX + r.left, window.scrollX + document.documentElement.clientWidth - tip.offsetWidth - 8)) + 'px';
      tip.style.top = (window.scrollY + r.bottom + 6) + 'px';
      setTimeout(hide, 3000);
    });
    window.addEventListener('scroll', hide, { passive: true });
  }

  // ------------------------------------------------------------------ окно ввода химических формул
  const FORMULA_KEYS = [
    ['Заряды', ['⁺', '⁻', '²⁺', '²⁻', '³⁺', '³⁻', '⁰']],
    ['Знаки', [' → ', ' ⇄ ', '↑', '↓', ' + ', ' = ', 't°', 'e⁻', '·']],
    ['Условия', ['(конц.)', '(разб.)', '(р-р)', '(тв.)', '(г.)', 'кат.', 'hν']],
    ['Частые', ['H2O', 'H2SO4', 'HCl', 'HNO3', 'NaOH', 'NaCl', 'CO2', 'O2', 'H2', 'KMnO4', 'Cu(OH)2', 'Fe(OH)3']],
  ];

  function openFormulaEditor(target) {
    const wrap = document.createElement('div');
    wrap.className = 'cq-modal';
    const card = document.createElement('div');
    card.className = 'cq-modal-card formula-card';
    card.setAttribute('role', 'dialog');
    card.innerHTML = '<div class="row between"><h3>⚗️ Формула</h3>' +
      '<button type="button" class="cq-modal-x" data-cancel title="Закрыть" aria-label="Закрыть">✕</button></div>' +
      '<p class="small muted">Пиши обычными цифрами — H2SO4 станет H₂SO₄. Заряды и стрелки — кнопками ниже.</p>' +
      '<input class="formula-input" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="например, Fe2(SO4)3 или SO4²⁻">' +
      '<div class="formula-preview chem-text" aria-live="polite"></div><div class="formula-keys"></div>' +
      '<div class="row"><button type="button" class="btn" data-ok>Вставить</button>' +
      '<button type="button" class="btn btn-ghost" data-cancel>Отмена</button></div>';
    wrap.append(card);
    const input = card.querySelector('.formula-input');
    const preview = card.querySelector('.formula-preview');
    const keys = card.querySelector('.formula-keys');
    const sel = target.selectionStart != null ? target.value.slice(target.selectionStart, target.selectionEnd) : '';
    input.value = sel;
    const update = () => { preview.innerHTML = input.value ? chemHtml(input.value) : '<span class="muted">здесь будет предпросмотр</span>'; };
    FORMULA_KEYS.forEach(([title, list]) => {
      const row = document.createElement('div');
      row.className = 'formula-row';
      const label = document.createElement('small');
      label.textContent = title;
      row.append(label);
      list.forEach((k) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'formula-key';
        b.innerHTML = chemHtml(k.trim() || k);
        b.addEventListener('click', () => {
          const s = input.selectionStart ?? input.value.length, e = input.selectionEnd ?? input.value.length;
          input.value = input.value.slice(0, s) + k + input.value.slice(e);
          input.focus();
          input.setSelectionRange(s + k.length, s + k.length);
          update();
        });
        row.append(b);
      });
      keys.append(row);
    });
    const close = () => { wrap.remove(); document.removeEventListener('keydown', onKey); target.focus(); };
    const insert = () => {
      const v = input.value;
      if (v) {
        const s = target.selectionStart ?? target.value.length, e = target.selectionEnd ?? target.value.length;
        target.value = target.value.slice(0, s) + v + target.value.slice(e);
        target.setSelectionRange(s + v.length, s + v.length);
        target.dispatchEvent(new Event('input', { bubbles: true }));
      }
      close();
    };
    const onKey = (e) => {
      if (e.key === 'Escape') close();
      if (e.key === 'Enter' && document.activeElement === input) { e.preventDefault(); insert(); }
    };
    input.addEventListener('input', update);
    card.querySelector('[data-ok]').addEventListener('click', insert);
    card.querySelectorAll('[data-cancel]').forEach((b) => b.addEventListener('click', close));
    wrap.addEventListener('click', (e) => { if (e.target === wrap) insert(); });   // щелчок мимо окна не теряет формулу
    document.addEventListener('keydown', onKey);
    document.body.append(wrap);
    update();
    input.focus();
  }

  function initDrafts() {
    // черновик формы в браузере: текст не пропадает при перезагрузке или ошибке; после отправки — стирается
    document.querySelectorAll('form[data-draft]').forEach((form) => {
      const key = 'cq-draft-' + form.dataset.draft;
      const fields = form.querySelectorAll('textarea');
      try {
        const saved = JSON.parse(localStorage.getItem(key) || '{}');
        fields.forEach((f) => { if (!f.value && saved[f.name]) f.value = saved[f.name]; });
      } catch (e) { /* без черновика */ }
      const save = () => {
        const data = {};
        fields.forEach((f) => { data[f.name] = f.value; });
        try { localStorage.setItem(key, JSON.stringify(data)); } catch (e) { /* нет места */ }
      };
      fields.forEach((f) => f.addEventListener('input', save));
      form.addEventListener('submit', () => { try { localStorage.removeItem(key); } catch (e) { /* ничего */ } });
    });
    document.querySelectorAll('[data-back]').forEach((b) => b.addEventListener('click', () => history.back()));
  }

  function initFormulaInputs() {
    document.querySelectorAll('[data-formula]').forEach((field) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn btn-small btn-ghost formula-open';
      b.textContent = '⚗️ Формула';
      b.title = 'Вставить химическую формулу с индексами и зарядами';
      b.addEventListener('click', () => openFormulaEditor(field));
      field.insertAdjacentElement('afterend', b);
    });
  }

  // ------------------------------------------------------------------ доска «от руки»: рисунок → картинка в поле файлов
  function openDrawPad(onDone) {
    const wrap = document.createElement('div');
    wrap.className = 'cq-modal';
    const card = document.createElement('div');
    card.className = 'cq-modal-card draw-card';
    card.innerHTML = '<div class="row between"><h3>✏️ От руки</h3><small class="muted">мышь, палец или стилус</small>' +
      '<button type="button" class="cq-modal-x" data-cancel title="Закрыть" aria-label="Закрыть">✕</button></div>' +
      '<div class="row draw-tools"></div><canvas class="draw-canvas"></canvas>' +
      '<div class="row"><button type="button" class="btn" data-ok>Прикрепить</button>' +
      '<button type="button" class="btn btn-ghost" data-cancel>Отмена</button></div>';
    wrap.append(card);
    document.body.append(wrap);
    const canvas = card.querySelector('canvas');
    const ctx = canvas.getContext('2d');
    // холст влезает в окно и по ширине, и по высоте: кнопки внизу не уходят под панель задач
    const avail = Math.max(180, window.innerHeight - 250);
    let W = Math.min(900, window.innerWidth - 64), H = Math.round(W * 0.66);
    if (H > avail) { H = avail; W = Math.min(W, Math.round(H / 0.5)); }
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    ctx.scale(dpr, dpr);
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, W, H);
    ctx.lineCap = ctx.lineJoin = 'round';
    let color = '#1d1838', width = 2.5, eraser = false;
    const history = [];
    const snapshot = () => { history.push(ctx.getImageData(0, 0, canvas.width, canvas.height)); if (history.length > 30) history.shift(); };
    const tools = card.querySelector('.draw-tools');
    const tool = (label, title, fn) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'formula-key';
      b.textContent = label;
      b.title = title;
      b.addEventListener('click', () => { fn(b); });
      tools.append(b);
      return b;
    };
    const mark = (b) => { tools.querySelectorAll('.formula-key').forEach((x) => x.classList.remove('on')); b.classList.add('on'); };
    [['⚫', '#1d1838'], ['🔵', '#1f5fd6'], ['🔴', '#d6332f'], ['🟢', '#14915a']].forEach(([l, c], i) => {
      const b = tool(l, 'Цвет', (bb) => { color = c; eraser = false; mark(bb); });
      if (!i) b.classList.add('on');
    });
    tool('✏️ тонко', 'Тонкая линия', () => { width = 2.5; eraser = false; });
    tool('🖍 толсто', 'Толстая линия', () => { width = 6; eraser = false; });
    tool('🧽 ластик', 'Ластик', (b) => { eraser = true; mark(b); });
    tool('↶', 'Отменить', () => { const h = history.pop(); if (h) ctx.putImageData(h, 0, 0); });
    tool('🗑', 'Очистить', () => { snapshot(); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, W, H); });
    let drawing = false, lastPt = null, drawn = false;
    const pos = (e) => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    canvas.addEventListener('pointerdown', (e) => {
      drawing = true; snapshot(); lastPt = pos(e); canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener('pointermove', (e) => {
      if (!drawing) return;
      const p = pos(e);
      ctx.strokeStyle = eraser ? '#fff' : color;
      ctx.lineWidth = eraser ? 18 : width * (e.pressure && e.pointerType === 'pen' ? 0.6 + e.pressure : 1);
      ctx.beginPath();
      ctx.moveTo(lastPt[0], lastPt[1]);
      ctx.lineTo(p[0], p[1]);
      ctx.stroke();
      lastPt = p;
      drawn = true;
    });
    const stop = () => { drawing = false; };
    canvas.addEventListener('pointerup', stop);
    canvas.addEventListener('pointercancel', stop);
    const close = () => wrap.remove();
    card.querySelectorAll('[data-cancel]').forEach((b) => b.addEventListener('click', close));
    card.querySelector('[data-ok]').addEventListener('click', () => {
      if (!drawn) { close(); return; }
      canvas.toBlob((blob) => { onDone(blob); close(); }, 'image/png');
    });
  }

  function initDrawPads() {
    document.querySelectorAll('input[type=file][data-drawpad]').forEach((input) => {
      const list = document.createElement('div');
      list.className = 'draw-list small muted';
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn btn-small btn-ghost';
      b.textContent = '✏️ Нарисовать от руки';
      input.insertAdjacentElement('afterend', list);
      input.insertAdjacentElement('afterend', b);
      const show = () => {
        list.textContent = input.files.length ? 'Прикреплено: ' + Array.from(input.files).map((f) => f.name).join(', ') : '';
      };
      const drawings = [];   // рисунки помним отдельно: выбор фото в окне файлов заменяет input.files целиком
      const merge = () => {
        const dt = new DataTransfer();
        const picked = Array.from(input.files).filter((f) => !drawings.includes(f));
        picked.concat(drawings).forEach((f) => dt.items.add(f));
        input.files = dt.files;
      };
      input.addEventListener('change', () => { merge(); show(); });
      b.addEventListener('click', () => openDrawPad((blob) => {
        drawings.push(new File([blob], 'рисунок-' + (drawings.length + 1) + '.png', { type: 'image/png' }));
        merge();
        show();
      }));
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    initCommon(); initHeroes(); initTask(); initDaily(); initTrainer(); initPlayground(); initHomework(); initProjectForm(); initCheck(); initRu(); initRobot(); initBots(); initChemTask(); initPeriodicTable(); initFormulaTips(); initFormulaInputs(); initDrafts(); initDrawPads();
  });
})();
