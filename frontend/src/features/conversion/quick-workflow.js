(function (ns) {
    ns.features = ns.features || {};
    ns.features.conversion = ns.features.conversion || {};
    ns.features.conversion.createQuickWorkflow = function (dependencies) {
        function hideLoading() { return dependencies.hideLoading.apply(null, arguments); }
        function setLoadingProgress() { return dependencies.setLoadingProgress.apply(null, arguments); }
        var state = dependencies.state;
        var parser = dependencies.parser;
        var ifcAdapter = dependencies.ifcAdapter;
        var exporter = dependencies.exporter;
        function boundsForClipping() { return dependencies.boundsForClipping.apply(null, arguments); }
        function loadFdsText() { return dependencies.loadFdsText.apply(null, arguments); }
        function openAudit() { return dependencies.openAudit.apply(null, arguments); }
        function renderDiagnostics() { return dependencies.renderDiagnostics.apply(null, arguments); }
        function setExportBusy() { return dependencies.setExportBusy.apply(null, arguments); }
        function setupClippingForBounds() { return dependencies.setupClippingForBounds.apply(null, arguments); }
        function showLoading() { return dependencies.showLoading.apply(null, arguments); }
        function updateIfcMetrics() { return dependencies.updateIfcMetrics.apply(null, arguments); }

        function exportIfc(action) {
            if (state.exportBusy) return;
            if (!state.ifcModel || !state.ifcModel.elements || !state.ifcModel.elements.length) return;
            var generation = state.exportRequestId;
            setExportBusy(true, action || 'convert');
            ensureFullModel().then(function (fullModel) {
                if (generation !== state.exportRequestId) return;
                runExportWithModel(fullModel, action);
            }).catch(function (err) {
                if (generation !== state.exportRequestId) return;
                hideLoading(); setExportBusy(false);
                addExportDiagnostic(err, {stage: 'ifc_parse'});
            });
        }

        function ensureFullModel() {
            if (state.fullModel && !state.fullModel.elements.some(function (e) { return e.exportGeometryComplete === false; })) return Promise.resolve(state.fullModel);
            if (!state.ifcSourceText) {
                return Promise.reject(new Error('IFC source not in memory — please reopen the file.'));
            }
            showLoading('Preparing FDS conversion', 'Parsing entities…');
            var generation = state.exportRequestId;
            // Export completes openings independently of the preview source.
            var parseOptions = { skipBoxOpenings: false };
            var parsePromise = ns.core.atStage('ifc_parse', function () { return ifcAdapter.parseAsync(state.ifcSourceText, state.ifcFileName, function (fraction) {
                setLoadingProgress(fraction, 'Parsing entities…');
            }, parseOptions); });
            return parsePromise.then(function (model) {
                if (generation !== state.exportRequestId) { var aborted = new Error('Conversion cancelled'); aborted.name = 'AbortError'; throw aborted; }
                state.fullModel = model;
                // Swap the displayed model to the precise one so sidebar counts and the IFC
                // mapping reflect the actual parser output instead of the meta heuristic.
                state.ifcModel = model;
                updateIfcMetrics(model);
                renderDiagnostics();
                hideLoading();
                return model;
            }, function (err) {
                hideLoading();
                throw err;
            });
        }

        function runExportWithModel(fullModel, action) {
            var els = dependencies.getElements(); var viewer = dependencies.getViewer();
            var options = currentExportOptions();
            var requestId = state.exportRequestId + 1;
            state.exportRequestId = requestId;
            setExportBusy(true, action || 'convert');
            // The Convert button's "Converting…" busy state runs in parallel with the export
            // worker; surface the same status on the top banner so the user gets the bigger
            // progress affordance during the FDS-text generation phase as well.
            var fileLabel = (state.ifcFileName || (state.ifcModel && state.ifcModel.fileName) || 'IFC model');
            showLoading('Converting ' + fileLabel, 'Generating FDS file…');

            try {
                var workerHandle = ns.workers.createExportWorker();
                var worker = workerHandle.worker;
                state.exportWorker = worker;
                state.exportWorkerUrl = workerHandle.url;
                worker.addEventListener('message', function (event) {
                    if (requestId !== state.exportRequestId) return;
                    var result = event.data || {};
                    if (result.type === 'progress') {
                        var stage = result.stage ? 'Generating FDS: ' + result.stage : 'Generating FDS file…';
                        setLoadingProgress(result.fraction, stage);
                        return;
                    }
                    if (result.type === 'error') {
                        finishExportWithError(result.error || new Error(result.message || 'Background conversion failed.'));
                        return;
                    }
                    if (result.type !== 'complete') return;

                    cleanupExportWorker();
                    try {
                        var base = (fullModel.fileName || 'ifc_model').replace(/\.[^.]+$/, '').replace(/[^\w.-]+/g, '_');
                        var fileName = base + '_quick_preview_legacy.fds';
                        state.generatedFdsText = result.text;
                        state.generatedFdsName = fileName;
                        els.saveFds.disabled = false;
                        var fdsDrawerBtn = document.getElementById('btn-download-fds');
                        if (fdsDrawerBtn && (!state.lastArtifactLinks || !state.lastArtifactLinks.fds)) {
                            fdsDrawerBtn.classList.remove('disabled');
                            fdsDrawerBtn.style.pointerEvents = '';
                            fdsDrawerBtn.style.opacity = '';
                            fdsDrawerBtn.removeAttribute('aria-disabled');
                        }
                        loadFdsText(result.text, fileName, result.model);
                        hideLoading();
                        // The reveal animation clears any partial clip box from before this
                        // convert; mirror that on the UI so the bars sit at the full extent.
                        setupClippingForBounds(boundsForClipping());
                        // Skip the bottom-up reveal for the in-place "voxelize selected GEOM" path
                        // — the user is editing a small subset of an already-converted scene and
                        // doesn't want the whole building to fade-and-rebuild every time they
                        // change a single OBST.
                        if (viewer.playConversionReveal && action !== 'voxelize') viewer.playConversionReveal();
                    } catch (error) {
                        addExportDiagnostic(error, {stage: 'viewer', requestId: requestId});
                        hideLoading();
                    }
                    setExportBusy(false);
                });
                worker.addEventListener('error', function (event) {
                    if (requestId !== state.exportRequestId) return;
                    finishExportWithError(ns.core.failure(event, {stage: 'worker', requestId: requestId}));
                });
                worker.postMessage({
                    type: 'export',
                    requestId: requestId,
                    ifcModel: fullModel,
                    options: options
                });
            } catch (error) {
                finishExportWithError(error);
            }
        }

        function finishExportWithError(message) {
            cleanupExportWorker();
            addExportDiagnostic(message);
            hideLoading();
            setExportBusy(false);
        }

        function addExportDiagnostic(error, context) {
            var viewer = dependencies.getViewer();
            var failure = ns.core.failure(error, Object.assign({requestId: state.exportRequestId}, context || {}));
            if (!state.ifcModel) state.ifcModel = { diagnostics: [] };
            if (!state.ifcModel.diagnostics) state.ifcModel.diagnostics = [];
            state.ifcModel.diagnostics.push(
                new ns.core.Diagnostic('error', failure.stage === 'viewer' ? 'FDS display failed' : 'FDS export failed',
                    failure.message + ' (stage: ' + failure.stage + ')', failure)
            );
            renderDiagnostics();
        }

        function cleanupExportWorker() {
            if (state.fdsParseReject) {
                var reject = state.fdsParseReject;
                state.fdsParseReject = null;
                var error = new Error('FDS display cancelled'); error.name = 'AbortError';
                reject(error);
            }
            if (state.exportWorker) state.exportWorker.terminate();
            if (state.exportWorkerUrl) URL.revokeObjectURL(state.exportWorkerUrl);
            state.exportWorker = null;
            state.exportWorkerUrl = null;
        }

        function parseFdsInWorker(text, requestId) {
            return new Promise(function (resolve, reject) {
                var handle = ns.workers.createExportWorker();
                state.exportWorker = handle.worker; state.exportWorkerUrl = handle.url;
                state.fdsParseReject = reject;
                function finish(error, model) {
                    state.fdsParseReject = null;
                    cleanupExportWorker();
                    if (error) reject(error); else resolve(model);
                }
                handle.worker.addEventListener('message', function (event) {
                    if (requestId !== state.exportRequestId) return;
                    var result = event.data || {};
                    if (result.type === 'complete') finish(null, result.model);
                    else if (result.type === 'error') finish(new Error(result.message || 'FDS display parsing failed'));
                });
                handle.worker.addEventListener('error', function (event) { finish(new Error(event.message || 'FDS display worker failed')); });
                handle.worker.postMessage({type:'parse-fds', requestId:requestId, text:text});
            });
        }

        function cancelPendingExport() {
            state.exportRequestId += 1;
            if (ns.verified.cancel) ns.verified.cancel().catch(function () {});
            cleanupExportWorker();
            setExportBusy(false);
        }

        function clearGeneratedFds() {
            var els = dependencies.getElements(); var viewer = dependencies.getViewer();
            state.verifiedJobId = null;
            state.generatedFdsText = null;
            state.generatedFdsName = null;
            if (viewer.cancelVerifiedLoad) viewer.cancelVerifiedLoad();
            state.lastArtifactLinks = null;
            state.lastAuditReport = null;
            state.lastManifest = null;
            if (ns.ui && ns.ui.auditDrawer && ns.ui.auditDrawer.clearArtifacts) ns.ui.auditDrawer.clearArtifacts();
            var scenario = ns.workbench && ns.workbench.state && ns.workbench.state.scenarioStore;
            if (scenario && scenario.setInvalidBaseMapping) {
                var previousBase = scenario.getScenarioSpec ? scenario.getScenarioSpec().mappingBundleSha : null;
                scenario.setInvalidBaseMapping(previousBase, 'Conversion result cleared');
            }
            if (els.saveFds) els.saveFds.disabled = true;
            if (els.openAudit) els.openAudit.disabled = true;
            if (els.saveManifest) els.saveManifest.disabled = true;
            var fdsDrawerBtn = document.getElementById('btn-download-fds');
            if (fdsDrawerBtn && (!state.lastArtifactLinks || !state.lastArtifactLinks.fds)) {
                fdsDrawerBtn.removeAttribute('href');
                fdsDrawerBtn.removeAttribute('download');
                fdsDrawerBtn.classList.add('disabled');
                fdsDrawerBtn.style.pointerEvents = 'none';
                fdsDrawerBtn.style.opacity = '0.5';
                fdsDrawerBtn.setAttribute('aria-disabled', 'true');
            }
        }

        function currentExportOptions() {
            var els = dependencies.getElements();
            var cellSize = Math.max(0.05, Number(els.meshCellSize && els.meshCellSize.value) || 0.1);
            var voxelSize = Math.max(0.05, Number(els.voxelSize && els.voxelSize.value) || 0.1);
            return {
                mode: 'hybrid',
                cellSize: cellSize,
                voxelSize: voxelSize,
                openingThickening: Math.max(0, Number(els.openingThickening && els.openingThickening.value) || 0),
                openingVoxelPolicy: els.openingVoxelPolicy ? els.openingVoxelPolicy.value : 'smaller',
                includeFillSolids: !!(els.includeFillSolids && els.includeFillSolids.checked),
                includeReviewSolids: !!(els.includeReviewSolids && els.includeReviewSolids.checked),
                // Default to HOLE approach (cleaner FDS, exact rectangular cutouts). Voxelization
                // is kept as a fallback for IFCs with non-axis-aligned or curved openings.
                useObstHoles: !els.conversionApproach || els.conversionApproach.value !== 'voxel',
                forceObstStepIds: Object.keys(state.forceObstStepIds),
                excludedStepIds: Object.keys(state.excludedStepIds),
                excludedItemIds: Object.keys(state.excludedItemIds),
                boxFriendlyThreshold: Math.max(0.5, Math.min(1, Number(els.obstThreshold && els.obstThreshold.value) || 0.8))
            };
        }

        function countConvertibleIfc(model) {
            return exporter.getExportableElements(model, currentExportOptions()).length;
        }

        return {
            exportIfc: exportIfc,
            ensureFullModel: ensureFullModel,
            runExportWithModel: runExportWithModel,
            finishExportWithError: finishExportWithError,
            addExportDiagnostic: addExportDiagnostic,
            cleanupExportWorker: cleanupExportWorker,
            parseFdsInWorker: parseFdsInWorker,
            cancelPendingExport: cancelPendingExport,
            clearGeneratedFds: clearGeneratedFds,
            currentExportOptions: currentExportOptions,
            countConvertibleIfc: countConvertibleIfc
        };
    };
})(window.IfcFds);
