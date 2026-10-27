/* Лаборатория ХимЛаба: «Атом изнутри».
 * Электронная конфигурация (порядок заполнения, исключения Cr/Cu и др., ионы, возбуждённое состояние),
 * электронно-графическая формула со спинами, 3D-модель на canvas (орбиты и облака орбиталей), игра «Собери атом».
 * Без внешних библиотек: свой маленький 3D — повороты, перспектива, сортировка по глубине. */
(function () {
  'use strict';
  const root = document.getElementById('lab-atom');
  if (!root) return;

  const ELEMENTS = JSON.parse(document.getElementById('lab-elements').textContent);
  const BY_Z = {};
  ELEMENTS.forEach((e) => { BY_Z[e.z] = e; });

  // ------------------------------------------------------------------ электронные конфигурации
  const ORDER = ['1s', '2s', '2p', '3s', '3p', '4s', '3d', '4p', '5s', '4d', '5p', '6s', '4f', '5d', '6p', '7s', '5f', '6d', '7p'];
  const CAP = { s: 2, p: 6, d: 10, f: 14 };
  const ORBS = { s: 1, p: 3, d: 5, f: 7 };
  const EXCEPT = { 24: { '3d': 5, '4s': 1 }, 29: { '3d': 10, '4s': 1 }, 41: { '4d': 4, '5s': 1 }, 42: { '4d': 5, '5s': 1 },
    44: { '4d': 7, '5s': 1 }, 45: { '4d': 8, '5s': 1 }, 46: { '4d': 10, '5s': 0 }, 47: { '4d': 10, '5s': 1 } };
  const SUP = (n) => String(n).replace(/\d/g, (d) => '⁰¹²³⁴⁵⁶⁷⁸⁹'[d]);
  const n0 = (sub) => +sub[0];
  const lIdx = (sub) => 'spdf'.indexOf(sub[1]);
  const byEnergy = (a, b) => (n0(a) - n0(b)) || (lIdx(a) - lIdx(b));

  function aufbau(electrons) {
    const occ = {};
    let left = electrons;
    for (const sub of ORDER) {
      if (left <= 0) break;
      occ[sub] = Math.min(CAP[sub[1]], left);
      left -= occ[sub];
    }
    return occ;
  }

  /** Основное состояние атома/иона: occ {подуровень: электронов}. */
  function groundState(z, charge) {
    let occ = aufbau(z);
    if (EXCEPT[z]) Object.assign(occ, EXCEPT[z]);
    if (charge > 0) {               // катион: электроны уходят с самого внешнего слоя (4s раньше 3d)
      for (let i = 0; i < charge; i++) {
        const subs = Object.keys(occ).filter((s) => occ[s] > 0).sort((a, b) => (n0(b) - n0(a)) || (lIdx(b) - lIdx(a)));
        if (!subs.length) break;
        occ[subs[0]] -= 1;
      }
    } else if (charge < 0) {        // анион: электроны добавляются по порядку заполнения
      occ = aufbau(z - charge);
    }
    Object.keys(occ).forEach((s) => { if (!occ[s]) delete occ[s]; });
    return occ;
  }

  /** Орбитали подуровня по правилу Хунда: массив из ORBS чисел 0/1/2 (1 — ↑, 2 — ↑↓). */
  function hund(sub, count) {
    const k = ORBS[sub[1]];
    const boxes = new Array(k).fill(0);
    for (let i = 0; i < count; i++) boxes[i % k] += 1;
    return boxes;
  }

  function boxesOf(occ) {
    const res = {};
    Object.keys(occ).forEach((s) => { res[s] = hund(s, occ[s]); });
    return res;
  }

  function outerShell(boxes) {
    return Math.max(...Object.keys(boxes).filter((s) => boxes[s].some((x) => x)).map(n0));
  }

  /** Один шаг возбуждения: распарить электроны внешнего слоя на свободную орбиталь того же слоя.
   *  Возвращает новые клетки или null, если возбуждение невозможно. */
  function exciteStep(boxes, period) {
    const n = outerShell(boxes);
    if (n === 1) return null;                                // у 1-го слоя только 1s: He не возбуждается
    const full = (s) => boxes[s] && boxes[s].every((x) => x === 2);
    if (n === 3 && full('3s') && full('3p')) return null;    // Ar: в школьном курсе валентных состояний нет
    const subs = ['s', 'p'].concat(n >= 3 ? ['d'] : []).map((l) => n + l);
    subs.forEach((s) => { if (!boxes[s]) boxes[s] = new Array(ORBS[s[1]]).fill(0); });
    for (let i = subs.length - 1; i >= 0; i--) {           // источник: пара на самом высоком подуровне
      const src = subs[i];
      const pair = boxes[src].indexOf(2);
      if (pair < 0) continue;
      for (let j = i + 1; j < subs.length; j++) {          // приёмник: пустая орбиталь выше
        const empty = boxes[subs[j]].indexOf(0);
        if (empty >= 0) {
          const nb = JSON.parse(JSON.stringify(boxes));
          nb[src][pair] = 1;
          nb[subs[j]][empty] = 1;
          return nb;
        }
      }
    }
    return null;
  }

  const unpaired = (boxes) => Object.values(boxes).reduce((a, arr) => a + arr.filter((x) => x === 1).length, 0);
  const configText = (boxes) => Object.keys(boxes).sort(byEnergy)
    .filter((s) => boxes[s].reduce((a, b) => a + b, 0) > 0)
    .map((s) => s + SUP(boxes[s].reduce((a, b) => a + b, 0))).join(' ');

  function shells(boxes) {
    const res = [];
    Object.keys(boxes).forEach((s) => {
      const n = n0(s);
      res[n - 1] = (res[n - 1] || 0) + boxes[s].reduce((a, b) => a + b, 0);
    });
    return Array.from(res, (x) => x || 0);
  }

  // ------------------------------------------------------------------ состояние страницы
  const state = { z: +root.dataset.z || 6, charge: 0, excited: 0, boxes: null, view: 'orbits', game: false, guess: {} };

  function recompute() {
    const el = BY_Z[state.z];
    state.boxes = boxesOf(groundState(state.z, state.charge));
    state.canExcite = true;
    state.exciteNote = '';
    for (let i = 0; i < state.excited; i++) {
      const nb = state.charge === 0 && el.main ? exciteStep(state.boxes, el.period) : null;
      if (!nb) { state.excited = i; state.canExcite = false; break; }
      state.boxes = nb;
    }
    if (state.charge === 0 && el.main) {
      state.canExcite = !!exciteStep(JSON.parse(JSON.stringify(state.boxes)), el.period);
      if (!state.canExcite && state.excited === 0) {
        state.exciteNote = el.period === 2
          ? 'Во 2-м периоде нет d-подуровня, а свободных p-орбиталей не осталось — распарить электроны некуда.'
          : (unpaired(state.boxes) === 0 && !Object.keys(state.boxes).some((s) => s.endsWith('p'))
            ? 'Свободных орбиталей на внешнем слое нет.' : 'Все электроны внешнего слоя уже неспаренные или переходить некуда.');
      }
    } else {
      state.canExcite = false;
      state.exciteNote = state.charge !== 0 ? 'Возбуждённое состояние показываем для нейтральных атомов.' :
        'Возбуждение показываем для элементов главных подгрупп.';
    }
  }

  // ------------------------------------------------------------------ электронно-графическая формула
  const diagram = root.querySelector('[data-lab-diagram]');

  function renderDiagram() {
    const subs = Object.keys(state.boxes).sort(byEnergy);
    const groups = {};
    subs.forEach((s) => { (groups[n0(s)] = groups[n0(s)] || []).push(s); });
    diagram.replaceChildren();
    Object.keys(groups).sort((a, b) => b - a).forEach((n) => {   // внешние слои — сверху, как в учебнике
      const row = document.createElement('div');
      row.className = 'eg-row';
      const lab = document.createElement('span');
      lab.className = 'eg-n';
      lab.textContent = n;
      row.append(lab);
      groups[n].forEach((s) => {
        const sub = document.createElement('div');
        sub.className = 'eg-sub eg-' + s[1];
        const cells = document.createElement('div');
        cells.className = 'eg-cells';
        const real = state.boxes[s];
        real.forEach((v, i) => {
          const c = document.createElement('button');
          c.type = 'button';
          c.className = 'eg-cell';
          const shown = state.game ? (state.guess[s] ? state.guess[s][i] : 0) : v;
          c.textContent = shown === 2 ? '↑↓' : (shown === 1 ? '↑' : '');
          if (state.game) {
            c.addEventListener('click', () => {
              state.guess[s] = state.guess[s] || new Array(real.length).fill(0);
              state.guess[s][i] = (state.guess[s][i] + 1) % 3;
              renderDiagram();
            });
            if (state.checked) c.classList.add(shown === v ? 'ok' : 'bad');
          } else {
            c.tabIndex = -1;
          }
          cells.append(c);
        });
        const name = document.createElement('small');
        name.textContent = s;
        sub.append(cells, name);
        row.append(sub);
      });
      diagram.append(row);
    });
  }

  // ------------------------------------------------------------------ 3D
  const canvas = root.querySelector('canvas');
  const ctx = canvas.getContext('2d');
  const cam = { yaw: -0.6, pitch: 0.35, zoom: 1, auto: true };
  let W = 0, H = 0, DPR = 1;

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = canvas.clientWidth;
    H = canvas.clientHeight;
    canvas.width = W * DPR;
    canvas.height = H * DPR;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }

  function project(p) {
    const cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw), cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
    const x1 = p[0] * cy - p[2] * sy, z1 = p[0] * sy + p[2] * cy;
    const y2 = p[1] * cp - z1 * sp, z2 = p[1] * sp + z1 * cp;
    const scale = Math.min(W, H) / 2.6 * cam.zoom;
    const persp = 3.2 / (3.2 + z2);
    return { x: W / 2 + x1 * scale * persp, y: H / 2 - y2 * scale * persp, z: z2, s: scale * persp };
  }

  function sphere(pr, r, c1, c2, alpha) {
    const g = ctx.createRadialGradient(pr.x - r * 0.35, pr.y - r * 0.35, r * 0.1, pr.x, pr.y, r);
    g.addColorStop(0, c1);
    g.addColorStop(1, c2);
    ctx.globalAlpha = alpha == null ? 1 : alpha;
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(pr.x, pr.y, Math.max(0.5, r), 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  // ядро: протоны и нейтроны на «шаре» (для крупных атомов — до 60 частиц, чтобы не тормозило)
  function nucleus(z) {
    const el = BY_Z[z];
    const mRaw = parseFloat(String(el.mass).replace(',', '.').replace(/[\[\]]/g, ''));
    // 35,5 → 35 (Cl-35: 18 нейтронов, как в школьных задачах), иначе — округление
    const mass = (Math.abs(mRaw % 1 - 0.5) < 1e-9 ? Math.floor(mRaw) : Math.round(mRaw)) || z * 2;
    const protons = z, neutrons = Math.max(0, mass - z);
    const total = Math.min(60, protons + neutrons);
    const pShare = protons / (protons + neutrons || 1);
    const pts = [];
    const rad = 0.06 + 0.012 * Math.cbrt(total);
    for (let i = 0; i < total; i++) {
      const t = (i + 0.5) / total, phi = Math.acos(1 - 2 * t), th = Math.PI * (1 + Math.sqrt(5)) * i;
      const r = rad * Math.cbrt((i + 1) / total);
      pts.push({ p: [r * Math.sin(phi) * Math.cos(th), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(th)],
        proton: (i * 37) % total < Math.round(total * pShare) });   // протоны вперемешку с нейтронами
    }
    return { pts, protons, neutrons };
  }

  let nuc = null;
  let t0 = performance.now();

  /** Электроны слоя n по подуровням и спинам — так же, как в клеточках: [{sub, spin, cell}]. */
  function shellElectrons(n) {
    const out = [];
    Object.keys(state.boxes).filter((sub) => n0(sub) === n).sort(byEnergy).forEach((sub) => {
      state.boxes[sub].forEach((v, i) => {
        if (v >= 1) out.push({ sub, spin: '↑', cell: i });
        if (v === 2) out.push({ sub, spin: '↓', cell: i });
      });
    });
    return out;
  }

  const P_AXES = ['px', 'py', 'pz'];
  let targets = [];

  function frame(now) {
    if (cam.auto && !dragging && !hoverTip) cam.yaw += 0.003;
    ctx.clearRect(0, 0, W, H);
    const t = (now - t0) / 1000;
    const items = [];
    const sh = shells(state.boxes);
    const maxN = sh.length;
    const R = (n) => 0.35 + 0.95 * (n / Math.max(maxN, 1));
    if (state.view === 'orbits') {
      // орбиты-кольца, наклонённые по-разному, и электроны на них (↑ — синий, ↓ — оранжевый)
      for (let n = 1; n <= maxN; n++) {
        const tilt = n * 0.9, r = R(n);
        const ring = [];
        for (let k = 0; k <= 64; k++) {
          const a = k / 64 * Math.PI * 2;
          ring.push(project(rot([r * Math.cos(a), 0, r * Math.sin(a)], tilt)));
        }
        const ringLabel = n + '-й электронный слой: ' + sh[n - 1] + ' эл.';
        items.push({ z: 9, hits: ring.filter((_, i) => i % 4 === 0).map((p) => ({ x: p.x, y: p.y, r: 6, label: ringLabel, pr: 0 })),
          draw: () => {
            ctx.strokeStyle = 'rgba(123,47,247,.28)';
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ring.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
            ctx.stroke();
          } });
        const electrons = shellElectrons(n);
        const count = electrons.length;
        electrons.forEach((e, k) => {
          const a = k / count * Math.PI * 2 + t * (1.4 / n);
          const pr = project(rot([r * Math.cos(a), 0, r * Math.sin(a)], tilt));
          const up = e.spin === '↑';
          const rr = Math.max(3, pr.s * 0.045);
          items.push({ z: pr.z, hits: [{ x: pr.x, y: pr.y, r: rr + 3, pr: 2,
            label: 'Электрон ' + e.sub + ' · спин ' + e.spin + (state.boxes[e.sub][e.cell] === 2 ? ' (в паре)' : ' (неспаренный)') }],
          draw: () => {
            sphere(pr, rr, up ? '#9cc4ff' : '#ffc79a', up ? '#2f6fe0' : '#e0701a');
            ctx.fillStyle = '#fff';
            ctx.font = 'bold ' + Math.round(rr * 1.3) + 'px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(e.spin, pr.x, pr.y + 0.5);
          } });
        });
      }
    } else {
      // облака орбиталей внешнего слоя: s — шар, p — гантели по осям, d — четыре лепестка
      const n = outerShell(state.boxes);
      const scale = 0.85;
      const subs = ['s', 'p', 'd'].map((l) => n + l).filter((s) => state.boxes[s]);
      subs.forEach((s) => {
        state.boxes[s].forEach((v, i) => {
          const alpha = v === 2 ? 0.5 : v === 1 ? 0.3 : 0.08;
          const color = s[1] === 's' ? ['#d8f3ff', '#4aa3df'] : s[1] === 'p' ? ['#ffe0f0', '#d14a8b'] : ['#fff2c6', '#d8a21a'];
          const name = s[1] === 'p' ? n + P_AXES[i] : s[1] === 'd' ? n + 'd (' + (i + 1) + '-я)' : s;
          const label = 'Орбиталь ' + name + ': ' + (v === 2 ? '2 электрона ↑↓' : v === 1 ? '1 электрон ↑' : 'пустая');
          lobes(s[1], i).forEach((c) => {
            const pr = project(c.map((x) => x * scale));
            const rr = pr.s * (s[1] === 's' ? 0.32 : 0.2);
            items.push({ z: pr.z, hits: [{ x: pr.x, y: pr.y, r: rr * 0.8, label, pr: 1 }],
              draw: () => sphere(pr, rr, color[0], color[1], alpha) });
          });
        });
      });
    }
    nuc.pts.forEach((q) => {
      const pr = project(q.p);
      const rr = Math.max(2.5, pr.s * 0.03);
      items.push({ z: pr.z, hits: [{ x: pr.x, y: pr.y, r: rr + 2, pr: 3,
        label: (q.proton ? 'Протон (заряд +1)' : 'Нейтрон (заряд 0)') + ' · в ядре ' + nuc.protons + ' p⁺ и ' + nuc.neutrons + ' n⁰' }],
      draw: () => sphere(pr, rr, q.proton ? '#ffb3b3' : '#e6e6ee', q.proton ? '#d33' : '#888') });
    });
    items.sort((a, b) => b.z - a.z);
    targets = [];
    items.forEach((it) => { it.draw(); if (it.hits) targets.push(...it.hits); });
    if (hoverPt) showTip(hoverPt);
    requestAnimationFrame(frame);
  }

  // ------------------------------------------------------------------ подписи при наведении (касании)
  const tipEl = document.createElement('div');
  tipEl.className = 'lab-tip';
  tipEl.hidden = true;
  canvas.parentElement.style.position = 'relative';
  canvas.parentElement.append(tipEl);
  let hoverPt = null, hoverTip = false;

  function showTip(pt) {
    // ближайшая к зрителю цель под курсором: важнее электроны и ядро, чем линия орбиты
    let best = null;
    for (const h of targets) {
      const d = Math.hypot(h.x - pt[0], h.y - pt[1]);
      if (d <= h.r && (!best || h.pr > best.pr || (h.pr === best.pr && d < best.d))) best = Object.assign({ d }, h);
    }
    hoverTip = !!best;
    tipEl.hidden = !best;
    if (best) {
      tipEl.textContent = best.label;
      tipEl.style.left = Math.min(pt[0] + canvas.offsetLeft + 14, canvas.offsetLeft + W - tipEl.offsetWidth - 4) + 'px';
      tipEl.style.top = (pt[1] + canvas.offsetTop + 14) + 'px';
    }
  }

  const localPt = (e) => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  canvas.addEventListener('pointermove', (e) => { if (e.pointerType === 'mouse' && !dragging) hoverPt = localPt(e); });
  canvas.addEventListener('pointerleave', () => { hoverPt = null; hoverTip = false; tipEl.hidden = true; });
  let downAt = null;
  canvas.addEventListener('pointerdown', (e) => { downAt = localPt(e); });
  canvas.addEventListener('pointerup', (e) => {
    if (e.pointerType !== 'mouse' && downAt) {
      const p = localPt(e);
      if (Math.hypot(p[0] - downAt[0], p[1] - downAt[1]) < 8) {     // касание без поворота — показать подпись
        hoverPt = p;
        setTimeout(() => { hoverPt = null; hoverTip = false; tipEl.hidden = true; }, 2500);
      }
    }
  });

  function rot(p, a) {   // наклон орбиты вокруг оси x и z
    const c = Math.cos(a), s = Math.sin(a);
    const y = p[1] * c - p[2] * s, z = p[1] * s + p[2] * c;
    const c2 = Math.cos(a * 0.6), s2 = Math.sin(a * 0.6);
    return [p[0] * c2 - y * s2, p[0] * s2 + y * c2, z];
  }

  function lobes(l, i) {
    const d = 0.55;
    if (l === 's') return [[0, 0, 0]];
    if (l === 'p') {
      const axis = [[1, 0, 0], [0, 1, 0], [0, 0, 1]][i];
      return [axis.map((x) => x * d), axis.map((x) => -x * d), axis.map((x) => x * d * 0.55), axis.map((x) => -x * d * 0.55)];
    }
    const planes = [[[1, 1, 0], [-1, -1, 0], [1, -1, 0], [-1, 1, 0]], [[1, 0, 1], [-1, 0, -1], [1, 0, -1], [-1, 0, 1]],
      [[0, 1, 1], [0, -1, -1], [0, 1, -1], [0, -1, 1]], [[1.2, 0, 0], [-1.2, 0, 0], [0, 1.2, 0], [0, -1.2, 0]],
      [[0, 0, 1.3], [0, 0, -1.3], [0, 0, 0.6], [0, 0, -0.6]]][i];
    return planes.map((v) => v.map((x) => x * d * 0.6));
  }

  let dragging = false, last = null, pinch = null;
  canvas.addEventListener('pointerdown', (e) => { dragging = true; cam.auto = false; last = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', (e) => {
    if (!dragging || !last) return;
    cam.yaw += (e.clientX - last[0]) * 0.01;
    cam.pitch = Math.max(-1.4, Math.min(1.4, cam.pitch + (e.clientY - last[1]) * 0.01));
    last = [e.clientX, e.clientY];
  });
  canvas.addEventListener('pointerup', () => { dragging = false; last = null; });
  canvas.addEventListener('wheel', (e) => { e.preventDefault(); cam.zoom = Math.max(0.5, Math.min(2.5, cam.zoom * (e.deltaY < 0 ? 1.1 : 0.9))); }, { passive: false });
  canvas.addEventListener('touchmove', (e) => {
    if (e.touches.length !== 2) return;
    const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
    if (pinch) cam.zoom = Math.max(0.5, Math.min(2.5, cam.zoom * d / pinch));
    pinch = d;
  }, { passive: true });
  canvas.addEventListener('touchend', () => { pinch = null; });

  // ------------------------------------------------------------------ панель
  const $ = (s) => root.querySelector(s);
  const select = $('[data-lab-el]');
  ELEMENTS.forEach((e) => {
    const o = document.createElement('option');
    o.value = e.z;
    o.textContent = e.z + ' ' + e.sym + ' — ' + e.name;
    select.append(o);
  });

  function info() {
    const el = BY_Z[state.z];
    const electrons = Object.values(state.boxes).reduce((a, arr) => a + arr.reduce((x, y) => x + y, 0), 0);
    const ch = state.charge;
    const ion = ch === 0 ? el.sym : el.sym + (Math.abs(ch) > 1 ? SUP(Math.abs(ch)) : '') + (ch > 0 ? '⁺' : '⁻');
    $('[data-lab-title]').textContent = el.name + (ch ? ' (ион ' + ion + ')' : '') + (state.excited ? ' — возбуждённое состояние' : '');
    $('[data-lab-config]').textContent = state.game ? 'Расставь электроны по клеткам и нажми «Проверить»' : configText(state.boxes);
    const sh = shells(state.boxes);
    $('[data-lab-facts]').textContent = state.game ? '' :
      'Протонов ' + el.z + ' · электронов ' + electrons + ' · по слоям: ' + sh.join(', ') +
      ' · неспаренных электронов: ' + unpaired(state.boxes);
    $('[data-lab-charge-val]').textContent = ch > 0 ? '+' + ch : ch;
    const ex = $('[data-lab-excite]');
    ex.disabled = state.game || !state.canExcite;
    $('[data-lab-ground]').disabled = state.excited === 0;
    $('[data-lab-note]').textContent = state.excited
      ? 'Возбуждение: электрон с парной орбитали перешёл на свободную того же слоя — неспаренных стало ' + unpaired(state.boxes) + ', значит, возможна валентность ' + unpaired(state.boxes) + '.'
      : state.exciteNote;
  }

  function update() {
    recompute();
    nuc = nucleus(state.z);
    select.value = state.z;
    renderDiagram();
    info();
    try { history.replaceState(null, '', '?z=' + state.z); } catch (e) { /* без адреса */ }
  }

  select.addEventListener('change', () => { state.z = +select.value; state.charge = 0; state.excited = 0; state.checked = false; state.guess = {}; update(); });
  $('[data-lab-prev]').addEventListener('click', () => { if (state.z > 1) { state.z--; state.charge = 0; state.excited = 0; state.guess = {}; state.checked = false; update(); } });
  $('[data-lab-next]').addEventListener('click', () => { if (BY_Z[state.z + 1]) { state.z++; state.charge = 0; state.excited = 0; state.guess = {}; state.checked = false; update(); } });
  $('[data-lab-charge-minus]').addEventListener('click', () => { if (state.charge > -3) { state.charge--; state.excited = 0; update(); } });
  $('[data-lab-charge-plus]').addEventListener('click', () => { if (state.charge < 3 && state.charge < state.z) { state.charge++; state.excited = 0; update(); } });
  $('[data-lab-excite]').addEventListener('click', () => { state.excited++; update(); });
  $('[data-lab-ground]').addEventListener('click', () => { state.excited = 0; update(); });
  root.querySelectorAll('[data-lab-view]').forEach((b) => b.addEventListener('click', () => {
    state.view = b.dataset.labView;
    root.querySelectorAll('[data-lab-view]').forEach((x) => x.classList.toggle('btn-ghost', x !== b));
    root.querySelectorAll('[data-legend]').forEach((x) => { x.hidden = x.dataset.legend !== state.view; });
  }));

  // игра «Собери атом»
  const gameBtn = $('[data-lab-game]');
  const checkBtn = $('[data-lab-check]');
  const gameMsg = $('[data-lab-game-msg]');
  gameBtn.addEventListener('click', () => {
    state.game = !state.game;
    state.checked = false;
    state.guess = {};
    state.charge = 0;
    state.excited = 0;
    gameBtn.textContent = state.game ? '✖ Выйти из игры' : '🎮 Собери атом';
    checkBtn.hidden = !state.game;
    gameMsg.textContent = state.game ? 'Нажимай на клетки: пусто → ↑ → ↑↓. Помни: по Хунду сначала по одному электрону в каждую орбиталь подуровня.' : '';
    update();
  });
  checkBtn.addEventListener('click', async () => {
    state.checked = true;
    let ok = true;
    Object.keys(state.boxes).forEach((s) => {
      const g = state.guess[s] || new Array(state.boxes[s].length).fill(0);
      // порядок клеток внутри подуровня не важен — сравниваем количество ↑ и ↑↓
      const norm = (a) => a.slice().sort().join('');
      if (norm(g) !== norm(state.boxes[s])) ok = false;
    });
    renderDiagram();
    gameMsg.textContent = ok ? '🎉 Верно! Это ' + BY_Z[state.z].name + ': ' + configText(state.boxes) :
      '😕 Есть ошибки (красные клетки). Проверь число электронов, порядок заполнения и правило Хунда.';
    if (ok && window.CQ && document.querySelector('meta[name="csrf"]')) {
      try { CQ.handleNotices(await CQ.api('/api/chem/lab/atom', { z: state.z })); } catch (e) { /* без сети */ }
    }
  });

  window.addEventListener('resize', resize);
  resize();
  update();
  requestAnimationFrame(frame);
})();
