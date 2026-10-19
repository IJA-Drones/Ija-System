/* Existing map companion: reads requests and explicitly linked returns only. */
(() => {
  const $=id=>document.getElementById(id);
  const labels={PENDENTE:'Pendente',ATRASADO:'Atrasado',CONCLUIDO:'Concluído / OS respondida',ENCERRADO:'Cancelado / reprovado'};
  let records=[], page=0, historySequence=0, controller;
  const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
  const dateText=value=>value ? value.slice(0,10).split('-').reverse().join('/')+(value.length>10?' '+value.slice(11,16):'') : 'Não informada';
  function close(){historySequence++;controller?.abort();$('mapFocusHistory')?.classList.add('d-none');$('mapHistoryBody')?.replaceChildren();}
  function table(){
    const tbody=$('mapRequestRows');if(!tbody)return;tbody.replaceChildren();
    for(const r of records.slice(page*50,(page+1)*50)){
      const tr=node('tr');
      for(const text of ['#'+r.id+(r.retorno?' · Retorno':''),dateText(r.data),r.foco+' / '+r.bairro,(labels[r.situacao]||r.situacao)+' · '+r.status,Number.isFinite(r.lat)&&Number.isFinite(r.lng)?'Sim':'Sem coordenadas válidas'])tr.append(node('td',text));
      const td=node('td'),button=node('button','Ver histórico','btn btn-outline-primary btn-sm');button.type='button';button.onclick=()=>history(r.id);td.append(button);tr.append(td);tbody.append(tr);
    }
    if(!records.length){const td=node('td','Nenhuma solicitação neste recorte.');td.colSpan=6;const tr=node('tr');tr.append(td);tbody.append(tr);}
    $('mapPrev').disabled=page===0;$('mapNext').disabled=(page+1)*50>=records.length;
    $('mapPageLabel').textContent=records.length?`Página ${page+1} de ${Math.ceil(records.length/50)} · ${records.length} ${records.length===1?'solicitação':'solicitações'}`:'';
  }
  function render(rows){
    records=rows;page=0;table();const target=$('mapOperationalSummary');if(!target)return;target.replaceChildren();
    const stats=[['Solicitações',rows.length],['Pendentes',rows.filter(r=>['PENDENTE','ATRASADO'].includes(r.situacao)).length],['Atrasadas',rows.filter(r=>r.situacao==='ATRASADO').length],['Retornos vinculados',rows.filter(r=>r.retorno).length],['Sem coordenadas válidas',rows.filter(r=>!Number.isFinite(r.lat)||!Number.isFinite(r.lng)).length]];
    for(const [label,value] of stats){const col=node('div',undefined,'col'),card=node('div',undefined,'card p-3 h-100');card.append(node('strong',value,'h4'),node('span',label,'small'));col.append(card);target.append(col);}
  }
  async function history(id){
    const own=++historySequence;controller?.abort();controller=new AbortController();
    const section=$('mapFocusHistory'),body=$('mapHistoryBody');section.classList.remove('d-none');body.replaceChildren(node('p','Carregando histórico…'));section.focus();section.scrollIntoView({behavior:'smooth',block:'start'});
    try{
      const response=await fetch(`/api/mapa-operacional/${encodeURIComponent(id)}/historico`,{signal:controller.signal});
      if(!response.ok){const error=await response.json().catch(()=>({}));throw Error(error.message||'Histórico indisponível para seu acesso.');}
      const data=await response.json();if(own!==historySequence)return;
      body.replaceChildren(node('p',data.criterio,'small text-muted'));
      for(const r of data.registros){
        const article=node('article',undefined,'border-top py-3');article.append(node('h4',`#${r.id} · ${dateText(r.data)}${r.retorno?' · Retorno':''}`,'h6'),node('p',`${r.foco} · ${r.endereco} · ${r.bairro}`),node('p',`${labels[r.situacao]||r.situacao} · Status: ${r.status}`));
        if(!r.ordens.length)article.append(node('p','Sem OS registrada.','small'));
        for(const os of r.ordens)article.append(node('p',`${os.origem} · OS ${os.identificador} · ${os.situacao} · Larvas: ${os.larvas} · Criadouro: ${os.criadouro} · Resposta: ${os.respondido_em?dateText(os.respondido_em):'Não registrada'}`,'small'));
        body.append(article);
      }
    }catch(error){if(own===historySequence&&error.name!=='AbortError')body.replaceChildren(node('p',error.message,'text-danger'));}
  }
  window.mapOperational={render,history,reset(){close();render([]);}};
  document.addEventListener('DOMContentLoaded',()=>{
    $('mapPrev').onclick=()=>{page=Math.max(0,page-1);table();};
    $('mapNext').onclick=()=>{if((page+1)*50<records.length)page++;table();};
    $('mapHistoryClose').onclick=close;
  });
})();
