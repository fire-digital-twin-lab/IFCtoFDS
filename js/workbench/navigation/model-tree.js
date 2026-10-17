/**
 * Semantic Model Tree for IFCtoFDS Research Workbench.
 * Renders hierarchical building model trees grouped by Storey, IFC Type,
 * MEP System, Mapping Role, or Validation State.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.navigation = root.IfcFds.workbench.navigation || {};

    var selectionStore = root.IfcFds.workbench.state.selectionStore;
    var visibilityStore = root.IfcFds.workbench.state.visibilityStore;
    var selectionManager = root.IfcFds.workbench.selection.selectionManager;
    var events = root.IfcFds.workbench.events;
    var WORKBENCH_EVENTS = root.IfcFds.workbench.WORKBENCH_EVENTS;

    function SemanticModelTree(containerId) {
        this.containerId = containerId || 'semantic-model-tree';
        this.groupBy = 'storey'; // 'storey', 'ifc-type', 'system', 'role', 'validation'
        this.searchQuery = '';
        this._collapsedGroups = {};
    }

    SemanticModelTree.prototype.init = function () {
        var self = this;
        if (events && WORKBENCH_EVENTS) {
            events.on(WORKBENCH_EVENTS.MODEL_INDEXED, function () {
                self.render();
            });
            events.on(WORKBENCH_EVENTS.SELECTION_CHANGED, function (payload) {
                self.updateActiveSelection(payload.keys || []);
            });
        }
    };

    SemanticModelTree.prototype.setGroupBy = function (mode) {
        this.groupBy = mode || 'storey';
        this.render();
    };

    SemanticModelTree.prototype.setSearchQuery = function (query) {
        this.searchQuery = (query || '').toLowerCase().trim();
        this.render();
    };

    SemanticModelTree.prototype.render = function () {
        var container = document.getElementById(this.containerId);
        if (!container) return;
        container.innerHTML = '';

        var descriptors = selectionStore.getAllDescriptors();
        if (!descriptors.length) {
            var empty = document.createElement('div');
            empty.style.color = 'var(--text-muted)';
            empty.style.fontSize = '11px';
            empty.style.padding = '16px';
            empty.style.textAlign = 'center';
            empty.textContent = 'No building model loaded.';
            container.appendChild(empty);
            return;
        }

        // Filter by search query
        var self = this;
        var filtered = descriptors;
        if (this.searchQuery) {
            filtered = descriptors.filter(function (d) {
                return (d.name && d.name.toLowerCase().includes(self.searchQuery)) ||
                    (d.globalId && d.globalId.toLowerCase().includes(self.searchQuery)) ||
                    (d.ifcType && d.ifcType.toLowerCase().includes(self.searchQuery)) ||
                    (d.storey && d.storey.toLowerCase().includes(self.searchQuery));
            });
        }

        // Group descriptors
        var groups = this._groupDescriptors(filtered, this.groupBy);
        var groupKeys = Object.keys(groups).sort();

        var treeRoot = document.createElement('div');
        treeRoot.className = 'semantic-tree-root';
        treeRoot.style.display = 'flex';
        treeRoot.style.flexDirection = 'column';
        treeRoot.style.gap = '4px';

        groupKeys.forEach(function (groupName) {
            var items = groups[groupName];
            var isCollapsed = !!self._collapsedGroups[groupName];

            var groupCard = document.createElement('div');
            groupCard.className = 'tree-group-card';
            groupCard.style.border = '1px solid var(--border-subtle)';
            groupCard.style.borderRadius = 'var(--radius-sm)';
            groupCard.style.overflow = 'hidden';

            // Group Header
            var groupHeader = document.createElement('div');
            groupHeader.className = 'tree-group-header';
            groupHeader.style.display = 'flex';
            groupHeader.style.alignItems = 'center';
            groupHeader.style.justifyContent = 'space-between';
            groupHeader.style.padding = '6px 8px';
            groupHeader.style.background = 'var(--bg-surface-elevated)';
            groupHeader.style.cursor = 'pointer';
            groupHeader.style.userSelect = 'none';

            var leftCol = document.createElement('div');
            leftCol.style.display = 'flex';
            leftCol.style.alignItems = 'center';
            leftCol.style.gap = '6px';

            var arrow = document.createElement('span');
            arrow.textContent = isCollapsed ? '▶' : '▼';
            arrow.style.fontSize = '9px';
            arrow.style.color = 'var(--text-muted)';
            leftCol.appendChild(arrow);

            var titleSpan = document.createElement('span');
            titleSpan.style.fontSize = '11px';
            titleSpan.style.fontWeight = '600';
            titleSpan.style.color = 'var(--text-primary)';
            titleSpan.textContent = groupName;
            leftCol.appendChild(titleSpan);

            var countBadge = document.createElement('span');
            countBadge.className = 'brand-badge';
            countBadge.style.fontSize = '9px';
            countBadge.textContent = String(items.length);
            leftCol.appendChild(countBadge);

            groupHeader.appendChild(leftCol);

            // Group Actions (Isolate group, Hide group)
            var actionWrap = document.createElement('div');
            actionWrap.style.display = 'flex';
            actionWrap.style.gap = '4px';

            var isolateBtn = document.createElement('button');
            isolateBtn.type = 'button';
            isolateBtn.className = 'btn btn-icon';
            isolateBtn.style.height = '18px';
            isolateBtn.style.width = '18px';
            isolateBtn.title = 'Isolate this group in 3D';
            isolateBtn.innerHTML = '<i data-lucide="filter" style="width:10px;height:10px"></i>';
            isolateBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                var keys = items.map(function (it) { return it.entityKey; });
                visibilityStore.isolateKeys(keys, 'tree');
            });
            actionWrap.appendChild(isolateBtn);

            groupHeader.appendChild(actionWrap);

            groupHeader.addEventListener('click', function () {
                self._collapsedGroups[groupName] = !self._collapsedGroups[groupName];
                self.render();
            });

            groupCard.appendChild(groupHeader);

            // Group Items
            if (!isCollapsed) {
                var itemsList = document.createElement('div');
                itemsList.className = 'tree-items-list';
                itemsList.style.display = 'flex';
                itemsList.style.flexDirection = 'column';
                itemsList.style.background = 'var(--bg-base)';

                items.forEach(function (desc) {
                    var itemRow = document.createElement('div');
                    itemRow.className = 'tree-item-row';
                    itemRow.setAttribute('data-entity-key', desc.entityKey);
                    itemRow.style.display = 'flex';
                    itemRow.style.alignItems = 'center';
                    itemRow.style.justifyContent = 'space-between';
                    itemRow.style.padding = '4px 8px 4px 20px';
                    itemRow.style.fontSize = '11px';
                    itemRow.style.cursor = 'pointer';
                    itemRow.style.borderBottom = '1px solid var(--border-subtle)';

                    if (selectionStore.isSelected(desc.entityKey)) {
                        itemRow.style.background = 'var(--accent-subtle)';
                        itemRow.style.color = 'var(--accent-hover)';
                        itemRow.style.fontWeight = '600';
                    }

                    var nameSpan = document.createElement('span');
                    nameSpan.textContent = desc.name || desc.entityKey;
                    nameSpan.style.whiteSpace = 'nowrap';
                    nameSpan.style.overflow = 'hidden';
                    nameSpan.style.textOverflow = 'ellipsis';
                    nameSpan.title = desc.entityKey + ' (' + desc.ifcType + ')';
                    itemRow.appendChild(nameSpan);

                    itemRow.addEventListener('click', function (e) {
                        e.stopPropagation();
                        selectionManager.handleViewerPick(desc, e);
                    });

                    itemsList.appendChild(itemRow);
                });

                groupCard.appendChild(itemsList);
            }

            treeRoot.appendChild(groupCard);
        });

        container.appendChild(treeRoot);

        if (window.lucide) {
            window.lucide.createIcons({ root: container });
        }
    };

    SemanticModelTree.prototype.updateActiveSelection = function (selectedKeys) {
        var keyMap = {};
        for (var i = 0; i < selectedKeys.length; i++) keyMap[selectedKeys[i]] = true;

        var container = document.getElementById(this.containerId);
        if (!container) return;
        var rows = container.querySelectorAll('.tree-item-row');
        rows.forEach(function (row) {
            var k = row.getAttribute('data-entity-key');
            if (keyMap[k]) {
                row.style.background = 'var(--accent-subtle)';
                row.style.color = 'var(--accent-hover)';
                row.style.fontWeight = '600';
            } else {
                row.style.background = '';
                row.style.color = '';
                row.style.fontWeight = '';
            }
        });
    };

    SemanticModelTree.prototype._groupDescriptors = function (descriptors, groupBy) {
        var groups = {};
        for (var i = 0; i < descriptors.length; i++) {
            var d = descriptors[i];
            var key = 'Unassigned';
            if (groupBy === 'storey') {
                key = d.storey || 'Unassigned';
            } else if (groupBy === 'ifc-type') {
                key = d.ifcType || 'Unknown Type';
            } else if (groupBy === 'system') {
                if (d.systemNames && d.systemNames.length) {
                    key = d.systemNames.join(', ');
                } else {
                    key = d.mepCategory ? ('MEP: ' + d.mepCategory) : 'Architecture & Structure';
                }
            } else if (groupBy === 'role') {
                key = d.simulationRole || 'REFERENCE_GEOMETRY';
            } else if (groupBy === 'validation') {
                var raw = d.raw || {};
                key = raw.review_status || raw.verification_status || 'NOT_RUN';
            }
            if (!groups[key]) groups[key] = [];
            groups[key].push(d);
        }
        return groups;
    };

    var defaultModelTree = new SemanticModelTree('semantic-model-tree');

    root.IfcFds.workbench.navigation.SemanticModelTree = SemanticModelTree;
    root.IfcFds.workbench.navigation.modelTree = defaultModelTree;

})(typeof window !== 'undefined' ? window : globalThis);
