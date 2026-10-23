(function (ns) {
    ns.app = ns.app || {};
    ns.app.createApplication = function () {
    var parser = new ns.fds.FdsNamelistParser();
    var adapter = new ns.fds.FdsGeometryAdapter();
    var ifcAdapter = new ns.ifc.IfcAdapter();
    var webIfcDisplay = ns.ifc.WebIfcDisplay ? new ns.ifc.WebIfcDisplay() : null;
    var exporter = new ns.fds.FdsExporter();
    var state = ns.state.createSessionState();

    var els = {};
    var viewer = null;
    var loading = null;
    var helpDialog = null;
    var creditsDialog = null;

    var VIEW_KEY_TO_DIRECTION = {
        '1': 'front',
        '2': 'back',
        '3': 'left',
        '4': 'right',
        '5': 'top',
        '6': 'bottom',
        '0': 'iso'
    };

    var mounted = false;
    var life = ns.core.createLifecycle();
    function mount() {
        if (mounted) return;
        mounted = true;
        cacheElements();
        loading = new ns.components.ProgressOverlay(els);
        helpDialog = new ns.components.Modal(els.helpModal, els.closeHelp, els.openHelp, '.help-body');
        creditsDialog = new ns.components.Modal(els.creditsModal, els.closeCredits, els.openCredits);
        viewer = new ns.viewer.SceneViewer(els.viewer, showSelection, {geometryClient: ns.api.geometry});
        viewer.setNavigationModeChangeHandler(updateWalkModeButton);
        applyTheme(readSavedTheme());
        if (window.lucide) window.lucide.createIcons();
        if (ns.ui && ns.ui.domainPanel) ns.ui.domainPanel.init(els);
        if (ns.workbench && ns.workbench.inspector && ns.workbench.inspector.inspectorController) {
            ns.workbench.inspector.inspectorController.init(els, viewer);
        } else if (ns.ui && ns.ui.inspectorPanel) {
            ns.ui.inspectorPanel.init(els, viewer);
        }
        if (ns.workbench && ns.workbench.state && ns.workbench.state.selectionStore) {
            life.own(ns.workbench.state.selectionStore.subscribe(function (payload) {
                if (payload.source !== 'viewer' && viewer && typeof viewer.selectByEntityKeys === 'function') {
                    viewer.selectByEntityKeys(payload.keys);
                }
            }));
        }
        if (ns.workbench && ns.workbench.state && ns.workbench.state.visibilityStore) {
            life.own(ns.workbench.state.visibilityStore.subscribe(function () {
                if (viewer && typeof viewer.applyVisibilityState === 'function') {
                    viewer.applyVisibilityState(ns.workbench.state.visibilityStore);
                }
            }));
        }
        if (ns.workbench && ns.workbench.navigation) {
            if (ns.workbench.navigation.colorOverlay) ns.workbench.navigation.colorOverlay.setViewer(viewer);
            if (ns.workbench.navigation.sectionBox) ns.workbench.navigation.sectionBox.setViewer(viewer);
            if (ns.workbench.navigation.modelTree) ns.workbench.navigation.modelTree.init();
        }
        if (ns.ui && ns.ui.auditDrawer) ns.ui.auditDrawer.init(els, viewer);
        shell.bind();
        workbenchBindings.bind();
        sourceEvents.bind();
        conversionActions.bind();
        artifactController.bind();
        treeBindings.bind();
        scopeEvents.bind();
        inspectorBindings.bind();
        auditBindings.bind();
        ns.verified.init();
        clearFdsModel();
        checkBackendHealth();
        life.listen(window, 'focus', checkBackendHealth);
    }

    function cacheElements() {
        if (ns.ui && ns.ui.domCache) {
            els = ns.ui.domCache.init();
        }
    }

    function showLoading(title, stage) { loading.show(title, stage); }
    function setLoadingProgress(fraction, stage) { loading.update(fraction, stage); }
    function hideLoading() { loading.hide(); }

    function setSaveProcessedEnabled(enabled) {
        if (els.saveProcessed) els.saveProcessed.disabled = !enabled;
    }

    // Prefers the lightweight meta model's expressIDs (when web-ifc rendered) by reading the
    // viewer's world Box3, then falls back to the parsed model's bounds. Returns IFC-native
    // coordinates because the clipping API speaks in those.

    // The meta model is enough for browse/select/preview, but FDS export needs the full
    // ifc-adapter parse (placements, void carving, classifications). We do it on demand
    // the first time the user clicks Convert, and cache the result for repeated exports.

    // Splits the current selection into source-level deletions (IFC meshes — cascade through
    // all their derived OBST/GEOM) and primitive-level deletions (OBST/GEOM meshes — remove
    // just that one instance, leaving sibling primitives from the same source untouched).

    var shell = ns.app.createShellController({
        getCreditsDialog: function () { return creditsDialog; },
        getElements: function () { return els; },
        getHelpDialog: function () { return helpDialog; },
        getViewer: function () { return viewer; },
        state: state,
        closeAudit: function () { return closeAudit.apply(null, arguments); },
        openAudit: function () { return openAudit.apply(null, arguments); }
    });
    var openHelp = shell.openHelp;
    var closeHelp = shell.closeHelp;
    var openCredits = shell.openCredits;
    var closeCredits = shell.closeCredits;
    var readSavedTheme = shell.readSavedTheme;
    var applyTheme = shell.applyTheme;
    var updateWalkModeButton = shell.updateWalkModeButton;
    var setWorkflowMode = shell.setWorkflowMode;
    var updateColorModeLegend = shell.updateColorModeLegend;
    var workbenchBindings = ns.app.createWorkbenchBindings({
        VIEW_KEY_TO_DIRECTION: VIEW_KEY_TO_DIRECTION,
        getElements: function () { return els; },
        getViewer: function () { return viewer; },
        setExportEnabled: function () { return setExportEnabled.apply(null, arguments); },
        state: state,
        undoLastChange: function () { return undoLastChange.apply(null, arguments); },
        updateColorModeLegend: function () { return updateColorModeLegend.apply(null, arguments); },
        viewBus: ns.workbench.commands.commandBus,
        boundsForClipping: function () { return boundsForClipping.apply(null, arguments); },
        countConvertibleIfc: function () { return countConvertibleIfc.apply(null, arguments); },
        setupClippingForBounds: function () { return setupClippingForBounds.apply(null, arguments); },
        updateIfcMetrics: function () { return updateIfcMetrics.apply(null, arguments); }
    });
    var bindToggle = workbenchBindings.bindToggle;
    var sourceEvents = ns.features.sources.createSourceEvents({
        clearFdsModel: function () { return clearFdsModel.apply(null, arguments); },
        getElements: function () { return els; },
        getViewer: function () { return viewer; },
        ifcAdapter: ifcAdapter,
        parser: parser,
        setExportEnabled: function () { return setExportEnabled.apply(null, arguments); },
        setLoadingProgress: function () { return setLoadingProgress.apply(null, arguments); },
        setSaveProcessedEnabled: function () { return setSaveProcessedEnabled.apply(null, arguments); },
        showLoading: function () { return showLoading.apply(null, arguments); },
        state: state,
        viewBus: ns.workbench.commands.commandBus,
        webIfcDisplay: webIfcDisplay,
        cancelPendingExport: function () { return cancelPendingExport.apply(null, arguments); },
        clearGeneratedFds: function () { return clearGeneratedFds.apply(null, arguments); },
        failIfcLoad: function () { return failIfcLoad.apply(null, arguments); },
        finishIfcLoad: function () { return finishIfcLoad.apply(null, arguments); }
    });
    var conversionActions = ns.features.conversion.createActionEvents({
        getElements: function () { return els; },
        getViewer: function () { return viewer; },
        hideLoading: function () { return hideLoading.apply(null, arguments); },
        pushUndo: function () { return pushUndo.apply(null, arguments); },
        selectedGeneratedGeomStepIds: function () { return selectedGeneratedGeomStepIds.apply(null, arguments); },
        setExportEnabled: function () { return setExportEnabled.apply(null, arguments); },
        showSelection: function () { return showSelection.apply(null, arguments); },
        splitSelectionForDelete: function () { return splitSelectionForDelete.apply(null, arguments); },
        state: state,
        viewBus: ns.workbench.commands.commandBus,
        bindClipSlider: function () { return bindClipSlider.apply(null, arguments); },
        bindClipSteppers: function () { return bindClipSteppers.apply(null, arguments); },
        boundsForClipping: function () { return boundsForClipping.apply(null, arguments); },
        cancelPendingExport: function () { return cancelPendingExport.apply(null, arguments); },
        countConvertibleIfc: function () { return countConvertibleIfc.apply(null, arguments); },
        exportIfc: function () { return exportIfc.apply(null, arguments); },
        exportVerified: function () { return exportVerified.apply(null, arguments); },
        setupClippingForBounds: function () { return setupClippingForBounds.apply(null, arguments); },
        undoLastChange: function () { return undoLastChange.apply(null, arguments); },
        updateIfcMetrics: function () { return updateIfcMetrics.apply(null, arguments); }
    });
    var artifactController = ns.features.artifacts.createArtifactController({
        getElements: function () { return els; },
        hideLoading: function () { return hideLoading.apply(null, arguments); },
        showLoading: function () { return showLoading.apply(null, arguments); },
        state: state
    });
    var downloadText = artifactController.downloadText;
    var treeBindings = ns.features.modelTree.createTreeBindings({

    });
    var scopeEvents = ns.features.scope.createScopeEvents({
        getElements: function () { return els; },
        checkScopedDomainPreflight: function () { return checkScopedDomainPreflight.apply(null, arguments); },
        updateDomainEstimates: function () { return updateDomainEstimates.apply(null, arguments); }
    });
    var inspectorBindings = ns.features.inspector.createInspectorBindings({
        renderStructuredInspector: function () { return renderStructuredInspector.apply(null, arguments); },
        state: state
    });
    var auditBindings = ns.features.audit.createAuditBindings({
        getElements: function () { return els; },
        toggleAuditDrawer: function () { return toggleAuditDrawer.apply(null, arguments); }
    });
    var conversionResults = ns.features.conversion.createResultController({
        adapter: adapter,
        getElements: function () { return els; },
        getViewer: function () { return viewer; },
        parser: parser,
        selectedGeneratedGeomStepIds: function () { return selectedGeneratedGeomStepIds.apply(null, arguments); },
        showSelection: function () { return showSelection.apply(null, arguments); },
        splitSelectionForDelete: function () { return splitSelectionForDelete.apply(null, arguments); },
        state: state,
        countConvertibleIfc: function () { return countConvertibleIfc.apply(null, arguments); },
        openAudit: function () { return openAudit.apply(null, arguments); },
        renderIfcMapping: function () { return renderIfcMapping.apply(null, arguments); }
    });
    var loadFdsText = conversionResults.loadFdsText;
    var clearFdsModel = conversionResults.clearFdsModel;
    var updateMetrics = conversionResults.updateMetrics;
    var renderDiagnostics = conversionResults.renderDiagnostics;
    var setExportEnabled = conversionResults.setExportEnabled;
    var refreshConversionActions = conversionResults.refreshConversionActions;
    var setExportBusy = conversionResults.setExportBusy;
    var checkBackendHealth = conversionResults.checkBackendHealth;
    var selectionController = ns.features.inspector.createSelectionController({
        getElements: function () { return els; },
        getViewer: function () { return viewer; },
        refreshConversionActions: function () { return refreshConversionActions.apply(null, arguments); },
        state: state
    });
    var showSelection = selectionController.showSelection;
    var selectionDetails = selectionController.selectionDetails;
    var normalizeSelection = selectionController.normalizeSelection;
    var selectedGeneratedGeomStepIds = selectionController.selectedGeneratedGeomStepIds;
    var selectedIfcStepIds = selectionController.selectedIfcStepIds;
    var splitSelectionForDelete = selectionController.splitSelectionForDelete;
    var renderStructuredInspector = selectionController.renderStructuredInspector;
    var conversionHistory = ns.features.conversion.createHistoryController({
        getViewer: function () { return viewer; },
        refreshConversionActions: function () { return refreshConversionActions.apply(null, arguments); },
        setExportEnabled: function () { return setExportEnabled.apply(null, arguments); },
        state: state,
        countConvertibleIfc: function () { return countConvertibleIfc.apply(null, arguments); },
        exportIfc: function () { return exportIfc.apply(null, arguments); },
        updateIfcMetrics: function () { return updateIfcMetrics.apply(null, arguments); }
    });
    var pushUndo = conversionHistory.pushUndo;
    var undoLastChange = conversionHistory.undoLastChange;
    var quickWorkflow = ns.features.conversion.createQuickWorkflow({
        boundsForClipping: function () { return boundsForClipping.apply(null, arguments); },
        exporter: exporter,
        getElements: function () { return els; },
        getViewer: function () { return viewer; },
        hideLoading: function () { return hideLoading.apply(null, arguments); },
        ifcAdapter: ifcAdapter,
        loadFdsText: function () { return loadFdsText.apply(null, arguments); },
        openAudit: function () { return openAudit.apply(null, arguments); },
        parser: parser,
        renderDiagnostics: function () { return renderDiagnostics.apply(null, arguments); },
        setExportBusy: function () { return setExportBusy.apply(null, arguments); },
        setLoadingProgress: function () { return setLoadingProgress.apply(null, arguments); },
        setupClippingForBounds: function () { return setupClippingForBounds.apply(null, arguments); },
        showLoading: function () { return showLoading.apply(null, arguments); },
        state: state,
        updateIfcMetrics: function () { return updateIfcMetrics.apply(null, arguments); }
    });
    var exportIfc = quickWorkflow.exportIfc;
    var ensureFullModel = quickWorkflow.ensureFullModel;
    var runExportWithModel = quickWorkflow.runExportWithModel;
    var finishExportWithError = quickWorkflow.finishExportWithError;
    var addExportDiagnostic = quickWorkflow.addExportDiagnostic;
    var cleanupExportWorker = quickWorkflow.cleanupExportWorker;
    var parseFdsInWorker = quickWorkflow.parseFdsInWorker;
    var cancelPendingExport = quickWorkflow.cancelPendingExport;
    var clearGeneratedFds = quickWorkflow.clearGeneratedFds;
    var currentExportOptions = quickWorkflow.currentExportOptions;
    var countConvertibleIfc = quickWorkflow.countConvertibleIfc;
    var verifiedController = ns.features.conversion.createVerifiedController({
        addExportDiagnostic: function () { return addExportDiagnostic.apply(null, arguments); },
        boundsForClipping: function () { return boundsForClipping.apply(null, arguments); },
        cleanupExportWorker: function () { return cleanupExportWorker.apply(null, arguments); },
        clearGeneratedFds: function () { return clearGeneratedFds.apply(null, arguments); },
        exposeFailedCheckpoints: function () { return exposeFailedCheckpoints.apply(null, arguments); },
        getElements: function () { return els; },
        getViewer: function () { return viewer; },
        hideLoading: function () { return hideLoading.apply(null, arguments); },
        loadFdsText: function () { return loadFdsText.apply(null, arguments); },
        openAudit: function () { return openAudit.apply(null, arguments); },
        parseFdsInWorker: function () { return parseFdsInWorker.apply(null, arguments); },
        renderAuditReport: function () { return renderAuditReport.apply(null, arguments); },
        setExportBusy: function () { return setExportBusy.apply(null, arguments); },
        setLoadingProgress: function () { return setLoadingProgress.apply(null, arguments); },
        setupClippingForBounds: function () { return setupClippingForBounds.apply(null, arguments); },
        showLoading: function () { return showLoading.apply(null, arguments); },
        state: state,
        updateGlobalStatusBadge: function () { return updateGlobalStatusBadge.apply(null, arguments); }
    });
    var exportVerified = verifiedController.exportVerified;
    var sourceController = ns.features.sources.createSourceController({
        countConvertibleIfc: function () { return countConvertibleIfc.apply(null, arguments); },
        currentExportOptions: function () { return currentExportOptions.apply(null, arguments); },
        exporter: exporter,
        getElements: function () { return els; },
        getViewer: function () { return viewer; },
        hideLoading: function () { return hideLoading.apply(null, arguments); },
        renderDiagnostics: function () { return renderDiagnostics.apply(null, arguments); },
        setExportEnabled: function () { return setExportEnabled.apply(null, arguments); },
        setLoadingProgress: function () { return setLoadingProgress.apply(null, arguments); },
        setSaveProcessedEnabled: function () { return setSaveProcessedEnabled.apply(null, arguments); },
        setupClippingForBounds: function () { return setupClippingForBounds.apply(null, arguments); },
        state: state,
        updateDomainEstimates: function () { return updateDomainEstimates.apply(null, arguments); }
    });
    var finishIfcLoad = sourceController.finishIfcLoad;
    var boundsForClipping = sourceController.boundsForClipping;
    var failIfcLoad = sourceController.failIfcLoad;
    var readText = sourceController.readText;
    var updateSourcePill = sourceController.updateSourcePill;
    var updateIfcMetrics = sourceController.updateIfcMetrics;
    var renderIfcMapping = sourceController.renderIfcMapping;
    var clippingControls = ns.features.scope.createClippingControls({
        getElements: function () { return els; },
        getViewer: function () { return viewer; }
    });
    var applyClip = clippingControls.applyClip;
    var clampClip = clippingControls.clampClip;
    var bindClipSlider = clippingControls.bindClipSlider;
    var bindClipSteppers = clippingControls.bindClipSteppers;
    var setupClippingForBounds = clippingControls.setupClippingForBounds;
    var updateDomainEstimates = clippingControls.updateDomainEstimates;
    var checkScopedDomainPreflight = clippingControls.checkScopedDomainPreflight;
    var auditController = ns.features.audit.createAuditController({
        getElements: function () { return els; },
        getViewer: function () { return viewer; },
        state: state
    });
    var renderAuditReport = auditController.renderAuditReport;
    var openAudit = auditController.openAudit;
    var closeAudit = auditController.closeAudit;
    var toggleAuditDrawer = auditController.toggleAuditDrawer;
    var renderAuditDrawer = auditController.renderAuditDrawer;
    var exposeFailedCheckpoints = auditController.exposeFailedCheckpoints;
    var updateGlobalStatusBadge = auditController.updateGlobalStatusBadge;

    function destroy() {
        if (!mounted) return;
        mounted = false;
        state.ifcLoadRequestId = (state.ifcLoadRequestId || 0) + 1;
        ns.ifc.backendPreview.cancel();
        cancelPendingExport();
        if (webIfcDisplay && webIfcDisplay.dispose) webIfcDisplay.dispose();
        if (ns.verified.destroy) ns.verified.destroy();
        life.destroy();
        if (auditController.destroy) auditController.destroy();
        if (clippingControls.destroy) clippingControls.destroy();
        if (sourceController.destroy) sourceController.destroy();
        if (verifiedController.destroy) verifiedController.destroy();
        if (quickWorkflow.destroy) quickWorkflow.destroy();
        if (conversionHistory.destroy) conversionHistory.destroy();
        if (selectionController.destroy) selectionController.destroy();
        if (conversionResults.destroy) conversionResults.destroy();
        if (auditBindings.destroy) auditBindings.destroy();
        if (inspectorBindings.destroy) inspectorBindings.destroy();
        if (scopeEvents.destroy) scopeEvents.destroy();
        if (treeBindings.destroy) treeBindings.destroy();
        if (artifactController.destroy) artifactController.destroy();
        if (conversionActions.destroy) conversionActions.destroy();
        if (sourceEvents.destroy) sourceEvents.destroy();
        if (workbenchBindings.destroy) workbenchBindings.destroy();
        if (shell.destroy) shell.destroy();

        var inspector = ns.workbench && ns.workbench.inspector && ns.workbench.inspector.inspectorController;
        if (inspector && inspector.destroy) inspector.destroy();
        var tree = ns.workbench && ns.workbench.navigation && ns.workbench.navigation.modelTree;
        if (tree && tree.destroy) tree.destroy();
        if (ns.ui.domainPanel && ns.ui.domainPanel.destroy) ns.ui.domainPanel.destroy();
        if (ns.ui.auditDrawer && ns.ui.auditDrawer.destroy) ns.ui.auditDrawer.destroy();
        if (helpDialog) helpDialog.destroy();
        if (creditsDialog) creditsDialog.destroy();
        if (viewer && viewer.dispose) viewer.dispose();
    }
    return {mount: mount, destroy: destroy, state: state, getViewer: function () { return viewer; }};
    };
})(window.IfcFds);
