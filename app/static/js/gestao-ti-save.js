/* Never replay an uncertain permission write: verify the saved version first. */
(() => {
  'use strict';
  const canonical = value => JSON.stringify({
    areas: [...value.areas].sort(), permissions: [...value.permissions].sort(),
    nome_acesso: (value.nome_acesso || '').trim(),
  });
  function matches(configuration, submitted, previousVersion) {
    return Boolean(configuration?.configured && configuration.version > previousVersion
      && canonical(configuration) === canonical(submitted));
  }
  async function save({write, read, submitted, previousVersion, onVerify = () => {}}) {
    try { return await write(); }
    catch (error) {
      const uncertain = ['request_timeout', 'network_error', 'invalid_response'].includes(error.code) || error.status >= 500;
      if (!uncertain) throw error;
      onVerify();
      try {
        const latest = await read();
        if (matches(latest, submitted, previousVersion)) return {configuration: latest, recovered: true};
      } catch (_) { /* Keep the user's draft when the verification also fails. */ }
      const unresolved = new Error('Não foi possível confirmar o salvamento. Suas alterações continuam nesta tela. Use “Conferir salvamento” antes de tentar novamente.');
      unresolved.code = 'save_unconfirmed';
      throw unresolved;
    }
  }
  window.IjaTiSave = {save, matches};
})();
