(function () {
  const page = document.querySelector("[data-portal-cidadao]");
  const catalogElement = document.getElementById("portalCidadaoFocusCatalog");
  if (!page || !catalogElement) return;

  let catalog = {};
  try {
    catalog = JSON.parse(catalogElement.textContent || "{}");
  } catch (error) {
    console.error("Não foi possível carregar o catálogo de focos do portal.", error);
    return;
  }

  const typeButtons = Array.from(page.querySelectorAll("[data-tipo-visita]"));
  const dependentFields = page.querySelector("#portalCidadaoDependentFields");
  const propertyField = page.querySelector("#portalTipoImovelField");
  const propertySelect = page.querySelector("#portalTipoImovel");
  const focusSelect = page.querySelector("#portalFoco");
  const focusHint = page.querySelector("#portalFocoHint");
  const fileInput = page.querySelector("#portalMidia");
  const fileList = page.querySelector("#portalCidadaoFileList");
  const previewButton = page.querySelector("#portalCidadaoPreviewButton");
  const form = page.querySelector("#portalCidadaoForm");
  let selectedType = "";

  function clearFocusOptions(placeholder) {
    focusSelect.innerHTML = "";
    const option = document.createElement("option");
    option.value = "";
    option.textContent = placeholder;
    focusSelect.appendChild(option);
  }

  function getFocusOptions() {
    if (selectedType === "Aedes") {
      const property = propertySelect.value;
      return property && catalog.aedes ? (catalog.aedes[property] || []) : [];
    }
    if (selectedType === "Culex") return catalog.culex || [];
    if (selectedType === "Outro") return catalog.outro || [];
    return [];
  }

  function renderFocusOptions() {
    const options = getFocusOptions();
    clearFocusOptions(options.length ? "Selecione uma opção" : "Escolha os campos anteriores");
    options.forEach(function (label) {
      const option = document.createElement("option");
      option.value = label;
      option.textContent = citizenFocusLabel(label);
      focusSelect.appendChild(option);
    });
    focusSelect.disabled = options.length === 0;
    focusSelect.required = options.length > 0;
    focusHint.textContent = options.length
      ? "Escolha uma opção que mais se aproxima do que você encontrou."
      : "Escolha primeiro o tipo de ocorrência e o local.";
  }

  function citizenFocusLabel(label) {
    const labels = {
      "Acumulador": "Muitos objetos que podem acumular água",
      "Edificação Abandonada com Inservíveis": "Imóvel abandonado com objetos acumulando água",
      "Terreno com Inservíveis": "Terreno com lixo ou objetos acumulando água",
      "Obra": "Obra com recipientes ou água parada",
      "Caixa d'agua": "Caixa-d'água sem proteção",
      "Piscina": "Piscina sem cuidado ou com água parada",
      "Laje com Acúmulo de Água": "Laje com água parada",
      "Telhado com Acumulo de Agua": "Telhado com água parada",
      "Area alagada": "Área alagada com muitos mosquitos",
      "Corrego": "Córrego com muitos mosquitos",
      "Piscinao": "Piscinão ou canal com muitos mosquitos",
      "Casa abandonada com inservíveis": "Casa abandonada com objetos acumulando água",
      "Galpão com inservíveis": "Galpão com objetos acumulando água",
      "Imovel com inservíveis": "Imóvel com objetos acumulando água",
      "Laje/telhado com Acúmulo de água": "Laje ou telhado com água parada",
      "P.E Cadastrado": "Ponto estratégico com possível foco",
      "Pátio com Veículos": "Pátio com veículos ou recipientes acumulando água",
      "Piscinao": "Piscinão ou canal com muitos mosquitos",
      "Reciclagem": "Reciclagem ou ecoponto com recipientes acumulando água",
      "Terreno com inservíveis": "Terreno com lixo ou objetos acumulando água"
    };
    return labels[label] || label;
  }

  function selectType(type) {
    selectedType = type;
    typeButtons.forEach(function (button) {
      const isActive = button.dataset.tipoVisita === type;
      button.classList.toggle("is-selected", isActive);
      button.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
    dependentFields.hidden = false;
    propertyField.hidden = type !== "Aedes";
    propertySelect.required = type === "Aedes";
    if (type !== "Aedes") propertySelect.value = "";
    renderFocusOptions();
  }

  typeButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      selectType(button.dataset.tipoVisita || "");
    });
  });

  propertySelect.addEventListener("change", renderFocusOptions);

  fileInput.addEventListener("change", function () {
    fileList.innerHTML = "";
    Array.from(fileInput.files || []).forEach(function (file) {
      const item = document.createElement("span");
      item.className = "portal-cidadao-file-item";
      item.innerHTML = '<i class="bi bi-paperclip" aria-hidden="true"></i>' + file.name;
      fileList.appendChild(item);
    });
  });

  previewButton.addEventListener("click", function () {
    if (!selectedType) {
      typeButtons[0]?.focus();
      return;
    }

    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }
  });
})();
