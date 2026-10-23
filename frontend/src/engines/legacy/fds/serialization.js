(function (ns) {
    ns.fds.legacyFactories = ns.fds.legacyFactories || {};
    ns.fds.legacyFactories.createSerialization = function (kernel, constants) {



        function wrapArray(prefix, values, perLine) {
            var lines = [];
            for (var i = 0; i < values.length; i += perLine) {
                lines.push((i === 0 ? prefix : spaces(prefix.length)) + values.slice(i, i + perLine).join(','));
            }
            return lines.join(',\n');
        }

        function paddedBounds(bounds, margin) {
            if (!bounds) return null;
            return {
                xmin: bounds.xmin - margin,
                xmax: bounds.xmax + margin,
                ymin: bounds.ymin - margin,
                ymax: bounds.ymax + margin,
                zmin: Math.min(0, bounds.zmin - margin),
                zmax: bounds.zmax + margin
            };
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

        function boundsForVertices(vertices) {
            var bounds = null;
            vertices.forEach(function (vertex) {
                if (!bounds) {
                    bounds = {
                        xmin: vertex[0], xmax: vertex[0],
                        ymin: vertex[1], ymax: vertex[1],
                        zmin: vertex[2], zmax: vertex[2]
                    };
                    return;
                }
                bounds.xmin = Math.min(bounds.xmin, vertex[0]);
                bounds.xmax = Math.max(bounds.xmax, vertex[0]);
                bounds.ymin = Math.min(bounds.ymin, vertex[1]);
                bounds.ymax = Math.max(bounds.ymax, vertex[1]);
                bounds.zmin = Math.min(bounds.zmin, vertex[2]);
                bounds.zmax = Math.max(bounds.zmax, vertex[2]);
            });
            return bounds;
        }

        function thinnestAxis(bounds) {
            var spans = [
                bounds.xmax - bounds.xmin,
                bounds.ymax - bounds.ymin,
                bounds.zmax - bounds.zmin
            ];
            var axis = 0;
            if (spans[1] < spans[axis]) axis = 1;
            if (spans[2] < spans[axis]) axis = 2;
            return axis;
        }

        function closedFillBounds(element, voxelSize, openingVoxelPolicy) {
            var bounds = copyBounds(element.fillOpeningBounds || element.bounds);
            var axis = thinnestAxis(bounds);
            var hostBounds = element.fillHostBounds || bounds;
            var size = Math.max(0.01, Number(voxelSize) || 0.1);
            ['x', 'y', 'z'].forEach(function (name, currentAxis) {
                var source = currentAxis === axis ? hostBounds : bounds;
                var snapped = currentAxis === axis
                    ? snapOutward(source[name + 'min'], source[name + 'max'], size)
                    : snapOpening(source[name + 'min'], source[name + 'max'], size, openingVoxelPolicy);
                bounds[name + 'min'] = snapped.min;
                bounds[name + 'max'] = snapped.max;
            });
            return inflateThinBounds(bounds, 0.02);
        }

        function normalizeOpeningVoxelPolicy(policy) {
            return policy === 'larger' ? 'larger' : 'smaller';
        }

        function snapOpening(min, max, size, openingVoxelPolicy) {
            if (normalizeOpeningVoxelPolicy(openingVoxelPolicy) !== 'smaller') {
                return snapOutward(min, max, size);
            }

            var snapped = {
                min: Math.ceil(min / size - 0.5) * size,
                max: (Math.floor(max / size - 0.5) + 1) * size
            };
            if (snapped.max <= snapped.min) return snapAroundCenter(min, max, size);
            return snapped;
        }

        function snapOutward(min, max, size) {
            return {
                min: Math.floor(min / size) * size,
                max: Math.ceil(max / size) * size
            };
        }

        function snapAroundCenter(min, max, size) {
            var snappedMin = Math.floor(((min + max) / 2) / size) * size;
            return { min: snappedMin, max: snappedMin + size };
        }

        function copyBounds(bounds) {
            return {
                xmin: bounds.xmin,
                xmax: bounds.xmax,
                ymin: bounds.ymin,
                ymax: bounds.ymax,
                zmin: bounds.zmin,
                zmax: bounds.zmax
            };
        }

        function inflateThinBounds(bounds, minThickness) {
            var b = copyBounds(bounds);
            inflateAxis(b, 'x', minThickness);
            inflateAxis(b, 'y', minThickness);
            inflateAxis(b, 'z', minThickness);
            return b;
        }

        function inflateAxis(bounds, axis, minThickness) {
            var minKey = axis + 'min';
            var maxKey = axis + 'max';
            var span = bounds[maxKey] - bounds[minKey];
            if (span >= minThickness) return;
            var center = (bounds[minKey] + bounds[maxKey]) / 2;
            bounds[minKey] = center - minThickness / 2;
            bounds[maxKey] = center + minThickness / 2;
        }

        function formatXb(bounds) {
            return [
                bounds.xmin, bounds.xmax,
                bounds.ymin, bounds.ymax,
                bounds.zmin, bounds.zmax
            ].map(formatNumber).join(',');
        }

        function formatNumber(value) {
            var fixed = Number(value).toFixed(6);
            return fixed.replace(/\.?0+$/, '');
        }

        function cleanId(name, index) {
            var id = String(name || 'IFC element ' + index).trim();
            if (id.length > 48) id = id.slice(0, 45) + '...';
            return id || 'IFC element ' + index;
        }

    // Two walls / slabs with the same IFC name (e.g. "Wand-001" copied across floors) used
    // to collide into a single FDS ID, which made the delete-by-id path remove *all*
    // instances when the user removed one. The exporter creates a fresh allocator at the
    // top of every export and threads it through every cleanId-producing site. The first
    // occurrence of a name keeps the name as-is (so tests that pin exact names still pass);
    // subsequent occurrences get a ":2", ":3", ... suffix.
        function makeIdAllocator() {
            var counts = {};
            return function (name, index) {
                var base = cleanId(name, index);
                if (counts[base] === undefined) {
                    counts[base] = 1;
                    return base;
                }
                counts[base] += 1;
                var suffix = ':' + counts[base];
                var maxBase = Math.max(1, 48 - suffix.length);
                var truncated = base.length > maxBase ? base.slice(0, Math.max(1, maxBase - 3)) + '...' : base;
                return truncated + suffix;
            };
        }

        function escapeFdsString(value) {
            return String(value).replace(/'/g, "''");
        }

        function surfaceForElement(element) {
            if (element.ifcType === 'IFCDOOR') return 'IFC_DOOR';
            if (element.ifcType === 'IFCWINDOW') return 'IFC_WINDOW';
            return 'IFC_SOLID';
        }

        function formatIfcSourceComment(element, outputType, itemId) {
            return [
                '! IFC_SOURCE',
                "OUTPUT='" + escapeFdsString(outputType) + "'",
                "ITEM_ID='" + escapeFdsString(itemId) + "'",
                "IFC_TYPE='" + escapeFdsString(element.ifcType || '') + "'",
                "GLOBAL_ID='" + escapeFdsString(element.globalId || '') + "'",
                "STEP_ID='" + escapeFdsString('#' + (element.stepId || '')) + "'",
                "NAME='" + escapeFdsString(element.name || '') + "'"
            ].join(', ');
        }

        function spaces(count) {
            return new Array(count + 1).join(' ');
        }


        kernel.boundsForElements = boundsForElements;
        kernel.boundsForVertices = boundsForVertices;
        kernel.cleanId = cleanId;
        kernel.closedFillBounds = closedFillBounds;
        kernel.copyBounds = copyBounds;
        kernel.escapeFdsString = escapeFdsString;
        kernel.formatIfcSourceComment = formatIfcSourceComment;
        kernel.formatNumber = formatNumber;
        kernel.formatXb = formatXb;
        kernel.inflateAxis = inflateAxis;
        kernel.inflateThinBounds = inflateThinBounds;
        kernel.makeIdAllocator = makeIdAllocator;
        kernel.normalizeOpeningVoxelPolicy = normalizeOpeningVoxelPolicy;
        kernel.paddedBounds = paddedBounds;
        kernel.snapAroundCenter = snapAroundCenter;
        kernel.snapOpening = snapOpening;
        kernel.snapOutward = snapOutward;
        kernel.spaces = spaces;
        kernel.surfaceForElement = surfaceForElement;
        kernel.thinnestAxis = thinnestAxis;
        kernel.wrapArray = wrapArray;
        return function bindDependencies() {

        };
    };
})(window.IfcFds);
