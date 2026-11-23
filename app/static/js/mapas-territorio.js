(() => {
  'use strict';
  const root=document.querySelector('[data-map-territory]');
  if(!root || !window.UvisTerritory)return;
  const quadraSelect=document.querySelector('[data-map-quadra-select]'), quadraStatus=document.querySelector('[data-map-quadra-status]');
  const enabled=document.querySelector('[data-map-quadras]');
  const displayPanel=document.querySelector('[data-map-display-panel]');
  const accountFilter=document.getElementById('uvisFilter');
  let maps=[], polygons=[], features=[], sequence=0, pending, scopeKey='|', lastQuadra='';
  let lastAccount='',linkedCode='',accountPending=Promise.resolve();
  const areaActive=()=>Boolean(document.getElementById('tabArea')?.classList.contains('active'));
  const mapShown=()=>areaActive()?maps[1]:maps[0];
  const info=(title,lines)=>{
    const status=root.querySelector('[data-uvis-status]');status.textContent=[title,...lines].join(' · ');
  };
  function clearShapes(){polygons.forEach(p=>p.setMap(null));polygons=[];}
  function invalidateQuadras(){
    sequence++;pending?.abort();features=[];clearShapes();
    quadraSelect.replaceChildren(new Option('Todas as quadras',''));lastQuadra='';
    quadraStatus.textContent='Recorte alterado. Aproxime o mapa e carregue as quadras da região.';
  }
  const overlay=window.UvisTerritory.create(root.querySelector('[data-uvis-controls]'),{
    onDetails:info,
    onChange(filters){
      const key=filters.crs+'|'+filters.cnes;
      if(key!==scopeKey){
        scopeKey=key;invalidateQuadras();
        for(const map of maps)overlay.fitGoogle(map);
      }
    }
  });
  function render(){
    clearShapes();if(!enabled.checked || !maps[1])return;
    for(const f of features)for(const polygon of window.UvisTerritory.polygons(f.geometry)){
      const selected=f.id===quadraSelect.value;
      const p=new google.maps.Polygon({map:maps[1],paths:polygon.map(r=>r.map(p=>({lat:p[1],lng:p[0]}))),strokeColor:'#b45309',strokeWeight:selected?4:1.5,fillColor:'#f59e0b',fillOpacity:selected ? .18 : .02,zIndex:1});
      p.addListener('click',()=>{quadraSelect.value=f.id;selectQuadra();});polygons.push(p);
    }
  }
  function selectQuadra(){
    lastQuadra=quadraSelect.value;render();
    const feature=features.find(f=>f.id===quadraSelect.value);
    if(feature){
      const b=window.UvisTerritory.bounds([feature]);
      maps[1]?.fitBounds({west:b.west,east:b.east,south:b.south,north:b.north},40);
      const p=feature.properties;quadraStatus.textContent=`Setor ${p.setor} · quadra ${p.quadra} · subquadra ${p.subquadra} · ${p.tipo}. Clique em Filtrar para consultar os registros nesta quadra.`;
    }
  }
  async function loadQuadras(){
    if(!areaActive())return;
    const map=maps[1];
    if(!map?.getBounds() || map.getZoom()<15){quadraStatus.textContent='Aproxime o mapa até ver as ruas (zoom 15 ou maior) e carregue as quadras.';return;}
    const b=map.getBounds(),ne=b.getNorthEast(),sw=b.getSouthWest();
    const bbox=[sw.lng(),sw.lat(),ne.lng(),ne.lat()].map(x=>x.toFixed(6)).join(',');
    const own=++sequence;pending?.abort();pending=new AbortController();
    quadraStatus.textContent='Consultando quadras no GeoSampa…';
    try{
      const response=await fetch(root.dataset.quadrasUrl+'?'+new URLSearchParams({bbox}),{signal:pending.signal});
      const data=await response.json();if(own!==sequence)return;
      if(!response.ok)throw new Error(data.message||'Não foi possível consultar quadras.');
      if(data.type!=='FeatureCollection'||!Array.isArray(data.features))throw new Error('Resposta inválida do GeoSampa.');
      const selected=features.find(f=>f.id===lastQuadra);
      features=[...data.features];
      if(selected&&!features.some(f=>f.id===selected.id))features.push(selected);
      quadraSelect.replaceChildren(new Option('Todas as quadras',''));
      for(const f of [...features].sort((a,b)=>(a.properties.setor+a.properties.quadra).localeCompare(b.properties.setor+b.properties.quadra)))quadraSelect.append(new Option(`Setor ${f.properties.setor} · quadra ${f.properties.quadra} / ${f.properties.subquadra}`,f.id));
      if(lastQuadra)quadraSelect.value=lastQuadra;
      enabled.checked=true;render();
      quadraStatus.textContent=`${data.features.length} contornos fiscais consultados na área visível. Selecione uma quadra para recortar os registros.`;
    }catch(error){if(own===sequence&&error.name!=='AbortError')quadraStatus.textContent=error.message;}
  }
  document.querySelector('[data-map-load-quadras]').addEventListener('click',loadQuadras);
  document.querySelector('[data-map-fit-sp]')?.addEventListener('click',()=>{if(mapShown())overlay.fitAllGoogle(mapShown());});
  enabled.addEventListener('change',()=>{render();if(enabled.checked&&!features.length)loadQuadras();});
  quadraSelect.addEventListener('change',selectQuadra);
  function attach(values){maps=values;if(maps[0])overlay.attachGoogle(maps[0],{heat:true});if(maps[1])overlay.attachGoogle(maps[1]);render();}
  async function syncAccountFilter(){
    if(!accountFilter||accountFilter.value===lastAccount)return accountPending;
    const id=accountFilter.value,code=accountFilter.selectedOptions?.[0]?.dataset.territoryCnes||'';
    const previous=accountPending;
    lastAccount=id;
    accountPending=(async()=>{
      await previous;
      if(id!==lastAccount)return;
      if(code){
        const found=await overlay.selectCode(code);
        linkedCode=found?code:'';
      }else if(linkedCode && overlay.getFilters().cnes===linkedCode){
        await overlay.resetFrame();linkedCode='';
      }
    })();
    return accountPending;
  }
  window.mapTerritory={syncAccountFilter,getFilters:()=>({...overlay.getFilters(),quadra:areaActive()?quadraSelect.value:''}),frame:()=>{
    const selected=areaActive()&&features.find(f=>f.id===quadraSelect.value);
    if(selected){const b=window.UvisTerritory.bounds([selected]);maps[1]?.fitBounds({west:b.west,east:b.east,south:b.south,north:b.north},40);}
    else if(mapShown())overlay.fitGoogle(mapShown());
  }};
  function tabChanged(){
    const active=areaActive();
    const host=document.querySelector(active?'#tabArea [data-map-display-host]':'#tabCalor [data-map-display-host]');
    if(host&&displayPanel)host.appendChild(displayPanel);
    const areaOptions=displayPanel?.querySelector('[data-map-area-options]');
    if(areaOptions)areaOptions.hidden=!active;
  }
  document.querySelectorAll('#mapTabs [data-bs-toggle="tab"]').forEach(tab=>tab.addEventListener('shown.bs.tab',tabChanged));
  tabChanged();
  document.addEventListener('operationalmaps:ready',e=>attach(e.detail.maps));
  if(window.__operationalMaps)attach(window.__operationalMaps);
})();
