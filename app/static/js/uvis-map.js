(() => {
  'use strict';
  const root=document.querySelector('[data-uvis-map]');
  if(!root || !window.UvisTerritory) return;
  const svg=root.querySelector('[data-uvis-svg]'), status=root.querySelector('[data-uvis-map-status]');
  const mapNode=root.querySelector('[data-uvis-google]'), fallback=root.querySelector('[data-uvis-fallback]');
  const details=root.querySelector('[data-uvis-details]');
  let overlay, map, loaded=false, timeout, previousSelection=null, hasFramed=false;
  function isVisible(){return document.getElementById('geoAreaPanel')?.classList.contains('active')!==false;}
  function information(title,lines){
    const heading=document.createElement('h4');heading.textContent=title;details.replaceChildren(heading);
    for(const line of lines){const p=document.createElement('p');p.textContent=line;details.append(p);}
  }
  function framePoints(){return overlay?.framePoints() || overlay?.allPoints() || [];}
  function fit(){
    const points=framePoints();if(!map || !points.length)return;
    const b=new google.maps.LatLngBounds();for(const p of points)b.extend({lat:p[1],lng:p[0]});map.fitBounds(b,30);
  }
  function draw(){
    if(!overlay) return;
    const points=framePoints();if(!points.length)return;
    let west=Infinity,east=-Infinity,south=Infinity,north=-Infinity;
    for(const p of points){west=Math.min(west,p[0]);east=Math.max(east,p[0]);south=Math.min(south,p[1]);north=Math.max(north,p[1]);}
    const cosine=Math.cos((south+north)/2*Math.PI/180), cx=(west+east)/2,cy=(south+north)/2;
    const scale=Math.min(800/Math.max((east-west)*cosine,.001),520/Math.max(north-south,.001));
    const pathFor=geometry=>window.UvisTerritory.polygons(geometry).flatMap(poly=>poly.map(ring=>ring.map((p,i)=>
      `${i?'L':'M'}${(450+(p[0]-cx)*cosine*scale).toFixed(2)},${(310-(p[1]-cy)*scale).toFixed(2)}`).join(' ')+' Z')).join(' ');
    const pointFor=p=>[450+(p[0]-cx)*cosine*scale,310-(p[1]-cy)*scale];
    svg.replaceChildren();overlay.drawSVG(svg,pathFor,pointFor);
    initializeGoogle();
    const selection=overlay.selectedCode();
    if(map && framePoints().length && (!hasFramed || selection!==previousSelection)){fit();previousSelection=selection;hasFramed=true;}
  }
  function unavailable(message){
    clearTimeout(timeout);mapNode.hidden=true;fallback.hidden=false;status.textContent=message+' Os contornos permanecem disponíveis para consulta.';
  }
  function initializeGoogle(){
    if(!isVisible() || !loaded)return;
    if(window.__GOOGLE_MAPS_AUTH_FAILED__){unavailable('O Google Maps está indisponível neste endereço.');return;}
    if(root.dataset.googleConfigured!=='true'){unavailable('O mapa de ruas não está configurado neste ambiente.');return;}
    if(!window.google?.maps?.Map){
      if(!timeout)timeout=setTimeout(()=>unavailable('O mapa de ruas não carregou.'),15000);
      return;
    }
    try{
      if(!map){
        if(!window.__uvisTerritoryMap) return;
        mapNode.hidden=false;
        map=window.__uvisTerritoryMap;
        overlay.attachGoogle(map);
        google.maps.event.trigger(map,'resize');
        fit();previousSelection=overlay.selectedCode();hasFramed=framePoints().length>0;
      }
      clearTimeout(timeout);mapNode.hidden=false;fallback.hidden=true;
      status.textContent='Google Maps · limites das UVIS e distritos de São Paulo. Clique em um território para consultar.';
    }catch(_error){unavailable('O Google Maps não pôde ser iniciado.');}
  }
  function start(){
    if(!isVisible())return;
    if(!loaded){
      loaded=true;
      overlay=window.UvisTerritory.create(root.querySelector('[data-uvis-controls]'),{onChange:draw,onDetails:information});
    }else {initializeGoogle();if(map){google.maps.event.trigger(map,'resize');fit();}}
  }
  root.querySelector('[data-uvis-fit]').addEventListener('click',()=>{overlay?.resetFrame();information('São Paulo',['28 UVIS · 96 distritos de referência.','Selecione uma UVIS ou clique em uma área do mapa para consultar.']);draw();fit();});
  document.addEventListener('geolocation:map-ready',initializeGoogle);
  document.addEventListener('googlemaps:ready',initializeGoogle);
  document.addEventListener('googlemaps:auth-failed',()=>unavailable('O Google Maps está indisponível neste endereço.'));
  document.getElementById('geoAreaTab')?.addEventListener('shown.bs.tab',start);
  start();
})();
