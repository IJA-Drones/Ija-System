const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

// Exercise the script shipped by the template with synthetic API responses.
// Google Maps rendering itself still needs browser verification.
const template = fs.readFileSync(
  path.join(__dirname, '../app/templates/mapa_relatorio.html'), 'utf8',
);
const focusOptions = [
  'Piscina', 'Piscinao', "Caixa d'agua", 'Terreno com Inservíveis',
  'Edificação Abandonada com Inservíveis', 'Outros',
];
const script = template.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/{{\s*ano_atual\|tojson\s*}}/g, '2026')
  .replace(/{{\s*mes_atual\|tojson\s*}}/g, '10')
  .replace(/{{\s*solicitacao_filter_foco_opcoes\|tojson\s*}}/g, JSON.stringify(focusOptions));

function element(value = '') {
  const classes = new Set(['d-none']);
  let text = '';
  return {
    value, innerHTML: '', disabled: false, hidden: false,
    style: { setProperty() {} },
    dataset: {}, attributes: {},
    classList: {
      add(...names) { names.forEach(name => classes.add(name)); },
      remove(...names) { names.forEach(name => classes.delete(name)); },
      contains(name) { return classes.has(name); },
      toggle(name, force) {
        const selected = force === undefined ? !classes.has(name) : force;
        if (selected) classes.add(name); else classes.delete(name);
        return selected;
      },
    },
    get textContent() { return text; },
    set textContent(value) { text = String(value); },
    get innerText() { return text; },
    set innerText(value) { text = String(value); },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    removeAttribute(name) { delete this.attributes[name]; },
    addEventListener() {},
  };
}

function harness({ uvis = true } = {}) {
  const elements = Object.fromEntries([
    'uvisFilter', 'mesFilter', 'anoFilter', 'larvaFilter', 'focoFilter',
    'filterBadge', 'mapFeedback', 'count-total', 'legend-count',
    'distancia-km', 'consumo-litros', 'custo-total-log',
    'areaLegendItems', 'areaLegendTotal',
  ].map(id => [id, element()]));
  Object.assign(elements.mesFilter, { value: '10' });
  Object.assign(elements.anoFilter, { value: '2026', reportValidity: () => true });
  Object.assign(elements.focoFilter, { value: 'todos' });
  if (!uvis) delete elements.uvisFilter;

  const requests = [];
  const errors = [];
  const overlays = [];
  const markers = [];
  const circles = [];
  const maps = [
    { setCenter() {}, setZoom() {}, fitBounds() {} },
    { setCenter() {}, setZoom() {}, fitBounds() {} },
  ];
  const context = vm.createContext({
    URLSearchParams, AbortController, Map, Number, Date,
    console: { warn() {}, error(error) { errors.push(error); } },
    window: {},
    document: {
      readyState: 'complete',
      addEventListener() {},
      getElementById(id) { return elements[id] || null; },
      querySelector() { return element(); },
      querySelectorAll() { return []; },
    },
    google: { maps: {
      OverlayView: class {
        constructor() { overlays.push(this); }
        setMap(map) { this.map = map; }
      },
      LatLng: class { constructor(lat, lng) { this.lat = lat; this.lng = lng; } },
      LatLngBounds: class { extend() {} },
      Marker: class {
        constructor(options) { Object.assign(this, options); markers.push(this); }
        setMap(map) { this.map = map; }
      },
      Circle: class {
        constructor(options) { Object.assign(this, options); circles.push(this); }
        setMap(map) { this.map = map; }
      },
      SymbolPath: { CIRCLE: 0 },
      event: { trigger() {} },
    } },
    fetch(url, options = {}) {
      return new Promise((resolve, reject) => requests.push({ url, options, resolve, reject }));
    },
    testMaps: maps,
  });
  vm.runInContext(script, context, { filename: 'mapa_relatorio.html' });
  vm.runInContext('mapHeat = testMaps[0]; mapArea = testMaps[1];', context);
  return {
    elements, requests, errors,
    update() { return vm.runInContext('atualizarMapas()', context); },
    url() { return new URL(vm.runInContext('heatmapDataUrl()', context), 'https://example.test'); },
    visiblePoints() {
      return {
        heat: overlays.filter(overlay => overlay.map).at(-1)?.data.length ?? 0,
        areas: markers.filter(marker => marker.map).length,
        circles: circles.filter(circle => circle.map).length,
        counter: elements['count-total'].textContent,
        legendCounter: elements['legend-count'].textContent,
        areaCounter: elements.areaLegendTotal.textContent,
      };
    },
  };
}

function point(foco = 'Piscina', index = 0) {
  return { lat: -23.55 - index / 1000, lng: -46.63, foco };
}

function respond(request, data, { ok = true, status = 200 } = {}) {
  request.resolve({ ok, status, json: async () => data });
}

function assertPoints(subject, count) {
  assert.deepEqual(subject.visiblePoints(), {
    heat: count, areas: count, circles: count,
    counter: String(count), legendCounter: String(count),
    areaCounter: `${count} foco${count === 1 ? '' : 's'}`,
  });
}

