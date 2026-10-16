(() => {
  'use strict';
  // Memory only: two recent rasters, 16 MiB of compressed blocks per source,
  // and a bounded WebGL tile cache. URLs still go through authenticated routes.
  window.createOrthoRasterCache = ({map, onStatus, maxEntries = 2}) => {
    const entries = new Map();
    const keyFor = item => `${item.prefeitura_id}:${item.id}:${item.arquivo_url}`;
    function remove(key, entry) {
      entries.delete(key);
      map.removeLayer(entry.layer);
      entry.layer.dispose();
      entry.source.dispose();
    }
    function acquire(item) {
      const key = keyFor(item);
      let entry = entries.get(key);
      if (entry?.failed) {remove(key, entry);entry = null;}
      if (entry) {entries.delete(key);entries.set(key, entry);return entry;}
      // A new processing result has a different versioned URL.
      for (const [oldKey, old] of entries) {
        if (old.id === item.id) remove(oldKey, old);
      }
      while (entries.size >= maxEntries) {
        const [oldKey, old] = entries.entries().next().value;
        remove(oldKey, old);
      }
      const source = new ol.source.GeoTIFF({
        sources: [{url: item.arquivo_url}], convertToRGB: false, interpolate: true,
        sourceOptions: {blockSize: 256 * 1024, cacheSize: 64, allowFullFile: false},
      });
      const layer = new ol.layer.WebGLTile({source, visible: false, cacheSize: 128});
      entry = {id: item.id, source, layer, pending: 0, status: 'loading', failed: false};
      entries.set(key, entry);map.addLayer(layer);
      function notify(status) {
        if (entries.get(key) !== entry) return;
        entry.status = status;
        onStatus(entry);
      }
      source.on('tileloadstart', () => {entry.pending++;if (!entry.failed) notify('loading');});
      source.on('tileloadend', () => {
        entry.pending = Math.max(0, entry.pending - 1);
        if (!entry.pending && !entry.failed) notify('ready');
      });
      const fail = () => {entry.failed = true;layer.set('loadError', true);notify('error');};
      source.on('tileloaderror', fail);
      source.on('change', () => {if (source.getState() === 'error') fail();});
      source.getView().catch(fail);
      return entry;
    }
    return {
      acquire,
      release(layer) {
        for (const entry of entries.values()) {
          if (entry.layer === layer) {layer.setVisible(false);return true;}
        }
        return false;
      },
      retain(items) {
        const allowed = new Set(items.filter(i => i.status === 'pronto' && i.tipo !== 'dem').map(keyFor));
        for (const [key, entry] of entries) if (!allowed.has(key)) remove(key, entry);
      },
      dispose() {for (const [key, entry] of entries) remove(key, entry);},
    };
  };
})();
