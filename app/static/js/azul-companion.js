/* Azul's mascot, practical guide and explicit, cancellable voice playback. */
(() => {
  new Set([...document.querySelectorAll('[data-azul-help]'), ...document.querySelectorAll('[data-azul-companion]')]).forEach(root => {
    if (root.azulCompanion) return;
    const voiceUrl = root.dataset.voiceUrl || '/api/azul/voz';
    const guide = root.querySelector('[data-guide]');
    const voiceStatus = root.querySelector('[data-voice-status]');
    let steps = [];
    try { steps = JSON.parse(root.querySelector('[data-guide-config]')?.textContent || '[]'); } catch (_) { /* Text chat still works. */ }
    if (!Array.isArray(steps)) steps = [];
    let stepIndex = 0, guideOpener = null, highlighted = null;
    let audio = null, audioRequest = null, voiceButton = null, voiceVersion = 0;
    let thinking = false, listening = false, voicePlaying = false, reactionTimer = null, speechContext = null;
    const clips = new Map();
    const setVoiceStatus = text => { if (voiceStatus) voiceStatus.textContent = text; };
    function droneState(value) { root.dataset.droneState = value; }
    function settleDrone() { droneState(voicePlaying ? 'speak' : (thinking || audioRequest) ? 'think' : listening ? 'listen' : 'idle'); }
    function stopVoice() {
      voiceVersion++;
      audioRequest?.abort();
      audioRequest = null;
      if (audio) { audio.pause?.(); try { audio.stop?.(); } catch (_) {} audio.src = ''; audio = null; }
      voicePlaying = false;
      if (voiceButton) {
        voiceButton.textContent = voiceButton.dataset.idleLabel || 'Ouvir resposta';
        voiceButton.setAttribute('aria-pressed', 'false');
        voiceButton.setAttribute('aria-busy', 'false');
      }
      voiceButton = null;
      setVoiceStatus('');
      settleDrone();
    }
    function clearAudio() {
      stopVoice();
      for (const url of clips.values()) URL.revokeObjectURL(url);
      clips.clear();
    }
    function attachSpeech(container, offer, idleLabel = 'Ouvir resposta') {
      if (!['/api/azul/voz', '/portal-cidadao/voz'].includes(voiceUrl) || !offer || offer.url !== voiceUrl || typeof offer.token !== 'string' || typeof Audio !== 'function') return;
      const recorded = typeof offer.clip === 'string' && /^\/static\/audio\/azul-falas\/[a-f0-9]{64}\.wav(?:\?v=[a-f0-9]{12})?$/.test(offer.clip) ? offer.clip : null;
      const cacheKey = recorded || offer.token;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'azul-speak';
      button.textContent = idleLabel;
      button.dataset.idleLabel = idleLabel;
      button.setAttribute('aria-label', idleLabel + ' com voz gerada por inteligência artificial');
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', async event => {
        if (event?.isTrusted && root.azulVoice?.isActive()) {
          const wasPlaying = voiceButton === button;
          root.azulVoice.stop();
          if (wasPlaying) return;
        }
        if (voiceButton === button) { stopVoice(); return; }
        stopVoice();
        const version = voiceVersion;
        voiceButton = button;
        button.setAttribute('aria-pressed', 'true');
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), recorded ? 10000 : 55000);
        try {
          let url = clips.get(cacheKey), rawAudio = null;
          if (!url) {
            audioRequest = controller;
            button.textContent = 'Parar preparação';
            button.setAttribute('aria-busy', 'true');
            setVoiceStatus(recorded ? 'Carregando a voz da Azul…' : 'Preparando a voz da Azul…');
            settleDrone();
            const response = await fetch(recorded || voiceUrl, recorded ? {
              signal:controller.signal, credentials:'same-origin'
            } : {
              method: 'POST', signal: controller.signal,
              headers: {'Content-Type': 'application/json', 'X-CSRFToken': root.dataset.csrf,
                ...(root.dataset.token ? {'X-Portal-Chat-Token':root.dataset.token} : {})},
              body: JSON.stringify({token: offer.token})
            });
            if (version !== voiceVersion) return;
            if (!response.ok) {
              const failure = await response.json().catch(() => ({}));
              if ([401, 403].includes(response.status) || failure.code === 'access_changed') {
                root.dispatchEvent(new CustomEvent('azul:access-changed'));
                return;
              }
              throw new Error(failure.error || 'A voz está indisponível agora. Continue pela resposta em texto.');
            }
            if (!/^audio\/(?:wav|x-wav|wave)(?:;|$)/i.test(response.headers.get('Content-Type') || '')) throw new Error('Não foi possível abrir o áudio. Atualize a página e tente novamente.');
            const blob = await response.blob();
            if (speechContext) rawAudio = await blob.arrayBuffer();
            if (version !== voiceVersion || controller.signal.aborted) return;
            if (!blob.size || blob.size > 9 * 1024 * 1024) throw new Error('Este áudio não está disponível. Continue pela resposta em texto.');
            url = URL.createObjectURL(blob);
            clips.set(cacheKey, url);
            while (clips.size > 3) {
              const oldest = clips.keys().next().value;
              URL.revokeObjectURL(clips.get(oldest)); clips.delete(oldest);
            }
          }
          if (version !== voiceVersion) return;
          audioRequest = null;
          const playing = () => {
            if (version !== voiceVersion) return;
            voicePlaying = true;
            button.textContent = 'Parar áudio';
            button.setAttribute('aria-busy', 'false');
            setVoiceStatus('A Azul está falando · voz gerada por IA');
            settleDrone();
            root.dispatchEvent(new CustomEvent('azul:voice-started'));
          };
          if (speechContext && speechContext.state !== 'closed') {
            const bytes = rawAudio || await (await fetch(url)).arrayBuffer();
            const decoded = await speechContext.decodeAudioData(bytes);
            if (version !== voiceVersion) return;
            audio = speechContext.createBufferSource(); audio.buffer = decoded; audio.connect(speechContext.destination);
          } else { audio = new Audio(url); audio.onplaying = playing; }
          audio.onended = () => {
            if (version !== voiceVersion) return;
            stopVoice(); root.dispatchEvent(new CustomEvent('azul:voice-ended'));
          };
          audio.onerror = () => {
            if (version !== voiceVersion) return;
            stopVoice(); setVoiceStatus('Não foi possível reproduzir o áudio. Tente ouvir novamente.');
            root.dispatchEvent(new CustomEvent('azul:voice-error'));
          };
          if (audio.start) { audio.start(); playing(); } else await audio.play();
        } catch (error) {
          if (version !== voiceVersion) return;
          stopVoice();
          setVoiceStatus(error.name === 'AbortError' ? 'A preparação do áudio demorou. Tente novamente.' :
            error.name === 'NotAllowedError' ? 'Áudio pronto. Clique em ouvir novamente para reproduzir.' : error.message);
          root.dispatchEvent(new CustomEvent('azul:voice-error'));
        } finally { clearTimeout(timer); }
      });
      container.append(button);
      return button;
    }
    function removeHighlight() {
      highlighted?.classList.remove('azul-guide-highlight');
      highlighted = null;
    }
    function highlight(target) {
      removeHighlight();
      if (target === 'screen-list' || target === 'screen-form') {
        const selector = target === 'screen-list' ? '.app-content table' : '.app-content form';
        highlighted = [...document.querySelectorAll(selector)].find(el => !el.closest('[data-azul-help]') && el.getClientRects().length);
      } else if (typeof target === 'string') {
        try { highlighted = [...root.querySelectorAll(target)].find(el => el.getClientRects().length); } catch (_) { /* Unknown guide anchor. */ }
      }
      highlighted?.classList.add('azul-guide-highlight');
    }
    function renderGuide() {
      if (!guide || !steps.length) return;
      const step = steps[stepIndex];
      root.querySelector('[data-guide-progress]').textContent = `${stepIndex + 1} de ${steps.length}`;
      root.querySelector('[data-guide-title]').textContent = step.title;
      root.querySelector('[data-guide-body]').textContent = step.body;
      root.querySelector('[data-guide-prev]').disabled = stepIndex === 0;
      root.querySelector('[data-guide-next]').textContent = stepIndex === steps.length - 1 ? 'Concluir' : 'Próximo →';
      const links = root.querySelector('[data-guide-links]');
      links.replaceChildren();
      for (const item of step.links || []) {
        if (typeof item.url !== 'string' || !item.url.startsWith('/') || item.url.startsWith('//') || item.url.includes('\\')) continue;
        const url = new URL(item.url, window.location.origin);
        if (url.origin !== window.location.origin) continue;
        const link = document.createElement('a'); link.href = url.pathname + url.search + url.hash; link.textContent = item.label; links.append(link);
      }
      const narration = root.querySelector('[data-guide-audio]');
      narration.replaceChildren();
      attachSpeech(narration, step.speech, 'Ouvir esta etapa');
      root.querySelector('[data-guide-question]').hidden = !step.question;
      highlight(step.target);
    }
    function closeGuide(focus = false) {
      if (!guide || guide.hidden) return;
      stopVoice(); removeHighlight(); guide.hidden = true;
      delete root.dataset.guideOpen;
      if (focus) guideOpener?.focus();
    }
    root.querySelectorAll('[data-guide-open]').forEach(button => button.addEventListener('click', () => {
      if (!guide || !steps.length || button.disabled) return;
      stopVoice(); guideOpener = button; stepIndex = 0;
      root.dispatchEvent(new CustomEvent('azul:open'));
      guide.hidden = false; root.dataset.guideOpen = '1'; renderGuide();
      root.querySelector('[data-guide-next]').focus();
    }));
    root.querySelector('[data-guide-close]')?.addEventListener('click', () => closeGuide(true));
    root.querySelector('[data-guide-prev]')?.addEventListener('click', () => {
      if (stepIndex > 0) { stopVoice(); stepIndex--; renderGuide(); }
    });
    root.querySelector('[data-guide-next]')?.addEventListener('click', () => {
      if (stepIndex === steps.length - 1) { closeGuide(true); return; }
      stopVoice(); stepIndex++; renderGuide();
    });
    root.querySelector('[data-guide-question]')?.addEventListener('click', () => {
      const step = steps[stepIndex];
      if (!step?.question) return;
      closeGuide();
      root.dispatchEvent(new CustomEvent('azul:ask', {detail: {message: step.question, intent: step.intent}}));
    });
    root.addEventListener('keydown', event => {
      if (event.key === 'Escape' && guide && !guide.hidden) { closeGuide(true); event.stopImmediatePropagation(); }
    });
    root.addEventListener('pointermove', event => {
      if (event.pointerType === 'touch' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      const mascot = event.target.closest('.azul-drone') || event.target.closest('.azul-launcher')?.querySelector('.azul-drone');
      if (!mascot || !root.contains(mascot)) return;
      const bounds = mascot.getBoundingClientRect();
      const x = Math.max(-1, Math.min(1, (event.clientX - bounds.left - bounds.width / 2) / bounds.width));
      const y = Math.max(-1, Math.min(1, (event.clientY - bounds.top - bounds.height / 2) / bounds.height));
      mascot.style.setProperty('--look-x', `${x * 7}px`);
      mascot.style.setProperty('--look-y', `${y * 5}px`);
      mascot.style.setProperty('--look-tilt', `${x * 4}deg`);
    });
    root.addEventListener('pointerleave', () => root.querySelectorAll('.azul-drone').forEach(mascot => {
      for (const property of ['--look-x', '--look-y', '--look-tilt']) mascot.style.removeProperty(property);
    }));
    root.azulCompanion = {
      attachSpeech,
      closeGuide,
      stopVoice,
      thinking(value) { thinking = value; settleDrone(); },
      listening(value) { listening = value; settleDrone(); },
      speaking(value) { voicePlaying = value; settleDrone(); },
      useAudioContext(context) { speechContext = context; },
      react(value = 'wave') { clearTimeout(reactionTimer); droneState(value); reactionTimer = setTimeout(settleDrone, 2200); },
      stop() { root.azulVoice?.stop(); closeGuide(); stopVoice(); },
      clear() { root.azulVoice?.stop(); closeGuide(); clearAudio(); clearTimeout(reactionTimer); thinking = false; settleDrone(); }
    };
    window.addEventListener('pagehide', () => root.azulCompanion.clear());
    document.addEventListener('visibilitychange', () => { if (document.hidden) stopVoice(); });
    droneState('idle');
  });
})();
