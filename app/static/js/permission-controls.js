/* The server enforces every action; this only keeps controls consistent. */
(() => {
  function updateControls(root = document) {
    root.querySelectorAll('form[data-ti-allowed="false"]').forEach((form) => {
      form.querySelectorAll('input,select,textarea,button[type="submit"],button:not([type])').forEach((control) => {
        if (control.closest('[data-ti-independent="true"]') || control.dataset.bsToggle === 'tab') return;
        control.disabled = true;
      });
      if (!form.dataset.tiReadonlyBound) {
        form.addEventListener('submit', (event) => event.preventDefault());
        form.dataset.tiReadonlyBound = 'true';
      }
    });
  }
  updateControls();
  let pending = false;
  new MutationObserver(() => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; updateControls(); });
  }).observe(document.body, { childList: true, subtree: true });
})();
