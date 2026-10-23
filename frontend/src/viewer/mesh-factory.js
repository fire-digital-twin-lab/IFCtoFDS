(function (ns) {
    ns.viewer.installMeshFactory = function (SceneViewer, helpers) {
        var sizeFromXb = helpers.sizeFromXb;
        var centerFromXb = helpers.centerFromXb;
        var toThree = helpers.toThree;
        var rgbToHex = helpers.rgbToHex;
        var darkenHex = helpers.darkenHex;
        var styleForIfcType = helpers.styleForIfcType;
        var categoryForIfcType = helpers.categoryForIfcType;
        var scaleIfcOpacity = helpers.scaleIfcOpacity;
        var makeUserData = helpers.makeUserData;
        var setVisibilityChannel = helpers.setVisibilityChannel;

        SceneViewer.prototype.addWebIfcDisplayMeshes = function (model, displayMeshes) {
            var elementsByExpressID = {};
            (model.elements || []).forEach(function (el) { elementsByExpressID[el.stepId] = el; });

            var zFlip = new THREE.Matrix4().set(
                1, 0, 0, 0,
                0, 1, 0, 0,
                0, 0, -1, 0,
                0, 0, 0, 1
            );
            var self = this;

            displayMeshes.forEach(function (entry) {
                var element = elementsByExpressID[entry.expressID];
                var group = (element && element.reference === true) ? self.ifcReferenceGroup : self.ifcSolidGroup;

                var geom = new THREE.BufferGeometry();
                geom.setAttribute('position', new THREE.BufferAttribute(entry.positions, 3));
                geom.setAttribute('normal', new THREE.BufferAttribute(entry.normals, 3));
                geom.setIndex(new THREE.BufferAttribute(entry.indices, 1));

                var ifcType = element ? element.ifcType : null;
                var style = styleForIfcType(ifcType, element && element.convertible === false, entry.color);
                var opacity = scaleIfcOpacity(style.opacity, self.ifcOpacity);
                var isTransparent = opacity < 1;

                var material = new THREE.MeshPhongMaterial({
                    color: style.color,
                    transparent: isTransparent,
                    opacity: opacity,
                    side: THREE.DoubleSide,
                    depthWrite: true,
                    shininess: 8,
                    specular: 0x0b0b0b
                });
                material.userData.ifcBaseOpacity = style.opacity;
                material.userData.isIfcFace = true;
                material.userData.isIfcOpeningSurface = !!style.openingSurface;

                var mesh = new THREE.Mesh(geom, material);
                var local = new THREE.Matrix4().fromArray(entry.matrix);
                mesh.matrixAutoUpdate = false;
                mesh.matrix.multiplyMatrices(zFlip, local);
                mesh.renderOrder = isTransparent ? 1 : 0;

                if (element) {
                    mesh.userData = {
                        type: 'IFC',
                        entityKey: element.entityKey || element.entity_key || ns.workbench.createEntityKey(element),
                        sourceId: element.sourceId || (element.raw && element.raw.source_id),
                        stepId: element.stepId,
                        id: element.name || element.ifcType + ' #' + element.stepId,
                        ifcType: element.ifcType,
                        ifcCategory: categoryForIfcType(element.ifcType),
                        globalId: element.globalId,
                        convertible: element.convertible,
                        fdsRole: element.fdsRole,
                        canExportAsSolid: element.canExportAsSolid,
                        conversionNote: element.conversionNote,
                        bounds: element.bounds,
                        raw: element.raw
                    };
                } else {
                    mesh.userData = {
                        type: 'IFC',
                        sourceId: self.sourceId || 'ifc',
                        entityKey: (self.sourceId || 'ifc') + ':' + entry.expressID,
                        id: 'IFC #' + entry.expressID,
                        ifcType: 'IFC',
                        ifcCategory: 'other',
                        expressID: entry.expressID
                    };
                }

                var edgeMaterial = new THREE.LineBasicMaterial({
                    color: style.edgeColor,
                    transparent: true,
                    opacity: scaleIfcOpacity(style.edgeOpacity, self.ifcOpacity),
                    depthWrite: false
                });
                edgeMaterial.userData.ifcBaseOpacity = style.edgeOpacity;
                var edges = new THREE.LineSegments(
                    new THREE.EdgesGeometry(geom, 50),
                    edgeMaterial
                );
                setVisibilityChannel(edges, 'edgeDisplay', style.openingSurface || self.showIfcEdges);
                edges._isIfcEdge = true;
                edges._isIfcOpeningEdge = !!style.openingSurface;
                edges.userData = mesh.userData;
                mesh.add(edges);

                group.add(mesh);
            });
        };

        SceneViewer.prototype.makeWireBox = function (item, color, type) {
            var size = sizeFromXb(item.xb, 0.001);
            var center = centerFromXb(item.xb);
            var geometry = new THREE.BoxGeometry(size.x, size.z, size.y);
            var edges = new THREE.EdgesGeometry(geometry);
            var material = new THREE.LineBasicMaterial({ color: color, transparent: true, opacity: 0.9 });
            var line = new THREE.LineSegments(edges, material);
            line.position.copy(toThree(center.x, center.y, center.z));
            line.userData = makeUserData(type, item);
            return line;
        };

        SceneViewer.prototype.makeBox = function (item, fallbackColor, type, forceThin) {
            var size = sizeFromXb(item.xb, forceThin ? 0.025 : 0.001);
            var center = centerFromXb(item.xb);
            var color = item.color ? rgbToHex(item.color) : fallbackColor;
            // Window/door closures sit exactly on the host wall plane, which causes z-fighting
            // flicker against the wall OBST behind them. Inflate the rendered geometry by ~6 mm
            // in each direction so the closure's faces sit slightly proud of the wall. The FDS
            // file data is unchanged — only the Three.js box is bumped.
            var isClosure = type === 'OBST' && (item.surf_id === 'IFC_WINDOW' || item.surf_id === 'IFC_DOOR');
            if (isClosure) {
                size.x += 0.012;
                size.y += 0.012;
                size.z += 0.012;
            }
            var geometry = new THREE.BoxGeometry(size.x, size.z, size.y);
            // HOLEs are "negative" entities (they carve blocking from a prior &OBST). When the
            // user also has Closed window/door fills on, a colored closure OBST sits in the same
            // volume — drawing the HOLE solid would mask the closure's IFC_WINDOW / IFC_DOOR
            // colour. Render HOLEs very transparent and depthWrite-off so the closure shows
            // through, but keep the edges visible so the user can still see which volumes are
            // declared as HOLEs.
            var faceOpacity;
            if (type === 'OBST') faceOpacity = this.opacity;
            else if (type === 'HOLE') faceOpacity = 0.18;
            else faceOpacity = 0.82;
            var material = new THREE.MeshPhongMaterial({
                color: color,
                transparent: true,
                opacity: faceOpacity,
                side: THREE.DoubleSide,
                depthWrite: type !== 'HOLE'
            });
            var box = new THREE.Mesh(geometry, material);
            box.position.copy(toThree(center.x, center.y, center.z));
            box.userData = makeUserData(type, item);
            if (type === 'HOLE') box.renderOrder = 2;

            var edgeMaterial = new THREE.LineBasicMaterial({
                color: type === 'HOLE' ? 0x00b3cc : 0x4d5264,
                transparent: true,
                opacity: type === 'HOLE' ? 0.85 : 0.55
            });
            var edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), edgeMaterial);
            edges.userData = box.userData;
            box.add(edges);
            return box;
        };

        SceneViewer.prototype.makeGeom = function (geom) {
            if (geom.type === 'sphere') {
                var sphereGeometry = new THREE.SphereGeometry(geom.radius, 24, 14);
                var sphereMaterial = new THREE.MeshPhongMaterial({ color: geom.color ? rgbToHex(geom.color) : 0x64c8ff, transparent: true, opacity: this.opacity });
                var sphere = new THREE.Mesh(sphereGeometry, sphereMaterial);
                sphere.position.copy(toThree(geom.origin[0], geom.origin[1], geom.origin[2]));
                sphere.userData = makeUserData('GEOM sphere', geom);
                return sphere;
            }

            var positions = [];
            var indices = [];
            var origin = geom.vertices.length ? geom.vertices[0] : [0,0,0];
            geom.vertices.forEach(function (v) {
                var converted = toThree(v[0] - origin[0], v[1] - origin[1], v[2] - origin[2]);
                positions.push(converted.x, converted.y, converted.z);
            });
            geom.faces.forEach(function (f) { indices.push(f[0], f[1], f[2]); });

            var geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
            geometry.setIndex(indices);
            geometry.computeVertexNormals();

            // GEOMs render distinctly darker than OBSTs so the two outputs are easy to tell
            // apart in the overlay. Most GEOMs are SURF_ID='IFC_SOLID' (RGB 185 gray); the 0.55
            // multiplier drops them to ~102 gray (about 45% darker), past the threshold where
            // Phong lighting could be mistaken for the lit/shadowed side of an OBST.
            var baseColor = geom.color ? rgbToHex(geom.color) : 0x707078;
            var material = new THREE.MeshPhongMaterial({
                color: darkenHex(baseColor, 0.55),
                transparent: true,
                opacity: this.opacity,
                side: THREE.DoubleSide
            });
            var mesh = new THREE.Mesh(geometry, material);
            mesh.position.copy(toThree(origin[0], origin[1], origin[2]));
            mesh.userData = makeUserData('GEOM', geom);
            var edges = new THREE.LineSegments(
                new THREE.EdgesGeometry(geometry, 25),
                new THREE.LineBasicMaterial({ color: 0x1d6f9c, transparent: true, opacity: 0.7 })
            );
            edges.userData = mesh.userData;
            mesh.add(edges);
            return mesh;
        };

        SceneViewer.prototype.makeIfcElement = function (element) {
            var positions = [];
            var indices = [];
            // Prefer the display mesh (host walls carry their window/door voids there); the
            // solid element.mesh is reserved for the FDS export pipeline.
            var source = element.displayMesh || element.mesh;
            var origin = source.vertices.length ? source.vertices[0] : [0,0,0];
            source.vertices.forEach(function (v) {
                // Keep Float32 vertex coordinates near the product origin. The
                // Object3D placement remains in the original double-precision world.
                var converted = toThree(v[0] - origin[0], v[1] - origin[1], v[2] - origin[2]);
                positions.push(converted.x, converted.y, converted.z);
            });
            source.faces.forEach(function (f) {
                indices.push(f[0], f[1], f[2]);
            });

            var geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
            geometry.setIndex(indices);
            geometry.computeVertexNormals();

            var style = styleForIfcType(element.ifcType, element.convertible === false && !element.backendSourcePreview);
            var opacity = scaleIfcOpacity(style.opacity, this.ifcOpacity);
            var isTransparent = opacity < 1;
            var material = new THREE.MeshPhongMaterial({
                color: style.color,
                transparent: isTransparent,
                opacity: opacity,
                side: THREE.DoubleSide,
                depthWrite: true,
                shininess: 8,
                specular: 0x0b0b0b
            });
            material.userData.ifcBaseOpacity = style.opacity;
            material.userData.isIfcFace = true;
            material.userData.isIfcOpeningSurface = !!style.openingSurface;
            var mesh = new THREE.Mesh(geometry, material);
            mesh.position.copy(toThree(origin[0], origin[1], origin[2]));
            mesh.renderOrder = isTransparent ? 1 : 0;
            mesh.userData = {
                type: 'IFC',
                entityKey: element.entityKey || element.entity_key || ns.workbench.createEntityKey(element),
                sourceId: element.sourceId || (element.raw && element.raw.source_id),
                stepId: element.stepId,
                id: element.name || element.ifcType + ' #' + element.stepId,
                ifcType: element.ifcType,
                ifcCategory: categoryForIfcType(element.ifcType),
                globalId: element.globalId,
                convertible: element.convertible,
                fdsRole: element.fdsRole,
                canExportAsSolid: element.canExportAsSolid,
                conversionNote: element.conversionNote,
                bounds: element.bounds,
                raw: element.raw
            };

            // Large backend previews build selection outlines only when selected.
            if (element.deferEdges) return mesh;
            var edgeMaterial = new THREE.LineBasicMaterial({
                color: style.edgeColor,
                transparent: true,
                opacity: scaleIfcOpacity(style.edgeOpacity, this.ifcOpacity),
                depthWrite: false
            });
            edgeMaterial.userData.ifcBaseOpacity = style.edgeOpacity;
            var edges = new THREE.LineSegments(
                new THREE.EdgesGeometry(geometry, 50),
                edgeMaterial
            );
            setVisibilityChannel(edges, 'edgeDisplay', style.openingSurface || this.showIfcEdges);
            edges._isIfcEdge = true;
            edges._isIfcOpeningEdge = !!style.openingSurface;
            edges.userData = mesh.userData;
            mesh.add(edges);
            return mesh;
        };

    };
})(window.IfcFds);
