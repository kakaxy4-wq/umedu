// Браузерный прогон КодКвеста: node tests/e2e.js [baseURL] [скриншоты]
// Нужен запущенный сервер с аккаунтами student/teacher (пароль secret123) и скачанным vendor.
const { chromium } = require('playwright');

const BASE = process.argv[2] || 'http://localhost:8095';
const SHOTS = process.argv[3] || '/tmp/cq-shots';
const fs = require('fs');
fs.mkdirSync(SHOTS, { recursive: true });

const problems = [];
function track(page, who) {
  page.on('console', (m) => { if (m.type() === 'error') problems.push(`[${who}] console: ${m.text()} @ ${page.url()}`); });
  page.on('pageerror', (e) => problems.push(`[${who}] pageerror: ${e.message} @ ${page.url()}`));
  page.on('response', (r) => { if (r.status() >= 500) problems.push(`[${who}] HTTP ${r.status()} ${r.url()}`); });
}

async function login(ctx, user) {
  const page = await ctx.newPage();
  track(page, user);
  await page.goto(BASE + '/login');
  await page.fill('input[name=username]', user);
  await page.fill('input[name=password]', 'secret123');
  await Promise.all([page.waitForNavigation(), page.click('button')]);
  return page;
}

function check(cond, msg) { if (!cond) problems.push('FAIL: ' + msg); else console.log('  ✓ ' + msg); }

