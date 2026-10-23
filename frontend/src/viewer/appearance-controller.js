(function (ns) {
    ns.viewer.installAppearanceController = function (SceneViewer, helpers) {
        var isExcludedMesh = helpers.isExcludedMesh;
        var setIfcMaterialOpacity = helpers.setIfcMaterialOpacity;
        var setVisibilityChannel = helpers.setVisibilityChannel;
        var applyGhostMaterial = helpers.applyGhostMaterial;

        SceneViewer.prototype.setViewMode = function (mode) {
            this.viewMode = mode;
            this.syncRootLayerVisibility();
        };

        SceneViewer.prototype.setTheme = function (theme) {
            this.theme = theme === 'dark' ? 'dark' : 'light';
            this.scene.background.setHex(this.theme === 'dark' ? 0x1a1a2e : 0xf4f5f8);
            this.applyGroundGridTheme();
        };

        SceneViewer.prototype.applyGroundGridTheme = function () {
            if (!this.groundGrid || !this.groundGrid.geometry) return;
            var colors = this.groundGrid.geometry.getAttribute('color');
            if (!colors) return;

            var major = new THREE.Color(this.theme === 'dark' ? 0x506080 : 0xa9afbd);
            var minor = new THREE.Color(this.theme === 'dark' ? 0x26334d : 0xd8dae2);
            var lineCount = colors.count / 4;
            var center = Math.floor(lineCount / 2);
            for (var line = 0; line < lineCount; line += 1) {
                var color = line === center ? major : minor;
                for (var vertex = 0; vertex < 4; vertex += 1) {
                    colors.setXYZ(line * 4 + vertex, color.r, color.g, color.b);
                }
            }
            colors.needsUpdate = true;
            this.groundGrid.material.opacity = this.theme === 'dark' ? 0.34 : 0.42;
        };

        SceneViewer.prototype.setLayerVisible = function (layer, visible) {
            if (layer === 'ifcEdges') {
                this.setIfcEdgesVisible(visible);
                return;
            }
            var map = {
                meshes: this.meshGroup,
                obsts: this.obstGroup,
                vents: this.ventGroup,
                holes: this.holeGroup,
                geoms: this.geomGroup,
                ifcReference: this.ifcReferenceGroup,
                groundGrid: this.groundGrid
            };
            if (map[layer]) map[layer].visible = visible;
        };

        SceneViewer.prototype.setIfcEdgesVisible = function (visible) {
            this.showIfcEdges = !!visible;
            [this.ifcSolidGroup, this.ifcReferenceGroup, this.verifiedReferenceGroup].forEach(function (group) {
                if (!group) return;
                group.traverse(function (node) {
                    if (node._isIfcEdge) setVisibilityChannel(node, 'edgeDisplay', node._isIfcOpeningEdge || !!visible);
                });
            });
        };

        SceneViewer.prototype.setIfcCategoryVisible = function (category, visible) {
            if (!this.ifcCategoryVisible) this.ifcCategoryVisible = { structure: true, fills: true, other: true };
            if (this.ifcCategoryVisible[category] === undefined) return;
            this.ifcCategoryVisible[category] = !!visible;
            this.applyIfcCategoryVisibility();
        };

        SceneViewer.prototype.applyIfcCategoryVisibility = function () {
            if (!this.ifcCategoryVisible) this.ifcCategoryVisible = { structure: true, fills: true, other: true };
            var categoryState = this.ifcCategoryVisible;
            var excludedSteps = this.excludedStepIds || {};
            var excludedItems = this.excludedItemIds || {};
            [this.ifcSolidGroup, this.ifcReferenceGroup].forEach(function (group) {
                group.children.forEach(function (mesh) {
                    setVisibilityChannel(mesh, 'exclusion', !isExcludedMesh(mesh, excludedSteps, excludedItems));
                    var category = mesh.userData && mesh.userData.ifcCategory;
                    setVisibilityChannel(mesh, 'category', !category || categoryState[category] !== false);
                });
            });
            this.applyVisibilityState(this.visibilityStore);
        };

        SceneViewer.prototype.setExclusions = function (stepIdMap, itemIdMap) {
            this.excludedStepIds = stepIdMap || {};
            this.excludedItemIds = itemIdMap || {};
            this.applyFdsClipVisibility();
            this.applyIfcCategoryVisibility();
        };

        SceneViewer.prototype.setFdsOpacity = function (opacity) {
            this.opacity = Math.max(0, Math.min(1, Number(opacity) || 0));
            if (this.opacity === 0) this.clearHover();

            var fdsOpacity = this.opacity;
            [this.meshGroup, this.obstGroup, this.ventGroup, this.geomGroup].forEach(function (group) {
                group.traverse(function (node) {
                    if (node.material && node.material.opacity !== undefined) {
                        applyGhostMaterial(node.material, false);
                        node.material.opacity = fdsOpacity;
                        node.material.transparent = true;
                    }
                });
            });
            this.syncRootLayerVisibility();
            this.applyVisibilityState(this.visibilityStore);
        };

        SceneViewer.prototype.setIfcOpacity = function (opacity) {
            this.ifcOpacity = Math.max(0, Math.min(1, Number(opacity) || 0));
            this.clearHover();

            var ifcOpacity = this.ifcOpacity;
            [this.ifcSolidGroup, this.ifcReferenceGroup].forEach(function (group) {
                group.traverse(function (node) {
                    (Array.isArray(node.material) ? node.material : [node.material]).forEach(function (material) { applyGhostMaterial(material, false); });
                    setIfcMaterialOpacity(node.material, ifcOpacity);
                    if (node.isMesh && node.userData && node.userData.type === 'IFC') {
                        node.renderOrder = ifcOpacity < 1 ? 1 : 0;
                    }
                });
            });
            this.syncRootLayerVisibility();
            this.applyVisibilityState(this.visibilityStore);
        };

        SceneViewer.prototype.syncRootLayerVisibility = function () {
            this.fdsGroup.visible = this.viewMode !== 'ifc' && this.opacity > 0;
            this.ifcGroup.visible = this.viewMode !== 'fds' && this.ifcOpacity > 0;
        };

    };
})(window.IfcFds);
