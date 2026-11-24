const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('app/static/js/azul-native-voice.js','utf8');
function setup(voices=[{name:'French voice',lang:'fr-FR'},{name:'Eddy',lang:'pt_BR'},{name:'Luciana',lang:'pt_BR'}]){
 const spoken=[],events=[],timers=new Map(),listeners={};let next=0,cancelled=0;
 const synth={getVoices:()=>voices,cancel(){cancelled++;},speak(message){spoken.push(message);message.onstart?.();},addEventListener:(name,fn)=>listeners[name]=fn,removeEventListener:name=>delete listeners[name]};
 const window={speechSynthesis:synth,SpeechSynthesisUtterance:class{constructor(text){this.text=text;}},addEventListener(){}};
 class Element{constructor(){this.events={};this.children=[];}addEventListener(name,fn){this.events[name]=fn;}setAttribute(name,value){this[name]=value;}append(node){this.children.push(node);}}
 const status={textContent:''};const root={dataset:{},querySelector:()=>status,dispatchEvent:event=>events.push(event.type),azulAudioPolicy:{check:async()=>true}};
 root.azulCompanion={speaking(){},stopVoice(){root.azulNativeVoice?.stop();}};
 vm.runInNewContext(source,{window,document:{hidden:false,addEventListener(){},createElement:()=>new Element()},CustomEvent:class{constructor(type){this.type=type;}},setTimeout:(fn,ms)=>{const id=++next;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id)});
 return{api:window.AzulNativeVoice,root,spoken,events,timers,listeners,status,Element,get cancelled(){return cancelled;},setVoices(value){voices=value;}};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('chooses a female pt-BR voice and never selects French, Portuguese Portugal or male Eddy',()=>{
 const env=setup();
 assert.equal(env.api.chooseVoice([{name:'Luciana',lang:'pt_PT'},{name:'Francisca',lang:'fr-FR'}]),null);
 assert.equal(env.api.chooseVoice([{name:'Eddy',lang:'pt-BR'},{name:'Luciana',lang:'pt-BR'}]).name,'Luciana');
});
test('reads exact server text with the native Brazilian voice without any network request',async()=>{
 const env=setup();const pending=env.api.speak(env.root,'Bom dia! Há 2 falhas.');
 assert.equal(env.spoken.length,1);assert.equal(env.spoken[0].lang,'pt-BR');assert.equal(env.spoken[0].voice.name,'Luciana');
 assert.equal(env.spoken[0].text,'Bom dia! Há 2 falhas.');assert.ok(env.events.includes('azul:voice-started'));
 env.spoken[0].onend();await pending;assert.ok(env.events.includes('azul:voice-ended'));
});
test('missing female Brazilian voice fails clearly instead of using another accent',async()=>{
 const env=setup([{name:'French',lang:'fr-FR'}]);const pending=env.api.speak(env.root,'Bom dia!');
 const failure=assert.rejects(pending,/Nenhuma voz feminina pt-BR/);
 [...env.timers.values()].find(timer=>timer.ms===2500).fn();await failure;assert.equal(env.spoken.length,0);
});
test('can wait for Brazilian voices to load and cancellation stops pending speech',async()=>{
 const env=setup([]);const pending=env.api.speak(env.root,'Bom dia!');
 env.setVoices([{name:'Microsoft Francisca Online',lang:'pt-BR'}]);env.listeners.voiceschanged();await settle();
 assert.equal(env.spoken[0].voice.name,'Microsoft Francisca Online');
 const failure=assert.rejects(pending,error=>error.name==='AbortError');env.root.azulNativeVoice.stop();await failure;
 assert.ok(env.cancelled>0);
});
test('native playback button respects sound policy and can stop narration',async()=>{
 const env=setup();const container=new env.Element();const button=env.api.attach(env.root,container,{text:'Bom dia!'},'Ouvir resumo');
 const pending=button.events.click();await settle();assert.equal(env.spoken.length,1);assert.equal(button.textContent,'Parar áudio');
 await button.events.click();await pending;assert.equal(button.textContent,'Ouvir resumo');
 env.root.azulAudioPolicy.check=async()=>false;await button.events.click();assert.equal(env.spoken.length,1);
});
