/* Standalone mode is a visual preview. The authenticated central saves proposed
 * configurations only. Existing authorization checks do not consume them yet.
 */
(() => {
  "use strict";
  const root = document.getElementById("ti-central");
  if (!root) return;
  const dataElement = document.getElementById("ti-central-data");
  const editorData = dataElement ? JSON.parse(dataElement.textContent) : null;

  const labels = editorData?.labels || {
    consultar: "Consultar", criar: "Cadastrar", editar: "Editar", excluir: "Excluir",
    exportar: "Exportar", aprovar: "Aprovar", cancelar: "Cancelar", concluir: "Concluir",
    midias: "Gerenciar mídias", atribuir: "Atribuir equipe", operar: "Operar",
    configurar: "Configurar", importar: "Importar", corrigir: "Corrigir",
    encaminhar: "Encaminhar", atender: "Atender", gerenciar: "Gerenciar acessos",
  };
  const catalog = editorData?.catalog || [
    { id: "prefeitura", label: "Prefeitura", icon: "bi-buildings", description: "Solicitações, equipes e operação municipal.", modules: [
      ["solicitacoes", "Solicitações", "Pedidos, aprovações e agendamentos.", "bi-inbox", "consultar criar editar aprovar cancelar excluir exportar"],
      ["os", "Ordens de serviço", "Execução, histórico e arquivos das OS.", "bi-clipboard-check", "consultar editar concluir midias exportar"],
      ["clientes", "Clientes e UVIS", "Cadastros e contatos da prefeitura.", "bi-people", "consultar criar editar excluir exportar"],
      ["equipes", "Equipes e pilotos", "Equipes OA, membros e acessos UVIS.", "bi-person-badge", "consultar criar editar excluir atribuir"],
      ["equipamentos", "Equipamentos", "Drones, baterias e manutenção.", "bi-cpu", "consultar criar editar excluir importar"],
      ["veiculos", "Veículos e turnos", "Frota, KM, abastecimento e limpeza.", "bi-truck", "consultar criar editar excluir operar corrigir exportar"],
      ["checklists", "Checklists", "Inspeções semanais de veículos e drones.", "bi-ui-checks-grid", "consultar editar corrigir"],
      ["relatorios", "Relatórios", "Indicadores, coleta de imagens e retornos.", "bi-bar-chart", "consultar exportar"],
      ["mapas", "Mapas e agenda", "Geolocalização e programação da operação.", "bi-geo-alt", "consultar exportar"],
      ["denuncias", "Denúncias", "Triagem e encaminhamento de registros.", "bi-megaphone", "consultar encaminhar atribuir"],
    ] },
    { id: "agro", label: "Agro", icon: "bi-tree", description: "Comercial, equipes e operação agrícola.", modules: [
      ["clientes", "Clientes e fornecedores", "Cadastros e contatos da operação Agro.", "bi-people", "consultar criar editar excluir"],
      ["comercial", "Comercial", "Orçamentos, contratos e documentos.", "bi-briefcase", "consultar criar editar excluir exportar"],
      ["mapeamentos", "Mapeamentos", "RD e templates de mapeamento.", "bi-map", "consultar editar concluir configurar"],
      ["os", "Ordens de serviço", "Contratos aprovados e execução em campo.", "bi-clipboard-check", "consultar criar editar concluir excluir exportar"],
      ["equipes", "Equipes e pilotos", "Cadastros e vínculos operacionais Agro.", "bi-person-badge", "consultar criar editar excluir"],
      ["equipamentos", "Equipamentos", "Equipamentos e equipe responsável.", "bi-cpu", "consultar criar editar excluir importar"],
      ["voos", "Logs de voo", "Importação, rotas KML e vínculo com OS.", "bi-airplane", "consultar importar editar exportar"],
      ["talentos", "Banco de talentos", "Currículos e análise de candidatos.", "bi-file-earmark-person", "consultar criar editar excluir"],
    ] },
    { id: "financeiro", label: "Financeiro", icon: "bi-bank", description: "Contas, caixa e gestão por empresa.", modules: [
      ["contas", "Contas e lançamentos", "Entradas, saídas, contas a pagar e receber.", "bi-wallet2", "consultar criar editar excluir operar"],
      ["caixa", "Caixa diário", "Abertura, movimentação e fechamento.", "bi-cash-stack", "consultar operar"],
      ["bancos", "Bancos e conciliação", "Contas bancárias e conferência de valores.", "bi-bank", "consultar criar editar excluir operar"],
      ["comprovantes", "Comprovantes", "Documentos dos pagamentos e recebimentos.", "bi-receipt", "consultar midias"],
      ["relacionamentos", "Fornecedores", "Cadastro de fornecedores da empresa.", "bi-briefcase", "consultar criar editar excluir"],
      ["comercial", "Clientes e comercial", "Consulta comercial da empresa.", "bi-briefcase", "consultar exportar"],
      ["relatorios", "Relatórios financeiros", "Visão geral e exportação dos resultados.", "bi-bar-chart", "consultar exportar"],
      ["configuracoes", "Configurações da empresa", "Identificação, logo, categorias e competências.", "bi-sliders", "consultar configurar"],
    ] },
    { id: "sistema", label: "Sistema", icon: "bi-shield-check", description: "Administração e ferramentas de suporte.", modules: [
      ["usuarios", "Usuários e acessos", "Contas, perfis e responsabilidades.", "bi-person-lock", "consultar criar editar excluir gerenciar"],
      ["perfis", "Central de TI", "Configurações por tipo de usuário.", "bi-shield-check", "consultar configurar"],
      ["suporte", "Bugs e suporte", "Solicitações de ajuda e tratamento de bugs.", "bi-tools", "consultar criar atender"],
      ["estoque", "Estoque", "Peças, quantidades e disponibilidade.", "bi-box-seam", "consultar criar editar excluir exportar"],
      ["operacional", "Painel operacional", "Acompanhamento da operação.", "bi-activity", "consultar"],
      ["auditoria", "Auditoria e presença", "Histórico de ações e presença no sistema.", "bi-clock-history", "consultar exportar"],
      ["tecnico", "Ferramentas técnicas", "Erros, verificações, backups e importações DJI.", "bi-terminal", "consultar operar importar"],
    ] },
  ];
  const profiles = editorData?.profiles || [
    ["prefeitura_admin", "Admin Prefeitura", "Administração municipal", "prefeitura", "administrativo", "bi-buildings"],
    ["financeiro", "Financeiro", "Operação financeira", "financeiro", "financeiro", "bi-wallet2"],
    ["financeiro_admin", "Admin Financeiro", "Gestão financeira", "financeiro", "financeiro", "bi-bank"],
    ["piloto", "Piloto OA", "Operação da Oceano Azul", "prefeitura", "operacao", "bi-airplane"],
    ["regional", "Regional", "Gestão regional", "prefeitura", "administrativo", "bi-geo-alt"],
    ["uvis", "UVIS", "Solicitações municipais", "prefeitura", "operacao", "bi-building"],
    ["operario", "Operário", "Gestão operacional", "prefeitura", "administrativo", "bi-clipboard-check"],
    ["sup_veiculos", "Supervisor de veículos", "Frota e turnos", "prefeitura", "operacao", "bi-truck"],
    ["piloto_agro", "Piloto Agro", "Operação agrícola", "agro", "operacao", "bi-tree"],
    ["equipe_oceano", "Equipe OA", "Equipe da Oceano Azul", "prefeitura", "operacao", "bi-people"],
    ["equipe_uvis", "Equipe UVIS", "Equipe municipal", "prefeitura", "operacao", "bi-people"],
    ["covisa", "COVISA", "Coordenação municipal", "prefeitura", "administrativo", "bi-diagram-3"],
    ["admin", "Admin", "Administração geral", "prefeitura", "administrativo", "bi-shield-check"],
    ["diretor", "Diretor", "Direção do sistema", "sistema", "administrativo", "bi-person-badge"],
    ["visualizar", "Visualização", "Consulta administrativa", "prefeitura", "administrativo", "bi-eye"],
    ["dev", "Dev", "Ferramentas técnicas", "sistema", "ti", "bi-terminal"],
    ["gestor_ti", "Gestor de TI", "Perfil proposto · Prévia", "sistema", "ti", "bi-person-lock"],
    ["visualizador", "Visualizador (legado)", "Consulta administrativa", "prefeitura", "legado", "bi-eye"],
    ["operador", "Operador (legado)", "Cadastros operacionais", "prefeitura", "legado", "bi-tools"],
    ["sup_veiculo", "Supervisor (legado)", "Alias de supervisor de veículos", "prefeitura", "legado", "bi-truck"],
  ].map(([id, name, description, area, group, glyph]) => ({ id, name, description, area, group, glyph }));

  const get = (id) => root.querySelector(`#${id}`);
  const create = (tag, className = "", text = "") => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text) element.textContent = text;
    return element;
  };
  const icon = (name) => {
    const element = create("i", `bi ${name}`);
    element.setAttribute("aria-hidden", "true");
    return element;
  };
  const normalize = (value) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  catalog.forEach((area) => {
    area.modules = area.modules.map(([id, label, description, moduleIcon, actions]) => {
      return { id: `${area.id}.${id}`, label, description, icon: moduleIcon, actions: actions.split(" ") };
    });
  });

  // The choices illustrate a profile editor; they are not the current permission matrix.
  // gestor_ti is a proposed profile in this preview only; no role is created in the app.
  function example(profile) {
    const permissions = new Set();
    const area = catalog.find((item) => item.id === profile.area);
    area.modules.forEach((module, index) => {
      if (index > 5 && profile.id !== "financeiro_admin") return;
      if (profile.id === "gestor_ti" && module.id !== "sistema.perfis") return;
      permissions.add(`${module.id}.consultar`);
      if (["prefeitura_admin", "operario", "financeiro", "financeiro_admin"].includes(profile.id)) {
        ["criar", "editar", "aprovar", "operar", "configurar"].forEach((action) => {
          if (module.actions.includes(action)) permissions.add(`${module.id}.${action}`);
        });
      }
      if (profile.id === "gestor_ti") permissions.add("sistema.perfis.configurar");
    });
    return {
      areas: new Set([profile.area]), permissions,
    };
  }
  // Standalone examples are never submitted or used as the real configuration baseline.
  const copySelection = (state) => ({ areas: new Set(state.areas), permissions: new Set(state.permissions) });
  const stored = new Map((editorData?.states || []).map((state) => [state.id, state]));
  const currentRules = new Map((editorData?.states || []).map((state) => [state.id, {
    permissions: new Set(state.current_rules.permissions), notes: state.current_rules.notes,
  }]));
  const baseline = new Map(profiles.map((profile) => [profile.id, editorData ? {
    areas: new Set(stored.get(profile.id).areas), permissions: new Set(stored.get(profile.id).permissions),
  } : example(profile)]));
  const drafts = new Map(Array.from(baseline, ([id, state]) => [id, copySelection(state)]));
  let selectedProfile = profiles[0];
  let selectedArea = selectedProfile.area;
  let saving = false;
  const draft = () => drafts.get(selectedProfile.id);
  const entries = (state) => new Set([...state.permissions, ...Array.from(state.areas, (id) => `area:${id}`)]);
  function changes(profile = selectedProfile) {
    const initial = baseline.get(profile.id);
    const current = drafts.get(profile.id);
    const before = entries(initial);
    const after = entries(current);
    return {
      added: Array.from(after).filter((id) => !before.has(id)),
      removed: Array.from(before).filter((id) => !after.has(id)),
    };
  }
  const pendingProfiles = () => profiles.filter((profile) => {
    const diff = changes(profile);
    return diff.added.length + diff.removed.length > 0;
  });

  function renderProfiles() {
    const query = normalize(get("ti-profile-search").value.trim());
    const visible = profiles.filter((profile) => normalize(`${profile.name} ${profile.id}`).includes(query));
    const list = get("ti-profile-list");
    list.replaceChildren();
    visible.forEach((profile) => {
      const item = create("li");
      const button = create("button", "ti-profile-button");
      button.type = "button";
      button.dataset.profileId = profile.id;
      button.setAttribute("aria-pressed", String(profile.id === selectedProfile.id));
      button.setAttribute("aria-controls", "ti-selected-name");
      const avatar = create("span", "ti-avatar");
      avatar.append(icon(profile.glyph));
      avatar.setAttribute("aria-hidden", "true");
      const text = create("span", "ti-profile-label", profile.name);
      const diff = changes(profile);
      if (diff.added.length + diff.removed.length) {
        const marker = create("span", "ti-profile-draft");
        marker.title = "Alterações não salvas";
        marker.setAttribute("aria-label", "Alterações não salvas");
        text.append(marker);
      }
      button.append(avatar, text);
      if (profile.id === selectedProfile.id) button.append(icon("bi-check-circle-fill ti-profile-marker"));
      button.addEventListener("click", () => {
        selectedProfile = profile;
        selectedArea = profile.area;
        get("ti-feedback").hidden = true;
        renderEditor();
        list.querySelector(`[data-profile-id="${profile.id}"]`)?.focus({ preventScroll: true });
      });
      item.append(button);
      list.append(item);
    });
    get("ti-profile-empty").hidden = visible.length > 0;
  }

  function renderAreas() {
    const navigation = get("ti-area-nav");
    navigation.replaceChildren();
    catalog.forEach((area) => {
      const button = create("button", "ti-area-button");
      button.type = "button";
      button.dataset.areaId = area.id;
      button.setAttribute("aria-pressed", String(area.id === selectedArea));
      button.setAttribute("aria-controls", "ti-module-list");
      button.append(icon(area.icon), create("span", "", area.label));
      button.addEventListener("click", () => {
        selectedArea = area.id;
        renderAreas();
        renderModules();
        navigation.querySelector(`[data-area-id="${area.id}"]`)?.focus({ preventScroll: true });
      });
      navigation.append(button);
    });
  }

  function renderModules() {
    const area = catalog.find((item) => item.id === selectedArea);
    const enabled = draft().areas.has(area.id);
    get("ti-area-title").textContent = area.label;
    get("ti-area-icon").replaceChildren(icon(area.icon));
    get("ti-area-enabled").checked = enabled;
    const note = get("ti-rule-note");
    if (note) {
      note.textContent = currentRules.get(selectedProfile.id)?.notes[area.id] || "";
      note.hidden = !note.textContent;
    }
    const list = get("ti-module-list");
    list.replaceChildren();
    area.modules.forEach((module, index) => {
      const details = create("details", "ti-module");
      details.dataset.moduleId = module.id;
      details.open = index < 2;
      const summary = create("summary");
      const glyph = create("span", "ti-module-icon");
      glyph.append(icon(module.icon));
      const heading = create("span", "ti-module-label", module.label);
      summary.append(glyph, heading, create("span", "ti-module-count"), icon("bi-chevron-down"));
      const fieldset = create("fieldset");
      fieldset.disabled = !enabled || module.id === "sistema.perfis";
      if (module.id === "sistema.perfis") {
        fieldset.title = "Acesso reservado aos perfis Dev e Gestor de TI, preservado para administrar permissões.";
      }
      fieldset.append(create("legend", "visually-hidden", `Ações permitidas em ${module.label}`));
      const tools = create("div", "ti-module-tools");
      [["Marcar todas", true], ["Limpar", false]].forEach(([label, checked]) => {
        const button = create("button", "ti-text-button", label);
        button.type = "button";
        button.setAttribute("aria-label", `${label} em ${module.label}`);
        button.addEventListener("click", () => {
          module.actions.forEach((action) => {
            const code = `${module.id}.${action}`;
            if (checked && editorData?.unavailable_permissions?.includes(code)) return;
            draft().permissions[checked ? "add" : "delete"](code);
          });
          syncModule(details);
          markChanged();
        });
        tools.append(button);
      });
      const grid = create("div", "ti-action-grid");
      module.actions.forEach((action) => {
        const label = create("label", "ti-action");
        const input = create("input");
        input.type = "checkbox";
        input.dataset.permissionId = `${module.id}.${action}`;
        input.checked = draft().permissions.has(input.dataset.permissionId);
        if (editorData?.unavailable_permissions?.includes(input.dataset.permissionId)) {
          input.disabled = true;
          label.title = "Ação ainda não disponível neste módulo.";
        }
        input.addEventListener("change", () => {
          draft().permissions[input.checked ? "add" : "delete"](input.dataset.permissionId);
          if (action === "consultar" && !input.checked) module.actions.forEach((item) => draft().permissions.delete(`${module.id}.${item}`));
          if (input.checked) draft().permissions.add(`${module.id}.consultar`);
          syncModule(details);
          markChanged();
        });
        label.append(input, create("span", "ti-action-label", labels[action]));
        if (currentRules.get(selectedProfile.id)?.permissions.has(input.dataset.permissionId)) {
          const badge = create("span", "ti-current-badge", "Atual");
          badge.title = "Prevista nas regras atuais deste perfil; os vínculos e filtros da tela continuam sendo aplicados.";
          label.append(badge);
        }
        grid.append(label);
      });
      fieldset.append(tools, grid);
      details.append(summary, fieldset);
      list.append(details);
      syncModule(details);
    });
  }

  function syncModule(element) {
    const inputs = Array.from(element.querySelectorAll("[data-permission-id]"));
    inputs.forEach((input) => {
      input.checked = input.dataset.permissionId.startsWith("sistema.perfis.")
        ? ["dev", "gestor_ti"].includes(selectedProfile.id)
        : draft().permissions.has(input.dataset.permissionId);
    });
    const count = inputs.filter((input) => input.checked).length;
    const indicator = element.querySelector(".ti-module-count");
    indicator.textContent = `${count}/${inputs.length}`;
    indicator.setAttribute("aria-label", `${count} de ${inputs.length} opções selecionadas`);
  }
  function refreshStatus() {
    const diff = changes();
    get("ti-profile-status").textContent = !editorData ? "" : diff.added.length + diff.removed.length
      ? "Alterações não salvas" : stored.get(selectedProfile.id).source === "current_rules"
        ? "Permissões atuais" : editorData?.active ? "Permissões aplicadas" : "Configuração em validação";
  }
  function refreshSave() {
    get("ti-save").disabled = saving || pendingProfiles().length === 0;
  }
  function markChanged() {
    get("ti-feedback").hidden = true;
    refreshSave();
    refreshStatus();
    renderProfiles();
  }
  function renderEditor() {
    get("ti-selected-name").textContent = selectedProfile.name;
    get("ti-selected-avatar").replaceChildren(icon(selectedProfile.glyph));
    refreshStatus();
    renderAreas();
    renderModules();
    refreshSave();
    renderProfiles();
  }

  get("ti-profile-search").addEventListener("input", renderProfiles);
  get("ti-area-enabled").addEventListener("change", (event) => {
    draft().areas[event.target.checked ? "add" : "delete"](selectedArea);
    if (!event.target.checked) {
      catalog.find((area) => area.id === selectedArea).modules.forEach((module) => module.actions.forEach((action) => draft().permissions.delete(`${module.id}.${action}`)));
    }
    renderModules();
    markChanged();
  });
  get("ti-save").addEventListener("click", async () => {
    if (saving) return;
    const pending = pendingProfiles();
    if (!pending.length) return;
    saving = true;
    const feedback = get("ti-feedback");
    feedback.hidden = true;
    get("ti-save").disabled = true;
    try {
      if (!window.Swal) throw new Error("Não foi possível abrir a confirmação. Recarregue a central.");
      const result = await window.Swal.fire({
        title: "Salvar alterações?",
        text: `Deseja salvar a configuração de ${pending.length} ${pending.length === 1 ? "tipo de usuário" : "tipos de usuário"}?`,
        icon: "question",
        iconColor: getComputedStyle(root).getPropertyValue("--color-primary").trim(),
        showCancelButton: true,
        confirmButtonText: "Sim, salvar",
        cancelButtonText: "Cancelar",
        reverseButtons: true,
        focusCancel: true,
        buttonsStyling: false,
        customClass: {
          popup: `ti-confirm-popup${document.body.classList.contains("dark-mode") ? " swal2-dark-mode" : ""}`,
          confirmButton: "btn btn-primary",
          cancelButton: "btn btn-outline-secondary",
        },
        footer: editorData?.active ? "Ao confirmar, menus, telas e ações serão atualizados para todos os usuários desses perfis na próxima requisição." : editorData ? "Configurações em validação. Os acessos atuais permanecem iguais." : "Prévia visual: nenhuma permissão real será alterada.",
      });
      if (result.isConfirmed) {
        if (editorData) {
          root.inert = true;
          root.setAttribute("aria-busy", "true");
          const response = await fetch(editorData.save_url, {
            method: "POST", credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-Central-TI-CSRF": editorData.csrf_token },
            body: JSON.stringify({ profiles: pending.map((profile) => ({
              id: profile.id, version: stored.get(profile.id).version,
              areas: Array.from(drafts.get(profile.id).areas), permissions: Array.from(drafts.get(profile.id).permissions),
            })) }),
          });
          if (response.redirected) throw new Error("Sua sessão pode ter expirado. Entre novamente e recarregue a central.");
          if (!response.headers.get("Content-Type")?.includes("application/json")) throw new Error("Não foi possível salvar. Recarregue a central e tente novamente.");
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || "Não foi possível salvar a configuração.");
          result.profiles.forEach((state) => {
            stored.set(state.id, state);
            if (result.active_rules_changed) currentRules.set(state.id, { permissions: new Set(state.permissions), notes: currentRules.get(state.id)?.notes || {} });
          });
        }
        pending.forEach((profile) => baseline.set(profile.id, copySelection(drafts.get(profile.id))));
        renderProfiles();
        refreshStatus();
        renderModules();
        feedback.textContent = editorData?.active ? "Permissões aplicadas. Menus, telas e ações serão atualizados no próximo acesso ou ao recarregar." : editorData ? "Configuração salva para validação. Os acessos atuais permanecem iguais." : "Simulação salva. Nenhuma permissão real foi alterada.";
        feedback.hidden = false;
      }
    } catch (error) {
      feedback.textContent = editorData ? (error instanceof TypeError ? "Não foi possível salvar. Confira sua conexão e tente novamente." : error.message || "Não foi possível salvar. Tente novamente.") : "Não foi possível abrir a confirmação. Recarregue a página e tente novamente.";
      feedback.hidden = false;
    } finally {
      saving = false;
      root.inert = false;
      root.removeAttribute("aria-busy");
      refreshSave();
    }
  });
  renderEditor();
})();
