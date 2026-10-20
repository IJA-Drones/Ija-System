const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/vigilancia-fluxo.js', 'utf8');

function browser(hash = '') {
  const elements = new Map(), events = [], handlers = {}, windows = {};
  const root = {dataset: {vigilanciaDefault: 'amostra'}, contains: () => true,
    addEventListener(name, fn) { handlers[name] = fn; }};
  function element(id, panel, tag = 'DIV') {
    const item = {id, tagName: tag, parentElement: root, hidden: false, open: false, attributes: {},
      setAttribute(name, value) { this.attributes[name] = value; }, scrollIntoView() {}, focus() {},
      closest(selector) { return selector === '[data-vigilancia-panel]' ? elements.get(panel || id) : this; },
      querySelector() { return {setAttribute() {}, focus() {}}; }};
    elements.set(id, item); return item;
  }
  const panels = ['territorio', 'levantamentos', 'amostra'].map(id => element(id));
  const links = panels.map(panel => ({dataset: {vigilanciaTarget: panel.id}, attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; }}));
  root.querySelectorAll = selector => selector === '[data-vigilancia-panel]' ? panels : links;
  const details = element('estrato', 'amostra', 'DETAILS');
  const input = element('codigo-estrato', 'amostra', 'INPUT'); input.parentElement = details; input.value = 'E-POC';
  const document = {querySelector: () => root, getElementById: id => elements.get(id), dispatchEvent(event) { events.push(event); }};
  vm.runInNewContext(source, {document, history: {replaceState() {}}, location: {hash},
    window: {addEventListener(name, fn) { windows[name] = fn; }}, CustomEvent: class {constructor(type, options) { this.type = type; this.detail = options.detail; }}});
  function click(target) {
    let prevented = false;
    handlers.click({target: {closest: () => ({getAttribute: () => '#' + target})}, preventDefault() { prevented = true; }});
    return prevented;
  }
  return {panels, input, details, links, events, click, invalid: () => handlers.invalid({target: input})};
}

test('planning opens only the active step and preserves form values when switching', () => {
  const ui = browser();
  assert.deepEqual(ui.panels.map(panel => panel.hidden), [true, true, false]);
  ui.click('territorio');
  assert.deepEqual(ui.panels.map(panel => panel.hidden), [false, true, true]);
  ui.click('amostra');
  assert.equal(ui.input.value, 'E-POC');
  assert.equal(ui.links[2].attributes['aria-current'], 'step');
});

test('deep links and native validation reveal the correct step and enclosing details', () => {
  const ui = browser('#codigo-estrato');
  assert.equal(ui.details.open, true);
  ui.click('territorio');
  ui.details.open = false;
  ui.invalid();
  assert.equal(ui.panels[2].hidden, false);
  assert.equal(ui.details.open, true);
});

test('opening the territory dispatches a visibility event for lazy map initialization', () => {
  const ui = browser();
  ui.click('territorio');
  assert.equal(ui.events.at(-1).type, 'vigilancia:panel-visible');
  assert.equal(ui.events.at(-1).detail.id, 'territorio');
});
