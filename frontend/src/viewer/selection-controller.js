(function (ns) {
    ns.viewer.installSelectionController = function (SceneViewer, helpers) {
        var setVisibilityChannel = helpers.setVisibilityChannel;
        var applyGhostMaterial = helpers.applyGhostMaterial;
        var findSelectableNode = helpers.findSelectableNode;
        var collectVisiblePickTargets = helpers.collectVisiblePickTargets;
        var setObjectHover = helpers.setObjectHover;
        var isOpaqueIfcHit = helpers.isOpaqueIfcHit;
        var selectionPriority = helpers.selectionPriority;

        SceneViewer.prototype.handlePointerDown = function (event) {
            if (event.button !== 0 || !event.shiftKey) return;
            if (this.navigationMode === 'walk') return;
            var rect = this.renderer.domElement.getBoundingClientRect();
            this.marqueeState = {
                startX: event.clientX,
                startY: event.clientY,
                rect: rect,
                dragged: false,
                pointerId: event.pointerId
            };
            try { this.renderer.domElement.setPointerCapture(event.pointerId); } catch (_) { /* ignore */ }
            this.controls.enabled = false;
            event.preventDefault();
        };

        SceneViewer.prototype.handlePointerUp = function (event) {
            if (!this.marqueeState || event.pointerId !== this.marqueeState.pointerId) return;
            var state = this.marqueeState;
            this.marqueeState = null;
            this.controls.enabled = true;
            if (this.marqueeEl) this.marqueeEl.hidden = true;
            try { this.renderer.domElement.releasePointerCapture(event.pointerId); } catch (_) { /* ignore */ }
            if (!state.dragged) return; // Treated as a Shift+click — let handleClick add to selection.
            var rect = state.rect;
            var x1 = state.startX - rect.left;
            var y1 = state.startY - rect.top;
            var x2 = event.clientX - rect.left;
            var y2 = event.clientY - rect.top;
            this.completeMarqueeSelection(
                Math.min(x1, x2), Math.min(y1, y2),
                Math.max(x1, x2), Math.max(y1, y2)
            );
        };

        SceneViewer.prototype.updateMarqueeRectFromPointer = function (event) {
            var state = this.marqueeState;
            if (!state) return;
            var dx = event.clientX - state.startX;
            var dy = event.clientY - state.startY;
            if (!state.dragged) {
                if (Math.abs(dx) + Math.abs(dy) < 4) return; // MARQUEE_MIN_DRAG_PX
                state.dragged = true;
                if (this.marqueeEl) this.marqueeEl.hidden = false;
            }
            if (!this.marqueeEl) return;
            var rect = state.rect;
            var left = Math.min(state.startX, event.clientX) - rect.left;
            var top = Math.min(state.startY, event.clientY) - rect.top;
            this.marqueeEl.style.left = left + 'px';
            this.marqueeEl.style.top = top + 'px';
            this.marqueeEl.style.width = Math.abs(dx) + 'px';
            this.marqueeEl.style.height = Math.abs(dy) + 'px';
        };

        SceneViewer.prototype.completeMarqueeSelection = function (x1, y1, x2, y2) {
            var canvas = this.renderer.domElement;
            var width = canvas.clientWidth || 1;
            var height = canvas.clientHeight || 1;
            var targets = [];
            if (this.ifcOpacity > 0) collectVisiblePickTargets(this.ifcGroup, targets);
            if (this.opacity > 0) collectVisiblePickTargets(this.fdsGroup, targets);
            this.scene.updateMatrixWorld(true);
            var camera = this.camera;
            var picked = [];
            var bbox = new THREE.Box3();
            var centre = new THREE.Vector3();
            for (var i = 0; i < targets.length; i += 1) {
                var mesh = targets[i];
                var selectable = findSelectableNode(mesh);
                if (!selectable || !selectable.userData || !selectable.userData.type) continue;
                bbox.makeEmpty().expandByObject(mesh);
                if (bbox.isEmpty()) continue;
                bbox.getCenter(centre);
                centre.project(camera);
                if (centre.z < -1 || centre.z > 1) continue;
                var sx = (centre.x * 0.5 + 0.5) * width;
                var sy = (-centre.y * 0.5 + 0.5) * height;
                if (sx < x1 || sx > x2 || sy < y1 || sy > y2) continue;
                if (picked.indexOf(selectable) === -1) picked.push(selectable);
            }
            this.setSelectedObjects(picked);
            this.onSelect(picked.map(function (object) { return object.userData; }));
        };

        SceneViewer.prototype.handleClick = function (event) {
            if (this.navigationMode === 'walk') {
                if (!this.walkPlaced) this.placeWalkerFromClick(event.clientX, event.clientY);
                else if (!this.walkControls.isLocked) this.walkControls.lock();
                return;
            }
            var candidate = this.pickCandidate(event.clientX, event.clientY);
            var additive = event.shiftKey || event.ctrlKey || event.metaKey;
            this.selectObject(candidate ? candidate.object : null, additive);
            this.onSelect(this.selectedObjects.map(function (object) { return object.userData; }));
        };

        SceneViewer.prototype.handlePointerMove = function (event) {
            if (this.marqueeState) {
                this.updateMarqueeRectFromPointer(event);
                return;
            }
            if (this.navigationMode === 'walk') {
                this.clearHover();
                return;
            }
            var candidate = this.pickCandidate(event.clientX, event.clientY);
            var object = candidate ? candidate.object : null;

            if (object !== this.hoveredObject) {
                this.setHoveredObject(object);
            }

            if (candidate) {
                this.container.classList.add('is-picking');
                this.showTooltip(candidate.data, event.clientX, event.clientY);
            } else {
                this.container.classList.remove('is-picking');
                this.hideTooltip();
            }
        };

        SceneViewer.prototype.pickCandidate = function (clientX, clientY) {
            var rect = this.renderer.domElement.getBoundingClientRect();
            this.mouse.x = ((clientX - rect.left) / rect.width) * 2 - 1;
            this.mouse.y = -((clientY - rect.top) / rect.height) * 2 + 1;
            this.raycaster.setFromCamera(this.mouse, this.camera);

            var targets = [];
            if (this.opacity > 0) {
                collectVisiblePickTargets(this.fdsGroup, targets);
            }
            if (this.ifcOpacity > 0) {
                collectVisiblePickTargets(this.ifcGroup, targets);
            }

            var hits = this.raycaster.intersectObjects(targets, true);
            var seen = [];
            var candidates = hits
                .map(function (hit) {
                    var object = findSelectableNode(hit.object);
                    return {
                        distance: hit.distance,
                        object: object,
                        data: object ? object.userData : null
                    };
                })
                .filter(function (candidate) {
                    if (!candidate.object || !candidate.data || !candidate.data.type) return false;
                    if (seen.indexOf(candidate.object) >= 0) return false;
                    seen.push(candidate.object);
                    return true;
                });

            candidates.sort(function (a, b) {
                // Distance-first so a click on the front wall picks the front wall, not a
                // HOLE / VENT / GEOM hiding behind it. Priority is only used as a tie-breaker
                // when two hits are within ~0.3 m of each other — that's the original case
                // priority was designed for (a VENT marker coincident with the OBST it sits on,
                // a HOLE rectangle overlapping a wall it carves into).
                var distGap = a.distance - b.distance;
                if (Math.abs(distGap) > 0.3) return distGap;
                var byPriority = selectionPriority(a.data.type) - selectionPriority(b.data.type);
                if (byPriority) return byPriority;
                // When two IFC hits are nearly the same distance, prefer the opaque one — clicking
                // through a window's glass should land on the wall behind, not on the glass itself.
                if (a.data.type === 'IFC' && b.data.type === 'IFC' && Math.abs(a.distance - b.distance) < 0.6) {
                    var ao = isOpaqueIfcHit(a.object) ? 0 : 1;
                    var bo = isOpaqueIfcHit(b.object) ? 0 : 1;
                    if (ao !== bo) return ao - bo;
                }
                return distGap;
            });

            return candidates.length ? candidates[0] : null;
        };

        SceneViewer.prototype.setHoveredObject = function (object) {
            if (this.hoveredObject) setObjectHover(this.hoveredObject, false);
            this.hoveredObject = object || null;
            if (this.hoveredObject) setObjectHover(this.hoveredObject, true);
        };

        SceneViewer.prototype.selectObject = function (object, additive) {
            if (!additive) {
                this.setSelectedObjects(object ? [object] : []);
                return;
            }
            if (!object) return;

            var selectedObjects = this.selectedObjects.slice();
            var index = selectedObjects.indexOf(object);
            if (index >= 0) selectedObjects.splice(index, 1);
            else selectedObjects.push(object);
            this.setSelectedObjects(selectedObjects);
        };

        SceneViewer.prototype.setSelectedObjects = function (objects) {
            this.selectionHelpers.forEach(function (helper) {
                if (helper.parent) helper.parent.remove(helper);
                if (helper.geometry) helper.geometry.dispose();
                if (helper.material) helper.material.dispose();
            });
            this.selectionHelpers = [];
            this.selectedObjects = (objects || []).filter(function (object) {
                return object && object.geometry;
            });

            var self = this;
            this.selectedObjects.forEach(function (object) {
                self.selectionHelpers.push(self.makeSelectionHelper(object));
            });
        };

        SceneViewer.prototype.makeSelectionHelper = function (object) {
            var geometry = object.isLineSegments
                ? object.geometry.clone()
                : new THREE.EdgesGeometry(object.geometry, 15);
            var material = new THREE.LineBasicMaterial({
                color: 0xd63856,
                transparent: true,
                opacity: 1,
                depthTest: false
            });
            var helper = new THREE.LineSegments(geometry, material);
            helper.name = 'Selected object outline';
            helper._isSelectionHelper = true;
            // Mirror the object's full local transform via the matrix, not just PQS — web-ifc
            // meshes drive their placement through mesh.matrix directly (matrixAutoUpdate=false),
            // so position/quaternion/scale are stuck at defaults and copying them lands the
            // outline at the origin.
            if (object.matrixAutoUpdate) object.updateMatrix();
            helper.matrix.copy(object.matrix);
            helper.matrixAutoUpdate = false;
            helper.renderOrder = 1000;
            helper.raycast = function () {};
            object.parent.add(helper);
            return helper;
        };

        SceneViewer.prototype.focusSelection = function () {
            if (!this.selectedObjects || !this.selectedObjects.length) return;
            var box = new THREE.Box3();
            this.selectedObjects.forEach(function (obj) {
                box.expandByObject(obj);
            });
            if (!box.isEmpty()) {
                var center = box.getCenter(new THREE.Vector3());
                var size = box.getSize(new THREE.Vector3());
                var span = Math.max(size.x, size.y, size.z, 0.5);
                this.controls.target.copy(center);
                this.camera.position.set(center.x + span * 1.5, center.y + span * 1.2, center.z + span * 1.5);
                this.camera.near = Math.max(span / 1000, 0.001);
                this.camera.far = Math.max(span * 1000, 100);
                this.camera.updateProjectionMatrix();
                this.controls.update();
            }
        };

        SceneViewer.prototype.selectByEntityKeys = function (keys) {
            if (!keys || !keys.length) {
                this.setSelectedObjects([]);
                return;
            }
            var keyMap = {};
            var sourceQualifiedMap = {};
            var globalGuidMap = {};
            var store = (window.IfcFds && window.IfcFds.workbench && window.IfcFds.workbench.state && window.IfcFds.workbench.state.selectionStore);

            for (var i = 0; i < keys.length; i++) {
                var rawK = String(keys[i]);
                keyMap[rawK] = true;
                if (store) {
                    if (store._aliasMap && store._aliasMap[rawK]) {
                        keyMap[store._aliasMap[rawK]] = true;
                    }
                    var desc = store.getDescriptor ? store.getDescriptor(rawK) : null;
                    if (desc) {
                        if (desc.entityKey) keyMap[desc.entityKey] = true;
                        if (desc.canonicalKey) keyMap[desc.canonicalKey] = true;
                        if (desc.sourceId) {
                            var sId = String(desc.sourceId);
                            if (desc.stepId !== undefined && desc.stepId !== null) {
                                sourceQualifiedMap[sId + ':' + String(desc.stepId)] = true;
                            }
                            if (desc.globalId) {
                                sourceQualifiedMap[sId + ':' + String(desc.globalId)] = true;
                            }
                        } else if (desc.globalId) {
                            globalGuidMap[String(desc.globalId)] = true;
                        }
                    }
                }
                var colonIdx = rawK.indexOf(':');
                if (colonIdx !== -1) {
                    var srcPart = rawK.substring(0, colonIdx);
                    var idPart = rawK.substring(colonIdx + 1);
                    sourceQualifiedMap[srcPart + ':' + idPart] = true;
                } else {
                    if (rawK.length >= 20 && !/^\d+$/.test(rawK)) {
                        globalGuidMap[rawK] = true;
                    }
                }
            }

            var matched = [];
            var createEntityKey = (window.IfcFds && window.IfcFds.workbench && window.IfcFds.workbench.createEntityKey) || function () { return ''; };

            function checkNode(node) {
                if (node._isSelectionHelper || (node.parent && node.parent.isMesh)) return;
                if (!node || !node.userData || !node.userData.type) return;
                var k = createEntityKey(node.userData);
                if (k && keyMap[k]) {
                    matched.push(node);
                    return;
                }
                if (store && store._aliasMap && store._aliasMap[k] && keyMap[store._aliasMap[k]]) {
                    matched.push(node);
                    return;
                }
                var u = node.userData;
                var raw = u.raw || {};
                var globalId = String(u.globalId || raw.global_id || raw.GlobalId || '');
                var stepId = String(u.stepId || raw.step_id || u.expressID || u.id || '');
                var nodeSource = String(u.sourceId || raw.source_id || (u.ifcSource && (u.ifcSource.sourceId || u.ifcSource.fileName)) || 'ifc');
                if (globalId && sourceQualifiedMap[nodeSource + ':' + globalId]) {
                    matched.push(node);
                    return;
                }
                if (stepId && sourceQualifiedMap[nodeSource + ':' + stepId]) {
                    matched.push(node);
                    return;
                }
                if (globalId && globalGuidMap[globalId]) {
                    matched.push(node);
                    return;
                }
            }

            if (this.fdsGroup) this.fdsGroup.traverse(checkNode);
            if (this.ifcGroup) this.ifcGroup.traverse(checkNode);
            this.setSelectedObjects(matched);
        };

        SceneViewer.prototype.applyVisibilityState = function (visStore) {
            if (!visStore) return;
            this.visibilityStore = visStore;
            var createEntityKey = (window.IfcFds && window.IfcFds.workbench && window.IfcFds.workbench.createEntityKey) || function () { return ''; };

            function updateNode(node) {
                if (!node.isMesh && !node.isLineSegments) return;
                if (!node.userData || !node.userData.type) return;
                var k = createEntityKey(node.userData);
                if (node._isSelectionHelper) return;
                var visible = visStore.isKeyVisible(k, ns.workbench.normalizeEntityDescriptor(node.userData));
                setVisibilityChannel(node, 'workbench', visible);
                var ghosted = visStore.isKeyGhosted(k);
                var materials = Array.isArray(node.material) ? node.material : [node.material];
                materials.forEach(function (material) { applyGhostMaterial(material, ghosted); });
            }

            if (this.fdsGroup) this.fdsGroup.traverse(updateNode);
            if (this.ifcGroup) this.ifcGroup.traverse(updateNode);
        };

        SceneViewer.prototype.clearHover = function () {
            this.setHoveredObject(null);
            this.container.classList.remove('is-picking');
            this.hideTooltip();
        };

        SceneViewer.prototype.showTooltip = function (data, clientX, clientY) {
            if (!this.tooltip || !data) return;

            var rect = this.container.getBoundingClientRect();
            var x = clientX - rect.left + 14;
            var y = clientY - rect.top + 14;
            var label = data.type + (data.id ? ': ' + data.id : '');

            this.tooltip.textContent = label;
            this.tooltip.hidden = false;

            var maxX = this.container.clientWidth - this.tooltip.offsetWidth - 10;
            var maxY = this.container.clientHeight - this.tooltip.offsetHeight - 10;
            this.tooltip.style.left = Math.max(10, Math.min(x, maxX)) + 'px';
            this.tooltip.style.top = Math.max(10, Math.min(y, maxY)) + 'px';
        };

        SceneViewer.prototype.hideTooltip = function () {
            if (this.tooltip) this.tooltip.hidden = true;
        };

    };
})(window.IfcFds);
