(function (ns) {
    ns.app = ns.app || {};
    ns.features = ns.features || {};
    ns.features.modelTree = ns.features.modelTree || {};
    ns.features.modelTree.createTreeBindings = function (dependencies) {
    var life = ns.core.createLifecycle();




    var bound = false;
    function bind() {
        if (bound) return;
        bound = true;
        // Semantic Tree Group & Search
        var treeGroupBy = document.getElementById('tree-group-by');
        if (treeGroupBy) {
            life.listen(treeGroupBy, 'change', function () {
                if (ns.workbench && ns.workbench.navigation && ns.workbench.navigation.modelTree) {
                    ns.workbench.navigation.modelTree.setGroupBy(treeGroupBy.value);
                }
            });
        }
        var treeSearch = document.getElementById('tree-search-input');
        if (treeSearch) {
            life.listen(treeSearch, 'input', function () {
                if (ns.workbench && ns.workbench.navigation && ns.workbench.navigation.modelTree) {
                    ns.workbench.navigation.modelTree.setSearchQuery(treeSearch.value);
                }
            });
        }


    }

    return {bind: bind, destroy: function () { life.destroy(); }};
    };
})(window.IfcFds);
