(function (ns) {
    ns.app = ns.app || {};
    ns.app.createWorkbenchBindings = function (dependencies) {
    var life = ns.core.createLifecycle();
    function boundsForClipping() { return dependencies.boundsForClipping.apply(null, arguments); }
    function countConvertibleIfc() { return dependencies.countConvertibleIfc.apply(null, arguments); }
    function setupClippingForBounds() { return dependencies.setupClippingForBounds.apply(null, arguments); }
    function updateIfcMetrics() { return dependencies.updateIfcMetrics.apply(null, arguments); }

    var state = dependencies.state;
    var VIEW_KEY_TO_DIRECTION = dependencies.VIEW_KEY_TO_DIRECTION;
    var viewBus = dependencies.viewBus;
    function setExportEnabled() { return dependencies.setExportEnabled.apply(null, arguments); }
    function undoLastChange() { return dependencies.undoLastChange.apply(null, arguments); }
    function updateColorModeLegend() { return dependencies.updateColorModeLegend.apply(null, arguments); }
    function bindToggle(id, layer) {
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        var el = document.getElementById(id);
        if (!el) return;
        life.listen(el, 'change', function (event) {
            viewer.setLayerVisible(layer, event.target.checked);
        });
    }
    var bound = false;
    function bind() {
        if (bound) return;
        bound = true;
        var viewer = dependencies.getViewer();
        var els = dependencies.getElements();
        life.listen(window, 'keydown', function (event) {
            var key = event.key && event.key.toLowerCase();
            var tag = (event.target && event.target.tagName) || '';
            var typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
            if (key === 'z' && (event.ctrlKey || event.metaKey) && !event.shiftKey) {
                if (typing) return;
                if (viewBus.canUndo()) { event.preventDefault(); viewBus.undo(); return; }
                if (els.undoLast && !els.undoLast.disabled) {
                    event.preventDefault();
                    undoLastChange();
                }
                return;
            }
            // Number-key view shortcuts (mirrors ProfRino/fds-viewer). Skipped while typing
            // in inputs, walking, or with any non-Shift modifier held.
            if (typing) return;
            if (viewer.navigationMode === 'walk') return;
            if (event.ctrlKey || event.metaKey || event.altKey) return;

            // Arrow-key orbit/dolly: left/right yaw, up/down pitch; Shift + arrows dollies
            // or strafes. Mirrors ProfRino/fds-viewer's keyboard navigation.
            var arrowMap = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down' };
            if (arrowMap[event.key] && viewer.orbitByKey) {
                event.preventDefault();
                viewer.orbitByKey(arrowMap[event.key], { shift: event.shiftKey });
                return;
            }

            if (event.shiftKey) return;
            var viewKey = VIEW_KEY_TO_DIRECTION[event.key];
            if (viewKey) {
                event.preventDefault();
                viewer.setView(viewKey);
            }
        });

        Array.prototype.forEach.call(document.querySelectorAll('[data-view-mode]'), function (button) {
            life.listen(button, 'click', function () {
                Array.prototype.forEach.call(document.querySelectorAll('[data-view-mode]'), function (other) {
                    other.classList.toggle('active', other === button);
                });
                viewer.setViewMode(button.getAttribute('data-view-mode'));
            });
        });

        life.listen(els.fdsOpacity, 'input', function () {
            viewer.setFdsOpacity(Number(els.fdsOpacity.value));
        });

        life.listen(els.ifcOpacity, 'input', function () {
            viewer.setIfcOpacity(Number(els.ifcOpacity.value));
        });

        [els.includeFillSolids, els.includeReviewSolids].forEach(function (input) {
            life.listen(input, 'change', function () {
                updateIfcMetrics(state.ifcModel);
                setExportEnabled(countConvertibleIfc(state.ifcModel) > 0);
            });
        });

        if (els.showIfcEdges) {
            life.listen(els.showIfcEdges, 'change', function (event) {
                viewer.setIfcEdgesVisible(event.target.checked);
            });
        }
        bindToggle('show-grid', 'groundGrid');
        bindToggle('show-obst', 'obsts');
        bindToggle('show-hole', 'holes');
        bindToggle('show-geom', 'geoms');
        if (els.showStructure) {
            life.listen(els.showStructure, 'change', function (event) {
                viewer.setIfcCategoryVisible('structure', event.target.checked);
            });
        }
        if (els.showFills) {
            life.listen(els.showFills, 'change', function (event) {
                viewer.setIfcCategoryVisible('fills', event.target.checked);
            });
        }
        if (els.showOther) {
            life.listen(els.showOther, 'change', function (event) {
                viewer.setIfcCategoryVisible('other', event.target.checked);
            });
        }

        // Color Mode Selector
        var colorSelect = document.getElementById('color-mode-select');
        if (colorSelect) {
            life.listen(colorSelect, 'change', function () {
                updateColorModeLegend(colorSelect.value);
                if (ns.workbench && ns.workbench.navigation && ns.workbench.navigation.colorOverlay) {
                    ns.workbench.navigation.colorOverlay.applyColorMode(colorSelect.value);
                }
            });
        }

        // Section Box Storey Cut & Reset
        var clipStoreySelect = document.getElementById('clip-storey-select');
        if (clipStoreySelect) {
            life.listen(clipStoreySelect, 'change', function () {
                if (ns.workbench && ns.workbench.navigation && ns.workbench.navigation.sectionBox) {
                    if (!clipStoreySelect.value) {
                        ns.workbench.navigation.sectionBox.reset();
                    } else {
                        ns.workbench.navigation.sectionBox.cutToStorey(clipStoreySelect.value);
                    }
                }
            });
        }
        var clipReset = document.getElementById('clip-reset');
        if (clipReset) {
            life.listen(clipReset, 'click', function () {
                if (ns.workbench && ns.workbench.navigation && ns.workbench.navigation.sectionBox) {
                    ns.workbench.navigation.sectionBox.reset();
                }
                if (clipStoreySelect) clipStoreySelect.value = '';
                setupClippingForBounds(boundsForClipping());
            });
        }


    }

    return {bindToggle: bindToggle, bind: bind, destroy: function () { life.destroy(); }};
    };
})(window.IfcFds);
