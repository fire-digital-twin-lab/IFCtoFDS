(function (ns) {
    ns.ifc.legacyFactories = ns.ifc.legacyFactories || {};
    ns.ifc.legacyFactories.createClipping = function (kernel, constants) {
        var addVector;
        var cross;
        var dot;
        var emptyMesh;
        var normalize;
        var scaleVector;
        var subtractVector;
        var vectorLength;


        function clipMeshByPlane(source, plane) {
            var mesh = emptyMesh();
            var vertexMap = {};
            var cutSegments = [];

            source.faces.forEach(function (face) {
                var triangle = face.map(function (index) { return source.vertices[index]; });
                var clipped = clipPolygonByPlane(triangle, plane);
                var cutPoints = intersectionPointsForTriangle(triangle, plane);

                if (cutPoints.length === 2) cutSegments.push(cutPoints);
                if (clipped.length < 3) return;

                var indices = clipped.map(function (point) {
                    return addUniqueVertex(mesh, vertexMap, point);
                });
                for (var i = 1; i < indices.length - 1; i += 1) {
                    mesh.faces.push([indices[0], indices[i], indices[i + 1]]);
                }
            });

            addClipCaps(mesh, vertexMap, cutSegments, plane);
            return mesh;
        }

        function clipPolygonByPlane(points, plane) {
            var result = [];

            for (var i = 0; i < points.length; i += 1) {
                var current = points[i];
                var next = points[(i + 1) % points.length];
                var currentDistance = signedDistanceToPlane(current, plane);
                var nextDistance = signedDistanceToPlane(next, plane);
                var currentInside = isInsideClip(currentDistance, plane);
                var nextInside = isInsideClip(nextDistance, plane);

                if (currentInside) result.push(current.slice());
                if (currentInside !== nextInside) {
                    result.push(intersectionPoint(current, next, currentDistance, nextDistance));
                }
            }

            return removeDuplicateLoopPoints(result);
        }

        function intersectionPointsForTriangle(points, plane) {
            var intersections = [];

            for (var i = 0; i < points.length; i += 1) {
                var current = points[i];
                var next = points[(i + 1) % points.length];
                var currentDistance = signedDistanceToPlane(current, plane);
                var nextDistance = signedDistanceToPlane(next, plane);

                if (Math.abs(currentDistance) < 1e-8) intersections.push(current.slice());
                if (isInsideClip(currentDistance, plane) !== isInsideClip(nextDistance, plane)) {
                    intersections.push(intersectionPoint(current, next, currentDistance, nextDistance));
                }
            }

            return uniquePoints(intersections);
        }

        function addClipCaps(mesh, vertexMap, segments, plane) {
            var unused = {};
            var adjacency = {};
            var capLoops = [];

            segments.forEach(function (segment) {
                var a = pointKey(segment[0]);
                var b = pointKey(segment[1]);
                if (a === b) return;
                var edgeKey = a < b ? a + '|' + b : b + '|' + a;
                if (unused[edgeKey]) return;
                unused[edgeKey] = { a: a, b: b, points: {} };
                unused[edgeKey].points[a] = segment[0];
                unused[edgeKey].points[b] = segment[1];
                adjacency[a] = adjacency[a] || [];
                adjacency[b] = adjacency[b] || [];
                adjacency[a].push(edgeKey);
                adjacency[b].push(edgeKey);
            });

            Object.keys(unused).forEach(function (startEdgeKey) {
                if (!unused[startEdgeKey]) return;
                var edge = unused[startEdgeKey];
                var startKey = edge.a;
                var currentKey = edge.b;
                var loop = [edge.points[startKey], edge.points[currentKey]];
                delete unused[startEdgeKey];

                while (currentKey !== startKey) {
                    var nextEdgeKey = (adjacency[currentKey] || []).find(function (candidate) {
                        return !!unused[candidate];
                    });
                    if (!nextEdgeKey) break;

                    var nextEdge = unused[nextEdgeKey];
                    var nextKey = nextEdge.a === currentKey ? nextEdge.b : nextEdge.a;
                    loop.push(nextEdge.points[nextKey]);
                    delete unused[nextEdgeKey];
                    currentKey = nextKey;
                }

                if (currentKey !== startKey || loop.length < 4) return;
                loop.pop();
                capLoops.push(loop);
            });
            addCapLoops(mesh, vertexMap, capLoops, plane);
        }

    // Triangulate concave sections and nested holes together. A center fan fills
    // previous window voids when another opening clips the same host later.
        function addCapLoops(mesh, vertexMap, loops, plane) {
            if (!loops.length) return;
            var triangulate = earcutFunction();
            if (!triangulate) throw new Error('Earcut is required for closed export caps');
            var normal = normalize(plane.normal, [0, 0, 1]);
            var u = perpendicularVector(normal);
            var v = cross(normal, u);
            var desired = plane.keepPositive ? scaleVector(normal, -1) : normal;
            var projected = loops.map(function (loop) {
                return loop.map(function (point) { return [dot(point, u), dot(point, v)]; });
            });
            var depths = projected.map(function (loop, index) {
                return projected.reduce(function (count, other, j) {
                    return count + (j !== index && pointStrictlyInsidePolygon(loop[0], other) ? 1 : 0);
                }, 0);
            });
            loops.forEach(function (outer, index) {
                if (depths[index] % 2) return;
                var rings = [index];
                loops.forEach(function (hole, j) {
                    if (depths[j] === depths[index] + 1 && pointStrictlyInsidePolygon(projected[j][0], projected[index])) rings.push(j);
                });
                var flat = [], holes = [], points = [];
                rings.forEach(function (ring, r) {
                    if (r) holes.push(points.length);
                    loops[ring].forEach(function (point, k) {
                        flat.push(projected[ring][k][0], projected[ring][k][1]); points.push(point);
                    });
                });
                var faces = triangulate(flat, holes, 2);
                for (var k = 0; k < faces.length; k += 3) {
                    var triangle = [points[faces[k]], points[faces[k + 1]], points[faces[k + 2]]];
                    if (dot(polygonNormal(triangle), desired) < 0) triangle.reverse();
                    mesh.faces.push(triangle.map(function (point) { return addUniqueVertex(mesh, vertexMap, point); }));
                }
            });
        }

        function polygonNormal(points) {
            var normal = [0, 0, 0];
            for (var i = 0; i < points.length; i += 1) {
                var current = points[i];
                var next = points[(i + 1) % points.length];
                normal[0] += (current[1] - next[1]) * (current[2] + next[2]);
                normal[1] += (current[2] - next[2]) * (current[0] + next[0]);
                normal[2] += (current[0] - next[0]) * (current[1] + next[1]);
            }
            return normal;
        }

        function signedDistanceToPlane(point, plane) {
            return dot(subtractVector(point, plane.origin), plane.normal);
        }

        function isInsideClip(distance, plane) {
            return plane.keepPositive ? distance >= -1e-8 : distance <= 1e-8;
        }

        function intersectionPoint(a, b, aDistance, bDistance) {
            var denominator = aDistance - bDistance;
            var t = Math.abs(denominator) < 1e-12 ? 0 : aDistance / denominator;
            return [
                a[0] + (b[0] - a[0]) * t,
                a[1] + (b[1] - a[1]) * t,
                a[2] + (b[2] - a[2]) * t
            ];
        }

        function removeDuplicateLoopPoints(points) {
            var result = [];
            points.forEach(function (point) {
                if (!result.length || pointKey(result[result.length - 1]) !== pointKey(point)) result.push(point);
            });
            if (result.length > 1 && pointKey(result[0]) === pointKey(result[result.length - 1])) result.pop();
            return result;
        }

        function uniquePoints(points) {
            var seen = {};
            return points.filter(function (point) {
                var key = pointKey(point);
                if (seen[key]) return false;
                seen[key] = true;
                return true;
            });
        }

        function addUniqueVertex(mesh, vertexMap, point) {
            var key = pointKey(point);
            if (vertexMap[key] === undefined) {
                vertexMap[key] = mesh.vertices.length;
                mesh.vertices.push(point.slice());
            }
            return vertexMap[key];
        }

        function pointKey(point) {
            return point.map(function (value) { return Number(value).toFixed(8); }).join(',');
        }

        function basisForExtrusion(extrusion) {
            var origin = extrusion.base[0];
            var normal = normalize(extrusion.offset, [0, 0, 1]);
            var uAxis = null;

            for (var i = 1; i < extrusion.base.length; i += 1) {
                var edge = subtractVector(extrusion.base[i], origin);
                if (vectorLength(edge) > 1e-8) {
                    uAxis = normalize(edge, [1, 0, 0]);
                    break;
                }
            }

            uAxis = uAxis || perpendicularVector(normal);
            var vAxis = normalize(cross(normal, uAxis), [0, 1, 0]);
            uAxis = normalize(cross(vAxis, normal), [1, 0, 0]);
            return { origin: origin.slice(), normal: normal, uAxis: uAxis, vAxis: vAxis };
        }

        function perpendicularVector(normal) {
            var candidate = Math.abs(normal[0]) < 0.8 ? [1, 0, 0] : [0, 1, 0];
            return normalize(cross(candidate, normal), [0, 0, 1]);
        }

        function projectToBasis2d(point, basis) {
            var relative = subtractVector(point, basis.origin);
            return [dot(relative, basis.uAxis), dot(relative, basis.vAxis)];
        }

        function pointFromBasis2d(point, basis) {
            return addVector(
                basis.origin,
                addVector(scaleVector(basis.uAxis, point[0]), scaleVector(basis.vAxis, point[1]))
            );
        }

        function pointStrictlyInsidePolygon(point, polygon) {
            var inside = false;

            for (var i = 0, j = polygon.length - 1; i < polygon.length; j = i, i += 1) {
                if (pointOnSegment2d(point, polygon[j], polygon[i])) return false;
                if ((polygon[i][1] > point[1]) !== (polygon[j][1] > point[1]) &&
                    point[0] < (polygon[j][0] - polygon[i][0]) * (point[1] - polygon[i][1]) /
                    (polygon[j][1] - polygon[i][1]) + polygon[i][0]) {
                    inside = !inside;
                }
            }

            return inside;
        }

        function pointOnSegment2d(point, a, b) {
            var crossValue = (point[1] - a[1]) * (b[0] - a[0]) - (point[0] - a[0]) * (b[1] - a[1]);
            if (Math.abs(crossValue) > 1e-8) return false;
            return point[0] >= Math.min(a[0], b[0]) - 1e-8 &&
                point[0] <= Math.max(a[0], b[0]) + 1e-8 &&
                point[1] >= Math.min(a[1], b[1]) - 1e-8 &&
                point[1] <= Math.max(a[1], b[1]) + 1e-8;
        }

        function earcutFunction() {
            if (!window.earcut) return null;
            return window.earcut.default || window.earcut;
        }


        kernel.addCapLoops = addCapLoops;
        kernel.addClipCaps = addClipCaps;
        kernel.addUniqueVertex = addUniqueVertex;
        kernel.basisForExtrusion = basisForExtrusion;
        kernel.clipMeshByPlane = clipMeshByPlane;
        kernel.clipPolygonByPlane = clipPolygonByPlane;
        kernel.earcutFunction = earcutFunction;
        kernel.intersectionPoint = intersectionPoint;
        kernel.intersectionPointsForTriangle = intersectionPointsForTriangle;
        kernel.isInsideClip = isInsideClip;
        kernel.perpendicularVector = perpendicularVector;
        kernel.pointFromBasis2d = pointFromBasis2d;
        kernel.pointKey = pointKey;
        kernel.pointOnSegment2d = pointOnSegment2d;
        kernel.pointStrictlyInsidePolygon = pointStrictlyInsidePolygon;
        kernel.polygonNormal = polygonNormal;
        kernel.projectToBasis2d = projectToBasis2d;
        kernel.removeDuplicateLoopPoints = removeDuplicateLoopPoints;
        kernel.signedDistanceToPlane = signedDistanceToPlane;
        kernel.uniquePoints = uniquePoints;
        return function bindDependencies() {
            addVector = kernel.addVector;
            cross = kernel.cross;
            dot = kernel.dot;
            emptyMesh = kernel.emptyMesh;
            normalize = kernel.normalize;
            scaleVector = kernel.scaleVector;
            subtractVector = kernel.subtractVector;
            vectorLength = kernel.vectorLength;
        };
    };
})(window.IfcFds);
