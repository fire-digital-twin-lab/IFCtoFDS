const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elements = {};
function element() { return {value:'',checked:false,files:[],options:[],children:[],appendChild(x){this.children.push(x);},replaceChildren(){this.children=[];},style:{}}; }
const doc={getElementById(id){return elements[id] || (elements[id]=element());},createElement(){return element();}};
const ns={viewer:{}};
let submitted;
const output={status:'MAPPING_VERIFIED',manifest:{records:[]},geometry_package:{elements:{}}};
const context=vm.createContext({window:{IfcFds:ns},document:doc,location:{protocol:'http:'},isFinite,Math,Number,Array,JSON,Promise,
    FormData:class {constructor(){this.values={};}append(k,v){this.values[k]=v;}},
    fetch:async(url,options)=>({ok:true,json:async()=>{
        if(url==='/api/jobs'){submitted=JSON.parse(options.body.values.configuration);return {id:'job1'};}
        if(url.endsWith('/result'))return output;
        return {state:'COMPLETED'};
    }})});
vm.runInContext(fs.readFileSync('js/verified-workflow.js','utf8'),context);
vm.runInContext(fs.readFileSync('js/viewer/scene-viewer.js','utf8'),context);
(async()=>{
    doc.getElementById('verified-profile').value='research-basement';
    doc.getElementById('verified-reference-case').value='basement';
    doc.getElementById('verified-use-domain').checked=true;
    ['xmin','xmax','ymin','ymax','zmin','zmax'].forEach((key,i)=>doc.getElementById('verified-domain-'+key).value=[0,10,0,10,-9,0][i]);
    doc.getElementById('verified-decisions').files=[{text:async()=>'{"fixture:1":{"action":"REFERENCE_GEOMETRY"}}'}];
    await ns.verified.run({name:'model.ifc'},{});
    assert.equal(submitted.profile,'research-basement');
    assert.equal(submitted.reference_case,'basement');
    assert.equal(submitted.simulation_domain.zmin,-9);
    assert.equal(submitted.decisions['fixture:1'].action,'REFERENCE_GEOMETRY');
    assert.equal(doc.getElementById('verified-artifacts').children.length,7);
    assert.ok(doc.getElementById('verified-artifacts').children.some(x=>x.href.endsWith('/geometry')));
    context.THREE={Group:class {constructor(){this.children=[];}add(x){this.children.push(x);}}};
    const viewer={ifcGroup:{add(){},remove(){}},makeIfcElement(record){return {userData:{},record};}};
    doc.getElementById('verified-show-reference').checked=true;
    ns.viewer.SceneViewer.prototype.loadVerifiedGeometry.call(viewer,{elements:{a:{mesh:{vertices:[],faces:[]}},b:{mesh:{vertices:[],faces:[]}}}},
        {records:[{entity_key:'a',simulation_role:'REFERENCE_GEOMETRY',scope_decision:'IN_SCOPE',name:'pipe'},
        {entity_key:'b',simulation_role:'PASSIVE_OBSTACLE',scope_decision:'IN_SCOPE',name:'wall'}]});
    assert.equal(viewer.verifiedReferenceGroup.children.length,1);
    assert.equal(viewer.verifiedReferenceGroup.children[0].userData.entityKey,'a');
    assert.equal(viewer.verifiedReferenceGroup.children[0].record.fdsRole,'REFERENCE_GEOMETRY');
    console.log('Golden workflow domain, profile, decisions, artifacts and separate reference viewer passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
