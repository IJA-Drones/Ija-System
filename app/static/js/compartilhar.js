// Compartilhamento em redes sociais: folha nativa do celular quando existe; senão, menu com as redes.
(function () {
  'use strict';
  const APP_URL = location.origin + '/app';
  const nets = (text, url) => {
    const t = encodeURIComponent(text), u = encodeURIComponent(url), tu = encodeURIComponent(text + ' ' + url);
    return [
      ['WhatsApp', 'https://wa.me/?text=' + tu, '#25D366'],
      ['Facebook', 'https://www.facebook.com/sharer/sharer.php?u=' + u + '&quote=' + t, '#1877F2'],
      ['Telegram', 'https://t.me/share/url?url=' + u + '&text=' + t, '#229ED9'],
      ['X', 'https://twitter.com/intent/tweet?text=' + t + '&url=' + u, '#111111'],
    ];
  };
  function menu(text, url) {
    let box = document.getElementById('ija-share-menu');
    if (box) box.remove();
    box = document.createElement('div');
    box.id = 'ija-share-menu';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-label', 'Compartilhar');
    box.style.cssText = 'position:fixed;inset:0;z-index:2000;background:rgba(6,24,39,.45);display:flex;align-items:flex-end;justify-content:center';
    const links = nets(text, url).map(([n, href, c]) => `<a href="${href}" target="_blank" rel="noopener" style="display:block;padding:14px 16px;margin:6px 0;border-radius:12px;background:${c};color:#fff;text-decoration:none;font-weight:600;text-align:center">${n}</a>`).join('');
    box.innerHTML = `<div style="background:#fff;width:100%;max-width:480px;border-radius:18px 18px 0 0;padding:18px 18px calc(18px + env(safe-area-inset-bottom));font-family:inherit">
      <div style="font-weight:600;color:#1c2b3f;margin-bottom:6px">Compartilhar</div>${links}
      <button type="button" data-copy style="width:100%;padding:14px;margin-top:6px;border-radius:12px;border:1px solid #94a3b8;background:#fff;font-weight:600;color:#087088">Copiar texto</button>
      <button type="button" data-close style="width:100%;padding:12px;margin-top:6px;border:0;background:transparent;color:#718096">Fechar</button></div>`;
    box.addEventListener('click', (e) => { if (e.target === box || e.target.hasAttribute('data-close')) box.remove(); });
    box.querySelector('[data-copy]').addEventListener('click', async (e) => {
      try { await navigator.clipboard.writeText(text + ' ' + url); e.target.textContent = 'Copiado!'; } catch (err) { e.target.textContent = 'Não foi possível copiar'; }
    });
    document.body.appendChild(box);
  }
  async function share({ title, text, url }) {
    url = url || APP_URL;
    if (navigator.share) {
      try { await navigator.share({ title: title || 'IJA Vigilância', text, url }); return; }
      catch (err) { if (err && err.name === 'AbortError') return; }
    }
    menu(text, url);
  }
  window.ijaShare = share;
  window.ijaShareTexts = {
    app: (cidade) => `Ajude a combater o mosquito da dengue${cidade ? ' em ' + cidade : ''}: relate focos e receba alertas da vigilância pelo app IJA Vigilância.`,
    foco: (cidade) => `Acabei de relatar um possível foco do mosquito da dengue${cidade ? ' em ' + cidade : ''} pelo app IJA Vigilância. Faça sua parte também: elimine água parada e relate focos.`,
    caso: () => 'Fique atento aos sintomas de dengue, zika e chikungunya (febre, dor no corpo, manchas). Em caso de suspeita, procure a unidade de saúde. Saiba mais no app IJA Vigilância.',
    alerta: (cidade, titulo, mensagem) => `⚠️ Alerta da vigilância em saúde${cidade ? ' – ' + cidade : ''}: ${titulo}. ${mensagem || ''} Proteja sua casa: elimine água parada.`,
    boletim: (cidade, nivel) => `Boletim da dengue${cidade ? ' em ' + cidade : ''}${nivel ? ': nível de alerta ' + nivel : ''}. Proteja sua família, elimine água parada e relate focos pelo IJA Vigilância.`,
  };
  // Botões declarativos: <button data-share="app|boletim" data-cidade="..." data-nivel="...">
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-share]');
    if (!b) return;
    e.preventDefault();
    const kind = b.dataset.share, T = window.ijaShareTexts;
    const text = kind === 'boletim' ? T.boletim(b.dataset.cidade, b.dataset.nivel) : kind === 'caso' ? T.caso() : kind === 'foco' ? T.foco(b.dataset.cidade) : T.app(b.dataset.cidade);
    share({ text, url: b.dataset.url || APP_URL });
  });
})();
