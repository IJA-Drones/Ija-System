const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/azul-help.js', 'utf8');
class Element {
  dispatchEvent(event) { return this.events[event.type]?.(event); }
  constructor() {this.children=[]; this.dataset={}; this.events={}; this.value=''; this.hidden=true;}
  set innerHTML(value) {throw new Error('Unsafe HTML');}
  set textContent(value) {this.text=value;}
  append(...values) {this.children.push(...values);}
  replaceChildren() {this.children=[];}
  addEventListener(name, fn) {this.events[name]=fn;}
  setAttribute(name,value) {this[name]=value;}
  focus() {}
}
function setup(fetcher, storage, chatKey, page = false) {
  const root=new Element(); root.dataset={url:'/api/azul/ajuda',page:'/admin',csrf:'token',chatKey};
  const parts=Object.fromEntries(['.azul-panel','[data-toggle]','[data-messages]','form','input','[data-status]','[data-profile]','[data-clear]','[data-close]'].map(key=>[key,new Element()]));
  if (page) {
    root.dataset.view='page';
    parts.textarea = new Element();
    parts['[data-stop]'] = new Element();
    parts['[data-count]'] = new Element();
    parts['[data-toggle]'] = null;
    parts['[data-close]'] = null;
    parts['.azul-panel'].hidden = false;
  }
  const copied=[];
  const send=new Element(); const chip=new Element();chip.dataset.question='Meus acessos?';
  parts.form.querySelector=()=>send;
  root.querySelector=key=>parts[key];root.querySelectorAll=()=>[chip];
  const requests=[];
  vm.runInNewContext(source,{document:{querySelectorAll:()=>[root],createElement:()=>new Element()},
    navigator:{clipboard:{writeText:async text=>copied.push(text)}},sessionStorage:storage,window:{location:{origin:'http://localhost:5002'}},URL,AbortController,setTimeout,clearTimeout,
    CustomEvent:class{constructor(type,options={}){this.type=type;this.detail=options.detail;}},
    fetch:async(url,options)=>{requests.push(options);return fetcher(url,options);}});
  return {root,parts,send,chip,requests,copied};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));

test('renders model text literally, filters unsafe links, sends CSRF and bounded history', async()=>{
  const env=setup(async()=>({ok:true,json:async()=>({answer:'<img src=x onerror=alert(1)>',mode:'ia',profile:'dev',links:[
    {label:'Allowed',url:'/admin'}, {label:'Bad',url:'javascript:alert(1)'},{label:'Bad',url:'//evil.com'}, {label:'Bad',url:'/\\evil.com'}]})}));
  await env.chip.events.click(); await settle();
  const bubble=env.parts['[data-messages]'].children.at(-1);
  assert.equal(bubble.children[1].text,'<img src=x onerror=alert(1)>');
  assert.equal(bubble.children[2].children.length,1);
  assert.equal(bubble.children[2].children[0].href,'/admin');
  assert.equal(env.requests[0].headers['X-CSRFToken'],'token');
  assert.equal(JSON.parse(env.requests[0].body).page,'/admin');
  for(let i=0;i<8;i++){await env.chip.events.click();await settle();}
  assert.equal(JSON.parse(env.requests.at(-1).body).history.length,12);
});

test('clearing in flight discards stale replies and double submits',async()=>{
  let resolve;
  const env=setup(()=>new Promise(done=>{resolve=done;}));
  env.chip.events.click();env.chip.events.click();
  assert.equal(env.requests.length,1);
  env.parts['[data-clear]'].events.click();
  assert.equal(env.requests[0].signal.aborted,true);
  resolve({ok:true,json:async()=>({answer:'stale',mode:'ia'})});
  await settle();
  assert.equal(env.parts['[data-messages]'].children.length,1);
  assert.equal(env.send.disabled,false);
});

test('HTTP failures restore composer and show a safe error',async()=>{
  const env=setup(async()=>({ok:false,json:async()=>({answer:'Acesso negado.'})}));
  await env.chip.events.click();await settle();
  assert.equal(env.send.disabled,false);
  assert.equal(env.parts['[data-messages]'].children.at(-1).children[1].text,'Acesso negado.');
});

