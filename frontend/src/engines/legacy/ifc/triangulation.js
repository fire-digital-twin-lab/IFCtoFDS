(function (ns) {
    ns.ifc.legacyFactories = ns.ifc.legacyFactories || {};
    ns.ifc.legacyFactories.createTriangulation = function (kernel, constants) {
        var addVector;
        var cross;
        var earcutFunction;
        var emptyMesh;
        var identityTransform;
        var normalize;
        var numberOr;
        var projectToBasis2d;
        var scaleVector;
        var subtractVector;
        var transformPoint;
        var vectorLength;


        function profilePoints2d(step, profile, diagnostics) {
            if (!profile) return [];
            var transform = step.transformForAxisPlacement(profile.args[2]);

            if (profile.type === 'IFCRECTANGLEPROFILEDEF') {
                var xDim = numberOr(profile.args[3], 0);
                var yDim = numberOr(profile.args[4], 0);
                var points = [
                    [-xDim / 2, -yDim / 2, 0],
                    [xDim / 2, -yDim / 2, 0],
                    [xDim / 2, yDim / 2, 0],
                    [-xDim / 2, yDim / 2, 0]
                ];
                return points.map(function (point) { return transformPoint(transform, point); });
            }

            if (profile.type === 'IFCARBITRARYCLOSEDPROFILEDEF') {
                var curve = step.ref(profile.args[2]);
                var curvePoints = pointsForCurve(step, curve);
                return curvePoints.map(function (point) { return transformPoint(transform, point); });
            }

            ns.core.addDiagnostic(
                diagnostics,
                'info',
                'Unsupported IFC profile: ' + profile.type,
                'Only rectangle and arbitrary closed polyline profiles are converted in this milestone.'
            );
            return [];
        }

        function pointsForCurve(step, curve) {
            if (!curve || curve.type !== 'IFCPOLYLINE') return [];
            var refs = Array.isArray(curve.args[0]) ? curve.args[0] : [];
            return refs.map(function (ref) { return step.point(ref); });
        }

        function extrudeProfile(profilePoints, direction, depth) {
            var mesh = emptyMesh();
            var n = profilePoints.length;
            if (n < 3) return mesh;

            var offset = scaleVector(normalize(direction, [0, 0, 1]), depth);
            for (var i = 0; i < n; i += 1) {
                mesh.vertices.push(profilePoints[i].slice());
            }
            for (var j = 0; j < n; j += 1) {
                mesh.vertices.push(addVector(profilePoints[j], offset));
            }

            for (var b = 1; b < n - 1; b += 1) {
                mesh.faces.push([0, b + 1, b]);
                mesh.faces.push([n, n + b, n + b + 1]);
            }
            for (var s = 0; s < n; s += 1) {
                var next = (s + 1) % n;
                mesh.faces.push([s, next, n + next]);
                mesh.faces.push([s, n + next, n + s]);
            }

            return mesh;
        }

        function meshForFacetedBrep(step, brep, productTransform, diagnostics) {
            var mesh = emptyMesh();
            var shell = step.ref(brep.args[0]);
            if (!shell || shell.type !== 'IFCCLOSEDSHELL') return mesh;

            var faceRefs = Array.isArray(shell.args[0]) ? shell.args[0] : [];
            appendFaceRefsToMesh(step, faceRefs, productTransform, mesh);

            if (!mesh.faces.length) {
                ns.core.addDiagnostic(diagnostics, 'warning', 'Faceted BREP skipped', 'A BREP was found but no triangulated outer faces could be read.');
            }
            return mesh;
        }

        function meshForFaceBasedSurfaceModel(step, surfaceModel, productTransform, diagnostics) {
            var mesh = emptyMesh();
            var vertexMap = {};
            var connectedFaceSetRefs = Array.isArray(surfaceModel.args[0]) ? surfaceModel.args[0] : [];

            connectedFaceSetRefs.forEach(function (connectedFaceSetRef) {
                var connectedFaceSet = step.ref(connectedFaceSetRef);
                if (!connectedFaceSet || connectedFaceSet.type !== 'IFCCONNECTEDFACESET') return;
                var faceRefs = Array.isArray(connectedFaceSet.args[0]) ? connectedFaceSet.args[0] : [];
                appendFaceRefsToMesh(step, faceRefs, productTransform, mesh, vertexMap);
            });

            if (!mesh.faces.length) {
                ns.core.addDiagnostic(
                    diagnostics,
                    'warning',
                    'Face-based surface model skipped',
                    'An IfcFaceBasedSurfaceModel was found but no triangulated outer faces could be read.'
                );
            }
            return mesh;
        }

        function appendFaceRefsToMesh(step, faceRefs, productTransform, mesh, vertexMap) {
            vertexMap = vertexMap || {};

            faceRefs.forEach(function (faceRef) {
                var face = step.ref(faceRef);
                if (!face || face.type !== 'IFCFACE') return;
                var bounds = Array.isArray(face.args[0]) ? face.args[0] : [];
                var outer = null;
                bounds.forEach(function (boundRef) {
                    var bound = step.ref(boundRef);
                    if (bound && bound.type === 'IFCFACEOUTERBOUND') outer = bound;
                });
                if (!outer) return;

                var loop = step.ref(outer.args[0]);
                if (!loop || loop.type !== 'IFCPOLYLOOP') return;
                var pointRefs = Array.isArray(loop.args[0]) ? loop.args[0] : [];
                var indices = [];

                pointRefs.forEach(function (pointRef) {
                    var point = transformPoint(productTransform, step.point(pointRef));
                    var key = point.map(function (value) { return value.toFixed(8); }).join(',');
                    if (vertexMap[key] === undefined) {
                        vertexMap[key] = mesh.vertices.length;
                        mesh.vertices.push(point);
                    }
                    indices.push(vertexMap[key]);
                });

                if (indices.length < 3) return;
                triangulatePlanarPolygon(mesh, indices);
            });
            return mesh;
        }

    // Fan-triangulate from the first vertex works only for CONVEX polygons. Real BREP
    // outlines from BIM models are routinely L / U / T shaped — a fan turns those into
    // triangles that lie outside the polygon, and downstream voxelization treats the
    // mesh as if it covered the whole bounding rectangle (which is what we saw on the
    // school slab). Earcut handles non-convex shapes correctly; falls back to the fan
    // only when earcut is unavailable or the polygon is degenerate.
        function triangulatePlanarPolygon(mesh, indices) {
            if (indices.length === 3) {
                mesh.faces.push([indices[0], indices[1], indices[2]]);
                return;
            }
            var earcut = earcutFunction();
            if (earcut) {
                var points3d = indices.map(function (idx) { return mesh.vertices[idx]; });
                var basis = basisFromPlanarPoints(points3d);
                if (basis) {
                    var flat = [];
                    points3d.forEach(function (p) {
                        var proj = projectToBasis2d(p, basis);
                        flat.push(proj[0], proj[1]);
                    });
                    var triangles = earcut(flat, null, 2);
                    if (triangles && triangles.length >= 3) {
                        for (var t = 0; t < triangles.length; t += 3) {
                            mesh.faces.push([
                                indices[triangles[t]],
                                indices[triangles[t + 1]],
                                indices[triangles[t + 2]]
                            ]);
                        }
                        return;
                    }
                }
            }
            // Last-resort fan triangulation (only correct for convex polygons).
            for (var i = 1; i < indices.length - 1; i += 1) {
                mesh.faces.push([indices[0], indices[i], indices[i + 1]]);
            }
        }

    // Builds a u/v basis for a set of co-planar 3-D points. Picks the polygon normal via
    // the first two non-degenerate edge cross product, then a perpendicular u axis on the
    // plane. Returns null if the points are colinear or degenerate.
        function basisFromPlanarPoints(points) {
            if (!points || points.length < 3) return null;
            var origin = points[0];
            var normal = null;
            for (var i = 1; i < points.length - 1; i += 1) {
                var e1 = subtractVector(points[i], origin);
                var e2 = subtractVector(points[i + 1], origin);
                var n = cross(e1, e2);
                if (vectorLength(n) > 1e-10) { normal = normalize(n, [0, 0, 1]); break; }
            }
            if (!normal) return null;
            var uAxis = null;
            for (var j = 1; j < points.length; j += 1) {
                var edge = subtractVector(points[j], origin);
                if (vectorLength(edge) > 1e-8) { uAxis = normalize(edge, [1, 0, 0]); break; }
            }
            if (!uAxis) return null;
            var vAxis = normalize(cross(normal, uAxis), [0, 1, 0]);
            uAxis = normalize(cross(vAxis, normal), [1, 0, 0]);
            return { origin: origin.slice(), normal: normal, uAxis: uAxis, vAxis: vAxis };
        }

        function meshForTriangulatedFaceSet(step, faceSet, productTransform, diagnostics) {
            var mesh = emptyMesh();
            var pointList = step.ref(faceSet.args[0]);
            var coords = pointList3d(pointList);
            var indices = Array.isArray(faceSet.args[3]) ? faceSet.args[3] : [];

            if (!coords.length || !indices.length) {
                ns.core.addDiagnostic(
                    diagnostics,
                    'warning',
                    'Triangulated face set skipped',
                    'An IfcTriangulatedFaceSet did not contain readable coordinates and triangle indices.'
                );
                return mesh;
            }

            coords.forEach(function (point) {
                mesh.vertices.push(transformPoint(productTransform, point));
            });

            indices.forEach(function (face) {
                if (!Array.isArray(face) || face.length < 3) return;
                var a = numberOr(face[0], 0) - 1;
                var b = numberOr(face[1], 0) - 1;
                var c = numberOr(face[2], 0) - 1;
                if (mesh.vertices[a] && mesh.vertices[b] && mesh.vertices[c]) {
                    mesh.faces.push([a, b, c]);
                }
            });

            return mesh;
        }

        function pointList3d(entity) {
            if (!entity || entity.type !== 'IFCCARTESIANPOINTLIST3D') return [];
            var coords = Array.isArray(entity.args[0]) ? entity.args[0] : [];
            return coords
                .filter(function (point) { return Array.isArray(point) && point.length >= 3; })
                .map(function (point) {
                    return [
                        numberOr(point[0], 0),
                        numberOr(point[1], 0),
                        numberOr(point[2], 0)
                    ];
                });
        }

        function transformForCartesianOperator(step, entity) {
            if (!entity || entity.type !== 'IFCCARTESIANTRANSFORMATIONOPERATOR3D') return identityTransform();
            var x = step.direction(entity.args[0], [1, 0, 0]);
            var y = step.direction(entity.args[1], [0, 1, 0]);
            var origin = step.point(entity.args[2]);
            var scale = numberOr(entity.args[3], 1);
            var z = step.direction(entity.args[4], [0, 0, 1]);
            return {
                origin: origin,
                xAxis: scaleVector(x, scale),
                yAxis: scaleVector(y, scale),
                zAxis: scaleVector(z, scale)
            };
        }


        kernel.appendFaceRefsToMesh = appendFaceRefsToMesh;
        kernel.basisFromPlanarPoints = basisFromPlanarPoints;
        kernel.extrudeProfile = extrudeProfile;
        kernel.meshForFaceBasedSurfaceModel = meshForFaceBasedSurfaceModel;
        kernel.meshForFacetedBrep = meshForFacetedBrep;
        kernel.meshForTriangulatedFaceSet = meshForTriangulatedFaceSet;
        kernel.pointList3d = pointList3d;
        kernel.pointsForCurve = pointsForCurve;
        kernel.profilePoints2d = profilePoints2d;
        kernel.transformForCartesianOperator = transformForCartesianOperator;
        kernel.triangulatePlanarPolygon = triangulatePlanarPolygon;
        return function bindDependencies() {
            addVector = kernel.addVector;
            cross = kernel.cross;
            earcutFunction = kernel.earcutFunction;
            emptyMesh = kernel.emptyMesh;
            identityTransform = kernel.identityTransform;
            normalize = kernel.normalize;
            numberOr = kernel.numberOr;
            projectToBasis2d = kernel.projectToBasis2d;
            scaleVector = kernel.scaleVector;
            subtractVector = kernel.subtractVector;
            transformPoint = kernel.transformPoint;
            vectorLength = kernel.vectorLength;
        };
    };
})(window.IfcFds);
