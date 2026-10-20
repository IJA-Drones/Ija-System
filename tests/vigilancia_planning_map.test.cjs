const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('app/static/js/vigilancia-planejamento-mapa.js', 'utf8');
const point = (lat, lng) => ({lat: () => lat, lng: () => lng});

function browser(records = [], options = {}) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      value: '', textContent: '', disabled: false, hidden: false, handlers: {}, attributes: {},
      addEventListener(name, handler) { (this.handlers[name] ??= []).push(handler); },
      setAttribute(name, value) { this.attributes[name] = value; },
      emit(name, event = {}) { for (const handler of this.handlers[name] || []) handler(event); },
      click() { if (!this.disabled) this.emit('click'); },
      scrollIntoView() {}, focus() {},
    });
    return elements.get(id);
  };
  const fields = new Map();
  const field = name => {
    if (!fields.has(name)) fields.set(name, {value: '', required: false, checked: false});
    return fields.get(name);
  };
  field('geometria_acao').value = 'manter';
  element('territorio-form').elements = {namedItem: field};
  element('territorio-mapa-data').textContent = JSON.stringify({
    registros: records, editavel: true, selecionarAmostra: false, inicial: '', configurado: options.configured ?? true,
  });
  class Path {
    constructor(values) { this.values = values.map(p => typeof p.lat === 'function' ? p : point(p.lat, p.lng)); this.handlers = {}; }
    getArray() { return this.values; }
    addListener(name, callback) {
      (this.handlers[name] ??= new Set()).add(callback);
      return {remove: () => this.handlers[name].delete(callback)};
    }
    emit(name) { for (const callback of this.handlers[name] || []) callback(); }
    push(value) { this.values.push(value); this.emit('insert_at'); }
    pop() { this.values.pop(); this.emit('remove_at'); }
    setAt(index, value) { this.values[index] = value; this.emit('set_at'); }
  }
  const polygons = [], maps = [];
  class Polygon {
    constructor(options) {
      // An empty list of paths has no first ring, as observed in Maps v3.66.
      const paths = options.paths;
      this.path = paths.length ? new Path(Array.isArray(paths[0]) ? paths[0] : paths) : undefined;
      this.editable = options.editable;
      polygons.push(this);
    }
    getPath() { return this.path; }
    setMap() {}
    setOptions() {}
    setEditable(value) { this.editable = value; }
    addListener() {}
  }
  class GoogleMap {
    constructor() { this.handlers = {}; maps.push(this); }
    addListener(name, handler) { this.handlers[name] = handler; }
    fitBounds() {}
  }
  const documentEvents = {};
  const document = {
    getElementById: element,
    querySelectorAll: () => records.map(item => {
      const button = element('record-' + item.code);
      button.dataset = {territorioCode: item.code};
      return button;
    }),
    addEventListener(name, handler) { documentEvents[name] = handler; },
  };
  const window = {document, google: options.googleAvailable === false ? undefined : {maps: {Map: GoogleMap, Polygon,
    InfoWindow: class { close() {} }, LatLngBounds: class { extend() {} }}},
    __GOOGLE_MAPS_AUTH_FAILED__: options.authFailed ?? false,
    confirm: () => true, setTimeout() {}, clearTimeout() {}};
  vm.runInNewContext(source, {window});
  return {
    element: id => element('territorio-' + id), field,
    load: code => element('record-' + code).click(),
    mapClick: (lat, lng) => maps[0].handlers.click({latLng: point(lat, lng)}),
    polygon: () => polygons.at(-1),
    failMaps: () => documentEvents['googlemaps:auth-failed'](),
  };
}

test('a new empty outline accepts map clicks, completes and remains editable', () => {
  const ui = browser();
  assert.doesNotThrow(() => ui.element('desenhar').click());
  assert.match(ui.element('mapa-feedback').textContent, /Desenho iniciado/);
  assert.equal(ui.element('concluir').disabled, true);
  ui.mapClick(-8.35, -36.70);
  ui.mapClick(-8.35, -36.69);
  assert.equal(ui.element('concluir').disabled, true);
  ui.mapClick(-8.34, -36.69);
  assert.equal(ui.element('concluir').disabled, false);
  ui.element('concluir').click();
  const geometry = JSON.parse(ui.field('geometria').value);
  assert.equal(geometry.type, 'Polygon');
  assert.equal(geometry.coordinates[0].length, 4);
  assert.deepEqual(geometry.coordinates[0][0], geometry.coordinates[0].at(-1));
  assert.equal(ui.field('geometria_acao').value, 'substituir');
  assert.equal(ui.field('geometria_confirmada').required, true);
  assert.equal(ui.polygon().editable, true);
  ui.polygon().getPath().setAt(1, point(-8.35, -36.68));
  assert.equal(JSON.parse(ui.field('geometria').value).coordinates[0][1][0], -36.68);
});

