(function (ns) {
    ns.core = ns.core || {};
    ns.core.createLifecycle = function () {
        var cleanups = [], closed = false;
        return {
            own: function (cleanup) {
                if (typeof cleanup !== 'function') return cleanup;
                if (closed) cleanup(); else cleanups.push(cleanup);
                return cleanup;
            },
            listen: function (target, name, handler, options) {
                if (!target || closed) return;
                target.addEventListener(name, handler, options);
                cleanups.push(function () { target.removeEventListener(name, handler, options); });
            },
            destroy: function () {
                if (closed) return;
                closed = true;
                cleanups.splice(0).reverse().forEach(function (cleanup) { cleanup(); });
            }
        };
    };
})((typeof window !== 'undefined' ? window : globalThis).IfcFds = (typeof window !== 'undefined' ? window : globalThis).IfcFds || {});
