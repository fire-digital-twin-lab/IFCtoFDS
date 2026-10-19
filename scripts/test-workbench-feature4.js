// Regressions for Feature 4: 3D Workbench IFC/FDS (F01 - F08)
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// Setup VM context
const context = vm.createContext({
    console,
    IfcFds: {
        workbench: {
            selection: { selectionManager: {} }
        }
    },
    THREE: {
        Color: function (c) {
            this.hex = 0;
            this.getHex = () => this.hex;
            this.setHex = h => { this.hex = h; };
            this.clone = () => new context.THREE.Color();
            this.copy = other => { this.hex = other.hex; };
        },
        Box3: function () {
            this.min = { x: 0, y: 0, z: 0 };
            this.max = { x: 0, y: 0, z: 0 };
            this.makeEmpty = () => this;
            this.isEmpty = () => false;
            this.expandByObject = obj => {
                if (obj._box) {
                    this.min = Object.assign({}, obj._box.min);
                    this.max = Object.assign({}, obj._box.max);
                }
                return this;
            };
        }
    }
});
context.window = context;
context.globalThis = context;

// Load workbench modules
for (const file of [
    'events/workbench-events.js',
    'state/selection-store.js',
    'state/visibility-store.js',
    'state/scenario-store.js',
    'state/workbench-store.js',
    'navigation/color-overlay.js',
    'navigation/model-tree.js',
    'selection/selection-query.js'
]) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/workbench', file), 'utf8'), context);
}

context.IfcFds.viewer = {};
vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/viewer/scene-viewer.js'), 'utf8'), context);

const wb = context.IfcFds.workbench;
const tests = [];
function test(name, fn) { tests.push([name, fn]); }

// F01: indexElements preserves hydrated manifest metadata
test('F01: indexElements preserves hydrated manifest metadata when loading FDS', () => {
    const store = new wb.state.SelectionStore();
    const ifcElement = {
        entityKey: 'model.ifc:101',
        sourceId: 'model.ifc',
        globalId: 'GUID_101',
        stepId: 101,
        name: 'Wall_101',
        ifcType: 'IFCWALL'
    };
    store.indexElements([ifcElement], 'model.ifc');

    // Simulate manifest hydration
    const records = [{
        entity_key: 'model.ifc:101',
        source_id: 'model.ifc',
        step_id: 101,
        global_id: 'GUID_101',
        simulation_role: 'PASSIVE_OBSTACLE',
        mapping_strategy: 'OBST',
        review_status: 'APPROVED',
        mep_data: { category: 'FIRE_SUPPRESSION', system_names: ['Sprinkler System'] }
    }];
    const report = { element_statuses: { 'model.ifc:101': 'PASS' } };
    store.hydrateManifest(records, report);

    const descBefore = store.getDescriptor('model.ifc:101');
    assert.equal(descBefore.verificationStatus, 'PASS');
    assert.equal(descBefore.simulationRole, 'PASSIVE_OBSTACLE');
    assert.equal(descBefore.mappingStrategy, 'OBST');
    assert.equal(descBefore.reviewStatus, 'APPROVED');

    // Now simulate loadFdsText indexing an FDS primitive mapped to this IFC element
    const fdsPrimitive = {
        id: 'OBST_101',
        ifcSource: { entityKey: 'model.ifc:101', sourceId: 'model.ifc', globalId: 'GUID_101' },
        bounds: { xmin: 0, xmax: 2, ymin: 0, ymax: 1, zmin: 0, zmax: 3 }
    };
    store.indexElements([fdsPrimitive], 'model.fds');

    // Must NOT overwrite the authoritative verified metadata!
    const descAfter = store.getDescriptor('model.ifc:101');
    assert.equal(descAfter.verificationStatus, 'PASS', 'verificationStatus must be preserved');
    assert.equal(descAfter.simulationRole, 'PASSIVE_OBSTACLE', 'simulationRole must be preserved');
    assert.equal(descAfter.mappingStrategy, 'OBST', 'mappingStrategy must be preserved');
    assert.equal(descAfter.reviewStatus, 'APPROVED', 'reviewStatus must be preserved');
    assert.ok(descAfter.fdsPrimitives && descAfter.fdsPrimitives.length === 1, 'FDS primitive must be linked');
    assert.ok(descAfter.fdsPrimitiveIds && descAfter.fdsPrimitiveIds.includes('OBST_101'), 'FDS primitive ID must be recorded');

    // Selection lookup by raw STEP ID must resolve to the authoritative descriptor
    store.setSelection('101');
    const selected = store.getSelection();
    assert.equal(selected.length, 1);
    assert.equal(selected[0].entityKey, 'model.ifc:101');
    assert.equal(selected[0].verificationStatus, 'PASS');
    assert.ok(store.isSelected('101'));
    assert.ok(store.isSelected('model.ifc:101'));
});

