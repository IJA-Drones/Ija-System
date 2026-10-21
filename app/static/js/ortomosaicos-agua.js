/* Explicit water measurements, scoped to the authorized survey. */
'use strict';
window.createOrthoWater = ({map, api}) => {
  const el = name => document.getElementById(`ortho-water-${name}`);
  const source = new ol.source.Vector();
  const draft = new ol.source.Vector();
  const style = (color, fill) => new ol.style.Style({
    stroke:new ol.style.Stroke({color,width:2}), fill:new ol.style.Fill({color:fill}),
    image:new ol.style.Circle({radius:7,fill:new ol.style.Fill({color}),stroke:new ol.style.Stroke({color:'#10202b',width:2})})
  });
  const savedLayer = new ol.layer.Vector({source,style:style('#a9c5df','#a9c5df22'),zIndex:30});
  const draftLayer = new ol.layer.Vector({source:draft,style:style('#39d6ca','#39d6ca44'),zIndex:31});
  map.addLayer(savedLayer);map.addLayer(draftLayer);
  const format = new ol.format.GeoJSON();
  const projection = {dataProjection:'EPSG:4326',featureProjection:'EPSG:3857'};
  const inputs = {comprimento_m:'length',largura_m:'width',diametro_m:'diameter',
    profundidade_m:'depth',agua_m:'current',capacidade_l:'capacity',ocupacao_pct:'percent'};
  let survey = null, geom = null, editing = null, draw = null, timer = null;
  let revision = 0, context = 0, listRevision = 0, busy = false, dirty = false;
  let saved = [];
  const liters = n => n == null ? 'Não informada' : `${n.toLocaleString('pt-BR',{maximumFractionDigits:1})} L`;
  const status = (text, error=false) => {el('status').textContent=text;el('status').classList.toggle('error',error);};
  function open(show) {
    el('panel').hidden=!show;el('toggle').setAttribute('aria-expanded',String(show));
    if(show) {
      document.getElementById('ortho-layers-panel').hidden=true;
      document.getElementById('ortho-layers-toggle').setAttribute('aria-expanded','false');
    } else if(draw) {stopDrawing();changed(false);}
  }
  function stopDrawing() {
    if(draw){map.removeInteraction(draw);draw=null;}
    el('drawing').hidden=true;
  }
  function setGeometry(value) {
    geom=value;draft.clear();
    if(value)draft.addFeature(format.readFeature({type:'Feature',geometry:value},projection));
    el('location').textContent=value ? (value.type==='Polygon'?'Área marcada no mapa.':'Localização marcada no mapa.') :
      (el('method').value==='mapa'?'Contorne a área interna do recipiente.':'Marque a localização do recipiente.');
  }
  function configure() {
    const method=el('method').value;
    el('rectangle').hidden=method!=='retangular';
    el('cylinder').hidden=method!=='cilindrico';
    el('depths').hidden=method==='capacidade';
    el('known').hidden=method!=='capacidade';
    const active = method==='capacidade'?['capacity','percent']:
      ['depth','current',...(method==='retangular'?['length','width']:method==='cilindrico'?['diameter']:[])];
    Object.values(inputs).forEach(name=>{
      el(name).disabled=!active.includes(name);
      el(name).required=active.includes(name)&&!['current','percent'].includes(name);
    });
    el('draw').textContent=method==='mapa'?'Desenhar área no mapa':'Marcar localização no mapa';
    el('assumption').textContent=method==='capacidade'?
      'O percentual representa a fração do volume, não a altura da água. Deixe em branco se desconhecido.':
      'Para paredes verticais. Use a profundidade média sobre toda a área; deixe a água atual em branco se desconhecida.';
    setGeometry(geom);
  }
  function payload() {
    const data={nome:el('name').value,tipo:el('kind').value,metodo:el('method').value,
      origem:el('origin').value,observacoes:el('notes').value,geometria:geom};
    Object.entries(inputs).forEach(([key,name])=>{if(!el(name).disabled)data[key]=el(name).value;});
    return data;
  }
  function showResult(item) {
    const result=item.resultado;
    el('result').hidden=false;
    el('total').textContent=liters(result.capacidade_l);
    el('volume').textContent=liters(result.agua_l);
    el('area').textContent=result.area_m2 == null ? 'Capacidade informada · volume proporcional ao percentual' :
      `Área ${result.area_m2.toLocaleString('pt-BR',{maximumFractionDigits:2})} m² · profundidades informadas`;
  }
  function invalidate() {
    revision++;clearTimeout(timer);el('save').disabled=true;el('result').hidden=true;
  }
  function changed(markDirty=true) {
    if(markDirty)dirty=true;
    invalidate();
    status('Preencha as medidas e marque o recipiente.');
    if(!survey||!geom||!el('form').checkValidity())return;
    const token=revision, url=survey.agua_url;
    timer=setTimeout(async()=>{
      status('Calculando estimativa…');
      try {
        const data=await api(`${url}/calcular`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload())});
        if(token!==revision)return;
        showResult(data.item);el('save').disabled=false;
        status('Estimativa calculada com as medidas informadas.');
      } catch(e){if(token===revision)status(e.message,true);}
    },300);
  }
  function reset() {
    invalidate();stopDrawing();editing=null;dirty=false;el('form').reset();setGeometry(null);configure();
    el('save').textContent='Salvar estimativa';status('Preencha as medidas para visualizar a estimativa.');
  }
  function loadItem(item) {
    if(busy)return;
    if(dirty&&!window.confirm('Descartar as alterações ainda não salvas?'))return;
    reset();editing=item.id;
    el('name').value=item.nome;el('kind').value=item.tipo;el('method').value=item.metodo;
    el('origin').value=item.origem;el('notes').value=item.observacoes;
    Object.entries(inputs).forEach(([key,name])=>{el(name).value=item.parametros[key]??'';});
    setGeometry(item.geometria);configure();showResult(item);el('save').textContent='Salvar alterações';
    status('Estimativa salva. Altere os campos para recalcular.');open(true);
    const geometry=draft.getFeatures()[0].getGeometry();
    const size=map.getSize(), panelWidth=size[0]>700?380:30;
    map.getView().fit(geometry.getExtent(),{maxZoom:22,padding:[100,panelWidth,100,45],duration:350});
    el('panel').scrollTop=0;
  }
  function renderList() {
    el('list').replaceChildren();source.clear();
    saved.forEach(item=>{
      const feature=format.readFeature({type:'Feature',geometry:item.geometria},projection);
      feature.set('estimateId',item.id);source.addFeature(feature);
      const row=document.createElement('div');row.className='ortho-water-saved';
      const button=document.createElement('button');button.type='button';button.className='ortho-water-entry';
      const title=document.createElement('strong');title.textContent=item.nome;
      const info=document.createElement('small');info.textContent=`Capacidade ${liters(item.resultado.capacidade_l)} · Água ${liters(item.resultado.agua_l)}`;
      button.append(title,info);button.onclick=()=>loadItem(item);
      const remove=document.createElement('button');remove.type='button';remove.className='ortho-water-delete';
      remove.textContent='Excluir';remove.setAttribute('aria-label',`Excluir ${item.nome}`);
      remove.onclick=async()=>{
        if(busy||!window.confirm(`Excluir a estimativa “${item.nome}”?`))return;
        const current=context, url=survey.agua_url;
        remove.disabled=true;
        try{
          await api(`${url}/${item.id}`,{method:'DELETE'});
          if(current!==context)return;
          if(editing===item.id)reset();
          await refresh();
        }catch(e){if(current===context){el('list-status').textContent=e.message;remove.disabled=false;}}
      };
      row.append(button,remove);el('list').append(row);
    });
    el('list-status').textContent=saved.length?`${saved.length} estimativa(s) salva(s). Selecione para consultar ou editar.`:'Nenhuma estimativa salva neste levantamento.';
  }
  async function refresh() {
    if(!survey)return;
    const token=++listRevision, current=context;
    el('list-status').textContent='Carregando estimativas…';
    try{
      const data=await api(survey.agua_url);
      if(current!==context||token!==listRevision)return;
      saved=data.items;renderList();
    }catch(e){if(current===context&&token===listRevision)el('list-status').textContent=e.message;}
  }
  el('toggle').onclick=()=>open(el('panel').hidden);
  el('close').onclick=()=>open(false);
  el('cancel').onclick=()=>{stopDrawing();open(true);changed(false);};
  el('draw').onclick=()=>{
    stopDrawing();invalidate();
    const polygon=el('method').value==='mapa';
    draw=new ol.interaction.Draw({type:polygon?'Polygon':'Point',maxPoints:500,stopClick:true});
    draw.on('drawend',event=>{
      setGeometry(format.writeGeometryObject(event.feature.getGeometry(),projection));
      stopDrawing();open(true);changed();
    });
    map.addInteraction(draw);el('panel').hidden=true;
    el('instruction').textContent=polygon?'Marque os vértices. Finalize no primeiro ponto ou com duplo clique.':'Toque no mapa para localizar o recipiente.';
    el('drawing').hidden=false;
  };
  el('form').addEventListener('input',changed);
  el('method').addEventListener('change',()=>{configure();changed();});
  el('new').onclick=()=>{if(!dirty||window.confirm('Descartar as alterações ainda não salvas?'))reset();};
  el('refresh').onclick=refresh;
  el('form').onsubmit=async event=>{
    event.preventDefault();if(busy||el('save').disabled||!survey)return;
    clearTimeout(timer);revision++;
    const current=context, url=survey.agua_url, id=editing;
    busy=true;el('fields').disabled=true;status('Salvando…');
    try{
      const data=await api(id?`${url}/${id}`:url,{method:id?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload())});
      if(current!==context)return;
      editing=data.item.id;dirty=false;showResult(data.item);el('save').textContent='Salvar alterações';el('save').disabled=true;
      status('Estimativa salva neste levantamento.');await refresh();
    }catch(e){if(current===context)status(e.message,true);}
    finally{busy=false;el('fields').disabled=false;}
  };
  map.on('singleclick',event=>{
    if(draw||busy)return;
    const feature=map.forEachFeatureAtPixel(event.pixel,f=>f,{layerFilter:l=>l===savedLayer,hitTolerance:5});
    const item=saved.find(i=>i.id===feature?.get('estimateId'));if(item)loadItem(item);
  });
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&draw){stopDrawing();open(true);changed(false);}});
  window.addEventListener('beforeunload',event=>{if(dirty||busy){event.preventDefault();event.returnValue='';}});
  configure();
  return {
    canSelect(item) {
      if(survey?.id===item?.id)return true;
      if(busy)return false;
      return !dirty||window.confirm('Descartar a estimativa ainda não salva e trocar de levantamento?');
    },
    select(item) {
      const next=item?.status==='pronto'?item:null;
      if(survey?.id===next?.id)return;
      context++;survey=next;saved=[];source.clear();el('list').replaceChildren();reset();
      el('toggle').disabled=!next;
      if(!next)open(false);else refresh();
    },
    close:()=>open(false)
  };
};
