const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source=fs.readFileSync('app/static/js/portal-mapa-vigilancia.js','utf8');
const polygon=(w,s,e,n)=>({type:'Polygon',coordinates:[[[w,s],[e,s],[e,n],[w,n],[w,s]]]});

function page({configured=true,api=true,empty=false}={}) {
  class Element {
    constructor(){this.children=[];this.attributes={};this.handlers={};this.style={};this.value='';this.textContent='';this.hidden=false;}
    append(...children){this.children.push(...children);}replaceChildren(...children){this.children=children;}
    setAttribute(name,value){this.attributes[name]=value;}addEventListener(name,fn){this.handlers[name]=fn;}
    change(value){this.value=value;this.handlers.change?.();}
    text(){return this.textContent+this.children.map(child=>typeof child==='string'?child:child.text()).join(' ');}
  }
  const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
  const city={type:'Feature',geometry:polygon(-46.82,-24,-46.36,-23.35),properties:{codigo:'3550308',nome:'São Paulo'}};
  const data={mapa_ruas:configured,municipio:{ibge:'3550308',name:'São Paulo'},demo:true,limite:empty?null:city,
    contexto:{features:empty?[]:[city]},filtros:{levantamento:'L-1'},legenda_iip:[],
    geografia:{features:empty?[]:[{type:'Feature',geometry:polygon(-46.64,-23.55,-46.63,-23.54),properties:{
      levantamento_codigo:'L-1',estrato_codigo:'E1',area_codigo:'A1',iip:0,cor:'#15803d',classificacao_rotulo:'Satisfatório',
      imoveis_inspecionados:8,imoveis_positivos:0,imoveis_pendentes:0}}]},
    liraa:{disponivel:!empty,visitas:8,inicio:'2026-11-11',fim:'2026-11-11'},
    focal:{disponivel:true,visitas:3,inspecionados:2},
    sinan:{total:6,parcial:true,doenca:'Dengue',ano:2026,origem:'Agregado municipal',classificacoes:[]},
    // Uma regressão não deve transformar dados individuais em marcadores públicos.
    pontos:[{latitude:-23.54,longitude:-46.63,imovel_codigo:'PRIVADO'}]};
  get('portal-risco-data').textContent=JSON.stringify(data);
  get('portal-risco-camada').value='liraa';get('portal-risco-mapa').hidden=true;
  const maps=[],polygons=[],events={},timers=new Set();let markers=0;
  class StreetMap {
    constructor(node,options){this.options=options;this.frames=[];maps.push(this);}
    fitBounds(bounds){this.frames.push(bounds.points);}getZoom(){return 15;}setZoom(){}
  }
  class Polygon {
    constructor(options){this.options=options;this.currentMap=options.map;this.handlers={};polygons.push(this);}
    setMap(map){this.currentMap=map;}setOptions(options){Object.assign(this.options,options);}
    addListener(name,fn){this.handlers[name]=fn;}
  }
  const google={maps:{Map:StreetMap,Polygon,LatLngBounds:class {constructor(){this.points=[];}extend(point){this.points.push(point);}},
    Marker:class {constructor(){markers++;throw new Error('individual marker forbidden');}},
    Circle:class {constructor(){markers++;throw new Error('individual circle forbidden');}},
    event:{addListenerOnce(map,name,fn){if(name==='idle')fn();}}}};
  const window={google:api?google:undefined,setTimeout(fn){timers.add(fn);return fn;},clearTimeout(fn){timers.delete(fn);}};
  const document={getElementById:get,createElement:()=>new Element(),createElementNS:()=>new Element(),createTextNode:text=>text,
    addEventListener(name,fn){events[name]=fn;}};
  vm.runInNewContext(source,{document,window});
  return {get,maps,polygons,events,window,google,timers,markerCount:()=>markers};
}

test('public streets show only aggregate polygons and fit all sampled areas initially',()=>{
  const p=page();
  assert.equal(p.maps.length,1);assert.equal(p.markerCount(),0);
  assert.equal(p.get('portal-risco-mapa').hidden,false);
  assert.equal(p.get('portal-risco-fallback').hidden,true);
  assert.equal(p.polygons[0].options.fillOpacity,0);
  assert.equal(p.polygons[1].options.fillColor,'#15803d');
  assert.ok(p.maps[0].frames.at(-1).every(point=>point.lng>=-46.64 && point.lng<=-46.63));
  p.get('portal-risco-area').change('municipio');
  assert.ok(p.maps[0].frames.at(-1).some(point=>point.lng===-46.82));
});

test('selecting a colored public area shows its class and indices without property details',()=>{
  const p=page();p.polygons[1].handlers.click();
  assert.equal(p.get('portal-risco-area').value,'0');
  assert.match(p.get('risco-detalhe').text(),/IIP: 0%.*Classificação: Satisfatório/);
  assert.doesNotMatch(p.get('risco-detalhe').text(),/PRIVADO/);
});

test('SINAN and focal remain municipal aggregates and hide LIRAa colors',()=>{
  const p=page();p.get('portal-risco-camada').change('sinan');
  assert.equal(p.polygons[1].currentMap,null);
  assert.equal(p.polygons[0].options.fillColor,'#bae6fd');
  assert.match(p.get('risco-detalhe').text(),/6 registros no snapshot parcial/);
  p.get('portal-risco-camada').change('focal');
  assert.match(p.get('risco-detalhe').text(),/3 visitas confirmadas/);
  p.get('portal-risco-camada').change('liraa');
  assert.equal(p.polygons[1].currentMap,p.maps[0]);
  assert.equal(p.markerCount(),0);
});

test('auth failure restores public contours and selection remains usable',()=>{
  const p=page();p.window.__GOOGLE_MAPS_AUTH_FAILED__=true;p.events['googlemaps:auth-failed']();
  assert.equal(p.get('portal-risco-mapa').hidden,true);
  assert.equal(p.get('portal-risco-fallback').hidden,false);
  p.get('portal-risco-area').change('0');
  assert.match(p.get('risco-detalhe').text(),/Classificação: Satisfatório/);
});

test('missing API falls back and can recover after ready',()=>{
  const p=page({api:false});[...p.timers].forEach(fn=>fn());
  assert.match(p.get('portal-risco-ruas-status').text(),/não carregou/);
  p.window.google=p.google;p.events['googlemaps:ready']();
  assert.equal(p.maps.length,1);assert.equal(p.get('portal-risco-fallback').hidden,true);
});

test('no configured key or geographic boundary keeps an explicit usable fallback',()=>{
  for(const options of [{configured:false},{empty:true}]) {
    const p=page(options);
    assert.equal(p.maps.length,0);
    assert.equal(p.get('portal-risco-fallback').hidden,false);
    assert.match(p.get('portal-risco-ruas-status').text(),/sem ruas/);
    assert.equal(p.markerCount(),0);
  }
});
