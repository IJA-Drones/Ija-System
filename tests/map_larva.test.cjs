const test=require('node:test');const assert=require('node:assert/strict');
const larva=require('../app/static/js/map-larva.js');
const territory=require('../app/static/js/uvis-territory.js');
const data=require('node:fs').readFileSync('app/static/data/uvis-sao-paulo/uvis.geojson','utf8');
const features=JSON.parse(data).features;
test('unknown answers never become no larva and positive wins conflicting orders',()=>{
 assert.equal(larva.state({ordens:[{larvas:'Não'},{larvas:' SIM '}]}),'SIM');
 assert.equal(larva.state({ordens:[{larvas:'Não'}]}),'NAO');
 for(const value of ['',null,'não informado','outro'])assert.equal(larva.state({larva_visualizada:value}),'NAO_INFORMADO');
 assert.notEqual(larva.states.NAO.color,larva.states.NAO_INFORMADO.color);
 assert.notEqual(larva.states.SIM.color,larva.states.NAO.color);
});
test('coordenadoria names, region aliases and UVIS searches are accent-insensitive',()=>{
 const regions=[...new Set(features.map(f=>f.properties.crs))];
 assert.equal(territory.regionFromSearch(regions,'Coordenadoria Regional de Saúde Norte'),'NORTE');
 assert.equal(territory.regionFromSearch(regions,'crs sul'),'SUL');
 assert.equal(territory.searchFeatures(features,'Norte').length,9);
 assert.equal(territory.selectedFeatures(features,'','NORTE').length,9);
 assert.equal(territory.searchFeatures(features,'UVIS Sé')[0].properties.cnes,'0314307');
 assert.equal(territory.searchFeatures(features,'Jaçanã')[0].properties.uvis,'JACANA/TREMEMBE');
 assert.equal(territory.searchFeatures(features,'não existe').length,0);
});
