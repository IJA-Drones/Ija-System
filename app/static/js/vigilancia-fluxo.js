(() => {
  "use strict";
  const root = document.querySelector("[data-vigilancia-view]");
  if (!root) return;
  const panels = [...root.querySelectorAll("[data-vigilancia-panel]")];
  const links = [...root.querySelectorAll("[data-vigilancia-target]")];
  if (!panels.length || !links.length) return;
  root.dataset.vigilanciaEnhanced = "true";
  function targetFor(hash) {
    let element;
    try { element = document.getElementById(decodeURIComponent(hash.replace(/^#/, ""))); } catch (_) { return null; }
    return element && root.contains(element) ? element.closest("[data-vigilancia-panel]") : null;
  }
  function reveal(element) {
    for (let ancestor = element; ancestor && ancestor !== root; ancestor = ancestor.parentElement) {
      if (ancestor.tagName === "DETAILS") ancestor.open = true;
    }
  }
  function show(panel, hash, focus = false) {
    if (!panel) return;
    for (const item of panels) item.hidden = item !== panel;
    for (const link of links) {
      const active = link.dataset.vigilanciaTarget === panel.id ||
        (panel.id === "levantamentos" && link.dataset.vigilanciaTarget === "amostra");
      link.setAttribute("aria-current", active ? "step" : "false");
      link.setAttribute("aria-expanded", String(active));
    }
    const element = document.getElementById(hash?.replace(/^#/, "")) || panel;
    reveal(element);
    document.dispatchEvent(new CustomEvent("vigilancia:panel-visible", { detail: { id: panel.id } }));
    if (focus) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
      const heading = panel.querySelector("h2, h3");
      if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus({ preventScroll: true }); }
    }
  }
  root.addEventListener("click", event => {
    const link = event.target.closest("a[href]");
    if (!link || event.defaultPrevented || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const href = link.getAttribute("href");
    if (!href.startsWith("#")) return;
    const panel = targetFor(href);
    if (!panel) return;
    event.preventDefault();
    history.replaceState(null, "", href);
    show(panel, href, true);
  });
  // Validação nativa continua alcançável quando o campo está em um detalhe.
  root.addEventListener("invalid", event => {
    const panel = event.target.closest("[data-vigilancia-panel]");
    if (panel) show(panel, "#" + panel.id);
    reveal(event.target);
  }, true);
  window.addEventListener("hashchange", () => show(targetFor(location.hash), location.hash));
  const initial = targetFor(location.hash) || document.getElementById(root.dataset.vigilanciaDefault) || panels[0];
  show(initial, location.hash);
})();
