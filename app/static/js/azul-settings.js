(() => {
  const root=document.querySelector('[data-azul-management]'); if(!root)return;
  const form=root.querySelector('[data-management-form]'),save=root.querySelector('[data-save]'),status=root.querySelector('[data-save-status]');
  let current=JSON.parse(root.querySelector('[data-initial-settings]').textContent),dirty=false;
  const tabs=[...root.querySelectorAll('[data-tab]')];
  function show(name){for(const tab of tabs){const selected=tab.dataset.tab===name;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;}for(const panel of root.querySelectorAll('[data-panel]'))panel.hidden=panel.dataset.panel!==name;}
  for(const tab of tabs){tab.addEventListener('click',()=>show(tab.dataset.tab));tab.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key))return;event.preventDefault();const i=tabs.indexOf(tab),next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(i+(['ArrowLeft','ArrowUp'].includes(event.key)?-1:1)+tabs.length)%tabs.length;show(tabs[next].dataset.tab);tabs[next].focus();});}
  const date=value=>value?new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeStyle:'short',timeZone:'America/Sao_Paulo'}).format(new Date(value*1000)):'—';
  const money=value=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL',minimumFractionDigits:4,maximumFractionDigits:4}).format(Number(value||0)/1e9);
  const integer=value=>new Intl.NumberFormat('pt-BR').format(value||0);
  for(const time of root.querySelectorAll('[data-timestamp]'))time.textContent=date(Number(time.dataset.timestamp));
  form.addEventListener('input',event=>{if(!event.target.matches('[data-setting],[data-rate-model]'))return;dirty=true;status.textContent='Alterações ainda não salvas.';delete status.dataset.error;});
  function payload(){const cfg={};for(const input of root.querySelectorAll('[data-setting]')){cfg[input.dataset.setting]=input.type==='checkbox'?input.checked:input.type==='number'&&input.step==='1'?Number(input.value):input.value;}cfg.rates={};for(const input of root.querySelectorAll('[data-rate-model]')){(cfg.rates[input.dataset.rateModel]||={})[input.dataset.rateKey]=input.value;}return cfg;}
  form.addEventListener('submit',async event=>{
    event.preventDefault();const invalid=[...form.querySelectorAll('input,textarea,select')].find(input=>!input.checkValidity());
    if(invalid){show(invalid.closest('[data-panel]').dataset.panel);invalid.reportValidity();return;}
    save.disabled=true;status.textContent='Salvando…';delete status.dataset.error;
    try{const response=await fetch(root.dataset.configUrl,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':root.dataset.csrf,'X-Azul-Config-CSRF':root.dataset.configCsrf},body:JSON.stringify({revision:current.revision,settings:payload()})});const data=await response.json();if(!response.ok)throw new Error(data.error||'Não foi possível salvar.');current=data.settings;dirty=false;status.textContent='Configurações salvas · versão '+current.revision+'.';window.dispatchEvent(new CustomEvent('azul:policy-refresh'));}
    catch(error){status.textContent=error.message==='Failed to fetch'?'Falha de conexão. Suas alterações continuam no formulário.':error.message;status.dataset.error='true';}
    finally{save.disabled=false;}
  });
  function rows(target,items,columns){const body=root.querySelector(target);body.replaceChildren();if(!items.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=columns.length;td.textContent='Nenhum evento registrado neste período.';tr.append(td);body.append(tr);return;}for(const item of items){const tr=document.createElement('tr');for(const fn of columns){const td=document.createElement('td');td.textContent=fn(item);tr.append(td);}body.append(tr);}}
  const operations={text:'Resposta de texto',voice:'Voz',transcription:'Transcrição'},sources={ai:'IA',local:'Resposta local',blocked:'Fora do escopo',recorded:'Gravação pronta',cache:'Áudio reutilizado'},states={pending:'Em andamento',unknown:'Sem consumo informado',complete:'Concluída',failed:'Falhou'};
  let version=0;
  async function usage(){const expected=++version,out=root.querySelector('[data-usage-status]');out.textContent='Atualizando…';delete out.dataset.error;try{const url=new URL(root.dataset.usageUrl,location.origin);url.searchParams.set('days',root.querySelector('[data-usage-days]').value);url.searchParams.set('channel',root.querySelector('[data-usage-channel]').value);const response=await fetch(url,{credentials:'same-origin',cache:'no-store'});const data=await response.json();if(!response.ok)throw new Error(data.error||'Não foi possível consultar o consumo.');if(expected!==version)return;root.querySelector('[data-kpi=cost]').textContent=money(data.totals.cost_brl);root.querySelector('[data-kpi=tokens]').textContent=integer(data.totals.tokens);root.querySelector('[data-kpi=conversations]').textContent=integer(data.totals.conversations);root.querySelector('[data-kpi=unknown]').textContent=integer(data.totals.unknown);root.querySelector('[data-kpi=reserved]').textContent=money(data.totals.reserved_brl)+' em reservas/sem medição';
    rows('[data-usage-groups]',data.groups,[x=>operations[x.operation]||x.operation,x=>sources[x.source]||x.source,x=>integer(x.count),x=>integer(x.tokens),x=>money(x.cost_brl)]);
    rows('[data-usage-conversations]',data.conversations,[x=>x.conversation.slice(0,10),x=>x.channel==='public'?'Público':'Interno',x=>date(x.last_at),x=>integer(x.tokens),x=>money(x.cost_brl)+(x.unknown?' + sem medição':'')]);
    rows('[data-usage-recent]',data.recent,[x=>date(x.created_at),x=>(operations[x.operation]||x.operation)+(x.model?' · '+x.model:''),x=>states[x.status]||x.status,x=>integer(x.total_tokens)+(x.audio_seconds?' · '+Number(x.audio_seconds).toFixed(1)+' s':''),x=>x.cost_brl===null?'Sem medição':money(x.cost_brl)]);
    out.textContent=data.first_event_at?'Primeiro evento registrado: '+date(data.first_event_at)+'.':'O consumo aparecerá após as primeiras interações com a AZUL.';
  }catch(error){if(expected!==version)return;out.textContent=error.message;out.dataset.error='true';}}
  for(const input of root.querySelectorAll('[data-usage-days],[data-usage-channel]'))input.addEventListener('change',usage);
  root.querySelector('[data-refresh-usage]').addEventListener('click',usage);usage();
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
})();
