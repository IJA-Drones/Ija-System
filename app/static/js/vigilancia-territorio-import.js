(() => {
  "use strict";
  const form = document.getElementById("territorio-csv-form");
  if (!form) return;
  const file = document.getElementById("territorio-csv");
  const confirmation = document.getElementById("territorio-csv-confirmado");
  const label = document.getElementById("territorio-csv-confirmacao");
  const status = document.getElementById("territorio-csv-status");
  const submit = form.querySelector('button[type="submit"], button:not([type])');
  let sequence = 0, checking = false, failed = false;
  const guide = () => {
    if (checking || failed) return;
    status.textContent = confirmation.required && !confirmation.checked ?
      "O CSV inclui o campo de contornos. Marque a confirmação abaixo antes de importar." : "";
  };
  file.addEventListener("change", async () => {
    const current = ++sequence, selected = file.files[0];
    confirmation.checked = false;
    confirmation.required = false;
    label.dataset.required = "false";
    failed = false;
    checking = !!selected;
    submit.disabled = checking;
    status.textContent = selected ? "Conferindo o arquivo…" : "";
    if (!selected) return;
    try {
      const header = (await selected.slice(0, 4096).text()).replace(/^\uFEFF/, "").split(/\r\n|\r|\n/, 1)[0];
      if (current !== sequence) return;
      confirmation.required = /(?:^|[;,])\s*"?geometria"?\s*(?:[;,]|$)/.test(header);
      label.dataset.required = String(confirmation.required);
    } catch (_error) {
      if (current !== sequence) return;
      failed = true;
      status.textContent = "Não foi possível ler o arquivo. Selecione o CSV novamente.";
    } finally {
      if (current === sequence) {
        checking = false;
        submit.disabled = false;
        guide();
      }
    }
  });
  confirmation.addEventListener("change", guide);
  confirmation.addEventListener("invalid", guide);
  form.addEventListener("submit", event => {
    if (checking || failed || (confirmation.required && !confirmation.checked)) {
      event.preventDefault();
      if (checking) status.textContent = "Aguarde a conferência do arquivo.";
      else if (!failed) { guide(); confirmation.focus(); }
    }
  });
})();