test('undo to zero and cancel let another drawing start without a missing path', () => {
  const ui = browser();
  ui.element('desenhar').click();
  ui.mapClick(-8.35, -36.70);
  ui.element('desfazer').click();
  assert.equal(ui.element('desfazer').disabled, true);
  assert.equal(ui.element('concluir').disabled, true);
  assert.doesNotThrow(() => ui.element('restaurar').click());
  assert.equal(ui.field('geometria_acao').value, 'manter');
  assert.equal(ui.field('geometria').value, '');
  assert.doesNotThrow(() => ui.element('desenhar').click());
  ui.mapClick(-8.35, -36.70);
  assert.match(ui.element('mapa-feedback').textContent, /1 ponto/);
});

test('a registered block without geometry can be loaded and receive its first outline', () => {
  const ui = browser([{code: 'Q-POC-01', bairro: 'Bairro ficticio', area: 'A-01', imoveis: 100,
    referencia: 'Demonstracao', versao: '1', geometria: null}]);
  assert.doesNotThrow(() => ui.load('Q-POC-01'));
  assert.equal(ui.field('quarteirao').value, 'Q-POC-01');
  ui.element('desenhar').click();
  ui.mapClick(-8.35, -36.70);
  ui.mapClick(-8.35, -36.69);
  ui.mapClick(-8.34, -36.69);
  ui.element('concluir').click();
  assert.equal(JSON.parse(ui.field('geometria').value).type, 'Polygon');
});

test('the block button loads its form when the map SDK is unavailable', () => {
  const ui = browser([{code: 'Q-001', bairro: 'Bairro ficticio', area: 'A-01', imoveis: 100,
    referencia: 'RG de demonstracao', versao: '1', geometria: null}], {configured: false, googleAvailable: false});
  ui.load('Q-001');
  assert.equal(ui.field('quarteirao').value, 'Q-001');
  assert.equal(ui.field('bairro').value, 'Bairro ficticio');
  assert.equal(ui.field('imoveis').value, 100);
  assert.equal(ui.element('cadastro').open, true);
  assert.match(ui.element('mapa-resumo').textContent, /mapa.*indisponível/i);
  assert.equal(ui.element('desenhar').disabled, true);
  assert.equal(ui.field('geometria_acao').value, 'manter');
});

test('loading a saved outline after Maps authorization fails preserves its geometry', () => {
  const geometry = {type: 'Polygon', coordinates: [[[-36.7, -8.35], [-36.69, -8.35], [-36.69, -8.34], [-36.7, -8.35]]]};
  const record = {code: 'Q-002', bairro: 'Bairro ficticio', area: 'A-01', imoveis: 100,
    referencia: 'RG de demonstracao', versao: '2', geometria: geometry};
  const ui = browser([record], {authFailed: true});
  ui.load('Q-002');
  assert.equal(ui.field('quarteirao').value, 'Q-002');
  assert.equal(ui.field('territorio_versao').value, '2');
  assert.equal(ui.field('geometria_acao').value, 'manter');
  assert.equal(ui.field('geometria_confirmada').required, false);
  assert.equal(record.geometria, geometry);
  assert.equal(ui.polygon(), undefined);
});

test('a late Maps authorization failure updates the loaded block instructions', () => {
  const ui = browser([{code: 'Q-001', bairro: 'Bairro ficticio', area: 'A-01', imoveis: 100,
    referencia: 'RG de demonstracao', versao: '1', geometria: null}]);
  ui.load('Q-001');
  assert.match(ui.element('mapa-resumo').textContent, /Desenhar área/);
  ui.failMaps();
  assert.match(ui.element('mapa-resumo').textContent, /mapa.*indisponível/i);
  assert.equal(ui.element('desenhar').disabled, true);
  assert.equal(ui.field('quarteirao').value, 'Q-001');
  assert.equal(ui.field('geometria_acao').value, 'manter');
});
