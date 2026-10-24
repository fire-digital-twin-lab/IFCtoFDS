// Unit and integration tests for EV Scenario Matrix Panel & Batch Queue (Task 5)
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// Setup VM context mimicking browser environment
class Element {
    constructor(tag = 'div') {
        this.tagName = tag.toUpperCase();
        this.children = [];
        this.style = {};
        this.listeners = {};
        this.hidden = false;
        this.disabled = false;
        this.textContent = '';
        this.value = '';
        this._id = '';
        this.className = '';
        this.attributes = {};
    }
    get id() {
        return this._id || '';
    }
    set id(val) {
        this._id = val;
        if (val) {
            elements[val] = this;
        }
    }
    appendChild(child) {
        this.children.push(child);
        return child;
    }
    replaceChildren(...newChildren) {
        this.children = newChildren.slice();
    }
    setAttribute(name, val) {
        this.attributes[name] = String(val);
    }
    getAttribute(name) {
        return this.attributes[name] || null;
    }
    addEventListener(name, handler) {
        (this.listeners[name] ||= []).push(handler);
    }
    click() {
        for (const handler of this.listeners.click || []) handler({ target: this });
    }
}

const elements = {};
function getOrCreateElement(id) {
    if (!elements[id]) {
        elements[id] = new Element('div');
        elements[id].id = id;
    }
    return elements[id];
}

const mockDoc = {
    getElementById(id) {
        return getOrCreateElement(id);
    },
    createElement(tag) {
        return new Element(tag);
    },
    querySelectorAll() {
        return [];
    }
};

const context = vm.createContext({
    console,
    document: mockDoc,
    window: {},
    IfcFds: {
        workbench: {
            state: {},
            panels: {}
        },
        ui: {}
    },
    setTimeout,
    clearTimeout,
    Promise,
    Object,
    Array,
    Math,
    JSON
});
context.window = context;
context.globalThis = context;
context.window.IfcFds = context.IfcFds;

// Load scenario store
const scenarioStorePath = path.join(__dirname, '../js/workbench/state/scenario-store.js');
vm.runInContext(fs.readFileSync(scenarioStorePath, 'utf8'), context, { filename: 'scenario-store.js' });

// Load EV scenario panel
const evPanelPath = path.join(__dirname, '../js/workbench/panels/ev-scenario-panel.js');
vm.runInContext(fs.readFileSync(evPanelPath, 'utf8'), context, { filename: 'ev-scenario-panel.js' });

