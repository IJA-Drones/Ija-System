(() => {
  'use strict';
  window.initOrthoBasemap = base => {
    const select = document.getElementById('ortho-basemap');
    const status = document.getElementById('ortho-basemap-status');
    const credit = document.getElementById('ortho-google-credit');
    const {key} = JSON.parse(document.getElementById('ortho-basemap-config').textContent);
    const streets = base.getSource();
    let google = null;
    function notice(text, error = false) {
      status.textContent = text;
      status.classList.toggle('error', error);
    }
    function fallback(text) {
      base.setSource(streets);base.setVisible(true);credit.hidden = true;
      select.value = 'streets';notice(text + ' O mapa de ruas continua disponível.', true);
    }
    function activateGoogle(source) {
      if (google !== source || select.value !== 'satellite') return;
      if (source.getState() === 'error') {
        fallback(source.userError || 'Não foi possível carregar o Google Satélite. Verifique a chave, a Map Tiles API e as permissões do site.');
      } else if (source.getState() === 'ready') {
        base.setSource(source);base.setVisible(true);credit.hidden = false;
        notice('Fundo: Google Satélite. Sobreposição: ortomosaico enviado ao IJA System.');
      }
    }
    // The pinned OpenLayers source handles sessions, renewal and viewport credits.
    // Convert network failures into a source error as well; never display raw API responses.
    class SatelliteSource extends ol.source.Google {
      async fetchSessionToken(url, config) {
        try {
          const response = await fetch(url, {...config, signal: AbortSignal.timeout(15000)});
          if (!response.ok) {
            const data = await response.clone().json().catch(() => ({}));
            const reasons = (data.error?.details || []).map(detail => detail.reason);
            this.userError = reasons.includes('API_KEY_INVALID')
              ? 'O Google recusou a chave configurada para o satélite. É necessário configurar uma chave válida.'
              : 'Google Satélite indisponível. Confira a habilitação da Map Tiles API, as restrições da chave e o faturamento no Google Cloud.';
          }
          return response;
        } catch (_) {
          this.userError = 'Não foi possível conectar ao Google Satélite. Confira sua conexão e tente novamente.';
          return new Response(JSON.stringify({error: {message: 'Satellite connection unavailable'}}), {status: 503});
        }
      }
    }
    function change() {
      credit.hidden = true;
      if (select.value !== 'satellite') {
        base.setSource(streets);base.setVisible(select.value === 'streets');
        notice(select.value === 'streets' ? 'Fundo: mapa de ruas OpenStreetMap.' : 'Mapa de fundo oculto.');
        return;
      }
      if (!key) {
        fallback('Google Satélite ainda não foi configurado.');return;
      }
      notice('Carregando Google Satélite…');
      if (google?.getState() === 'error' || google?.retryRequired) {google.dispose();google = null;}
      if (!google) {
        const source = new SatelliteSource({key, mapType: 'satellite', language: 'pt-BR', region: 'BR', attributionsCollapsible: false});
        google = source;
        source.on('change', () => activateGoogle(source));
        source.on('tileloaderror', () => {
          if (google === source && select.value === 'satellite') {
            source.retryRequired = true;
            fallback('Uma parte das imagens do Google não carregou. Selecione Google Satélite para tentar novamente.');
          }
        });
      }
      activateGoogle(google);
    }
    select.addEventListener('change', change);
    change();
  };
})();
