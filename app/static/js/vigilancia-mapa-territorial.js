(() => {
  "use strict";
  const node = document.getElementById("campo-territorio-data");
  if (!node) return;
  const data = JSON.parse(node.textContent);
  const svg = document.getElementById("campo-territorio-svg");
  const detail = document.getElementById("campo-territorio-detalhe");
  const status = document.getElementById("campo-territorio-status");
  const context = data.contexto.features;
  const features = data.geografia.features;
  const visits = data.pontos;
  const controls = [...document.querySelectorAll("[data-territorial-layer]")];
  const ns = "http://www.w3.org/2000/svg";
  const polygons = geometry => geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  const positions = geometry => polygons(geometry).flat(2);
  const geographicVisits = visits.map(point => [point.longitude, point.latitude]);
  let view = "levantamento";
  const visible = name => controls.find(control => control.dataset.territorialLayer === name)?.checked;
  const number = value => value === null || value === undefined ? "Indisponível" : value.toLocaleString("pt-BR", { maximumFractionDigits: 2 });

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
  function draw() {
    const selected = context.filter(feature => feature.properties.selecionado);
    const plotted = features.flatMap(feature => positions(feature.geometry)).concat(geographicVisits);
    let frame = view === "estado" ? context.flatMap(feature => positions(feature.geometry)) :
      (plotted.length ? plotted : (selected.length ? selected : context).flatMap(feature => positions(feature.geometry)));
    if (!frame.length) frame = [[-41.4, -9.5], [-34.8, -7.1]];
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
         props.condomar ? "Município do CONDOMAR." : "Município de contexto de Pernambuco.",
         "Este contorno é referência territorial. Os índices do levantamento não são aplicados automaticamente a todo o município."]));
      svg.append(path);
    }
    if (visible("iip")) for (const feature of features) {
      const props = feature.properties, path = document.createElementNS(ns, "path");
      path.setAttribute("d", pathFor(feature.geometry)); path.setAttribute("fill-rule", "evenodd");
      path.setAttribute("class", "campo-contorno-iip"); path.setAttribute("fill", props.cor);
      interactive(path, `Estrato ${props.estrato_codigo} · IIP ${number(props.iip)}%`, () => information(`Estrato ${props.estrato_codigo}`,
        [`Levantamento ${props.levantamento_codigo}`, `Área ${props.area_codigo}`, `IIP preliminar: ${number(props.iip)}%`,
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
    status.textContent = `${visible("visitas") ? visits.length : 0} visitas com coordenadas · ${visible("iip") ? features.length : 0} contornos de planejamento. ${view === "estado" ? "Visão de Pernambuco continental." : "Visão do levantamento selecionado."}`;
  }
  document.getElementById("campo-territorio-estado").addEventListener("click", () => { view = "estado"; draw(); });
  document.getElementById("campo-territorio-enquadrar").addEventListener("click", () => { view = "levantamento"; draw(); });
  controls.forEach(control => control.addEventListener("change", draw));
  draw();
})();
