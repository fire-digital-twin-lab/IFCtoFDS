(function (ns) {
    ns.api.artifacts = {
        optionalJson: function (url) {
            return ns.api.request(url).then(function (response) { return response.ok ? response.json() : null; });
        },
        blob: function (url, options) {
            return ns.api.request(url, options).then(function (response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.blob();
            });
        }
    };
})(window.IfcFds);
