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
    // Test 2.1: Vehicle spacing offset prevents geometry collision
    // -------------------------------------------------------------
    console.log('Checking vehicle spacing offset and non-overlapping centers...');
    const multiEbike = panel.generateScenarioMatrix({
        vehicleCounts: [2],
        spacingsM: [0.5],
        chemistryMix: [{ ebike: 1.0, auto: 0 }],
        doorStates: ['CLOSED'],
        baseBundleSha: validSha,
        scenarioStore: store
    });
    assert.equal(multiEbike[0].ev_selections.length, 2);
    const ebike0 = multiEbike[0].ev_selections[0];
    const ebike1 = multiEbike[0].ev_selections[1];
    const ebikeSpacing = ebike1.position[0] - ebike0.position[0];
    assert.ok(
        ebikeSpacing >= (1.8 + 0.5 - 1e-4),
        `E-bike vehicle centers must be spaced by at least vehicleWidth + spacing (expected >= 2.3, got ${ebikeSpacing})`
    );

    const multiAuto = panel.generateScenarioMatrix({
        vehicleCounts: [2],
        spacingsM: [1.0],
        chemistryMix: [{ ebike: 0, auto: 1.0 }],
        doorStates: ['CLOSED'],
        baseBundleSha: validSha,
        scenarioStore: store
    });
    assert.equal(multiAuto[0].ev_selections.length, 2);
    const auto0 = multiAuto[0].ev_selections[0];
    const auto1 = multiAuto[0].ev_selections[1];
    const autoSpacing = auto1.position[0] - auto0.position[0];
    assert.ok(
        autoSpacing >= (4.5 + 1.0 - 1e-4),
        `Auto vehicle centers must be spaced by at least vehicleWidth + spacing (expected >= 5.5, got ${autoSpacing})`
    );

    // Verify preview placeholder fragment header note
    assert.ok(
        multiAuto[0].fds_fragment.includes('! NOTE: Preview placeholder fragment. Authoritative scenario emission generated via ifc_to_fds.fire.scenario_emitter'),
        'fds_fragment must include preview placeholder note'
    );

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
    const inputSocEl = elements['ev-input-soc-percent'];
    assert.ok(inputSocEl, 'SoC percent input must be mounted');
    assert.equal(inputSocEl.value, '80', 'Default SoC percent input must be 80');
    const tableContainer = elements['ev-batch-results-table'];
    assert.ok(tableContainer, 'Results table container must be mounted');

    // Trigger button click
    btnGenerate.click();
    // Allow async job processing
    await new Promise(r => setTimeout(r, 20));

    // Verify results table is populated
    assert.ok(tableContainer.children.length > 0, 'Results table should have rows populated after generation');

    // -------------------------------------------------------------
    // Test 5: SoC (State of Charge) Dimension
    // -------------------------------------------------------------
    console.log('Checking SoC matrix dimension and scaling...');
    const socScenarios = panel.generateScenarioMatrix({
        vehicleCounts: [1],
        spacingsM: [0.5],
        chemistryMix: [{ ebike: 0, auto: 1.0 }],
        doorStates: ['CLOSED'],
        socPercent: [50, 80, 100],
        baseBundleSha: validSha,
        scenarioStore: store
    });
    assert.equal(socScenarios.length, 3, 'Should generate 3 scenarios across SoC dimension');
    assert.equal(socScenarios[0].soc_percent, 50);
    assert.equal(socScenarios[1].soc_percent, 80);
    assert.equal(socScenarios[2].soc_percent, 100);
    assert.equal(socScenarios[0].ev_selections[0].soc_percent, 50);
    assert.equal(socScenarios[1].ev_selections[0].soc_percent, 80);
    assert.equal(socScenarios[2].ev_selections[0].soc_percent, 100);
    assert.ok(socScenarios[0].total_peak_hrr_mw < socScenarios[1].total_peak_hrr_mw, '50% SoC peak HRR must be less than 80% SoC');
    assert.ok(socScenarios[1].total_peak_hrr_mw < socScenarios[2].total_peak_hrr_mw, '80% SoC peak HRR must be less than 100% SoC');

    // Default SoC percent should be [80]
    const defaultSocScenario = panel.generateScenarioMatrix({
        vehicleCounts: [1],
        spacingsM: [0.5],
        chemistryMix: [{ ebike: 0, auto: 1.0 }],
        doorStates: ['CLOSED'],
        baseBundleSha: validSha,
        scenarioStore: store
    });
    assert.equal(defaultSocScenario[0].soc_percent, 80, 'Default scenario should have soc_percent 80');

    // -------------------------------------------------------------
    // Test 6: HTTP 429 Handling, Retry & Numeric Status Safety
    // -------------------------------------------------------------
    console.log('Checking HTTP 429 handling, retry with backoff, and numeric status safety...');

    // 6.1 Temporary 429 succeeds on retry with backoff
    let attemptCount429 = 0;
    const retryDispatch = async (scenario) => {
        attemptCount429++;
        if (attemptCount429 === 1) {
            // Return numeric 429 status object on first attempt
            return { status: 429, error: 'Queue is full' };
        }
        return {
            job_id: 'job_retry_success',
            scenario_id: scenario.scenario_id,
            state: 'COMPLETED',
            verdict: 'PASS',
            peak_hrr_mw: scenario.total_peak_hrr_mw
        };
    };
    const retryBatchOutput = await panel.queueScenarioBatch(
        [socScenarios[0]],
        retryDispatch,
        { maxRetries: 2, retryDelayMs: 10 }
    );
    assert.equal(attemptCount429, 2, 'Should retry on 429');
    assert.equal(retryBatchOutput.results[0].state, 'COMPLETED');
    assert.equal(retryBatchOutput.summary.passed, 1);

    // 6.2 Persistent 429 gracefully marks QUEUED_WAITING and does not abort batch
    const persistent429Dispatch = async (scenario) => {
        return { status: 429, error: 'Queue is full' };
    };
    const queuedWaitingOutput = await panel.queueScenarioBatch(
        [socScenarios[0]],
        persistent429Dispatch,
        { maxRetries: 1, retryDelayMs: 5 }
    );
    assert.equal(queuedWaitingOutput.results.length, 1);
    assert.equal(queuedWaitingOutput.results[0].state, 'QUEUED_WAITING');
    assert.equal(queuedWaitingOutput.summary.queued_waiting, 1);
    assert.equal(queuedWaitingOutput.summary.rejected, 0);

    // 6.3 Dispatch throws Error with 429 status or message
    const error429Dispatch = async (scenario) => {
        const err = new Error('HTTP 429 Too Many Requests');
        err.status = 429;
        throw err;
    };
    const errBatchOutput = await panel.queueScenarioBatch(
        [socScenarios[0]],
        error429Dispatch,
        { maxRetries: 1, retryDelayMs: 5 }
    );
    assert.equal(errBatchOutput.results[0].state, 'QUEUED_WAITING');
    assert.equal(errBatchOutput.summary.queued_waiting, 1);

    // -------------------------------------------------------------
    // Test 7: JobService Polling & Terminal Status Mapping
    // -------------------------------------------------------------
    console.log('Checking JobService polling and status mapping...');

    // 7.1 Async queued job polls until COMPLETED (must NOT treat QUEUED/RUNNING as rejected)
    const jobPollStates = ['QUEUED', 'RUNNING', 'COMPLETED'];
    let pollIndex = 0;
    const asyncDispatch = async (scenario) => {
        return {
            id: 'job_async_1',
            status: 202,
            state: 'QUEUED'
        };
    };
    const mockPollFn = async (jobId) => {
        assert.equal(jobId, 'job_async_1');
        const state = jobPollStates[Math.min(pollIndex++, jobPollStates.length - 1)];
        return {
            id: jobId,
            state: state,
            verdict: state === 'COMPLETED' ? 'PASS' : undefined,
            peak_hrr_mw: 3.6
        };
    };

    const polledBatchOutput = await panel.queueScenarioBatch(
        [socScenarios[0]],
        asyncDispatch,
        { pollJobFn: mockPollFn, pollIntervalMs: 10 }
    );
    assert.equal(polledBatchOutput.results[0].state, 'COMPLETED');
    assert.equal(polledBatchOutput.summary.passed, 1);
    assert.equal(polledBatchOutput.summary.rejected, 0);

    // 7.2 Async job polls until FAILED -> mapped to rejected
    pollIndex = 0;
    const failPollStates = ['QUEUED', 'FAILED'];
    const mockFailPollFn = async (jobId) => {
        const state = failPollStates[Math.min(pollIndex++, failPollStates.length - 1)];
        return { id: jobId, state: state, error: 'Solver divergence' };
    };
    const failedBatchOutput = await panel.queueScenarioBatch(
        [socScenarios[0]],
        asyncDispatch,
        { pollJobFn: mockFailPollFn, pollIntervalMs: 10 }
    );
    assert.equal(failedBatchOutput.results[0].state, 'FAILED');
    assert.equal(failedBatchOutput.summary.rejected, 1);

    // 7.3 Async job polls until TIMED_OUT -> mapped to rejected
    pollIndex = 0;
    const timeoutPollStates = ['QUEUED', 'TIMED_OUT'];
    const mockTimeoutPollFn = async (jobId) => {
        const state = timeoutPollStates[Math.min(pollIndex++, timeoutPollStates.length - 1)];
        return { id: jobId, state: state };
    };
    const timeoutBatchOutput = await panel.queueScenarioBatch(
        [socScenarios[0]],
        asyncDispatch,
        { pollJobFn: mockTimeoutPollFn, pollIntervalMs: 10 }
    );
    assert.equal(timeoutBatchOutput.results[0].state, 'TIMED_OUT');
    assert.equal(timeoutBatchOutput.summary.rejected, 1);

    console.log('All EV Scenario Panel tests passed cleanly!');
}

runTests().catch(err => {
    console.error('Test failed:', err);
    process.exit(1);
});
