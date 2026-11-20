/* Web Worker: Python (Pyodide) отдельно от страницы, чтобы бесконечный цикл не вешал вкладку.
 * Ввод (input) — через SharedArrayBuffer: воркер засыпает, пока страница не пришлёт строку.
 * Если страница не изолирована (нет SharedArrayBuffer), ввод берётся из заранее заданных строк. */
const BASE = '/static/vendor/pyodide/';
let pyodide = null;
let ctrl = null;       // Int32Array: [0] состояние, [1] длина
let data = null;       // Uint8Array с текстом ввода
let fallbackStdin = [];
const decoder = new TextDecoder();

function post(msg) { self.postMessage(msg); }

async function init(msg) {
  importScripts(BASE + 'pyodide.js');
  pyodide = await loadPyodide({ indexURL: BASE, stdout: () => {}, stderr: () => {} });
  if (msg.inputBuffer) {
    ctrl = new Int32Array(msg.inputBuffer, 0, 2);
    data = new Uint8Array(msg.inputBuffer, 8);
  }
  if (msg.interruptBuffer) pyodide.setInterruptBuffer(new Uint8Array(msg.interruptBuffer));

  const files = ['turtle.py', 'cq_runtime.py', 'robot.py', 'bots.py'];
  for (const f of files) {
    const text = await (await fetch('/static/py/' + f + '?v=' + msg.version)).text();
    pyodide.FS.writeFile('/home/pyodide/' + f, text);
  }
  pyodide.setStdout({ write: (buf) => { post({ type: 'stdout', text: decoder.decode(buf) }); return buf.length; } });
  pyodide.setStderr({ write: (buf) => { post({ type: 'stderr', text: decoder.decode(buf) }); return buf.length; } });
  pyodide.setStdin({ stdin: readLine, isatty: true });
  self.cqTurtle = (ops) => post({ type: 'turtle', ops: JSON.parse(ops) });
  pyodide.runPython(`
import sys, json
sys.path.insert(0, '/home/pyodide')
sys.modules.pop('turtle', None)
import turtle, cq_runtime, robot, bots
from js import cqTurtle
turtle._emit = lambda ops: cqTurtle(json.dumps(ops))
`);
  // Код ученика не должен ходить в сеть от имени пользователя
  self.fetch = undefined;
  self.XMLHttpRequest = undefined;
  self.importScripts = undefined;
  post({ type: 'ready', interactive: !!ctrl });
}

function readLine() {
  if (!ctrl) {
    if (!fallbackStdin.length) return null;
    return fallbackStdin.shift() + '\n';
  }
  Atomics.store(ctrl, 0, 0);
  post({ type: 'input' });
  Atomics.wait(ctrl, 0, 0);
  const len = ctrl[1];
  if (len < 0) return null;                    // Стоп во время ожидания ввода
  const text = decoder.decode(data.slice(0, len));
  return text + '\n';
}

self.onmessage = async (e) => {
  const msg = e.data;
  try {
    if (msg.type === 'init') {
      await init(msg);
    } else if (msg.type === 'run') {
      fallbackStdin = (msg.stdin || '').split('\n');
      if (fallbackStdin.length && fallbackStdin[fallbackStdin.length - 1] === '') fallbackStdin.pop();
      pyodide.globals.set('_cq_code', msg.code);
      const res = pyodide.runPython('cq_runtime.run(_cq_code)');
      post({ type: 'done', id: msg.id, result: JSON.parse(res) });
    } else if (msg.type === 'check') {
      pyodide.globals.set('_cq_code', msg.code);
      pyodide.globals.set('_cq_tests', JSON.stringify(msg.tests));
      const res = pyodide.runPython('cq_runtime.check(_cq_code, _cq_tests)');
      post({ type: 'checked', id: msg.id, result: JSON.parse(res) });
    } else if (msg.type === 'bots') {
      pyodide.globals.set('_cq_code', msg.code);
      pyodide.globals.set('_cq_boss', msg.boss);
      const res = pyodide.runPython('bots.fight_boss(_cq_code, _cq_boss)');
      post({ type: 'checked', id: msg.id, result: JSON.parse(res) });
    } else if (msg.type === 'robot') {
      pyodide.globals.set('_cq_code', msg.code);
      pyodide.globals.set('_cq_fields', msg.fields);
      const res = pyodide.runPython('robot.run_all(_cq_code, _cq_fields)');
      post({ type: 'checked', id: msg.id, result: JSON.parse(res) });
    }
  } catch (err) {
    post({ type: 'fatal', id: msg.id, error: String(err && err.message || err) });
  }
};
