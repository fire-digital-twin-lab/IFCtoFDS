(function (ns) {
    'use strict';
    // Upload the File directly: no whole-file ArrayBuffer, STEP string or legacy parse.
    var active = null;
    function request(url, options) {
        options = options || {};
        options.headers = ns.verified.getAuthHeaders(options.headers);
        return fetch(url, options);
    }
    async function response(res) {
        if ((res.headers.get('content-type') || '').indexOf('application/json') < 0) {
            throw new Error('Local IFC backend is unavailable. Start the Python backend and open http://127.0.0.1:8000.');
        }
        var data = await res.json();
        if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
        return data;
    }
    function abortError() { return new DOMException('Preview cancelled', 'AbortError'); }
    ns.ifc.backendPreview = {
        cancel: function () {
            if (!active) return;
            active.controller.abort();
            if (active.id) request('/api/jobs/' + active.id + '/cancel', {method:'POST'}).catch(function () {});
            active = null;
        },
        load: async function (file, viewer, onProgress) {
            this.cancel();
            if (location.protocol === 'file:') throw new Error('Large IFC preview requires the local backend. Open http://127.0.0.1:8000 and select this file again.');
            var run = {controller:new AbortController(), id:null}; active = run;
            var signal = run.controller.signal, data = new FormData(); data.append('file', file);
            try {
                onProgress(0.02, 'Uploading IFC to local geometry worker…');
                // Keep the submission alive so cancellation can delete a job even
                // if the user changes files just before its ID is returned.
                var job = await response(await request('/api/preview-jobs', {method:'POST', body:data}));
                run.id = job.id;
                if (signal.aborted) {
                    await request('/api/jobs/' + run.id + '/cancel', {method:'POST'});
                    throw abortError();
                }
                while (job.state !== 'COMPLETED') {
                    if (signal.aborted) throw abortError();
                    if (['FAILED','CANCELLED','TIMED_OUT'].indexOf(job.state) >= 0) throw new Error(job.error || job.state);
                    var p = job.progress || {}, ratio = p.total ? p.completed / p.total : 0;
                    onProgress(0.1 + 0.55 * ratio, (p.stage || job.state) + (p.total ? ' ' + p.completed + '/' + p.total : ''));
                    await new Promise(function (resolve) { setTimeout(resolve, 500); });
                    job = await response(await request('/api/jobs/' + run.id, {signal:signal}));
                }
                var result = await response(await request('/api/jobs/' + run.id + '/result', {signal:signal}));
                var index = await response(await request(result.artifacts.geometry.url, {signal:signal}));
                var entries = Object.values(index.elements);
                var model = {filename:file.name, backendPreview:true, bounds:result.bounds, diagnostics:[],
                    inventorySummary:{total_elements:result.total_elements, sources:result.sources, storey_references:result.storeys},
                    storeys:result.storeys, elements:entries.map(function (entry) {
                        var cls = (ns.ifc && ns.ifc.IfcMeta && typeof ns.ifc.IfcMeta.classifyType === 'function')
                            ? ns.ifc.IfcMeta.classifyType(entry.ifc_type)
                            : null;
                        var nonConvertible = /^(IFCSPACE|IFCOPENINGELEMENT|IFCRAILING|IFCANNOTATION|IFCGRID)$/i.test(entry.ifc_type || '');
                        var isConvertible = cls ? cls.convertible : !nonConvertible;
                        var isSolid = cls ? cls.exportAsSolid : (isConvertible && !/^(IFCWINDOW|IFCDOOR)$/i.test(entry.ifc_type || ''));
                        var role = cls ? cls.fdsRole : (/^(IFCWINDOW|IFCDOOR)$/i.test(entry.ifc_type || '') ? 'opening' : (isConvertible ? 'solid' : 'ignore'));
                        return {entityKey:entry.entity_key, sourceId:entry.source_id, stepId:entry.step_id,
                            globalId:entry.global_id, name:entry.name, ifcType:entry.ifc_type,
                            mepCategory:entry.mep_category, systemNames:entry.system_names,
                            storey:entry.storey, bounds:entry.bounds,
                            convertible: isConvertible,
                            exportAsSolid: isSolid,
                            canExportAsSolid: isConvertible,
                            fdsRole: role,
                            conversionNote: cls ? cls.note : (isConvertible ? 'Converted by default.' : 'Excluded or reference.'),
                            raw:entry};
                    })};
                viewer.loadIfcModel({elements:[], bounds:result.bounds});
                await viewer.loadBackendPreview(index, run.id, signal, function (done, total) {
                    onProgress(0.65 + 0.35 * done / Math.max(1,total), 'Loading geometry ' + done + '/' + total);
                });
                model.diagnostics.push(new ns.core.Diagnostic('info', 'Backend source preview',
                    result.rendered_elements + ' source shapes loaded; ' + result.failed_elements +
                    ' shapes unavailable. Verification NOT RUN. Use Verified Mapping for FDS export. Edges are built on selection.'));
                return model;
            } catch (error) {
                run.controller.abort();
                if (run.id) request('/api/jobs/' + run.id + '?purge=true', {method:'DELETE'}).catch(function () {});
                throw error;
            } finally { if (active === run) active = null; }
        }
    };
})(window.IfcFds);