test('all API filter combinations preserve UVIS, month, year and larva selection', () => {
  const subject = harness();
  for (const uvis of ['', '42']) {
    for (const month of ['', '1', '10', '12']) {
      for (const year of ['2025', '2026']) {
        for (const larvae of ['', 'SIM', 'NAO', 'NAO_INFORMADO']) {
          subject.elements.uvisFilter.value = uvis;
          subject.elements.mesFilter.value = month;
          subject.elements.anoFilter.value = year;
          subject.elements.larvaFilter.value = larvae;
          const params = subject.url().searchParams;
          assert.equal(params.get('uvis_id'), uvis);
          assert.equal(params.get('mes'), month);
          assert.equal(params.get('ano'), year);
          assert.equal(params.get('larva_visualizada'), larvae);
        }
      }
    }
  }
  assert.equal(harness({ uvis: false }).url().searchParams.get('uvis_id'), '');
});

test('one response supplies both maps, counters and category legend', async () => {
  const subject = harness();
  const update = subject.update();
  assert.equal(subject.requests.length, 1);
  respond(subject.requests[0], [point('Piscina'), point('Terreno com Inservíveis', 1)]);
  await update;
  assertPoints(subject, 2);
  assert.match(subject.elements.areaLegendItems.innerHTML, /Piscina/);
  assert.match(subject.elements.areaLegendItems.innerHTML, /Terreno com Inservíveis/);
});

test('focus selection is exact and tolerates case, accents and whitespace', async () => {
  for (const focus of focusOptions) {
    const subject = harness();
    subject.elements.focoFilter.value = focus;
    const selected = ` ${focus.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase()} `;
    const update = subject.update();
    respond(subject.requests[0], [point(selected), point(`${focus} adicional`, 1)]);
    await update;
    assertPoints(subject, 1);
    assert.equal(subject.elements.filterBadge.classList.contains('d-none'), false);
  }
});

test('latest filter response wins even when an aborted request still resolves', async () => {
  const subject = harness();
  subject.elements.mesFilter.value = '1';
  const first = subject.update();
  subject.elements.mesFilter.value = '2';
  subject.elements.focoFilter.value = 'Piscina';
  const second = subject.update();
  assert.equal(subject.requests.length, 2);
  assert.equal(subject.requests[0].options.signal.aborted, true);
  respond(subject.requests[1], [point(), point('Terreno com Inservíveis', 1)]);
  await second;
  assertPoints(subject, 1);
  respond(subject.requests[0], [point(), point(), point()]);
  await first;
  assertPoints(subject, 1);
});

test('a failure from an older request does not erase the latest result', async () => {
  const subject = harness();
  const first = subject.update();
  const second = subject.update();
  respond(subject.requests[1], [point()]);
  await second;
  subject.requests[0].reject(new Error('old network failure'));
  await first;
  assertPoints(subject, 1);
});

test('HTTP, malformed JSON and network failures clear stale points and show feedback', async () => {
  for (const failure of ['http', 'shape', 'json', 'network']) {
    const subject = harness();
    const initial = subject.update();
    respond(subject.requests[0], [point(), point()]);
    await initial;
    assertPoints(subject, 2);
    const update = subject.update();
    const request = subject.requests[1];
    if (failure === 'http') respond(request, { error: 'server' }, { ok: false, status: 500 });
    if (failure === 'shape') respond(request, { error: 'not an array' });
    if (failure === 'json') request.resolve({ ok: true, json: async () => { throw new SyntaxError('invalid JSON'); } });
    if (failure === 'network') request.reject(new Error('network failure'));
    await update;
    assertPoints(subject, 0);
    assert.equal(subject.elements.mapFeedback.classList.contains('d-none'), false);
    assert.match(subject.elements.mapFeedback.textContent, /erro|falha|não|nao/i);
  }
});

test('an empty successful result resets both maps and gives explicit feedback', async () => {
  const subject = harness();
  const initial = subject.update();
  respond(subject.requests[0], [point()]);
  await initial;
  const update = subject.update();
  respond(subject.requests[1], []);
  await update;
  assertPoints(subject, 0);
  assert.equal(subject.elements.mapFeedback.classList.contains('d-none'), false);
  assert.match(subject.elements.areaLegendItems.innerHTML, /Sem focos/);
});

test('the active filter badge includes UVIS, month, year and larvae', async () => {
  for (const [id, value] of [
    ['uvisFilter', '42'], ['mesFilter', '1'], ['anoFilter', '2025'], ['larvaFilter', 'SIM'],
  ]) {
    const subject = harness();
    subject.elements[id].value = value;
    const update = subject.update();
    respond(subject.requests[0], []);
    await update;
    assert.equal(subject.elements.filterBadge.classList.contains('d-none'), false, id);
  }
  const subject = harness();
  const update = subject.update();
  respond(subject.requests[0], []);
  await update;
  assert.equal(subject.elements.filterBadge.classList.contains('d-none'), true);
});

test('an invalid year aborts pending work and does not request unfiltered data', async () => {
  const subject = harness();
  const pending = subject.update();
  subject.elements.anoFilter.value = '';
  subject.elements.anoFilter.reportValidity = () => false;
  await subject.update();
  assert.equal(subject.requests.length, 1);
  assert.equal(subject.requests[0].options.signal.aborted, true);
  assert.match(subject.elements.mapFeedback.textContent, /ano válido/);
  respond(subject.requests[0], [point()]);
  await pending;
  assertPoints(subject, 0);
});