test('export preview requires a separate confirmation request',async()=>{
  const preview={title:'Solicitações municipais',format:'excel',total:2,filters:{Período:'2026'},columns:['Solicitação'],notice:'Confira.',token:'signed',url:'/api/azul/exportar'};
  const env=setup(async(url)=>url==='/api/azul/exportar'
    ? {ok:false,json:async()=>({error:'Os dados mudaram. Peça nova prévia.'})}
    : {ok:true,json:async()=>({answer:'Confira',mode:'ia',links:[],export_preview:preview})});
  await env.chip.events.click();await settle();
  assert.equal(env.requests.length,1);
  const card=env.parts['[data-messages]'].children.at(-1).children.at(-1);
  const confirm=card.children.find(child=>child.text==='Confirmar e baixar');
  assert.ok(confirm);
  await confirm.events.click();await settle();
  assert.equal(env.requests.length,2);
  assert.deepEqual(JSON.parse(env.requests[1].body),{token:'signed',confirm:true});
  assert.equal(card.children.at(-1).text,'Os dados mudaram. Peça nova prévia.');
});

test('canceling a preview does not generate a file',async()=>{
  const env=setup(async()=>({ok:true,json:async()=>({answer:'Confira',mode:'ia',links:[],export_preview:{title:'OS',format:'pdf',total:1,filters:{},columns:[],notice:'',token:'signed',url:'/api/azul/exportar'}})}));
  await env.chip.events.click();await settle();
  const card=env.parts['[data-messages]'].children.at(-1).children.at(-1);
  card.children.find(child=>child.text==='Cancelar').events.click();
  assert.equal(env.requests.length,1);
  assert.equal(card.text,'Geração cancelada.');
});

test('starting a report clears previous report choices from sent history', async()=>{
  const env=setup(async()=>({ok:true,json:async()=>({answer:'Qual relatório e quais filtros?',mode:'guided',links:[]})}));
  await env.chip.events.click();await settle();
  env.chip.dataset.intent='start_report';
  env.chip.dataset.question='Quero gerar um relatório.';
  await env.chip.events.click();await settle();
  const start=JSON.parse(env.requests.at(-1).body);
  assert.equal(start.intent,'start_report');
  assert.deepEqual(start.history,[]);
  env.parts.input.value='Solicitações, Excel, todo o período, todos os bairros e status';
  env.parts.form.events.submit({preventDefault(){}});await settle();
  const followup=JSON.parse(env.requests.at(-1).body);
  assert.equal(followup.history.length,2);
  assert.equal(followup.history[0].content,'Quero gerar um relatório.');
  assert.equal(followup.intent,undefined);
});

function memoryStorage() {
  const values=new Map();
  return {get length(){return values.size;},key:index=>[...values.keys()][index],getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};
}

test('report choices given separately survive the final answer and navigation',async()=>{
  const storage=memoryStorage();
  const fetcher=async()=>({ok:true,json:async()=>({answer:'Qual a próxima escolha?',mode:'guided',links:[]})});
  const env=setup(fetcher,storage,'report-session',true);
  env.chip.dataset.intent='start_report';
  env.chip.dataset.question='Quero gerar um relatório.';
  await env.chip.events.click();await settle();
  const choices=['OS municipais','Excel','Outubro de 2026','Centro','Todos os status'];
  for(const choice of choices) {
    env.parts.textarea.value=choice;
    env.parts.form.events.submit({preventDefault(){}});await settle();
  }
  const last=JSON.parse(env.requests.at(-1).body);
  assert.equal(last.message,'Todos os status');
  assert.deepEqual(last.history.filter(item=>item.role==='user').map(item=>item.content),
    ['Quero gerar um relatório.',...choices.slice(0,-1)]);
  const restored=setup(fetcher,storage,'report-session');
  restored.parts.input.value='Pode preparar a prévia.';
  restored.parts.form.events.submit({preventDefault(){}});await settle();
  assert.deepEqual(JSON.parse(restored.requests[0].body).history.filter(item=>item.role==='user').map(item=>item.content),
    ['Quero gerar um relatório.',...choices]);
});

test('long exchanges are trimmed within a total budget without orphan replies',async()=>{
  const storage=memoryStorage();
  const fetcher=async()=>({ok:true,json:async()=>({answer:'ç'.repeat(3000),mode:'ia',links:[]})});
  const env=setup(fetcher,storage,'bounded-session');
  for(let index=0;index<8;index++) {
    env.parts.input.value=String(index)+('ã'.repeat(1499));
    env.parts.form.events.submit({preventDefault(){}});await settle();
  }
  const restored=setup(fetcher,storage,'bounded-session',true);
  await restored.chip.events.click();await settle();
  const history=JSON.parse(restored.requests[0].body).history;
  assert.ok(history.length<=12);
  assert.ok(history.reduce((total,item)=>total+item.content.length,0)<=18000);
  assert.equal(history[0].role,'user');
  assert.equal(history.at(-1).role,'assistant');
  assert.equal(history.at(-2).content[0],'7');
});

