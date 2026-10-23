(function (ns) {
    ns.app = ns.app || {};
    ns.app.createShellController = function (dependencies) {
    var life = ns.core.createLifecycle();
    function closeAudit() { return dependencies.closeAudit.apply(null, arguments); }
    function openAudit() { return dependencies.openAudit.apply(null, arguments); }

    var state = dependencies.state;
    var sidebarTabs = null;

    function openHelp(event) {
        var creditsDialog = dependencies.getCreditsDialog();
        var helpDialog = dependencies.getHelpDialog();
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        viewer.setNavigationMode('orbit');
        helpDialog.open(event);
    }

    function closeHelp() {
        var creditsDialog = dependencies.getCreditsDialog();
        var helpDialog = dependencies.getHelpDialog();
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements(); helpDialog.close(); }

    function openCredits() {
        var creditsDialog = dependencies.getCreditsDialog();
        var helpDialog = dependencies.getHelpDialog();
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements(); creditsDialog.open(); }

    function closeCredits() {
        var creditsDialog = dependencies.getCreditsDialog();
        var helpDialog = dependencies.getHelpDialog();
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements(); creditsDialog.close(); }

    function readSavedTheme() {
        var creditsDialog = dependencies.getCreditsDialog();
        var helpDialog = dependencies.getHelpDialog();
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        try {
            return localStorage.getItem('ifc-fds-theme') || 'light';
        } catch (error) {
            return 'light';
        }
    }

    function applyTheme(theme) {
        var creditsDialog = dependencies.getCreditsDialog();
        var helpDialog = dependencies.getHelpDialog();
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        state.theme = theme === 'dark' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', state.theme);
        if (viewer) viewer.setTheme(state.theme);
        if (!els.toggleTheme) return;

        var nextTheme = state.theme === 'dark' ? 'light' : 'dark';
        els.toggleTheme.title = 'Switch to ' + nextTheme + ' theme';
        els.toggleTheme.setAttribute('aria-label', els.toggleTheme.title);
        els.toggleTheme.innerHTML = '<i data-lucide="' + (state.theme === 'dark' ? 'sun' : 'moon') + '"></i>';
        if (window.lucide) window.lucide.createIcons();
    }

    function updateWalkModeButton(mode) {
        var creditsDialog = dependencies.getCreditsDialog();
        var helpDialog = dependencies.getHelpDialog();
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        var walking = mode === 'walk';
        els.toggleWalk.classList.toggle('active', walking);
        els.toggleWalk.setAttribute('aria-pressed', walking ? 'true' : 'false');
        els.toggleWalk.title = walking
            ? 'Exit walk mode'
            : 'Enter walk mode';
        els.toggleWalk.setAttribute('aria-label', walking ? 'Exit walk mode' : 'Enter walk mode');
    }

    function setWorkflowMode(mode) {
        var creditsDialog = dependencies.getCreditsDialog();
        var helpDialog = dependencies.getHelpDialog();
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        var isVerified = mode === 'verified';
        if (els.modeTabVerified) els.modeTabVerified.classList.toggle('active', isVerified);
        if (els.modeTabQuick) els.modeTabQuick.classList.toggle('active', !isVerified);
        var target = isVerified ? els.containerVerified : els.containerQuick;
        if (target && target.scrollIntoView) {
            target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    function updateColorModeLegend(mode) {
        var creditsDialog = dependencies.getCreditsDialog();
        var helpDialog = dependencies.getHelpDialog();
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
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
    var bound = false;
    function bind() {
        if (bound) return;
        bound = true;
        var creditsDialog = dependencies.getCreditsDialog();
        var helpDialog = dependencies.getHelpDialog();
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        life.listen(els.toggleTheme, 'click', function () {
            var theme = state.theme === 'dark' ? 'light' : 'dark';
            applyTheme(theme);
            try {
                localStorage.setItem('ifc-fds-theme', theme);
            } catch (error) {
                // Theme switching still works when storage is unavailable.
            }
        });

        life.listen(els.toggleWalk, 'click', function () {
            viewer.setNavigationMode(viewer.navigationMode === 'walk' ? 'orbit' : 'walk');
        });

        // Both the toolbar help button and the footer "Guide" link now open the standalone
        // single-column guide.html page in a new tab instead of layering a modal over the
        // viewer. The old modal markup is left in place as a fallback for any environment
        // where window.open is blocked.
        [els.openHelp, els.footerHelp].forEach(function (button) {
            if (!button) return;
            life.listen(button, 'click', function (event) {
                event.preventDefault();
                var opened = window.open('guide.html', '_blank', 'noopener');
                if (!opened) openHelp();
            });
        });

        if (els.closeHelp) life.listen(els.closeHelp, 'click', closeHelp);
        if (els.helpModal) {
            var backdrop = els.helpModal.querySelector('[data-close-help]');
            if (backdrop) life.listen(backdrop, 'click', closeHelp);
        }

        if (els.openCredits) life.listen(els.openCredits, 'click', openCredits);
        if (els.closeCredits) life.listen(els.closeCredits, 'click', closeCredits);
        if (els.creditsModal) life.listen(els.creditsModal.querySelector('[data-close-credits]'), 'click', closeCredits);

        if (els.openAudit) life.listen(els.openAudit, 'click', openAudit);
        if (els.closeAudit) life.listen(els.closeAudit, 'click', closeAudit);
        if (els.auditModal) {
            var auditBackdrop = els.auditModal.querySelector('[data-close-audit]');
            if (auditBackdrop) life.listen(auditBackdrop, 'click', closeAudit);
        }

        life.listen(window, 'keydown', function (event) {
            if (event.key === 'Escape' && !els.helpModal.hidden) closeHelp();
            if (event.key === 'Escape' && els.creditsModal && !els.creditsModal.hidden) closeCredits();
            if (event.key === 'Escape' && els.auditModal && !els.auditModal.hidden) closeAudit();
        });

        // Workflow Mode Switcher
        if (els.modeTabVerified) {
            life.listen(els.modeTabVerified, 'click', function () { setWorkflowMode('verified'); });
        }
        if (els.modeTabQuick) {
            life.listen(els.modeTabQuick, 'click', function () { setWorkflowMode('quick'); });
        }

        // Viewport Floating Toolbar Popovers
        var btnLayers = document.getElementById('toggle-layers-popover');
        var popLayers = document.getElementById('layers-popover');
        var btnCamera = document.getElementById('toggle-camera-views');
        var popCamera = document.getElementById('camera-popover');
        if (btnLayers && popLayers) {
            life.listen(btnLayers, 'click', function (e) {
                e.stopPropagation();
                popLayers.style.display = popLayers.style.display === 'none' ? 'flex' : 'none';
                if (popCamera) popCamera.style.display = 'none';
            });
        }
        if (btnCamera && popCamera) {
            life.listen(btnCamera, 'click', function (e) {
                e.stopPropagation();
                popCamera.style.display = popCamera.style.display === 'none' ? 'flex' : 'none';
                if (popLayers) popLayers.style.display = 'none';
            });
        }
        life.listen(document, 'click', function () {
            if (popLayers) popLayers.style.display = 'none';
            if (popCamera) popCamera.style.display = 'none';
        });

        var btnClip = document.getElementById('toggle-clip');
        if (btnClip && els.clipPanel) {
            life.listen(btnClip, 'click', function () {
                els.clipPanel.hidden = !els.clipPanel.hidden;
            });
        }

        Array.prototype.forEach.call(document.querySelectorAll('[data-cam]'), function (btn) {
            life.listen(btn, 'click', function () {
                var dir = btn.getAttribute('data-cam');
                if (dir && viewer && viewer.setView) viewer.setView(dir);
            });
        });

        // Sidebar Nav Switcher (Workflow vs Model Tree)
        var tabWorkflow = document.getElementById('sidebar-tab-workflow');
        var tabTree = document.getElementById('sidebar-tab-tree');
        var panelWorkflow = document.getElementById('sidebar-panel-workflow');
        var panelTree = document.getElementById('sidebar-panel-tree');

        if (tabWorkflow && tabTree && panelWorkflow && panelTree) {
            sidebarTabs = new ns.components.Tabs([
                {id: 'workflow', button: tabWorkflow, panel: panelWorkflow, display: 'block'},
                {id: 'tree', button: tabTree, panel: panelTree, display: 'flex'}
            ], function (id) {
                if (id === 'tree' && ns.workbench && ns.workbench.navigation && ns.workbench.navigation.modelTree) {
                    ns.workbench.navigation.modelTree.render();
                }
            }).mount();
        }


    }

    return {openHelp: openHelp, closeHelp: closeHelp, openCredits: openCredits, closeCredits: closeCredits, readSavedTheme: readSavedTheme, applyTheme: applyTheme, updateWalkModeButton: updateWalkModeButton, setWorkflowMode: setWorkflowMode, updateColorModeLegend: updateColorModeLegend, bind: bind, destroy: function () { life.destroy(); if (sidebarTabs) sidebarTabs.destroy(); }};
    };
})(window.IfcFds);
