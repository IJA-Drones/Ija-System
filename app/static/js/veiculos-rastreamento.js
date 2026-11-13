(() => {
  'use strict';
  const page = document.getElementById('trackingPage');
  if (!page) return;
  const $ = (id) => document.getElementById(id);
  const initial = JSON.parse($('trackingData').textContent);
  const statusLabels = { moving: 'Em movimento', stopped: 'Parado', stale: 'Posição antiga', pending: 'Sem posição' };
  const number = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
  const dateTime = new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short' });
  const dayFormatter = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit' });
  const dayParts = dayFormatter.formatToParts(new Date());
  const part = (name) => dayParts.find((item) => item.type === name).value;
  const today = `${part('year')}-${part('month')}-${part('day')}`;
  const state = { live: initial, demo: false, selected: null, view: 'history', map: null, provider: null, markers: null, googleMarkers: [], googleOverlays: [], bounds: [], busy: false, playIndex: 0, playTimer: null, period: null, requestId: 0 };
  const historyChecks = new Map();
  const savedRoutes = new Map();
  const historyKey = (id = state.selected, period = state.period) => `${id}:${period.start}:${period.end}`;
  const needsHistory = () => ['history', 'playback', 'telemetry', 'comparison', 'reports'].includes(state.view);
  const isFixtureData = () => !state.demo && state.live.integration?.status === 'test';
  const hasConnectedData = () => !state.demo && ['test', 'connected'].includes(state.live.integration?.status);
  const normalize = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const numeric = (value) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const km = (value) => numeric(value) ? `${number.format(Number(value))} km` : '—';
  const when = (value) => value && Number.isFinite(Date.parse(value)) ? dateTime.format(new Date(value)) : '—';
  const dailyFor = (vehicle) => !state.demo && vehicle ? savedRoutes.get(historyKey(vehicle.id))?.daily : null;
  const driverName = (vehicle) => vehicle?.ploa_driver?.name || 'Sem piloto titular no PLOA';
  const speedText = (vehicle) => numeric(vehicle?.position?.speed_kmh) ? `${number.format(vehicle.position.speed_kmh)} km/h${status(vehicle) === 'stale' ? ' · última leitura' : ''}` : '—';
  const reasons = { open: 'Turno em andamento; aguarde o fechamento.', unknown_end: 'Log antigo sem horário de fechamento.', invalid_log: 'Horário ou quilometragem inválidos no log.', crosses_day: 'Turno atravessa a meia-noite; amplie o período.', outside_period: 'O período selecionado cobre somente parte deste turno.', demo: 'Dados fictícios não conferem logs reais.', no_gps: 'Sem amostras suficientes no período do turno.', partial_gps: 'Cobertura parcial ou leituras inconsistentes no período.', estimated_gps: 'Distância estimada entre coordenadas; sem odômetro para conferir.', overlap: 'Turnos sobrepostos; confira os registros.' };
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
  state.period = initial.history_period || { start: `${initial.history_date || today}T00:00`, end: `${initial.history_date || today}T23:59` };
  $('trackingPeriodStart').value = state.period.start;
  $('trackingPeriodEnd').value = state.period.end;
  $('trackingPeriodStart').max = $('trackingPeriodEnd').max = `${today}T23:59`;
  function saveRoutes(data) {
    const period = data.history_period || { start: `${data.history_date}T00:00`, end: `${data.history_date}T23:59` };
    (data.vehicles || []).forEach((vehicle) => {
      if (vehicle.history_loaded !== false) savedRoutes.set(historyKey(vehicle.id, period), { history: vehicle.history || [], daily: vehicle.daily });
    });
    while (savedRoutes.size > 24) savedRoutes.delete(savedRoutes.keys().next().value);
  }
  saveRoutes(initial);

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
      (!search || normalize([vehicle.plate, vehicle.model, vehicle.team, vehicle.responsible, vehicle.ploa_driver?.name, vehicle.driver?.name, ...(dailyFor(vehicle)?.logs || []).map((log) => log.driver?.name)].join(' ')).includes(search)) &&
      (!operation || vehicle.operation === operation) && (!situation || status(vehicle) === situation)
    );
  }
  function selectedVehicle() { return filteredVehicles().find((vehicle) => vehicle.id === state.selected); }
  function routeData(vehicle) {
    if (!vehicle) return [];
    const history = state.demo ? vehicle.history : savedRoutes.get(historyKey(vehicle.id))?.history;
    if (!history) return [];
    const selectedDay = `${state.period.start}:${state.period.end}`;
    const cache = state.routeCache;
    if (cache && cache.history === history && cache.day === selectedDay && cache.demo === state.demo && cache.log === state.logFilter) return cache.points;
    const points = history.map((point, index) => {
      if (Array.isArray(point)) return { lat: Number(point[0]), lng: Number(point[1]), speed_kmh: demoSpeeds[index], reported_at: new Date(Date.parse(`${today}T08:00:00-03:00`) + index * 60000).toISOString(), is_demo: true, driver_name: 'Condutor de demonstração' };
      return { ...point, lat: Number(point.lat), lng: Number(point.lng) };
    }).filter((point) => {
      if (state.logFilter && point.log_id !== state.logFilter) return false;
      if (!Number.isFinite(point.lat) || !Number.isFinite(point.lng)) return false;
      const date = new Date(point.reported_at);
      if (!Number.isFinite(date.getTime())) return false;
      if (!state.demo) return true; // The server filtered this exact cached interval.
      return date.getTime() >= Date.parse(`${state.period.start}-03:00`) && date.getTime() < Date.parse(`${state.period.end}-03:00`) + 60000;
    });
    state.routeCache = { history, day: selectedDay, demo: state.demo, log: state.logFilter, points };
    return points;
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
    const sync = state.live.integration?.sync;
    if (sync?.error) {
      $('trackingNoticeTitle').textContent = 'Atualização do rastreamento indisponível';
      $('trackingNoticeText').textContent = 'Não foi possível consultar novas posições. As últimas informações recebidas foram mantidas; confira o horário de cada veículo.';
      return;
    }
    $('trackingNoticeTitle').textContent = hasConnectedData() ? 'Rastreamento conectado' : 'Aguardando posições';
    $('trackingNoticeText').textContent = hasConnectedData()
      ? `Posições recebidas da OLLOG / RedGPS.${sync?.enabled ? ` Atualização automática a cada ${sync.poll_interval_seconds} segundos enquanto este painel estiver aberto.` : ''} Os trajetos reúnem os pontos coletados pelo IJA System.`
      : 'Os veículos sem localização recebida permanecem na lista como “Sem posição”.';
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
      bottom.append(node('span', `badge tracking-badge ${situation}`, statusLabels[situation]), node('span', '', speedText(vehicle)));
      button.append(top, node('span', 'tracking-vehicle-model', `${vehicle.model} · ${vehicle.team}`), node('span', 'tracking-vehicle-driver', `Condutor: ${state.demo ? 'Fictício · demonstração' : driverName(vehicle)}`), node('span', 'tracking-vehicle-responsible', `Responsável: ${state.demo ? 'Fictício · demonstração' : vehicle.responsible || 'Não informado'}`), bottom);
      button.addEventListener('click', () => selectVehicle(vehicle.id));
      fragment.append(button);
    });
    if (!list.length) fragment.append(node('p', 'tracking-list-message', vehicles().length ? 'Nenhum veículo encontrado. Experimente ajustar os filtros.' : 'Nenhum veículo disponível para o seu acesso.'));
    $('trackingVehicleList').replaceChildren(fragment);
  }
  function selectVehicle(id) {
    cancelRouteRequests();
    stopPlayback();
    state.playIndex = 0;
    state.logFilter = null;
    state.selected = id;
    state.fleetExpanded = false;
    $('trackingFleetBody').classList.add('is-collapsed');
    $('trackingFleetToggle').setAttribute('aria-expanded', 'false');
    document.querySelectorAll('.tracking-vehicle').forEach((button) => {
      button.classList.toggle('is-selected', button.dataset.vehicleId === id);
      button.setAttribute('aria-pressed', String(button.dataset.vehicleId === id));
    });
    if (state.view === 'positions') setView('history');
    else { renderDetails(); renderMap(true); ensureRoute(); }
  }
  function renderDetails() {
    const vehicle = selectedVehicle();
    const p = vehicle && vehicle.position;
    const situation = vehicle ? status(vehicle) : 'pending';
    $('trackingFleetSelection').textContent = vehicle ? `${vehicle.plate} · ${vehicle.model}` : 'Selecione um veículo';
    $('trackingDetailTitle').textContent = vehicle ? `${vehicle.plate} · ${vehicle.model}` : 'Selecione um veículo';
    $('trackingDetailSubtitle').textContent = vehicle ? `${vehicle.team} · ${vehicle.operation || 'Sem operação'}` : 'Consulte a localização e as informações da frota.';
    $('trackingDetailStatus').textContent = statusLabels[situation];
    $('trackingDetailStatus').className = `badge tracking-badge ${situation}`;
    $('detailSpeed').textContent = speedText(vehicle);
    $('detailSpeedLabel').textContent = situation === 'stale' ? 'Velocidade na última leitura' : 'Velocidade atual';
    $('trackingResponsibleName').textContent = vehicle ? (state.demo ? 'Responsável fictício · demonstração' : vehicle.responsible || 'Não informado') : '—';
    $('trackingDriverName').textContent = vehicle ? (state.demo ? 'Condutor fictício · demonstração' : driverName(vehicle)) : 'Selecione um veículo';
    $('trackingDriverMeta').textContent = state.demo ? 'Identificação ilustrativa para explorar o rastreamento.' : vehicle?.ploa_driver ? `Piloto titular do ${vehicle.team}${vehicle.driver_conflict ? ' · Há turnos sobrepostos; confira os logs.' : vehicle.driver ? ` · Turno aberto: log #${vehicle.driver.log_id}` : ' · Sem turno aberto'}. A reprodução usa a identificação registrada em cada turno.` : 'Vincule um piloto titular ao PLOA do veículo para identificar o condutor.';
    renderDaySummary(vehicle);
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
  function renderDaySummary(vehicle) {
    const section = $('trackingDaySummary');
    section.replaceChildren();
    if (!vehicle) {
      section.append(node('p', '', 'Selecione um veículo para consultar o resumo do período.'));
      return;
    }
    const daily = dailyFor(vehicle);
    if (!daily) {
      section.append(node('p', '', state.demo ? 'Demonstração fictícia. A conferência de logs utiliza os dados da sua frota.' : 'Consultando os trajetos salvos para este período…'));
      return;
    }
    [['Distância GPS', km(daily.distance_km), daily.distance_source === 'estimated' ? 'Estimativa entre coordenadas' : 'Soma dos trechos observados'], ['Distância nos logs', km(daily.recorded_km), 'Turnos completos dentro do período'], ['Velocidade máxima', numeric(daily.max_speed_kmh) ? `${number.format(daily.max_speed_kmh)} km/h` : '—', `${daily.sample_count} amostras recebidas`], ['Conferência dos turnos', `${daily.differences} diferença(s)`, `${daily.logs.filter((log) => log.comparison === 'inconclusive').length} inconclusivo(s)`]].forEach(([label, value, note]) => {
      const card = node('div');
      card.append(node('span', '', label), node('strong', '', value), node('small', '', note));
      section.append(card);
    });
    const coverage = node('details', 'tracking-coverage');
    coverage.append(node('summary', '', `Cobertura do período · ${daily.sample_count} amostras · ${daily.gaps || 0} lacuna(s)`), node('p', '', `Janela observada: ${when(daily.first_at)} a ${when(daily.last_at)} · ${daily.invalid_segments || 0} trecho(s) inconsistente(s). Posição e condutor acima são atuais; o resumo corresponde ao período escolhido. Lacunas podem indicar trechos sem cobertura GPS.`));
    section.append(coverage);
  }
  function renderPlaybackDetails(point) {
    if (!point) return;
    $('detailSpeedLabel').textContent = 'Velocidade no ponto do Flashback';
    $('detailSpeed').textContent = numeric(point.speed_kmh) ? `${number.format(point.speed_kmh)} km/h` : '—';
    $('detailIgnition').textContent = ({ 0: 'Desligada', 1: 'Ligada', 2: 'Desconhecida' })[point.ignition] || 'Desconhecida';
    $('detailGpsKm').textContent = km(point.odometer_km);
    $('trackingDetailSubtitle').textContent = `Flashback · ${point.driver_name || 'Condutor não identificado'}${point.log_id ? ` · Log #${point.log_id}` : ''}`;
    $('trackingDetailStatus').textContent = 'Ponto do histórico';
    $('trackingDetailStatus').className = 'badge tracking-badge';
    $('detailAddress').textContent = `${Number(point.lat).toFixed(6)}, ${Number(point.lng).toFixed(6)}`;
    $('detailReportedAt').textContent = `Ponto reproduzido: ${when(point.reported_at)}${state.demo || point.is_demo ? ' · Fictício' : ''}`;
  }
  function renderComparison(panel, vehicle) {
    const daily = dailyFor(vehicle);
    if (!daily) { panel.append(node('p', '', 'Selecione um veículo e atualize a data para consultar os logs.')); return; }
    panel.append(node('p', '', 'Cada turno é associado aos pontos do mesmo veículo, entre a abertura e o fechamento. A diferença é KM GPS menos KM informado. A tolerância é o maior valor entre 2 km e 5% do percurso declarado.'));
    if (daily.unlinked_samples) panel.append(node('p', 'alert alert-warning', `${daily.unlinked_samples} amostra(s) sem turno vinculado. Confira se os logs foram registrados. Isso também pode ocorrer em logs antigos sem horário de fechamento.`));
    if (!daily.logs.length) { panel.append(node('p', 'alert alert-light border', 'Nenhum log relacionado a este veículo na data selecionada.')); return; }
    const wrap = node('div', 'table-responsive');
    const table = node('table', 'table align-middle tracking-comparison-table');
    const head = node('thead');
    const headings = node('tr');
    ['Turno / condutor', 'Período', 'KM informado', 'KM GPS no turno', 'Conferência', 'Consultar'].forEach((label) => headings.append(node('th', '', label)));
    head.append(headings);
    const body = node('tbody');
    daily.logs.forEach((log) => {
      const row = node('tr');
      const identity = node('td');
      identity.append(node('strong', '', `#${log.id} · ${log.driver.name || 'Condutor não informado'}`), node('small', '', log.status === 'open' ? 'Turno aberto' : 'Turno encerrado'));
      const period = node('td', '', when(log.started_at));
      period.append(node('small', '', log.ended_at ? `Até ${when(log.ended_at)}` : 'Fechamento não registrado'));
      const result = node('td');
      const label = log.comparison === 'difference' ? 'Diferença identificada' : log.comparison === 'within_tolerance' ? 'Dentro da tolerância' : 'Inconclusivo';
      result.append(node('strong', log.comparison === 'difference' ? 'text-danger' : '', label), node('small', '', log.reason ? reasons[log.reason] : `${km(log.difference_km)} · tolerância ${km(log.tolerance_km)}`));
      const actions = node('td');
      const routeButton = node('button', 'btn btn-sm btn-outline-primary', 'Ver trecho');
      routeButton.type = 'button';
      routeButton.disabled = !savedRoutes.get(historyKey(vehicle.id))?.history.some((point) => point.log_id === log.id);
      routeButton.addEventListener('click', () => { state.logFilter = log.id; setView('history'); });
      actions.append(routeButton);
      if (log.url) { const link = node('a', 'd-block mt-2', 'Abrir log'); link.href = log.url; actions.append(link); }
      row.append(identity, period, node('td', '', km(log.recorded_km)), node('td', '', km(log.gps.distance_km)), result, actions);
      body.append(row);
    });
    table.append(head, body); wrap.append(table); panel.append(wrap);
  }
  function ensureMap() {
    if (state.map) return true;
    if (!window.__GOOGLE_MAPS_AUTH_FAILED__ && window.google?.maps?.Map) {
      state.provider = 'google';
      state.map = new google.maps.Map($('trackingMap'), {
        center: { lat: -23.566, lng: -46.655 },
        zoom: 12,
        maxZoom: 19,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        gestureHandling: 'cooperative',
        styles: [{ featureType: 'poi', stylers: [{ visibility: 'off' }] }],
      });
      if (window.ResizeObserver) {
        const map = state.map;
        state.mapObserver = new ResizeObserver(() => { if (state.map === map) google.maps.event.trigger(map, 'resize'); });
        state.mapObserver.observe($('trackingMap'));
      }
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
    if (window.ResizeObserver) {
      const map = state.map;
      state.mapObserver = new ResizeObserver(() => { if (state.map === map) map.invalidateSize(); });
      state.mapObserver.observe($('trackingMap'));
    }
    return true;
  }
  function fitMap() {
    if (!state.map || !state.bounds.length) return;
    if (state.provider === 'google') {
      const bounds = new google.maps.LatLngBounds();
      const points = state.bounds.map((point) => ({ lat: Number(Array.isArray(point) ? point[0] : point.lat), lng: Number(Array.isArray(point) ? point[1] : point.lng) }));
      points.forEach((point) => bounds.extend(point));
      if (points.every((point) => Math.abs(point.lat - points[0].lat) < .0005 && Math.abs(point.lng - points[0].lng) < .0005)) {
        state.map.setCenter(points[0]);
        state.map.setZoom(14);
      } else state.map.fitBounds(bounds, 48);
      return;
    }
    state.map.fitBounds(state.bounds, { padding: [55, 55], maxZoom: 14, animate: false });
  }
  function clearMapLayers() {
    state.playbackMarker = null;
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
  function openRoutePoint(index) {
    const vehicle = selectedVehicle(), points = routeData(vehicle);
    if (!vehicle || !points[index]) return;
    stopPlayback();
    window.IjaTrackingDetails?.open({ vehicle, points, index, daily: dailyFor(vehicle), isDemo: state.demo || isFixtureData(),
      onSelect: openRoutePoint,
      onPlay: (from) => { setView('playback'); state.playIndex = from; updatePlaybackFrame(); startPlayback(); },
    });
  }
  function selectNearestRoutePoint(location) {
    const points = routeData(selectedVehicle());
    if (points.length && window.IjaTrackingDetails) openRoutePoint(window.IjaTrackingDetails.nearestIndex(points, location));
  }
  function routePointMarkers() {
    const points = routeData(selectedVehicle());
    return window.IjaTrackingDetails ? { points, indices: window.IjaTrackingDetails.sampleIndices(points), stops: window.IjaTrackingDetails.stops(points, dailyFor(selectedVehicle())?.gap_threshold_seconds || 300).slice(0, 100) } : { points, indices: [], stops: [] };
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
      routeSegments().forEach((segment) => {
        const line = addGoogleOverlay(new google.maps.Polyline({ map: state.map, path: segment.map(([lat, lng]) => ({ lat, lng })), strokeColor: accent, strokeOpacity: state.view === 'playback' ? .65 : .9, strokeWeight: 5 }));
        line.addListener?.('click', (event) => { if (event.latLng) selectNearestRoutePoint({ lat: event.latLng.lat(), lng: event.latLng.lng() }); });
      });
      const selectable = routePointMarkers();
      selectable.indices.forEach((index) => {
        const point = selectable.points[index];
        const marker = new google.maps.Marker({ map: state.map, position: { lat: point.lat, lng: point.lng }, title: `${when(point.reported_at)} · Clique para ver a leitura`, icon: { path: google.maps.SymbolPath.CIRCLE, scale: 3, fillColor: accent, fillOpacity: .8, strokeColor: '#fff', strokeWeight: .5 } });
        marker.addListener('click', () => openRoutePoint(index)); state.googleMarkers.push(marker);
      });
      selectable.stops.forEach((stop, index) => {
        const point = selectable.points[stop.start];
        const marker = new google.maps.Marker({ map: state.map, position: { lat: point.lat, lng: point.lng }, title: `Parada observada ${index + 1} · Clique para ver os detalhes`, label: { text: 'P', color: '#fff', fontSize: '11px', fontWeight: '600' }, icon: { path: google.maps.SymbolPath.CIRCLE, scale: 11, fillColor: '#c57618', fillOpacity: 1, strokeColor: '#fff', strokeWeight: 2 } });
        marker.addListener('click', () => openRoutePoint(stop.start)); state.googleMarkers.push(marker);
      });
      routeSegments().filter((segment) => segment.length === 1).slice(0, 200).forEach(([point]) => {
        state.googleMarkers.push(new google.maps.Marker({ map: state.map, position: { lat: point[0], lng: point[1] }, title: 'Leitura isolada · sem continuidade GPS', icon: { path: google.maps.SymbolPath.CIRCLE, scale: 3, fillColor: accent, fillOpacity: .8, strokeWeight: 0 } }));
      });
      [[route[0], 'Início observado', '#299975'], [route[route.length - 1], 'Fim observado', '#087e91']].forEach(([point, label, color]) => {
        const marker = new google.maps.Marker({ map: state.map, position: { lat: point[0], lng: point[1] }, title: `${label}${state.demo || isFixtureData() ? ' · Fictício' : ''}`, icon: { path: google.maps.SymbolPath.CIRCLE, scale: 7, fillColor: color, fillOpacity: 1, strokeColor: '#fff', strokeWeight: 3 } });
        marker.addListener('click', () => openRoutePoint(label === 'Início observado' ? 0 : route.length - 1)); state.googleMarkers.push(marker);
      });
      if (state.view === 'playback') {
        state.playbackMarker = new google.maps.Marker({ map: state.map, position: { lat: route[state.playIndex][0], lng: route[state.playIndex][1] }, icon: { path: google.maps.SymbolPath.CIRCLE, scale: 10, fillColor: accent, fillOpacity: 1, strokeColor: '#fff', strokeWeight: 3 }, title: 'Ponto do Flashback' });
        state.playbackMarker.addListener('click', () => openRoutePoint(state.playIndex));
        state.googleMarkers.push(state.playbackMarker);
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
        title: `${vehicle.plate} · ${driverName(vehicle)} · ${statusLabels[situation]} · ${speedText(vehicle)}`,
        icon: { path: google.maps.SymbolPath.CIRCLE, scale: vehicle.id === state.selected ? 12 : 9, fillColor: color, fillOpacity: 1, strokeColor: '#fff', strokeWeight: 3 },
      });
      marker.addListener('click', () => selectVehicle(vehicle.id));
      state.googleMarkers.push(marker);
    });
    if (focus && hasPosition(selected)) state.map.setCenter({ lat: Number(selected.position.lat), lng: Number(selected.position.lng) });
  }
  function routeGeometry() {
    const points = routeData(selectedVehicle());
    if (state.geometryCache?.points === points) return state.geometryCache;
    const coordinates = [], segments = [];
    points.forEach((point) => {
      const coordinate = [point.lat, point.lng];
      coordinates.push(coordinate);
      if (!segments.length || (point.geometry_break_before ?? point.break_before)) segments.push([]);
      segments[segments.length - 1].push(coordinate);
    });
    state.geometryCache = { points, coordinates, segments };
    return state.geometryCache;
  }
  function currentRoute() { return routeGeometry().coordinates; }
  function routeSegments() { return routeGeometry().segments; }
  function currentRouteSpeeds() {
    return routeData(selectedVehicle()).map((point) => numeric(point.speed_kmh) ? Number(point.speed_kmh) : null);
  }
  function updatePlaybackFrame() {
    const points = routeData(selectedVehicle());
    state.playIndex = Math.max(0, Math.min(state.playIndex, points.length - 1));
    const point = points[state.playIndex];
    $('trackingPlaybackRange').value = state.playIndex;
    $('trackingPlaybackLabel').textContent = point ? `Ponto ${state.playIndex + 1} de ${points.length} · ${numeric(point.speed_kmh) ? number.format(point.speed_kmh) : '—'} km/h · ${when(point.reported_at)} · ${point.driver_name || 'Condutor não identificado'}${state.demo || isFixtureData() ? ' · Fictício' : ''}${state.playIndex === points.length - 1 ? ' · Fim da reprodução' : ''}` : 'Nenhum trajeto disponível para reprodução.';
    renderPlaybackDetails(point);
    if (point && state.playbackMarker) {
      if (state.provider === 'google') state.playbackMarker.setPosition({ lat: point.lat, lng: point.lng });
      else state.playbackMarker.setLatLng([point.lat, point.lng]);
    }
  }
  function stopPlayback() {
    if (state.playTimer) clearInterval(state.playTimer);
    state.playTimer = null;
    $('trackingPlay').textContent = 'Reproduzir';
    $('trackingPlay').setAttribute('aria-label', 'Reproduzir trajeto');
  }
  function startPlayback() {
    const points = routeData(selectedVehicle());
    if (points.length < 2) return;
    if (state.playIndex >= points.length - 1) state.playIndex = 0;
    const rate = Math.max(1, Number($('trackingPlaybackSpeed').value) || 60);
    const skip = $('trackingSkipGaps').checked;
    const times = [0];
    const gapThreshold = dailyFor(selectedVehicle())?.gap_threshold_seconds || 300;
    for (let i = 1; i < points.length; i += 1) {
      const before = points[i - 1], point = points[i];
      let elapsed = Math.max(0, Date.parse(point.reported_at) - Date.parse(before.reported_at));
      const stationary = before.speed_kmh === 0 && point.speed_kmh === 0 && Math.abs(point.lat - before.lat) < .0002 && Math.abs(point.lng - before.lng) < .0002;
      if (skip && stationary) elapsed = 0;
      else if (skip && elapsed > gapThreshold * 1000) elapsed = Math.min(elapsed, rate * 1000);
      times.push(times[i - 1] + elapsed);
    }
    const startAt = Date.now(), from = times[state.playIndex];
    $('trackingPlay').textContent = 'Pausar';
    $('trackingPlay').setAttribute('aria-label', 'Pausar reprodução');
    state.playTimer = setInterval(() => {
      const until = from + (Date.now() - startAt) * rate;
      const previous = state.playIndex;
      while (state.playIndex + 1 < points.length && times[state.playIndex + 1] <= until) state.playIndex += 1;
      if (state.playIndex >= points.length - 1) stopPlayback();
      if (previous !== state.playIndex) updatePlaybackFrame();
    }, 250);
    updatePlaybackFrame();
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
    const rows = [['Origem', 'Placa', 'Modelo', 'Equipe', 'Operação', 'Responsável cadastrado', 'Condutor do PLOA', 'KM registrado', 'Situação', 'Velocidade no último reporte (km/h)', 'Último reporte']];
    filteredVehicles().forEach((v) => rows.push([state.demo || isFixtureData() ? 'DEMONSTRAÇÃO FICTÍCIA' : 'Cadastro Ija-System / RedGPS', v.plate, v.model, v.team, v.operation, state.demo ? 'Fictício' : v.responsible, state.demo ? 'Fictício' : driverName(v), v.registered_km, statusLabels[status(v)], v.position?.speed_kmh, v.position?.reported_at]));
    download('\uFEFF' + rows.map((row) => row.map(csvCell).join(';')).join('\r\n'), `${state.demo ? 'demonstracao-' : ''}frota-${today}.csv`, 'text/csv;charset=utf-8');
  }
  function exportRoute(format) {
    const route = currentRoute();
    if (!route.length) return;
    if (format === 'kml') {
      const vehicle = selectedVehicle();
      const title = (state.demo || isFixtureData() ? 'DEMONSTRAÇÃO FICTÍCIA · ' : '') + `Trajeto ${vehicle?.plate || ''}`;
      const escapeXml = (text) => text.replace(/[<>&"']/g, (char) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&apos;' }[char]));
      const geometry = routeSegments().map((segment) => `<LineString><tessellate>1</tessellate><coordinates>${segment.map(([lat, lng]) => `${lng},${lat},0`).join(' ')}</coordinates></LineString>`).join('');
      download(`<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>${escapeXml(title)}</name><Placemark><name>Trajeto observado</name><MultiGeometry>${geometry}</MultiGeometry></Placemark></Document></kml>`, `${state.demo || isFixtureData() ? 'demonstracao-' : ''}trajeto-${state.period.start.replace(/:/g, '')}_${state.period.end.replace(/:/g, '')}.kml`, 'application/vnd.google-earth.kml+xml');
    } else {
      const speeds = currentRouteSpeeds();
      const points = routeData(selectedVehicle());
      const rows = [['Origem', 'Ponto', 'Latitude', 'Longitude', 'Velocidade (km/h)', 'Reporte', 'Log', 'Condutor', 'Início de trecho após lacuna'], ...route.map(([lat, lng], index) => [state.demo || points[index].is_demo ? 'DEMONSTRAÇÃO FICTÍCIA' : 'REDGPS', index + 1, lat, lng, speeds[index], points[index].reported_at, points[index].log_id, points[index].driver_name, points[index].break_before ? 'Sim' : 'Não'])];
      download('\uFEFF' + rows.map((row) => row.map(csvCell).join(';')).join('\r\n'), `${state.demo || isFixtureData() ? 'demonstracao-' : ''}trajeto-${state.period.start.replace(/:/g, '')}_${state.period.end.replace(/:/g, '')}.csv`, 'text/csv;charset=utf-8');
    }
  }
  function exportComparison() {
    const vehicle = selectedVehicle();
    const daily = dailyFor(vehicle);
    if (!daily) return;
    const rows = [['Início da consulta', 'Fim da consulta', 'Placa', 'Log', 'Condutor', 'Abertura', 'Fechamento', 'KM informado', 'KM GPS', 'Diferença (GPS - log)', 'Tolerância (km)', 'Resultado', 'Motivo']];
    daily.logs.forEach((log) => rows.push([state.period.start, state.period.end, vehicle.plate, log.id, log.driver.name, log.started_at, log.ended_at, log.recorded_km, log.gps.distance_km, log.difference_km, log.tolerance_km, log.comparison === 'difference' ? 'Diferença identificada' : log.comparison === 'within_tolerance' ? 'Dentro da tolerância' : 'Inconclusivo', reasons[log.reason] || '']));
    download('\uFEFF' + rows.map((row) => row.map(csvCell).join(';')).join('\r\n'), `conferencia-${vehicle.plate}-${state.period.start.replace(/:/g, '')}_${state.period.end.replace(/:/g, '')}.csv`, 'text/csv;charset=utf-8');
  }
  function renderSpeedChart(panel, vehicle) {
    const points = routeData(vehicle);
    if (!points.length) return;
    panel.append(node('h6', 'text-primary mt-4 mb-2', 'Velocidade ao longo do trajeto'));
    const wrap = node('div', 'tracking-speed-chart');
    const svgNode = (tag, attributes = {}, text) => {
      const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
      Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
      if (text !== undefined) element.textContent = text;
      return element;
    };
    const valid = points.filter((point) => numeric(point.speed_kmh) && Number(point.speed_kmh) >= 0);
    if (!valid.length) { panel.append(node('p', 'tracking-panel-caption', 'Não há leituras de velocidade para desenhar o gráfico neste período.')); return; }
    const maximum = valid.reduce((maximum, point) => Math.max(maximum, Number(point.speed_kmh)), 0);
    const ceiling = Math.max(20, Math.ceil(maximum / 20) * 20);
    const first = Date.parse(points[0].reported_at), last = Date.parse(points[points.length - 1].reported_at);
    const clock = new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit', ...(last - first > 86400000 ? { day: '2-digit', month: '2-digit' } : {}) });
    const svg = svgNode('svg', { role: 'img', 'aria-label': `Velocidade em km/h por horário · ${valid.length} leituras · máxima ${number.format(maximum)} km/h`, height: 230 });
    const readout = node('output', 'tracking-chart-readout', `Máxima: ${number.format(maximum)} km/h · ${valid.length} leituras de velocidade`);
    const slider = node('input', 'tracking-chart-scrubber');
    slider.type = 'range'; slider.min = 0; slider.max = valid.length - 1; slider.value = 0;
    slider.setAttribute('aria-label', 'Consultar horário e velocidade de uma leitura do gráfico');
    wrap.append(svg, slider, readout);
    panel.append(wrap, node('p', 'tracking-panel-caption', `${points.length} amostras${state.demo || isFixtureData() ? ' fictícias' : ''} · Horários de Brasília. Lacunas e velocidades ausentes não são ligadas. Arraste o controle para consultar cada leitura.`));
    let cursor, dot, x, y;
    function showReading(index) {
      const point = valid[Math.max(0, Math.min(valid.length - 1, index))];
      if (!point || !cursor) return;
      const label = `${when(point.reported_at)} · ${number.format(point.speed_kmh)} km/h`;
      readout.textContent = label;
      slider.setAttribute('aria-valuetext', label);
      const position = x(Date.parse(point.reported_at));
      cursor.setAttribute('x1', position); cursor.setAttribute('x2', position); cursor.setAttribute('visibility', 'visible');
      dot.setAttribute('cx', position); dot.setAttribute('cy', y(point.speed_kmh)); dot.setAttribute('visibility', 'visible');
    }
    function draw() {
      const width = Math.max(260, wrap.clientWidth || 600), height = 230;
      const left = 44, right = width - 16, top = 24, bottom = height - 32;
      x = (time) => left + (time - first) / Math.max(1, last - first) * (right - left);
      y = (speed) => bottom - Number(speed) / ceiling * (bottom - top);
      svg.replaceChildren(); svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      svg.append(svgNode('text', { x: left, y: 14, class: 'tracking-chart-unit' }, 'km/h'));
      for (let i = 0; i <= 4; i += 1) {
        const value = ceiling * i / 4, position = y(value);
        svg.append(svgNode('line', { x1: left, x2: right, y1: position, y2: position, class: 'tracking-chart-grid' }), svgNode('text', { x: left - 8, y: position + 4, 'text-anchor': 'end' }, number.format(value)));
      }
      const ticks = width < 500 ? 2 : 4;
      for (let i = 0; i <= ticks; i += 1) {
        const time = first + (last - first) * i / ticks;
        svg.append(svgNode('text', { x: x(time), y: height - 8, 'text-anchor': i === 0 ? 'start' : i === ticks ? 'end' : 'middle' }, clock.format(new Date(time))));
      }
      const gap = (dailyFor(vehicle)?.gap_threshold_seconds || 300) * 1000;
      let segment = [];
      function flush() {
        if (!segment.length) return;
        const path = segment.map((point, i) => `${i ? 'L' : 'M'}${x(Date.parse(point.reported_at)).toFixed(1)},${y(point.speed_kmh).toFixed(1)}`).join(' ');
        if (segment.length > 1) {
          const start = x(Date.parse(segment[0].reported_at)), finish = x(Date.parse(segment[segment.length - 1].reported_at));
          svg.append(svgNode('path', { d: `${path} L${finish},${bottom} L${start},${bottom} Z`, class: 'tracking-chart-area' }));
          svg.append(svgNode('path', { d: path, class: 'tracking-chart-line' }));
        } else svg.append(svgNode('circle', { cx: x(Date.parse(segment[0].reported_at)), cy: y(segment[0].speed_kmh), r: 3, class: 'tracking-chart-point' }));
        segment = [];
      }
      points.forEach((point, i) => {
        if (!numeric(point.speed_kmh) || Number(point.speed_kmh) < 0) { flush(); return; }
        if ((point.geometry_break_before ?? point.break_before) || (i && Date.parse(point.reported_at) - Date.parse(points[i - 1].reported_at) > gap)) flush();
        segment.push(point);
      });
      flush();
      cursor = svgNode('line', { y1: top, y2: bottom, class: 'tracking-chart-cursor', visibility: 'hidden' });
      dot = svgNode('circle', { r: 4, class: 'tracking-chart-point', visibility: 'hidden' });
      svg.append(cursor, dot);
    }
    slider.addEventListener('input', () => showReading(Number(slider.value)));
    svg.addEventListener('pointermove', (event) => {
      const box = svg.getBoundingClientRect();
      const target = first + Math.max(0, Math.min(1, (event.clientX - box.left - 44) / Math.max(1, box.width - 60))) * (last - first);
      let low = 0, high = valid.length - 1;
      while (low < high) { const mid = Math.floor((low + high) / 2); if (Date.parse(valid[mid].reported_at) < target) low = mid + 1; else high = mid; }
      slider.value = low; showReading(low);
    });
    draw();
    if (window.ResizeObserver) { state.chartObserver = new ResizeObserver(draw); state.chartObserver.observe(wrap); }
  }
  function renderToolPanel() {
    state.chartObserver?.disconnect();
    const panel = $('trackingToolPanel');
    const vehicle = selectedVehicle();
    panel.replaceChildren();
    const titles = { telemetry: 'Telemetria do veículo', comparison: 'Conferência dos logs do período', alerts: 'Quadro de avisos', reports: 'Relatórios e exportações' };
    if (!titles[state.view]) { panel.hidden = true; return; }
    panel.hidden = false;
    panel.append(node('h5', 'text-primary mb-2', titles[state.view]));
    panel.append(node('p', '', state.view === 'reports' ? 'Exporte a frota filtrada e os pontos do trajeto para análise.' : `${vehicle ? `${vehicle.plate} · ${vehicle.team}` : 'Selecione um veículo na lista.'}${state.demo || isFixtureData() ? ' · Dados fictícios' : ''}`));
    const empty = (text) => panel.append(node('div', 'alert alert-light border text-muted text-center my-4', text));
    if (state.view === 'comparison') {
      renderComparison(panel, vehicle);
    } else if (state.view === 'telemetry') {
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
      const sensors = vehicle.position.telemetry || {};
      const sensorValue = (value, unit = '') => numeric(value) ? `${number.format(value)}${unit}` : '—';
      [['Velocidade no último reporte', speedText(vehicle)], ['Horário do reporte', when(vehicle.position.reported_at)], ['Hodômetro GPS', km(vehicle.position.odometer_km)], ['Ignição', ({0: 'Desligada', 1: 'Ligada', 2: 'Desconhecida'})[vehicle.position.ignition] || 'Desconhecida'], ['Bateria do rastreador (leitura do aparelho)', state.demo ? '84 · fictício' : sensorValue(sensors.gps_battery)], ['Bateria do veículo', state.demo ? '12,7 V · fictício' : sensorValue(sensors.vehicle_battery_v, ' V')], ['Satélites', state.demo ? '15 · fictício' : sensorValue(sensors.satellites)], ['Sinal GSM (leitura do aparelho)', sensorValue(sensors.signal)], ['Condutor informado no rastreador', sensors.device_driver || '—']].forEach(([label, value]) => {
        const row = node('tr');
        row.append(node('td', '', label), node('td', 'fw-semibold', value));
        body.append(row);
      });
      table.append(head, body);
      tableWrap.append(table);
      panel.append(tableWrap);
      renderSpeedChart(panel, vehicle);
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
      report('Pontos do trajeto', 'Coordenadas, horários e velocidade no período selecionado em Rotas percorridas.', 'Exportar CSV do trajeto', () => exportRoute('csv'), currentRoute().length > 0);
      report('Trajeto para mapas', 'Arquivo KML para abrir em ferramentas de análise geográfica.', 'Exportar KML', () => exportRoute('kml'), currentRoute().length > 0);
      report('Conferência GPS × logs', 'Quilometragem por turno, condutor, diferenças e limitações da comparação.', 'Exportar conferência CSV', exportComparison, Boolean(dailyFor(vehicle)?.logs.length));
      panel.append(node('p', 'tracking-panel-caption', state.demo || isFixtureData() ? 'Todos os arquivos deste modo são identificados como dados fictícios.' : 'As exportações de trajetos serão liberadas quando houver histórico disponível.'));
    }
  }
  function renderMap(focus = false) {
    const list = filteredVehicles();
    const selected = selectedVehicle();
    const historyMode = ['history', 'playback'].includes(state.view);
    const areaMode = state.view === 'areas';
    const panelMode = ['telemetry', 'comparison', 'alerts', 'reports'].includes(state.view);
    renderToolPanel();
    ['trackingMapToolbar', 'trackingMapWrap', 'trackingMapLegend'].forEach((id) => { $(id).hidden = panelMode; });
    const route = historyMode ? currentRoute() : [];
    const positionFallback = historyMode && !route.length && hasPosition(selected);
    const located = positionFallback ? [selected] : list.filter(hasPosition);
    const visible = !panelMode && (areaMode ? state.demo : historyMode ? Boolean(route.length) || positionFallback : Boolean(located.length));
    $('trackingHistoryControls').hidden = state.view === 'positions' || areaMode;
    $('trackingHistorySummary').hidden = state.view === 'positions' || areaMode;
    $('trackingDaySummary').hidden = state.view === 'positions' || areaMode;
    $('trackingAllShifts').hidden = !state.logFilter;
    renderHistoryFeedback();
    $('trackingPlayback').hidden = state.view !== 'playback';
    $('trackingPlay').disabled = route.length < 2;
    $('trackingPlaybackRange').disabled = route.length < 2;
    $('trackingPlaybackRange').max = Math.max(0, route.length - 1);
    state.playIndex = Math.min(state.playIndex, Math.max(0, route.length - 1));
    $('trackingPlaybackRange').value = state.playIndex;
    const routeSpeeds = currentRouteSpeeds();
    const playbackPoint = routeData(selected)[state.playIndex];
    if (state.view === 'playback') renderPlaybackDetails(playbackPoint);
    $('trackingPlaybackLabel').textContent = route.length ? `Ponto ${state.playIndex + 1} de ${route.length} · ${routeSpeeds[state.playIndex] ?? '—'} km/h · ${when(playbackPoint?.reported_at)} · ${playbackPoint?.driver_name || 'Condutor não identificado'} · ${state.demo || isFixtureData() ? 'Reprodução fictícia' : 'Reprodução'}` : 'Nenhum trajeto disponível para reprodução. Amplie o período para buscar outras leituras.';
    if (route.length === 1) $('trackingPlaybackLabel').textContent = 'Uma leitura no período. Amplie o intervalo para reproduzir um deslocamento.';
    const mapTitles = { positions: ['Mapa da frota', 'Localização dos veículos filtrados'], history: ['Rotas percorridas', 'Trajeto do veículo no período selecionado'], playback: ['Flashback', 'Reproduza o percurso e acompanhe cada ponto'], areas: ['Áreas de interesse', 'Geocercas e locais de referência para a operação'] };
    const mapTitle = mapTitles[state.view] || ['', ''];
    $('trackingMapTitle').textContent = mapTitle[0];
    $('trackingMapSubtitle').textContent = mapTitle[1];
    $('trackingMapEmpty').hidden = visible;
    $('trackingMap').classList.toggle('is-visible', visible);
    $('trackingMapEmptyTitle').textContent = historyMode ? 'Nenhum trajeto disponível' : (list.length ? 'O próximo destino da sua frota está aqui' : 'Nenhum veículo para mostrar');
    $('trackingMapEmptyText').textContent = historyMode ? (state.demo ? 'Selecione DEMO-01 e a data de hoje para explorar um trajeto fictício.' : 'Ainda não há pontos salvos para este veículo no período selecionado. A atualização é automática.') : (list.length ? 'As posições aparecerão no mapa quando o rastreamento estiver conectado.' : 'Ajuste os filtros ou consulte os veículos disponíveis para o seu acesso.');
    if (areaMode) {
      $('trackingMapEmptyTitle').textContent = 'Áreas de interesse da operação';
      $('trackingMapEmptyText').textContent = 'As geocercas disponíveis aparecerão aqui após a conexão. Explore duas áreas fictícias na demonstração.';
    }
    const dayPoints = routeData(selected);
    $('trackingHistorySummary').textContent = dayPoints.length ? `${dayPoints.length} pontos ${state.demo || isFixtureData() ? 'ilustrativos' : ''} · ${selected?.plate || 'veículo selecionado'}${state.logFilter ? ` · Log #${state.logFilter}` : ''}` : 'Sem pontos para o veículo e o período selecionados.';
    $('trackingMapLabel').textContent = state.demo ? 'Demonstração · dados fictícios' : isFixtureData() ? 'Neon · dados fictícios' : positionFallback ? 'Última posição · sem trajeto no período' : historyMode ? 'RedGPS · trajeto do período' : hasConnectedData() ? 'RedGPS · última posição recebida' : 'Aguardando posições';
    const legend = $('trackingMapLegend');
    legend.replaceChildren();
    const legendItems = positionFallback ? [[status(selected), 'Última leitura recebida']] : historyMode ? [['route-start', 'Início'], ['route-end', 'Fim'], ['route-line', 'Trajeto registrado']] : [['moving', 'Em movimento'], ['stopped', 'Parado'], ['stale', 'Posição antiga']];
    legendItems.forEach(([kind, label]) => {
      const item = node('span');
      item.append(node('i', kind === 'route-line' ? 'tracking-route-line' : `tracking-dot ${kind}`), document.createTextNode(label));
      legend.append(item);
    });
    if (historyMode && route.length) legend.append(node('span', '', 'Clique na linha ou nos pontos para ver detalhes · P: parada observada'));
    legend.append(node('span', 'tracking-legend-note', 'Horários de Brasília'));
    $('trackingFit').disabled = !visible;
    state.bounds = [];
    clearMapLayers();
    if (!visible) { $('trackingMapError').hidden = true; return; }
    if (!ensureMap()) { $('trackingFit').disabled = true; return; }
    $('trackingProvider').textContent = state.provider === 'google' ? 'Google Maps · RedGPS' : 'Mapa alternativo · RedGPS';
    if (state.provider === 'leaflet') state.map.invalidateSize();
    else if (window.google?.maps?.event) google.maps.event.trigger(state.map, 'resize');
    if (state.provider === 'google') {
      renderGoogleMap({ areaMode, historyMode: historyMode && route.length > 0, route, located, selected, focus });
      if (areaMode) {
        state.bounds = [[-23.549, -46.674], [-23.544, -46.650], [-23.558, -46.638], [-23.565, -46.658], [-23.579, -46.657]];
        fitMap();
      } else if (historyMode && route.length) {
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
    } else if (historyMode && route.length) {
      routeSegments().forEach((segment) => L.polyline(segment, { color: '#087e91', weight: 5, opacity: state.view === 'playback' ? .65 : .9 }).on('click', (event) => selectNearestRoutePoint(event.latlng)).addTo(state.markers));
      const selectable = routePointMarkers();
      selectable.indices.forEach((index) => {
        const point = selectable.points[index];
        L.circleMarker([point.lat, point.lng], { radius: 3, color: '#fff', weight: .5, fillColor: '#087e91', fillOpacity: .8 }).bindTooltip(`${when(point.reported_at)} · Clique para ver a leitura`).on('click', () => openRoutePoint(index)).addTo(state.markers);
      });
      selectable.stops.forEach((stop, index) => {
        const point = selectable.points[stop.start];
        L.circleMarker([point.lat, point.lng], { radius: 10, color: '#fff', weight: 2, fillColor: '#c57618', fillOpacity: 1 }).bindTooltip(`Parada observada ${index + 1}`).on('click', () => openRoutePoint(stop.start)).addTo(state.markers);
      });
      if (state.view === 'playback') {
        state.playbackMarker = L.circleMarker(route[state.playIndex], { radius: 10, color: '#fff', weight: 3, fillColor: '#087e91', fillOpacity: 1 }).on('click', () => openRoutePoint(state.playIndex)).addTo(state.markers);
      }
      routeSegments().filter((segment) => segment.length === 1).slice(0, 200).forEach(([point]) => L.circleMarker(point, { radius: 3, stroke: false, fillColor: '#087e91', fillOpacity: .8 }).bindTooltip('Leitura isolada · sem continuidade GPS').addTo(state.markers));
      [[route[0], state.demo || isFixtureData() ? 'Início ilustrativo' : 'Início', '#299975'], [route[route.length - 1], state.demo || isFixtureData() ? 'Fim ilustrativo' : 'Fim', '#087e91']].forEach(([point, label, color]) => {
        L.circleMarker(point, { radius: 7, color: '#fff', weight: 3, fillColor: color, fillOpacity: 1 }).bindTooltip(node('span', '', label)).on('click', () => openRoutePoint(point === route[0] ? 0 : route.length - 1)).addTo(state.markers);
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
        marker.bindTooltip(node('span', '', `${vehicle.plate} · ${driverName(vehicle)} · ${statusLabels[situation]} · ${speedText(vehicle)}`), { direction: 'top', offset: [0, -20] });
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
    if (!list.some((vehicle) => vehicle.id === state.selected)) {
      state.selected = list.length ? list[0].id : null;
      state.logFilter = null;
    }
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
    renderDetails();
    renderMap();
    if (needsHistory()) ensureRoute();
  }
  $('trackingSearch').addEventListener('input', () => { render(); if (needsHistory()) ensureRoute(); });
  ['trackingOperation', 'trackingStatus'].forEach((id) => $(id).addEventListener('change', () => { render(); if (needsHistory()) ensureRoute(); }));
  $('trackingClear').addEventListener('click', () => {
    ['trackingSearch', 'trackingOperation', 'trackingStatus'].forEach((id) => { $(id).value = ''; });
    render();
    $('trackingSearch').focus();
  });
  $('trackingFit').addEventListener('click', fitMap);
  $('trackingFleetToggle').addEventListener('click', () => {
    state.fleetExpanded = !state.fleetExpanded;
    $('trackingFleetBody').classList.toggle('is-collapsed', !state.fleetExpanded);
    $('trackingFleetToggle').setAttribute('aria-expanded', String(state.fleetExpanded));
  });
  document.querySelectorAll('.tracking-module-tabs button').forEach((button) => button.addEventListener('click', () => { state.logFilter = null; setView(button.dataset.view); button.closest?.('details')?.removeAttribute('open'); }));
  $('trackingCompare').addEventListener('click', () => { state.logFilter = null; setView('comparison'); });
  $('trackingAllShifts').addEventListener('click', () => { state.logFilter = null; renderMap(); });
  function applyPeriod() {
    const period = { start: $('trackingPeriodStart').value, end: $('trackingPeriodEnd').value };
    const start = Date.parse(`${period.start}-03:00`), end = Date.parse(`${period.end}-03:00`) + 60000;
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start || end - start > 15 * 86400000 || period.start.slice(0, 10) > today || period.end.slice(0, 10) > today) {
      feedback('Informe um período válido de até 15 dias, com início e fim até hoje.', true);
      return;
    }
    cancelRouteRequests();
    stopPlayback(); state.playIndex = 0; state.logFilter = null; state.period = period;
    feedback(''); renderDetails(); renderMap(); ensureRoute();
  }
  $('trackingApplyPeriod').addEventListener('click', applyPeriod);
  $('trackingToday').addEventListener('click', () => {
    $('trackingPeriodStart').value = `${today}T00:00`; $('trackingPeriodEnd').value = `${today}T23:59`; applyPeriod();
  });
  $('trackingPlay').addEventListener('click', () => state.playTimer ? stopPlayback() : startPlayback());
  $('trackingPlaybackRange').addEventListener('input', () => { stopPlayback(); state.playIndex = Number($('trackingPlaybackRange').value); updatePlaybackFrame(); });
  $('trackingPlaybackSpeed').addEventListener('change', () => { if (state.playTimer) { stopPlayback(); startPlayback(); } });
  $('trackingSkipGaps').addEventListener('change', () => { if (state.playTimer) { stopPlayback(); startPlayback(); } });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopPlayback(); });
  window.addEventListener('pagehide', stopPlayback);
  $('trackingDemo').addEventListener('click', () => {
    state.demo = !state.demo;
    state.selected = null;
    state.logFilter = null;
    page.classList.toggle('is-demo', state.demo);
    $('trackingDemo').setAttribute('aria-pressed', String(state.demo));
    $('trackingDemo').textContent = state.demo ? 'Voltar à minha frota' : 'Explorar demonstração';
    updateNotice();
    $('trackingRefresh').disabled = state.demo;
    ['trackingSearch', 'trackingOperation', 'trackingStatus'].forEach((id) => { $(id).value = ''; });
    state.period = { start: `${today}T00:00`, end: `${today}T23:59` };
    $('trackingPeriodStart').value = state.period.start; $('trackingPeriodEnd').value = state.period.end;
    state.view = 'history';
    fillOperations();
    feedback('');
    render();
    setView('history');
    if (!state.demo) refreshTracking(true);
  });
  function cancelRouteRequests() {
    state.requestController?.abort();
    state.requestId += 1;
    state.busy = false;
    state.importController?.abort();
    if (state.historyBusy) historyChecks.delete(state.historyBusy);
    state.historyBusy = null;
    state.importController = null;
    $('trackingRefresh').disabled = state.demo;
    $('trackingRefresh').replaceChildren(node('i', 'bi bi-arrow-clockwise'), document.createTextNode(' Atualizar'));
  }
  async function ensureRoute(force = false) {
    if (state.demo || !selectedVehicle()) return;
    const key = historyKey();
    if (!savedRoutes.has(key) && !await refreshTracking(true, { cached: true })) return;
    if (key === historyKey()) loadHistory(force);
  }
  function renderHistoryFeedback() {
    const text = historyChecks.get(historyKey())?.text || '';
    $('trackingHistoryFeedback').textContent = text;
    $('trackingHistoryFeedback').hidden = !text || state.demo;
    $('trackingPanelHistoryFeedback').textContent = text;
    $('trackingPanelHistoryFeedback').hidden = !text || state.demo || !['telemetry', 'comparison', 'alerts', 'reports'].includes(state.view);
  }
  async function refreshTracking(automatic = false, { cached = true } = {}) {
    if (state.demo || (automatic && state.playTimer)) return false;
    const key = historyKey();
    const period = { ...state.period };
    const vehicleId = state.selected;
    state.requestController?.abort();
    const controller = new AbortController();
    state.requestController = controller;
    const requestId = ++state.requestId;
    state.busy = true;
    $('trackingRefresh').disabled = true;
    $('trackingRefresh').textContent = 'Atualizando…';
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 15000);
    try {
      const url = new URL(page.dataset.url, window.location.href);
      url.searchParams.set('start', period.start);
      url.searchParams.set('end', period.end);
      if (vehicleId) url.searchParams.set('vehicle_id', vehicleId);
      url.searchParams.set('cached', cached ? '1' : '0');
      const response = await fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('response');
      const data = await response.json();
      if (!Array.isArray(data.vehicles) || !data.integration) throw new Error('payload');
      if (requestId !== state.requestId || key !== historyKey() || state.demo) return false;
      if (state.playTimer) return false; // An in-flight refresh must not stop or replace the active recording.
      saveRoutes(data);
      state.live = data;
      fillOperations(); render(); updateNotice();
      if (data.integration.sync?.error) feedback('As últimas informações recebidas foram mantidas. A atualização das posições está indisponível.', true);
      else if (!automatic) feedback('Painel atualizado.');
      return true;
    } catch (_) {
      if ((!controller.signal.aborted || timedOut) && requestId === state.requestId && key === historyKey()) feedback('Não foi possível consultar o período. Os trajetos já salvos continuam disponíveis.', true);
      return false;
    } finally {
      clearTimeout(timeout);
      if (requestId === state.requestId) {
        state.busy = false;
        $('trackingRefresh').disabled = state.demo;
        $('trackingRefresh').replaceChildren(node('i', 'bi bi-arrow-clockwise'), document.createTextNode(' Atualizar'));
      }
    }
  }
  async function loadHistory(force = false) {
    const vehicle = selectedVehicle();
    if (state.demo || !vehicle || !state.live.integration?.sync?.enabled || !page.dataset.historyUrl) return;
    const key = historyKey();
    if (state.historyBusy === key) return;
    const previous = historyChecks.get(key);
    if (!force && Date.now() - (previous?.at || 0) < 60000) return;
    state.importController?.abort();
    const controller = new AbortController();
    state.importController = controller;
    state.historyBusy = key;
    const period = { ...state.period };
    const attempts = force ? 0 : (previous?.attempts || 0);
    historyChecks.set(key, { at: 0, text: 'Atualizando em segundo plano. Os pontos salvos já estão disponíveis.', attempts });
    renderHistoryFeedback();
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 15000);
    try {
      const response = await fetch(page.dataset.historyUrl, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '' },
        body: JSON.stringify({ vehicle_id: vehicle.id, start: period.start, end: period.end, background: true }),
      });
      if (!response.ok) throw new Error('history');
      const result = await response.json();
      if (controller.signal.aborted) return;
      if (result.busy) {
        historyChecks.set(key, { at: 0, attempts: attempts + 1, text: 'Buscando novas leituras em segundo plano. Exibindo os pontos salvos.' });
        if ((attempts + 1) % 3 === 0 && key === historyKey() && !state.playTimer) await refreshTracking(true, { cached: true });
        if (attempts < 90) setTimeout(() => { if (key === historyKey() && !state.playTimer) loadHistory(); }, Math.min(5000, Number(result.retry_after_ms) || 1500));
      } else {
        const text = !result.vehicles ? 'Não há rastreador vinculado a este veículo.'
          : result.inserted + result.duplicate ? 'Trajeto atualizado e salvo no sistema.'
          : 'Nenhuma posição recebida neste período.';
        historyChecks.set(key, { at: Date.now(), text, attempts: 0 });
        if (key === historyKey() && !state.playTimer) await refreshTracking(true, { cached: true });
      }
    } catch (_) {
      if (controller.signal.aborted && !timedOut) { if (state.importController === controller) historyChecks.delete(key); }
      else historyChecks.set(key, { at: Date.now(), text: 'A atualização está indisponível. Exibindo o trajeto já salvo.' });
    } finally {
      clearTimeout(timeout);
      if (state.importController === controller) {
        state.historyBusy = null;
        renderHistoryFeedback();
      }
    }
  }
  $('trackingRefresh').addEventListener('click', () => refreshTracking().then(() => ensureRoute(true)));
  {
    const interval = Math.max(60, Number(initial.integration?.sync?.poll_interval_seconds) || 60) * 1000;
    setInterval(() => {
      if (!document.hidden && !state.playTimer) refreshTracking(true).then(() => ensureRoute());
    }, interval);
  }
  document.addEventListener('googlemaps:ready', () => {
    if (state.demo || state.provider === 'google') return;
    state.mapObserver?.disconnect();
    if (state.map && state.provider === 'leaflet' && typeof state.map.remove === 'function') state.map.remove();
    state.map = null;
    state.markers = null;
    state.provider = null;
    renderMap();
  });
  document.addEventListener('googlemaps:auth-failed', () => {
    if (state.provider !== 'google') return;
    state.mapObserver?.disconnect();
    clearMapLayers();
    state.map = null;
    state.markers = null;
    state.provider = null;
    $('trackingMap').replaceChildren();
    renderMap();
  });
  const params = new URLSearchParams(window.location.search);
  if (initial.vehicles.some((vehicle) => vehicle.id === params.get('vehicle'))) {
    state.selected = params.get('vehicle');
    const logId = Number(params.get('log'));
    if (initial.vehicles.find((vehicle) => vehicle.id === state.selected)?.daily?.logs.some((log) => log.id === logId)) {
      state.logFilter = logId;
      state.view = 'history';
    }
  }
  if (!state.selected) {
    const withRoute = initial.vehicles.find((vehicle) => vehicle.history?.length);
    const latestPosition = initial.vehicles.filter(hasPosition).sort((a, b) => Date.parse(b.position.reported_at) - Date.parse(a.position.reported_at))[0];
    state.selected = withRoute?.id || latestPosition?.id || null;
  }
  fillOperations();
  updateNotice();
  render();
  setView(state.view);
})();
