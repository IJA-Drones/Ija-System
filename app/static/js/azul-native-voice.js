/* Native pt-BR narration. Never substitute a different language or a server voice. */
(() => {
  if (window.AzulNativeVoice) return;
  let owner = null;
  const abortError = () => Object.assign(new Error('Narração interrompida.'), {name:'AbortError'});
  function chooseVoice(voices) {
    const brazilian = voices.filter(voice => /^pt[-_]br$/i.test(voice.lang || ''));
    const names = ['Luciana','Francisca','Thalita','Brenda','Giovanna','Manuela','Yara','Helena','Heloisa','Elza','Leila','Google português do Brasil','Google Brazilian Portuguese'];
    for (const name of names) {
      const found = brazilian.find(voice => voice.name.toLocaleLowerCase('pt-BR').includes(name.toLocaleLowerCase('pt-BR')));
      if (found) return found;
    }
    return null;
  }
  function controller(root) {
    if (root.azulNativeVoice) return root.azulNativeVoice;
    const synth = window.speechSynthesis;
    let version = 0, utterance = null, rejectPending = null, cleanup = () => {};
    function stop() {
      version++; cleanup(); cleanup = () => {};
      if (owner === root) { owner = null; synth?.cancel(); }
      utterance = null;
      const reject = rejectPending; rejectPending = null;
      root.azulCompanion?.speaking(false);
      reject?.(abortError());
    }
    async function speak(text, options={}) {
      if (!synth || typeof window.SpeechSynthesisUtterance !== 'function') throw new Error('A voz brasileira do dispositivo não está disponível neste navegador. Continue pelo texto.');
      if (typeof text !== 'string' || !text.trim() || text.length > 3000) throw new Error('Texto indisponível para narração.');
      if (owner && owner !== root) owner.azulNativeVoice?.stop();
      stop();
      const expected = version;
      let voice = chooseVoice(synth.getVoices());
      if (!voice) {
        await new Promise((resolve,reject) => {
          const changed = () => { if (chooseVoice(synth.getVoices())) { done(); resolve(); } };
          const timer = setTimeout(() => { done(); resolve(); }, 2500);
          const done = () => { clearTimeout(timer); synth.removeEventListener('voiceschanged', changed); };
          cleanup = done; rejectPending = reject;
          synth.addEventListener('voiceschanged', changed);
          changed();
        });
        rejectPending = null; cleanup = () => {};
        if (expected !== version) throw abortError();
        voice = chooseVoice(synth.getVoices());
      }
      if (!voice) throw new Error('Nenhuma voz feminina pt-BR foi encontrada. Instale uma voz brasileira no dispositivo; não vou substituí-la por outro idioma.');
      return new Promise((resolve,reject) => {
        const message = new window.SpeechSynthesisUtterance(text);
        utterance = message; owner = root; rejectPending = reject;
        message.voice = voice; message.lang = 'pt-BR'; message.rate = .98; message.pitch = 1.06; message.volume = 1;
        const timer = setTimeout(() => { if (expected === version) stop(); }, 180000);
        const finish = (error) => {
          if (expected !== version) return;
          clearTimeout(timer); cleanup = () => {}; rejectPending = null;
          utterance = null; if (owner === root) owner = null;
          root.azulCompanion?.speaking(false);
          if (error) {
            if (options.emitEvents !== false) root.dispatchEvent(new CustomEvent('azul:voice-error'));
            reject(error);
          } else {
            if (options.emitEvents !== false) root.dispatchEvent(new CustomEvent('azul:voice-ended'));
            resolve();
          }
        };
        cleanup = () => { clearTimeout(timer); message.onstart = message.onend = message.onerror = null; };
        message.onstart = () => {
          if (expected !== version) return;
          root.azulCompanion?.speaking(true); options.onStart?.(voice.name);
          if (options.emitEvents !== false) root.dispatchEvent(new CustomEvent('azul:voice-started'));
        };
        message.onend = () => finish();
        message.onerror = () => finish(new Error('Não foi possível falar agora. Clique em ouvir novamente ou continue pelo texto.'));
        try { synth.speak(message); } catch (error) { finish(error); }
      });
    }
    root.azulNativeVoice = {speak,stop};
    window.addEventListener('pagehide', stop);
    document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
    return root.azulNativeVoice;
  }
  function attach(root,container,offer,idleLabel) {
    if (!offer || typeof offer.text !== 'string' || offer.text.length > 3000) return;
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'azul-speak'; button.textContent = idleLabel;
    button.setAttribute('aria-pressed','false');
    button.setAttribute('aria-label', idleLabel + ' com voz brasileira do dispositivo');
    let active = false;
    button.addEventListener('click', async event => {
      if (event?.isTrusted && root.azulVoice?.isActive()) root.azulVoice.stop();
      if (active) { controller(root).stop(); return; }
      if (root.azulAudioPolicy && !await root.azulAudioPolicy.check('sound')) return;
      root.azulCompanion?.stopVoice();
      active = true; button.textContent = 'Parar áudio'; button.setAttribute('aria-pressed','true');
      try { await controller(root).speak(offer.text); }
      catch (error) { if (error.name !== 'AbortError') { const status=root.querySelector('[data-voice-status]'); if (status) status.textContent=error.message; } }
      finally { active=false; button.textContent=idleLabel; button.setAttribute('aria-pressed','false'); }
    });
    container.append(button); return button;
  }
  window.AzulNativeVoice = {chooseVoice, speak:(root,text,options)=>controller(root).speak(text,options), attach};
})();