// F02: ModelTree groups by verificationStatus and reviewStatus separately
test('F02: ModelTree groups validation state by verificationStatus, not review_status', () => {
    const tree = new wb.navigation.SemanticModelTree('test-tree');
    const descriptors = [
        {
            entityKey: 'elem:1',
            verificationStatus: 'DEVIATED',
            reviewStatus: 'NOT_REQUIRED',
            raw: { verification_status: 'DEVIATED', review_status: 'NOT_REQUIRED' }
        },
        {
            entityKey: 'elem:2',
            verificationStatus: 'PASS',
            reviewStatus: 'APPROVED',
            raw: { verification_status: 'PASS', review_status: 'APPROVED' }
        }
    ];

    const validationGroups = tree._groupDescriptors(descriptors, 'validation');
    assert.ok(validationGroups['DEVIATED'], 'Validation grouping must contain DEVIATED group');
    assert.equal(validationGroups['DEVIATED'].length, 1);
    assert.equal(validationGroups['DEVIATED'][0].entityKey, 'elem:1');
    assert.ok(validationGroups['PASS'], 'Validation grouping must contain PASS group');
    assert.equal(validationGroups['PASS'].length, 1);
    assert.equal(validationGroups['PASS'][0].entityKey, 'elem:2');
    assert.equal(validationGroups['NOT_REQUIRED'], undefined, 'NOT_REQUIRED should not mask validation status');

    const reviewGroups = tree._groupDescriptors(descriptors, 'review');
    assert.ok(reviewGroups['NOT_REQUIRED'], 'Review grouping must contain NOT_REQUIRED');
    assert.ok(reviewGroups['APPROVED'], 'Review grouping must contain APPROVED');
});

// F03: applyFdsClipVisibility uses bounding box intersection
test('F03: applyFdsClipVisibility uses bounding box intersection, not strict containment', () => {
    let visibilityResult = null;
    const node = {
        isMesh: true,
        // Continuous wall spanning height z = -6 to 0 in IFC coordinates
        // In Three world coords (Three Y is IFC Z, Three Z is IFC Y):
        _box: {
            min: { x: 0, y: -6.0, z: 0 },
            max: { x: 10, y: 0.0, z: 0.3 }
        }
    };
    const viewer = {
        fdsGroup: {
            updateMatrixWorld: () => {},
            traverse: fn => fn(node)
        },
        clipRanges: {
            xmin: -Infinity, xmax: Infinity,
            ymin: -Infinity, ymax: Infinity,
            // Slicing at storey B2: height -6m to -3m
            zmin: -6.0, zmax: -3.0
        }
    };
    const applyClip = context.IfcFds.viewer.SceneViewer.prototype.applyFdsClipVisibility;
    applyClip.call(viewer);

    // Because the wall from -6m to 0m intersects the range [-6m, -3m], it must remain VISIBLE
    assert.equal(node._visibilityChannels && node._visibilityChannels.section, true, 'Boundary elements intersecting section plane must remain visible');
});

// F04: ColorOverlayEngine looks up descriptors from SelectionStore
test('F04: ColorOverlayEngine looks up authoritative descriptors from SelectionStore', () => {
    const store = new wb.state.SelectionStore();
    context.IfcFds.workbench.state.selectionStore = store;

    const desc = {
        entityKey: 'model.ifc:55',
        sourceId: 'model.ifc',
        globalId: 'GUID_55',
        raw: { verification_status: 'PASS' }
    };
    store.indexElements([desc], 'model.ifc');

    const mesh = {
        isMesh: true,
        userData: { type: 'IFC', entityKey: 'model.ifc:55' },
        material: { color: new context.THREE.Color() }
    };
    const group = { traverse: fn => fn(mesh) };
    const engine = new wb.navigation.ColorOverlayEngine({ fdsGroup: null, ifcGroup: group });
    engine.updateLegend = () => {};

    engine.applyColorMode('verification');
    // Must be PASS green (0x10b981), not NOT_RUN slate
    assert.equal(mesh.material.color.hex, 0x10b981, 'Mesh must be colored with verified status from SelectionStore');
});

