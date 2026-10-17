// Exercise the real opening-depth predicate at V8's argument-count boundary.
// Expose its lexical function in the test VM only, without adding a product API.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const cp = require('child_process');
const baseline = process.argv.includes('--baseline');
const ctx = {window: {IfcFds: {ifc: {}}}};
let source = baseline
    ? cp.execFileSync('git', ['show', '36db24e:js/ifc/ifc-adapter.js'], {encoding: 'utf8', maxBuffer: 2e6})
    : fs.readFileSync('js/ifc/ifc-adapter.js', 'utf8');
source = source.replace('    ns.ifc.IfcAdapter = IfcAdapter;', '    ns.ifc.testOpening = holeForOpeningExtrusion;\n    ns.ifc.IfcAdapter = IfcAdapter;');
vm.runInNewContext(source, ctx, {filename: 'ifc-adapter.js'});
const host = {base: [[0,0,0],[4,0,0],[4,4,0],[0,4,0]], offset: [0,0,1]};
const opening = {base: [], offset: [0,0,1]};
for (let i=0; i<150000; i++) {
    const angle = i*2*Math.PI/150000;
    opening.base.push([2+Math.cos(angle),2+Math.sin(angle),0]);
}
const hole = ctx.window.IfcFds.ifc.testOpening(host, opening);
assert.equal(hole.length, opening.base.length);
assert.deepEqual(hole[0], opening.base[0]);
// Moving the opening away from the host depth must still fail the predicate.
opening.base = opening.base.map(v => [v[0],v[1],2]);
assert.equal(ctx.window.IfcFds.ifc.testOpening(host, opening), null);
console.log('Large opening: 150000 profile points retain depth and shape without argument expansion.');
