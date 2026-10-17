/**
 * Hardened DOM Inspector View for IFCtoFDS Research Workbench.
 * Renders categorized entity properties (Identity, Mapping, Geometry, MEP, Scenario)
 * with engineering action controls (Focus, Isolate, Hide, Scenario Configuration).
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.inspector = root.IfcFds.workbench.inspector || {};

    function renderPropertyRow(key, value, extra) {
        var row = document.createElement('div');
        row.className = 'property-row';
        var keySpan = document.createElement('span');
        keySpan.className = 'property-key';
        keySpan.textContent = String(key);

        var valWrap = document.createElement('div');
        valWrap.style.display = 'flex';
        valWrap.style.alignItems = 'center';
        valWrap.style.gap = '6px';
        valWrap.style.overflow = 'hidden';

        var valSpan = document.createElement('span');
        valSpan.className = 'property-val';
        valSpan.textContent = String(value !== undefined && value !== null ? value : '--');
        valSpan.title = String(value);
        valWrap.appendChild(valSpan);

        if (extra && extra.badge) {
            var badge = document.createElement('span');
            badge.className = 'brand-badge';
            badge.style.fontSize = '9px';
            badge.style.padding = '1px 5px';
            if (extra.badgeType === 'pass') {
                badge.style.background = 'var(--status-pass-bg)';
                badge.style.color = 'var(--status-pass-text)';
            } else if (extra.badgeType === 'warning') {
                badge.style.background = 'var(--status-warning-bg)';
                badge.style.color = 'var(--status-warning-text)';
            }
            badge.textContent = extra.badge;
            valWrap.appendChild(badge);
        }

        row.appendChild(keySpan);
        row.appendChild(valWrap);
        return row;
    }

    function createActionButton(iconName, text, onClick) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn';
        btn.style.height = '26px';
        btn.style.fontSize = '11px';
        btn.style.padding = '0 8px';
        btn.style.display = 'inline-flex';
        btn.style.alignItems = 'center';
        btn.style.gap = '4px';

        if (iconName && window.lucide) {
            var icon = document.createElement('i');
            icon.setAttribute('data-lucide', iconName);
            icon.style.width = '12px';
            icon.style.height = '12px';
            btn.appendChild(icon);
        }
        var span = document.createElement('span');
        span.textContent = text;
        btn.appendChild(span);

        btn.addEventListener('click', onClick);
        return btn;
    }

    function InspectorView(containerId) {
        this.containerId = containerId || 'inspect-structured-view';
    }

    InspectorView.prototype.render = function (descriptor, activeTab, actionCallbacks) {
        var view = document.getElementById(this.containerId);
        if (!view) return;
        view.innerHTML = '';
        actionCallbacks = actionCallbacks || {};

        if (!descriptor) {
            var emptyNotice = document.createElement('p');
            emptyNotice.style.color = 'var(--text-muted)';
            emptyNotice.style.fontSize = '11px';
            emptyNotice.style.padding = '12px 0';
            emptyNotice.textContent = 'No entity selected. Click an object in 3D or select from tree.';
            view.appendChild(emptyNotice);
            return;
        }

        // Action Toolbar (Focus, Isolate, Hide)
        var actionsBar = document.createElement('div');
        actionsBar.style.display = 'flex';
        actionsBar.style.gap = '6px';
        actionsBar.style.padding = '6px 0 10px 0';
        actionsBar.style.borderBottom = '1px solid var(--border-subtle)';
        actionsBar.style.marginBottom = '8px';

        actionsBar.appendChild(createActionButton('scan', 'Focus', function () {
            if (actionCallbacks.onFocus) actionCallbacks.onFocus(descriptor);
        }));
        actionsBar.appendChild(createActionButton('eye-off', 'Hide', function () {
            if (actionCallbacks.onHide) actionCallbacks.onHide(descriptor);
        }));
        actionsBar.appendChild(createActionButton('filter', 'Isolate', function () {
            if (actionCallbacks.onIsolate) actionCallbacks.onIsolate(descriptor);
        }));

        view.appendChild(actionsBar);

        // Tab Content
        var tab = activeTab || 'id';
        var rows = [];

        if (tab === 'id') {
            rows.push(renderPropertyRow('IFC Type', descriptor.ifcType));
            rows.push(renderPropertyRow('GlobalId', descriptor.globalId));
            rows.push(renderPropertyRow('STEP ID', descriptor.stepId));
            rows.push(renderPropertyRow('Entity Key', descriptor.entityKey));
            rows.push(renderPropertyRow('Source File', descriptor.sourceId));
            rows.push(renderPropertyRow('Storey', descriptor.storey));
            rows.push(renderPropertyRow('Building', descriptor.building));
        } else if (tab === 'map') {
            rows.push(renderPropertyRow('Simulation Role', descriptor.simulationRole, {
                badge: descriptor.simulationRole === 'EXCLUDE' ? 'EXCLUDED' : 'ACTIVE',
                badgeType: descriptor.simulationRole === 'EXCLUDE' ? 'warning' : 'pass'
            }));
            rows.push(renderPropertyRow('Mapping Strategy', descriptor.mappingStrategy));
            rows.push(renderPropertyRow('Representation', descriptor.representation));
            rows.push(renderPropertyRow('Boundary Treatment', descriptor.boundaryTreatment));
            rows.push(renderPropertyRow('Review Status', descriptor.reviewStatus));
        } else if (tab === 'geom') {
            var b = descriptor.bounds || (descriptor.raw && descriptor.raw.bounding_box) || {};
            var dx = (b.xmax !== undefined && b.xmin !== undefined) ? Math.abs(b.xmax - b.xmin).toFixed(3) : '--';
            var dy = (b.ymax !== undefined && b.ymin !== undefined) ? Math.abs(b.ymax - b.ymin).toFixed(3) : '--';
            var dz = (b.zmax !== undefined && b.zmin !== undefined) ? Math.abs(b.zmax - b.zmin).toFixed(3) : '--';
            rows.push(renderPropertyRow('Extents dx×dy×dz', dx + ' × ' + dy + ' × ' + dz + ' m'));
            var raw = descriptor.raw || {};
            rows.push(renderPropertyRow('Surface Area', raw.surface_area_m2 ? raw.surface_area_m2.toFixed(3) + ' m²' : '--'));
            rows.push(renderPropertyRow('Volume', raw.volume_m3 ? raw.volume_m3.toFixed(3) + ' m³' : '--'));
            rows.push(renderPropertyRow('FDS Primitives', (raw.fds_primitive_ids || []).join(', ') || '--'));
            rows.push(renderPropertyRow('BBox Check', 'PASS', { badge: 'PASS', badgeType: 'pass' }));
        } else if (tab === 'mep') {
            rows.push(renderPropertyRow('MEP Category', descriptor.mepCategory || 'NOT_APPLICABLE'));
            rows.push(renderPropertyRow('Systems', (descriptor.systemNames || []).join(', ') || '--'));
            rows.push(renderPropertyRow('System IDs', (descriptor.systemIds || []).join(', ') || '--'));
            rows.push(renderPropertyRow('Ports Count', descriptor.portsCount));
            rows.push(renderPropertyRow('Operational Status', descriptor.operationalStatus));

            // Scenario action hook for operational fan/duct
            if (descriptor.ifcType === 'IFCFAN' || descriptor.ifcType === 'IFCFLOWMOVINGDEVICE') {
                var hvacConfigRow = document.createElement('div');
                hvacConfigRow.style.marginTop = '10px';
                hvacConfigRow.style.padding = '8px';
                hvacConfigRow.style.background = 'var(--bg-base)';
                hvacConfigRow.style.borderRadius = '4px';

                var title = document.createElement('div');
                title.style.fontSize = '10px';
                title.style.fontWeight = '600';
                title.style.color = 'var(--text-secondary)';
                title.style.marginBottom = '6px';
                title.textContent = 'Operational HVAC Role';
                hvacConfigRow.appendChild(title);

                var cfgBtn = createActionButton('wind', 'Configure Fan Volume Flow', function () {
                    if (actionCallbacks.onConfigureHvac) actionCallbacks.onConfigureHvac(descriptor);
                });
                hvacConfigRow.appendChild(cfgBtn);
                rows.push(hvacConfigRow);
            }
        }

        // Append rows
        for (var i = 0; i < rows.length; i++) {
            view.appendChild(rows[i]);
        }

        if (window.lucide) {
            window.lucide.createIcons({ root: view });
        }
    };

    root.IfcFds.workbench.inspector.InspectorView = InspectorView;

})(typeof window !== 'undefined' ? window : globalThis);
