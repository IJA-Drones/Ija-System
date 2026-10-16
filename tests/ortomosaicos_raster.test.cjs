const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function setup() {
  const layers = new Set(), created = [], notices = [];
  class Source {
    constructor(options) {this.options=options;this.events={};this.state='ready';created.push(this);}
    on(event, fn) {(this.events[event] ||= []).push(fn);}
    emit(event) {(this.events[event] || []).forEach(fn=>fn());}
    getState() {return this.state;}
    getView() {return new Promise((resolve,reject)=>{this.resolve=resolve;this.reject=reject;});}
    dispose() {this.disposed=true;}
  }
  class Layer {
    constructor(options) {this.options=options;this.visible=options.visible;}
    setVisible(value) {this.visible=value;}
    set(key,value) {this[key]=value;}
    dispose() {this.disposed=true;}
  }
  const map = {addLayer:l=>layers.add(l),removeLayer:l=>layers.delete(l)};
  const context = {window:{},ol:{source:{GeoTIFF:Source},layer:{WebGLTile:Layer}}};
  vm.runInNewContext(fs.readFileSync('app/static/js/ortomosaicos-raster.js','utf8'),context);
  const cache=context.window.createOrthoRasterCache({map,onStatus:e=>notices.push(e.status)});
  return {cache,created,layers,notices};
}
const item=(id=1,version='a',prefeitura_id=1)=>({id,prefeitura_id,arquivo_url:`/${id}.tif?v=${version}`,tipo:'rgb',status:'pronto'});
test('turning the reference off and on reuses decoded tiles and the source',()=>{
  const h=setup(),first=h.cache.acquire(item());first.layer.setVisible(true);
  assert.equal(h.cache.release(first.layer),true);assert.equal(first.layer.visible,false);
  assert.equal(h.cache.acquire(item()),first);assert.equal(h.created.length,1);
  assert.equal(first.source.disposed,undefined);
  assert.equal(first.source.options.convertToRGB,false); // Preserve RGBA transparency.
  assert.equal(first.source.options.sourceOptions.allowFullFile,false);
});
test('keeps only two recent rasters; frees GPU and source on eviction',()=>{
  const h=setup(),a=h.cache.acquire(item(1)),b=h.cache.acquire(item(2));
  h.cache.acquire(item(1));h.cache.acquire(item(3));
  assert.equal(b.layer.disposed,true);assert.equal(b.source.disposed,true);
  assert.equal(a.layer.disposed,undefined);assert.equal(h.layers.size,2);
  h.cache.dispose();assert.equal(h.layers.size,0);assert.equal(a.source.disposed,true);
});
test('a replacement COG URL invalidates the old raster for the same record',()=>{
  const h=setup(),old=h.cache.acquire(item());const next=h.cache.acquire(item(1,'b'));
  assert.notEqual(old,next);assert.equal(old.layer.disposed,true);assert.equal(h.layers.size,1);
});
test('filter changes discard references absent from the authorized list',()=>{
  const h=setup(),a=h.cache.acquire(item(1)),b=h.cache.acquire(item(2));
  h.cache.retain([item(2)]);assert.equal(a.source.disposed,true);assert.equal(b.source.disposed,undefined);
  h.cache.retain([{...item(2),prefeitura_id:2}]);assert.equal(b.source.disposed,true);
});
test('status waits for tiles; metadata alone does not announce a loaded image',async()=>{
  const h=setup(),e=h.cache.acquire(item());e.source.resolve({});await Promise.resolve();
  assert.equal(e.status,'loading');e.source.emit('tileloadstart');e.source.emit('tileloadstart');
  e.source.emit('tileloadend');assert.equal(e.status,'loading');e.source.emit('tileloadend');assert.equal(e.status,'ready');
});
test('failed tiles remain errors and selecting again creates a fresh source',()=>{
  const h=setup(),e=h.cache.acquire(item());e.source.emit('tileloadstart');e.source.emit('tileloaderror');e.source.emit('tileloadend');
  assert.equal(e.status,'error');assert.equal(e.layer.loadError,true);
  const fresh=h.cache.acquire(item());assert.notEqual(fresh,e);assert.equal(e.source.disposed,true);
});
test('metadata failure is caught; disposed sources cannot emit stale UI status',async()=>{
  const h=setup(),e=h.cache.acquire(item());e.source.reject(Error('network'));await Promise.resolve();
  assert.equal(e.status,'error');h.cache.dispose();const count=h.notices.length;e.source.emit('tileloaderror');
  assert.equal(h.notices.length,count);
});
