/* Local territorial masks and Google basemap presentation. No imagery downloads. */
(function(scope){
  'use strict';
  const REGIONS=new Set(['LESTE','NORTE','OESTE','SUDESTE','SUL']);
  const HIDDEN_PLACES=[{featureType:'poi',elementType:'labels',stylers:[{visibility:'off'}]},
    {featureType:'transit',elementType:'labels',stylers:[{visibility:'off'}]}];
  function intersects(a,b){return a.east>=b.west && a.west<=b.east && a.north>=b.south && a.south<=b.north;}
  function create(root){
    const checkbox=root.querySelector('[data-satellite-surroundings]'),status=root.querySelector('[data-satellite-status]');
    const pois=root.querySelector('[data-map-pois]');
    const layers=new Map(),originalStyles=new Map(),downloads=new Map();
    let base=null,geo=null,city=null,territory='',territoryLabel='',requestedTerritory='',sequence=0;
    function describe(){
      status.textContent=checkbox.checked ? 'Satélite no entorno ativado.' : territory ? `${territoryLabel} em destaque · demais áreas em branco.` : 'São Paulo destacado · entorno claro.';
    }
    function refresh(map,layer){
      const b=map.getBounds();
      const frame=b ? {west:b.getSouthWest().lng(),south:b.getSouthWest().lat(),east:b.getNorthEast().lng(),north:b.getNorthEast().lat()} : null;
      layer.setMap(!checkbox.checked && (territory || !frame || !city || intersects(frame,city)) ? map : null);
    }
    function places(map){
      const visible=Boolean(pois?.checked),styles=originalStyles.get(map)||[];
      map.setOptions({clickableIcons:visible,styles:visible ? styles : [...styles,...HIDDEN_PLACES]});
    }
    function draw(map){
      layers.get(map)?.setMap(null);
      if(!geo){layers.set(map,null);return;}
      const layer=new scope.google.maps.Data();
      layer.addGeoJson(geo);layer.setStyle({fillColor:'#ffffff',fillOpacity:territory ? 1 : .93,strokeOpacity:0,strokeWeight:0,clickable:false,zIndex:-100});
      layers.set(map,layer);refresh(map,layer);
    }
    function redraw(){for(const map of layers.keys())draw(map);}
    function attach(map){
      if(!map||layers.has(map))return;
      originalStyles.set(map,map.get('styles')||[]);places(map);
      map.setMapTypeId('hybrid');layers.set(map,null);draw(map);
      map.addListener('idle',()=>{const layer=layers.get(map);if(layer)refresh(map,layer);});
    }
    async function download(url){
      if(!downloads.has(url))downloads.set(url,fetch(url,{credentials:'same-origin'}).then(r=>{if(!r.ok)throw new Error();return r.json();}).then(data=>{
        if(data.type!=='FeatureCollection'||!Array.isArray(data.features)||!Array.isArray(data.metadata?.limite_bbox)||data.metadata.limite_bbox.length!==4)throw new Error();
        return data;
      }).catch(error=>{downloads.delete(url);throw error;}));
      return downloads.get(url);
    }
    async function setTerritory({crs='',cnes=''}={}){
      const code=/^\d{7}$/.test(cnes)?cnes:'';
      const region=REGIONS.has(crs)?crs:'';
      const next=code ? 'uvis:'+code : region ? 'crs:'+region : '';
      if(next===requestedTerritory)return;
      requestedTerritory=next;const own=++sequence;
      if(!next){territory='';territoryLabel='';geo=base;redraw();describe();return;}
      // Clear the previous selection immediately while the new mask is loading.
      territory='';territoryLabel='';geo=base;redraw();status.textContent='Destacando território…';
      try{
        const file=code ? 'mascara-uvis-'+code+'.geojson?v=20261119-1' : 'mascara-'+region.toLowerCase()+'.geojson?v=20261119-3';
        const data=await download(root.dataset.regionMaskBase+file);
        if(own!==sequence)return;
        const properties=data.features[0]?.properties;
        if(code ? properties?.cnes!==code : properties?.crs!==region)throw new Error();
        territory=next;territoryLabel=code ? 'UVIS '+properties.uvis : 'CRS '+region;geo=data;redraw();describe();
      }catch(error){if(own===sequence){requestedTerritory='';status.textContent='Não foi possível destacar o território. O mapa e os filtros continuam disponíveis.';}}
    }
    checkbox.addEventListener('change',()=>{
      for(const [map,layer] of layers){map.setMapTypeId('hybrid');if(layer)refresh(map,layer);}describe();
    });
    pois?.addEventListener('change',()=>{for(const map of layers.keys())places(map);});
    download(root.dataset.maskUrl).then(data=>{
      base=data;const [west,south,east,north]=data.metadata.limite_bbox;city={west,south,east,north};
      if(!territory){geo=base;redraw();if(!requestedTerritory)describe();}
    }).catch(()=>{if(!territory&&!requestedTerritory)status.textContent='Não foi possível aplicar o destaque municipal. O mapa e seus filtros continuam disponíveis.';});
    return {attach,setTerritory,setRegion(value){return setTerritory({crs:value});}};
  }
  const api={create,intersects,HIDDEN_PLACES};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  if(!scope)return;
  scope.MunicipalSatellite=api;
  const root=document.querySelector('[data-satellite-context]');if(!root)return;
  const controller=create(root);
  document.addEventListener('uvis:selection-change',e=>controller.setTerritory(e.detail));
  document.addEventListener('geolocation:map-ready',e=>controller.attach(e.detail.map));
  document.addEventListener('operationalmaps:ready',e=>e.detail.maps.forEach(map=>controller.attach(map)));
  if(scope.__uvisTerritoryMap)controller.attach(scope.__uvisTerritoryMap);
  if(scope.__operationalMaps)scope.__operationalMaps.forEach(map=>controller.attach(map));
})(typeof window==='undefined'?null:window);
