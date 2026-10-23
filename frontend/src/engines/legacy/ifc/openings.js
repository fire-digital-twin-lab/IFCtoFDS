(function (ns) {
    ns.ifc.legacyFactories = ns.ifc.legacyFactories || {};
    ns.ifc.legacyFactories.createOpenings = function (kernel, constants) {
        var addDiagnosticOnce;
        var addUniqueVertex;
        var addVector;
        var appendMesh;
        var asText;
        var basisForExtrusion;
        var boundsForElements;
        var boundsForVertices;
        var cross;
        var dot;
        var earcutFunction;
        var emptyMesh;
        var meshForExtrusionWithHoles;
        var meshForRepresentationItem;
        var normalize;
        var pointFromBasis2d;
        var pointStrictlyInsidePolygon;
        var projectToBasis2d;
        var refId;
        var removeDuplicateLoopPoints;
        var representationItems;
        var scaleVector;
        var subtractVector;
        var vectorLength;


        function indexVoidsByHost(step) {
            var byHost = {};

            step.each(function (entity) {
                if (entity.type !== 'IFCRELVOIDSELEMENT') return;
                var hostId = refId(entity.args[4]);
                var opening = step.ref(entity.args[5]);
                if (!hostId || !opening || opening.type !== 'IFCOPENINGELEMENT') return;
                byHost[hostId] = byHost[hostId] || [];
                byHost[hostId].push(opening);
            });

            return byHost;
        }

        function indexOpeningsByFill(step) {
            var byFill = {};

            step.each(function (entity) {
                if (entity.type !== 'IFCRELFILLSELEMENT') return;
                var opening = step.ref(entity.args[4]);
                var fillId = refId(entity.args[5]);
                if (!fillId || !opening || opening.type !== 'IFCOPENINGELEMENT') return;
                byFill[fillId] = byFill[fillId] || [];
                byFill[fillId].push(opening);
            });

            return byFill;
        }

        function indexHostIdsByOpening(voidsByHost) {
            var byOpening = {};
            Object.keys(voidsByHost).forEach(function (hostId) {
                voidsByHost[hostId].forEach(function (opening) {
                    byOpening[opening.id] = Number(hostId);
                });
            });
            return byOpening;
        }

        function countIndexedVoids(voidsByHost) {
            return Object.keys(voidsByHost).reduce(function (count, hostId) {
                return count + voidsByHost[hostId].length;
            }, 0);
        }

        function extrusionsForOpenings(step, openings, diagnostics, unsupported) {
            var extrusions = [];

            openings.forEach(function (opening) {
                var placement = step.transformForLocalPlacement(opening.args[5]);
                var representation = step.ref(opening.args[6]);
                representationItems(step, representation).forEach(function (item) {
                    var mesh = meshForRepresentationItem(step, item, placement, diagnostics, unsupported);
                    if (mesh.extrusion) {
                        extrusions.push({
                            openingId: opening.id,
                            openingName: asText(opening.args[2]) || 'Opening #' + opening.id,
                            extrusion: mesh.extrusion
                        });
                    }
                });
            });

            return extrusions;
        }

        function meshesForOpenings(step, openings, diagnostics, unsupported) {
            return openings.map(function (opening) {
                var placement = step.transformForLocalPlacement(opening.args[5]);
                var representation = step.ref(opening.args[6]);
                var mesh = emptyMesh();

                representationItems(step, representation).forEach(function (item) {
                    appendMesh(mesh, meshForRepresentationItem(step, item, placement, diagnostics, unsupported));
                });

                if (!mesh.faces.length) return null;
                return {
                    stepId: opening.id,
                    name: asText(opening.args[2]) || 'Opening #' + opening.id,
                    mesh: mesh
                };
            }).filter(Boolean);
        }

        function boundsForOpeningMeshes(openings) {
            var vertices = [];
            openings.forEach(function (opening) {
                vertices = vertices.concat(opening.mesh.vertices);
            });
            return vertices.length ? boundsForVertices(vertices) : null;
        }

        function attachFillHostBounds(elements) {
            var byStepId = {};
            elements.forEach(function (element) {
                byStepId[element.stepId] = element;
            });

            elements.forEach(function (element) {
                var hosts = (element.fillHostStepIds || []).map(function (stepId) {
                    return byStepId[stepId];
                }).filter(Boolean);
                if (hosts.length) element.fillHostBounds = boundsForElements(hosts);
            });
        }

    // Carve an item's openings, returning separate export and display meshes.
    // Profile holes that run parallel to and span the host extrusion (e.g. a shaft through a
    // slab) are subtracted from both meshes, exactly as before. Openings that cut across the
    // host (windows/doors in a wall) are boolean-subtracted into the display mesh only, so the
    // preview shows the void while the FDS export keeps the watertight solid that the
    // voxel/HOLE pipeline depends on.
        function carveItemOpenings(mesh, openings, diagnostics, voidStats, options) {
            if (!openings.length || !mesh.faces.length) {
                return { exportMesh: mesh, displayMesh: mesh };
            }
            if (!earcutFunction()) {
                addDiagnosticOnce(
                    diagnostics,
                    'warning',
                    'IFC void triangulation unavailable',
                    'Earcut was not loaded, so opening voids could not be triangulated.'
                );
                return { exportMesh: mesh, displayMesh: mesh };
            }

            var profileHoles = [];
            var boxOpenings = [];
            if (mesh.extrusion) {
                openings.forEach(function (opening) {
                    var hole = holeForOpeningExtrusion(mesh.extrusion, opening.extrusion);
                    if (hole) profileHoles.push({ opening: opening, hole: hole });
                    else boxOpenings.push(opening);
                });
            } else {
                boxOpenings = openings.slice();
            }

            var exportMesh = mesh;
            if (profileHoles.length) {
                var extrusion = cloneExtrusion(mesh.extrusion);
                profileHoles.forEach(function (item) {
                    extrusion.holes.push(item.hole);
                    voidStats.applied[item.opening.openingId] = true;
                });
                exportMesh = meshForExtrusionWithHoles(extrusion);
            }

            var displayMesh = exportMesh;
            // Preview may skip this pass; the export completeness flag prevents reuse.
            if (!(options && options.skipBoxOpenings)) {
                boxOpenings.forEach(function (opening) {
                    var box = boxFromExtrusion(opening.extrusion);
                    if (!box) return;
                    try {
                        var carved = subtractBoxFromMesh(displayMesh, box);
                        if (carved && carved.faces && carved.faces.length) {
                            displayMesh = carved;
                            voidStats.applied[opening.openingId] = true;
                        }
                    } catch (err) {
                        console.warn('Carving opening #' + opening.openingId + ' failed:', err);
                    }
                });
            }

            return { exportMesh: exportMesh, displayMesh: displayMesh };
        }

    // Tight oriented box for an opening extrusion: an orthonormal frame (two base edges plus
    // the extrusion direction) with the min/max extent of the opening along each axis. A small
    // relative pad guarantees the box pokes through coincident host faces (no z-fighting caps).
        function boxFromExtrusion(extrusion) {
            var base = removeDuplicateLoopPoints(extrusion.base);
            if (base.length < 3 || vectorLength(extrusion.offset) < 1e-8) return null;

            var basis = basisForExtrusion(extrusion);
            var axes = [basis.uAxis, basis.vAxis, basis.normal];
            var corners = base.concat(base.map(function (point) {
                return addVector(point, extrusion.offset);
            }));

            var mins = [Infinity, Infinity, Infinity];
            var maxs = [-Infinity, -Infinity, -Infinity];
            corners.forEach(function (point) {
                for (var i = 0; i < 3; i += 1) {
                    var distance = dot(subtractVector(point, basis.origin), axes[i]);
                    if (distance < mins[i]) mins[i] = distance;
                    if (distance > maxs[i]) maxs[i] = distance;
                }
            });

            for (var axis = 0; axis < 3; axis += 1) {
                var pad = (maxs[axis] - mins[axis]) * 0.005;
                if (pad < 1e-9) return null;
                mins[axis] -= pad;
                maxs[axis] += pad;
            }
            return { origin: basis.origin.slice(), axes: axes, mins: mins, maxs: maxs };
        }

    // BSP solid difference. Partition pieces must be unioned as solids: simply
    // appending capped pieces can introduce internal faces across existing voids.
        function subtractBoxFromMesh(mesh, box) {
            try {
                var epsilon = 1e-7;
                function polygon(vertices) {
                    var n = [0, 0, 0];
                    for (var i = 0; i < vertices.length; i += 1) {
                        var j = (i + 1) % vertices.length;
                        var vi = vertices[i], vj = vertices[j];
                        n[0] += (vi[1] - vj[1]) * (vi[2] + vj[2]);
                        n[1] += (vi[2] - vj[2]) * (vi[0] + vj[0]);
                        n[2] += (vi[0] - vj[0]) * (vi[1] + vj[1]);
                    }
                    var len = Math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]);
                    if (len > 1e-9) {
                        n = [n[0] / len, n[1] / len, n[2] / len];
                    } else {
                        n = normalize(cross(subtractVector(vertices[1], vertices[0]), subtractVector(vertices[2], vertices[0])), [0, 0, 1]);
                    }
                    var w = 0;
                    for (var k = 0; k < vertices.length; k += 1) {
                        w += dot(n, vertices[k]);
                    }
                    w /= vertices.length;
                    return { vertices: vertices, normal: n, w: w };
                }
                function flip(p) { p.vertices.reverse(); p.normal = scaleVector(p.normal, -1); p.w = -p.w; }
                function split(plane, p, coFront, coBack, front, back) {
                    var types = [], kind = 0;
                    p.vertices.forEach(function (v) {
                        var distance = dot(plane.normal, v) - plane.w;
                        var t = distance < -epsilon ? 2 : distance > epsilon ? 1 : 0;
                        kind |= t; types.push(t);
                    });
                    if (kind === 0) (dot(plane.normal, p.normal) > 0 ? coFront : coBack).push(p);
                    else if (kind === 1) front.push(p);
                    else if (kind === 2) back.push(p);
                    else {
                        var f = [], b = [];
                        p.vertices.forEach(function (v, i) {
                            var j = (i + 1) % p.vertices.length, next = p.vertices[j];
                            if (types[i] !== 2) f.push(v);
                            if (types[i] !== 1) b.push(v);
                            if ((types[i] | types[j]) === 3) {
                                var delta = subtractVector(next, v);
                                var denom = dot(plane.normal, delta);
                                var t = Math.abs(denom) > 1e-12 ? (plane.w - dot(plane.normal, v)) / denom : 0.5;
                                if (!isFinite(t)) t = 0.5;
                                t = Math.max(0, Math.min(1, t));
                                var point = addVector(v, scaleVector(delta, t));
                                f.push(point); b.push(point.slice());
                            }
                        });
                        f = removeDuplicateLoopPoints(f); b = removeDuplicateLoopPoints(b);
                        if (f.length >= 3) front.push(polygon(f));
                        if (b.length >= 3) back.push(polygon(b));
                    }
                }
                function Node(polygons, depth) {
                    this.polygons = []; this.plane = null; this.front = null; this.back = null;
                    if (polygons) this.build(polygons, depth || 0);
                }
                Node.prototype.build = function (polygons, depth) {
                    depth = depth || 0;
                    if (!polygons || !polygons.length) return;
                    if (depth > 60) {
                        for (var d = 0; d < polygons.length; d += 1) this.polygons.push(polygons[d]);
                        return;
                    }
                    if (!this.plane) this.plane = { normal: polygons[0].normal.slice(), w: polygons[0].w };
                    var front = [], back = [], node = this;
                    polygons.forEach(function (p) { split(node.plane, p, node.polygons, node.polygons, front, back); });
                    if (front.length === polygons.length && !node.polygons.length) {
                        for (var fi = 0; fi < polygons.length; fi += 1) node.polygons.push(polygons[fi]);
                        return;
                    }
                    if (back.length === polygons.length && !node.polygons.length) {
                        for (var bi = 0; bi < polygons.length; bi += 1) node.polygons.push(polygons[bi]);
                        return;
                    }
                    if (front.length) { if (!this.front) this.front = new Node(null, depth + 1); this.front.build(front, depth + 1); }
                    if (back.length) { if (!this.back) this.back = new Node(null, depth + 1); this.back.build(back, depth + 1); }
                };
                Node.prototype.invert = function () {
                    this.polygons.forEach(flip);
                    if (this.plane) { this.plane.normal = scaleVector(this.plane.normal, -1); this.plane.w = -this.plane.w; }
                    if (this.front) this.front.invert(); if (this.back) this.back.invert();
                    var temp = this.front; this.front = this.back; this.back = temp;
                };
                Node.prototype.all = function () { return this.polygons.concat(this.front ? this.front.all() : [], this.back ? this.back.all() : []); };
                Node.prototype.clip = function (polygons, depth) {
                    depth = depth || 0;
                    if (!this.plane || !polygons || !polygons.length || depth > 60) return polygons ? polygons.slice() : [];
                    var front = [], back = [], node = this;
                    polygons.forEach(function (p) { split(node.plane, p, front, back, front, back); });
                    if (this.front) front = this.front.clip(front, depth + 1);
                    back = this.back ? this.back.clip(back, depth + 1) : [];
                    return front.concat(back);
                };
                Node.prototype.clipTo = function (other, depth) {
                    depth = depth || 0;
                    if (depth > 60) return;
                    this.polygons = other.clip(this.polygons, depth);
                    if (this.front) this.front.clipTo(other, depth + 1);
                    if (this.back) this.back.clipTo(other, depth + 1);
                };
                var signedVolume = 0;
                mesh.faces.forEach(function (f) { signedVolume += dot(mesh.vertices[f[0]], cross(mesh.vertices[f[1]], mesh.vertices[f[2]])) / 6; });
                var input = mesh.faces.map(function (f) {
                    var points = f.map(function (index) { return mesh.vertices[index].slice(); });
                    if (signedVolume < 0) points.reverse();
                    return polygon(points);
                });
                var corners = [];
                for (var mask = 0; mask < 8; mask += 1) {
                    var point = box.origin.slice();
                    for (var axis = 0; axis < 3; axis += 1) point = addVector(point, scaleVector(box.axes[axis], mask & (1 << axis) ? box.maxs[axis] : box.mins[axis]));
                    corners.push(point);
                }
                var faces = [[0,4,6,2],[1,3,7,5],[0,1,5,4],[2,6,7,3],[0,2,3,1],[4,5,7,6]];
                var a = new Node(input), b = new Node(faces.map(function (f) { return polygon(f.map(function (i) { return corners[i]; })); }));
                a.invert(); a.clipTo(b); b.clipTo(a); b.invert(); b.clipTo(a); b.invert(); a.build(b.all()); a.invert();
                var result = emptyMesh(), vertexMap = {};
                a.all().forEach(function (p) {
                    var indices = p.vertices.map(function (v) { return addUniqueVertex(result, vertexMap, v); });
                    for (var i = 1; i < indices.length - 1; i += 1) {
                        var points = [result.vertices[indices[0]], result.vertices[indices[i]], result.vertices[indices[i+1]]];
                        if (vectorLength(cross(subtractVector(points[1],points[0]),subtractVector(points[2],points[0]))) > 1e-10) result.faces.push([indices[0],indices[i],indices[i+1]]);
                    }
                });
                return result;
            } catch (err) {
                console.warn('subtractBoxFromMesh fallback due to CSG error:', err);
                return mesh;
            }
        }

        function holeForOpeningExtrusion(host, opening) {
            var hostLength = vectorLength(host.offset);
            var openingLength = vectorLength(opening.offset);
            if (hostLength < 1e-8 || openingLength < 1e-8) return null;

            var basis = basisForExtrusion(host);
            var openingNormal = normalize(opening.offset, [0, 0, 1]);
            if (Math.abs(dot(basis.normal, openingNormal)) < 0.9999) return null;

            var minHeight = Infinity, maxHeight = -Infinity;
            opening.base.forEach(function (point) {
                var bottom = dot(subtractVector(point, basis.origin), basis.normal);
                var top = dot(subtractVector(addVector(point, opening.offset), basis.origin), basis.normal);
                minHeight = Math.min(minHeight, bottom, top);
                maxHeight = Math.max(maxHeight, bottom, top);
            });
            if (minHeight > 1e-7 || maxHeight < hostLength - 1e-7) return null;

            var outer2d = host.base.map(function (point) { return projectToBasis2d(point, basis); });
            var hole = removeDuplicateLoopPoints(opening.base).map(function (point) {
                var projected = projectToBasis2d(point, basis);
                return {
                    point: pointFromBasis2d(projected, basis),
                    projected: projected
                };
            });

            if (hole.length < 3 || !hole.every(function (item) {
                return pointStrictlyInsidePolygon(item.projected, outer2d);
            })) {
                return null;
            }

            return hole.map(function (item) { return item.point; });
        }

        function cloneExtrusion(extrusion) {
            return {
                base: extrusion.base.map(function (point) { return point.slice(); }),
                offset: extrusion.offset.slice(),
                holes: (extrusion.holes || []).map(function (hole) {
                    return hole.map(function (point) { return point.slice(); });
                })
            };
        }


        kernel.attachFillHostBounds = attachFillHostBounds;
        kernel.boundsForOpeningMeshes = boundsForOpeningMeshes;
        kernel.boxFromExtrusion = boxFromExtrusion;
        kernel.carveItemOpenings = carveItemOpenings;
        kernel.cloneExtrusion = cloneExtrusion;
        kernel.countIndexedVoids = countIndexedVoids;
        kernel.extrusionsForOpenings = extrusionsForOpenings;
        kernel.holeForOpeningExtrusion = holeForOpeningExtrusion;
        kernel.indexHostIdsByOpening = indexHostIdsByOpening;
        kernel.indexOpeningsByFill = indexOpeningsByFill;
        kernel.indexVoidsByHost = indexVoidsByHost;
        kernel.meshesForOpenings = meshesForOpenings;
        kernel.subtractBoxFromMesh = subtractBoxFromMesh;
        return function bindDependencies() {
            addDiagnosticOnce = kernel.addDiagnosticOnce;
            addUniqueVertex = kernel.addUniqueVertex;
            addVector = kernel.addVector;
            appendMesh = kernel.appendMesh;
            asText = kernel.asText;
            basisForExtrusion = kernel.basisForExtrusion;
            boundsForElements = kernel.boundsForElements;
            boundsForVertices = kernel.boundsForVertices;
            cross = kernel.cross;
            dot = kernel.dot;
            earcutFunction = kernel.earcutFunction;
            emptyMesh = kernel.emptyMesh;
            meshForExtrusionWithHoles = kernel.meshForExtrusionWithHoles;
            meshForRepresentationItem = kernel.meshForRepresentationItem;
            normalize = kernel.normalize;
            pointFromBasis2d = kernel.pointFromBasis2d;
            pointStrictlyInsidePolygon = kernel.pointStrictlyInsidePolygon;
            projectToBasis2d = kernel.projectToBasis2d;
            refId = kernel.refId;
            removeDuplicateLoopPoints = kernel.removeDuplicateLoopPoints;
            representationItems = kernel.representationItems;
            scaleVector = kernel.scaleVector;
            subtractVector = kernel.subtractVector;
            vectorLength = kernel.vectorLength;
        };
    };
})(window.IfcFds);
