// Путь нового человека на стенде umedu: лендинг → регистрация → экзамен → самооценка →
// 3 задания → прогресс → ссылка родителю → вход родителя → выход.
// Ширины 375 и 1280, светлая и тёмная тема. Падает на ошибке в консоли и на нарушении CSP.
// Запуск: bash tests/e2e/run_umedu.sh   (в обычный pytest этот файл не входит)
const fs = require('fs');
const { chromium } = require('playwright-core');

const BASE = process.argv[2] || 'http://localhost:8098';
const SHOTS = process.argv[3] || '/tmp/umedu-e2e-shots';
fs.mkdirSync(SHOTS, { recursive: true });

const problems = [];
function check(cond, msg) {
  if (!cond) problems.push('FAIL: ' + msg);
  else console.log('  ✓ ' + msg);
}

function track(page) {
  page.on('console', (m) => {
    if (m.type() === 'error') problems.push(`console: ${m.text()} @ ${page.url()}`);
  });
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message} @ ${page.url()}`));
  page.on('response', (r) => {
    const type = r.request().resourceType();
    if (type !== 'document' || r.status() >= 400) return;
    const csp = r.headers()['content-security-policy'] || '';
    if (!csp.includes("script-src 'self'")) problems.push('нет script-src self: ' + r.url());
    const robots = r.headers()['x-robots-tag'] || '';
    if (!robots.includes('noindex')) problems.push('нет noindex: ' + r.url());
  });
}

async function noOverflow(page) {
  return page.evaluate(() => {
    const el = document.scrollingElement || document.documentElement;
    const before = el.scrollLeft;
    el.scrollLeft = 2000;
    const moved = el.scrollLeft > 1;
    el.scrollLeft = before;
    return !moved;
  });
}

async function shot(page, name) {
  await page.screenshot({ path: SHOTS + '/' + name + '.png', fullPage: true });
}

async function solveThree(page) {
  for (let i = 0; i < 3; i++) {
    await page.goto(BASE + '/u2/today');
    await page.locator('a[href*="/u2/train/"]').first().click();
    await page.waitForURL(/\/u2\/train\//);
    const scores = page.locator('[data-qa="score"]');
    const n = await scores.count();
    check(n > 0, 'задание ' + (i + 1) + ' с самопроверкой');
    await scores.nth(n - 1).click();
    await page.getByRole('heading', { name: /Записано/ }).waitFor();
  }
}

async function journey(browser) {
  const stamp = Date.now().toString(36);
  const login = 'e2e' + stamp.slice(-6);
  const parentLogin = 'par' + stamp.slice(-6);
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, colorScheme: 'light' });
  await ctx.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (e) => {
      console.error('CSP ' + e.violatedDirective + ' ' + e.blockedURI);
    });
  });
  const page = await ctx.newPage();
  track(page);

  await page.goto(BASE + '/welcome');
  await page.locator('[data-qa="stage-banner"]').waitFor();
  check(await noOverflow(page), 'лендинг 1280 без горизонтальной прокрутки');
  await shot(page, 'welcome-1280-light');
  await page.locator('[data-qa="start"]').click();
  await page.waitForURL(/\/join/);
  const form = page.locator('[data-qa="join"]');
  await form.locator('input[name="name"]').fill('Аня');
  await form.locator('input[name="grade"][value="9"]').check();
  await form.locator('input[name="login"]').fill(login);
  await form.locator('input[name="password"]').fill('uchenik-demo');
  await form.locator('input[name="age14"]').check();
  await form.locator('input[name="consent"]').check();
  await form.locator('button').click();
  await page.waitForURL(/\/$/);
  check(true, 'регистрация, вход выполнен');

  await page.locator('[data-qa="exam-prep"]').click();
  await page.waitForURL(/\/u2\/start/);
  const pick = page.locator('[data-qa="pick-exam"][data-exam-id="oge-rus-2026"]');
  await pick.locator('button').click();
  await page.waitForURL(/\/u2\/diag\//);
  const sections = page.locator('[data-qa="diag"] fieldset');
  const count = await sections.count();
  check(count > 0, 'самооценка: есть разделы');
  for (let i = 0; i < count; i++) await sections.nth(i).locator('input[value="2"]').check();
  await page.locator('[data-qa="diag"] button').click();
  await page.waitForURL(/\/u2\/today/);
  check(true, 'экзамен выбран, самооценка сохранена');

  await solveThree(page);
  await page.locator('[data-qa="tab-progress"]').click();
  await page.waitForURL(/\/u2\/progress/);
  const progress = await page.locator('body').innerText();
  const attempts = progress.match(/попыток:\s*(\d+)/);
  check(attempts && Number(attempts[1]) >= 3, 'прогресс показывает попытки: ' + (attempts && attempts[1]));
  await shot(page, 'progress-1280-light');

  await page.goto(BASE + '/');
  await page.locator('[data-qa="for-parents"]').click();
  await page.locator('[data-qa="parent-link"]').click();
  await page.locator('[data-qa="parent-url"]').waitFor();
  const parentUrl = await page.locator('[data-qa="parent-url"]').inputValue();
  check(parentUrl.includes('/parent/'), 'ссылка для родителя');

  const parentCtx = await browser.newContext({ viewport: { width: 1280, height: 800 }, colorScheme: 'light' });
  await parentCtx.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (e) => {
      console.error('CSP ' + e.violatedDirective + ' ' + e.blockedURI);
    });
  });
  const parent = await parentCtx.newPage();
  track(parent);
  await parent.goto(parentUrl);
  await parent.locator('[data-qa="parent-account"]').click();
  const join = parent.locator('[data-qa="parent-join"]');
  await join.locator('input[name="name"]').fill('Родитель Ани');
  await join.locator('input[name="login"]').fill(parentLogin);
  await join.locator('input[name="password"]').fill('roditel-demo');
  await join.locator('input[name="consent"]').check();
  await join.locator('button').click();
  await parent.waitForURL(/\/family$/);
  check((await parent.locator('body').innerText()).includes('Аня'), 'родитель видит ребёнка');
  await parent.locator('[data-qa="logout"]').click();
  await parent.waitForURL(/\/family\/login/);
  const loginForm = parent.locator('[data-qa="parent-login"]');
  await loginForm.locator('input[name="username"]').fill(parentLogin);
  await loginForm.locator('input[name="password"]').fill('roditel-demo');
  await loginForm.locator('button').click();
  await parent.waitForURL(/\/family$/);
  check(true, 'повторный вход родителя');
  await parent.locator('[data-qa="logout"]').click();
  await parent.waitForURL(/\/family\/login/);
  check(true, 'выход родителя');

  await ctx.storageState({ path: SHOTS + '/student.json' });
  await parentCtx.storageState({ path: SHOTS + '/parent.json' });
  await ctx.close();
  await parentCtx.close();
}

async function look(browser, spec) {
  const ctx = await browser.newContext({
    viewport: spec.viewport,
    colorScheme: spec.scheme,
    storageState: SHOTS + '/student.json',
  });
  await ctx.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (e) => {
      console.error('CSP ' + e.violatedDirective + ' ' + e.blockedURI);
    });
  });
  const page = await ctx.newPage();
  track(page);
  await page.goto(BASE + '/welcome');
  await page.locator('[data-qa="stage-banner"]').waitFor();
  check(await noOverflow(page), 'лендинг ' + spec.name + ' без горизонтальной прокрутки');
  if (spec.shot) await shot(page, 'welcome-' + spec.name);

  await page.goto(BASE + '/u2/today');
  check(await noOverflow(page), 'сегодня ' + spec.name + ' без горизонтальной прокрутки');
  await page.goto(BASE + '/u2/me');
  await page.locator('[data-theme-set="' + spec.theme + '"]').click();
  const theme = await page.evaluate(() => document.documentElement.getAttribute('data-theme') || '');
  check(theme === spec.theme, 'тема ' + spec.name + ' = ' + (theme || 'система'));
  await page.goto(BASE + '/u2/progress');
  check(await noOverflow(page), 'прогресс ' + spec.name + ' без горизонтальной прокрутки');
  if (spec.shot) await shot(page, 'progress-' + spec.name);
  await ctx.close();

  const pctx = await browser.newContext({
    viewport: spec.viewport,
    colorScheme: spec.scheme,
    storageState: SHOTS + '/parent.json',
  });
  const parent = await pctx.newPage();
  track(parent);
  await parent.goto(BASE + '/family/login');
  check(await noOverflow(parent), 'вход родителя ' + spec.name + ' без горизонтальной прокрутки');
  await pctx.close();
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME || '/usr/local/bin/google-chrome',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  await journey(browser);
  const views = [
    { name: '375-light', viewport: { width: 375, height: 812 }, scheme: 'light', theme: 'light', shot: true },
    { name: '1280-dark', viewport: { width: 1280, height: 800 }, scheme: 'dark', theme: 'dark', shot: true },
    { name: '375-dark', viewport: { width: 375, height: 812 }, scheme: 'dark', theme: 'dark', shot: false },
  ];
  for (const spec of views) await look(browser, spec);
  await browser.close();
  console.log('\n' + (problems.length ? 'ПРОБЛЕМЫ:\n' + problems.join('\n') : 'Всё чисто'));
  process.exit(problems.length ? 1 : 0);
})().catch((e) => {
  console.error(e);
  console.log(problems.join('\n'));
  process.exit(2);
});
