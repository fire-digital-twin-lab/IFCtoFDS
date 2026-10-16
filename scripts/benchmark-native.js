const fs = require('fs');
const vm = require('vm');
const path = require('path');
const root = path.resolve(__dirname, '..');
const ctx = {console, FileReader: function () {}};
ctx.window = ctx;
['js/vendor/earcut.min.js', 'js/core/namespace.js', 'js/core/diagnostics.js',
    'js/ifc/ifc-adapter.js', 'js/fds/fds-exporter.js'].forEach(file => {
    vm.runInNewContext(fs.readFileSync(path.join(root, file), 'utf8'), ctx, {filename:file});
});
const start = performance.now();
const model = new ctx.IfcFds.ifc.IfcAdapter().parse(fs.readFileSync(process.argv[2], 'utf8'), path.basename(process.argv[2]));
const parsed = performance.now();
const text = new ctx.IfcFds.fds.FdsExporter().exportFromIfcScene(model, {mode:'geom', cellSize:0.2});
fs.writeFileSync(process.argv[3], text);
console.log(JSON.stringify({parse_s:(parsed-start)/1000, serialize_s:(performance.now()-parsed)/1000, bytes:Buffer.byteLength(text)}));
