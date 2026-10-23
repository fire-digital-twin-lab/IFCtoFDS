/**
 * Scenario Store for IFCtoFDS Research Workbench.
 * Encapsulates simulation scenario specifications (Fire sources, Door states,
 * Operational HVAC parameters, and Sensors) without mutating the immutable MappingBundle.
 * Adheres strictly to Principle A3: "Scenario không được mutate MappingBundle".
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.state = root.IfcFds.workbench.state || {};

    var events = root.IfcFds.workbench.events;
    var WORKBENCH_EVENTS = root.IfcFds.workbench.WORKBENCH_EVENTS;

    function ScenarioStore() {
        this._mappingBundleSha = null;
        this._baseMappingVerified = false;
        this._status = 'DRAFT'; // DRAFT, BASE_MAPPING_VALID, CONFIGURING, SCENARIO_VALIDATED, STALE
        this._fireSources = [];
        this._openingStates = {}; // entityKey -> { state: 'CLOSED'|'OPEN', eventTime: number|null }
        this._hvacOperations = {}; // entityKey -> { operational: bool, flowRateM3s, activation, activationTime }
        this._devices = []; // Array of { id, name, type, position: [x,y,z], quantity, setpoint }
        this._listeners = [];
    }

    ScenarioStore.prototype.setBaseMapping = function (sha) {
        if (!sha) {
            this.setInvalidBaseMapping(null, 'Missing verified mapping hash');
            return;
        }
        if (this._mappingBundleSha && this._mappingBundleSha !== sha) {
            this._status = 'STALE';
        } else if (!this._mappingBundleSha || this._status === 'INVALID_BASE_MAPPING') {
            this._status = 'BASE_MAPPING_VALID';
        }
        this._mappingBundleSha = sha || null;
        this._baseMappingVerified = true;
        this._invalidationReason = null;
        this._notifyChanged('baseMapping');
    };

    ScenarioStore.prototype.setInvalidBaseMapping = function (sha, mappingStatus, reason) {
        this._mappingBundleSha = sha || null;
        this._baseMappingVerified = false;
        this._status = 'INVALID_BASE_MAPPING';
        this._invalidationReason = reason || mappingStatus || 'Mapping unverified or rejected';
        this._notifyChanged('baseMapping');
    };

    ScenarioStore.prototype.isSimulationPermitted = function () {
        return !!this._mappingBundleSha && this._baseMappingVerified &&
            (this._status === 'BASE_MAPPING_VALID' || this._status === 'SCENARIO_VALIDATED');
    };

    ScenarioStore.prototype.getStatus = function () {
        return this._status;
    };

    ScenarioStore.prototype.reset = function () {
        this._mappingBundleSha = null;
        this._baseMappingVerified = false;
        this._invalidationReason = null;
        this._status = 'DRAFT';
        this._fireSources = [];
        this._openingStates = {};
        this._hvacOperations = {};
        this._devices = [];
        this._notifyChanged('reset');
    };

    ScenarioStore.prototype.setStatus = function (status) {
        if ((status === 'BASE_MAPPING_VALID' || status === 'SCENARIO_VALIDATED') && !this._baseMappingVerified) {
            this.setInvalidBaseMapping(this._mappingBundleSha, 'Mapping has not been independently verified');
            return;
        }
        this._status = status;
        this._notifyChanged('status');
    };

    ScenarioStore.prototype.getFireSources = function () {
        return this._fireSources.slice();
    };

    ScenarioStore.prototype.addFireSource = function (fire) {
        if (!fire) return;
        var id = fire.id || ('FIRE_' + (this._fireSources.length + 1));
        var item = Object.assign({
            id: id,
            name: fire.name || ('Fire Source ' + id),
            position: null,
            type: null,
            peakHrrKw: null,
            curve: null,
            fuel: null
        }, fire);
        this._fireSources.push(item);
        this._status = 'CONFIGURING';
        this._notifyChanged('addFire');
        return item;
    };

    ScenarioStore.prototype.removeFireSource = function (id) {
        this._fireSources = this._fireSources.filter(function (f) { return f.id !== id; });
        this._notifyChanged('removeFire');
    };

    ScenarioStore.prototype.getOpeningState = function (entityKey) {
        return this._openingStates[entityKey] || null;
    };

    ScenarioStore.prototype.setOpeningState = function (entityKey, state, eventTime) {
        if (!entityKey) return;
        this._openingStates[entityKey] = {
            state: state === 'OPEN' ? 'OPEN' : 'CLOSED',
            eventTime: typeof eventTime === 'number' ? eventTime : null
        };
        this._status = 'CONFIGURING';
        this._notifyChanged('openingState');
    };

    ScenarioStore.prototype.getHvacOperation = function (entityKey) {
        return this._hvacOperations[entityKey] || null;
    };

    ScenarioStore.prototype.configureHvac = function (entityKey, config) {
        if (!entityKey) return;
        config = config || {};
        if (config.flowRateM3s !== undefined && config.flowRateM3s !== null &&
            (typeof config.flowRateM3s !== 'number' || !isFinite(config.flowRateM3s) || config.flowRateM3s <= 0)) {
            throw new Error('HVAC volume flow must be a finite positive number in m³/s.');
        }
        this._hvacOperations[entityKey] = Object.assign({
            operational: false,
            flowRateM3s: null,
            activation: null,
            activationTime: null,
            provenance: null,
            validationStatus: 'INCONCLUSIVE'
        }, config, {validationStatus: 'INCONCLUSIVE'});
        this._status = 'CONFIGURING';
        this._notifyChanged('hvacOperation');
    };

    ScenarioStore.prototype.getDevices = function () {
        return this._devices.slice();
    };

    ScenarioStore.prototype.addDevice = function (dev) {
        if (!dev) return;
        var id = dev.id || ('DEVC_' + (this._devices.length + 1));
        var item = Object.assign({
            id: id,
            name: dev.name || id,
            type: dev.type || 'TEMPERATURE',
            position: dev.position || [0, 0, 0],
            quantity: dev.quantity || 'TEMPERATURE',
            setpoint: dev.setpoint || null
        }, dev);
        this._devices.push(item);
        this._status = 'CONFIGURING';
        this._notifyChanged('addDevice');
        return item;
    };

    ScenarioStore.prototype.removeDevice = function (id) {
        this._devices = this._devices.filter(function (d) { return d.id !== id; });
        this._notifyChanged('removeDevice');
    };

    ScenarioStore.prototype.getScenarioSpec = function () {
        return {
            mappingBundleSha: this._mappingBundleSha,
            status: this._status,
            fireSources: this.getFireSources(),
            openingStates: Object.assign({}, this._openingStates),
            hvacOperations: Object.assign({}, this._hvacOperations),
            devices: this.getDevices()
        };
    };

    ScenarioStore.prototype.subscribe = function (listener) {
        if (typeof listener !== 'function') return function () {};
        this._listeners.push(listener);
        var self = this;
        return function () {
            self._listeners = self._listeners.filter(function (l) { return l !== listener; });
        };
    };

    ScenarioStore.prototype._notifyChanged = function (action) {
        var spec = this.getScenarioSpec();
        var payload = {
            spec: spec,
            action: action || 'unknown'
        };

        for (var i = 0; i < this._listeners.length; i++) {
            try {
                this._listeners[i](payload);
            } catch (err) {
                console.error('[ScenarioStore] Listener error:', err);
            }
        }

        if (events && WORKBENCH_EVENTS) {
            events.emit(WORKBENCH_EVENTS.SCENARIO_STATE_CHANGED, payload);
        }
    };

    var defaultScenarioStore = new ScenarioStore();

    root.IfcFds.workbench.state.ScenarioStore = ScenarioStore;
    root.IfcFds.workbench.state.scenarioStore = defaultScenarioStore;

})(typeof window !== 'undefined' ? window : globalThis);
