/* Public territorial boundaries; independent of surveillance indices and account permissions. */
(function (scope) {
  'use strict';
  const polygons = geometry => geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  const positions = feature => polygons(feature.geometry).flat(2);
  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');
  const selectedFeatures = (features, cnes, crs='') => features.filter(f => (!cnes || f.properties.cnes === cnes) && (!crs || f.properties.crs === crs));
  const territoryColor = feature => /^#[0-9a-f]{6}$/i.test(feature.properties.cor || '') ? feature.properties.cor : '#1a4a7c';
  const LABEL_ZOOM=12;
  const FILL_OPACITY=.4, HEAT_FILL_OPACITY=.18;
  const labelVisible=zoom=>Number.isFinite(zoom)&&zoom>=LABEL_ZOOM;
  function labelText(name){
    if(name==='SE')return 'Sé';
    return name.toLocaleLowerCase('pt-BR').split('/').map(part=>part.trim().split(/\s+/).map((word,i)=>
      i && ['de','do','da','dos','das'].includes(word) ? word : word.charAt(0).toLocaleUpperCase('pt-BR')+word.slice(1)).join(' ')).join(' / ');
  }
  let UvisLabel;
  function addLabel(map,feature){
    if(!UvisLabel)UvisLabel=class extends scope.google.maps.OverlayView {
      constructor(feature,map){super();this.feature=feature;this.owner=map;}
      onAdd(){
        this.node=document.createElement('div');this.node.className='uvis-map-label';
        this.node.textContent=labelText(this.feature.properties.uvis);
        this.getPanes().markerLayer.appendChild(this.node);
        this.zoomListener=this.owner.addListener('zoom_changed',()=>this.draw());
      }
      draw(){
        if(!this.node)return;
        this.node.hidden=!labelVisible(this.owner.getZoom());
        if(this.node.hidden)return;
        const anchor=this.feature.properties.rotulo;
        if(!anchor)return;
        const pixel=this.getProjection().fromLatLngToDivPixel(new scope.google.maps.LatLng(anchor[1],anchor[0]));
        if(pixel){this.node.style.left=pixel.x+'px';this.node.style.top=pixel.y+'px';}
      }
      onRemove(){this.zoomListener?.remove();this.node?.remove();this.node=null;}
    };
    const label=new UvisLabel(feature,map);label.setMap(map);return label;
  }
  const regionAliases = region => [region, 'CRS '+region, 'Região '+region, 'Coordenadoria '+region, 'Coordenadoria Regional de Saúde '+region];
  const regionFromSearch = (regions, term) => regions.find(r=>regionAliases(r).some(alias=>normalize(alias)===normalize(term))) || '';
  const searchFeatures = (features, term) => !normalize(term) ? features : features.filter(f=>normalize([f.properties.uvis,'UVIS '+f.properties.uvis,...regionAliases(f.properties.crs),...(f.properties.distritos||[])].join(' ')).includes(normalize(term)));
  const bounds = features => {
    const result = {west: Infinity, east: -Infinity, south: Infinity, north: -Infinity};
    for (const f of features) for (const p of positions(f)) {
      result.west = Math.min(result.west, p[0]); result.east = Math.max(result.east, p[0]);
      result.south = Math.min(result.south, p[1]); result.north = Math.max(result.north, p[1]);
    }
    return result;
  };
  const downloads = new Map();
  async function load(url) {
    if (!downloads.has(url)) {
      downloads.set(url, fetch(url, {credentials: 'same-origin'}).then(response => {
        if (!response.ok) throw new Error('Fonte territorial indisponível.');
        return response.json();
      }).then(data => {
        if (data.type !== 'FeatureCollection' || data.metadata?.ibge !== '3550308' || !Array.isArray(data.features)) throw new Error('Fonte territorial inválida.');
        return data.features;
      }).catch(error => { downloads.delete(url); throw error; }));
    }
    return downloads.get(url);
  }
  function create(root, {onChange = () => {}, onDetails = () => {}} = {}) {
    if (!root) return null;
    const visible = document.querySelector('[data-uvis-visible]');
    const districtsVisible = document.querySelector('[data-districts-visible]');
    const select = root.querySelector('[data-uvis-select]');
    const status = root.querySelector('[data-uvis-status]');
    const region = root.querySelector('[data-uvis-region]');
    const search = root.querySelector('[data-uvis-search]');
    const colors = document.querySelector('[data-uvis-colors]');
    const labels = document.querySelector('[data-uvis-labels]');
    const crs = () => region?.value || '';
    const filters = () => ({crs:crs(), cnes:select.value});
    function options() {
      const before=select.value;
      select.replaceChildren(new Option('Todas as UVIS',''));
      for (const feature of [...searchFeatures(uvis,search?.value)].sort((a,b)=>a.properties.uvis.localeCompare(b.properties.uvis,'pt-BR'))) {
        const p=feature.properties;
        if(crs() && crs()!==p.crs)continue;
        select.append(new Option(`UVIS ${p.uvis}`,p.cnes));
      }
      if([...select.options].some(o=>o.value===before))select.value=before;
    }
    let uvis = [], districts = [], sequence = 0, autoRegion=false;
    const maps = new Map();
    const heatMaps = new WeakSet();
    const active = () => visible.checked || districtsVisible.checked || colors?.checked || labels?.checked;
    function description(feature) {
      const p = feature.properties;
      return [`UVIS ${p.uvis} · CNES ${p.cnes}`, ...(p.distrito ? [`Distrito: ${p.distrito} · código ${p.codigo_distrito}`] : [`Distritos: ${p.distritos.join(', ')}`]),
        `CRS ${p.crs} · referência de 27/07/2026.`, 'Limite de atuação territorial. Não representa índice de infestação ou caso de doença.'];
    }
    function entries() {
      return [
        ...(visible.checked || colors?.checked ? selectedFeatures(uvis, select.value, crs()).map(feature => ({feature, district: false})) : []),
        ...(districtsVisible.checked ? selectedFeatures(districts, select.value, crs()).map(feature => ({feature, district: true})) : [])
      ];
    }
    function fit(map,all=false) {
      if (!all && !select.value && !crs()) return;
      const b = bounds(all?uvis:selectedFeatures(uvis, select.value, crs()));
      if (Number.isFinite(b.west)) map.fitBounds({west:b.west, east:b.east, south:b.south, north:b.north}, 30);
    }
    function refreshGoogle(map) {
      const old = maps.get(map) || []; old.forEach(shape => shape.setMap(null));
      const shapes = [];
      for (const {feature, district} of entries()) for (const polygon of polygons(feature.geometry)) {
        const shape = new scope.google.maps.Polygon({map, paths: polygon.map(r => r.map(p => ({lat:p[1],lng:p[0]}))),
          strokeColor:district ? '#64748b' : territoryColor(feature), strokeWeight:district ? 1 : 2.5,
          strokeOpacity:district || visible.checked ? 1 : 0,
          fillColor:territoryColor(feature), fillOpacity:!district && colors?.checked ? (heatMaps.has(map) ? HEAT_FILL_OPACITY : FILL_OPACITY) : 0, zIndex:0});
        shape.addListener('click', () => onDetails(feature.properties.distrito || `UVIS ${feature.properties.uvis}`, description(feature)));
        shapes.push(shape);
      }
      if(labels?.checked)for(const feature of selectedFeatures(uvis, select.value, crs()))shapes.push(addLabel(map,feature));
      maps.set(map, shapes);
    }
    async function change() {
      const id = ++sequence;
      try {
        if (active() && !uvis.length) {
          status.textContent = 'Carregando limites territoriais…';
          uvis = await load(root.dataset.uvisUrl);
          if(region && region.options.length===1){
            for(const value of [...new Set(uvis.map(f=>f.properties.crs))].sort())region.append(new Option(`CRS ${value}`,value));
          }
          options();
        }
        if (districtsVisible.checked && !districts.length) districts = await load(root.dataset.districtsUrl);
        if (id !== sequence) return;
        const chosen = uvis.find(f => f.properties.cnes === select.value);
        const selected=selectedFeatures(uvis,select.value,crs());
        status.textContent = active() ? chosen ? `UVIS ${chosen.properties.uvis} · ${chosen.properties.distritos.length} distritos · referência de 27/07/2026.` : crs() ? `CRS ${crs()} · ${selected.length} UVIS · selecione uma unidade para consultar seus detalhes.` : `${uvis.length} UVIS · 96 distritos de referência. Selecione uma UVIS para enquadrar seu território.` : 'Camadas territoriais ocultas.';
        for (const map of maps.keys()) refreshGoogle(map);
        document.dispatchEvent(new CustomEvent('uvis:selection-change',{detail:filters()}));
        onChange(filters());
        if (chosen) onDetails(`UVIS ${chosen.properties.uvis}`, description(chosen));
      } catch (_error) {
        if (id !== sequence) return;
        status.textContent = 'Não foi possível carregar os limites. Desative e ative a camada para tentar novamente. Os demais dados do mapa continuam disponíveis.';
      }
    }
    region?.addEventListener('change',()=>{autoRegion=false;if(search)search.value='';options();change();});
    search?.addEventListener('input',()=>{
      const before=JSON.stringify(filters());
      const found=regionFromSearch([...new Set(uvis.map(f=>f.properties.crs))],search.value);
      if(region && found){region.value=found;autoRegion=true;}
      else if(region && autoRegion){region.value='';autoRegion=false;}
      options();
      const exact=uvis.filter(f=>normalize(f.properties.uvis)===normalize(search.value)||normalize('UVIS '+f.properties.uvis)===normalize(search.value));
      if(exact.length===1 && (!crs()||exact[0].properties.crs===crs()))select.value=exact[0].properties.cnes;
      if(before!==JSON.stringify(filters()))change();
    });
    visible.addEventListener('change', change); districtsVisible.addEventListener('change', change);
    colors?.addEventListener('change',change); labels?.addEventListener('change',change);
    select.addEventListener('change', () => { if (select.value && !active()) visible.checked = true; change(); });
    if (active()) change();
    return {
      allPoints() { return uvis.flatMap(positions); },
      selectedCode() { return `${crs()}|${select.value}`; },
      getFilters: filters,
      drawSVG(svg, pathFor, pointFor) {
        const ns = 'http://www.w3.org/2000/svg';
        for (const {feature, district} of entries()) {
          const path = document.createElementNS(ns,'path'); const label = feature.properties.distrito || `UVIS ${feature.properties.uvis}`;
          path.setAttribute('d', pathFor(feature.geometry)); path.setAttribute('fill-rule','evenodd');
          path.setAttribute('fill',!district && colors?.checked ? territoryColor(feature) : 'none');
          path.setAttribute('fill-opacity',String(FILL_OPACITY));path.setAttribute('stroke',district ? '#64748b' : visible.checked ? territoryColor(feature) : 'none');
          path.setAttribute('stroke-width',district ? '1' : '2'); path.setAttribute('vector-effect','non-scaling-stroke');
          path.setAttribute('pointer-events','all'); path.setAttribute('tabindex','0'); path.setAttribute('role','button'); path.setAttribute('aria-label',label);
          const title = document.createElementNS(ns,'title'); title.textContent=label; path.append(title);
          const show=()=>onDetails(label,description(feature)); path.addEventListener('click',show);
          path.addEventListener('keydown', e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show();}}); svg.append(path);
        }
        if(labels?.checked && pointFor && select.value)for(const feature of selectedFeatures(uvis,select.value,crs())){
          const point=pointFor(feature.properties.rotulo),text=document.createElementNS(ns,'text');
          text.setAttribute('x',point[0]);text.setAttribute('y',point[1]);text.setAttribute('class','uvis-svg-label');
          text.textContent=labelText(feature.properties.uvis);svg.append(text);
        }
      },
      resetFrame() { select.value = ''; if(region)region.value=''; if(search)search.value=''; autoRegion=false;options();change(); },
      framePoints() {return (select.value || crs()) && active() ? selectedFeatures(uvis, select.value, crs()).flatMap(positions) : null;},
      attachGoogle(map,{heat=false}={}) { if (!map || maps.has(map)) return; if(heat)heatMaps.add(map);maps.set(map,[]); refreshGoogle(map); },
      fitGoogle: fit,
      fitAllGoogle(map) { fit(map,true); }
    };
  }
  const api = {create, polygons, positions, selectedFeatures, bounds, normalize, searchFeatures, regionFromSearch, territoryColor, labelVisible, labelText, LABEL_ZOOM};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (scope) scope.UvisTerritory = api;
})(typeof window === 'undefined' ? null : window);
