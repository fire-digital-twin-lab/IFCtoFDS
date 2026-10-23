(function (ns) {
    ns.api.geometry = {
        readIndex: async function (url, signal) {
            var response = await ns.api.request(url, {signal: signal});
            if (!response.ok) throw new Error('Geometry index unavailable');
            return response.json();
        },
        readPayload: async function (indexUrl, reference, entityKey, signal) {
            var url = indexUrl.replace(/\/artifacts\/geometry$/, '/geometry/' + reference.payload);
            var response = await ns.api.request(url, {signal: signal});
            if (!response.ok) throw new Error('Geometry payload unavailable: ' + entityKey);
            return response.arrayBuffer();
        },
        readPreviewBatch: async function (jobId, group, expectedBytes, signal) {
            var endpoint = group.length === 1 && expectedBytes > 16 * 1024 * 1024
                ? '/geometry/' + group[0].mesh.payload
                : '/geometry-batch?' + group.map(function (entry) { return 'payloads=' + entry.mesh.payload; }).join('&');
            var response = await ns.api.request('/api/jobs/' + jobId + endpoint, {signal: signal});
            if (!response.ok) throw new Error('Geometry batch unavailable');
            return response.arrayBuffer();
        }
    };
})(window.IfcFds);
