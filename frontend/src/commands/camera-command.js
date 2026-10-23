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
        this.active = false;
    }

    FocusSelectedCommand.prototype.execute = function () {
        if (!this.viewer) return false;
        if (typeof this.viewer.focusSelection === 'function') {
            if (this.viewer.setNavigationMode) this.viewer.setNavigationMode('orbit');
            this._previous = {
                position: this.viewer.camera.position.clone(),
                target: this.viewer.controls.target.clone(),
                near: this.viewer.camera.near,
                far: this.viewer.camera.far
            };
            this.viewer.focusSelection();
            this.active = true;
            return true;
        }
        return false;
    };

    FocusSelectedCommand.prototype.undo = function () {
        if (!this._previous) return false;
        var v = this.viewer, s = this._previous;
        v.camera.position.copy(s.position);
        v.controls.target.copy(s.target);
        v.camera.near = s.near;
        v.camera.far = s.far;
        v.camera.updateProjectionMatrix();
        v.controls.update();
        this.active = false;
        return true;
    };

    function RestoreFocusCommand(focusCommand) {
        this.name = 'RestoreFocusCommand';
        this.focusCommand = focusCommand;
    }
    RestoreFocusCommand.prototype.execute = function () {
        var v = this.focusCommand.viewer;
        this._focused = {position:v.camera.position.clone(), target:v.controls.target.clone(), near:v.camera.near, far:v.camera.far};
        return this.focusCommand.undo();
    };
    RestoreFocusCommand.prototype.undo = function () {
        var v = this.focusCommand.viewer, s = this._focused;
        v.camera.position.copy(s.position); v.controls.target.copy(s.target);
        v.camera.near = s.near; v.camera.far = s.far;
        v.camera.updateProjectionMatrix(); v.controls.update();
        this.focusCommand.active = true;
        return true;
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
    root.IfcFds.workbench.commands.RestoreFocusCommand = RestoreFocusCommand;
    root.IfcFds.workbench.commands.SetViewDirectionCommand = SetViewDirectionCommand;
    root.IfcFds.workbench.commands.ResetCameraCommand = ResetCameraCommand;

})(typeof window !== 'undefined' ? window : globalThis);
