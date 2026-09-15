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
  const selectedTypeInput = page.querySelector("#portalTipoVisita");
  const feedback = page.querySelector("#portalCidadaoFeedback");
  const cepInput = page.querySelector("#portalCep");
  const cpfInput = page.querySelector("#portalCpf");
  const phoneInput = page.querySelector("#portalTelefone");
  const logradouroInput = page.querySelector("#portalLogradouro");
  const numeroInput = page.querySelector("#portalNumero");
  const bairroInput = page.querySelector("#portalBairro");
  const cidadeInput = page.querySelector("#portalCidade");
  const ufInput = page.querySelector("#portalUf");
  const latitudeInput = page.querySelector("#portalLatitude");
  const longitudeInput = page.querySelector("#portalLongitude");
  const placeIdInput = page.querySelector("#portalPlaceId");
  const complementoInput = page.querySelector("#portalComplemento");
  const useLocationButton = page.querySelector("#portalUseLocationButton");
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
    selectedTypeInput.value = type;
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

  function digits(value) {
    return String(value || "").replace(/\D/g, "");
  }

  function maskCep(value) {
    const raw = digits(value).slice(0, 8);
    return raw.length > 5 ? raw.slice(0, 5) + "-" + raw.slice(5) : raw;
  }

  function maskCpf(value) {
    const raw = digits(value).slice(0, 11);
    return raw
      .replace(/^(\d{3})(\d)/, "$1.$2")
      .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
      .replace(/\.(\d{3})(\d)/, ".$1-$2");
  }

  function maskPhone(value) {
    const raw = digits(value).slice(0, 11);
    if (raw.length <= 10) {
      return raw
        .replace(/^(\d{2})(\d)/, "($1) $2")
        .replace(/(\d{4})(\d)/, "$1-$2");
    }
    return raw
      .replace(/^(\d{2})(\d)/, "($1) $2")
      .replace(/(\d{5})(\d)/, "$1-$2");
  }

  cepInput.addEventListener("input", function () {
    cepInput.value = maskCep(cepInput.value);
    const raw = digits(cepInput.value);
    if (raw.length === 8) {
      lookupCep(raw);
    }
  });

  cpfInput.addEventListener("input", function () {
    cpfInput.value = maskCpf(cpfInput.value);
  });

  phoneInput.addEventListener("input", function () {
    phoneInput.value = maskPhone(phoneInput.value);
  });

  function applyAddressPayload(payload) {
    if (payload.cep) cepInput.value = maskCep(payload.cep);
    if (payload.logradouro) logradouroInput.value = payload.logradouro;
    if (payload.numero) numeroInput.value = payload.numero;
    if (payload.bairro) bairroInput.value = payload.bairro;
    if (payload.cidade) cidadeInput.value = payload.cidade;
    if (payload.uf) ufInput.value = payload.uf;
    if (payload.complemento) complementoInput.value = payload.complemento;
    if (payload.place_id) placeIdInput.value = payload.place_id;
  }

  async function lookupCep(cepDigits) {
    try {
      const response = await fetch("/portal-cidadao/cep/" + cepDigits, {
        headers: { Accept: "application/json" }
      });
      const payload = await response.json();
      if (response.ok && payload.ok) {
        applyAddressPayload(payload);
      }
    } catch (error) {
      console.error("Erro ao consultar CEP.", error);
    }
  }

  function setLocationLoading(isLoading) {
    useLocationButton.disabled = isLoading;
    useLocationButton.innerHTML = isLoading
      ? '<i class="bi bi-hourglass-split" aria-hidden="true"></i> Localizando...'
      : '<i class="bi bi-crosshair" aria-hidden="true"></i> Usar minha localização';
  }

  useLocationButton.addEventListener("click", function () {
    if (!navigator.geolocation) {
      showFeedback("Seu navegador não permite capturar localização.", "error");
      return;
    }

    setLocationLoading(true);
    navigator.geolocation.getCurrentPosition(async function (position) {
      const latitude = String(position.coords.latitude);
      const longitude = String(position.coords.longitude);
      latitudeInput.value = latitude;
      longitudeInput.value = longitude;

      try {
        const response = await fetch("/portal-cidadao/reverse-geocode", {
          method: "POST",
          headers: {
            "Accept": "application/json",
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ latitude, longitude })
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          showFeedback(payload.error || "Não foi possível preencher o endereço pela localização.", "error");
          return;
        }
        applyAddressPayload(payload);
        showFeedback("Localização encontrada. Revise o endereço antes de enviar.", "success");
      } catch (error) {
        console.error("Erro ao resolver localização.", error);
        showFeedback("Erro ao resolver sua localização. Preencha o endereço manualmente.", "error");
      } finally {
        setLocationLoading(false);
      }
    }, function () {
      setLocationLoading(false);
      showFeedback("Não foi possível acessar sua localização. Você pode preencher o endereço manualmente.", "error");
    }, {
      enableHighAccuracy: true,
      timeout: 12000,
      maximumAge: 60000
    });
  });

  fileInput.addEventListener("change", function () {
    fileList.innerHTML = "";
    Array.from(fileInput.files || []).forEach(function (file) {
      const item = document.createElement("span");
      item.className = "portal-cidadao-file-item";
      item.innerHTML = '<i class="bi bi-paperclip" aria-hidden="true"></i>' + file.name;
      fileList.appendChild(item);
    });
  });

  function showFeedback(message, type) {
    feedback.hidden = false;
    feedback.className = "portal-cidadao-feedback is-" + type;
    feedback.textContent = message;
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();

    if (!selectedType) {
      typeButtons[0]?.focus();
      showFeedback("Escolha o tipo de ocorrência antes de enviar.", "error");
      return;
    }

    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    previewButton.disabled = true;
    previewButton.innerHTML = 'Enviando <i class="bi bi-hourglass-split" aria-hidden="true"></i>';
    feedback.hidden = true;

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" }
      });
      const payload = await response.json();

      if (!response.ok || !payload.success) {
        const errors = payload.errors || {};
        const firstError = Object.values(errors)[0] || "Não foi possível registrar o relato.";
        showFeedback(firstError, "error");
        return;
      }

      showFeedback("Relato registrado com sucesso. Protocolo: " + payload.protocolo, "success");
      form.reset();
      selectedType = "";
      selectedTypeInput.value = "";
      typeButtons.forEach(function (button) {
        button.classList.remove("is-selected");
        button.setAttribute("aria-pressed", "false");
      });
      dependentFields.hidden = true;
      fileList.innerHTML = "";
      clearFocusOptions("Primeiro escolha o tipo de ocorrência");
      focusSelect.disabled = true;
    } catch (error) {
      console.error("Erro ao enviar relato cidadão.", error);
      showFeedback("Erro de comunicação ao registrar o relato. Tente novamente.", "error");
    } finally {
      previewButton.disabled = false;
      previewButton.innerHTML = 'Enviar relato <i class="bi bi-arrow-right" aria-hidden="true"></i>';
    }
  });
})();
