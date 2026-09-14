(() => {
  'use strict';
  const page = document.getElementById('trackingPage');
  if (!page) return;
  const $ = (id) => document.getElementById(id);
  const initial = JSON.parse($('trackingData').textContent);
  const statusLabels = { moving: 'Em movimento', stopped: 'Parado', stale: 'Posição antiga', pending: 'Sem posição' };
  const number = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
  const dateTime = new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short' });
  const dayParts = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const part = (name) => dayParts.find((item) => item.type === name).value;
  const today = `${part('year')}-${part('month')}-${part('day')}`;
  const state = { live: initial, demo: false, selected: null, view: 'positions', map: null, provider: null, markers: null, googleMarkers: [], googleOverlays: [], bounds: [], busy: false, playIndex: 0, playTimer: null };
  const isFixtureData = () => !state.demo && state.live.integration?.status === 'test';
  const hasConnectedData = () => !state.demo && ['test', 'connected'].includes(state.live.integration?.status);
  const normalize = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const numeric = (value) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const km = (value) => numeric(value) ? `${number.format(Number(value))} km` : '—';
  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };

  // Explicitly fictional, browser-only examples. Never merged into the real fleet.
  const demoRoute = [
    [-23.5858, -46.6637], [-23.5841, -46.6596], [-23.5815, -46.6550],
    [-23.5775, -46.6509], [-23.5723, -46.6470], [-23.5678, -46.6482],
    [-23.5634, -46.6544], [-23.5598, -46.6582], [-23.5562, -46.6624],
  ];
  const demoSpeeds = [0, 18, 26, 31, 0, 24, 42, 36, 32];
  const demoEvents = [
    { vehicle: 'demo-1', title: 'Entrada em área de interesse', description: 'O veículo entrou na área de operação de exemplo.', time: '08:15', category: 'Geocerca' },
    { vehicle: 'demo-1', title: 'Parada identificada', description: 'Parada ilustrativa durante o percurso selecionado.', time: '08:20', category: 'Parada' },
    { vehicle: 'demo-2', title: 'Ignição desligada', description: 'O veículo encerrou o deslocamento de exemplo.', time: '08:35', category: 'Ignição' },
    { vehicle: 'demo-3', title: 'Comunicação atrasada', description: 'A última posição recebida está fora do intervalo esperado.', time: '07:10', category: 'Comunicação' },
  ];
  const demoFleet = [
    { id: 'demo-1', plate: 'DEMO-01', model: 'Veículo de exemplo 01', operation: 'PMSP', team: 'Equipe de exemplo Sul', registered_km: 42500, position: { lat: -23.5562, lng: -46.6624, speed_kmh: 32, ignition: 1, odometer_km: 42518.4, reported_at: new Date(Date.now() - 60000).toISOString(), address: 'São Paulo · localização ilustrativa' }, history: demoRoute },
    { id: 'demo-2', plate: 'DEMO-02', model: 'Veículo de exemplo 02', operation: 'PMSP', team: 'Equipe de exemplo Centro', registered_km: 18740, position: { lat: -23.5491, lng: -46.6375, speed_kmh: 0, ignition: 0, odometer_km: 18742.8, reported_at: new Date(Date.now() - 120000).toISOString(), address: 'São Paulo · localização ilustrativa' }, history: [] },
    { id: 'demo-3', plate: 'DEMO-03', model: 'Veículo de exemplo 03', operation: 'AGRO', team: 'Equipe de exemplo Agro', registered_km: 63820, position: { lat: -23.5910, lng: -46.6844, speed_kmh: 0, ignition: 2, odometer_km: 63837, reported_at: new Date(Date.now() - 5400000).toISOString(), address: 'São Paulo · última localização ilustrativa' }, history: [] },
    { id: 'demo-4', plate: 'DEMO-04', model: 'Veículo de exemplo 04', operation: 'PMSP', team: 'Equipe de exemplo Norte', registered_km: 9200, position: null, history: [] },
  ];
  $('trackingHistoryDate').value = today;
  $('trackingHistoryDate').max = today;

  function vehicles() { return state.demo ? demoFleet : state.live.vehicles; }
  function hasPosition(vehicle) {
    const p = vehicle && vehicle.position;
    return p && numeric(p.lat) && numeric(p.lng) && Math.abs(Number(p.lat)) <= 90 && Math.abs(Number(p.lng)) <= 180;
  }
  function status(vehicle) {
    if (!hasPosition(vehicle)) return 'pending';
    const age = Date.now() - Date.parse(vehicle.position.reported_at);
    // Provisional UI freshness threshold; align with device cadence on integration.
    if (!Number.isFinite(age) || age > 15 * 60000 || age < -5 * 60000) return 'stale';
    if (!numeric(vehicle.position.speed_kmh) || Number(vehicle.position.speed_kmh) < 0) return 'pending';
    return Number(vehicle.position.speed_kmh) > 0 ? 'moving' : 'stopped';
  }
  function filteredVehicles() {
    const search = normalize($('trackingSearch').value);
    const operation = $('trackingOperation').value;
    const situation = $('trackingStatus').value;
    return vehicles().filter((vehicle) =>
      (!search || normalize([vehicle.plate, vehicle.model, vehicle.team].join(' ')).includes(search)) &&
      (!operation || vehicle.operation === operation) && (!situation || status(vehicle) === situation)
    );
  }
  function selectedVehicle() { return filteredVehicles().find((vehicle) => vehicle.id === state.selected); }
  function routeData(vehicle) {
    if (!vehicle || $('trackingHistoryDate').value !== today) return [];
    return (vehicle.history || []).map((point) => {
      if (Array.isArray(point)) return { lat: Number(point[0]), lng: Number(point[1]), speed_kmh: null };
      return { ...point, lat: Number(point.lat), lng: Number(point.lng) };
    }).filter((point) => Number.isFinite(point.lat) && Number.isFinite(point.lng));
  }
  function fillOperations() {
    const previous = $('trackingOperation').value;
    $('trackingOperation').replaceChildren(new Option('Todas as operações', ''));
    [...new Set(vehicles().map((vehicle) => vehicle.operation).filter(Boolean))].sort().forEach((operation) => {
      $('trackingOperation').add(new Option(operation, operation));
    });
    if ([...$('trackingOperation').options].some((option) => option.value === previous)) $('trackingOperation').value = previous;
  }
  function feedback(message, error = false) {
    $('trackingFeedback').textContent = message;
    $('trackingFeedback').classList.toggle('is-error', error);
    $('trackingFeedback').hidden = !message;
  }
  function updateNotice() {
    if (state.demo) {
      $('trackingNoticeTitle').textContent = 'Demonstração do rastreamento';
      $('trackingNoticeText').textContent = 'Veículos, posições e trajetos fictícios para explorar a interface. Nenhum dado da sua frota é alterado.';
      return;
    }
    if (isFixtureData()) {
      $('trackingNoticeTitle').textContent = 'Dados fictícios do Neon de teste';
      $('trackingNoticeText').textContent = 'A tela está carregando o fixture RedGPS persistido no banco de teste. Esses registros são identificados como demonstração.';
      return;
    }
    $('trackingNoticeTitle').textContent = hasConnectedData() ? 'Rastreamento conectado' : 'Aguardando conexão com o rastreamento';
    $('trackingNoticeText').textContent = hasConnectedData() ? 'As posições e os trajetos abaixo vieram do sincronizador RedGPS.' : 'Consulte a frota cadastrada. As posições e os trajetos estarão disponíveis após a ativação.';
  }
  function renderList(list) {
    const fragment = document.createDocumentFragment();
    list.forEach((vehicle) => {
      const situation = status(vehicle);
      const button = node('button', 'list-group-item list-group-item-action tracking-vehicle');
      button.type = 'button';
      button.dataset.vehicleId = vehicle.id;
      button.classList.toggle('is-selected', vehicle.id === state.selected);
      button.setAttribute('aria-pressed', String(vehicle.id === state.selected));
      const top = node('span', 'tracking-vehicle-top');
      top.append(node('strong', '', vehicle.plate), node('span', 'tracking-operation', vehicle.operation || '—'));
      const bottom = node('span', 'tracking-vehicle-bottom');
      const p = vehicle.position;
      bottom.append(node('span', `badge tracking-badge ${situation}`, statusLabels[situation]), node('span', '', p && numeric(p.speed_kmh) ? `${number.format(p.speed_kmh)} km/h` : '— km/h'));
      button.append(top, node('span', 'tracking-vehicle-model', `${vehicle.model} · ${vehicle.team}`), bottom);
      button.addEventListener('click', () => selectVehicle(vehicle.id));
      fragment.append(button);
    });
    if (!list.length) fragment.append(node('p', 'tracking-list-message', vehicles().length ? 'Nenhum veículo encontrado. Experimente ajustar os filtros.' : 'Nenhum veículo disponível para o seu acesso.'));
    $('trackingVehicleList').replaceChildren(fragment);
  }
  function selectVehicle(id) {
    stopPlayback();
    state.playIndex = 0;
    state.selected = id;
    document.querySelectorAll('.tracking-vehicle').forEach((button) => {
      button.classList.toggle('is-selected', button.dataset.vehicleId === id);
      button.setAttribute('aria-pressed', String(button.dataset.vehicleId === id));
    });
    renderDetails();
    renderMap(true);
  }
  function renderDetails() {
    const vehicle = selectedVehicle();
    const p = vehicle && vehicle.position;
    const situation = vehicle ? status(vehicle) : 'pending';
    $('trackingDetailTitle').textContent = vehicle ? `${vehicle.plate} · ${vehicle.model}` : 'Selecione um veículo';
    $('trackingDetailSubtitle').textContent = vehicle ? `${vehicle.team} · ${vehicle.operation || 'Sem operação'}` : 'Consulte a localização e as informações da frota.';
    $('trackingDetailStatus').textContent = statusLabels[situation];
    $('trackingDetailStatus').className = `badge tracking-badge ${situation}`;
    $('detailSpeed').textContent = p && numeric(p.speed_kmh) ? `${number.format(p.speed_kmh)} km/h` : '—';
    $('detailIgnition').textContent = p ? ({ 0: 'Desligada', 1: 'Ligada', 2: 'Desconhecida' }[p.ignition] || 'Desconhecida') : '—';
    $('detailRegisteredKm').textContent = vehicle ? km(vehicle.registered_km) : '—';
    $('detailGpsKm').textContent = p ? km(p.odometer_km) : '—';
    $('detailAddress').textContent = (p && p.address) || 'Localização ainda não disponível';
    const reportDate = p ? new Date(p.reported_at) : null;
    $('detailReportedAt').textContent = reportDate && Number.isFinite(reportDate.getTime()) ? `Último reporte: ${dateTime.format(reportDate)}${state.demo ? ' · Exemplo fictício' : isFixtureData() ? ' · Dados fictícios do Neon' : ''}` : 'Sem reporte recebido';
    const logs = $('trackingLogsLink');
    logs.hidden = !vehicle || !vehicle.logs_url || state.demo;
    if (!logs.hidden) logs.href = vehicle.logs_url;
    else logs.removeAttribute('href');
  }
  function ensureMap() {
    if (state.map) return true;
    if (!window.__GOOGLE_MAPS_AUTH_FAILED__ && window.google?.maps?.Map) {
      state.provider = 'google';
      state.map = new google.maps.Map($('trackingMap'), {
        center: { lat: -23.566, lng: -46.655 },
        zoom: 12,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        gestureHandling: 'cooperative',
        styles: [{ featureType: 'poi', stylers: [{ visibility: 'off' }] }],
      });
      return true;
    }
    if (!window.L) {
      $('trackingMapError').hidden = false;
      return false;
    }
    state.provider = 'leaflet';
    state.map = L.map('trackingMap', { zoomControl: false, scrollWheelZoom: false }).setView([-23.566, -46.655], 12);
    L.control.zoom({ position: 'topright' }).addTo(state.map);
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(state.map);
    tiles.on('tileerror', () => { $('trackingMapError').hidden = false; });
    tiles.on('tileload', () => { $('trackingMapError').hidden = true; });
    state.markers = L.layerGroup().addTo(state.map);
    if (window.ResizeObserver) new ResizeObserver(() => state.map.invalidateSize()).observe($('trackingMap'));
    return true;
  }
  function fitMap() {
    if (!state.map || !state.bounds.length) return;
    if (state.provider === 'google') {
      const bounds = new google.maps.LatLngBounds();
      state.bounds.forEach((point) => bounds.extend({ lat: Number(Array.isArray(point) ? point[0] : point.lat), lng: Number(Array.isArray(point) ? point[1] : point.lng) }));
      state.map.fitBounds(bounds);
      return;
    }
    state.map.fitBounds(state.bounds, { padding: [55, 55], maxZoom: 14, animate: false });
  }
  function clearMapLayers() {
    if (state.provider === 'google') {
      state.googleMarkers.forEach((marker) => marker.setMap(null));
      state.googleOverlays.forEach((overlay) => overlay.setMap(null));
      state.googleMarkers = [];
      state.googleOverlays = [];
    } else if (state.markers) {
      state.markers.clearLayers();
    }
  }
  function addGoogleOverlay(overlay) {
    state.googleOverlays.push(overlay);
    return overlay;
  }
  function renderGoogleMap({ areaMode, historyMode, route, located, selected, focus }) {
    if (areaMode) {
      const circle = addGoogleOverlay(new google.maps.Circle({
        map: state.map,
        center: { lat: -23.579, lng: -46.657 },
        radius: 700,
        strokeColor: getComputedStyle(page).getPropertyValue('--color-accent').trim() || '#00a3c4',
        strokeOpacity: .95,
        strokeWeight: 2,
        fillColor: getComputedStyle(page).getPropertyValue('--color-accent').trim() || '#00a3c4',
        fillOpacity: .15,
      }));
      circle.set('title', 'Base de apoio · área fictícia');
      const polygon = addGoogleOverlay(new google.maps.Polygon({
        map: state.map,
        paths: [{ lat: -23.549, lng: -46.674 }, { lat: -23.544, lng: -46.650 }, { lat: -23.558, lng: -46.638 }, { lat: -23.565, lng: -46.658 }],
        strokeColor: getComputedStyle(page).getPropertyValue('--color-recomended').trim() || '#f7630c',
        strokeOpacity: .95,
        strokeWeight: 2,
        fillColor: getComputedStyle(page).getPropertyValue('--color-recomended').trim() || '#f7630c',
        fillOpacity: .13,
      }));
      polygon.set('title', 'Setor de operação · área fictícia');
      return;
    }
    const accent = getComputedStyle(page).getPropertyValue('--color-accent').trim() || '#00a3c4';
    if (historyMode) {
      addGoogleOverlay(new google.maps.Polyline({ map: state.map, path: route.map(([lat, lng]) => ({ lat, lng })), strokeColor: accent, strokeOpacity: state.view === 'playback' ? .25 : .9, strokeWeight: 5 }));
      if (state.view === 'playback') {
        addGoogleOverlay(new google.maps.Polyline({ map: state.map, path: route.slice(0, state.playIndex + 1).map(([lat, lng]) => ({ lat, lng })), strokeColor: accent, strokeOpacity: 1, strokeWeight: 5 }));
        state.googleMarkers.push(new google.maps.Marker({ map: state.map, position: { lat: route[state.playIndex][0], lng: route[state.playIndex][1] }, icon: { path: google.maps.SymbolPath.CIRCLE, scale: 10, fillColor: accent, fillOpacity: 1, strokeColor: '#fff', strokeWeight: 3 }, title: 'Ponto do Flashback' }));
      }
      return;
    }
    located.forEach((vehicle) => {
      const p = vehicle.position;
      const situation = status(vehicle);
      const color = situation === 'moving' ? '#299975' : situation === 'stopped' ? '#488bce' : '#bc8527';
      const marker = new google.maps.Marker({
        map: state.map,
        position: { lat: Number(p.lat), lng: Number(p.lng) },
        title: `${vehicle.plate} · ${statusLabels[situation]}`,
        icon: { path: google.maps.SymbolPath.CIRCLE, scale: vehicle.id === state.selected ? 12 : 9, fillColor: color, fillOpacity: 1, strokeColor: '#fff', strokeWeight: 3 },
      });
      marker.addListener('click', () => selectVehicle(vehicle.id));
      state.googleMarkers.push(marker);
    });
    if (focus && hasPosition(selected)) state.map.setCenter({ lat: Number(selected.position.lat), lng: Number(selected.position.lng) });
  }
  function currentRoute() {
    const vehicle = selectedVehicle();
    return routeData(vehicle).map((point) => [point.lat, point.lng]);
  }
  function currentRouteSpeeds() {
    const vehicle = selectedVehicle();
    return routeData(vehicle).map((point, index) => state.demo ? demoSpeeds[index] : (numeric(point.speed_kmh) ? Number(point.speed_kmh) : 0));
  }
  function stopPlayback() {
    if (state.playTimer) clearInterval(state.playTimer);
    state.playTimer = null;
    $('trackingPlay').textContent = 'Reproduzir';
    $('trackingPlay').setAttribute('aria-label', 'Reproduzir trajeto');
  }
  function startPlayback() {
    const route = currentRoute();
    if (route.length < 2) return;
    if (state.playIndex >= route.length - 1) state.playIndex = 0;
    $('trackingPlay').textContent = 'Pausar';
    $('trackingPlay').setAttribute('aria-label', 'Pausar reprodução');
    state.playTimer = setInterval(() => {
      state.playIndex += 1;
      if (state.playIndex >= currentRoute().length - 1) stopPlayback();
      renderMap();
    }, 1200 / Number($('trackingPlaybackSpeed').value));
    renderMap();
  }
  function download(content, filename, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const link = node('a');
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function csvCell(value) {
    const text = value == null ? '' : String(value);
    const safe = typeof value === 'string' && /^[=+@\-\t\r]/.test(text) ? `'${text}` : text;
    return `"${safe.replace(/"/g, '""')}"`;
  }
  function exportFleet() {
    const rows = [['Origem', 'Placa', 'Modelo', 'Equipe', 'Operação', 'KM registrado', 'Situação']];
    filteredVehicles().forEach((v) => rows.push([state.demo ? 'DEMONSTRAÇÃO FICTÍCIA' : 'Cadastro Ija-System', v.plate, v.model, v.team, v.operation, v.registered_km, statusLabels[status(v)]]));
    download('\uFEFF' + rows.map((row) => row.map(csvCell).join(';')).join('\r\n'), `${state.demo ? 'demonstracao-' : ''}frota-${today}.csv`, 'text/csv;charset=utf-8');
  }
  function exportRoute(format) {
    const route = currentRoute();
    if (!route.length) return;
    if (format === 'kml') {
      const coordinates = route.map(([lat, lng]) => `${lng},${lat},0`).join(' ');
      const vehicle = selectedVehicle();
      const title = state.demo ? 'Demonstração fictícia DEMO-01' : `Trajeto ${vehicle?.plate || ''}`;
      download(`<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>${title}</name><Placemark><name>Trajeto</name><LineString><tessellate>1</tessellate><coordinates>${coordinates}</coordinates></LineString></Placemark></Document></kml>`, `${state.demo ? 'demonstracao-' : ''}trajeto-${today}.kml`, 'application/vnd.google-earth.kml+xml');
    } else {
      const speeds = currentRouteSpeeds();
      const rows = [['Origem', 'Ponto', 'Latitude', 'Longitude', 'Velocidade (km/h)'], ...route.map(([lat, lng], index) => [state.demo ? 'DEMONSTRAÇÃO FICTÍCIA' : 'NEON / REDGPS', index + 1, lat, lng, speeds[index]])];
      download('\uFEFF' + rows.map((row) => row.map(csvCell).join(';')).join('\r\n'), `${state.demo ? 'demonstracao-' : ''}trajeto-${today}.csv`, 'text/csv;charset=utf-8');
    }
  }
  function renderToolPanel() {
    const panel = $('trackingToolPanel');
    const vehicle = selectedVehicle();
    panel.replaceChildren();
    const titles = { telemetry: 'Telemetria do veículo', alerts: 'Quadro de avisos', reports: 'Relatórios e exportações' };
    if (!titles[state.view]) { panel.hidden = true; return; }
    panel.hidden = false;
    panel.append(node('h5', 'text-primary mb-2', titles[state.view]));
    panel.append(node('p', '', state.view === 'reports' ? 'Exporte a frota filtrada e os pontos do trajeto para análise.' : `${vehicle ? `${vehicle.plate} · ${vehicle.team}` : 'Selecione um veículo na lista.'}${state.demo || isFixtureData() ? ' · Dados fictícios' : ''}`));
    const empty = (text) => panel.append(node('div', 'alert alert-light border text-muted text-center my-4', text));
    if (state.view === 'telemetry') {
      if (!vehicle || !vehicle.position) {
        empty('Sem leituras de telemetria. Os sensores disponíveis serão exibidos após a conexão e o primeiro reporte.');
        return;
      }
      const tableWrap = node('div', 'table-responsive');
      const table = node('table', 'table table-hover align-middle mb-0');
      const head = node('thead', 'table-light');
      const headRow = node('tr');
      headRow.append(node('th', '', 'Leitura'), node('th', '', 'Valor'));
      head.append(headRow);
      const body = node('tbody');
      [['Velocidade', numeric(vehicle.position.speed_kmh) ? `${vehicle.position.speed_kmh} km/h` : '—'], ['Hodômetro GPS', km(vehicle.position.odometer_km)], ['Ignição', ({0: 'Desligada', 1: 'Ligada', 2: 'Desconhecida'})[vehicle.position.ignition] || 'Desconhecida'], ['Bateria GPS', state.demo ? '84%' : '—'], ['Bateria do veículo', state.demo ? '12,7 V' : '—'], ['Satélites', state.demo ? '15' : '—']].forEach(([label, value]) => {
        const row = node('tr');
        row.append(node('td', '', label), node('td', 'fw-semibold', value));
        body.append(row);
      });
      table.append(head, body);
      tableWrap.append(table);
      panel.append(tableWrap);
      if (vehicle.history?.length) {
        panel.append(node('h6', 'text-primary mt-4 mb-2', 'Velocidade ao longo do trajeto'));
        const chart = node('div', 'tracking-chart');
        chart.setAttribute('role', 'img');
        const speeds = currentRouteSpeeds();
        chart.setAttribute('aria-label', `Velocidades em km/h: ${speeds.join(', ')}`);
        speeds.forEach((speed) => {
          const column = node('div', 'tracking-chart-column');
          const bar = node('span', 'tracking-chart-bar');
          bar.style.height = `${speed * 2.4}px`;
          column.append(node('span', '', String(speed)), bar);
          chart.append(column);
        });
        panel.append(chart, node('p', 'tracking-panel-caption', `${vehicle.history.length} amostras ${state.demo || isFixtureData() ? 'fictícias' : ''}, na ordem do percurso · km/h`));
      }
    } else if (state.view === 'alerts') {
      const events = state.demo && vehicle ? demoEvents.filter((event) => event.vehicle === vehicle.id) : (vehicle?.alerts || []);
      if (!events.length) empty(state.demo ? 'Nenhum aviso de exemplo para o veículo selecionado.' : hasConnectedData() ? 'Nenhum aviso para o veículo selecionado.' : 'Os avisos aparecerão após a conexão. Ainda não há eventos de rastreamento recebidos.');
      events.forEach((event) => {
        const card = node('article', 'card border-start border-warning shadow-sm p-3 mt-3');
        const when = event.time || (event.reported_at ? dateTime.format(new Date(event.reported_at)) : '');
        card.append(node('strong', '', event.title), node('p', 'text-muted small my-2', event.description), node('small', 'text-warning', `${when} · ${event.category || event.severity || 'Aviso'}${state.demo || isFixtureData() ? ' · Exemplo fictício' : ''}`));
        panel.append(card);
      });
    } else {
      const report = (title, description, label, action, enabled) => {
        const card = node('div', 'card border-0 shadow-sm p-3 my-3 d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3');
        const text = node('div');
        text.append(node('strong', '', title), node('p', '', description));
        const button = node('button', 'btn btn-outline-primary btn-sm', label);
        button.type = 'button';
        button.disabled = !enabled;
        button.addEventListener('click', action);
        card.append(text, button);
        panel.append(card);
      };
      report('Frota e situação dos veículos', `${filteredVehicles().length} veículos conforme os filtros${state.demo ? ' · Demonstração fictícia' : isFixtureData() ? ' · Fixture do Neon' : ' · Dados do cadastro'}`, 'Exportar CSV da frota', exportFleet, filteredVehicles().length > 0);
      report('Pontos do trajeto', 'Coordenadas e velocidade do veículo e da data selecionados em Rotas percorridas.', 'Exportar CSV do trajeto', () => exportRoute('csv'), currentRoute().length > 0);
      report('Trajeto para mapas', 'Arquivo KML para abrir em ferramentas de análise geográfica.', 'Exportar KML', () => exportRoute('kml'), currentRoute().length > 0);
      panel.append(node('p', 'tracking-panel-caption', state.demo || isFixtureData() ? 'Todos os arquivos deste modo são identificados como dados fictícios.' : 'As exportações de trajetos serão liberadas quando houver histórico disponível.'));
    }
  }
  function renderMap(focus = false) {
    const list = filteredVehicles();
    const selected = selectedVehicle();
    const historyMode = ['history', 'playback'].includes(state.view);
    const areaMode = state.view === 'areas';
    const panelMode = ['telemetry', 'alerts', 'reports'].includes(state.view);
    renderToolPanel();
    ['trackingMapToolbar', 'trackingMapWrap', 'trackingMapLegend'].forEach((id) => { $(id).hidden = panelMode; });
    const route = historyMode ? currentRoute() : [];
    const located = list.filter(hasPosition);
    const visible = !panelMode && (areaMode ? state.demo : historyMode ? Boolean(route.length) : Boolean(located.length));
    $('trackingHistoryControls').hidden = !historyMode;
    $('trackingPlayback').hidden = state.view !== 'playback';
    $('trackingPlay').disabled = route.length < 2;
    $('trackingPlaybackRange').disabled = route.length < 2;
    $('trackingPlaybackRange').max = Math.max(0, route.length - 1);
    state.playIndex = Math.min(state.playIndex, Math.max(0, route.length - 1));
    $('trackingPlaybackRange').value = state.playIndex;
    const routeSpeeds = currentRouteSpeeds();
    $('trackingPlaybackLabel').textContent = route.length ? `Ponto ${state.playIndex + 1} de ${route.length} · ${routeSpeeds[state.playIndex] || 0} km/h · ${state.demo || isFixtureData() ? 'Reprodução fictícia' : 'Reprodução'}` : 'Nenhum trajeto disponível para reprodução.';
    const mapTitles = { positions: ['Mapa da frota', 'Localização dos veículos filtrados'], history: ['Rotas percorridas', 'Trajeto do veículo selecionado por data'], playback: ['Flashback', 'Reproduza o percurso e acompanhe cada ponto'], areas: ['Áreas de interesse', 'Geocercas e locais de referência para a operação'] };
    const mapTitle = mapTitles[state.view] || ['', ''];
    $('trackingMapTitle').textContent = mapTitle[0];
    $('trackingMapSubtitle').textContent = mapTitle[1];
    $('trackingMapEmpty').hidden = visible;
    $('trackingMap').classList.toggle('is-visible', visible);
    $('trackingMapEmptyTitle').textContent = historyMode ? 'Nenhum trajeto disponível' : (list.length ? 'O próximo destino da sua frota está aqui' : 'Nenhum veículo para mostrar');
    $('trackingMapEmptyText').textContent = historyMode ? (state.demo ? 'Selecione DEMO-01 e a data de hoje para explorar um trajeto fictício.' : 'O histórico estará disponível quando houver pontos para o veículo e a data selecionados.') : (list.length ? 'As posições aparecerão no mapa quando o rastreamento estiver conectado.' : 'Ajuste os filtros ou consulte os veículos disponíveis para o seu acesso.');
    if (areaMode) {
      $('trackingMapEmptyTitle').textContent = 'Áreas de interesse da operação';
      $('trackingMapEmptyText').textContent = 'As geocercas disponíveis aparecerão aqui após a conexão. Explore duas áreas fictícias na demonstração.';
    }
    $('trackingHistorySummary').textContent = route.length ? `${route.length} pontos ${state.demo || isFixtureData() ? 'ilustrativos' : ''} · ${selected?.plate || 'veículo selecionado'}` : 'Sem pontos para o veículo e a data selecionados.';
    $('trackingMapLabel').textContent = state.demo ? 'Demonstração · dados fictícios' : isFixtureData() ? 'Neon · dados fictícios' : hasConnectedData() ? 'RedGPS · posição recebida' : 'Aguardando posições';
    $('trackingFit').disabled = !visible;
    state.bounds = [];
    clearMapLayers();
    if (!visible) { $('trackingMapError').hidden = true; return; }
    if (!ensureMap()) { $('trackingFit').disabled = true; return; }
    $('trackingProvider').textContent = state.provider === 'google' ? 'Google Maps · RedGPS' : 'Mapa alternativo · RedGPS';
    if (state.provider === 'leaflet') state.map.invalidateSize();
    else if (window.google?.maps?.event) google.maps.event.trigger(state.map, 'resize');
    if (state.provider === 'google') {
      renderGoogleMap({ areaMode, historyMode, route, located, selected, focus });
      if (areaMode) {
        state.bounds = [[-23.549, -46.674], [-23.544, -46.650], [-23.558, -46.638], [-23.565, -46.658], [-23.579, -46.657]];
        fitMap();
      } else if (historyMode) {
        state.bounds = route;
        fitMap();
      } else {
        state.bounds = located.map((vehicle) => [Number(vehicle.position.lat), Number(vehicle.position.lng)]);
        if (!(focus && hasPosition(selected))) fitMap();
      }
      return;
    }
    if (areaMode) {
      const circle = L.circle([-23.579, -46.657], { radius: 700, color: '#087e91', weight: 2, fillOpacity: .15 }).bindTooltip('Base de apoio · área fictícia').addTo(state.markers);
      const polygon = L.polygon([[-23.549, -46.674], [-23.544, -46.650], [-23.558, -46.638], [-23.565, -46.658]], { color: '#a77921', weight: 2, fillOpacity: .13 }).bindTooltip('Setor de operação · área fictícia').addTo(state.markers);
      state.bounds = [circle.getBounds().getSouthWest(), circle.getBounds().getNorthEast(), polygon.getBounds().getSouthWest(), polygon.getBounds().getNorthEast()];
      fitMap();
    } else if (historyMode) {
      L.polyline(route, { color: '#087e91', weight: 5, opacity: state.view === 'playback' ? .25 : .9 }).addTo(state.markers);
      if (state.view === 'playback') {
        L.polyline(route.slice(0, state.playIndex + 1), { color: '#087e91', weight: 5 }).addTo(state.markers);
        L.circleMarker(route[state.playIndex], { radius: 10, color: '#fff', weight: 3, fillColor: '#087e91', fillOpacity: 1 }).addTo(state.markers);
      }
      [[route[0], state.demo || isFixtureData() ? 'Início ilustrativo' : 'Início', '#299975'], [route[route.length - 1], state.demo || isFixtureData() ? 'Fim ilustrativo' : 'Fim', '#087e91']].forEach(([point, label, color]) => {
        L.circleMarker(point, { radius: 7, color: '#fff', weight: 3, fillColor: color, fillOpacity: 1 }).bindTooltip(node('span', '', label)).addTo(state.markers);
      });
      state.bounds = route;
      fitMap();
    } else {
      located.forEach((vehicle) => {
        const p = vehicle.position;
        const situation = status(vehicle);
        const point = [Number(p.lat), Number(p.lng)];
        const marker = L.marker(point, {
          icon: L.divIcon({ className: `tracking-marker ${situation}${vehicle.id === state.selected ? ' is-selected' : ''}`, html: '<span><i class="bi bi-truck-front-fill"></i></span>', iconSize: [34, 34], iconAnchor: [17, 17] }),
          title: vehicle.plate,
          alt: vehicle.plate,
        }).addTo(state.markers);
        marker.bindTooltip(node('span', '', `${vehicle.plate} · ${statusLabels[situation]}`), { direction: 'top', offset: [0, -20] });
        marker.on('click', () => selectVehicle(vehicle.id));
        state.bounds.push(point);
      });
      if (focus && hasPosition(selected)) state.map.setView([selected.position.lat, selected.position.lng], 14, { animate: false });
      else fitMap();
    }
  }
  function render() {
    stopPlayback();
    const list = filteredVehicles();
    if (!list.some((vehicle) => vehicle.id === state.selected)) state.selected = list.length ? list[0].id : null;
    $('trackingCount').textContent = list.length;
    $('statTotal').textContent = list.length;
    $('statMoving').textContent = list.filter((vehicle) => status(vehicle) === 'moving').length;
    $('statStopped').textContent = list.filter((vehicle) => status(vehicle) === 'stopped').length;
    $('statPending').textContent = list.filter((vehicle) => ['pending', 'stale'].includes(status(vehicle))).length;
    $('trackingClear').hidden = !$('trackingSearch').value && !$('trackingOperation').value && !$('trackingStatus').value;
    renderList(list);
    renderDetails();
    renderMap();
  }
  function setView(view) {
    stopPlayback();
    state.playIndex = 0;
    state.view = view;
    document.querySelectorAll('.tracking-module-tabs button').forEach((button) => {
      button.classList.toggle('is-active', view === button.dataset.view);
      button.classList.toggle('active', view === button.dataset.view);
      button.setAttribute('aria-pressed', String(view === button.dataset.view));
    });
    renderMap();
  }
  $('trackingSearch').addEventListener('input', render);
  ['trackingOperation', 'trackingStatus'].forEach((id) => $(id).addEventListener('change', render));
  $('trackingClear').addEventListener('click', () => {
    ['trackingSearch', 'trackingOperation', 'trackingStatus'].forEach((id) => { $(id).value = ''; });
    render();
    $('trackingSearch').focus();
  });
  $('trackingFit').addEventListener('click', fitMap);
  document.querySelectorAll('.tracking-module-tabs button').forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));
  $('trackingHistoryDate').addEventListener('change', () => { stopPlayback(); state.playIndex = 0; renderMap(); });
  $('trackingPlay').addEventListener('click', () => state.playTimer ? stopPlayback() : startPlayback());
  $('trackingPlaybackRange').addEventListener('input', () => { stopPlayback(); state.playIndex = Number($('trackingPlaybackRange').value); renderMap(); });
  $('trackingPlaybackSpeed').addEventListener('change', () => { if (state.playTimer) { stopPlayback(); startPlayback(); } });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopPlayback(); });
  window.addEventListener('pagehide', stopPlayback);
  $('trackingDemo').addEventListener('click', () => {
    state.demo = !state.demo;
    state.selected = null;
    page.classList.toggle('is-demo', state.demo);
    $('trackingDemo').setAttribute('aria-pressed', String(state.demo));
    $('trackingDemo').textContent = state.demo ? 'Voltar à minha frota' : 'Explorar demonstração';
    updateNotice();
    $('trackingRefresh').disabled = state.demo;
    ['trackingSearch', 'trackingOperation', 'trackingStatus'].forEach((id) => { $(id).value = ''; });
    $('trackingHistoryDate').value = today;
    state.view = 'positions';
    fillOperations();
    feedback('');
    render();
    setView('positions');
  });
  $('trackingRefresh').addEventListener('click', async () => {
    if (state.busy || state.demo) return;
    state.busy = true;
    $('trackingRefresh').disabled = true;
    $('trackingDemo').disabled = true;
    $('trackingRefresh').textContent = 'Atualizando…';
    page.setAttribute('aria-busy', 'true');
    feedback('');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(page.dataset.url, { headers: { Accept: 'application/json' }, credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('response');
      const data = await response.json();
      if (!Array.isArray(data.vehicles) || !data.integration) throw new Error('payload');
      state.live = data;
      fillOperations();
      render();
      updateNotice();
      feedback(isFixtureData() ? 'Fixture do Neon atualizado no painel.' : hasConnectedData() ? 'Frota atualizada com dados recebidos.' : 'Frota atualizada. O rastreamento continua aguardando conexão.');
    } catch (_) {
      feedback('Não foi possível atualizar o painel. Os dados anteriores foram mantidos. Tente novamente; se sua sessão expirou, entre no sistema.', true);
    } finally {
      clearTimeout(timeout);
      state.busy = false;
      $('trackingRefresh').disabled = false;
      $('trackingDemo').disabled = false;
      $('trackingRefresh').replaceChildren(node('i', 'bi bi-arrow-clockwise'), document.createTextNode(' Atualizar painel'));
      page.setAttribute('aria-busy', 'false');
    }
  });
  document.addEventListener('googlemaps:ready', () => {
    if (state.demo || state.provider === 'google') return;
    if (state.map && state.provider === 'leaflet' && typeof state.map.remove === 'function') state.map.remove();
    state.map = null;
    state.markers = null;
    state.provider = null;
    renderMap();
  });
  fillOperations();
  updateNotice();
  render();
})();
