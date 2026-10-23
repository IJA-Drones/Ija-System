const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/vigilancia-validacao.js', 'utf8');

function ui() {
  const pending = [], events = {};
  const element = value => ({value, disabled:false, dataset:{}, children:[], attributes:{}, handlers:{},
    addEventListener(name, handler) { (this.handlers[name] ||= []).push(handler); },
    replaceChildren(...children) {this.children = children;}, append(child) {this.children.push(child);},
    setAttribute(name,value) {this.attributes[name]=value;}, removeAttribute(name) {delete this.attributes[name];},
    get options(){return this.children;},focus(){this.focused=true;}});
  const form = element('');
  const city = element('7'), mode = element('true'), dest = element('ANTERIOR'), status = element('');
  dest.dataset.listUrl = '/vigilancia/importacoes/levantamentos';
  dest.closest = () => form;
  dest.children=[element(''),element('ANTERIOR')];
  const file=element(''),link=element('');file.files=[];link.dataset.planningUrl='/vigilancia/planejamento';
  const nodes = {'prefeitura-id':city,'campo-demo':mode,'campo-levantamento-destino':dest,'campo-levantamento-status':status,
    'arquivo-csv':file,'campo-planejamento-link':link};
  const document = {getElementById:id=>nodes[id] || null,createElement:()=>element('')};
  const fetch = (url,options) => new Promise(resolve => pending.push({url,options,resolve}));
  vm.runInNewContext(source,{document,fetch,AbortController,URLSearchParams});
  const change = control => control.handlers.change.at(-1)();
  const submit = () => {let blocked=false;form.handlers.submit[0]({preventDefault(){blocked=true;}});return blocked;};
  return {city,mode,dest,status,pending,change,submit,file,link};
}
const reply = rows => ({ok:true,json:async()=>({levantamentos:rows})});
const plan = codigo => ({codigo,titulo:'Levantamento '+codigo,inicio:'20/10/2026',fim:'23/10/2026'});

test('scope change clears destination and file submission waits for the scoped list', async () => {
  const x=ui(); x.city.value='8';
  const loading=x.change(x.city);
  assert.equal(x.dest.value,''); assert.equal(x.dest.disabled,true); assert.equal(x.submit(),true);
  assert.equal(x.pending[0].url,'/vigilancia/importacoes/levantamentos?prefeitura_id=8&demo=true');
  x.pending[0].resolve(reply([plan('NOVO')])); await loading;
  assert.equal(x.dest.disabled,false); assert.equal(x.dest.children[1].value,'NOVO');
  assert.equal(x.submit(),false);
});

test('a stale demo response cannot overwrite the authorized-data list', async () => {
  const x=ui(); const first=x.change(x.city);
  x.mode.value='false'; const second=x.change(x.mode);
  assert.equal(x.pending[0].options.signal.aborted,true);
  x.pending[1].resolve(reply([plan('AUTORIZADO')])); await second;
  x.pending[0].resolve(reply([plan('DEMO')])); await first;
  assert.deepEqual(x.dest.children.map(p=>p.value),['','AUTORIZADO']);
  assert.equal(x.dest.disabled,false);
});

test('empty city cancels a request without reviving the previous selection', async () => {
  const x=ui(); const first=x.change(x.city);
  x.city.value=''; await x.change(x.city);
  x.pending[0].resolve(reply([plan('ANTIGO')])); await first;
  assert.deepEqual(x.dest.children.map(p=>p.value),['']);
  assert.equal(x.dest.disabled,false); assert.match(x.status.textContent,/Selecione a prefeitura/);
});

test('failure blocks accidental fallback; a successful retry restores submission', async () => {
  const x=ui(); const first=x.change(x.city);
  x.pending[0].resolve({ok:false}); await first;
  assert.equal(x.submit(),true); assert.equal(x.dest.value,'');
  const second=x.change(x.mode); x.pending[1].resolve(reply([])); await second;
  assert.equal(x.submit(),false); assert.match(x.status.textContent,/Nenhum levantamento liberado/);
});

const csvFile = text => ({slice(){return {text:async()=>text};}});

test('the period link follows the selected survey and resets with the selection', () => {
  const x=ui(); x.dest.value='L-2026-01'; x.change(x.dest);
  assert.equal(x.link.href,'/vigilancia/planejamento?demo=true&prefeitura_id=7&plano=L-2026-01#periodo-levantamento');
  assert.match(x.link.textContent,/ampliar período/);
  x.dest.value=''; x.change(x.dest);
  assert.equal(x.link.href,'/vigilancia/planejamento?demo=true&prefeitura_id=7');
  assert.equal(x.link.textContent,'Abrir planejamento');
});

test('planned visits require a deliberate destination before upload; legacy CSV stays optional', async () => {
  const x=ui(); x.dest.value='';
  x.file.files=[csvFile('\uFEFF"municipio_id";"quarteirao_codigo";"levantamento_codigo"\n7;Q1;CODIGO-ANTIGO')];
  await x.change(x.file);
  assert.equal(x.dest.required,true);assert.equal(x.submit(),true);
  assert.equal(x.dest.focused,true);assert.match(x.status.textContent,/Selecione o levantamento de destino/);
  x.dest.value='ANTERIOR';x.change(x.dest);assert.equal(x.submit(),false);
  x.file.files=[csvFile('municipio_id,origem,levantamento_codigo\n7,FOCAL,')];
  await x.change(x.file);x.dest.value='';
  assert.equal(x.dest.required,false);assert.equal(x.submit(),false);
});

test('no released plan guides planned CSV to the scoped planning page instead of posting', async () => {
  const x=ui();const loading=x.change(x.city);x.pending[0].resolve(reply([]));await loading;
  x.file.files=[csvFile('municipio_id,quarteirao_codigo\n7,Q1')];await x.change(x.file);
  assert.equal(x.submit(),true);assert.match(x.status.textContent,/complete a amostra e libere/);
  assert.equal(x.link.href,'/vigilancia/planejamento?demo=true&prefeitura_id=7');
  x.city.value='8';x.mode.value='false';const other=x.change(x.mode);
  x.pending[1].resolve(reply([]));await other;
  assert.equal(x.link.href,'/vigilancia/planejamento?demo=false&prefeitura_id=8');
});

test('file read race cannot revive planned requirements after removing the file', async () => {
  const x=ui();let resolve;
  x.file.files=[{slice(){return {text:()=>new Promise(done=>{resolve=done;})};}}];
  const loading=x.change(x.file);assert.equal(x.submit(),true);
  x.file.files=[];await x.change(x.file);
  resolve('municipio_id,quarteirao_codigo');await loading;
  assert.equal(x.dest.required,false);assert.equal(x.submit(),false);
});

test('read failure blocks submission until a readable file is selected', async () => {
  const x=ui();x.file.files=[{slice(){return {text:async()=>{throw new Error('unreadable');}};}}];
  await x.change(x.file);assert.equal(x.submit(),true);assert.match(x.status.textContent,/Selecione o CSV novamente/);
  x.file.files=[csvFile('municipio_id,origem')];await x.change(x.file);assert.equal(x.submit(),false);
});
