(() => {
  'use strict';
  const app = document.getElementById('ortho-app');
  if (!app) return;
  const el = name => document.getElementById(`ortho-${name}`);
  const labels = {pendente:'Na fila',processando:'Processando',pronto:'Disponível',falha:'Falha no processamento'};
  let items = [], selected = null, layer = null, map = null, source = null, uploading = false, pollBusy = false;
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
    map.on('pointermove',event=>{const point=ol.proj.toLonLat(event.coordinate);el('coordinates').textContent=`${point[1].toFixed(6)}°, ${point[0].toFixed(6)}° · WGS 84`;});
  } catch (_) {message('Não foi possível iniciar o mapa neste navegador.',true);}
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
      const sub=document.createElement('small');sub.textContent=`${item.prefeitura} · ${(item.tamanho_bytes/1048576).toFixed(1)} MB`;
      const status=document.createElement('span');status.className=`status ${item.status}`;status.textContent=labels[item.status]||item.status;
      button.append(title,sub,status);button.addEventListener('click',()=>select(item));el('list').append(button);
    });
  }
  function details(item) {
    const meta=item.metadados||{};el('details').replaceChildren();
    const data=[['Prefeitura',item.prefeitura],['Dimensões',`${meta.largura} × ${meta.altura}`],['Coordenadas',meta.crs_origem],['Bandas',meta.bandas],['Enviado em',new Date(item.criado_em).toLocaleDateString('pt-BR')]];
    data.forEach(([label,value])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value??'—';el('details').append(dt,dd);});
    el('detail-name').textContent=item.nome;
  }
  function select(item) {
    const needsLayer = !layer || source?.getState()==='error' || selected?.id!==item.id || selected?.arquivo_url!==item.arquivo_url;
    selected=item;renderList();details(item);el('active-title').textContent=item.nome;
    el('empty').hidden=item.status==='pronto';
    if(item.status!=='pronto'){
      if(layer&&map){map.removeLayer(layer);layer.dispose();layer=null;source=null;}
      el('empty').querySelector('h2').textContent=labels[item.status]||item.status;
      el('empty').querySelector('p').textContent=item.erro||'Seu arquivo está salvo. O sistema está preparando os níveis de zoom para a visualização.';
      message(item.erro||'O processamento continua em segundo plano. Você pode voltar a esta página depois.',item.status==='falha');
      if(item.status==='falha'){
        const retry=document.createElement('button');retry.type='button';retry.textContent='Processar novamente';
        retry.onclick=async()=>{retry.disabled=true;try{const data=await api(item.retry_url,{method:'POST'});Object.assign(item,data.item);select(item);}catch(e){message(e.message,true);retry.disabled=false;el('message').append(retry);}};
        el('message').append(retry);
      }
      return;
    }
    if(!needsLayer||!map)return;
    if(layer){map.removeLayer(layer);layer.dispose();}
    message('Carregando ortomosaico…');
    // The processor emits RGB(A). readRGB would discard the fourth alpha band.
    source=new ol.source.GeoTIFF({sources:[{url:item.arquivo_url}],convertToRGB:false,interpolate:true});
    const thisSource=source;
    layer=new ol.layer.WebGLTile({source,opacity:Number(el('opacity').value)/100,visible:el('visible').checked});
    map.addLayer(layer);fit();
    source.on('change',()=>{if(source===thisSource&&source.getState()==='error')message('Não foi possível ler o ortomosaico. Verifique sua sessão e tente abrir novamente.',true);});
    source.on('tileloaderror',()=>{if(source===thisSource)message('Uma parte do mapa não carregou. Confira sua conexão e recarregue a página.',true);});
    source.getView().then(()=>{if(source===thisSource)message('Ortomosaico disponível. Use o zoom e a opacidade para explorar.');}).catch(()=>message('O navegador não conseguiu abrir este GeoTIFF.',true));
  }
  async function load(preferId) {
    const data=await api(`${app.dataset.listUrl}?prefeitura_id=${encodeURIComponent(el('filter').value)}`);items=data.items;
    const wanted=items.find(i=>i.id===preferId)||items.find(i=>i.id===selected?.id)||items[0];
    if(wanted)select(wanted);else{
      selected=null;if(layer&&map){map.removeLayer(layer);layer.dispose();layer=null;}source=null;
      el('empty').hidden=false;el('empty').querySelector('h2').textContent='Selecione um levantamento';
      el('empty').querySelector('p').textContent='Envie um ortomosaico ou escolha outra prefeitura para visualizar os mapas.';
      el('active-title').textContent='Selecione um levantamento';el('detail-name').textContent='Detalhes do levantamento';
      el('details').replaceChildren();message('Escolha um ortomosaico na biblioteca.');renderList();
    }
  }
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
      el('dialog').close();el('form').reset();el('filter').value=String(data.item.prefeitura_id);
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
