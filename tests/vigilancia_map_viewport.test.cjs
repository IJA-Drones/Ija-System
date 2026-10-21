const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/vigilancia-mapa-territorial.js', 'utf8');

const polygon = (west, south, east, north) => ({type:'Polygon',coordinates:[[
  [west,south],[east,south],[east,north],[west,north],[west,south]
]]});

function map({areas=false, selected=true} = {}) {
  const element = () => ({children:[],attributes:{},handlers:{},dataset:{},checked:true,
    setAttribute(key,value){this.attributes[key]=String(value);},
    append(child){this.children.push(child);},replaceChildren(...children){this.children=children;},
    addEventListener(name,handler){this.handlers[name]=handler;}});
  const nodes = Object.fromEntries(['data','svg','detalhe','status','estado','enquadrar','municipio']
    .map(name=>['campo-territorio-'+name,element()]));
  const controls=['iip','visitas'].map(name=>({...element(),dataset:{territorialLayer:name}}));
  nodes['campo-territorio-data'].textContent=JSON.stringify({
    contexto:{features:[
      {geometry:polygon(-37,-9,-36,-8),properties:{nome:'Pesqueira',codigo:'2610905',selecionado:selected}},
      {geometry:polygon(-36,-9,-35,-8),properties:{nome:'Contexto',codigo:'2600000'}}]},
    geografia:{features:areas?[{geometry:polygon(-36.72,-8.36,-36.70,-8.34),properties:{
      estrato_codigo:'E1',area_codigo:'A1',levantamento_codigo:'L1',iip:25,cor:'#ff0000'}}]:[]},
    pontos:[{longitude:-36.71,latitude:-8.35,situacao:'INSPECIONADO',positivo_aedes:'SIM',bairro:'Demo'}]
  });
  vm.runInNewContext(source,{document:{getElementById:id=>nodes[id],
    querySelectorAll:()=>controls,createElement:element,createElementNS:element}});
  return {nodes,controls,svg:nodes['campo-territorio-svg'],status:nodes['campo-territorio-status'],
    click:name=>nodes['campo-territorio-'+name].handlers.click()};
}

function insideViewport(path) {
  const points=[...path.attributes.d.matchAll(/[ML](-?[\d.]+),(-?[\d.]+)/g)];
  return points.every(([,x,y])=>Number(x)>=0 && Number(x)<=1000 && Number(y)>=0 && Number(y)<=610);
}

test('visits without contours open with the entire municipality visible', () => {
  const x=map();
  assert.equal(insideViewport(x.svg.children[0]),true);
  assert.match(x.status.textContent,/Visão do município selecionado/);
  assert.match(x.status.textContent,/Sem contornos vinculados/);
  assert.equal(x.svg.children.filter(el=>el.attributes.class?.startsWith('campo-visita')).length,1);
});

test('close-up, municipal and state views remain distinct and reversible', () => {
  const x=map(); x.click('enquadrar');
  assert.equal(insideViewport(x.svg.children[0]),false);
  assert.match(x.status.textContent,/Visão aproximada do levantamento/);
  x.click('municipio'); assert.equal(insideViewport(x.svg.children[0]),true);
  x.click('estado'); assert.equal(x.svg.children.slice(0,2).every(insideViewport),true);
  assert.match(x.status.textContent,/Visão de Pernambuco continental/);
});

test('linked contours still open on the survey and layer controls retain visits', () => {
  const x=map({areas:true});
  assert.match(x.status.textContent,/1 contornos de planejamento.*Visão aproximada/);
  const area=x.svg.children.find(el=>el.attributes.class==='campo-contorno-iip');
  assert.equal(insideViewport(area),true); assert.equal(area.attributes.fill,'#ff0000');
  x.controls[0].checked=false; x.controls[0].handlers.change();
  assert.equal(x.svg.children.some(el=>el.attributes.class==='campo-contorno-iip'),false);
  assert.equal(x.svg.children.some(el=>el.attributes.class?.startsWith('campo-visita')),true);
});

test('missing municipal context leaves the close-up usable without inventing contours', () => {
  const x=map({selected:false});
  assert.equal(x.nodes['campo-territorio-municipio'].disabled,true);
  assert.match(x.status.textContent,/0 contornos de planejamento.*Visão aproximada/);
});
