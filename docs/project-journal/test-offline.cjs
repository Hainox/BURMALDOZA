const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const directory = __dirname;
const seeded = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(directory, 'seed.js'), 'utf8'), seeded);

class Element {
  constructor() {
    this.children = [];
    this.listeners = {};
    this.value = '';
    this.textContent = '';
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
}

const elements = new Map();
const document = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  },
  createElement() { return new Element(); },
  querySelector() { return null; }
};

let online = true;
const response = (value) => ({ ok: true, json: async () => value });
const context = {
  window: { PROJECT_JOURNAL_SEED: seeded.window.PROJECT_JOURNAL_SEED },
  document,
  localStorage: {
    getItem() { throw new Error('Storage denied'); },
    setItem() { throw new Error('Storage denied'); }
  },
  fetch: async (url) => {
    if (!online) throw new Error('Offline');
    if (url.includes('/issues?')) return response([{ number: 99, title: 'Fresh issue', state: 'open', html_url: 'https://github.com/Hainox/BURMALDOZA/issues/99', updated_at: '2026-09-27T01:00:00Z', closed_at: null, labels: [{ name: 'to:codex' }] }]);
    if (url.includes('/pulls?')) return response([]);
    if (url.includes('/commits/main')) return response({ sha: 'a'.repeat(40) });
    throw new Error(`Unexpected URL: ${url}`);
  },
  navigator: {},
  setTimeout,
  clearTimeout,
  AbortController,
  Intl,
  Date,
  console
};

vm.runInNewContext(fs.readFileSync(path.join(directory, 'app.js'), 'utf8'), context);

(async () => {
  const refresh = elements.get('refresh').listeners.click;
  await refresh();
  assert.equal(elements.get('source-label').textContent, 'Данные GitHub API');
  assert.equal(elements.get('metric-issues').textContent, 1);
  const freshTime = elements.get('source-time').textContent;

  online = false;
  await refresh();
  assert.equal(elements.get('source-label').textContent, 'Данные текущей вкладки');
  assert.equal(elements.get('metric-issues').textContent, 1);
  assert.equal(elements.get('source-time').textContent, freshTime);
  assert.match(elements.get('source-detail').textContent, /в памяти текущей вкладки/);
  console.log('offline regression passed: newest in-memory response survives storage denial and network failure');
})().catch((error) => { console.error(error); process.exitCode = 1; });
