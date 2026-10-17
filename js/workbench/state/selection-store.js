/**
 * Selection Store for IFCtoFDS Research Workbench.
 * Manages deterministic EntityKey selections, provides O(1) entity lookups,
 * and synchronizes selection state across the 3D Viewer, Model Tree, and Inspector.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.state = root.IfcFds.workbench.state || {};

    var normalizeEntityDescriptor = root.IfcFds.workbench.normalizeEntityDescriptor;
    var createEntityKey = root.IfcFds.workbench.createEntityKey;
    var events = root.IfcFds.workbench.events;
    var WORKBENCH_EVENTS = root.IfcFds.workbench.WORKBENCH_EVENTS;

    function SelectionStore() {
        this._selectedKeys = {}; // entityKey -> true
        this._selectedItems = []; // Array of descriptors
        this._entityIndex = {}; // entityKey -> descriptor
        this._listeners = [];
    }

    SelectionStore.prototype.indexElements = function (elements, defaultSourceId) {
        if (!elements) return;
        var list = Array.isArray(elements) ? elements : Object.values(elements);
        for (var i = 0; i < list.length; i++) {
            var item = list[i];
            if (!item) continue;
            var desc = normalizeEntityDescriptor(item);
            if (!desc || !desc.entityKey) continue;
            if (defaultSourceId && (!desc.sourceId || desc.sourceId === 'ifc')) {
                desc.sourceId = defaultSourceId;
                desc.entityKey = defaultSourceId + ':' + (desc.globalId || desc.stepId || desc.name);
            }
            this._entityIndex[desc.entityKey] = desc;
        }
        if (events && WORKBENCH_EVENTS) {
            events.emit(WORKBENCH_EVENTS.MODEL_INDEXED, {
                totalIndexed: Object.keys(this._entityIndex).length
            });
        }
    };

    SelectionStore.prototype.clearIndex = function () {
        this._entityIndex = {};
        this.clearSelection('system');
    };

    SelectionStore.prototype.getDescriptor = function (key) {
        if (!key) return null;
        return this._entityIndex[key] || null;
    };

    SelectionStore.prototype.getAllDescriptors = function () {
        var self = this;
        return Object.keys(this._entityIndex).map(function (k) {
            return self._entityIndex[k];
        });
    };

    SelectionStore.prototype.getSelection = function () {
        return this._selectedItems.slice();
    };

    SelectionStore.prototype.getSelectedKeys = function () {
        return Object.keys(this._selectedKeys);
    };

    SelectionStore.prototype.isSelected = function (keyOrItem) {
        if (!keyOrItem) return false;
        var key = typeof keyOrItem === 'string' ? keyOrItem : createEntityKey(keyOrItem);
        return !!this._selectedKeys[key];
    };

    SelectionStore.prototype.setSelection = function (itemsOrKeys, source) {
        var prevKeys = this.getSelectedKeys();
        this._selectedKeys = {};
        this._selectedItems = [];

        var list = Array.isArray(itemsOrKeys) ? itemsOrKeys : (itemsOrKeys ? [itemsOrKeys] : []);
        for (var i = 0; i < list.length; i++) {
            var entry = list[i];
            if (!entry) continue;
            var desc = null;
            if (typeof entry === 'string') {
                desc = this._entityIndex[entry] || { entityKey: entry, name: entry, ifcType: 'UNKNOWN' };
            } else {
                desc = normalizeEntityDescriptor(entry);
                if (desc && desc.entityKey && !this._entityIndex[desc.entityKey]) {
                    this._entityIndex[desc.entityKey] = desc;
                }
            }
            if (desc && desc.entityKey) {
                this._selectedKeys[desc.entityKey] = true;
                this._selectedItems.push(desc);
            }
        }

        this._notifyChanged(source, prevKeys);
    };

    SelectionStore.prototype.addSelection = function (itemsOrKeys, source) {
        var prevKeys = this.getSelectedKeys();
        var list = Array.isArray(itemsOrKeys) ? itemsOrKeys : (itemsOrKeys ? [itemsOrKeys] : []);
        for (var i = 0; i < list.length; i++) {
            var entry = list[i];
            if (!entry) continue;
            var desc = null;
            if (typeof entry === 'string') {
                desc = this._entityIndex[entry] || { entityKey: entry, name: entry, ifcType: 'UNKNOWN' };
            } else {
                desc = normalizeEntityDescriptor(entry);
            }
            if (desc && desc.entityKey && !this._selectedKeys[desc.entityKey]) {
                this._selectedKeys[desc.entityKey] = true;
                this._selectedItems.push(desc);
            }
        }
        this._notifyChanged(source, prevKeys);
    };

    SelectionStore.prototype.removeSelection = function (itemsOrKeys, source) {
        var prevKeys = this.getSelectedKeys();
        var list = Array.isArray(itemsOrKeys) ? itemsOrKeys : (itemsOrKeys ? [itemsOrKeys] : []);
        var removeMap = {};
        for (var i = 0; i < list.length; i++) {
            var key = typeof list[i] === 'string' ? list[i] : createEntityKey(list[i]);
            if (key) removeMap[key] = true;
        }

        for (var k in removeMap) {
            delete this._selectedKeys[k];
        }
        this._selectedItems = this._selectedItems.filter(function (item) {
            return !removeMap[item.entityKey];
        });

        this._notifyChanged(source, prevKeys);
    };

    SelectionStore.prototype.toggleSelection = function (itemOrKey, source) {
        if (!itemOrKey) return;
        var key = typeof itemOrKey === 'string' ? itemOrKey : createEntityKey(itemOrKey);
        if (this._selectedKeys[key]) {
            this.removeSelection([key], source);
        } else {
            this.addSelection([itemOrKey], source);
        }
    };

    SelectionStore.prototype.clearSelection = function (source) {
        if (!this.getSelectedKeys().length) return;
        var prevKeys = this.getSelectedKeys();
        this._selectedKeys = {};
        this._selectedItems = [];
        this._notifyChanged(source, prevKeys);
    };

    SelectionStore.prototype.subscribe = function (listener) {
        if (typeof listener !== 'function') return function () {};
        this._listeners.push(listener);
        var self = this;
        return function () {
            self._listeners = self._listeners.filter(function (l) { return l !== listener; });
        };
    };

    SelectionStore.prototype._notifyChanged = function (source, prevKeys) {
        var currentSelection = this.getSelection();
        var currentKeys = this.getSelectedKeys();
        var payload = {
            selection: currentSelection,
            keys: currentKeys,
            previousKeys: prevKeys || [],
            source: source || 'unknown'
        };

        for (var i = 0; i < this._listeners.length; i++) {
            try {
                this._listeners[i](payload);
            } catch (err) {
                console.error('[SelectionStore] Listener error:', err);
            }
        }

        if (events && WORKBENCH_EVENTS) {
            events.emit(WORKBENCH_EVENTS.SELECTION_CHANGED, payload);
        }
    };

    var defaultSelectionStore = new SelectionStore();

    root.IfcFds.workbench.state.SelectionStore = SelectionStore;
    root.IfcFds.workbench.state.selectionStore = defaultSelectionStore;

})(typeof window !== 'undefined' ? window : globalThis);
