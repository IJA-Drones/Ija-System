const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const {intersects}=require('../app/static/js/municipal-satellite.js');

test('municipal highlight is limited to views intersecting São Paulo',()=>{
 const sp={west:-46.83,south:-24.01,east:-46.36,north:-23.35};
 assert.equal(intersects({west:-46.7,south:-23.6,east:-46.5,north:-23.5},sp),true);
 assert.equal(intersects({west:-35,south:-9,east:-34,north:-8},sp),false);
});

test('surroundings toggle removes only the mask, preserving both map cameras',async()=>{
 const checkbox={checked:false,addEventListener(_,fn){this.change=fn;}};
 const pois={checked:false,addEventListener(_,fn){this.change=fn;}};
 const status={textContent:''};
 const root={dataset:{maskUrl:'/public-mask'},querySelector:s=>s.includes('surroundings')?checkbox:s.includes('pois')?pois:status};
 const layers=[];
 class Data {
   constructor(){layers.push(this);}
   addGeoJson(value){this.geo=value;}
   setStyle(value){this.style=value;}
   setMap(value){this.map=value;}
 }
 const window={google:{maps:{Data}}};
 const document={querySelector:()=>root,addEventListener(){}};
 const geo={type:'FeatureCollection',features:[],metadata:{limite_bbox:[-46.83,-24.01,-46.36,-23.35]}};
 vm.runInNewContext(fs.readFileSync('app/static/js/municipal-satellite.js','utf8'),{window,document,Map,fetch:async()=>({ok:true,json:async()=>geo})});
 const controller=window.MunicipalSatellite.create(root);
 const maps=[0,1].map(()=>({
   listeners:{},get(){return[];},setOptions(value){this.options=value;},setMapTypeId(value){this.type=value;},addListener(event,fn){this.listeners[event]=fn;},
   getBounds:()=>({getSouthWest:()=>({lng:()=>-46.7,lat:()=>-23.6}),getNorthEast:()=>({lng:()=>-46.5,lat:()=>-23.5})})
 }));
 maps.forEach(m=>controller.attach(m));
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(layers.length,2);
 layers.forEach((layer,i)=>assert.equal(layer.map,maps[i]));
 checkbox.checked=true;checkbox.change();
 layers.forEach(layer=>assert.equal(layer.map,null));
 checkbox.checked=false;checkbox.change();
 layers.forEach((layer,i)=>assert.equal(layer.map,maps[i]));
 maps[0].getBounds=()=>({getSouthWest:()=>({lng:()=>-35,lat:()=>-9}),getNorthEast:()=>({lng:()=>-34,lat:()=>-8})});
 maps[0].listeners.idle();
 assert.equal(layers[0].map,null);
 assert.equal(layers[1].map,maps[1]);
 maps.forEach(map=>assert.equal(map.options.clickableIcons,false));
 maps.forEach(map=>assert.equal(map.options.styles[0].featureType,'poi'));
 pois.checked=true;pois.change();
 maps.forEach(map=>{assert.equal(map.options.clickableIcons,true);assert.equal(map.options.styles.length,0);});
});

