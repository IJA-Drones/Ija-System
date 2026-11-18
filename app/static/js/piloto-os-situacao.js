(() => {
  'use strict';

  function init() {
    const form = document.getElementById('os-form-main');
    const rulesElement = document.getElementById('os-execucao-regras');
    if (!form || !rulesElement) return;

    const rules = JSON.parse(rulesElement.textContent);
    const situation = form.querySelector('[name="situacao_aplicacao"]');
    const application = document.getElementById('os-campos-aplicacao');
    const note = document.getElementById('os-sem-aplicacao-aviso');
    const reason = form.querySelector('[name="motivo_nao_realizacao"]');
    const reasonMarker = document.getElementById('os-motivo-obrigatorio');
    if (!situation || !application) return;

    function sync() {
      const noFlight = situation.value === rules.situacao_sem_voo;
      const noApplication = rules.situacoes_sem_aplicacao.includes(situation.value);
      // Disable the fieldset rather than individual inputs: edit reservations and read-only
      // permissions still control the inputs, and temporary selections keep unsaved values.
      application.disabled = noApplication;
      application.hidden = noApplication;
      if (note) {
        note.hidden = !noApplication;
        note.textContent = noFlight
          ? 'Nenhum voo realizado: informe o motivo e os dados do atendimento. Produto e dosagem não se aplicam. Registre observações de campo somente se foram realizadas.'
          : 'Apenas monitorado: preencha as observações do atendimento. Produto e dosagem não se aplicam.';
      }
      if (reason) reason.required = noFlight;
      if (reasonMarker) reasonMarker.hidden = !noFlight;
      rules.campos_observacao.forEach(name => {
        const input = form.querySelector(`[name="${name}"]`);
        const marker = form.querySelector(`[data-obrigatorio-observacao="${name}"]`);
        if (input) input.required = !noFlight;
        if (marker) marker.hidden = noFlight;
      });
    }

    situation.addEventListener('change', sync);
    sync();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