async function runTests() {
    const wb = context.IfcFds.workbench;
    const panel = wb.panels.evScenarioPanel || context.IfcFds.ui.evScenarioPanel;
    assert.ok(panel, 'EV Scenario Panel must be exposed on IfcFds.workbench.panels.evScenarioPanel or IfcFds.ui.evScenarioPanel');

    const ScenarioStore = wb.state.ScenarioStore;
    const store = new ScenarioStore();
    const validSha = 'a'.repeat(64);

    // -------------------------------------------------------------
    // Test 1: Block when mapping is not MAPPING_VERIFIED
    // -------------------------------------------------------------
    console.log('Checking simulation permission enforcement...');
    // Initial status: DRAFT
    assert.equal(store.isSimulationPermitted(), false);
    assert.throws(() => {
        panel.generateScenarioMatrix({
            vehicleCounts: [1],
            spacingsM: [0.5],
            chemistryMix: [{ ebike: 1, auto: 0 }],
            doorStates: ['CLOSED'],
            baseBundleSha: validSha,
            scenarioStore: store
        });
    }, /Mapping must be MAPPING_VERIFIED before generating scenario batch/);

    // Status: INVALID_BASE_MAPPING
    store.setInvalidBaseMapping(validSha, 'REJECTED', 'Audit failure');
    assert.equal(store.isSimulationPermitted(), false);
    assert.throws(() => {
        panel.generateScenarioMatrix({
            vehicleCounts: [1],
            spacingsM: [0.5],
            chemistryMix: [{ ebike: 1, auto: 0 }],
            doorStates: ['CLOSED'],
            baseBundleSha: validSha,
            scenarioStore: store
        });
    }, /Mapping must be MAPPING_VERIFIED before generating scenario batch/);

    // Status: STALE (setting a different SHA)
    store.setBaseMapping(validSha);
    assert.equal(store.isSimulationPermitted(), true);
    store.setBaseMapping('b'.repeat(64));
    assert.equal(store.getStatus(), 'STALE');
    assert.equal(store.isSimulationPermitted(), false);
    assert.throws(() => {
        panel.generateScenarioMatrix({
            vehicleCounts: [1],
            spacingsM: [0.5],
            chemistryMix: [{ ebike: 1, auto: 0 }],
            doorStates: ['CLOSED'],
            baseBundleSha: validSha,
            scenarioStore: store
        });
    }, /Mapping must be MAPPING_VERIFIED before generating scenario batch/);

    // Now set valid verified mapping
    store.reset();
    store.setBaseMapping(validSha);
    assert.equal(store.isSimulationPermitted(), true);

    // -------------------------------------------------------------
    // Test 2: Matrix generation across dimensions & clamp to 3
    // -------------------------------------------------------------
    console.log('Checking scenario matrix permutation and clamping...');
    // 2x2 matrix clamped or tailored to 3 valid scenarios
    // vehicleCounts: [1, 2], doorStates: ['CLOSED', 'OPEN'] -> 4 combos, clamped to 3
    const scenarios = panel.generateScenarioMatrix({
        vehicleCounts: [1, 2],
        spacingsM: [0.5],
        chemistryMix: [
            { ebike: 0.5, auto: 0.5 }
        ],
        doorStates: ['CLOSED', 'OPEN'],
        baseBundleSha: validSha,
        scenarioStore: store,
        maxScenarios: 3
    });

    // Requirement: assert(scenarios.length === 3 && scenarios.every(s => s.ev_library_version));
    assert.equal(scenarios.length, 3, 'Expected exactly 3 scenarios after generation / clamping');
    assert.ok(scenarios.every(s => s.ev_library_version === '1.0.0'), 'All scenarios must have ev_library_version 1.0.0');
    assert.ok(scenarios.every(s => s.confidence === 'low' || s.confidence === 'medium'), 'All scenarios must have valid confidence');
    assert.ok(scenarios.every(s => typeof s.total_peak_hrr_mw === 'number' && s.total_peak_hrr_mw > 0), 'All scenarios must calculate total_peak_hrr_mw');
    assert.ok(scenarios.every(s => s.bundle_sha256 === validSha), 'Scenario must bind immutable base bundle SHA');
    assert.ok(scenarios.every(s => s.disclaimer && s.disclaimer.includes('Kịch bản giả định, cần kỹ sư PCCC thẩm định độc lập')), 'Scenario must include required disclaimer');

    // Test confidence hierarchy:
    // When only auto (NMC) is present -> confidence should be "medium"
    const autoOnly = panel.generateScenarioMatrix({
        vehicleCounts: [1],
        spacingsM: [1.0],
        chemistryMix: [{ ebike: 0, auto: 1.0 }],
        doorStates: ['CLOSED'],
        baseBundleSha: validSha,
        scenarioStore: store
    });
    assert.equal(autoOnly[0].confidence, 'medium', 'Auto NMC only scenario should have medium confidence');

    // When ebike is present -> confidence falls back to lowest ("low")
    const mixed = panel.generateScenarioMatrix({
        vehicleCounts: [2],
        spacingsM: [0.5],
        chemistryMix: [{ ebike: 0.5, auto: 0.5 }],
        doorStates: ['CLOSED'],
        baseBundleSha: validSha,
        scenarioStore: store
    });
    assert.equal(mixed[0].confidence, 'low', 'Mixed scenario with ebike must inherit lowest confidence ("low")');

    // -------------------------------------------------------------
    // Test 3: Batch Queue Dispatch and Aggregate Summary
    // -------------------------------------------------------------
    console.log('Checking batch queuing and summary reporting...');
    const dispatched = [];
    const mockDispatchJob = async (scenario) => {
        dispatched.push(scenario);
        // Simulate results: 2 pass, 1 inconclusive
        const isInc = scenario.scenario_id.endsWith('3');
        return {
            job_id: 'job_' + scenario.scenario_id,
            scenario_id: scenario.scenario_id,
            state: 'COMPLETED',
            mesh_status: isInc ? 'FAIL' : 'PASS',
            verdict: isInc ? 'INCONCLUSIVE' : 'PASS',
            peak_hrr_mw: scenario.total_peak_hrr_mw
        };
    };

    const batchOutput = await panel.queueScenarioBatch(scenarios, mockDispatchJob);
    assert.equal(dispatched.length, 3, 'All 3 scenarios must be dispatched');
    assert.equal(batchOutput.results.length, 3, 'All results must be collected');

    const summary = batchOutput.summary;
    assert.equal(summary.total, 3);
    assert.equal(summary.passed, 2);
    assert.equal(summary.inconclusive, 1);
    assert.equal(summary.rejected, 0);
    assert.ok(summary.disclaimer.includes('Kịch bản giả định, cần kỹ sư PCCC thẩm định độc lập'), 'Aggregate summary must contain independent verification disclaimer');
    assert.ok(summary.assumptions && summary.assumptions.length > 0, 'Aggregate summary must include engineering assumptions notes');

    // -------------------------------------------------------------
    // Test 4: UI DOM Builder & Event Wiring
    // -------------------------------------------------------------
    console.log('Checking UI mounting and form interactions...');
    const container = new Element('div');
    container.id = 'ev-scenario-panel-container';
    elements['ev-scenario-panel-container'] = container;

    panel.mount(container, {
        scenarioStore: store,
        getBaseBundleSha: () => validSha,
        dispatchJobFn: mockDispatchJob
    });

    // Check rendered inputs exist
    const btnGenerate = elements['ev-btn-generate-batch'];
    assert.ok(btnGenerate, 'Generate EV Fire Batch button must be mounted');
    const tableContainer = elements['ev-batch-results-table'];
    assert.ok(tableContainer, 'Results table container must be mounted');

    // Trigger button click
    btnGenerate.click();
    // Allow async job processing
    await new Promise(r => setTimeout(r, 20));

    // Verify results table is populated
    assert.ok(tableContainer.children.length > 0, 'Results table should have rows populated after generation');

    console.log('All EV Scenario Panel tests passed cleanly!');
}

runTests().catch(err => {
    console.error('Test failed:', err);
    process.exit(1);
});
