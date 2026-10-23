// Regressions for pre-main identity, fail-closed colors and scenario lifecycle.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({console});
for (const file of [
    'shared/lifecycle.js','events/workbench-events.js', 'state/selection-store.js', 'state/visibility-store.js',
    'state/scenario-store.js', 'state/workbench-store.js', 'viewer/color-overlay.js'
]) vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/src', file), 'utf8'), context);
const wb = context.IfcFds.workbench;
context.window = context;
context.IfcFds.viewer = {};
require('./test-support/load-viewer')(context);
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
test('scenario status cannot approve a missing or rejected base mapping', () => {
    const scenario = new wb.state.ScenarioStore();
    scenario.setBaseMapping(null);
    assert.equal(scenario.isSimulationPermitted(), false);
    scenario.setBaseMapping('verified');
    assert.equal(scenario.isSimulationPermitted(), true);
    scenario.setInvalidBaseMapping(null, 'New conversion started');
    scenario.setStatus('SCENARIO_VALIDATED');
    assert.equal(scenario.isSimulationPermitted(), false);
    scenario.setBaseMapping('verified-new');
    assert.equal(scenario.isSimulationPermitted(), true);
    scenario.setInvalidBaseMapping('verified-new', 'Conversion restarted');
    scenario.setBaseMapping('different-bundle');
    assert.equal(scenario.getStatus(), 'STALE');
    assert.equal(scenario.isSimulationPermitted(), false);
    scenario.reset();
    scenario.setStatus('BASE_MAPPING_VALID');
    assert.equal(scenario.isSimulationPermitted(), false);
});
test('hydrateManifest separates human review_status from machine verification_status without duplicates', () => {
    const store = new wb.state.SelectionStore();
    const elem = {entityKey: 'arch.ifc:101', sourceId: 'arch.ifc', globalId: 'GUID101', stepId: 101, name: 'Wall #101'};
    store.indexElements([elem], 'arch.ifc');
    assert.equal(store.getAllDescriptors().length, 1);

    const records = [{
        entity_key: 'sha-canon:101',
        source_id: 'sha-canon',
        global_id: 'GUID101',
        step_id: 101,
        ifc_type: 'IfcWall',
        simulation_role: 'PASSIVE_OBSTACLE',
        mapping_strategy: 'OBST',
        review_status: 'REQUIRES_REVIEW'
    }];
    const report = {
        element_statuses: {'sha-canon:101': 'MATCHED'}
    };
    store.hydrateManifest(records, report);

    const desc = store.getDescriptor('sha-canon:101');
    assert.ok(desc);
    assert.equal(desc.verificationStatus, 'MATCHED');
    assert.equal(desc.reviewStatus, 'REQUIRES_REVIEW');
    assert.equal(desc.raw.verification_status, 'MATCHED');
    assert.equal(desc.raw.review_status, 'REQUIRES_REVIEW');
    // Ensure no phantom duplicate entries in Model Tree / index
    assert.equal(store.getAllDescriptors().length, 1);
});
test('selectByEntityKeys uses source-qualified keys and avoids cross-file STEP ID collision', () => {
    const viewer = Object.create(context.IfcFds.viewer.SceneViewer.prototype);
    let selected = [];
    viewer.setSelectedObjects = objs => { selected = objs; };

    const nodeA = {userData: {type: 'wall', sourceId: 'sourceA', stepId: 105, raw: {source_id: 'sourceA', step_id: 105}}};
    const nodeB = {userData: {type: 'wall', sourceId: 'sourceB', stepId: 105, raw: {source_id: 'sourceB', step_id: 105}}};

    viewer.fdsGroup = {traverse: fn => { fn(nodeA); fn(nodeB); }};
    viewer.ifcGroup = null;

    viewer.selectByEntityKeys(['sourceA:105']);
    assert.equal(selected.length, 1);
    assert.equal(selected[0], nodeA);
    assert.notEqual(selected[0], nodeB);
});
test('selectByEntityKeys uses source-qualified keys and avoids cross-file duplicate GlobalId collision', () => {
    const viewer = Object.create(context.IfcFds.viewer.SceneViewer.prototype);
    let selected = [];
    viewer.setSelectedObjects = objs => { selected = objs; };

    const nodeA = {userData: {type: 'wall', sourceId: 'sourceA', stepId: 105, globalId: 'GUID_COMMON', raw: {source_id: 'sourceA', step_id: 105, global_id: 'GUID_COMMON'}}};
    const nodeB = {userData: {type: 'duct', sourceId: 'sourceB', stepId: 205, globalId: 'GUID_COMMON', raw: {source_id: 'sourceB', step_id: 205, global_id: 'GUID_COMMON'}}};

    viewer.fdsGroup = {traverse: fn => { fn(nodeA); fn(nodeB); }};
    viewer.ifcGroup = null;

    viewer.selectByEntityKeys(['sourceA:GUID_COMMON']);
    assert.equal(selected.length, 1);
    assert.equal(selected[0], nodeA);
    assert.notEqual(selected[0], nodeB);
});
test('SelectionStore isolates identical STEP ID across federated models in hydration and lookup', () => {
    const store = new wb.state.SelectionStore();
    const wall = {entityKey: 'arch:105', sourceId: 'arch', globalId: 'GUID_W105', stepId: 105, name: 'Arch Wall #105'};
    const duct = {entityKey: 'mep:105', sourceId: 'mep', globalId: 'GUID_D105', stepId: 105, name: 'MEP Duct #105'};
    store.indexElements([wall, duct], 'default');

    assert.equal(store.getAllDescriptors().length, 2);
    assert.equal(store.getDescriptor('arch:105').name, 'Arch Wall #105');
    assert.equal(store.getDescriptor('mep:105').name, 'MEP Duct #105');

    // Hydrate manifest only for arch:105
    const records = [{
        entity_key: 'sha-arch:105',
        source_id: 'arch',
        global_id: 'GUID_W105',
        step_id: 105,
        ifc_type: 'IfcWall',
        simulation_role: 'PASSIVE_OBSTACLE',
        mapping_strategy: 'OBST',
        review_status: 'APPROVED'
    }];
    const report = {
        element_statuses: {'sha-arch:105': 'MATCHED'}
    };
    store.hydrateManifest(records, report);

    const archDesc = store.getDescriptor('arch:105');
    const mepDesc = store.getDescriptor('mep:105');
    assert.equal(archDesc.reviewStatus, 'APPROVED');
    assert.equal(archDesc.verificationStatus, 'MATCHED');
    // Ensure mep:105 was NOT mutated by arch manifest hydration!
    assert.notEqual(mepDesc.reviewStatus, 'APPROVED');
    assert.notEqual(mepDesc.verificationStatus, 'MATCHED');
});
let failures = 0;
for (const [name, fn] of tests) {
    try { fn(); console.log('PASS ' + name); }
    catch (error) { failures++; console.error('FAIL ' + name + '\n' + error.stack); }
}
process.exitCode = failures ? 1 : 0;
