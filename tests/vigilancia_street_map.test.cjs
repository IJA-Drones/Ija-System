const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/vigilancia-mapa-territorial.js', 'utf8');
const polygon = (west, south, east, north) => ({type:'Polygon',coordinates:[[
  [west,south],[east,south],[east,north],[west,north],[west,south]
]]});

function page({configured=true, api=true, collapsed=false, fail=false, iip=25, color='#dc2626', classification='Risco'}={}) {
  function element() {
    return {children:[],attributes:{},handlers:{},dataset:{},checked:true,hidden:false,
      setAttribute(name,value){this.attributes[name]=String(value);},
      append(child){this.children.push(child);},replaceChildren(...children){this.children=children;},
      addEventListener(name,callback){(this.handlers[name]??=[]).push(callback);},
      emit(name,event={}){(this.handlers[name]||[]).forEach(fn=>fn(event));}};
  }
  const nodes=Object.fromEntries(['data','svg','detalhe','status','estado','enquadrar','municipio','mapa','fallback','ruas-status']
    .map(name=>[name,element()]));
  const details={...element(),tagName:'DETAILS',open:!collapsed};
  nodes.mapa.parentElement=details;
  nodes.mapa.closest=()=>({getClientRects:()=>details.open?[{}]:[]});
  nodes.mapa.hidden=true;
  const controls=['iip','visitas'].map(name=>({...element(),dataset:{territorialLayer:name}}));
  const data={mapa_ruas:configured,
    contexto:{metadata:{recorte:'Município de São Paulo'},features:[{
      geometry:polygon(-46.82,-24,-46.36,-23.35),properties:{codigo:'3550308',nome:'São Paulo',selecionado:true}}]},
    geografia:{features:[{geometry:polygon(-46.639,-23.55,-46.631,-23.544),properties:{
      estrato_codigo:'E1',area_codigo:'A1',levantamento_codigo:'L1',iip,cor:color,classificacao_rotulo:classification}}]},
    pontos:['SIM','NAO',''].map((positivo,index)=>({longitude:-46.635+index*.001,latitude:-23.548,
      situacao:index===2?'FECHADO':'INSPECIONADO',positivo_aedes:positivo,inspecao_codigo:`VIS-${index}`,bairro:'Sé'}))};
  nodes.data.textContent=JSON.stringify(data);
  const maps=[],polygons=[],markers=[],events={},timeouts=new Set(),resizes=[];
  class Shape {
    constructor(options){this.options=options;this.currentMap=options.map;this.handlers={};}
    setMap(map){this.currentMap=map;}
    addListener(name,callback){this.handlers[name]=callback;}
  }
  const google={maps:{
    Map:class {constructor(node,options){if(fail)throw new Error('unavailable');this.options=options;this.frames=[];this.zoom=12;maps.push(this);}
      fitBounds(bounds,padding){this.frames.push({points:bounds.points,padding});} getZoom(){return this.zoom;} setZoom(zoom){this.zoom=zoom;}},
    LatLngBounds:class {constructor(){this.points=[];}extend(point){this.points.push(point);}},
    Polygon:class extends Shape {constructor(options){super(options);polygons.push(this);}},
    Marker:class extends Shape {constructor(options){super(options);markers.push(this);}},
    InfoWindow:class {close(){}setContent(content){this.content=content;}setPosition(position){this.position=position;}open(){}},
    SymbolPath:{CIRCLE:'circle'},
    event:{addListenerOnce(map,name,callback){if(name==='idle')callback();},trigger(map,name){resizes.push(name);}}
  }};
  const window={google:api?google:undefined,setTimeout(callback){timeouts.add(callback);return callback;},clearTimeout(callback){timeouts.delete(callback);}};
  const document={getElementById:id=>nodes[id.replace('campo-territorio-','')],querySelectorAll:()=>controls,
    createElement:element,createElementNS:element,addEventListener(name,callback){events[name]=callback;}};
  vm.runInNewContext(source,{document,window});
  return {nodes,controls,maps,polygons,markers,window,google,events,timeouts,details,resizes,
    click:name=>nodes[name].emit('click'),timeout:()=>[...timeouts].forEach(fn=>fn())};
}

