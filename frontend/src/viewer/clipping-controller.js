(function (ns) {
    ns.viewer.installClippingController = function (SceneViewer, helpers) {
        var toThree = helpers.toThree;
        var easeOutCubic = helpers.easeOutCubic;
        var isExcludedMesh = helpers.isExcludedMesh;
        var setVisibilityChannel = helpers.setVisibilityChannel;

        SceneViewer.prototype.setClipBoundsNative = function (nativeBounds) {
            if (!nativeBounds) { this.clipBoundsNative = null; this.resetClipping(); return; }
            this.clipBoundsNative = {
                xmin: nativeBounds.xmin, xmax: nativeBounds.xmax,
                ymin: nativeBounds.ymin, ymax: nativeBounds.ymax,
                zmin: nativeBounds.zmin, zmax: nativeBounds.zmax
            };
            this.resetClipping();
        };

        SceneViewer.prototype.setClipPlane = function (axis, side, value) {
            if (!this.clipPlanes) return;
            // IFC X -> Three X, IFC Y -> Three Z, IFC Z -> Three Y (per toThree).
            if (axis === 'x') {
                if (side === 'min') this.clipPlanes[0].constant = -value;
                else this.clipPlanes[1].constant = value;
            } else if (axis === 'y') {
                if (side === 'min') this.clipPlanes[4].constant = -value;
                else this.clipPlanes[5].constant = value;
            } else if (axis === 'z') {
                if (side === 'min') this.clipPlanes[2].constant = -value;
                else this.clipPlanes[3].constant = value;
            }
            this.clipRanges = this.clipRanges || { xmin: -Infinity, xmax: Infinity, ymin: -Infinity, ymax: Infinity, zmin: -Infinity, zmax: Infinity };
            this.clipRanges[axis + side] = value;
            this.applyFdsClipVisibility();
        };

        SceneViewer.prototype.applyFdsClipVisibility = function () {
            var range = this.clipRanges;
            var excludedSteps = this.excludedStepIds || {};
            var excludedItems = this.excludedItemIds || {};
            var noActiveClip = !range || (
                range.xmin === -Infinity && range.xmax === Infinity
                && range.ymin === -Infinity && range.ymax === Infinity
                && range.zmin === -Infinity && range.zmax === Infinity
            );
            this.fdsGroup.updateMatrixWorld(true);
            var box = new THREE.Box3();
            this.fdsGroup.traverse(function (node) {
                if (!node.isMesh && !node.isLineSegments) return;
                setVisibilityChannel(node, 'exclusion', !isExcludedMesh(node, excludedSteps, excludedItems));
                if (noActiveClip) { setVisibilityChannel(node, 'section', true); return; }
                box.makeEmpty().expandByObject(node);
                if (box.isEmpty()) { setVisibilityChannel(node, 'section', true); return; }
                var eps = 1e-4;
                // Three world -> IFC native: Three Y is IFC Z (height), Three Z is IFC Y.
                var intersects = (box.max.x >= range.xmin - eps) && (box.min.x <= range.xmax + eps)
                    && (box.max.y >= range.zmin - eps) && (box.min.y <= range.zmax + eps)
                    && (box.max.z >= range.ymin - eps) && (box.min.z <= range.ymax + eps);
                setVisibilityChannel(node, 'section', intersects);
            });
        };

        SceneViewer.prototype.playConversionReveal = function (options) {
            options = options || {};
            var fadeMs = Math.max(0, Number(options.fadeMs) || 1400);
            var finalIfcOpacity = typeof options.finalIfcOpacity === 'number' ? options.finalIfcOpacity : 0.15;
            var onComplete = typeof options.onComplete === 'function' ? options.onComplete : function () {};
            var self = this;

            // Clear any prior clip state so a stale partial clip box from before this convert
            // doesn't hide the freshly-produced FDS primitives during the reveal. The clip-bar
            // UI is re-synced by the controller right after this call.
            this.resetClipping();
            this.fdsGroup.updateMatrixWorld(true);
            var box = new THREE.Box3().expandByObject(this.fdsGroup);
            if (box.isEmpty()) { onComplete(); return; }

            // Scale the reveal duration with the building height so a tall building (Institute,
            // school) doesn't blow past in the same 2.2 s as a single-storey house. Caller can
            // still override via options.revealMs.
            var height = Math.max(0.01, box.max.y - box.min.y);
            var revealMs = Math.max(0, Number(options.revealMs) || Math.max(2200, Math.min(6000, height * 350)));

            // Stop any in-flight reveal so back-to-back conversions don't double-animate.
            if (this._revealCleanup) { this._revealCleanup(); this._revealCleanup = null; }

            var yMin = box.min.y - 0.01;
            var yMax = box.max.y + 0.01;
            var revealPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), yMin);
            var savedClips = [];
            this.fdsGroup.traverse(function (node) {
                if (node.material && node.material.isMaterial) {
                    savedClips.push({ material: node.material, previous: node.material.clippingPlanes });
                    node.material.clippingPlanes = [revealPlane];
                }
            });

            this.setIfcOpacity(1);

            var startTime = performance.now();
            var animFrame = null;
            var finished = false;
            function cleanup() {
                if (finished) return;
                finished = true;
                savedClips.forEach(function (entry) { entry.material.clippingPlanes = entry.previous; });
                // Land the IFC at the configured final opacity (default 0.3) so it stays as a
                // ghosted backdrop next to the FDS. Push the slider too so the UI reflects it.
                self.setIfcOpacity(finalIfcOpacity);
                var ifcSlider = document.getElementById('ifc-opacity');
                if (ifcSlider) ifcSlider.value = String(finalIfcOpacity);
                if (animFrame !== null) cancelAnimationFrame(animFrame);
                self._revealCleanup = null;
            }
            this._revealCleanup = cleanup;

            function step(now) {
                var elapsed = now - startTime;
                if (elapsed < fadeMs) {
                    var t = elapsed / fadeMs;
                    self.setIfcOpacity(1 - (1 - finalIfcOpacity) * easeOutCubic(t));
                    animFrame = requestAnimationFrame(step);
                    return;
                }
                if (self.ifcOpacity !== finalIfcOpacity) self.setIfcOpacity(finalIfcOpacity);
                if (elapsed < fadeMs + revealMs) {
                    // Linear pace for the reveal: the plane climbs at a constant m/s, so a
                    // 10 m building takes roughly twice as long as a 5 m one and the viewer
                    // can actually follow the sweep instead of seeing only the slow tail of
                    // easeOutCubic.
                    var t2 = Math.max(0, Math.min(1, (elapsed - fadeMs) / revealMs));
                    revealPlane.constant = yMin + (yMax - yMin) * t2;
                    animFrame = requestAnimationFrame(step);
                    return;
                }
                cleanup();
                onComplete();
            }

            animFrame = requestAnimationFrame(step);
        };

        SceneViewer.prototype.resetClipping = function () {
            if (!this.clipPlanes) return;
            for (var i = 0; i < this.clipPlanes.length; i += 1) {
                this.clipPlanes[i].constant = Infinity;
            }
            this.clipRanges = { xmin: -Infinity, xmax: Infinity, ymin: -Infinity, ymax: Infinity, zmin: -Infinity, zmax: Infinity };
            this.applyFdsClipVisibility();
        };

    };
})(window.IfcFds);
