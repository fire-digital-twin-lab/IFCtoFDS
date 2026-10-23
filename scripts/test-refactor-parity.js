// Exact before/after checks for a structural refactor; never update source fixtures.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const baseline = process.argv[2] || 'f0c6d9c02342312266f2cfb8f9102833640061c3';

function engine(before) {
    const context = {console, FileReader: function () {}};
    context.window = context;
    const original = ['js/vendor/earcut.min.js', 'js/core/namespace.js', 'js/core/diagnostics.js', 'js/ifc/ifc-adapter.js', 'js/fds/fds-exporter.js'];
    const manifest = JSON.parse(fs.readFileSync(path.join(root, 'frontend/engine-scripts.json'), 'utf8'));
    const current = ['vendor/earcut.min.js', 'src/shared/namespace.js', 'src/shared/diagnostics.js', ...manifest.ifc, ...manifest.fds];
    for (const file of before ? original : current) {
        const source = before
            ? cp.execFileSync('git', ['show', baseline + ':' + file], {cwd: root, encoding: 'utf8', maxBuffer: 4e6})
            : fs.readFileSync(path.join(root, 'frontend', file), 'utf8');
        vm.runInNewContext(source, context, {filename: file});
    }
    return context.IfcFds;
}

const before = engine(true), after = engine(false);
const digest = text => crypto.createHash('sha256').update(text).digest('hex');
const results = [];
for (const filename of ['AC20-FZK-Haus.ifc', 'AC20-Institute-Var-2.ifc', 'IfcOpenShell-Duplex.ifc']) {
    const input = fs.readFileSync(path.join(root, 'examples', filename), 'utf8');
    const first = new before.ifc.IfcAdapter().parse(input, filename);
    const second = new after.ifc.IfcAdapter().parse(input, filename);
    assert.equal(JSON.stringify(second), JSON.stringify(first), filename + ': source model changed');
    const modes = {};
    for (const mode of ['hybrid', 'geom']) {
        const options = {mode, cellSize: 0.2, voxelSize: 0.2, openingThickening: 0};
        const expected = new before.fds.FdsExporter().exportFromIfcScene(first, options);
        const actual = new after.fds.FdsExporter().exportFromIfcScene(second, options);
        assert.equal(actual, expected, filename + ': ' + mode + ' FDS changed');
        modes[mode] = {identical: true, sha256: digest(actual)};
    }
    results.push({filename, source_sha256: digest(input), inventory_identical: true, modes});
    console.log(filename + ': inventory and hybrid/GEOM FDS are identical.');
}
const output = path.join(root, 'scripts/out/refactor-parity');
fs.mkdirSync(output, {recursive: true});
fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({baseline, results}, null, 2));
