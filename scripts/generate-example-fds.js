const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const ctx = { window: {}, console, FileReader: function () {} };
ctx.window = ctx;

[
    'frontend/vendor/earcut.min.js',
    'frontend/src/shared/namespace.js',
    'frontend/src/shared/diagnostics.js',
    'frontend/src/engines/legacy/ifc/step-parser.js',
    'frontend/src/engines/legacy/ifc/openings.js',
    'frontend/src/engines/legacy/ifc/representations.js',
    'frontend/src/engines/legacy/ifc/clipping.js',
    'frontend/src/engines/legacy/ifc/triangulation.js',
    'frontend/src/engines/legacy/ifc/mesh-transforms.js',
    'frontend/src/engines/legacy/ifc/ifc-adapter.js',
    'frontend/src/engines/legacy/fds/representation-policy.js',
    'frontend/src/engines/legacy/fds/voxelizer.js',
    'frontend/src/engines/legacy/fds/serialization.js',
    'frontend/src/engines/legacy/fds/fds-exporter.js'
].forEach((file) => {
    vm.runInNewContext(
        fs.readFileSync(path.join(root, file), 'utf8'),
        ctx,
        { filename: file }
    );
});

const sourceName = 'AC20-FZK-Haus.ifc';
const sourcePath = path.join(root, 'examples', sourceName);
const outputPath = path.join(root, 'examples', 'AC20-FZK-Haus_obst-geom.fds');
const ifcAdapter = new ctx.IfcFds.ifc.IfcAdapter();
const exporter = new ctx.IfcFds.fds.FdsExporter();
const model = ifcAdapter.parse(fs.readFileSync(sourcePath, 'utf8'), sourceName);

const text = exporter.exportFromIfcScene(model, {
    mode: 'hybrid',
    cellSize: 0.1,
    voxelSize: 0.1,
    openingThickening: 0.05
});

fs.writeFileSync(outputPath, text);
console.log(`Generated ${path.relative(root, outputPath)} (${text.length} characters).`);
