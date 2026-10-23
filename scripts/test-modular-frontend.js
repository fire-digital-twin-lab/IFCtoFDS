const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../frontend');
const ctx = vm.createContext({console, setTimeout});
ctx.window = ctx;
ctx.IfcFds = {verified: {}, core: {atStage: (_stage, callback) => callback()}};
function load(name) { vm.runInContext(fs.readFileSync(path.join(root, 'src', name), 'utf8'), ctx, {filename: name}); }
for (const name of ['shared/diagnostics.js', 'shared/lifecycle.js', 'state/session-state.js', 'components/tabs.js', 'features/conversion/quick-workflow.js', 'features/sources/source-events.js']) load(name);

function element() {
    const listeners = new Set();
    return {style: {}, classList: {toggle() {}}, setAttribute() {},
        addEventListener: (_name, fn) => listeners.add(fn), removeEventListener: (_name, fn) => listeners.delete(fn),
        click() {for (const fn of listeners) fn();}, listenerCount: () => listeners.size};
}
const buttons = [element(), element()], panels = [element(), element()];
let changes = 0;
const tabs = new ctx.IfcFds.components.Tabs([
    {id: 'a', button: buttons[0], panel: panels[0], display: 'block'},
    {id: 'b', button: buttons[1], panel: panels[1], display: 'flex'}
], () => changes++);
tabs.mount(); tabs.mount(); buttons[1].click();
assert.equal(changes, 1); assert.equal(panels[1].style.display, 'flex');
tabs.destroy(); assert.equal(buttons[0].listenerCount(), 0);

(async () => {
    const state = ctx.IfcFds.state.createSessionState();
    const other = ctx.IfcFds.state.createSessionState();
    state.undoStack.push('a'); assert.equal(other.undoStack.length, 0);
    state.ifcSourceText = 'fixture'; state.ifcFileName = 'source.ifc';
    let complete;
    const calls = [];
    const context = new Proxy({state, getElements: () => ({}), getViewer: () => ({}),
        ifcAdapter: {parseAsync: (_text, _name, progress) => {
            progress(0.5); return new Promise(resolve => {complete = resolve;});
        }}, exporter: {}, parser: {}}, {
        get(target, key) {return key in target ? target[key] : () => calls.push(key);}
    });
    const quick = ctx.IfcFds.features.conversion.createQuickWorkflow(context);
    quick.addExportDiagnostic(new Error('display fixture'), {stage: 'viewer'});
    assert.equal(state.ifcModel.diagnostics[0].title, 'FDS display failed');
    const pending = quick.ensureFullModel();
    state.exportRequestId++;
    complete({elements: []});
    await assert.rejects(pending, /cancel/i);
    assert.equal(state.fullModel, null, 'A stale parse must not replace the active model');
    assert.ok(calls.includes('setLoadingProgress'), 'Progress remains wired after extraction');
    quick.cancelPendingExport();
    assert.ok(calls.includes('setExportBusy'), 'Cancellation releases the active conversion action');
    let sourceChange, finishRead, indexed = 0;
    const sourceState = ctx.IfcFds.state.createSessionState();
    ctx.IfcFds.ifc = {backendPreview: {cancel() {}}, IfcMeta: {buildModel() {indexed++;}}};
    ctx.IfcFds.verified.setFallback = () => {};
    ctx.IfcFds.workbench = {state: {visibilityStore: {resetVisibility() {}}}};
    const fileControl = {addEventListener(_type, handler) {sourceChange = handler;}, removeEventListener() {}};
    const sourceDependencies = new Proxy({state: sourceState,
        getElements: () => ({ifcFile: fileControl, ifcSourceName: {}, resetCamera: element()}),
        getViewer: () => ({}), viewBus: {clear() {}}}, {
        get(target, key) {return key in target ? target[key] : () => {};}
    });
    const sources = ctx.IfcFds.features.sources.createSourceEvents(sourceDependencies);
    sources.bind();
    sourceChange({target: {files: [{size: 8, name: 'late.ifc',
        arrayBuffer: () => new Promise(resolve => {finishRead = resolve;})}]}});
    sources.destroy();
    finishRead(new ArrayBuffer(8));
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(indexed, 0, 'A file read finishing after destroy must not restart parsing');
    console.log('Module state isolation, idempotent tabs, stale parse protection and cancellation wiring passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
