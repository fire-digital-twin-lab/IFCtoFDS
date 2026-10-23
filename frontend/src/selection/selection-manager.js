/**
 * Selection Manager for IFCtoFDS Research Workbench.
 * Bridges 3D Viewport picking with the CommandBus and SelectionStore.
 * Enforces unified EntityKey identity (sourceId + GlobalId / stepId).
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.selection = root.IfcFds.workbench.selection || {};

    var normalizeEntityDescriptor = root.IfcFds.workbench.normalizeEntityDescriptor;
    var createEntityKey = root.IfcFds.workbench.createEntityKey;
    var commandBus = root.IfcFds.workbench.commands.commandBus;
    var SelectCommand = root.IfcFds.workbench.commands.SelectCommand;
    var selectionStore = root.IfcFds.workbench.state.selectionStore;

    function SelectionManager(store, bus) {
        this.store = store || selectionStore;
        this.bus = bus || commandBus;
    }

    /**
     * Handles selection incoming from 3D Viewport raycasting.
     * @param {Object|Array} candidate - Picked node userData or array of userDatas
     * @param {MouseEvent|Object} event - Browser mouse/pointer event with modifier keys
     */
    SelectionManager.prototype.handleViewerPick = function (candidate, event) {
        var additive = event && (event.shiftKey || event.ctrlKey || event.metaKey);
        if (!candidate || (Array.isArray(candidate) && !candidate.length)) {
            if (!additive) {
                var clearCmd = new SelectCommand([], 'clear', this.store);
                this.bus.execute(clearCmd);
            }
            return;
        }

        if (Array.isArray(candidate)) {
            var descriptors = candidate.map(normalizeEntityDescriptor).filter(Boolean);
            var mode = additive ? 'add' : 'replace';
            var multiCmd = new SelectCommand(descriptors, mode, this.store);
            this.bus.execute(multiCmd);
            return;
        }

        var desc = normalizeEntityDescriptor(candidate);
        if (!desc || !desc.entityKey) return;

        if (additive) {
            var toggleCmd = new SelectCommand(desc, 'toggle', this.store);
            this.bus.execute(toggleCmd);
        } else {
            var replaceCmd = new SelectCommand([desc], 'replace', this.store);
            this.bus.execute(replaceCmd);
        }
    };

    /**
     * Explicit selection by EntityKeys (from tree, table, or query).
     */
    SelectionManager.prototype.selectByEntityKeys = function (keys, mode) {
        var list = Array.isArray(keys) ? keys : [keys];
        var descriptors = [];
        for (var i = 0; i < list.length; i++) {
            var key = String(list[i]);
            var desc = this.store.getDescriptor(key) || { entityKey: key, name: key, ifcType: 'UNKNOWN' };
            descriptors.push(desc);
        }
        var cmd = new SelectCommand(descriptors, mode || 'replace', this.store);
        this.bus.execute(cmd);
    };

    SelectionManager.prototype.clear = function () {
        var cmd = new SelectCommand([], 'clear', this.store);
        this.bus.execute(cmd);
    };

    var defaultSelectionManager = new SelectionManager();

    root.IfcFds.workbench.selection.SelectionManager = SelectionManager;
    root.IfcFds.workbench.selection.selectionManager = defaultSelectionManager;

})(typeof window !== 'undefined' ? window : globalThis);
