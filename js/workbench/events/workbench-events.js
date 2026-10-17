/**
 * Event Hub and Entity Identity Contract for IFCtoFDS Research Workbench.
 * Encapsulates strongly-typed workbench events and deterministic EntityKey generation.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};

    var WORKBENCH_EVENTS = {
        SELECTION_CHANGED: 'workbench:selection:changed',
        HOVER_CHANGED: 'workbench:hover:changed',
        VISIBILITY_CHANGED: 'workbench:visibility:changed',
        INSPECTOR_TAB_CHANGED: 'workbench:inspector:tab_changed',
        CAMERA_COMMAND: 'workbench:camera:command',
        SCENARIO_STATE_CHANGED: 'workbench:scenario:changed',
        MODEL_INDEXED: 'workbench:model:indexed',
        MODE_CHANGED: 'workbench:mode:changed'
    };

    function EventBus() {
        this._handlers = {};
    }

    EventBus.prototype.on = function (event, handler) {
        if (typeof handler !== 'function') return function () {};
        if (!this._handlers[event]) {
            this._handlers[event] = [];
        }
        this._handlers[event].push(handler);
        var self = this;
        return function () {
            self.off(event, handler);
        };
    };

    EventBus.prototype.once = function (event, handler) {
        var self = this;
        var wrapper = function (payload) {
            self.off(event, wrapper);
            handler(payload);
        };
        return this.on(event, wrapper);
    };

    EventBus.prototype.off = function (event, handler) {
        if (!this._handlers[event]) return;
        this._handlers[event] = this._handlers[event].filter(function (h) {
            return h !== handler;
        });
    };

    EventBus.prototype.emit = function (event, payload) {
        var list = this._handlers[event];
        if (!list || !list.length) return;
        var copy = list.slice();
        for (var i = 0; i < copy.length; i++) {
            try {
                copy[i](payload);
            } catch (err) {
                console.error('[WorkbenchEventBus] Error in handler for ' + event + ':', err);
            }
        }
    };

    /**
     * Deterministic EntityKey generation: source_id + ':' + (globalId || stepId || id)
     */
    function createEntityKey(item) {
        if (!item) return '';
        var raw = item.raw || {};
        if (item.entityKey) return String(item.entityKey);
        if (item.entity_key) return String(item.entity_key);
        if (raw.entity_key) return String(raw.entity_key);

        var sourceId = item.sourceId || item.source_id || raw.source_id ||
            (item.ifcSource && item.ifcSource.fileName) ||
            'ifc';

        var primaryId = item.globalId ||
            raw.global_id ||
            raw.GlobalId ||
            item.stepId ||
            raw.step_id ||
            item.expressID ||
            (item.ifcSource && (item.ifcSource.globalId || item.ifcSource.stepId)) ||
            item.id || item.name ||
            'unknown';

        return String(sourceId) + ':' + String(primaryId);
    }

    /**
     * Normalizes an IFC or FDS item into a standard Entity Descriptor.
     */
    function normalizeEntityDescriptor(item) {
        if (!item) return null;
        var raw = item.raw || {};
        var entityKey = createEntityKey(item);
        var ifcType = item.ifcType || raw.ifc_type || item.type || 'UNKNOWN';

        var globalId = item.globalId || raw.global_id || raw.GlobalId || null;
        var stepId = item.stepId || raw.step_id || item.expressID || item.id || null;
        var sourceId = item.sourceId || item.source_id || raw.source_id || (item.ifcSource && item.ifcSource.fileName) || 'ifc';

        var mepData = raw.mep_data || {};
        var ports = raw.ports || mepData.ports || [];
        var systemNames = raw.system_names || mepData.system_names || [];
        var systemIds = raw.system_ids || mepData.system_ids || [];

        return {
            entityKey: entityKey,
            sourceId: sourceId,
            globalId: globalId,
            stepId: stepId,
            ifcType: ifcType,
            category: item.ifcCategory || item.category || 'other',
            name: item.name || (ifcType + (stepId ? ' #' + stepId : '')),
            storey: raw.storey || item.storey || null,
            building: raw.building_id || null,
            bounds: item.bounds || raw.bounding_box || null,
            xb: item.xb || raw.xb || null,
            simulationRole: raw.simulation_role || item.simulationRole || item.fdsRole || 'UNKNOWN',
            mappingStrategy: raw.mapping_strategy || item.mappingStrategy || 'NONE',
            representation: raw.fds_representation || item.representation || item.type || 'NONE',
            boundaryTreatment: raw.boundary_treatment || 'NOT_APPLICABLE',
            reviewStatus: raw.review_status || 'NOT_REQUIRED',
            mepCategory: raw.mep_category || mepData.category || null,
            systemNames: systemNames,
            systemIds: systemIds,
            portsCount: ports.length,
            operationalStatus: raw.operational_status || 'NOT_APPLICABLE',
            raw: raw,
            sourceItem: item
        };
    }

    var defaultEvents = new EventBus();

    root.IfcFds.workbench.WORKBENCH_EVENTS = WORKBENCH_EVENTS;
    root.IfcFds.workbench.EventBus = EventBus;
    root.IfcFds.workbench.events = defaultEvents;
    root.IfcFds.workbench.createEntityKey = createEntityKey;
    root.IfcFds.workbench.normalizeEntityDescriptor = normalizeEntityDescriptor;

})(typeof window !== 'undefined' ? window : globalThis);
