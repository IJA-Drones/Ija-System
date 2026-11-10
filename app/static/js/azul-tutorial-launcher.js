/* Open the practice room inside a sandbox, separate from the operational page. */
(() => {
  let opened = null;
  const roots = new Set([...document.querySelectorAll('[data-azul-help]'), ...document.querySelectorAll('[data-azul-companion]')]);
  for (const root of roots) {
    if (!root.dataset.tutorialUrl || root.dataset.tutorialReady) continue;
    root.dataset.tutorialReady = '1';
    let quickGuide = false;
    function close() {
      if (opened?.root !== root) return;
      const {dialog,frame,observer,opener,timer} = opened;
      opened = null; clearTimeout(timer);
      root.azulCompanion?.stopVoice(); observer.disconnect(); frame.remove();
      dialog.close(); dialog.remove();
      const returnTo = opener?.getClientRects().length ? opener : root.querySelector('[data-toggle],.portal-chat-toggle');
      returnTo?.focus();
    }
    root.addEventListener('click', event => {
      const opener = event.target.closest('[data-guide-open]');
      if (!opener || !root.contains(opener) || opener.disabled || quickGuide || typeof HTMLDialogElement !== 'function') return;
      let url;
      try { url = new URL(root.dataset.tutorialUrl,location.origin); } catch (_) { return; }
      if (url.origin !== location.origin || url.pathname !== '/azul/tutorial') return;
      event.preventDefault(); event.stopImmediatePropagation();
      if (opened) opened.close();
      root.azulCompanion?.stop();
      root.dispatchEvent(new CustomEvent('azul:close'));
      const dialog = document.createElement('dialog');
      dialog.className = 'azul-training-dialog azul-help';
      dialog.setAttribute('aria-label','Aprender na prática com a Azul — dados fictícios');
      dialog.innerHTML = '<header class="azul-training-toolbar"><div><strong>Aprender na prática</strong><small>Azul · ambiente com dados fictícios</small></div><span class="azul-training-narration">Pratique no seu ritmo</span><button type="button" data-training-quick>Guia rápido em texto</button><button type="button" data-training-close aria-label="Sair do treinamento">×</button></header><p class="azul-training-loading" role="status">Abrindo a sala de prática…</p>';
      const frame = document.createElement('iframe');
      frame.title = 'Tutorial interativo da Azul com dados fictícios';
      frame.hidden = true;
      frame.setAttribute('sandbox','allow-scripts');
      frame.referrerPolicy = 'no-referrer'; frame.src = url.href;
      dialog.append(frame); document.body.append(dialog);
      const narration = dialog.querySelector('.azul-training-narration');
      const observer = new MutationObserver(() => {
        frame.contentWindow?.postMessage({type:'azul-tutorial:voice-state',state:root.dataset.droneState},'*');
      });
      observer.observe(root,{attributes:true,attributeFilter:['data-drone-state']});
      const timer = setTimeout(() => {
        if (opened?.frame !== frame) return;
        dialog.querySelector('.azul-training-loading').textContent = 'A sala de prática não carregou. Feche e tente novamente ou consulte o guia rápido em texto.';
      },12000);
      opened = {root,dialog,frame,observer,opener,timer,close};
      dialog.querySelector('[data-training-close]').addEventListener('click',close);
      dialog.querySelector('[data-training-quick]').addEventListener('click',() => {
        close(); quickGuide = true;
        try { opener.click(); } finally { quickGuide = false; }
      });
      dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
      dialog.showModal(); dialog.querySelector('[data-training-close]').focus();
      function onMessage(message) {
        if (opened?.frame !== frame || message.source !== frame.contentWindow) return;
        const payload = message.data;
        if (payload?.type === 'azul-tutorial:exit') { close(); return; }
        if (payload?.type !== 'azul-tutorial:step') return;
        clearTimeout(timer); dialog.querySelector('.azul-training-loading').hidden = true; frame.hidden = false;
        root.azulCompanion?.stopVoice(); narration.replaceChildren();
        if (payload.speech && typeof payload.speech.token === 'string' && payload.speech.token.length <= 20000) {
          root.azulCompanion?.attachSpeech(narration,payload.speech,'Ouvir esta etapa');
        }
        if (!narration.children.length) narration.textContent = 'Pratique no seu ritmo';
      }
      window.addEventListener('message',onMessage,{signal: (() => {
        const controller = new AbortController();
        dialog.addEventListener('close',() => controller.abort(),{once:true});
        return controller.signal;
      })()});
    },true);
    root.addEventListener('azul:access-changed',close);
    window.addEventListener('pagehide',close);
  }
})();
