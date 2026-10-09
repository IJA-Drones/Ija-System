// Keep the chat inside the visible screen when mobile keyboards resize/pan it.
(() => {
  const root = document.querySelector('[data-portal-chat]');
  if (!root) return;
  const viewport = window.visualViewport;
  function syncViewport() {
    root.style.setProperty('--chat-viewport-height', `${viewport ? viewport.height : window.innerHeight}px`);
    root.style.setProperty('--chat-viewport-top', `${viewport ? viewport.offsetTop : 0}px`);
  }
  viewport?.addEventListener('resize', syncViewport);
  viewport?.addEventListener('scroll', syncViewport);
  window.addEventListener('resize', syncViewport);
  syncViewport();
})();
