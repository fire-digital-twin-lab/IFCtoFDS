/**
 * Interactive 3D Section Box & Storey Cut Controller for IFCtoFDS Research Workbench.
 * Provides spatial section box clipping, storey-based bounding cuts, and focus.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.workbench = root.IfcFds.workbench || {};
    root.IfcFds.workbench.navigation = root.IfcFds.workbench.navigation || {};

    var selectionStore = root.IfcFds.workbench.state.selectionStore;

    function SectionBoxController(viewerInstance) {
        this.viewer = viewerInstance || null;
        this.activeBounds = null; // { xmin, xmax, ymin, ymax, zmin, zmax }
        this.nativeExtents = null;
    }

    SectionBoxController.prototype.setViewer = function (viewer) {
        this.viewer = viewer;
    };

    SectionBoxController.prototype.setNativeExtents = function (bounds) {
        this.nativeExtents = bounds || null;
        if (bounds) {
            this.activeBounds = Object.assign({}, bounds);
        }
    };

    SectionBoxController.prototype.setRange = function (axis, side, value) {
        var val = Number(value);
        if (!isFinite(val)) return;

        if (!this.activeBounds) {
            this.activeBounds = this.nativeExtents ? Object.assign({}, this.nativeExtents) : {};
        }
        this.activeBounds[axis + side] = val;

        if (this.viewer && typeof this.viewer.setClipPlane === 'function') {
            this.viewer.setClipPlane(axis, side, val);
        }
    };

    SectionBoxController.prototype.cutToStorey = function (storeyName) {
        if (!storeyName) return false;
        var descriptors = selectionStore.getAllDescriptors();
        var storeyItems = descriptors.filter(function (d) {
            return d && d.storey && d.storey.toLowerCase() === String(storeyName).toLowerCase();
        });

        if (!storeyItems.length) return false;

        var zmin = Infinity;
        var zmax = -Infinity;

        storeyItems.forEach(function (it) {
            var b = it.bounds || (it.raw && it.raw.bounding_box);
            if (b) {
                if (b.zmin !== undefined && b.zmin < zmin) zmin = b.zmin;
                if (b.zmax !== undefined && b.zmax > zmax) zmax = b.zmax;
            }
        });

        if (zmin === Infinity || zmax === -Infinity) return false;

        // Add 0.2m safety margin above and below
        var margin = 0.20;
        this.setRange('z', 'min', zmin - margin);
        this.setRange('z', 'max', zmax + margin);

        // Synchronize UI inputs if present
        var zminInput = document.getElementById('clip-zmin');
        var zmaxInput = document.getElementById('clip-zmax');
        if (zminInput) zminInput.value = String(zmin - margin);
        if (zmaxInput) zmaxInput.value = String(zmax + margin);

        return true;
    };

    SectionBoxController.prototype.reset = function () {
        if (!this.viewer) return;
        if (typeof this.viewer.resetClipping === 'function') {
            this.viewer.resetClipping();
        }
        if (this.nativeExtents) {
            this.activeBounds = Object.assign({}, this.nativeExtents);
        }
    };

    var defaultSectionBox = new SectionBoxController();

    root.IfcFds.workbench.navigation.SectionBoxController = SectionBoxController;
    root.IfcFds.workbench.navigation.sectionBox = defaultSectionBox;

})(typeof window !== 'undefined' ? window : globalThis);
