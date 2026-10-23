(function (ns) {
    ns.ifc.legacyFactories = ns.ifc.legacyFactories || {};
    ns.ifc.legacyFactories.createStepParser = function (kernel, constants) {
        var axesTransform;
        var composeTransform;
        var identityTransform;
        var normalize;
        var numberOr;
        var refId;


        function StepModel(text) {
            this.entities = parseEntities(text);
            this.byId = {};
            this.schema = detectSchema(text);
            this._placementCache = {};
            this._axisCache = {};

            for (var i = 0; i < this.entities.length; i += 1) {
                this.byId[this.entities[i].id] = this.entities[i];
            }
        }

    StepModel.prototype.each = function (callback) {
        this.entities.forEach(callback);
    };

    StepModel.prototype.ref = function (value) {
        var id = refId(value);
        return id ? this.byId[id] : null;
    };

    StepModel.prototype.point = function (value) {
        var entity = this.ref(value) || (value && value.type === 'IFCCARTESIANPOINT' ? value : null);
        if (!entity || entity.type !== 'IFCCARTESIANPOINT') return [0, 0, 0];
        var coords = Array.isArray(entity.args[0]) ? entity.args[0] : [];
        return [
            numberOr(coords[0], 0),
            numberOr(coords[1], 0),
            numberOr(coords[2], 0)
        ];
    };

    StepModel.prototype.direction = function (value, fallback) {
        var entity = this.ref(value) || (value && value.type === 'IFCDIRECTION' ? value : null);
        if (!entity || entity.type !== 'IFCDIRECTION') return fallback.slice();
        var ratios = Array.isArray(entity.args[0]) ? entity.args[0] : [];
        return normalize([
            numberOr(ratios[0], fallback[0]),
            numberOr(ratios[1], fallback[1]),
            numberOr(ratios[2], fallback[2])
        ], fallback);
    };

    StepModel.prototype.transformForAxisPlacement = function (value) {
        if (!value) return identityTransform();
        var id = refId(value) || (value.id || null);
        if (id && this._axisCache[id]) return this._axisCache[id];

        var entity = this.ref(value) || value;
        if (!entity) return identityTransform();

        var tx = identityTransform();
        if (entity.type === 'IFCAXIS2PLACEMENT3D') {
            var origin3 = this.point(entity.args[0]);
            var z3 = this.direction(entity.args[1], [0, 0, 1]);
            var x3 = this.direction(entity.args[2], [1, 0, 0]);
            tx = axesTransform(origin3, x3, z3);
        } else if (entity.type === 'IFCAXIS2PLACEMENT2D') {
            var origin2 = this.point(entity.args[0]);
            var x2 = this.direction(entity.args[1], [1, 0, 0]);
            tx = axesTransform(origin2, x2, [0, 0, 1]);
        }

        if (id) this._axisCache[id] = tx;
        return tx;
    };

    StepModel.prototype.transformForLocalPlacement = function (value) {
        var id = refId(value);
        if (!id) return identityTransform();
        if (this._placementCache[id]) return this._placementCache[id];

        var entity = this.byId[id];
        if (!entity || entity.type !== 'IFCLOCALPLACEMENT') return identityTransform();

        var parent = this.transformForLocalPlacement(entity.args[0]);
        var local = this.transformForAxisPlacement(entity.args[1]);
        var result = composeTransform(parent, local);
        this._placementCache[id] = result;
        return result;
    };

        function parseEntities(text) {
            var entities = [];
            var i = 0;

            while (i < text.length) {
                var hash = text.indexOf('#', i);
                if (hash < 0) break;
                var eq = text.indexOf('=', hash);
                if (eq < 0) break;
                var idText = text.slice(hash + 1, eq).trim();
                if (!/^\d+$/.test(idText)) {
                    i = hash + 1;
                    continue;
                }

                var end = findStatementEnd(text, eq + 1);
                if (end < 0) break;
                var statement = text.slice(hash, end).trim();
                var match = statement.match(/^#(\d+)\s*=\s*([A-Z0-9_]+)\s*\(([\s\S]*)\)$/i);
                if (match) {
                    entities.push({
                        id: parseInt(match[1], 10),
                        type: match[2].toUpperCase(),
                        args: splitTopLevel(match[3], ',').map(parseArg),
                        raw: statement
                    });
                }
                i = end + 1;
            }

            return entities;
        }

        function findStatementEnd(text, from) {
            var inString = false;
            for (var i = from; i < text.length; i += 1) {
                var ch = text.charAt(i);
                if (ch === "'") {
                    if (text.charAt(i + 1) === "'") {
                        i += 1;
                    } else {
                        inString = !inString;
                    }
                } else if (ch === ';' && !inString) {
                    return i;
                }
            }
            return -1;
        }

        function splitTopLevel(text, delimiter) {
            var parts = [];
            var current = '';
            var depth = 0;
            var inString = false;

            for (var i = 0; i < text.length; i += 1) {
                var ch = text.charAt(i);
                if (ch === "'") {
                    current += ch;
                    if (text.charAt(i + 1) === "'") {
                        current += text.charAt(i + 1);
                        i += 1;
                    } else {
                        inString = !inString;
                    }
                    continue;
                }

                if (!inString) {
                    if (ch === '(') depth += 1;
                    if (ch === ')') depth -= 1;
                    if (ch === delimiter && depth === 0) {
                        parts.push(current.trim());
                        current = '';
                        continue;
                    }
                }
                current += ch;
            }

            if (current.trim() || text.length === 0) parts.push(current.trim());
            return parts;
        }

        function parseArg(token) {
            var value = String(token || '').trim();
            if (!value || value === '$' || value === '*') return null;
            if (/^#\d+$/.test(value)) return value;
            if (value.charAt(0) === '(' && value.charAt(value.length - 1) === ')') {
                var inner = value.slice(1, -1).trim();
                return inner ? splitTopLevel(inner, ',').map(parseArg) : [];
            }
            if (value.charAt(0) === "'" && value.charAt(value.length - 1) === "'") {
                return value.slice(1, -1).replace(/''/g, "'");
            }

            var typed = value.match(/^([A-Z0-9_]+)\s*\(([\s\S]*)\)$/i);
            if (typed) {
                return {
                    type: typed[1].toUpperCase(),
                    args: splitTopLevel(typed[2], ',').map(parseArg)
                };
            }

            var numberText = value.replace(/D/i, 'E');
            var numeric = Number(numberText);
            return Number.isFinite(numeric) ? numeric : value.toUpperCase();
        }

        function detectSchema(text) {
            var match = text.match(/FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'/i);
            return match ? match[1] : 'IFC';
        }


        kernel.StepModel = StepModel;
        kernel.detectSchema = detectSchema;
        kernel.findStatementEnd = findStatementEnd;
        kernel.parseArg = parseArg;
        kernel.parseEntities = parseEntities;
        kernel.splitTopLevel = splitTopLevel;
        return function bindDependencies() {
            axesTransform = kernel.axesTransform;
            composeTransform = kernel.composeTransform;
            identityTransform = kernel.identityTransform;
            normalize = kernel.normalize;
            numberOr = kernel.numberOr;
            refId = kernel.refId;
        };
    };
})(window.IfcFds);
