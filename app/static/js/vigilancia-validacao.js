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
  updateSampleLink();

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
