// Execute the real inspector buttons, stores, and command history without WebGL.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Element {
    constructor(tag='div') { this.tagName=tag; this.children=[]; this.style={}; this.listeners={}; this.hidden=false; }
    appendChild(child) { this.children.push(child); return child; }
    set innerHTML(value) { this.children=[]; }
    addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
    click() { for (const handler of this.listeners.click || []) handler({}); }
    setAttribute() {}
}
const elements={};
const context=vm.createContext({console,document:{
    getElementById(id) { return elements[id] ||= new Element(); },
    createElement(tag) { return new Element(tag); }, querySelectorAll() { return []; }
}});
context.window=context;
for(const file of ['events/workbench-events.js','state/selection-store.js','state/visibility-store.js',
    'commands/command-bus.js','commands/select-command.js','commands/visibility-command.js','commands/camera-command.js',
    'inspector/inspector-view.js','inspector/inspector-controller.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/workbench',file),'utf8'),context,{filename:file});
}
class Vector {
    constructor(x=0) { this.x=x; }
    clone() { return new Vector(this.x); }
    copy(other) { this.x=other.x; return this; }
}
const viewer={camera:{position:new Vector(100),near:.1,far:1000,updateProjectionMatrix(){}},
    controls:{target:new Vector(0),update(){}}, focusSelection(){this.camera.position.x=5; this.controls.target.x=4;}};
const wb=context.IfcFds.workbench, store=wb.state.visibilityStore, bus=wb.commands.commandBus;
const inspector=wb.inspector.inspectorController;
inspector.init({},viewer);
wb.state.selectionStore.indexElements([{entityKey:'a:1',name:'Wall',ifcType:'IFCWALL',sourceId:'a',stepId:1}]);
wb.state.selectionStore.setSelection(['a:1']);
function click(label) {
    const bar=elements['inspect-structured-view'].children[0];
    const button=bar.children.find(b=>b.children.some(c=>c.textContent===label));
    assert.ok(button,'Missing inspector action '+label); button.click();
}
click('Focus'); assert.equal(viewer.camera.position.x,5);
click('Back'); assert.equal(viewer.camera.position.x,100);
bus.undo(); assert.equal(viewer.camera.position.x,5);
bus.undo(); assert.equal(viewer.camera.position.x,100);
click('Hide'); assert.equal(store.isKeyVisible('a:1'),false);
click('Show'); assert.equal(store.isKeyVisible('a:1'),true);
store.hideKeys(['other']);
const before=JSON.stringify(store.getState());
click('Isolate'); assert.equal(store.isKeyVisible('a:1'),true); assert.equal(store.isKeyVisible('unselected'),false);
click('Unisolate'); assert.equal(JSON.stringify(store.getState()),before);
bus.undo(); assert.equal(store.isKeyVisible('unselected'),false);
bus.execute(new wb.commands.ResetVisibilityCommand(store));
assert.equal(store.isKeyVisible('other'),true);
bus.undo(); assert.equal(store.isKeyVisible('unselected'),false);
let notifications=0;store.subscribe(()=>notifications++);
bus.undo();assert.equal(notifications,1,'Visibility undo must apply one atomic scene update');
console.log('Inspector Focus/Back, Hide/Show, Isolate/Unisolate, global restore and atomic undo passed.');
