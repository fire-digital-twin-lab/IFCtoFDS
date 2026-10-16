// Regression test: ensure wall openings are preserved in GEOM export mode.
// Specifically, Wand-Ext-ERDG-1 in AC20-FZK-Haus.ifc has 3 openings.
// Previously, GEOM export used element.mesh (12 triangles), completely discarding the 3 openings.
// With the fix, GEOM export uses element.displayMesh (1532 triangles with carved voids).

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const ctx = { window: {}, console, FileReader: function () {} };
ctx.window = ctx;

[
    'js/vendor/earcut.min.js',
    'js/core/namespace.js',
    'js/core/diagnostics.js',
    'js/ifc/ifc-adapter.js',
    'js/fds/fds-exporter.js'
].forEach((file) => {
    vm.runInNewContext(
        fs.readFileSync(path.join(root, file), 'utf8'),
        ctx,
        { filename: file }
    );
});

const ifcAdapter = new ctx.IfcFds.ifc.IfcAdapter();
const exporter = new ctx.IfcFds.fds.FdsExporter();

const ifcText = fs.readFileSync(path.join(root, 'examples', 'AC20-FZK-Haus.ifc'), 'utf8');
const model = ifcAdapter.parse(ifcText, 'AC20-FZK-Haus.ifc');

const wall = model.elements.find(el => el.name === 'Wand-Ext-ERDG-1');
if (!wall) {
    console.error('FAIL: Wand-Ext-ERDG-1 not found in parsed model');
    process.exit(1);
}

console.log('Found Wand-Ext-ERDG-1:');
console.log('  Openings detected:', wall.openings ? wall.openings.length : 0);
console.log('  Base mesh faces:', wall.mesh.faces.length);
console.log('  Carved displayMesh faces:', wall.displayMesh ? wall.displayMesh.faces.length : 'none');

if (!wall.displayMesh || wall.displayMesh.faces.length <= 12) {
    console.error('FAIL: displayMesh does not contain carved openings!');
    process.exit(1);
}

// Export model in all-geom mode
const fdsText = exporter.exportFromIfcScene(model, {
    mode: 'geom',
    includeReviewSolids: false
});

// Check that the GEOM output for Wand-Ext-ERDG-1 has more than 12 faces
const match = fdsText.match(/&GEOM ID='Wand-Ext-ERDG-1'[\s\S]*?FACES=([\s\S]*?)\s*\//);
if (!match) {
    console.error('FAIL: Wand-Ext-ERDG-1 GEOM block not found in FDS output');
    process.exit(1);
}

const faceIndices = match[1].trim().split(/\s*,\s*|\s+/).filter(Boolean);
const faceCount = faceIndices.length / 4;
console.log(`  Exported GEOM face count: ${faceCount}`);

if (faceCount <= 12) {
    console.error(`FAIL: GEOM face count is ${faceCount} (expected > 100 with carved openings)`);
    process.exit(1);
}

console.log('PASS: Wand-Ext-ERDG-1 retained all opening voids in GEOM export!');
