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
        this._byScopedStepId = {}; // sourceId:stepId -> descriptor
        this._byScopedGlobalId = {}; // sourceId:globalId -> descriptor
        this._byStepId = {}; // stepId (str) -> Array of descriptors
        this._byGlobalId = {}; // globalId (str) -> Array of descriptors
        this._aliasMap = {}; // aliasKey -> canonicalKey
        this._listeners = [];
    }

    SelectionStore.prototype.indexElements = function (elements, defaultSourceId) {
        if (!elements) return;
        var list = Array.isArray(elements) ? elements : Object.values(elements);
        for (var i = 0; i < list.length; i++) {
            var item = list[i];
            if (!item) continue;
            // Bind identity once on the scene input, before either tree or mesh is built.
            var raw = item.raw || {};
            if (!item.sourceId && !item.source_id && !raw.source_id && !(item.ifcSource && (item.ifcSource.sourceId || item.ifcSource.fileName))) {
                item.sourceId = defaultSourceId || 'ifc';
            }
            item.entityKey = createEntityKey(item);
            var desc = normalizeEntityDescriptor(item);
            if (!desc || !desc.entityKey) continue;
            this._entityIndex[desc.entityKey] = desc;

            var src = String(desc.sourceId || defaultSourceId || 'ifc');
            if (desc.stepId !== null && desc.stepId !== undefined) {
                var sKey = String(desc.stepId);
                this._byScopedStepId[src + ':' + sKey] = desc;
                if (!this._byStepId[sKey]) this._byStepId[sKey] = [];
                this._byStepId[sKey].push(desc);
            }
            if (desc.globalId) {
                var gKey = String(desc.globalId);
                this._byScopedGlobalId[src + ':' + gKey] = desc;
                if (!this._byGlobalId[gKey]) this._byGlobalId[gKey] = [];
                this._byGlobalId[gKey].push(desc);
            }
        }
        if (events && WORKBENCH_EVENTS) {
            events.emit(WORKBENCH_EVENTS.MODEL_INDEXED, {
                totalIndexed: Object.keys(this._entityIndex).length
            });
        }
    };

    SelectionStore.prototype.hydrateManifest = function (records, report) {
        if (!records || !records.length) return;
        var elementStatuses = (report && report.element_statuses) || {};
        for (var i = 0; i < records.length; i++) {
            var rec = records[i];
            if (!rec) continue;
            var canonicalKey = rec.entity_key;
            var recSrc = rec.source_id ? String(rec.source_id) : null;
            var stepId = rec.step_id !== undefined && rec.step_id !== null ? String(rec.step_id) : null;
            var globalId = rec.global_id ? String(rec.global_id) : null;

            var desc = this._entityIndex[canonicalKey] ||
                (this._aliasMap[canonicalKey] && this._entityIndex[this._aliasMap[canonicalKey]]) ||
                (recSrc && stepId && this._byScopedStepId[recSrc + ':' + stepId]) ||
                (recSrc && globalId && this._byScopedGlobalId[recSrc + ':' + globalId]);

            if (!desc && stepId && this._byStepId[stepId]) {
                if (this._byStepId[stepId].length === 1) {
                    desc = this._byStepId[stepId][0];
                } else {
                    var matchS = this._byStepId[stepId].find(function (d) {
                        return d.sourceId && String(d.sourceId) === recSrc;
                    });
                    if (matchS) desc = matchS;
                }
            }
            if (!desc && globalId && this._byGlobalId[globalId]) {
                if (this._byGlobalId[globalId].length === 1) {
                    desc = this._byGlobalId[globalId][0];
                } else {
                    var matchG = this._byGlobalId[globalId].find(function (d) {
                        return d.sourceId && String(d.sourceId) === recSrc;
                    });
                    if (matchG) desc = matchG;
                }
            }

            if (desc) {
                desc.canonicalKey = canonicalKey;
                desc.simulationRole = rec.simulation_role || desc.simulationRole;
                desc.mappingStrategy = rec.mapping_strategy || desc.mappingStrategy;
                desc.representation = rec.fds_representation || desc.representation;
                desc.boundaryTreatment = rec.boundary_treatment || desc.boundaryTreatment;
                if (rec.review_status) {
                    desc.reviewStatus = rec.review_status;
                    if (!desc.raw) desc.raw = {};
                    desc.raw.review_status = rec.review_status;
                }
                desc.fdsPrimitiveIds = rec.fds_primitive_ids || desc.fdsPrimitiveIds;
                if (elementStatuses[canonicalKey]) {
                    desc.verificationStatus = elementStatuses[canonicalKey];
                    if (!desc.raw) desc.raw = {};
                    desc.raw.verification_status = elementStatuses[canonicalKey];
                }
                if (rec.mep_data) {
                    desc.mepCategory = rec.mep_data.category || desc.mepCategory;
                    desc.systemNames = rec.mep_data.system_names || desc.systemNames;
                    desc.systemIds = rec.mep_data.system_ids || desc.systemIds;
                    desc.portsCount = (rec.mep_data.ports && rec.mep_data.ports.length) || desc.portsCount;
                }
                this._aliasMap[canonicalKey] = desc.entityKey;
                this._aliasMap[desc.entityKey] = canonicalKey;
                this._entityIndex[canonicalKey] = desc;
            } else {
                var rawRec = Object.assign({}, rec);
                if (elementStatuses[canonicalKey]) {
                    rawRec.verification_status = elementStatuses[canonicalKey];
                }
                var newDesc = normalizeEntityDescriptor({
                    entityKey: canonicalKey,
                    sourceId: rec.source_id,
                    globalId: rec.global_id,
                    stepId: rec.step_id,
                    ifcType: rec.ifc_type,
                    name: rec.name || (rec.ifc_type + ' #' + rec.step_id),
                    storey: rec.storey,
                    simulationRole: rec.simulation_role,
                    mappingStrategy: rec.mapping_strategy,
                    representation: rec.fds_representation,
                    boundaryTreatment: rec.boundary_treatment,
                    reviewStatus: rec.review_status || 'NOT_REQUIRED',
                    verificationStatus: elementStatuses[canonicalKey] || 'NOT_RUN',
                    raw: rawRec
                });
                if (newDesc && newDesc.entityKey) {
                    this._entityIndex[newDesc.entityKey] = newDesc;
                    var nSrc = String(newDesc.sourceId || recSrc || 'ifc');
                    if (newDesc.stepId !== null && newDesc.stepId !== undefined) {
                        var nStep = String(newDesc.stepId);
                        this._byScopedStepId[nSrc + ':' + nStep] = newDesc;
                        if (!this._byStepId[nStep]) this._byStepId[nStep] = [];
                        this._byStepId[nStep].push(newDesc);
                    }
                    if (newDesc.globalId) {
                        var nGlob = String(newDesc.globalId);
                        this._byScopedGlobalId[nSrc + ':' + nGlob] = newDesc;
                        if (!this._byGlobalId[nGlob]) this._byGlobalId[nGlob] = [];
                        this._byGlobalId[nGlob].push(newDesc);
                    }
                }
            }
        }
        if (events && WORKBENCH_EVENTS) {
            events.emit(WORKBENCH_EVENTS.MODEL_INDEXED, {
                totalIndexed: this.getAllDescriptors().length,
                hydrated: true
            });
        }
    };

    SelectionStore.prototype.clearIndex = function () {
        this._entityIndex = {};
        this._byScopedStepId = {};
        this._byScopedGlobalId = {};
        this._byStepId = {};
        this._byGlobalId = {};
        this._aliasMap = {};
        this.clearSelection('system');
        if (events && WORKBENCH_EVENTS) events.emit(WORKBENCH_EVENTS.MODEL_INDEXED, {totalIndexed: 0});
    };

    SelectionStore.prototype.getDescriptor = function (key) {
        if (!key) return null;
        var k = String(key);
        if (this._entityIndex[k]) return this._entityIndex[k];
        if (this._aliasMap[k] && this._entityIndex[this._aliasMap[k]]) return this._entityIndex[this._aliasMap[k]];
        var colonIdx = k.indexOf(':');
        if (colonIdx !== -1) {
            var src = k.substring(0, colonIdx);
            var idPart = k.substring(colonIdx + 1);
            var qualified = src + ':' + idPart;
            if (this._byScopedStepId[qualified]) return this._byScopedStepId[qualified];
            if (this._byScopedGlobalId[qualified]) return this._byScopedGlobalId[qualified];
            if (this._byGlobalId[idPart]) {
                var matchG = this._byGlobalId[idPart].find(function (d) {
                    return !d.sourceId || String(d.sourceId) === src;
                });
                if (matchG) return matchG;
            }
            if (this._byStepId[idPart]) {
                var matchS = this._byStepId[idPart].find(function (d) {
                    return !d.sourceId || String(d.sourceId) === src;
                });
                if (matchS) return matchS;
            }
        } else {
            var defaultKey = 'ifc:' + k;
            if (this._byScopedStepId[defaultKey]) return this._byScopedStepId[defaultKey];
            if (this._byScopedGlobalId[defaultKey]) return this._byScopedGlobalId[defaultKey];
            if (this._byStepId[k] && this._byStepId[k].length) return this._byStepId[k][0];
            if (this._byGlobalId[k] && this._byGlobalId[k].length) return this._byGlobalId[k][0];
        }
        return null;
    };

    SelectionStore.prototype.getAllDescriptors = function () {
        var self = this;
        var seen = {};
        var unique = [];
        var keys = Object.keys(this._entityIndex);
        for (var i = 0; i < keys.length; i++) {
            var desc = self._entityIndex[keys[i]];
            if (!desc) continue;
            var primary = desc.entityKey || keys[i];
            if (!seen[primary]) {
                seen[primary] = true;
                unique.push(desc);
            }
        }
        return unique;
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
