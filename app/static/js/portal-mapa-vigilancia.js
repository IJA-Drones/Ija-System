(() => {
  "use strict";
  const node = document.getElementById("portal-risco-data");
  if (!node) return;
  const data = JSON.parse(node.textContent);
  const svg = document.getElementById("risco-svg");
  const detail = document.getElementById("risco-detalhe");
  const status = document.getElementById("portal-risco-status");
  const layer = document.getElementById("portal-risco-camada");
  const area = document.getElementById("portal-risco-area");
  const legend = document.getElementById("risco-legenda");
  const features = data.geografia.features;
  const context = data.contexto?.features || (data.limite ? [data.limite] : []);
  const ns = "http://www.w3.org/2000/svg";
  const polygons = geometry => geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  const positions = geometry => polygons(geometry).flat(2);
  const number = value => value == null ? "Indisponível" : value.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  const percent = value => value == null ? "Indisponível" : `${number(value)}%`;

  function information(title, lines) {
    const heading = document.createElement("h3");
    heading.textContent = title;
    detail.replaceChildren(heading);
    for (const line of lines) {
      const p = document.createElement("p"); p.textContent = line; detail.append(p);
    }
  }
  function summary() {
    const city = data.municipio.name;
    if (layer.value === "sinan") {
      const source = data.sinan;
      information(`SINAN · ${city}`, source ? [
        `${source.doenca} · ${source.ano} · ${source.total} registros no snapshot ${source.parcial ? "parcial" : "concluído"}.`,
        ...source.classificacoes.map(item => `${item.rotulo}: ${item.total}`),
        source.origem,
        "Agregado municipal de um único snapshot. O recorte importado pode não representar toda a base municipal.",
        "A contagem não define sozinha o risco de epidemia. Não são exibidas localizações individuais.",
      ] : ["Nenhum snapshot disponível para o município, doença, ano e modo selecionados."]);
    } else if (layer.value === "focal") {
      const source = data.focal;
      information(`Atividade focal · ${city}`, source.disponivel ? [
        `${source.visitas} visitas confirmadas · ${source.inspecionados} inspeções realizadas.`,
        `Período: ${source.inicio} a ${source.fim}.`,
        "As visitas são agregadas no município. Não representam casos de doença.",
      ] : ["Nenhuma visita focal confirmada neste recorte."]);
    } else {
      information(`LIRAa · ${city}`, data.liraa.disponivel ? [
        `${data.liraa.visitas} visitas confirmadas no levantamento ${data.filtros.levantamento}.`,
        `Período: ${data.liraa.inicio} a ${data.liraa.fim}.`,
        `${features.length} contornos disponíveis no planejamento.`,
        "O IIP se refere a cada estrato e área amostrada. Consulte os índices abaixo, mesmo quando não houver contorno cadastrado.",
      ] : ["Nenhum levantamento confirmado neste município e modo de dados.",
        "Ausência de dados não significa ausência de focos."]);
    }
  }
  function areaInformation(feature) {
    const props = feature.properties;
    information(`Estrato ${props.estrato_codigo} · área ${props.area_codigo}`, [
      `Levantamento ${props.levantamento_codigo}`,
      `IIP: ${percent(props.iip)}`,
      `${props.imoveis_inspecionados} imóveis inspecionados · ${props.imoveis_positivos} positivos · ${props.imoveis_pendentes} pendentes.`,
      "Contorno preservado no planejamento. O índice não é estendido ao restante do município.",
    ]);
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
    const liraa = layer.value === "liraa";
    area.disabled = !liraa;
    const selected = liraa && area.value !== "municipio" ? features[Number(area.value)] : null;
    const shapes = selected ? [selected] : data.limite ? [data.limite] : features;
    const frame = shapes.flatMap(feature => positions(feature.geometry));
    svg.replaceChildren();
    if (frame.length) {
      const west = Math.min(...frame.map(point => point[0])), east = Math.max(...frame.map(point => point[0]));
      const south = Math.min(...frame.map(point => point[1])), north = Math.max(...frame.map(point => point[1]));
      const cosine = Math.cos((south + north) / 2 * Math.PI / 180);
      const scale = Math.min(800 / Math.max((east - west) * cosine, .001), 470 / Math.max(north - south, .001));
      const cx = (east + west) / 2, cy = (north + south) / 2;
      const xy = point => [450 + (point[0] - cx) * cosine * scale, 285 - (point[1] - cy) * scale];
      const pathFor = geometry => polygons(geometry).flatMap(polygon => polygon.map(ring => ring.map((point, index) =>
        `${index ? "L" : "M"}${xy(point).map(value => value.toFixed(2)).join(",")}`).join(" ") + " Z")).join(" ");
      for (const feature of context) {
        const props = feature.properties;
        const isCity = props.codigo === data.municipio.ibge;
        const path = document.createElementNS(ns, "path");
        path.setAttribute("d", pathFor(feature.geometry)); path.setAttribute("fill-rule", "evenodd");
        const source = layer.value === "sinan" ? data.sinan : layer.value === "focal" ? data.focal.disponivel : null;
        path.setAttribute("fill", isCity ? (source ? "#bae6fd" : "#e2e8f0") : "#f1f5f9");
        if (isCity) interactive(path, `${data.municipio.name} · resumo municipal`, () => {
          area.value = "municipio"; draw();
        });
        else { const title = document.createElementNS(ns, "title"); title.textContent = props.nome; path.append(title); }
        svg.append(path);
      }
      if (liraa) features.forEach((feature, index) => {
        const props = feature.properties;
        const path = document.createElementNS(ns, "path");
        path.setAttribute("d", pathFor(feature.geometry)); path.setAttribute("fill-rule", "evenodd");
        path.setAttribute("fill", props.cor);
        path.setAttribute("data-selected", String(selected === feature));
        interactive(path, `Estrato ${props.estrato_codigo} · área ${props.area_codigo} · IIP ${percent(props.iip)}`, () => {
          area.value = String(index); draw();
        });
        svg.append(path);
      });
    }
    if (selected) areaInformation(selected); else summary();
    legend.replaceChildren();
    for (const [color, label] of (liraa ? [
      ["#e2e8f0", "Limite municipal · referência"], ["#dbeafe", "IIP menor"], ["#1e40af", "IIP maior · somente área amostrada"],
    ] : [["#bae6fd", "Informação agregada no município"], ["#e2e8f0", "Sem dados disponíveis"]])) {
      const entry = document.createElement("span"), swatch = document.createElement("i");
      swatch.style.backgroundColor = color;
      entry.append(swatch, document.createTextNode(label)); legend.append(entry);
    }
    status.textContent = frame.length ? `${data.municipio.name} · ${liraa ? `${features.length} contornos LIRAa` : "resumo municipal"} · ${data.demo ? "dados fictícios de demonstração" : "dados da vigilância"}.` :
      "Contorno municipal indisponível nesta malha. Os dados agregados continuam disponíveis nos quadros abaixo.";
  }
  layer.addEventListener("change", draw);
  area.addEventListener("change", draw);
  for (const id of ["portal-risco-modo", "portal-risco-municipio", "portal-risco-regiao"]) {
    document.getElementById(id).addEventListener("change", () => {
      document.getElementById("portal-risco-levantamento").value = "";
    });
  }
  if (features.length) area.value = "0";
  draw();
})();
