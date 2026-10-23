(function (ns) {
    ns.features = ns.features || {};
    ns.features.audit = ns.features.audit || {};
    ns.features.audit.createAuditController = function (dependencies) {
        var state = dependencies.state;


        function renderAuditReport(report) {
            var els = dependencies.getElements();
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
            var exported = (report.coverage || {}).fds_export;
            if (exported) {
                line('p', 'FDS written: ' + exported.entities + ' entities / ' + exported.primitives + ' primitives (' + exported.obst + ' OBST, ' + exported.geom + ' GEOM). Independently verified: ' + exported.verified_entities + '.');
                if (exported.comparisons_skipped_for_source_errors) line('p', 'Source topology errors stopped the remaining solid comparisons. The FDS download is available as an unaccepted diagnostic artifact.');
            }
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
            var els = dependencies.getElements();
            if (!els.auditModal) return;
            renderAuditReport(state.lastAuditReport);
            els.auditModal.hidden = false;
        }

        function closeAudit() {
            var els = dependencies.getElements();
            if (!els.auditModal) return;
            els.auditModal.hidden = true;
        }

        function toggleAuditDrawer() {
            var els = dependencies.getElements();
            if (ns.ui && ns.ui.auditDrawer) {
                ns.ui.auditDrawer.toggleAuditDrawer(els);
            }
        }

        function renderAuditDrawer(report) {
            var viewer = dependencies.getViewer();
            if (ns.ui && ns.ui.auditDrawer) {
                ns.ui.auditDrawer.renderAuditDrawer(report, viewer);
            }
        }

        function exposeFailedCheckpoints(jobId) {
            if (ns.ui && ns.ui.auditDrawer) {
                ns.ui.auditDrawer.exposeFailedCheckpoints(jobId);
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

        return {
            renderAuditReport: renderAuditReport,
            openAudit: openAudit,
            closeAudit: closeAudit,
            toggleAuditDrawer: toggleAuditDrawer,
            renderAuditDrawer: renderAuditDrawer,
            exposeFailedCheckpoints: exposeFailedCheckpoints,
            updateGlobalStatusBadge: updateGlobalStatusBadge
        };
    };
})(window.IfcFds);
