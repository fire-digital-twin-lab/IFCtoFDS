/**
 * Reactive State Store for IFCtoFDS Research Workbench.
 * Centralizes UI and conversion state, manages undo history,
 * and notifies subscribers on state updates.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.ui = root.IfcFds.ui || {};

    function StateStore(initialState) {
        this._state = Object.assign({
            fdsModel: null,
            ifcModel: null,
            ifcSourceText: null,
            ifcFileName: null,
            fullModel: null,
            lastDisplayMeshes: null,
            generatedFdsText: null,
            generatedFdsName: null,
            forceObstStepIds: {},
            excludedStepIds: {},
            excludedItemIds: {},
            undoStack: [],
            selection: [],
            exportEnabled: false,
            exportBusy: false,
            exportAction: null,
            exportRequestId: 0,
            exportWorker: null,
            exportWorkerUrl: null,
            helpTrigger: null,
            lastAuditReport: null,
            lastManifest: null,
            backendOnline: false,
            currentIfcFile: null
        }, initialState || {});

        this._listeners = [];
    }

    StateStore.prototype.get = function (key) {
        return this._state[key];
    };

    StateStore.prototype.getState = function () {
        return this._state;
    };

    StateStore.prototype.set = function (key, value) {
        var patch = {};
        patch[key] = value;
        this.setState(patch);
    };

    StateStore.prototype.setState = function (patch) {
        var prevState = Object.assign({}, this._state);
        Object.assign(this._state, patch);
        for (var i = 0; i < this._listeners.length; i++) {
            try {
                this._listeners[i](this._state, prevState);
            } catch (err) {
                console.error('StateStore listener error:', err);
            }
        }
    };

    StateStore.prototype.subscribe = function (listener) {
        this._listeners.push(listener);
        var self = this;
        return function () {
            self._listeners = self._listeners.filter(function (l) { return l !== listener; });
        };
    };

    StateStore.prototype.pushUndo = function (action) {
        this._state.undoStack.push(action);
    };

    StateStore.prototype.popUndo = function () {
        return this._state.undoStack.pop();
    };

    StateStore.prototype.clearUndo = function () {
        this._state.undoStack = [];
    };

    root.IfcFds.ui.StateStore = StateStore;
})(window);
