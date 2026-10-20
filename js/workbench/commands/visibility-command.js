/**
 * Reversible Visibility Commands for IFCtoFDS Research Workbench.
 * Encapsulates Hide, Isolate, Ghost, and Reset visibility operations.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.commands = root.IfcFds.workbench.commands || {};

    function cloneVisibilityState(store) {
        var s = store.getState();
        return {
            hiddenKeys: s.hiddenKeys.slice(),
            isolatedKeys: s.isolatedKeys ? s.isolatedKeys.slice() : null,
            ghostKeys: s.ghostKeys.slice(),
            storeyVisibility: Object.assign({}, s.storeyVisibility),
            systemVisibility: Object.assign({}, s.systemVisibility)
        };
    }

    function restoreVisibilityState(store, prevState) {
        if (store.restoreState) { store.restoreState(prevState, 'undo'); return; }
        store.resetVisibility('undo');
        if (prevState.hiddenKeys.length) store.hideKeys(prevState.hiddenKeys, 'undo');
        if (prevState.isolatedKeys) store.isolateKeys(prevState.isolatedKeys, 'undo');
        if (prevState.ghostKeys.length) store.ghostKeys(prevState.ghostKeys, 'undo');
        for (var st in prevState.storeyVisibility) {
            store.setStoreyVisibility(st, prevState.storeyVisibility[st], 'undo');
        }
        for (var sys in prevState.systemVisibility) {
            store.setSystemVisibility(sys, prevState.systemVisibility[sys], 'undo');
        }
    }

    function HideCommand(keys, visibilityStore) {
        this.name = 'HideCommand';
        this.keys = Array.isArray(keys) ? keys : (keys ? [keys] : []);
        this.visibilityStore = visibilityStore || root.IfcFds.workbench.state.visibilityStore;
        this._prevState = null;
    }

    HideCommand.prototype.execute = function () {
        this._prevState = cloneVisibilityState(this.visibilityStore);
        if (this.keys.every(function (key) { return this._prevState.hiddenKeys.indexOf(key) >= 0; }, this)) {
            this.visibilityStore.showKeys(this.keys, 'command');
        } else this.visibilityStore.hideKeys(this.keys, 'command');
        return true;
    };

    HideCommand.prototype.undo = function () {
        if (this._prevState) {
            restoreVisibilityState(this.visibilityStore, this._prevState);
            return true;
        }
        return false;
    };

    function IsolateCommand(keys, visibilityStore) {
        this.name = 'IsolateCommand';
        this.keys = Array.isArray(keys) ? keys : (keys ? [keys] : []);
        this.visibilityStore = visibilityStore || root.IfcFds.workbench.state.visibilityStore;
        this._prevState = null;
    }

    IsolateCommand.prototype.execute = function () {
        this._prevState = cloneVisibilityState(this.visibilityStore);
        var same = this._prevState.isolatedKeys && this._prevState.isolatedKeys.length === this.keys.length &&
            this.keys.every(function (key) { return this._prevState.isolatedKeys.indexOf(key) >= 0; }, this);
        if (same) {
            this.visibilityStore.restoreState(this._beforeIsolation || Object.assign({}, this._prevState, {isolatedKeys:null}), 'command');
        } else {
            this._beforeIsolation = cloneVisibilityState(this.visibilityStore);
            var next = cloneVisibilityState(this.visibilityStore);
            next.isolatedKeys = this.keys.slice();
            next.hiddenKeys = next.hiddenKeys.filter(function (key) { return this.keys.indexOf(key) < 0; }, this);
            this.visibilityStore.restoreState(next, 'command');
        }
        return true;
    };

    IsolateCommand.prototype.undo = function () {
        if (this._prevState) {
            restoreVisibilityState(this.visibilityStore, this._prevState);
            return true;
        }
        return false;
    };

    function GhostCommand(keys, visibilityStore) {
        this.name = 'GhostCommand';
        this.keys = Array.isArray(keys) ? keys : (keys ? [keys] : []);
        this.visibilityStore = visibilityStore || root.IfcFds.workbench.state.visibilityStore;
        this._prevState = null;
    }

    GhostCommand.prototype.execute = function () {
        this._prevState = cloneVisibilityState(this.visibilityStore);
        this.visibilityStore.ghostKeys(this.keys, 'command');
        return true;
    };

    GhostCommand.prototype.undo = function () {
        if (this._prevState) {
            restoreVisibilityState(this.visibilityStore, this._prevState);
            return true;
        }
        return false;
    };

    function ResetVisibilityCommand(visibilityStore) {
        this.name = 'ResetVisibilityCommand';
        this.visibilityStore = visibilityStore || root.IfcFds.workbench.state.visibilityStore;
        this._prevState = null;
    }

    ResetVisibilityCommand.prototype.execute = function () {
        this._prevState = cloneVisibilityState(this.visibilityStore);
        this.visibilityStore.resetVisibility('command');
        return true;
    };

    ResetVisibilityCommand.prototype.undo = function () {
        if (this._prevState) {
            restoreVisibilityState(this.visibilityStore, this._prevState);
            return true;
        }
        return false;
    };

    function RestoreVisibilityCommand(state, visibilityStore) {
        this.name = 'RestoreVisibilityCommand';
        this.targetState = state;
        this.visibilityStore = visibilityStore || root.IfcFds.workbench.state.visibilityStore;
    }
    RestoreVisibilityCommand.prototype.execute = function () {
        this._prevState = cloneVisibilityState(this.visibilityStore);
        restoreVisibilityState(this.visibilityStore, this.targetState);
        return true;
    };
    RestoreVisibilityCommand.prototype.undo = function () {
        restoreVisibilityState(this.visibilityStore, this._prevState);
        return true;
    };

    root.IfcFds.workbench.commands.HideCommand = HideCommand;
    root.IfcFds.workbench.commands.IsolateCommand = IsolateCommand;
    root.IfcFds.workbench.commands.GhostCommand = GhostCommand;
    root.IfcFds.workbench.commands.ResetVisibilityCommand = ResetVisibilityCommand;
    root.IfcFds.workbench.commands.RestoreVisibilityCommand = RestoreVisibilityCommand;

})(typeof window !== 'undefined' ? window : globalThis);
