self.window = self;

importScripts(
    '../shared/namespace.js',
    '../shared/diagnostics.js',
    '../engines/legacy/fds/representation-policy.js',
    '../engines/legacy/fds/voxelizer.js',
    '../engines/legacy/fds/serialization.js',
    '../engines/legacy/fds/fds-exporter.js',
    '../engines/legacy/fds/namelist-parser.js',
    '../engines/legacy/fds/fds-geometry-adapter.js'
);

var exporter = new self.IfcFds.fds.FdsExporter();
var parser = new self.IfcFds.fds.FdsNamelistParser();
var adapter = new self.IfcFds.fds.FdsGeometryAdapter();

self.onmessage = function (event) {
    var request = event.data || {};
    if (request.type !== 'export' && request.type !== 'parse-fds') return;

    try {
        var options = request.options || {};
        options.onProgress = function (fraction, stage) {
            self.postMessage({
                type: 'progress',
                requestId: request.requestId,
                fraction: fraction,
                stage: stage || ''
            });
        };
        var text = request.type === 'parse-fds' ? request.text : self.IfcFds.core.atStage('serialization', function () { return exporter.exportFromIfcScene(request.ifcModel, options); });
        var parsed = self.IfcFds.core.atStage('fds_parse', function () { return parser.parse(text); });
        var model = self.IfcFds.core.atStage('scene_model', function () { return adapter.toSceneModel(parsed); });
        self.postMessage({
            type: 'complete',
            requestId: request.requestId,
            text: request.type === 'parse-fds' ? undefined : text,
            model: model
        });
    } catch (error) {
        self.postMessage({
            type: 'error',
            requestId: request.requestId,
            message: error && error.message ? error.message : String(error),
            error: self.IfcFds.core.failure(error, {requestId: request.requestId})
        });
    }
};
