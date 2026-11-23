(function(scope){
  'use strict';
  const states={
    SIM:{id:'SIM',label:'Larva observada',color:'#dc2626',gradient:['rgba(220,38,38,0)','#fca5a5','#dc2626','#7f1d1d']},
    NAO:{id:'NAO',label:'Larva não observada',color:'#15803d',gradient:['rgba(21,128,61,0)','#86efac','#15803d','#14532d']},
    NAO_INFORMADO:{id:'NAO_INFORMADO',label:'Não informado',color:'#64748b',gradient:['rgba(100,116,139,0)','#cbd5e1','#64748b','#334155']}
  };
  const normalize=value=>String(value||'').trim().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase();
  function state(point){
    const answer=normalize(point.larva_visualizada);
    if(states[answer])return answer;
    const answers=(point.ordens||[]).map(o=>normalize(o.larvas));
    return answers.includes('SIM')?'SIM':answers.includes('NAO')?'NAO':'NAO_INFORMADO';
  }
  const style=point=>states[state(point)];
  const api={states,state,style};
  if(scope)scope.MapLarva=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window==='undefined'?null:window);
