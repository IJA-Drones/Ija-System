(() => {
  "use strict";
  const municipality = document.getElementById("prefeitura-id");
  const sampleLink = document.getElementById("sample-download");
  const updateSampleLink = () => {
    if (!municipality || !sampleLink) return;
    const raw = municipality.value.trim();
    const valid = /^[1-9]\d*$/.test(raw) && Number.isSafeInteger(Number(raw));
    sampleLink.classList.toggle("disabled", !valid);
    if (valid) {
      sampleLink.href = `${sampleLink.dataset.sampleUrl}?prefeitura_id=${encodeURIComponent(raw)}`;
      sampleLink.removeAttribute("aria-disabled");
      sampleLink.removeAttribute("tabindex");
    } else {
      sampleLink.href = "#";
      sampleLink.setAttribute("aria-disabled", "true");
      sampleLink.setAttribute("tabindex", "-1");
    }
  };
  municipality?.addEventListener("input", updateSampleLink);
  municipality?.addEventListener("change", updateSampleLink);
  updateSampleLink();

  const mode = document.getElementById("campo-demo");
  const authorization = document.getElementById("campo-autorizacao");
  const authorized = document.getElementById("campo-autorizado");
  if (mode && authorization && authorized) {
    const updateAuthorization = () => {
      const required = mode.value === "false";
      authorization.hidden = !required;
      authorized.required = required;
      if (!required) authorized.checked = false;
    };
    mode.addEventListener("change", updateAuthorization);
    updateAuthorization();
  }

  const destination = document.getElementById("campo-levantamento-destino");
  const destinationStatus = document.getElementById("campo-levantamento-status");
  if (destination && destinationStatus && municipality && mode) {
    let sequence = 0, controller, pending = false, failed = false;
    let plannedFile = false, checkingFile = false, fileFailed = false, fileSequence = 0;
    const fileInput = document.getElementById("arquivo-csv");
    const planningLink = document.getElementById("campo-planejamento-link");
    const updateGuidance = () => {
      destination.required = plannedFile;
      if (destination.options[0]) destination.options[0].textContent = plannedFile ?
        "Selecione o levantamento liberado" : "Usar o código do CSV / tratamento focal";
      if (planningLink) {
        const query = new URLSearchParams({demo: mode.value});
        if (/^[1-9]\d*$/.test(municipality.value)) query.set("prefeitura_id", municipality.value);
        if (destination.value) query.set("plano", destination.value);
        planningLink.href = `${planningLink.dataset.planningUrl}?${query}${destination.value ? "#periodo-levantamento" : ""}`;
        planningLink.textContent = destination.value ? "Conferir / ampliar período do levantamento" : "Abrir planejamento";
      }
      if (pending || failed || checkingFile || fileFailed) return;
      if (!/^[1-9]\d*$/.test(municipality.value)) {
        destinationStatus.textContent = "Selecione a prefeitura para consultar os levantamentos.";
      } else if (plannedFile && !destination.value) {
        destinationStatus.textContent = destination.options.length > 1 ?
          "Este CSV contém visitas planejadas. Selecione o levantamento de destino antes de validar." :
          "Este CSV contém visitas planejadas. Abra o planejamento, complete a amostra e libere o levantamento antes de importar.";
      } else {
        destinationStatus.textContent = destination.options.length > 1 ? "" :
          "Nenhum levantamento liberado. Complete a amostra no planejamento e libere o levantamento para importar visitas planejadas.";
      }
    };
    const reset = () => {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Usar o código do CSV / tratamento focal";
      destination.replaceChildren(option);
      destination.value = "";
      updateGuidance();
    };
    const updateDestinations = async () => {
      const current = ++sequence;
      controller?.abort();
      reset();
      failed = false;
      if (!/^[1-9]\d*$/.test(municipality.value)) {
        pending = false;
        destination.disabled = false;
        destination.removeAttribute("aria-busy");
        destinationStatus.textContent = "Selecione a prefeitura para consultar os levantamentos.";
        return;
      }
      controller = new AbortController();
      pending = true;
      destination.disabled = true;
      destination.setAttribute("aria-busy", "true");
      destinationStatus.textContent = "Consultando levantamentos liberados…";
      try {
        const query = new URLSearchParams({prefeitura_id: municipality.value, demo: mode.value});
        const response = await fetch(`${destination.dataset.listUrl}?${query}`, {signal: controller.signal, headers: {Accept: "application/json"}});
        if (!response.ok) throw new Error("list-unavailable");
        const data = await response.json();
        if (current !== sequence) return;
        if (!Array.isArray(data.levantamentos)) throw new Error("invalid-list");
        for (const item of data.levantamentos) {
          const option = document.createElement("option");
          option.value = item.codigo;
          option.textContent = `${item.titulo} · ${item.codigo} · ${item.inicio} a ${item.fim}`;
          destination.append(option);
        }
        destinationStatus.textContent = data.levantamentos.length ? "" : "Nenhum levantamento liberado nesta prefeitura e origem de dados.";
      } catch (error) {
        if (current !== sequence || error.name === "AbortError") return;
        failed = true;
        destinationStatus.textContent = "Não foi possível consultar os levantamentos. Altere o filtro novamente ou recarregue a página antes de importar.";
      } finally {
        if (current === sequence) {
          pending = false;
          destination.disabled = false;
          destination.removeAttribute("aria-busy");
          updateGuidance();
        }
      }
    };
    municipality.addEventListener("change", updateDestinations);
    mode.addEventListener("change", updateDestinations);
    destination.addEventListener("change", updateGuidance);
    fileInput?.addEventListener("change", async () => {
      const current = ++fileSequence;
      const file = fileInput.files[0];
      plannedFile = false;
      fileFailed = false;
      checkingFile = !!file;
      updateGuidance();
      if (!file) return;
      destinationStatus.textContent = "Conferindo o tipo do arquivo…";
      try {
        // Apenas o cabeçalho: a validação integral e os vínculos continuam no servidor.
        const header = (await file.slice(0, 4096).text()).replace(/^\uFEFF/, "").split(/\r?\n/, 1)[0];
        if (current !== fileSequence) return;
        plannedFile = /(?:^|[;,])\s*"?quarteirao_codigo"?\s*(?:[;,]|$)/.test(header);
      } catch (_error) {
        if (current !== fileSequence) return;
        fileFailed = true;
        destinationStatus.textContent = "Não foi possível ler o arquivo. Selecione o CSV novamente antes de validar.";
      } finally {
        if (current === fileSequence) {
          checkingFile = false;
          updateGuidance();
        }
      }
    });
    destination.closest("form").addEventListener("submit", event => {
      if (checkingFile || fileFailed || (plannedFile && !destination.value)) {
        event.preventDefault();
        if (checkingFile) destinationStatus.textContent = "Aguarde a conferência do arquivo antes de validar.";
        else if (!fileFailed) { updateGuidance(); destination.focus(); }
        return;
      }
      if (pending || failed) {
        event.preventDefault();
        destinationStatus.textContent = pending ? "Aguarde a consulta dos levantamentos antes de importar." :
          "Recarregue a lista de levantamentos antes de importar.";
      }
    });
    updateGuidance();
  }

  const reportButton = document.getElementById("download-report");
  reportButton?.addEventListener("click", () => {
    const report = document.getElementById("preview-report");
    if (!report) return;
    const payload = JSON.parse(report.textContent);
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "vigilancia-previa.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
})();
