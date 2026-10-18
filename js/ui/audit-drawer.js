/**
 * Audit & Acceptance Console Drawer for IFCtoFDS Research Workbench.
 * Renders core gate cards, filterable findings table with P0-P3 severity badges,
 * locate-in-3D hooks, and failed simulation checkpoint downloads.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.ui = root.IfcFds.ui || {};

    var activeViewer = null;

    function renderAuditDrawer(report, viewer) {
        if (viewer) activeViewer = viewer;
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
        var totalFindings = (typeof report.findings_count === 'number')
            ? report.findings_count
            : ((typeof report.total_findings === 'number') ? report.total_findings : findings.length);
        var findingCountBadge = document.getElementById('drawer-finding-count');
        if (findingCountBadge) findingCountBadge.textContent = totalFindings;

        var panelFindings = document.getElementById('panel-findings');
        var truncationBanner = document.getElementById('findings-truncation-banner');
        if (totalFindings > findings.length) {
            if (!truncationBanner && panelFindings) {
                truncationBanner = document.createElement('div');
                truncationBanner.id = 'findings-truncation-banner';
                truncationBanner.style.padding = '6px 12px';
                truncationBanner.style.marginBottom = '8px';
                truncationBanner.style.fontSize = '11px';
                truncationBanner.style.background = 'var(--status-warning-bg)';
                truncationBanner.style.color = 'var(--status-warning-text)';
                truncationBanner.style.border = '1px solid var(--status-warning-border)';
                truncationBanner.style.borderRadius = 'var(--radius-xs)';
                panelFindings.insertBefore(truncationBanner, panelFindings.firstChild);
            }
            if (truncationBanner) {
                truncationBanner.style.display = 'block';
                var reportUrl = (report.artifacts && report.artifacts.report && report.artifacts.report.url) || null;
                var linkHtml = reportUrl
                    ? '<a href="' + reportUrl + '" download style="color:inherit;text-decoration:underline;font-weight:600">Download full acceptance report</a> for complete list.'
                    : '<span style="font-weight:600">Download full report from Artifacts tab</span> for complete list.';
                truncationBanner.innerHTML = 'Showing first ' + findings.length + ' of ' + totalFindings + ' findings. ' + linkHtml;
            }
        } else if (truncationBanner) {
            truncationBanner.style.display = 'none';
        }

        var findingsTbody = document.getElementById('findings-table-body');
        if (findingsTbody) {
            findingsTbody.innerHTML = '';
            if (!findings.length) {
                findingsTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:24px">No findings reported. Check gate statuses for unverified requirements.</td></tr>';
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
                            if (root.IfcFds && root.IfcFds.workbench && root.IfcFds.workbench.selection && root.IfcFds.workbench.selection.selectionManager) {
                                root.IfcFds.workbench.selection.selectionManager.selectByEntityKeys([f.element_id]);
                            }
                            if (activeViewer) {
                                if (typeof activeViewer.selectByEntityKeys === 'function') {
                                    activeViewer.selectByEntityKeys([f.element_id]);
                                }
                                if (typeof activeViewer.focusSelection === 'function') {
                                    activeViewer.focusSelection();
                                }
                            }
                        });
                        tdAct.appendChild(btn);
                    }
                    tr.appendChild(tdAct);
                    findingsTbody.appendChild(tr);
                });
            }
        }

        var fdsBtn = document.getElementById('btn-download-fds');
        if (fdsBtn) {
            fdsBtn.textContent = 'Download FDS';
            if (report.artifacts && report.artifacts.fds) fdsBtn.href = report.artifacts.fds.url;
        }
        var manifestBtn = document.getElementById('btn-download-manifest');
        if (manifestBtn) {
            manifestBtn.textContent = 'Download Manifest';
            if (report.artifacts && report.artifacts.manifest) manifestBtn.href = report.artifacts.manifest.url;
        }
        var geomBtn = document.getElementById('btn-download-geom-pkg');
        if (geomBtn) {
            geomBtn.textContent = 'Download Geometries';
            if (report.artifacts && report.artifacts.geometry) geomBtn.href = report.artifacts.geometry.url;
        }
        var reportBtn = document.getElementById('btn-download-report');
        if (reportBtn) {
            reportBtn.textContent = 'Download Full Report';
            if (report.artifacts && report.artifacts.report) reportBtn.href = report.artifacts.report.url;
        }

        updateGlobalStatusBadge(report.status);
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
        var reportBtn = document.getElementById('btn-download-report');
        if (reportBtn) {
            reportBtn.href = '/api/jobs/' + jobId + '/checkpoints/report';
            reportBtn.textContent = 'Download Checkpoint Report (UNACCEPTED)';
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

    function toggleAuditDrawer(els) {
        var drawer = (els && els.auditDrawer) || document.getElementById('audit-drawer');
        if (!drawer) return;
        var isMin = drawer.classList.toggle('minimized');
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
        } else if (status === 'REJECTED') {
            badge.classList.add('rejected');
            label.textContent = 'REJECTED';
        } else {
            badge.classList.add('untested');
            label.textContent = status || 'READY';
        }
    }

    function init(els, viewer) {
        if (viewer) activeViewer = viewer;
        var drawerTabs = document.querySelectorAll('.audit-tab-btn');
        drawerTabs.forEach(function (btn) {
            btn.addEventListener('click', function () {
                drawerTabs.forEach(function (b) { b.classList.remove('active'); });
                btn.classList.add('active');
                var tab = btn.getAttribute('data-tab');
                var panelGates = document.getElementById('panel-gates');
                var panelFindings = document.getElementById('panel-findings');
                var panelArtifacts = document.getElementById('panel-artifacts');
                if (panelGates) panelGates.style.display = tab === 'gates' ? 'grid' : 'none';
                if (panelFindings) panelFindings.style.display = tab === 'findings' ? 'block' : 'none';
                if (panelArtifacts) panelArtifacts.style.display = tab === 'artifacts' ? 'grid' : 'none';
            });
        });

        var toggleBtn = (els && els.toggleDrawer) || document.getElementById('toggle-drawer');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', function () { toggleAuditDrawer(els); });
        }
    }

    root.IfcFds.ui.auditDrawer = {
        init: init,
        renderAuditDrawer: renderAuditDrawer,
        exposeFailedCheckpoints: exposeFailedCheckpoints,
        toggleAuditDrawer: toggleAuditDrawer,
        updateGlobalStatusBadge: updateGlobalStatusBadge,
        setViewer: function (v) { activeViewer = v; }
    };
})(window);
