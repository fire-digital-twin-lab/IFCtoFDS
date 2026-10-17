// Regressions for pre-main identity, fail-closed colors and scenario lifecycle.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({console});
for (const file of [
    'events/workbench-events.js', 'state/selection-store.js', 'state/visibility-store.js',
    'state/scenario-store.js', 'state/workbench-store.js', 'navigation/color-overlay.js'
]) vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/workbench', file), 'utf8'), context);
const wb = context.IfcFds.workbench;
context.window = context;
context.IfcFds.viewer = {};
vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/viewer/scene-viewer.js'), 'utf8'), context);
const tests = [];
function test(name, fn) { tests.push([name, fn]); }
test('edge-display preserves opening outlines and composes with hidden entities', () => {
    const regular = {_isIfcEdge: true}, opening = {_isIfcEdge: true, _isIfcOpeningEdge: true};
    const referenceEdge = {_isIfcEdge: true};
    const group = {traverse: fn => [regular, opening].forEach(fn)};
    const viewer = {ifcSolidGroup: group, ifcReferenceGroup: {traverse: () => {}},
        verifiedReferenceGroup: {traverse: fn => fn(referenceEdge)}};
    const setEdges = context.IfcFds.viewer.SceneViewer.prototype.setIfcEdgesVisible;
    const channel = context.IfcFds.viewer.setVisibilityChannel;
    setEdges.call(viewer, false);
    assert.equal(regular.visible, false);
    assert.equal(opening.visible, true);
    assert.equal(referenceEdge.visible, false);
    channel(regular, 'workbench', true);
    assert.equal(regular.visible, false);
    channel(opening, 'workbench', false);
    setEdges.call(viewer, true);
    assert.equal(referenceEdge.visible, true);
    assert.equal(opening.visible, false);
    channel(opening, 'workbench', true);
    assert.equal(opening.visible, true);
});
test('canonical identity survives indexing, descriptors and duplicate GUIDs across sources', () => {
    const store = new wb.state.SelectionStore();
    const a = {entityKey: 'sha-a:42', sourceId: 'sha-a', globalId: 'GUID', stepId: 42};
    const b = {sourceId: 'sha-b', globalId: 'GUID', stepId: 43};
    assert.equal(wb.createEntityKey(a), 'sha-a:42');
    assert.equal(wb.normalizeEntityDescriptor(b).sourceId, 'sha-b');
    store.indexElements([a, b], 'display-name.ifc');
    assert.equal(store.getAllDescriptors().length, 2);
    assert.ok(store.getDescriptor('sha-a:42'));
    assert.ok(store.getDescriptor('sha-b:GUID'));
    const missingGuid = {stepId: 77, name: 'Wall'};
    store.indexElements([missingGuid], 'model.ifc');
    assert.equal(wb.createEntityKey(missingGuid), 'model.ifc:77');
    // The FDS parser retains authoritative provenance in ifcSource, not raw.
    const savedFds = {id: 'GEOM_1', ifcSource: {entityKey: 'source-hash:88', sourceId: 'source-hash', globalId: 'GUID'}};
    store.indexElements([savedFds], 'output.fds');
    assert.equal(wb.createEntityKey(savedFds), 'source-hash:88');
    assert.equal(store.getDescriptor('source-hash:88').sourceId, 'source-hash');
});
test('unknown mapping and review approval never imply verification', () => {
    const colors = new wb.navigation.ColorOverlayEngine();
    const green = colors._getColorForDescriptor({mappingStrategy: 'OBST'}, 'mapping');
    for (const strategy of ['', 'NONE', 'UNKNOWN', 'OBST/GEOM', 'NOT_OBST']) {
        assert.notEqual(colors._getColorForDescriptor({mappingStrategy: strategy}, 'mapping'), green, strategy);
    }
    assert.notEqual(colors._getColorForDescriptor({mappingStrategy: 'OBST', raw: {verification_status: 'FAIL'}}, 'mapping'), green);
    assert.notEqual(colors._getColorForDescriptor({mappingStrategy: 'OBST', raw: {geometry_status: 'FAILED'}}, 'mapping'), green);
    assert.notEqual(colors._getColorForDescriptor({mappingStrategy: 'OBST', raw: {boundary_treatment: 'PENDING_VALIDATION'}}, 'mapping'), green);
    for (const geometryStatus of ['failed', 'Invalid', ' unsupported ']) {
        assert.equal(colors._getColorForDescriptor({mappingStrategy: 'OBST', raw: {geometry_status: geometryStatus}}, 'mapping'), 0xef4444);
    }
    assert.equal(colors._getColorForDescriptor({mappingStrategy: 'OBST', raw: {review_status: 'review_required'}}, 'mapping'), 0xf97316);
    assert.equal(colors._getColorForDescriptor({mappingStrategy: 'OBST', raw: {boundary_treatment: 'pending_validation'}}, 'mapping'), 0xf97316);
    const pass = colors._getColorForDescriptor({raw: {verification_status: 'PASS'}}, 'verification');
    assert.notEqual(colors._getColorForDescriptor({raw: {review_status: 'PASS'}}, 'verification'), pass);
    assert.notEqual(colors._getColorForDescriptor({raw: {verification_status: 'NOT_PASS'}}, 'verification'), pass);
});
test('scenario reset clears all project data, commands and invented physics', () => {
    const scenario = wb.state.scenarioStore;
    scenario.setBaseMapping('old');
    const fire = scenario.addFireSource({name: 'Unconfigured'});
    assert.equal(fire.peakHrrKw, null);
    assert.equal(fire.curve, null);
    assert.equal(fire.fuel, null);
    scenario.setOpeningState('old:door', 'OPEN', 10);
    scenario.configureHvac('old:fan', {flowRateM3s: 12, provenance: {reviewer: 'Engineer', evidence: 'design'}});
    scenario.addDevice({id: 'old-device'});
    wb.state.workbenchStore.resetAll();
    const spec = scenario.getScenarioSpec();
    assert.equal(spec.mappingBundleSha, null);
    assert.equal(spec.status, 'DRAFT');
    assert.equal(spec.fireSources.length, 0);
    assert.equal(spec.devices.length, 0);
    assert.equal(Object.keys(spec.openingStates).length, 0);
    assert.equal(Object.keys(spec.hvacOperations).length, 0);
    for (const value of [-1, NaN, Infinity, '', '12']) {
        assert.throws(() => scenario.configureHvac('fan', {flowRateM3s: value}));
    }
    assert.equal(scenario.getHvacOperation('fan'), null);
});
let failures = 0;
for (const [name, fn] of tests) {
    try { fn(); console.log('PASS ' + name); }
    catch (error) { failures++; console.error('FAIL ' + name + '\n' + error.stack); }
}
process.exitCode = failures ? 1 : 0;
