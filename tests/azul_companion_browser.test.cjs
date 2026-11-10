const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/azul-companion.js', 'utf8');
class Element {
  constructor() { this.children=[]; this.dataset={}; this.events={}; this.hidden=false; this.textContent=''; this.classList={add(){},remove(){}}; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children=items; }
  addEventListener(name, fn) { this.events[name]=fn; }
  setAttribute(name, value) { this[name]=value; }
  focus() {}
  getClientRects() { return [1]; }
}
function setup(fetcher, audioSupported=true, guideSteps=null) {
  const root=new Element();root.dataset.csrf='csrf-test';
  const keys=['.azul-panel','[data-guide]','[data-voice-status]','[data-guide-config]',
    '[data-guide-progress]','[data-guide-title]','[data-guide-body]','[data-guide-prev]',
    '[data-guide-next]','[data-guide-links]','[data-guide-audio]','[data-guide-question]','[data-guide-close]'];
  const parts=Object.fromEntries(keys.map(key=>[key,new Element()]));
  const offer={url:'/api/azul/voz',token:'signed-server-text'};
  parts['[data-guide]'].hidden=true;
  parts['[data-guide-config]'].textContent=JSON.stringify(guideSteps || [
    {title:'Comece',body:'Escolha um recurso.',links:[{label:'Permitido',url:'/admin'},{label:'Inválido',url:'//evil.test'}],speech:offer,question:'Meus acessos?',intent:'access_overview'},
    {title:'Continue',body:'Confira os detalhes.',links:[],speech:{...offer,token:'another-step'}}
  ]);
  const opener=new Element(),sent=[],requests=[],revoked=[];
  root.querySelector=selector=>parts[selector];
  root.querySelectorAll=selector=>selector==='[data-guide-open]'?[opener]:[];
  root.dispatchEvent=event=>{sent.push(event);root.events[event.type]?.(event);};
  const audioInstances=[];
  class Audio {
    constructor(url) { this.src=url;this.paused=false;audioInstances.push(this); }
    async play() { this.onplaying?.(); }
    pause() { this.paused=true; }
  }
  const context={
    document:{querySelectorAll:selector=>selector==='[data-azul-help]'?[root]:[],createElement:()=>new Element(),addEventListener(){}},
    window:{location:{origin:'https://system.test'},addEventListener(){}},
    URL:class extends URL {static createObjectURL(){return 'blob:audio-'+requests.length;}static revokeObjectURL(url){revoked.push(url);}},
    Audio:audioSupported?Audio:undefined,AbortController,setTimeout,clearTimeout,
    CustomEvent:class {constructor(type,options={}){this.type=type;this.detail=options.detail;}},
    fetch:async(url,options)=>{requests.push({url,...options});return fetcher(url,options);}
  };
  vm.runInNewContext(source,context);
  const bubble=new Element();root.azulCompanion.attachSpeech(bubble,offer);
  return {root,parts,opener,sent,requests,revoked,audioInstances,button:bubble.children[0]};
}
const audioResponse=()=>({ok:true,headers:{get:()=> 'audio/wav'},blob:async()=>({size:120})});

test('no audio is requested automatically; explicit playback animates and can replay from memory',async()=>{
  const env=setup(async()=>audioResponse());
  assert.equal(env.requests.length,0);
  await env.button.events.click();
  assert.equal(env.root.dataset.droneState,'speak');
  assert.equal(env.button.textContent,'Parar áudio');
  assert.equal(env.requests[0].headers['X-CSRFToken'],'csrf-test');
  assert.deepEqual(JSON.parse(env.requests[0].body),{token:'signed-server-text'});
  await env.button.events.click();
  assert.equal(env.audioInstances[0].paused,true);
  assert.equal(env.root.dataset.droneState,'idle');
  await env.button.events.click();
  assert.equal(env.requests.length,1);
  env.root.azulCompanion.clear();
  assert.ok(env.revoked.includes('blob:audio-1'));
});

