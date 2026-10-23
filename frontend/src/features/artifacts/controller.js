(function (ns) {
    ns.app = ns.app || {};
    ns.features = ns.features || {};
    ns.features.artifacts = ns.features.artifacts || {};
    ns.features.artifacts.createArtifactController = function (dependencies) {
    var life = ns.core.createLifecycle();

    var state = dependencies.state;
    function hideLoading() { return dependencies.hideLoading.apply(null, arguments); }
    function showLoading() { return dependencies.showLoading.apply(null, arguments); }
    function downloadText(fileName, text) {
        var els = dependencies.getElements();
        var blob = new Blob([text], { type: 'text/plain' });
        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }
    var bound = false;
    function bind() {
        if (bound) return;
        bound = true;
        var els = dependencies.getElements();
        life.listen(els.saveFds, 'click', function () {
            if (!state.generatedFdsText || !state.generatedFdsName) return;
            downloadText(state.generatedFdsName, state.generatedFdsText);
        });

        if (els.saveManifest) {
            life.listen(els.saveManifest, 'click', function (e) {
                e.preventDefault();
                if (state.lastManifest) {
                    var base = ((state.lastManifest || {}).source_filename || state.ifcFileName || 'ifc_model').replace(/\.[^.]+$/, '').replace(/[^\w.-]+/g, '_');
                    downloadText(base + '_manifest.json', JSON.stringify(state.lastManifest, null, 2));
                    return;
                }
                if (state.lastArtifactLinks && state.lastArtifactLinks.manifest && state.lastArtifactLinks.manifest.url) {
                    var authH = (ns.verified && typeof ns.verified.getAuthHeaders === 'function') ? ns.verified.getAuthHeaders() : {};
                    ns.api.request(state.lastArtifactLinks.manifest.url, { headers: authH })
                        .then(function (r) { return r.ok ? r.json() : null; })
                        .then(function (data) {
                            if (data) {
                                state.lastManifest = data;
                                var base = (data.source_filename || state.ifcFileName || 'ifc_model').replace(/\.[^.]+$/, '').replace(/[^\w.-]+/g, '_');
                                downloadText(base + '_manifest.json', JSON.stringify(data, null, 2));
                            }
                        })
                        .catch(function (err) { console.error('Download Manifest failed:', err); });
                }
            });
        }

        if (els.saveProcessed) {
            life.listen(els.saveProcessed, 'click', function () {
                var processed = ns.ifc.ProcessedFile;
                if (!processed || !state.ifcModel || !state.ifcModel.elements || !state.ifcModel.elements.length) return;
                showLoading('Saving processed file', 'Serializing…');
                // Defer to next tick so the bar paints before the (potentially long)
                // JSON.stringify pass on the structured-clone payload.
                setTimeout(function () {
                    try {
                        var text = processed.serialize(state.ifcModel, state.lastDisplayMeshes);
                        var base = (state.ifcModel.fileName || 'ifc_model').replace(/\.[^.]+$/, '').replace(/[^\w.-]+/g, '_');
                        downloadText(base + processed.EXTENSION, text);
                    } catch (err) {
                        console.warn('processed-file save failed:', err);
                    }
                    hideLoading();
                }, 0);
            });
        }


    }

    return {downloadText: downloadText, bind: bind, destroy: function () { life.destroy(); }};
    };
})(window.IfcFds);
