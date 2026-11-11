/* Server-owned audio controls and anonymous per-conversation metering labels. */
(() => {
  const roots=new Set([...document.querySelectorAll('[data-azul-help]'),...document.querySelectorAll('[data-azul-companion]')]);
  for(const root of roots){
    const publicChat=root.hasAttribute('data-portal-chat');
    let policy={};try{policy=JSON.parse(root.querySelector('[data-audio-policy]')?.textContent||'{}');}catch(_){}
    const storageKey='azul_meter_'+(root.dataset.usageScope||'anonymous');
    const uuid=()=>crypto.randomUUID().replaceAll('-','');
    try{root.dataset.conversationId=sessionStorage.getItem(storageKey)||uuid();sessionStorage.setItem(storageKey,root.dataset.conversationId);}catch(_){root.dataset.conversationId=uuid();}
    function newConversation(){root.dataset.conversationId=uuid();try{sessionStorage.setItem(storageKey,root.dataset.conversationId);}catch(_){}}
    root.addEventListener('click',event=>{const button=event.target.closest('[data-clear]');if(button&&!button.disabled)newConversation();});
    function headers(){return{'X-CSRFToken':root.dataset.csrf||'','X-Azul-Conversation':root.dataset.conversationId,
      ...(publicChat?{'X-Portal-Chat-Token':root.dataset.token}:{'X-Azul-Chat-Key':root.dataset.chatKey})};}
    function apply(value){
      policy=value;root.dataset.soundEnabled=value.sound_enabled===false?'0':'1';
      root.dataset.microphoneEnabled=value.microphone_enabled===false?'0':'1';
      root.dataset.conversationEnabled=value.conversation_enabled===false?'0':'1';
      const input=root.querySelector('[data-compose-input]');if(input&&value.max_message_chars)input.maxLength=value.max_message_chars;
      const controls=root.querySelector('[data-voice-controls]');if(controls)controls.hidden=value.microphone_enabled===false;
      const mode=root.dataset.voiceMode;
      if((mode==='conversation'&&value.conversation_enabled===false)||(mode==='dictation'&&value.microphone_enabled===false))root.azulVoice?.stop(value.unavailable?'Não foi possível confirmar a disponibilidade do áudio. Continue pelo texto.':'A conversa por voz foi desativada nas configurações da AZUL.');
      if(value.sound_enabled===false)root.azulCompanion?.stopVoice();
    }
    async function refresh(){
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);
      try{const response=await fetch('/api/azul/politica'+(publicChat?'?audience=public':''),{credentials:'same-origin',cache:'no-store',signal:controller.signal});if(!response.ok)throw new Error();apply(await response.json());return true;}
      catch(_){apply({sound_enabled:false,microphone_enabled:false,conversation_enabled:false,unavailable:true});return false;}
      finally{clearTimeout(timer);}
    }
    root.azulAudioPolicy={
      get current(){return policy;},headers,
      get message(){return policy.unavailable?'Não foi possível confirmar a disponibilidade do áudio. Continue pelo texto.':'O som ou o microfone da AZUL está desativado nas configurações.';},
      async check(kind){if(!await refresh())return false;return kind==='sound'?policy.sound_enabled!==false:kind==='microphone'?policy.microphone_enabled!==false:policy.conversation_enabled!==false;},
      record(clip){fetch('/api/azul/audio-evento',{method:'POST',credentials:'same-origin',keepalive:true,
        headers:{...headers(),'Content-Type':'application/json'},body:JSON.stringify({clip,event_id:uuid()})}).catch(()=>{});},
      refresh
    };
    apply(policy);
    const interval=setInterval(()=>{if(!document.hidden&&root.querySelector('.azul-panel,.portal-chat-panel')?.hidden!==true)refresh();},10000);
    window.addEventListener('pagehide',()=>clearInterval(interval));
    window.addEventListener('azul:policy-refresh',refresh);
  }
})();
