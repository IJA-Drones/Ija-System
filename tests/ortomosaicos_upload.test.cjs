const {test}=require('node:test');
const assert=require('node:assert/strict');
const {upload}=require('../app/static/js/ortomosaicos-upload.js');
const response=(body,status=200)=>({ok:status<400,status,json:async()=>body});
const store=()=>{const data=new Map();return {getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k),data};};

test('lost chunk response resumes at server offset without duplicating bytes',async()=>{
 const file=new File(['abcdefgh'],'mapa.tif',{lastModified:1}), storage=store();
 let state={url:'/uploads/abc',offset:0,chunk_bytes:4,status:'receiving'}, received='',fail=true, puts=0;
 const fetcher=async(url,options)=>{
  if(url==='/uploads')return response(state,201);
  if(options.method==='PUT'){
   assert.equal(Number(options.headers['Upload-Offset']),received.length);
   received+=await options.body.text();puts++;state={...state,offset:received.length};
   if(fail){fail=false;throw new TypeError('connection lost after server committed');}
  }
  if(options.method==='POST')state={...state,status:'finalizing'};
  else if(state.status==='finalizing')state={...state,status:'complete',item:{id:7}};
  return response(state);
 };
 assert.deepEqual(await upload({file,fields:{nome:'Mapa'},url:'/uploads',csrf:()=>'',progress:()=>{},storage,fetcher,wait:async()=>{}}),{id:7});
 assert.equal(received,'abcdefgh');assert.equal(puts,2);assert.equal(storage.data.size,0);
});

test('16 GiB file slices remain bounded and preserve offsets above 32 bits',async()=>{
 const size=16*1024**3,offset=size-8*1024*1024;
 const slices=[];
 const file={name:'large.tif',size,lastModified:1,slice(start,end){slices.push([start,end]);return new Blob(['data']);}};
 const storage=store();let stage=0;
 const fetcher=async(url,options)=>{
  if(url==='/uploads')return response({url:'/uploads/big',offset,chunk_bytes:8*1024*1024,status:'receiving'},201);
  if(options.method==='PUT'){assert.equal(options.headers['Upload-Offset'],String(offset));stage=1;}
  if(options.method==='POST')stage=2;
  return response({url:'/uploads/big',offset:stage?size:offset,chunk_bytes:8*1024*1024,status:stage===2?'complete':'receiving',item:stage===2?{id:8}:undefined});
 };
 await upload({file,fields:{},url:'/uploads',csrf:()=>'',progress:()=>{},storage,fetcher,wait:async()=>{}});
 assert.deepEqual(slices.at(-1),[offset,size]);
});

test('failed connection preserves session for another attempt and does not fall back to giant upload',async()=>{
 const file=new File(['hello'],'mapa.tif',{lastModified:1}),storage=store();let starts=0;
 const options={file,fields:{},url:'/uploads',csrf:()=>'',progress:()=>{},storage,wait:async()=>{}};
 const fetcher=async(url)=>{if(url==='/uploads'){starts++;return response({url:'/uploads/resume',offset:0,status:'receiving',chunk_bytes:4},201);}throw new TypeError('offline');};
 await assert.rejects(upload({...options,fetcher}),/offline/);
 assert.equal(storage.data.size,1);
 await assert.rejects(upload({...options,fetcher}),/offline/);
 assert.equal(starts,1);
});
