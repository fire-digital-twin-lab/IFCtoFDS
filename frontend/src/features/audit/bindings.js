(function (ns) {
    ns.app = ns.app || {};
    ns.features = ns.features || {};
    ns.features.audit = ns.features.audit || {};
    ns.features.audit.createAuditBindings = function (dependencies) {
    var life = ns.core.createLifecycle();
    function toggleAuditDrawer() { return dependencies.toggleAuditDrawer.apply(null, arguments); }




    var bound = false;
    function bind() {
        if (bound) return;
        bound = true;
        var els = dependencies.getElements();
        // Bottom Audit Drawer Toggle & Tabs
        if (els.toggleDrawer && els.auditDrawer) {
            life.listen(els.toggleDrawer, 'click', function (e) {
                e.stopPropagation();
                toggleAuditDrawer();
            });
            var drawerHeader = document.querySelector('.audit-drawer-header');
            if (drawerHeader) {
                life.listen(drawerHeader, 'click', function (e) {
                    if (e.target.closest('.audit-tab-btn')) return;
                    toggleAuditDrawer();
                });
            }
        }
        ['gates', 'findings', 'artifacts'].forEach(function (tab) {
            var btn = document.getElementById('drawer-tab-' + tab);
            var panel = document.getElementById('panel-' + tab);
            if (btn && panel) {
                life.listen(btn, 'click', function (e) {
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

    return {bind: bind, destroy: function () { life.destroy(); }};
    };
})(window.IfcFds);