// F05: hydrateManifest fallback verifies sourceId
test('F05: hydrateManifest fallback verifies sourceId before matching', () => {
    const store = new wb.state.SelectionStore();
    const elemA = { entityKey: 'sourceA:500', sourceId: 'sourceA', stepId: 500 };
    const elemB = { entityKey: 'sourceB:500', sourceId: 'sourceB', stepId: 500 };
    store.indexElements([elemA, elemB], 'display.ifc');

    // Hydrate record specifically for sourceA
    const records = [{
        source_id: 'sourceA',
        step_id: 500,
        simulation_role: 'PASSIVE_OBSTACLE'
    }];
    store.hydrateManifest(records, null);

    const descA = store.getDescriptor('sourceA:500');
    const descB = store.getDescriptor('sourceB:500');
    assert.equal(descA.simulationRole, 'PASSIVE_OBSTACLE');
    assert.notEqual(descB.simulationRole, 'PASSIVE_OBSTACLE', 'sourceB must not be accidentally hydrated');
});

// F06: findConnectedMepKeys supports source_element_id / target_element_id schema
test('F06: findConnectedMepKeys resolves connection schema from backend MEPConnection', () => {
    const query = wb.selection.SelectionQuery;
    const mepGraph = {
        connections: [
            { source_element_id: 'FAN_01', target_element_id: 'DUCT_01' },
            { source_element_id: 'DUCT_01', target_element_id: 'TERMINAL_01' }
        ]
    };
    const connected = query.findConnectedMepKeys('FAN_01', mepGraph);
    assert.ok(connected.includes('FAN_01'));
    assert.ok(connected.includes('DUCT_01'));
    assert.ok(connected.includes('TERMINAL_01'));
    assert.equal(connected.length, 3);
});

// F07: IFC Type mode correctly categorizes MEP and reaches type branches
test('F07: ifc-type color mode correctly styles MEP elements and eliminates dead code', () => {
    const colors = new wb.navigation.ColorOverlayEngine();
    // Element with category 'other' but ifcType 'IFCDUCTSEGMENT'
    const duct = { ifcType: 'IFCDUCTSEGMENT', category: 'other' };
    const hex = colors._getColorForDescriptor(duct, 'ifc-type');
    assert.equal(hex, 0xec4899, 'IFCDUCTSEGMENT must be styled as MEP pink, not purple other');

    const wall = { ifcType: 'IFCWALL', category: 'other' };
    assert.equal(colors._getColorForDescriptor(wall, 'ifc-type'), 0x94a3b8, 'IFCWALL must be styled as structure');

    const catFn = context.IfcFds.viewer.categoryForIfcType;
    assert.equal(catFn('IFCDUCTSEGMENT'), 'mep');
    assert.equal(catFn('IFCPIPESEGMENT'), 'mep');
    assert.equal(catFn('IFCFLOWTERMINAL'), 'mep');
    assert.equal(catFn('IFCWALLSTANDARDCASE'), 'structure');
});

// F08: clearGroup detaches Three.js children via group.remove()
test('F08: clearGroup detaches Three.js parent references and disposes assets', () => {
    let disposedGeom = false;
    let disposedMat = false;
    const child = {
        geometry: { dispose: () => { disposedGeom = true; } },
        material: { dispose: () => { disposedMat = true; } },
        traverse: fn => fn(child)
    };
    const group = {
        children: [child],
        remove: function (c) {
            const idx = this.children.indexOf(c);
            if (idx >= 0) this.children.splice(idx, 1);
            c.parent = null;
        }
    };
    child.parent = group;

    const clearGroupFn = context.IfcFds.viewer.clearGroup;
    clearGroupFn(group);

    assert.equal(group.children.length, 0, 'Children array must be cleared');
    assert.equal(child.parent, null, 'Child parent reference must be reset to null');
    assert.ok(disposedGeom, 'Geometry must be disposed');
    assert.ok(disposedMat, 'Material must be disposed');
});

// Run all test cases
let passed = 0;
for (const [name, fn] of tests) {
    try {
        fn();
        console.log(`PASS ${name}`);
        passed++;
    } catch (err) {
        console.error(`FAIL ${name}: ${err.message}`);
        console.error(err.stack);
        process.exit(1);
    }
}
console.log(`\nAll ${passed}/${tests.length} Feature 4 Workbench tests passed successfully.`);
