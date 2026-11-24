const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('app/static/js/azul-runtime.js','utf8');

test('a voice change stops the old call, releases old audio and applies the Bossa library',async()=>{
 const policy={voice_profile:'jett',voice_style:'jett-v2',sound_enabled:true,microphone_enabled:true,conversation_enabled:true};
 let next={...policy},cleared=0,stopped=0;
 const root={dataset:{},hasAttribute:()=>false,addEventListener(){},
  querySelector:key=>key==='[data-audio-policy]'?{textContent:JSON.stringify(policy)}:null,
  azulCompanion:{clearAudio(){cleared++;}},azulVoice:{stop(){stopped++;}}};
 vm.runInNewContext(source,{
  document:{querySelectorAll:()=>[root]},window:{addEventListener(){}},
  sessionStorage:{getItem:()=>null,setItem(){}},crypto:{randomUUID:()=> 'a'.repeat(32)},
  AbortController,setTimeout,clearTimeout,setInterval:()=>1,clearInterval(){},
  fetch:async()=>({ok:true,json:async()=>next})
 });
 await root.azulAudioPolicy.refresh();
 assert.equal(cleared,0);assert.equal(stopped,0);
 next={...policy,voice_profile:'bossa',voice_style:'azul-ptbr-bossa-v1',call_welcome:'/static/audio/azul-falas/new.wav'};
 await root.azulAudioPolicy.refresh();
 assert.equal(cleared,1);assert.equal(stopped,1);
 assert.equal(root.dataset.voiceProfile,'bossa');assert.equal(root.dataset.voiceEngine,'server');
 assert.equal(root.dataset.callWelcome,next.call_welcome);
 await root.azulAudioPolicy.refresh();
 assert.equal(cleared,1);assert.equal(stopped,1);
});
