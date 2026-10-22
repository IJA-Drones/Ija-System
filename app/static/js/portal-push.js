// Inscrição para alertas no celular: app (Capacitor/FCM) ou navegador (Web Push).
(function () {
  'use strict';
  const button = document.getElementById('portal-push-button');
  const status = document.getElementById('portal-push-status');
  if (!button) return;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const say = (text, kind) => { status.textContent = text; status.dataset.kind = kind || ''; };
  const native = () => window.Capacitor && typeof window.Capacitor.isNativePlatform === 'function' && window.Capacitor.isNativePlatform();
  const prefeituraId = () => document.getElementById('portalPrefeitura')?.value || '';

  function position() {
    return new Promise(resolve => {
      if (!navigator.geolocation) return resolve({});
      navigator.geolocation.getCurrentPosition(
        p => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude }),
        () => resolve({}), { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 });
    });
  }
  async function register(body) {
    const where = await position();
    const response = await fetch('/api/push/inscrever', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ ...body, ...where, prefeitura_id: prefeituraId() || undefined }) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'Não foi possível inscrever este aparelho.');
    try { localStorage.setItem('ija-push', '1'); } catch (e) { /* privado */ }
    say(where.latitude ? 'Alertas ativados para a sua localização.' : 'Alertas ativados para o município.', 'ok');
    button.textContent = 'Alertas ativados';
    button.disabled = true;
  }
  function base64ToUint8(base64) {
    const padding = '='.repeat((4 - base64.length % 4) % 4);
    const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(raw, c => c.charCodeAt(0));
  }
  async function viaNative() {
    const push = window.Capacitor.Plugins.PushNotifications;
    const perm = await push.requestPermissions();
    if (perm.receive !== 'granted') throw new Error('Permissão de notificação negada no aparelho.');
    const token = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('O aparelho não devolveu o token de notificação. Verifique a configuração do Firebase no app.')), 15000);
      push.addListener('registration', t => { clearTimeout(timer); resolve(t.value); });
      push.addListener('registrationError', e => {
        clearTimeout(timer);
        const detail = String(e.error || JSON.stringify(e));
        reject(new Error(/firebase|api key|FirebaseApp/i.test(detail)
          ? 'As notificações dentro do aplicativo ainda não foram ativadas no servidor (Firebase). Abra o portal pelo navegador do celular para receber alertas por lá.'
          : 'Falha ao registrar: ' + detail));
      });
      push.register();
    });
    await register({ canal: 'fcm', token });
  }
  async function viaWeb() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      const ios = /iphone|ipad/i.test(navigator.userAgent);
      throw new Error(ios ? 'No iPhone, adicione o portal à Tela de Início (Compartilhar → Adicionar à Tela de Início) e abra por lá para ativar os alertas.' : 'Este navegador não suporta notificações.');
    }
    const keys = await (await fetch('/api/push/chave-publica')).json();
    if (!keys.publicKey) throw new Error('Alertas push ainda não configurados no servidor.');
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') throw new Error('Permissão de notificação negada.');
    const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
    await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription()
      || await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: base64ToUint8(keys.publicKey) });
    await register({ canal: 'webpush', subscription: subscription.toJSON() });
  }
  button.addEventListener('click', async () => {
    button.disabled = true; say('Ativando…');
    try { await (native() ? viaNative() : viaWeb()); }
    catch (error) { say(error.message, 'error'); button.disabled = false; }
  });
  try { if (localStorage.getItem('ija-push') === '1') { button.textContent = 'Alertas ativados'; say('Este aparelho já recebe alertas. Toque para atualizar a localização.'); } } catch (e) { /* privado */ }
})();
