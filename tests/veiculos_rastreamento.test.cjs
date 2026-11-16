const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/js/veiculos-rastreamento.js'), 'utf8');
const detailSource = fs.readFileSync(path.join(__dirname, '../app/static/js/tracking-route-details.js'), 'utf8');
const template = fs.readFileSync(path.join(__dirname, '../app/templates/veiculos_rastreamento.html'), 'utf8');

class Element {
  constructor(tag = 'div') { this.tag = tag; this.children = []; this.dataset = {}; this.style = {}; this.events = {}; this.value = ''; this.className = ''; this.hidden = false; this._text = ''; this.attrs = {}; this.classList = { toggle() {}, add() {}, remove() {} }; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(' '); }
  get options() { return this.children; }
  append(...children) { for (const child of children) this.children.push(...(child.tag === 'fragment' ? child.children : [child])); }
  replaceChildren(...children) { this._text = ''; this.children = []; this.append(...children); }
  add(child) { this.append(child); }
  setAttribute(name, value) { this.attrs[name] = value; }
  removeAttribute(name) { delete this.attrs[name]; }
  addEventListener(name, callback) { this.events[name] = callback; }
  fire(name) { return this.events[name]?.(); }
  click() { return this.fire('click'); }
  remove() {}
  focus() {}
  showModal() { this.open = true; }
  close() { this.open = false; this.fire('close'); }
}

function fixture() {
  return {
    integration: { status: 'connected', sync: { enabled: false } }, history_date: '2026-10-07',
    vehicles: [{ id: '1', plate: 'DEMO001', model: 'Fictício', team: 'Equipe fictícia', responsible: 'Responsável do cadastro', ploa_driver: { name: 'Condutora de teste', pilot_id: 11 },
      driver: { name: 'Condutora de teste', log_id: 7, started_at: '2026-10-07T08:00:00-03:00' },
      position: { lat: -23.55, lng: -46.63, speed_kmh: 32, reported_at: new Date().toISOString() },
      history: [0, 1, 2].map(i => ({ lat: -23.55 + i / 1000, lng: -46.63,
        reported_at: `2026-10-07T11:0${i}:00Z`, speed_kmh: i === 1 ? null : 32,
        log_id: 7, driver_name: 'Condutora de teste', break_before: i === 2 })),
      daily: { date: '2026-10-07', logs: [{ id: 7, driver: { name: 'Condutora de teste' }, gps: { distance_km: 10 }, comparison: 'difference', difference_km: 3, tolerance_km: 2 }],
        distance_km: 10, recorded_km: 7, differences: 1, gaps: 1, sample_count: 3 },
    }],
  };
}

