const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/js/portal-chat-report.js'), 'utf8');
class Element {
  constructor() { this.childNodes=[]; this.listeners={}; this.dataset={}; this.hidden=false; this.value=''; this.selectors={}; this.name=''; }
  append(...nodes) { for(const node of nodes) { node.remove(); this.childNodes.push(node); node.parentNode=this; } }
  remove() { if(this.parentNode) { const items=this.parentNode.childNodes; items.splice(items.indexOf(this),1); this.parentNode=null; } }
  insertBefore(node, before) { node.remove(); const i=before?this.childNodes.indexOf(before):this.childNodes.length; if(i<0) throw Error('Wrong parent'); this.childNodes.splice(i,0,node); node.parentNode=this; }
  before(node) { this.parentNode.insertBefore(node,this); }
  replaceWith(...nodes) { nodes.forEach(node=>this.before(node)); this.remove(); }
  replaceChildren(...nodes) { [...this.childNodes].forEach(node=>node.remove()); this.append(...nodes); }
  querySelector(selector) { return this.selectors[selector] || null; }
  querySelectorAll(selector) {
    if(this.selectors[selector]) return this.selectors[selector];
    return this.childNodes.flatMap(node=>[...(node.name?[node]:[]), ...node.querySelectorAll(selector)]);
  }
  addEventListener(name,fn) { this.listeners[name]=fn; }
  setAttribute() {}
  focus() {}
  checkValidity() { return this.valid !== false; }
  reportValidity() { this.reported=true; }
}
function setup() {
  const root=new Element(), form=new Element(), home=new Element(), chat=new Element();
  const keys=['[data-report]','[data-report-form]','[data-report-review]','[data-report-title]','[data-report-help]','[data-report-progress]','[data-report-feedback]','[data-report-next]','[data-report-back]','[data-report-exit]','.portal-chat-messages','.portal-chat-links','.portal-chat-panel','.portal-chat-toggle','[data-start-report]'];
  keys.forEach(key=>root.selectors[key]=new Element()); root.selectors.form=chat;
  chat.selectors.button=new Element(); chat.selectors.textarea=new Element();
  const fieldsets=Array.from({length:4},()=>new Element());
  form.selectors[':scope > fieldset']=fieldsets;
  const dependent=new Element(), consent=new Element(), footer=new Element(), feedback=new Element();
  Object.assign(form.selectors,{'#portalCidadaoDependentFields':dependent,'.portal-cidadao-consent':consent,'.portal-cidadao-form-footer':footer,'#portalCidadaoFeedback':feedback,'[data-tipo-visita]':new Element()});
  const inputs={};
  for(const [name,index] of [['tipo_visita',0],['foco',0],['logradouro',1],['nome',2],['cpf',2],['midias',3],['consentimento',4]]) {
    const input=new Element(); input.name=name; input.value=name==='tipo_visita'?'Aedes':'teste'; input.files=[];
    inputs[name]=input; form.selectors[`[name="${name}"]`]=input;
    (index===4?consent:fieldsets[index]).append(input);
  }
  consent.querySelectorAll=()=>[inputs.consentimento];
  form.append(fieldsets[0],dependent,...fieldsets.slice(1),consent,footer,feedback); home.append(form);
  let submitted=0;
  form.requestSubmit=()=>{submitted++; form.dataset.submitting='true';};
  const document={querySelector:()=>root,getElementById:()=>form,createElement:()=>new Element()};
  class Data { get(name) { return inputs[name]?.value || ''; } }
  vm.runInNewContext(source,{document,FormData:Data});
  return {root,form,home,inputs,get submitted(){return submitted;},click(key){root.selectors[key].listeners.click();}};
}
test('five stages require review and consent before using the existing submit handler',()=>{
  const ui=setup(); ui.click('[data-start-report]');
  assert.equal(ui.form.dataset.chatReport,'true');
  assert.equal(ui.form.parentNode,ui.root.selectors['[data-report-form]']);
  ui.inputs.logradouro.valid=false;
  ui.click('[data-report-next]'); ui.click('[data-report-next]');
  assert.equal(ui.root.selectors['[data-report-progress]'].textContent,'Etapa 2 de 5');
  assert.equal(ui.submitted,0);
  ui.inputs.logradouro.valid=true;
  ui.click('[data-report-next]'); ui.click('[data-report-next]'); ui.click('[data-report-next]');
  assert.equal(ui.root.selectors['[data-report-progress]'].textContent,'Etapa 5 de 5');
  assert.equal(ui.root.selectors['[data-report-review]'].parentNode,ui.form);
  ui.inputs.consentimento.valid=false; ui.click('[data-report-next]'); assert.equal(ui.submitted,0);
  ui.inputs.consentimento.valid=true; ui.click('[data-report-next]'); ui.click('[data-report-next]');
  assert.equal(ui.submitted,1); assert.equal(ui.form.dataset.reportConfirmed,'true');
  ui.form.listeners['portal:report-success']({detail:{protocolo:'TEST-123'}});
  assert.equal(ui.root.selectors['[data-report-feedback]'].textContent,'Protocolo: TEST-123');
  assert.equal(ui.root.selectors['[data-report-next]'].hidden,true);
});
test('leaving preserves the same form and draft; reopening works',()=>{
  const ui=setup(); const input=ui.inputs.nome; input.value='Rascunho';
  ui.click('[data-start-report]'); ui.click('[data-report-exit]');
  assert.equal(ui.form.parentNode,ui.home); assert.equal(input.value,'Rascunho');
  assert.equal(ui.form.dataset.chatReport,undefined);
  ui.click('[data-start-report]'); assert.equal(ui.form.dataset.chatReport,'true');
  ui.click('[data-report-next]'); ui.click('[data-report-next]'); ui.click('[data-report-next]'); ui.click('[data-report-next]');
  assert.equal(ui.root.selectors['[data-report-progress]'].textContent,'Etapa 5 de 5');
});
test('server validation errors return to the relevant step without claiming success',()=>{
  const ui=setup(); ui.click('[data-start-report]');
  for(let i=0;i<5;i++) ui.click('[data-report-next]');
  ui.form.listeners['portal:report-error']({detail:{errors:{cpf:'CPF inválido'},message:'CPF inválido'}});
  assert.equal(ui.root.selectors['[data-report-progress]'].textContent,'Etapa 3 de 5');
  assert.equal(ui.root.selectors['[data-report-feedback]'].textContent,'CPF inválido');
  assert.equal(ui.root.selectors['[data-report-next]'].disabled,false);
});
