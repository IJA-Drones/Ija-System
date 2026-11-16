/* Bounded transfers; server offset is authoritative after lost responses. */
(function(root) {
  'use strict';
  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
  async function upload({file, fields, url, csrf, progress, onAdvance = ()=>{}, storage = window.localStorage, fetcher = fetch, wait = delay}) {
    // Fingerprint only small edge samples, never buffer a multi-GB raster in JS.
    const samples = new Uint8Array(await new Blob([file.slice(0, 65536), file.slice(-65536)]).arrayBuffer());
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', samples)), n => n.toString(16).padStart(2,'0')).join('');
    const key = 'ortho-upload:' + JSON.stringify([file.name, file.size, file.lastModified, fields, hash]);
    const saved = {get:()=>{try{return storage.getItem(key);}catch(_){return null;}},
      set:value=>{try{storage.setItem(key,value);}catch(_){}}, clear:()=>{try{storage.removeItem(key);}catch(_){}}};
    async function request(target, options={}) {
      const controller = new AbortController();
      const timer = setTimeout(()=>controller.abort(), 120000);
      try {
        const response = await fetcher(target, {...options, signal:controller.signal, cache:'no-store',
          headers:{Accept:'application/json','X-CSRFToken':csrf(), ...options.headers}});
        const data = await response.json().catch(()=>({}));
        if (!response.ok) {
          const error = new Error(data.error || (response.status===401 ? 'Sua sessão expirou. Entre novamente e selecione o mesmo arquivo para continuar.' : 'Não foi possível enviar. Tente novamente para retomar o arquivo.'));
          error.status=response.status; throw error;
        }
        return data;
      } finally {clearTimeout(timer);}
    }
    async function retry(fn) {
      for(let attempt=0;;attempt++) {
        try {return await fn();} catch(error) {
          if(attempt>=4 || (error.status && ![408,409,429,500,502,503,504].includes(error.status))) throw error;
          progress(null, 'Conexão interrompida. Tentando retomar o envio…');
          await wait(1000 * 2**attempt);
        }
      }
    }
    let state;
    const previous=saved.get();
    if(previous && previous.startsWith(url+'/')) {
      try {state=await retry(()=>request(previous));} catch(error) {if(error.status!==404)throw error;saved.clear();}
    }
    if(!state) {
      state=await request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...fields,filename:file.name,size:file.size})});
      saved.set(state.url);
    }
    while(state.status==='receiving' && state.offset<file.size) {
      const previousOffset=state.offset;
      state=await retry(async()=>{
        const latest=await request(state.url);
        if(latest.status!=='receiving' || latest.offset===file.size)return latest;
        if(!Number.isSafeInteger(latest.offset) || latest.offset<0 || latest.offset>file.size || latest.chunk_bytes<1 || latest.chunk_bytes>8*1024*1024)throw new Error('Posição de envio inválida.');
        return request(latest.url,{method:'PUT',headers:{'Content-Type':'application/octet-stream','Upload-Offset':String(latest.offset)},
          body:file.slice(latest.offset,latest.offset+latest.chunk_bytes)});
      });
      if(state.offset>previousOffset)onAdvance();
      const percent=Math.floor(state.offset/file.size*100);
      progress(percent, `Enviando arquivo… ${percent}% (${(state.offset/1073741824).toFixed(2)} de ${(file.size/1073741824).toFixed(2)} GB)`);
    }
    if(state.status==='receiving' || state.status==='failed')state=await retry(()=>request(state.url,{method:'POST'}));
    while(state.status==='finalizing') {
      progress(100,'Arquivo recebido. Validando e armazenando; esta etapa pode demorar…');
      await wait(3000);
      state=await retry(()=>request(state.url));
    }
    if(state.status!=='complete' || !state.item)throw new Error(state.error || 'Não foi possível concluir o envio. Tente novamente para retomar.');
    saved.clear();
    return state.item;
  }
  root.uploadOrthoFile=upload;
  if(typeof module!=='undefined')module.exports={upload};
})(typeof window!=='undefined'?window:globalThis);
