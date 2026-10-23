(function (root) {
  "use strict";
  const EPS = 1e-12;
  const cross = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const on = (a, b, c) => Math.abs(cross(a, b, c)) <= EPS &&
    Math.min(a[0], b[0]) - EPS <= c[0] && c[0] <= Math.max(a[0], b[0]) + EPS &&
    Math.min(a[1], b[1]) - EPS <= c[1] && c[1] <= Math.max(a[1], b[1]) + EPS;
  function polygonFromPoints(points) {
    if (!Array.isArray(points) || points.length < 3 || points.length > 200) throw new Error("Marque entre 3 e 200 pontos para formar a área.");
    const ring = points.map(p => {
      if (!p || !Number.isFinite(p.lat) || !Number.isFinite(p.lng) || Math.abs(p.lat) > 90 || Math.abs(p.lng) > 180) throw new Error("Há uma coordenada inválida no desenho.");
      return [Number(p.lng.toFixed(6)), Number(p.lat.toFixed(6))];
    });
    if (new Set(ring.map(p => p.join(","))).size !== ring.length) throw new Error("Há pontos repetidos. Ajuste o contorno da área.");
    if (Math.max(...ring.map(p => p[0])) - Math.min(...ring.map(p => p[0])) > 180) throw new Error("Confira o local e a extensão da área.");
    ring.push([...ring[0]]);
    for (let i = 0; i < points.length; i++) for (let j = i + 1; j < points.length; j++) {
      if (j === i + 1 || (i === 0 && j === points.length - 1)) continue;
      const [a, b, c, d] = [ring[i], ring[i + 1], ring[j], ring[j + 1]];
      if ((cross(a, b, c) * cross(a, b, d) < 0 && cross(c, d, a) * cross(c, d, b) < 0) || on(a, b, c) || on(a, b, d) || on(c, d, a) || on(c, d, b)) throw new Error("As linhas estão se cruzando. Arraste os pontos para corrigir o contorno.");
    }
    const area = Math.abs(ring.slice(0, -1).reduce((sum, p, i) => sum + p[0] * ring[i + 1][1] - ring[i + 1][0] * p[1], 0)) / 2;
    if (area < 1e-10) throw new Error("Os pontos não formam uma área. Afaste ou ajuste os cantos.");
    return { type: "Polygon", coordinates: [ring] };
  }
  function pointsFromPolygon(geometry) {
    return geometry ? geometry.coordinates[0].slice(0, -1).map(p => ({ lat: p[1], lng: p[0] })) : [];
  }
  if (typeof module === "object" && module.exports) module.exports = { polygonFromPoints, pointsFromPolygon };
  if (!root.document) return;
  const document = root.document;
  const node = document.getElementById("territorio-mapa-data");
  if (!node) return;
  const config = JSON.parse(node.textContent);
  const byId = id => document.getElementById("territorio-" + id);
  const form = byId("form");
  const field = name => form?.elements.namedItem(name);
  const state = { map: null, polygon: null, drawing: false, loaded: null, listeners: [], shapes: [], search: 0, dirty: false, ready: false };
  const message = value => { byId("mapa-feedback").textContent = value; };
  const allow = (id, enabled) => { if (byId(id)) byId(id).disabled = !enabled; };
  function confirmChange(action) {
    if (!form) return;
    field("geometria_acao").value = action;
    const box = byId("confirmacao");
    box.hidden = action === "manter";
    field("geometria_confirmada").required = action !== "manter";
    field("geometria_confirmada").checked = false;
  }
  function currentPoints() {
    return state.polygon ? state.polygon.getPath().getArray().map(p => ({ lat: p.lat(), lng: p.lng() })) : [];
  }
  function controls() {
    const count = currentPoints().length;
    allow("desenhar", state.ready && config.editavel);
    allow("desfazer", state.ready && state.drawing && count > 0);
    allow("concluir", state.ready && state.drawing && count >= 3);
    allow("restaurar", state.ready && config.editavel && (state.dirty || state.drawing));
    allow("remover", state.ready && config.editavel && (count > 0 || !!state.loaded?.geometria));
    byId("desenhar")?.setAttribute("aria-pressed", String(state.drawing));
  }
  function changed() {
    const points = currentPoints();
    state.dirty = true;
    confirmChange("substituir");
    field("geometria").value = "";
    if (!state.drawing && points.length >= 3) {
      try {
        field("geometria").value = JSON.stringify(polygonFromPoints(points));
        byId("mapa-resumo").textContent = `Área com ${points.length} pontos. Confira o contorno e confirme a alteração antes de salvar.`;
      } catch (error) { byId("mapa-resumo").textContent = error.message; }
    }
    if (state.drawing) message(`${points.length} ponto(s) marcado(s). Toque nos próximos cantos e depois em “Concluir desenho”.`);
    controls();
  }
  function setPolygon(points, editable) {
    state.listeners.forEach(listener => listener.remove());
    state.listeners = [];
    if (state.polygon) state.polygon.setMap(null);
    // Keep a first ring even before the first click; paths: [] has no getPath().
    state.polygon = new root.google.maps.Polygon({ map: state.map, paths: [points], editable, clickable: false,
      strokeColor: "#d97706", strokeOpacity: 1, strokeWeight: 3, fillColor: "#f59e0b", fillOpacity: .22, zIndex: 5 });
    if (config.editavel) for (const event of ["insert_at", "set_at", "remove_at"]) state.listeners.push(state.polygon.getPath().addListener(event, changed));
  }
  function fit(points) {
    if (!points.length) return;
    const bounds = new root.google.maps.LatLngBounds();
    points.forEach(point => bounds.extend(point));
    state.map.fitBounds(bounds, 40);
  }
  const unavailableRecordMessage = item => `Quarteirão ${item.code} carregado. O mapa está indisponível neste momento. Você pode editar os dados abaixo; o contorno existente será mantido.`;
  function loadRecord(item) {
    const tools = document.getElementById("territorio-ferramentas");
    if (tools) tools.open = true;
    if (!form) {
      if (state.ready) fit(pointsFromPolygon(item.geometria));
      else message("O mapa está indisponível neste momento. O cadastro do quarteirão permanece disponível na tabela.");
      return true;
    }
    if (state.dirty && !root.confirm("Há um desenho ainda não salvo. Carregar outro cadastro e descartar essa alteração?")) return false;
    state.loaded = item;
    state.drawing = false;
    state.dirty = false;
    for (const [name, key] of Object.entries({ quarteirao: "code", bairro: "bairro", area: "area", imoveis: "imoveis", referencia: "referencia", territorio_versao: "versao" })) field(name).value = item[key] ?? "";
    confirmChange("manter");
    field("geometria").value = "";
    byId("cadastro").open = true;
    if (state.ready) {
      setPolygon(pointsFromPolygon(item.geometria), !!item.geometria);
      if (item.geometria) fit(pointsFromPolygon(item.geometria));
      byId("mapa-resumo").textContent = item.geometria ? `Quarteirão ${item.code} carregado. Arraste os pontos para ajustar ou mantenha o limite salvo.` : `Quarteirão ${item.code} carregado. Localize-o e clique em “Desenhar área” para definir seu limite.`;
      message(item.geometria ? `Área ${item.code} selecionada. O desenho salvo está destacado em laranja.` : `O quarteirão ${item.code} ainda não possui contorno. Você pode delimitá-lo no mapa.`);
    } else {
      byId("mapa-resumo").textContent = unavailableRecordMessage(item);
      message("Cadastro carregado. Para localizar ou desenhar a área, é necessário que o Google Maps esteja disponível.");
    }
    controls();
    return true;
  }
  function chooseSample(item) {
    const select = document.getElementById("amostra-quarteirao");
    if (!select) return;
    select.value = item.code;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    document.querySelector('[data-vigilancia-target="amostra"]')?.click();
    const details = document.getElementById("quarteirao-amostra");
    details.open = true;
    document.getElementById("amostra-mapa-selecao").textContent = `Área selecionada: ${item.code} · ${item.bairro}. Confira o estrato, a meta e a conta responsável antes de salvar.`;
    details.scrollIntoView({ behavior: "smooth", block: "center" });
    select.focus({ preventScroll: true });
  }
  function showInfo(item, position) {
    const content = document.createElement("div"); content.className = "territorio-mapa-info";
    const title = document.createElement("strong"); title.textContent = `Quarteirão ${item.code}`; content.append(title);
    const info = document.createElement("p"); info.textContent = `${item.bairro} · Área ${item.area} · ${item.imoveis} imóveis`; content.append(info);
    function button(label, handler) {
      const el = document.createElement("button"); el.type = "button"; el.className = "btn btn-sm btn-outline-primary";
      el.textContent = label; el.addEventListener("click", () => { state.info.close(); handler(); }); content.append(el);
    }
    if (config.editavel) button("Carregar cadastro", () => loadRecord(item));
    if (config.selecionarAmostra) button("Usar no levantamento", () => chooseSample(item));
    state.info.setContent(content); state.info.setPosition(position); state.info.open({ map: state.map });
  }
  function unavailable() {
    state.ready = false; state.drawing = false;
    for (const id of ["buscar", "enquadrar", "desenhar", "desfazer", "concluir", "restaurar", "remover"]) allow(id, false);
    if (state.loaded && form) byId("mapa-resumo").textContent = unavailableRecordMessage(state.loaded);
    message("O mapa não pôde ser carregado. Recarregue a página; se o problema continuar, informe o administrador. Você pode continuar usando o cadastro por formulário.");
  }
  async function search() {
    const query = byId("busca").value.trim();
    if (!query) { message("Informe um município, bairro ou endereço para localizar."); byId("busca").focus(); return; }
    const sequence = ++state.search;
    allow("buscar", false); message("Localizando o endereço no mapa…");
    let timeout;
    try {
      const result = await Promise.race([
        new root.google.maps.Geocoder().geocode({ address: query + ", Brasil", region: "br" }),
        new Promise((_resolve, reject) => { timeout = root.setTimeout(() => reject(new Error("Busca indisponível")), 10000); }),
      ]);
      if (sequence !== state.search) return;
      if (!result.results?.length) throw new Error("Endereço não encontrado");
      const match = result.results[0];
      if (match.geometry.viewport) state.map.fitBounds(match.geometry.viewport); else { state.map.setCenter(match.geometry.location); state.map.setZoom(17); }
      message("Local encontrado. Aproxime o mapa e clique em “Desenhar área” para marcar os cantos do quarteirão.");
    } catch (_error) { if (sequence === state.search) message("Não foi possível localizar esse endereço. Inclua município e UF, tente novamente ou navegue pelo mapa."); }
    finally { root.clearTimeout(timeout); if (sequence === state.search && state.ready) allow("buscar", true); }
  }
  function initialize() {
    if (state.map || !config.configurado || !root.google?.maps?.Map || root.__GOOGLE_MAPS_AUTH_FAILED__) return;
    if (byId("mapa-canvas").closest?.("[data-vigilancia-panel]")?.hidden) return;
    if (document.getElementById("territorio-ferramentas")?.open === false) return;
    try {
      state.map = new root.google.maps.Map(byId("mapa-canvas"), { center: { lat: -8.5, lng: -37 }, zoom: 7,
        mapTypeId: "hybrid", streetViewControl: false, fullscreenControl: true, gestureHandling: "cooperative" });
      state.ready = true;
      state.info = new root.google.maps.InfoWindow();
      config.registros.filter(item => item.geometria).forEach(item => {
        const points = pointsFromPolygon(item.geometria);
        const polygon = new root.google.maps.Polygon({ map: state.map, paths: points, strokeColor: "#2563eb", strokeWeight: 2, fillColor: "#2563eb", fillOpacity: .18 });
        polygon.addListener("click", event => { if (!state.drawing) showInfo(item, event.latLng); });
        state.shapes.push(polygon);
      });
      function frame() {
        const points = config.registros.flatMap(item => pointsFromPolygon(item.geometria));
        if (points.length) fit(points); else message("Ainda não há áreas desenhadas. Localize o município ou bairro para começar.");
      }
      byId("buscar").addEventListener("click", search);
      byId("busca").addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); search(); } });
      byId("enquadrar").addEventListener("click", frame);
      for (const id of ["buscar", "enquadrar"]) allow(id, true);
      state.map.addListener("click", event => {
        if (!state.drawing || !event.latLng) return;
        if (currentPoints().length >= 200) { message("Limite de 200 pontos atingido. Conclua ou ajuste o desenho."); return; }
        state.polygon.getPath().push(event.latLng);
      });
      if (config.editavel && form) {
        byId("desenhar").addEventListener("click", () => {
          state.info.close(); state.drawing = true; state.dirty = true;
          state.shapes.forEach(shape => shape.setOptions({ clickable: false }));
          setPolygon([], false); confirmChange("substituir"); field("geometria").value = "";
          byId("cadastro").open = true;
          message("Desenho iniciado. Clique ou toque nos cantos da área. Use pelo menos três pontos e depois conclua.");
          controls();
        });
        byId("desfazer").addEventListener("click", () => state.polygon.getPath().pop());
        byId("concluir").addEventListener("click", () => {
          try {
            polygonFromPoints(currentPoints()); state.drawing = false; state.polygon.setEditable(true);
            state.shapes.forEach(shape => shape.setOptions({ clickable: true })); changed();
            message("Contorno concluído. Arraste os pontos para ajustar e confira os dados do quarteirão antes de salvar.");
          } catch (error) { message(error.message + " Use “Desfazer ponto” para corrigir."); }
        });
        byId("restaurar").addEventListener("click", () => {
          state.dirty = false; state.drawing = false;
          state.shapes.forEach(shape => shape.setOptions({ clickable: true }));
          if (state.loaded) loadRecord(state.loaded); else {
            setPolygon([], false); confirmChange("manter"); field("geometria").value = "";
            byId("mapa-resumo").textContent = "Desenho cancelado. O cadastro pode ser preenchido sem contorno.";
            message("Alteração do desenho cancelada."); controls();
          }
        });
        byId("remover").addEventListener("click", () => {
          state.drawing = false; state.dirty = true; setPolygon([], false);
          state.shapes.forEach(shape => shape.setOptions({ clickable: true }));
          confirmChange(state.loaded?.geometria ? "remover" : "manter"); field("geometria").value = "";
          message("Contorno removido da edição. Confira o cadastro e salve para confirmar a alteração."); controls();
        });
        form.addEventListener("submit", event => {
          const action = field("geometria_acao").value;
          if (state.drawing || (action === "substituir" && !field("geometria").value)) {
            event.preventDefault(); message("Conclua e confira o desenho antes de salvar o quarteirão.");
            byId("mapa-feedback").scrollIntoView({ behavior: "smooth", block: "center" });
          }
        });
      }
      const initial = state.loaded || config.registros.find(item => item.code === config.inicial);
      if (initial && !field("geometria_acao")?.value.match(/substituir|remover/)) loadRecord(initial);
      else if (form && field("geometria_acao").value === "substituir" && field("geometria").value) {
        try { setPolygon(pointsFromPolygon(JSON.parse(field("geometria").value)), true); fit(currentPoints()); changed(); } catch (_error) { message("Revise o desenho informado antes de tentar salvar novamente."); }
      } else { frame(); if (config.registros.some(item => item.geometria)) message("Clique em uma área azul para consultar ou selecionar seu cadastro."); }
      controls();
    } catch (_error) { unavailable(); }
  }
  // Loading a registered block must work even if Maps has not loaded or was denied.
  document.querySelectorAll("[data-territorio-code]").forEach(button => button.addEventListener("click", () => {
    const item = config.registros.find(row => row.code === button.dataset.territorioCode);
    if (item && loadRecord(item)) {
      const target = state.ready || !form ? byId("mapa") : byId("cadastro");
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }));
  document.addEventListener("googlemaps:ready", initialize);
  document.getElementById("territorio-ferramentas")?.addEventListener("toggle", event => {
    if (event.target.open) {
      if (state.map) root.google?.maps?.event?.trigger?.(state.map, "resize");
      else initialize();
    }
  });
  document.addEventListener("vigilancia:panel-visible", event => {
    if (event.detail.id === "territorio") {
      if (state.map) root.google?.maps?.event?.trigger?.(state.map, "resize");
      else initialize();
    }
  });
  document.addEventListener("googlemaps:auth-failed", unavailable);
  if (root.__GOOGLE_MAPS_AUTH_FAILED__ || !config.configurado) unavailable(); else initialize();
  root.setTimeout(() => { if (!state.map) unavailable(); }, 15000);
})(typeof window === "object" ? window : globalThis);
