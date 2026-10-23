(function (ns) {
    ns.ifc.legacyFactories = ns.ifc.legacyFactories || {};
    ns.ifc.legacyFactories.createRepresentations = function (kernel, constants) {
        var addDiagnosticOnce;
        var addVector;
        var appendMesh;
        var basisForExtrusion;
        var clipMeshByPlane;
        var cloneExtrusion;
        var composeTransform;
        var earcutFunction;
        var emptyMesh;
        var extrudeProfile;
        var invertTransform;
        var isIdentityish;
        var meshForFaceBasedSurfaceModel;
        var meshForFacetedBrep;
        var meshForTriangulatedFaceSet;
        var normalize;
        var numberOr;
        var profilePoints2d;
        var projectToBasis2d;
        var removeDuplicateLoopPoints;
        var scaleVector;
        var transformForCartesianOperator;
        var transformMesh;
        var transformPoint;
        var transformVector;


        function meshForRepresentationItem(step, item, productTransform, diagnostics, unsupported) {
            if (!item) return emptyMesh();
            if (item.type === 'IFCEXTRUDEDAREASOLID') {
                return meshForExtrudedAreaSolid(step, item, productTransform, diagnostics);
            }
            if (item.type === 'IFCFACETEDBREP') {
                return meshForFacetedBrep(step, item, productTransform, diagnostics);
            }
            if (item.type === 'IFCFACEBASEDSURFACEMODEL') {
                return meshForFaceBasedSurfaceModel(step, item, productTransform, diagnostics);
            }
            if (item.type === 'IFCTRIANGULATEDFACESET') {
                return meshForTriangulatedFaceSet(step, item, productTransform, diagnostics);
            }
            if (item.type === 'IFCMAPPEDITEM') {
                return meshForMappedItem(step, item, productTransform, diagnostics, unsupported);
            }
            if (item.type === 'IFCBOOLEANCLIPPINGRESULT') {
                return meshForBooleanClippingResult(step, item, productTransform, diagnostics, unsupported);
            }

            unsupported[item.type] = (unsupported[item.type] || 0) + 1;
            return emptyMesh();
        }

        function meshForMappedItem(step, item, productTransform, diagnostics, unsupported) {
            var source = step.ref(item.args[0]);
            var target = transformForCartesianOperator(step, step.ref(item.args[1]));
            var mesh = emptyMesh();

            if (!source || source.type !== 'IFCREPRESENTATIONMAP') {
                unsupported.IFCMAPPEDITEM = (unsupported.IFCMAPPEDITEM || 0) + 1;
                return mesh;
            }

            var origin = step.transformForAxisPlacement(source.args[0]);
            if (!isIdentityish(origin)) {
                ns.core.addDiagnostic(
                    diagnostics,
                    'info',
                    'IFC mapped origin approximated',
                    'A non-identity IfcRepresentationMap origin was detected. Geometry may need a later precision pass.'
                );
            }

            var mappedRepresentation = step.ref(source.args[1]);
            var items = [];
            if (mappedRepresentation && mappedRepresentation.type === 'IFCSHAPEREPRESENTATION') {
                var refs = Array.isArray(mappedRepresentation.args[3]) ? mappedRepresentation.args[3] : [];
                refs.forEach(function (ref) {
                    var mapped = step.ref(ref);
                    if (mapped) items.push(mapped);
                });
            }

            var mappedTransform = composeTransform(productTransform, target);
            if (!isIdentityish(origin)) {
                var invOrigin = invertTransform(origin);
                mappedTransform = composeTransform(mappedTransform, invOrigin);
            }
            items.forEach(function (mappedItem) {
                appendMesh(mesh, meshForRepresentationItem(step, mappedItem, mappedTransform, diagnostics, unsupported));
            });
            return mesh;
        }

        function meshForBooleanClippingResult(step, item, productTransform, diagnostics, unsupported) {
            if (String(item.args[0] || '').toUpperCase() !== '.DIFFERENCE.') {
                unsupported.IFCBOOLEANCLIPPINGRESULT = (unsupported.IFCBOOLEANCLIPPINGRESULT || 0) + 1;
                return emptyMesh();
            }

            var source = step.ref(item.args[1]);
            var halfSpace = step.ref(item.args[2]);
            var mesh = meshForRepresentationItem(step, source, productTransform, diagnostics, unsupported);
            var plane = clippingPlaneForHalfSpace(step, halfSpace, productTransform);

            if (!mesh.faces.length || !plane) {
                unsupported.IFCBOOLEANCLIPPINGRESULT = (unsupported.IFCBOOLEANCLIPPINGRESULT || 0) + 1;
                return emptyMesh();
            }

            if (halfSpace.type === 'IFCPOLYGONALBOUNDEDHALFSPACE') {
                addDiagnosticOnce(
                    diagnostics,
                    'info',
                    'Polygonal clipping boundary approximated',
                    'IfcPolygonalBoundedHalfSpace roof cuts are currently applied as planar cuts. This preserves the supported building walls, but a later precision pass should also limit the cut to the polygon boundary.'
                );
            }

            return clipMeshByPlane(mesh, plane);
        }

        function clippingPlaneForHalfSpace(step, halfSpace, productTransform) {
            if (!halfSpace ||
                (halfSpace.type !== 'IFCHALFSPACESOLID' && halfSpace.type !== 'IFCPOLYGONALBOUNDEDHALFSPACE')) {
                return null;
            }

            var surface = step.ref(halfSpace.args[0]);
            if (!surface || surface.type !== 'IFCPLANE') return null;

            var surfaceTransform = step.transformForAxisPlacement(surface.args[0]);
            var worldTransform = composeTransform(productTransform, surfaceTransform);
            return {
                origin: worldTransform.origin,
                normal: normalize(worldTransform.zAxis, [0, 0, 1]),
                keepPositive: String(halfSpace.args[1] || '').toUpperCase() === '.T.'
            };
        }

        function meshForExtrudedAreaSolid(step, solid, productTransform, diagnostics) {
            var profile = step.ref(solid.args[0]);
            var solidPosition = step.transformForAxisPlacement(solid.args[1]);
            var direction = step.direction(solid.args[2], [0, 0, 1]);
            var depth = numberOr(solid.args[3], 0);
            var profilePoints = profilePoints2d(step, profile, diagnostics);

            if (!profilePoints.length || depth <= 0) return emptyMesh();

            profilePoints = removeDuplicateLoopPoints(profilePoints);
            var localMesh = extrudeProfile(profilePoints, direction, depth);
            var transform = composeTransform(productTransform, solidPosition);
            transformMesh(localMesh, transform);
            localMesh.extrusion = {
                base: profilePoints.map(function (point) { return transformPoint(transform, point); }),
                offset: transformVector(transform, scaleVector(normalize(direction, [0, 0, 1]), depth)),
                holes: []
            };
            return localMesh;
        }

        function meshForExtrusionWithHoles(extrusion) {
            var mesh = emptyMesh();
            var rings = [removeDuplicateLoopPoints(extrusion.base)].concat(
                extrusion.holes.map(removeDuplicateLoopPoints)
            );
            var basis = basisForExtrusion(extrusion);
            var flat = [];
            var holeIndices = [];
            var ringStarts = [];
            var vertexCount = 0;

            rings.forEach(function (ring, index) {
                ringStarts.push(vertexCount);
                if (index > 0) holeIndices.push(vertexCount);
                ring.forEach(function (point) {
                    var projected = projectToBasis2d(point, basis);
                    flat.push(projected[0], projected[1]);
                    mesh.vertices.push(point.slice());
                    vertexCount += 1;
                });
            });

            var triangles = earcutFunction()(flat, holeIndices, 2);
            var baseCount = mesh.vertices.length;
            mesh.vertices.slice().forEach(function (point) {
                mesh.vertices.push(addVector(point, extrusion.offset));
            });

            for (var i = 0; i < triangles.length; i += 3) {
                mesh.faces.push([triangles[i], triangles[i + 2], triangles[i + 1]]);
                mesh.faces.push([
                    baseCount + triangles[i],
                    baseCount + triangles[i + 1],
                    baseCount + triangles[i + 2]
                ]);
            }

            rings.forEach(function (ring, ringIndex) {
                var start = ringStarts[ringIndex];
                for (var j = 0; j < ring.length; j += 1) {
                    var current = start + j;
                    var next = start + (j + 1) % ring.length;
                    if (ringIndex === 0) {
                        mesh.faces.push([current, next, baseCount + next]);
                        mesh.faces.push([current, baseCount + next, baseCount + current]);
                    } else {
                        mesh.faces.push([current, baseCount + next, next]);
                        mesh.faces.push([current, baseCount + current, baseCount + next]);
                    }
                }
            });

            mesh.extrusion = cloneExtrusion(extrusion);
            return mesh;
        }


        kernel.clippingPlaneForHalfSpace = clippingPlaneForHalfSpace;
        kernel.meshForBooleanClippingResult = meshForBooleanClippingResult;
        kernel.meshForExtrudedAreaSolid = meshForExtrudedAreaSolid;
        kernel.meshForExtrusionWithHoles = meshForExtrusionWithHoles;
        kernel.meshForMappedItem = meshForMappedItem;
        kernel.meshForRepresentationItem = meshForRepresentationItem;
        return function bindDependencies() {
            addDiagnosticOnce = kernel.addDiagnosticOnce;
            addVector = kernel.addVector;
            appendMesh = kernel.appendMesh;
            basisForExtrusion = kernel.basisForExtrusion;
            clipMeshByPlane = kernel.clipMeshByPlane;
            cloneExtrusion = kernel.cloneExtrusion;
            composeTransform = kernel.composeTransform;
            earcutFunction = kernel.earcutFunction;
            emptyMesh = kernel.emptyMesh;
            extrudeProfile = kernel.extrudeProfile;
            invertTransform = kernel.invertTransform;
            isIdentityish = kernel.isIdentityish;
            meshForFaceBasedSurfaceModel = kernel.meshForFaceBasedSurfaceModel;
            meshForFacetedBrep = kernel.meshForFacetedBrep;
            meshForTriangulatedFaceSet = kernel.meshForTriangulatedFaceSet;
            normalize = kernel.normalize;
            numberOr = kernel.numberOr;
            profilePoints2d = kernel.profilePoints2d;
            projectToBasis2d = kernel.projectToBasis2d;
            removeDuplicateLoopPoints = kernel.removeDuplicateLoopPoints;
            scaleVector = kernel.scaleVector;
            transformForCartesianOperator = kernel.transformForCartesianOperator;
            transformMesh = kernel.transformMesh;
            transformPoint = kernel.transformPoint;
            transformVector = kernel.transformVector;
        };
    };
})(window.IfcFds);
