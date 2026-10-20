const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/portal-mapa-vigilancia.js', 'utf8');
const geometry = {type: 'Polygon', coordinates: [[[-36.71,-8.36],[-36.69,-8.36],[-36.69,-8.34],[-36.71,-8.36]]]};

function browser(overrides = {}) {
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.attributes = {}; this.style = {}; this.handlers = {}; this.value = ''; this.textContent = ''; }
    replaceChildren(...children) { this.children = children; }
    append(...children) { this.children.push(...children); }
    setAttribute(name, value) { this.attributes[name] = value; }
    addEventListener(name, callback) { this.handlers[name] = callback; }
    change(value) { this.value = value; this.handlers.change?.(); }
    text() { return this.textContent + this.children.map(child => typeof child === 'string' ? child : child.text()).join(' '); }
  }
  const city = {type: 'Feature', geometry, properties: {nome: 'Pesqueira', codigo: '2610905'}};
  const data = {municipio: {name: 'Pesqueira', ibge: '2610905'}, demo: true, contexto: {features: [city]}, limite: city,
    filtros: {levantamento: 'L-POC'}, geografia: {features: [{type: 'Feature', geometry, properties: {cor: '#1e40af',
      levantamento_codigo: 'L-POC', estrato_codigo: 'E-01', area_codigo: 'A-01', iip: 25, imoveis_inspecionados: 16, imoveis_positivos: 4, imoveis_pendentes: 4}}]},
    liraa: {disponivel: true, visitas: 20, inicio: '2026-10-19', fim: '2026-10-20'},
    sinan: {doenca: 'Dengue', ano: 2026, total: 4, parcial: true, origem: 'Arquivo importado', classificacoes: [{rotulo: 'Confirmado', total: 4}]},
    focal: {disponivel: true, visitas: 5, inspecionados: 3, inicio: '2026-10-19', fim: '2026-10-20'}, ...overrides};
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element('div')); return elements.get(id); };
  get('portal-risco-data').textContent = JSON.stringify(data);
  get('portal-risco-camada').value = 'liraa'; get('portal-risco-area').value = 'municipio';
  vm.runInNewContext(source, {document: {getElementById: get, createElement: tag => new Element(tag), createElementNS: (_, tag) => new Element(tag), createTextNode: text => text}});
  return {get, data};
}

test('public map starts with the sampled area and never draws individual markers', () => {
  const ui = browser();
  assert.match(ui.get('risco-detalhe').text(), /IIP: 25%/);
  assert.match(ui.get('portal-risco-status').text(), /dados fictícios/);
  assert.equal(ui.get('risco-svg').children.filter(node => node.tag === 'path').length, 2);
  assert.equal(ui.get('risco-svg').children.some(node => node.tag === 'circle'), false);
});

test('switching to SINAN shows municipal counts, preserves partial status and hides sampled-area coloring', () => {
  const ui = browser();
  ui.get('portal-risco-camada').change('sinan');
  assert.equal(ui.get('portal-risco-area').disabled, true);
  assert.match(ui.get('risco-detalhe').text(), /4 registros no snapshot parcial/);
  assert.match(ui.get('risco-detalhe').text(), /Confirmado: 4/);
  assert.equal(ui.get('risco-svg').children.filter(node => node.tag === 'path').length, 1);
  ui.get('portal-risco-camada').change('focal');
  assert.match(ui.get('risco-detalhe').text(), /5 visitas confirmadas/);
});

test('empty sources are described as unavailable and do not become zero risk', () => {
  const ui = browser({geografia: {features: []}, liraa: {disponivel: false}, sinan: null, focal: {disponivel: false}});
  assert.match(ui.get('risco-detalhe').text(), /Ausência de dados não significa ausência de focos/);
  ui.get('portal-risco-camada').change('sinan');
  assert.match(ui.get('risco-detalhe').text(), /Nenhum snapshot disponível/);
  assert.doesNotMatch(ui.get('risco-detalhe').text(), /0 registros/);
});

test('switching demo mode resets the previous survey before submitting', () => {
  const ui = browser();
  ui.get('portal-risco-levantamento').value = 'L-POC';
  ui.get('portal-risco-modo').change('false');
  assert.equal(ui.get('portal-risco-levantamento').value, '');
});
