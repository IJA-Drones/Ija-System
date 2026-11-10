const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('app/static/js/azul-drag.js','utf8');
function setup(saved=null,width=1280,height=900) {
 const timers=[],storage=new Map(saved?[['azul-launcher-position-v1',JSON.stringify(saved)]]:[]);
 const events={},root={dataset:{},addEventListener(){}};
 const style={removeProperty(name){delete this[name];}};
 const handle={style,events:{},classList:{add(){}},setAttribute(){},setPointerCapture(){},addEventListener(name,fn){this.events[name]=fn;},getBoundingClientRect(){const x=parseFloat(this.style.left)||1000,y=parseFloat(this.style.top)||700;return{left:x,top:y,right:x+108,bottom:y+100,width:108,height:100};}};
 const panel={hidden:true,style:{removeProperty(name){delete this[name];}},getBoundingClientRect(){return{width:410,height:600};}};
 root.querySelector=selector=>selector==='[data-toggle]'?handle:selector==='.azul-panel'?panel:null;
 vm.runInNewContext(source,{
  document:{querySelectorAll:selector=>selector==='[data-azul-help]'?[root]:[]},
  window:{innerWidth:width,innerHeight:height,addEventListener(name,fn){events[name]=fn;}},
  localStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},
  MutationObserver:class{constructor(fn){events.observe=fn;}observe(){}},requestAnimationFrame:fn=>fn(),setTimeout:fn=>timers.push(fn)
 });
 const point=(x,y)=>({button:0,pointerId:1,clientX:x,clientY:y,cancelable:true,preventDefault(){this.prevented=true;}});
 return{root,handle,panel,events,timers,storage,point};
}
test('drag moves the launcher, persists bounded coordinates, and does not open the chat',()=>{
 const env=setup();
 env.handle.events.pointerdown(env.point(1020,720));
 env.handle.events.pointermove(env.point(220,220));
 env.handle.events.pointerup(env.point(220,220));
 assert.equal(env.handle.style.left,'200px');
 assert.equal(env.handle.style.top,'200px');
 let prevented=false,stopped=false;
 env.handle.events.click({preventDefault(){prevented=true;},stopImmediatePropagation(){stopped=true;}});
 assert.equal(prevented,true);assert.equal(stopped,true);
 const saved=JSON.parse(env.storage.get('azul-launcher-position-v1'));
 assert.ok(saved.x>=0&&saved.x<=1&&saved.y>=0&&saved.y<=1);
 const restored=setup(saved);
 assert.equal(restored.handle.style.left,'200px');
 assert.equal(restored.handle.style.top,'200px');
});
test('an ordinary tap keeps the normal chat click available',()=>{
 const env=setup();env.handle.events.pointerdown(env.point(1020,720));env.handle.events.pointerup(env.point(1020,720));
 env.handle.events.click({preventDefault(){assert.fail('tap was prevented');},stopImmediatePropagation(){assert.fail('tap was stopped');}});
 assert.equal(env.storage.size,0);
});
test('mouse and touch drags cannot move the mascot outside the viewport',()=>{
 const env=setup(null,390,844);
 env.handle.events.pointerdown(env.point(1020,720));
 env.handle.events.pointermove(env.point(-2000,-2000));
 assert.equal(env.handle.style.left,'8px');assert.equal(env.handle.style.top,'8px');
 env.handle.events.pointermove(env.point(8000,8000));
 assert.equal(env.handle.style.left,'274px');assert.equal(env.handle.style.top,'736px');
});
test('keyboard repositioning and desktop popup placement stay within bounds',()=>{
 const env=setup();
 env.handle.events.keydown({key:'ArrowLeft',shiftKey:true,preventDefault(){}});
 assert.equal(env.handle.style.left,'984px');
 env.panel.hidden=false;env.events.observe();
 assert.ok(parseFloat(env.panel.style.left)>=12);
 assert.ok(parseFloat(env.panel.style.top)>=12);
 assert.ok(parseFloat(env.panel.style.left)+410<=1280);
 assert.ok(parseFloat(env.panel.style.top)+600<=900);
});
