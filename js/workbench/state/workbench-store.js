/**
 * Unified Root Workbench Store for IFCtoFDS Research Workbench.
 * Composes SelectionStore, VisibilityStore, ScenarioStore, and Workspace Mode.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.state = root.IfcFds.workbench.state || {};

    var events = root.IfcFds.workbench.events;
    var WORKBENCH_EVENTS = root.IfcFds.workbench.WORKBENCH_EVENTS;

    var MODES = {
        MODEL: 'MODEL',
        ENGINEER: 'ENGINEER',
        SIMULATE: 'SIMULATE',
        ANALYZE: 'ANALYZE'
    };

    function WorkbenchStore(selectionStore, visibilityStore, scenarioStore) {
        this.selection = selectionStore || root.IfcFds.workbench.state.selectionStore;
        this.visibility = visibilityStore || root.IfcFds.workbench.state.visibilityStore;
        this.scenario = scenarioStore || root.IfcFds.workbench.state.scenarioStore;
        this._mode = MODES.MODEL;
        this._listeners = [];
    }

    WorkbenchStore.prototype.getMode = function () {
        return this._mode;
    };

    WorkbenchStore.prototype.setMode = function (mode) {
        if (!MODES[mode]) return;
        var prevMode = this._mode;
        this._mode = mode;
        this._notifyModeChanged(prevMode);
    };

    WorkbenchStore.prototype.resetAll = function () {
        this.selection.clearSelection('reset');
        this.selection.clearIndex();
        this.visibility.resetVisibility('reset');
        this._mode = MODES.MODEL;
    };

    WorkbenchStore.prototype.subscribe = function (listener) {
        if (typeof listener !== 'function') return function () {};
        this._listeners.push(listener);
        var self = this;
        return function () {
            self._listeners = self._listeners.filter(function (l) { return l !== listener; });
        };
    };

    WorkbenchStore.prototype._notifyModeChanged = function (prevMode) {
        var payload = {
            mode: this._mode,
            previousMode: prevMode
        };
        for (var i = 0; i < this._listeners.length; i++) {
            try {
                this._listeners[i](payload);
            } catch (err) {
                console.error('[WorkbenchStore] Listener error:', err);
            }
        }
        if (events && WORKBENCH_EVENTS) {
            events.emit(WORKBENCH_EVENTS.MODE_CHANGED, payload);
        }
    };

    var defaultWorkbenchStore = new WorkbenchStore();

    root.IfcFds.workbench.MODES = MODES;
    root.IfcFds.workbench.state.WorkbenchStore = WorkbenchStore;
    root.IfcFds.workbench.state.workbenchStore = defaultWorkbenchStore;

})(typeof window !== 'undefined' ? window : globalThis);
