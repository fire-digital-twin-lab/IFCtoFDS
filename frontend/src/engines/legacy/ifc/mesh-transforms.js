(function (ns) {
    ns.ifc.legacyFactories = ns.ifc.legacyFactories || {};
    ns.ifc.legacyFactories.createMeshTransforms = function (kernel, constants) {

        var REVIEW_TYPES = constants.REVIEW_TYPES;

        function emptyMesh() {
            return { vertices: [], faces: [] };
        }

        function appendMesh(target, source) {
            if (!source || !source.vertices.length) return target;
            var offset = target.vertices.length;
            source.vertices.forEach(function (vertex) { target.vertices.push(vertex); });
            source.faces.forEach(function (face) {
                target.faces.push([face[0] + offset, face[1] + offset, face[2] + offset]);
            });
            return target;
        }

        function transformMesh(mesh, transform) {
            mesh.vertices = mesh.vertices.map(function (vertex) { return transformPoint(transform, vertex); });
            return mesh;
        }

        function scaleMesh(mesh, scale) {
            if (scale === 1) return mesh;
            mesh.vertices = mesh.vertices.map(function (vertex) {
                return [vertex[0] * scale, vertex[1] * scale, vertex[2] * scale];
            });
            return mesh;
        }

        function boundsForVertices(vertices) {
            var bounds = null;
            vertices.forEach(function (v) {
                if (!bounds) {
                    bounds = { xmin: v[0], xmax: v[0], ymin: v[1], ymax: v[1], zmin: v[2], zmax: v[2] };
                } else {
                    bounds.xmin = Math.min(bounds.xmin, v[0]);
                    bounds.xmax = Math.max(bounds.xmax, v[0]);
                    bounds.ymin = Math.min(bounds.ymin, v[1]);
                    bounds.ymax = Math.max(bounds.ymax, v[1]);
                    bounds.zmin = Math.min(bounds.zmin, v[2]);
                    bounds.zmax = Math.max(bounds.zmax, v[2]);
                }
            });
            return bounds;
        }

        function boundsForElements(elements) {
            var bounds = null;
            elements.forEach(function (element) {
                var b = element.bounds;
                if (!b) return;
                if (!bounds) {
                    bounds = { xmin: b.xmin, xmax: b.xmax, ymin: b.ymin, ymax: b.ymax, zmin: b.zmin, zmax: b.zmax };
                } else {
                    bounds.xmin = Math.min(bounds.xmin, b.xmin);
                    bounds.xmax = Math.max(bounds.xmax, b.xmax);
                    bounds.ymin = Math.min(bounds.ymin, b.ymin);
                    bounds.ymax = Math.max(bounds.ymax, b.ymax);
                    bounds.zmin = Math.min(bounds.zmin, b.zmin);
                    bounds.zmax = Math.max(bounds.zmax, b.zmax);
                }
            });
            return bounds;
        }

        function classifyElement(entity) {
            var type = entity.type;

            if (type === 'IFCSPACE') {
                return {
                    convertible: false,
                    reference: true,
                    exportAsSolid: false,
                    canExportAsSolid: false,
                    fdsRole: 'ignore',
                    note: 'IfcSpace is a room volume. It is useful for checking layout, but should not become an FDS obstruction.'
                };
            }

            if (type === 'IFCRAILING') {
                return {
                    convertible: false,
                    reference: false,
                    exportAsSolid: false,
                    canExportAsSolid: true,
                    fdsRole: 'review',
                    note: 'Railing is visible in the IFC building preview and excluded from FDS by default. Enable review objects only when it should block the flow.'
                };
            }

            if (REVIEW_TYPES[type]) {
                return {
                    convertible: false,
                    reference: false,
                    exportAsSolid: false,
                    canExportAsSolid: true,
                    fdsRole: 'review',
                    note: REVIEW_TYPES[type] + ' is shown in the IFC preview and excluded from FDS by default. Enable review objects only when it should block the flow.'
                };
            }

            if (type === 'IFCWINDOW' || type === 'IFCDOOR') {
                return {
                    convertible: true,
                    reference: false,
                    exportAsSolid: false,
                    canExportAsSolid: true,
                    fdsRole: 'opening',
                    note: 'Window and door fills remain visible for IFC review but are excluded from FDS obstructions; their host openings are carved during voxel export.'
                };
            }

            return {
                convertible: true,
                reference: false,
                exportAsSolid: true,
                canExportAsSolid: true,
                fdsRole: 'solid',
                note: 'Converted by default.'
            };
        }

        function identityTransform() {
            return {
                origin: [0, 0, 0],
                xAxis: [1, 0, 0],
                yAxis: [0, 1, 0],
                zAxis: [0, 0, 1]
            };
        }

        function axesTransform(origin, xAxis, zAxis) {
            var z = normalize(zAxis, [0, 0, 1]);
            var x = normalize(xAxis, [1, 0, 0]);
            var y = normalize(cross(z, x), [0, 1, 0]);
            x = normalize(cross(y, z), [1, 0, 0]);
            return { origin: origin.slice(), xAxis: x, yAxis: y, zAxis: z };
        }

        function composeTransform(a, b) {
            return {
                origin: transformPoint(a, b.origin),
                xAxis: transformVector(a, b.xAxis),
                yAxis: transformVector(a, b.yAxis),
                zAxis: transformVector(a, b.zAxis)
            };
        }

        function invertTransform(t) {
            var invX = [t.xAxis[0], t.yAxis[0], t.zAxis[0]];
            var invY = [t.xAxis[1], t.yAxis[1], t.zAxis[1]];
            var invZ = [t.xAxis[2], t.yAxis[2], t.zAxis[2]];
            var invOrigin = [
                -(invX[0] * t.origin[0] + invX[1] * t.origin[1] + invX[2] * t.origin[2]),
                -(invY[0] * t.origin[0] + invY[1] * t.origin[1] + invY[2] * t.origin[2]),
                -(invZ[0] * t.origin[0] + invZ[1] * t.origin[1] + invZ[2] * t.origin[2])
            ];
            return {
                origin: invOrigin,
                xAxis: invX,
                yAxis: invY,
                zAxis: invZ
            };
        }

        function transformPoint(transform, point) {
            return addVector(transform.origin, transformVector(transform, point));
        }

        function transformVector(transform, vector) {
            return [
                transform.xAxis[0] * vector[0] + transform.yAxis[0] * vector[1] + transform.zAxis[0] * vector[2],
                transform.xAxis[1] * vector[0] + transform.yAxis[1] * vector[1] + transform.zAxis[1] * vector[2],
                transform.xAxis[2] * vector[0] + transform.yAxis[2] * vector[1] + transform.zAxis[2] * vector[2]
            ];
        }

        function cross(a, b) {
            return [
                a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0]
            ];
        }

        function normalize(vector, fallback) {
            var len = Math.sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2]);
            if (len < 1e-12) return fallback.slice();
            return [vector[0] / len, vector[1] / len, vector[2] / len];
        }

        function addVector(a, b) {
            return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
        }

        function subtractVector(a, b) {
            return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
        }

        function scaleVector(vector, scale) {
            return [vector[0] * scale, vector[1] * scale, vector[2] * scale];
        }

        function vectorLength(vector) {
            return Math.sqrt(dot(vector, vector));
        }

        function dot(a, b) {
            return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
        }

        function numberOr(value, fallback) {
            return Number.isFinite(value) ? value : fallback;
        }

        function refId(value) {
            if (typeof value === 'string') {
                var match = value.match(/^#(\d+)$/);
                return match ? parseInt(match[1], 10) : null;
            }
            return null;
        }

        function asText(value) {
            return typeof value === 'string' && value.charAt(0) !== '#' ? value : '';
        }

        function labelForEntity(entity) {
            return entity.type + ' #' + entity.id + (asText(entity.args[2]) ? ' (' + asText(entity.args[2]) + ')' : '');
        }

        function isIdentityish(transform) {
            var id = identityTransform();
            return vectorClose(transform.origin, id.origin) &&
                vectorClose(transform.xAxis, id.xAxis) &&
                vectorClose(transform.yAxis, id.yAxis) &&
                vectorClose(transform.zAxis, id.zAxis);
        }

        function vectorClose(a, b) {
            return Math.abs(a[0] - b[0]) < 1e-8 &&
                Math.abs(a[1] - b[1]) < 1e-8 &&
                Math.abs(a[2] - b[2]) < 1e-8;
        }

        function addDiagnosticOnce(diagnostics, level, title, detail) {
            var exists = diagnostics.some(function (diagnostic) {
                return diagnostic.title === title;
            });
            if (!exists) ns.core.addDiagnostic(diagnostics, level, title, detail);
        }


        kernel.addDiagnosticOnce = addDiagnosticOnce;
        kernel.addVector = addVector;
        kernel.appendMesh = appendMesh;
        kernel.asText = asText;
        kernel.axesTransform = axesTransform;
        kernel.boundsForElements = boundsForElements;
        kernel.boundsForVertices = boundsForVertices;
        kernel.classifyElement = classifyElement;
        kernel.composeTransform = composeTransform;
        kernel.cross = cross;
        kernel.dot = dot;
        kernel.emptyMesh = emptyMesh;
        kernel.identityTransform = identityTransform;
        kernel.invertTransform = invertTransform;
        kernel.isIdentityish = isIdentityish;
        kernel.labelForEntity = labelForEntity;
        kernel.normalize = normalize;
        kernel.numberOr = numberOr;
        kernel.refId = refId;
        kernel.scaleMesh = scaleMesh;
        kernel.scaleVector = scaleVector;
        kernel.subtractVector = subtractVector;
        kernel.transformMesh = transformMesh;
        kernel.transformPoint = transformPoint;
        kernel.transformVector = transformVector;
        kernel.vectorClose = vectorClose;
        kernel.vectorLength = vectorLength;
        return function bindDependencies() {

        };
    };
})(window.IfcFds);
