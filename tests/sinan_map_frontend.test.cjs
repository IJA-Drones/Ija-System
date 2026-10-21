const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/vigilancia_sinan_import.js', 'utf8');
const municipality = {ibge: '2610905', name: 'Pesqueira', uf: 'PE'};
const job = {id: 'test-lot', kind: 'api', status: 'completed', demo: false,
  disease: 'chikungunya', ibge: municipality.ibge, year: 2026, count: 3, created: 1, updated: 2,
  summary: {classifications: {'5': 2, '13': 1}, weeks: {'202619': 3}}};
const geometry = {location: {lat: -8.357, lng: -36.697}, viewport: {south: -8.6, north: -8.1}};
const turn = () => new Promise(resolve => setImmediate(resolve));

function browser(options = {}) {
  const lot = {...job, ...options.job};
  const elements = new Map(), documentEvents = {}, markers = [], circles = [], maps = [], infos = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, {id, textContent: '', value: '', hidden: false,
      dataset: {}, children: [], handlers: {}, classList: {contains: () => true, toggle() {}},
      addEventListener(name, callback) {(this.handlers[name] ??= []).push(callback);},
      appendChild(child) {this.children.push(child); return child;},
      append(...children) {this.children.push(...children);}, replaceChildren(...children) {this.children = children;},
      setAttribute() {}, scrollIntoView() {}, focus() {}, style: {},
      async emit(name) {for (const handler of this.handlers[name] || []) await handler({preventDefault() {}});},
    });
    return elements.get(id);
  };
  const el = id => element('sinan-' + id);
  el('workflow').dataset = {url: '/api/imports', csrf: 'fake-token'};
  el('config').textContent = JSON.stringify({municipalities: [municipality], diseases: {
    chikungunya: {label: 'Chikungunya', classifications: {'5': 'Descartado', '13': 'Chikungunya'}},
    zika: {label: 'Zika', classifications: {}},
  }});
  el('disease').value = lot.disease; el('scope').value = lot.ibge; el('year').value = String(lot.year);
  el('import-source').value = 'csv';
  const document = {getElementById: element, createElement: tag => ({tagName: tag.toUpperCase(), textContent: '', children: [], style: {},
    appendChild(child) {this.children.push(child);return child;}, append(...children) {this.children.push(...children);},
    addEventListener() {}, setAttribute() {}}),
    addEventListener(name, callback) {(documentEvents[name] ??= []).push(callback);}, removeEventListener() {}};
  class Shape {constructor(settings) {this.options = settings; this.handlers = {};}
    setMap(value) {this.options.map = value;} addListener(name, callback) {this.handlers[name] = callback;}}
  class Marker extends Shape {constructor(settings) {super(settings); markers.push(this);}}
  class Circle extends Shape {constructor(settings) {super(settings); circles.push(this);}}
  class GoogleMap {constructor() {this.zoom = 9; maps.push(this);} fitBounds(bounds) {this.bounds = bounds;}
    setCenter(value) {this.center = value;} setZoom(value) {this.zoom = value;} getZoom() {return this.zoom;}}
  class InfoWindow {constructor(settings) {this.options = settings || {}; this.closed = false; infos.push(this);}
    setContent(value) {this.content = value;} setPosition(value) {this.position = value;}
    open(settings) {this.opened = settings;} close() {this.closed = true;}}
  const google = {maps: {Map: GoogleMap, Marker, Circle, InfoWindow, SymbolPath: {CIRCLE: 'CIRCLE'},
    LatLngBounds: class {constructor() {this.positions = [];} extend(p) {this.positions.push(p);}},
    Geocoder: class {geocode() {return options.geocode ? options.geocode() : Promise.resolve({results: [{geometry}]});}},
    event: {trigger() {}, addListenerOnce(_map, _name, callback) {callback();}},
  }};
  const window = {document, google, addEventListener() {}};
  const fetch = async url => ({ok: true, json: async () => url.endsWith('/mapa')
    ? {kind: lot.kind, demo: lot.demo, status: lot.status, count: lot.count, municipality, points: options.points || []}
    : {jobs: el('disease').value === lot.disease ? [lot] : [], current_id: lot.id}});
  vm.runInNewContext(source, {window, fetch, AbortController, URLSearchParams, setTimeout: () => 1, clearTimeout() {}});
  return {el, markers, circles, infos, maps,
    async load() {await el('saved-tab').emit('shown.bs.tab'); await turn();},
    open: () => el('open-map').emit('click'),
    text(node) {return [node?.textContent || '', ...(node?.children || []).map(child => this.text(child))].join(' ');},
  };
}

