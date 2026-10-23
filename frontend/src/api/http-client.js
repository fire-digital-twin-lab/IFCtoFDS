(function (ns) {
    ns.api = ns.api || {};

    function getAuthHeaders(extraHeaders) {
        var headers = Object.assign({}, extraHeaders || {});
        var key = (typeof window !== 'undefined' && window.IFCFDS_API_KEY) || '';
        try { key = (window.localStorage && window.localStorage.getItem('ifcfds_api_key')) || key; } catch (_) { /* Storage may be disabled. */ }
        if (key) headers['x-api-key'] = key;
        return headers;
    }

    function request(url, options) {
        options = options || {};
        options.headers = getAuthHeaders(options.headers);
        return fetch(url, options);
    }

    function response(res) {
        return res.json().then(function (data) {
            if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
            return data;
        });
    }

    ns.api.getAuthHeaders = getAuthHeaders;
    ns.api.request = request;
    ns.api.response = response;
})(window.IfcFds);
