/**
 * Selection and Spatial Query Engine for IFCtoFDS Research Workbench.
 * Provides fast querying across building storeys, MEP systems, IFC types,
 * and mapping classifications.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.selection = root.IfcFds.workbench.selection || {};

    var SelectionQuery = {
        byStorey: function (descriptors, storey) {
            if (!descriptors || !storey) return [];
            return descriptors.filter(function (d) {
                return d && d.storey && d.storey.toLowerCase() === String(storey).toLowerCase();
            });
        },

        byIfcType: function (descriptors, ifcType) {
            if (!descriptors || !ifcType) return [];
            var target = String(ifcType).toUpperCase();
            return descriptors.filter(function (d) {
                return d && d.ifcType && d.ifcType.toUpperCase() === target;
            });
        },

        bySystem: function (descriptors, systemName) {
            if (!descriptors || !systemName) return [];
            var target = String(systemName).toLowerCase();
            return descriptors.filter(function (d) {
                if (!d || !d.systemNames) return false;
                for (var i = 0; i < d.systemNames.length; i++) {
                    if (String(d.systemNames[i]).toLowerCase() === target) return true;
                }
                return false;
            });
        },

        byMappingRole: function (descriptors, role) {
            if (!descriptors || !role) return [];
            var target = String(role).toUpperCase();
            return descriptors.filter(function (d) {
                return d && d.simulationRole && d.simulationRole.toUpperCase() === target;
            });
        },

        byMepCategory: function (descriptors, category) {
            if (!descriptors || !category) return [];
            var target = String(category).toLowerCase();
            return descriptors.filter(function (d) {
                return d && d.mepCategory && d.mepCategory.toLowerCase() === target;
            });
        },

        findConnectedMepKeys: function (startEntityKey, mepGraph) {
            if (!startEntityKey || !mepGraph || !mepGraph.connections) return [startEntityKey];
            var visited = {};
            var queue = [startEntityKey];
            visited[startEntityKey] = true;

            var adj = {};
            var conns = mepGraph.connections || [];
            for (var i = 0; i < conns.length; i++) {
                var c = conns[i];
                var from = c.from_entity || c.from || c.source_key || c.source_element_id || c.source_id;
                var to = c.to_entity || c.to || c.target_key || c.target_element_id || c.target_id;
                if (from && to) {
                    if (!adj[from]) adj[from] = [];
                    if (!adj[to]) adj[to] = [];
                    adj[from].push(to);
                    adj[to].push(from);
                }
            }

            while (queue.length > 0) {
                var curr = queue.shift();
                var neighbors = adj[curr] || [];
                for (var j = 0; j < neighbors.length; j++) {
                    var n = neighbors[j];
                    if (!visited[n]) {
                        visited[n] = true;
                        queue.push(n);
                    }
                }
            }

            return Object.keys(visited);
        }
    };

    root.IfcFds.workbench.selection.SelectionQuery = SelectionQuery;

})(typeof window !== 'undefined' ? window : globalThis);