test('streets are the primary view; municipal fill does not cover the streets',()=>{
  const p=page();
  assert.equal(p.maps.length,1);
  assert.equal(p.nodes.mapa.hidden,false);
  assert.equal(p.nodes.fallback.hidden,true);
  assert.equal(p.maps[0].options.mapTypeId,'roadmap');
  assert.equal(p.polygons[0].options.fillOpacity,0);
  assert.equal(p.polygons[1].options.fillColor,'#dc2626');
  assert.deepEqual(p.markers.map(marker=>marker.options.icon.fillColor),['#dc2626','#15803d','#d97706']);
  assert.deepEqual({...p.markers[0].options.position},{lat:-23.548,lng:-46.635});
  assert.match(p.nodes['ruas-status'].textContent,/Mapa de ruas/);
});

test('the initial street viewport fits the survey; municipal view is explicit and reversible',()=>{
  const p=page(),map=p.maps[0];
  const first=JSON.stringify(map.frames.at(-1));
  assert.ok(map.frames.at(-1).points.every(point=>point.lng>-46.65 && point.lng<-46.62));
  p.click('municipio');
  assert.ok(map.frames.at(-1).points.some(point=>point.lng===-46.82));
  p.click('enquadrar');
  assert.equal(JSON.stringify(map.frames.at(-1)),first);
});

test('layer controls toggle the same contours and visits on the street map',()=>{
  const p=page();
  p.controls[0].checked=false;p.controls[0].emit('change');
  assert.equal(p.polygons[1].currentMap,null);
  assert.equal(p.polygons[0].currentMap,p.maps[0]);
  assert.ok(p.markers.every(marker=>marker.currentMap===p.maps[0]));
  p.controls[1].checked=false;p.controls[1].emit('change');
  assert.ok(p.markers.every(marker=>marker.currentMap===null));
  assert.match(p.nodes.status.textContent,/0 visitas.*0 contornos/);
});

test('clicking a visit shows its source, date and inspection status without HTML injection',()=>{
  const p=page();
  p.markers[0].handlers.click();
  assert.equal(p.nodes.detalhe.children[0].textContent,'Visita de campo confirmada');
  assert.ok(p.nodes.detalhe.children.some(child=>child.textContent==='Código da inspeção: VIS-0'));
});

test('area selection shows its infestation class and never turns missing IIP into zero',()=>{
  for (const options of [{}, {iip:null,color:'#94a3b8',classification:'Sem dados'}]) {
    const p=page(options);
    p.polygons[1].handlers.click({latLng:{lat:-23.548,lng:-46.635}});
    assert.ok(p.nodes.detalhe.children.some(child=>child.textContent===`Classificação: ${options.classification || 'Risco'}`));
    if (options.iip===null) {
      assert.ok(p.nodes.detalhe.children.some(child=>child.textContent==='IIP preliminar: Sem dados'));
      assert.equal(p.polygons[1].options.fillColor,'#94a3b8');
    }
  }
});

test('an authorization failure restores the SVG and preserves its visits and controls',()=>{
  const p=page();p.window.__GOOGLE_MAPS_AUTH_FAILED__=true;p.events['googlemaps:auth-failed']();
  assert.equal(p.nodes.mapa.hidden,true);
  assert.equal(p.nodes.fallback.hidden,false);
  assert.match(p.nodes['ruas-status'].textContent,/indisponível neste endereço.*sem ruas/);
  p.click('municipio');
  assert.match(p.nodes.status.textContent,/Visão do município/);
  assert.equal(p.nodes.svg.children.filter(shape=>shape.attributes.class?.startsWith('campo-visita')).length,3);
});

test('a missing API times out to a clearly identified fallback and can recover on ready',()=>{
  const p=page({api:false});p.timeout();
  assert.equal(p.nodes.fallback.hidden,false);
  assert.match(p.nodes['ruas-status'].textContent,/não carregou/);
  p.window.google=p.google;p.events['googlemaps:ready']();
  assert.equal(p.maps.length,1);
  assert.equal(p.nodes.fallback.hidden,true);
});

test('no configured key or a constructor failure keeps the fallback usable',()=>{
  for(const options of [{configured:false},{fail:true}]){
    const p=page(options);
    assert.equal(p.nodes.fallback.hidden,false);
    assert.equal(p.nodes.mapa.hidden,true);
    assert.match(p.nodes['ruas-status'].textContent,/sem ruas/);
  }
});

test('results initialize streets only when expanded and refit when reopened',()=>{
  const p=page({collapsed:true});
  assert.equal(p.maps.length,0);
  assert.equal(p.timeouts.size,0);
  p.details.open=true;p.details.emit('toggle');
  assert.equal(p.maps.length,1);
  p.details.open=false;p.details.emit('toggle');
  p.details.open=true;p.details.emit('toggle');
  assert.equal(p.maps.length,1);
  assert.ok(p.resizes.includes('resize'));
});
