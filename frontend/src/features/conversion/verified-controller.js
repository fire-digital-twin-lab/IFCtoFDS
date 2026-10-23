(function (ns) {
    ns.features = ns.features || {};
    ns.features.conversion = ns.features.conversion || {};
    ns.features.conversion.createVerifiedController = function (dependencies) {
        function hideLoading() { return dependencies.hideLoading.apply(null, arguments); }
        function setLoadingProgress() { return dependencies.setLoadingProgress.apply(null, arguments); }
        var state = dependencies.state;
        function addExportDiagnostic() { return dependencies.addExportDiagnostic.apply(null, arguments); }
        function boundsForClipping() { return dependencies.boundsForClipping.apply(null, arguments); }
        function cleanupExportWorker() { return dependencies.cleanupExportWorker.apply(null, arguments); }
        function clearGeneratedFds() { return dependencies.clearGeneratedFds.apply(null, arguments); }
        function exposeFailedCheckpoints() { return dependencies.exposeFailedCheckpoints.apply(null, arguments); }
        function loadFdsText() { return dependencies.loadFdsText.apply(null, arguments); }
        function openAudit() { return dependencies.openAudit.apply(null, arguments); }
        function parseFdsInWorker() { return dependencies.parseFdsInWorker.apply(null, arguments); }
        function renderAuditReport() { return dependencies.renderAuditReport.apply(null, arguments); }
        function setExportBusy() { return dependencies.setExportBusy.apply(null, arguments); }
        function setupClippingForBounds() { return dependencies.setupClippingForBounds.apply(null, arguments); }
        function showLoading() { return dependencies.showLoading.apply(null, arguments); }
        function updateGlobalStatusBadge() { return dependencies.updateGlobalStatusBadge.apply(null, arguments); }

        function exportVerified() {
            var els = dependencies.getElements(); var viewer = dependencies.getViewer();
            if (state.exportBusy) return;
            if (!state.ifcSourceText && !state.currentIfcFile && !ns.verified.hasFiles()) {
                addExportDiagnostic('IFC source not in memory — please reopen the file.');
                return;
            }
            clearGeneratedFds();
            // The single background worker should convert immediately instead of
            // waiting for a now-unneeded source preview to finish first.
            ns.ifc.backendPreview.cancel();
            state.ifcLoadRequestId = (state.ifcLoadRequestId || 0) + 1;

            var fileLabel = (state.ifcFileName || (state.ifcModel && state.ifcModel.fileName) || 'IFC model');
            showLoading('Verified Conversion: ' + fileLabel, 'Processing with IfcOpenShell & OpenCASCADE...');
            setExportBusy(true, 'convert-verified');
            var generation = ++state.exportRequestId;
            var cancelButton = document.getElementById('verified-cancel');
            if (cancelButton) cancelButton.disabled = false;

            var blob = state.currentIfcFile || new File([state.ifcSourceText || ''], state.ifcFileName || 'model.ifc');
            var forceGeom = !!(els.verifiedForceGeom && els.verifiedForceGeom.checked);
            var cellSize = Number(els.verifiedCellSize && els.verifiedCellSize.value) || Number(els.meshCellSize && els.meshCellSize.value) || 0.20;
            ns.verified.run(blob, {
                cell_size: cellSize,
                all_geom: forceGeom,
            }, function (message, detail, activeJobId) {
                if (generation !== state.exportRequestId) return;
                state.verifiedJobId = activeJobId;
                if (els.ifcLoadingStage) els.ifcLoadingStage.textContent = message;
            })
            .then(async function (data) {
                if (generation !== state.exportRequestId) return;
                state.verifiedJobId = data && data.job_id;
                setLoadingProgress(0.85, 'Loading conversion artifacts.');
                if (!data || !data.artifacts) throw new Error('Missing conversion artifacts');
                state.lastArtifactLinks = data.artifacts;
                var summary = Object.assign({}, data, {configuration: {}, matched_count: (data.coverage || {}).geometry || 0});
                state.lastAuditReport = summary;
                state.lastManifest = null;
                if (els.openAudit) els.openAudit.disabled = false;
                if (els.saveManifest) els.saveManifest.disabled = false;
                if (viewer.bindVerifiedArtifacts) viewer.bindVerifiedArtifacts(data.artifacts);

                var manifestPromise = (data.artifacts.manifest && data.artifacts.manifest.url)
                    ? ns.api.artifacts.optionalJson(data.artifacts.manifest.url).catch(function () { return null; })
                    : Promise.resolve(null);
                var reportPromise = (data.artifacts.report && data.artifacts.report.url)
                    ? ns.api.artifacts.optionalJson(data.artifacts.report.url).catch(function () { return null; })
                    : Promise.resolve(null);

                var extraArtifacts = await Promise.all([manifestPromise, reportPromise]);
                if (generation !== state.exportRequestId) return;
                var manifestData = extraArtifacts[0];
                var fullReport = Object.assign({}, summary, extraArtifacts[1] || {});
                if (data && data.artifacts) {
                    fullReport.artifacts = data.artifacts;
                }
                state.lastManifest = manifestData;
                state.lastAuditReport = fullReport;

                if (ns.workbench && ns.workbench.state && ns.workbench.state.selectionStore && manifestData) {
                    var records = manifestData.records || manifestData.elements || [];
                    ns.workbench.state.selectionStore.hydrateManifest(records, fullReport);
                }

                renderAuditReport(fullReport); openAudit();
                var authH = (ns.verified && typeof ns.verified.getAuthHeaders === 'function') ? ns.verified.getAuthHeaders() : {};
                var response = await ns.api.request(data.artifacts.fds.url, { headers: authH });
                if (!response.ok) throw new Error('FDS artifact unavailable');
                var text = await response.text();
                if (generation !== state.exportRequestId) return;
                var base = (data.source_filename || state.ifcFileName || 'model').replace(/\.[^.]+$/, '');
                var fileName = base + (data.status === 'MAPPING_VERIFIED' ? '_mapping_verified.fds' : '_diagnostic_unaccepted.fds');
                state.generatedFdsText = text; state.generatedFdsName = fileName;
                if (els.saveFds) els.saveFds.disabled = false;
                setLoadingProgress(0.95, 'Preparing FDS display.');
                var displayModel = await parseFdsInWorker(text, generation);
                if (generation !== state.exportRequestId) return;
                loadFdsText(text, fileName, displayModel);
                if (ns.workbench && ns.workbench.state && ns.workbench.state.scenarioStore) {
                    var mSha = (manifestData && (manifestData.bundle_sha256 || manifestData.fds_sha256 || manifestData.source_sha256)) ||
                               (data.artifacts && data.artifacts.manifest && data.artifacts.manifest.sha256) ||
                               (data.artifacts && data.artifacts.fds && data.artifacts.fds.sha256);
                    if (mSha) {
                        var isVerified = (data.status === 'MAPPING_VERIFIED' || data.mapping_status === 'MAPPING_VERIFIED');
                        if (isVerified) {
                            ns.workbench.state.scenarioStore.setBaseMapping(mSha);
                        } else if (typeof ns.workbench.state.scenarioStore.setInvalidBaseMapping === 'function') {
                            ns.workbench.state.scenarioStore.setInvalidBaseMapping(mSha, data.status || data.mapping_status);
                        }
                    }
                }
                setupClippingForBounds(boundsForClipping());
            })
            .catch(function (err) {
                if (generation !== state.exportRequestId || err.name === 'AbortError') return;
                state.verifiedJobId = err.jobId || state.verifiedJobId;
                hideLoading();
                setExportBusy(false);
                addExportDiagnostic(err, {stage: 'verified_conversion', jobId: state.verifiedJobId});
                updateGlobalStatusBadge('FAILED');
                if (state.verifiedJobId) exposeFailedCheckpoints(state.verifiedJobId);
            }).finally(function () {
                if (generation === state.exportRequestId) { cleanupExportWorker(); hideLoading(); setExportBusy(false); }
            });
        }

        return {
            exportVerified: exportVerified
        };
    };
})(window.IfcFds);