test('municipal API map has a visible pixel marker, a count and an automatically opened summary', async () => {
  const ui = browser(); await ui.load(); await ui.open();
  assert.equal(ui.markers.length, 1);
  const marker = ui.markers[0];
  assert.equal(marker.options.icon.path, 'CIRCLE');
  assert.ok(marker.options.icon.scale >= 18);
  assert.equal(marker.options.label.text, '3');
  assert.equal(ui.circles.length, 0, 'do not plot a tiny circle or invented case locations');
  assert.equal(ui.maps[0].bounds.south, geometry.viewport.south);
  const info = ui.infos.at(-1);
  assert.equal(info.opened.anchor, marker);
  const content = ui.text(info.content || info.options.content);
  assert.match(content, /Pesqueira/); assert.match(content, /3 registros/); assert.match(content, /Chikungunya.*2026/);
  assert.match(content, /Descartado.*2/); assert.match(content, /Chikungunya.*1/);
  assert.match(ui.el('map-status').textContent, /municipal|município/i);
});

test('reopening and changing filters closes the previous summary and removes its marker', async () => {
  const ui = browser(); await ui.load(); await ui.open();
  const firstInfo = ui.infos.at(-1), firstMarker = ui.markers.at(-1);
  await ui.open();
  assert.equal(firstInfo.closed, true); assert.equal(firstMarker.options.map, null);
  const secondInfo = ui.infos.at(-1), secondMarker = ui.markers.at(-1);
  ui.el('disease').value = 'zika'; await ui.el('disease').emit('change');
  assert.equal(secondInfo.closed, true); assert.equal(secondMarker.options.map, null);
  assert.equal(ui.el('map-section').hidden, true);
});

test('a geocoding response from a previous municipality or filter cannot draw a marker', async () => {
  let finish;
  const ui = browser({geocode: () => new Promise(resolve => {finish = resolve;})});
  await ui.load(); const pending = ui.open(); await turn();
  ui.el('disease').value = 'zika'; await ui.el('disease').emit('change');
  finish({results: [{geometry}]}); await pending;
  assert.equal(ui.markers.length, 0); assert.equal(ui.el('map-section').hidden, true);
});

test('partial and zero-record API lots remain explicitly identified as aggregate recuts', async () => {
  const ui = browser({job: {status: 'partial', count: 0, summary: {classifications: {}, weeks: {}}}});
  await ui.load(); await ui.open();
  assert.equal(ui.markers[0].options.label.text, '0');
  assert.match(ui.el('map-caption').textContent, /LOTE PARCIAL/);
  assert.match(ui.text(ui.infos.at(-1).content || ui.infos.at(-1).options.content), /PARCIAL/);
});

test('CSV cases still use supplied coordinates and classification filtering', async () => {
  const points = [{latitude: -8.35, longitude: -36.7, classification: 'confirmado', week: '202619'},
    {latitude: -8.36, longitude: -36.71, classification: 'descartado', week: '202619'}];
  const ui = browser({job: {kind: 'csv', demo: true, count: 2}, points});
  await ui.load(); await ui.open();
  assert.equal(ui.markers.length, 0); assert.equal(ui.circles.length, 2);
  assert.equal(ui.circles[0].options.center.lat, points[0].latitude);
  assert.equal(ui.el('map-class').hidden, false);
  ui.el('map-class').value = 'confirmado'; await ui.el('map-class').emit('change');
  assert.equal(ui.circles[0].options.map, null);
  assert.match(ui.el('map-status').textContent, /1 de 2 casos/);
});

test('geocoding errors show a message and never pretend there are patient points', async () => {
  const ui = browser({geocode: () => Promise.reject(new Error('Município não localizado.'))});
  await ui.load(); await ui.open();
  assert.equal(ui.markers.length, 0); assert.equal(ui.circles.length, 0);
  assert.equal(ui.el('map').hidden, true); assert.match(ui.el('map-status').textContent, /não localizado/);
});
