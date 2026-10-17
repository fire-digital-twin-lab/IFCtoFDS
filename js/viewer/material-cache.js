/**
 * Material & Color Palette Manager for 3D SceneViewer.
 * Encapsulates IFC semantic styling, theme colors, and material instantiations.
 */
(function (root) {
    root.IfcFds = root.IfcFds || {};
    root.IfcFds.viewer = root.IfcFds.viewer || {};

    function darkenHex(hex, factor) {
        var f = Math.max(0, Math.min(1, factor));
        var r = Math.max(0, Math.min(255, Math.round(((hex >> 16) & 0xff) * f)));
        var g = Math.max(0, Math.min(255, Math.round(((hex >> 8) & 0xff) * f)));
        var b = Math.max(0, Math.min(255, Math.round((hex & 0xff) * f)));
        return (r << 16) | (g << 8) | b;
    }

    function rgbColorToHex(color) {
        var r = Math.round(Math.max(0, Math.min(1, color.r)) * 255);
        var g = Math.round(Math.max(0, Math.min(1, color.g)) * 255);
        var b = Math.round(Math.max(0, Math.min(1, color.b)) * 255);
        return (r << 16) | (g << 8) | b;
    }

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

    function categoryForIfcType(type) {
        if (!type) return 'other';
        if (type === 'IFCDOOR' || type === 'IFCWINDOW') return 'fills';
        if (/^IFC(WALL|SLAB|ROOF|COLUMN|BEAM|STAIR|MEMBER|RAILING|CURTAINWALL|PLATE|COVERING|FOOTING|PILE)/.test(type)) return 'structure';
        return 'other';
    }

    function scaleIfcOpacity(baseOpacity, masterOpacity) {
        return Math.max(0, Math.min(1, baseOpacity * masterOpacity));
    }

    root.IfcFds.viewer.materialCache = {
        darkenHex: darkenHex,
        rgbColorToHex: rgbColorToHex,
        styleForIfcType: styleForIfcType,
        categoryForIfcType: categoryForIfcType,
        scaleIfcOpacity: scaleIfcOpacity,
        colors: {
            bgLight: 0xf4f5f8,
            bgDark: 0x0a0d14,
            gridLight: 0xd8dbe2,
            gridDark: 0x222a38,
            highlight: 0x3b82f6
        }
    };
})(window);
