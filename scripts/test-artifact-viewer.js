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
class Vector3 {constructor(x=0,y=0,z=0){this.x=x;this.y=y;this.z=z;}copy(v){this.x=v.x;this.y=v.y;this.z=v.z;return this;}}
class Group {constructor(){this.children=[];this.position=new Vector3();}add(x){this.children.push(x);}remove(x){this.children=this.children.filter(v=>v!==x);}}
const ns={viewer:{}};
const fetchCalls=[],authCalls=[];
async function mockFetch(url,options){
 options=options||{};
 fetchCalls.push({url,headers:options.headers||{}});
 const signal=options.signal;
 requests++; if(url.endsWith('/artifacts/geometry'))return {ok:true,json:async()=>({elements:entries})};
 active++;peak=Math.max(peak,active);
 await new Promise((resolve,reject)=>{const t=setTimeout(resolve,hold?100:5);signal.addEventListener('abort',()=>{clearTimeout(t);reject(Object.assign(new Error('aborted'),{name:'AbortError'}));},{once:true});}).finally(()=>active--);
 return {ok:!fail,arrayBuffer:async()=>payload};
}
ns.verified={
 getAuthHeaders(){return {'x-api-key':'test-key'};},
 authFetch(url,options){authCalls.push(url);return mockFetch(url,Object.assign({},options,{headers:ns.verified.getAuthHeaders()}));}
};
const context=vm.createContext({window:{IfcFds:ns},document:{getElementById(id){return id==='verified-show-reference'?toggle:progress;}},
 THREE:{Group,Vector3},AbortController,crypto:webcrypto,DataView,Uint8Array,Array,Object,Promise,
 fetch:mockFetch});
vm.runInContext(fs.readFileSync('js/viewer/scene-viewer.js','utf8'),context);
const viewer={ifcGroup:new Group(),makeIfcElement(record){return {record,userData:{},traverse(fn){fn({geometry:{dispose(){disposed++;}}});}};}};
const bind=()=>ns.viewer.SceneViewer.prototype.bindVerifiedArtifacts.call(viewer,{geometry:{url:'/api/jobs/1/artifacts/geometry'}});
(async()=>{
 bind();assert.equal(requests,0);
 toggle.checked=true;await toggle.onchange();assert.equal(viewer.verifiedReferenceGroup.children.length,4);assert.equal(peak,2);
 toggle.checked=false;await toggle.onchange();assert.equal(disposed,4);assert.equal(viewer.verifiedReferenceGroup.children.length,0);
 hold=true;toggle.checked=true;const loading=toggle.onchange();await new Promise(r=>setTimeout(r,10));bind();await loading;
 assert.equal(viewer.verifiedReferenceGroup.children.length,0);assert.equal(active,0);
 hold=false;fail=true;toggle.checked=true;await toggle.onchange();assert.match(progress.textContent,/payload unavailable/);assert.equal(toggle.checked,false);
 // C1: verified artifact fetches must carry the API key through ns.verified.authFetch.
 // C2: a recreated overlay group must keep the FDS coordinate-rebase offset.
 fail=false;fetchCalls.length=0;authCalls.length=0;
 viewer.meshGroup=new Group();viewer.obstGroup=new Group();viewer.ventGroup=new Group();
 viewer.holeGroup=new Group();viewer.geomGroup=new Group();viewer.fdsGroup=new Group();
 viewer.fdsGroup.traverse=function(){};viewer.setNavigationMode=function(){};viewer.setSelectedObjects=function(){};
 viewer.clearHover=function(){};viewer.applyFdsClipVisibility=function(){};viewer.applyVisibilityState=function(){};
 viewer.makeWireBox=function(){return {traverse:function(){}};};
 viewer.makeBox=viewer.makeWireBox;viewer.makeGeom=viewer.makeWireBox;
 ns.viewer.SceneViewer.prototype.loadFdsModel.call(viewer,{coordinateRebase:[10,20,30],meshes:[],obsts:[],vents:[],holes:[],geoms:[]});
 assert.deepEqual(viewer.fdsCoordinateRebase,[10,20,30]);
 toggle.checked=true;await toggle.onchange();
 assert.ok(fetchCalls.length>0);
 assert.equal(authCalls.length,fetchCalls.length);
 fetchCalls.forEach(function(call){assert.equal(call.headers['x-api-key'],'test-key');});
 assert.equal(viewer.verifiedReferenceGroup.children.length,4);
 assert.deepEqual([viewer.verifiedReferenceGroup.position.x,viewer.verifiedReferenceGroup.position.y,viewer.verifiedReferenceGroup.position.z],[10,30,20]);
 // Fallback path: plain fetch still sends the key when authFetch is unavailable.
 delete ns.verified.authFetch;fetchCalls.length=0;
 toggle.checked=false;await toggle.onchange();toggle.checked=true;await toggle.onchange();
 assert.ok(fetchCalls.length>0);
 fetchCalls.forEach(function(call){assert.equal(call.headers['x-api-key'],'test-key');});
 assert.deepEqual([viewer.verifiedReferenceGroup.position.x,viewer.verifiedReferenceGroup.position.y,viewer.verifiedReferenceGroup.position.z],[10,30,20]);
 console.log('Lazy binary viewer: bounded concurrency, disposal, job cancellation and artifact errors passed.');
 console.log('Verified overlay fetches send x-api-key and the recreated group keeps the rebase offset passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