test('follow-up report format changes retain preview filters without its token',async()=>{
  const storage=memoryStorage();
  const summary='Prévia de OS municipais em Excel.\nPeríodo: 01/10/2026 até 31/10/2026\nBairro: Centro\nStatus da solicitação: Todos';
  const env=setup(async()=>({ok:true,json:async()=>({answer:summary,mode:'ia',export_preview:{
    title:'OS municipais',format:'excel',total:1,filters:{Bairro:'Centro'},columns:[],notice:'',
    token:'secret-preview-token',url:'/api/azul/exportar'}})}),storage,'preview-session');
  await env.chip.events.click();await settle();
  env.parts.input.value='Agora o mesmo em PDF';
  env.parts.form.events.submit({preventDefault(){}});await settle();
  const followup=JSON.parse(env.requests.at(-1).body);
  assert.equal(followup.history.at(-1).content,summary);
  assert.ok(!env.requests.at(-1).body.includes('secret-preview-token'));
  assert.ok(!storage.getItem('azul-chat:preview-session').includes('secret-preview-token'));
  const restored=setup(()=>{throw Error('Must not request');},storage,'preview-session',true);
  assert.ok(restored.parts['[data-messages]'].children.some(bubble=>bubble.children[1]?.text.includes(summary)));
  assert.ok(restored.parts['[data-messages]'].children.every(bubble=>bubble.children.every(child=>child.className!=='azul-export')));
});

test('navigation restores messages, safe links, open state and conversation context',async()=>{
  const storage=memoryStorage();
  const first=setup(async()=>({ok:true,json:async()=>({answer:'38 solicitações',links:[{label:'Abrir lista',url:'/admin?bairro=Centro'}]})}),storage,'user-session');
  await first.chip.events.click();await settle();
  const second=setup(async()=>({ok:true,json:async()=>({answer:'Continuando'})}),storage,'user-session');
  assert.equal(second.parts['.azul-panel'].hidden,false);
  const restored=second.parts['[data-messages]'].children.at(-1);
  assert.equal(restored.children[1].text,'38 solicitações');
  assert.equal(restored.children[2].children[0].href,'/admin?bairro=Centro');
  await second.chip.events.click();await settle();
  assert.equal(JSON.parse(second.requests[0].body).history.length,2);
});

test('another login cannot restore messages and clearing survives reload',async()=>{
  const storage=memoryStorage();
  const fetcher=async()=>({ok:true,json:async()=>({answer:'Mensagem privada'})});
  const first=setup(fetcher,storage,'user-session');
  await first.chip.events.click();await settle();
  const other=setup(fetcher,storage,'other-session');
  assert.equal(other.parts['[data-messages]'].children.length,1);
  first.parts['[data-clear]'].events.click();
  const restored=setup(fetcher,storage,'user-session');
  assert.equal(restored.parts['[data-messages]'].children.length,1);
});

test('restoring a report never replays a confirmation token',async()=>{
  const storage=memoryStorage();
  const first=setup(async()=>({ok:true,json:async()=>({answer:'Confira',export_preview:{title:'OS',format:'pdf',total:1,filters:{},columns:[],notice:'',token:'private-signed-token',url:'/api/azul/exportar'}})}),storage,'session');
  await first.chip.events.click();await settle();
  assert.ok(!storage.getItem('azul-chat:session').includes('private-signed-token'));
  const restored=setup(()=>{throw Error('Must not request');},storage,'session');
  assert.equal(restored.requests.length,0);
  assert.match(restored.parts['[data-messages]'].children.at(-1).children[1].text,/nova prévia/);
});


test('page supports multiline entry, copy and a fresh conversation',async()=>{
  const env=setup(async()=>({ok:true,json:async()=>({answer:'Resposta da Azul',links:[]})}),memoryStorage(),'page-session',true);
  assert.equal(env.root.dataset.conversation,'0');
  env.parts.textarea.value='Primeira linha\nSegunda linha';
  env.parts.textarea.events.keydown({key:'Enter',shiftKey:true});
  assert.equal(env.requests.length,0);
  env.parts.textarea.events.keydown({key:'Enter',isComposing:true});
  assert.equal(env.requests.length,0);
  env.parts.textarea.events.keydown({key:'Enter',preventDefault(){}});
  await settle();
  assert.equal(JSON.parse(env.requests[0].body).message,'Primeira linha\nSegunda linha');
  assert.equal(env.root.dataset.conversation,'1');
  const bubble=env.parts['[data-messages]'].children.at(-1);
  await bubble.children.find(child=>child.className==='azul-copy').events.click();
  assert.deepEqual(env.copied,['Resposta da Azul']);
  env.parts['[data-clear]'].events.click();
  assert.equal(env.parts['[data-messages]'].children.length,0);
  assert.equal(env.root.dataset.conversation,'0');
});

