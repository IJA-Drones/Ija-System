(() => {
  const notice = document.querySelector('[data-login-blocked]');
  if (!notice) return;
  const seconds = Number(notice.dataset.retryAfter);
  const wait = notice.querySelector('[data-login-wait]');
  if (!wait || !Number.isFinite(seconds) || seconds <= 0) return;

  const deadline = Date.now() + seconds * 1000;
  // Read the explanation on arrival, without announcing every timer tick.
  notice.focus({ preventScroll: true });
  notice.scrollIntoView({ block: 'nearest', behavior: 'instant' });
  const update = () => {
    const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
    if (remaining === 0) {
      wait.setAttribute('role', 'status');
      wait.setAttribute('aria-live', 'polite');
      wait.textContent = 'O tempo de espera informado terminou. Confira seus dados e tente entrar novamente.';
      clearInterval(timer);
      return;
    }
    const minutes = Math.floor(remaining / 60);
    const rest = String(remaining % 60).padStart(2, '0');
    wait.textContent = `Tente novamente em ${minutes} min ${rest} s.`;
  };
  const timer = setInterval(update, 1000);
  update();
})();
