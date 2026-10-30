const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/azul-help.js', 'utf8');
class Element {
  constructor() {this.children=[]; this.dataset={}; this.events={}; this.value=''; this.hidden=true;}
  set innerHTML(value) {throw new Error('Unsafe HTML');}
  set textContent(value) {this.text=value;}
  append(...values) {this.children.push(...values);}
  replaceChildren() {this.children=[];}
  addEventListener(name, fn) {this.events[name]=fn;}
  setAttribute(name,value) {this[name]=value;}
  focus() {}
}
function setup(fetcher, storage, chatKey) {
  const root=new Element(); root.dataset={url:'/api/azul/ajuda',page:'/admin',csrf:'token',chatKey};
  const parts=Object.fromEntries(['.azul-panel','[data-toggle]','[data-messages]','form','input','[data-status]','[data-profile]','[data-clear]','[data-close]'].map(key=>[key,new Element()]));
  const send=new Element(); const chip=new Element();chip.dataset.question='Meus acessos?';
  parts.form.querySelector=()=>send;
  root.querySelector=key=>parts[key];root.querySelectorAll=()=>[chip];
  const requests=[];
  vm.runInNewContext(source,{document:{querySelectorAll:()=>[root],createElement:()=>new Element()},
    sessionStorage:storage,window:{location:{origin:'http://localhost:5002'}},URL,AbortController,setTimeout,clearTimeout,
    fetch:async(url,options)=>{requests.push(options);return fetcher(url,options);}});
  return {root,parts,send,chip,requests};
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
  for(let i=0;i<5;i++){await env.chip.events.click();await settle();}
  assert.equal(JSON.parse(env.requests.at(-1).body).history.length,6);
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
  return {getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};
}

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
