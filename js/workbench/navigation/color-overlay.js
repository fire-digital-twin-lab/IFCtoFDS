/**
 * Color Overlay Engine for IFCtoFDS Research Workbench.
 * Provides dynamic visual QA auditing by recoloring 3D building elements
 * according to Mapping State, Verification Status, IFC Category, MEP System, or Storey.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.navigation = root.IfcFds.workbench.navigation || {};

    var normalizeEntityDescriptor = root.IfcFds.workbench.normalizeEntityDescriptor;
    var createEntityKey = root.IfcFds.workbench.createEntityKey;

    var COLOR_PALETTES = {
        mapping: {
            OBST: 0x10b981,        // Solid conversion (Green)
            GEOM: 0x059669,        // Surface conversion (Emerald)
            REFERENCE: 0x3b82f6,   // Reference only (Blue)
            EXCLUDE: 0x64748b,     // Excluded from simulation (Gray)
            FAILED: 0xef4444       // Unsupported / Failed (Red)
        },
        verification: {
            PASS: 0x10b981,        // Verified (Green)
            WARNING: 0xf59e0b,     // Minor tolerance warning (Amber)
            INCONCLUSIVE: 0xf97316,// Inconclusive / Missing evidence (Orange)
            FAIL: 0xef4444,        // Acceptance gate failure (Red)
            NOT_RUN: 0x64748b      // Not evaluated (Slate)
        },
        ifcType: {
            structure: 0x94a3b8,   // Wall, Slab, Beam, Column
            fills: 0x38bdf8,       // Door, Window
            mep: 0xec4899,         // Duct, Pipe, Fan, Terminal
            space: 0xa7f3d0,       // IfcSpace
            other: 0xc084fc        // Furniture, Proxy
        },
        mep: {
            suppression: 0xef4444, // Sprinkler / Fire (Red)
            exhaust: 0xf97316,     // Smoke Extract (Orange)
            ventilation: 0x06b6d4, // Supply Air (Cyan)
            plumbing: 0x3b82f6,    // Water / Waste (Blue)
            other: 0x8b5cf6        // Other MEP (Violet)
        }
    };

    function hashStringToColor(str) {
        var hash = 0;
        for (var i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
        }
        var h = Math.abs(hash) % 360;
        return new THREE.Color('hsl(' + h + ', 65%, 55%)').getHex();
    }

    function ColorOverlayEngine(viewerInstance) {
        this.viewer = viewerInstance || null;
        this.currentMode = 'mapping';
        this._storeyColorMap = {};
    }

    ColorOverlayEngine.prototype.setViewer = function (viewer) {
        this.viewer = viewer;
    };

    ColorOverlayEngine.prototype.applyColorMode = function (mode) {
        this.currentMode = mode || 'mapping';
        if (!this.viewer) return;

        var self = this;
        var counts = {};

        function processGroup(group) {
            if (!group) return;
            group.traverse(function (node) {
                if (!node.isMesh || !node.material || !node.material.color) return;
                if (!node.userData || !node.userData.type) return;

                // Save initial material color once
                if (!node._origColor) {
                    node._origColor = node.material.color.clone();
                }

                if (self.currentMode === 'original') {
                    node.material.color.copy(node._origColor);
                    return;
                }

                var desc = normalizeEntityDescriptor(node.userData);
                var targetHex = self._getColorForDescriptor(desc, self.currentMode);
                if (targetHex !== null) {
                    node.material.color.setHex(targetHex);
                } else {
                    node.material.color.copy(node._origColor);
                }
            });
        }

        processGroup(this.viewer.fdsGroup);
        processGroup(this.viewer.ifcGroup);

        this.updateLegend(this.currentMode);
    };

    ColorOverlayEngine.prototype._getColorForDescriptor = function (desc, mode) {
        if (!desc) return null;

        if (mode === 'mapping') {
            var role = (desc.simulationRole || '').toUpperCase();
            if (role === 'EXCLUDE') return COLOR_PALETTES.mapping.EXCLUDE;
            if (role === 'REFERENCE_GEOMETRY') return COLOR_PALETTES.mapping.REFERENCE;
            var strat = (desc.mappingStrategy || '').toUpperCase();
            if (strat.indexOf('OBST') >= 0) return COLOR_PALETTES.mapping.OBST;
            if (strat.indexOf('GEOM') >= 0) return COLOR_PALETTES.mapping.GEOM;
            return COLOR_PALETTES.mapping.OBST;
        }

        if (mode === 'verification') {
            var raw = desc.raw || {};
            var status = (raw.review_status || raw.verification_status || 'NOT_RUN').toUpperCase();
            if (status.indexOf('PASS') >= 0 || status === 'MATCHED') return COLOR_PALETTES.verification.PASS;
            if (status.indexOf('WARN') >= 0) return COLOR_PALETTES.verification.WARNING;
            if (status.indexOf('INCON') >= 0) return COLOR_PALETTES.verification.INCONCLUSIVE;
            if (status.indexOf('FAIL') >= 0 || status === 'REJECTED') return COLOR_PALETTES.verification.FAIL;
            return COLOR_PALETTES.verification.NOT_RUN;
        }

        if (mode === 'ifc-type') {
            var cat = desc.category || 'other';
            if (COLOR_PALETTES.ifcType[cat]) return COLOR_PALETTES.ifcType[cat];
            var type = (desc.ifcType || '').toUpperCase();
            if (type.indexOf('WALL') >= 0 || type.indexOf('SLAB') >= 0 || type.indexOf('COLUMN') >= 0 || type.indexOf('BEAM') >= 0) {
                return COLOR_PALETTES.ifcType.structure;
            }
            if (type.indexOf('DOOR') >= 0 || type.indexOf('WINDOW') >= 0) {
                return COLOR_PALETTES.ifcType.fills;
            }
            if (type.indexOf('FLOW') >= 0 || type.indexOf('DUCT') >= 0 || type.indexOf('PIPE') >= 0 || type.indexOf('FAN') >= 0) {
                return COLOR_PALETTES.ifcType.mep;
            }
            if (type.indexOf('SPACE') >= 0) return COLOR_PALETTES.ifcType.space;
            return COLOR_PALETTES.ifcType.other;
        }

        if (mode === 'mep') {
            var mepCat = (desc.mepCategory || '').toLowerCase();
            var sys = (desc.systemNames || []).join(' ').toLowerCase();
            if (mepCat.indexOf('suppress') >= 0 || sys.indexOf('sprinkler') >= 0 || sys.indexOf('fire') >= 0) {
                return COLOR_PALETTES.mep.suppression;
            }
            if (mepCat.indexOf('exhaust') >= 0 || sys.indexOf('smoke') >= 0 || sys.indexOf('exhaust') >= 0) {
                return COLOR_PALETTES.mep.exhaust;
            }
            if (mepCat.indexOf('vent') >= 0 || sys.indexOf('supply') >= 0 || sys.indexOf('air') >= 0) {
                return COLOR_PALETTES.mep.ventilation;
            }
            if (mepCat.indexOf('pipe') >= 0 || sys.indexOf('water') >= 0 || sys.indexOf('plumb') >= 0) {
                return COLOR_PALETTES.mep.plumbing;
            }
            return COLOR_PALETTES.mep.other;
        }

        if (mode === 'storey') {
            var storey = desc.storey || 'Unassigned';
            if (!this._storeyColorMap[storey]) {
                this._storeyColorMap[storey] = hashStringToColor(storey);
            }
            return this._storeyColorMap[storey];
        }

        return null;
    };

    ColorOverlayEngine.prototype.updateLegend = function (mode) {
        var container = document.getElementById('legend-swatches');
        if (!container) return;
        container.innerHTML = '';

        var items = [];
        if (mode === 'mapping') {
            items = [
                ['#10b981', 'OBST Solid'],
                ['#059669', 'GEOM Solid'],
                ['#3b82f6', 'Reference'],
                ['#64748b', 'Excluded']
            ];
        } else if (mode === 'verification') {
            items = [
                ['#10b981', 'PASS'],
                ['#f59e0b', 'WARNING'],
                ['#f97316', 'INCONCLUSIVE'],
                ['#ef4444', 'FAIL / REJECT']
            ];
        } else if (mode === 'ifc-type') {
            items = [
                ['#94a3b8', 'Structure'],
                ['#38bdf8', 'Doors / Windows'],
                ['#ec4899', 'MEP Distribution'],
                ['#a7f3d0', 'Spaces']
            ];
        } else if (mode === 'mep') {
            items = [
                ['#ef4444', 'Fire Suppression'],
                ['#f97316', 'Smoke Extract'],
                ['#06b6d4', 'Ventilation'],
                ['#3b82f6', 'Plumbing']
            ];
        } else if (mode === 'storey') {
            items = [
                ['#3b82f6', 'Storey Colors']
            ];
        } else {
            items = [
                ['#94a3b8', 'Default Materials']
            ];
        }

        items.forEach(function (pair) {
            var wrap = document.createElement('div');
            wrap.className = 'legend-swatch-item';
            var swatch = document.createElement('span');
            swatch.className = 'swatch-color';
            swatch.style.background = pair[0];
            var label = document.createElement('span');
            label.textContent = pair[1];
            wrap.appendChild(swatch);
            wrap.appendChild(label);
            container.appendChild(wrap);
        });
    };

    ColorOverlayEngine.prototype.init = function (selectElementId, viewerInstance) {
        if (viewerInstance) this.viewer = viewerInstance;
        var select = document.getElementById(selectElementId || 'color-mode-select');
        var self = this;
        if (select) {
            select.addEventListener('change', function () {
                self.applyColorMode(select.value);
            });
        }
    };

    var defaultColorOverlay = new ColorOverlayEngine();

    root.IfcFds.workbench.navigation.ColorOverlayEngine = ColorOverlayEngine;
    root.IfcFds.workbench.navigation.colorOverlay = defaultColorOverlay;

})(typeof window !== 'undefined' ? window : globalThis);
