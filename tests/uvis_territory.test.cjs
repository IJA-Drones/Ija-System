const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const api=require('../app/static/js/uvis-territory.js');
const collection=JSON.parse(fs.readFileSync('app/static/data/uvis-sao-paulo/uvis.geojson','utf8'));

test('UVIS selection isolates one territory by stable CNES, including its leading zero',()=>{
 const features=api.selectedFeatures(collection.features,'0314307');
 assert.equal(features.length,1);assert.equal(features[0].properties.uvis,'SE');
 assert.equal(api.selectedFeatures(collection.features,'missing').length,0);
 assert.equal(api.selectedFeatures(collection.features,'').length,28);
 const b=api.bounds(features);assert(b.west < b.east && b.south < b.north);
 assert(api.positions(features[0]).length>0);
});
test('territory colors identify every UVIS and remain stable across filtered views',()=>{
 assert.equal(new Set(collection.features.map(api.territoryColor)).size,28);
 const se=api.selectedFeatures(collection.features,'0314307')[0];
 assert.equal(api.territoryColor(se),api.territoryColor(api.selectedFeatures(collection.features,'','NORTE').find(f=>f.properties.cnes==='0314307')));
 assert.equal(api.territoryColor({properties:{cor:'invalid'}}),'#1a4a7c');
});


test('territory names appear only after zooming in, with plain map label text',()=>{
 for(const zoom of [0,9,10,11,11.99,NaN,undefined])assert.equal(api.labelVisible(zoom),false);
 for(const zoom of [12,13,16])assert.equal(api.labelVisible(zoom),true);
 assert.equal(api.labelText('SE'),'Sé');
 assert.equal(api.labelText('CASA VERDE/CACHOEIRINHA'),'Casa Verde / Cachoeirinha');
});
