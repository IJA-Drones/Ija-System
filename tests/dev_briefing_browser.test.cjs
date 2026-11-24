const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/dev-briefing.js','utf8');
class Element {
  constructor(){this.events={};this.dataset={};this.hidden=false;this.children=[];this.disabled=false;this.textContent='';}
  addEventListener(name,fn){this.events[name]=fn;}
  dispatchEvent(event){return this.events[event.type]?.(event);}
  append(...items){this.children.push(...items);}
  replaceChildren(){this.children=[];}
  focus(){}
  scrollIntoView(){}
}
function setup(fetcher,options={}){
  const ids=Object.fromEntries(['devBriefing','devBriefingListen','devBriefingRead','devBriefingStatus','devBriefingResult','devBriefingSpeech','devBriefingDismiss','devBriefingOpen'].map(id=>[id,new Element()]));
  ids.devBriefing.dataset={url:'/dev/briefing',invite:options.invite?'1':'0',clip:options.clip||''};
  ids.devBriefing.hidden=!options.invite;
  const root=new Element(), requests=[], audio=[], speechClicks=[];
  root.azulAudioPolicy={check:async()=>options.sound!==false,record(){}};
  root.azulCompanion={stopVoice(){},speaking(){},attachSpeech(container,offer){
    if (!offer) return;
    const button=new Element();button.click=()=>speechClicks.push(offer);container.append(button);return button;
  }};
  const docEvents={}, winEvents={};
  const document={hidden:false,getElementById:id=>ids[id],querySelector:()=>root,createElement:()=>new Element(),addEventListener:(name,fn)=>docEvents[name]=fn};
  class Audio {constructor(url){this.url=url;audio.push(this);}play(){return options.blockAutoplay?Promise.reject(Error('blocked')):Promise.resolve();}pause(){}}
  vm.runInNewContext(source,{document,window:{addEventListener:(name,fn)=>winEvents[name]=fn},Audio,AbortController,CustomEvent:class{constructor(type){this.type=type;}},
    setTimeout,clearTimeout,fetch:async(...args)=>{requests.push(args);return fetcher(...args);}});
  docEvents.DOMContentLoaded();
  return {ids,root,requests,audio,speechClicks,document,docEvents,winEvents};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const response=()=>({ok:true,status:200,json:async()=>({answer:'2 falhas nas últimas 24 horas.',speech:{url:'/api/azul/voz',token:'signed'},links:[
  {label:'Registro',url:'/dev?erro=12'},{label:'Ataque',url:'javascript:alert(1)'},{label:'Externo',url:'//evil.com'}]})});

test('login invitation does not fetch private data or synthesize audio before a choice',async()=>{
  const env=setup(response,{invite:true});await settle();
  assert.equal(env.ids.devBriefing.hidden,false);
  assert.equal(env.requests.length,0);assert.equal(env.audio.length,0);assert.equal(env.speechClicks.length,0);
  env.ids.devBriefingDismiss.events.click();assert.equal(env.ids.devBriefing.hidden,true);
  env.ids.devBriefingOpen.events.click();assert.equal(env.ids.devBriefing.hidden,false);
  assert.equal(env.requests.length,0);
});
test('read fetches once and never starts narration; listen starts only the signed offer',async()=>{
  const env=setup(response,{invite:true});
  await env.ids.devBriefingRead.events.click();await settle();
  assert.equal(env.requests.length,1);assert.equal(env.speechClicks.length,0);
  assert.equal(env.ids.devBriefingResult.textContent,'2 falhas nas últimas 24 horas.');
  assert.equal(env.ids.devBriefingResult.children[0].children.length,1);
  await env.ids.devBriefingListen.events.click();await settle();
  assert.equal(env.speechClicks.length,1);assert.equal(env.speechClicks[0].token,'signed');
});
test('dismiss cancels an in-flight summary and late replies cannot reappear',async()=>{
  let finish;const env=setup(()=>new Promise(resolve=>finish=resolve),{invite:true});
  env.ids.devBriefingListen.events.click();env.ids.devBriefingListen.events.click();
  assert.equal(env.requests.length,1);
  env.ids.devBriefingDismiss.events.click();assert.equal(env.requests[0][1].signal.aborted,true);
  finish(response());await settle();
  assert.equal(env.ids.devBriefing.hidden,true);assert.equal(env.speechClicks.length,0);
});
test('generic invitation respects sound policy and blocked autoplay leaves the choice visible',async()=>{
  const clip='/static/audio/azul-falas/'+'a'.repeat(64)+'.wav?v='+'b'.repeat(12);
  const muted=setup(response,{invite:true,clip,sound:false});await settle();assert.equal(muted.audio.length,0);
  const blocked=setup(response,{invite:true,clip,blockAutoplay:true});await settle();
  assert.equal(blocked.audio.length,1);assert.equal(blocked.requests.length,0);
  assert.equal(blocked.ids.devBriefing.hidden,false);assert.match(blocked.ids.devBriefingStatus.textContent,/Ouvir pendências/);
});
test('revoked access hides the summary instead of narrating stale data',async()=>{
  const env=setup(async()=>({ok:false,status:403}),{invite:true});
  await env.ids.devBriefingListen.events.click();await settle();
  assert.equal(env.ids.devBriefing.hidden,true);assert.equal(env.speechClicks.length,0);
});
