/* A rounded lens refracts the backdrop; foreground text never enters the filter. */
(() => {
  'use strict';
  const pane = document.querySelector('.dev-hero');
  if (!pane) return;

  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const reducedTransparency = matchMedia('(prefers-reduced-transparency: reduce)');
  const finePointer = matchMedia('(hover: hover) and (pointer: fine)');
  let frame = 0;
  let pointerX = 22;
  let pointerY = 0;

  function paintLight() {
    frame = 0;
    pane.style.setProperty('--dev-light-x', `${pointerX}%`);
    pane.style.setProperty('--dev-light-y', `${pointerY}%`);
    pane.style.setProperty('--dev-light-angle', `${115 + (pointerX - 50) * .4}deg`);
  }

  pane.addEventListener('pointermove', event => {
    if (!finePointer.matches || reducedMotion.matches || reducedTransparency.matches) return;
    const rect = pane.getBoundingClientRect();
    pointerX = Math.max(0, Math.min(100, (event.clientX - rect.left) / rect.width * 100));
    pointerY = Math.max(0, Math.min(100, (event.clientY - rect.top) / rect.height * 100));
    if (!frame) frame = requestAnimationFrame(paintLight);
  }, { passive: true });

  function resetLight() {
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    pane.style.removeProperty('--dev-light-x');
    pane.style.removeProperty('--dev-light-y');
    pane.style.removeProperty('--dev-light-angle');
  }
  pane.addEventListener('pointerleave', resetLight);
  reducedMotion.addEventListener('change', resetLight);
  reducedTransparency.addEventListener('change', resetLight);

  // Reference SVG backdrop filters are not interoperable in WebKit/Firefox.
  // Keep the CSS blur and reflections there; opt in only on Chromium engines.
  const chromium = navigator.userAgentData?.brands?.some(brand => /Chromium/.test(brand.brand))
    || Boolean(window.chrome);
  if (!chromium || !window.ResizeObserver || !CSS.supports('backdrop-filter', 'url("#devGlassLens")')) return;

  const ns = 'http://www.w3.org/2000/svg';
  function node(name, attrs) {
    const element = document.createElementNS(ns, name);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  }
  const svg = node('svg', { width: 0, height: 0, 'aria-hidden': 'true', focusable: 'false' });
  svg.classList.add('dev-glass-filters');
  const defs = node('defs', {});
  const filter = node('filter', {
    id: 'devGlassLens', x: 0, y: 0,
    filterUnits: 'userSpaceOnUse', 'color-interpolation-filters': 'sRGB'
  });
  const map = node('feImage', { x: 0, y: 0, width: '100%', height: '100%', preserveAspectRatio: 'none', result: 'lensMap' });
  filter.append(map, node('feDisplacementMap', {
    in: 'SourceGraphic', in2: 'lensMap', scale: 14,
    xChannelSelector: 'R', yChannelSelector: 'G', result: 'refracted'
  }), node('feGaussianBlur', { in: 'refracted', stdDeviation: .8 }));
  defs.append(filter);
  svg.append(defs);
  pane.parentElement.append(svg);

  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  let lastSize = '';
  let resizeFrame = 0;

  function updateLens() {
    resizeFrame = 0;
    const backdrop = pane.querySelector('.dev-glass-backdrop');
    const width = backdrop.clientWidth;
    const height = backdrop.clientHeight;
    const radius = Math.min(parseFloat(getComputedStyle(pane).borderTopLeftRadius), width / 2, height / 2);
    const size = `${width}:${height}:${radius}`;
    if (!width || !height || size === lastSize) return;
    lastSize = size;
    filter.setAttribute('width', width);
    filter.setAttribute('height', height);
    map.setAttribute('width', width);
    map.setAttribute('height', height);
    // The map is capped in size and rebuilt only when the pane resizes.
    const scale = Math.min(1, 640 / width, 420 / height);
    canvas.width = Math.max(2, Math.round(width * scale));
    canvas.height = Math.max(2, Math.round(height * scale));
    const pixels = ctx.createImageData(canvas.width, canvas.height);
    const rim = Math.min(24, radius * .7);
    for (let row = 0; row < canvas.height; row++) {
      for (let col = 0; col < canvas.width; col++) {
        const x = (col + .5) / canvas.width * width - width / 2;
        const y = (row + .5) / canvas.height * height - height / 2;
        const qx = Math.abs(x) - (width / 2 - radius);
        const qy = Math.abs(y) - (height / 2 - radius);
        const ox = Math.max(qx, 0);
        const oy = Math.max(qy, 0);
        const outer = Math.hypot(ox, oy);
        const distance = outer + Math.min(Math.max(qx, qy), 0) - radius;
        let nx = 0;
        let ny = 0;
        if (qx > 0 && qy > 0) {
          nx = ox / outer * Math.sign(x);
          ny = oy / outer * Math.sign(y);
        } else if (qx > qy) {
          nx = Math.sign(x);
        } else {
          ny = Math.sign(y);
        }
        const depth = Math.max(0, -distance);
        const bend = distance <= 0 && depth < rim ? Math.sin((1 - depth / rim) * Math.PI / 2) ** 1.5 : 0;
        const offset = (row * canvas.width + col) * 4;
        pixels.data[offset] = Math.round(127.5 - nx * bend * 117);
        pixels.data[offset + 1] = Math.round(127.5 - ny * bend * 117);
        pixels.data[offset + 2] = 128;
        pixels.data[offset + 3] = 255;
      }
    }
    ctx.putImageData(pixels, 0, 0);
    map.setAttribute('href', canvas.toDataURL('image/png'));
    pane.classList.add('has-glass-refraction');
  }
  new ResizeObserver(() => {
    if (!resizeFrame) resizeFrame = requestAnimationFrame(updateLens);
  }).observe(pane);
  updateLens();
})();
