/* Sharing is initiated by the visitor; this script never sends messages. */
(() => {
  const input=document.getElementById('acao-public-link');
  if(!input)return;
  const feedback=document.querySelector('[data-share-status]');
  document.querySelector('[data-copy-link]').addEventListener('click',async()=>{
    try{await navigator.clipboard.writeText(input.value);feedback.textContent='Link copiado.';}
    catch{input.focus();input.select();feedback.textContent='Selecione e copie o endereço acima.';}
  });
  const share=document.querySelector('[data-share-link]');
  if(typeof navigator.share==='function'){
    share.hidden=false;
    share.addEventListener('click',async()=>{
      try{await navigator.share({title:share.dataset.title,url:input.value});feedback.textContent='Compartilhamento concluído.';}
      catch(error){if(error.name!=='AbortError')feedback.textContent='Use Copiar link ou um dos aplicativos abaixo.';}
    });
  }
})();
