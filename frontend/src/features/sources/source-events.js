(function (ns) {
    ns.app = ns.app || {};
    ns.features = ns.features || {};
    ns.features.sources = ns.features.sources || {};
    ns.features.sources.createSourceEvents = function (dependencies) {
    var life = ns.core.createLifecycle();
    function cancelPendingExport() { return dependencies.cancelPendingExport.apply(null, arguments); }
    function clearGeneratedFds() { return dependencies.clearGeneratedFds.apply(null, arguments); }
    function failIfcLoad() { return dependencies.failIfcLoad.apply(null, arguments); }
    function finishIfcLoad() { return dependencies.finishIfcLoad.apply(null, arguments); }

    var state = dependencies.state;
    var parser = dependencies.parser;
    var ifcAdapter = dependencies.ifcAdapter;
    var webIfcDisplay = dependencies.webIfcDisplay;
    var viewBus = dependencies.viewBus;
    function clearFdsModel() { return dependencies.clearFdsModel.apply(null, arguments); }
    function setExportEnabled() { return dependencies.setExportEnabled.apply(null, arguments); }
    function setLoadingProgress() { return dependencies.setLoadingProgress.apply(null, arguments); }
    function setSaveProcessedEnabled() { return dependencies.setSaveProcessedEnabled.apply(null, arguments); }
    function showLoading() { return dependencies.showLoading.apply(null, arguments); }

    var bound = false;
    function bind() {
        if (bound) return;
        bound = true;
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        life.listen(els.ifcFile, 'change', function (event) {
            var file = event.target.files[0];
            if (!file) return;
            var loadGeneration = state.ifcLoadRequestId = (state.ifcLoadRequestId || 0) + 1;
            function currentLoad() {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements(); return state.currentIfcFile === file && state.ifcLoadRequestId === loadGeneration; }
            ns.ifc.backendPreview.cancel();
            state.currentIfcFile = file;
            ns.verified.setFallback(file);
            cancelPendingExport();
            clearGeneratedFds();
            clearFdsModel();
            state.forceObstStepIds = {};
            state.excludedStepIds = {};
            state.excludedItemIds = {};
            state.undoStack = [];
            viewBus.clear();
            ns.workbench.state.visibilityStore.resetVisibility('source-change');
            state.fullModel = null;
            state.ifcSourceText = null;
            state.ifcFileName = file.name;
            // The previous file's reveal animation may have left the IFC slider at 0.3 so
            // the new model would render as a barely-visible ghost. Reset to full opacity
            // before showing the new file.
            if (els.ifcOpacity) {
                els.ifcOpacity.value = '1';
                viewer.setIfcOpacity(1);
            }
            setExportEnabled(false);
            setSaveProcessedEnabled(false);
            els.ifcSourceName.textContent = file.name;
            showLoading('Loading ' + file.name, 'Reading file…');

            // Large sources go directly to an isolated backend worker. Never
            // decode their entire STEP content or send them to the legacy parser.
            var WEB_IFC_MAX_BYTES = 8 * 1024 * 1024;
            if (file.size > WEB_IFC_MAX_BYTES) {
                ns.ifc.backendPreview.load(file, viewer, function (fraction, message) {
                    if (currentLoad()) setLoadingProgress(fraction, message);
                }).then(function (model) {
                    if (currentLoad()) finishIfcLoad(model, null, null);
                }).catch(function (error) {
                    if (currentLoad() && error.name !== 'AbortError') failIfcLoad(file.name, error);
                });
                return;
            }
            var useWebIfcDisplay = webIfcDisplay && file.size <= WEB_IFC_MAX_BYTES;
            var oversizeNotice = null;

            file.arrayBuffer().then(function (buffer) {
                if (!currentLoad()) return;
                setLoadingProgress(0.1, 'Indexing entities…');
                var text = new TextDecoder().decode(new Uint8Array(buffer));
                state.ifcSourceText = text;
                var meta = ns.ifc.IfcMeta.buildModel(text, file.name);
                setLoadingProgress(0.5, useWebIfcDisplay ? 'Rendering geometry…' : 'Building legacy mesh…');
                var displayPromise = useWebIfcDisplay
                    ? webIfcDisplay.load(buffer).catch(function (err) {
                        console.warn('web-ifc display load failed:', err);
                        return null;
                    })
                    : Promise.resolve(null);
                return displayPromise.then(function (displayMeshes) {
                    if (!currentLoad()) return;
                    if (displayMeshes && displayMeshes.length) {
                        finishIfcLoad(meta, displayMeshes, oversizeNotice);
                        return;
                    }
                    // No WASM display available — fall back to the legacy parser so the viewer
                    // has geometry to draw. Caches it as state.fullModel so Convert won't reparse.
                    return ifcAdapter.parseAsync(text, file.name, function (fraction) {
                        setLoadingProgress(fraction, 'Parsing legacy mesh…');
                    }).then(function (fullModel) {
                        if (!currentLoad()) return;
                        state.fullModel = fullModel;
                        finishIfcLoad(fullModel, null, oversizeNotice);
                    });
                });
            }).catch(function (error) {
                if (!currentLoad()) return;
                failIfcLoad(file.name, error);
            });
        });

        life.listen(els.resetCamera, 'click', function () {
            viewer.resetCamera();
        });


    }

    return {bind: bind, destroy: function () { life.destroy(); }};
    };
})(window.IfcFds);
