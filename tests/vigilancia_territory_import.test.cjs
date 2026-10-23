const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/vigilancia-territorio-import.js', 'utf8');

function ui() {
  const node = () => ({handlers:{},dataset:{},files:[],checked:false,required:false,disabled:false,textContent:'',
    addEventListener(name,fn){this.handlers[name]=fn;},focus(){this.focused=true;}});
  const form=node(), file=node(), confirmation=node(), label=node(), status=node(), submit=node();
  form.querySelector=()=>submit;
  const nodes={'territorio-csv-form':form,'territorio-csv':file,'territorio-csv-confirmado':confirmation,
    'territorio-csv-confirmacao':label,'territorio-csv-status':status};
  vm.runInNewContext(source,{document:{getElementById:id=>nodes[id]}});
  return {file,confirmation,label,status,submit,
    change(selected){file.files=selected?[selected]:[];return file.handlers.change();},
    send(){let blocked=false;form.handlers.submit({preventDefault(){blocked=true;}});return blocked;}};
}
const csv=text=>({slice(){return {text:async()=>text};}});

test('a polygon CSV requires confirmation before any submission, without Maps',async()=>{
  const x=ui(); await x.change(csv('\uFEFFquarteirao;bairro;geometria\r\nQ;B;{}'));
  assert.equal(x.confirmation.required,true);assert.equal(x.label.dataset.required,'true');
  assert.match(x.status.textContent,/Marque a confirmação/);assert.equal(x.send(),true);
  x.confirmation.checked=true;x.confirmation.handlers.change();
  assert.equal(x.send(),false);assert.equal(x.status.textContent,'');
});

test('a CSV without polygon columns remains importable without that confirmation',async()=>{
  const x=ui();await x.change(csv('quarteirao;bairro;area;imoveis;referencia\nQ;B;A;10;DEMO'));
  assert.equal(x.confirmation.required,false);assert.equal(x.send(),false);
});

test('selecting another file clears the previous confirmation',async()=>{
  const x=ui();await x.change(csv('quarteirao;geometria'));
  x.confirmation.checked=true;
  await x.change(csv('"quarteirao","geometria"\n"Q","{}"'));
  assert.equal(x.confirmation.checked,false);assert.equal(x.confirmation.required,true);
  assert.equal(x.send(),true);
});

test('pending and unreadable files block submission until a successful read',async()=>{
  const x=ui();let resolve;
  const read=x.change({slice(){return {text:()=>new Promise(done=>{resolve=done;})};}});
  assert.equal(x.submit.disabled,true);assert.equal(x.send(),true);
  resolve('quarteirao;geometria');await read;
  await x.change({slice(){return {text:async()=>{throw Error('unreadable');}};}});
  assert.equal(x.send(),true);assert.match(x.status.textContent,/Não foi possível ler/);
  await x.change(csv('quarteirao;bairro'));
  assert.equal(x.send(),false);assert.equal(x.submit.disabled,false);
});

test('removing the file fences a late header result',async()=>{
  const x=ui();let resolve;
  const read=x.change({slice(){return {text:()=>new Promise(done=>{resolve=done;})};}});
  await x.change(null);resolve('quarteirao;geometria');await read;
  assert.equal(x.confirmation.required,false);assert.equal(x.submit.disabled,false);
  assert.equal(x.label.dataset.required,'false');
});
