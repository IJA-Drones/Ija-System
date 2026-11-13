(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const numeric = (value) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const number = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
  const date = new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'medium' });
  const when = (value) => Number.isFinite(Date.parse(value)) ? date.format(new Date(value)) : '—';
  const ignition = (value) => ({ 0: 'Desligada', 1: 'Ligada' })[value] || 'Não informada';
  const duration = (milliseconds) => {
    const seconds = Math.max(0, Math.round(milliseconds / 1000));
    return `${Math.floor(seconds / 3600) ? `${Math.floor(seconds / 3600)}h ` : ''}${Math.floor(seconds / 60) % 60}min ${seconds % 60}s`;
  };
  const node = (tag, className, text) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const meters = (a, b) => Math.hypot((a.lat - b.lat) * 111320, (a.lng - b.lng) * 111320 * Math.cos(a.lat * Math.PI / 180));
  const stopCache = new WeakMap();
  function stops(points, threshold = 300) {
    const cached = stopCache.get(points);
    if (cached?.threshold === threshold) return cached.stops;
    const result = [];
    let current = null;
    function finish() {
      if (current && Date.parse(points[current.end].reported_at) - Date.parse(points[current.start].reported_at) >= 60000) result.push(current);
      current = null;
    }
    points.forEach((point, index) => {
      if (!numeric(point.speed_kmh) || Number(point.speed_kmh) > 1 || Number(point.speed_kmh) < 0) { finish(); return; }
      const elapsed = index ? Date.parse(point.reported_at) - Date.parse(points[index - 1].reported_at) : 0;
      if (current && ((point.geometry_break_before ?? point.break_before) || elapsed <= 0 || elapsed > threshold * 1000 || meters(points[current.start], point) > 40)) finish();
      if (!current) current = { start: index, end: index };
      else current.end = index;
    });
    finish();
    stopCache.set(points, { threshold, stops: result });
    return result;
  }
  function sampleIndices(points, maximum = 80) {
    const indices = [];
    for (let i = 0; i < points.length; i += Math.max(1, Math.ceil(points.length / maximum))) indices.push(i);
    if (points.length && indices[indices.length - 1] !== points.length - 1) indices.push(points.length - 1);
    return indices;
  }
  function nearestIndex(points, location) {
    let best = 0, distance = Infinity;
    points.forEach((point, index) => { const value = meters(point, location); if (value < distance) { best = index; distance = value; } });
    return best;
  }
  let current, token = 0, panorama;
  function field(container, label, value) {
    const item = node('div', 'tracking-point-field');
    item.append(node('span', '', label), node('strong', '', value));
    container.append(item);
  }
  function showInfo() {
    $('trackingPointInfo').hidden = false; $('trackingPointStreet').hidden = true;
    $('trackingPointInfoTab').setAttribute('aria-pressed', 'true'); $('trackingPointStreetTab').setAttribute('aria-pressed', 'false');
    panorama?.setVisible(false);
  }
  function close() { $('trackingPointModal').close(); }
  function open(context) {
    current = context; token += 1;
    const { vehicle, points, index, daily } = context;
    const point = points[index];
    if (!point) return;
    $('trackingPointTitle').textContent = `${vehicle.plate} · ${vehicle.model}`;
    $('trackingPointTime').textContent = `${when(point.reported_at)} · ${context.isDemo ? 'Dados fictícios' : 'Leitura GPS registrada'}`;
    const grid = $('trackingPointFields'); grid.replaceChildren();
    field(grid, 'Velocidade', numeric(point.speed_kmh) ? `${number.format(point.speed_kmh)} km/h` : 'Não informada');
    field(grid, 'Ignição', ignition(point.ignition));
    field(grid, 'Hodômetro GPS', numeric(point.odometer_km) ? `${number.format(point.odometer_km)} km` : 'Não informado');
    field(grid, 'Condutor registrado no turno', point.driver_name || 'Não identificado neste ponto');
    field(grid, 'Piloto titular atual do PLOA', vehicle.ploa_driver?.name || 'Não vinculado');
    field(grid, 'Responsável cadastrado', vehicle.responsible || 'Não informado');
    field(grid, 'Equipe / PLOA', vehicle.team || 'Sem equipe');
    field(grid, 'Coordenadas GPS', `${Number(point.lat).toFixed(6)}, ${Number(point.lng).toFixed(6)}`);
    const log = daily?.logs?.find((item) => item.id === point.log_id);
    $('trackingPointLog').hidden = !log?.url;
    if (log?.url) $('trackingPointLog').href = log.url;
    else $('trackingPointLog').removeAttribute('href');
    $('trackingPointMapLink').href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${point.lat},${point.lng}`)}`;
    $('trackingPointStreetLink').href = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${encodeURIComponent(`${point.lat},${point.lng}`)}`;
    const stop = stops(points, daily?.gap_threshold_seconds || 300).find((item) => item.start <= index && item.end >= index);
    const section = $('trackingPointStop'); section.replaceChildren();
    if (stop) {
      const begin = points[stop.start], end = points[stop.end];
      section.append(node('h4', '', 'Parada observada'));
      const summary = node('div', 'tracking-point-grid');
      field(summary, 'Início observado', when(begin.reported_at)); field(summary, 'Fim observado', when(end.reported_at));
      field(summary, 'Duração observada', duration(Date.parse(end.reported_at) - Date.parse(begin.reported_at)));
      section.append(summary);
      const totals = { on: 0, off: 0, unknown: 0 }, timeline = node('div', 'tracking-stop-timeline');
      for (let i = stop.start + 1; i <= stop.end; i += 1) {
        const a = points[i - 1], b = points[i], elapsed = Date.parse(b.reported_at) - Date.parse(a.reported_at);
        const kind = a.ignition === 1 && b.ignition === 1 ? 'on' : a.ignition === 0 && b.ignition === 0 ? 'off' : 'unknown';
        totals[kind] += elapsed;
        const segment = node('span', `is-${kind}`); segment.style.flexGrow = elapsed;
        segment.title = `${when(a.reported_at)} a ${when(b.reported_at)} · ${kind === 'on' ? 'Ignição ligada' : kind === 'off' ? 'Ignição desligada' : 'Ignição não determinada'}`;
        timeline.append(segment);
      }
      timeline.setAttribute('aria-label', 'Intervalos observados da ignição durante a parada');
      section.append(timeline);
      const times = node('div', 'tracking-stop-times');
      [['Ligada', totals.on], ['Desligada', totals.off], ['Não determinada', totals.unknown]].forEach(([label, value]) => times.append(node('span', '', `${label}: ${duration(value)}`)));
      section.append(times, node('p', 'tracking-point-note', 'Duração entre leituras observadas, sem incluir lacunas de comunicação. Não comprova a chegada ou a saída exata do local.'));
    } else section.append(node('p', 'tracking-point-note', 'Sem parada contínua de pelo menos 1 minuto identificada nesta leitura.'));
    const nearby = $('trackingPointNearby'); nearby.replaceChildren();
    for (let i = Math.max(0, index - 4); i <= Math.min(points.length - 1, index + 4); i += 1) {
      const reading = points[i], button = node('button', i === index ? 'is-selected' : '', `${when(reading.reported_at)} · ${numeric(reading.speed_kmh) ? `${number.format(reading.speed_kmh)} km/h` : 'Velocidade não informada'} · ${ignition(reading.ignition)}`);
      button.type = 'button'; button.addEventListener('click', () => context.onSelect(i)); nearby.append(button);
    }
    $('trackingPointPlay').disabled = points.length < 2;
    showInfo(); $('trackingPointStreetStatus').textContent = 'Abra o Street View para consultar as imagens disponíveis perto desta leitura.';
    if (!$('trackingPointModal').open) $('trackingPointModal').showModal();
  }
  async function showStreet() {
    if (!current) return;
    const requested = ++token, point = current.points[current.index];
    $('trackingPointInfo').hidden = true; $('trackingPointStreet').hidden = false;
    $('trackingPointInfoTab').setAttribute('aria-pressed', 'false'); $('trackingPointStreetTab').setAttribute('aria-pressed', 'true');
    $('trackingPointStreetStatus').textContent = 'Procurando imagens próximas no Google Street View…';
    $('trackingStreetCanvas').hidden = true;
    const timeout = setTimeout(() => { if (requested === token) $('trackingPointStreetStatus').textContent = 'O Google Street View está demorando para responder. Você pode abrir o local pelo link abaixo.'; }, 12000);
    try {
      if (!window.google?.maps || window.__GOOGLE_MAPS_AUTH_FAILED__) throw new Error('maps');
      if (!google.maps.StreetViewService || !google.maps.StreetViewPanorama) await google.maps.importLibrary('streetView');
      if (requested !== token || !$('trackingPointModal').open) return;
      const service = new google.maps.StreetViewService();
      const request = service.getPanorama({ location: { lat: point.lat, lng: point.lng }, radius: 80 }, (data, status) => {
        clearTimeout(timeout);
        if (requested !== token || !$('trackingPointModal').open) return;
        if (status !== 'OK' || !data?.location?.pano) {
          $('trackingPointStreetStatus').textContent = 'Não há imagens disponíveis próximas desta leitura, ou o serviço está indisponível. Você pode abrir o local no Google Maps.';
          return;
        }
        $('trackingStreetCanvas').hidden = false;
        if (!panorama) panorama = new google.maps.StreetViewPanorama($('trackingStreetCanvas'), { visible: false, motionTracking: false, motionTrackingControl: false, fullscreenControl: true });
        panorama.setPano(data.location.pano); panorama.setVisible(true);
        google.maps.event.trigger(panorama, 'resize');
        $('trackingPointStreetStatus').textContent = data.location.description || 'Imagem disponível próxima ao ponto selecionado.';
      });
      request?.catch(() => {}); // Callback reports provider status, including ZERO_RESULTS.
    } catch (_) {
      clearTimeout(timeout);
      if (requested === token) $('trackingPointStreetStatus').textContent = 'Street View indisponível nesta conexão. Use o link para abrir a posição no Google Maps.';
    }
  }
  $('trackingPointClose')?.addEventListener('click', close);
  $('trackingPointInfoTab')?.addEventListener('click', () => { token += 1; showInfo(); });
  $('trackingPointStreetTab')?.addEventListener('click', showStreet);
  $('trackingPointPlay')?.addEventListener('click', () => { const context = current; close(); context?.onPlay(context.index); });
  $('trackingPointModal')?.addEventListener('close', () => { token += 1; panorama?.setVisible(false); });
  window.IjaTrackingDetails = { open, close, stops, sampleIndices, nearestIndex };
})();
