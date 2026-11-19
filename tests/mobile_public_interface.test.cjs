const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/js/app-movel.js'), 'utf8');
const tick = () => new Promise(setImmediate);

async function mobile(hash = '', queued = []) {
  const listeners = new Map(), requests = [], rows = structuredClone(queued);
  const element = () => ({innerHTML: '', hidden: true, textContent: '', dataset: {},
    addEventListener() {}, querySelector: () => element(), querySelectorAll: () => []});
  const app = element(); app.dataset.vigilanciaEnabled = 'false';
  const config = {prefeituras: [{id: 1, nome: 'Município Exemplo'}], catalogo: {}};
  const stored = new Map(Object.entries({config, prefeitura_id: 1, agente_token: 'cached-token',
    agente_usuario: {id: 5, tipo: 'agente_endemias'}, device_id: 'test-device'})
    .map(([key, value]) => [key, JSON.stringify(value)]));
  const on = (name, handler) => listeners.set(name, [...(listeners.get(name) || []), handler]);
  const off = (name, handler) => listeners.set(name, (listeners.get(name) || []).filter(fn => fn !== handler));
  const db = {close() {}, transaction() {
    const tx = {objectStore: () => ({getAll: () => ({result: structuredClone(rows)}), put(item) {
      const index = rows.findIndex(row => row.id === item.id);
      if (index < 0) rows.push(structuredClone(item)); else rows[index] = structuredClone(item);
      return {};
    }})};
    queueMicrotask(() => tx.oncomplete?.()); return tx;
  }};
  const indexedDB = {open() {
    const request = {result: db}; queueMicrotask(() => request.onsuccess?.()); return request;
  }};
  const location = {hash};
  const document = {getElementById: id => id === 'app' ? app : element(), querySelector: () => null,
    addEventListener: on, removeEventListener: off,
    dispatchEvent: event => (listeners.get(event.type) || []).slice().forEach(fn => fn(event))};
  const context = {document, location, indexedDB, FormData, AbortSignal, URL, console,
    setTimeout, clearTimeout, setInterval, clearInterval,
    crypto: {randomUUID: () => 'test-uuid'},
    CustomEvent: class {constructor(type) {this.type = type;}},
    localStorage: {getItem: key => stored.get(key) ?? null, setItem: (key, value) => stored.set(key, value), removeItem: key => stored.delete(key)},
    navigator: {onLine: true, serviceWorker: {register: async () => ({})}},
    window: {indexedDB, location, scrollTo() {}, addEventListener: on, removeEventListener: off},
    fetch: async (url, options = {}) => {
      requests.push({url, method: options.method || 'GET'});
      return {ok: true, json: async () => url === '/api/mobile/config' ? config : {protocolo: 'DEMO-001'}};
    }};
  vm.runInNewContext(source, context);
  await tick(); await tick();
  return {app, requests, rows};
}

for (const hash of ['', '#agente', '#agente/visita/0', '#caso-suspeito']) {
  test(`mobile retains citizen features and blocks retired hash ${hash || '(home)'}`, async () => {
    const page = await mobile(hash);
    for (const card of ['relatar-foco', 'alertas', 'chat']) assert.match(page.app.innerHTML, new RegExp(`data-card="${card}"`));
    assert.match(page.app.innerHTML, /\/portal-cidadao\/boletim-dengue/);
    assert.doesNotMatch(page.app.innerHTML, /data-card="(?:agente|caso-suspeito)"/);
    assert.ok(page.requests.every(call => !/\/agente|\/relato-saude|\/mobile\/me/.test(call.url)));
  });
}

test('offline queue sends citizen reports and preserves archived visits and health reports', async () => {
  const queued = ['foco', 'visita', 'caso'].map((kind, index) => ({
    id: String(index), kind, fields: {foco: 'Pneu'}, files: [],
    createdAt: '2026-11-18T12:00:00Z', protocolo: null, erro: null,
  }));
  const page = await mobile('#enviados', queued);
  assert.deepEqual(page.requests.filter(call => call.method === 'POST').map(call => call.url), ['/portal-cidadao/denuncias']);
  assert.equal(page.rows.find(row => row.kind === 'foco').protocolo, 'DEMO-001');
  for (const kind of ['visita', 'caso']) {
    assert.deepEqual(page.rows.find(row => row.kind === kind), queued.find(row => row.kind === kind));
  }
  assert.doesNotMatch(page.app.innerHTML, /Caso suspeito:|Visita: imóvel/);
});

test('service worker displays public push and opens the notification destination', async () => {
  const handlers = {}, notifications = [], opened = [], pending = [];
  const worker = fs.readFileSync(path.join(__dirname, '../app/static/sw.js'), 'utf8');
  vm.runInNewContext(worker, {self: {
    addEventListener: (name, fn) => {handlers[name] = fn;},
    registration: {showNotification: async (title, options) => notifications.push({title, options})},
    clients: {matchAll: async () => [], openWindow: async url => opened.push(url)},
  }});
  handlers.push({data: {json: () => ({title: 'Aviso municipal', body: 'Confira as orientações no portal.'})},
    waitUntil: promise => pending.push(promise)});
  await Promise.all(pending);
  assert.equal(notifications[0].title, 'Aviso municipal');
  assert.equal(notifications[0].options.body, 'Confira as orientações no portal.');
  handlers.notificationclick({notification: {close() {}, data: {url: '/portal-cidadao/boletim-dengue'}},
    waitUntil: promise => pending.push(promise)});
  await Promise.all(pending);
  assert.deepEqual(opened, ['/portal-cidadao/boletim-dengue']);
});
