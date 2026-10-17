(function (ns) {
    var parser = new ns.fds.FdsNamelistParser();
    var adapter = new ns.fds.FdsGeometryAdapter();
    var ifcAdapter = new ns.ifc.IfcAdapter();
    var webIfcDisplay = ns.ifc.WebIfcDisplay ? new ns.ifc.WebIfcDisplay() : null;
    var exporter = new ns.fds.FdsExporter();
    var state = {
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

    var els = {};
    var viewer = null;
    var currentTheme = 'light';
    var VIEW_KEY_TO_DIRECTION = {
        '1': 'front',
        '2': 'back',
        '3': 'left',
        '4': 'right',
        '5': 'top',
        '6': 'bottom',
        '0': 'iso'
    };

    document.addEventListener('DOMContentLoaded', function () {
        cacheElements();
        viewer = new ns.viewer.SceneViewer(els.viewer, showSelection);
        viewer.setNavigationModeChangeHandler(updateWalkModeButton);
        applyTheme(readSavedTheme());
        if (window.lucide) window.lucide.createIcons();
        bindEvents();
        ns.verified.init();
        clearFdsModel();
        checkBackendHealth();
        window.addEventListener('focus', checkBackendHealth);
    });

    function cacheElements() {
        els.viewer = document.getElementById('viewer');
        els.ifcFile = document.getElementById('ifc-file');
        els.toggleTheme = document.getElementById('toggle-theme');
        els.toggleWalk = document.getElementById('toggle-walk');
        els.openHelp = document.getElementById('open-help');
        els.footerHelp = document.getElementById('footer-help');
        els.helpModal = document.getElementById('help-modal');
        els.closeHelp = document.getElementById('close-help');
        els.resetCamera = document.getElementById('reset-camera');
        els.convertIfc = document.getElementById('convert-ifc');
        els.convertSelectedObst = document.getElementById('convert-selected-obst');
        els.saveFds = document.getElementById('save-fds');
        els.fdsSourceName = document.getElementById('fds-source-name');
        els.ifcSourceName = document.getElementById('ifc-source-name');
        els.diagnostics = document.getElementById('diagnostics');
        els.inspectCard = document.getElementById('inspect-card');
        els.inspectTitle = document.getElementById('inspect-title');
        els.inspectBody = document.getElementById('inspect-body');
        els.countMeshes = document.getElementById('count-meshes');
        els.countObsts = document.getElementById('count-obsts');
        els.countVents = document.getElementById('count-vents');
        els.countGeoms = document.getElementById('count-geoms');
        els.countTriangles = document.getElementById('count-triangles');
        els.countIfc = document.getElementById('count-ifc');
        els.countIfcConvertible = document.getElementById('count-ifc-convertible');
        els.ifcMapping = document.getElementById('ifc-mapping');
        els.fdsOpacity = document.getElementById('fds-opacity');
        els.ifcOpacity = document.getElementById('ifc-opacity');
        els.meshCellSize = document.getElementById('mesh-cell-size');
        els.voxelSize = document.getElementById('voxel-size');
        els.openingThickening = document.getElementById('opening-thickening');
        els.openingVoxelPolicy = document.getElementById('opening-voxel-policy');
        els.includeFillSolids = document.getElementById('include-fill-solids');
        els.includeReviewSolids = document.getElementById('include-review-solids');
        els.conversionApproach = document.getElementById('conversion-approach');
        els.obstThreshold = document.getElementById('obst-threshold');
        els.obstThresholdVal = document.getElementById('obst-threshold-val');
        els.openCredits = document.getElementById('open-credits');
        els.creditsModal = document.getElementById('credits-modal');
        els.closeCredits = document.getElementById('close-credits');
        els.openAudit = document.getElementById('open-audit');
        els.saveManifest = document.getElementById('save-manifest');
        els.convertVerified = document.getElementById('convert-verified');
        els.auditModal = document.getElementById('audit-modal');
        els.closeAudit = document.getElementById('close-audit');
        els.auditBody = document.getElementById('audit-body');
        els.backendStatusIndicator = document.getElementById('backend-status-indicator');
        els.backendStatusText = document.getElementById('backend-status-text');
        els.ifcLoading = document.getElementById('ifc-loading');
        els.ifcLoadingTitle = document.getElementById('ifc-loading-title');
        els.ifcLoadingPercent = document.getElementById('ifc-loading-percent');
        els.ifcLoadingFill = document.getElementById('ifc-loading-fill');
        els.ifcLoadingStage = document.getElementById('ifc-loading-stage');
        els.saveProcessed = document.getElementById('save-processed');
        els.showIfcEdges = document.getElementById('show-ifc-edges');
        els.showGrid = document.getElementById('show-grid');
        els.showStructure = document.getElementById('show-structure');
        els.showFills = document.getElementById('show-fills');
        els.showOther = document.getElementById('show-other');
        els.showObst = document.getElementById('show-obst');
        els.showHole = document.getElementById('show-hole');
        els.showGeom = document.getElementById('show-geom');
        els.deleteSelected = document.getElementById('delete-selected-ifc');
        els.undoLast = document.getElementById('undo-last');
        els.clipPanel = document.getElementById('clip-panel');
        els.clipReset = document.getElementById('clip-reset');
        els.clipSliders = {
            xmin: document.getElementById('clip-xmin'),
            xmax: document.getElementById('clip-xmax'),
            ymin: document.getElementById('clip-ymin'),
            ymax: document.getElementById('clip-ymax'),
            zmin: document.getElementById('clip-zmin'),
            zmax: document.getElementById('clip-zmax')
        };
        els.clipInputs = {
            xmin: document.getElementById('clip-xmin-val'),
            xmax: document.getElementById('clip-xmax-val'),
            ymin: document.getElementById('clip-ymin-val'),
            ymax: document.getElementById('clip-ymax-val'),
            zmin: document.getElementById('clip-zmin-val'),
            zmax: document.getElementById('clip-zmax-val')
        };
        els.modeTabVerified = document.getElementById('mode-tab-verified');
        els.modeTabQuick = document.getElementById('mode-tab-quick');
        els.containerVerified = document.getElementById('container-verified');
        els.containerQuick = document.getElementById('container-quick');
        els.verifiedWorkflowBanner = document.getElementById('verified-workflow-banner');
        els.quickWorkflowBanner = document.getElementById('quick-workflow-banner');
        els.verifiedStoreys = document.getElementById('verified-storeys');
        els.verifiedUseDomain = document.getElementById('verified-use-domain');
        els.verifiedDomainWarning = document.getElementById('verified-domain-warning');
        els.verifiedForceGeom = document.getElementById('verified-force-geom');
        els.verifiedCellSize = document.getElementById('verified-cell-size');
        els.domainEstCells = document.getElementById('domain-est-cells');
        els.domainEstBudget = document.getElementById('domain-est-budget');
        els.domainDimensionsText = document.getElementById('domain-dimensions-text');
        els.auditDrawer = document.getElementById('audit-drawer');
        els.toggleDrawer = document.getElementById('toggle-drawer');
        els.closeInspector = document.getElementById('close-inspector');
    }

    function applyClip(id, value) {
        var slider = els.clipSliders[id];
        var input = els.clipInputs[id];
        if (slider) slider.value = String(value);
        if (input) input.value = Number(value).toFixed(2);
        var axisChar = id.charAt(0);
        var side = id.slice(1);
        viewer.setClipPlane(axisChar, side, Number(value));
    }

    function clampClip(id, raw) {
        var slider = els.clipSliders[id];
        if (!slider) return raw;
        var v = Number(raw);
        if (!isFinite(v)) return Number(slider.value);
        return Math.max(Number(slider.min), Math.min(Number(slider.max), v));
    }

    function bindClipSlider(id) {
        var slider = els.clipSliders[id];
        var input = els.clipInputs[id];
        if (!slider) return;
        slider.addEventListener('input', function () { applyClip(id, slider.value); });
        if (input) {
            input.addEventListener('change', function () { applyClip(id, clampClip(id, input.value)); });
            input.addEventListener('keydown', function (event) {
                if (event.key === 'Enter') input.blur();
            });
        }
    }

    function bindClipSteppers() {
        Array.prototype.forEach.call(document.querySelectorAll('.clip-step'), function (btn) {
            btn.addEventListener('click', function () {
                var id = String(btn.getAttribute('data-target') || '').replace(/^clip-/, '');
                var dir = Number(btn.getAttribute('data-dir')) || 0;
                var slider = els.clipSliders[id];
                if (!slider) return;
                var step = Number(slider.step) || 0.1;
                var current = Number(slider.value);
                applyClip(id, clampClip(id, current + dir * step));
            });
        });
    }

    function setupClippingForBounds(bounds) {
        if (!els.clipPanel) return;
        if (!bounds) { els.clipPanel.hidden = true; return; }
        els.clipPanel.hidden = false;
        var pairs = [['xmin', 'xmax', bounds.xmin, bounds.xmax], ['ymin', 'ymax', bounds.ymin, bounds.ymax], ['zmin', 'zmax', bounds.zmin, bounds.zmax]];
        pairs.forEach(function (p) {
            var lo = p[2], hi = p[3];
            var span = Math.max(hi - lo, 0.001);
            // Step granularity: round to a sensible nudge (cm-scale on a metre-scale model)
            // so the ▲/▼ buttons feel like 0.01–0.1 m per click rather than fractional µm.
            var step = Math.max(span / 200, 0.01);
            [[p[0], lo], [p[1], hi]].forEach(function (pair) {
                var id = pair[0], value = pair[1];
                var slider = els.clipSliders[id];
                var input = els.clipInputs[id];
                if (slider) { slider.min = String(lo); slider.max = String(hi); slider.step = String(step); slider.value = String(value); }
                if (input) input.value = Number(value).toFixed(2);
            });
        });
        viewer.setClipBoundsNative(bounds);
    }

    function showLoading(title, stage) {
        if (!els.ifcLoading) return;
        els.ifcLoadingTitle.textContent = title || 'Loading IFC…';
        els.ifcLoadingStage.textContent = stage || '';
        els.ifcLoadingPercent.textContent = '';
        els.ifcLoadingFill.classList.add('is-indeterminate');
        els.ifcLoadingFill.style.width = '';
        els.ifcLoading.hidden = false;
    }

    function setLoadingProgress(fraction, stage) {
        if (!els.ifcLoading || els.ifcLoading.hidden) return;
        if (stage !== undefined) els.ifcLoadingStage.textContent = stage;
        var f = Math.max(0, Math.min(1, fraction || 0));
        els.ifcLoadingFill.classList.remove('is-indeterminate');
        els.ifcLoadingFill.style.width = (f * 100).toFixed(1) + '%';
        els.ifcLoadingPercent.textContent = Math.round(f * 100) + '%';
    }

    function hideLoading() {
        if (!els.ifcLoading) return;
        els.ifcLoading.hidden = true;
        els.ifcLoadingFill.classList.add('is-indeterminate');
        els.ifcLoadingFill.style.width = '';
    }

    function setSaveProcessedEnabled(enabled) {
        if (els.saveProcessed) els.saveProcessed.disabled = !enabled;
    }

    function finishIfcLoad(model, displayMeshes, oversizeNotice) {
        state.ifcModel = model;
        state.lastDisplayMeshes = displayMeshes || null;
        if (oversizeNotice && model && model.diagnostics) model.diagnostics.unshift(oversizeNotice);
        setLoadingProgress(1, 'Rendering…');
        viewer.loadIfcModel(model, displayMeshes);
        viewer.setIfcOpacity(Number(els.ifcOpacity.value));
        updateIfcMetrics(model);
        updateSourcePill(state.currentIfcFile, model);
        setExportEnabled(countConvertibleIfc(model) > 0);
        setSaveProcessedEnabled(!!(model && model.elements && model.elements.length));
        setupClippingForBounds(boundsForClipping());
        renderDiagnostics();
        hideLoading();
    }

    // Prefers the lightweight meta model's expressIDs (when web-ifc rendered) by reading the
    // viewer's world Box3, then falls back to the parsed model's bounds. Returns IFC-native
    // coordinates because the clipping API speaks in those.
    function boundsForClipping() {
        var model = state.ifcModel;
        if (model && (model.convertibleBounds || model.bounds)) return model.convertibleBounds || model.bounds;
        // Meta-only model — compute world box from the IFC group, then unswap to native.
        if (!viewer || !viewer.ifcGroup) return null;
        viewer.ifcGroup.updateMatrixWorld(true);
        var box = new THREE.Box3().expandByObject(viewer.ifcGroup);
        if (box.isEmpty()) return null;
        // toThree(x, y, z) = (x, z, y) — so to invert: native (x, z_three, y_three).
        return {
            xmin: box.min.x, xmax: box.max.x,
            ymin: box.min.z, ymax: box.max.z,
            zmin: box.min.y, zmax: box.max.y
        };
    }

    function failIfcLoad(fileName, error) {
        hideLoading();
        state.ifcModel = {
            fileName: fileName,
            elements: [],
            diagnostics: [
                new ns.core.Diagnostic('error', 'IFC import failed', error && error.message ? error.message : String(error), ns.core.failure(error, {stage: 'ifc_read'}))
            ]
        };
        state.lastDisplayMeshes = null;
        updateIfcMetrics(state.ifcModel);
        setExportEnabled(false);
        setSaveProcessedEnabled(false);
        renderDiagnostics();
    }

    function bindEvents() {
        els.toggleTheme.addEventListener('click', function () {
            var theme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(theme);
            try {
                localStorage.setItem('ifc-fds-theme', theme);
            } catch (error) {
                // Theme switching still works when storage is unavailable.
            }
        });

        els.toggleWalk.addEventListener('click', function () {
            viewer.setNavigationMode(viewer.navigationMode === 'walk' ? 'orbit' : 'walk');
        });

        // Both the toolbar help button and the footer "Guide" link now open the standalone
        // single-column guide.html page in a new tab instead of layering a modal over the
        // viewer. The old modal markup is left in place as a fallback for any environment
        // where window.open is blocked.
        [els.openHelp, els.footerHelp].forEach(function (button) {
            if (!button) return;
            button.addEventListener('click', function (event) {
                event.preventDefault();
                var opened = window.open('guide.html', '_blank', 'noopener');
                if (!opened) openHelp();
            });
        });

        if (els.closeHelp) els.closeHelp.addEventListener('click', closeHelp);
        if (els.helpModal) {
            var backdrop = els.helpModal.querySelector('[data-close-help]');
            if (backdrop) backdrop.addEventListener('click', closeHelp);
        }

        if (els.openCredits) els.openCredits.addEventListener('click', openCredits);
        if (els.closeCredits) els.closeCredits.addEventListener('click', closeCredits);
        if (els.creditsModal) els.creditsModal.querySelector('[data-close-credits]').addEventListener('click', closeCredits);

        if (els.openAudit) els.openAudit.addEventListener('click', openAudit);
        if (els.closeAudit) els.closeAudit.addEventListener('click', closeAudit);
        if (els.auditModal) {
            var auditBackdrop = els.auditModal.querySelector('[data-close-audit]');
            if (auditBackdrop) auditBackdrop.addEventListener('click', closeAudit);
        }

        window.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && !els.helpModal.hidden) closeHelp();
            if (event.key === 'Escape' && els.creditsModal && !els.creditsModal.hidden) closeCredits();
            if (event.key === 'Escape' && els.auditModal && !els.auditModal.hidden) closeAudit();
        });

        els.ifcFile.addEventListener('change', function (event) {
            var file = event.target.files[0];
            if (!file) return;
            state.currentIfcFile = file;
            ns.verified.setFallback(file);
            cancelPendingExport();
            clearGeneratedFds();
            clearFdsModel();
            state.forceObstStepIds = {};
            state.excludedStepIds = {};
            state.excludedItemIds = {};
            state.undoStack = [];
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

            // Mirrors the demo's fast open: regex-index for sidebar/selection metadata, web-ifc
            // for display. The heavy ifc-adapter parse runs later, only when Convert to FDS is
            // clicked. Above WEB_IFC_MAX_BYTES we still skip the WASM display path to keep the
            // tab stable — the meta index by itself is fine on any size.
            var WEB_IFC_MAX_BYTES = 32 * 1024 * 1024;
            var useWebIfcDisplay = webIfcDisplay && file.size <= WEB_IFC_MAX_BYTES;
            var oversizeNotice = (webIfcDisplay && file.size > WEB_IFC_MAX_BYTES)
                ? new ns.core.Diagnostic(
                    'info',
                    'High-detail preview disabled',
                    'IFC file is ' + (file.size / (1024 * 1024)).toFixed(1)
                        + ' MB; the WASM display engine is skipped to keep the tab stable. '
                        + 'FDS conversion is unaffected.'
                )
                : null;

            file.arrayBuffer().then(function (buffer) {
                if (state.currentIfcFile !== file) return;
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
                    if (state.currentIfcFile !== file) return;
                    if (displayMeshes && displayMeshes.length) {
                        finishIfcLoad(meta, displayMeshes, oversizeNotice);
                        return;
                    }
                    // No WASM display available — fall back to the legacy parser so the viewer
                    // has geometry to draw. Caches it as state.fullModel so Convert won't reparse.
                    return ifcAdapter.parseAsync(text, file.name, function (fraction) {
                        setLoadingProgress(fraction, 'Parsing legacy mesh…');
                    }).then(function (fullModel) {
                        if (state.currentIfcFile !== file) return;
                        state.fullModel = fullModel;
                        finishIfcLoad(fullModel, null, oversizeNotice);
                    });
                });
            }).catch(function (error) {
                if (state.currentIfcFile !== file) return;
                failIfcLoad(file.name, error);
            });
        });

        els.resetCamera.addEventListener('click', function () {
            viewer.resetCamera();
        });

        els.convertIfc.addEventListener('click', function () {
            exportIfc('convert');
        });

        if (els.convertVerified) {
            els.convertVerified.addEventListener('click', function () {
                exportVerified();
            });
        }

        els.convertSelectedObst.addEventListener('click', function () {
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
            els.deleteSelected.addEventListener('click', function () {
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
            els.undoLast.addEventListener('click', undoLastChange);
        }

        ['xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'].forEach(bindClipSlider);
        bindClipSteppers();
        if (els.obstThreshold && els.obstThresholdVal) {
            els.obstThreshold.addEventListener('input', function () {
                els.obstThresholdVal.value = Number(els.obstThreshold.value).toFixed(2);
            });
            els.obstThresholdVal.addEventListener('change', function () {
                var v = Number(els.obstThresholdVal.value);
                if (!isFinite(v)) { els.obstThresholdVal.value = Number(els.obstThreshold.value).toFixed(2); return; }
                v = Math.max(Number(els.obstThreshold.min), Math.min(Number(els.obstThreshold.max), v));
                els.obstThreshold.value = String(v);
                els.obstThresholdVal.value = v.toFixed(2);
            });
            els.obstThresholdVal.addEventListener('keydown', function (event) {
                if (event.key === 'Enter') els.obstThresholdVal.blur();
            });
        }
        if (els.clipReset) {
            els.clipReset.addEventListener('click', function () {
                viewer.resetClipping();
                if (state.ifcModel) setupClippingForBounds(boundsForClipping());
            });
        }

        window.addEventListener('keydown', function (event) {
            var key = event.key && event.key.toLowerCase();
            var tag = (event.target && event.target.tagName) || '';
            var typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
            if (key === 'z' && (event.ctrlKey || event.metaKey) && !event.shiftKey) {
                if (typing) return;
                if (els.undoLast && !els.undoLast.disabled) {
                    event.preventDefault();
                    undoLastChange();
                }
                return;
            }
            // Number-key view shortcuts (mirrors ProfRino/fds-viewer). Skipped while typing
            // in inputs, walking, or with any non-Shift modifier held.
            if (typing) return;
            if (viewer.navigationMode === 'walk') return;
            if (event.ctrlKey || event.metaKey || event.altKey) return;

            // Arrow-key orbit/dolly: left/right yaw, up/down pitch; Shift + arrows dollies
            // or strafes. Mirrors ProfRino/fds-viewer's keyboard navigation.
            var arrowMap = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down' };
            if (arrowMap[event.key] && viewer.orbitByKey) {
                event.preventDefault();
                viewer.orbitByKey(arrowMap[event.key], { shift: event.shiftKey });
                return;
            }

            if (event.shiftKey) return;
            var viewKey = VIEW_KEY_TO_DIRECTION[event.key];
            if (viewKey) {
                event.preventDefault();
                viewer.setView(viewKey);
            }
        });

        els.saveFds.addEventListener('click', function () {
            if (!state.generatedFdsText || !state.generatedFdsName) return;
            downloadText(state.generatedFdsName, state.generatedFdsText);
        });

        if (els.saveManifest) {
            els.saveManifest.addEventListener('click', function () {
                if (state.lastArtifactLinks) {
                    var link = document.createElement('a'); link.href = state.lastArtifactLinks.manifest.url;
                    link.download = ''; link.click(); return;
                }
                if (!state.lastManifest) return;
                var base = ((state.lastManifest || {}).source_filename || state.ifcFileName || 'ifc_model').replace(/\.[^.]+$/, '').replace(/[^\w.-]+/g, '_');
                downloadText(base + '_manifest.json', JSON.stringify(state.lastManifest, null, 2));
            });
        }

        if (els.saveProcessed) {
            els.saveProcessed.addEventListener('click', function () {
                var processed = ns.ifc.ProcessedFile;
                if (!processed || !state.ifcModel || !state.ifcModel.elements || !state.ifcModel.elements.length) return;
                showLoading('Saving processed file', 'Serializing…');
                // Defer to next tick so the bar paints before the (potentially long)
                // JSON.stringify pass on the structured-clone payload.
                setTimeout(function () {
                    try {
                        var text = processed.serialize(state.ifcModel, state.lastDisplayMeshes);
                        var base = (state.ifcModel.fileName || 'ifc_model').replace(/\.[^.]+$/, '').replace(/[^\w.-]+/g, '_');
                        downloadText(base + processed.EXTENSION, text);
                    } catch (err) {
                        console.warn('processed-file save failed:', err);
                    }
                    hideLoading();
                }, 0);
            });
        }

        Array.prototype.forEach.call(document.querySelectorAll('[data-view-mode]'), function (button) {
            button.addEventListener('click', function () {
                Array.prototype.forEach.call(document.querySelectorAll('[data-view-mode]'), function (other) {
                    other.classList.toggle('active', other === button);
                });
                viewer.setViewMode(button.getAttribute('data-view-mode'));
            });
        });

        els.fdsOpacity.addEventListener('input', function () {
            viewer.setFdsOpacity(Number(els.fdsOpacity.value));
        });

        els.ifcOpacity.addEventListener('input', function () {
            viewer.setIfcOpacity(Number(els.ifcOpacity.value));
        });

        [els.includeFillSolids, els.includeReviewSolids].forEach(function (input) {
            input.addEventListener('change', function () {
                updateIfcMetrics(state.ifcModel);
                setExportEnabled(countConvertibleIfc(state.ifcModel) > 0);
            });
        });

        if (els.showIfcEdges) {
            els.showIfcEdges.addEventListener('change', function (event) {
                viewer.setIfcEdgesVisible(event.target.checked);
            });
        }
        bindToggle('show-grid', 'groundGrid');
        bindToggle('show-obst', 'obsts');
        bindToggle('show-hole', 'holes');
        bindToggle('show-geom', 'geoms');
        if (els.showStructure) {
            els.showStructure.addEventListener('change', function (event) {
                viewer.setIfcCategoryVisible('structure', event.target.checked);
            });
        }
        if (els.showFills) {
            els.showFills.addEventListener('change', function (event) {
                viewer.setIfcCategoryVisible('fills', event.target.checked);
            });
        }
        if (els.showOther) {
            els.showOther.addEventListener('change', function (event) {
                viewer.setIfcCategoryVisible('other', event.target.checked);
            });
        }

        // Workflow Mode Switcher
        if (els.modeTabVerified) {
            els.modeTabVerified.addEventListener('click', function () { setWorkflowMode('verified'); });
        }
        if (els.modeTabQuick) {
            els.modeTabQuick.addEventListener('click', function () { setWorkflowMode('quick'); });
        }

        // Viewport Floating Toolbar Popovers
        var btnLayers = document.getElementById('toggle-layers-popover');
        var popLayers = document.getElementById('layers-popover');
        var btnCamera = document.getElementById('toggle-camera-views');
        var popCamera = document.getElementById('camera-popover');
        if (btnLayers && popLayers) {
            btnLayers.addEventListener('click', function (e) {
                e.stopPropagation();
                popLayers.style.display = popLayers.style.display === 'none' ? 'flex' : 'none';
                if (popCamera) popCamera.style.display = 'none';
            });
        }
        if (btnCamera && popCamera) {
            btnCamera.addEventListener('click', function (e) {
                e.stopPropagation();
                popCamera.style.display = popCamera.style.display === 'none' ? 'flex' : 'none';
                if (popLayers) popLayers.style.display = 'none';
            });
        }
        document.addEventListener('click', function () {
            if (popLayers) popLayers.style.display = 'none';
            if (popCamera) popCamera.style.display = 'none';
        });

        var btnClip = document.getElementById('toggle-clip');
        if (btnClip && els.clipPanel) {
            btnClip.addEventListener('click', function () {
                els.clipPanel.hidden = !els.clipPanel.hidden;
            });
        }

        Array.prototype.forEach.call(document.querySelectorAll('[data-cam]'), function (btn) {
            btn.addEventListener('click', function () {
                var dir = btn.getAttribute('data-cam');
                if (dir && viewer && viewer.setView) viewer.setView(dir);
            });
        });

        // Color Mode Selector
        var colorSelect = document.getElementById('color-mode-select');
        if (colorSelect) {
            colorSelect.addEventListener('change', function () {
                updateColorModeLegend(colorSelect.value);
            });
        }

        // Domain Estimates & Preflight Scoped Domain Warning
        ['xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'].forEach(function (axis) {
            var input = document.getElementById('verified-domain-' + axis);
            if (input) input.addEventListener('input', updateDomainEstimates);
        });
        if (els.verifiedCellSize) {
            els.verifiedCellSize.addEventListener('input', updateDomainEstimates);
        }
        if (els.verifiedStoreys) {
            els.verifiedStoreys.addEventListener('change', checkScopedDomainPreflight);
        }
        if (els.verifiedUseDomain) {
            els.verifiedUseDomain.addEventListener('change', function () {
                var box = document.getElementById('verified-domain-box');
                if (box) box.style.display = els.verifiedUseDomain.checked ? 'grid' : 'none';
                checkScopedDomainPreflight();
            });
        }
        var useBoundsCheck = document.getElementById('verified-use-bounds');
        var boundsBox = document.getElementById('verified-bounds-box');
        if (useBoundsCheck && boundsBox) {
            useBoundsCheck.addEventListener('change', function () {
                boundsBox.style.display = useBoundsCheck.checked ? 'grid' : 'none';
            });
        }

        // Reviewed Decisions Upload Summary Preview
        var decisionsInput = document.getElementById('verified-decisions');
        var decisionsChip = document.getElementById('decisions-summary-chip');
        if (decisionsInput && decisionsChip) {
            decisionsInput.addEventListener('change', async function () {
                if (!decisionsInput.files || !decisionsInput.files.length) {
                    decisionsChip.style.display = 'none';
                    return;
                }
                try {
                    var data = JSON.parse(await decisionsInput.files[0].text());
                    var keys = Object.keys(data);
                    var passive = keys.filter(function (k) { return data[k].action === 'PASSIVE_OBSTACLE'; }).length;
                    var ref = keys.filter(function (k) { return data[k].action === 'REFERENCE_GEOMETRY'; }).length;
                    var excl = keys.filter(function (k) { return data[k].action === 'EXCLUDE'; }).length;
                    decisionsChip.style.display = 'flex';
                    decisionsChip.textContent = '✓ ' + keys.length + ' decisions loaded (' + passive + ' Obstacle, ' + ref + ' Reference, ' + excl + ' Excluded)';
                } catch (e) {
                    decisionsChip.style.display = 'flex';
                    decisionsChip.textContent = '⚠️ Malformed decisions JSON';
                }
            });
        }

        // Inspector Tabs
        ['id', 'map', 'geom', 'mep'].forEach(function (tab) {
            var btn = document.getElementById('inspect-tab-' + tab);
            if (btn) {
                btn.addEventListener('click', function () {
                    activeInspectorTab = tab;
                    ['id', 'map', 'geom', 'mep'].forEach(function (t) {
                        var b = document.getElementById('inspect-tab-' + t);
                        if (b) b.classList.toggle('active', t === tab);
                    });
                    if (state.selection && state.selection.length) {
                        renderStructuredInspector(state.selection[0]);
                    }
                });
            }
        });
        if (els.closeInspector) {
            els.closeInspector.addEventListener('click', function () {
                if (els.inspectCard) els.inspectCard.hidden = true;
                if (viewer && viewer.setSelectedObjects) viewer.setSelectedObjects([]);
            });
        }

        // Bottom Audit Drawer Toggle & Tabs
        if (els.toggleDrawer && els.auditDrawer) {
            els.toggleDrawer.addEventListener('click', function (e) {
                e.stopPropagation();
                toggleAuditDrawer();
            });
            var drawerHeader = document.querySelector('.audit-drawer-header');
            if (drawerHeader) {
                drawerHeader.addEventListener('click', function (e) {
                    if (e.target.closest('.audit-tab-btn')) return;
                    toggleAuditDrawer();
                });
            }
        }
        ['gates', 'findings', 'artifacts'].forEach(function (tab) {
            var btn = document.getElementById('drawer-tab-' + tab);
            var panel = document.getElementById('panel-' + tab);
            if (btn && panel) {
                btn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    if (els.auditDrawer && els.auditDrawer.classList.contains('minimized')) {
                        els.auditDrawer.classList.remove('minimized');
                        var icon = document.getElementById('drawer-toggle-icon');
                        if (icon) icon.setAttribute('data-lucide', 'chevron-down');
                        if (window.lucide) window.lucide.createIcons();
                    }
                    ['gates', 'findings', 'artifacts'].forEach(function (t) {
                        var b = document.getElementById('drawer-tab-' + t);
                        var p = document.getElementById('panel-' + t);
                        if (b) b.classList.toggle('active', t === tab);
                        if (p) p.style.display = t === tab ? (t === 'artifacts' || t === 'gates' ? 'grid' : 'block') : 'none';
                    });
                });
            }
        });
    }

    function bindToggle(id, layer) {
        var el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('change', function (event) {
            viewer.setLayerVisible(layer, event.target.checked);
        });
    }

    function openHelp(event) {
        viewer.setNavigationMode('orbit');
        state.helpTrigger = event && event.currentTarget ? event.currentTarget : els.openHelp;
        els.helpModal.hidden = false;
        els.helpModal.querySelector('.help-body').scrollTop = 0;
        els.closeHelp.focus();
    }

    function closeHelp() {
        els.helpModal.hidden = true;
        (state.helpTrigger || els.openHelp).focus();
    }

    function openCredits() {
        els.creditsModal.hidden = false;
        els.closeCredits.focus();
    }

    function closeCredits() {
        els.creditsModal.hidden = true;
        if (els.openCredits) els.openCredits.focus();
    }

    function readSavedTheme() {
        try {
            return localStorage.getItem('ifc-fds-theme') || 'light';
        } catch (error) {
            return 'light';
        }
    }

    function applyTheme(theme) {
        currentTheme = theme === 'dark' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', currentTheme);
        if (viewer) viewer.setTheme(currentTheme);
        if (!els.toggleTheme) return;

        var nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
        els.toggleTheme.title = 'Switch to ' + nextTheme + ' theme';
        els.toggleTheme.setAttribute('aria-label', els.toggleTheme.title);
        els.toggleTheme.innerHTML = '<i data-lucide="' + (currentTheme === 'dark' ? 'sun' : 'moon') + '"></i>';
        if (window.lucide) window.lucide.createIcons();
    }

    function updateWalkModeButton(mode) {
        var walking = mode === 'walk';
        els.toggleWalk.classList.toggle('active', walking);
        els.toggleWalk.setAttribute('aria-pressed', walking ? 'true' : 'false');
        els.toggleWalk.title = walking
            ? 'Exit walk mode'
            : 'Enter walk mode';
        els.toggleWalk.setAttribute('aria-label', walking ? 'Exit walk mode' : 'Enter walk mode');
    }

    function loadFdsText(text, sourceName, preparedModel) {
        var parsed = preparedModel ? null : ns.core.atStage('fds_parse', function () { return parser.parse(text); });
        var model = preparedModel || ns.core.atStage('scene_model', function () { return adapter.toSceneModel(parsed); });
        state.fdsModel = model;
        els.fdsSourceName.textContent = sourceName;
        ns.core.atStage('viewer', function () { viewer.loadFdsModel(model); });
        viewer.setFdsOpacity(Number(els.fdsOpacity.value));
        viewer.setExclusions(state.excludedStepIds, state.excludedItemIds);
        updateMetrics(model);
        renderDiagnostics();
        showSelection(null);
    }

    function clearFdsModel() {
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
        updateMetrics(model);
        renderDiagnostics();
        showSelection(null);
    }

    function readText(file) {
        return new Promise(function (resolve, reject) {
            var reader = new FileReader();
            reader.onload = function () { resolve(String(reader.result || '')); };
            reader.onerror = function () { reject(reader.error); };
            reader.readAsText(file);
        });
    }

    function updateMetrics(model) {
        els.countMeshes.textContent = model.meshes.length;
        els.countObsts.textContent = model.obsts.length;
        els.countVents.textContent = model.vents.length;
        els.countGeoms.textContent = model.geoms.length;
        els.countTriangles.textContent = model.triangleCount;
        els.countIfc.textContent = state.ifcModel && state.ifcModel.elements ? state.ifcModel.elements.length : 0;
        els.countIfcConvertible.textContent = countConvertibleIfc(state.ifcModel);
        renderIfcMapping(state.ifcModel);
    }

    function updateIfcMetrics(model) {
        els.countIfc.textContent = model && model.elements ? model.elements.length : 0;
        els.countIfcConvertible.textContent = countConvertibleIfc(model);
        renderIfcMapping(model);
    }

    function renderIfcMapping(model) {
        var rows = exporter.summarizeIfcMapping(model, currentExportOptions());
        els.ifcMapping.innerHTML = '';

        if (!rows.length) {
            els.ifcMapping.innerHTML = '<p class="empty-state">Open an IFC model to review its FDS mapping.</p>';
            return;
        }

        rows.forEach(function (row) {
            var item = document.createElement('div');
            var exported = row.exported ? row.exported + ' exported' : 'not exported';
            item.className = 'mapping-row';
            item.innerHTML = '<span class="mapping-type"></span><span class="mapping-status"><strong></strong><span></span></span>';
            item.querySelector('.mapping-type').textContent = row.ifcType.replace(/^IFC/, '');
            item.querySelector('strong').textContent = row.imported;
            item.querySelector('.mapping-status span').textContent = row.role + ' - ' + exported;
            els.ifcMapping.appendChild(item);
        });
    }

    function renderDiagnostics() {
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
                download.addEventListener('click', function () {
                    var url = URL.createObjectURL(new Blob([JSON.stringify(diag.ref, null, 2)], {type: 'application/json'}));
                    var link = document.createElement('a'); link.href = url; link.download = 'conversion-diagnostic.json';
                    link.click(); setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
                });
                item.appendChild(download);
            }
        });
    }

    function showSelection(data) {
        var selection = normalizeSelection(data);
        state.selection = selection;
        refreshConversionActions();
        if (!selection.length) {
            els.inspectCard.hidden = true;
            return;
        }
        els.inspectCard.hidden = false;
        if (selection.length === 1) {
            els.inspectTitle.textContent = selection[0].type + (selection[0].id ? ': ' + selection[0].id : '');
            renderStructuredInspector(selection[0]);
            els.inspectBody.textContent = JSON.stringify(selectionDetails(selection[0]), null, 2);
            return;
        }
        els.inspectTitle.textContent = 'Selected objects: ' + selection.length;
        renderStructuredInspector(null);
        els.inspectBody.textContent = JSON.stringify(selection.map(selectionDetails), null, 2);
    }

    function selectionDetails(data) {
        return {
            surf_id: data.surf_id,
            ifcType: data.ifcType,
            globalId: data.globalId,
            convertible: data.convertible,
            fdsRole: data.fdsRole,
            canExportAsSolid: data.canExportAsSolid,
            conversionNote: data.conversionNote,
            ifcSource: data.ifcSource,
            xb: data.xb,
            bounds: data.bounds,
            raw: data.raw
        };
    }

    function setExportEnabled(enabled) {
        state.exportEnabled = !!enabled;
        refreshConversionActions();
    }

    function refreshConversionActions() {
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

    function pushUndo(entry) {
        state.undoStack.push(entry);
        refreshConversionActions();
    }

    function undoLastChange() {
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

    function setExportBusy(busy, action) {
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

    function exportIfc(action) {
        if (state.exportBusy) return;
        if (!state.ifcModel || !state.ifcModel.elements || !state.ifcModel.elements.length) return;
        var generation = state.exportRequestId;
        ensureFullModel().then(function (fullModel) {
            if (generation !== state.exportRequestId) return;
            runExportWithModel(fullModel, action);
        }).catch(function (err) {
            if (generation !== state.exportRequestId) return;
            addExportDiagnostic(err, {stage: 'ifc_parse'});
        });
    }

    // The meta model is enough for browse/select/preview, but FDS export needs the full
    // ifc-adapter parse (placements, void carving, classifications). We do it on demand
    // the first time the user clicks Convert, and cache the result for repeated exports.
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
        if (state.exportWorker) state.exportWorker.terminate();
        if (state.exportWorkerUrl) URL.revokeObjectURL(state.exportWorkerUrl);
        state.exportWorker = null;
        state.exportWorkerUrl = null;
    }

    function cancelPendingExport() {
        state.exportRequestId += 1;
        if (ns.verified.cancel) ns.verified.cancel().catch(function () {});
        cleanupExportWorker();
        setExportBusy(false);
    }

    function clearGeneratedFds() {
        state.verifiedJobId = null;
        state.generatedFdsText = null;
        state.generatedFdsName = null;
        if (viewer.cancelVerifiedLoad) viewer.cancelVerifiedLoad();
        state.lastArtifactLinks = null;
        state.lastAuditReport = null;
        state.lastManifest = null;
        if (els.saveFds) els.saveFds.disabled = true;
        if (els.openAudit) els.openAudit.disabled = true;
        if (els.saveManifest) els.saveManifest.disabled = true;
    }

    function exportVerified() {
        if (state.exportBusy) return;
        if (!state.ifcSourceText && !state.currentIfcFile && !ns.verified.hasFiles()) {
            addExportDiagnostic('IFC source not in memory — please reopen the file.');
            return;
        }

        var fileLabel = (state.ifcFileName || (state.ifcModel && state.ifcModel.fileName) || 'IFC model');
        showLoading('Verified Conversion: ' + fileLabel, 'Processing with IfcOpenShell & OpenCASCADE...');
        setExportBusy(true, 'convert-verified');
        var generation = ++state.exportRequestId;

        var blob = state.currentIfcFile || new File([state.ifcSourceText || ''], state.ifcFileName || 'model.ifc');
        var forceGeom = !!(els.verifiedForceGeom && els.verifiedForceGeom.checked);
        var cellSize = Number(els.verifiedCellSize && els.verifiedCellSize.value) || Number(els.meshCellSize && els.meshCellSize.value) || 0.20;
        ns.verified.run(blob, {
            cell_size: cellSize,
            all_geom: forceGeom,
        })
        .then(async function (data) {
            if (generation !== state.exportRequestId) return;
            state.verifiedJobId = data && data.job_id;
            hideLoading(); setExportBusy(false);
            if (!data || !data.artifacts) throw new Error('Missing conversion artifacts');
            state.lastArtifactLinks = data.artifacts;
            var summary = Object.assign({}, data, {configuration: {}, matched_count: (data.coverage || {}).matched || 0});
            state.lastAuditReport = summary;
            state.lastManifest = null;
            if (els.openAudit) els.openAudit.disabled = false;
            if (els.saveManifest) els.saveManifest.disabled = false;
            if (viewer.bindVerifiedArtifacts) viewer.bindVerifiedArtifacts(data.artifacts);
            renderAuditReport(summary); openAudit();
            var response = await fetch(data.artifacts.fds.url);
            if (!response.ok) throw new Error('FDS artifact unavailable');
            var text = await response.text();
            if (generation !== state.exportRequestId) return;
            var base = (data.source_filename || state.ifcFileName || 'model').replace(/\.[^.]+$/, '');
            var fileName = base + (data.status === 'MAPPING_VERIFIED' ? '_mapping_verified.fds' : '_diagnostic_unaccepted.fds');
            state.generatedFdsText = text; state.generatedFdsName = fileName;
            if (els.saveFds) els.saveFds.disabled = false;
            loadFdsText(text, fileName);
            setupClippingForBounds(boundsForClipping());
        })
        .catch(function (err) {
            if (generation !== state.exportRequestId || err.name === 'AbortError') return;
            hideLoading();
            setExportBusy(false);
            addExportDiagnostic(err, {stage: 'verified_conversion', jobId: state.verifiedJobId});
            updateGlobalStatusBadge('FAILED');
            if (state.verifiedJobId) exposeFailedCheckpoints(state.verifiedJobId);
        }).finally(function () {
            if (generation === state.exportRequestId) { hideLoading(); setExportBusy(false); }
        });
    }

    function renderAuditReport(report) {
        if (!report) return;
        updateGlobalStatusBadge(report.status);
        if (!els.auditBody) return;
        if (!report) {
            els.auditBody.innerHTML = '<p>No audit report available. Run <strong>Verified Conversion</strong> to generate a complete 3-tier audit.</p>';
            return;
        }
        els.auditBody.replaceChildren();
        function line(tag, text, parent) {
            var node = document.createElement(tag);
            node.textContent = text;
            (parent || els.auditBody).appendChild(node);
            return node;
        }
        line('h3', 'Acceptance: ' + report.status);
        line('p', 'Mapping: ' + report.mapping_status + '; simulation: ' + report.simulation_status);
        var roles = (report.coverage || {}).representation || {};
        line('p', 'Reference objects: ' + (roles.REFERENCE_GEOMETRY || 0) + '; passive obstacles: ' + (roles.PASSIVE_OBSTACLE || 0) + '; operational objects: ' + (roles.OPERATIONAL_MEP || 0));
        var pending = (report.coverage || {}).boundary_pending || 0;
        line('p', 'Pending boundary treatment: ' + (Array.isArray(pending) ? pending.length : pending));
        if (report.research) line('p', 'Research acceptance: ' + report.research.research_acceptance + '; reference parity: ' + report.research.parity_status);
        var domain = (report.configuration || {}).simulation_domain;
        if (domain) line('p', 'Fixed domain (m): X ' + domain.xmin + ' to ' + domain.xmax + '; Y ' + domain.ymin + ' to ' + domain.ymax + '; Z ' + domain.zmin + ' to ' + domain.zmax);
        if (report.total_elements_checked !== undefined) line('p', 'Matched solids: ' + report.matched_count + ' / accounted entities: ' + report.total_elements_checked);
        var scope = (report.configuration || {}).scope || {};
        var storeys = (((report.coverage || {}).scope || {}).selected_storeys || []);
        if (!Array.isArray(storeys)) storeys = [String(storeys) + ' selected (see configuration artifact)'];
        line('p', 'Export storeys: ' + (storeys.length ? storeys.join(', ') : 'All storeys'));
        if (scope.bounding_box) line('p', 'Export volume (m): ' + ['xmin','xmax','ymin','ymax','zmin','zmax'].map(function (key) { return key + ': ' + scope.bounding_box[key]; }).join(', '));
        line('p', 'Retained crossing elements: ' + (((report.coverage || {}).scope || {}).BOUNDARY_RETAINED || 0));
        var list = line('ul', '');
        Object.keys(report.gates || {}).forEach(function (name) {
            var gate = report.gates[name];
            line('li', name + ': ' + gate.status + (gate.reason ? ' — ' + gate.reason : ''), list);
        });
        (report.findings || []).forEach(function (f) { line('p', f.severity + ' — ' + f.element_id + ': ' + f.detail); });
        renderAuditDrawer(report);
    }

    function openAudit() {
        if (!els.auditModal) return;
        renderAuditReport(state.lastAuditReport);
        els.auditModal.hidden = false;
    }

    function closeAudit() {
        if (!els.auditModal) return;
        els.auditModal.hidden = true;
    }

    function checkBackendHealth() {
        var apiUrl = (window.location.protocol === 'http:' || window.location.protocol === 'https:')
            ? '/api/health'
            : 'http://127.0.0.1:8000/api/health';

        fetch(apiUrl, { method: 'GET' })
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

    function downloadText(fileName, text) {
        var blob = new Blob([text], { type: 'text/plain' });
        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }

    function countConvertibleIfc(model) {
        return exporter.getExportableElements(model, currentExportOptions()).length;
    }

    function currentExportOptions() {
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

    function normalizeSelection(data) {
        if (!data) return [];
        return Array.isArray(data) ? data : [data];
    }

    function selectedGeneratedGeomStepIds(data) {
        return normalizeSelection(data).map(function (item) {
            if (!item || String(item.type || '').indexOf('GEOM') !== 0 || !item.ifcSource) return null;
            return String(item.ifcSource.stepId || '').replace(/^#/, '') || null;
        }).filter(Boolean);
    }

    function selectedIfcStepIds(data) {
        return normalizeSelection(data).map(function (item) {
            if (!item || item.type !== 'IFC') return null;
            var raw = item.raw || {};
            var id = raw.id || raw.stepId || raw.STEP_ID || (raw.__ifcSource && raw.__ifcSource.stepId);
            return id ? String(id).replace(/^#/, '') : null;
        }).filter(Boolean);
    }

    // Splits the current selection into source-level deletions (IFC meshes — cascade through
    // all their derived OBST/GEOM) and primitive-level deletions (OBST/GEOM meshes — remove
    // just that one instance, leaving sibling primitives from the same source untouched).
    function splitSelectionForDelete(data) {
        var stepIds = [];
        var itemIds = [];
        normalizeSelection(data).forEach(function (item) {
            if (!item) return;
            if (item.type === 'IFC') {
                var raw = item.raw || {};
                var sid = raw.id || raw.stepId || raw.STEP_ID;
                if (sid) stepIds.push(String(sid).replace(/^#/, ''));
                return;
            }
            // OBST / GEOM primitive — exclude this specific itemId only.
            var primitiveId = item.id || (item.raw && item.raw.ID) || (item.ifcSource && item.ifcSource.itemId);
            if (primitiveId) itemIds.push(String(primitiveId));
        });
        return { stepIds: stepIds, itemIds: itemIds };
    }

    var activeInspectorTab = 'id';
    function renderStructuredInspector(item) {
        var view = document.getElementById('inspect-structured-view');
        if (!view) return;
        view.innerHTML = '';
        if (!item) {
            view.innerHTML = '<p style="color:var(--text-muted);font-size:11px">Multi-object selection active.</p>';
            return;
        }
        var raw = item.raw || {};
        var rows = [];
        if (activeInspectorTab === 'id') {
            rows = [
                ['IFC Type', item.ifcType || item.type || '--'],
                ['GlobalId', item.globalId || raw.global_id || '--'],
                ['STEP ID', item.id || raw.step_id || '--'],
                ['Source File', item.ifcSource ? item.ifcSource.fileName : (raw.source_id || '--')],
                ['Building', raw.building_id || '--'],
                ['Storey', raw.storey || '--']
            ];
        } else if (activeInspectorTab === 'map') {
            rows = [
                ['Simulation Role', raw.simulation_role || item.fdsRole || '--'],
                ['Mapping Strategy', raw.mapping_strategy || (item.canExportAsSolid ? 'OBST/GEOM' : 'NONE')],
                ['FDS Representation', raw.fds_representation || item.type || '--'],
                ['Review Status', raw.review_status || 'NOT_REQUIRED'],
                ['Boundary Treatment', raw.boundary_treatment || 'NOT_APPLICABLE']
            ];
        } else if (activeInspectorTab === 'geom') {
            var b = item.bounds || raw.bounding_box || {};
            var dx = (b.xmax !== undefined && b.xmin !== undefined) ? Math.abs(b.xmax - b.xmin).toFixed(3) : '--';
            var dy = (b.ymax !== undefined && b.ymin !== undefined) ? Math.abs(b.ymax - b.ymin).toFixed(3) : '--';
            var dz = (b.zmax !== undefined && b.zmin !== undefined) ? Math.abs(b.zmax - b.zmin).toFixed(3) : '--';
            rows = [
                ['Extents dx×dy×dz', dx + ' × ' + dy + ' × ' + dz + ' m'],
                ['FDS Primitive IDs', (raw.fds_primitive_ids || []).join(', ') || '--'],
                ['Surface Area', raw.surface_area_m2 ? raw.surface_area_m2.toFixed(3) + ' m²' : '--'],
                ['Volume', raw.volume_m3 ? raw.volume_m3.toFixed(3) + ' m³' : '--']
            ];
        } else if (activeInspectorTab === 'mep') {
            rows = [
                ['MEP Category', raw.mep_category || 'NOT_APPLICABLE'],
                ['System Names', (raw.system_names || []).join(', ') || '--'],
                ['System IDs', (raw.system_ids || []).join(', ') || '--'],
                ['Ports Count', raw.ports ? raw.ports.length : (item.ports_count || 0)],
                ['Operational Status', raw.operational_status || 'NOT_APPLICABLE']
            ];
        }
        rows.forEach(function (pair) {
            var row = document.createElement('div');
            row.className = 'property-row';
            var keySpan = document.createElement('span');
            keySpan.className = 'property-key';
            keySpan.textContent = String(pair[0]);
            var valSpan = document.createElement('span');
            valSpan.className = 'property-val';
            valSpan.title = String(pair[1]);
            valSpan.textContent = String(pair[1]);
            row.appendChild(keySpan);
            row.appendChild(valSpan);
            view.appendChild(row);
        });
    }

    function updateSourcePill(file, model) {
        var nameEl = document.getElementById('ifc-source-name');
        if (nameEl) nameEl.textContent = file ? file.name : ((model && model.fileName) || 'Loaded model');
        var sizeEl = document.getElementById('ifc-size-tag');
        if (sizeEl) sizeEl.textContent = file ? (file.size / (1024 * 1024)).toFixed(1) + ' MB' : '-- MB';
        var schemaEl = document.getElementById('ifc-schema-tag');
        if (schemaEl) schemaEl.textContent = (model && model.schema) || 'IFC';

        var b = model && (model.convertibleBounds || model.bounds);
        if (b) {
            ['xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'].forEach(function (axis) {
                var domainInput = document.getElementById('verified-domain-' + axis);
                if (domainInput && b[axis] !== undefined) {
                    domainInput.value = Number(b[axis]).toFixed(2);
                }
            });
            updateDomainEstimates();
        }
    }

    function setWorkflowMode(mode) {
        var isVerified = mode === 'verified';
        if (els.modeTabVerified) els.modeTabVerified.classList.toggle('active', isVerified);
        if (els.modeTabQuick) els.modeTabQuick.classList.toggle('active', !isVerified);
        var target = isVerified ? els.containerVerified : els.containerQuick;
        if (target && target.scrollIntoView) {
            target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    function updateDomainEstimates() {
        var xminInput = document.getElementById('verified-domain-xmin');
        var xmaxInput = document.getElementById('verified-domain-xmax');
        var yminInput = document.getElementById('verified-domain-ymin');
        var ymaxInput = document.getElementById('verified-domain-ymax');
        var zminInput = document.getElementById('verified-domain-zmin');
        var zmaxInput = document.getElementById('verified-domain-zmax');
        var cellInput = document.getElementById('verified-cell-size') || els.meshCellSize;

        var xmin = Number(xminInput ? xminInput.value : 0) || 0;
        var xmax = Number(xmaxInput ? xmaxInput.value : 10) || 10;
        var ymin = Number(yminInput ? yminInput.value : 0) || 0;
        var ymax = Number(ymaxInput ? ymaxInput.value : 10) || 10;
        var zmin = Number(zminInput ? zminInput.value : 0) || 0;
        var zmax = Number(zmaxInput ? zmaxInput.value : 3) || 3;
        var cellSize = Math.max(0.01, Number(cellInput ? cellInput.value : 0.20) || 0.20);

        var dx = Math.max(0.01, Math.abs(xmax - xmin));
        var dy = Math.max(0.01, Math.abs(ymax - ymin));
        var dz = Math.max(0.01, Math.abs(zmax - zmin));

        var cellsX = Math.ceil(dx / cellSize);
        var cellsY = Math.ceil(dy / cellSize);
        var cellsZ = Math.ceil(dz / cellSize);
        var totalCells = cellsX * cellsY * cellsZ;

        if (els.domainDimensionsText) {
            els.domainDimensionsText.textContent = dx.toFixed(1) + ' × ' + dy.toFixed(1) + ' × ' + dz.toFixed(1) + ' m';
        }
        if (els.domainEstCells) {
            els.domainEstCells.textContent = totalCells.toLocaleString() + ' cells';
        }
        if (els.domainEstBudget) {
            if (totalCells <= 10000000) {
                els.domainEstBudget.className = 'domain-budget-chip reasonable';
                els.domainEstBudget.textContent = '● OK';
            } else if (totalCells <= 50000000) {
                els.domainEstBudget.className = 'domain-budget-chip heavy';
                els.domainEstBudget.textContent = '▲ Heavy';
            } else {
                els.domainEstBudget.className = 'domain-budget-chip heavy';
                els.domainEstBudget.textContent = '⚠️ Critical (>50M)';
            }
        }
    }

    function checkScopedDomainPreflight() {
        if (!els.verifiedStoreys || !els.verifiedUseDomain || !els.verifiedDomainWarning) return;
        var hasSelectedStoreys = Array.prototype.some.call(els.verifiedStoreys.options, function (o) { return o.selected; });
        var hasDomain = els.verifiedUseDomain.checked;
        els.verifiedDomainWarning.style.display = (hasSelectedStoreys && !hasDomain) ? 'flex' : 'none';
    }

    function toggleAuditDrawer() {
        if (!els.auditDrawer) return;
        var isMin = els.auditDrawer.classList.toggle('minimized');
        var icon = document.getElementById('drawer-toggle-icon');
        if (icon) {
            icon.setAttribute('data-lucide', isMin ? 'chevron-up' : 'chevron-down');
            if (window.lucide) window.lucide.createIcons();
        }
    }

    function updateGlobalStatusBadge(status) {
        var badge = document.getElementById('global-run-status');
        var label = document.getElementById('global-status-label');
        if (!badge || !label) return;
        badge.className = 'global-status-badge';
        if (status === 'MAPPING_VERIFIED' || status === 'SIMULATION_VERIFIED') {
            badge.classList.add('verified');
            label.textContent = 'VERIFIED';
        } else if (status === 'INCONCLUSIVE') {
            badge.classList.add('inconclusive');
            label.textContent = 'INCONCLUSIVE';
        } else if (status === 'REJECTED' || status === 'FAILED') {
            badge.classList.add('rejected');
            label.textContent = status;
        } else {
            label.textContent = status || 'NOT RUN';
        }
    }

    function updateColorModeLegend(mode) {
        var container = document.getElementById('legend-swatches');
        if (!container) return;
        if (mode === 'mapping') {
            container.innerHTML = '<div class="legend-swatch-item"><span class="swatch-color" style="background:#3b82f6"></span><span>OBST</span></div>' +
                '<div class="legend-swatch-item"><span class="swatch-color" style="background:#f59e0b"></span><span>GEOM</span></div>' +
                '<div class="legend-swatch-item"><span class="swatch-color" style="background:#64748b"></span><span>Reference</span></div>' +
                '<div class="legend-swatch-item"><span class="swatch-color" style="background:#ef4444"></span><span>Unsupported</span></div>';
        } else if (mode === 'verification') {
            container.innerHTML = '<div class="legend-swatch-item"><span class="swatch-color" style="background:#10b981"></span><span>PASS</span></div>' +
                '<div class="legend-swatch-item"><span class="swatch-color" style="background:#f59e0b"></span><span>INCONCLUSIVE</span></div>' +
                '<div class="legend-swatch-item"><span class="swatch-color" style="background:#ef4444"></span><span>FAIL / REJECT</span></div>' +
                '<div class="legend-swatch-item"><span class="swatch-color" style="background:#64748b"></span><span>NOT RUN</span></div>';
        } else if (mode === 'ifc-type') {
            container.innerHTML = '<div class="legend-swatch-item"><span class="swatch-color" style="background:#60a5fa"></span><span>Wall / Column</span></div>' +
                '<div class="legend-swatch-item"><span class="swatch-color" style="background:#a78bfa"></span><span>Slab / Roof</span></div>' +
                '<div class="legend-swatch-item"><span class="swatch-color" style="background:#34d399"></span><span>Door / Window</span></div>' +
                '<div class="legend-swatch-item"><span class="swatch-color" style="background:#f472b6"></span><span>MEP / Flow</span></div>';
        } else if (mode === 'mep') {
            container.innerHTML = '<div class="legend-swatch-item"><span class="swatch-color" style="background:#ef4444"></span><span>Fire Suppression</span></div>' +
                '<div class="legend-swatch-item"><span class="swatch-color" style="background:#f97316"></span><span>Smoke Extract</span></div>' +
                '<div class="legend-swatch-item"><span class="swatch-color" style="background:#06b6d4"></span><span>Ventilation</span></div>' +
                '<div class="legend-swatch-item"><span class="swatch-color" style="background:#3b82f6"></span><span>Plumbing</span></div>';
        }
    }

    function renderAuditDrawer(report) {
        if (!report) return;
        var verdictText = document.getElementById('drawer-verdict-summary');
        if (verdictText) verdictText.textContent = report.status || 'INCONCLUSIVE';

        var gatesContainer = document.getElementById('panel-gates');
        if (gatesContainer && report.gates) {
            Object.keys(report.gates).forEach(function (gateName) {
                var card = gatesContainer.querySelector('[data-gate="' + gateName + '"]');
                if (!card && gateName === 'golden_reference_parity') {
                    card = gatesContainer.querySelector('[data-gate="golden"]');
                }
                if (!card && gateName === 'golden') {
                    card = gatesContainer.querySelector('[data-gate="golden_reference_parity"]');
                }
                if (card) {
                    var gate = report.gates[gateName];
                    var dot = card.querySelector('.status-dot');
                    var reason = card.querySelector('.gate-card-reason');
                    if (dot) {
                        dot.className = 'status-dot ' + (gate.status === 'PASS' ? 'online' : (gate.status === 'FAIL' ? 'offline' : ''));
                        if (gate.status === 'FAIL') dot.style.background = 'var(--status-error)';
                    }
                    if (reason && gate.reason) {
                        reason.textContent = gate.status + ': ' + gate.reason;
                    }
                }
            });
        }

        var findings = report.findings || [];
        var findingCountBadge = document.getElementById('drawer-finding-count');
        if (findingCountBadge) findingCountBadge.textContent = findings.length;

        var findingsTbody = document.getElementById('findings-table-body');
        if (findingsTbody) {
            findingsTbody.innerHTML = '';
            if (!findings.length) {
                findingsTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:24px">No active findings. All evaluated gates satisfied.</td></tr>';
            } else {
                findings.forEach(function (f) {
                    var tr = document.createElement('tr');
                    var isErr = f.severity === 'P0' || f.severity === 'ERROR' || f.severity === 'P1';
                    var sevColor = isErr ? 'var(--status-error-text)' : 'var(--status-warning-text)';

                    var tdSev = document.createElement('td');
                    var badge = document.createElement('span');
                    badge.className = 'brand-badge';
                    badge.style.color = sevColor;
                    badge.textContent = f.severity || 'WARN';
                    tdSev.appendChild(badge);
                    tr.appendChild(tdSev);

                    var tdCat = document.createElement('td');
                    var catTag = document.createElement('span');
                    catTag.className = 'source-meta-tag';
                    catTag.textContent = f.category || 'general';
                    tdCat.appendChild(catTag);
                    tr.appendChild(tdCat);

                    var tdKey = document.createElement('td');
                    tdKey.style.fontFamily = 'var(--font-mono)';
                    tdKey.style.color = 'var(--text-primary)';
                    tdKey.textContent = f.element_id || '—';
                    tr.appendChild(tdKey);

                    var tdDesc = document.createElement('td');
                    tdDesc.style.color = 'var(--text-secondary)';
                    tdDesc.textContent = f.detail || f.title || '';
                    tr.appendChild(tdDesc);

                    var tdAct = document.createElement('td');
                    tdAct.style.textAlign = 'right';
                    if (f.element_id) {
                        var btn = document.createElement('button');
                        btn.className = 'btn';
                        btn.style.height = '22px';
                        btn.style.padding = '0 6px';
                        btn.style.fontSize = '10px';
                        btn.textContent = 'Locate';
                        btn.addEventListener('click', function () {
                            if (viewer && viewer.selectElementByKey) viewer.selectElementByKey(f.element_id);
                        });
                        tdAct.appendChild(btn);
                    }
                    tr.appendChild(tdAct);
                    findingsTbody.appendChild(tr);
                });
            }
        }

        if (report.artifacts) {
            var fdsBtn = document.getElementById('btn-download-fds');
            if (fdsBtn && report.artifacts.fds) fdsBtn.href = report.artifacts.fds.url;
            var manifestBtn = document.getElementById('btn-download-manifest');
            if (manifestBtn && report.artifacts.manifest) manifestBtn.href = report.artifacts.manifest.url;
            var geomBtn = document.getElementById('btn-download-geom-pkg');
            if (geomBtn && report.artifacts.geometry) geomBtn.href = report.artifacts.geometry.url;
        }
    }

    function exposeFailedCheckpoints(jobId) {
        if (!jobId) return;
        var fdsBtn = document.getElementById('btn-download-fds');
        if (fdsBtn) {
            fdsBtn.href = '/api/jobs/' + jobId + '/checkpoints/fds';
            fdsBtn.textContent = 'Download Checkpoint FDS (UNACCEPTED)';
        }
        var manifestBtn = document.getElementById('btn-download-manifest');
        if (manifestBtn) {
            manifestBtn.href = '/api/jobs/' + jobId + '/checkpoints/manifest';
            manifestBtn.textContent = 'Download Checkpoint Manifest (UNACCEPTED)';
        }
        var geomBtn = document.getElementById('btn-download-geom-pkg');
        if (geomBtn) {
            geomBtn.href = '/api/jobs/' + jobId + '/checkpoints/geometry';
            geomBtn.textContent = 'Download Checkpoint Geometries (AUDIT INCOMPLETE)';
        }
        var panelArtifacts = document.getElementById('panel-artifacts');
        if (panelArtifacts) {
            panelArtifacts.style.display = 'grid';
            var tabs = document.querySelectorAll('.audit-tab-btn');
            tabs.forEach(function (t) { t.classList.remove('active'); });
            var artTab = document.getElementById('drawer-tab-artifacts');
            if (artTab) artTab.classList.add('active');
            var panelGates = document.getElementById('panel-gates');
            if (panelGates) panelGates.style.display = 'none';
        }
    }

})(window.IfcFds);
