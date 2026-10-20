(function () {
  "use strict";
  const filtersForm = document.getElementById("resultados-filtros");
  for (const name of ["prefeitura_id", "demo", "doenca", "ano_sinan"]) {
    filtersForm?.elements.namedItem(name)?.addEventListener("change", () => {
      filtersForm.elements.namedItem("lote_sinan").value = "";
      if (name === "ano_sinan") for (const week of ["semana_inicio", "semana_fim"]) filtersForm.elements.namedItem(week).value = "";
    });
  }
  const node = document.getElementById("resultados-mapa-data");
  if (!node) return;
  const config = JSON.parse(node.textContent);
  const status = document.getElementById("resultados-mapa-status");
  const controls = Array.from(document.querySelectorAll("[data-camada]"));
  const frameButton = document.getElementById("resultados-enquadrar");
  const layers = { iip: [], liraa: [], focal: [], sinan: [] };
  let map, info, ready = false;
  const googleDetails = document.getElementById("resultados-google-details");
  const unavailable = () => {
    ready = false;
    status.textContent = "O Google Maps está indisponível neste endereço. As tabelas, os gráficos e os contornos para impressão continuam disponíveis.";
    frameButton.disabled = true;
  };
  function popup(title, lines, position) {
    const content = document.createElement("div"); content.className = "resultado-mapa-info";
    const heading = document.createElement("strong"); heading.textContent = title; content.append(heading);
    for (const line of lines) { const p = document.createElement("p"); p.textContent = line; content.append(p); }
    info.setContent(content); info.setPosition(position); info.open({ map });
  }
  function visible(name) { return controls.find(control => control.dataset.camada === name).checked; }
  function frame() {
    const bounds = new google.maps.LatLngBounds(); let count = 0;
    for (const [name, shapes] of Object.entries(layers)) if (visible(name)) for (const item of shapes) {
      for (const point of item.points) { bounds.extend(point); count++; }
    }
    if (count) map.fitBounds(bounds, 40);
    status.textContent = count ? "Clique nos contornos ou nos pontos para consultar a origem e os valores." : "Nenhuma geometria ou coordenada disponível nas camadas visíveis deste recorte.";
  }
  function refresh() {
    if (!ready) return;
    for (const [name, shapes] of Object.entries(layers)) for (const item of shapes) item.shape.setMap(visible(name) ? map : null);
    info.close();
  }
  function circle(layer, point, color, title, lines) {
    const center = { lat: point.latitude, lng: point.longitude };
    const shape = new google.maps.Circle({ map, center, radius: 18, strokeColor: color, strokeWeight: 2,
      fillColor: color, fillOpacity: .85, zIndex: layer === "sinan" ? 4 : 3 });
    shape.addListener("click", () => popup(title, lines, center));
    layers[layer].push({ shape, points: [center] });
  }
  function initialize() {
    if (googleDetails && !googleDetails.open) return;
    if (map || !window.google?.maps?.Map || window.__GOOGLE_MAPS_AUTH_FAILED__) return;
    try {
      map = new google.maps.Map(document.getElementById("resultados-mapa"), { center: {lat:-8.5,lng:-37},
        zoom: 7, mapTypeId: "roadmap", streetViewControl: false, gestureHandling: "cooperative" });
      info = new google.maps.InfoWindow();
      for (const feature of config.geografia.features) {
        const props = feature.properties;
        for (const polygon of feature.geometry.coordinates) {
          const points = polygon[0].slice(0,-1).map(point => ({lat:point[1],lng:point[0]}));
          const shape = new google.maps.Polygon({ map, paths: points, strokeColor: "#1e40af", strokeWeight: 2,
            fillColor: props.cor, fillOpacity: .65, zIndex: 1 });
          shape.addListener("click", event => popup(`Estrato ${props.estrato_codigo} · Área ${props.area_codigo}`,
            [`Levantamento ${props.levantamento_codigo}`, `IIP preliminar: ${props.iip === null ? "indisponível" : props.iip.toLocaleString("pt-BR") + "%"}`,
             `${props.imoveis_inspecionados} imóveis inspecionados · ${props.imoveis_positivos} positivos · ${props.imoveis_pendentes} pendentes`,
             "Contornos dos quarteirões preservados no plano; índice calculado para o estrato/área."], event.latLng));
          layers.iip.push({shape,points});
        }
      }
      for (const point of config.pontos) {
        const layer = point.origem === "FOCAL" ? "focal" : "liraa";
        circle(layer, point, layer === "focal" ? "#7c3aed" : "#0f766e", layer === "focal" ? "Ação de tratamento focal" : "Visita LIRAa",
          [point.bairro, `Inspeção: ${point.data_inspecao} · ${point.situacao}`, `Resultado Aedes aegypti: ${point.positivo_aedes || "não avaliado"}`]);
      }
      for (const point of config.sinan) circle("sinan", point,
        point.classification === "confirmado" ? "#be123c" : point.classification === "suspeito" ? "#d97706" : "#64748b",
        "Notificação SINAN · CSV da equipe", [`Classificação: ${point.classification}`, `Semana: ${point.week || "não informada"}`, "Não representa vínculo com um imóvel inspecionado."]);
      ready = true; controls.forEach(control => control.addEventListener("change", () => { refresh(); frame(); }));
      frameButton.disabled = false; frameButton.addEventListener("click", frame);
      refresh(); frame();
    } catch (_error) { unavailable(); }
  }
  document.getElementById("resultados-imprimir")?.addEventListener("click", () => {
    const details = Array.from(document.querySelectorAll(".resultados-page details"));
    const previous = details.map(item => item.open);
    details.forEach(item => { item.open = true; });
    const restore = () => { details.forEach((item,index) => {item.open = previous[index];}); window.removeEventListener("afterprint", restore); };
    window.addEventListener("afterprint", restore);
    window.print();
  });
  document.addEventListener("googlemaps:ready", initialize);
  googleDetails?.addEventListener("toggle", () => { if (googleDetails.open) { initialize(); if (ready) frame(); } });
  document.addEventListener("googlemaps:auth-failed", unavailable);
  if (window.__GOOGLE_MAPS_AUTH_FAILED__ || !config.configurado) unavailable(); else initialize();
  window.setTimeout(() => { if (!map) unavailable(); }, 15000);
})();
