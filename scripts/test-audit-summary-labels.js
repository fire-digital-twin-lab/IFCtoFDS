// Role counts can include entities that were not written to FDS.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../js/app-controller.js'), 'utf8');
const start = source.indexOf('    function renderAuditReport(');
const end = source.indexOf('\n    function ', start + 1);
assert.ok(start >= 0 && end > start, 'Audit renderer was not found');

function element() {
    return {
        children: [],
        appendChild(child) { this.children.push(child); },
        replaceChildren() { this.children = []; }
    };
}
const auditBody = element();
const context = vm.createContext({
    els: {auditBody}, document: {createElement: element},
    updateGlobalStatusBadge() {}, renderAuditDrawer() {}
});
vm.runInContext(source.slice(start, end), context);

const report = {
    status: 'MAPPING_VERIFIED', mapping_status: 'MAPPING_VERIFIED', simulation_status: 'NOT_RUN',
    coverage: {
        representation: {REFERENCE_GEOMETRY: 2, PASSIVE_OBSTACLE: 7, OPERATIONAL_MEP: 3},
        fds_export: {entities: 5, primitives: 6, obst: 1, geom: 5, verified_entities: 4}
    }
};
const before = JSON.stringify(report);
context.renderAuditReport(report);
const lines = auditBody.children.map(node => node.textContent);
assert.ok(lines.includes('Role classification in scope (see FDS written for export counts): reference objects: 2; passive obstacles: 7; operational objects: 3'));
assert.ok(lines.includes('FDS written: 5 entities / 6 primitives (1 OBST, 5 GEOM). Independently verified: 4.'));
assert.equal(JSON.stringify(report), before, 'Rendering must preserve report data');

context.renderAuditReport({status: 'INCONCLUSIVE'});
const fallback = auditBody.children.map(node => node.textContent).join('\n');
assert.match(fallback, /reference objects: 0; passive obstacles: 0; operational objects: 0/);
assert.doesNotMatch(fallback, /FDS written:|undefined entities/);
console.log('Audit summary labels: role classification, FDS export counts and missing coverage passed.');
