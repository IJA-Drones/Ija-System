// Envia a posição do agente de endemias a cada 30 s ou 25 m enquanto o app/página está aberto.
(function () {
  'use strict';
  if (!navigator.geolocation) return;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const origem = window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform() ? 'app' : 'web';
  let last = null, lastAt = 0;
  function distance(a, b) {
    const r = Math.PI / 180, dLat = (b.latitude - a.latitude) * r, dLng = (b.longitude - a.longitude) * r;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.latitude * r) * Math.cos(b.latitude * r) * Math.sin(dLng / 2) ** 2;
    return 2 * 6371000 * Math.asin(Math.sqrt(h));
  }
  function send(coords) {
    const now = Date.now();
    if (last && now - lastAt < 30000 && distance(last, coords) < 25) return;
    last = coords; lastAt = now;
    fetch('/api/agente/posicao', { method: 'POST', keepalive: true, headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ latitude: coords.latitude, longitude: coords.longitude, precisao: coords.accuracy, origem }) }).catch(() => {});
  }
  navigator.geolocation.watchPosition(p => send(p.coords), () => {}, { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 });
})();
