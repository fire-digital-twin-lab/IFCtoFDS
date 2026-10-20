/**
 * Visibility Store for IFCtoFDS Research Workbench.
 * Coordinates 3D spatial filtering: Hide, Isolate, Ghost, Storey filters, and System filters.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.state = root.IfcFds.workbench.state || {};

    var events = root.IfcFds.workbench.events;
    var WORKBENCH_EVENTS = root.IfcFds.workbench.WORKBENCH_EVENTS;

    function VisibilityStore() {
        this._hiddenKeys = {}; // entityKey -> true
        this._isolatedKeys = null; // null when not in isolate mode, or { entityKey: true }
        this._ghostKeys = {}; // entityKey -> true
        this._storeyVisibility = {}; // storeyName -> boolean
        this._systemVisibility = {}; // systemName -> boolean
        this._listeners = [];
    }

    VisibilityStore.prototype.hideKeys = function (keys, source) {
        var list = Array.isArray(keys) ? keys : (keys ? [keys] : []);
        if (!list.length) return;
        for (var i = 0; i < list.length; i++) {
            var k = String(list[i]);
            this._hiddenKeys[k] = true;
            delete this._ghostKeys[k];
        }
        this._notifyChanged(source || 'hide');
    };

    VisibilityStore.prototype.showKeys = function (keys, source) {
        var list = Array.isArray(keys) ? keys : (keys ? [keys] : []);
        if (!list.length) return;
        for (var i = 0; i < list.length; i++) {
            var k = String(list[i]);
            delete this._hiddenKeys[k];
            if (this._isolatedKeys) {
                this._isolatedKeys[k] = true;
            }
        }
        this._notifyChanged(source || 'show');
    };

    VisibilityStore.prototype.isolateKeys = function (keys, source) {
        var list = Array.isArray(keys) ? keys : (keys ? [keys] : []);
        if (!list.length) {
            this._isolatedKeys = null;
        } else {
            this._isolatedKeys = {};
            for (var i = 0; i < list.length; i++) {
                this._isolatedKeys[String(list[i])] = true;
            }
        }
        this._notifyChanged(source || 'isolate');
    };

    VisibilityStore.prototype.ghostKeys = function (keys, source) {
        var list = Array.isArray(keys) ? keys : (keys ? [keys] : []);
        if (!list.length) return;
        for (var i = 0; i < list.length; i++) {
            var k = String(list[i]);
            this._ghostKeys[k] = true;
            delete this._hiddenKeys[k];
        }
        this._notifyChanged(source || 'ghost');
    };

    VisibilityStore.prototype.unghostKeys = function (keys, source) {
        var list = Array.isArray(keys) ? keys : (keys ? [keys] : []);
        if (!list.length) return;
        for (var i = 0; i < list.length; i++) {
            delete this._ghostKeys[String(list[i])];
        }
        this._notifyChanged(source || 'unghost');
    };

    VisibilityStore.prototype.resetVisibility = function (source) {
        this._hiddenKeys = {};
        this._isolatedKeys = null;
        this._ghostKeys = {};
        this._storeyVisibility = {};
        this._systemVisibility = {};
        this._notifyChanged(source || 'reset');
    };

    VisibilityStore.prototype.restoreState = function (state, source) {
        function keys(values) {
            var result = {};
            (values || []).forEach(function (key) { result[key] = true; });
            return result;
        }
        this._hiddenKeys = keys(state.hiddenKeys);
        this._isolatedKeys = state.isolatedKeys ? keys(state.isolatedKeys) : null;
        this._ghostKeys = keys(state.ghostKeys);
        this._storeyVisibility = Object.assign({}, state.storeyVisibility);
        this._systemVisibility = Object.assign({}, state.systemVisibility);
        this._notifyChanged(source || 'restore');
    };

    VisibilityStore.prototype.setStoreyVisibility = function (storey, isVisible, source) {
        if (!storey) return;
        this._storeyVisibility[storey] = !!isVisible;
        this._notifyChanged(source || 'storey');
    };

    VisibilityStore.prototype.setSystemVisibility = function (system, isVisible, source) {
        if (!system) return;
        this._systemVisibility[system] = !!isVisible;
        this._notifyChanged(source || 'system');
    };

    VisibilityStore.prototype.isKeyVisible = function (key, metadata) {
        if (!key) return true;
        if (this._hiddenKeys[key]) return false;
        if (this._isolatedKeys && !this._isolatedKeys[key]) return false;

        if (metadata) {
            if (metadata.storey && this._storeyVisibility[metadata.storey] === false) {
                return false;
            }
            if (metadata.systemNames && metadata.systemNames.length) {
                var hasVisibleSystem = false;
                var anySystemConfigured = false;
                for (var i = 0; i < metadata.systemNames.length; i++) {
                    var sys = metadata.systemNames[i];
                    if (this._systemVisibility[sys] !== undefined) {
                        anySystemConfigured = true;
                        if (this._systemVisibility[sys] === true) {
                            hasVisibleSystem = true;
                            break;
                        }
                    }
                }
                if (anySystemConfigured && !hasVisibleSystem) return false;
            }
        }
        return true;
    };

    VisibilityStore.prototype.isKeyGhosted = function (key) {
        if (!key) return false;
        return !!this._ghostKeys[key];
    };

    VisibilityStore.prototype.getState = function () {
        return {
            hiddenKeys: Object.keys(this._hiddenKeys),
            isolatedKeys: this._isolatedKeys ? Object.keys(this._isolatedKeys) : null,
            ghostKeys: Object.keys(this._ghostKeys),
            storeyVisibility: Object.assign({}, this._storeyVisibility),
            systemVisibility: Object.assign({}, this._systemVisibility)
        };
    };

    VisibilityStore.prototype.subscribe = function (listener) {
        if (typeof listener !== 'function') return function () {};
        this._listeners.push(listener);
        var self = this;
        return function () {
            self._listeners = self._listeners.filter(function (l) { return l !== listener; });
        };
    };

    VisibilityStore.prototype._notifyChanged = function (source) {
        var state = this.getState();
        var payload = {
            state: state,
            source: source || 'unknown'
        };

        for (var i = 0; i < this._listeners.length; i++) {
            try {
                this._listeners[i](payload);
            } catch (err) {
                console.error('[VisibilityStore] Listener error:', err);
            }
        }

        if (events && WORKBENCH_EVENTS) {
            events.emit(WORKBENCH_EVENTS.VISIBILITY_CHANGED, payload);
        }
    };

    var defaultVisibilityStore = new VisibilityStore();

    root.IfcFds.workbench.state.VisibilityStore = VisibilityStore;
    root.IfcFds.workbench.state.visibilityStore = defaultVisibilityStore;

})(typeof window !== 'undefined' ? window : globalThis);
