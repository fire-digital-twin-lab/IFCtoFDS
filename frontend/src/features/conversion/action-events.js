(function (ns) {
    ns.app = ns.app || {};
    ns.features = ns.features || {};
    ns.features.conversion = ns.features.conversion || {};
    ns.features.conversion.createActionEvents = function (dependencies) {
    var life = ns.core.createLifecycle();
    function bindClipSlider() { return dependencies.bindClipSlider.apply(null, arguments); }
    function bindClipSteppers() { return dependencies.bindClipSteppers.apply(null, arguments); }
    function boundsForClipping() { return dependencies.boundsForClipping.apply(null, arguments); }
    function cancelPendingExport() { return dependencies.cancelPendingExport.apply(null, arguments); }
    function countConvertibleIfc() { return dependencies.countConvertibleIfc.apply(null, arguments); }
    function exportIfc() { return dependencies.exportIfc.apply(null, arguments); }
    function exportVerified() { return dependencies.exportVerified.apply(null, arguments); }
    function setupClippingForBounds() { return dependencies.setupClippingForBounds.apply(null, arguments); }
    function undoLastChange() { return dependencies.undoLastChange.apply(null, arguments); }
    function updateIfcMetrics() { return dependencies.updateIfcMetrics.apply(null, arguments); }

    var state = dependencies.state;
    var viewBus = dependencies.viewBus;
    function hideLoading() { return dependencies.hideLoading.apply(null, arguments); }
    function pushUndo() { return dependencies.pushUndo.apply(null, arguments); }
    function selectedGeneratedGeomStepIds() { return dependencies.selectedGeneratedGeomStepIds.apply(null, arguments); }
    function setExportEnabled() { return dependencies.setExportEnabled.apply(null, arguments); }
    function showSelection() { return dependencies.showSelection.apply(null, arguments); }
    function splitSelectionForDelete() { return dependencies.splitSelectionForDelete.apply(null, arguments); }

    var bound = false;
    function bind() {
        if (bound) return;
        bound = true;
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        var undoView = document.getElementById('undo-view');
        var resetVisibility = document.getElementById('reset-visibility');
        if (undoView) {
            life.listen(undoView, 'click', function () { viewBus.undo(); });
            life.own(viewBus.subscribe(function () { undoView.disabled = !viewBus.canUndo(); }));
        }
        if (resetVisibility) life.listen(resetVisibility, 'click', function () {
            viewBus.execute(new ns.workbench.commands.ResetVisibilityCommand());
        });
        var cancelTask = document.getElementById('cancel-task');
        function cancelUiTask() {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
            state.ifcLoadRequestId = (state.ifcLoadRequestId || 0) + 1;
            ns.ifc.backendPreview.cancel();
            cancelPendingExport();
            hideLoading();
            document.getElementById('verified-progress').textContent = 'Cancelled';
        }
        if (cancelTask) life.listen(cancelTask, 'click', cancelUiTask);
        var verifiedCancel = document.getElementById('verified-cancel');
        if (verifiedCancel) life.listen(verifiedCancel, 'click', cancelUiTask);
        life.listen(els.convertIfc, 'click', function () {
            exportIfc('convert');
        });

        if (els.convertVerified) {
            life.listen(els.convertVerified, 'click', function () {
                exportVerified();
            });
        }

        life.listen(els.convertSelectedObst, 'click', function () {
            var stepIds = selectedGeneratedGeomStepIds(state.selection);
            if (!stepIds.length) return;
            var added = stepIds.filter(function (id) { return !state.forceObstStepIds[id]; });
            stepIds.forEach(function (stepId) {
                state.forceObstStepIds[stepId] = true;
            });
            if (added.length) pushUndo({ kind: 'voxelize', stepIds: added });
            exportIfc('voxelize');
        });

        if (els.deleteSelected) {
            life.listen(els.deleteSelected, 'click', function () {
                var split = splitSelectionForDelete(state.selection);
                if (!split.stepIds.length && !split.itemIds.length) return;
                var addedStepIds = split.stepIds.filter(function (id) { return !state.excludedStepIds[id]; });
                var addedItemIds = split.itemIds.filter(function (id) { return !state.excludedItemIds[id]; });
                addedStepIds.forEach(function (id) { state.excludedStepIds[id] = true; });
                addedItemIds.forEach(function (id) { state.excludedItemIds[id] = true; });
                if (addedStepIds.length || addedItemIds.length) {
                    pushUndo({ kind: 'delete', stepIds: addedStepIds, itemIds: addedItemIds });
                }
                viewer.setSelectedObjects([]);
                showSelection(null);
                viewer.setExclusions(state.excludedStepIds, state.excludedItemIds);
                updateIfcMetrics(state.ifcModel);
                setExportEnabled(countConvertibleIfc(state.ifcModel) > 0);
            });
        }

        if (els.undoLast) {
            life.listen(els.undoLast, 'click', undoLastChange);
        }

        ['xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'].forEach(bindClipSlider);
        bindClipSteppers();
        if (els.obstThreshold && els.obstThresholdVal) {
            life.listen(els.obstThreshold, 'input', function () {
                els.obstThresholdVal.value = Number(els.obstThreshold.value).toFixed(2);
            });
            life.listen(els.obstThresholdVal, 'change', function () {
                var v = Number(els.obstThresholdVal.value);
                if (!isFinite(v)) { els.obstThresholdVal.value = Number(els.obstThreshold.value).toFixed(2); return; }
                v = Math.max(Number(els.obstThreshold.min), Math.min(Number(els.obstThreshold.max), v));
                els.obstThreshold.value = String(v);
                els.obstThresholdVal.value = v.toFixed(2);
            });
            life.listen(els.obstThresholdVal, 'keydown', function (event) {
                if (event.key === 'Enter') els.obstThresholdVal.blur();
            });
        }
        if (els.clipReset) {
            life.listen(els.clipReset, 'click', function () {
                viewer.resetClipping();
                if (state.ifcModel) setupClippingForBounds(boundsForClipping());
            });
        }


    }

    return {bind: bind, destroy: function () { life.destroy(); }};
    };
})(window.IfcFds);
