(function (ns) {
    ns.app = ns.app || {};
    ns.features = ns.features || {};
    ns.features.conversion = ns.features.conversion || {};
    ns.features.conversion.createResultController = function (dependencies) {
    var life = ns.core.createLifecycle();
    function countConvertibleIfc() { return dependencies.countConvertibleIfc.apply(null, arguments); }
    function openAudit() { return dependencies.openAudit.apply(null, arguments); }
    function renderIfcMapping() { return dependencies.renderIfcMapping.apply(null, arguments); }

    var state = dependencies.state;
    var parser = dependencies.parser;
    var adapter = dependencies.adapter;
    function selectedGeneratedGeomStepIds() { return dependencies.selectedGeneratedGeomStepIds.apply(null, arguments); }
    function showSelection() { return dependencies.showSelection.apply(null, arguments); }
    function splitSelectionForDelete() { return dependencies.splitSelectionForDelete.apply(null, arguments); }
    function loadFdsText(text, sourceName, preparedModel) {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        var parsed = preparedModel ? null : ns.core.atStage('fds_parse', function () { return parser.parse(text); });
        var model = preparedModel || ns.core.atStage('scene_model', function () { return adapter.toSceneModel(parsed); });
        state.fdsModel = model;
        els.fdsSourceName.textContent = sourceName;
        if (ns.workbench && ns.workbench.state) {
            var sceneItems = [].concat(model.obsts || [], model.geoms || [], model.vents || [], model.holes || []);
            ns.workbench.state.selectionStore.indexElements(sceneItems, sourceName || 'fds');
        }
        ns.core.atStage('viewer', function () { viewer.loadFdsModel(model); });
        viewer.setFdsOpacity(Number(els.fdsOpacity.value));
        viewer.setExclusions(state.excludedStepIds, state.excludedItemIds);
        updateMetrics(model);
        renderDiagnostics();
        showSelection(null);
        if (ns.workbench && ns.workbench.navigation) {
            if (ns.workbench.navigation.colorOverlay) {
                var currentMode = ns.workbench.navigation.colorOverlay.currentMode || 'mapping';
                ns.workbench.navigation.colorOverlay.applyColorMode(currentMode);
            }
            if (ns.workbench.navigation.modelTree) {
                ns.workbench.navigation.modelTree.render();
            }
        }
    }

    function clearFdsModel() {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        var model = {
            meshes: [],
            obsts: [],
            vents: [],
            holes: [],
            geoms: [],
            triangleCount: 0,
            bounds: null,
            diagnostics: []
        };
        state.fdsModel = model;
        els.fdsSourceName.textContent = 'No conversion';
        viewer.loadFdsModel(model);
        if (ns.workbench && ns.workbench.state && ns.workbench.state.workbenchStore) {
            ns.workbench.state.workbenchStore.resetAll();
        }
        updateMetrics(model);
        renderDiagnostics();
        showSelection(null);
    }

    function updateMetrics(model) {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        els.countMeshes.textContent = model.meshes.length;
        els.countObsts.textContent = model.obsts.length;
        els.countVents.textContent = model.vents.length;
        els.countGeoms.textContent = model.geoms.length;
        els.countTriangles.textContent = model.triangleCount;
        els.countIfc.textContent = state.ifcModel && state.ifcModel.elements ? state.ifcModel.elements.length : 0;
        els.countIfcConvertible.textContent = countConvertibleIfc(state.ifcModel);
        renderIfcMapping(state.ifcModel);
    }

    function renderDiagnostics() {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        var diagnostics = ns.compare.runChecks(state.fdsModel, state.ifcModel);
        els.diagnostics.innerHTML = '';
        diagnostics.forEach(function (diag) {
            var item = document.createElement('li');
            item.className = diag.level || 'info';
            item.innerHTML = '<strong></strong><span></span>';
            item.querySelector('strong').textContent = diag.title;
            item.querySelector('span').textContent = diag.detail;
            els.diagnostics.appendChild(item);
            if (diag.ref && diag.ref.kind === 'conversion-failure') {
                var download = document.createElement('button');
                download.type = 'button'; download.textContent = 'Download diagnostic';
                life.listen(download, 'click', function () {
                    var url = URL.createObjectURL(new Blob([JSON.stringify(diag.ref, null, 2)], {type: 'application/json'}));
                    var link = document.createElement('a'); link.href = url; link.download = 'conversion-diagnostic.json';
                    link.click(); setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
                });
                item.appendChild(download);
            }
        });
    }

    function setExportEnabled(enabled) {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        state.exportEnabled = !!enabled;
        refreshConversionActions();
    }

    function refreshConversionActions() {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        els.convertIfc.disabled = state.exportBusy || !state.exportEnabled;
        if (els.convertVerified) {
            els.convertVerified.disabled = state.exportBusy || (!state.exportEnabled && !ns.verified.hasFiles());
        }
        els.convertSelectedObst.disabled = state.exportBusy || !selectedGeneratedGeomStepIds(state.selection).length;
        if (els.deleteSelected) {
            var split = splitSelectionForDelete(state.selection);
            els.deleteSelected.disabled = state.exportBusy || (!split.stepIds.length && !split.itemIds.length);
        }
        if (els.undoLast) {
            els.undoLast.disabled = state.exportBusy || !state.undoStack.length;
        }
        if (els.openAudit) {
            els.openAudit.disabled = !state.lastAuditReport;
        }
        if (els.saveManifest) {
            els.saveManifest.disabled = !state.lastManifest && !state.lastArtifactLinks;
        }
    }

    function setExportBusy(busy, action) {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        state.exportBusy = !!busy;
        state.exportAction = state.exportBusy ? action : null;
        els.convertIfc.classList.toggle('is-busy', state.exportBusy && action === 'convert');
        if (els.convertVerified) {
            els.convertVerified.classList.toggle('is-busy', state.exportBusy && action === 'convert-verified');
            els.convertVerified.setAttribute('aria-busy', state.exportBusy && action === 'convert-verified' ? 'true' : 'false');
            var span = els.convertVerified.querySelector('span');
            if (span) {
                span.textContent = (state.exportBusy && action === 'convert-verified')
                    ? 'Verifying...'
                    : 'Verified Conversion (Audit)';
            }
        }
        els.convertSelectedObst.classList.toggle('is-busy', state.exportBusy && action === 'voxelize');
        els.convertIfc.setAttribute('aria-busy', state.exportBusy && action === 'convert' ? 'true' : 'false');
        els.convertSelectedObst.setAttribute('aria-busy', state.exportBusy && action === 'voxelize' ? 'true' : 'false');
        var spanIfc = els.convertIfc ? els.convertIfc.querySelector('span') : null;
        if (spanIfc) {
            spanIfc.textContent = state.exportBusy && action === 'convert'
                ? 'Converting...'
                : 'Run Quick Preview (Legacy)';
        }
        var spanObst = els.convertSelectedObst ? els.convertSelectedObst.querySelector('span') : null;
        if (spanObst) {
            spanObst.textContent = state.exportBusy && action === 'voxelize'
                ? 'Voxelizing selected GEOM...'
                : 'Voxelize selected GEOM to OBST';
        }
        refreshConversionActions();
    }

    function checkBackendHealth() {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        var apiUrl = (window.location.protocol === 'http:' || window.location.protocol === 'https:')
            ? '/api/health'
            : 'http://127.0.0.1:8000/api/health';

        ns.api.request(apiUrl, { method: 'GET' })
            .then(function (res) {
                if (res.ok) return res.json();
                throw new Error('HTTP ' + res.status);
            })
            .then(function (data) {
                if (data && data.status === 'ok') {
                    state.backendOnline = true;
                    if (els.backendStatusIndicator) {
                        els.backendStatusIndicator.className = 'status-indicator online';
                    }
                    if (els.backendStatusText) {
                        els.backendStatusText.textContent = 'Backend: Online (IfcOpenShell v' + (data.version || '0.2.0') + ')';
                    }
                    refreshConversionActions();
                }
            })
            .catch(function () {
                state.backendOnline = false;
                if (els.backendStatusIndicator) {
                    els.backendStatusIndicator.className = 'status-indicator offline';
                }
                if (els.backendStatusText) {
                    els.backendStatusText.textContent = 'Backend: Offline (Run: python -m ifc_to_fds serve)';
                }
                refreshConversionActions();
            });
    }
    return {loadFdsText: loadFdsText, clearFdsModel: clearFdsModel, updateMetrics: updateMetrics, renderDiagnostics: renderDiagnostics, setExportEnabled: setExportEnabled, refreshConversionActions: refreshConversionActions, setExportBusy: setExportBusy, checkBackendHealth: checkBackendHealth, destroy: function () { life.destroy(); }};
    };
})(window.IfcFds);