test('coordinator changes replace the white mask and stale downloads cannot restore another region',async()=>{
 const control=()=>({checked:false,addEventListener(_,fn){this.change=fn;}});
 const checkbox=control(),pois=control(),status={};
 const root={dataset:{maskUrl:'/municipio',regionMaskBase:'/ref/'},querySelector:s=>s.includes('surroundings')?checkbox:s.includes('pois')?pois:status};
 const responses=new Map(),layers=[];
 const json=crs=>({type:'FeatureCollection',features:[{properties:{crs}}],metadata:{limite_bbox:[-46.9,-24.1,-46.3,-23.25]}});
 class Data {
  constructor(){layers.push(this);} addGeoJson(value){this.geo=value;} setStyle(value){this.style=value;} setMap(value){this.map=value;}
 }
 const window={google:{maps:{Data}}};
 vm.runInNewContext(fs.readFileSync('app/static/js/municipal-satellite.js','utf8'),{
  window,document:{querySelector:()=>null},Map,Set,fetch:url=>new Promise(resolve=>responses.set(url,crs=>resolve({ok:true,json:async()=>json(crs)})))
 });
 const controller=window.MunicipalSatellite.create(root);
 const map={get:()=>[],setOptions(){},setMapTypeId(){},addListener(){},getBounds:()=>null};
 controller.attach(map);responses.get('/municipio')('');await new Promise(resolve=>setImmediate(resolve));
 const north=controller.setRegion('NORTE'),south=controller.setRegion('SUL');
 responses.get('/ref/mascara-sul.geojson?v=20261119-3')('SUL');await south;
 responses.get('/ref/mascara-norte.geojson?v=20261119-3')('NORTE');await north;
 const active=()=>layers.filter(layer=>layer.map===map);
 assert.equal(active().length,1);assert.equal(active()[0].geo.features[0].properties.crs,'SUL');
 assert.equal(active()[0].style.fillOpacity,1);
 checkbox.checked=true;checkbox.change();assert.equal(active().length,0);
 checkbox.checked=false;checkbox.change();assert.equal(active()[0].geo.features[0].properties.crs,'SUL');
 await controller.setRegion('');assert.equal(active().length,1);assert.equal(active()[0].geo.features[0].properties.crs,'');
});

test('UVIS takes priority over its coordinator, preserves leading zeros and discards stale masks',async()=>{
 const checkbox={checked:false,addEventListener(_,fn){this.change=fn;}},status={};
 const root={dataset:{maskUrl:'/municipio',regionMaskBase:'/ref/'},querySelector:s=>s.includes('surroundings')?checkbox:s.includes('pois')?null:status};
 const responses=new Map(),layers=[];
 class Data {constructor(){layers.push(this);}addGeoJson(value){this.geo=value;}setStyle(value){this.style=value;}setMap(value){this.map=value;}}
 const window={google:{maps:{Data}}};
 vm.runInNewContext(fs.readFileSync('app/static/js/municipal-satellite.js','utf8'),{
  window,document:{querySelector:()=>null},Map,Set,fetch:url=>new Promise(resolve=>responses.set(url,props=>resolve({ok:true,json:async()=>({type:'FeatureCollection',features:[{properties:props}],metadata:{limite_bbox:[-46.9,-24.1,-46.3,-23.25]}})})))
 });
 const controller=window.MunicipalSatellite.create(root);
 const map={get:()=>[],setOptions(){},setMapTypeId(){},addListener(){},getBounds:()=>null};controller.attach(map);
 responses.get('/municipio')({nome:'São Paulo'});await new Promise(resolve=>setImmediate(resolve));
 const region=controller.setTerritory({crs:'NORTE'}),uvis=controller.setTerritory({crs:'NORTE',cnes:'0314307'});
 responses.get('/ref/mascara-uvis-0314307.geojson?v=20261119-1')({cnes:'0314307',uvis:'SE',crs:'NORTE'});await uvis;
 responses.get('/ref/mascara-norte.geojson?v=20261119-3')({crs:'NORTE'});await region;
 const active=()=>layers.filter(layer=>layer.map===map);
 assert.equal(active().length,1);assert.equal(active()[0].geo.features[0].properties.cnes,'0314307');assert.equal(active()[0].style.fillOpacity,1);
 assert.match(status.textContent,/UVIS SE em destaque/);
 checkbox.checked=true;checkbox.change();assert.equal(active().length,0);
 checkbox.checked=false;checkbox.change();assert.equal(active()[0].geo.features[0].properties.cnes,'0314307');
 await controller.setTerritory({crs:'NORTE'});assert.equal(active()[0].geo.features[0].properties.crs,'NORTE');assert.equal(active()[0].geo.features[0].properties.cnes,undefined);
 await controller.setTerritory({});assert.equal(active()[0].geo.features[0].properties.nome,'São Paulo');
});
