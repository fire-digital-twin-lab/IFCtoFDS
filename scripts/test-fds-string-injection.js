// An IFC name with a line break must not start a new FDS namelist in the exported deck.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = path.resolve(__dirname, '..');
const ctx = {console, FileReader: function () {}};
ctx.window = ctx;
['js/vendor/earcut.min.js', 'js/core/namespace.js', 'js/core/diagnostics.js',
    'js/ifc/ifc-adapter.js', 'js/fds/fds-exporter.js'].forEach(file => {
    vm.runInNewContext(fs.readFileSync(path.join(root, file), 'utf8'), ctx, {filename: file});
});
const adapter = new ctx.IfcFds.ifc.IfcAdapter();
const exporter = new ctx.IfcFds.fds.FdsExporter();
const source = fs.readFileSync(path.join(root, 'examples/AC20-FZK-Haus.ifc'), 'utf8');
const scene = adapter.parse(source, 'source.ifc', {skipBoxOpenings: false});
const wall = scene.elements.find(e => e.name === 'Wand-Ext-ERDG-1');
wall.name = "Wall'\n&ZZZ_INJECT X=1 /\r\n&ZZZ_INJECT Y=2 /";
wall.globalId = "G\n&ZZZ_INJECT Z=3 /";
const text = exporter.exportFromIfcScene(scene, {mode: 'geom'});
const injected = text.split(/\r\n|\r|\n/).filter(line => /^\s*&ZZZ_INJECT/.test(line));
assert.deepStrictEqual(injected, [], 'a line break in an IFC name started a new namelist');
assert(text.includes('! IFC_SOURCE'), 'provenance comments must still be written');
console.log('FDS string injection guard: ok');
