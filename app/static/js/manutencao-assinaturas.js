(() => {
  const setupPad = (key) => {
    const canvas = document.getElementById(`${key}-pad`);
    const input = document.getElementById(`${key}-data`);
    const clearFlag = document.getElementById(`${key}-clear`);
    if (!canvas || !input) return;
    const ctx = canvas.getContext('2d');
    let drawing = false;
    const restore = () => {
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.round(rect.width * ratio));
      canvas.height = Math.max(1, Math.round(rect.height * ratio));
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.lineWidth = 2.5; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = '#111827';
      if (input.value && input.value.startsWith('data:image/png;base64,')) {
        const image = new Image(); image.onload = () => ctx.drawImage(image, 0, 0, rect.width, rect.height); image.src = input.value;
      }
    };
    const point = (event) => { const rect = canvas.getBoundingClientRect(); return {x:event.clientX-rect.left,y:event.clientY-rect.top}; };
    canvas.addEventListener('pointerdown', (event) => { drawing = true; if (clearFlag) clearFlag.value='0'; canvas.setPointerCapture(event.pointerId); const p=point(event); ctx.beginPath(); ctx.moveTo(p.x,p.y); });
    canvas.addEventListener('pointermove', (event) => { if (!drawing) return; const p=point(event); ctx.lineTo(p.x,p.y); ctx.stroke(); });
    const stop = () => { if (!drawing) return; drawing = false; input.value = canvas.toDataURL('image/png'); };
    canvas.addEventListener('pointerup', (event) => { stop(); input.dispatchEvent(new Event('input', { bubbles: true })); }); canvas.addEventListener('pointercancel', stop);
    document.querySelector(`[data-clear-signature="${key}"]`)?.addEventListener('click', () => { ctx.clearRect(0,0,canvas.width,canvas.height); input.value=''; if (clearFlag) clearFlag.value='1'; input.dispatchEvent(new Event('input', { bubbles: true })); });
    window.addEventListener('resize', restore);
    canvas.closest('details')?.addEventListener('toggle', restore);
    restore();
  };
  setupPad('assinatura-tecnico'); setupPad('assinatura-avaria');
})();
