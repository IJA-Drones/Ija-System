(function () {
  function normalize(value) {
    return (value || "")
      .toString()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .trim()
      .toLowerCase();
  }

  function resolveVisitKey(value) {
    var visit = normalize(value);
    if (visit === "aedes") return "aedes";
    if (visit === "culex") return "culex";
    return "outro";
  }

  function getTipoImovelInputs(root) {
    return Array.prototype.slice.call(
      root.querySelectorAll('[name="tipo_imovel"]')
    );
  }

  function getTipoImovelValue(root) {
    var inputs = getTipoImovelInputs(root);
    var checked = inputs.find(function (input) {
      return input.checked;
    });
    return checked ? checked.value : "";
  }

  function setTipoImovelValue(root, value) {
    var normalizedValue = normalize(value);
    getTipoImovelInputs(root).forEach(function (input) {
      input.checked = normalize(input.value) === normalizedValue;
    });
  }

  function setTipoImovelRequired(root, required) {
    getTipoImovelInputs(root).forEach(function (input) {
      input.required = required;
    });
  }

  function clearTipoImovelValue(root) {
    getTipoImovelInputs(root).forEach(function (input) {
      input.checked = false;
    });
  }

  function resolveOptions(catalog, tipoVisita, tipoImovel) {
    var visitKey = resolveVisitKey(tipoVisita);

    if (visitKey === "aedes") {
      var imovelKey = normalize(tipoImovel);
      var grupos = (catalog && catalog.aedes) || {};
      for (var label in grupos) {
        if (Object.prototype.hasOwnProperty.call(grupos, label) && normalize(label) === imovelKey) {
          return grupos[label] || [];
        }
      }
      return [];
    }

    if (visitKey === "culex") {
      return (catalog && catalog.culex) || [];
    }

    return (catalog && catalog.outro) || [];
  }

  function rebuildSelect(select, options, selectedValue, placeholder) {
    if (!select) return;

    var normalizedSelected = normalize(selectedValue);
    select.innerHTML = "";

    var placeholderOption = document.createElement("option");
    placeholderOption.value = "";
    placeholderOption.textContent = placeholder || "Selecione...";
    placeholderOption.disabled = true;
    placeholderOption.selected = !normalizedSelected;
    select.appendChild(placeholderOption);

    options.forEach(function (option) {
      var element = document.createElement("option");
      element.value = option;
      element.textContent = option;
      if (normalize(option) === normalizedSelected) {
        element.selected = true;
        placeholderOption.selected = false;
      }
      select.appendChild(element);
    });
  }

  function syncCustomVisitField(config, root, selectedValue, fallbackValue) {
    var wrapper =
      root.querySelector("[data-tipo-visita-outros-wrapper]") ||
      document.getElementById((config && config.customVisitWrapperId) || "");
    var input = root.querySelector('[name="tipo_visita_outros"]');
    var allowCustom = !!(config && config.allowCustomOtherVisit);
    var customLabel =
      (config && config.customOtherVisitLabel) ||
      ((config && config.catalog && config.catalog.tipo_visita_outro_label) || "Outro");
    var showField = allowCustom && normalize(selectedValue) === normalize(customLabel);

    if (wrapper) {
      wrapper.classList.toggle("d-none", !showField);
    }

    if (!input) {
      return;
    }

    input.disabled = !showField;
    input.required = showField;

    if (showField && typeof fallbackValue === "string" && fallbackValue) {
      input.value = fallbackValue;
    }
  }

  window.initSolicitacaoFocusForm = function initSolicitacaoFocusForm(config) {
    var catalog = (config && config.catalog) || {};
    var root =
      (config && config.root && document.querySelector(config.root)) ||
      document;
    var tipoVisitaSelect = root.querySelector('[name="tipo_visita"]');
    var focoSelect = root.querySelector('[name="foco"]');
    var tipoImovelWrapper =
      root.querySelector("[data-tipo-imovel-wrapper]") ||
      document.getElementById((config && config.tipoImovelWrapperId) || "");
    var tipoImovelInputs = getTipoImovelInputs(root);

    if (!tipoVisitaSelect || !focoSelect || !tipoImovelInputs.length) {
      return;
    }

    var firstSync = true;
    var quadraControl = root.querySelector('[data-quadra-focus]');
    var quadraFocus = root.querySelector('[data-quadra-foco-hidden]');
    var quadraSelected = !!quadraControl && (
      quadraControl.checked || normalize(focoSelect.value) === 'quadra'
    );
    var previousFocus = quadraSelected ? '' : focoSelect.value;
    var quadraOperation = "Tratamento e monitoramento de quadra";
    var operationInputs = Array.prototype.slice.call(root.querySelectorAll('[name="tipo_operacao"]'));
    var previousOperation = "Tratamento";
    operationInputs.forEach(function (input) {
      if ((input.tagName === "SELECT" || input.checked) && input.value) previousOperation = input.value;
    });
    var wasQuadra = false;

    function syncFields() {
      var visitValue = tipoVisitaSelect.value;
      var showTipoImovel = resolveVisitKey(visitValue) === "aedes";

      if (tipoImovelWrapper) {
        tipoImovelWrapper.classList.toggle("d-none", !showTipoImovel);
      }

      if (!showTipoImovel) {
        clearTipoImovelValue(root);
      }

      setTipoImovelRequired(root, showTipoImovel);

      syncCustomVisitField(
        config,
        root,
        visitValue,
        (root.querySelector('[name="tipo_visita_outros"]') || {}).value ||
          ((config && config.initialCustomVisit) || "")
      );

      var options = resolveOptions(catalog, visitValue, getTipoImovelValue(root));
      if (quadraControl) options = options.filter(function (option) { return normalize(option) !== 'quadra'; });
      var currentFocus = quadraSelected ? '' : focoSelect.value;
      var normalizedCurrentFocus = normalize(currentFocus);
      var focusStillValid = options.some(function (option) {
        return normalize(option) === normalizedCurrentFocus;
      });

      // Preserve historical values only when reopening the saved request.
      if (firstSync && normalizedCurrentFocus && !focusStillValid) {
        options = [currentFocus].concat(options);
        focusStillValid = true;
      }

      rebuildSelect(
        focoSelect,
        options,
        focusStillValid ? currentFocus : "",
        quadraSelected ? 'Quadra selecionada' : (config && config.focoPlaceholder) || "Selecione o foco da acao..."
      );
      var isQuadra = quadraControl ? quadraSelected : normalize(focoSelect.value) === "quadra";
      if (quadraControl) {
        focoSelect.disabled = isQuadra;
        focoSelect.required = !isQuadra;
        quadraFocus.disabled = !isQuadra;
        quadraFocus.value = 'QUADRA';
        quadraControl.checked = isQuadra;
      }

      if (isQuadra && !wasQuadra) {
        operationInputs.forEach(function (input) {
          if ((input.tagName === "SELECT" || input.checked) && input.value) previousOperation = input.value;
        });
      }
      operationInputs.forEach(function (input) {
        if (input.tagName === "SELECT") {
          if (isQuadra) input.value = quadraControl ? '' : quadraOperation;
          else if (wasQuadra) input.value = normalize(previousOperation) === normalize(quadraOperation)
            ? "Tratamento" : previousOperation;
          input.disabled = isQuadra;
          return;
        }
        var isQuadraOperation = normalize(input.value) === normalize(quadraOperation);
        if (isQuadra) {
          input.checked = !quadraControl && isQuadraOperation;
          input.disabled = true;
        } else {
          input.disabled = false;
          if (wasQuadra) input.checked = normalize(input.value) === normalize(
            normalize(previousOperation) === normalize(quadraOperation) ? "Tratamento" : previousOperation
          );
        }
      });
      wasQuadra = isQuadra;
      firstSync = false;
    }

    tipoVisitaSelect.addEventListener("change", syncFields);
    focoSelect.addEventListener("change", syncFields);
    if (quadraControl) quadraControl.addEventListener(quadraControl.type === 'radio' ? 'click' : 'change', function () {
      var nextSelected = quadraControl.type === 'radio' ? !quadraSelected : quadraControl.checked;
      if (nextSelected) previousFocus = focoSelect.value;
      quadraSelected = nextSelected;
      if (!quadraSelected) focoSelect.value = previousFocus;
      syncFields();
    });
    tipoImovelInputs.forEach(function (input) {
      input.addEventListener("change", syncFields);
    });

    if (config && config.initialTipoImovel) {
      setTipoImovelValue(root, config.initialTipoImovel);
    }
    syncFields();
  };
})();