function browser(data = fixture(), fetch = async () => { throw new Error('offline'); }) {
  const elements = Object.fromEntries([...template.matchAll(/id="([^"]+)"/g)].map(match => [match[1], new Element()]));
  elements.trackingSkipGaps.checked = true;
  elements.trackingData.textContent = JSON.stringify(data);
  elements.trackingPage.dataset.url = '/veiculos/rastreamento/dados';
  elements.trackingPage.dataset.historyUrl = '/veiculos/rastreamento/historico';
  const tabs = ['positions', 'history', 'playback', 'comparison', 'telemetry', 'reports'].map(view => {
    const button = new Element('button'); button.dataset.view = view; return button;
  });
  const paths = [], downloads = [], intervals = [], markerMoves = [], cameraMoves = [], markers = [];
  let clock = Date.now();
  class ClockDate extends Date { constructor(...args) { super(...(args.length ? args : [clock])); } static now() { return clock; } }
  const google = { maps: {
    Map: class { fitBounds() { cameraMoves.push('fit'); } setCenter() { cameraMoves.push('center'); } setZoom() { cameraMoves.push('zoom'); } },
    LatLngBounds: class { extend() {} },
    Marker: class { constructor(options) { this.options = options; this.listeners = {}; markers.push(this); } addListener(name, callback) { this.listeners[name] = callback; } setMap() {} setPosition(point) { markerMoves.push(point); } },
    Polyline: class { constructor(options) { paths.push(options.path); } setMap() {} },
    StreetViewService: class { getPanorama(request, callback) { callback({ location: { pano: 'fictional-pano', description: 'Panorama fictício de teste' } }, 'OK'); } },
    StreetViewPanorama: class { setPano() {} setVisible() {} },
    SymbolPath: { CIRCLE: 'circle' }, event: { trigger() {} },
  } };
  class DownloadURL extends URL { static createObjectURL(blob) { downloads.push(blob); return 'blob:fixture'; } static revokeObjectURL() {} }
  const context = {
    document: { getElementById: id => elements[id], createElement: tag => new Element(tag), createElementNS: (namespace, tag) => new Element(tag),
      createDocumentFragment: () => new Element('fragment'), createTextNode: text => { const n = new Element(); n.textContent = text; return n; },
      querySelectorAll: selector => selector === '.tracking-module-tabs button' ? tabs : elements.trackingVehicleList.children.filter(e => e.tag === 'button'),
      addEventListener() {}, querySelector() { return null; }, body: new Element('body') },
    window: { google, location: { href: 'http://localhost/veiculos/rastreamento', search: '' }, addEventListener() {} },
    google, getComputedStyle: () => ({ getPropertyValue: () => '#087e91' }),
    Option: function(text, value) { const option = new Element('option'); option.textContent = text; option.value = value; return option; },
    URL: DownloadURL, URLSearchParams, Blob, AbortController, fetch, Date: ClockDate,
    setInterval(callback) { intervals.push(callback); return intervals.length; }, clearInterval() {}, setTimeout() { return 1; }, clearTimeout() {},
  };
  vm.runInNewContext(detailSource, context);
  vm.runInNewContext(source, context);
  return { elements, paths, downloads, markerMoves, cameraMoves, markers, google, details: context.window.IjaTrackingDetails, advance(ms) { clock += ms; intervals.at(-1)(); }, view: name => tabs.find(tab => tab.dataset.view === name).click() };
}

test('shows the PLOA driver immediately in fleet list and selected vehicle', () => {
  const { elements } = browser();
  assert.equal(elements.trackingDriverName.textContent, 'Condutora de teste');
  assert.match(elements.trackingVehicleList.textContent, /Condutora de teste/);
  elements.trackingSearch.value = 'condutora'; elements.trackingSearch.fire('input');
  assert.equal(elements.trackingCount.textContent, '1');
});

test('registered responsible is visible and searchable independently of the driver', () => {
  const { elements } = browser();
  assert.equal(elements.trackingResponsibleName.textContent, 'Responsável do cadastro');
  assert.match(elements.trackingVehicleList.textContent, /Responsável: Responsável do cadastro/);
  elements.trackingSearch.value = 'responsavel do cadastro'; elements.trackingSearch.fire('input');
  assert.equal(elements.trackingCount.textContent, '1');
  assert.equal(elements.trackingDriverName.textContent, 'Condutora de teste');
  const data = fixture(); data.vehicles[0].responsible = null;
  assert.equal(browser(data).elements.trackingResponsibleName.textContent, 'Não informado');
});

test('fleet export includes responsible and current driver in separate columns', async () => {
  const page = browser();
  page.view('reports');
  const walk = element => [element, ...element.children.flatMap(walk)];
  walk(page.elements.trackingToolPanel).find(element => element.tag === 'button' && element.textContent === 'Exportar CSV da frota').click();
  const csv = await page.downloads[0].text();
  assert.match(csv, /"Responsável cadastrado";"Condutor do PLOA"/);
  assert.match(csv, /"Responsável do cadastro";"Condutora de teste"/);
});

test('old speed is explicitly a last reading and missing speed is not zero', () => {
  const data = fixture();
  data.vehicles[0].position.reported_at = new Date(Date.now() - 3600000).toISOString();
  let page = browser(data);
  assert.match(page.elements.detailSpeed.textContent, /última leitura/);
  assert.equal(page.elements.detailSpeedLabel.textContent, 'Velocidade na última leitura');
  data.vehicles[0].position.speed_kmh = null;
  page = browser(data);
  assert.equal(page.elements.detailSpeed.textContent, '—');
});

test('Google polylines do not connect segments across GPS gaps', () => {
  const page = browser();
  page.view('history');
  assert.deepEqual(page.paths.slice(-2).map(points => points.length), [2, 1]);
});

test('comparison panel links a shift to its filtered route', () => {
  const page = browser();
  page.elements.trackingCompare.click();
  assert.match(page.elements.trackingToolPanel.textContent, /Diferença identificada/);
  const walk = element => [element, ...element.children.flatMap(walk)];
  walk(page.elements.trackingToolPanel).find(element => element.tag === 'button' && element.textContent === 'Ver trecho').click();
  assert.match(page.elements.trackingHistorySummary.textContent, /Log #7/);
  assert.equal(page.elements.trackingAllShifts.hidden, false);
});

test('route CSV keeps missing speeds blank and includes driver and report times', async () => {
  const page = browser();
  page.view('reports');
  const walk = element => [element, ...element.children.flatMap(walk)];
  walk(page.elements.trackingToolPanel).find(element => element.tag === 'button' && element.textContent === 'Exportar CSV do trajeto').click();
  const csv = await page.downloads[0].text();
  assert.match(csv, /Reporte.*Log.*Condutor/);
  assert.match(csv, /"2";"[^"]+";"[^"]+";"";"2026-10-07T11:01:00Z";"7";"Condutora de teste"/);
});

test('changing date hides previous day summary even if refresh fails', async () => {
  const page = browser();
  page.elements.trackingPeriodStart.value = '2026-10-06T00:00';
  page.elements.trackingPeriodEnd.value = '2026-10-06T23:59';
  page.elements.trackingApplyPeriod.click();
  await new Promise(resolve => setImmediate(resolve));
  assert.doesNotMatch(page.elements.trackingDaySummary.textContent, /10 km/);
  assert.match(page.elements.trackingDaySummary.textContent, /Consultando os trajetos salvos/);
});

test('Flashback follows actual sample timestamps and updates the point telemetry', () => {
  const page = browser();
  page.view('playback');
  assert.equal(page.elements.detailSpeedLabel.textContent, 'Velocidade no ponto do Flashback');
  assert.match(page.elements.detailReportedAt.textContent, /08:00/);
  page.elements.trackingPlaybackSpeed.value = '60';
  page.elements.trackingPlay.click();
  page.advance(1000);  // 60 seconds of the recorded route, not one arbitrary step.
  assert.equal(page.elements.trackingPlaybackRange.value, 1);
  assert.equal(page.elements.detailSpeed.textContent, '—');
  assert.match(page.elements.detailReportedAt.textContent, /08:01/);
  page.advance(1000);
  assert.equal(page.elements.trackingPlaybackRange.value, 2);
  assert.equal(page.elements.trackingPlay.textContent, 'Reproduzir');
  page.view('positions');
  assert.equal(page.elements.detailSpeed.textContent, '32 km/h');
});

test('telemetry table uses real sensor values received in the payload', () => {
  const data = fixture();
  data.vehicles[0].position.telemetry = { gps_battery: null, vehicle_battery_v: 12.7, satellites: 15, signal: 62 };
  const page = browser(data);
  page.view('telemetry');
  assert.match(page.elements.trackingToolPanel.textContent, /12,7 V/);
  assert.match(page.elements.trackingToolPanel.textContent, /Satélites 15/);
  assert.match(page.elements.trackingToolPanel.textContent, /Sinal GSM .* 62/);
});

test('opening routes retrieves provider history for selected vehicle and day once', async () => {
  const data = fixture();
  data.integration.sync.enabled = true;
  const requests = [];
  const page = browser(data, async (url, options) => {
    requests.push({ url: String(url), options });
    return { ok: true, headers: { get() { return 'application/json'; } }, async json() {
      return options.method === 'POST' ? { vehicles: 1, inserted: 3, duplicate: 0, invalid: 0 } : data;
    } };
  });
  page.view('history');
  await new Promise(resolve => setImmediate(resolve));
  const post = requests.find(request => request.options.method === 'POST');
  assert.ok(post, 'selecting the route tab must request history, without a manual refresh');
  assert.deepEqual(JSON.parse(post.options.body), { vehicle_id: '1', start: '2026-10-07T00:00', end: '2026-10-07T23:59', background: true });
  assert.match(page.elements.trackingHistoryFeedback.textContent, /Trajeto atualizado e salvo/);
  page.view('playback');
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests.filter(request => request.options.method === 'POST').length, 1);
});

test('selecting a vehicle opens its saved route and discards an older response', async () => {
  const data = fixture();
  data.vehicles.push({ ...data.vehicles[0], id: '2', plate: 'DEMO002', history_loaded: false, history: [], daily: null });
  let complete, request;
  const page = browser(data, (url, options) => {
    request = { url: new URL(url), signal: options.signal };
    return new Promise(resolve => { complete = resolve; });
  });
  page.view('positions');
  page.elements.trackingVehicleList.children[1].click();
  assert.equal(request.url.searchParams.get('vehicle_id'), '2');
  assert.equal(request.url.searchParams.get('cached'), '1');
  assert.equal(page.elements.trackingMapTitle.textContent, 'Rotas percorridas');
  page.elements.trackingVehicleList.children[0].click();
  assert.equal(request.signal.aborted, true);
  complete({ ok: true, headers: { get() { return 'application/json'; } }, json: async () => data });
  await new Promise(resolve => setImmediate(resolve));
  assert.match(page.elements.trackingDetailTitle.textContent, /DEMO001/);
  assert.match(page.elements.trackingHistorySummary.textContent, /3 pontos/);
});

test('applies both period boundaries to saved-route queries', async () => {
  let request;
  const page = browser(fixture(), async url => { request = new URL(url); throw new Error('offline'); });
  page.elements.trackingPeriodStart.value = '2026-10-06T23:00';
  page.elements.trackingPeriodEnd.value = '2026-10-07T08:30';
  page.elements.trackingApplyPeriod.click();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(request.searchParams.get('start'), '2026-10-06T23:00');
  assert.equal(request.searchParams.get('end'), '2026-10-07T08:30');
  assert.equal(request.searchParams.get('vehicle_id'), '1');
});

test('background route updates do not disable playback of saved points', async () => {
  const data = fixture(); data.integration.sync.enabled = true;
  const page = browser(data, () => new Promise(() => {}));
  page.view('playback');
  assert.equal(page.elements.trackingPlay.disabled, false);
  assert.equal(page.elements.trackingPlaybackRange.disabled, false);
  assert.match(page.elements.trackingHistoryFeedback.textContent, /segundo plano/);
});

test('Flashback moves the marker and seeks without rebuilding paths or resetting the camera', () => {
  const data = fixture();
  data.vehicles[0].history = Array.from({ length: 5000 }, (_, i) => ({ lat: -23.55 + i / 100000, lng: -46.63,
    reported_at: new Date(Date.parse('2026-10-07T03:00:00Z') + i * 1000).toISOString(), speed_kmh: 30 }));
  const page = browser(data);
  page.view('playback');
  const paths = page.paths.length, camera = page.cameraMoves.length;
  page.elements.trackingPlay.click();
  page.advance(1000);
  assert.equal(page.elements.trackingPlaybackRange.value, 60);
  assert.equal(page.paths.length, paths);
  assert.equal(page.cameraMoves.length, camera);
  assert.ok(page.markerMoves.length >= 2);
  page.elements.trackingPlaybackRange.value = '4500'; page.elements.trackingPlaybackRange.fire('input');
  assert.equal(page.elements.trackingPlaybackRange.value, 4500);
  assert.equal(page.paths.length, paths);
  assert.equal(page.cameraMoves.length, camera);
});

test('long stationary intervals can be skipped without changing the recorded timestamps', () => {
  const data = fixture();
  data.vehicles[0].history = [data.vehicles[0].history[0], { ...data.vehicles[0].history[2], reported_at: '2026-10-07T14:00:00Z' }];
  const page = browser(data);
  page.view('playback'); page.elements.trackingPlay.click(); page.advance(1000);
  assert.equal(page.elements.trackingPlaybackRange.value, 1);
  assert.match(page.elements.trackingPlaybackLabel.textContent, /11:00.*Fim da reprodução/);
  const realTime = browser(data);
  realTime.elements.trackingSkipGaps.checked = false;
  realTime.view('playback'); realTime.elements.trackingPlay.click(); realTime.advance(1000);
  assert.equal(realTime.elements.trackingPlaybackRange.value, 0);
});

test('an earlier request completing during playback cannot stop or replace the recording', async () => {
  let complete;
  const data = fixture();
  const page = browser(data, () => new Promise(resolve => { complete = resolve; }));
  page.elements.trackingRefresh.click();
  page.view('playback'); page.elements.trackingPlay.click();
  const updated = fixture(); updated.vehicles[0].history = [];
  complete({ ok: true, headers: { get() { return 'application/json'; } }, json: async () => updated });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(page.elements.trackingPlay.textContent, 'Pausar');
  page.advance(1000);
  assert.equal(page.elements.trackingPlaybackRange.value, 1);
});

test('unknown odometer continuity does not break a geometrically valid map segment', () => {
  const data = fixture();
  data.vehicles[0].history[2].geometry_break_before = false;
  const page = browser(data);
  assert.equal(page.paths.at(-1).length, 3);
});

test('an empty route still shows the selected vehicle last position with a clear label', () => {
  const data = fixture(); data.vehicles[0].history = [];
  const page = browser(data);
  assert.equal(page.elements.trackingMapEmpty.hidden, true);
  assert.match(page.elements.trackingMapLabel.textContent, /Última posição.*sem trajeto/);
  assert.equal(page.elements.trackingPlay.disabled, true);
});


test('current driver comes from the PLOA and Flashback keeps the recorded shift identity', () => {
  const data = fixture(); data.vehicles[0].ploa_driver.name = 'Titular atual do PLOA';
  data.vehicles[0].driver.name = 'Outro nome informado no turno';
  const page = browser(data);
  assert.equal(page.elements.trackingDriverName.textContent, 'Titular atual do PLOA');
  assert.match(page.elements.trackingVehicleList.textContent, /Titular atual do PLOA/);
  page.view('playback');
  assert.match(page.elements.trackingDetailSubtitle.textContent, /Condutora de teste/);
  assert.equal(page.elements.trackingDriverName.textContent, 'Titular atual do PLOA');
});

test('speed chart has a proportional scale above 60 km/h and uses actual report times', () => {
  const data = fixture();
  data.vehicles[0].history = [0, 1, 2].map((i) => ({ lat: -23, lng: -46,
    reported_at: `2026-10-07T11:0${i}:00Z`, speed_kmh: [20, 60, 92][i] }));
  const page = browser(data); page.view('telemetry');
  const walk = element => [element, ...element.children.flatMap(walk)];
  const nodes = walk(page.elements.trackingToolPanel);
  const svg = nodes.find(element => element.tag === 'svg');
  assert.match(svg.attrs['aria-label'], /máxima 92 km/);
  assert.match(svg.textContent, /100/);
  assert.match(svg.textContent, /08:00/);
  const path = nodes.find(element => element.tag === 'path' && element.attrs.class === 'tracking-chart-line');
  const ys = [...path.attrs.d.matchAll(/[ML][\d.]+,([\d.]+)/g)].map(match => Number(match[1]));
  assert.ok(ys[2] < ys[1] && ys[1] < ys[0], 'larger speeds must have proportionally higher points');
  const slider = nodes.find(element => element.tag === 'input' && element.type === 'range');
  slider.value = '2'; slider.fire('input');
  assert.match(page.elements.trackingToolPanel.textContent, /08:02.*92 km/);
});


test('clicking a route point opens its recorded data and links to Street View', () => {
  const page = browser();
  page.markers.find(marker => marker.options.title.includes('Clique para ver a leitura')).listeners.click();
  assert.equal(page.elements.trackingPointModal.open, true);
  assert.match(page.elements.trackingPointTitle.textContent, /DEMO001/);
  assert.match(page.elements.trackingPointFields.textContent, /Condutora de teste/);
  assert.match(page.elements.trackingPointStreetLink.href, /google.com\/maps\/@.*map_action=pano.*viewpoint=/);
  page.elements.trackingPointClose.click();
  assert.equal(page.elements.trackingPointModal.open, false);
});

test('stop markers require observed continuity and do not include long communication gaps', () => {
  const page = browser();
  const points = [0, 60, 120, 3600, 3660].map((seconds) => ({ lat: -23, lng: -46, speed_kmh: 0,
    reported_at: new Date(Date.parse('2026-10-07T11:00:00Z') + seconds * 1000).toISOString() }));
  const stops = page.details.stops(points);
  assert.deepEqual(Array.from(stops, stop => [stop.start, stop.end]), [[0, 2], [3, 4]]);
  assert.ok(page.details.sampleIndices(Array.from({ length: 10000 }, () => ({}))).length <= 81);
});

test('Street View supports imagery and reports unavailable locations without leaving a blank panel', async () => {
  const page = browser();
  page.markers.find(marker => marker.options.title.includes('Clique para ver a leitura')).listeners.click();
  await page.elements.trackingPointStreetTab.click();
  assert.equal(page.elements.trackingStreetCanvas.hidden, false);
  assert.match(page.elements.trackingPointStreetStatus.textContent, /Panorama fictício/);
  page.google.maps.StreetViewService = class { getPanorama(request, callback) { callback(null, 'ZERO_RESULTS'); } };
  await page.elements.trackingPointStreetTab.click();
  assert.equal(page.elements.trackingStreetCanvas.hidden, true);
  assert.match(page.elements.trackingPointStreetStatus.textContent, /Não há imagens/);
});

test('stop details report observed ignition durations without inventing transition times', () => {
  const page = browser();
  const points = [0, 60, 120].map((seconds, i) => ({ lat: -23, lng: -46, speed_kmh: 0, ignition: i < 2 ? 1 : 0,
    reported_at: new Date(Date.parse('2026-10-07T11:00:00Z') + seconds * 1000).toISOString() }));
  page.details.open({ vehicle: fixture().vehicles[0], points, index: 0, daily: { logs: [] }, onSelect() {}, onPlay() {} });
  assert.match(page.elements.trackingPointStop.textContent, /Duração observada 2min 0s/);
  assert.match(page.elements.trackingPointStop.textContent, /Ligada: 1min 0s/);
  assert.match(page.elements.trackingPointStop.textContent, /Não determinada: 1min 0s/);
});


test('initial selection prefers a saved route or a recent fix over an empty stale vehicle', () => {
  const data = fixture(); data.vehicles[0].history = [];
  data.vehicles[0].position.reported_at = '2026-10-07T11:00:00Z';
  data.vehicles.push({ ...data.vehicles[0], id: '2', plate: 'DEMO002', history_loaded: false,
    position: { ...data.vehicles[0].position, reported_at: new Date().toISOString() } });
  assert.match(browser(data).elements.trackingDetailTitle.textContent, /DEMO002/);
});
