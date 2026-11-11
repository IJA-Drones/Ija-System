/* Microphone turns use the same guarded chat as text. No direct voice-agent session. */
(() => {
  for (const root of new Set([...document.querySelectorAll('[data-azul-help]'), ...document.querySelectorAll('[data-azul-companion]')])) {
    const controls = root.querySelector('[data-voice-controls]');
    if (!controls || root.azulVoice) continue;
    const mic = controls.querySelector('[data-microphone]'), action = controls.querySelector('[data-voice-action]');
    const dictate = controls.querySelector('[data-dictate]');
    const status = controls.querySelector('[data-microphone-status]') || root.querySelector('[data-microphone-status]');
    const call = root.querySelector('[data-voice-call]');
    const callTitle = call?.querySelector('[data-call-title]'), callDescription = call?.querySelector('[data-call-description]');
    const callAction = call?.querySelector('[data-call-action]'), callActionLabel = call?.querySelector('[data-call-action-label]');
    const callEnd = call?.querySelector('[data-call-end]');
    const url = root.dataset.transcribeUrl;
    if (!['/api/azul/transcrever','/portal-cidadao/transcrever'].includes(url)) { controls.hidden = true; continue; }
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!navigator.mediaDevices?.getUserMedia || !Context) {
      mic.disabled = true; if (dictate) dictate.disabled = true;
      root.dataset.voiceNotice = '1'; status.textContent = 'O microfone precisa de um navegador compatível e de HTTPS ou localhost.'; continue;
    }
    let active = false, version = 0, context = null, capture = null, request = null, clipSource = null, greeted = false;
    let phase = 'idle', mode = 'conversation', turns = 0, sessionTimer = null, nextTimer = null, moduleReady = null;
    function state(value, text, notice = false) {
      phase = value; root.dataset.voiceState = value; root.dataset.voiceMode = active ? mode : '';
      root.dataset.voiceNotice = notice ? '1' : '0';
      mic.setAttribute('aria-pressed', String(active && mode === 'conversation'));
      mic.setAttribute('aria-label', active ? 'Encerrar conversa por voz com a AZUL' : 'Conversar por voz com a AZUL');
      mic.setAttribute('title', active ? 'Encerrar conversa por voz' : 'Conversar por voz com a AZUL. Sua fala será transcrita por IA.');
      mic.querySelector('span').textContent = active ? 'Encerrar voz' : 'Conversar por voz';
      if (dictate) {
        dictate.setAttribute('aria-pressed',String(active && mode === 'dictation'));
        dictate.setAttribute('aria-label',active && mode === 'dictation' ? 'Concluir ditado' : 'Ditar mensagem');
      }
      action.hidden = !active || mode === 'dictation';
      const actionText = value === 'listening' ? 'Enviar fala' : 'Interromper e falar';
      const actionLabel = action.querySelector?.('[data-voice-action-label]');
      if (actionLabel) actionLabel.textContent = actionText; else action.textContent = actionText;
      action.setAttribute('aria-label',actionText); action.setAttribute('title',actionText);
      status.textContent = text;
      const calling = active && mode === 'conversation';
      root.dataset.voiceCallOpen = calling ? '1' : '0';
      if (call) {
        const wasOpen = !call.hidden;
        call.hidden = !calling;
        callTitle.textContent = ({starting:'Conectando…',listening:'Estou ouvindo',transcribing:'Entendendo sua fala…',waiting:'Pensando na sua pergunta…',preparing:'Preparando a voz…',speaking:'A AZUL está falando'})[value] || 'Conversa com a AZUL';
        callDescription.textContent = text;
        const label = value === 'listening' ? 'Enviar fala' : 'Falar agora';
        callActionLabel.textContent = label; callAction.setAttribute('aria-label',label); callAction.setAttribute('title',label);
        callAction.disabled = value === 'starting';
        if (calling && !wasOpen) call.focus();
        else if (!calling && wasOpen) mic.focus();
      }
    }
    function release(segment) {
      if (!segment) return;
      clearTimeout(segment.silenceTimer); clearTimeout(segment.limitTimer);
      segment.node?.disconnect(); segment.source?.disconnect(); segment.gain?.disconnect();
      if (segment.node?.port) segment.node.port.onmessage = null;
      if (segment.node) segment.node.onaudioprocess = null;
      segment.stream.getTracks().forEach(track => track.stop());
    }
    function stopClip() {
      if (!clipSource) return;
      clipSource.onended = null;
      try { clipSource.stop(); } catch (_) {}
      clipSource.disconnect(); clipSource = null;
      root.azulCompanion?.speaking(false);
    }
    async function sayClip(kind) {
      const expected = version, controller = new AbortController(); request = controller;
      const clips = {
        welcome:{url:'/static/audio/azul-inicio-chamada.wav',text:'Olá! Sou a AZUL. Como posso ajudar você?'},
        scope:{url:'/static/audio/azul-escopo-chamada.wav',text:'Posso ajudar com o sistema, saúde, dengue e dados epidemiológicos. Sobre qual desses assuntos você quer conversar?'}
      };
      state('preparing','A AZUL está entrando na conversa…'); root.azulCompanion?.thinking(true);
      const timeout = setTimeout(() => controller.abort(),10000);
      try {
        const response = await fetch(clips[kind].url,{signal:controller.signal,credentials:'same-origin'});
        if (!response.ok) throw new Error('Clip unavailable');
        const bytes = await response.arrayBuffer();
        if (expected !== version || !active) return;
        const decoded = await context.decodeAudioData(bytes);
        if (expected !== version || !active) return;
        request = null;
        const source = context.createBufferSource(); clipSource = source; source.buffer = decoded; source.connect(context.destination);
        source.onended = () => {
          if (clipSource !== source) return;
          source.disconnect(); clipSource = null; root.azulCompanion?.speaking(false);
          if (active && expected === version) nextTimer = setTimeout(listen,200);
        };
        root.azulCompanion?.thinking(false); root.azulCompanion?.speaking(true);
        state('speaking',clips[kind].text); source.start(); root.azulAudioPolicy?.record(clips[kind].url);
      } catch (_) {
        if (expected === version && active) { request = null; root.azulCompanion?.thinking(false); listen(); }
      } finally { clearTimeout(timeout); }
    }
    function stop(message = 'Microfone desligado. Você pode continuar escrevendo.') {
      active = false; version++;
      clearTimeout(sessionTimer); clearTimeout(nextTimer);
      request?.abort(); request = null;
      stopClip();
      release(capture); capture = null;
      root.azulCompanion?.listening(false); root.azulCompanion?.thinking(false); root.azulCompanion?.stopVoice();
      root.azulCompanion?.useAudioContext(null);
      context?.close().catch(() => {}); context = null; moduleReady = null;
      state('idle',message,message !== 'Microfone desligado. Você pode continuar escrevendo.');
    }
    function wav(segment) {
      const samples = new Float32Array(segment.count);
      let offset = 0;
      for (const block of segment.blocks) { samples.set(block,offset); offset += block.length; }
      const count = Math.min(16000*(root.azulAudioPolicy?.current.speech_seconds || 30), Math.floor(samples.length * 16000 / segment.rate));
      const bytes = new ArrayBuffer(44 + count * 2), view = new DataView(bytes);
      const word = (at,text) => { for (let i=0;i<text.length;i++) view.setUint8(at+i,text.charCodeAt(i)); };
      word(0,'RIFF'); view.setUint32(4,36+count*2,true); word(8,'WAVE'); word(12,'fmt ');
      view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true);
      view.setUint32(24,16000,true); view.setUint32(28,32000,true); view.setUint16(32,2,true); view.setUint16(34,16,true);
      word(36,'data'); view.setUint32(40,count*2,true);
      for (let i=0;i<count;i++) {
        const from = Math.floor(i * segment.rate / 16000), to = Math.min(samples.length,Math.floor((i+1) * segment.rate / 16000));
        let sum = 0; for (let j=from;j<to;j++) sum += samples[j];
        const value = Math.max(-1,Math.min(1,sum / Math.max(1,to-from)));
        view.setInt16(44+i*2,Math.round(value * (value < 0 ? 32768 : 32767)),true);
      }
      return new Blob([bytes],{type:'audio/wav'});
    }
    async function finishTurn() {
      const segment = capture, expected = version;
      if (!segment || !active) return;
      capture = null; release(segment); root.azulCompanion?.listening(false);
      if (segment.heard < .2) { stop('Não ouvi uma fala. Toque no microfone para tentar novamente.'); return; }
      state('transcribing','Entendendo sua fala…'); root.azulCompanion?.thinking(true);
      const controller = new AbortController(); request = controller;
      const timeout = setTimeout(() => controller.abort(),35000);
      try {
        const response = await fetch(url,{
          method:'POST',signal:controller.signal,credentials:'same-origin',
          headers:{'Content-Type':'audio/wav','X-CSRFToken':root.dataset.csrf,
            'X-Azul-Voice-Mode':mode,
            'X-Azul-Conversation':root.dataset.conversationId || '',
            ...(root.dataset.token ? {'X-Portal-Chat-Token':root.dataset.token} : {'X-Azul-Chat-Key':root.dataset.chatKey})},
          body:wav(segment)
        });
        if (expected !== version || !active) return;
        const result = await response.json();
        if (!response.ok || !result.text) {
          if ([401,403,409].includes(response.status)) root.dispatchEvent(new CustomEvent('azul:access-changed'));
          throw new Error(result.error || 'Não consegui entender essa fala. Tente novamente.');
        }
        request = null;
        if (mode === 'dictation') {
          const input = root.querySelector('[data-compose-input]');
          const text = input.value ? input.value.trimEnd() + ' ' + result.text : result.text;
          if (text.length > (input.maxLength > 0 ? input.maxLength : 1500)) {
            stop('O ditado excedeu o espaço da mensagem. Envie o texto atual antes de ditar mais.'); return;
          }
          stop(); input.value = text; input.dispatchEvent(new Event('input',{bubbles:true})); input.focus(); return;
        }
        turns++;
        state('waiting','A AZUL está preparando sua resposta…');
        root.dispatchEvent(new CustomEvent('azul:ask',{detail:{message:result.text,voice:true}}));
      } catch (error) {
        if (expected === version) stop(error.name === 'AbortError' ? 'A fala demorou. Tente novamente ou escreva sua pergunta.' : error.message);
      } finally { clearTimeout(timeout); }
    }
    async function listen() {
      const expected = version;
      if (active && mode==='conversation' && greeted && root.azulAudioPolicy && !await root.azulAudioPolicy.check('conversation')) {
        if (active && expected===version) stop(root.azulAudioPolicy.message); return;
      }
      if (expected!==version) return;
      const limits=root.azulAudioPolicy?.current || {};
      if (!active || turns >= (limits.session_turns || 10)) { if (active) stop('Conversa concluída. Toque no microfone para começar outra.'); return; }
      state('starting','Ligando o microfone…');
      try {
        const stream = await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
        if (!active || expected !== version) { stream.getTracks().forEach(track => track.stop()); return; }
        if (mode === 'conversation' && !greeted) {
          greeted = true; stream.getTracks().forEach(track => track.stop());
          sayClip('welcome'); return;
        }
        const segment = {stream,rate:context.sampleRate,blocks:[],count:0,heard:0,lastSpeech:0};
        capture = segment;
        segment.silenceTimer = setTimeout(() => { if (capture === segment && segment.heard < .2) stop('Não ouvi uma fala. Toque no microfone para tentar novamente.'); },(limits.silence_seconds || 8)*1000);
        segment.limitTimer = setTimeout(() => { if (capture === segment) finishTurn(); },(limits.speech_seconds || 30)*1000+500);
        segment.source = context.createMediaStreamSource(stream); segment.gain = context.createGain(); segment.gain.gain.value = 0;
        const receive = ({samples,rms}) => {
          if (capture !== segment || !active) return;
          const seconds = samples.length / segment.rate;
          segment.blocks.push(samples); segment.count += samples.length;
          if (rms > .018) { segment.heard += seconds; segment.lastSpeech = performance.now(); }
          if (segment.heard >= .2 && performance.now()-segment.lastSpeech > 1100) finishTurn();
          else if (segment.count / segment.rate >= (limits.speech_seconds || 30)) finishTurn();
        };
        if (context.audioWorklet && typeof AudioWorkletNode === 'function') {
          try {
            moduleReady ||= context.audioWorklet.addModule('/static/js/azul-mic-processor.js?v=20261110-1');
            await moduleReady;
            if (capture !== segment || !active || expected !== version) return;
            segment.node = new AudioWorkletNode(context,'azul-mic');
            segment.node.port.onmessage = event => receive(event.data);
          } catch (_) { /* Older or restricted browsers can still capture bounded PCM. */ }
        }
        if (capture !== segment || !active || expected !== version) return;
        if (!segment.node) {
          segment.node = context.createScriptProcessor(2048,1,1);
          segment.node.onaudioprocess = event => {
            const samples = new Float32Array(event.inputBuffer.getChannelData(0));
            receive({samples,rms:Math.sqrt(samples.reduce((sum,value)=>sum+value*value,0)/samples.length)});
          };
        }
        segment.source.connect(segment.node); segment.node.connect(segment.gain); segment.gain.connect(context.destination);
        root.azulCompanion?.thinking(false); root.azulCompanion?.listening(true);
        state('listening','A AZUL está ouvindo. Fale sobre o sistema ou saúde.');
      } catch (error) {
        if (expected !== version) return;
        stop(error.name === 'NotAllowedError' ? 'Permita o microfone no navegador para conversar com a AZUL.' : 'Não foi possível abrir o microfone. Confira seu aparelho ou continue pelo texto.');
      }
    }
    async function start(selectedMode = 'conversation') {
      if (active) { stop(); root.dispatchEvent(new CustomEvent('azul:interrupt')); return; }
      mode = selectedMode;
      root.azulCompanion?.stopVoice(); root.azulCompanion?.closeGuide();
      active = true; const expected = ++version; turns = 0; greeted = false;
      root.dispatchEvent(new CustomEvent('azul:interrupt'));
      state('starting','Permita o microfone para conversar com a AZUL.');
      try {
        context = new Context(); root.azulCompanion?.useAudioContext(context);
        await context.resume();
      } catch (_) { if (expected === version) stop('Não foi possível ativar o áudio. Tente novamente.'); return; }
      if (!active || expected !== version) return;
      if (root.azulAudioPolicy && !await root.azulAudioPolicy.check(mode==='dictation'?'microphone':'conversation')) {
        stop(root.azulAudioPolicy.message || 'O som ou o microfone da AZUL foi desativado nas configurações.'); return;
      }
      if (!active || expected !== version) return;
      sessionTimer = setTimeout(() => stop('A conversa por voz foi encerrada. Toque no microfone para retomar.'),(root.azulAudioPolicy?.current.session_minutes || 5)*60000);
      listen();
    }
    mic.addEventListener('click',() => start('conversation'));
    dictate?.addEventListener('click',() => {
      if (active && mode === 'dictation') { if (phase === 'listening') finishTurn(); else stop(); return; }
      start('dictation');
    });
    function speakNext() {
      if (phase === 'starting') return;
      if (phase === 'listening') { finishTurn(); return; }
      if (!active) return;
      clearTimeout(nextTimer); version++; request?.abort(); request = null; release(capture); capture = null; stopClip(); root.azulCompanion?.stopVoice();
      root.dispatchEvent(new CustomEvent('azul:interrupt')); listen();
    }
    action.addEventListener('click',speakNext);
    callAction?.addEventListener('click',speakNext);
    callEnd?.addEventListener('click',() => { stop(); root.dispatchEvent(new CustomEvent('azul:interrupt')); });
    root.addEventListener('azul:reply',event => {
      if (!active || phase !== 'waiting') return;
      const {speechButton,mode} = event.detail || {};
      if (['blocked','clarify'].includes(mode)) { sayClip('scope'); return; }
      if (!speechButton) { stop('A resposta está no chat. O áudio está indisponível agora.'); return; }
      state('preparing','Preparando o áudio da resposta. Você pode interromper para falar.');
      speechButton.click();
    });
    root.addEventListener('azul:voice-started',() => {
      if (active && phase === 'preparing') state('speaking','Ouça a resposta ou toque em Falar agora para interromper.');
    });
    root.addEventListener('azul:voice-ended',() => {
      if (!active || phase !== 'speaking') return;
      nextTimer = setTimeout(listen,200);
    });
    root.addEventListener('azul:voice-error',() => { if (active) stop('O áudio não pôde ser reproduzido. A resposta continua no chat.'); });
    root.addEventListener('azul:reply-error',() => { if (active) stop('A conversa foi interrompida. Continue pelo texto ou tente novamente.'); });
    root.addEventListener('azul:access-changed',() => { stop('Recarregue a página para atualizar sua sessão.'); mic.disabled = true; if (dictate) dictate.disabled = true; });
    window.addEventListener('pagehide',() => stop());
    document.addEventListener('visibilitychange',() => { if (document.hidden) stop(); });
    root.azulVoice = {stop,isActive:()=>active};
    state('idle','Fale com a AZUL. O áudio será enviado para transcrição por IA. Evite dados pessoais.');
  }
})();
