/**
 * Structured Entity Inspector Panel for IFCtoFDS Research Workbench.
 * Renders categorized entity properties (Identity, Mapping, Geometry, MEP)
 * with hardened DOM element creation to eliminate XSS/injection risks.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.ui = root.IfcFds.ui || {};

    var activeInspectorTab = 'id';
    var currentItem = null;

    function renderStructuredInspector(item) {
        currentItem = item;
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

    function init(els) {
        var inspectorTabs = document.querySelectorAll('.inspector-tab-btn');
        inspectorTabs.forEach(function (btn) {
            btn.addEventListener('click', function () {
                inspectorTabs.forEach(function (b) { b.classList.remove('active'); });
                btn.classList.add('active');
                activeInspectorTab = btn.getAttribute('data-tab');
                renderStructuredInspector(currentItem);
            });
        });

        var closeBtn = (els && els.closeInspector) || document.getElementById('close-inspector');
        if (closeBtn) {
            closeBtn.addEventListener('click', function () {
                var card = (els && els.inspectCard) || document.getElementById('inspect-card');
                if (card) card.style.display = 'none';
            });
        }
    }

    root.IfcFds.ui.inspectorPanel = {
        init: init,
        renderStructuredInspector: renderStructuredInspector,
        setActiveTab: function (tab) {
            activeInspectorTab = tab;
            renderStructuredInspector(currentItem);
        }
    };
})(window);
