const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app/static/js/edit-control.js'), 'utf8');

function browser() {
  let clock = 100000;
  const requests = [], intervals = [], replies = [];
  function element(extra = {}) {
    return {disabled:false,hidden:false,value:'',textContent:'',events:{},classList:{toggle(){}},
      addEventListener(name, fn){this.events[name]=fn;},scrollIntoView(){},
      async fire(name, event={}){return this.events[name]?.(event);}, ...extra};
  }
  const items = Object.fromEntries(['.edit-start','.edit-cancel','.edit-reload','.edit-dev','.edit-message','.edit-force','.edit-reason',
    '[name="_edit_ticket"]','[name="_edit_token"]'].map(key=>[key,element()]));
  items['[name="_edit_ticket"]'].value='signed-ticket';
  const input=element(), fixed=element({disabled:true}), submit=element();
  const form=element({action:'https://ija.test/admin/os/1/formulario',dataset:{},querySelectorAll:()=>[input,fixed,submit]});
  const box=element({dataset:{editKey:'solicitacao:1',editApi:'/api/edicao'},closest:()=>form,
    contains:el=>Object.values(items).includes(el),querySelector:selector=>items[selector]});
  class XHR {open(){}send(){}setRequestHeader(){}addEventListener(){}}
  const context={console,URL,Headers,Request,XMLHttpRequest:XHR,Date:class extends Date{static now(){return clock;}},
    location:{href:form.action,origin:'https://ija.test',reload(){}},confirm:()=>true,
    document:{readyState:'complete',hidden:false,querySelectorAll:()=>[box]},setInterval:fn=>intervals.push(fn),
    fetch:async(url,options)=>{
      requests.push({url,options});const reply=replies.shift()||{ok:true,token:'lease-token',expires:new Date(clock+120000).toISOString()};
      return {ok:reply.ok!==false,status:reply.status||200,json:async()=>reply,
        headers:new Headers(reply.headers||{})};
    }};
  context.window=context;vm.runInNewContext(source,context);
  return {items,input,fixed,submit,form,context,requests,replies,intervals,tick:ms=>{clock+=ms;}};
}

test('consultation locks inputs, reservation enables only originally editable controls',async()=>{
  const b=browser();assert(b.input.disabled);assert(b.submit.disabled);
  await b.items['.edit-start'].fire('click');
  assert.equal(b.input.disabled,false);assert.equal(b.fixed.disabled,true);
  assert.equal(b.items['[name="_edit_token"]'].value,'lease-token');
  assert.match(b.items['.edit-message'].textContent,/Você está editando/);
});

test('busy message remains visible and DEV can see explicit release controls',async()=>{
  const b=browser();b.replies.push({ok:false,status:409,code:'busy',error:'Maria está editando este registro.'});
  await b.items['.edit-start'].fire('click');
  assert(b.input.disabled);assert.equal(b.items['.edit-message'].textContent,'Maria está editando este registro.');
  assert.equal(b.items['.edit-dev'].hidden,false);assert.equal(b.items['.edit-start'].textContent,'Tentar novamente');
});

test('idle or hidden tabs do not renew; expiry blocks submission without erasing values',async()=>{
  const b=browser();await b.items['.edit-start'].fire('click');b.input.value='texto ainda não salvo';
  b.tick(95000);await b.intervals[0]();assert.equal(b.requests.length,1);
  b.tick(30000);await b.intervals[0]();assert(b.input.disabled);assert.equal(b.input.value,'texto ainda não salvo');
  let stopped=false;await b.form.fire('submit',{preventDefault(){stopped=true;},stopImmediatePropagation(){}});
  assert(stopped);assert.match(b.items['.edit-message'].textContent,/reserva expirou/);
});

test('network failure pauses editing and never extends an unconfirmed lease',async()=>{
  const b=browser();await b.items['.edit-start'].fire('click');
  b.replies.push({ok:false,status:503,error:'Sem conexão.'});await b.intervals[0]();
  assert(b.input.disabled);assert.equal(b.items['.edit-message'].textContent,'Sem conexão.');
});

test('lease headers stay on same-origin OS operations and newer snapshots win',async()=>{
  const b=browser();await b.items['.edit-start'].fire('click');
  b.replies.push({headers:{'X-Edit-Ticket':'new','X-Edit-Versions':'1,3,0'}});
  await b.context.fetch('/api/os/1/upload-stream',{method:'PUT'});
  assert.equal(b.requests.at(-1).options.headers.get('X-Edit-Token'),'lease-token');
  assert.equal(b.items['[name="_edit_ticket"]'].value,'new');
  b.replies.push({headers:{'X-Edit-Ticket':'old','X-Edit-Versions':'1,2,0'}});
  await b.context.fetch('/api/os/1/upload-stream',{method:'PUT'});
  assert.equal(b.items['[name="_edit_ticket"]'].value,'new');
  await b.context.fetch('https://external.test/api/os/1/upload-stream',{method:'PUT'});
  assert.equal(b.requests.at(-1).options.headers,undefined);
});

test('successful save releases editing and requires refreshed data',async()=>{
  const b=browser();await b.items['.edit-start'].fire('click');
  b.replies.push({headers:{'X-Edit-Ticket':'saved','X-Edit-Versions':'2,0,0','X-Edit-Released':'1'}});
  await b.context.fetch(b.form.action,{method:'POST'});
  assert(b.input.disabled);assert.equal(b.items['[name="_edit_token"]'].value,'');
  assert.match(b.items['.edit-message'].textContent,/Alterações salvas/);
});

test('exempt profile unlocks an old form without renewing or sending lease headers',async()=>{
  const b=browser();b.input.value='dados preenchidos';
  b.replies.push({ok:true,required:false,token:'direct-edit',expires:new Date(100000+86400000).toISOString()});
  await b.items['.edit-start'].fire('click');
  assert.equal(b.input.disabled,false);assert.equal(b.fixed.disabled,true);
  assert.equal(b.input.value,'dados preenchidos');
  assert.equal(b.items['[name="_edit_token"]'].value,'');
  b.tick(2*86400000);await b.intervals[0]();assert.equal(b.requests.length,1);
  let blocked=false;
  await b.form.fire('submit',{preventDefault(){blocked=true;},stopImmediatePropagation(){}});
  assert.equal(blocked,false);
  await b.context.fetch('/api/os/1/upload-stream',{method:'PUT'});
  assert.equal(b.requests.at(-1).options.headers,undefined);
});

test('renewal discovers exemption and preserves unsaved fields',async()=>{
  const b=browser();await b.items['.edit-start'].fire('click');b.input.value='em andamento';
  b.replies.push({ok:true,required:false,token:'direct-edit',expires:new Date(100000+86400000).toISOString()});
  await b.intervals[0]();assert.equal(b.input.disabled,false);assert.equal(b.input.value,'em andamento');
  assert.equal(b.items['[name="_edit_ticket"]'].value,'');
  await b.intervals[0]();assert.equal(b.requests.length,2);
});