test('clearing while generation is pending aborts it and prevents late playback',async()=>{
  let resolve;
  const env=setup(()=>new Promise(done=>{resolve=done;}));
  const pending=env.button.events.click();
  assert.equal(env.root.dataset.droneState,'think');
  env.root.azulCompanion.clear();
  assert.equal(env.requests[0].signal.aborted,true);
  resolve(audioResponse());
  await pending;
  assert.equal(env.audioInstances.length,0);
  assert.equal(env.root.dataset.droneState,'idle');
});

test('guide navigation stops narration and questions retain the explicit intent',async()=>{
  const env=setup(async()=>audioResponse());
  env.opener.events.click();
  assert.equal(env.parts['[data-guide]'].hidden,false);
  assert.equal(env.parts['[data-guide-progress]'].textContent,'1 de 2');
  assert.equal(env.parts['[data-guide-links]'].children.length,1);
  await env.parts['[data-guide-audio]'].children[0].events.click();
  env.parts['[data-guide-next]'].events.click();
  assert.equal(env.audioInstances[0].paused,true);
  assert.equal(env.parts['[data-guide-progress]'].textContent,'2 de 2');
  env.parts['[data-guide-prev]'].events.click();
  env.parts['[data-guide-question]'].events.click();
  assert.equal(env.parts['[data-guide]'].hidden,true);
  const request=env.sent.find(event=>event.type==='azul:ask');
  assert.equal(request.detail.message,'Meus acessos?');
  assert.equal(request.detail.intent,'access_overview');
});

test('guide links preserve form anchors and mobile routes while rejecting external URLs',()=>{
  const env=setup(async()=>audioResponse(),true,[{
    title:'Caminhos do cidadão',body:'Escolha o formulário.',links:[
      {label:'Foco no aplicativo',url:'/m/?preview=1#relatar-foco'},
      {label:'Saúde no aplicativo',url:'/m/#caso-suspeito'},
      {label:'Relato no portal',url:'/portal-cidadao#portal-relato'},
      {label:'Externo',url:'https://evil.test/'},
      {label:'Protocolo relativo',url:'//evil.test/'},
      {label:'Barra invertida',url:'/\\evil.test/'}
    ]
  }]);
  env.opener.events.click();
  assert.deepEqual(env.parts['[data-guide-links]'].children.map(link=>link.href),[
    '/m/?preview=1#relatar-foco','/m/#caso-suspeito','/portal-cidadao#portal-relato'
  ]);
});

test('completing the guide returns to the conversation and reopening starts at the first step',()=>{
  const env=setup(async()=>audioResponse());
  env.opener.events.click();
  assert.equal(env.parts['[data-guide-prev]'].disabled,true);
  env.parts['[data-guide-next]'].events.click();
  assert.equal(env.parts['[data-guide-next]'].textContent,'Concluir');
  env.parts['[data-guide-next]'].events.click();
  assert.equal(env.parts['[data-guide]'].hidden,true);
  assert.equal(env.root.dataset.guideOpen,undefined);
  env.opener.events.click();
  assert.equal(env.parts['[data-guide-progress]'].textContent,'1 de 2');
  env.parts['[data-guide-close]'].events.click();
  assert.equal(env.parts['[data-guide]'].hidden,true);
});

test('revoked access ends narration instead of playing an error response',async()=>{
  const env=setup(async()=>({ok:false,status:409,json:async()=>({code:'access_changed'})}));
  env.root.events['azul:access-changed']=()=>env.root.azulCompanion.clear();
  await env.button.events.click();
  assert.equal(env.audioInstances.length,0);
  assert.equal(env.root.dataset.droneState,'idle');
  assert.ok(env.sent.some(event=>event.type==='azul:access-changed'));
});

test('unsupported audio leaves the guide and text controls usable',()=>{
  const env=setup(async()=>audioResponse(),false);
  assert.equal(env.button,undefined);
  env.opener.events.click();
  assert.equal(env.parts['[data-guide]'].hidden,false);
  env.parts['[data-guide-next]'].events.click();
  assert.equal(env.parts['[data-guide-progress]'].textContent,'2 de 2');
});
