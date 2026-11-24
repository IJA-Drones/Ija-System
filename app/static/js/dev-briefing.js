/* A login invitation; private data and narration load only after a choice. */
(() => {
  document.addEventListener('DOMContentLoaded', () => {
    const card = document.getElementById('devBriefing');
    const root = document.querySelector('[data-azul-help]');
    if (!card || !root) return;
    const listen = document.getElementById('devBriefingListen');
    const read = document.getElementById('devBriefingRead');
    const status = document.getElementById('devBriefingStatus');
    const result = document.getElementById('devBriefingResult');
    const speech = document.getElementById('devBriefingSpeech');
    let request = null, generation = 0, invitation = null, context = null, invited = false;
    const setStatus = text => { status.textContent = text; };
    function stopInvitation() {
      if (invitation) { invitation.pause(); invitation.src = ''; invitation = null; root.azulCompanion?.speaking(false); }
    }
    function stop() {
      generation++;
      request?.abort(); request = null;
      stopInvitation();
      root.azulCompanion?.stopVoice();
      if (context) { context.close().catch(() => {}); context = null; }
      listen.disabled = read.disabled = false;
    }
    async function invite() {
      if (invited || document.hidden || card.hidden || card.dataset.invite !== '1') return;
      invited = true;
      if (root.dataset.voiceEngine === 'browser-pt-BR') {
        const version = generation;
        if (!root.azulAudioPolicy || !await root.azulAudioPolicy.check('sound')) return;
        if (version !== generation || card.hidden || document.hidden) return;
        try { await window.AzulNativeVoice?.speak(root,'Gostaria de ouvir suas pendências de hoje?',{emitEvents:false}); }
        catch (_) { setStatus('Escolha Ouvir pendências para iniciar a voz brasileira da Jett.'); }
        return;
      }
      // A generic prerecorded phrase has no user data and never invokes synthesis on load.
      if (!/^\/static\/audio\/azul-falas\/[a-f0-9]{64}\.wav(?:\?v=[a-f0-9]{12})?$/.test(card.dataset.clip || '') || typeof Audio !== 'function') return;
      const version = generation;
      if (!root.azulAudioPolicy || !await root.azulAudioPolicy.check('sound')) return;
      if (version !== generation || card.hidden || document.hidden) return;
      invitation = new Audio(card.dataset.clip);
      invitation.onplaying = () => root.azulCompanion?.speaking(true);
      invitation.onended = stopInvitation;
      invitation.onerror = stopInvitation;
      try { await invitation.play(); root.azulAudioPolicy.record(card.dataset.clip); }
      catch (_) { stopInvitation(); setStatus('Escolha Ouvir pendências para iniciar a voz da Azul.'); }
    }
    async function load(speak) {
      if (request) return;
      stopInvitation();
      root.azulCompanion?.stopVoice();
      const controller = new AbortController();
      request = controller;
      const version = ++generation;
      listen.disabled = read.disabled = true;
      speech.replaceChildren(); result.hidden = true; result.textContent = '';
      setStatus('Consultando falhas e bugs das últimas 24 horas…');
      const timer = setTimeout(() => controller.abort(), 15000);
      try {
        if (speak && !context) {
          const AudioContext = window.AudioContext || window.webkitAudioContext;
          if (AudioContext) {
            try { context = new AudioContext(); await context.resume(); root.azulCompanion?.useAudioContext(context); }
            catch (_) { context?.close().catch(() => {}); context = null; }
          }
        }
        if (version !== generation) return;
        const response = await fetch(card.dataset.url, {headers: {Accept:'application/json'}, cache:'no-store', signal:controller.signal});
        if (version !== generation) return;
        if ([401,403,409].includes(response.status)) {
          stop(); card.hidden = true; result.textContent = ''; speech.replaceChildren();
          root.dispatchEvent(new CustomEvent('azul:access-changed')); return;
        }
        if (!response.ok) throw new Error('Não foi possível consultar as pendências. Tente novamente.');
        const payload = await response.json();
        if (version !== generation) return;
        if (typeof payload.answer !== 'string') throw new Error('Resumo indisponível. Tente novamente.');
        result.textContent = payload.answer;
        result.hidden = false;
        const links = document.createElement('div'); links.className = 'dev-briefing-links';
        for (const item of (Array.isArray(payload.links) ? payload.links : []).slice(0,4)) {
          if (!item || typeof item.label !== 'string' || !/^\/dev\?erro=[1-9][0-9]{0,17}$|^\/feedback$/.test(item.url)) continue;
          const link = document.createElement('a'); link.href = item.url; link.textContent = item.label; links.append(link);
        }
        result.append(links);
        const button = root.azulCompanion?.attachSpeech(speech, payload.speech, 'Ouvir resumo');
        setStatus(button ? 'Resumo atualizado. Use o controle abaixo para ouvir ou parar a narração.' : 'Resumo disponível em texto. A voz está indisponível ou desativada nas configurações da Azul.');
        if (speak && button) button.click();
      } catch (error) {
        if (version !== generation) return;
        setStatus(error.name === 'AbortError' ? 'A consulta demorou. Tente novamente.' : error.message);
      } finally {
        clearTimeout(timer);
        if (version === generation) { request = null; listen.disabled = read.disabled = false; }
      }
    }
    listen.addEventListener('click', () => load(true));
    read.addEventListener('click', () => load(false));
    document.getElementById('devBriefingDismiss').addEventListener('click', () => { stop(); card.hidden = true; });
    document.getElementById('devBriefingOpen')?.addEventListener('click', () => {
      card.hidden = false;
      card.scrollIntoView({block:'start',behavior:'smooth'});
      listen.focus({preventScroll:true});
    });
    root.addEventListener('azul:access-changed', () => { stop(); card.hidden = true; result.textContent = ''; speech.replaceChildren(); });
    document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); else invite(); });
    window.addEventListener('pagehide', stop);
    invite();
  });
})();
