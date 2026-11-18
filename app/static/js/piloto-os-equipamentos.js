(() => {
  "use strict";

  function init() {
    const form = document.getElementById("os-form-main");
    if (!form || form.dataset.equipmentReadonly === "true") return;
    const situation = form.querySelector('[name="situacao_aplicacao"]');
    const states = [];

    for (const [id, suffix, kind] of [
      ["drone_id", "pulv", "pulverizacao"],
      ["drone_monitoramento_id", "monit", "monitoramento"],
    ]) {
      const select = document.getElementById(id);
      if (!select) continue;
      const fields = Object.fromEntries(["serie", "modelo", "renomacao", "anatel", "anac"].map(name => {
        const field = ["anatel", "anac"].includes(name) ? `registro_${name}` : name;
        return [name, document.getElementById(`drone_${field}_${suffix}`)];
      }));
      fields.prefixo = document.getElementById(`prefixo_${kind}`);
      const note = document.getElementById(`drone-${suffix}-autofill-note`);
      const drafts = new Map();
      const read = () => Object.fromEntries(Object.entries(fields).map(([key, node]) => [key, node?.value || ""]));
      const apply = (onlyEmpty = false) => {
        const option = select.selectedOptions?.[0];
        const data = option?.dataset || {};
        const values = drafts.get(select.value) || {...data, prefixo: data.renomacao || ""};
        for (const [key, node] of Object.entries(fields)) {
          if (node && (!onlyEmpty || !node.value)) node.value = values[key] || "";
        }
      };
      const automatic = select.dataset.autoSelected === "true";
      const state = {select, kind, value: select.value, suggested: automatic ? select.value : "",
        automatic, manual: false};
      const updateNote = () => { if (note) note.hidden = !state.automatic; };
      const change = value => {
        drafts.set(state.value, read());
        select.value = value;
        apply();
        state.value = value;
      };
      // Saved snapshots and manually typed prefixes are not refreshed on page load.
      if (automatic) apply(true);
      select.addEventListener("change", () => {
        if (select.value === state.value) return;
        state.manual = true;
        state.automatic = false;
        change(select.value);
        updateNote();
      });
      state.sync = () => {
        const value = situation?.value || "";
        const applicable = value !== "NENHUM VOO REALIZADO" &&
          !(kind === "pulverizacao" && value === "APENAS MONITORADO");
        if (!applicable && state.automatic) {
          change("");
          state.automatic = false;
        } else if (applicable && !state.manual && state.suggested && !select.value) {
          change(state.suggested);
          state.automatic = true;
        }
        updateNote();
      };
      states.push(state);
    }
    const sync = () => states.forEach(state => state.sync());
    situation?.addEventListener("change", sync);
    sync();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
