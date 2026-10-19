/* One definition and one response drive table, chart and map. */
(() => {
  'use strict';
  const $ = id => document.getElementById(`cq-${id}`);
  const catalog = JSON.parse($('catalog-data').textContent), fields = Object.fromEntries(catalog.fields.map(f => [f.id, f]));
  let selected = ['id', 'data', 'bairro', 'categoria', 'status'], formats = {}, saved = [], currentId = null, version = null;
  let result = null, page = 0, busy = false, map = null, layer = null, editVersion = 0;
  let preparedEmailUrl = null;
  const base = '/relatorios/consultas';
  const node = (tag, text, cls) => { const el = document.createElement(tag); if(text !== undefined) el.textContent=text; if(cls) el.className=cls; return el; };
  const option = (label,value) => { const el=node('option',label); el.value=value;return el; };
  function message(text,error=false){$('message').textContent=text;$('message').className=error?'mt-2 cq-error':'mt-2';}
  async function api(url, data, method='POST', blob=false){
    const controller = new AbortController(), timer = setTimeout(()=>controller.abort(),60000);
    try {
      const response=await fetch(url,{method,headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('meta[name="csrf-token"]')?.content||''},body:data===undefined?undefined:JSON.stringify(data),signal:controller.signal});
      if(!response.ok){let error='Não foi possível concluir. Verifique sua sessão e tente novamente.';try{error=(await response.json()).error||error;}catch{}throw new Error(error);}
      return blob ? response.blob() : response.json();
    } finally {clearTimeout(timer);}
  }
  async function task(fn, label='Consultando dados… Aguarde.'){
    if(busy)return;busy=true;message(label);$('run').disabled=true;
    try{await fn();}catch(error){message(error.name==='AbortError'?'A operação demorou mais que o esperado. Verifique o resultado antes de repetir.':error.message,true);}
    finally{busy=false;$('run').disabled=false;}
  }
  function formatSelect(value, change){const s=node('select',undefined,'form-select form-select-sm');[['Padrão','padrao'],['Inteiro','inteiro'],['Decimal','decimal'],['Percentual','percentual']].forEach(([l,v])=>s.append(option(l,v)));s.value=value||'padrao';s.onchange=()=>change(s.value);return s;}
  function drawFields(){
    $('fields').querySelectorAll('input').forEach(i=>i.checked=selected.includes(i.value));
    $('selected').replaceChildren();const oldGroup=$('group').value;$('group').replaceChildren(option('Sem quebra',''));
    selected.forEach((key,i)=>{
      const div=node('div');div.append(node('span',fields[key].label));
      for(const [label,offset] of [['↑',-1],['↓',1]]){const b=node('button',label,'btn btn-sm btn-outline-secondary');b.type='button';b.disabled=i+offset<0||i+offset>=selected.length;b.setAttribute('aria-label',`${offset<0?'Subir':'Descer'} ${fields[key].label}`);b.onclick=()=>{[selected[i],selected[i+offset]]=[selected[i+offset],selected[i]];editVersion++;drawFields();};div.append(b);}
      if(fields[key].type==='number')div.append(formatSelect(formats[key],v=>{formats[key]=v;editVersion++;}));
      $('selected').append(div);if(fields[key].type==='text')$('group').append(option(fields[key].label,key));
    });$('group').value=selected.includes(oldGroup)?oldGroup:'';
  }
  $('fields').onchange=e=>{const key=e.target.value;if(e.target.checked){if(selected.length>=12){e.target.checked=false;message('Selecione no máximo 12 campos.',true);return;}selected.push(key);}else{selected=selected.filter(k=>k!==key);delete formats[key];}drawFields();};
  function addRule(target, value={field:'bairro',op:'eq',value:''}){
    if($(target).children.length>=10)return;
    const div=node('div',undefined,'cq-rule'), field=node('select',undefined,'form-select'), op=node('select',undefined,'form-select'), input=node('input',undefined,'form-control'), remove=node('button','Remover','btn btn-outline-danger');
    catalog.fields.forEach(f=>field.append(option(f.label,f.id)));field.value=value.field;
    [['Igual a','eq'],['Diferente de','ne'],['Contém','contains'],['Maior ou igual','gte'],['Menor ou igual','lte'],['Não informado','empty']].forEach(([l,v])=>op.append(option(l,v)));op.value=value.op;input.value=value.value??'';
    field.setAttribute('aria-label','Campo');op.setAttribute('aria-label','Condição');input.setAttribute('aria-label','Valor');
    remove.onclick=()=>{div.remove();editVersion++;};div.append(field,op,input,remove);$(target).append(div);
  }
  function addFormula(value={label:'',expression:''},format='padrao'){
    if($('formulas').children.length>=3)return;
    const div=node('div',undefined,'cq-formula'), name=node('input',undefined,'form-control'), expr=node('input',undefined,'form-control'), remove=node('button','Remover','btn btn-outline-danger');
    name.placeholder='Nome da coluna';name.maxLength=60;name.value=value.label;expr.placeholder='imagens + videos';expr.maxLength=200;expr.value=value.expression;
    name.setAttribute('aria-label','Nome da fórmula');expr.setAttribute('aria-label','Expressão');remove.onclick=()=>{div.remove();editVersion++;};div.append(name,expr,formatSelect(format,()=>{}),remove);$('formulas').append(div);
  }
  function definition(){
    const rules=id=>[...$(id).children].map(div=>({field:div.children[0].value,op:div.children[1].value,value:div.children[2].value}));
    const outFormats=Object.fromEntries(Object.entries(formats).filter(([k])=>selected.includes(k)));
    const formulas=[...$('formulas').children].map((div,i)=>{outFormats[`formula_${i}`]=div.children[2].value;return {label:div.children[0].value,expression:div.children[1].value};});
    return {source:$('source').value,columns:selected,formulas,formats:outFormats,group:$('group').value,conditions:rules('conditions'),exclusions:rules('exclusions'),filters:Object.fromEntries(['prefeitura','bairro','categoria','status','inicio','fim'].map(k=>[k,$(k).value]))};
  }
  function load(spec){selected=[...spec.columns];formats={...spec.formats};$('source').value=spec.source;drawFields();$('group').value=spec.group;
    ['prefeitura','bairro','categoria','status','inicio','fim'].forEach(k=>{const value=spec.filters[k]||'';if(['bairro','categoria','status'].includes(k)&&value&&![...$(k).options].some(o=>o.value===value))$(k).append(option(value,value));$(k).value=value;});
    ['conditions','exclusions','formulas'].forEach(k=>$(k).replaceChildren());spec.conditions.forEach(r=>addRule('conditions',r));spec.exclusions.forEach(r=>addRule('exclusions',r));spec.formulas.forEach((f,i)=>addFormula(f,spec.formats[`formula_${i}`]));editVersion++;$('auto').checked=false;message('Definição carregada. Execute para consultar os dados atuais.');
  }
  async function refreshCatalog(){saved=(await api(`${base}/catalogo`,undefined,'GET')).items;$('saved').replaceChildren(option('Nova consulta',''));saved.forEach(r=>$('saved').append(option(r.nome,r.id)));$('saved').value=currentId||'';$('delete').disabled=!currentId;}
  $('saved').onchange=()=>{const row=saved.find(r=>String(r.id)===$('saved').value);currentId=row?.id||null;version=row?.versao||null;$('name').value=row?.nome||'';$('delete').disabled=!row;if(row)load(row.definicao);};
  async function save(copy=false){const value=await api(`${base}/catalogo`,{id:copy?null:currentId,versao:version,nome:$('name').value,definicao:definition()});currentId=value.id;version=value.versao;await refreshCatalog();message('Consulta salva no seu catálogo.');}
  $('save').onclick=()=>task(()=>save());$('copy').onclick=()=>task(()=>save(true));
  function confirm(title,text,email=false){return new Promise(resolve=>{const d=$('dialog');$('dialog-title').textContent=title;$('dialog-text').textContent=text;$('email-label').hidden=!email;$('recipient').required=email;$('confirm').textContent=email&&$('email').dataset.directSend!=='true'?'Baixar PDF e continuar':'Confirmar';d.returnValue='cancel';d.addEventListener('close',()=>resolve(d.returnValue==='confirm'),{once:true});d.showModal();});}
  $('delete').onclick=async()=>{if(currentId&&await confirm('Excluir consulta salva?','A definição será removida do seu catálogo. Os dados do sistema serão preservados.'))task(async()=>{await api(`${base}/catalogo/${currentId}`,undefined,'DELETE');currentId=null;version=null;await refreshCatalog();message('Definição excluída.');});};
  function table(all=false){const t=$('table');t.tHead.replaceChildren();t.tBodies[0].replaceChildren();const header=node('tr');result.columns.forEach(c=>header.append(node('th',c.label)));t.tHead.append(header);
    const start=all?0:page*100,end=all?result.rows.length:Math.min(start+100,result.rows.length), groups=new Map(result.groups.map(g=>[g.start,g]));
    for(let i=start;i<end;i++){if(result.spec.group&&groups.has(i)){const tr=node('tr',undefined,'cq-group-row'),cell=node('td',`${groups.get(i).label} — ${groups.get(i).count} registros`);cell.colSpan=result.columns.length;tr.append(cell);t.tBodies[0].append(tr);}const tr=node('tr');result.rows[i].forEach(value=>tr.append(node('td',value)));t.tBodies[0].append(tr);}
    $('page-info').textContent=result.total?`Exibindo ${start+1}–${end} de ${result.total}`:'Nenhum registro encontrado.';$('prev').disabled=page===0;$('next').disabled=end>=result.total;
  }
  function draw(){
    $('result').hidden=false;page=0;table();$('print').disabled=false;
    $('meta').textContent=`${result.total} registros · Atualizado em ${new Date(result.generated_at).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'})} (Brasília) · Consulta: ${result.duration_ms} ms`;
    $('chart').replaceChildren();Object.entries(result.chart).forEach(([label,total])=>{const d=node('div'),p=node('progress');p.max=Math.max(1,result.total);p.value=total;d.append(node('span',label),p,node('strong',total));$('chart').append(d);});
    $('unmapped').textContent=`${result.points.length} registros no mapa; ${result.unmapped} sem coordenadas válidas (mantidos na tabela).`;
    if(window.L){if(!map){map=L.map($('map'),{preferCanvas:true});L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);}if(layer)map.removeLayer(layer);layer=L.featureGroup(result.points.map(p=>L.circleMarker([p.lat,p.lng],{radius:4}).bindPopup(node('span',`Solicitação ${p.id} · ${p.bairro}`)))).addTo(map);map.invalidateSize();if(result.points.length)map.fitBounds(layer.getBounds(),{padding:[20,20],maxZoom:17});else map.setView([-14,-51],4);}else $('map').textContent='Mapa indisponível. A tabela e a contagem permanecem disponíveis.';
    $('totals').replaceChildren();result.groups.forEach(g=>{const text=Object.entries(g.totals).map(([k,v])=>`${result.columns.find(c=>c.id===k)?.label||k}: ${v.toLocaleString('pt-BR')}`).join(' · ');$('totals').append(node('p',`${g.label}: ${g.count} registros${text?' · Somas: '+text:''}`));});
  }
  async function run(){const revision=editVersion;const received=await api(`${base}/executar`,definition());if(revision!==editVersion){message('Os critérios mudaram durante a consulta. Execute novamente.');return;}result=received;draw();message('Consulta concluída.');}
  $('run').onclick=()=>task(run);$('prev').onclick=()=>{page--;table();};$('next').onclick=()=>{page++;table();};
  function download(format){return task(async()=>{const blob=await api(`${base}/exportar/${format}`,definition(),'POST',true),url=URL.createObjectURL(blob),a=node('a');a.href=url;a.download=format==='pdf'?'consulta.pdf':'consulta.xlsx';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);message('Arquivo gerado com os critérios atuais.');},'Gerando arquivo… Aguarde.');}
  $('pdf').onclick=()=>download('pdf');$('excel').onclick=()=>download('excel');$('print').onclick=()=>{if(result){table(true);window.print();table();}};
  $('email').onclick=()=>task(async()=>{
    $('open-email').removeAttribute('href');
    const direct=$('email').dataset.directSend==='true';
    const spec=definition(), city=spec.filters.prefeitura;
    if(!city)throw new Error('Selecione uma prefeitura nos filtros para enviar o relatório.');
    const destination=await api(`${base}/email-destino?prefeitura_id=${encodeURIComponent(city)}`,undefined,'GET');
    $('recipient').value=destination.destinatario;
    const explanation=direct?'O sistema gerará e enviará o PDF ao destinatário cadastrado.':'O PDF será baixado. Depois, abra a mensagem, anexe o PDF baixado e envie pelo seu aplicativo de e-mail.';
    if(!await confirm(direct?'Enviar relatório por e-mail':'Preparar e-mail',`Prefeitura: ${destination.prefeitura}. ${explanation}`,true)){message('Operação cancelada.');return;}
    if(!direct){
      message('Gerando PDF para anexar ao e-mail…');
      const blob=await api(`${base}/exportar/pdf`,spec,'POST',true),url=URL.createObjectURL(blob),a=node('a');
      if(preparedEmailUrl)URL.revokeObjectURL(preparedEmailUrl);preparedEmailUrl=url;
      a.href=url;a.download='consulta.pdf';document.body.append(a);a.click();a.remove();
      $('email-download').href=url;
      const subject=`IJA System — consulta personalizada — ${destination.prefeitura}`;
      const body=`Olá,\r\n\r\nEncaminho o relatório da consulta personalizada de ${destination.prefeitura}, gerado no IJA System.\r\n\r\n[Anexe o arquivo consulta.pdf baixado e remova este lembrete antes de enviar.]`;
      $('open-email').href=`mailto:${encodeURIComponent(destination.destinatario)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
      $('outlook-web').href=`https://outlook.office.com/mail/deeplink/compose?to=${encodeURIComponent(destination.destinatario)}&subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
      $('ready-recipient').textContent=destination.destinatario;
      $('email-ready').showModal();$('open-email').focus();
      message('Download do PDF solicitado. Clique em Abrir aplicativo de e-mail, anexe o arquivo consulta.pdf e envie. O sistema ainda não enviou nenhum e-mail.');
      return;
    }
    message('Gerando e enviando o PDF… Não repita o envio enquanto aguarda.');
    const response=await api(`${base}/email`,{...destination,envio_id:crypto.randomUUID(),definicao:spec});
    message(response.message);
  },'Consultando destinatário da prefeitura…');
  $('email-ready-close').onclick=()=>$('email-ready').close();
  $('open-email').onclick=()=>{ $('email-launch-help').textContent='A abertura foi solicitada ao navegador. Se aparecer uma confirmação, permita abrir seu aplicativo de e-mail. Anexe consulta.pdf antes de enviar. Se nada abrir, use o Outlook manualmente com o destinatário acima.'; };
  window.addEventListener('unload',()=>{if(preparedEmailUrl)URL.revokeObjectURL(preparedEmailUrl);});
  $('add-condition').onclick=()=>addRule('conditions');$('add-exclusion').onclick=()=>addRule('exclusions');$('add-formula').onclick=()=>addFormula();
  document.getElementById('consultas-app').addEventListener('input',e=>{if(!['cq-recipient','cq-name','cq-auto'].includes(e.target.id)){editVersion++;if(result){$('print').disabled=true;message('Critérios alterados. Execute novamente para atualizar o resultado exibido.');}}});
  setInterval(()=>{if($('auto').checked&&!document.hidden&&!busy)task(run);},30000);
  drawFields();task(refreshCatalog,'Carregando catálogo…').then(()=>{if(!$('message').classList.contains('cq-error'))message('Pronto para consultar.');});
})();
