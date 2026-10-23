(function (ns) {
    ns.viewer.installGeometryLoader = function (SceneViewer, helpers) {
        var clearGroup = helpers.clearGroup;
        var toThree = helpers.toThree;

        SceneViewer.prototype.loadFdsModel = function (model) {
            this.fdsCoordinateRebase = model.coordinateRebase || [0, 0, 0];
            if (this.verifiedReferenceGroup && this.verifiedReferenceGroup.position) {
                var offset = this.fdsCoordinateRebase;
                this.verifiedReferenceGroup.position.copy(toThree(offset[0], offset[1], offset[2]));
            }
            this.setNavigationMode('orbit');
            this.setSelectedObjects([]);
            clearGroup(this.meshGroup);
            clearGroup(this.obstGroup);
            clearGroup(this.ventGroup);
            clearGroup(this.holeGroup);
            clearGroup(this.geomGroup);

            var self = this;
            (model.meshes || []).forEach(function (mesh) { self.meshGroup.add(self.makeWireBox(mesh, 0x4488ff, 'MESH')); });
            (model.obsts || []).forEach(function (obst) { self.obstGroup.add(self.makeBox(obst, 0xb0b0c0, 'OBST')); });
            (model.vents || []).forEach(function (vent) { self.ventGroup.add(self.makeBox(vent, 0xff6b35, 'VENT', true)); });
            (model.holes || []).forEach(function (hole) { self.holeGroup.add(self.makeBox(hole, 0x00e5ff, 'HOLE', true)); });
            (model.geoms || []).forEach(function (geom) { self.geomGroup.add(self.makeGeom(geom)); });

            // Opt FDS materials out of the global smooth clipping — for FDS the clip bars are
            // expected to make whole primitives appear/disappear rather than slicing through them.
            // applyFdsClipVisibility() below toggles each mesh.visible based on its world bbox.
            this.fdsGroup.traverse(function (node) {
                if (node.material && node.material.isMaterial) {
                    node.material.clippingPlanes = [];
                }
            });

            this.clearHover();
            this.applyFdsClipVisibility();
            this.applyVisibilityState(this.visibilityStore);
        };

        SceneViewer.prototype.bindVerifiedArtifacts = function (artifacts) {
            var self = this, generation = 0, controller;
            if (this.cancelVerifiedLoad) this.cancelVerifiedLoad();
            function reset() {
                generation++;
                if (controller) controller.abort();
                if (self.verifiedReferenceGroup) clearGroup(self.verifiedReferenceGroup);
            }
            this.cancelVerifiedLoad = reset;
            var toggle = document.getElementById('verified-show-reference');
            toggle.checked = false;
            toggle.onchange = async function () {
                reset();
                if (!toggle.checked) return;
                controller = new AbortController();
                var token = generation, signal = controller.signal;
                try {
                    var index = await (self.geometryClient || ns.api.geometry).readIndex(artifacts.geometry.url, signal);
                    if (token !== generation) return;
                    if (self.verifiedReferenceGroup) self.ifcGroup.remove(self.verifiedReferenceGroup);
                    self.verifiedReferenceGroup = new THREE.Group();
                    self.ifcGroup.add(self.verifiedReferenceGroup);
                    var entries = Object.values(index.elements).filter(function (entry) {
                        return entry.mesh && entry.simulation_role === 'REFERENCE_GEOMETRY' && entry.scope_decision !== 'OUT_OF_SCOPE';
                    });
                    var next = 0;
                    async function worker() {
                        while (next < entries.length && token === generation) {
                            var entry = entries[next++], ref = entry.mesh;
                            var buffer = await (self.geometryClient || ns.api.geometry).readPayload(artifacts.geometry.url, ref, entry.entity_key, signal);
                            var hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', buffer))).map(function (x) {return x.toString(16).padStart(2, '0');}).join('');
                            if (hash !== ref.payload || buffer.byteLength !== ref.byte_length) throw new Error('Geometry payload checksum mismatch');
                            var view = new DataView(buffer), vertices = [], faces = [];
                            for (var i=0; i<ref.vertex_count; i++) vertices.push([0,1,2].map(function (axis) {return view.getFloat64(i*24+axis*8,true);}));
                            for (var j=0; j<ref.face_count; j++) faces.push([0,1,2].map(function (axis) {return view.getUint32(ref.faces_offset+j*12+axis*4,true);}));
                            if (token !== generation) return;
                            var mesh = self.makeIfcElement({mesh:{vertices:vertices,faces:faces}, ifcType:entry.ifc_type,
                                name:entry.name, globalId:entry.global_id, stepId:entry.step_id, convertible:false, fdsRole:entry.simulation_role});
                            mesh.userData.entityKey = entry.entity_key;
                            self.verifiedReferenceGroup.add(mesh);
                        }
                    }
                    await Promise.all([worker(), worker()]);
                } catch (error) {
                    if (error.name !== 'AbortError' && token === generation) {
                        reset(); toggle.checked = false;
                        document.getElementById('verified-progress').textContent = error.message;
                    }
                }
            };
        };

        SceneViewer.prototype.loadVerifiedGeometry = function (packageData, manifest) {
            if (this.verifiedReferenceGroup) {
                clearGroup(this.verifiedReferenceGroup);
                this.ifcGroup.remove(this.verifiedReferenceGroup);
            }
            this.verifiedReferenceGroup = new THREE.Group();
            this.verifiedReferenceGroup.name = 'Verified source reference (not FDS obstacles)';
            this.ifcGroup.add(this.verifiedReferenceGroup);
            var entries = (packageData || {}).elements || {}, self = this;
            (manifest.records || []).forEach(function (record) {
                var entry = entries[record.entity_key];
                if (!entry || !entry.mesh || record.simulation_role !== 'REFERENCE_GEOMETRY' || record.scope_decision === 'OUT_OF_SCOPE') return;
                var mesh = self.makeIfcElement({mesh: entry.mesh, ifcType: record.ifc_type, name: record.name,
                    globalId: record.global_id, stepId: record.step_id, convertible: false,
                    fdsRole: record.simulation_role, raw: record});
                mesh.userData.entityKey = record.entity_key;
                mesh.userData.simulationRole = record.simulation_role;
                self.verifiedReferenceGroup.add(mesh);
            });
            this.verifiedReferenceGroup.visible = document.getElementById('verified-show-reference').checked;
            var group = this.verifiedReferenceGroup;
            document.getElementById('verified-show-reference').onchange = function (event) { group.visible = event.target.checked; };
        };

        SceneViewer.prototype.loadBackendPreview = async function (index, jobId, signal, onProgress) {
            var self = this, entries = Object.values(index.elements).filter(function (e) { return e.mesh; });
            var loadingToken = {}; this.backendPreviewLoading = loadingToken;
            var batches = [], batch = [], bytes = 0;
            entries.forEach(function (entry) {
                if (batch.length && (batch.length === 16 || bytes + entry.mesh.byte_length > 16 * 1024 * 1024)) {
                    batches.push(batch); batch = []; bytes = 0;
                }
                batch.push(entry); bytes += entry.mesh.byte_length;
            });
            if (batch.length) batches.push(batch);
            var next = 0, done = 0;
            async function worker() {
                while (next < batches.length) {
                    if (signal.aborted) throw new DOMException('Preview cancelled', 'AbortError');
                    var group = batches[next++], expectedBytes = group.reduce(function (sum, e) { return sum + e.mesh.byte_length; }, 0);
                    var buffer = await (self.geometryClient || ns.api.geometry).readPreviewBatch(jobId, group, expectedBytes, signal);
                    if (buffer.byteLength !== expectedBytes) throw new Error('Geometry batch length mismatch');
                    var offset = 0;
                    for (var item = 0; item < group.length; item++) {
                    var entry = group[item], ref = entry.mesh;
                    var hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new Uint8Array(buffer, offset, ref.byte_length)))).map(function (x) { return x.toString(16).padStart(2, '0'); }).join('');
                    if (hash !== ref.payload ||
                        ref.faces_offset !== ref.vertex_count * 24 ||
                        ref.byte_length !== ref.vertex_count * 24 + ref.face_count * 12) throw new Error('Invalid geometry payload: ' + entry.entity_key);
                    var view = new DataView(buffer, offset, ref.byte_length), vertices = [], faces = [];
                    offset += ref.byte_length;
                    for (var i = 0; i < ref.vertex_count; i++) vertices.push([0,1,2].map(function (axis) { return view.getFloat64(i*24+axis*8,true); }));
                    for (var j = 0; j < ref.face_count; j++) faces.push([0,1,2].map(function (axis) { return view.getUint32(ref.faces_offset+j*12+axis*4,true); }));
                    if (signal.aborted) throw new DOMException('Preview cancelled', 'AbortError');
                    self.ifcSolidGroup.add(self.makeIfcElement({mesh:{vertices:vertices,faces:faces},
                        entityKey:entry.entity_key, sourceId:entry.source_id, stepId:entry.step_id,
                        ifcType:entry.ifc_type, globalId:entry.global_id, name:entry.name, bounds:entry.bounds,
                        convertible:false, backendSourcePreview:true, deferEdges:true, raw:entry}));
                    if ((done + 1) % 32 === 0) self.applyIfcCategoryVisibility();
                    onProgress(++done, entries.length);
                    }
                }
            }
            // Two batches, at most 16 payloads / 16 MiB each, in flight.
            try {
                await Promise.all([worker(), worker()]);
                self.applyIfcCategoryVisibility();
            } finally {
                if (self.backendPreviewLoading === loadingToken) self.backendPreviewLoading = null;
            }
        };

        SceneViewer.prototype.loadIfcModel = function (model, displayMeshes) {
            this.setNavigationMode('orbit');
            this.setSelectedObjects([]);
            clearGroup(this.ifcSolidGroup);
            clearGroup(this.ifcReferenceGroup);

            if (displayMeshes && displayMeshes.length) {
                this.addWebIfcDisplayMeshes(model, displayMeshes);
            } else {
                var self = this;
                (model.elements || []).forEach(function (element) {
                    var group = element.reference === true ? self.ifcReferenceGroup : self.ifcSolidGroup;
                    group.add(self.makeIfcElement(element));
                });
            }

            this.clearHover();
            this.applyIfcCategoryVisibility();
            if (model.convertibleBounds || model.bounds) {
                this.fitToBounds(model.convertibleBounds || model.bounds);
            } else {
                this.fitToWorldBox();
            }
        };

    };
})(window.IfcFds);
