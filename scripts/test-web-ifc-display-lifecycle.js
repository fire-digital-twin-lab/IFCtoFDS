const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const workers = [];
class Worker {
    constructor() { this.terminated = false; workers.push(this); }
    postMessage(message) { this.message = message; }
    terminate() { this.terminated = true; }
    complete() { this.onmessage({data: {id: this.message.id, type: 'meshes', meshes: [{expressID: 1}]}}); }
}
const context = vm.createContext({URL, Worker, console: {warn() {}, error() {}},
    document: {currentScript: {src: 'file:///frontend/src/features/preview/web-ifc-display.js'}}});
context.window = context;
context.IfcFds = {ifc: {}};
vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/src/features/preview/web-ifc-display.js'), 'utf8'), context);

(async () => {
    const first = new context.IfcFds.ifc.WebIfcDisplay();
    const cancelled = first.load(new ArrayBuffer(8));
    const cancelledAssertion = assert.rejects(cancelled, error => error.name === 'AbortError');
    const stale = workers[0];
    first.dispose();
    await cancelledAssertion;
    assert.ok(stale.terminated);
    await assert.rejects(first.load(new ArrayBuffer(8)), error => error.name === 'AbortError');

    const second = new context.IfcFds.ifc.WebIfcDisplay();
    const third = new context.IfcFds.ifc.WebIfcDisplay();
    const secondResult = second.load(new ArrayBuffer(8));
    const thirdResult = third.load(new ArrayBuffer(8));
    assert.equal(workers.length, 3, 'Each display owns its worker');
    stale.onerror({message: 'late error after termination'});
    assert.ok(!workers[1].terminated && !workers[2].terminated);
    workers[1].complete();
    workers[2].complete();
    assert.equal((await secondResult)[0].expressID, 1);
    assert.equal((await thirdResult)[0].expressID, 1);
    second.dispose();
    third.dispose();
    console.log('Display cancellation, instance ownership and late worker events verified.');
})().catch(error => { console.error(error); process.exitCode = 1; });
