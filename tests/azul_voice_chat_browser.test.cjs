const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('app/static/js/azul-voice-chat.js','utf8');
class Element {
 constructor(){this.events={};this.dataset={};this.hidden=false;this.textContent='';}
 addEventListener(name,fn){this.events[name]=fn;}
 setAttribute(name,value){this[name]=value;}
 dispatchEvent(event){this.events[event.type]?.(event);}
 focus(){}
}
function setup({fetcher,permission}={}){
 const root=new Element(),controls=new Element(),mic=new Element(),label=new Element(),action=new Element(),status=new Element(),dictate=new Element(),input=new Element();input.value='';input.maxLength=1500;
 const call=new Element(),callTitle=new Element(),callDescription=new Element(),callAction=new Element(),callActionLabel=new Element(),callEnd=new Element();call.hidden=true;
 call.querySelector=key=>({'[data-call-title]':callTitle,'[data-call-description]':callDescription,'[data-call-action]':callAction,'[data-call-action-label]':callActionLabel,'[data-call-end]':callEnd}[key]);
 root.dataset={transcribeUrl:'/portal-cidadao/transcrever',token:'session-token',csrf:'csrf'};
 root.querySelector=key=>key==='[data-voice-controls]'?controls:key==='[data-compose-input]'?input:key==='[data-voice-call]'?call:null;
 controls.querySelector=key=>({'[data-microphone]':mic,'[data-dictate]':dictate,'[data-voice-action]':action,'[data-microphone-status]':status}[key]);
 mic.querySelector=()=>label;
 const tracks=[],nodes=[],contexts=[],sources=[],clips=[],requests=[],sent=[],timers=new Map(),documentEvents={};let now=0,nextTimer=0;
 root.azulCompanion={listening(){},thinking(){},speaking(){},stopVoice(){},closeGuide(){},useAudioContext(){}};
 const originalDispatch=root.dispatchEvent.bind(root);root.dispatchEvent=event=>{sent.push(event);originalDispatch(event);};
 class AudioContext {
  constructor(){this.sampleRate=48000;contexts.push(this);}
  async resume(){}
  async close(){this.closed=true;}
  async decodeAudioData(bytes){return bytes;}
  createBufferSource(){const source={connect(){},disconnect(){},start(){},stop(){this.stopped=true;}};sources.push(source);return source;}
  createMediaStreamSource(){return{connect(){},disconnect(){}};}
  createGain(){return{gain:{value:0},connect(){},disconnect(){}};}
  createScriptProcessor(){const node={connect(){},disconnect(){}};nodes.push(node);return node;}
 }
 const media={getUserMedia:async()=>{
  if(permission)return permission();
  const track={readyState:'live',stop(){this.readyState='ended';}};tracks.push(track);
  return{getTracks:()=>[track]};
 }};
 vm.runInNewContext(source,{
  document:{querySelectorAll:key=>key==='[data-azul-help]'?[root]:[],addEventListener:(name,fn)=>documentEvents[name]=fn},
  window:{AudioContext,addEventListener(){}},navigator:{mediaDevices:media},performance:{now:()=>now},
  Float32Array,DataView,ArrayBuffer,Blob,AbortController,
  Event:class{constructor(type){this.type=type;}},
  CustomEvent:class{constructor(type,opts={}){this.type=type;this.detail=opts.detail;}},
  setTimeout:(fn,ms)=>{timers.set(++nextTimer,{fn,ms});return nextTimer;},clearTimeout:id=>timers.delete(id),
  fetch:async(url,opts)=>{if(url.startsWith('/static/audio/')){clips.push(url);return{ok:true,arrayBuffer:async()=>new ArrayBuffer(100)};}requests.push({url,...opts});return fetcher?fetcher(url,opts):{ok:true,json:async()=>({text:'Qual seu nome?'})};}
 });
 function feed(value=0.1,milliseconds=50){now+=milliseconds;const samples=new Float32Array(2048).fill(value);nodes.at(-1).onaudioprocess?.({inputBuffer:{getChannelData:()=>samples}});}
 return{root,mic,dictate,input,action,status,call,callTitle,callAction,callActionLabel,callEnd,tracks,nodes,contexts,sources,clips,requests,sent,timers,documentEvents,feed};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
async function start(env){await env.mic.events.click();await settle();assert.equal(env.root.dataset.voiceState,'speaking');env.sources.at(-1).onended();[...env.timers.values()].find(timer=>timer.ms===200).fn();await settle();assert.equal(env.root.dataset.voiceState,'listening');}
function speak(env){for(let i=0;i<10;i++)env.feed(.1);env.feed(0,1200);}

test('microphone is opt-in; a bounded WAV goes to transcription and then to the normal chat',async()=>{
 const env=setup();assert.equal(env.tracks.length,0);assert.equal(env.requests.length,0);assert.equal(env.call.hidden,true);
 await start(env);assert.equal(env.call.hidden,false);assert.equal(env.callTitle.textContent,'Estou ouvindo');
 speak(env);await settle();
 assert.equal(env.requests.length,1);assert.equal(env.requests[0].headers['X-Portal-Chat-Token'],'session-token');
 const bytes=Buffer.from(await env.requests[0].body.arrayBuffer());
 assert.equal(bytes.subarray(0,4).toString(),'RIFF');assert.equal(bytes.readUInt32LE(24),16000);
 const ask=env.sent.find(event=>event.type==='azul:ask');assert.deepEqual({...ask.detail},{message:'Qual seu nome?',voice:true});
 assert.equal(env.tracks[0].readyState,'ended');env.root.azulVoice.stop();
});

test('silence ends listening without transcription tokens',async()=>{
 const env=setup();await start(env);
 const silence=[...env.timers.values()].find(timer=>timer.ms===8000);silence.fn();
 assert.equal(env.requests.length,0);assert.equal(env.tracks[0].readyState,'ended');assert.equal(env.root.azulVoice.isActive(),false);
});

test('dictation fills the writing field for review without asking the chat or generating a spoken answer',async()=>{
 const env=setup();env.input.value='Olá.';
 env.dictate.events.click();await settle();assert.equal(env.root.dataset.voiceMode,'dictation');
 assert.equal(env.call.hidden,true);assert.equal(env.root.dataset.voiceCallOpen,'0');
 speak(env);await settle();
 assert.equal(env.input.value,'Olá. Qual seu nome?');
 assert.equal(env.sent.some(event=>event.type==='azul:ask'),false);
 assert.equal(env.requests.length,1);assert.equal(env.root.azulVoice.isActive(),false);
});

test('a short spoken answer such as sim is not discarded as silence',async()=>{
 const env=setup();await start(env);
 for(let i=0;i<5;i++)env.feed(.1);env.feed(0,1200);await settle();
 assert.equal(env.requests.length,1);env.root.azulVoice.stop();
});

test('an unrelated or ambiguous reply plays a fixed scope reminder without paid narration and resumes listening',async()=>{
 for(const mode of ['blocked','clarify']){
  const env=setup();await start(env);speak(env);await settle();let played=false;
  env.root.dispatchEvent({type:'azul:reply',detail:{mode,speechButton:{click(){played=true;}}}});
  await settle();assert.equal(played,false);assert.equal(env.root.azulVoice.isActive(),true);assert.equal(env.clips.at(-1),'/static/audio/azul-escopo-chamada.wav');
  assert.equal(env.root.dataset.voiceState,'speaking');assert.ok(env.tracks.every(track=>track.readyState==='ended'));
  env.sources.at(-1).onended();[...env.timers.values()].find(timer=>timer.ms===200).fn();await settle();
  assert.equal(env.root.dataset.voiceState,'listening');env.root.azulVoice.stop();
 }
});

test('a normal spoken response starts playback and resumes listening after it ends',async()=>{
 const env=setup();await start(env);speak(env);await settle();let played=0;
 env.root.dispatchEvent({type:'azul:reply',detail:{mode:'local',speechButton:{click(){played++;}}}});
 assert.equal(played,1);assert.equal(env.root.dataset.voiceState,'preparing');assert.equal(env.callActionLabel.textContent,'Falar agora');
 env.root.dispatchEvent({type:'azul:voice-started'});assert.equal(env.root.dataset.voiceState,'speaking');
 env.root.dispatchEvent({type:'azul:voice-ended'});[...env.timers.values()].find(timer=>timer.ms===200).fn();await settle();
 assert.equal(env.root.dataset.voiceState,'listening');assert.equal(env.tracks.length,3);
 env.root.azulVoice.stop();assert.ok(env.tracks.every(track=>track.readyState==='ended'));
});

test('a call opens with a spoken greeting, keeps capture off during playback and supports interruption',async()=>{
 const env=setup();await env.mic.events.click();await settle();
 assert.equal(env.root.dataset.voiceState,'speaking');assert.equal(env.call.hidden,false);assert.equal(env.clips[0],'/static/audio/azul-inicio-chamada.wav');
 assert.equal(env.requests.length,0);assert.ok(env.tracks.every(track=>track.readyState==='ended'));
 env.callAction.events.click();await settle();
 assert.equal(env.sources[0].stopped,true);assert.equal(env.root.dataset.voiceState,'listening');
 env.callEnd.events.click();assert.ok(env.tracks.every(track=>track.readyState==='ended'));
});

test('interrupting an in-flight transcription ignores its late result and releases the old capture',async()=>{
 let resolve;const env=setup({fetcher:()=>new Promise(done=>resolve=done)});
 await start(env);speak(env);await settle();env.callAction.events.click();await settle();
 assert.equal(env.requests[0].signal.aborted,true);assert.equal(env.tracks[0].readyState,'ended');
 resolve({ok:true,json:async()=>({text:'Late transcript'})});await settle();
 assert.equal(env.sent.some(event=>event.type==='azul:ask'),false);env.root.azulVoice.stop();
 assert.ok(env.tracks.every(track=>track.readyState==='ended'));
});

test('ending the call cancels transcription, restores text mode and ignores a late transcript',async()=>{
 let resolve;const env=setup({fetcher:()=>new Promise(done=>resolve=done)});
 await start(env);speak(env);await settle();env.callEnd.events.click();
 assert.equal(env.requests[0].signal.aborted,true);assert.equal(env.call.hidden,true);assert.equal(env.root.dataset.voiceCallOpen,'0');
 assert.equal(env.contexts[0].closed,true);assert.equal(env.root.azulVoice.isActive(),false);
 resolve({ok:true,json:async()=>({text:'Resposta atrasada'})});await settle();
 assert.equal(env.sent.some(event=>event.type==='azul:ask'),false);assert.equal(env.sent.at(-1).type,'azul:interrupt');
 assert.ok(env.tracks.every(track=>track.readyState==='ended'));
});

test('a microphone granted after cancellation is released immediately',async()=>{
 let resolve;const track={readyState:'live',stop(){this.readyState='ended';}};
 const env=setup({permission:()=>new Promise(done=>resolve=done)});await env.mic.events.click();await settle();
 env.root.azulVoice.stop();resolve({getTracks:()=>[track]});await settle();
 assert.equal(track.readyState,'ended');assert.equal(env.requests.length,0);
});

test('denied microphone permission leaves text available and no background request',async()=>{
 const env=setup({permission:async()=>{throw Object.assign(new Error('denied'),{name:'NotAllowedError'});}});
 await env.mic.events.click();await settle();assert.match(env.status.textContent,/Permita o microfone/);
 assert.equal(env.call.hidden,true);
 assert.equal(env.root.azulVoice.isActive(),false);assert.equal(env.requests.length,0);
});

test('server-provided voice limits bound the WAV and stop after the allowed turn',async()=>{
 const env=setup();env.root.azulAudioPolicy={current:{speech_seconds:3,silence_seconds:4,session_turns:1,session_minutes:1},check:async()=>true,record(){}};
 await start(env);assert.ok([...env.timers.values()].some(timer=>timer.ms===4000));
 for(let i=0;i<80;i++)env.feed(.1);await settle();
 assert.equal(env.requests.length,1);const bytes=Buffer.from(await env.requests[0].body.arrayBuffer());
 assert.equal(bytes.readUInt32LE(40),16000*3*2);
 env.root.dispatchEvent({type:'azul:reply',detail:{mode:'local',speechButton:{click(){}}}});
 env.root.dispatchEvent({type:'azul:voice-started'});env.root.dispatchEvent({type:'azul:voice-ended'});
 [...env.timers.values()].find(timer=>timer.ms===200).fn();await settle();
 assert.equal(env.root.azulVoice.isActive(),false);
});

test('a disabled conversation policy stops before requesting microphone permission',async()=>{
 const env=setup();env.root.azulAudioPolicy={current:{conversation_enabled:false},check:async()=>false};
 await env.mic.events.click();await settle();
 assert.equal(env.tracks.length,0);assert.equal(env.requests.length,0);assert.equal(env.call.hidden,true);
 assert.equal(env.contexts[0].closed,true);
});
