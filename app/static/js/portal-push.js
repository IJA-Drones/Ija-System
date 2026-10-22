// Alertas no celular (Web Push) e instalação do app (PWA) no Portal do Cidadão.
(function () {
  'use strict';
  const button = document.getElementById('portal-push-button');
  if (!button) return;
  const status = document.getElementById('portal-push-status');
  const disableButton = document.getElementById('portal-push-disable');
  const installButton = document.getElementById('portal-install-button');
  const installHint = document.getElementById('portal-install-hint');
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const standalone = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const supported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const prefeituraId = () => document.getElementById('portalPrefeitura')?.value || '';
  const say = (text, kind) => { status.textContent = text; status.dataset.kind = kind || ''; };
  const setButton = (text, enabled) => { button.innerHTML = '<i class="bi bi-bell" aria-hidden="true"></i> ' + text; button.disabled = !enabled; };
  let installEvent = null;

  function base64ToUint8(base64) {
    const padding = '='.repeat((4 - base64.length % 4) % 4);
    const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(raw, c => c.charCodeAt(0));
  }
  function position() {
    return new Promise(resolve => {
      if (!navigator.geolocation) return resolve({});
      navigator.geolocation.getCurrentPosition(
        p => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude }),
        () => resolve({}), { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 });
    });
  }
  async function registration() {
    const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
    await navigator.serviceWorker.ready;
    return reg;
  }
  async function publicKey() {
    const data = await (await fetch('/api/push/chave-publica', { cache: 'no-store' })).json();
    return data.publicKey || null;
  }
  async function register(subscription) {
    const where = await position();
    const response = await fetch('/api/push/inscrever', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ canal: 'webpush', subscription: subscription.toJSON(), ...where, prefeitura_id: prefeituraId() || undefined }) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'Não foi possível inscrever este aparelho.');
    return where;
  }
  function showSubscribed(where) {
    setButton('Alertas ativados', false);
    disableButton.hidden = false;
    say(where && where.latitude ? 'Alertas ativados para a sua localização. Você será avisado quando houver aumento de focos ou casos perto de você.'
      : 'Alertas ativados para o município.', 'ok');
  }
  function showIdle(text) {
    setButton('Receber alertas no celular', true);
    disableButton.hidden = true;
    if (text) say(text);
  }
  async function enable() {
    if (!supported()) {
      if (isIos && !standalone()) { installHint.hidden = false; throw new Error('No iPhone, instale o app primeiro: Compartilhar → Adicionar à Tela de Início. Depois abra pelo ícone e toque aqui.'); }
      throw new Error('Este navegador não suporta notificações. Baixe o aplicativo Android ou use o Chrome.');
    }
    const key = await publicKey();
    if (!key) throw new Error('Alertas push ainda não configurados no servidor.');
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') throw new Error(permission === 'denied'
      ? 'Notificações bloqueadas neste navegador. Libere em Configurações do site → Notificações e tente de novo.'
      : 'Permissão de notificação não concedida.');
    const reg = await registration();
    const subscription = await reg.pushManager.getSubscription()
      || await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: base64ToUint8(key) });
    const where = await register(subscription);
    try { localStorage.setItem('ija-push', '1'); } catch (e) { /* privado */ }
    showSubscribed(where);
  }
  async function disable() {
    disableButton.disabled = true;
    try {
      const reg = await navigator.serviceWorker.getRegistration('/');
      const subscription = reg && await reg.pushManager.getSubscription();
      if (subscription) {
        await fetch('/api/push/remover', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf }, body: JSON.stringify({ token: subscription.endpoint }) }).catch(() => {});
        await subscription.unsubscribe();
      }
      try { localStorage.removeItem('ija-push'); } catch (e) { /* privado */ }
      showIdle('Alertas desativados neste aparelho.');
    } finally { disableButton.disabled = false; }
  }
  async function detect() {
    if (installButton) {
      window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); installEvent = e; if (!standalone()) installButton.hidden = false; });
      window.addEventListener('appinstalled', () => { installButton.hidden = true; installHint.hidden = true; say('Aplicativo instalado. Abra pelo ícone na tela inicial.', 'ok'); });
      installButton.addEventListener('click', async () => { if (!installEvent) return; installEvent.prompt(); await installEvent.userChoice.catch(() => {}); installEvent = null; installButton.hidden = true; });
    }
    if (isIos && !standalone()) installHint.hidden = false;
    if (!supported()) { setButton('Receber alertas no celular', true); return; }
    if (Notification.permission === 'denied') { say('Notificações bloqueadas neste navegador. Libere em Configurações do site para receber alertas.', 'error'); return; }
    try {
      const reg = await navigator.serviceWorker.getRegistration('/');
      const subscription = reg && await reg.pushManager.getSubscription();
      if (subscription && Notification.permission === 'granted') showSubscribed(null);
    } catch (e) { /* sem registro ainda */ }
  }
  button.addEventListener('click', async () => {
    button.disabled = true; say('Ativando…');
    try { await enable(); }
    catch (error) { say(error.message, 'error'); showIdle(); }
  });
  disableButton.addEventListener('click', disable);
  detect();
})();
