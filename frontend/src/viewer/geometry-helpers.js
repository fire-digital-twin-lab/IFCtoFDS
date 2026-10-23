(function (ns) {
    function clearGroup(group) {
        if (!group) return;
        while (group.children.length) {
            var child = group.children[group.children.length - 1];
            group.remove(child);
            child.traverse(function (node) {
                if (node.geometry) node.geometry.dispose();
                if (node.material) {
                    if (Array.isArray(node.material)) node.material.forEach(function (mat) { mat.dispose(); });
                    else node.material.dispose();
                }
            });
        }
    }

    function sizeFromXb(xb, minSize) {
        return {
            x: Math.max(xb[1] - xb[0], minSize),
            y: Math.max(xb[3] - xb[2], minSize),
            z: Math.max(xb[5] - xb[4], minSize)
        };
    }

    function centerFromXb(xb) {
        return {
            x: (xb[0] + xb[1]) / 2,
            y: (xb[2] + xb[3]) / 2,
            z: (xb[4] + xb[5]) / 2
        };
    }

    function toThree(x, y, z) {
        return new THREE.Vector3(x, z, y);
    }

    function rgbToHex(rgb) {
        return (rgb[0] << 16) + (rgb[1] << 8) + rgb[2];
    }

    // Multiply each RGB channel by `factor` (0..1) to darken a packed-int hex color. Used
    // to push GEOM materials a notch below their OBST siblings so the two output kinds are
    // visually distinct in the overlay.
    function darkenHex(hex, factor) {
        var f = Math.max(0, Math.min(1, factor));
        var r = Math.max(0, Math.min(255, Math.round(((hex >> 16) & 0xff) * f)));
        var g = Math.max(0, Math.min(255, Math.round(((hex >> 8) & 0xff) * f)));
        var b = Math.max(0, Math.min(255, Math.round((hex & 0xff) * f)));
        return (r << 16) | (g << 8) | b;
    }

    // Palette mirrors the standalone demo viewer: specific colors for the BIM staples (doors,
    // windows, walls, slabs, roofs, spaces) and the IFC-file's own surface color for anything
    // else when web-ifc supplied one.
    function styleForIfcType(type, referenceOnly, sourceColor) {
        if (type === 'IFCDOOR') {
            return { color: 0x985d3f, opacity: 1, edgeColor: 0x5a2c1d, edgeOpacity: 0.72, openingSurface: true };
        }
        if (type === 'IFCWINDOW') {
            return { color: 0x6db4d6, opacity: 0.62, edgeColor: 0x286c91, edgeOpacity: 0.72, openingSurface: true };
        }
        if (type === 'IFCSLAB' || type === 'IFCROOF') {
            return { color: 0xb7becb, opacity: 1, edgeColor: 0x5f6877, edgeOpacity: 0.72, openingSurface: false };
        }
        if (type === 'IFCWALL' || type === 'IFCWALLSTANDARDCASE') {
            return { color: 0xd2d6dc, opacity: 1, edgeColor: 0x67707d, edgeOpacity: 0.72, openingSurface: false };
        }
        if (type === 'IFCSPACE') {
            return { color: 0xa6d7c8, opacity: 0.18, edgeColor: 0x4b8b79, edgeOpacity: 0.5, openingSurface: false };
        }
        var fallback = sourceColor ? rgbColorToHex(sourceColor) : 0xc1c7d2;
        var fallbackOpacity = sourceColor && typeof sourceColor.a === 'number'
            ? Math.max(0.22, sourceColor.a)
            : 1;
        return {
            color: fallback,
            opacity: referenceOnly ? 0.45 : fallbackOpacity,
            edgeColor: 0x687184,
            edgeOpacity: 0.6,
            openingSurface: false
        };
    }

    function rgbColorToHex(color) {
        var r = Math.round(Math.max(0, Math.min(1, color.r)) * 255);
        var g = Math.round(Math.max(0, Math.min(1, color.g)) * 255);
        var b = Math.round(Math.max(0, Math.min(1, color.b)) * 255);
        return (r << 16) | (g << 8) | b;
    }

    function easeOutCubic(t) {
        return 1 - Math.pow(1 - Math.max(0, Math.min(1, t)), 3);
    }

    function categoryForIfcType(type) {
        if (!type) return 'other';
        var u = String(type).toUpperCase();
        if (u === 'IFCDOOR' || u === 'IFCWINDOW') return 'fills';
        if (/^IFC(WALL|SLAB|ROOF|COLUMN|BEAM|STAIR|MEMBER|RAILING|CURTAINWALL|PLATE|COVERING|FOOTING|PILE)/.test(u)) return 'structure';
        if (/^IFC(FLOW|DUCT|PIPE|AIRTERMINAL|FAN|VALVE|DISTRIBUTION|PUMP|BOILER|CHILLER|DAMPER)/.test(u)) return 'mep';
        if (u.indexOf('SPACE') >= 0) return 'space';
        return 'other';
    }

    function isExcludedMesh(mesh, excludedSteps, excludedItems) {
        if (!mesh || !mesh.userData) return false;
        var userData = mesh.userData;
        if (excludedItems) {
            var itemIds = itemIdsForMesh(userData);
            for (var j = 0; j < itemIds.length; j += 1) {
                if (excludedItems[itemIds[j]]) return true;
            }
        }
        if (excludedSteps) {
            var stepIds = stepIdsForMesh(userData);
            for (var i = 0; i < stepIds.length; i += 1) {
                if (excludedSteps[stepIds[i]]) return true;
            }
        }
        return false;
    }

    function itemIdsForMesh(userData) {
        var ids = [];
        if (userData.id) ids.push(String(userData.id));
        if (userData.raw && userData.raw.ID) ids.push(String(userData.raw.ID));
        if (userData.ifcSource && userData.ifcSource.itemId) ids.push(String(userData.ifcSource.itemId));
        return ids;
    }

    function stepIdsForMesh(userData) {
        var ids = [];
        if (userData.ifcSource && userData.ifcSource.stepId) {
            ids.push(String(userData.ifcSource.stepId).replace(/^#/, ''));
        }
        if (userData.raw) {
            var raw = userData.raw;
            if (raw.id) ids.push(String(raw.id).replace(/^#/, ''));
            if (raw.stepId) ids.push(String(raw.stepId).replace(/^#/, ''));
            if (raw.__ifcSource && raw.__ifcSource.stepId) ids.push(String(raw.__ifcSource.stepId).replace(/^#/, ''));
        }
        if (userData.expressID) ids.push(String(userData.expressID));
        return ids;
    }

    function setIfcMaterialOpacity(material, ifcOpacity) {
        if (Array.isArray(material)) {
            material.forEach(function (item) { setIfcMaterialOpacity(item, ifcOpacity); });
            return;
        }
        if (!material || material.userData.ifcBaseOpacity === undefined) return;
        var opacity = scaleIfcOpacity(material.userData.ifcBaseOpacity, ifcOpacity);
        material.opacity = opacity;
        material.transparent = opacity < 1;
        if (material.userData.isIfcFace) {
            material.side = THREE.DoubleSide;
            material.depthWrite = true;
            material.needsUpdate = true;
        }
    }

    function scaleIfcOpacity(baseOpacity, ifcOpacity) {
        return Math.max(0, Math.min(1, baseOpacity * ifcOpacity));
    }

    function makeUserData(type, item) {
        return {
            type: type,
            entityKey: item.entityKey || item.entity_key || (ns.workbench && ns.workbench.createEntityKey(item)),
            sourceId: item.sourceId || item.source_id,
            id: item.id,
            surf_id: item.surf_id || null,
            ifcSource: item.ifcSource || null,
            xb: item.xb || null,
            raw: item.raw || item
        };
    }

    // Each subsystem owns one channel. Parent groups independently retain layer/root visibility.
    function setVisibilityChannel(node, channel, visible) {
        var channels = node._visibilityChannels || (node._visibilityChannels = {});
        channels[channel] = !!visible;
        node.visible = Object.keys(channels).every(function (key) { return channels[key]; });
    }

    function applyGhostMaterial(material, ghosted) {
        if (!material) return;
        if (ghosted && !material._ghostBase) {
            material._ghostBase = {opacity: material.opacity, transparent: material.transparent, depthWrite: material.depthWrite};
            material.transparent = true;
            material.opacity = 0.15;
            material.depthWrite = false;
            material.needsUpdate = true;
        } else if (!ghosted && material._ghostBase) {
            Object.assign(material, material._ghostBase);
            delete material._ghostBase;
            material.needsUpdate = true;
        }
    }

    ns.viewer.setVisibilityChannel = setVisibilityChannel;

    function findSelectableNode(object) {
        var node = object;
        var match = null;
        while (node) {
            if (node.userData && node.userData.type) match = node;
            node = node.parent;
        }
        return match;
    }

    function collectVisiblePickTargets(group, targets) {
        if (!group.visible) return;
        group.traverse(function (node) {
            if ((node.isMesh || node.isLineSegments) && isVisibleWithin(node, group)) targets.push(node);
        });
    }

    function collectWalkTargets(group, targets, predicate) {
        if (!group) return;
        group.traverse(function (node) {
            if (!node.isMesh || !node.visible) return;
            if (!predicate || predicate(node)) targets.push(node);
        });
    }

    function walkHitHasUpwardNormal(hit, minimumY) {
        if (!hit.face || !hit.object) return true;
        var normal = hit.face.normal.clone();
        normal.applyMatrix3(new THREE.Matrix3().getNormalMatrix(hit.object.matrixWorld)).normalize();
        return normal.y >= minimumY;
    }

    // Decides whether a horizontal walk-collision hit should be ignored, letting the walker
    // pass through:
    //  * Door closure OBSTs (SURF_ID='IFC_DOOR' in the FDS namelist) — doors are openable.
    //  * Wall sections that are carved away by a sibling &HOLE — the FDS-truth says there
    //    is no blocking at that location even though the mesh OBST geometry covers it.
    function walkHitIsPassable(hit, holeBoxes) {
        if (!hit || !hit.object) return false;
        var data = hit.object.userData;
        if (data && data.surf_id === 'IFC_DOOR') return true;
        if (!holeBoxes || !holeBoxes.length) return false;
        var pt = hit.point;
        for (var i = 0; i < holeBoxes.length; i += 1) {
            if (holeBoxes[i].containsPoint(pt)) return true;
        }
        return false;
    }

    function isVisibleWithin(node, root) {
        while (node) {
            if (!node.visible) return false;
            if (node === root) return true;
            node = node.parent;
        }
        return false;
    }

    function setObjectHover(object, hovered) {
        object.traverse(function (node) {
            if (node.material) setMaterialHover(node.material, hovered);
        });
    }

    function setMaterialHover(material, hovered) {
        if (Array.isArray(material)) {
            material.forEach(function (mat) { setMaterialHover(mat, hovered); });
            return;
        }

        if (!material) return;
        if (!material.userData.__hoverOriginal) {
            material.userData.__hoverOriginal = {
                color: material.color ? material.color.getHex() : null,
                emissive: material.emissive ? material.emissive.getHex() : null,
                opacity: material.opacity
            };
        }

        var original = material.userData.__hoverOriginal;
        if (hovered) {
            if (material.color) material.color.setHex(0xffd166);
            if (material.emissive) material.emissive.setHex(0x332000);
            if (material.opacity !== undefined) {
                material.opacity = Math.min(1, Math.max(material.opacity, 0.92));
                material.transparent = material.opacity < 1;
            }
        } else {
            if (material.color && original.color !== null) material.color.setHex(original.color);
            if (material.emissive && original.emissive !== null) material.emissive.setHex(original.emissive);
            if (material.opacity !== undefined) {
                material.opacity = original.opacity;
                material.transparent = material.opacity < 1;
            }
            delete material.userData.__hoverOriginal;
        }
    }

    function isOpaqueIfcHit(object) {
        if (!object || !object.material) return true;
        var material = object.material;
        var base = material.userData && material.userData.ifcBaseOpacity;
        if (typeof base === 'number') return base >= 0.95;
        return !material.transparent;
    }

    function selectionPriority(type) {
        if (type === 'VENT') return 1;
        if (type === 'HOLE') return 2;
        if (type === 'GEOM' || type === 'GEOM sphere') return 3;
        if (type === 'OBST') return 4;
        if (type === 'IFC') return 5;
        if (type === 'MESH') return 20;
        return 10;
    }


    ns.viewer.geometryHelpers = {
        clearGroup: clearGroup,
        sizeFromXb: sizeFromXb,
        centerFromXb: centerFromXb,
        toThree: toThree,
        rgbToHex: rgbToHex,
        darkenHex: darkenHex,
        styleForIfcType: styleForIfcType,
        rgbColorToHex: rgbColorToHex,
        easeOutCubic: easeOutCubic,
        categoryForIfcType: categoryForIfcType,
        isExcludedMesh: isExcludedMesh,
        itemIdsForMesh: itemIdsForMesh,
        stepIdsForMesh: stepIdsForMesh,
        setIfcMaterialOpacity: setIfcMaterialOpacity,
        scaleIfcOpacity: scaleIfcOpacity,
        makeUserData: makeUserData,
        setVisibilityChannel: setVisibilityChannel,
        applyGhostMaterial: applyGhostMaterial,
        findSelectableNode: findSelectableNode,
        collectVisiblePickTargets: collectVisiblePickTargets,
        collectWalkTargets: collectWalkTargets,
        walkHitHasUpwardNormal: walkHitHasUpwardNormal,
        walkHitIsPassable: walkHitIsPassable,
        isVisibleWithin: isVisibleWithin,
        setObjectHover: setObjectHover,
        setMaterialHover: setMaterialHover,
        isOpaqueIfcHit: isOpaqueIfcHit,
        selectionPriority: selectionPriority
    };
})(window.IfcFds);
