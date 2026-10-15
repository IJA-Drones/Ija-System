const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/ortomosaicos-basemap.js', 'utf8');
function setup({key = 'browser-test-key', fetch = async () => new Response('{}')} = {}) {
  const elements = Object.fromEntries(['basemap', 'basemap-status', 'google-credit', 'basemap-config'].map(id => [id, {
    value: 'satellite', hidden: true, textContent: '', classList: {toggle() {}},
    addEventListener(event, callback) {this[event] = callback;},
  }]));
  elements['basemap-config'].textContent = JSON.stringify({key});
  const created = [];
  class Google {
    constructor(options) {this.options = options;this.state = 'loading';this.listeners = {};created.push(this);}
    on(event, callback) {this.listeners[event] = callback;}
    getState() {return this.state;}
    stateTo(state) {this.state = state;this.listeners.change();}
    dispose() {this.disposed = true;}
  }
  const streets = {kind: 'streets'};
  const base = {source: streets, visible: true, getSource() {return this.source;}, setSource(value) {this.source = value;}, setVisible(value) {this.visible = value;}};
  const context = {window: {}, document: {getElementById: id => elements[id.replace('ortho-', '')]}, ol: {source: {Google}}, fetch, Response, AbortSignal};
  vm.runInNewContext(source, context);context.window.initOrthoBasemap(base);
  return {base, streets, elements, created, change(value) {elements.basemap.value = value;elements.basemap.change();}};
}
test('satellite becomes the background with attribution; streets and none stay selectable', () => {
  const h = setup();const google = h.created[0];
  assert.equal(google.options.mapType, 'satellite');assert.equal(google.options.attributionsCollapsible, false);
  assert.equal(h.base.source, h.streets);
  google.stateTo('ready');assert.equal(h.base.source, google);assert.equal(h.elements['google-credit'].hidden, false);
  h.change('streets');assert.equal(h.base.source, h.streets);assert.equal(h.elements['google-credit'].hidden, true);
  h.change('none');assert.equal(h.base.visible, false);
  h.change('satellite');assert.equal(h.base.source, google);assert.equal(h.base.visible, true);assert.equal(h.created.length, 1);
});
test('no key keeps the streets usable without requests', () => {
  const h = setup({key: ''});assert.equal(h.created.length, 0);assert.equal(h.elements.basemap.value, 'streets');
  assert.match(h.elements['basemap-status'].textContent, /não foi configurado/);
});
test('late session completion cannot override a newer user choice', () => {
  const h = setup();h.change('none');h.created[0].stateTo('ready');
  assert.equal(h.base.visible, false);assert.equal(h.elements['google-credit'].hidden, true);
});
test('authentication error falls back and an explicit retry creates a fresh source', async () => {
  const h = setup({fetch: async () => new Response(JSON.stringify({error: {details: [{reason: 'API_KEY_INVALID'}]}}), {status: 400})});
  const google = h.created[0];await google.fetchSessionToken('https://tile.googleapis.com/v1/createSession', {});google.stateTo('error');
  assert.equal(h.base.source, h.streets);assert.equal(h.elements.basemap.value, 'streets');
  assert.match(h.elements['basemap-status'].textContent, /chave válida/);
  h.change('satellite');assert.equal(google.disposed, true);assert.equal(h.created.length, 2);
});
test('network timeout is handled without leaking the request URL', async () => {
  const h = setup({fetch: async () => {throw Error('https://example.invalid/?key=secret');}});
  const google = h.created[0];const response = await google.fetchSessionToken('unused', {});
  assert.equal(response.status, 503);google.stateTo('error');
  assert.match(h.elements['basemap-status'].textContent, /conexão/);assert.doesNotMatch(h.elements['basemap-status'].textContent, /secret/);
});
test('tile failure restores streets and retry does not reuse failed tiles', () => {
  const h = setup();const google = h.created[0];google.stateTo('ready');google.listeners.tileloaderror();
  assert.equal(h.base.source, h.streets);assert.equal(h.elements['google-credit'].hidden, true);
  h.change('satellite');assert.equal(google.disposed, true);assert.equal(h.created.length, 2);
});
