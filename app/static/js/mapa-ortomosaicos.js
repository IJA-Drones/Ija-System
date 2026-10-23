/* Orthomosaic overlays on a Google map, read from the same private COG route used by the orthomosaic viewer. */
'use strict';
window.initMapaOrtomosaicos = (map, listUrl) => {
  const HALF = Math.PI * 6378137;  // Web Mercator half extent; the stored COG is EPSG:3857.
  const panel = document.createElement('div');
  panel.className = 'mapa-orto glass-panel';
  panel.innerHTML = '<button type="button" class="mapa-orto-toggle" aria-expanded="false"><i class="bi bi-layers" aria-hidden="true"></i> Ortomosaicos</button>' +
    '<div class="mapa-orto-body" hidden><label class="mapa-orto-opacity">Opacidade <output>80%</output><input type="range" min="0" max="100" value="80"></label>' +
    '<div class="mapa-orto-list" role="group" aria-label="Ortomosaicos disponíveis"><small>Carregando…</small></div></div>';
  map.controls[google.maps.ControlPosition.RIGHT_TOP].push(panel);
  const body = panel.querySelector('.mapa-orto-body'), list = panel.querySelector('.mapa-orto-list');
  const toggle = panel.querySelector('.mapa-orto-toggle'), range = panel.querySelector('input'), output = panel.querySelector('output');
  const active = new Map();
  let opacity = .8;
  toggle.onclick = () => {body.hidden = !body.hidden;toggle.setAttribute('aria-expanded', String(!body.hidden));};
  range.oninput = () => {
    opacity = range.value / 100;output.textContent = `${range.value}%`;
    active.forEach(type => type.tiles.forEach(tile => {tile.style.opacity = opacity;}));
  };

  function overlay(item, onError) {
    const source = GeoTIFF.fromUrl(item.arquivo_url, {allowFullFile: false, blockSize: 256 * 1024, cacheSize: 64});
    const ready = source.then(async tiff => [tiff, (await tiff.getImage()).getBoundingBox()]);
    ready.catch(onError);
    async function draw(canvas, coord, zoom) {
      const [tiff, box] = await ready;
      const n = 2 ** zoom, size = 2 * HALF / n, x = ((coord.x % n) + n) % n;
      const west = -HALF + x * size, north = HALF - coord.y * size;
      const px = v => (v - west) / size * 256, py = v => (north - v) / size * 256;
      const left = Math.max(0, Math.floor(px(box[0]))), right = Math.min(256, Math.ceil(px(box[2])));
      const top = Math.max(0, Math.floor(py(box[3]))), bottom = Math.min(256, Math.ceil(py(box[1])));
      const width = right - left, height = bottom - top;
      if (width < 1 || height < 1 || canvas.released) return;
      const bbox = [west + left / 256 * size, north - bottom / 256 * size, west + right / 256 * size, north - top / 256 * size];
      const data = await tiff.readRasters({bbox, width, height, interleave: true, fillValue: 0, resampleMethod: 'bilinear'});
      if (canvas.released) return;
      const bands = data.length / (width * height), rgba = new Uint8ClampedArray(width * height * 4);
      for (let i = 0, j = 0; i < rgba.length; i += 4, j += bands) {
        rgba[i] = data[j];rgba[i + 1] = data[j + 1];rgba[i + 2] = data[j + 2];rgba[i + 3] = bands > 3 ? data[j + 3] : 255;
      }
      canvas.getContext('2d').putImageData(new ImageData(rgba, width, height), left, top);
    }
    return {
      tileSize: new google.maps.Size(256, 256), maxZoom: 24, name: item.nome, tiles: new Set(),
      getTile(coord, zoom, doc) {
        const canvas = doc.createElement('canvas');canvas.width = canvas.height = 256;canvas.style.opacity = opacity;
        this.tiles.add(canvas);draw(canvas, coord, zoom).catch(() => {});
        return canvas;
      },
      releaseTile(tile) {tile.released = true;this.tiles.delete(tile);},
    };
  }

  function setActive(item, checked, status) {
    if (!checked) {
      const index = map.overlayMapTypes.getArray().indexOf(active.get(item.id));
      if (index >= 0) map.overlayMapTypes.removeAt(index);
      active.delete(item.id);status.textContent = '';return;
    }
    const type = overlay(item, () => {status.textContent = 'Não foi possível carregar.';});
    active.set(item.id, type);map.overlayMapTypes.push(type);
    const [w, s, e, n] = item.metadados.limites;
    map.fitBounds(new google.maps.LatLngBounds({lat: s, lng: w}, {lat: n, lng: e}));
  }

  fetch(listUrl, {headers: {Accept: 'application/json'}, credentials: 'same-origin'})
    .then(response => response.ok ? response.json() : Promise.reject(new Error()))
    .then(data => {
      const items = data.items.filter(i => i.tipo !== 'dem' && i.status === 'pronto' && i.arquivo_url && i.metadados?.limites);
      list.replaceChildren();
      if (!items.length) {list.innerHTML = '<small>Nenhum ortomosaico disponível.</small>';return;}
      items.forEach(item => {
        const label = document.createElement('label'), input = document.createElement('input'), text = document.createElement('span');
        const status = document.createElement('small');status.className = 'mapa-orto-erro';
        input.type = 'checkbox';text.textContent = `${item.nome} · ${item.prefeitura}`;
        input.onchange = () => setActive(item, input.checked, status);
        label.append(input, text, status);list.append(label);
      });
    })
    .catch(() => {list.innerHTML = '<small>Não foi possível listar os ortomosaicos.</small>';});
};
