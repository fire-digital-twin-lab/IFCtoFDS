/**
 * Inspector Controller for IFCtoFDS Research Workbench.
 * Orchestrates entity selection state, tab switching, and action dispatching.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.inspector = root.IfcFds.workbench.inspector || {};

    var InspectorView = root.IfcFds.workbench.inspector.InspectorView;
    var selectionStore = root.IfcFds.workbench.state.selectionStore;
    var visibilityStore = root.IfcFds.workbench.state.visibilityStore;
    var commandBus = root.IfcFds.workbench.commands.commandBus;
    var FocusSelectedCommand = root.IfcFds.workbench.commands.FocusSelectedCommand;
    var HideCommand = root.IfcFds.workbench.commands.HideCommand;
    var IsolateCommand = root.IfcFds.workbench.commands.IsolateCommand;
    var events = root.IfcFds.workbench.events;
    var WORKBENCH_EVENTS = root.IfcFds.workbench.WORKBENCH_EVENTS;

    function InspectorController(viewerInstance) {
        this.viewer = viewerInstance || null;
        this.view = new InspectorView('inspect-structured-view');
        this.activeTab = 'id';
        this.currentDescriptor = null;
        this.els = {};
        this._unsubscribe = null;
    }

    InspectorController.prototype.init = function (domElements, viewer) {
        this.els = domElements || {};
        if (viewer) this.viewer = viewer;
        var self = this;

        // Bind Inspector Tabs
        var inspectorTabs = document.querySelectorAll('.inspector-tab-btn');
        inspectorTabs.forEach(function (btn) {
            btn.addEventListener('click', function () {
                inspectorTabs.forEach(function (b) { b.classList.remove('active'); });
                btn.classList.add('active');
                var tab = btn.getAttribute('data-tab');
                if (!tab) {
                    var id = btn.id || '';
                    if (id.indexOf('map') >= 0) tab = 'map';
                    else if (id.indexOf('geom') >= 0) tab = 'geom';
                    else if (id.indexOf('mep') >= 0) tab = 'mep';
                    else tab = 'id';
                }
                self.setActiveTab(tab);
            });
        });

        // Bind Close Button
        var closeBtn = (this.els && this.els.closeInspector) || document.getElementById('close-inspector');
        if (closeBtn) {
            closeBtn.addEventListener('click', function () {
                commandBus.execute(new root.IfcFds.workbench.commands.SelectCommand([], 'clear', selectionStore));
            });
        }

        // Subscribe to SelectionStore updates
        if (this._unsubscribe) this._unsubscribe();
        this._unsubscribe = selectionStore.subscribe(function (payload) {
            self.onSelectionChanged(payload);
        });
    };

    InspectorController.prototype.setViewer = function (viewer) {
        this.viewer = viewer;
    };

    InspectorController.prototype.setActiveTab = function (tab) {
        this.activeTab = tab || 'id';
        this.refresh();
        if (events && WORKBENCH_EVENTS) {
            events.emit(WORKBENCH_EVENTS.INSPECTOR_TAB_CHANGED, { tab: this.activeTab });
        }
    };

    InspectorController.prototype.onSelectionChanged = function (payload) {
        var selection = payload.selection || [];
        var card = (this.els && this.els.inspectCard) || document.getElementById('inspect-card');
        var titleEl = (this.els && this.els.inspectTitle) || document.getElementById('inspect-title');
        var bodyEl = (this.els && this.els.inspectBody) || document.getElementById('inspect-body');

        if (!selection.length) {
            if (card) card.hidden = true;
            this.currentDescriptor = null;
            this.view.render(null, this.activeTab);
            return;
        }

        if (card) card.hidden = false;

        if (selection.length === 1) {
            this.currentDescriptor = selection[0];
            if (titleEl) {
                titleEl.textContent = this.currentDescriptor.name || this.currentDescriptor.entityKey;
            }
            if (bodyEl) {
                bodyEl.textContent = JSON.stringify(this.currentDescriptor.raw || this.currentDescriptor, null, 2);
            }
        } else {
            this.currentDescriptor = null;
            if (titleEl) {
                titleEl.textContent = 'Selected: ' + selection.length + ' objects';
            }
            if (bodyEl) {
                bodyEl.textContent = JSON.stringify(selection.map(function (s) {
                    return s.entityKey || s.name;
                }), null, 2);
            }
        }

        this.refresh();
    };

    InspectorController.prototype.refresh = function () {
        var self = this;
        var actionCallbacks = {
            onFocus: function (desc) {
                if (self.viewer) {
                    var cmd = new FocusSelectedCommand(self.viewer, selectionStore);
                    commandBus.execute(cmd);
                }
            },
            onHide: function (desc) {
                if (desc && desc.entityKey) {
                    var cmd = new HideCommand([desc.entityKey], visibilityStore);
                    commandBus.execute(cmd);
                }
            },
            onIsolate: function (desc) {
                if (desc && desc.entityKey) {
                    var cmd = new IsolateCommand([desc.entityKey], visibilityStore);
                    commandBus.execute(cmd);
                }
            },
            onConfigureHvac: function (desc) {
                // Operational modeling requires reviewed source values and provenance.
                // Keep this control disabled until that workflow exists.
                return;
            }
        };

        this.view.render(this.currentDescriptor, this.activeTab, actionCallbacks);
    };

    // Backward-compatible method
    InspectorController.prototype.renderStructuredInspector = function (item) {
        if (!item) {
            this.currentDescriptor = null;
        } else {
            this.currentDescriptor = root.IfcFds.workbench.normalizeEntityDescriptor(item);
        }
        this.refresh();
    };

    var defaultInspectorController = new InspectorController();

    root.IfcFds.workbench.inspector.InspectorController = InspectorController;
    root.IfcFds.workbench.inspector.inspectorController = defaultInspectorController;

    // Backward-compatible alias for existing callers
    root.IfcFds.ui = root.IfcFds.ui || {};
    root.IfcFds.ui.inspectorPanel = {
        init: function (els, viewer) {
            defaultInspectorController.init(els, viewer);
        },
        renderStructuredInspector: function (item) {
            defaultInspectorController.renderStructuredInspector(item);
        },
        setActiveTab: function (tab) {
            defaultInspectorController.setActiveTab(tab);
        }
    };

})(typeof window !== 'undefined' ? window : globalThis);
