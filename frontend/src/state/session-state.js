(function (ns) {
    ns.state = ns.state || {};
    ns.state.createSessionState = function () {
        return {
        theme: 'light',
        activeInspectorTab: 'id',
        fdsModel: null,
        ifcModel: null,             // currently displayed (meta until conversion)
        ifcSourceText: null,        // cached decoded STEP text, reused by deferred parse
        ifcFileName: null,
        fullModel: null,            // ifc-adapter heavy parse, lazy
        lastDisplayMeshes: null,
        generatedFdsText: null,
        generatedFdsName: null,
        forceObstStepIds: {},
        excludedStepIds: {},        // IFC elements the user has removed (cascades to all their OBST/GEOM)
        excludedItemIds: {},        // individual OBST/GEOM primitives the user has removed
        undoStack: [],              // history of voxelize/delete actions for Ctrl+Z reversal
        selection: [],
        exportEnabled: false,
        exportBusy: false,
        exportAction: null,
        exportRequestId: 0,
        exportWorker: null,
        exportWorkerUrl: null,
        helpTrigger: null,
        lastAuditReport: null,
        lastManifest: null,
        backendOnline: false,
        currentIfcFile: null
    };
    };
})(window.IfcFds);
