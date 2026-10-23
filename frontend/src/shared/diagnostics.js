(function (ns) {
    function Diagnostic(level, title, detail, ref) {
        this.level = level || 'info';
        this.title = title || 'Notice';
        this.detail = detail || '';
        this.ref = ref || null;
    }

    function add(list, level, title, detail, ref) {
        list.push(new Diagnostic(level, title, detail, ref));
        return list;
    }

    ns.core.Diagnostic = Diagnostic;
    ns.core.addDiagnostic = add;
    // Only diagnostic metadata crosses workers/downloads; never attach model data.
    ns.core.failure = function (error, context) {
        context = context || {};
        error = error || {};
        return {
            kind: 'conversion-failure',
            name: error.name || 'Error',
            message: error.message || String(error),
            stack: error.stack || '',
            stage: error.stage || context.stage || 'conversion',
            requestId: error.requestId == null ? (context.requestId == null ? null : context.requestId) : error.requestId,
            jobId: error.jobId || context.jobId || null,
            entityId: error.entityId == null ? null : error.entityId
        };
    };
    ns.core.atStage = function (stage, work) {
        function annotate(error) { if (!error.stage) error.stage = stage; throw error; }
        try {
            var result = work();
            return result && typeof result.then === 'function' ? result.catch(annotate) : result;
        } catch (error) { return annotate(error); }
    };
})(window.IfcFds);
