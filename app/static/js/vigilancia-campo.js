(() => {
  "use strict";
  const form = document.getElementById("campo-form");
  if (!form) return;
  const origin = document.getElementById("campo-origem");
  const status = document.getElementById("campo-situacao");
  const toggle = (selector, active) => {
    form.querySelectorAll(selector).forEach(group => {
      group.hidden = !active;
      group.querySelectorAll("input, select").forEach(input => { input.disabled = !active; });
    });
  };
  const update = () => {
    toggle("[data-liraa-only]", origin.value === "LIRAA");
    toggle("[data-inspecionado-only]", status.value === "INSPECIONADO");
  };
  origin.addEventListener("change", update);
  status.addEventListener("change", update);
  update();
})();
