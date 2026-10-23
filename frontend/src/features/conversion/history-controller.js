(function (ns) {
    ns.app = ns.app || {};
    ns.features = ns.features || {};
    ns.features.conversion = ns.features.conversion || {};
    ns.features.conversion.createHistoryController = function (dependencies) {
    var life = ns.core.createLifecycle();
    function countConvertibleIfc() { return dependencies.countConvertibleIfc.apply(null, arguments); }
    function exportIfc() { return dependencies.exportIfc.apply(null, arguments); }
    function updateIfcMetrics() { return dependencies.updateIfcMetrics.apply(null, arguments); }

    var state = dependencies.state;
    function refreshConversionActions() { return dependencies.refreshConversionActions.apply(null, arguments); }
    function setExportEnabled() { return dependencies.setExportEnabled.apply(null, arguments); }
    function pushUndo(entry) {
        var viewer = dependencies.getViewer();
        state.undoStack.push(entry);
        refreshConversionActions();
    }

    function undoLastChange() {
        var viewer = dependencies.getViewer();
        var entry = state.undoStack.pop();
        if (!entry) return;
        if (entry.kind === 'voxelize') {
            entry.stepIds.forEach(function (id) { delete state.forceObstStepIds[id]; });
            // The voxelize action ran an export; undoing it has to re-run the export to
            // get the original GEOM triangles back on screen.
            if (state.ifcModel && state.ifcModel.elements && state.ifcModel.elements.length) {
                exportIfc('convert');
            }
        } else if (entry.kind === 'delete') {
            (entry.stepIds || []).forEach(function (id) { delete state.excludedStepIds[id]; });
            (entry.itemIds || []).forEach(function (id) { delete state.excludedItemIds[id]; });
            viewer.setExclusions(state.excludedStepIds, state.excludedItemIds);
            updateIfcMetrics(state.ifcModel);
            setExportEnabled(countConvertibleIfc(state.ifcModel) > 0);
        }
        refreshConversionActions();
    }
    return {pushUndo: pushUndo, undoLastChange: undoLastChange, destroy: function () { life.destroy(); }};
    };
})(window.IfcFds);
