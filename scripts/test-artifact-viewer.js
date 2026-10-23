const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto,createHash} = require('node:crypto');
const toggle={checked:false}; const progress={textContent:''};
let requests=0, active=0, peak=0, disposed=0, hold=false, fail=false;
const payload=new ArrayBuffer(84); const data=new DataView(payload);
[0,0,0,1,0,0,0,1,0].forEach((v,i)=>data.setFloat64(i*8,v,true));
[0,1,2].forEach((v,i)=>data.setUint32(72+i*4,v,true));
const hash=createHash('sha256').update(Buffer.from(payload)).digest('hex');
const ref={payload:hash,vertex_count:3,face_count:1,faces_offset:72,byte_length:84};
const entries=Object.fromEntries(['a','b','c','d'].map(key=>[key,{entity_key:key,simulation_role:'REFERENCE_GEOMETRY',scope_decision:'IN_SCOPE',mesh:ref}]));
class Group {constructor(){this.children=[];}add(x){this.children.push(x);}remove(x){this.children=this.children.filter(v=>v!==x);}}
const ns={viewer:{}};
const context=vm.createContext({window:{IfcFds:ns,IFCFDS_API_KEY:'fixture-key'},document:{getElementById(id){return id==='verified-show-reference'?toggle:progress;}},
 THREE:{Group},AbortController,crypto:webcrypto,DataView,Uint8Array,Array,Object,Promise,
 fetch:async(url,{signal,headers})=>{
  assert.equal(headers['x-api-key'],'fixture-key','Geometry downloads must use the shared authenticated client');
  requests++; if(url.endsWith('/artifacts/geometry'))return {ok:true,json:async()=>({elements:entries})};
  active++;peak=Math.max(peak,active);
  await new Promise((resolve,reject)=>{const t=setTimeout(resolve,hold?100:5);signal.addEventListener('abort',()=>{clearTimeout(t);reject(Object.assign(new Error('aborted'),{name:'AbortError'}));},{once:true});}).finally(()=>active--);
  return {ok:!fail,arrayBuffer:async()=>payload};
 }});
require('./test-support/load-viewer')(context);
const viewer={ifcGroup:new Group(),makeIfcElement(record){return {record,userData:{},traverse(fn){fn({geometry:{dispose(){disposed++;}}});}};}};
const bind=()=>ns.viewer.SceneViewer.prototype.bindVerifiedArtifacts.call(viewer,{geometry:{url:'/api/jobs/1/artifacts/geometry'}});
(async()=>{
 bind();assert.equal(requests,0);
 toggle.checked=true;await toggle.onchange();assert.equal(viewer.verifiedReferenceGroup.children.length,4);assert.equal(peak,2);
 toggle.checked=false;await toggle.onchange();assert.equal(disposed,4);assert.equal(viewer.verifiedReferenceGroup.children.length,0);
 hold=true;toggle.checked=true;const loading=toggle.onchange();await new Promise(r=>setTimeout(r,10));bind();await loading;
 assert.equal(viewer.verifiedReferenceGroup.children.length,0);assert.equal(active,0);
 hold=false;fail=true;toggle.checked=true;await toggle.onchange();assert.match(progress.textContent,/payload unavailable/);assert.equal(toggle.checked,false);
 console.log('Lazy binary viewer: bounded concurrency, disposal, job cancellation and artifact errors passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
