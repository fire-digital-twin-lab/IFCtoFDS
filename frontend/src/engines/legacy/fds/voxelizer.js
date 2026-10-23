(function (ns) {
    ns.fds.legacyFactories = ns.fds.legacyFactories || {};
    ns.fds.legacyFactories.createVoxelizer = function (kernel, constants) {
        var boundsForVertices;
        var defaultSlabThickness;
        var flatAxisFromBounds;
        var inflateFlatMesh;
        var isAxisAlignedDominant;
        var normalizeOpeningVoxelPolicy;
        var thinPrismAxis;
        var thinnestAxis;


        function voxelizeElement(element, voxelSize, openingThickening, openingVoxelPolicy) {
            var size = Math.max(0.01, Number(voxelSize) || 0.1);
            var holePolicy = normalizeOpeningVoxelPolicy(openingVoxelPolicy);
            var mesh = element && element.mesh;
            var bounds = element && element.bounds;
            if (!mesh || !mesh.vertices || !mesh.faces || !bounds) return { boxes: [], voxelCount: 0 };

            // Some IFC files (notably the school file's Basic Roof / Floor slabs) deliver slab
            // representations that the parser couldn't extrude, so element.mesh ends up as the
            // 2-D floor-plan polygon triangulated in place — every vertex at the same Z, no
            // enclosed volume for point-in-mesh tests. Auto-inflate that polygon downward into
            // a thin solid so the existing voxelizer can trace the actual L / U outline.
            var workingMesh = mesh;
            var workingBounds = bounds;
            var flatAxis = flatAxisFromBounds(bounds);
            if (flatAxis >= 0) {
                var inflated = inflateFlatMesh(mesh, bounds, flatAxis, defaultSlabThickness(element));
                if (inflated) {
                    workingMesh = inflated.mesh;
                    workingBounds = inflated.bounds;
                }
            }

            // Beyond the perfectly-flat case, a *thin* axis-aligned prism (concrete-deck roof
            // ~0.4 m thick over a 60 m × 50 m footprint, or a slab with real but small Z extent)
            // also collapses to a one-slice rasterization. Require both a clear thin axis AND
            // ≥95% axis-aligned faces — without the alignment check we'd wrongly prismatize a
            // thin sloped roof and stair-step its slope. Skip for elements with openings to
            // avoid carving an opening through every Z layer when the opening is local to one.
            var prismAxis = flatAxis;
            if (prismAxis < 0) {
                var maybeThin = thinPrismAxis(workingBounds);
                if (maybeThin >= 0
                    && (!element.openings || !element.openings.length)
                    && isAxisAlignedDominant(element, 0.95)) {
                    prismAxis = maybeThin;
                }
            }

            var epsilon = size * 1e-7;
            var range = {
                xmin: Math.floor(workingBounds.xmin / size),
                xmax: Math.ceil((workingBounds.xmax - epsilon) / size),
                ymin: Math.floor(workingBounds.ymin / size),
                ymax: Math.ceil((workingBounds.ymax - epsilon) / size),
                zmin: Math.floor(workingBounds.zmin / size),
                zmax: Math.ceil((workingBounds.zmax - epsilon) / size)
            };
            // For a flat-inflated slab (parser failed to extrude), occupancy is identical on
            // every Z layer — the inflated solid is a prism. Compute one layer and replicate it
            // up so the L/U outline is preserved without paying for k× the per-cell work and
            // without blowing the candidate cap on a 60 m × 50 m floor plan.
            var effectiveCount = (range.xmax - range.xmin) * (range.ymax - range.ymin) * (range.zmax - range.zmin);
            var prismMode = prismAxis >= 0;
            if (prismMode) {
                // The slice loop below collapses the prism axis to a single layer, so multiply
                // out two dimensions instead of three.
                var dimX = range.xmax - range.xmin;
                var dimY = range.ymax - range.ymin;
                var dimZ = range.zmax - range.zmin;
                if (prismAxis === 0) effectiveCount = 1 * dimY * dimZ;
                else if (prismAxis === 1) effectiveCount = dimX * 1 * dimZ;
                else effectiveCount = dimX * dimY * 1;
            }
            // Hard ceiling on the *effective* candidate count: above this, voxelization runs
            // into minutes per element on huge foundation pads. Surface the cap upstream so the
            // caller can fall back to GEOM (which keeps opening cutouts) instead of a misleading
            // rectangular bounding OBST. Prism mode brings huge flat slabs comfortably under
            // the cap because the work scales with one slice instead of all k layers.
            if (effectiveCount > 500000) {
                return { boxes: [], voxelCount: 0, oversize: effectiveCount };
            }

            var triangles = prepareTriangles(workingMesh);
            var openingTriangleSets = [];
            // Parallel array of bboxes (with the same axis-thickening as the triangle sets).
            // For axis-aligned-dominant openings (the common window/door case) the bbox is the
            // opening, and the cheap bbox test is robust against the ray-casting boundary bugs
            // that left "phantom holes" one cell wide along the opening edges.
            var openingBboxes = [];
            (element.openings || []).forEach(function (opening) {
                var sets = prepareOpeningTriangleSets(opening.mesh, openingThickening);
                var bbox = inflatedOpeningBbox(opening.mesh, openingThickening);
                var axisAligned = !!opening.mesh && isAxisAlignedDominant({ mesh: opening.mesh }, 0.95);
                sets.forEach(function (trianglesForOpening) {
                    if (!trianglesForOpening.length) return;
                    openingTriangleSets.push(trianglesForOpening);
                    openingBboxes.push(axisAligned && bbox ? bbox : null);
                });
            });
            var occupied = {};
            var halfSize = Math.max(size / 2 - epsilon, size * 0.499);

            if (prismMode) {
                // Compute occupancy on one slice mid-way through the prism axis, then duplicate
                // it into every layer along that axis. For a true axis-aligned prism (flat slab
                // after inflation, or a thin axis-aligned roof) the cross-section is invariant
                // along the prism axis, so one slice = the whole element.
                var sliceIdxX = range.xmin + Math.floor((range.xmax - range.xmin) / 2);
                var sliceIdxY = range.ymin + Math.floor((range.ymax - range.ymin) / 2);
                var sliceIdxZ = range.zmin + Math.floor((range.zmax - range.zmin) / 2);
                var occupiedSlice = {};
                for (var siy = range.ymin; siy < range.ymax; siy += 1) {
                    if (prismAxis === 1 && siy !== sliceIdxY) continue;
                    for (var six = range.xmin; six < range.xmax; six += 1) {
                        if (prismAxis === 0 && six !== sliceIdxX) continue;
                        for (var siz = range.zmin; siz < range.zmax; siz += 1) {
                            if (prismAxis === 2 && siz !== sliceIdxZ) continue;
                            var sc = [
                                (six + 0.5) * size,
                                (siy + 0.5) * size,
                                (siz + 0.5) * size
                            ];
                            if (voxelIsOccupied(triangles, sc, halfSize) &&
                                !openingCarvesVoxel(openingTriangleSets, openingBboxes, sc, halfSize, holePolicy)) {
                                occupiedSlice[voxelKey(six, siy, siz)] = true;
                            }
                        }
                    }
                }
                // Replicate the slice into every layer along the prism axis.
                Object.keys(occupiedSlice).forEach(function (key) {
                    var parts = key.split(',');
                    var bx = parseInt(parts[0], 10);
                    var by = parseInt(parts[1], 10);
                    var bz = parseInt(parts[2], 10);
                    if (prismAxis === 0) {
                        for (var rx = range.xmin; rx < range.xmax; rx += 1) {
                            occupied[voxelKey(rx, by, bz)] = true;
                        }
                    } else if (prismAxis === 1) {
                        for (var ry = range.ymin; ry < range.ymax; ry += 1) {
                            occupied[voxelKey(bx, ry, bz)] = true;
                        }
                    } else {
                        for (var rz = range.zmin; rz < range.zmax; rz += 1) {
                            occupied[voxelKey(bx, by, rz)] = true;
                        }
                    }
                });
            } else {
                for (var iz = range.zmin; iz < range.zmax; iz += 1) {
                    for (var iy = range.ymin; iy < range.ymax; iy += 1) {
                        for (var ix = range.xmin; ix < range.xmax; ix += 1) {
                            var center = [
                                (ix + 0.5) * size,
                                (iy + 0.5) * size,
                                (iz + 0.5) * size
                            ];
                            if (voxelIsOccupied(triangles, center, halfSize) &&
                                !openingCarvesVoxel(openingTriangleSets, openingBboxes, center, halfSize, holePolicy)) {
                                occupied[voxelKey(ix, iy, iz)] = true;
                            }
                        }
                    }
                }
            }

            var voxelCount = Object.keys(occupied).length;
            return {
                boxes: mergeOccupiedVoxels(occupied, size),
                voxelCount: voxelCount
            };
        }

        function prepareOpeningTriangleSets(mesh, openingThickening) {
            var margin = Math.max(0, Number(openingThickening) || 0);
            if (!mesh || !mesh.vertices || !mesh.faces) return [];
            if (!margin) return splitTrianglesByConnectedFaces(mesh);

            var bounds = boundsForVertices(mesh.vertices);
            var axis = thinnestAxis(bounds);
            var minKey = ['xmin', 'ymin', 'zmin'][axis];
            var maxKey = ['xmax', 'ymax', 'zmax'][axis];
            var center = (bounds[minKey] + bounds[maxKey]) / 2;
            var inflated = {
                vertices: mesh.vertices.map(function (vertex) {
                    var copy = vertex.slice();
                    if (copy[axis] < center) copy[axis] -= margin;
                    if (copy[axis] > center) copy[axis] += margin;
                    return copy;
                }),
                faces: mesh.faces
            };
            return splitTrianglesByConnectedFaces(inflated);
        }

    // Same axis-thickening as prepareOpeningTriangleSets, but returns the bbox of the
    // inflated polygon rather than its triangles. Used by openingCarvesVoxel as a robust
    // fast path: for axis-aligned-rectangular openings (almost every IFC window/door) the
    // bbox IS the opening volume, and a simple point-in-bbox test is exact and immune to
    // the ray-casting parity bug that pointInsideMesh suffers at axis-aligned mesh corners.
        function inflatedOpeningBbox(mesh, openingThickening) {
            if (!mesh || !mesh.vertices || !mesh.vertices.length) return null;
            var bounds = boundsForVertices(mesh.vertices);
            if (!bounds) return null;
            var margin = Math.max(0, Number(openingThickening) || 0);
            if (!margin) return bounds;
            var axis = thinnestAxis(bounds);
            var minKey = ['xmin', 'ymin', 'zmin'][axis];
            var maxKey = ['xmax', 'ymax', 'zmax'][axis];
            var inflated = {
                xmin: bounds.xmin, xmax: bounds.xmax,
                ymin: bounds.ymin, ymax: bounds.ymax,
                zmin: bounds.zmin, zmax: bounds.zmax
            };
            inflated[minKey] -= margin;
            inflated[maxKey] += margin;
            return inflated;
        }

        function openingCarvesVoxel(openingTriangleSets, openingBboxes, center, halfSize, openingVoxelPolicy) {
            for (var i = 0; i < openingTriangleSets.length; i += 1) {
                var bbox = openingBboxes && openingBboxes[i];
                if (bbox) {
                    // Fast and numerically exact path for axis-aligned-rectangular openings.
                    // 'smaller': cell center strictly inside opening bbox → cell carved.
                    // 'larger':  cell volume overlaps opening bbox (any touch) → cell carved.
                    if (openingVoxelPolicy === 'smaller') {
                        if (center[0] > bbox.xmin && center[0] < bbox.xmax
                            && center[1] > bbox.ymin && center[1] < bbox.ymax
                            && center[2] > bbox.zmin && center[2] < bbox.zmax) return true;
                    } else {
                        if (center[0] + halfSize > bbox.xmin && center[0] - halfSize < bbox.xmax
                            && center[1] + halfSize > bbox.ymin && center[1] - halfSize < bbox.ymax
                            && center[2] + halfSize > bbox.zmin && center[2] - halfSize < bbox.zmax) return true;
                    }
                    continue;
                }
                // Non-axis-aligned opening (arched window, circular porthole, etc.) — fall back
                // to the mesh-based test.
                var trianglesForOpening = openingTriangleSets[i];
                if (openingVoxelPolicy === 'smaller'
                    ? pointInsideMesh(center, trianglesForOpening)
                    : voxelIsOccupied(trianglesForOpening, center, halfSize)) return true;
            }
            return false;
        }

        function splitTrianglesByConnectedFaces(mesh) {
            var triangles = prepareTriangles(mesh);
            var facesByVertex = {};
            var visited = {};
            var sets = [];

            mesh.faces.forEach(function (face, faceIndex) {
                face.forEach(function (vertexIndex) {
                    facesByVertex[vertexIndex] = facesByVertex[vertexIndex] || [];
                    facesByVertex[vertexIndex].push(faceIndex);
                });
            });

            mesh.faces.forEach(function (face, startIndex) {
                if (visited[startIndex]) return;

                var pending = [startIndex];
                var set = [];
                visited[startIndex] = true;

                while (pending.length) {
                    var faceIndex = pending.pop();
                    set.push(triangles[faceIndex]);
                    mesh.faces[faceIndex].forEach(function (vertexIndex) {
                        facesByVertex[vertexIndex].forEach(function (connectedFaceIndex) {
                            if (visited[connectedFaceIndex]) return;
                            visited[connectedFaceIndex] = true;
                            pending.push(connectedFaceIndex);
                        });
                    });
                }

                sets.push(set);
            });

            return sets;
        }

        function prepareTriangles(mesh) {
            if (!mesh || !mesh.vertices || !mesh.faces) return [];
            return mesh.faces.map(function (face) {
                var vertices = [mesh.vertices[face[0]], mesh.vertices[face[1]], mesh.vertices[face[2]]];
                return {
                    vertices: vertices,
                    bounds: triangleBounds(vertices)
                };
            });
        }

        function triangleBounds(vertices) {
            return {
                xmin: Math.min(vertices[0][0], vertices[1][0], vertices[2][0]),
                xmax: Math.max(vertices[0][0], vertices[1][0], vertices[2][0]),
                ymin: Math.min(vertices[0][1], vertices[1][1], vertices[2][1]),
                ymax: Math.max(vertices[0][1], vertices[1][1], vertices[2][1]),
                zmin: Math.min(vertices[0][2], vertices[1][2], vertices[2][2]),
                zmax: Math.max(vertices[0][2], vertices[1][2], vertices[2][2])
            };
        }

        function voxelIsOccupied(triangles, center, halfSize) {
            var cellBounds = {
                xmin: center[0] - halfSize,
                xmax: center[0] + halfSize,
                ymin: center[1] - halfSize,
                ymax: center[1] + halfSize,
                zmin: center[2] - halfSize,
                zmax: center[2] + halfSize
            };

            for (var i = 0; i < triangles.length; i += 1) {
                var triangle = triangles[i];
                if (boundsOverlap(triangle.bounds, cellBounds) &&
                    triangleIntersectsBox(triangle.vertices, center, halfSize)) {
                    return true;
                }
            }

            return pointInsideMesh(center, triangles);
        }

        function boundsOverlap(a, b) {
            return a.xmax >= b.xmin && a.xmin <= b.xmax &&
                a.ymax >= b.ymin && a.ymin <= b.ymax &&
                a.zmax >= b.zmin && a.zmin <= b.zmax;
        }

        function triangleIntersectsBox(vertices, center, halfSize) {
            var translated = vertices.map(function (vertex) {
                return subtractVector(vertex, center);
            });
            var edges = [
                subtractVector(translated[1], translated[0]),
                subtractVector(translated[2], translated[1]),
                subtractVector(translated[0], translated[2])
            ];
            var axes = [
                [1, 0, 0],
                [0, 1, 0],
                [0, 0, 1],
                cross(edges[0], edges[1])
            ];
            var boxAxes = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];

            edges.forEach(function (edge) {
                boxAxes.forEach(function (axis) {
                    axes.push(cross(edge, axis));
                });
            });

            return axes.every(function (axis) {
                if (dot(axis, axis) < 1e-18) return true;
                var projections = translated.map(function (vertex) { return dot(vertex, axis); });
                var radius = halfSize * (Math.abs(axis[0]) + Math.abs(axis[1]) + Math.abs(axis[2]));
                return Math.max.apply(Math, projections) >= -radius &&
                    Math.min.apply(Math, projections) <= radius;
            });
        }

        function pointInsideMesh(point, triangles) {
            var direction = [0.912870929, 0.365148372, 0.182574186];
            var hits = {};

            triangles.forEach(function (triangle) {
                var distance = rayTriangleDistance(point, direction, triangle.vertices);
                if (distance !== null && distance > 1e-8) hits[distance.toFixed(8)] = true;
            });

            return Object.keys(hits).length % 2 === 1;
        }

        function rayTriangleDistance(origin, direction, vertices) {
            var edge1 = subtractVector(vertices[1], vertices[0]);
            var edge2 = subtractVector(vertices[2], vertices[0]);
            var p = cross(direction, edge2);
            var determinant = dot(edge1, p);
            if (Math.abs(determinant) < 1e-12) return null;

            var inverse = 1 / determinant;
            var t = subtractVector(origin, vertices[0]);
            var u = dot(t, p) * inverse;
            if (u < -1e-10 || u > 1 + 1e-10) return null;

            var q = cross(t, edge1);
            var v = dot(direction, q) * inverse;
            if (v < -1e-10 || u + v > 1 + 1e-10) return null;

            var distance = dot(edge2, q) * inverse;
            return distance >= 0 ? distance : null;
        }

        function mergeOccupiedVoxels(occupied, size) {
            var visited = {};
            var boxes = [];
            var cells = Object.keys(occupied).map(function (key) {
                return key.split(',').map(Number);
            });

            cells.sort(function (a, b) {
                return a[2] - b[2] || a[1] - b[1] || a[0] - b[0];
            });

            cells.forEach(function (cell) {
                var ix = cell[0];
                var iy = cell[1];
                var iz = cell[2];
                if (!voxelAvailable(occupied, visited, ix, iy, iz)) return;

                var xmax = ix + 1;
                while (voxelAvailable(occupied, visited, xmax, iy, iz)) xmax += 1;

                var ymax = iy + 1;
                while (voxelRectangleAvailable(occupied, visited, ix, xmax, ymax, ymax + 1, iz, iz + 1)) ymax += 1;

                var zmax = iz + 1;
                while (voxelRectangleAvailable(occupied, visited, ix, xmax, iy, ymax, zmax, zmax + 1)) zmax += 1;

                markVoxelRectangle(visited, ix, xmax, iy, ymax, iz, zmax);
                boxes.push({
                    xmin: ix * size,
                    xmax: xmax * size,
                    ymin: iy * size,
                    ymax: ymax * size,
                    zmin: iz * size,
                    zmax: zmax * size
                });
            });

            return boxes;
        }

        function voxelAvailable(occupied, visited, ix, iy, iz) {
            var key = voxelKey(ix, iy, iz);
            return !!occupied[key] && !visited[key];
        }

        function voxelRectangleAvailable(occupied, visited, xmin, xmax, ymin, ymax, zmin, zmax) {
            for (var iz = zmin; iz < zmax; iz += 1) {
                for (var iy = ymin; iy < ymax; iy += 1) {
                    for (var ix = xmin; ix < xmax; ix += 1) {
                        if (!voxelAvailable(occupied, visited, ix, iy, iz)) return false;
                    }
                }
            }
            return true;
        }

        function markVoxelRectangle(visited, xmin, xmax, ymin, ymax, zmin, zmax) {
            for (var iz = zmin; iz < zmax; iz += 1) {
                for (var iy = ymin; iy < ymax; iy += 1) {
                    for (var ix = xmin; ix < xmax; ix += 1) {
                        visited[voxelKey(ix, iy, iz)] = true;
                    }
                }
            }
        }

        function voxelKey(ix, iy, iz) {
            return ix + ',' + iy + ',' + iz;
        }

        function subtractVector(a, b) {
            return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
        }

        function cross(a, b) {
            return [
                a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0]
            ];
        }

        function dot(a, b) {
            return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
        }

        function pointKey(point) {
            return point.map(function (value) { return Number(value).toFixed(4); }).join(',');
        }


        kernel.boundsOverlap = boundsOverlap;
        kernel.cross = cross;
        kernel.dot = dot;
        kernel.inflatedOpeningBbox = inflatedOpeningBbox;
        kernel.markVoxelRectangle = markVoxelRectangle;
        kernel.mergeOccupiedVoxels = mergeOccupiedVoxels;
        kernel.openingCarvesVoxel = openingCarvesVoxel;
        kernel.pointInsideMesh = pointInsideMesh;
        kernel.pointKey = pointKey;
        kernel.prepareOpeningTriangleSets = prepareOpeningTriangleSets;
        kernel.prepareTriangles = prepareTriangles;
        kernel.rayTriangleDistance = rayTriangleDistance;
        kernel.splitTrianglesByConnectedFaces = splitTrianglesByConnectedFaces;
        kernel.subtractVector = subtractVector;
        kernel.triangleBounds = triangleBounds;
        kernel.triangleIntersectsBox = triangleIntersectsBox;
        kernel.voxelAvailable = voxelAvailable;
        kernel.voxelIsOccupied = voxelIsOccupied;
        kernel.voxelKey = voxelKey;
        kernel.voxelRectangleAvailable = voxelRectangleAvailable;
        kernel.voxelizeElement = voxelizeElement;
        return function bindDependencies() {
            boundsForVertices = kernel.boundsForVertices;
            defaultSlabThickness = kernel.defaultSlabThickness;
            flatAxisFromBounds = kernel.flatAxisFromBounds;
            inflateFlatMesh = kernel.inflateFlatMesh;
            isAxisAlignedDominant = kernel.isAxisAlignedDominant;
            normalizeOpeningVoxelPolicy = kernel.normalizeOpeningVoxelPolicy;
            thinPrismAxis = kernel.thinPrismAxis;
            thinnestAxis = kernel.thinnestAxis;
        };
    };
})(window.IfcFds);
