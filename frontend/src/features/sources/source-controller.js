(function (ns) {
    ns.features = ns.features || {};
    ns.features.sources = ns.features.sources || {};
    ns.features.sources.createSourceController = function (dependencies) {
        function hideLoading() { return dependencies.hideLoading.apply(null, arguments); }
        function setLoadingProgress() { return dependencies.setLoadingProgress.apply(null, arguments); }
        function setSaveProcessedEnabled() { return dependencies.setSaveProcessedEnabled.apply(null, arguments); }
        var state = dependencies.state;
        var exporter = dependencies.exporter;
        function countConvertibleIfc() { return dependencies.countConvertibleIfc.apply(null, arguments); }
        function currentExportOptions() { return dependencies.currentExportOptions.apply(null, arguments); }
        function renderDiagnostics() { return dependencies.renderDiagnostics.apply(null, arguments); }
        function setExportEnabled() { return dependencies.setExportEnabled.apply(null, arguments); }
        function setupClippingForBounds() { return dependencies.setupClippingForBounds.apply(null, arguments); }
        function updateDomainEstimates() { return dependencies.updateDomainEstimates.apply(null, arguments); }

        function finishIfcLoad(model, displayMeshes, oversizeNotice) {
            var els = dependencies.getElements(); var viewer = dependencies.getViewer();
            state.ifcModel = model;
            state.lastDisplayMeshes = displayMeshes || null;
            if (oversizeNotice && model && model.diagnostics) model.diagnostics.unshift(oversizeNotice);
            setLoadingProgress(1, 'Rendering…');
            if (ns.workbench && ns.workbench.state && ns.workbench.state.selectionStore) {
                if (model && model.elements) {
                    ns.workbench.state.selectionStore.indexElements(
                        model.elements,
                        state.currentIfcFile ? state.currentIfcFile.name : 'ifc'
                    );
                }
            }
            viewer.sourceId = state.currentIfcFile ? state.currentIfcFile.name : 'ifc';
            if (!model.backendPreview) viewer.loadIfcModel(model, displayMeshes);
            else ns.verified.usePreviewInventory(model.inventorySummary, state.currentIfcFile);
            viewer.setIfcOpacity(Number(els.ifcOpacity.value));
            updateIfcMetrics(model);
            updateSourcePill(state.currentIfcFile, model);
            setExportEnabled(countConvertibleIfc(model) > 0);
            setSaveProcessedEnabled(!!(model && !model.backendPreview && model.elements && model.elements.length));
            setupClippingForBounds(boundsForClipping());
            if (ns.workbench && ns.workbench.navigation) {
                if (ns.workbench.navigation.sectionBox) {
                    ns.workbench.navigation.sectionBox.setNativeExtents(boundsForClipping());
                }
                if (ns.workbench.navigation.modelTree) {
                    ns.workbench.navigation.modelTree.render();
                }
                var clipStoreySelect = document.getElementById('clip-storey-select');
                if (clipStoreySelect && model && model.storeys) {
                    clipStoreySelect.innerHTML = '<option value="" selected>Full Height</option>';
                    model.storeys.forEach(function (st) {
                        var opt = document.createElement('option');
                        var name = typeof st === 'string' ? st : (st.name || st.storey_id || 'Storey');
                        opt.value = name;
                        opt.textContent = name;
                        clipStoreySelect.appendChild(opt);
                    });
                }
            }
            renderDiagnostics();
            hideLoading();
        }

        function boundsForClipping() {
            var viewer = dependencies.getViewer();
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

        function readText(file) {
            return new Promise(function (resolve, reject) {
                var reader = new FileReader();
                reader.onload = function () { resolve(String(reader.result || '')); };
                reader.onerror = function () { reject(reader.error); };
                reader.readAsText(file);
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

        function updateIfcMetrics(model) {
            var els = dependencies.getElements();
            els.countIfc.textContent = model && model.elements ? model.elements.length : 0;
            els.countIfcConvertible.textContent = countConvertibleIfc(model);
            renderIfcMapping(model);
        }

        function renderIfcMapping(model) {
            var els = dependencies.getElements();
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

        return {
            finishIfcLoad: finishIfcLoad,
            boundsForClipping: boundsForClipping,
            failIfcLoad: failIfcLoad,
            readText: readText,
            updateSourcePill: updateSourcePill,
            updateIfcMetrics: updateIfcMetrics,
            renderIfcMapping: renderIfcMapping
        };
    };
})(window.IfcFds);
