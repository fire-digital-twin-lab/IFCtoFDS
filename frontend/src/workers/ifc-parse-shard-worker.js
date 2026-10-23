self.window = self;

importScripts(
    '../../vendor/earcut.min.js',
    '../shared/namespace.js',
    '../shared/diagnostics.js',
    '../engines/legacy/ifc/step-parser.js',
    '../engines/legacy/ifc/openings.js',
    '../engines/legacy/ifc/representations.js',
    '../engines/legacy/ifc/clipping.js',
    '../engines/legacy/ifc/triangulation.js',
    '../engines/legacy/ifc/mesh-transforms.js',
    '../engines/legacy/ifc/ifc-adapter.js'
);

var IfcAdapter = self.IfcFds.ifc.IfcAdapter;

self.onmessage = function (event) {
    var request = event.data || {};
    if (request.type !== 'parse-shard') return;

    try {
        var ctx = IfcAdapter.beginParse(request.text);
        var entities = ctx.step.entities;
        var end = Math.min(request.endIndex, entities.length);
        for (var i = request.startIndex; i < end; i += 1) {
            IfcAdapter.processEntity(ctx, entities[i]);
        }
        self.postMessage({
            type: 'parse-shard-result',
            requestId: request.requestId,
            shardIndex: request.shardIndex,
            elements: ctx.elements,
            unsupported: ctx.unsupported,
            diagnostics: ctx.diagnostics,
            voidStatsApplied: ctx.voidStats.applied,
            openingMaskCount: ctx.openingMaskCount
        });
    } catch (error) {
        self.postMessage({
            type: 'error',
            requestId: request.requestId,
            shardIndex: request.shardIndex,
            message: error && error.message ? error.message : String(error),
            error: self.IfcFds.core.failure(error, {stage: 'ifc_parse', requestId: request.requestId})
        });
    }
};
