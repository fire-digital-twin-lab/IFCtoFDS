/**
 * 6-Axis Interactive Clipping and Conversion Reveal Sweep Controller for SceneViewer.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.viewer = root.IfcFds.viewer || {};

    function easeOutCubic(t) {
        return 1 - Math.pow(1 - Math.max(0, Math.min(1, t)), 3);
    }

    function ClippingController(renderer, fdsGroup, onOpacityChange) {
        this.renderer = renderer;
        this.fdsGroup = fdsGroup;
        this.onOpacityChange = onOpacityChange || function () {};
        this.clipPlanes = [
            new THREE.Plane(new THREE.Vector3(1, 0, 0), Infinity),   // X min
            new THREE.Plane(new THREE.Vector3(-1, 0, 0), Infinity),  // X max
            new THREE.Plane(new THREE.Vector3(0, 1, 0), Infinity),   // Y min
            new THREE.Plane(new THREE.Vector3(0, -1, 0), Infinity),  // Y max
            new THREE.Plane(new THREE.Vector3(0, 0, 1), Infinity),   // Z min
            new THREE.Plane(new THREE.Vector3(0, 0, -1), Infinity)   // Z max
        ];
        this.renderer.clippingPlanes = this.clipPlanes;
        this.clipBoundsNative = null;
        this.clipRanges = null;
        this._revealCleanup = null;
    }

    ClippingController.prototype.setClipBoundsNative = function (bounds) {
        this.clipBoundsNative = bounds;
        this.resetClipping();
    };

    ClippingController.prototype.resetClipping = function () {
        for (var i = 0; i < this.clipPlanes.length; i++) {
            this.clipPlanes[i].constant = Infinity;
        }
        this.clipRanges = {
            xmin: -Infinity, xmax: Infinity,
            ymin: -Infinity, ymax: Infinity,
            zmin: -Infinity, zmax: Infinity
        };
        this.applyFdsClipVisibility();
    };

    ClippingController.prototype.setClipPlane = function (axis, side, value) {
        var val = Number(value);
        if (!isFinite(val)) return;
        var planeIdx = -1;
        if (axis === 'x') planeIdx = (side === 'min') ? 0 : 1;
        if (axis === 'z') planeIdx = (side === 'min') ? 2 : 3;
        if (axis === 'y') planeIdx = (side === 'min') ? 4 : 5;
        if (planeIdx < 0) return;

        var constant = (side === 'min') ? -val : val;
        this.clipPlanes[planeIdx].constant = constant;
        if (!this.clipRanges) this.resetClipping();
        this.clipRanges[axis + side] = val;
        this.applyFdsClipVisibility();
    };

    ClippingController.prototype.applyFdsClipVisibility = function (excludedStepIds, excludedItemIds) {
        var range = this.clipRanges;
        var noActiveClip = !range || (
            range.xmin === -Infinity && range.xmax === Infinity
            && range.ymin === -Infinity && range.ymax === Infinity
            && range.zmin === -Infinity && range.zmax === Infinity
        );
        this.fdsGroup.updateMatrixWorld(true);
        var box = new THREE.Box3();
        this.fdsGroup.traverse(function (node) {
            if (!node.isMesh && !node.isLineSegments) return;
            if (noActiveClip) { root.IfcFds.viewer.setVisibilityChannel(node, 'section', true); return; }
            box.makeEmpty().expandByObject(node);
            if (box.isEmpty()) { root.IfcFds.viewer.setVisibilityChannel(node, 'section', true); return; }
            var inside = box.min.x >= range.xmin && box.max.x <= range.xmax
                && box.min.y >= range.zmin && box.max.y <= range.zmax
                && box.min.z >= range.ymin && box.max.z <= range.ymax;
            root.IfcFds.viewer.setVisibilityChannel(node, 'section', inside);
        });
    };

    ClippingController.prototype.playConversionReveal = function (options) {
        options = options || {};
        var fadeMs = Math.max(0, Number(options.fadeMs) || 1400);
        var finalIfcOpacity = typeof options.finalIfcOpacity === 'number' ? options.finalIfcOpacity : 0.15;
        var onComplete = typeof options.onComplete === 'function' ? options.onComplete : function () {};
        var self = this;

        this.resetClipping();
        this.fdsGroup.updateMatrixWorld(true);
        var box = new THREE.Box3().expandByObject(this.fdsGroup);
        if (box.isEmpty()) { onComplete(); return; }

        var height = Math.max(0.01, box.max.y - box.min.y);
        var revealMs = Math.max(0, Number(options.revealMs) || Math.max(2200, Math.min(6000, height * 350)));

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

        self.onOpacityChange(1);

        var startTime = performance.now();
        var animFrame = null;
        var finished = false;

        function cleanup() {
            if (finished) return;
            finished = true;
            savedClips.forEach(function (entry) { entry.material.clippingPlanes = entry.previous; });
            self.onOpacityChange(finalIfcOpacity);
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
                self.onOpacityChange(1 - (1 - finalIfcOpacity) * easeOutCubic(t));
                animFrame = requestAnimationFrame(step);
            } else if (elapsed < fadeMs + revealMs) {
                self.onOpacityChange(finalIfcOpacity);
                var u = (elapsed - fadeMs) / revealMs;
                var currentY = yMin + (yMax - yMin) * easeOutCubic(u);
                revealPlane.constant = currentY;
                animFrame = requestAnimationFrame(step);
            } else {
                cleanup();
                onComplete();
            }
        }
        animFrame = requestAnimationFrame(step);
    };

    ClippingController.prototype.dispose = function () {
        if (this._revealCleanup) {
            this._revealCleanup();
            this._revealCleanup = null;
        }
    };

    root.IfcFds.viewer.ClippingController = ClippingController;
})(window);
