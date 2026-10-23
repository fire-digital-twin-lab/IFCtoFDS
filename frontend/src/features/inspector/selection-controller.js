(function (ns) {
    ns.app = ns.app || {};
    ns.features = ns.features || {};
    ns.features.inspector = ns.features.inspector || {};
    ns.features.inspector.createSelectionController = function (dependencies) {
    var life = ns.core.createLifecycle();

    var state = dependencies.state;
    function refreshConversionActions() { return dependencies.refreshConversionActions.apply(null, arguments); }
    function showSelection(data) {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        var selection = normalizeSelection(data);
        state.selection = selection;
        refreshConversionActions();
        if (ns.workbench && ns.workbench.state && ns.workbench.state.selectionStore) {
            ns.workbench.state.selectionStore.setSelection(selection, 'viewer');
        } else {
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
    }

    function selectionDetails(data) {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
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

    function normalizeSelection(data) {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        if (!data) return [];
        return Array.isArray(data) ? data : [data];
    }

    function selectedGeneratedGeomStepIds(data) {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        return normalizeSelection(data).map(function (item) {
            if (!item || String(item.type || '').indexOf('GEOM') !== 0 || !item.ifcSource) return null;
            return String(item.ifcSource.stepId || '').replace(/^#/, '') || null;
        }).filter(Boolean);
    }

    function selectedIfcStepIds(data) {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        return normalizeSelection(data).map(function (item) {
            if (!item || item.type !== 'IFC') return null;
            var raw = item.raw || {};
            var id = raw.id || raw.stepId || raw.STEP_ID || (raw.__ifcSource && raw.__ifcSource.stepId);
            return id ? String(id).replace(/^#/, '') : null;
        }).filter(Boolean);
    }

    function splitSelectionForDelete(data) {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
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

    function renderStructuredInspector(item) {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        if (ns.ui && ns.ui.inspectorPanel) {
            ns.ui.inspectorPanel.renderStructuredInspector(item);
        }
    }
    return {showSelection: showSelection, selectionDetails: selectionDetails, normalizeSelection: normalizeSelection, selectedGeneratedGeomStepIds: selectedGeneratedGeomStepIds, selectedIfcStepIds: selectedIfcStepIds, splitSelectionForDelete: splitSelectionForDelete, renderStructuredInspector: renderStructuredInspector, destroy: function () { life.destroy(); }};
    };
})(window.IfcFds);