test('page stop ignores late responses and allows another request',async()=>{
  let resolve;
  const env=setup(()=>new Promise(done=>{resolve=done;}),memoryStorage(),'page-session',true);
  env.chip.events.click();
  assert.equal(env.parts['[data-stop]'].hidden,false);
  env.parts['[data-stop]'].events.click();
  assert.equal(env.requests[0].signal.aborted,true);
  assert.equal(env.send.disabled,false);
  assert.equal(env.parts['[data-stop]'].hidden,true);
  resolve({ok:true,json:async()=>({answer:'Resposta antiga'})});
  await settle();
  assert.equal(env.parts['[data-messages]'].children.at(-1).children[1].text,'Resposta interrompida. Você pode enviar outra pergunta.');
  env.chip.events.click();
  assert.equal(env.requests.length,2);
  env.parts['[data-stop]'].events.click();
  resolve({ok:true,json:async()=>({answer:'Outra resposta antiga'})});
  await settle();
});

test('page continues a closed widget conversation and keeps it available to the widget',async()=>{
  const storage=memoryStorage();
  const fetcher=async()=>({ok:true,json:async()=>({answer:'Conversa compartilhada',links:[]})});
  const widget=setup(fetcher,storage,'shared');
  await widget.chip.events.click();await settle();
  widget.parts['[data-close]'].events.click();
  const page=setup(fetcher,storage,'shared',true);
  assert.equal(page.parts['.azul-panel'].hidden,false);
  assert.equal(page.root.dataset.conversation,'1');
  await page.chip.events.click();await settle();
  assert.equal(JSON.parse(page.requests[0].body).history.length,2);
  const restored=setup(fetcher,storage,'shared');
  assert.equal(restored.parts['[data-messages]'].children.length,5);
});


for (const status of [401,403,409]) {
  test(`access change (${status}) clears private transcript and disables stale page`,async()=>{
    const storage=memoryStorage();
    let changed=false;
    const env=setup(async()=>changed
      ? {ok:false,status,json:async()=>({code:status===409?'access_changed':undefined})}
      : {ok:true,json:async()=>({answer:'Dados privados anteriores'})},storage,'same-login',true);
    await env.chip.events.click();await settle();
    assert.ok(storage.getItem('azul-chat:same-login').includes('Dados privados anteriores'));
    changed=true;
    await env.chip.events.click();await settle();
    assert.equal(storage.getItem('azul-chat:same-login'),null);
    assert.equal(env.parts['[data-messages]'].children.length,1);
    assert.match(env.parts['[data-messages]'].children[0].children[1].text,/acesso ou sessão mudou/);
    assert.equal(env.parts.textarea.disabled,true);
    assert.equal(env.send.disabled,true);
    assert.equal(env.root.dataset.pending,'0');
    env.parts['[data-clear]'].events.click();
    await env.chip.events.click();await settle();
    assert.equal(env.requests.length,2);
  });
}

test('a new account or access scope removes prior chat storage in the tab',async()=>{
  const storage=memoryStorage();
  const fetcher=async()=>({ok:true,json:async()=>({answer:'Privado'})});
  const first=setup(fetcher,storage,'user1:session:old-scope');
  await first.chip.events.click();await settle();
  setup(fetcher,storage,'user1:session:new-scope',true);
  assert.equal(storage.getItem('azul-chat:user1:session:old-scope'),null);
});

test('access revoked during download clears the old preview and conversation',async()=>{
  const storage=memoryStorage();
  const preview={title:'OS',format:'pdf',total:1,filters:{},columns:[],notice:'',token:'signed',url:'/api/azul/exportar'};
  const env=setup(async url=>url==='/api/azul/exportar'
    ? {ok:false,status:409,json:async()=>({code:'access_changed',error:'Acesso mudou'})}
    : {ok:true,json:async()=>({answer:'Prévia privada',export_preview:preview})},storage,'old-scope',true);
  await env.chip.events.click();await settle();
  const card=env.parts['[data-messages]'].children.at(-1).children.at(-1);
  await card.children.find(child=>child.text==='Confirmar e baixar').events.click();await settle();
  assert.equal(storage.getItem('azul-chat:old-scope'),null);
  assert.equal(env.parts['[data-messages]'].children.length,1);
  assert.match(env.parts['[data-messages]'].children[0].children[1].text,/acesso ou sessão mudou/);
  assert.equal(env.send.disabled,true);
});
