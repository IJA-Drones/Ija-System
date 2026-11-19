const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function setup(){
  class Element{constructor(){this.hidden=true;this.value='';this.disabled=false;this.children=[];this.checked=true;}append(...v){this.children.push(...v);}replaceChildren(){this.children=[];}setAttribute(){} }
  const elements=new Map();const el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  class Source{clear(){}addFeature(){} }
  class Layer{constructor(o){this.options=o;this.visible=true;this.events={};}on(n,f){this.events[n]=f;}getVisible(){return this.visible;}setVisible(v){this.visible=v;}dispose(){this.disposed=true;}getSource(){return this.options.source;} }
  const polygon={getCoordinates:()=>[[[1,2],[3,4],[5,6],[1,2]]],getExtent:()=>[1,2,5,6]};
  class GeoJSON{readFeature(){return {getGeometry:()=>polygon};}writeGeometryObject(){return {type:'Polygon',coordinates:polygon.getCoordinates()};} }
  class Draw{constructor(){this.events={};}on(n,f){this.events[n]=f;} }
  const layers=[],calls=[],requests=[],interactions=[],isolated=[],fits=[];
  const map={getSize:()=>[1200,800],getView:()=>({fit:(...args)=>fits.push(args)}),addLayer:l=>layers.push(l),removeLayer:l=>calls.push(l),addInteraction:l=>interactions.push(l),removeInteraction:l=>calls.push(l),getPixelFromCoordinate:([x,y])=>[x*10,y*10]};
  const api=(url,opts)=>new Promise((resolve,reject)=>requests.push({url,opts,resolve,reject}));
  const context={window:{addEventListener(){}},document:{getElementById:el,createElement:()=>new Element(),createTextNode:t=>t,addEventListener(){}},ol:{source:{Vector:Source},layer:{Vector:Layer,WebGLTile:Layer},style:{Style:class{},Stroke:class{},Fill:class{}},format:{GeoJSON},interaction:{Draw}},confirm:()=>true,setTimeout:fn=>fn()};
  vm.runInNewContext(fs.readFileSync('app/static/js/ortomosaicos-areas.js','utf8'),context);
  return {areas:context.window.createOrthoAreas({map,api,onOpen(){},onIsolate:v=>isolated.push(v)}),layers,calls,requests,el,isolated,interactions,fits};
}
const survey=id=>({id,status:'pronto',tipo:'rgb',areas_url:`/${id}/areas`});
const item={id:7,nome:'Área',geometria:{},resultado:{area_m2:100,area_ha:.01,perimetro_m:40}};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('crop clips only its own canvas and reuses original raster source',async()=>{
  const h=setup(),source={};h.areas.select(survey(1),source);h.requests[0].resolve({items:[item]});await tick();
  const crop=h.layers.find(l=>l.options.className==='ortho-crop-7');assert.equal(crop.options.source,source);
  const canvas={style:{},parentElement:{style:{}}};crop.events.prerender({context:{canvas}});
  assert.equal(canvas.style.clipPath,'polygon(10px 20px,30px 40px,50px 60px,10px 20px)');assert.equal(canvas.parentElement.style.clipPath,undefined);
  h.areas.select(null,null);assert.equal(crop.disposed,true);assert.equal(source.disposed,undefined);
});
test('late responses from another survey cannot restore stale crop layers',async()=>{
  const h=setup();h.areas.select(survey(1),{});h.areas.select(survey(2),{});
  h.requests[0].resolve({items:[item]});h.requests[1].resolve({items:[]});await tick();
  assert.equal(h.layers.length,1);assert.equal(h.el('ortho-area-isolate').disabled,true);
});
test('clearing a draft ignores its pending calculation and never enables save',async()=>{
  const h=setup();h.areas.select(survey(1),{});h.requests[0].resolve({items:[]});await tick();
  h.el('ortho-area-draw').onclick();h.interactions[0].events.drawend({feature:{getGeometry(){return {};}}});
  h.el('ortho-area-clear').onclick();h.requests[1].resolve({item});await tick();
  assert.equal(h.el('ortho-area-save').disabled,true);
});

test('saved sidebar reopens a hidden crop after closing its panel and returning to original',async()=>{
  const h=setup();h.areas.select(survey(1),{});h.requests[0].resolve({items:[item]});await tick();
  const crop=h.layers.find(l=>l.options.className==='ortho-crop-7');assert.equal(crop.getVisible(),false);
  h.el('ortho-area-library-list').children[0].onclick();assert.equal(crop.getVisible(),true);assert.equal(h.el('ortho-area-editor').hidden,true);
  h.areas.close();h.areas.showOriginal();assert.equal(crop.getVisible(),false);
  h.el('ortho-area-library-list').children[0].onclick();assert.equal(crop.getVisible(),true);assert.equal(h.el('ortho-area-panel').hidden,false);
  assert.equal(h.fits.length,2);
});
test('switching surveys and returning reloads saved shortcuts',async()=>{
  const h=setup();h.areas.select(survey(1),{});h.requests[0].resolve({items:[item]});await tick();
  h.areas.select(null,null);assert.equal(h.el('ortho-area-library').hidden,true);
  h.areas.select(survey(1),{});h.requests[1].resolve({items:[item]});await tick();
  assert.equal(h.el('ortho-area-library-list').children.length,1);
  h.el('ortho-area-library-list').children[0].onclick();assert.equal(h.el('ortho-area-panel').hidden,false);
});
test('editing updates the existing layer instead of creating a duplicate',async()=>{
  const h=setup();h.areas.select(survey(1),{});h.requests[0].resolve({items:[item]});await tick();
  const card=h.el('ortho-area-list').children[0],actions=card.children[2];actions.children[1].onclick();
  assert.equal(h.el('ortho-area-save').textContent,'Salvar alterações');
  h.el('ortho-area-name').value='Renomeada';const pending=h.el('ortho-area-form').onsubmit({preventDefault(){}});
  assert.equal(h.requests[1].opts.method,'PUT');assert.equal(h.requests[1].url,'/1/areas/7');
  h.requests[1].resolve({item:{...item,nome:'Renomeada'}});await pending;
  assert.equal(h.el('ortho-area-library-list').children.length,1);
  assert.equal(h.el('ortho-area-library-list').children[0].textContent,'Renomeada');
});
