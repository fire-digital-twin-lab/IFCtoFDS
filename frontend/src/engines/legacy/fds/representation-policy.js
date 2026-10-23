(function (ns) {
    ns.fds.legacyFactories = ns.fds.legacyFactories || {};
    ns.fds.legacyFactories.createRepresentationPolicy = function (kernel, constants) {
        var allOpeningsAxisAligned;
        var fillsBoundingBox;
        var flatAxisFromBounds;
        var voxelizeElement;


        function strategyForElement(mode, element, options) {
            if (hasForcedObstOverride(element, options)) return 'voxel';
            if (roleForElement(element) === 'opening' && options && options.includeFillSolids) return 'closure';
            if (mode === 'geom') return 'geom';
            if (mode === 'hybrid') {
                var boxThreshold = (options && typeof options.boxFriendlyThreshold === 'number')
                    ? options.boxFriendlyThreshold : 0.8;
                // Slider extremes are exclusive overrides: minimum (0.5) forces voxel OBST on
                // every element regardless of type or alignment; maximum (1.0) forces detailed
                // GEOM on everything, even simple boxy walls.
                if (boxThreshold <= 0.5 + 1e-6) return 'voxel';
                if (boxThreshold >= 1.0 - 1e-6) return 'geom';
                // Zero-extent guard: a slab whose parsed mesh is *flat* (parser missed the
                // extrusion, so the mesh is the 2-D polygon triangulated in place) gets
                // auto-extruded with a default thickness inside voxelizeElement. Truly
                // degenerate elements (zero extent in 2 axes) are sent to GEOM.
                var b = element.bounds;
                if (b) {
                    var zeroAxes = 0;
                    if (b.xmax - b.xmin < 1e-4) zeroAxes += 1;
                    if (b.ymax - b.ymin < 1e-4) zeroAxes += 1;
                    if (b.zmax - b.zmin < 1e-4) zeroAxes += 1;
                    if (zeroAxes >= 2) return 'geom';
                }
                if (element.openings && element.openings.length) {
                    // Experimental: when the user opted in to &HOLE-carved walls/slabs, take the
                    // OBST+HOLE path for any axis-aligned-dominant box-friendly element whose
                    // openings are themselves axis-aligned rectangles. Otherwise fall back to
                    // the voxel carve (which handles arched/circular/curved openings).
                    // Tolerance 0.90 (not 0.95) because real-world wall meshes carry small
                    // off-axis chunks at end caps / cutout corners from the parser's
                    // triangulation. The bbox-vs-bbox HOLE math doesn't care about that —
                    // it only matters that the wall is roughly box-shaped and the openings
                    // are themselves axis-aligned rectangles.
                    //
                    // fillsBoundingBox is the critical guard: an L- or U-shaped slab passes
                    // every other check above (its faces are still all axis-aligned because the
                    // L outline is just a planar polygon) but its bbox is much bigger than its
                    // actual footprint. Without this check the OBST+HOLE strategy emits the
                    // bbox as one rectangular OBST, losing the L outline. Send those to voxel.
                    if (options && options.useObstHoles
                        && isBoxFriendlyType(element)
                        && isAxisAlignedDominant(element, 0.90)
                        && fillsBoundingBox(element, 0.95)
                        && allOpeningsAxisAligned(element)) {
                        return 'obst_holes';
                    }
                    return isAxisAlignedDominant(element) ? 'voxel' : 'geom';
                }
                if (shouldUseObstInHybrid(element)) return 'obst';
                // For the wall/slab/beam/column family we accept a more permissive aligned-area
                // threshold because mitred corner joinery is very common. Non-box-friendly types
                // (stair stringers, railings, curved roofs) stay on the strict 0.9 path.
                if (isBoxFriendlyType(element) && isAxisAlignedDominant(element, boxThreshold)) return 'voxel';
                return 'geom';
            }
            return 'voxel';
        }

        function hasForcedObstOverride(element, options) {
            var stepId = String(element && element.stepId || '').replace(/^#/, '');
            return forcedObstStepIds(options).some(function (forcedStepId) {
                return String(forcedStepId).replace(/^#/, '') === stepId;
            });
        }

        function forcedObstStepIds(options) {
            return options && Array.isArray(options.forceObstStepIds) ? options.forceObstStepIds : [];
        }

        function exportableElements(ifcScene, options) {
            return ifcScene && ifcScene.elements
                ? ifcScene.elements.filter(function (element) {
                    return isExportableElement(element, options || {});
                })
                : [];
        }

        function isExportableElement(element, options) {
            if (isExcludedStepId(element, options)) return false;
            var role = roleForElement(element);
            if (role === 'opening') return !!options.includeFillSolids;
            if (role === 'review') return !!options.includeReviewSolids;
            if (role === 'ignore') return false;
            return element.convertible !== false && element.exportAsSolid !== false;
        }

        function isExcludedStepId(element, options) {
            if (!element || !options || !Array.isArray(options.excludedStepIds) || !options.excludedStepIds.length) return false;
            var stepId = String(element.stepId || '').replace(/^#/, '');
            return options.excludedStepIds.some(function (excluded) {
                return String(excluded).replace(/^#/, '') === stepId;
            });
        }

        function roleForElement(element) {
            if (element.fdsRole) return element.fdsRole;
            if (element.exportAsSolid === false) return element.convertible === false ? 'ignore' : 'opening';
            return 'solid';
        }

    var BOX_FRIENDLY_TYPES = {
        IFCWALL: true,
        IFCWALLSTANDARDCASE: true,
        IFCSLAB: true,
        // IFCROOF is included so flat roof decks (tapered-insulation roofs, concrete-deck
        // roofs) get the L/U-outline voxel treatment. Sloped roofs (gable / hip / barrel)
        // still fall through to GEOM because their large sloped faces drop the area-weighted
        // aligned ratio below the 0.8 box-friendly threshold.
        IFCROOF: true,
        IFCBEAM: true,
        IFCCOLUMN: true,
        IFCPLATE: true,
        // IFCMEMBER stays off this list: it is the type used for stair stringers (and
        // diagonal braces, sloped struts), which can still hit 85–92% aligned area
        // even though their main faces are sloped. Letting them through the permissive
        // 0.8 box-friendly path turns stair geometry into ugly block-art.
        IFCDOOR: true,
        IFCWINDOW: true,
        IFCFURNISHINGELEMENT: true,
        IFCBUILDINGELEMENTPROXY: true
    };

        function isBoxFriendlyType(element) {
            return !!BOX_FRIENDLY_TYPES[element && element.ifcType];
        }

        function shouldUseObstInHybrid(element) {
            if (!isBoxFriendlyType(element)) return false;
            // A flat polygon (parser failed to extrude the slab) is degenerate for the
            // axis-aligned-box check below: every triangle's normal points purely ±flat-axis
            // and every vertex sits at bounds.{flat}min === bounds.{flat}max, so the test
            // reports a "perfect axis-aligned box" and routes the slab to a single bounding
            // OBST — ignoring the L/U outline. Send these to voxel (the inflater rebuilds the
            // outline) instead.
            if (flatAxisFromBounds(element && element.bounds) >= 0) return false;
            // L / U / C / T shaped slabs and walls would also get collapsed to their bbox
            // here. fillsBoundingBox rejects anything whose footprint covers less than 95% of
            // its bbox — those go on to voxel so the outline is preserved cell-by-cell.
            if (!fillsBoundingBox(element, 0.95)) return false;
            return isAxisAlignedBoxLike(element);
        }

        function isAxisAlignedBoxLike(element) {
            if (!element || !element.mesh || !element.mesh.vertices || !element.mesh.faces || !element.bounds) return false;
            var b = element.bounds;
            var eps = 1e-3;
            var vertices = element.mesh.vertices;
            var faces = element.mesh.faces;

            for (var i = 0; i < faces.length; i++) {
                var f = faces[i];
                var v0 = vertices[f[0]], v1 = vertices[f[1]], v2 = vertices[f[2]];
                var ex = v1[0] - v0[0], ey = v1[1] - v0[1], ez = v1[2] - v0[2];
                var fx = v2[0] - v0[0], fy = v2[1] - v0[1], fz = v2[2] - v0[2];
                var nx = ey * fz - ez * fy;
                var ny = ez * fx - ex * fz;
                var nz = ex * fy - ey * fx;
                var nl = Math.sqrt(nx * nx + ny * ny + nz * nz);
                if (nl < 1e-10) continue;
                nx /= nl; ny /= nl; nz /= nl;

                var ax = Math.abs(nx), ay = Math.abs(ny), az = Math.abs(nz);
                var mx = Math.max(ax, ay, az);
                if (mx < 0.999) return false;

                var axis;
                if (ax >= ay && ax >= az) axis = 0;
                else if (ay >= ax && ay >= az) axis = 1;
                else axis = 2;

                var axisKey = ['x', 'y', 'z'][axis];
                var coord = v0[axis];
                var atMin = Math.abs(coord - b[axisKey + 'min']) <= eps;
                var atMax = Math.abs(coord - b[axisKey + 'max']) <= eps;
                if (!atMin && !atMax) return false;
            }
            return true;
        }

    // Area-weighted check: is the element dominantly made of axis-aligned faces?
    // Robust to opening cutouts (window/door reveals), so walls and flat slabs with
    // openings still qualify for voxelization, while sloped/curved surfaces (roofs)
    // fall through to detailed GEOM instead of being stair-stepped.
        function isAxisAlignedDominant(element, threshold) {
            if (!element || !element.mesh || !element.mesh.vertices || !element.mesh.faces) return false;
            var vertices = element.mesh.vertices;
            var faces = element.mesh.faces;
            var alignedArea = 0;
            var totalArea = 0;
            var minRatio = typeof threshold === 'number' ? threshold : 0.9;

            for (var i = 0; i < faces.length; i++) {
                var f = faces[i];
                var v0 = vertices[f[0]], v1 = vertices[f[1]], v2 = vertices[f[2]];
                var ex = v1[0] - v0[0], ey = v1[1] - v0[1], ez = v1[2] - v0[2];
                var fx = v2[0] - v0[0], fy = v2[1] - v0[1], fz = v2[2] - v0[2];
                var nx = ey * fz - ez * fy;
                var ny = ez * fx - ex * fz;
                var nz = ex * fy - ey * fx;
                var doubleArea = Math.sqrt(nx * nx + ny * ny + nz * nz);
                if (doubleArea < 1e-12) continue;

                totalArea += doubleArea;
                var mx = Math.max(Math.abs(nx), Math.abs(ny), Math.abs(nz)) / doubleArea;
                if (mx >= 0.999) alignedArea += doubleArea;
            }

            if (totalArea <= 0) return false;
            return (alignedArea / totalArea) >= minRatio;
        }

    // Returns 0/1/2 for the flat axis (x/y/z) if the mesh bounds are degenerate on exactly
    // one axis, or -1 if the bounds are 3-D (no inflation needed) or worse (two/three axes
    // collapsed — too degenerate to recover; the strategy router sends those to GEOM).

        kernel.exportableElements = exportableElements;
        kernel.forcedObstStepIds = forcedObstStepIds;
        kernel.hasForcedObstOverride = hasForcedObstOverride;
        kernel.isAxisAlignedBoxLike = isAxisAlignedBoxLike;
        kernel.isAxisAlignedDominant = isAxisAlignedDominant;
        kernel.isBoxFriendlyType = isBoxFriendlyType;
        kernel.isExcludedStepId = isExcludedStepId;
        kernel.isExportableElement = isExportableElement;
        kernel.roleForElement = roleForElement;
        kernel.shouldUseObstInHybrid = shouldUseObstInHybrid;
        kernel.strategyForElement = strategyForElement;
        return function bindDependencies() {
            allOpeningsAxisAligned = kernel.allOpeningsAxisAligned;
            fillsBoundingBox = kernel.fillsBoundingBox;
            flatAxisFromBounds = kernel.flatAxisFromBounds;
            voxelizeElement = kernel.voxelizeElement;
        };
    };
})(window.IfcFds);
