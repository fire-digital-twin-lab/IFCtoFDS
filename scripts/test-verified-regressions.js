const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = path.resolve(__dirname, '..');
const ctx = {console, FileReader: function () {}};
ctx.window = ctx;
['js/vendor/earcut.min.js', 'js/core/namespace.js', 'js/core/diagnostics.js',
    'js/ifc/ifc-adapter.js', 'js/fds/fds-exporter.js', 'js/fds/namelist-parser.js'].forEach(file => {
    vm.runInNewContext(fs.readFileSync(path.join(root, file), 'utf8'), ctx, {filename:file});
});
const adapter = new ctx.IfcFds.ifc.IfcAdapter();
const exporter = new ctx.IfcFds.fds.FdsExporter();
const source = fs.readFileSync(path.join(root, 'examples/AC20-FZK-Haus.ifc'), 'utf8');
const preview = adapter.parse(source, 'source.ifc', {skipBoxOpenings:true});
const complete = adapter.parse(source, 'source.ifc', {skipBoxOpenings:false});
assert.throws(() => exporter.exportFromIfcScene(preview, {mode:'geom'}), /Incomplete opening processing/);
const text = exporter.exportFromIfcScene(complete, {mode:'geom'});
assert(text.includes('&GEOM'));
const wall = complete.elements.find(e => e.name === 'Wand-Ext-ERDG-1');
// Exact section membership of exported triangles, not triangle-count heuristics.
function rayHitsAt(y, z) {
    let hits = 0;
    const m = wall.geomExportMesh;
    m.faces.forEach(face => {
        const a=m.vertices[face[0]], b=m.vertices[face[1]], c=m.vertices[face[2]];
        const d=(b[1]-a[1])*(c[2]-a[2])-(c[1]-a[1])*(b[2]-a[2]);
        if (Math.abs(d)<1e-10) return;
        const u=((y-a[1])*(c[2]-a[2])-(c[1]-a[1])*(z-a[2]))/d;
        const v=((b[1]-a[1])*(z-a[2])-(y-a[1])*(b[2]-a[2]))/d;
        if (u>1e-6 && v>1e-6 && u+v<1-1e-6) hits++;
    });
    return hits;
}
// Host wall is X-normal. At least one interior point in each source opening
// must be transparent through the exported wall; use off-center points to avoid edges.
wall.openings.forEach(opening => {
    const verts=opening.mesh.vertices;
    const ys=verts.map(v=>v[1]), zs=verts.map(v=>v[2]);
    const y=Math.min(...ys)+.473*(Math.max(...ys)-Math.min(...ys));
    const z=Math.min(...zs)+.531*(Math.max(...zs)-Math.min(...zs));
    assert.strictEqual(rayHitsAt(y,z),0,'Opening was blocked in canonical export mesh');
});
const parser = new ctx.IfcFds.fds.FdsNamelistParser();
const parsed = parser.parse('! IFC_SOURCE {"entity_key":"source:1","source_id":"source","global_id":"GUID","step_id":1,"ifc_type":"IfcWall"}\n&OBST ID=\'wall\', XB=0,1,0,1,0,1 /');
assert.strictEqual(parsed.obsts[0].ifcSource.entityKey,'source:1');
console.log('Canonical export completeness, opening rays and JSON provenance passed.');
