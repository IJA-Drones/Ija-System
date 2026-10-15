const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = {window:{}};
vm.runInNewContext(fs.readFileSync('app/static/js/video-upload-recovery.js','utf8'),context);
const {upload,httpError} = context.window.IjaVideoUploadRecovery;
const lost = () => httpError('missing',404,{code:'video_upload_session_missing'});

function fixture() {
  const calls=[], progress=[];let sessions=0,restarts=0;
  return {
    calls,progress,get sessions(){return sessions;},get restarts(){return restarts;},
    args:{file:new Blob(['abcdefg']),chunkBytes:3,
      createSession:async()=>({session_id:`s${++sessions}`}),
      sendChunk:async(id,index,blob,tick)=>{calls.push([id,index,await blob.text()]);tick(blob.size);},
      complete:async id=>({success:true,job_id:`job-${id}`}),
      onProgress:(...args)=>progress.push(args),onRestart:()=>{restarts++;}},
  };
}

test('lost chunk session restarts from zero, sends every part, and completes only the replacement',async()=>{
  const f=fixture();const send=f.args.sendChunk;
  f.args.sendChunk=async(...args)=>{if(args[0]==='s1'&&args[1]===1)throw lost();return send(...args);};
  const completed=[];f.args.complete=async id=>{completed.push(id);return {job_id:'finished'};};
  assert.equal((await upload(f.args)).job_id,'finished');
  assert.equal(f.restarts,1);
  assert.deepEqual(f.calls,[['s1',0,'abc'],['s2',0,'abc'],['s2',1,'def'],['s2',2,'g']]);
  assert.deepEqual(completed,['s2']);
  assert.equal(f.progress.at(-1)[0],7);
  assert.equal(f.progress.at(-1)[4],1);
});

test('explicit missing session at completion can recover',async()=>{
  const f=fixture();f.args.complete=async id=>{if(id==='s1')throw lost();return {job_id:'new'};};
  assert.equal((await upload(f.args)).job_id,'new');assert.equal(f.sessions,2);
});

test('repeated session loss stops after one restart with an actionable error',async()=>{
  const f=fixture();f.args.sendChunk=async()=>{throw lost();};
  await assert.rejects(upload(f.args),/avise o suporte/);
  assert.equal(f.sessions,2);assert.equal(f.restarts,1);
});

for(const status of [401,403,409,404,500])test(`HTTP ${status} without the missing-session code is not replayed`,async()=>{
  const f=fixture();const error=httpError('other',status,{});
  f.args.sendChunk=async()=>{throw error;};
  await assert.rejects(upload(f.args),e=>e===error);assert.equal(f.sessions,1);
});

test('uncertain completion after a network error is never replayed',async()=>{
  const f=fixture();f.args.complete=async()=>{throw new Error('network');};
  await assert.rejects(upload(f.args),/network/);assert.equal(f.sessions,1);
});

test('init failures stop immediately; legacy missing-session response is recognized',async()=>{
  const f=fixture();f.args.createSession=async()=>{throw lost();};
  await assert.rejects(upload(f.args));assert.equal(f.restarts,0);
  assert.equal(httpError('old',404,{error:'Sessao de upload de video nao encontrada.'}).code,'video_upload_session_missing');
});
