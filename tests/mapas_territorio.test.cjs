const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const territory=require('../app/static/js/uvis-territory.js');

function harness(){
 const element=()=>({value:'',checked:false,handlers:{},options:[],addEventListener(event,fn){this.handlers[event]=fn;},replaceChildren(...options){this.options=options;this.value=options[0]?.value||'';},append(option){this.options.push(option);}});
 const select=element(),enabled=element(),status=element(),load=element(),account=element(),tabs=[element(),element()];
 let onTerritoryChange,filters={crs:'NORTE',cnes:''};
 let area=false,fetches=0;const updates=[],drawn=[],territorialMaps=[];
 const areaOptions={hidden:true},panel={querySelector:()=>areaOptions},hosts=[{appendChild(node){node.host='heat';}},{appendChild(node){node.host='area';}}];
 const map=()=>({fits:[],fitBounds(value){this.fits.push(value);},getZoom:()=>16,getBounds:()=>({getSouthWest:()=>({lng:()=>-46.635,lat:()=>-23.552}),getNorthEast:()=>({lng:()=>-46.632,lat:()=>-23.549})})});
 const maps=[map(),map()];
 const root={dataset:{quadrasUrl:'/quadras'},querySelector:()=>({})};
 const nodes={'[data-map-territory]':root,'[data-map-quadra-select]':select,'[data-map-quadra-status]':status,'[data-map-quadras]':enabled,'[data-map-load-quadras]':load,'[data-map-display-panel]':panel,'#tabCalor [data-map-display-host]':hosts[0],'#tabArea [data-map-display-host]':hosts[1]};
 const feature={type:'Feature',id:'123',properties:{setor:'001',quadra:'002',subquadra:'001',tipo:'FISCAL'},geometry:{type:'Polygon',coordinates:[[[-46.635,-23.552],[-46.632,-23.552],[-46.632,-23.549],[-46.635,-23.549],[-46.635,-23.552]]]}};
 class Polygon {constructor(options){this.options=options;drawn.push(this);}addListener(){}setMap(map){this.options.map=map;}}
 const change=(next)=>{filters=next;onTerritoryChange(next);};
 const window={UvisTerritory:{...territory,create:(_,options)=>{onTerritoryChange=options.onChange;return {getFilters:()=>filters,async selectCode(cnes){change({crs:'NORTE',cnes});return true;},async resetFrame(){change({crs:'',cnes:''});},attachGoogle(map){territorialMaps.push(map);},fitGoogle(){}};}},__operationalMaps:maps,atualizarMapas:()=>updates.push({...window.mapTerritory.getFilters()})};
 const document={querySelector:selector=>nodes[selector],querySelectorAll:()=>tabs,getElementById:id=>id==='uvisFilter'?account:id==='tabArea'?{classList:{contains:()=>area}}:null,addEventListener(){}};
 vm.runInNewContext(fs.readFileSync('app/static/js/mapas-territorio.js','utf8'),{window,document,google:{maps:{Polygon}},Option:class{constructor(text,value){this.value=value;}},AbortController,URLSearchParams,fetch:async()=>{fetches++;return{ok:true,json:async()=>({type:'FeatureCollection',features:[feature]})};}});
 return {select,load,account,change,window,updates,drawn,territorialMaps,maps,panel,fetches:()=>fetches,switchTab(value){area=value;tabs[value?1:0].handlers['shown.bs.tab']();}};
}

test('a quadra selected in Areas never narrows Heat and is restored when returning',async()=>{
 const h=harness();h.switchTab(true);await h.load.handlers.click();h.select.value='123';h.select.handlers.change();
 assert.equal(h.window.mapTerritory.getFilters().quadra,'123');assert.equal(h.panel.host,'area');
 h.switchTab(false);
 assert.equal(h.window.mapTerritory.getFilters().quadra,'');assert.equal(h.panel.host,'heat');
 assert.equal(h.select.value,'123');
 h.switchTab(true);assert.equal(h.window.mapTerritory.getFilters().quadra,'123');assert.equal(h.updates.length,0);
});

test('territorial and quadra edits only prepare filters, without requesting records',async()=>{
 const h=harness();h.change({crs:'SUL',cnes:''});assert.equal(h.updates.length,0);
 h.switchTab(true);await h.load.handlers.click();h.select.value='123';h.select.handlers.change();
 h.switchTab(false);assert.equal(h.updates.length,0);
});

test('the explicit filter action links a registered UVIS and clearing it removes only that automatic selection',async()=>{
 const h=harness();h.account.value='42';h.account.selectedOptions=[{dataset:{territoryCnes:'0314307'}}];
 assert.equal(h.window.mapTerritory.getFilters().cnes,'');
 await Promise.all([h.window.mapTerritory.syncAccountFilter(),h.window.mapTerritory.syncAccountFilter()]);
 assert.equal(h.window.mapTerritory.getFilters().cnes,'0314307');assert.equal(h.updates.length,0);
 h.account.value='';h.account.selectedOptions=[];await h.window.mapTerritory.syncAccountFilter();
 assert.equal(h.window.mapTerritory.getFilters().cnes,'');assert.equal(h.updates.length,0);
 h.account.value='42';h.account.selectedOptions=[{dataset:{territoryCnes:'0314307'}}];await h.window.mapTerritory.syncAccountFilter();
 h.change({crs:'SUL',cnes:'9999999'});h.account.value='';h.account.selectedOptions=[];await h.window.mapTerritory.syncAccountFilter();
 assert.equal(h.window.mapTerritory.getFilters().cnes,'9999999');
});

test('quadra loading and contours belong only to the Areas map',async()=>{
 const h=harness();await h.load.handlers.click();assert.equal(h.fetches(),0);
 assert.deepEqual(h.territorialMaps,h.maps);
 h.switchTab(true);await h.load.handlers.click();assert.equal(h.fetches(),1);
 assert.equal(h.drawn.length,1);assert.equal(h.drawn[0].options.map,h.maps[1]);
 h.select.value='123';h.select.handlers.change();assert.equal(h.maps[0].fits.length,0);assert.equal(h.maps[1].fits.length,1);
});
