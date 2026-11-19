/* Saved polygon masks share the existing COG source; no TIFF is copied. */
'use strict';
window.createOrthoAreas = ({map, api, onOpen, onIsolate, onOriginal}) => {
  const el = name => document.getElementById(`ortho-area-${name}`);
  const format = new ol.format.GeoJSON();
  const projection = {dataProjection:'EPSG:4326',featureProjection:'EPSG:3857'};
  const draft = new ol.source.Vector();
  const outlineStyle = new ol.style.Style({stroke:new ol.style.Stroke({color:'#ffcb66',width:3}),fill:new ol.style.Fill({color:'#ffcb6620'})});
  const draftLayer = new ol.layer.Vector({source:draft,style:outlineStyle,zIndex:45});
  map.addLayer(draftLayer);
  let survey=null, rasterSource=null, geometry=null, draw=null, busy=false, generation=0, revision=0, editing=null, active=null, listRevision=0;
  const entries = new Map();
  const number = n => n.toLocaleString('pt-BR',{maximumFractionDigits:2});
  const result = data => `${number(data.area_m2)} m² · ${number(data.area_ha)} ha · Perímetro: ${number(data.perimetro_m)} m`;
  const status = text => {el('status').textContent=text;};
  function stop() {if(draw)map.removeInteraction(draw);draw=null;el('drawing').hidden=true;}
  function open(show) {
    if(show){if(el('panel').hidden)el('panel').scrollTop=0;onOpen();document.getElementById('ortho-layers-panel').hidden=true;document.getElementById('ortho-layers-toggle').setAttribute('aria-expanded','false');}
    else stop();
    el('panel').hidden=!show;el('toggle').setAttribute('aria-expanded',String(show));
  }
  function clear(resetEditing=true) {if(resetEditing){editing=null;el('save').textContent='Salvar área e recorte';}revision++;stop();geometry=null;draft.clear();el('save').disabled=true;el('result').textContent='Nenhum contorno desenhado.';}
  function isolate(value) {el('isolate').checked=value;el('original').hidden=!value;onIsolate(value);}
  function mode(saved) {
    el('editor').hidden=saved;el('saved').hidden=!saved;
    el('new-tab').setAttribute('aria-pressed',String(!saved));
    el('saved-tab').setAttribute('aria-pressed',String(saved));
    el('panel').scrollTop=0;
  }
  function showSaved() {stop();mode(true);open(true);}
  function discard() {return !busy&&(!(geometry||draw)||confirm('Descartar as alterações ainda não salvas?'));}
  function showOriginal(fit=true) {
    active=null;for(const entry of entries.values())setVisible(entry,false);
    isolate(false);onOriginal?.(fit);render();status('Ortomosaico inteiro. Selecione um recorte em Meus recortes para voltar a ele.');
  }
  function setVisible(entry,value) {entry.raster.setVisible(value);entry.outline.setVisible(value);}
  function fitEntry(entry) {
    map.getView().fit(entry.polygon.getExtent(),{padding:[180,map.getSize()[0]>800&&!el('panel').hidden?430:60,90,60],duration:300,maxZoom:23});
  }
  function activate(entry) {
    if(busy)return;
    active=entry.item.id;for(const candidate of entries.values())setVisible(candidate,candidate===entry);
    isolate(true);showSaved();render();fitEntry(entry);
    status(`Recorte selecionado: ${entry.item.nome}.`);
  }
  function edit(entry) {
    if(!discard())return;
    clear();editing=entry.item.id;geometry=entry.item.geometria;
    draft.addFeature(format.readFeature({type:'Feature',geometry},projection));
    el('name').value=entry.item.nome;el('result').textContent=result(entry.item.resultado);
    el('save').textContent='Salvar alterações';el('save').disabled=false;
    showOriginal(false);mode(false);open(true);fitEntry(entry);
    status('Edite o nome ou redesenhe o contorno e salve as alterações.');
  }
  function removeLayers(entry) {
    for(const layer of [entry.raster,entry.outline]){map.removeLayer(layer);layer.dispose();}
    entry.outline.getSource()?.clear();
  }
  function add(item) {
    const feature=format.readFeature({type:'Feature',geometry:item.geometria},projection);
    const polygon=feature.getGeometry();
    // A unique class prevents OpenLayers from sharing this WebGL canvas.
    // WebGL canvases use viewport CSS dimensions, independently of pixel ratio.
    const raster=new ol.layer.WebGLTile({source:rasterSource,className:`ortho-crop-${item.id}`,visible:false,zIndex:20,cacheSize:32});
    const clip=event=>{
      const container=event.context?.canvas;
      if(!container)return;
      const points=polygon.getCoordinates()[0].map(p=>map.getPixelFromCoordinate(p));
      container.style.clipPath=points.every(p=>p&&p.every(Number.isFinite))?
        `polygon(${points.map(p=>`${p[0]}px ${p[1]}px`).join(',')})`:'polygon(0 0,0 0,0 0)';
    };
    raster.on('prerender',clip);
    const outline=new ol.layer.Vector({source:new ol.source.Vector({features:[feature]}),style:new ol.style.Style({stroke:new ol.style.Stroke({color:'#ffcb66',width:2})}),zIndex:40});
    raster.setVisible(false);outline.setVisible(false);
    map.addLayer(raster);map.addLayer(outline);
    entries.set(item.id,{item,raster,outline,polygon});
  }
  function button(text, action) {const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=action;return b;}
  function render() {
    el('list').replaceChildren();el('library-list').replaceChildren();
    el('saved-toggle').textContent=`Meus recortes (${entries.size})`;
    if(!entries.size)el('library-list').textContent='Nenhum recorte salvo.';
    el('isolate').disabled=!entries.size;
    if(!entries.size){el('list').textContent='Nenhuma área salva.';isolate(false);}
    for(const entry of entries.values()){
      const {item,raster,outline,polygon}=entry;
      const card=document.createElement('article');card.className=`ortho-area-card${active===item.id?' selected':''}`;
      const label=document.createElement('label'),toggle=document.createElement('input');toggle.type='checkbox';toggle.checked=raster.getVisible();
      toggle.onchange=()=>{setVisible(entry,toggle.checked);if(!toggle.checked&&active===item.id)active=null;if(![...entries.values()].some(e=>e.raster.getVisible()))showOriginal(false);else render();};
      label.append(toggle,document.createTextNode(item.nome));
      const measurement=document.createElement('p');measurement.textContent=result(item.resultado);
      const actions=document.createElement('div');
      actions.append(button('Abrir recorte',()=>activate(entry)),button('Editar',()=>edit(entry)),
        button('Baixar contorno',()=>{
          const blob=new Blob([JSON.stringify({type:'FeatureCollection',features:[{type:'Feature',geometry:item.geometria,properties:{nome:item.nome,...item.resultado}}]})],{type:'application/geo+json'});
          const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`area-${item.id}.geojson`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
        }),button('Excluir',async()=>{
          if(busy||!confirm(`Excluir a área e o recorte “${item.nome}”?`))return;
          setBusy(true);
          try{await api(`${survey.areas_url}/${item.id}`,{method:'DELETE'});removeLayers(entry);entries.delete(item.id);if(editing===item.id)clear();if(active===item.id)showOriginal(false);render();status('Área excluída.');}
          catch(e){status(e.message);}finally{setBusy(false);}
        }));
      card.append(label,measurement,actions);el('list').append(card);
      const shortcut=button(item.nome,()=>activate(entry));shortcut.className='ortho-area-shortcut';shortcut.setAttribute('aria-pressed',String(active===item.id));el('library-list').append(shortcut);
    }
  }
  function setBusy(value) {busy=value;el('fields').disabled=value;}
  function newArea() {
    if(!discard())return;
    clear();el('name').value='';showOriginal(false);mode(false);open(true);status('');
  }
  async function refresh() {
    if(!survey||busy)return;
    const ctx=generation,requestId=++listRevision;
    status('Carregando recortes salvos…');el('library-list').textContent='Carregando recortes…';
    try {
      const data=await api(survey.areas_url);
      if(ctx!==generation||requestId!==listRevision)return;
      const visible=new Set([...entries.values()].filter(e=>e.raster.getVisible()).map(e=>e.item.id));
      for(const entry of entries.values())removeLayers(entry);entries.clear();
      data.items.forEach(add);for(const entry of entries.values())setVisible(entry,visible.has(entry.item.id));
      if(active&&!entries.has(active))showOriginal(false);
      render();status('');
    } catch(e) {if(ctx===generation&&requestId===listRevision){status(e.message);el('library-list').textContent='Não foi possível carregar os recortes. Abra Gerenciar recortes e atualize a lista.';}}
  }
  el('toggle').onclick=()=>{stop();mode(false);open(true);};
  el('new-tab').onclick=newArea;
  for(const name of ['saved-toggle','saved-tab','library-open','manage'])el(name).onclick=showSaved;
  el('refresh').onclick=refresh;
  el('original').onclick=()=>showOriginal();el('back-original').onclick=()=>showOriginal();
  el('close').onclick=()=>open(false);
  el('clear').onclick=()=>{clear();status('');};
  el('isolate').onchange=()=>isolate(el('isolate').checked);
  el('draw').onclick=()=>{
    clear(false);showOriginal(false);onOpen();open(false);el('drawing').hidden=false;
    draw=new ol.interaction.Draw({source:draft,type:'Polygon',maxPoints:500});map.addInteraction(draw);
    draw.on('drawend',async event=>{
      geometry=format.writeGeometryObject(event.feature.getGeometry(),projection);
      const current=++revision,ctx=generation;
      // Let OpenLayers finish inserting the feature before detaching the interaction.
      setTimeout(()=>{if(ctx===generation){stop();mode(false);open(true);}},0);
      status('Calculando área…');
      try{
        const data=await api(survey.areas_url+'/calcular',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome:el('name').value.trim()||'Nova área',geometria:geometry})});
        if(current!==revision||ctx!==generation)return;
        el('result').textContent=result(data.item.resultado);el('save').disabled=false;status('Área calculada. Dê um nome e salve o recorte.');
      }catch(e){if(current===revision&&ctx===generation)status(e.message);}
    });
  };
  el('undo').onclick=()=>draw?.removeLastPoint();
  el('finish').onclick=()=>draw?.finishDrawing();
  el('cancel').onclick=()=>{clear();open(true);};
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&draw){clear();open(true);}});
  el('form').onsubmit=async event=>{
    event.preventDefault();if(busy||!geometry||el('save').disabled)return;
    setBusy(true);status('Salvando…');
    try{
      const data=await api(editing?`${survey.areas_url}/${editing}`:survey.areas_url,{method:editing?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome:el('name').value,geometria:geometry})});
      listRevision++;const previous=entries.get(data.item.id);if(previous)removeLayers(previous);
      add(data.item);clear();el('name').value='';setBusy(false);activate(entries.get(data.item.id));status('Área salva. Abra este recorte a qualquer momento em Meus recortes.');
    }catch(e){status(e.message);}finally{setBusy(false);}
  };
  window.addEventListener('beforeunload',event=>{if(geometry||draw||busy){event.preventDefault();event.returnValue='';}});
  return {
    close:()=>open(false),
    originalShown:()=>{el('isolate').checked=false;el('original').hidden=true;},
    showOriginal,
    canSelect:item=>survey?.id===item?.id||(!busy&&(!(geometry||draw)||confirm('Descartar o desenho ainda não salvo e trocar de levantamento?'))),
    select(item,source) {
      const next=item?.status==='pronto'&&item.tipo==='rgb'?item:null;
      if(next?.id===survey?.id&&source===rasterSource)return;
      generation++;listRevision++;active=null;clear();isolate(false);for(const entry of entries.values())removeLayers(entry);entries.clear();render();
      survey=next;rasterSource=source;el('toggle').disabled=!next;el('saved-toggle').disabled=!next;el('library').hidden=!next;el('manage').hidden=!next;el('name').value='';status('');open(false);
      if(!next)return;
      mode(false);refresh();
    }
  };
};
