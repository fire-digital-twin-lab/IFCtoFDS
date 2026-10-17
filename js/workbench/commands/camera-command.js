/**
 * Camera Commands for IFCtoFDS Research Workbench.
 * Encapsulates view snaps (Top, Front, Left, Isometric) and Focus Selection.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.commands = root.IfcFds.workbench.commands || {};

    function FocusSelectedCommand(viewer, selectionStore) {
        this.name = 'FocusSelectedCommand';
        this.viewer = viewer;
        this.selectionStore = selectionStore || root.IfcFds.workbench.state.selectionStore;
    }

    FocusSelectedCommand.prototype.execute = function () {
        if (!this.viewer) return false;
        if (typeof this.viewer.focusSelection === 'function') {
            this.viewer.focusSelection();
            return true;
        }
        return false;
    };

    function SetViewDirectionCommand(viewer, direction) {
        this.name = 'SetViewDirectionCommand';
        this.viewer = viewer;
        this.direction = direction; // 'top', 'bottom', 'left', 'right', 'front', 'back', 'iso'
    }

    SetViewDirectionCommand.prototype.execute = function () {
        if (!this.viewer) return false;
        if (typeof this.viewer.setViewDirection === 'function') {
            this.viewer.setViewDirection(this.direction);
            return true;
        }
        return false;
    };

    function ResetCameraCommand(viewer) {
        this.name = 'ResetCameraCommand';
        this.viewer = viewer;
    }

    ResetCameraCommand.prototype.execute = function () {
        if (!this.viewer) return false;
        if (typeof this.viewer.resetCamera === 'function') {
            this.viewer.resetCamera();
            return true;
        }
        return false;
    };

    root.IfcFds.workbench.commands.FocusSelectedCommand = FocusSelectedCommand;
    root.IfcFds.workbench.commands.SetViewDirectionCommand = SetViewDirectionCommand;
    root.IfcFds.workbench.commands.ResetCameraCommand = ResetCameraCommand;

})(typeof window !== 'undefined' ? window : globalThis);
