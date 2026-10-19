(function () {
  "use strict";
  document.querySelectorAll(".risco-page form[method='post']").forEach(form => form.addEventListener("submit", () => {
    const button = form.querySelector("[data-risco-submit]");
    if (button) { button.disabled = true; button.textContent = "Analisando… aguarde"; }
  }));
  const dataNode = document.getElementById("risco-data");
  if (!dataNode) return;
  const {report, google: configured} = JSON.parse(dataNode.textContent);
  const svg = document.getElementById("risco-svg"), view = document.getElementById("risco-visao"), area = document.getElementById("risco-area");
  const ns = "http://www.w3.org/2000/svg", colors = {hotspot:"#dc2626",coldspot:"#2563eb",nao_significativo:"#e2e8f0",nao_avaliado:"#64748b"};
  const labels = {hotspot:"Hotspot · concentração alta",coldspot:"Coldspot · concentração baixa",nao_significativo:"Não significativo",nao_avaliado:"Não avaliado"};
  const features = report.geografia.features;
  const parts = geometry => geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  const points = features.flatMap(f => parts(f.geometry).flat(2));
  const minX=Math.min(...points.map(p=>p[0])), maxX=Math.max(...points.map(p=>p[0]));
  const minY=Math.min(...points.map(p=>p[1])), maxY=Math.max(...points.map(p=>p[1]));
  const cos=Math.cos((minY+maxY)/2*Math.PI/180), scale=Math.min(820/((maxX-minX)*cos),490/(maxY-minY));
  const dx=(900-(maxX-minX)*cos*scale)/2, dy=(570-(maxY-minY)*scale)/2;
  const xy=p=>[dx+(p[0]-minX)*cos*scale,dy+(maxY-p[1])*scale];
  const shapes=new Map(), googleShapes=new Map();
  let map, info;
  const number=(v,d=2)=>v===null || v===undefined ? "—" : v.toLocaleString("pt-BR",{maximumFractionDigits:d});
  const recurrence=code=>report.recorrencia.find(r=>r.codigo===code);
  const result=code=>report.anual.find(r=>r.codigo===code && String(r.ano)===view.value);
  const recurrenceColors=["#f1f5f9","#fee2e2","#fecaca","#f87171","#ef4444","#991b1b"];
  const fill=code=> {
    if (view.value!=="recorrencia") return colors[result(code)?.classe || "nao_avaliado"];
    const count=recurrence(code).anos_hotspot;
    return count===null ? colors.nao_avaliado : recurrenceColors[count===0?0:Math.max(1,Math.ceil(count/report.anos.length*5))];
  };
  function selectedDetails() {
    const code=area.value, feature=features.find(f=>f.properties.codigo===code), rec=recurrence(code), annual=result(code);
    const target=document.getElementById("risco-detalhe"); target.replaceChildren();
    const heading=document.createElement("h3"); heading.textContent=feature.properties.nome; target.append(heading);
    const lines=[`Código: ${code}`,`Vizinhos: ${report.vizinhos[code].length}`,`Anos avaliados: ${rec.anos_avaliados} de ${report.anos.length}`];
    if(view.value==="recorrencia") lines.push(rec.anos_hotspot===null?"Recorrência não avaliada":`Hotspot em ${rec.anos_hotspot} de ${report.anos.length} anos`);
    else if(annual) lines.push(`${annual.ano}: ${annual.casos_provaveis} casos prováveis`,labels[annual.classe],`Z de Gi*: ${number(annual.z,4)}`,`Pseudo-p: ${number(annual.p,3)}`,annual.motivo || "");
    if(rec.anos_hotspot===null && view.value==="recorrencia") lines.push("Consulte os avisos: não há classificação válida para todos os anos.");
    for(const line of lines.filter(Boolean)) { const p=document.createElement("p"); p.textContent=line; target.append(p); }
    for(const [key,path] of shapes) path.dataset.selected=String(key===code);
    for(const [key,list] of googleShapes) list.forEach(p=>p.setOptions({strokeWeight:key===code?4:1.5}));
  }
  function select(code) { area.value=code; selectedDetails(); }
  for(const feature of features) {
    const code=feature.properties.codigo, path=document.createElementNS(ns,"path");
    const d=parts(feature.geometry).flatMap(polygon=>polygon.map(ring=>ring.map((p,i)=>`${i?"L":"M"}${xy(p).map(v=>v.toFixed(2)).join(",")}`).join(" ")+" Z")).join(" ");
    path.setAttribute("d",d); path.setAttribute("fill-rule","evenodd"); path.setAttribute("tabindex","0"); path.setAttribute("role","button");
    path.setAttribute("aria-label",`Consultar ${feature.properties.nome}`); path.addEventListener("click",()=>select(code));
    path.addEventListener("keydown",event=>{if(event.key==="Enter" || event.key===" "){event.preventDefault();select(code);}});
    svg.append(path); shapes.set(code,path);
    // Códigos na grade de demonstração e territórios pequenos; o seletor mantém os nomes acessíveis.
    if(features.length<=35) {
      const ring=parts(feature.geometry)[0][0], projected=ring.slice(0,-1).map(xy);
      const text=document.createElementNS(ns,"text"); text.setAttribute("x",numberPlain(projected.map(p=>p[0]))); text.setAttribute("y",numberPlain(projected.map(p=>p[1]))); text.setAttribute("text-anchor","middle"); text.textContent=code; svg.append(text);
    }
  }
  function numberPlain(values) { return String(values.reduce((a,b)=>a+b,0)/values.length); }
  function refresh() {
    for(const [code,path] of shapes) path.setAttribute("fill",fill(code));
    for(const [code,list] of googleShapes) list.forEach(p=>p.setOptions({fillColor:fill(code)}));
    const legend=document.getElementById("risco-legenda"); legend.replaceChildren();
    let entries;
    if(view.value==="recorrencia") {
      entries=[];
      for(let n=0;n<=report.anos.length;n++) entries.push([`${n} ${n===1?"ano":"anos"}`,recurrenceColors[n===0?0:Math.max(1,Math.ceil(n/report.anos.length*5))]]);
      entries.push(["Não avaliado",colors.nao_avaliado]);
    } else entries=Object.keys(labels).map(key=>[labels[key],colors[key]]);
    for(const [label,color] of entries) { const span=document.createElement("span"), icon=document.createElement("i"); icon.style.backgroundColor=color; span.append(icon,document.createTextNode(label)); legend.append(span); }
    document.getElementById("risco-interpretacao").textContent=view.value==="recorrencia"?"Mais anos como hotspot indicam maior recorrência histórica. Zero anos não comprova ausência de risco de surto.":"Vermelho: concentração alta significativa; azul: concentração baixa significativa. p ≤ 0,05, análise exploratória sem correção por testes múltiplos.";
    selectedDetails();
  }
  area.addEventListener("change",selectedDetails); view.addEventListener("change",refresh); refresh();
  const unavailable=()=>{document.getElementById("risco-google-status").textContent="Google Maps indisponível neste endereço. O mapa territorial acima permanece disponível.";};
  function initializeGoogle() {
    if(map || !document.getElementById("risco-google-details").open) return;
    if(!configured || window.__GOOGLE_MAPS_AUTH_FAILED__){unavailable();return;}
    if(!window.google?.maps?.Map) return;
    try {
      map=new google.maps.Map(document.getElementById("risco-google"),{center:{lat:(minY+maxY)/2,lng:(minX+maxX)/2},zoom:13,streetViewControl:false,gestureHandling:"cooperative"});
      info=new google.maps.InfoWindow(); const bounds=new google.maps.LatLngBounds();
      for(const feature of features) {
        const code=feature.properties.codigo, list=[];
        for(const polygon of parts(feature.geometry)) {
          const paths=polygon.map(ring=>ring.map(p=>({lng:p[0],lat:p[1]})));
          paths.flat().forEach(p=>bounds.extend(p));
          const shape=new google.maps.Polygon({map,paths,fillColor:fill(code),fillOpacity:.7,strokeColor:"#334155",strokeWeight:1.5});
          shape.addListener("click",event=>{select(code); const content=document.createElement("div");content.textContent=`${feature.properties.nome} · consulte os resultados no painel da área`;info.setContent(content);info.setPosition(event.latLng);info.open({map});});
          list.push(shape);
        }
        googleShapes.set(code,list);
      }
      map.fitBounds(bounds,30); selectedDetails();
      document.getElementById("risco-google-status").textContent="Os mesmos contornos e resultados sobre o mapa-base. Clique em uma área para selecioná-la.";
    } catch(_error) { unavailable(); }
  }
  document.getElementById("risco-google-details").addEventListener("toggle",initializeGoogle);
  document.addEventListener("googlemaps:ready",initializeGoogle); document.addEventListener("googlemaps:auth-failed",unavailable);
  window.setTimeout(()=>{if(!map)unavailable();},15000);
  document.getElementById("risco-imprimir")?.addEventListener("click",()=> {
    const details=Array.from(document.querySelectorAll(".risco-page details:not(.risco-noprint)")), previous=details.map(d=>d.open);
    details.forEach(d=>{d.open=true;});
    window.addEventListener("afterprint",()=>details.forEach((d,i)=>{d.open=previous[i];}),{once:true});window.print();
  });
})();
