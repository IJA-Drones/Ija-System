/* Floating Azul launchers: pointer/touch dragging, bounded position and safe clicks. */
(() => {
  const storageKey = 'azul-launcher-position-v1';
  const roots = new Set([...document.querySelectorAll('[data-azul-help]'), ...document.querySelectorAll('[data-azul-companion]')]);
  for (const root of roots) {
    const handle = root.querySelector('[data-toggle]') || root.querySelector('.portal-chat-toggle');
    const panel = root.querySelector('.azul-panel') || root.querySelector('.portal-chat-panel');
    if (!handle || !panel || root.dataset.dragReady) continue;
    root.dataset.dragReady = '1';
    handle.classList.add('azul-drag-handle');
    handle.setAttribute('aria-description', 'Arraste para mover. Com o botão em foco, use Shift e as setas para reposicionar.');
    let pointer = null, suppressClick = false, position = null;
    function bounds() {
      const rect = handle.getBoundingClientRect();
      return {width: rect.width, height: rect.height,
        maxX: Math.max(8, window.innerWidth - rect.width - 8),
        maxY: Math.max(8, window.innerHeight - rect.height - 8)};
    }
    function placePanel() {
      if (panel.hidden) return;
      if (window.innerWidth <= 600) {
        for (const name of ['left', 'right', 'top', 'bottom', 'position']) panel.style.removeProperty(name);
        return;
      }
      const anchor = handle.getBoundingClientRect(), rect = panel.getBoundingClientRect();
      const width = rect.width, height = rect.height, margin = 12;
      const x = Math.max(margin, Math.min(window.innerWidth - width - margin,
        anchor.left > window.innerWidth / 2 ? anchor.right - width : anchor.left));
      let y = anchor.top - height - margin;
      if (y < margin) y = anchor.bottom + margin;
      y = Math.max(margin, Math.min(window.innerHeight - height - margin, y));
      Object.assign(panel.style, {position:'fixed', left:x+'px', right:'auto', top:y+'px', bottom:'auto'});
    }
    function move(x, y, persist = false) {
      const box = bounds();
      position = {x: Math.max(8, Math.min(box.maxX, x)), y: Math.max(8, Math.min(box.maxY, y))};
      Object.assign(handle.style, {position:'fixed', left:position.x+'px', top:position.y+'px', right:'auto', bottom:'auto'});
      placePanel();
      if (persist) {
        try { localStorage.setItem(storageKey, JSON.stringify({x:position.x / box.maxX, y:position.y / box.maxY})); } catch (_) { /* Optional presentation preference. */ }
      }
    }
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey));
      if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y) && saved.x >= 0 && saved.x <= 1 && saved.y >= 0 && saved.y <= 1) {
        const box = bounds(); move(saved.x * box.maxX, saved.y * box.maxY);
      }
    } catch (_) { /* Storage may be blocked or contain an old value. */ }
    handle.addEventListener('pointerdown', event => {
      if (pointer || (event.button !== undefined && event.button !== 0)) return;
      suppressClick = false;
      const rect = handle.getBoundingClientRect();
      pointer = {id:event.pointerId, startX:event.clientX, startY:event.clientY, x:rect.left, y:rect.top, moved:false};
      handle.setPointerCapture?.(event.pointerId);
    });
    handle.addEventListener('pointermove', event => {
      if (!pointer || pointer.id !== event.pointerId) return;
      const dx = event.clientX - pointer.startX, dy = event.clientY - pointer.startY;
      if (!pointer.moved && Math.hypot(dx, dy) < 7) return;
      pointer.moved = true; root.dataset.dragging = '1';
      move(pointer.x + dx, pointer.y + dy);
      if (event.cancelable) event.preventDefault();
    });
    function finish(event) {
      if (!pointer || pointer.id !== event.pointerId) return;
      if (pointer.moved) {
        suppressClick = true;
        move(position.x, position.y, true);
      }
      pointer = null; delete root.dataset.dragging;
    }
    handle.addEventListener('pointerup', finish);
    handle.addEventListener('pointercancel', finish);
    handle.addEventListener('lostpointercapture', finish);
    handle.addEventListener('click', event => {
      if (!suppressClick || event.detail === 0) { suppressClick = false; return; }
      event.preventDefault(); event.stopImmediatePropagation(); suppressClick = false;
    }, true);
    handle.addEventListener('keydown', event => {
      if (!event.shiftKey || !['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)) return;
      event.preventDefault();
      const rect = handle.getBoundingClientRect();
      move(rect.left + (event.key === 'ArrowLeft' ? -16 : event.key === 'ArrowRight' ? 16 : 0),
        rect.top + (event.key === 'ArrowUp' ? -16 : event.key === 'ArrowDown' ? 16 : 0), true);
    });
    window.addEventListener('resize', () => { if (position) move(position.x, position.y); else placePanel(); });
    new MutationObserver(placePanel).observe(panel, {attributes:true, attributeFilter:['hidden']});
    root.addEventListener('azul:open', () => requestAnimationFrame(placePanel));
  }
})();
