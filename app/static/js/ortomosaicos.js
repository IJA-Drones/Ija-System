(() => {
  'use strict';
  const app = document.getElementById('ortho-app');
  if (!app) return;
  const el = name => document.getElementById(`ortho-${name}`);
  const labels = {pendente:'Na fila',processando:'Processando',pronto:'Disponível',falha:'Falha no processamento'};
  let items = [], selected = null, layer = null, map = null, source = null, uploading = false, pollBusy = false;
  let referenceLayer = null, vectorRequest = null;
  const base = new ol.layer.Tile({source:new ol.source.OSM()});
  const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
  function message(text, error=false) {el('message').textContent=text;el('message').classList.toggle('error',error);}
  async function api(url, options={}) {
    const response=await fetch(url,{...options,headers:{Accept:'application/json','X-CSRFToken':csrf(),...options.headers}});
    const data=await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(response.status===401 ? 'Sua sessão expirou. Entre novamente para continuar.' : data.error || 'Não foi possível concluir esta operação.');
    return data;
  }
  try {
    map = new ol.Map({target:'ortho-map',layers:[base],view:new ol.View({center:ol.proj.fromLonLat([-47,-23]),zoom:6})});
    window.initOrthoBasemap(base);
    el('layers-panel').hidden=map.getSize()[0]<650;
    el('layers-toggle').setAttribute('aria-expanded',String(!el('layers-panel').hidden));
    map.on('singleclick', event=>{
      if(selected?.tipo!=='dem')return;
      const feature=map.forEachFeatureAtPixel(event.pixel, f=>f, {layerFilter:l=>l===layer,hitTolerance:6});
      el('elevation').textContent=feature?`Cota: ${Number(feature.get('cota')).toLocaleString('pt-BR')} m${feature.get('mestra')?' · Curva mestra':''}`:'Clique em uma curva para consultar sua cota.';
    });
    map.on('pointermove',event=>{const point=ol.proj.toLonLat(event.coordinate);el('coordinates').textContent=`${point[1].toFixed(6)}°, ${point[0].toFixed(6)}° · WGS 84`;});
  } catch (_) {message('Não foi possível iniciar o mapa neste navegador.',true);}
  const rasterCache = map ? window.createOrthoRasterCache({map, onStatus: rasterStatus}) : null;
  function referenceStatus(entry) {
    const notice=el('reference-status');notice.hidden=false;
    const item=items.find(i=>String(i.id)===el('reference').value);
    const bounds=item?.metadados?.limites, demBounds=selected?.metadados?.limites;
    const outside=bounds&&demBounds&&!ol.extent.intersects(bounds,demBounds);
    notice.textContent=entry.status==='error'?'Não foi possível carregar a referência. Selecione-a novamente para tentar.':
      outside?'Esta referência não cobre a área das curvas selecionadas.':
      entry.status==='ready'?'Referência carregada.':'Carregando ortomosaico de referência…';
    notice.classList.toggle('error',entry.status==='error');
    notice.setAttribute('aria-busy',String(!outside&&entry.status==='loading'));
  }
  function rasterStatus(entry) {
    if(entry.layer===referenceLayer)referenceStatus(entry);
    if(entry.layer===layer&&selected?.tipo!=='dem')message(entry.status==='error'?
      'Não foi possível carregar o ortomosaico. Selecione-o novamente para tentar.':
      entry.status==='ready'?'Ortomosaico disponível. Use o zoom e a opacidade para explorar.':'Carregando ortomosaico…',entry.status==='error');
  }
  function releaseMainLayer() {
    if(layer&&map&&!rasterCache.release(layer)){map.removeLayer(layer);layer.dispose();}
    layer=null;source=null;
  }
  function fit() {
    if (!selected?.metadados?.limites || !map) return;
    map.getView().fit(ol.proj.transformExtent(selected.metadados.limites,'EPSG:4326','EPSG:3857'),
      {padding:el('layers-panel').hidden?[85,35,65,35]:(map.getSize()[0]>650?[85,260,65,40]:[85,25,270,25]),duration:500,maxZoom:23});
  }
  function renderList() {
    el('list').replaceChildren();el('count').textContent=items.length;
    if(!items.length){const p=document.createElement('p');p.className='ortho-muted';p.textContent='Nenhum ortomosaico nesta seleção. Envie o primeiro levantamento.';el('list').append(p);}
    items.forEach(item=>{
      const button=document.createElement('button');button.type='button';button.className=`ortho-item${item.id===selected?.id?' selected':''}`;
      button.setAttribute('aria-pressed',String(item.id===selected?.id));
      const title=document.createElement('strong');title.textContent=item.nome;
      const sub=document.createElement('small');sub.textContent=`${item.tipo==='dem'?'Curvas de nível':'RGB'} · ${item.prefeitura} · ${(item.tamanho_bytes/1048576).toFixed(1)} MB`;
      const status=document.createElement('span');status.className=`status ${item.status}`;status.textContent=labels[item.status]||item.status;
      button.append(title,sub,status);button.addEventListener('click',()=>select(item));el('list').append(button);
    });
  }
  function details(item) {
    const meta=item.metadados||{};el('details').replaceChildren();
    const data=[['Prefeitura',item.prefeitura],['Dimensões',`${meta.largura} × ${meta.altura}`],['Coordenadas',meta.crs_origem],['Bandas',meta.bandas],['Enviado em',new Date(item.criado_em).toLocaleDateString('pt-BR')]];
    if(item.tipo==='dem')data.push(['Intervalo',`${item.intervalo_m} m`],['Grade',`${meta.resolucao_m||item.resolucao_m} m`],['Curvas',meta.curvas||'—'],['CRS de cálculo',meta.crs_processamento||'—']);
    data.forEach(([label,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value??'—';el('details').append(dt,dd);});
    el('detail-name').textContent=item.nome;el('loading-note').textContent=item.tipo==='dem'?'JPEG com estilo cartográfico fixo. Os controles acima alteram a camada no mapa.':'O mapa carrega os trechos necessários conforme você navega.';
  }
  const styleCache=new Map();
  function curveStyle(feature, resolution) {
    const key=[feature.get("cota"),feature.get("mestra"),resolution<1].join(":");
    if(styleCache.has(key))return styleCache.get(key);
    const master=feature.get('mestra');
    const style=new ol.style.Style({stroke:new ol.style.Stroke({color:el('color').value,width:Number(el('width').value)*(master?1.8:1)}),
      text:el('labels').checked&&(master||resolution<1)?new ol.style.Text({text:`${feature.get('cota')} m`,placement:'line',repeat:250,
        font:'12px sans-serif',fill:new ol.style.Fill({color:el('color').value}),stroke:new ol.style.Stroke({color:'#14212b',width:3})}):undefined});
    styleCache.set(key,style);return style;
  }
  function clearReference() {
    if(referenceLayer)rasterCache?.release(referenceLayer);referenceLayer=null;
    el('reference-status').hidden=true;el('reference-status').textContent='';el('reference-status').setAttribute('aria-busy','false');
  }
  function referenceOptions(item) {
    const previous=el('reference').value;
    el('reference').replaceChildren(new Option('Sem ortomosaico',''));
    items.filter(i=>i.tipo!=='dem'&&i.status==='pronto'&&i.prefeitura_id===item.prefeitura_id).forEach(i=>el('reference').add(new Option(i.nome,String(i.id))));
    el('reference').value=previous;
    if(!el('reference').value)clearReference();
  }
  function select(item) {
    const needsLayer = !layer || layer.get('loadError') || source?.getState()==='error' || selected?.id!==item.id || selected?.arquivo_url!==item.arquivo_url || selected?.curvas_url!==item.curvas_url;
    if(needsLayer){vectorRequest?.abort();vectorRequest=null;styleCache.clear();}
    el('dem-controls').hidden=item.tipo!=='dem'||item.status!=='pronto';
    el('jpeg').removeAttribute('href');if(item.jpeg_url)el('jpeg').href=item.jpeg_url;
    el('layer-label').textContent=item.tipo==='dem'?'Curvas de nível':'Ortomosaico RGB';
    if(item.tipo==='dem')referenceOptions(item);else clearReference();
    selected=item;renderList();details(item);el('active-title').textContent=item.nome;
    if(item.tipo!=='dem'||item.status!=='pronto')clearReference();
    el('empty').hidden=item.status==='pronto';
    if(item.status!=='pronto'){
      releaseMainLayer();
      el('empty').querySelector('h2').textContent=labels[item.status]||item.status;
      el('empty').querySelector('p').textContent=item.erro||'Seu arquivo está salvo. O sistema está preparando o mapa e os resultados. Acompanhe o estado na biblioteca.';
      message(item.erro||'O processamento continua em segundo plano. Você pode voltar a esta página depois.',item.status==='falha');
      if(item.status==='falha'){
        const retry=document.createElement('button');retry.type='button';retry.textContent='Processar novamente';
        const params={};
        if(item.tipo==='dem'){
          for(const [key,label,value,min,max] of [['intervalo_m','Intervalo (m)',item.intervalo_m,.25,1000],['resolucao_m','Resolução (m)',item.resolucao_m,.25,100]]){
            const control=document.createElement('input');control.type='number';control.min=min;control.max=max;control.step='any';control.value=value;control.required=true;
            control.setAttribute('aria-label',label);const wrapper=document.createElement('label');wrapper.textContent=label;wrapper.append(control);el('message').append(wrapper);params[key]=control;
          }
        }
        retry.onclick=async()=>{retry.disabled=true;try{const values=Object.fromEntries(Object.entries(params).map(([k,v])=>[k,v.value]));const data=await api(item.retry_url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)});Object.assign(item,data.item);select(item);}catch(e){retry.disabled=false;const notice=document.createElement('p');notice.textContent=e.message;el('message').append(notice);}};
        el('message').append(retry);
      }
      return;
    }
    if(!needsLayer||!map){if(item.tipo==='dem'&&map)updateReference();return;}
    releaseMainLayer();
    if(item.tipo==='dem')updateReference();
    if(item.tipo==='dem'){
      source=new ol.source.Vector();
      layer=new ol.layer.Vector({source,style:curveStyle,declutter:true,opacity:Number(el('opacity').value)/100,visible:el('visible').checked});
      layer.setZIndex(10);map.addLayer(layer);fit();message('Carregando curvas de nível…');
      const thisSource=source,controller=new AbortController();vectorRequest=controller;
      api(item.curvas_url,{signal:controller.signal}).then(data=>{
        if(source!==thisSource)return;
        source.addFeatures(new ol.format.GeoJSON().readFeatures(data,{dataProjection:'EPSG:4326',featureProjection:'EPSG:3857'}));
        message(`Curvas disponíveis · intervalo ${item.intervalo_m} m · grade ${item.metadados.resolucao_m} m. ${item.metadados.aviso||''}`);
      }).catch(e=>{if(e.name!=='AbortError'&&source===thisSource){layer.set('loadError',true);message(e.message,true);}});
      return;
    }
    message('Carregando ortomosaico…');
    const raster=rasterCache.acquire(item);source=raster.source;layer=raster.layer;
    layer.setZIndex(1);layer.setOpacity(Number(el('opacity').value)/100);layer.setVisible(el('visible').checked);
    fit();rasterStatus(raster);
  }
  async function load(preferId) {
    const data=await api(`${app.dataset.listUrl}?prefeitura_id=${encodeURIComponent(el('filter').value)}`);items=data.items;rasterCache?.retain(items);
    const wanted=items.find(i=>i.id===preferId)||items.find(i=>i.id===selected?.id)||items[0];
    if(wanted)select(wanted);else{
      vectorRequest?.abort();clearReference();el('dem-controls').hidden=true;el('jpeg').removeAttribute('href');
      selected=null;releaseMainLayer();
      el('empty').hidden=false;el('empty').querySelector('h2').textContent='Selecione um levantamento';
      el('empty').querySelector('p').textContent='Envie um ortomosaico ou escolha outra prefeitura para visualizar os mapas.';
      el('active-title').textContent='Selecione um levantamento';el('detail-name').textContent='Detalhes do levantamento';
      el('details').replaceChildren();message('Escolha um ortomosaico na biblioteca.');renderList();
    }
  }
  function updateReference() {
    const item=items.find(i=>String(i.id)===el('reference').value&&i.prefeitura_id===selected?.prefeitura_id&&i.tipo!=='dem'&&i.status==='pronto');
    if(!item||!map){clearReference();return;}
    clearReference();
    const raster=rasterCache.acquire(item);referenceLayer=raster.layer;
    referenceLayer.setZIndex(1);referenceLayer.setOpacity(1);referenceLayer.setVisible(true);referenceStatus(raster);
  }
  el('reference').onchange=updateReference;
  ['color','width','labels'].forEach(name=>el(name).addEventListener('input',()=>{if(selected?.tipo==='dem'){styleCache.clear();layer?.changed();}}));
  function updateType(){
    const dem=el('type').value==='dem';el('dem-fields').hidden=!dem;
    ['interval','resolution','meters'].forEach(name=>{el(name).disabled=!dem;el(name).required=dem;});
    el('format-hint').textContent=dem?'Uma banda numérica com altitudes em metros.':'RGB de 8 bits, com ou sem transparência.';
    el('send').textContent=dem?'Enviar e gerar curvas':'Enviar e preparar mapa';
  }
  el('type').onchange=updateType;
  updateType();
  el('filter').addEventListener('change',()=>load().catch(e=>message(e.message,true)));
  el('visible').onchange=()=>layer?.setVisible(el('visible').checked);
  el('opacity').oninput=()=>{el('opacity-label').textContent=`${el('opacity').value}%`;layer?.setOpacity(Number(el('opacity').value)/100);};
  el('fit').onclick=fit;
  el('layers-toggle').onclick=()=>{el('layers-panel').hidden=!el('layers-panel').hidden;el('layers-toggle').setAttribute('aria-expanded',String(!el('layers-panel').hidden));};
  el('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await el('stage').requestFullscreen();map?.updateSize();fit();}catch(_){message('Tela cheia não está disponível neste navegador.',true);}};
  el('new').onclick=()=>{el('prefeitura').value=el('filter').value;el('dialog').showModal();};
  el('close').onclick=()=>{if(!uploading)el('dialog').close();};
  el('dialog').addEventListener('cancel',e=>{if(uploading)e.preventDefault();});
  el('form').addEventListener('submit',event=>{
    event.preventDefault();if(uploading)return;
    const file=el('file').files[0];
    if(!file){el('upload-status').textContent='Selecione um arquivo TIF.';return;}
    const limitMb=Number(app.dataset.maxMb);
    if(limitMb>0&&file.size>limitMb*1048576){el('upload-status').textContent=`Selecione um TIF de até ${limitMb} MB.`;return;}
    uploading=true;el('send').disabled=true;el('close').disabled=true;el('upload-progress').hidden=false;
    const xhr=new XMLHttpRequest();xhr.open('POST',app.dataset.uploadUrl);xhr.setRequestHeader('X-CSRFToken',csrf());xhr.setRequestHeader('Accept','application/json');
    xhr.upload.onprogress=e=>{if(e.lengthComputable){const percent=Math.round(e.loaded/e.total*100);el('upload-progress').value=percent;el('upload-status').textContent=percent===100?'Validando e armazenando o arquivo…':`Enviando arquivo… ${percent}%`;}};
    const finish=()=>{uploading=false;el('send').disabled=false;el('close').disabled=false;};
    xhr.onload=async()=>{finish();let data={};try{data=JSON.parse(xhr.responseText);}catch(_){}
      if(xhr.status!==202){el('upload-status').textContent=data.error||(xhr.status===413?'A hospedagem recusou o tamanho deste envio. Solicite o ajuste do limite de upload do servidor.':'Não foi possível enviar. Confira sua sessão e tente novamente.');return;}
      el('dialog').close();el('form').reset();updateType();el('filter').value=String(data.item.prefeitura_id);
      await load(data.item.id).catch(e=>message(e.message,true));};
    xhr.onerror=()=>{finish();el('upload-status').textContent='A conexão foi interrompida. Confira a biblioteca antes de repetir o envio.';};
    xhr.send(new FormData(el('form')));
  });
  load(Number(new URLSearchParams(location.search).get('id'))).catch(e=>message(e.message,true));
  setInterval(async()=>{
    if(pollBusy||document.hidden)return;pollBusy=true;
    try{for(const item of items.filter(i=>['pendente','processando'].includes(i.status)).slice(0,5)){
      const data=await api(item.status_url);const changed=data.item.status!==item.status;Object.assign(item,data.item);
      if(changed){if(selected?.id===item.id)select({...item});else renderList();}
    }}catch(e){message(e.message,true);}finally{pollBusy=false;}
  },4000);
})();
