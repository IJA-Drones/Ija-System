const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app/static/js/portal-chat-mobile.js'), 'utf8');

test('chat follows visible viewport when keyboard opens, pans, and closes', () => {
  const values = {}, events = {};
  const viewport = {height:844, offsetTop:0, addEventListener:(name, fn)=>{events[name]=fn;}};
  const root = {style:{setProperty:(key,value)=>{values[key]=value;}}};
  vm.runInNewContext(source,{document:{querySelector:()=>root},window:{visualViewport:viewport,addEventListener(){}}});
  assert.equal(values['--chat-viewport-height'],'844px');
  viewport.height=390; viewport.offsetTop=120; events.resize();
  assert.equal(values['--chat-viewport-height'],'390px');
  assert.equal(values['--chat-viewport-top'],'120px');
  viewport.offsetTop=160; events.scroll();
  assert.equal(values['--chat-viewport-top'],'160px');
  viewport.height=844; viewport.offsetTop=0; events.resize();
  assert.equal(values['--chat-viewport-height'],'844px');
  assert.equal(values['--chat-viewport-top'],'0px');
});
test('falls back to window height without VisualViewport', () => {
  const values = {};
  vm.runInNewContext(source,{document:{querySelector:()=>({style:{setProperty:(k,v)=>{values[k]=v;}}})},window:{innerHeight:568,addEventListener(){}}});
  assert.equal(values['--chat-viewport-height'],'568px');
});
