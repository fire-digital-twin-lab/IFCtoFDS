// Real drawer handlers: authenticated artifacts, failed-job checkpoints, reset.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
    constructor(tag='div') { this.tagName=tag; this.children=[]; this.attrs={}; this.style={}; this.listeners={}; this.textContent=''; this.classes=new Set(); this.classList={add:v=>this.classes.add(v),remove:v=>this.classes.delete(v)}; }
    set href(v) {this.attrs.href=v;} get href() {return this.attrs.href;}
    set download(v) {this.attrs.download=v;} get download() {return this.attrs.download;}
    setAttribute(k,v){this.attrs[k]=v;} getAttribute(k){return this.attrs[k] ?? null;} removeAttribute(k){delete this.attrs[k];}
    appendChild(e){this.children.push(e);return e;} remove(){} querySelector(){return null;}
    addEventListener(n,f){(this.listeners[n] ||= []).push(f);}
    click(){const e={currentTarget:this,preventDefault(){this.prevented=true;}};for(const f of this.listeners.click || [])f(e);return e;}
}
const elements={};
for(const id of ['btn-download-fds','btn-download-manifest','btn-download-geom-pkg','btn-download-report','panel-artifacts','drawer-verdict-summary','artifact-download-status']) elements[id]=new Element();
const requests=[],downloads=[];
let httpStatus=200;
const ctx=vm.createContext({console, setTimeout: f=>f(), URL:{createObjectURL:blob=>{downloads.push(blob);return 'blob:test';},revokeObjectURL(){}},fetch:async(url,opts)=>{requests.push({url,opts});return {ok:httpStatus===200,status:httpStatus,blob:async()=>({url})};},document:{getElementById:id=>elements[id] || null,querySelectorAll:()=>[],createElement:tag=>new Element(tag),body:new Element('body')}});
ctx.window=ctx;
ctx.IfcFds={verified:{getAuthHeaders:()=>({'x-api-key':'test-key'})}};
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../js/ui/audit-drawer.js'),'utf8'),ctx);
const drawer=ctx.IfcFds.ui.auditDrawer;
const tick=()=>new Promise(setImmediate);
(async()=>{
    drawer.init();
    drawer.renderAuditDrawer({status:'REJECTED',artifacts:{fds:{url:'/api/jobs/new/artifacts/fds'},manifest:{url:'/api/jobs/new/artifacts/manifest'},geometry:{url:'/api/jobs/new/artifacts/geometry'},geometry_archive:{url:'/api/jobs/new/artifacts/geometry_archive'}}});
    assert.equal(elements['btn-download-geom-pkg'].href,'/api/jobs/new/artifacts/geometry_archive');
    assert.equal(elements['btn-download-fds'].download,'model_diagnostic_unaccepted.fds');
    elements['btn-download-fds'].click();await tick();
    assert.equal(requests[0].url,'/api/jobs/new/artifacts/fds');
    assert.equal(requests[0].opts.headers['x-api-key'],'test-key');
    drawer.exposeFailedCheckpoints('failed');
    elements['btn-download-fds'].click();await tick();
    assert.equal(requests[1].url,'/api/jobs/failed/checkpoints/fds');
    assert.equal(downloads[1].url,requests[1].url);
    assert.equal(elements['btn-download-geom-pkg'].download,'model_checkpoint_geometry.json');
    httpStatus=404;elements['btn-download-manifest'].click();await tick();
    assert.match(elements['artifact-download-status'].textContent,/Download failed.*HTTP 404/);
    drawer.clearArtifacts();
    const before=requests.length;
    assert.equal(elements['btn-download-fds'].click().prevented,true);
    await tick();assert.equal(requests.length,before);
    assert.equal(elements['btn-download-report'].getAttribute('href'),null);
    console.log('Authenticated artifact downloads, current-job checkpoint selection, ZIP type, errors and stale-link reset passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
