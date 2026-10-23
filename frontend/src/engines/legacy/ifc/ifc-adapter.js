(function (ns) {
    var PRODUCT_TYPES = {
        IFCWALL: true,
        IFCWALLSTANDARDCASE: true,
        IFCSLAB: true,
        IFCDOOR: true,
        IFCWINDOW: true,
        IFCSTAIR: true,
        IFCSTAIRFLIGHT: true,
        IFCMEMBER: true,
        IFCRAILING: true,
        IFCROOF: true,
        IFCCOLUMN: true,
        IFCBEAM: true,
        IFCBUILDINGELEMENTPROXY: true,
        IFCFURNISHINGELEMENT: true,
        IFCFLOWSEGMENT: true,
        IFCFLOWFITTING: true,
        IFCFLOWTERMINAL: true,
        IFCDUCTSEGMENT: true,
        IFCPIPESEGMENT: true,
        IFCAIRTERMINAL: true,
        IFCELEMENTASSEMBLY: true,
        IFCSPACE: true,
        IFCCOVERING: true,
        IFCFOOTING: true,
        IFCRAMP: true,
        IFCRAMPFLIGHT: true,
        IFCFLOWCONTROLLER: true,
        IFCFLOWMOVINGDEVICE: true,
        IFCFLOWSTORAGEDEVICE: true,
        IFCFLOWMETER: true,
        IFCFIRESUPPRESSIONTERMINAL: true,
        IFCDISTRIBUTIONCHAMBERELEMENT: true,
        IFCDISTRIBUTIONPORT: true
    };
    var REVIEW_TYPES = {
        IFCBUILDINGELEMENTPROXY: 'Building element proxy',
        IFCFURNISHINGELEMENT: 'Furnishing element',
        IFCFLOWSEGMENT: 'Flow segment',
        IFCFLOWFITTING: 'Flow fitting',
        IFCFLOWTERMINAL: 'Flow terminal',
        IFCDUCTSEGMENT: 'Duct segment',
        IFCPIPESEGMENT: 'Pipe segment',
        IFCAIRTERMINAL: 'Air terminal',
        IFCELEMENTASSEMBLY: 'Element assembly',
        IFCRAILING: 'Railing',
        IFCCOVERING: 'Covering',
        IFCFOOTING: 'Footing',
        IFCRAMP: 'Ramp',
        IFCRAMPFLIGHT: 'Ramp flight',
        IFCFLOWCONTROLLER: 'Flow controller (valve / damper)',
        IFCFLOWMOVINGDEVICE: 'Flow moving device (fan / pump)',
        IFCFLOWSTORAGEDEVICE: 'Flow storage device (tank)',
        IFCFLOWMETER: 'Flow meter',
        IFCFIRESUPPRESSIONTERMINAL: 'Fire suppression terminal (sprinkler)',
        IFCDISTRIBUTIONCHAMBERELEMENT: 'Distribution chamber',
        IFCDISTRIBUTIONPORT: 'Distribution port'
    };

    function IfcAdapter() {}

    IfcAdapter.prototype.readFile = function (file, onProgress, options) {
        var self = this;
        return readText(file).then(function (text) {
            var fileName = file ? file.name : 'IFC model';
            return (onProgress || options)
                ? self.parseAsync(text, fileName, onProgress, options)
                : self.parse(text, fileName, options);
        });
    };

    IfcAdapter.prototype.parse = function (text, fileName, options) {
        var ctx = beginParse(text, options);
        ctx.step.entities.forEach(function (entity) { processEntity(ctx, entity); });
        return finishParse(ctx, fileName);
    };

    // Shards the entity list across N worker scripts, each running the same beginParse +
    // processEntity pipeline on its slice. Returns a merged model identical to parseAsync.
    // Falls back to a single worker / serial parse cleanly via the existing parseAsync if the
    // worker can't start.
    IfcAdapter.prototype.parseAsyncParallel = function (text, fileName, onProgress, options, workerCount) {
        var self = this;
        var factory = window.IfcFds && window.IfcFds.workers && window.IfcFds.workers.createParseShardWorker;
        if (!factory) return self.parseAsync(text, fileName, onProgress, options);

        var ctx = beginParse(text, options);
        var entities = ctx.step.entities;
        var total = entities.length;
        var shards = Math.max(1, Math.min(workerCount || (navigator.hardwareConcurrency || 4), 8));
        if (total < 50000) {
            // Sharding overhead (each worker re-parses STEP text + builds indexes) only pays
            // off on big models; small models like FZK (44k entities) and Duplex (27k) are
            // measurably faster on the main-thread async path.
            return self.parseAsync(text, fileName, onProgress, options);
        }
        var shardSize = Math.ceil(total / shards);
        var completed = 0;

        function runShard(shardIndex) {
            var startIndex = shardIndex * shardSize;
            var endIndex = Math.min(startIndex + shardSize, total);
            return new Promise(function (resolve, reject) {
                var handle;
                try { handle = factory(); } catch (err) { reject(err); return; }
                var worker = handle.worker;
                worker.onmessage = function (event) {
                    var data = event.data || {};
                    if (data.type === 'error') {
                        cleanup();
                        reject(Object.assign(new Error(data.message || 'parse shard failed'), data.error || {}));
                        return;
                    }
                    if (data.type !== 'parse-shard-result') return;
                    cleanup();
                    completed += 1;
                    if (onProgress) onProgress(completed / shards);
                    resolve(data);
                };
                worker.onerror = function (event) {
                    cleanup();
                    reject(new Error(event.message || 'parse shard worker error'));
                };
                worker.postMessage({
                    type: 'parse-shard',
                    requestId: shardIndex,
                    shardIndex: shardIndex,
                    text: text,
                    startIndex: startIndex,
                    endIndex: endIndex
                });
                function cleanup() {
                    try { worker.terminate(); } catch (_) { /* ignore */ }
                    if (handle.url) {
                        try { URL.revokeObjectURL(handle.url); } catch (_) { /* ignore */ }
                    }
                }
            });
        }

        var jobs = [];
        for (var i = 0; i < shards; i += 1) jobs.push(runShard(i));

        return Promise.all(jobs).then(function (results) {
            // Merge each shard's partial state back into the main context, then finish.
            results.forEach(function (r) {
                if (Array.isArray(r.elements)) {
                    r.elements.forEach(function (el) { ctx.elements.push(el); });
                }
                if (r.unsupported) {
                    Object.keys(r.unsupported).forEach(function (k) {
                        ctx.unsupported[k] = (ctx.unsupported[k] || 0) + r.unsupported[k];
                    });
                }
                if (Array.isArray(r.diagnostics)) {
                    r.diagnostics.forEach(function (d) { ctx.diagnostics.push(d); });
                }
                if (r.voidStatsApplied) {
                    Object.keys(r.voidStatsApplied).forEach(function (k) { ctx.voidStats.applied[k] = true; });
                }
                if (typeof r.openingMaskCount === 'number') ctx.openingMaskCount += r.openingMaskCount;
            });
            return finishParse(ctx, fileName);
        }).catch(function (err) {
            console.warn('parallel parse failed, falling back to serial:', err);
            return self.parseAsync(text, fileName, onProgress, options);
        });
    };

    // Same work as parse() but with cooperative yields every CHUNK entities so a large
    // IFC doesn't freeze the main thread. onProgress(fraction) is called between chunks.
    IfcAdapter.prototype.parseAsync = function (text, fileName, onProgress, options) {
        var ctx = beginParse(text, options);
        var entities = ctx.step.entities;
        var total = entities.length;
        var CHUNK = 800;
        var idx = 0;

        function processChunk() {
            var end = Math.min(idx + CHUNK, total);
            for (; idx < end; idx += 1) processEntity(ctx, entities[idx]);
            if (onProgress) onProgress(total ? idx / total : 1);
            if (idx < total) {
                return new Promise(function (resolve) { setTimeout(resolve, 0); }).then(processChunk);
            }
            return finishParse(ctx, fileName);
        }

        return Promise.resolve().then(processChunk);
    };

    function beginParse(text, options) {
        var diagnostics = [];
        var step = new StepModel(text);
        var scale = detectLengthScale(step, diagnostics);
        var voidsByHost = indexVoidsByHost(step);
        return {
            step: step,
            diagnostics: diagnostics,
            scale: scale,
            elements: [],
            unsupported: {},
            stairChildIds: indexStairChildIds(step),
            voidsByHost: voidsByHost,
            hostIdsByOpening: indexHostIdsByOpening(voidsByHost),
            openingsByFill: indexOpeningsByFill(step),
            voidStats: { applied: {}, total: countIndexedVoids(voidsByHost) },
            openingMaskCount: 0,
            skipBoxOpenings: !!(options && options.skipBoxOpenings)
        };
    }

    function processEntity(ctx, entity) {
        try { return processEntityGeometry(ctx, entity); }
        catch (error) { error.entityId = entity.id; if (!error.stage) error.stage = 'ifc_geometry'; throw error; }
    }

    function processEntityGeometry(ctx, entity) {
        if (!isSupportedProduct(entity, ctx.stairChildIds)) return;
        var step = ctx.step;

        var placement = step.transformForLocalPlacement(entity.args[5]);
        var representation = step.ref(entity.args[6]);
        var items = representationItems(step, representation);
        var mesh = emptyMesh();
        var hostOpenings = ctx.voidsByHost[entity.id] || [];
        var openingExtrusions = extrusionsForOpenings(
            step,
            hostOpenings,
            ctx.diagnostics,
            ctx.unsupported
        );
        var openings = meshesForOpenings(step, hostOpenings, ctx.diagnostics, ctx.unsupported);
        var fillOpenings = meshesForOpenings(step, ctx.openingsByFill[entity.id] || [], ctx.diagnostics, ctx.unsupported);
        ctx.openingMaskCount += openings.length;
        var displayMesh = openingExtrusions.length ? emptyMesh() : null;
        var displayDiffers = false;

        items.forEach(function (item) {
            var itemMesh = meshForRepresentationItem(step, item, placement, ctx.diagnostics, ctx.unsupported);
            if (displayMesh) {
                var carved = ns.core.atStage('openings', function () { return carveItemOpenings(itemMesh, openingExtrusions, ctx.diagnostics, ctx.voidStats, { skipBoxOpenings: ctx.skipBoxOpenings }); });
                appendMesh(mesh, carved.exportMesh);
                appendMesh(displayMesh, carved.displayMesh);
                if (carved.displayMesh !== carved.exportMesh) displayDiffers = true;
            } else {
                appendMesh(mesh, itemMesh);
            }
        });

        scaleMesh(mesh, ctx.scale);
        if (displayMesh && displayDiffers) scaleMesh(displayMesh, ctx.scale);
        openings.forEach(function (opening) {
            scaleMesh(opening.mesh, ctx.scale);
        });
        fillOpenings.forEach(function (opening) {
            scaleMesh(opening.mesh, ctx.scale);
        });
        if (!mesh.vertices.length || !mesh.faces.length) {
            ns.core.addDiagnostic(
                ctx.diagnostics,
                'warning',
                'IFC element skipped',
                labelForEntity(entity) + ' has no supported Body geometry yet.'
            );
            return;
        }

        var bounds = boundsForVertices(mesh.vertices);
        var classification = classifyElement(entity, bounds);
        ctx.elements.push({
            stepId: entity.id,
            ifcType: entity.type,
            globalId: asText(entity.args[0]),
            name: asText(entity.args[2]) || entity.type + ' #' + entity.id,
            convertible: classification.convertible,
            reference: classification.reference,
            exportAsSolid: classification.exportAsSolid !== false,
            canExportAsSolid: classification.canExportAsSolid !== false,
            fdsRole: classification.fdsRole,
            conversionNote: classification.note,
            openings: openings,
            fillOpeningBounds: boundsForOpeningMeshes(fillOpenings),
            fillHostStepIds: fillOpenings.map(function (opening) {
                return ctx.hostIdsByOpening[opening.stepId];
            }).filter(Boolean),
            geomExportMesh: (displayMesh && displayDiffers) ? displayMesh : mesh,
            exportGeometryComplete: (!ctx.skipBoxOpenings || !hostOpenings.length) && hostOpenings.every(function (opening) { return !!ctx.voidStats.applied[opening.id]; }),
            mesh: mesh,
            displayMesh: (displayMesh && displayDiffers) ? displayMesh : undefined,
            bounds: bounds,
            raw: {
                id: '#' + entity.id,
                type: entity.type,
                globalId: asText(entity.args[0]),
                name: asText(entity.args[2]),
                convertible: classification.convertible,
                exportAsSolid: classification.exportAsSolid !== false,
                canExportAsSolid: classification.canExportAsSolid !== false,
                fdsRole: classification.fdsRole,
                conversionNote: classification.note
            }
        });
    }

    function finishParse(ctx, fileName) {
        attachFillHostBounds(ctx.elements);

        Object.keys(ctx.unsupported).forEach(function (type) {
            ns.core.addDiagnostic(
                ctx.diagnostics,
                'info',
                'Unsupported IFC geometry: ' + type,
                ctx.unsupported[type] + ' representation item(s) were skipped in this first importer milestone.'
            );
        });

        var appliedVoidCount = Object.keys(ctx.voidStats.applied).length;
        if (appliedVoidCount) {
            ns.core.addDiagnostic(
                ctx.diagnostics,
                'success',
                'IFC voids applied',
                appliedVoidCount + ' opening void(s) were subtracted from directly extruded host geometry.'
            );
        }
        if (ctx.voidStats.total > appliedVoidCount) {
            ns.core.addDiagnostic(
                ctx.diagnostics,
                'info',
                'IFC voids awaiting broader CSG support',
                (ctx.voidStats.total - appliedVoidCount) + ' opening void(s) could not yet be subtracted from their host representation.'
            );
        }
        if (ctx.openingMaskCount) {
            ns.core.addDiagnostic(
                ctx.diagnostics,
                'success',
                'IFC voxel opening masks ready',
                ctx.openingMaskCount + ' host opening volume(s) will carve window, door, and shaft apertures from voxel OBST export.'
            );
        }

        if (!ctx.elements.length) {
            ns.core.addDiagnostic(
                ctx.diagnostics,
                'warning',
                'No convertible IFC elements',
                'This importer currently supports IfcExtrudedAreaSolid with rectangle/polyline profiles and IfcFacetedBrep.'
            );
        } else {
            ns.core.addDiagnostic(
                ctx.diagnostics,
                'success',
                'IFC import ready',
                ctx.elements.length + ' element(s) were converted to browser geometry in metres.'
            );
        }

        return {
            fileName: fileName,
            schema: ctx.step.schema,
            unitScale: ctx.scale,
            elements: ctx.elements,
            meshes: ctx.elements.map(function (element) { return element.mesh; }),
            bounds: boundsForElements(ctx.elements),
            convertibleBounds: boundsForElements(ctx.elements.filter(function (element) { return element.convertible !== false; })),
            diagnostics: ctx.diagnostics,
            stats: {
                entities: ctx.step.entities.length,
                elements: ctx.elements.length
            }
        };
    }

    function detectLengthScale(step, diagnostics) {
        var scale = 1;
        step.each(function (entity) {
            if (entity.type !== 'IFCSIUNIT') return;
            var unitType = String(entity.args[1] || '').toUpperCase();
            var prefix = String(entity.args[2] || '').toUpperCase();
            var name = String(entity.args[3] || '').toUpperCase();
            if (unitType !== '.LENGTHUNIT.' || name !== '.METRE.') return;
            scale = prefixScale(prefix);
        });

        if (scale !== 1) {
            ns.core.addDiagnostic(
                diagnostics,
                'info',
                'IFC units converted',
                'Length coordinates were scaled by ' + scale + ' to metres.'
            );
        }
        return scale;
    }

    function prefixScale(prefix) {
        if (prefix === '.MILLI.') return 0.001;
        if (prefix === '.CENTI.') return 0.01;
        if (prefix === '.DECI.') return 0.1;
        if (prefix === '.KILO.') return 1000;
        return 1;
    }

    function representationItems(step, productDefinitionShape) {
        if (!productDefinitionShape || productDefinitionShape.type !== 'IFCPRODUCTDEFINITIONSHAPE') return [];
        var representations = Array.isArray(productDefinitionShape.args[2]) ? productDefinitionShape.args[2] : [];
        var resolved = representations.map(function (repRef) { return step.ref(repRef); }).filter(function (representation) {
            return representation && representation.type === 'IFCSHAPEREPRESENTATION';
        });
        var bodies = resolved.filter(function (representation) {
            return String(representation.args[1] || '').toUpperCase() === 'BODY';
        });
        var items = [];

        (bodies.length ? bodies : resolved).forEach(function (representation) {
            var repItems = Array.isArray(representation.args[3]) ? representation.args[3] : [];
            repItems.forEach(function (itemRef) {
                var item = step.ref(itemRef);
                if (item) items.push(item);
            });
        });

        return items;
    }

    function indexStairChildIds(step) {
        var ids = {};

        step.each(function (entity) {
            if (entity.type !== 'IFCRELAGGREGATES') return;
            var parent = step.ref(entity.args[4]);
            if (!parent || parent.type !== 'IFCSTAIR') return;
            var children = Array.isArray(entity.args[5]) ? entity.args[5] : [];
            children.forEach(function (child) {
                var childId = refId(child);
                if (childId) ids[childId] = true;
            });
        });

        return ids;
    }

    function isSupportedProduct(entity, stairChildIds) {
        if (entity.type === 'IFCMEMBER') return !!stairChildIds[entity.id];
        return !!PRODUCT_TYPES[entity.type];
    }

    function readText(file) {
        return new Promise(function (resolve, reject) {
            var reader = new FileReader();
            reader.onload = function () { resolve(String(reader.result || '')); };
            reader.onerror = function () { reject(reader.error); };
            reader.readAsText(file);
        });
    }

    // Link private function references once; preserve numerical hot paths.
    var kernel = {
        IfcAdapter: IfcAdapter,
        beginParse: beginParse,
        detectLengthScale: detectLengthScale,
        finishParse: finishParse,
        indexStairChildIds: indexStairChildIds,
        isSupportedProduct: isSupportedProduct,
        prefixScale: prefixScale,
        processEntity: processEntity,
        processEntityGeometry: processEntityGeometry,
        readText: readText,
        representationItems: representationItems
    };
    var constants = {PRODUCT_TYPES: PRODUCT_TYPES, REVIEW_TYPES: REVIEW_TYPES};
    var bindings = [
        ns.ifc.legacyFactories.createStepParser(kernel, constants),
        ns.ifc.legacyFactories.createOpenings(kernel, constants),
        ns.ifc.legacyFactories.createRepresentations(kernel, constants),
        ns.ifc.legacyFactories.createClipping(kernel, constants),
        ns.ifc.legacyFactories.createTriangulation(kernel, constants),
        ns.ifc.legacyFactories.createMeshTransforms(kernel, constants)
    ];
    bindings.forEach(function (bind) { bind(); });
    var StepModel = kernel.StepModel;
    var addCapLoops = kernel.addCapLoops;
    var addClipCaps = kernel.addClipCaps;
    var addDiagnosticOnce = kernel.addDiagnosticOnce;
    var addUniqueVertex = kernel.addUniqueVertex;
    var addVector = kernel.addVector;
    var appendFaceRefsToMesh = kernel.appendFaceRefsToMesh;
    var appendMesh = kernel.appendMesh;
    var asText = kernel.asText;
    var attachFillHostBounds = kernel.attachFillHostBounds;
    var axesTransform = kernel.axesTransform;
    var basisForExtrusion = kernel.basisForExtrusion;
    var basisFromPlanarPoints = kernel.basisFromPlanarPoints;
    var boundsForElements = kernel.boundsForElements;
    var boundsForOpeningMeshes = kernel.boundsForOpeningMeshes;
    var boundsForVertices = kernel.boundsForVertices;
    var boxFromExtrusion = kernel.boxFromExtrusion;
    var carveItemOpenings = kernel.carveItemOpenings;
    var classifyElement = kernel.classifyElement;
    var clipMeshByPlane = kernel.clipMeshByPlane;
    var clipPolygonByPlane = kernel.clipPolygonByPlane;
    var clippingPlaneForHalfSpace = kernel.clippingPlaneForHalfSpace;
    var cloneExtrusion = kernel.cloneExtrusion;
    var composeTransform = kernel.composeTransform;
    var countIndexedVoids = kernel.countIndexedVoids;
    var cross = kernel.cross;
    var detectSchema = kernel.detectSchema;
    var dot = kernel.dot;
    var earcutFunction = kernel.earcutFunction;
    var emptyMesh = kernel.emptyMesh;
    var extrudeProfile = kernel.extrudeProfile;
    var extrusionsForOpenings = kernel.extrusionsForOpenings;
    var findStatementEnd = kernel.findStatementEnd;
    var holeForOpeningExtrusion = kernel.holeForOpeningExtrusion;
    var identityTransform = kernel.identityTransform;
    var indexHostIdsByOpening = kernel.indexHostIdsByOpening;
    var indexOpeningsByFill = kernel.indexOpeningsByFill;
    var indexVoidsByHost = kernel.indexVoidsByHost;
    var intersectionPoint = kernel.intersectionPoint;
    var intersectionPointsForTriangle = kernel.intersectionPointsForTriangle;
    var invertTransform = kernel.invertTransform;
    var isIdentityish = kernel.isIdentityish;
    var isInsideClip = kernel.isInsideClip;
    var labelForEntity = kernel.labelForEntity;
    var meshForBooleanClippingResult = kernel.meshForBooleanClippingResult;
    var meshForExtrudedAreaSolid = kernel.meshForExtrudedAreaSolid;
    var meshForExtrusionWithHoles = kernel.meshForExtrusionWithHoles;
    var meshForFaceBasedSurfaceModel = kernel.meshForFaceBasedSurfaceModel;
    var meshForFacetedBrep = kernel.meshForFacetedBrep;
    var meshForMappedItem = kernel.meshForMappedItem;
    var meshForRepresentationItem = kernel.meshForRepresentationItem;
    var meshForTriangulatedFaceSet = kernel.meshForTriangulatedFaceSet;
    var meshesForOpenings = kernel.meshesForOpenings;
    var normalize = kernel.normalize;
    var numberOr = kernel.numberOr;
    var parseArg = kernel.parseArg;
    var parseEntities = kernel.parseEntities;
    var perpendicularVector = kernel.perpendicularVector;
    var pointFromBasis2d = kernel.pointFromBasis2d;
    var pointKey = kernel.pointKey;
    var pointList3d = kernel.pointList3d;
    var pointOnSegment2d = kernel.pointOnSegment2d;
    var pointStrictlyInsidePolygon = kernel.pointStrictlyInsidePolygon;
    var pointsForCurve = kernel.pointsForCurve;
    var polygonNormal = kernel.polygonNormal;
    var profilePoints2d = kernel.profilePoints2d;
    var projectToBasis2d = kernel.projectToBasis2d;
    var refId = kernel.refId;
    var removeDuplicateLoopPoints = kernel.removeDuplicateLoopPoints;
    var scaleMesh = kernel.scaleMesh;
    var scaleVector = kernel.scaleVector;
    var signedDistanceToPlane = kernel.signedDistanceToPlane;
    var splitTopLevel = kernel.splitTopLevel;
    var subtractBoxFromMesh = kernel.subtractBoxFromMesh;
    var subtractVector = kernel.subtractVector;
    var transformForCartesianOperator = kernel.transformForCartesianOperator;
    var transformMesh = kernel.transformMesh;
    var transformPoint = kernel.transformPoint;
    var transformVector = kernel.transformVector;
    var triangulatePlanarPolygon = kernel.triangulatePlanarPolygon;
    var uniquePoints = kernel.uniquePoints;
    var vectorClose = kernel.vectorClose;
    var vectorLength = kernel.vectorLength;

    // Exposed for the parallel parse-shard worker so it can drive the same parse pipeline
    // on a slice of entities without duplicating the per-entity body.
    IfcAdapter.beginParse = beginParse;
    IfcAdapter.processEntity = processEntity;
    IfcAdapter.finishParse = finishParse;

    ns.ifc.IfcAdapter = IfcAdapter;
})(window.IfcFds);
