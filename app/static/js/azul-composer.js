/* Keep the compact composer and its accessible controls in sync. */
(() => {
  document.querySelectorAll('[data-azul-compose]').forEach(form => {
    const root = form.closest('[data-azul-help],[data-azul-companion]');
    const input = form.querySelector('[data-compose-input]');
    const send = form.querySelector('[type="submit"]'), stop = form.querySelector('[data-stop]');
    const controls = form.querySelector('[data-voice-controls]'), mic = form.querySelector('[data-microphone]');
    const dictate = form.querySelector('[data-dictate]'), action = form.querySelector('[data-voice-action]');
    const status = form.querySelector('[data-status]'), voiceStatus = form.querySelector('[data-microphone-status]');
    function refresh() {
      const hasText = !!input.value.trim();
      if (!input.value) input.style.height = '';
      const pending = form.getAttribute('aria-busy') === 'true' || (send.disabled && !input.disabled);
      const active = root.dataset.voiceState && root.dataset.voiceState !== 'idle';
      const conversation = active && root.dataset.voiceMode !== 'dictation';
      const hasVoice = controls && !controls.hidden;
      send.hidden = conversation || pending || (!hasText && hasVoice);
      stop.hidden = pending && !conversation ? false : true;
      if (mic) mic.hidden = root.dataset.soundEnabled==='0' || root.dataset.conversationEnabled==='0' || (!conversation && (hasText || pending || active));
      if (dictate) dictate.hidden = root.dataset.microphoneEnabled==='0' || conversation || pending;
      if (action) action.hidden = !conversation;
      status?.classList.toggle('azul-sr-only', !status.textContent.trim() || status.textContent.trim() === (status.dataset.idleStatus || '').trim());
      voiceStatus?.classList.toggle('azul-sr-only', !active && root.dataset.voiceNotice !== '1');
    }
    input.addEventListener('input', () => {
      input.style.height = 'auto'; input.style.height = Math.min(180,Math.max(62,input.scrollHeight))+'px';
      refresh();
    });
    input.addEventListener('keydown',event => {
      if (!event.defaultPrevented && event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
        event.preventDefault(); if (input.value.trim() && !send.disabled) form.requestSubmit();
      }
    });
    root.addEventListener('click', () => requestAnimationFrame(refresh));
    new MutationObserver(refresh).observe(form,{subtree:true,attributes:true,attributeFilter:['disabled','aria-busy'],childList:true,characterData:true});
    new MutationObserver(refresh).observe(root,{attributes:true,attributeFilter:['data-voice-state','data-voice-mode','data-voice-notice','data-sound-enabled','data-microphone-enabled','data-conversation-enabled']});
    refresh();
  });
})();
