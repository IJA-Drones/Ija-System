(() => {
  "use strict";
  const node = document.getElementById("campo-territorio-data");
  if (!node) return;
  const data = JSON.parse(node.textContent);
  const svg = document.getElementById("campo-territorio-svg");
  const detail = document.getElementById("campo-territorio-detalhe");
  const status = document.getElementById("campo-territorio-status");
  const context = data.contexto.features;
  const contextName = data.contexto.metadata?.recorte || "território disponível";
  const features = data.geografia.features;
  const visits = data.pontos;
  const controls = [...document.querySelectorAll("[data-territorial-layer]")];
  const ns = "http://www.w3.org/2000/svg";
  const polygons = geometry => geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  const positions = geometry => polygons(geometry).flat(2);
  const geographicVisits = visits.map(point => [point.longitude, point.latitude]);
  const selectedMunicipalities = context.filter(feature => feature.properties.selecionado);
  let view = !features.length && selectedMunicipalities.length ? "municipio" : "levantamento";
  const mapNode = document.getElementById("campo-territorio-mapa");
  const fallback = document.getElementById("campo-territorio-fallback");
  const streetStatus = document.getElementById("campo-territorio-ruas-status");
  const browser = typeof window === "undefined" ? null : window;
  const streetShapes = [];
  let streetMap, streetInfo, waitTimer;
  const visible = name => controls.find(control => control.dataset.territorialLayer === name)?.checked;
  const number = value => value === null || value === undefined ? "Indisponível" : value.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  const percent = value => value === null || value === undefined ? "Sem dados" : `${number(value)}%`;

  function information(title, lines) {
    const heading = document.createElement("h3"); heading.textContent = title;
    detail.replaceChildren(heading);
    for (const line of lines) { const p = document.createElement("p"); p.textContent = line; detail.append(p); }
  }
  function interactive(element, label, action) {
    element.setAttribute("tabindex", "0"); element.setAttribute("role", "button"); element.setAttribute("aria-label", label);
    const title = document.createElementNS(ns, "title"); title.textContent = label; element.append(title);
    element.addEventListener("click", action);
    element.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); action(); }
    });
  }
  function framePoints() {
    const selected = selectedMunicipalities;
    const plotted = features.flatMap(feature => positions(feature.geometry)).concat(geographicVisits);
    let frame = view === "estado" ? context.flatMap(feature => positions(feature.geometry)) : view === "municipio" ?
      selected.flatMap(feature => positions(feature.geometry)).concat(geographicVisits) :
      (plotted.length ? plotted : (selected.length ? selected : context).flatMap(feature => positions(feature.geometry)));
    if (!frame.length) frame = [[-74, -34], [-34, 6]];
    return frame;
  }
  function draw() {
    const frame = framePoints();
    const west = Math.min(...frame.map(point => point[0])), east = Math.max(...frame.map(point => point[0]));
    const south = Math.min(...frame.map(point => point[1])), north = Math.max(...frame.map(point => point[1]));
    const cosine = Math.cos((south + north) / 2 * Math.PI / 180);
    const width = Math.max((east - west) * cosine, .015), height = Math.max(north - south, .015);
    const scale = Math.min(900 / width, 500 / height);
    const cx = (east + west) / 2, cy = (north + south) / 2;
    const xy = point => [500 + (point[0] - cx) * cosine * scale, 310 - (point[1] - cy) * scale];
    const pathFor = geometry => polygons(geometry).flatMap(polygon => polygon.map(ring =>
      ring.map((point, index) => `${index ? "L" : "M"}${xy(point).map(value => value.toFixed(2)).join(",")}`).join(" ") + " Z")).join(" ");
    svg.replaceChildren();
    for (const feature of context) {
      const props = feature.properties, path = document.createElementNS(ns, "path");
      path.setAttribute("d", pathFor(feature.geometry)); path.setAttribute("fill-rule", "evenodd");
      path.setAttribute("class", `campo-municipio${props.condomar ? " condomar" : ""}${props.selecionado ? " selecionado" : ""}`);
      interactive(path, `${props.nome} · IBGE ${props.codigo}`, () => information(props.nome,
        [`IBGE ${props.codigo}`, "Limite municipal oficial do IBGE, simplificado para visualização.",
         props.condomar ? "Município do CONDOMAR." : `Referência territorial: ${contextName}.`,
         "Este contorno é referência territorial. Os índices do levantamento não são aplicados automaticamente a todo o município."]));
      svg.append(path);
    }
    if (visible("iip")) for (const feature of features) {
      const props = feature.properties, path = document.createElementNS(ns, "path");
      path.setAttribute("d", pathFor(feature.geometry)); path.setAttribute("fill-rule", "evenodd");
      path.setAttribute("class", "campo-contorno-iip"); path.setAttribute("fill", props.cor);
      interactive(path, `Estrato ${props.estrato_codigo} · ${props.classificacao_rotulo || "IIP"} · ${percent(props.iip)}`, () => information(`Estrato ${props.estrato_codigo}`,
        [`Levantamento ${props.levantamento_codigo}`, `Área ${props.area_codigo}`, `IIP preliminar: ${percent(props.iip)}`,
         `Classificação: ${props.classificacao_rotulo || "Não informada"}`, props.faixa_iip || "",
         `${props.imoveis_inspecionados} imóveis inspecionados · ${props.imoveis_positivos} positivos · ${props.imoveis_pendentes} pendentes`,
         "Contorno preservado no planejamento do levantamento; não é limite oficial de bairro."]));
      svg.append(path);
    }
    if (visible("visitas")) visits.forEach((point, index) => {
      const marker = document.createElementNS(ns, "circle");
      const [x, y] = xy([point.longitude, point.latitude]);
      marker.setAttribute("cx", x); marker.setAttribute("cy", y); marker.setAttribute("r", "6");
      const state = point.situacao !== "INSPECIONADO" ? "pendente" : point.positivo_aedes === "SIM" ? "positivo" : "negativo";
      marker.setAttribute("class", `campo-visita ${state}`);
      interactive(marker, `Visita ${point.inspecao_codigo || index + 1} · ${point.situacao} · ${point.bairro}`, () => information("Visita de campo confirmada",
        [`Origem: ${point.origem}`, `Código da inspeção: ${point.inspecao_codigo || "não informado"}`, `Imóvel: ${point.imovel_codigo || "não informado"}`,
         `Bairro: ${point.bairro}`, `Inspeção: ${point.data_inspecao}`, `Situação: ${point.situacao}`,
         `Resultado para Aedes: ${point.positivo_aedes || "não avaliado"}`, `Levantamento: ${point.levantamento || "não se aplica"}`,
         "Posição informada na visita ou no CSV; não é um caso de doença."]));
      svg.append(marker);
    });
    const caption = view === "estado" ? `Visão de ${contextName}.` : view === "municipio" ?
      "Visão do município selecionado." : "Visão aproximada do levantamento selecionado.";
    const missing = !features.length && visits.length ? " Sem contornos vinculados a este levantamento; são exibidas somente as visitas." : "";
    status.textContent = `${visible("visitas") ? visits.length : 0} visitas com coordenadas · ${visible("iip") ? features.length : 0} contornos de planejamento. ${caption}${missing}`;
    if (streetMap && !mapNode.hidden) {
      for (const item of streetShapes) item.shape.setMap(!item.layer || visible(item.layer) ? streetMap : null);
      streetInfo.close();
      fitStreetMap();
    }
  }

  function fitStreetMap() {
    const bounds = new browser.google.maps.LatLngBounds();
    framePoints().forEach(point => bounds.extend({lat:point[1], lng:point[0]}));
    streetMap.fitBounds(bounds, 40);
    // Uma única coordenada não deve levar o mapa até o nível máximo de zoom.
    browser.google.maps.event.addListenerOnce(streetMap, "idle", () => {
      if (streetMap.getZoom() > 18) streetMap.setZoom(18);
    });
  }
  function streetUnavailable(message) {
    if (!mapNode) return;
    browser.clearTimeout(waitTimer);
    mapNode.hidden = true;
    fallback.hidden = false;
    streetStatus.textContent = message + " Os contornos e as visitas continuam disponíveis abaixo, sem ruas.";
  }
  function selectOnStreet(title, lines, position) {
    information(title, lines);
    const content = document.createElement("div"), heading = document.createElement("strong");
    heading.textContent = title; content.append(heading);
    lines.forEach(line => { const p = document.createElement("p"); p.textContent = line; content.append(p); });
    streetInfo.setContent(content); streetInfo.setPosition(position); streetInfo.open({map:streetMap});
  }
  function initializeStreetMap() {
    if (!mapNode || !browser || !data.mapa_ruas || browser.__GOOGLE_MAPS_AUTH_FAILED__) return;
    if (mapNode.closest(".campo-territorio").getClientRects().length === 0) return;
    if (!browser.google?.maps?.Map) {
      if (!waitTimer) waitTimer = browser.setTimeout(() => streetUnavailable("O mapa de ruas não carregou. Confira sua conexão."), 15000);
      return;
    }
    if (streetMap) {
      if (!mapNode.hidden) { browser.google.maps.event.trigger(streetMap, "resize"); fitStreetMap(); }
      return;
    }
    try {
      const maps = browser.google.maps, initial = framePoints()[0];
      mapNode.hidden = false;
      streetMap = new maps.Map(mapNode, {center:{lat:initial[1], lng:initial[0]}, zoom:12,
        mapTypeId:"roadmap", streetViewControl:false, gestureHandling:"cooperative"});
      streetInfo = new maps.InfoWindow();
      for (const feature of context) for (const polygon of polygons(feature.geometry)) {
        const shape = new maps.Polygon({map:streetMap, paths:polygon.map(ring => ring.map(point => ({lat:point[1], lng:point[0]}))),
          strokeColor:feature.properties.selecionado ? "#64748b" : "#94a3b8", strokeWeight:1,
          fillOpacity:0, clickable:false, zIndex:0});
        streetShapes.push({shape});
      }
      for (const feature of features) for (const polygon of polygons(feature.geometry)) {
        const props = feature.properties;
        const shape = new maps.Polygon({map:streetMap, paths:polygon.map(ring => ring.map(point => ({lat:point[1], lng:point[0]}))),
          strokeColor:"#475569", strokeWeight:2, fillColor:props.cor, fillOpacity:.85, zIndex:1});
        shape.addListener("click", event => selectOnStreet(`Estrato ${props.estrato_codigo}`,
          [`Levantamento ${props.levantamento_codigo}`, `Área ${props.area_codigo}`, `IIP preliminar: ${percent(props.iip)}`,
           `Classificação: ${props.classificacao_rotulo || "Não informada"}`, props.faixa_iip || "",
           `${props.imoveis_inspecionados} imóveis inspecionados · ${props.imoveis_positivos} positivos · ${props.imoveis_pendentes} pendentes`,
           "Contorno preservado no planejamento; não é limite oficial de bairro."], event.latLng));
        streetShapes.push({shape, layer:"iip"});
      }
      visits.forEach((point, index) => {
        const position = {lat:point.latitude, lng:point.longitude};
        const color = point.situacao !== "INSPECIONADO" ? "#d97706" : point.positivo_aedes === "SIM" ? "#dc2626" : "#15803d";
        const shape = new maps.Marker({map:streetMap, position,
          title:`Visita ${point.inspecao_codigo || index + 1} · ${point.situacao} · ${point.bairro}`,
          icon:{path:maps.SymbolPath.CIRCLE, scale:6, fillColor:color, fillOpacity:1, strokeColor:"#fff", strokeWeight:2}, zIndex:3});
        shape.addListener("click", () => selectOnStreet("Visita de campo confirmada",
          [`Origem: ${point.origem}`, `Código da inspeção: ${point.inspecao_codigo || "não informado"}`, `Imóvel: ${point.imovel_codigo || "não informado"}`,
           `Bairro: ${point.bairro}`, `Inspeção: ${point.data_inspecao}`, `Situação: ${point.situacao}`,
           `Resultado para Aedes: ${point.positivo_aedes || "não avaliado"}`, `Levantamento: ${point.levantamento || "não se aplica"}`,
           "Posição informada na visita ou no CSV; não é um caso de doença."], position));
        streetShapes.push({shape, layer:"visitas"});
      });
      browser.clearTimeout(waitTimer);
      fallback.hidden = true;
      streetStatus.textContent = "Mapa de ruas · Google Maps. Use os controles para ampliar e arraste para explorar o levantamento.";
      draw();
    } catch (_error) { streetUnavailable("O mapa de ruas está indisponível neste momento."); }
  }
  const contextButton = document.getElementById("campo-territorio-estado");
  if (contextButton) {
    contextButton.disabled = !context.length;
    contextButton.addEventListener("click", () => { view = "estado"; draw(); });
  }
  document.getElementById("campo-territorio-enquadrar").addEventListener("click", () => { view = "levantamento"; draw(); });
  const municipalityButton = document.getElementById("campo-territorio-municipio");
  if (municipalityButton) {
    municipalityButton.disabled = !selectedMunicipalities.length;
    municipalityButton.addEventListener("click", () => { view = "municipio"; draw(); });
  }
  controls.forEach(control => control.addEventListener("change", draw));
  draw();
  if (mapNode && browser) {
    if (!data.mapa_ruas) streetUnavailable("O mapa de ruas não está configurado.");
    else if (browser.__GOOGLE_MAPS_AUTH_FAILED__) streetUnavailable("O Google Maps está indisponível neste endereço.");
    else initializeStreetMap();
    document.addEventListener("googlemaps:ready", initializeStreetMap);
    document.addEventListener("googlemaps:auth-failed", () => streetUnavailable("O Google Maps está indisponível neste endereço."));
    for (let parent = mapNode.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === "DETAILS") parent.addEventListener("toggle", () => initializeStreetMap());
    }
  }
})();
