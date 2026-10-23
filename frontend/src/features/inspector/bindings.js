(function (ns) {
    ns.app = ns.app || {};
    ns.features = ns.features || {};
    ns.features.inspector = ns.features.inspector || {};
    ns.features.inspector.createInspectorBindings = function (dependencies) {
    var life = ns.core.createLifecycle();

    var state = dependencies.state;
    function renderStructuredInspector() { return dependencies.renderStructuredInspector.apply(null, arguments); }

    var bound = false;
    function bind() {
        if (bound) return;
        bound = true;
        // Inspector Tabs
        ['id', 'map', 'geom', 'mep'].forEach(function (tab) {
            var btn = document.getElementById('inspect-tab-' + tab);
            if (btn) {
                life.listen(btn, 'click', function () {
                    state.activeInspectorTab = tab;
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


    }

    return {bind: bind, destroy: function () { life.destroy(); }};
    };
})(window.IfcFds);
