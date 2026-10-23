(function (ns) {
    var helpers = ns.viewer.geometryHelpers;
    var clearGroup = helpers.clearGroup;
    var toThree = helpers.toThree;
    var categoryForIfcType = helpers.categoryForIfcType;
    function SceneViewer(container, onSelect, options) {
        this.lifecycle = ns.core.createLifecycle();
        this.geometryClient = options && options.geometryClient || ns.api.geometry;
        this.container = container;
        this.onSelect = onSelect || function () {};
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf4f5f8);
        this.camera = new THREE.PerspectiveCamera(55, 1, 0.1, 5000);
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.localClippingEnabled = true;
        // Six clipping planes track the user's clip-bar sliders. Plane normals point INTO the
        // kept region. Inactive (no clip) = constant pushed far away so nothing gets cut.
        this.clipPlanes = [
            new THREE.Plane(new THREE.Vector3(1, 0, 0), Infinity),   // X min (keep X >= xmin)
            new THREE.Plane(new THREE.Vector3(-1, 0, 0), Infinity),  // X max (keep X <= xmax)
            new THREE.Plane(new THREE.Vector3(0, 1, 0), Infinity),   // Y min
            new THREE.Plane(new THREE.Vector3(0, -1, 0), Infinity),  // Y max
            new THREE.Plane(new THREE.Vector3(0, 0, 1), Infinity),   // Z min
            new THREE.Plane(new THREE.Vector3(0, 0, -1), Infinity)   // Z max
        ];
        this.clipBoundsNative = null;
        this.renderer.clippingPlanes = this.clipPlanes;
        this.controls = null;
        this.walkControls = null;
        this.onNavigationModeChange = function () {};
        this.navigationMode = 'orbit';
        this.walkFloorY = 0;
        this.walkEyeHeight = 1.65;
        this.walkPlaced = false;
        this.walkVelocityY = 0;
        this.walkSpeed = 1.8;
        this.walkRunMultiplier = 2.5;
        this.walkRadius = 0.3;
        this.walkGravity = 9.81;
        this.walkStepHeight = 0.45;
        this.walkRaycaster = new THREE.Raycaster();
        this.walkSavedCamera = null;
        this.walkMovement = {
            forward: false,
            backward: false,
            left: false,
            right: false,
            jump: false,
            fast: false
        };
        this.lastFrameTime = 0;
        this.fdsGroup = new THREE.Group();
        this.ifcGroup = new THREE.Group();
        this.meshGroup = new THREE.Group();
        this.obstGroup = new THREE.Group();
        this.ventGroup = new THREE.Group();
        this.holeGroup = new THREE.Group();
        this.geomGroup = new THREE.Group();
        this.ifcSolidGroup = new THREE.Group();
        this.ifcReferenceGroup = new THREE.Group();
        this.groundGrid = null;
        this.raycaster = new THREE.Raycaster();
        this.raycaster.params.Line.threshold = 0.05;
        this.mouse = new THREE.Vector2();
        this.theme = 'light';
        this.viewMode = 'overlay';
        this.showIfcEdges = true;
        this.opacity = 0.72;
        this.ifcOpacity = 1;
        this.hoveredObject = null;
        this.selectedObjects = [];
        this.selectionHelpers = [];
        this.tooltip = null;

        this.init();
    }

    SceneViewer.prototype.init = function () {
        this.renderer.setPixelRatio(window.devicePixelRatio || 1);
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.outputEncoding = THREE.sRGBEncoding;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.0;
        this.container.appendChild(this.renderer.domElement);

        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.08;
        this.walkControls = new THREE.PointerLockControls(this.camera, this.renderer.domElement);

        this.camera.position.set(10, 8, 10);
        this.controls.target.set(0, 0, 0);

        var hemi = new THREE.HemisphereLight(0xffffff, 0xb8bcc4, 0.9);
        var key = new THREE.DirectionalLight(0xffffff, 0.8);
        key.position.set(6, 14, 8);
        var fill = new THREE.DirectionalLight(0xffffff, 0.2);
        fill.position.set(-6, 4, -8);
        this.scene.add(hemi, key, fill);

        this.groundGrid = new THREE.GridHelper(2000, 2000, 0xa9afbd, 0xd8dae2);
        this.groundGrid.name = 'Ground grid';
        this.groundGrid.material.transparent = true;
        this.groundGrid.material.opacity = 0.42;
        this.groundGrid.material.depthWrite = false;
        // Opt the ground grid out of the global clipping planes — the grid is a UI helper
        // that should always extend to the camera horizon regardless of the clip-bar state.
        this.groundGrid.material.clippingPlanes = [];
        this.scene.add(this.groundGrid);

        this.fdsGroup.name = 'FDS';
        this.ifcGroup.name = 'IFC';
        this.ifcSolidGroup.name = 'IFC solids';
        this.ifcReferenceGroup.name = 'IFC reference';
        this.scene.add(this.fdsGroup, this.ifcGroup);
        this.fdsGroup.add(this.meshGroup, this.obstGroup, this.ventGroup, this.holeGroup, this.geomGroup);
        this.ifcGroup.add(this.ifcSolidGroup, this.ifcReferenceGroup);
        this.ifcReferenceGroup.visible = false;

        this.tooltip = document.createElement('div');
        this.tooltip.className = 'hover-tooltip';
        this.tooltip.hidden = true;
        this.container.appendChild(this.tooltip);

        this.lifecycle.listen(window, 'resize', this.resize.bind(this));
        this.lifecycle.listen(window, 'keydown', this.handleWalkKey.bind(this, true));
        this.lifecycle.listen(window, 'keyup', this.handleWalkKey.bind(this, false));
        this.lifecycle.listen(this.renderer.domElement, 'click', this.handleClick.bind(this));
        this.lifecycle.listen(this.renderer.domElement, 'pointermove', this.handlePointerMove.bind(this));
        this.lifecycle.listen(this.renderer.domElement, 'pointerleave', this.clearHover.bind(this));
        this.lifecycle.listen(this.renderer.domElement, 'pointerdown', this.handlePointerDown.bind(this));
        this.lifecycle.listen(this.renderer.domElement, 'pointerup', this.handlePointerUp.bind(this));
        this.marqueeEl = this.container.querySelector('#marquee') || document.getElementById('marquee');
        this.marqueeState = null;
        this.lifecycle.listen(this.walkControls, 'unlock', this.handleWalkUnlock.bind(this));
        this.resize();
        this.animate();
    };

    SceneViewer.prototype.animate = function (time) {
        if (this.disposed) return;
        this.animationFrame = requestAnimationFrame(this.animate.bind(this));
        // Leave CPU/GPU time for payload decoding while a large import grows.
        if (this.backendPreviewLoading && time - (this.lastPreviewFrame || 0) < 1000) return;
        this.lastPreviewFrame = time;
        var delta = this.lastFrameTime ? Math.min((time - this.lastFrameTime) / 1000, 0.1) : 0;
        this.lastFrameTime = time;
        if (this.navigationMode === 'walk') this.updateWalkMovement(delta);
        else this.controls.update();
        this.updateGroundGrid();
        this.renderer.render(this.scene, this.camera);
    };

    SceneViewer.prototype.updateGroundGrid = function () {
        if (!this.groundGrid || !this.controls) return;
        var target = this.navigationMode === 'walk' ? this.camera.position : this.controls.target;
        this.groundGrid.position.x = Math.round(target.x);
        this.groundGrid.position.z = Math.round(target.z);
    };

    SceneViewer.prototype.resize = function () {
        var width = Math.max(1, this.container.clientWidth);
        var height = Math.max(1, this.container.clientHeight);
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    };

    // Canonical view shortcuts (1=front, 2=back, 3=left, 4=right, 5=top, 6=bottom, 0=iso),
    // matching ProfRino/fds-viewer's keymap. Frame is computed from the visible IFC + FDS
    // groups so the building stays in shot regardless of which model is loaded.

    // Arrow-key orbit/zoom for the desktop user, mirroring how ProfRino/fds-viewer drives
    // the camera with the keyboard:
    //   left  / right  → orbit yaw around the target (counter-/clockwise)
    //   up    / down   → orbit pitch (raise / lower the camera)
    //   shift + left/right → strafe target sideways instead of orbit
    //   shift + up/down    → dolly in / out (the same effect the mouse wheel has)
    // The walk-mode keyboard handler owns WASD + arrow keys separately and takes priority,
    // so this method early-outs when navigationMode is 'walk'.

    // Clipping is driven by 6 sliders along the bottom of the viewer. The slider values are
    // in IFC-native coordinates (X east, Y north, Z up); we translate to Three.js world axes
    // here because toThree() does a Y/Z swap. clipBoundsNative caches the world span so the
    // sliders stay in lock-step with the model whenever a new IFC is loaded.

    // axis: 'x' | 'y' | 'z', side: 'min' | 'max'. Value is in IFC-native coords.

    // Per-primitive discrete clipping for the FDS group. An OBST/GEOM/VENT mesh is shown
    // only when its full world bbox sits inside the current clip box — so as the user drags
    // a clip slider, individual primitives appear/disappear whole rather than being sliced.
    // The smooth fragment-clip is still applied to the IFC materials.

    // Plays a two-phase "reveal" animation after a conversion: IFC snaps to full opacity
    // and eases away to zero, then the FDS group is uncovered bottom-up by a temporary
    // per-material clip plane. Falls back gracefully (and instantly) if the FDS group is
    // empty or clipping isn't supported. Cleans up its own state on finish so the user's
    // own clip-bar settings keep working.

    // Used when the model came from the lightweight meta builder and doesn't carry IFC-native
    // bounds. Computes the world box from the freshly-added IFC group and frames it.

    // Mounts geometry produced by the web-ifc WASM engine. Walls/slabs come pre-cut around
    // their window/door openings (web-ifc applies IfcRelVoidsElement booleans natively), so
    // the preview shows real voids. web-ifc converts IFC Z-up to Three Y-up with Rx(-90°)
    // (a rotation), while the rest of the scene goes through toThree() (a Y/Z swap, i.e. a
    // mirror). The two differ only in the sign of the depth axis, so a Z-flip on the web-ifc
    // matrices is enough to land them in the same world space as the FDS overlay.

    // Builds a cached list of HOLE world-space bboxes for the current walk step. Called
    // once per movement update so each individual ray cast can reuse it.

    // Tracks per-category visibility (structure/fills/other). Re-evaluated on every load and
    // on every checkbox toggle so meshes added later (web-ifc deferred swap) honor the state.

    // Hides FDS / IFC meshes whose source IFC stepId is in the source-exclusion set OR whose
    // own primitive id is in the item-exclusion set. The first is the "delete the whole IFC
    // element" path; the second is the "delete just this OBST/GEOM box" path. Reapplies on
    // every load and on undo so toggling them on and off doesn't rebuild the scene.

    // Shift+drag starts a marquee selection that picks every visible IFC / OBST / GEOM mesh
    // whose bbox-center projects inside the rectangle. A pure Shift+click (no movement past
    // MARQUEE_MIN_DRAG_PX) still falls through to handleClick so add-to-selection works.

    ns.viewer.installCameraController(SceneViewer, helpers);
    ns.viewer.installWalkController(SceneViewer, helpers);
    ns.viewer.installClippingController(SceneViewer, helpers);
    ns.viewer.installMeshFactory(SceneViewer, helpers);
    ns.viewer.installGeometryLoader(SceneViewer, helpers);
    ns.viewer.installSelectionController(SceneViewer, helpers);
    ns.viewer.installAppearanceController(SceneViewer, helpers);

    SceneViewer.prototype.dispose = function () {
        if (this.disposed) return;
        this.disposed = true;
        this.lifecycle.destroy();
        if (this.animationFrame) cancelAnimationFrame(this.animationFrame);
        if (this.cancelVerifiedLoad) this.cancelVerifiedLoad();
        if (this.walkControls && this.walkControls.isLocked) this.walkControls.unlock();
        if (this.controls && this.controls.dispose) this.controls.dispose();
        if (this.walkControls && this.walkControls.dispose) this.walkControls.dispose();
        clearGroup(this.fdsGroup);
        clearGroup(this.ifcGroup);
        clearGroup(this.scene);
        if (this.tooltip) this.tooltip.remove();
        if (this.renderer && this.renderer.dispose) this.renderer.dispose();
        if (this.renderer && this.renderer.domElement) this.renderer.domElement.remove();
    };

    ns.viewer.SceneViewer = SceneViewer;
    ns.viewer.categoryForIfcType = categoryForIfcType;
    ns.viewer.clearGroup = clearGroup;
})(window.IfcFds);
