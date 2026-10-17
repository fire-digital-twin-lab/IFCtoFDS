/**
 * Reversible Selection Command for IFCtoFDS Research Workbench.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.commands = root.IfcFds.workbench.commands || {};

    function SelectCommand(itemsOrKeys, mode, selectionStore) {
        this.name = 'SelectCommand';
        this.itemsOrKeys = itemsOrKeys;
        this.mode = mode || 'replace'; // 'replace', 'add', 'toggle', 'clear'
        this.selectionStore = selectionStore || root.IfcFds.workbench.state.selectionStore;
        this._previousSelectionKeys = null;
    }

    SelectCommand.prototype.execute = function () {
        this._previousSelectionKeys = this.selectionStore.getSelectedKeys();
        if (this.mode === 'replace') {
            this.selectionStore.setSelection(this.itemsOrKeys, 'command');
        } else if (this.mode === 'add') {
            this.selectionStore.addSelection(this.itemsOrKeys, 'command');
        } else if (this.mode === 'toggle') {
            this.selectionStore.toggleSelection(this.itemsOrKeys, 'command');
        } else if (this.mode === 'clear') {
            this.selectionStore.clearSelection('command');
        }
        return true;
    };

    SelectCommand.prototype.undo = function () {
        if (this._previousSelectionKeys !== null) {
            this.selectionStore.setSelection(this._previousSelectionKeys, 'undo');
            return true;
        }
        return false;
    };

    root.IfcFds.workbench.commands.SelectCommand = SelectCommand;

})(typeof window !== 'undefined' ? window : globalThis);
