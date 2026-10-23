const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const ctx = { console };
ctx.self = ctx;
ctx.window = ctx;
ctx.importScripts = (...files) => files.forEach((file) => {
    const resolved = path.resolve(root, 'frontend/src/workers', file);
    vm.runInContext(fs.readFileSync(resolved, 'utf8'), ctx, { filename: resolved });
});

let response = null;
ctx.postMessage = (message) => { response = message; };
vm.createContext(ctx);
vm.runInContext(
    fs.readFileSync(path.join(root, 'frontend/src/workers/fds-export-worker.js'), 'utf8'),
    ctx,
    { filename: 'fds-export-worker.js' }
);

[
    'frontend/vendor/earcut.min.js',
    'frontend/src/engines/legacy/ifc/step-parser.js',
    'frontend/src/engines/legacy/ifc/openings.js',
    'frontend/src/engines/legacy/ifc/representations.js',
    'frontend/src/engines/legacy/ifc/clipping.js',
    'frontend/src/engines/legacy/ifc/triangulation.js',
    'frontend/src/engines/legacy/ifc/mesh-transforms.js',
    'frontend/src/engines/legacy/ifc/ifc-adapter.js'
].forEach((file) => {
    vm.runInContext(
        fs.readFileSync(path.join(root, file), 'utf8'),
        ctx,
        { filename: file }
    );
});

const ifcAdapter = new ctx.IfcFds.ifc.IfcAdapter();
const ifcText = fs.readFileSync(path.join(root, 'examples', 'AC20-FZK-Haus.ifc'), 'utf8');
const model = ifcAdapter.parse(ifcText, 'AC20-FZK-Haus.ifc');

ctx.onmessage({
    data: {
        type: 'export',
        requestId: 7,
        ifcModel: model,
        options: {
            mode: 'hybrid',
            cellSize: 0.1,
            voxelSize: 0.1,
            openingThickening: 0.05
        }
    }
});

if (!response || response.type !== 'complete') {
    console.error(response && response.message ? response.message : 'Worker did not return a completed conversion.');
    process.exit(1);
}
if (response.requestId !== 7 || !response.text || !response.model || !response.model.obsts.length) {
    console.error('Worker returned an incomplete conversion payload.');
    process.exit(1);
}
if (!response.text.includes('! Hole voxel policy: smaller.')) {
    console.error('Worker export did not use the default smaller-hole policy.');
    process.exit(1);
}

const inlineHost = { window: {} };
inlineHost.window = inlineHost;
vm.createContext(inlineHost);
vm.runInContext(
    fs.readFileSync(path.join(root, 'frontend/generated/fds-export-worker-inline.js'), 'utf8'),
    inlineHost,
    { filename: 'fds-export-worker-inline.js' }
);

let inlineResponse = null;
const inlineCtx = { console };
inlineCtx.self = inlineCtx;
inlineCtx.window = inlineCtx;
inlineCtx.postMessage = (message) => { inlineResponse = message; };
vm.createContext(inlineCtx);
vm.runInContext(
    inlineHost.IfcFdsExportWorkerSource,
    inlineCtx,
    { filename: 'fds-export-worker-inline-source.js' }
);
inlineCtx.onmessage({
    data: {
        type: 'export',
        requestId: 8,
        ifcModel: model,
        options: {
            mode: 'hybrid',
            cellSize: 0.1,
            voxelSize: 0.1,
            openingThickening: 0.05
        }
    }
});

if (!inlineResponse || inlineResponse.type !== 'complete' || inlineResponse.requestId !== 8) {
    console.error(inlineResponse && inlineResponse.message ? inlineResponse.message : 'Inline worker did not return a completed conversion.');
    process.exit(1);
}
if (!inlineResponse.text.includes('! Hole voxel policy: smaller.') || !inlineResponse.model.obsts.length) {
    console.error('Inline worker returned an incomplete conversion payload.');
    process.exit(1);
}

console.log({
    textChars: response.text.length,
    meshes: response.model.meshes.length,
    obsts: response.model.obsts.length,
    geoms: response.model.geoms.length,
    inlineObsts: inlineResponse.model.obsts.length
});
console.log('Background and direct-file export worker tests passed.');

for (const [workerCtx, getResponse] of [[ctx, () => response], [inlineCtx, () => inlineResponse]]) {
    workerCtx.onmessage({data:{type:'parse-fds',requestId:90,text:"&MESH IJK=1,1,1, XB=0,1,0,1,0,1 /\n&OBST ID='wall', XB=0,1,0,1,0,1 /"}});
    const imported = getResponse();
    if (imported.type !== 'complete' || imported.requestId !== 90 || imported.model.obsts.length !== 1 || imported.text !== undefined) {
        throw new Error('FDS import worker returned an incomplete model');
    }
}
console.log('Verified FDS display is parsed in the background worker and inline bundle.');

// Errors preserve stage/stack/identity without embedding the conversion payload.
for (const [workerCtx, getResponse] of [[ctx, () => response], [inlineCtx, () => inlineResponse]]) {
    vm.runInContext("IfcFds.fds.FdsNamelistParser.prototype.parse = function () { throw new RangeError('parser fixture failure'); };", workerCtx);
    workerCtx.onmessage({data:{type:'export',requestId:99,ifcModel:model,options:{mode:'hybrid',cellSize:0.1}}});
    const failure = getResponse();
    if (failure.type !== 'error' || failure.error.stage !== 'fds_parse' || failure.error.requestId !== 99 || !failure.error.stack) {
        throw new Error('Worker lost structured failure evidence');
    }
    if ('vertices' in failure.error || 'fds_text' in failure.error || 'model' in failure.error) {
        throw new Error('Worker diagnostics embedded geometry');
    }
}
console.log('Worker and inline diagnostics retain stage, stack and request identity.');