async function setCode(page, box, code) {
  await page.evaluate(([sel, c]) => document.querySelector(sel).codebox.setCode(c), [box, code]);
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
  const viewports = { desktop: { width: 1366, height: 900 }, mobile: { width: 390, height: 844 } };

  // ---------------- учитель открывает уроки
  const tctx = await browser.newContext({ viewport: viewports.desktop });
  const tp = await login(tctx, 'teacher');
  check(tp.url().endsWith('/teacher'), 'teacher lands on /teacher');
  for (const n of [1, 2, 3, 4]) {
    await tp.goto(BASE + '/teacher/lessons');
    const open = tp.locator(`#l${n} form[action$="/open"] button`);
    if (await open.count()) await Promise.all([tp.waitForNavigation(), open.click()]);
  }
  await tp.goto(BASE + '/teacher/lessons');
  await Promise.all([tp.waitForNavigation(), tp.locator('#l1 form[action$="/done"] button').click()]);
  check(await tp.locator('#l1').innerText().then((t) => t.includes('✅')), 'lesson 1 marked done');

  // ---------------- ученик
  const sctx = await browser.newContext({ viewport: viewports.desktop });
  const sp = await login(sctx, 'student');
  check(sp.url() === BASE + '/', 'student lands on home');
  check(await sp.locator('.toast').count() > 0, 'notices shown as toasts on home');
  await sp.screenshot({ path: SHOTS + '/01-home.png', fullPage: true });

  // запуск кода с input()
  await sp.goto(BASE + '/lesson/1');
  check(await sp.locator('.CodeMirror').count() >= 2, 'CodeMirror editors on lesson page');
  const box2 = '.example:nth-of-type(2) .codebox';
  await sp.locator(box2 + ' .btn-run').click();
  await sp.locator(box2 + ' .cb-input input').waitFor({ timeout: 60000 });
  await sp.locator(box2 + ' .cb-input input').fill('Миша');
  await sp.keyboard.press('Enter');
  await sp.locator(box2 + ' .cb-input input').waitFor({ state: 'visible', timeout: 10000 });
  await sp.locator(box2 + ' .cb-input input').fill('13');
  await sp.keyboard.press('Enter');
  await sp.waitForFunction((s) => document.querySelector(s + ' .cb-status').textContent.includes('Готово'), box2, { timeout: 10000 });
  const out = await sp.locator(box2 + ' .cb-out').innerText();
  check(out.includes('Привет, Миша!') && out.includes('37'), 'interactive input() works: ' + JSON.stringify(out));
  await sp.screenshot({ path: SHOTS + '/02-lesson-run.png', fullPage: true });

  // ошибка по-русски
  await setCode(sp, box2, 'prnt("hi")');
  await sp.locator(box2 + ' .btn-run').click();
  await sp.locator(box2 + ' .cb-error').waitFor({ timeout: 10000 });
  check((await sp.locator(box2 + ' .cb-error').innerText()).includes("print"), 'friendly NameError hint');

  // бесконечный цикл и стоп
  await setCode(sp, box2, 'while True:\n    pass');
  await sp.locator(box2 + ' .btn-run').click();
  await sp.waitForTimeout(800);
  await sp.locator(box2 + ' .btn-stop').click();
  await sp.locator(box2 + ' .cb-error').waitFor({ timeout: 8000 });
  check((await sp.locator(box2 + ' .cb-error').innerText()).includes('KeyboardInterrupt'), 'stop button interrupts infinite loop');
  await setCode(sp, box2, 'print(1+1)');
  await sp.locator(box2 + ' .btn-run').click();
  await sp.waitForFunction((s) => document.querySelector(s + ' .cb-out').textContent.trim() === '2', box2, { timeout: 10000 });
  check(true, 'runner works again after stop');

  // задача: сначала неверно, потом верно
  await sp.goto(BASE + '/task/greet');
  await setCode(sp, '.codebox', 'name = input()\nprint("Привет " + name)');
  await sp.locator('.btn-check').click();
  await sp.locator('.cb-results').waitFor({ timeout: 60000 });
  check((await sp.locator('.cb-results-head').innerText()).includes('Пока не всё'), 'wrong solution rejected');
  await setCode(sp, '.codebox', 'name = input()\nprint("Привет, " + name + "!")');
  await sp.locator('.btn-check').click();
  await sp.waitForFunction(() => document.querySelector('.cb-results-head').textContent.includes('Все тесты'), null, { timeout: 15000 });
  await sp.locator('#solution:not([hidden])').waitFor({ timeout: 5000 });
  check(true, 'correct solution accepted, solution revealed');
  await sp.waitForTimeout(1200);
  await sp.screenshot({ path: SHOTS + '/03-task-solved.png', fullPage: true });

  // черепашка
  await sp.goto(BASE + '/task/t_square');
  await setCode(sp, '.codebox', 'import turtle\nt = turtle.Turtle()\nt.shape("turtle")\nfor _ in range(4):\n    t.forward(100)\n    t.left(90)');
  await sp.locator('.btn-run').click();
  await sp.locator('.cb-turtle canvas').first().waitFor({ timeout: 60000 });
  await sp.waitForTimeout(2500);
  const px = await sp.evaluate(() => {
    const c = document.querySelector('.cb-turtle canvas');
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
    return n;
  });
  check(px > 500, 'turtle drew on canvas (' + px + ' px)');
  await sp.locator('.btn-check').click();
  await sp.waitForFunction(() => document.querySelector('.cb-results-head') && document.querySelector('.cb-results-head').textContent.includes('Все тесты'), null, { timeout: 15000 });
  check(true, 'turtle task auto-checked');
  await sp.screenshot({ path: SHOTS + '/04-turtle.png', fullPage: true });

  // задача дня
  await sp.goto(BASE + '/daily');
  if (await sp.locator('#daily-form').count()) {
    await sp.fill('#daily-form textarea', 'не знаю');
    await sp.click('#daily-form button');
    await sp.locator('#daily-result').waitFor();
    await sp.fill('#daily-form textarea', 'тоже не знаю');
    await sp.click('#daily-form button');
    await sp.locator('#daily-reveal:not([hidden])').waitFor({ timeout: 5000 });
    check(true, 'daily quiz: 2 attempts then answer revealed');
    await sp.waitForTimeout(500);
    check((await sp.locator('#daily-reveal .CodeMirror-code').innerText()).trim().length > 5, 'revealed editor shows code');
  }
  await sp.screenshot({ path: SHOTS + '/05-daily.png', fullPage: true });

  // арена (ускоряем время)
  await sp.goto(BASE + '/trainer');
  await sp.evaluate(() => { const real = Date.now; let off = 0; Date.now = () => real() + off; window.__skip = (s) => { off += s * 1000; }; });
  await sp.click('[data-mode="table"]');
  for (let i = 0; i < 6; i++) {
    const q = await sp.locator('.tr-q').innerText();
    const m = q.match(/(\d+) × (\d+)/);
    await sp.fill('.tr-input', String(m[1] * m[2]));
    await sp.keyboard.press('Enter');
  }
  check((await sp.locator('.tr-score').innerText()) === '6', 'arena counts correct answers');
  check(Number(await sp.locator('.tr-points').innerText()) >= 12, 'arena basketball points');
  await sp.screenshot({ path: SHOTS + '/06-arena-game.png' });
  await sp.evaluate(() => window.__skip(61));
  await sp.locator('.tr-end:not([hidden])').waitFor({ timeout: 5000 });
  await sp.waitForTimeout(800);
  check((await sp.locator('.tr-info').innerText()).includes('+3'), 'arena awards trophies: ' + await sp.locator('.tr-info').innerText());
  await sp.screenshot({ path: SHOTS + '/07-arena-end.png' });

  // песочница: сохранить
  await sp.goto(BASE + '/playground');
  await sp.fill('#snippet-title', 'Тест');
  await sp.click('#save-snippet');
  await sp.waitForURL(/s=\d+/);
  check(true, 'snippet saved');

  // домашка
  await sp.goto(BASE + '/lesson/1');
  await setCode(sp, '#hw-form .codebox', 'print("моя анкета")');
  await sp.fill('#hw-form textarea[name=comment]', 'Сделал!');
  await Promise.all([sp.waitForNavigation(), sp.click('#hw-form button.btn:has-text("Сдать")')]);
  check((await sp.locator('.submission').count()) === 1, 'homework submitted');

  // портфолио
  await sp.goto(BASE + '/portfolio/new');
  await sp.fill('input[name=title]', 'Звёздное небо');
  await sp.fill('textarea[name=description]', 'Моя первая открытка');
  await setCode(sp, '#project-form .codebox', 'import turtle\nturtle.bgcolor("navy")\nt = turtle.Turtle()\nt.color("gold")\nt.begin_fill()\nfor _ in range(5):\n    t.forward(100)\n    t.right(144)\nt.end_fill()');
  await sp.check('input[name=public]');
  await Promise.all([sp.waitForNavigation(), sp.click('#project-form button.btn')]);
  const publicHref = await sp.locator('a:has-text("Публичная страница")').getAttribute('href');
  check(!!publicHref, 'public project created');

  // магазин
  await sp.goto(BASE + '/shop');
  await sp.screenshot({ path: SHOTS + '/08-shop.png', fullPage: true });
  await sp.goto(BASE + '/achievements');
  await sp.screenshot({ path: SHOTS + '/09-achievements.png', fullPage: true });
  for (const path of ['/map', '/cheatsheet', '/portfolio']) {
    await sp.goto(BASE + path);
    await sp.screenshot({ path: SHOTS + '/10' + path.replace(/\//g, '-') + '.png', fullPage: true });
  }

  // аноним смотрит публичный проект и запускает его
  const actx = await browser.newContext({ viewport: viewports.mobile });
  const ap = await actx.newPage();
  track(ap, 'anon');
  await ap.goto(BASE + publicHref);
  await ap.locator('.btn-run').click();
  await ap.locator('.cb-turtle canvas').first().waitFor({ timeout: 60000 });
  await ap.waitForTimeout(2500);
  check(true, 'anonymous visitor can run public project');
  await ap.screenshot({ path: SHOTS + '/11-public-mobile.png', fullPage: true });
  const r = await ap.goto(BASE + '/teacher');
  check(ap.url().endsWith('/login'), 'anonymous redirected to login');

  // мобильная вёрстка ученика
  const mctx = await browser.newContext({ viewport: viewports.mobile });
  const mp = await login(mctx, 'student');
  await mp.screenshot({ path: SHOTS + '/12-home-mobile.png', fullPage: true });
  const overflow = await mp.evaluate(() => (() => { window.scrollTo(1000, window.scrollY); const x = window.scrollX; window.scrollTo(0, window.scrollY); return x > 0; })());
  check(!overflow, 'no horizontal scroll on mobile home');
  for (const path of ['/lesson/1', '/task/greet', '/trainer', '/achievements', '/map', '/shop', '/cheatsheet', '/playground']) {
    await mp.goto(BASE + path);
    const ov = await mp.evaluate(() => (() => { window.scrollTo(1000, window.scrollY); const x = window.scrollX; window.scrollTo(0, window.scrollY); return x > 0; })());
    check(!ov, 'no horizontal scroll on mobile ' + path);
  }
  await mp.goto(BASE + '/lesson/1');
  await mp.screenshot({ path: SHOTS + '/13-lesson-mobile.png', fullPage: true });
  await mp.click('.nav-toggle');
  await mp.screenshot({ path: SHOTS + '/14-nav-mobile.png' });

  // тёмная тема
  const dctx = await browser.newContext({ viewport: viewports.desktop, colorScheme: 'dark' });
  const dp = await login(dctx, 'student');
  await dp.screenshot({ path: SHOTS + '/18-home-dark.png', fullPage: true });
  await dp.goto(BASE + '/lesson/3');
  await dp.screenshot({ path: SHOTS + '/19-lesson-dark.png', fullPage: true });

  // ---------------- учитель проверяет домашку
  await tp.goto(BASE + '/teacher/reviews');
  await tp.fill('textarea[name=comment]', 'Отлично!');
  await Promise.all([tp.waitForNavigation(), tp.click('button[value=approve]')]);
  check((await tp.locator('.center-card').count()) === 1, 'homework approved');
  await tp.goto(BASE + '/teacher');
  await tp.screenshot({ path: SHOTS + '/15-teacher.png', fullPage: true });
  await tp.goto(BASE + '/lesson/2');
  await tp.screenshot({ path: SHOTS + '/16-teacher-lesson.png', fullPage: true });
  for (const path of ['/teacher/lessons', '/teacher/solutions', '/teacher/attempts/greet', '/teacher/rewards', '/teacher/journal', '/gallery']) {
    await tp.goto(BASE + path);
  }
  await tp.screenshot({ path: SHOTS + '/17-teacher-rewards.png', fullPage: true });

  await browser.close();
  console.log('\n' + (problems.length ? 'ПРОБЛЕМЫ:\n' + problems.join('\n') : 'Всё чисто ✅'));
  process.exit(problems.length ? 1 : 0);
})().catch((e) => { console.error(e); console.log(problems.join('\n')); process.exit(2); });
